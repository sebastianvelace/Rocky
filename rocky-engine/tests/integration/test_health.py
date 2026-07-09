"""Readiness HTTP local: contrato usado por el bridge de Tauri."""

import httpx

from src.main import app


async def test_health_is_public_and_does_not_expose_runtime_details() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
