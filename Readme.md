🚀 PROYECTO: ROCKY (Phase 1: Eridani) - Master Blueprint v2.0
"Erid-fist-bump. 👊" - Documento de Arquitectura y Especificaciones de Ingeniería.

1. Visión del Proyecto
Rocky es un asistente de ingeniería para Linux diseñado bajo el principio de Cero-VRAM local y Alta Resiliencia. Actúa como un "Kernel de Inteligencia" que orquesta telemetría, automatización del OS y servicios de terceros (Spotify, Google Calendar) sin parasitar los recursos del PC local, dejando la memoria libre para cargas de trabajo pesadas de desarrollo (SaaS, simulaciones, compilación).

2. Requisitos del Sistema y Stack Tecnológico
2.1. Backend de Sistema y UI Container (Rust / Tauri)
Rol: Seguridad perimetral, gestión de ventana nativa y telemetría de bajo nivel del SO.

Lenguaje: Rust.

Crates Clave:

tauri: Gestión IPC (Inter-Process Communication).

sysinfo: Lectura directa de hardware (CPU, RAM, Temperaturas).

uuid: Generación de tokens efímeros para seguridad.

tokio: Runtime asíncrono para el servidor de telemetría.

2.2. Núcleo Cognitivo y Controlador (Python)
Rol: Cerebro lógico, procesamiento de voz, NLP y ejecución determinista de herramientas.

Lenguaje: Python 3.11+.

Librerías Clave:

FastAPI + Uvicorn: Servidor de WebSockets.

Groq: Inferencia ultrarrápida Llama-3 y Whisper (STT).

Pydantic: Validación estricta de esquemas y contratos de datos.

Tenacity: Gestión de reintentos y resiliencia de red (Circuit breakers).

edge-tts: Síntesis de voz (Azure Neural) sin consumo de GPU local.

spotipy: Control de la API de Spotify.

google-api-python-client & google-auth: Integración con Google Calendar.

sounddevice & numpy: Captura de buffers de audio locales para el flujo de voz.

2.3. Interfaz de Usuario (Next.js)
Rol: Visualización de telemetría y consola de interacción manual.

Framework: Next.js 14/15 (App Router).

Estética: Tailwind CSS (Diseño terminal/industrial), Lucide React.

3. Arquitectura del Flujo de Voz (Voice-to-Command)
El audio no satura la memoria. Se procesa así:

Captura (Python): El módulo infrastructure/audio/capture.py escucha mediante un atajo global de teclado (ej. Super + Espacio). Graba un buffer de audio en memoria (sin escribir a disco duro para evitar desgaste del SSD).

Transcripción (Groq STT): El buffer de bytes se envía a la API de Whisper en Groq. Retorna texto en milisegundos.

Parseo y Despacho: El texto entra al intent_parser.py, que usa Llama-3 (vía Groq) para extraer un JSON con la intención. El tool_dispatcher.py ejecuta la acción.

