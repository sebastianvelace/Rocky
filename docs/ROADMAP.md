# 🗺️ ROADMAP de Rocky

Caminos posibles a partir del estado actual. Ordenados por relación
valor/esfuerzo, con notas de diseño para cuando se aborden.

## ✅ Hecho (antes en este roadmap)

- **Streaming de respuestas del LLM** — deltas `ChatEvent(partial:true)` por
  el WebSocket; evento final con el texto completo; la UI escribe en vivo.
- **Atajo global de teclado** — Super+Espacio vía
  `tauri-plugin-global-shortcut`, con fallback Ctrl+Alt+Espacio.
- **Intent parser + tool dispatcher** — `core/intent_parser.py`
  (llama-3.1-8b-instant, JSON mode, degradación a chat) +
  `core/tool_dispatcher.py` (registro `BaseTool`; primera herramienta:
  `system.status` determinista con telemetría real).
- **Resiliencia con Tenacity** — 3 reintentos con backoff exponencial en
  todas las llamadas a Groq.

## Corto plazo (siguiente iteración)

- **Spotify** — `spotify.play` (busca y reproduce, o reanuda), `spotify.pause`
  y `spotify.next` con spotipy + OAuth cacheado; mensajes humanos sin
  credenciales o sin dispositivo activo.
- **Google Calendar** — `calendar.today` lista la agenda del día; soporta
  service account y OAuth de usuario (detección automática del JSON).
- **Historial persistente** — SQLite en `~/.local/share/rocky/history.db`
  (XDG); los últimos turnos se recargan al arrancar; degradación a RAM si el
  disco falla.

- **Contexto de procesos** — Rust envía el top de procesos (agregados por
  nombre, CPU normalizada por núcleos); herramienta determinista
  `system.top`; el chat libre recibe los 3 más pesados en contexto; panel
  de procesos en vivo en la UI.

## Corto plazo (siguiente iteración)

### 8. Más telemetría
Temperaturas, GPU (nvml), disco y red. El contrato `SystemTelemetry` crece con
campos opcionales para no romper la UI vieja; la UI gana una fila de tarjetas
secundarias.

## Largo plazo / ideas

- **Wake word** ("Rocky…") con un detector ligero local (openWakeWord) — ojo
  con el principio Cero-VRAM: elegir modelo de CPU pequeño.
- **Adapters X11/Wayland** para automatización del OS (ventanas, workspaces,
  portapapeles) como herramientas del dispatcher.
- **Modo tray**: Rocky minimizado a la bandeja del sistema, solo avatar
  flotante + hotkey.
- **Panel de configuración** en la UI (voz TTS, umbrales de alerta, cooldown)
  persistido en `tauri-plugin-store`.
- **Empaquetado**: AppImage/deb con `tauri build` + sidecar de Python
  (PyInstaller) para instalar sin venv manual.

## Deuda técnica conocida

- El `TelemetryAck` por cada tick es tráfico ocioso (Rust no lo usa); se
  puede eliminar del contrato o responder 1 de cada N.
- `httpx`/TestClient emite un DeprecationWarning de Starlette (cosmético).
- El engine asume un único cliente WebSocket (el puente Rust); si algún día
  hay más, el estado del orquestador debe ser por conexión.
