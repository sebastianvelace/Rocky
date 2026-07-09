# Estado Operativo de Rocky

Última inspección local: 2026-07-09.

## Verificado

- Engine Python: `62 passed` con `venv/bin/python -m pytest -q`.
- Frontend: `npm run build` genera export estático correctamente.
- TypeScript: `npm run lint` / `npm run typecheck` ejecutan `tsc --noEmit`.
- Rust/Tauri: `cargo check` y `cargo test` pasan.
- WebSocket real: Uvicorn acepta `ws://127.0.0.1:<puerto>/ws` con
  `x-rocky-auth-token` y responde a telemetría con `TelemetryAck`.
- UI demo: `npm run dev` sirve la página correctamente. Si `3000` está ocupado,
  Next usa el siguiente puerto libre, por ejemplo `3002`.
- Telemetría avanzada: CPU/RAM globales más `top_cpu` y `top_ram` con procesos
  principales por consumo; visible en UI y disponible vía `system.top`.
- Acciones de procesos: copiar PID y terminar proceso desde Tauri con
  confirmación, validación de nombre/PID y protección para Rocky/engine,
  procesos de sistema/escritorio y procesos internos marcados desde Rust.
- Diagnóstico determinista: `system.diagnose` identifica CPU/RAM como cuello de
  botella y recomienda qué proceso revisar primero.
- Groq: los errores de autenticación (`401`, key inválida/sin permisos) no se
  reintentan; Rocky deshabilita el cliente en memoria y degrada a fallback
  sin saturar logs ni la API.
- Ollama: Rocky consulta modelos locales por `/api/tags`, permite seleccionar
  uno desde la UI y consume `/api/chat` por streaming NDJSON. Si Ollama está
  apagado, el selector queda recuperable y no inventa modelos.
- Investigación: `web.search` y `workspace.search` son de solo lectura, con
  límites de resultados/archivos y sin capacidad de ejecutar comandos.
- Memoria: los canales de telemetría/comandos tienen retención acotada;
  streaming, historial SQLite y chat visual también tienen límites explícitos.
- Readiness: el engine expone `GET /health` y el bridge Rust espera esta señal
  antes de iniciar el WebSocket normal. La UI muestra actividad de herramientas
  sin registrar sus argumentos.

## Correcciones Aplicadas

- `websockets` quedó como dependencia runtime. Sin eso, Uvicorn no soportaba
  upgrades WebSocket y respondía `404 Not Found` en `/ws`.
- Tauri ya no fija el engine en `8000`: reserva un puerto local libre por
  arranque y conecta el puente Rust a ese puerto.
- Los tests WebSocket ya no usan `fastapi.testclient`, porque se bloquea con
  WebSockets en las versiones actuales. Ahora prueban la app ASGI directamente.
- `npm run lint` ya no llama `next lint`, removido/obsoleto en Next 16; ahora
  ejecuta el typecheck de TypeScript.
- `tauri.conf.json` declara los íconos existentes.
- Tauri usa `127.0.0.1:3000` y limpia `.next/dev` antes de arrancar Next en
  modo desarrollo, evitando estado persistente contaminado de `localhost`.
- El puente Rust→Python reintenta rápido durante el arranque del engine y no
  registra como fallo crítico la primera conexión rechazada mientras Uvicorn
  aún inicia.

## Cómo Correr

UI demo en navegador:

```bash
cd rocky-ui
npm run dev
```

App completa:

```bash
cd rocky-engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

cd ../rocky-ui
npm install
npm run tauri dev
```

Secretos opcionales:

- `GROQ_API_KEY`: habilita Llama/Whisper reales. Sin ella hay fallback.
  Si ves `Groq deshabilitado: GROQ_API_KEY inválida o sin permisos`, reinicia
  Rocky después de corregir la key.
- `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`.
- `GOOGLE_APPLICATION_CREDENTIALS`.

## Pendientes Reales

- Verificación visual automatizada de la UI demo/app.
- Telemetría extendida: GPU, temperatura, disco y red.
- Configuración editable desde la UI.
- Health/readiness explícito del engine para sustituir el retry inicial por
  una comprobación formal.
- Wake word y modo tray.
- Empaquetado instalable; no es prioridad mientras sea de uso personal.