4. Blueprint de Directorios Estricto (Separation of Concerns)
Plaintext
rocky/
├── rocky-engine/               # Capa de Inteligencia y Control (Python)
│   ├── src/
│   │   ├── api/                # Protocolos y Seguridad
│   │   │   ├── middleware.py   # Validación del ROCKY_AUTH_TOKEN
│   │   │   └── ws_handler.py   # Gestión asíncrona de WebSockets
│   │   ├── domain/             # Modelos de Datos (Independientes del framework)
│   │   │   ├── interfaces.py   # Clases Base (OSController, BaseTool)
│   │   │   └── schemas.py      # Modelos Pydantic (Intenciones, Telemetría)
│   │   ├── infrastructure/     # Conexión con el Mundo Exterior
│   │   │   ├── adapters/       # OS (x11_adapter.py, wayland_adapter.py)
│   │   │   ├── audio/          # Flujo de Voz (capture.py, tts_engine.py)
│   │   │   ├── clients/        # Integraciones con retries (Tenacity)
│   │   │   │   ├── groq_client.py
│   │   │   │   ├── spotify_client.py
│   │   │   │   └── gcalendar_client.py
│   │   │   └── logger.py       # Configuración de Structlog (Logs en JSON)
│   │   ├── core/               # Lógica de Orquestación (Dividida para escalabilidad)
│   │   │   ├── intent_parser.py    # LLM traduce texto a un Schema estructurado
│   │   │   └── tool_dispatcher.py  # Ejecuta la herramienta según el Schema
│   │   └── main.py             # Entry point FastAPI, inyección de dependencias
│   ├── tests/                  # Cobertura
│   │   ├── unit/               # Mocks de Groq/Spotify y tests de Pydantic
│   │   └── integration/        # Tests del WebSocket local
│   ├── pytest.ini
│   └── requirements.txt
├── rocky-ui/                   # Frontend y Runtime (Tauri + Next.js)
│   ├── src-tauri/              # Backend Rust
│   │   ├── src/
│   │   │   ├── main.rs         # Lógica de arranque, generación UUID
│   │   │   └── telemetry.rs    # Bucle de lectura hardware (sysinfo)
│   │   └── Cargo.toml
│   ├── src/                    # App Next.js
│   │   ├── components/         # Widgets aislados (StatsChart, SpotifyPlayer)
│   │   ├── hooks/              # useRockySocket (Conexión + Reintentos)
│   │   └── lib/                # Utilidades de frontend
│   ├── package.json
│   └── tauri.conf.json
├── deploy/                     # Infraestructura local
│   ├── rocky-core.service      # Systemd daemon
│   └── setup_env.sh            # Script de inicialización
└── .env.example                # Plantilla de secretos (Obligatoria)
5. Diccionario de Variables de Entorno (.env.example)
La configuración debe ser explícita para evitar fallos silenciosos.

Fragmento de código
# ==========================================
# ROCKY - VARIABLES DE ENTORNO (Phase 1)
# ==========================================

# 1. Seguridad IPC (Inyectado dinámicamente por Rust en producción, manual en dev)
ROCKY_AUTH_TOKEN=dev_secret_token_12345

# 2. IA Inferencia y Voz (Groq)
GROQ_API_KEY=gsk_tullaveaqui...

# 3. Integración Spotify
SPOTIFY_CLIENT_ID=tu_client_id
SPOTIFY_CLIENT_SECRET=tu_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback

# 4. Integración Google Calendar (Path al JSON de credenciales de Google Cloud)
GOOGLE_APPLICATION_CREDENTIALS=/ruta/absoluta/a/tu/credentials.json

# 5. Sistema y Observabilidad
ROCKY_LOG_LEVEL=INFO # Opciones: DEBUG, INFO, WARNING, ERROR
XDG_SESSION_TYPE=x11 # o wayland, para el adapter correcto
6. Línea de Tiempo Realista (Ejecución "Tracer Bullet")
Hemos ajustado el cronograma duplicando el tiempo para acomodar la complejidad real del IPC y delegando la IA hasta asegurar la estabilidad estructural.

Milestone 1: El Hilo Conductor (Semana 1-2)
Objetivo: Un pipeline de telemetría inquebrantable sin IA.

Día 1-3: Setup Tauri + Rust. Generación de Token Efímero y lectura básica de sysinfo.

Día 4-7: Setup FastAPI. Middleware de autenticación estricta validando el token de Rust.

Día 8-10: UI en Next.js conecta al WebSocket y renderiza gráficas de RAM/CPU en tiempo real.

Día 11-14: Refactorización, manejo de desconexiones (reconexión automática del frontend) y configuración del logger JSON (structlog).

Milestone 2: Sentidos y Voz (Semana 3)
Objetivo: Capacidad de escuchar y hablar de forma nativa.

Día 15-17: Implementación de infrastructure/audio/capture.py. Grabar audio temporalmente mediante atajo de teclado.

Día 18-21: Implementación de edge-tts para que Rocky notifique por voz cuando la RAM supere el 90%.

Milestone 3: Cerebro y Agentes (Semana 4-5)
Objetivo: Integración con Groq y ejecución de herramientas de terceros.

Día 22-25: Integración de Whisper (para STT) y Llama-3 en intent_parser.py para estructurar JSONs de acciones.

Día 26-30: Desarrollo del spotify_client.py y gcalendar_client.py con Tenacity para asegurar la resiliencia de la red.

