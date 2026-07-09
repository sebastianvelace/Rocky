"""Herramientas deterministas ejecutables por el ToolDispatcher."""

from src.core.tools.gcalendar import CalendarTodayTool
from src.core.tools.local_workspace import LocalWorkspaceSearchTool
from src.core.tools.spotify import SpotifyNextTool, SpotifyPauseTool, SpotifyPlayTool
from src.core.tools.system import SystemDiagnoseTool, SystemStatusTool, SystemTopTool
from src.core.tools.web_research import WebResearchTool

__all__ = [
    "CalendarTodayTool",
    "LocalWorkspaceSearchTool",
    "SpotifyNextTool",
    "SpotifyPauseTool",
    "SpotifyPlayTool",
    "SystemDiagnoseTool",
    "SystemStatusTool",
    "SystemTopTool",
    "WebResearchTool",
]
