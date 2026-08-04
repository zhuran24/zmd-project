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


# --------------------------------------------------------------------------
# memory lane (2026-08-03 剪枝 v2 P2 对抗审查修复批)
# --------------------------------------------------------------------------


def _memory_lane_run(monkeypatch, tmp_path, *, present: tuple[str, ...]):
    """Run check_memory_tests against a synthetic project root.

    ``PROJECT_ROOT`` is the only thing swapped, so the directory-existence
    decision under test is the real one.
    """
    for relative in present:
        (tmp_path / relative).mkdir(parents=True)
    monkeypatch.setattr(preflight_gate, "PROJECT_ROOT", tmp_path)
    observed: dict[str, object] = {}

    def fake_run(command, **kwargs):
        observed["command"] = list(command)
        return _FakeCompletedProcess(0, "2 passed in 0.01s\n")

    monkeypatch.setattr(preflight_gate.subprocess, "run", fake_run)
    gate = preflight_gate.GateResult()
    preflight_gate.check_memory_tests(gate, always=True)
    return gate, observed


def test_a_missing_memory_test_root_blocks_the_gate(monkeypatch, tmp_path) -> None:
    """一个根没了 = BLOCK。

    旧写法只有两个根**同时**消失才 warn 一句，少一个连话都不说，退出码 0：
    删掉 / rename / checkout 不全，那一半测试就悄悄不跑了，而这条 lane 的
    全部意义就是「它们真的跑了」。
    """
    gate, observed = _memory_lane_run(monkeypatch, tmp_path, present=("cc_memory/tests",))

    assert gate.exit_code == 1
    assert any("cc_memory_vnext/tests" in blocker for blocker in gate.blockers)
    assert "command" not in observed, "缺根时不该还去跑 pytest"


def test_both_memory_test_roots_missing_blocks_rather_than_warns(monkeypatch, tmp_path) -> None:
    gate, _ = _memory_lane_run(monkeypatch, tmp_path, present=())

    assert gate.exit_code == 1
    assert not gate.warnings, "旧行为是 warn + exit 0，那正是这条要拦的"
    for root in preflight_gate.MEMORY_TEST_DIRS:
        assert any(root in blocker for blocker in gate.blockers), root


def test_both_memory_test_roots_present_runs_the_lane(monkeypatch, tmp_path) -> None:
    gate, observed = _memory_lane_run(
        monkeypatch, tmp_path, present=preflight_gate.MEMORY_TEST_DIRS
    )

    assert gate.exit_code == 0
    assert gate.blockers == []
    command = observed["command"]
    for root in preflight_gate.MEMORY_TEST_DIRS:
        assert root in command, root


def test_each_memory_lane_call_gets_its_own_basetemp(monkeypatch, tmp_path) -> None:
    """固定名字的 basetemp 会被并发的另一次门禁删掉重建。

    pytest 启动时清理自己的 basetemp，所以两次并发调用共享一个目录 = 先起的
    那个进程正在用的 tmp_path 凭空消失，报出与被测代码无关的假红。同机并发跑
    门禁是常态（多窗口 / wf 并发）。
    """
    seen: list[str] = []
    for relative in preflight_gate.MEMORY_TEST_DIRS:
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(preflight_gate, "PROJECT_ROOT", tmp_path)

    def fake_run(command, **kwargs):
        seen.append(command[command.index("--basetemp") + 1])
        return _FakeCompletedProcess(0, "2 passed in 0.01s\n")

    monkeypatch.setattr(preflight_gate.subprocess, "run", fake_run)
    for _ in range(3):
        preflight_gate.check_memory_tests(preflight_gate.GateResult(), always=True)

    assert len(seen) == 3
    assert len(set(seen)) == 3, seen
    for path in seen:
        assert str(tmp_path / ".pytest_tmp") in path
        assert preflight_gate.Path(path).parent.is_dir(), "父目录必须仍被预建"
