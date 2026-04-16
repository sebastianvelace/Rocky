//! WebSocket hacia rocky-engine (Python): telemetría JSON + reconexión.

use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use tauri::{AppHandle, Emitter};
use tokio::sync::mpsc::UnboundedReceiver;
use tokio::time::sleep;
use tokio_tungstenite::connect_async;
use tokio_tungstenite::tungstenite::client::IntoClientRequest;
use tokio_tungstenite::tungstenite::http::header::HeaderName;
use tokio_tungstenite::tungstenite::http::{HeaderValue, Request};
use tokio_tungstenite::tungstenite::Message;
use tokio_tungstenite::tungstenite::Result as WsResult;
use url::Url;

use crate::telemetry::SystemStats;

const PYTHON_WS_URL: &str = "ws://127.0.0.1:8000/ws";
const RECONNECT_SECS: u64 = 5;

/// Handshake WebSocket correcto: `into_client_request()` rellena Upgrade, Connection,
/// Sec-WebSocket-Key, Sec-WebSocket-Version, Host; luego añadimos el token Rocky.
fn build_ws_request(token: &str) -> WsResult<Request<()>> {
    let url: Url = PYTHON_WS_URL
        .parse()
        .expect("PYTHON_WS_URL is a static valid ws:// URL");

    let mut request = url.into_client_request()?;

    request.headers_mut().insert(
        HeaderName::from_static("x-rocky-auth-token"),
        HeaderValue::from_str(token)?,
    );

    Ok(request)
}

/// Mantiene la conexión con Python: reconecta cada [`RECONNECT_SECS`] si falla o se corta.
/// Recibe los mismos [`SystemStats`] que se emiten a la UI.
pub fn spawn_python_telemetry_bridge(
    auth_token: String,
    mut stats_rx: UnboundedReceiver<SystemStats>,
    mut cmd_rx: UnboundedReceiver<String>,
    app_handle: AppHandle,
) {
    tokio::spawn(async move {
        loop {
            let request = match build_ws_request(&auth_token) {
                Ok(r) => r,
                Err(e) => {
                    eprintln!("[rocky-python-ws] build request failed: {e}");
                    sleep(Duration::from_secs(RECONNECT_SECS)).await;
                    continue;
                }
            };

            match connect_async(request).await {
                Ok((ws, _response)) => {
                    eprintln!("[rocky-python-ws] connected to {PYTHON_WS_URL}");
                    let (mut write, mut read) = ws.split();

                    loop {
                        tokio::select! {
                            biased;

                            msg = read.next() => {
                                match msg {
                                    None => {
                                        eprintln!("[rocky-python-ws] server closed stream");
                                        break;
                                    }
                                    Some(Ok(Message::Close(_))) => {
                                        eprintln!("[rocky-python-ws] received Close");
                                        break;
                                    }
                                    Some(Ok(Message::Ping(p))) => {
                                        let _ = write.send(Message::Pong(p)).await;
                                    }
                                    Some(Ok(Message::Pong(_))) => {}
                                    Some(Ok(Message::Text(text))) => {
                                        let txt = text.as_str();
                                        if let Ok(value) = serde_json::from_str::<Value>(txt) {
                                            if value.get("type").and_then(|v| v.as_str())
                                                == Some("alert")
                                            {
                                                if let Err(e) =
                                                    app_handle.emit("system-alert", value)
                                                {
                                                    eprintln!(
                                                        "[rocky-python-ws] emit system-alert: {e}"
                                                    );
                                                }
                                            }
                                        }
                                    }
                                    Some(Ok(Message::Binary(_))) => {}
                                    Some(Ok(Message::Frame(_))) => {}
                                    Some(Err(e)) => {
                                        eprintln!("[rocky-python-ws] read error: {e}");
                                        break;
                                    }
                                }
                            }

                            stats = stats_rx.recv() => {
                                match stats {
                                    Some(stats) => {
                                        let json = match serde_json::to_string(&stats) {
                                            Ok(j) => j,
                                            Err(e) => {
                                                eprintln!("[rocky-python-ws] serialize: {e}");
                                                continue;
                                            }
                                        };
                                        if let Err(e) = write.send(Message::text(json)).await {
                                            eprintln!("[rocky-python-ws] send failed: {e}");
                                            break;
                                        }
                                    }
                                    None => {
                                        eprintln!("[rocky-python-ws] stats channel closed");
                                        return;
                                    }
                                }
                            }

                            cmd = cmd_rx.recv() => {
                                match cmd {
                                    Some(cmd) => {
                                        if let Err(e) = write.send(Message::text(cmd)).await {
                                            eprintln!("[rocky-python-ws] send cmd failed: {e}");
                                            break;
                                        }
                                    }
                                    None => {
                                        // Si el canal de comandos se cerró, seguimos con telemetría.
                                    }
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[rocky-python-ws] connect failed: {e}");
                }
            }

            sleep(Duration::from_secs(RECONNECT_SECS)).await;
        }
    });
}
