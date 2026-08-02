from __future__ import annotations

import fcntl
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
ORCHESTRATOR_PATH = TOOLS / "organic_unit_orchestrator_v1.py"
RUNNER_PATH = TOOLS / "organic_arm_runner_v1.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ORCHESTRATOR = _load(ORCHESTRATOR_PATH, "noncert_cuts_ab16_execution_guard_orchestrator_v1_tested")
RUNNER = _load(RUNNER_PATH, "noncert_cuts_ab16_execution_guard_runner_v1_tested")


def _release_prod_scale_locks(descriptors: tuple[int, ...]) -> None:
    for descriptor in reversed(descriptors):
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def test_prod_scale_lock_names_remain_compatible() -> None:
    assert RUNNER.PROD_SCALE_LOCK_PATHS == (
        Path("/tmp/zmd-pj-codex-heavy-validation.lock"),
        Path("/run/user/1000/zmd_pj_prod_scale_solver.lock"),
        Path("/run/user/1000/zmd-pj-prod-scale-solve.lock"),
    )


def test_lock_contention_fails_closed_and_releases_partial_set(tmp_path: Path) -> None:
    first = tmp_path / "first.lock"
    blocked = tmp_path / "blocked.lock"
    blocker = RUNNER._acquire_prod_scale_locks((blocked,))  # noqa: SLF001
    try:
        with pytest.raises(RUNNER.RunnerError, match="already held"):
            RUNNER._acquire_prod_scale_locks((first, blocked))  # noqa: SLF001
        probe = RUNNER._acquire_prod_scale_locks((first,))  # noqa: SLF001
        _release_prod_scale_locks(probe)
        assert first.is_file()
    finally:
        _release_prod_scale_locks(blocker)


