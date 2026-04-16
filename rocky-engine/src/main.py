import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.api.middleware import RockySecurity
from src.core.analyzer import SystemAnalyzer
from src.domain.models import SystemTelemetry, TelemetryAck

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Rocky Handshake Backend")
security = RockySecurity()
ws_logger = logging.getLogger("rocky.ws")
analyzer = SystemAnalyzer()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    is_valid = await security.validate_websocket(websocket)
    if not is_valid:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    ws_logger.info("WebSocket connected")

    try:
        while True:
            payload = await websocket.receive_text()
            try:
                model = SystemTelemetry.model_validate_json(payload)
            except (ValidationError, json.JSONDecodeError) as exc:
                ws_logger.error("[DATA] Validación de telemetría fallida: %s", exc)
                continue

            ws_logger.info(
                "[DATA] Telemetría validada: CPU=%s%% RAM=%s%%",
                model.cpu,
                model.ram,
            )
            alert = analyzer.analyze(model)
            ack = TelemetryAck(status="ok", cpu_received=model.cpu)
            await websocket.send_text(ack.model_dump_json())
            if alert is not None:
                await websocket.send_json(alert)
    except WebSocketDisconnect:
        ws_logger.info("WebSocket disconnected")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
