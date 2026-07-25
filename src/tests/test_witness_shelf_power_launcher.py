from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import subprocess

import pytest


LAUNCHER = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.launch_shelf_power"
)
SUPERVISOR = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.run_supervisor"
)


NOW = datetime(2026, 7, 20, 4, 5, 6, tzinfo=timezone.utc)
UNIT = "zmd-witness-shelf-power-20260720T040506Z.service"


def _events(**updates: int) -> dict[str, int]:
    result = {
        "low": 0,
        "high": 0,
        "max": 0,
        "oom": 0,
        "oom_kill": 0,
        "oom_group_kill": 0,
    }
    result.update(updates)
    return result


def _limit(path: str, *, leaf: bool) -> dict[str, object]:
    return {
        "path": path,
        "memory.high": SUPERVISOR.MEMORY_HIGH_BYTES if leaf else "max",
        "memory.max": SUPERVISOR.MEMORY_MAX_BYTES if leaf else "max",
        "memory.swap.max": SUPERVISOR.MEMORY_SWAP_MAX_BYTES if leaf else "max",
    }


def _contract(cgroup_path: str) -> dict[str, object]:
    return {
        "leaf": _limit(cgroup_path, leaf=True),
        "ancestors": [_limit("/user.slice", leaf=False), _limit("/", leaf=False)],
        "effective": {
            "memory.high": SUPERVISOR.MEMORY_HIGH_BYTES,
            "memory.max": SUPERVISOR.MEMORY_MAX_BYTES,
            "memory.swap.max": SUPERVISOR.MEMORY_SWAP_MAX_BYTES,
        },
    }


def _counters(events: dict[str, int], *, peak: int) -> dict[str, object]:
    return {
        "memory.current": 100,
        "memory.peak": peak,
        "memory.swap.current": 0,
        "memory.swap.peak": 0,
        "pids.current": 2,
        "memory.events": events,
    }


def _telemetry(unit: str = UNIT) -> dict[str, object]:
    cgroup_path = f"/user.slice/{unit}"
    start_events = _events()
    end_events = _events(high=1)
    return {
        "schema_version": "routing_aware_witness_cgroup_telemetry.v1",
        "expected_unit_name": unit,
        "cgroup_path": cgroup_path,
        "contract_start": _contract(cgroup_path),
        "contract_end": _contract(cgroup_path),
        "counters_start": _counters(start_events, peak=100),
        "counters_end": _counters(end_events, peak=200),
        "memory.events.delta": _events(high=1),
        "oom_attribution": "NO_CGROUP_OOM",
    }


def _result(telemetry: object | None = None) -> dict[str, object]:
    return {
        "schema_version": "witness_shelf_power_result_v1",
        "status": "FEASIBLE",
        "input_sha256": {"strict": "a" * 64},
        "manufacturing_slots": [],
        "pole_anchors": [],
        "pole_bay_anchors": [],
        "protected_rect": [1, 3, 6, 7],
        "network_edges": [],
        "stats": {},
        "route_validation": {"status": "WITNESS_BUILT"},
        "cgroup_telemetry": _telemetry() if telemetry is None else telemetry,
        "failure": None,
    }


def _empty_process_query(**kwargs):
    assert kwargs == {}
    return ()


