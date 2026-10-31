//! ADB-источник кадров и жестов (Фаза 2 лаборатории «Эмулятор и тесты», ТЗ §8.6).
//!
//! Кадр снимается с реального устройства Android через `adb exec-out screencap -p`
//! и уходит в тот же `POST /api/v1/vision/observations` (analyze=true) — Vision-цепочка
//! и цепочка решений остаются реальными. Изображение не пишется на диск: баз64 уходит
//! в интерфейс и дальше по решению пользователя (ADR-0007/0008).
//!
//! Разделение тестируемости: работа с процессом (`run_adb`) покрыта таймаутом и watchdog,
//! а чистая логика (`parse_devices`, `png_size`, `downscale_png`, `scale_rgba`) — unit-тестами
//! без устройства (CI: desktop-rust гоняет `cargo test`).

use std::io::Read;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

use serde::Serialize;

use super::vision::{CapturedFrame, MAX_FRAME_WIDTH, base64_encode, encode_png};

/// Таймаут любого вызова adb: недоступное устройство не должно вешать интерфейс.
const ADB_TIMEOUT_SECS: u64 = 20;

#[derive(Debug, Clone, Serialize)]
pub struct AdbDevice {
    pub serial: String,
    /// device | unauthorized | offline | bootloader — состояние из `adb devices`.
    pub state: String,
    pub model: Option<String>,
}

/// Разбирает вывод `adb devices -l` вне процесса (чистая функция).
pub fn parse_devices(output: &str) -> Vec<AdbDevice> {
    let mut devices = Vec::new();
    for line in output.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty()
            || trimmed.starts_with("List of devices")
            || trimmed.starts_with("* daemon")
            || trimmed.starts_with("adb:")
        {
            continue;
        }
        let mut parts = trimmed.split_whitespace();
        let Some(serial) = parts.next() else { continue };
        let Some(state) = parts.next() else { continue };
        let model = parts
            .find_map(|pair| pair.strip_prefix("model:"))
            .map(|value| value.to_string());
        devices.push(AdbDevice {
            serial: serial.to_string(),
            state: state.to_string(),
            model,
        });
    }
    devices
}

/// Размеры PNG из IHDR без декодирования картинки (чистая функция).
pub fn png_size(png: &[u8]) -> Result<(u32, u32), String> {
    const SIGNATURE: [u8; 8] = [137, 80, 78, 71, 13, 10, 26, 10];
    if png.len() < 24 {
        return Err(format!("кадр слишком мал: {} байт", png.len()));
    }
    if png[..8] != SIGNATURE {
        return Err("кадр не является PNG".to_string());
    }
    let width = u32::from_be_bytes([png[16], png[17], png[18], png[19]]);
    let height = u32::from_be_bytes([png[20], png[21], png[22], png[23]]);
    Ok((width, height))
}

/// Box-даунскейл RGBA до MAX_FRAME_WIDTH (чистая функция).
fn scale_rgba(source: &[u8], width: u32, height: u32) -> (u32, u32, Vec<u8>) {
    let out_width = width.clamp(1, MAX_FRAME_WIDTH);
    let scale = width as f32 / out_width as f32;
    let out_height = ((height as f32 / scale).round() as u32).max(1);
    let mut rgba = vec![0u8; (out_width * out_height * 4) as usize];
    for y in 0..out_height {
        let src_y = ((y as f32 * scale) as usize).min(height as usize - 1);
        for x in 0..out_width {
            let src_x = ((x as f32 * scale) as usize).min(width as usize - 1);
            let src = (src_y * width as usize + src_x) * 4;
            let dst = ((y * out_width + x) * 4) as usize;
            rgba[dst..dst + 4].copy_from_slice(&source[src..src + 4]);
        }
    }
    (out_width, out_height, rgba)
}

