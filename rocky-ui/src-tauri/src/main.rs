// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod auth_token;
mod python_bridge;
mod telemetry;

use std::time::Duration;
use std::env;

use tauri::Emitter;
use tokio::sync::mpsc;
use tokio::time::sleep;

#[tokio::main]
async fn main() {
    // 1. Generar el secreto compartido
    let token = auth_token::generate_token();
    println!("[rocky-handshake] ROCKY_AUTH_TOKEN={}", token);

    // 2. Inyectar el token en el entorno del proceso actual
    // Esto es vital para que los sub-procesos que lance Tauri lo hereden
    env::set_var("ROCKY_AUTH_TOKEN", &token);

    let auth_for_python = env::var("ROCKY_AUTH_TOKEN").expect("ROCKY_AUTH_TOKEN set at startup");

    tauri::Builder::default()
        .setup(move |app| {
            let app_handle = app.handle().clone();

            let (stats_tx, stats_rx) = mpsc::unbounded_channel();
            python_bridge::spawn_python_telemetry_bridge(
                auth_for_python,
                stats_rx,
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}