def test_launch_command_has_wait_pipe_exact_contract_and_worker_suffix(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    worker = LAUNCHER._worker_command(
        project_root=LAUNCHER.PROJECT_ROOT,
        result_path=result_path,
        unit_name=UNIT,
        time_limit_seconds=123.0,
        workers=7,
    )
    command = LAUNCHER._launch_command(
        project_root=LAUNCHER.PROJECT_ROOT,
        unit_name=UNIT,
        worker_command=worker,
    )

    assert command.count("--wait") == 1
    assert command.count("--pipe") == 1
    assert command.count("--collect") == 1
    assert command.count("--service-type=exec") == 1
    assert command[-len(worker) :] == worker
    assert worker[:3] == (
        str(Path(LAUNCHER.sys.executable).resolve(strict=True)),
        "-m",
        "docs.research.witness_constructor_20260717.07_routing_aware.solve_shelf_power",
    )
    assert worker[-10:] == (
        "--project-root",
        str(LAUNCHER.PROJECT_ROOT),
        "--time-limit-seconds",
        "123.0",
        "--workers",
        "7",
        "--out",
        str(result_path),
        "--expected-unit",
        UNIT,
    )


def test_dry_run_records_one_fresh_a001_without_starting_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    calls = 0

    def forbidden_runner(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("dry-run must not start systemd-run")

    outcome = LAUNCHER.launch_shelf_power(
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        dry_run=True,
        now=NOW,
        lock_path=tmp_path / "lock",
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=forbidden_runner,
    )

    assert calls == 0
    assert outcome.dry_run is True
    assert outcome.attempt_dir.name == "a001"
    assert outcome.run_dir.name == "run-20260720T040506Z-ea407fa"
    assert outcome.unit_name == UNIT
    assert not outcome.result_path.exists()
    assert (outcome.attempt_dir / "stdout.log").read_bytes() == b""
    command = json.loads((outcome.attempt_dir / "command.json").read_text())
    assert command["argv"].count("--wait") == 1
    classification = json.loads(outcome.classification_path.read_text())
    assert classification["classification"]["code"] == "DRY_RUN"

    with pytest.raises(SUPERVISOR.ArtifactExistsError, match="refusing to reuse run"):
        LAUNCHER.launch_shelf_power(
            project_root=LAUNCHER.PROJECT_ROOT,
            run_root=tmp_path / "runs",
            dry_run=True,
            now=NOW,
            lock_path=tmp_path / "lock",
            unit_query=lambda: (),
            process_query=_empty_process_query,
        )


def test_busy_preflight_never_starts_or_creates_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    run_root = tmp_path / "runs"
    with pytest.raises(SUPERVISOR.BusyError, match="related prod-scale work"):
        LAUNCHER.launch_shelf_power(
            project_root=LAUNCHER.PROJECT_ROOT,
            run_root=run_root,
            dry_run=True,
            now=NOW,
            lock_path=tmp_path / "lock",
            unit_query=lambda: ("zmd-r45-live.service",),
            process_query=_empty_process_query,
        )
    assert not run_root.exists()


def test_missing_result_is_classified_fail_closed_while_lock_is_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    lock_path = tmp_path / "lock"

    def runner(command, **kwargs):
        assert kwargs == {
            "check": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": LAUNCHER.PROJECT_ROOT,
        }
        with pytest.raises(SUPERVISOR.BusyError):
            with SUPERVISOR.acquire_prod_scale_lock(lock_path):
                pass
        return subprocess.CompletedProcess(command, 1, stdout=b"worker out\n", stderr=b"worker err\n")

    outcome = LAUNCHER.launch_shelf_power(
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        now=NOW,
        lock_path=lock_path,
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=runner,
    )

    assert outcome.successful is False
    assert outcome.classification_code == "OOM_TELEMETRY_MISSING"
    assert (outcome.attempt_dir / "stdout.log").read_bytes() == b"worker out\n"
    assert (outcome.attempt_dir / "stderr.log").read_bytes() == b"worker err\n"
    record = json.loads(outcome.classification_path.read_text())
    assert record["result"]["present"] is False
    with SUPERVISOR.acquire_prod_scale_lock(lock_path):
        pass


def test_result_json_and_cgroup_telemetry_are_strict_and_independently_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(_result(), sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(LAUNCHER, "_current_input_hashes", lambda project_root: {"strict": "a" * 64})
    monkeypatch.setattr(
        LAUNCHER.shelf_constructor,
        "_load_shelf_result",
        lambda result_path, project_root: ((), (), (), frozenset()),
    )
    worker_sha = SUPERVISOR.sha256_file(LAUNCHER.WORKER_PATH)

    inspected = LAUNCHER._inspect_result(
        path,
        project_root=LAUNCHER.PROJECT_ROOT,
        unit_name=UNIT,
        expected_worker_sha256=worker_sha,
    )
    assert inspected.present is True
    assert inspected.parse_valid is True
    assert inspected.schema_valid is True
    assert inspected.integrity_valid is True
    assert inspected.memory_events_before == _events()
    assert inspected.memory_events_after == _events(high=1)

    bad = _result(_telemetry("zmd-witness-shelf-power-20260720T040507Z.service"))
    path2 = tmp_path / "bad.json"
    path2.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    inspected = LAUNCHER._inspect_result(
        path2,
        project_root=LAUNCHER.PROJECT_ROOT,
        unit_name=UNIT,
        expected_worker_sha256=worker_sha,
    )
    assert inspected.schema_valid is True
    assert inspected.integrity_valid is False
    assert inspected.memory_events_before is None
    assert any("TELEMETRY_UNIT_MISMATCH" in error for error in inspected.errors)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"status":"FEASIBLE","status":"OPTIMAL"}',
        b'{"status":NaN}',
        b"[]",
        b"\xff",
    ],
)
def test_strict_json_rejects_duplicate_nonfinite_nonobject_and_nonutf8(payload: bytes) -> None:
    with pytest.raises(LAUNCHER.ShelfPowerLaunchError, match="RESULT_JSON_INVALID"):
        LAUNCHER._strict_json_object(payload, label="test")


def test_output_scope_escape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LAUNCHER.ShelfPowerLaunchError, match="OUTPUT_SCOPE_INVALID"):
        LAUNCHER.launch_shelf_power(
            project_root=LAUNCHER.PROJECT_ROOT,
            run_root=tmp_path,
            dry_run=True,
            now=NOW,
            lock_path=tmp_path / "lock",
            unit_query=lambda: (),
            process_query=_empty_process_query,
        )


def test_cli_rejects_clean_infeasible_as_no_geometry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    outcome = LAUNCHER.LaunchOutcome(
        run_dir=tmp_path / "run",
        attempt_dir=tmp_path / "run" / "a001",
        unit_name=UNIT,
        result_path=tmp_path / "run" / "a001" / "result.json",
        classification_path=tmp_path / "run" / "a001" / "classification.json",
        classification_code="CLEAN_RESULT",
        successful=True,
        geometry_ready=False,
        dry_run=False,
    )
    monkeypatch.setattr(LAUNCHER, "launch_shelf_power", lambda **kwargs: outcome)

    assert LAUNCHER.run_cli([]) == 1
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["successful"] is True
    assert rendered["geometry_ready"] is False
