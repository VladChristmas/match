//! Vision-слой клиента (Этап 10): захват окна через `Windows.Graphics.Capture` (ADR-0008).
//!
//! Модуль не «парсит» чужие сайты: он делает снимок выбранного пользователем окна и
//! возвращает PNG (base64) в интерфейс. Изображение не пишется на диск; пользователь решает,
//! отправить ли кадр на сервер (`POST /api/v1/vision/observations`).

use serde::Serialize;

const MAX_FRAME_WIDTH: u32 = 1280;
const FRAME_TIMEOUT_MS: u32 = 2000;

#[derive(Debug, Clone, Serialize)]
pub struct CaptureTarget {
    pub handle: u64,
    pub title: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct CapturedFrame {
    pub width: u32,
    pub height: u32,
    pub png_base64: String,
}

fn base64_encode(data: &[u8]) -> String {
    const TABLE: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(data.len().div_ceil(3) * 4);
    for chunk in data.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = *chunk.get(1).unwrap_or(&0) as u32;
        let b2 = *chunk.get(2).unwrap_or(&0) as u32;
        let triple = (b0 << 16) | (b1 << 8) | b2;
        out.push(TABLE[((triple >> 18) & 63) as usize] as char);
        out.push(TABLE[((triple >> 12) & 63) as usize] as char);
        out.push(if chunk.len() > 1 {
            TABLE[((triple >> 6) & 63) as usize] as char
        } else {
            '='
        });
        out.push(if chunk.len() > 2 {
            TABLE[(triple & 63) as usize] as char
        } else {
            '='
        });
    }
    out
}

fn encode_png(width: u32, height: u32, rgba: &[u8]) -> Result<Vec<u8>, String> {
    let mut buffer = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut buffer, width, height);
        encoder.set_color(png::ColorType::Rgba);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().map_err(|e| e.to_string())?;
        writer.write_image_data(rgba).map_err(|e| e.to_string())?;
    }
    Ok(buffer)
}

/// Box-downscale до `MAX_FRAME_WIDTH`, заодно конвертируя BGRA → RGBA.
fn to_rgba_scaled(source: &[u8], row_pitch: usize, width: u32, height: u32) -> (u32, u32, Vec<u8>) {
    let out_width = width.clamp(1, MAX_FRAME_WIDTH);
    let scale = width as f32 / out_width as f32;
    let out_height = ((height as f32 / scale).round() as u32).max(1);
    let mut rgba = vec![0u8; (out_width * out_height * 4) as usize];

    for y in 0..out_height {
        let src_y = ((y as f32 * scale) as usize).min(height as usize - 1);
        for x in 0..out_width {
            let src_x = ((x as f32 * scale) as usize).min(width as usize - 1);
            let src = src_y * row_pitch + src_x * 4;
            let dst = ((y * out_width + x) * 4) as usize;
            rgba[dst] = source[src + 2];
            rgba[dst + 1] = source[src + 1];
            rgba[dst + 2] = source[src];
            rgba[dst + 3] = source[src + 3];
        }
    }
    (out_width, out_height, rgba)
}

#[cfg(not(windows))]
pub fn list_windows() -> Result<Vec<CaptureTarget>, String> {
    Err("vision capture is only supported on Windows".to_string())
}

#[cfg(not(windows))]
pub fn capture_window(_handle: u64) -> Result<CapturedFrame, String> {
    Err("vision capture is only supported on Windows".to_string())
}

#[cfg(windows)]
mod platform {
    use std::thread::sleep;
    use std::time::Duration;

    use windows::Graphics::Capture::{Direct3D11CaptureFramePool, GraphicsCaptureItem};
    use windows::Graphics::DirectX::Direct3D11::IDirect3DDevice;
    use windows::Graphics::DirectX::DirectXPixelFormat;
    use windows::Win32::Foundation::{HWND, LPARAM, TRUE};
    use windows::Win32::Graphics::Direct3D::D3D_DRIVER_TYPE_HARDWARE;
    use windows::Win32::Graphics::Direct3D11::{
        D3D11_CPU_ACCESS_READ, D3D11_CREATE_DEVICE_BGRA_SUPPORT, D3D11_MAP_READ,
        D3D11_MAPPED_SUBRESOURCE, D3D11_SDK_VERSION, D3D11_TEXTURE2D_DESC, D3D11_USAGE_STAGING,
        D3D11CreateDevice, ID3D11Device, ID3D11DeviceContext, ID3D11Texture2D,
    };
    use windows::Win32::Graphics::Dxgi::IDXGIDevice;
    use windows::Win32::System::WinRT::Direct3D11::{
        CreateDirect3D11DeviceFromDXGIDevice, IDirect3DDxgiInterfaceAccess,
    };
    use windows::Win32::System::WinRT::Graphics::Capture::IGraphicsCaptureItemInterop;
    use windows::Win32::System::WinRT::RoGetActivationFactory;
    use windows::Win32::UI::WindowsAndMessaging::{
        EnumWindows, GetWindowTextLengthW, GetWindowTextW, IsWindowVisible,
    };
    use windows::core::{BOOL, HSTRING, Interface};

    use super::{
        CaptureTarget, CapturedFrame, FRAME_TIMEOUT_MS, base64_encode, encode_png, to_rgba_scaled,
    };

    unsafe extern "system" fn collect_window(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let targets = unsafe { &mut *(lparam.0 as *mut Vec<CaptureTarget>) };
        if unsafe { IsWindowVisible(hwnd).as_bool() } {
            let len = unsafe { GetWindowTextLengthW(hwnd) };
            if len > 0 {
                let mut buffer = vec![0u16; len as usize + 1];
                let copied = unsafe { GetWindowTextW(hwnd, &mut buffer) };
                if copied > 0 {
                    let title = String::from_utf16_lossy(&buffer[..copied as usize]);
                    if !title.trim().is_empty() {
                        targets.push(CaptureTarget {
                            handle: hwnd.0 as u64,
                            title,
                        });
                    }
                }
            }
        }
        TRUE
    }

