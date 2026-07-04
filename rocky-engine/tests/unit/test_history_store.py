from pathlib import Path

from src.infrastructure.history_store import HistoryStore


class TestHistoryStore:
    def test_append_and_load_roundtrip(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history.db")
        store.append("user", "hola")
        store.append("assistant", "qué tal, Sebas")

        recent = store.load_recent(10)
        assert recent == [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "qué tal, Sebas"},
        ]

    def test_load_recent_respects_limit_and_order(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history.db")
        for i in range(10):
            store.append("user", f"m{i}")

        recent = store.load_recent(3)
        assert [m["content"] for m in recent] == ["m7", "m8", "m9"]

    def test_persists_across_instances(self, tmp_path: Path) -> None:
        db = tmp_path / "history.db"
        HistoryStore(db).append("user", "sobrevive al reinicio")
        assert HistoryStore(db).load_recent(5)[0]["content"] == "sobrevive al reinicio"

    def test_unwritable_path_degrades_silently(self) -> None:
        store = HistoryStore("/proc/definitivamente/no/existe/x.db")
        store.append("user", "nada explota")
        assert store.load_recent(5) == []

    def test_empty_content_is_not_stored(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history.db")
        store.append("user", "")
        assert store.load_recent(5) == []