Día 31-35: Pruebas de integración. Rocky recibe comando de voz, transcribe, parsea intención y reproduce música en Spotify de forma determinista.

7. README.md Oficial del Repositorio
Markdown
# 🪨 ROCKY: Engineering Assistant & Telemetry Core

Rocky es un asistente personal nativo para Linux diseñado para ingenieros de software. Construido bajo el principio de **Cero-VRAM local**, Rocky utiliza un modelo de "Inferencia Externa y Ejecución Local". Actúa como un daemon de bajo consumo que orquesta telemetría, scripts de sistema y APIs de terceros sin ralentizar la estación de trabajo.

## 🏗 Arquitectura de Tres Capas
1. **Rust (Tauri):** Frontera de seguridad (Token efímero), renderizado webview ligero y recolección de métricas del hardware vía `sysinfo`.
2. **Python (FastAPI):** Núcleo cognitivo. Maneja WebSockets, procesa audio local, interactúa con la API de Groq (Llama-3/Whisper) y despacha intenciones (Spotify, OS Tools).
3. **Next.js:** Interfaz industrial de alta reactividad.

## ✨ Funcionalidades Core (Phase 1)
- **Seguridad IPC Estricta:** Handshake criptográfico en cada arranque entre Rust y Python. Ningún proceso externo puede inyectar comandos.
- **Telemetría Proactiva:** Monitoreo en background con alertas de voz naturales (`edge-tts`) para umbrales críticos de CPU/RAM.
- **Resiliencia de Red:** Tolerancia a fallos en llamadas a APIs externas mediante decoradores `Tenacity` (Circuit breaking / Exponential Backoff).
- **Separation of Concerns:** Despliegue modular. El parseo de lenguaje natural (`intent_parser.py`) está estrictamente separado de la ejecución de código (`tool_dispatcher.py`).

## ⚙️ Desarrollo Local
1. Instala dependencias del sistema: `sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev portaudio19-dev` (portaudio es requerido para PyAudio).
2. Inicia el entorno Python: `cd rocky-engine && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
3. Configura el `.env` guiándote por `.env.example`.
4. Corre el proyecto en modo Dev (Rust levantará Next.js): `cd rocky-ui && npm run tauri dev`.
8. Prompt de Inicialización Definitivo (Para entregar a Cursor)
Copia exactamente este texto y dáselo a Cursor (o tu LLM de código) como la instrucción maestra o colócalo en tu archivo rules de Cursor:

"Actúa como un Ingeniero de Software Staff experto en sistemas distribuidos locales. Estamos construyendo 'ROCKY', un asistente para Linux dividido en un contenedor Tauri (Rust + Next.js) y un backend de control (Python/FastAPI).

REGLAS INMUTABLES DE DESARROLLO:

Rigor de Tipado: Toda la comunicación vía WebSocket y los parseos del LLM deben estar blindados por esquemas Pydantic en Python y TypeScript en el frontend. Si no hay contrato de datos, no se escribe lógica.

Seguridad Zero-Trust Local: Python NO acepta conexiones WebSocket que no posean el ROCKY_AUTH_TOKEN inyectado por Rust en el arranque.

No uses print(): Importa y utiliza structlog en Python para emitir logs en formato JSON.

Resiliencia por defecto: Toda llamada a APIs de terceros (Groq, Spotify, Google) DEBE estar decorada con tenacity para implementar reintentos con backoff exponencial. No asumas que la red funciona.

Separation of Concerns: El orquestador no hace el trabajo. intent_parser.py solo convierte texto a un Schema Pydantic validado. tool_dispatcher.py recibe ese Schema y ejecuta el adaptador correspondiente. Mantén los archivos pequeños y específicos.

NUESTRA PRIMERA TAREA (Tracer Bullet): > Ignora temporalmente la IA y la voz. Vamos a construir el pipeline de telemetría de punta a punta. Crea la estructura de carpetas rocky-ui/src-tauri y genera el código en Rust (main.rs y telemetry.rs) para: 1. Generar un UUID (Auth Token), 2. Leer la RAM/CPU cada 1000ms usando la crate sysinfo, y 3. Prepararse para enviar este token al proceso de Python."