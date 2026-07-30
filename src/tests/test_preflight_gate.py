from __future__ import annotations

import os

import pytest

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


def _capture_pytest_command(monkeypatch, *, full: bool) -> tuple[list[str], dict[str, object]]:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _FakeCompletedProcess(0, "1 passed in 0.01s\n")

    for name in (
        "ZMD_AB16_PYTEST_COLLECTION_FD",
        "ZMD_AB16_PYTEST_COLLECTION_NONCE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(preflight_gate.subprocess, "run", fake_run)
    monkeypatch.setattr(preflight_gate, "_pytest_xdist_available", lambda: True)
    gate = preflight_gate.GateResult()

    preflight_gate.check_tests(gate, full=full)

    assert gate.exit_code == 0
    assert isinstance(captured["command"], list)
    assert isinstance(captured["kwargs"], dict)
    return captured["command"], captured["kwargs"]


def test_core_pytest_command_remains_generic_and_ab16_free(monkeypatch) -> None:
    command, kwargs = _capture_pytest_command(monkeypatch, full=False)

    assert command[:3] == [preflight_gate.sys.executable, "-m", "pytest"]
    assert "-I" not in command
    assert "-B" not in command
    assert "--repository-workflow=full" not in command
    assert "randomly" not in command
    assert command[command.index("-n") + 1] == "auto"
    assert not any("AB16" in item or "ab16" in item for item in command)
    environment = kwargs["env"]
    assert isinstance(environment, dict)
    assert not any(name.startswith("ZMD_AB16_") for name in environment)
    assert "pass_fds" not in kwargs


def test_full_pytest_command_remains_generic_and_ab16_free(monkeypatch) -> None:
    command, kwargs = _capture_pytest_command(monkeypatch, full=True)

    assert command[:3] == [preflight_gate.sys.executable, "-m", "pytest"]
    assert command[-1] == "src/tests/"
    assert "-I" not in command
    assert "-B" not in command
    assert "--repository-workflow=full" not in command
    assert "randomly" not in command
    assert command[command.index("-n") + 1] == "auto"
    assert not any("AB16" in item or "ab16" in item for item in command)
    environment = kwargs["env"]
    assert isinstance(environment, dict)
    assert not any(name.startswith("ZMD_AB16_") for name in environment)
    assert "pass_fds" not in kwargs


def test_slow_pytest_command_remains_generic_and_ab16_free(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _FakeCompletedProcess(0, "1 passed in 0.01s\n")

    for name in (
        "ZMD_AB16_PYTEST_COLLECTION_FD",
        "ZMD_AB16_PYTEST_COLLECTION_NONCE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(preflight_gate.subprocess, "run", fake_run)
    gate = preflight_gate.GateResult()

    preflight_gate.check_slow_tests(gate, require_collection=True)

    command = captured["command"]
    kwargs = captured["kwargs"]
    assert isinstance(command, list)
    assert isinstance(kwargs, dict)
    assert command == [
        preflight_gate.sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "--no-header",
        "-m",
        "slow",
        "src/tests",
    ]
    assert not any("AB16" in item or "ab16" in item for item in command)
    environment = kwargs["env"]
    assert isinstance(environment, dict)
    assert not any(name.startswith("ZMD_AB16_") for name in environment)
    assert "pass_fds" not in kwargs


@pytest.mark.parametrize(
    ("ambient_name", "ambient_value"),
    [
        ("ZMD_AB16_PYTEST_COLLECTION_FD", "999999"),
        ("ZMD_AB16_PYTEST_COLLECTION_NONCE", "0" * 64),
    ],
)
def test_ordinary_pytest_ignores_one_sided_ab16_ambient_state(
    tmp_path,
    ambient_name: str,
    ambient_value: str,
) -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment[ambient_name] = ambient_value
    completed = preflight_gate.subprocess.run(
        [
            preflight_gate.sys.executable,
            "-I",
            "-B",
            "-m",
            "pytest",
            "-p",
            "no:randomly",
            "--repository-workflow=developer",
            "--basetemp",
            str(tmp_path / "nested-basetemp"),
            "src/tests/test_preflight_gate.py::test_secret_scan_uses_default_timeout_scale",
            "-q",
        ],
        check=False,
        close_fds=True,
        cwd=preflight_gate.PROJECT_ROOT,
        env=environment,
        stdin=preflight_gate.subprocess.DEVNULL,
        stdout=preflight_gate.subprocess.PIPE,
        stderr=preflight_gate.subprocess.PIPE,
        timeout=30,
    )

    assert completed.returncode == 0, (completed.stdout, completed.stderr)


def test_external_artifact_check_runs_with_safe_path_environment() -> None:
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONSAFEPATH"] = "1"
    completed = preflight_gate.subprocess.run(
        [
            preflight_gate.sys.executable,
            "-B",
            str(
                preflight_gate.PROJECT_ROOT
                / "scripts/check_external_artifacts.py"
            ),
        ],
        check=False,
        cwd=preflight_gate.PROJECT_ROOT,
        env=environment,
        stdin=preflight_gate.subprocess.DEVNULL,
        stdout=preflight_gate.subprocess.PIPE,
        stderr=preflight_gate.subprocess.PIPE,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert "external artifact check passed" in completed.stdout
