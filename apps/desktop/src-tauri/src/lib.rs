#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(desktop)]
use tauri::Manager;

#[cfg(desktop)]
use std::process::{Child, Command, Stdio};
#[cfg(desktop)]
use std::sync::Mutex;

#[cfg(desktop)]
struct ApiProcess(Mutex<Option<Child>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|_app| {
            #[cfg(desktop)]
            {
                let data_dir = _app.path().app_data_dir()?;
                std::fs::create_dir_all(&data_dir)?;
                let api_origin = "http://127.0.0.1:8765";
                let sidecar_name = if cfg!(target_os = "windows") {
                    "novelforge-api.exe"
                } else {
                    "novelforge-api"
                };
                let sidecar_path = std::env::current_exe()?
                    .parent()
                    .ok_or_else(|| std::io::Error::other("desktop executable has no parent"))?
                    .join(sidecar_name);
                let mut command = Command::new(sidecar_path);
                command
                    .env("APP_ENV", "development")
                    .env(
                        "DATABASE_URL",
                        format!("sqlite:///{}", data_dir.join("novelforge.db").display()),
                    )
                    .env("NOVELFORGE_HOST", "127.0.0.1")
                    .env("NOVELFORGE_PORT", "8765")
                    .env("SESSION_COOKIE_SECURE", "false")
                    .env("CORS_ORIGINS", "tauri://localhost,http://tauri.localhost")
                    .stdout(Stdio::null())
                    .stderr(Stdio::null());
                let child = command.spawn()?;
                _app.manage(ApiProcess(Mutex::new(Some(child))));
                _app.manage(api_origin.to_string());
            }
            Ok(())
        })
        .on_window_event(|_window, _event| {
            #[cfg(desktop)]
            {
                if let tauri::WindowEvent::Destroyed = _event {
                    if let Some(process) = _window.app_handle().try_state::<ApiProcess>() {
                        if let Ok(mut child) = process.0.lock() {
                            if let Some(child) = child.as_mut() {
                                let _ = child.kill();
                                let _ = child.wait();
                            }
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running NovelForge");
}
