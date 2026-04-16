import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status

from src.api.middleware import RockySecurity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Rocky Handshake Backend")
security = RockySecurity()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    is_valid = await security.validate_websocket(websocket)
    if not is_valid:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    logging.getLogger("rocky.ws").info("WebSocket connected")

    try:
        while True:
            payload = await websocket.receive_text()
            await websocket.send_text(f"ack:{payload}")
    except WebSocketDisconnect:
        logging.getLogger("rocky.ws").info("WebSocket disconnected")
