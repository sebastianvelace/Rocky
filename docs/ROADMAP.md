# 🗺️ ROADMAP de Rocky

Caminos posibles a partir del estado actual (Phase 1 completa: telemetría,
alertas con IA, voz y chat de texto con memoria). Ordenados por relación
valor/esfuerzo, con notas de diseño para cuando se aborden.

## Corto plazo (siguiente iteración)

### 1. Streaming de respuestas del LLM
Hoy la respuesta llega completa y el typewriter la "actúa". Groq soporta
`stream=True`: enviar deltas por el WebSocket (`ChatEvent` con `partial: true`)
haría la latencia percibida casi cero y el typewriter sería real.
**Tocaría:** `groq_client` (generador), `orchestrator` (loop de deltas),
contrato `ChatEvent`, `useRocky` (append de deltas).

### 2. Atajo global de teclado (Super+Espacio)
El blueprint lo pide; hoy la voz se dispara desde la UI. Tauri tiene el plugin
oficial `tauri-plugin-global-shortcut`: registrar el atajo en Rust y llamar al
mismo `request_listen`. Cero cambios en Python.

### 3. Intent parser + tool dispatcher (el gran salto)
Separar "entender" de "ejecutar", como manda el blueprint:
- `core/intent_parser.py`: Llama 3.3 con salida JSON estricta (Pydantic
  `Intent`) — `{"tool": "spotify.play", "args": {...}}` o `{"tool": "chat"}`.
- `core/tool_dispatcher.py`: registro de herramientas (`BaseTool`), ejecuta el
  intent validado.
Con esto, "pon música" deja de ser una respuesta sarcástica y pasa a ser una
acción. El chat actual queda como herramienta por defecto (`chat`).

### 4. Resiliencia con Tenacity
Decorar las llamadas a Groq con reintentos + backoff exponencial (el blueprint
lo exige y la dependencia es pequeña). Medir: hoy un fallo cae a fallback
inmediatamente; con tenacity, 2-3 reintentos antes de rendirse.

## Medio plazo

### 5. Spotify (`infrastructure/clients/spotify_client.py`)
`spotipy` + OAuth (el redirect a `localhost:8000/callback` ya está previsto en
el `.env`). Herramientas: play/pause, siguiente, buscar y reproducir. Encaja
detrás del tool dispatcher (#3), no antes.

### 6. Google Calendar
`google-api-python-client`: "¿qué tengo hoy?" → lista de eventos en la consola
y por voz. También detrás del dispatcher.

### 7. Historial persistente y contexto del sistema
- Guardar la conversación en SQLite (`~/.local/share/rocky/history.db`) para
  que la memoria sobreviva reinicios.
- Enriquecer el contexto del LLM: top de procesos por CPU/RAM (ya que sysinfo
  los conoce) para que "¿qué está comiendo la RAM?" tenga respuesta real.

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
- `tauri.conf.json` tiene `"icon": []` — para `tauri build` hay que declarar
  los íconos (existen en `src-tauri/icons/`).