/// Уменьшает кадр шире MAX_FRAME_WIDTH; узкие кадры проходят без изменений (чистая функция).
pub fn downscale_png(png: &[u8]) -> Result<Vec<u8>, String> {
    let (width, _) = png_size(png)?;
    if width <= MAX_FRAME_WIDTH {
        return Ok(png.to_vec());
    }
    let mut decoder = png::Decoder::new(std::io::Cursor::new(png));
    decoder.set_transformations(png::Transformations::EXPAND | png::Transformations::STRIP_16);
    let mut reader = decoder
        .read_info()
        .map_err(|err| format!("не удалось разобрать PNG устройства: {err}"))?;
    let buffer_size = reader
        .output_buffer_size()
        .ok_or_else(|| "png: не удалось определить размер буфера".to_string())?;
    let mut buffer = vec![0u8; buffer_size];
    let info = reader
        .next_frame(&mut buffer)
        .map_err(|err| format!("не удалось декодировать PNG устройства: {err}"))?;
    let (out_width, out_height, rgba) =
        scale_rgba(&buffer[..info.buffer_size()], info.width, info.height);
    encode_png(out_width, out_height, &rgba)
}

/// Аргументы adb с учётом выбранного устройства (`-s serial` идёт перед подкомандой).
fn device_args(serial: Option<&str>) -> Vec<String> {
    let mut args: Vec<String> = Vec::new();
    if let Some(serial) = serial {
        args.push("-s".to_string());
        args.push(serial.to_string());
    }
    args
}

/// Выполняет adb с перехватом stdout и watchdog-таймаутом (процесс убивается при зависании).
fn run_adb(args: &[&str]) -> Result<Vec<u8>, String> {
    let mut command = Command::new("adb");
    command
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = command.spawn().map_err(|err| {
        format!("adb недоступен: {err}. Установите Android Platform Tools и добавьте adb в PATH.")
    })?;
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| "adb: не удалось перехватить stdout".to_string())?;
    let (sender, receiver) = mpsc::channel();
    let reader = thread::spawn(move || {
        let mut buffer = Vec::new();
        let result = stdout.read_to_end(&mut buffer);
        let _ = sender.send((buffer, result.err().map(|err| err.to_string())));
    });
    let (output, read_error) = match receiver.recv_timeout(Duration::from_secs(ADB_TIMEOUT_SECS)) {
        Ok(payload) => payload,
        Err(_) => {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!(
                "adb не ответил за {ADB_TIMEOUT_SECS} с — устройство офлайн или adb завис"
            ));
        }
    };
    let _ = reader.join();
    if let Some(err) = read_error {
        return Err(format!("adb: ошибка чтения stdout: {err}"));
    }
    let status = child.wait().map_err(|err| format!("adb: {err}"))?;
    if !status.success() {
        return Err(format!(
            "adb завершился с ошибкой (код {:?})",
            status.code()
        ));
    }
    Ok(output)
}

/// Список устройств `adb devices -l` (неподготовленные/офлайн — честно попадают в список).
pub fn list_devices() -> Result<Vec<AdbDevice>, String> {
    let output = run_adb(&["devices", "-l"])?;
    let text = String::from_utf8_lossy(&output);
    Ok(parse_devices(&text))
}

/// Кадр экрана устройства: `adb exec-out screencap -p` → PNG (base64), при ширине > 1280 — даунскейл.
pub fn screencap(serial: Option<&str>) -> Result<CapturedFrame, String> {
    let mut args = device_args(serial);
    args.push("exec-out".to_string());
    args.push("screencap".to_string());
    args.push("-p".to_string());
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let png = run_adb(&refs)?;
    if png.is_empty() {
        return Err("adb вернул пустой кадр".to_string());
    }
    let (mut width, mut height) = png_size(&png)?;
    let mut payload = png;
    if width > MAX_FRAME_WIDTH {
        payload = downscale_png(&payload)?;
        (width, height) = png_size(&payload)?;
    }
    Ok(CapturedFrame {
        width,
        height,
        png_base64: base64_encode(&payload),
    })
}

/// Тап по экрану устройства (`adb shell input tap x y`, пиксели совпадают с размерами кадра).
pub fn tap(serial: Option<&str>, x: i32, y: i32) -> Result<(), String> {
    let mut args = device_args(serial);
    args.push("shell".to_string());
    args.push("input".to_string());
    args.push("tap".to_string());
    args.push(x.to_string());
    args.push(y.to_string());
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    run_adb(&refs).map(|_| ())
}

