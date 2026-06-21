from __future__ import annotations

from scripts import preflight_gate


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


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
