// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod auth_token;
mod python_bridge;
mod telemetry;

use std::env;
use std::net::TcpListener;
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
struct PythonBridgeControl(mpsc::Sender<String>);

const COMMAND_QUEUE_CAPACITY: usize = 32;

#[tauri::command]
fn request_listen(control: State<'_, PythonBridgeControl>) -> Result<(), String> {
    control
        .0
        .try_send(r#"{"action":"listen"}"#.to_string())
        .map_err(|_| "El engine está ocupado o desconectado; intenta de nuevo.".to_string())
}

#[tauri::command]
fn send_chat(text: String, control: State<'_, PythonBridgeControl>) -> Result<(), String> {
    let payload = serde_json::json!({ "action": "chat", "text": text });
    control
        .0
        .try_send(payload.to_string())
        .map_err(|_| "El engine está ocupado o desconectado; intenta de nuevo.".to_string())
}

#[tauri::command]
fn list_models(control: State<'_, PythonBridgeControl>) -> Result<(), String> {
    control
        .0
        .try_send(r#"{"action":"models.list"}"#.to_string())
        .map_err(|_| "El engine está ocupado o desconectado; intenta de nuevo.".to_string())
}

#[tauri::command]
fn select_model(model: String, control: State<'_, PythonBridgeControl>) -> Result<(), String> {
    let payload = serde_json::json!({ "action": "models.select", "model": model });
    control
        .0
        .try_send(payload.to_string())
        .map_err(|_| "El engine está ocupado o desconectado; intenta de nuevo.".to_string())
}

#[tauri::command]
fn terminate_process(
    pid: String,
    expected_name: String,
    engine_state: State<'_, RockyEngineProcess>,
) -> Result<String, String> {
    let raw_pid: u32 = pid.parse().map_err(|_| format!("PID inválido: {pid}"))?;

    if raw_pid <= 1 {
        return Err("No voy a terminar procesos críticos del sistema.".to_string());
    }
    if raw_pid == std::process::id() {
        return Err("No voy a terminar la propia app de Rocky.".to_string());
    }

    let engine_pid = {
        let guard = engine_state.0.lock().expect("engine mutex poisoned");
        guard.as_ref().map(|child| child.id())
    };
    if Some(raw_pid) == engine_pid {
        return Err("No voy a terminar el engine de Rocky desde el panel.".to_string());
    }

    let target_pid = sysinfo::Pid::from_u32(raw_pid);
    let mut system = sysinfo::System::new();
    system.refresh_processes(sysinfo::ProcessesToUpdate::Some(&[target_pid]), true);

    let process = system
        .process(target_pid)
        .ok_or_else(|| format!("El proceso {raw_pid} ya no existe."))?;
    let current_name = process.name().to_string_lossy().into_owned();

    if current_name != expected_name {
        return Err(format!(
            "El PID {raw_pid} ahora pertenece a '{current_name}', no a '{expected_name}'."
        ));
    }

    let mut protected_pids = vec![std::process::id()];
    if let Some(engine_pid) = engine_pid {
        protected_pids.push(engine_pid);
    }
    if let Some(reason) = telemetry::classify_process_protection(
        raw_pid,
        &current_name,
        &protected_pids,
    ) {
        return Err(format!("No voy a terminar {current_name}: {reason}."));
    }

    if process.kill() {
        Ok(format!("Proceso terminado: {current_name} ({raw_pid})."))
    } else {
        Err(format!(
            "No pude terminar {current_name} ({raw_pid}). Revisa permisos o estado del proceso."
        ))
    }
}

fn reserve_local_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}

fn spawn_rocky_engine(token: String, port: u16) -> std::io::Result<Child> {
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
        .arg(port.to_string())
        // Logs: que fluyan a la terminal principal.
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
}

#[tokio::main]
async fn main() {
    // 1. Generar el secreto compartido
    let token = auth_token::generate_token();
    println!("[rocky-handshake] token efímero generado");

    // 2. Inyectar el token en el entorno del proceso actual
    // Esto es vital para que los sub-procesos que lance Tauri lo hereden
    env::set_var("ROCKY_AUTH_TOKEN", &token);

    let auth_for_python = env::var("ROCKY_AUTH_TOKEN").expect("ROCKY_AUTH_TOKEN set at startup");
    let engine_port = reserve_local_port().expect("failed to reserve local rocky-engine port");
    let python_ws_url = format!("ws://127.0.0.1:{engine_port}/ws");
    println!("[rocky-engine] puerto local asignado: {engine_port}");

    let app = tauri::Builder::default()
        .manage(RockyEngineProcess::default())
        // Atajo global (blueprint: Super+Espacio): dispara el mismo flujo de
        // voz que el botón de la UI, aunque la ventana no tenga el foco.
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state() == tauri_plugin_global_shortcut::ShortcutState::Pressed {
                        if let Some(control) = app.try_state::<PythonBridgeControl>() {
                            if let Err(e) = control.0.try_send(r#"{"action":"listen"}"#.to_string()) {
                                eprintln!("[rocky-hotkey] no se pudo pedir escucha: {e}");
                            }
                        }
                    }
                })
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            request_listen,
            send_chat,
            list_models,
            select_model,
            terminate_process
        ])
        .setup(move |app| {
            let app_handle = app.handle().clone();

            // Orquestación: lanzar motor de Python (uvicorn) al iniciar.
            {
                let engine_state = app.state::<RockyEngineProcess>();
                match spawn_rocky_engine(token.clone(), engine_port) {
                    Ok(child) => {
                        *engine_state.0.lock().expect("engine mutex poisoned") = Some(child);
                        println!(
                            "[Orchestrator] Motor de Python lanzado en 127.0.0.1:{engine_port}."
                        );
                    }
                    Err(err) => {
                        eprintln!("[Orchestrator] Falló al lanzar el motor de Python: {err}");
                    }
                }
            }

            // Telemetría: un único snapshot actual; comandos: cola pequeña y
            // acotada. Ambas decisiones eliminan crecimiento de memoria si el
            // engine se cae o tarda en arrancar.
            let (stats_tx, stats_rx) = tokio::sync::watch::channel(telemetry::SystemStats::default());
            let (cmd_tx, cmd_rx) = mpsc::channel::<String>(COMMAND_QUEUE_CAPACITY);
            app.manage(PythonBridgeControl(cmd_tx));

            // Registrar Super+Espacio. Si el compositor ya lo usa (p. ej.
            // GNOME), se registra la alternativa Ctrl+Alt+Espacio.
            {
                use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

                let primary = Shortcut::new(Some(Modifiers::SUPER), Code::Space);
                let fallback =
                    Shortcut::new(Some(Modifiers::CONTROL | Modifiers::ALT), Code::Space);
                match app.global_shortcut().register(primary) {
                    Ok(()) => println!("[rocky-hotkey] Super+Espacio registrado"),
                    Err(primary_err) => match app.global_shortcut().register(fallback) {
                        Ok(()) => println!(
                            "[rocky-hotkey] Super+Espacio ocupado ({primary_err}); \
                             usando Ctrl+Alt+Espacio"
                        ),
                        Err(e) => {
                            eprintln!("[rocky-hotkey] sin atajo global disponible: {e}")
                        }
                    },
                }
            }
            python_bridge::spawn_python_telemetry_bridge(
                python_ws_url.clone(),
                auth_for_python,
                stats_rx,
                cmd_rx,
                app.handle().clone(),
            );

            // Loop de telemetría: UI (Tauri) + mismo JSON hacia Python (WebSocket)
            tokio::spawn(async move {
                let mut system = sysinfo::System::new();

                loop {
                    let mut protected_pids = vec![std::process::id()];
                    if let Some(engine_pid) = {
                        let engine_state = app_handle.state::<RockyEngineProcess>();
                        let guard = engine_state.0.lock().expect("engine mutex poisoned");
                        guard.as_ref().map(|child| child.id())
                    } {
                        protected_pids.push(engine_pid);
                    }
                    let stats = telemetry::collect_stats(&mut system, &protected_pids);

                    if let Err(error) =
                        app_handle.emit(telemetry::SYSTEM_STATS_EVENT, stats.clone())
                    {
                        eprintln!("[rocky-telemetry] failed to emit event: {error}");
                    }

                    stats_tx.send_replace(stats);
                    if stats_tx.is_closed() {
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
