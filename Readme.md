# 🪨 ROCKY — Engineering Assistant & Telemetry Core

Rocky es un asistente personal nativo para Linux, diseñado bajo el principio de
**Cero-VRAM local**: la inferencia (Llama 3.3 y Whisper vía Groq) y la síntesis
de voz (edge-tts) ocurren fuera de la máquina, dejando CPU/GPU/RAM libres para
cargas de trabajo pesadas. Localmente corre un daemon ligero que orquesta
telemetría, voz y herramientas deterministas de terceros.

> La visión completa y el cronograma original están en
> [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md). Este README describe **lo que existe
> hoy** y las decisiones de arquitectura tomadas al implementarlo.

## Estado actual (Phase 1)

Funciona de punta a punta:

- ✅ **Telemetría en tiempo real** — Rust (`sysinfo`) lee CPU/RAM y el top de
  procesos (agregados por nombre) cada segundo; la UI grafica valor, barra
  con umbral, sparkline de 60 s y panel de procesos en vivo.
- ✅ **Contexto de procesos** — "¿qué está comiendo la RAM?" lo responde la
  herramienta determinista `system.top` con datos reales, y la conversación
  libre recibe los 3 procesos más pesados en su contexto.
- ✅ **Handshake de seguridad** — Tauri genera un UUID por arranque y lo inyecta
  al engine; el WebSocket rechaza cualquier conexión sin ese token.
- ✅ **Alertas proactivas con IA** — CPU > 80 % o RAM > 90 % sostenidas 3 s
  disparan un consejo generado por Llama 3.3, mostrado en la UI y hablado por
  TTS. Cooldown de 60 s para no spamear.
- ✅ **Voz conversacional** — botón de micrófono → Whisper (Groq) →
  Llama 3.3 → respuesta en pantalla + voz. La transcripción y la respuesta se
  ven en la consola; el estado del pipeline (escuchando/pensando/hablando) se
  refleja en vivo.
- ✅ **Chat por texto con streaming** — input estilo prompt en la consola
  (Enter para enviar). La respuesta del LLM llega en deltas y se escribe en
  vivo; si escribes en vez de hablar, no reproduce audio.
- ✅ **Atajo global** — Super+Espacio (o Ctrl+Alt+Espacio si el compositor
  ya lo usa) dispara la escucha aunque la ventana no tenga el foco.
- ✅ **Intenciones y herramientas** — un modelo rápido (llama-3.1-8b-instant)
  clasifica cada mensaje: las preguntas de estado del sistema las responde
  una herramienta determinista con la telemetría real (cero LLM, cero red);
  el resto va a conversación libre. Registro extensible (`BaseTool`).
- ✅ **Spotify** — "pon música de Queen", "pausa", "siguiente" ejecutan
  acciones reales (`spotipy`, OAuth). Sin credenciales, Rocky explica cómo
  configurarlo en vez de fallar.
- ✅ **Google Calendar** — "¿qué tengo hoy?" lista la agenda del día
  (service account u OAuth de usuario, detectado automáticamente).
- ✅ **Memoria persistente** — la conversación se guarda en SQLite
  (`~/.local/share/rocky/history.db`) y los últimos turnos se recargan al
  arrancar: reiniciar Rocky ya no es amnesia total.
- ✅ **Resiliencia** — toda llamada a Groq lleva reintentos con backoff
  exponencial (Tenacity) y degrada a fallback, nunca a crash.
- ✅ **Memoria y contexto real** — Rocky recuerda los últimos turnos de la
  sesión y recibe la telemetría actual: "¿cómo va el sistema?" se responde
  con los números reales.
- ✅ **Procesos top** — Rust envía rankings de procesos por CPU/RAM; la UI los
  muestra en vivo y Rocky puede responder "qué está consumiendo memoria" con
  la herramienta determinista `system.top`.
- ✅ **Acciones seguras sobre procesos** — desde la UI puedes copiar PID o
  terminar un proceso con confirmación explícita. Rocky bloquea PIDs críticos,
  su propia app y el engine Python.
