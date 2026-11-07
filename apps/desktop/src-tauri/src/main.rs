#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

struct ApiProcess(Mutex<Option<Child>>);

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            let api_origin = "http://127.0.0.1:8765";
            let mut command = Command::new("binaries/novelforge-api");
            command
                .env("APP_ENV", "development")
                .env("DATABASE_URL", format!("sqlite:///{}", data_dir.join("novelforge.db").display()))
                .env("NOVELFORGE_HOST", "127.0.0.1")
                .env("NOVELFORGE_PORT", "8765")
                .env("SESSION_COOKIE_SECURE", "false")
                .env("CORS_ORIGINS", "tauri://localhost,http://tauri.localhost")
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            let child = command.spawn()?;
            app.manage(ApiProcess(Mutex::new(Some(child))));
            app.manage(api_origin.to_string());
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(process) = window.app_handle().try_state::<ApiProcess>() {
                    if let Ok(mut child) = process.0.lock() {
                        if let Some(child) = child.as_mut() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running NovelForge desktop");
}