    pub fn list_windows() -> Result<Vec<CaptureTarget>, String> {
        let mut targets: Vec<CaptureTarget> = Vec::new();
        unsafe {
            EnumWindows(
                Some(collect_window),
                LPARAM(&mut targets as *mut _ as isize),
            )
            .map_err(|e| e.message())?;
        }
        targets.sort_by_key(|t| t.title.to_lowercase());
        targets.dedup_by_key(|t| t.handle);
        Ok(targets)
    }

    fn create_device() -> Result<ID3D11Device, String> {
        let mut device: Option<ID3D11Device> = None;
        unsafe {
            D3D11CreateDevice(
                None,
                D3D_DRIVER_TYPE_HARDWARE,
                Default::default(),
                D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                None,
                D3D11_SDK_VERSION,
                Some(&mut device),
                None,
                None,
            )
            .map_err(|e| e.message())?;
        }
        device.ok_or_else(|| "failed to create D3D11 device".to_string())
    }

    fn capture_item(hwnd: HWND) -> Result<GraphicsCaptureItem, String> {
        let class_id = HSTRING::from("Windows.Graphics.Capture.GraphicsCaptureItem");
        let interop: IGraphicsCaptureItemInterop =
            unsafe { RoGetActivationFactory(&class_id).map_err(|e| e.message())? };
        unsafe { interop.CreateForWindow(hwnd).map_err(|e| e.message()) }
    }

    type Frame = (u32, u32, Vec<u8>, usize);

    fn read_frame(
        pool: &Direct3D11CaptureFramePool,
        device: &ID3D11Device,
    ) -> Result<Frame, String> {
        let mut waited = 0;
        let frame = loop {
            match pool.TryGetNextFrame() {
                Ok(frame) => break frame,
                Err(err) => {
                    if waited >= FRAME_TIMEOUT_MS {
                        return Err(format!("no frame arrived: {}", err.message()));
                    }
                    sleep(Duration::from_millis(20));
                    waited += 20;
                }
            }
        };

        let surface = frame.Surface().map_err(|e| e.message())?;
        let access: IDirect3DDxgiInterfaceAccess = surface.cast().map_err(|e| e.message())?;
        let texture: ID3D11Texture2D = unsafe { access.GetInterface().map_err(|e| e.message())? };

        let mut desc = D3D11_TEXTURE2D_DESC::default();
        unsafe { texture.GetDesc(&mut desc) };
        let width = desc.Width;
        let height = desc.Height;

        let mut staging_desc = desc;
        staging_desc.Usage = D3D11_USAGE_STAGING;
        staging_desc.BindFlags = 0;
        staging_desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ.0 as u32;
        staging_desc.MiscFlags = 0;
        staging_desc.MipLevels = 1;
        staging_desc.ArraySize = 1;

        let mut staging: Option<ID3D11Texture2D> = None;
        unsafe {
            device
                .CreateTexture2D(&staging_desc, None, Some(&mut staging))
                .map_err(|e| e.message())?;
        };
        let staging = staging.ok_or_else(|| "failed to create staging texture".to_string())?;

        let context: ID3D11DeviceContext =
            unsafe { device.GetImmediateContext().map_err(|e| e.message())? };
        unsafe { context.CopyResource(&staging, &texture) };

        let mut mapped = D3D11_MAPPED_SUBRESOURCE::default();
        unsafe {
            context
                .Map(&staging, 0, D3D11_MAP_READ, 0, Some(&mut mapped))
                .map_err(|e| e.message())?
        };

        let row_pitch = mapped.RowPitch as usize;
        let mut pixels = vec![0u8; row_pitch * height as usize];
        unsafe {
            std::ptr::copy_nonoverlapping(
                mapped.pData as *const u8,
                pixels.as_mut_ptr(),
                pixels.len(),
            );
        }
        unsafe { context.Unmap(&staging, 0) };

        Ok((width, height, pixels, row_pitch))
    }

    pub fn capture_window(handle: u64) -> Result<CapturedFrame, String> {
        let hwnd = HWND(handle as *mut _);
        let device = create_device()?;
        let dxgi_device: IDXGIDevice = device.cast().map_err(|e| e.message())?;
        let inspectable =
            unsafe { CreateDirect3D11DeviceFromDXGIDevice(&dxgi_device).map_err(|e| e.message())? };
        let direct3d_device: IDirect3DDevice = inspectable.cast().map_err(|e| e.message())?;

        let item = capture_item(hwnd)?;
        let size = item.Size().map_err(|e| e.message())?;

        let pool = Direct3D11CaptureFramePool::CreateFreeThreaded(
            &direct3d_device,
            DirectXPixelFormat::B8G8R8A8UIntNormalized,
            2,
            size,
        )
        .map_err(|e| e.message())?;
        let session = pool.CreateCaptureSession(&item).map_err(|e| e.message())?;
        let _ = session.SetIsCursorCaptureEnabled(false);
        session.StartCapture().map_err(|e| e.message())?;

        let (width, height, pixels, row_pitch) = read_frame(&pool, &device)?;
        let _ = session.Close();

        let (out_width, out_height, rgba) = to_rgba_scaled(&pixels, row_pitch, width, height);
        let png = encode_png(out_width, out_height, &rgba)?;
        Ok(CapturedFrame {
            width: out_width,
            height: out_height,
            png_base64: base64_encode(&png),
        })
    }
}

#[cfg(windows)]
pub use platform::{capture_window, list_windows};