- ✅ **Diagnóstico accionable** — `system.diagnose` resume el cuello de botella
  actual y sugiere qué proceso revisar primero, sin depender del LLM.
- ✅ **Avatar animado** — Rocky respira y parpadea en reposo, emite anillos
  de sonar al escuchar, gira un anillo al pensar, mueve una boca ecualizador
  al hablar y se sacude en rojo ante una alerta. Todo SVG + CSS (respeta
  `prefers-reduced-motion`).
- 🔜 Roadmap detallado en [`docs/ROADMAP.md`](docs/ROADMAP.md): más
  telemetría (GPU/temperaturas), wake word, modo tray, empaquetado.

## Arquitectura

Tres procesos, un solo dueño de cada responsabilidad:

```
┌────────────────────────── Tauri (Rust) ──────────────────────────┐
│  · Genera ROCKY_AUTH_TOKEN (UUID) por arranque                   │
│  · Lanza rocky-engine (uvicorn) como subproceso                  │
│  · Lee CPU/RAM cada 1 s (sysinfo)                                │
│  · Puente WebSocket ↔ Python con reconexión cada 5 s             │
└──────────┬───────────────────────────────┬───────────────────────┘
   eventos Tauri                   WebSocket local dinámico
 (system-stats, system-alert,      (telemetría JSON + comandos +
  rocky-chat, voice-state)          eventos tipados de vuelta)
           │                               │
┌──────────▼──────────┐         ┌──────────▼───────────────────────┐
│  Next.js (webview)  │         │  rocky-engine (Python/FastAPI)   │
│  Dashboard + consola│         │  · Valida token (middleware)     │
│  de voz. Sin acceso │         │  · Orquestador: telemetría→      │
│  a red ni al token. │         │    analyzer→Groq, voz→STT/LLM/TTS│
└─────────────────────┘         └──────────────────────────────────┘
```

### Decisiones de arquitectura (y desviaciones del blueprint)

1. **Doble puente en lugar de UI→WebSocket directo.** El blueprint sugería que
   Next.js conectara al WebSocket. Se decidió que **solo Rust** hable con
   Python: el token jamás entra al webview (menor superficie de ataque), hay un
   único cliente que gestionar y la UI queda 100 % pasiva (solo escucha eventos
   Tauri). La reconexión vive en Rust.
2. **Logs JSON con stdlib, sin structlog.** `infrastructure/logger.py`
   implementa un `JsonFormatter` propio: mismo resultado (una línea JSON por
   evento, nivel vía `ROCKY_LOG_LEVEL`) sin una dependencia más.
3. **Voz por botón de UI y atajo global.** El disparador de voz viaja UI/Rust
   (`request_listen`) → Python (`{"action":"listen"}`). Además,
   `tauri-plugin-global-shortcut` registra Super+Espacio, con fallback a
   Ctrl+Alt+Espacio si el compositor ya ocupa el atajo.
4. **SpeechRecognition + PyAudio para captura.** Más simple que
   `sounddevice`+numpy para la fase actual (detección de silencio incluida).
   El audio se graba a un temporal y se borra inmediatamente tras transcribir.
5. **Un solo modelo de texto: `llama-3.3-70b-versatile`.** El id previo
   (`llama-3-70b-8192`) no existe en Groq y hacía que toda alerta cayera al
   mensaje de fallback en silencio.
6. **El orquestador no hace el trabajo.** `orchestrator.py` solo enruta:
   telemetría → `analyzer` (+Groq si hay alerta), `{"action":"listen"}` →
   pipeline de voz como tarea independiente (la telemetría nunca se bloquea,
   las llamadas HTTP van en `asyncio.to_thread`). Los envíos por el socket se
   serializan con un lock.
7. **Sin GROQ_API_KEY todo sigue funcionando** con respuestas de fallback: la
   resiliencia es degradación, no crash.

### Contratos de datos (WebSocket y eventos Tauri)

Todos los mensajes están blindados por Pydantic (`src/domain/models.py`) y
tipados en TypeScript (`src/hooks/useRocky.ts`).

