import asyncio
from pathlib import Path

from src.core.tools.local_workspace import LocalWorkspaceSearchTool
from src.core.tools.web_research import WebResearchTool


def test_workspace_search_is_read_only_and_scoped(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "token.py").write_text("AUTH_TOKEN = 'secret'", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.txt").write_text("AUTH_TOKEN", encoding="utf-8")
    monkeypatch.setenv("ROCKY_WORKSPACE_ROOT", str(tmp_path))

    result = asyncio.run(LocalWorkspaceSearchTool().run({"query": "AUTH_TOKEN"}, None))

    assert "src/token.py" in result
    assert "node_modules" not in result


def test_web_research_can_be_disabled_without_network(monkeypatch) -> None:
    monkeypatch.setenv("ROCKY_WEB_ENABLED", "false")
    result = asyncio.run(WebResearchTool().run({"query": "actualidad"}, None))
    assert "desactivada" in result
