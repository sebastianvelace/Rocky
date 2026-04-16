import logging
import os
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger("rocky.security")


class RockySecurity:
    """Valida handshake WebSocket contra ROCKY_AUTH_TOKEN."""

    def __init__(self, env_var: str = "ROCKY_AUTH_TOKEN") -> None:
        self.env_var = env_var

    def _expected_token(self) -> str:
        token = os.getenv(self.env_var, "").strip()
        if not token:
            raise RuntimeError(f"Missing required env var: {self.env_var}")
        return token

    def validate_token(self, received_token: Optional[str]) -> bool:
        if not received_token:
            return False
        return received_token == self._expected_token()

    async def validate_websocket(self, websocket: WebSocket) -> bool:
        received_token = (
            websocket.headers.get("x-rocky-auth-token")
            or websocket.query_params.get("token")
        )

        is_valid = self.validate_token(received_token)
        if not is_valid:
            logger.warning("Handshake denied: invalid ROCKY_AUTH_TOKEN")
        else:
            logger.info("Handshake accepted: token validated")
        return is_valid
