from src.core.analyzer import SystemAnalyzer
from src.domain.models import SystemTelemetry


def t(cpu: float = 10.0, ram: float = 10.0) -> SystemTelemetry:
    return SystemTelemetry(cpu=cpu, ram=ram)


class TestCpuThreshold:
    def test_single_spike_does_not_alert(self) -> None:
        analyzer = SystemAnalyzer()
        assert analyzer.analyze(t(cpu=95.0)) is None
        assert analyzer.analyze(t(cpu=10.0)) is None

    def test_sustained_high_cpu_alerts_on_third_tick(self) -> None:
        analyzer = SystemAnalyzer()
        assert analyzer.analyze(t(cpu=90.0)) is None
        assert analyzer.analyze(t(cpu=90.0)) is None
        alert = analyzer.analyze(t(cpu=90.0))
        assert alert is not None
        assert alert.resource == "cpu"
        assert alert.value == 90.0

    def test_counter_resets_after_alert(self) -> None:
        analyzer = SystemAnalyzer()
        for _ in range(2):
            analyzer.analyze(t(cpu=90.0))
        assert analyzer.analyze(t(cpu=90.0)) is not None
        # Después de disparar, hay que sostener otros 3 ticks.
        assert analyzer.analyze(t(cpu=90.0)) is None
        assert analyzer.analyze(t(cpu=90.0)) is None
        assert analyzer.analyze(t(cpu=90.0)) is not None

    def test_dip_resets_counter(self) -> None:
        analyzer = SystemAnalyzer()
        analyzer.analyze(t(cpu=90.0))
        analyzer.analyze(t(cpu=90.0))
        analyzer.analyze(t(cpu=50.0))  # baja: se reinicia
        assert analyzer.analyze(t(cpu=90.0)) is None


class TestRamThreshold:
    def test_sustained_high_ram_alerts(self) -> None:
        analyzer = SystemAnalyzer()
        assert analyzer.analyze(t(ram=95.0)) is None
        assert analyzer.analyze(t(ram=95.0)) is None
        alert = analyzer.analyze(t(ram=95.0))
        assert alert is not None
        assert alert.resource == "ram"

    def test_ram_at_90_does_not_alert(self) -> None:
        analyzer = SystemAnalyzer()
        for _ in range(5):
            assert analyzer.analyze(t(ram=90.0)) is None

    def test_ram_has_priority_over_cpu(self) -> None:
        analyzer = SystemAnalyzer()
        for _ in range(2):
            analyzer.analyze(t(cpu=95.0, ram=95.0))
        alert = analyzer.analyze(t(cpu=95.0, ram=95.0))
        assert alert is not None
        assert alert.resource == "ram"