def test_public_runner_rejects_missing_selected_unit_before_lock_or_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    selection = {
        "attempt_dir": "/attempt",
        "unit_name": "cuts-ab16-selected.service",
    }
    pre_run = {
        "resource_contract": {
            "memory_high_bytes": 35 * 1024**3,
            "memory_max_bytes": 39 * 1024**3,
            "memory_swap_max_bytes": 16 * 1024**3,
        },
    }
    monkeypatch.setattr(RUNNER, "_PUBLIC_RUN_STARTED", False)
    monkeypatch.setattr(RUNNER.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(RUNNER.os, "getuid", lambda: 1000)
    monkeypatch.setattr(
        RUNNER,
        "_load_authority",
        lambda _path: ({}, selection, {}, pre_run),
    )
    monkeypatch.setattr(
        RUNNER,
        "_current_unified_cgroup_path",
        lambda: Path("/user.slice/cuts-ab16-selected.service/nested.scope"),
    )
    monkeypatch.setattr(RUNNER, "_retain_process_lifetime_prod_scale_locks", lambda: events.append("locks"))
    monkeypatch.setattr(RUNNER, "_prepare_selected_attempt", lambda *_args: events.append("attempt"))

    with pytest.raises(RUNNER.RunnerError, match="selected prod-scale resource unit context is absent"):
        RUNNER.run_selected_arm(Path("selection.json"))
    assert events == []


def test_public_runner_checks_exact_cgroup_limits_then_retains_process_locks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit_name = "cuts-ab16-selected.service"
    events: list[str] = []
    resource_contract = {
        "memory_high_bytes": 35 * 1024**3,
        "memory_max_bytes": 39 * 1024**3,
        "memory_swap_max_bytes": 16 * 1024**3,
    }
    monkeypatch.setattr(RUNNER, "_PUBLIC_RUN_STARTED", False)
    monkeypatch.setattr(RUNNER.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(RUNNER.os, "getuid", lambda: 1000)
    monkeypatch.setattr(
        RUNNER,
        "_load_authority",
        lambda _path: (
            {},
            {"attempt_dir": "/attempt", "unit_name": unit_name},
            {},
            {"resource_contract": resource_contract},
        ),
    )
    monkeypatch.setattr(
        RUNNER,
        "_current_unified_cgroup_path",
        lambda: Path("/user.slice/user-1000.slice/app.slice") / unit_name,
    )
    expected_controls = {
        "memory.high": str(resource_contract["memory_high_bytes"]),
        "memory.max": str(resource_contract["memory_max_bytes"]),
        "memory.swap.max": str(resource_contract["memory_swap_max_bytes"]),
    }

    def read_control(path: Path, _label: str) -> str:
        events.append(path.name)
        return expected_controls[path.name] + "\n"

    def retain_locks() -> None:
        events.append("locks")

    def stop_before_attempt(*_args: object) -> None:
        events.append("attempt")
        raise RUNNER.RunnerError("fixture stopped before attempt creation")

    monkeypatch.setattr(RUNNER, "_read_small_ascii", read_control)
    monkeypatch.setattr(RUNNER, "_retain_process_lifetime_prod_scale_locks", retain_locks)
    monkeypatch.setattr(RUNNER, "_prepare_selected_attempt", stop_before_attempt)

    with pytest.raises(RUNNER.RunnerError, match="stopped before attempt"):
        RUNNER.run_selected_arm(Path("selection.json"))
    assert events == ["memory.high", "memory.max", "memory.swap.max", "locks", "attempt"]


@pytest.mark.parametrize("drifted_control", ["memory.high", "memory.max", "memory.swap.max"])
def test_public_runner_rejects_cgroup_limit_drift_before_locks(
    drifted_control: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit_name = "cuts-ab16-selected.service"
    resource_contract = {
        "memory_high_bytes": 35 * 1024**3,
        "memory_max_bytes": 39 * 1024**3,
        "memory_swap_max_bytes": 16 * 1024**3,
    }
    expected_controls = {
        "memory.high": str(resource_contract["memory_high_bytes"]),
        "memory.max": str(resource_contract["memory_max_bytes"]),
        "memory.swap.max": str(resource_contract["memory_swap_max_bytes"]),
    }
    events: list[str] = []
    monkeypatch.setattr(RUNNER, "_PUBLIC_RUN_STARTED", False)
    monkeypatch.setattr(RUNNER.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(RUNNER.os, "getuid", lambda: 1000)
    monkeypatch.setattr(
        RUNNER,
        "_load_authority",
        lambda _path: (
            {},
            {"attempt_dir": "/attempt", "unit_name": unit_name},
            {},
            {"resource_contract": resource_contract},
        ),
    )
    monkeypatch.setattr(
        RUNNER,
        "_current_unified_cgroup_path",
        lambda: Path("/user.slice/user-1000.slice/app.slice") / unit_name,
    )
    monkeypatch.setattr(
        RUNNER,
        "_read_small_ascii",
        lambda path, _label: ("1" if path.name == drifted_control else expected_controls[path.name]) + "\n",
    )
    monkeypatch.setattr(RUNNER, "_retain_process_lifetime_prod_scale_locks", lambda: events.append("locks"))
    monkeypatch.setattr(RUNNER, "_prepare_selected_attempt", lambda *_args: events.append("attempt"))

    with pytest.raises(RUNNER.RunnerError, match=rf"cgroup {drifted_control} differs"):
        RUNNER.run_selected_arm(Path("selection.json"))
    assert events == []


def test_live_adapter_surfaces_unit_exit_before_inner_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = object.__new__(ORCHESTRATOR.SubprocessLifecycleAdapter)
    adapter.pre_run = {
        "launch": {"payload_argv": ["payload"]},
        "output_paths": {"inner": str(tmp_path / "absent-inner.json")},
        "resource_contract": {"runtime_max_seconds": 120},
    }
    launch_state = {
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "4242",
        "Result": "success",
        "ExecMainCode": "0",
        "ExecMainStatus": "0",
    }
    starttimes = iter((77, None))
    adapter._run = lambda _argv, timeout: SimpleNamespace(returncode=0)  # type: ignore[method-assign]
    adapter._show = lambda _unit, fields: (  # type: ignore[method-assign]
        launch_state if tuple(fields) == ORCHESTRATOR.SYSTEMD_LAUNCH_FIELDS else pytest.fail("wrong fields")
    )
    adapter._monotonic = lambda: 0.0
    adapter.sleep = lambda _seconds: pytest.fail("dead supervisor should fail before sleeping")
    monkeypatch.setattr(ORCHESTRATOR.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR.os, "getuid", lambda: 1000)
    monkeypatch.setattr(ORCHESTRATOR, "_proc_starttime", lambda _pid: next(starttimes))

    with pytest.raises(ORCHESTRATOR.OrchestratorError, match="supervisor exited before inner lifecycle"):
        adapter.launch_and_wait_for_keeper(
            unit_name="cuts-ab16-selected.service",
            systemd_run_argv=["/usr/bin/systemd-run"],
            payload_argv=["payload"],
        )


def test_controller_death_does_not_release_payload_process_locks(tmp_path: Path) -> None:
    lock_paths = tuple(tmp_path / f"prod-scale-{index}.lock" for index in range(3))
    identity_path = tmp_path / "payload-identity"
    ready_path = tmp_path / "payload-ready"
    orphan_path = tmp_path / "payload-observed-orphan"
    stop_path = tmp_path / "payload-stop"
    unit_code = r"""
import importlib.util
import os
from pathlib import Path
import sys
import time

runner_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
orphan_path = Path(sys.argv[3])
stop_path = Path(sys.argv[4])
lock_paths = tuple(Path(item) for item in sys.argv[5:])
spec = importlib.util.spec_from_file_location("ab16_r11_payload_holder", runner_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
original_parent = os.getppid()
module._retain_process_lifetime_prod_scale_locks(lock_paths)
ready_path.write_text(f"{os.getpid()} {original_parent}\n", encoding="ascii")
while not stop_path.exists():
    if os.getppid() != original_parent and not orphan_path.exists():
        orphan_path.write_text(f"{os.getppid()}\n", encoding="ascii")
    time.sleep(0.01)
assert module._PROD_SCALE_LOCK_DESCRIPTORS
"""
    controller_code = r"""
import subprocess
from pathlib import Path
import sys
import time

child = subprocess.Popen(
    [sys.executable, "-c", sys.argv[1], *sys.argv[3:]],
    close_fds=True,
    start_new_session=True,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
try:
    raw_stat = Path(f"/proc/{child.pid}/stat").read_text(encoding="ascii")
    starttime = int(raw_stat[raw_stat.rfind(")") + 2 :].split()[19])
    Path(sys.argv[2]).write_text(f"{child.pid} {starttime}\n", encoding="ascii")
except BaseException:
    child.kill()
    child.wait()
    raise
while True:
    time.sleep(1)
"""
    controller = subprocess.Popen(
        [
            sys.executable,
            "-c",
            controller_code,
            unit_code,
            str(identity_path),
            str(RUNNER_PATH),
            str(ready_path),
            str(orphan_path),
            str(stop_path),
            *(str(path) for path in lock_paths),
        ],
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    payload_pid: int | None = None
    payload_starttime: int | None = None
    payload_finished = False

    def wait_for_nonempty(path: Path, timeout: float = 5.0) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() <= deadline:
            try:
                value = path.read_text(encoding="ascii")
            except FileNotFoundError:
                value = ""
            if value:
                return value
            time.sleep(0.01)
        raise AssertionError(f"timed out waiting for {path.name}")

    def wait_for_pair(path: Path, timeout: float = 5.0) -> tuple[int, int]:
        deadline = time.monotonic() + timeout
        while time.monotonic() <= deadline:
            try:
                value = path.read_text(encoding="ascii")
            except FileNotFoundError:
                value = ""
            fields = value.split()
            if value.endswith("\n") and len(fields) == 2 and all(field.isascii() and field.isdigit() for field in fields):
                return int(fields[0]), int(fields[1])
            time.sleep(0.01)
        raise AssertionError(f"timed out waiting for complete {path.name}")

    def proc_starttime(pid: int) -> int | None:
        try:
            raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        except (FileNotFoundError, ProcessLookupError):
            return None
        close = raw.rfind(")")
        if close < 0:
            return None
        fields = raw[close + 2 :].split()
        return int(fields[19]) if len(fields) > 19 else None

    def assert_all_blocked() -> None:
        for path in lock_paths:
            try:
                unexpected = RUNNER._acquire_prod_scale_locks((path,))  # noqa: SLF001
            except RUNNER.RunnerError as exc:
                assert "already held" in str(exc)
            else:
                _release_prod_scale_locks(unexpected)
                pytest.fail(f"payload did not retain {path.name}")

    try:
        payload_pid, payload_starttime = wait_for_pair(identity_path)
        ready_pid, original_parent = wait_for_pair(ready_path)
        assert (ready_pid, original_parent) == (payload_pid, controller.pid)
        assert_all_blocked()
        controller.send_signal(signal.SIGKILL)
        controller.wait(timeout=5)
        wait_for_nonempty(orphan_path)
        assert_all_blocked()
        stop_path.touch()
        deadline = time.monotonic() + 5.0
        while True:
            try:
                final_probe = RUNNER._acquire_prod_scale_locks(lock_paths)  # noqa: SLF001
                break
            except RUNNER.RunnerError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.01)
        _release_prod_scale_locks(final_probe)
        payload_finished = True
    finally:
        stop_path.touch(exist_ok=True)
        if controller.poll() is None:
            controller.kill()
            controller.wait(timeout=5)
        if (
            not payload_finished
            and payload_pid is not None
            and payload_starttime is not None
            and proc_starttime(payload_pid) == payload_starttime
        ):
            try:
                os.kill(payload_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
