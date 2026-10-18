use serde::Serialize;
use tauri::AppHandle;

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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            app_info,
            list_capture_windows,
            capture_window_frame,
            storage::load_state,
            storage::save_state,
            storage::journal_append,
            storage::journal_clear,
            storage::storage_info
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