/// Свайп по экрану устройства (`adb shell input swipe x1 y1 x2 y2 duration_ms`).
pub fn swipe(
    serial: Option<&str>,
    x1: i32,
    y1: i32,
    x2: i32,
    y2: i32,
    duration_ms: u32,
) -> Result<(), String> {
    let duration = duration_ms.clamp(1, 2000);
    let mut args = device_args(serial);
    args.push("shell".to_string());
    args.push("input".to_string());
    args.push("swipe".to_string());
    args.push(x1.to_string());
    args.push(y1.to_string());
    args.push(x2.to_string());
    args.push(y2.to_string());
    args.push(duration.to_string());
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    run_adb(&refs).map(|_| ())
}

/// Валидация keyevent-кода Android (чистая функция; поддерживаемые коды 1..=300).
pub fn validate_keycode(keycode: i32) -> Result<(), String> {
    if !(1..=300).contains(&keycode) {
        return Err(format!("некорректный keycode: {keycode}"));
    }
    Ok(())
}

/// Системная клавиша устройства (`adb shell input keyevent keycode`, BACK = 4).
pub fn key(serial: Option<&str>, keycode: i32) -> Result<(), String> {
    validate_keycode(keycode)?;
    let mut args = device_args(serial);
    args.push("shell".to_string());
    args.push("input".to_string());
    args.push("keyevent".to_string());
    args.push(keycode.to_string());
    let refs: Vec<&str> = args.iter().map(String::as_str).collect();
    run_adb(&refs).map(|_| ())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tiny_png(width: u32, height: u32) -> Vec<u8> {
        let rgba = vec![200u8; (width * height * 4) as usize];
        encode_png(width, height, &rgba).expect("encode")
    }

    #[test]
    fn parse_devices_reads_state_and_model() {
        let output = "List of devices attached\n\
             emulator-5554          device product:sdk_gphone64 model:Pixel_8 transport_id:1\n\
             10.0.0.5:5555          device model:Galaxy_S24\n\
             R5CT30ABCDE            unauthorized\n\
             offline-1              offline\n\n";
        let devices = parse_devices(output);
        assert_eq!(devices.len(), 4);
        assert_eq!(devices[0].serial, "emulator-5554");
        assert_eq!(devices[0].state, "device");
        assert_eq!(devices[0].model.as_deref(), Some("Pixel_8"));
        assert_eq!(devices[1].model.as_deref(), Some("Galaxy_S24"));
        assert_eq!(devices[2].state, "unauthorized");
        assert_eq!(devices[2].model, None);
        assert_eq!(devices[3].state, "offline");
    }

    #[test]
    fn parse_devices_ignores_noise() {
        let devices = parse_devices(
            "List of devices attached\n* daemon not running; starting now\nadb: no devices/emulators found\n\n",
        );
        assert!(devices.is_empty());
    }

    #[test]
    fn png_size_reads_ihdr() {
        let png = tiny_png(1080, 2400);
        assert_eq!(png_size(&png), Ok((1080, 2400)));
        assert!(png_size(b"not-a-png-at-all..").is_err());
        assert!(png_size(b"\x89PNG\r\n\x1a\n").is_err());
    }

    #[test]
    fn downscale_png_passes_narrow_frames_through() {
        let png = tiny_png(1080, 4);
        let scaled = downscale_png(&png).expect("downscale");
        assert_eq!(scaled, png);
        assert_eq!(png_size(&scaled), Ok((1080, 4)));
    }

    #[test]
    fn downscale_png_clamps_width() {
        let png = tiny_png(1600, 1600);
        let scaled = downscale_png(&png).expect("downscale");
        assert_eq!(png_size(&scaled), Ok((1280, 1280)));
        assert_ne!(scaled, png);
    }

    #[test]
    fn validate_keycode_rejects_unknown_codes() {
        assert_eq!(validate_keycode(4), Ok(())); // 4 = keyevent BACK
        assert!(validate_keycode(0).is_err());
        assert!(validate_keycode(301).is_err());
        assert!(validate_keycode(-1).is_err());
    }
}
