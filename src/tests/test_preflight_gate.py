from __future__ import annotations

from scripts import preflight_gate


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def _assert_secret_scan_timeout(monkeypatch, *, scale: float, expected_timeout: int) -> None:
    observed: dict[str, int] = {}

    def fake_run(*args, **kwargs):
        observed["timeout"] = kwargs["timeout"]
        raise preflight_gate.subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(preflight_gate, "_TIMEOUT_SCALE", scale)
    monkeypatch.setattr(preflight_gate.subprocess, "run", fake_run)
    gate = preflight_gate.GateResult()

    preflight_gate.check_publish_secret_scan(gate)

    assert observed == {"timeout": expected_timeout}
    assert gate.blockers == [f"secret scan 超时 (>{expected_timeout}s)"]
    assert gate.exit_code == 1


def test_secret_scan_uses_default_timeout_scale(monkeypatch) -> None:
    _assert_secret_scan_timeout(monkeypatch, scale=1.0, expected_timeout=30)


def test_secret_scan_uses_scaled_timeout_and_reports_it(monkeypatch) -> None:
    _assert_secret_scan_timeout(monkeypatch, scale=2.0, expected_timeout=60)


def test_slow_lane_missing_collection_blocks_when_required(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        del args, kwargs
        return _FakeCompletedProcess(5, "no tests ran in 0.01s\n")

    monkeypatch.setattr(preflight_gate.subprocess, "run", fake_run)
    gate = preflight_gate.GateResult()

    preflight_gate.check_slow_tests(gate, require_collection=True)

    assert any("未收集到 @slow 测试" in blocker for blocker in gate.blockers)
    assert not gate.warnings
    assert gate.exit_code == 1


def test_slow_lane_missing_collection_can_remain_warning_for_local_probe(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        del args, kwargs
        return _FakeCompletedProcess(5, "no tests ran in 0.01s\n")

    monkeypatch.setattr(preflight_gate.subprocess, "run", fake_run)
    gate = preflight_gate.GateResult()

    preflight_gate.check_slow_tests(gate)

    assert any("未收集到 @slow 测试" in warning for warning in gate.warnings)
    assert not gate.blockers
    assert gate.exit_code == 0
