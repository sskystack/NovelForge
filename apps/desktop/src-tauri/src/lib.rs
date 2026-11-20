#[cfg(desktop)]
mod runtime;

#[cfg(desktop)]
use std::sync::Arc;
#[cfg(desktop)]
use tauri::Manager;

#[cfg(desktop)]
struct DesktopRuntime(Arc<runtime::Runtime>);

#[cfg(desktop)]
#[tauri::command]
fn get_runtime_info(state: tauri::State<DesktopRuntime>) -> runtime::RuntimeInfo {
    state.0.info()
}

#[cfg(desktop)]
#[tauri::command]
fn restart_runtime(state: tauri::State<DesktopRuntime>) {
    state.0.stop();
    state.0.start();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default();
    #[cfg(desktop)]
    let builder =
        builder.invoke_handler(tauri::generate_handler![get_runtime_info, restart_runtime]);
    let application = builder
        .setup(|_app| {
            #[cfg(desktop)]
            {
                let data_dir = std::env::var_os("NOVELFORGE_DATA_DIR")
                    .map(std::path::PathBuf::from)
                    .unwrap_or(_app.path().app_data_dir()?);
                std::fs::create_dir_all(&data_dir)?;
                let runtime = runtime::Runtime::new(data_dir);
                runtime.start();
                _app.manage(DesktopRuntime(runtime));
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Could not initialize NovelForge");
    application.run(|_app, _event| {
        #[cfg(desktop)]
        if matches!(
            _event,
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
        ) {
            if let Some(runtime) = _app.try_state::<DesktopRuntime>() {
                runtime.0.stop();
            }
        }
    });
}
