"""Política central de mínimo privilegio para herramientas de Rocky."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None


class ToolPolicy:
    """Resuelve capacidades declarativas sin dejar que el modelo las eluda."""

    _ENV_BY_CAPABILITY = {
        "workspace.read": "ROCKY_ALLOW_WORKSPACE_READ",
        "web.research": "ROCKY_WEB_ENABLED",
        "calendar.read": "ROCKY_ALLOW_CALENDAR_READ",
        "spotify.control": "ROCKY_ALLOW_SPOTIFY_CONTROL",
    }

    @staticmethod
    def _enabled(name: str, default: bool = True) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes"}

    def decide(self, capability: str) -> PolicyDecision:
        env_name = self._ENV_BY_CAPABILITY.get(capability)
        if env_name is None or self._enabled(env_name):
            return PolicyDecision(allowed=True)
        return PolicyDecision(
            allowed=False,
            reason=f"La capacidad {capability} está desactivada ({env_name}=false).",
        )
