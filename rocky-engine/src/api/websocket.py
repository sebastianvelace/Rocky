"""Endpoint WebSocket: recepción, autenticación y despacho al orquestador."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from src.api.middleware import RockySecurity
from src.orchestrator import RockyOrchestrator

logger = logging.getLogger("rocky.ws")


def create_ws_router(security: RockySecurity, orchestrator: RockyOrchestrator) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        if not await security.validate_websocket(websocket):
            await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()
        logger.info("WebSocket connected")

        try:
            while True:
                payload = await websocket.receive_text()
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError as exc:
                    logger.error("[DATA] JSON inválido: %s", exc)
                    continue

                await orchestrator.handle_message(websocket, data)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")

    return router
