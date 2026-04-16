// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod auth_token;
mod python_bridge;
mod telemetry;

use std::env;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use tauri::Emitter;
use tauri::Manager;
use tauri::State;
use tokio::sync::mpsc;
use tokio::time::sleep;

#[derive(Default)]
struct RockyEngineProcess(Mutex<Option<Child>>);

#[derive(Clone)]
struct PythonBridgeControl(mpsc::UnboundedSender<String>);

#[tauri::command]
fn request_listen(control: State<'_, PythonBridgeControl>) -> Result<(), String> {
    control
        .0
        .send(r#"{"action":"listen"}"#.to_string())
        .map_err(|e| e.to_string())
}

fn spawn_rocky_engine(token: String) -> std::io::Result<Child> {
    // Base fiable en runtime: carpeta `rocky-ui/src-tauri`
    // Desde ahí, el motor vive en `../../rocky-engine/`.
    let engine_dir: PathBuf = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../rocky-engine");
    let python_path = engine_dir.join("venv/bin/python3");

    Command::new(python_path)
        .current_dir(&engine_dir)
        .env("ROCKY_AUTH_TOKEN", token)
        .arg("-m")
        .arg("uvicorn")
        .arg("src.main:app")
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg("8000")
        // Logs: que fluyan a la terminal principal.
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
}

#[tokio::main]
async fn main() {
    // 1. Generar el secreto compartido
    let token = auth_token::generate_token();
    println!("[rocky-handshake] ROCKY_AUTH_TOKEN={}", token);

    // 2. Inyectar el token en el entorno del proceso actual
    // Esto es vital para que los sub-procesos que lance Tauri lo hereden
    env::set_var("ROCKY_AUTH_TOKEN", &token);

    let auth_for_python = env::var("ROCKY_AUTH_TOKEN").expect("ROCKY_AUTH_TOKEN set at startup");

    let app = tauri::Builder::default()
        .manage(RockyEngineProcess::default())
        .invoke_handler(tauri::generate_handler![request_listen])
        .setup(move |app| {
            let app_handle = app.handle().clone();

            // Orquestación: lanzar motor de Python (uvicorn) al iniciar.
            {
                let engine_state = app.state::<RockyEngineProcess>();
                match spawn_rocky_engine(token.clone()) {
                    Ok(child) => {
                        *engine_state.0.lock().expect("engine mutex poisoned") = Some(child);
                        println!("[Orchestrator] Motor de Python lanzado con éxito.");
                    }
                    Err(err) => {
                        eprintln!("[Orchestrator] Falló al lanzar el motor de Python: {err}");
                    }
                }
            }

            let (stats_tx, stats_rx) = mpsc::unbounded_channel();
            let (cmd_tx, cmd_rx) = mpsc::unbounded_channel::<String>();
            app.manage(PythonBridgeControl(cmd_tx));
            python_bridge::spawn_python_telemetry_bridge(
                auth_for_python,
                stats_rx,
                cmd_rx,
                app.handle().clone(),
            );

            // Loop de telemetría: UI (Tauri) + mismo JSON hacia Python (WebSocket)
            tokio::spawn(async move {
                let mut system = sysinfo::System::new();

                loop {
                    let stats = telemetry::collect_stats(&mut system);
                    eprintln!(
                        "[rocky-telemetry] emit {} cpu={:.1}% ram={:.1}%",
                        telemetry::SYSTEM_STATS_EVENT,
                        stats.cpu,
                        stats.ram
                    );

                    if let Err(error) =
                        app_handle.emit(telemetry::SYSTEM_STATS_EVENT, stats.clone())
                    {
                        eprintln!("[rocky-telemetry] failed to emit event: {error}");
                    }

                    if stats_tx.send(stats).is_err() {
                        eprintln!("[rocky-telemetry] python bridge channel closed");
                    }

                    sleep(Duration::from_millis(1000)).await;
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } = event {
            let engine_state = app_handle.state::<RockyEngineProcess>();
            let child = {
                let mut guard = engine_state.0.lock().expect("engine mutex poisoned");
                guard.take()
            };
            if let Some(mut child) = child {
                let _ = child.kill();
            }
        }
    });
}