| Dirección | Mensaje WS | Evento Tauri | Contenido |
|---|---|---|---|
| Rust → Python | `{cpu, ram}` | — | telemetría cada 1 s |
| Rust → Python | `{top_cpu, top_ram}` | — | rankings opcionales de procesos con PID, CPU, RAM y memoria |
| Rust → Python | `{"action":"listen"}` | — | iniciar pipeline de voz |
| Rust → Python | `{"action":"chat","text"}` | — | mensaje escrito por el usuario |
| Python → Rust | `TelemetryAck` | — (no llega a UI) | `{status, cpu_received}` |
| Python → Rust | `AlertEvent` | `system-alert` | `{type:"alert", level, resource, message}` |
| Python → Rust | `ChatEvent` | `rocky-chat` | `{type:"chat", role, text, partial}` — `partial:true` = delta de streaming; el evento final trae el texto completo |
| Python → Rust | `VoiceStateEvent` | `voice-state` | `{type:"voice", state, detail?}` |
| Rust → UI | — | `system-stats` | `{cpu, ram, top_cpu?, top_ram?}` |

## Estructura del repositorio

```
rocky/
├── rocky-engine/            # Núcleo cognitivo (Python 3.11+ / FastAPI)
│   ├── src/
│   │   ├── api/             # middleware.py (auth) · websocket.py (endpoint)
│   │   ├── core/            # analyzer.py (umbrales sostenidos)
│   │   ├── domain/          # models.py (contratos Pydantic)
│   │   ├── infrastructure/  # audio/ (STT, TTS) · clients/ (Groq) · logger.py
│   │   ├── orchestrator.py  # enrutamiento de mensajes y pipeline de voz
│   │   └── main.py          # entry point + inyección de dependencias
│   └── tests/               # unit/ e integration/ (pytest, 46 tests)
├── rocky-ui/                # Frontend (Tauri 2 + Next.js 16 + Tailwind 4)
│   ├── src-tauri/src/       # main.rs · telemetry.rs · python_bridge.rs · auth_token.rs
│   └── src/                 # app/ · components/ · hooks/useRocky.ts
├── scripts/                 # deploy.sh · rocky.service (systemd)
└── docs/BLUEPRINT.md        # visión y cronograma original
```

## Desarrollo local

Requisitos de sistema (Debian/Ubuntu):

```bash
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
  libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev \
  portaudio19-dev mpv
```

(`portaudio19-dev` es necesario para PyAudio/micrófono; `mpv` reproduce el TTS.)

1. **Engine Python** (el venv debe llamarse `venv`, Tauri lo busca ahí):

   ```bash
   cd rocky-engine
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Secretos**: copia `.env.example` a `rocky-engine/.env` y pon tu
   `GROQ_API_KEY`. (Sin ella, Rocky funciona con respuestas de fallback.)

3. **App completa** (Tauri lanza Next.js y el engine automáticamente en un
   puerto local libre):

   ```bash
   cd rocky-ui
   npm install
   npm run tauri dev
   ```

### Solo la UI en el navegador (modo demo)

```bash
cd rocky-ui && npm run dev
```

Fuera de Tauri la UI entra en **modo demo** con telemetría simulada (indicado
en el header) para iterar el diseño sin compilar la app nativa.

### Solo el engine (sin Tauri)

```bash
cd rocky-engine
ROCKY_AUTH_TOKEN=dev_secret_token_12345 venv/bin/python -m uvicorn src.main:app --port 8000
```

### Tests

```bash
cd rocky-engine
pip install -r requirements-dev.txt
python -m pytest
```

## Seguridad

- **Zero-trust local**: el WebSocket rechaza (código 1008) cualquier conexión
  sin el header `x-rocky-auth-token` correcto. El token es un UUID nuevo por
  arranque, generado por Rust e inyectado al subproceso Python por entorno.
- El engine escucha solo en `127.0.0.1`.
- El webview no conoce el token ni tiene acceso al engine.
- El audio del micrófono se transcribe desde un archivo temporal que se borra
  de inmediato; nada persiste en disco.
