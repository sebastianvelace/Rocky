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
  `core/tool_dispatcher.py` (registro `BaseTool`; `system.status` determinista
  con telemetría real).
- **Resiliencia con Tenacity** — 3 reintentos con backoff exponencial en
  todas las llamadas a Groq.
- **Spotify** — `spotify.play` (busca y reproduce, o reanuda), `spotify.pause`
  y `spotify.next` con spotipy + OAuth cacheado; mensajes humanos sin
  credenciales o sin dispositivo activo.
- **Google Calendar** — `calendar.today` lista la agenda del día; soporta
  service account y OAuth de usuario (detección automática del JSON).
- **Historial persistente** — SQLite en `~/.local/share/rocky/history.db`
  (XDG); los últimos turnos se recargan al arrancar; degradación a RAM si el
  disco falla.
- **WebSocket runtime estable** — `websockets` es dependencia runtime explícita
  para que Uvicorn acepte upgrades WebSocket reales.
- **Puerto dinámico en Tauri** — la app completa asigna un puerto local libre
  para `rocky-engine`, evitando choques con otros procesos en `8000`.
- **Checks locales actualizados** — `npm run lint` ejecuta `tsc --noEmit`
  porque `next lint` ya no aplica en Next 16.
- **Top de procesos** — Rust envía rankings por CPU/RAM, la UI los muestra y
  `system.top` responde qué está consumiendo recursos con datos reales.
- **Acciones seguras sobre procesos** — la UI permite copiar PID y terminar un
  proceso con confirmación, validando nombre/PID y bloqueando procesos de
  Rocky.

## Corto plazo (siguiente iteración)

### 1. Más telemetría
Temperaturas, GPU (nvml), disco y red. El contrato `SystemTelemetry` crece con
campos opcionales para no romper la UI vieja; la UI gana una fila de tarjetas
secundarias.

### 2. Configuración desde la UI
Voz TTS, umbrales de alerta, cooldown y credenciales opcionales deberían ser
visibles/configurables sin editar archivos manualmente.

### 3. Verificación visual automatizada
Agregar una prueba de humo con Playwright para `npm run dev` que valide que la
UI demo renderiza telemetría, consola y avatar sin solapamientos obvios.

### 4. Diagnóstico accionable
Convertir el ranking de procesos en recomendaciones: detectar outliers,
comparar contra historial reciente y sugerir acciones antes de ofrecer cerrar
un proceso.

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
- El engine asume un único cliente WebSocket (el puente Rust); si algún día
  hay más, el estado del orquestador debe ser por conexión.
- Los tests de integración WebSocket usan un harness ASGI propio porque
  `fastapi.testclient`/`starlette.testclient` se queda bloqueado con WebSockets
  en las versiones actuales.
