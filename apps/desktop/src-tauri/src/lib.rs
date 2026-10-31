use serde::Serialize;
use tauri::AppHandle;

mod adb;
mod storage;
mod vision;

#[derive(Serialize)]
struct AppInfo {
    name: String,
    version: String,
    tauri_version: String,
    os: String,
}

#[tauri::command]
fn app_info(app: AppHandle) -> AppInfo {
    let package = app.package_info();
    AppInfo {
        name: package.name.clone(),
        version: package.version.to_string(),
        tauri_version: tauri::VERSION.to_string(),
        os: std::env::consts::OS.to_string(),
    }
}

/// Перечисляет видимые окна, доступные для наблюдения (Windows.Graphics.Capture).
#[tauri::command]
fn list_capture_windows() -> Result<Vec<vision::CaptureTarget>, String> {
    vision::list_windows()
}

/// Снимает кадр выбранного окна и возвращает PNG в base64. Изображение не сохраняется на диск.
#[tauri::command]
fn capture_window_frame(handle: u64) -> Result<vision::CapturedFrame, String> {
    vision::capture_window(handle)
}

/// Список Android-устройств (`adb devices -l`) — Фаза 2 лаборатории «Эмулятор и тесты».
#[tauri::command]
async fn adb_devices() -> Result<Vec<adb::AdbDevice>, String> {
    tauri::async_runtime::spawn_blocking(adb::list_devices)
        .await
        .map_err(|err| format!("adb_devices: {err}"))?
}

/// Кадр экрана устройства (`adb exec-out screencap -p`) → PNG в base64.
#[tauri::command]
async fn adb_screencap(serial: Option<String>) -> Result<vision::CapturedFrame, String> {
    tauri::async_runtime::spawn_blocking(move || adb::screencap(serial.as_deref()))
        .await
        .map_err(|err| format!("adb_screencap: {err}"))?
}

/// Тап по экрану устройства (`adb shell input tap x y`).
#[tauri::command]
async fn adb_tap(serial: Option<String>, x: i32, y: i32) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || adb::tap(serial.as_deref(), x, y))
        .await
        .map_err(|err| format!("adb_tap: {err}"))?
}

/// Свайп по экрану устройства (`adb shell input swipe …`).
#[tauri::command]
async fn adb_swipe(
    serial: Option<String>,
    x1: i32,
    y1: i32,
    x2: i32,
    y2: i32,
    duration_ms: Option<u32>,
) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || {
        adb::swipe(
            serial.as_deref(),
            x1,
            y1,
            x2,
            y2,
            duration_ms.unwrap_or(300),
        )
    })
    .await
    .map_err(|err| format!("adb_swipe: {err}"))?
}

/// Системная клавиша устройства (`adb shell input keyevent keycode`, BACK = 4).
#[tauri::command]
async fn adb_key(serial: Option<String>, keycode: i32) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || adb::key(serial.as_deref(), keycode))
        .await
        .map_err(|err| format!("adb_key: {err}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            app_info,
            list_capture_windows,
            capture_window_frame,
            adb_devices,
            adb_screencap,
            adb_tap,
            adb_swipe,
            adb_key,
            storage::load_state,
            storage::save_state,
            storage::journal_append,
            storage::journal_clear,
            storage::storage_info,
            storage::outbox_add,
            storage::outbox_list,
            storage::outbox_remove,
            storage::outbox_fail,
            storage::outbox_clear,
            storage::memory_add,
            storage::memory_list,
            storage::memory_get,
            storage::memory_classify,
            storage::memory_verify,
            storage::memory_correct,
            storage::memory_delete,
            storage::memory_events,
            storage::profile_save,
            storage::profile_load,
            storage::conversations_save,
            storage::conversations_load,
            storage::messages_save,
            storage::messages_load
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
