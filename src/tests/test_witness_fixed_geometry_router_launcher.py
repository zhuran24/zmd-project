from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import signal
import subprocess

import pytest


LAUNCHER = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.launch_fixed_geometry_router"
)
PROCESS_WORKER = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.solve_fixed_geometry_router"
)
ROUTER = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.fixed_geometry_router"
)
SUPERVISOR = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.run_supervisor"
)


NOW = datetime(2026, 7, 20, 5, 6, 7, tzinfo=timezone.utc)
UNIT = "zmd-witness-fixed-router-20260720T050607Z.service"


def _geometry_payload() -> dict[str, object]:
    return {
        "schema_version": ROUTER.INPUT_SCHEMA_VERSION,
        "required_placements": [
            {
                "instance_id": f"required_{index:03d}",
                "template": "tiny",
                "mode": "fixed",
                "anchor": {"x": index % 70, "y": (index // 70) % 70},
            }
            for index in range(LAUNCHER.EXPECTED_REQUIRED_PLACEMENTS)
        ],
        "pole_anchors": [[index, 69] for index in range(9)],
        "manufacturing_port_bindings": {},
    }


def _write_geometry(path: Path) -> str:
    raw = (json.dumps(_geometry_payload(), sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


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


def _cgroup(unit_name: str = UNIT) -> dict[str, object]:
    cgroup_path = f"/user.slice/{unit_name}"
    return {
        "schema_version": "routing_aware_witness_cgroup_telemetry.v1",
        "expected_unit_name": unit_name,
        "cgroup_path": cgroup_path,
        "contract_start": _contract(cgroup_path),
        "contract_end": _contract(cgroup_path),
        "counters_start": _counters(_events(), peak=100),
        "counters_end": _counters(_events(high=1), peak=200),
        "memory.events.delta": _events(high=1),
        "oom_attribution": "NO_CGROUP_OOM",
    }


def _rejected_result(*, classification: str = "ROUTING_PRECHECK_REJECTED") -> dict[str, object]:
    return {
        "schema_version": ROUTER.OUTPUT_SCHEMA_VERSION,
        "status": "REJECTED",
        "classification": classification,
        "phase": "routing_precheck",
        "message": "front_blocked",
        "route_components": [],
        "telemetry": {},
    }


def _feasible_result(*, geometry_sha256: str, unit_name: str = UNIT) -> dict[str, object]:
    required = [
        {"instance_id": f"required_{index:03d}"}
        for index in range(LAUNCHER.EXPECTED_REQUIRED_PLACEMENTS)
    ]
    optional = [{"instance_id": f"research_power_pole_{index:03d}"} for index in range(9)]
    route_components = [{"cell": {"x": 0, "y": 0}, "kind": "straight"}]
    return {
        "schema_version": ROUTER.OUTPUT_SCHEMA_VERSION,
        "status": "FEASIBLE",
        "classification": "STRICT_ROUTES_INDEPENDENTLY_REACHABLE",
        "claim_boundary": "research_witness_candidate_only",
        "required_placements": required,
        "optional_placements": optional,
        "port_specs": [{} for _ in range(LAUNCHER.EXPECTED_PORT_SPECS)],
        "route_components": route_components,
        "route_components_digest": ROUTER.canonical_digest(route_components),
        "telemetry": {
            "input_snapshot": {
                "geometry_sha256": geometry_sha256,
                "dependency_hashes": {"strict_instance": "a" * 64},
                "post_solve_revalidated": True,
            },
            "cgroup": _cgroup(unit_name),
        },
    }


def _empty_process_query(**kwargs):
    assert kwargs["markers"] >= {"solve_fixed_geometry_router.py", "routing_subproblem.py"}
    return ()


def _result_path_from_command(command: tuple[str, ...]) -> Path:
    index = command.index("--out")
    return Path(command[index + 1])


def test_process_worker_writes_structured_rejection_and_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    geometry_path = tmp_path / "geometry.json"
    geometry_sha256 = _write_geometry(geometry_path)
    out_path = tmp_path / "result.json"
    observed: dict[str, object] = {}

    def fake_supervised(path, **kwargs):
        observed["path"] = path
        observed.update(kwargs)
        return _rejected_result()

    monkeypatch.setattr(ROUTER, "run_supervised_fixed_geometry_router", fake_supervised)
    monkeypatch.setenv(PROCESS_WORKER.WORKER_COUNT_ENV, "17")

    code = PROCESS_WORKER.run_cli(
        [
            "--project-root",
            str(LAUNCHER.PROJECT_ROOT),
            "--geometry",
            str(geometry_path),
            "--geometry-sha256",
            geometry_sha256,
            "--out",
            str(out_path),
            "--expected-unit",
            UNIT,
            "--time-limit-seconds",
            "12.5",
            "--wall-time-limit-seconds",
            "30",
            "--workers",
            "3",
        ]
    )

    assert code == 0
    assert json.loads(out_path.read_text())["status"] == "REJECTED"
    assert json.loads(capsys.readouterr().out)["classification"] == "ROUTING_PRECHECK_REJECTED"
    assert observed["path"] == geometry_path
    assert observed["expected_geometry_sha256"] == geometry_sha256
    config = observed["config"]
    assert config.minimum_poles == 9
    assert config.required_grid == (70, 70)
    assert config.require_cgroup is True
    assert config.expected_unit_name == UNIT
    assert PROCESS_WORKER.os.environ[PROCESS_WORKER.WORKER_COUNT_ENV] == "17"


def test_process_worker_turns_unexpected_exception_into_normal_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    geometry_path = tmp_path / "geometry.json"
    geometry_sha256 = _write_geometry(geometry_path)
    out_path = tmp_path / "result.json"

    def explode(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("unexpected")

    monkeypatch.setattr(ROUTER, "run_supervised_fixed_geometry_router", explode)
    result = PROCESS_WORKER.run_worker(
        project_root=LAUNCHER.PROJECT_ROOT,
        geometry_path=geometry_path,
        out_path=out_path,
        expected_geometry_sha256=geometry_sha256,
        expected_unit_name=UNIT,
        time_limit_seconds=1.0,
        wall_time_limit_seconds=2.0,
        workers=1,
    )

    assert result["status"] == "REJECTED"
    assert result["classification"] == "FAIL_CLOSED_WORKER_CLI_EXCEPTION"
    assert result["route_components"] == []
    assert json.loads(out_path.read_text()) == result


def test_launch_command_has_exact_cgroup_contract_and_hash_pinned_worker_suffix(
    tmp_path: Path,
) -> None:
    geometry = LAUNCHER.GeometrySnapshot(
        source_path=str(tmp_path / "source.json"),
        snapshot_path=tmp_path / f"geometry.{'a' * 64}.json",
        sha256="a" * 64,
        size_bytes=10,
        required_placement_count=266,
        pole_count=9,
    )
    worker = LAUNCHER._worker_command(
        project_root=LAUNCHER.PROJECT_ROOT,
        geometry=geometry,
        result_path=tmp_path / "result.json",
        unit_name=UNIT,
        time_limit_seconds=123.0,
        wall_time_limit_seconds=456.0,
        workers=7,
    )
    command = LAUNCHER._launch_command(
        project_root=LAUNCHER.PROJECT_ROOT,
        unit_name=UNIT,
        worker_command=worker,
        service_runtime_max_seconds=486,
    )

    assert command.count("--wait") == 1
    assert command.count("--pipe") == 1
    assert command.count("--collect") == 1
    assert command.count("--service-type=exec") == 1
    assert {f"--property={item}" for item in SUPERVISOR.CGROUP_PROPERTIES} <= set(command)
    assert command.count("--property=RuntimeMaxSec=486s") == 1
    assert command.count("--property=TimeoutStopSec=15s") == 1
    assert command.count("--property=SendSIGKILL=yes") == 1
    assert command[-len(worker) :] == worker
    assert worker[:3] == (
        str(Path(LAUNCHER.sys.executable).resolve(strict=True)),
        "-m",
        LAUNCHER.WORKER_MODULE,
    )
    assert worker[worker.index("--geometry") + 1] == str(geometry.snapshot_path)
    assert worker[worker.index("--geometry-sha256") + 1] == geometry.sha256
    assert worker[worker.index("--wall-time-limit-seconds") + 1] == "456.0"


def test_wall_time_contract_defaults_above_solve_and_rejects_unsafe_values() -> None:
    assert LAUNCHER._resolve_wall_time_limit(
        time_limit_seconds=100.0,
        wall_time_limit_seconds=None,
    ) == 100.0 + LAUNCHER.DEFAULT_BUILD_AND_FINALIZE_GRACE_SECONDS
    assert LAUNCHER._service_runtime_max_seconds(1000.25) == 1031
    assert LAUNCHER._client_wait_timeout_seconds(1031) == 1061.0

    for invalid in (100.0, 99.0, float("inf"), True):
        with pytest.raises(LAUNCHER.FixedRouterLaunchError, match="WALL_TIME_LIMIT_INVALID"):
            LAUNCHER._resolve_wall_time_limit(
                time_limit_seconds=100.0,
                wall_time_limit_seconds=invalid,
            )


def test_process_worker_classifies_whole_worker_timeout_without_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    geometry_path = tmp_path / "geometry.json"
    geometry_sha256 = _write_geometry(geometry_path)
    out_path = tmp_path / "result.json"

    def expire(*args, **kwargs):
        del args, kwargs
        raise PROCESS_WORKER.WorkerWallTimeoutError(
            "WORKER_WALL_TIMEOUT",
            "synthetic timeout",
        )

    monkeypatch.setattr(ROUTER, "run_supervised_fixed_geometry_router", expire)
    result = PROCESS_WORKER.run_worker(
        project_root=LAUNCHER.PROJECT_ROOT,
        geometry_path=geometry_path,
        out_path=out_path,
        expected_geometry_sha256=geometry_sha256,
        expected_unit_name=UNIT,
        time_limit_seconds=1.0,
        wall_time_limit_seconds=2.0,
        workers=1,
    )

    assert result["status"] == "REJECTED"
    assert result["classification"] == "WORKER_WALL_TIMEOUT_UNPROVEN"
    assert result["phase"] == "worker_wall_watchdog"
    assert result["error_code"] == "WORKER_WALL_TIMEOUT"
    assert result["route_components"] == []
    assert json.loads(out_path.read_text()) == result


def test_whole_worker_watchdog_raises_stable_timeout_and_restores_signal_handler() -> None:
    previous_handler = signal.getsignal(signal.SIGALRM)
    with pytest.raises(PROCESS_WORKER.WorkerWallTimeoutError, match="WORKER_WALL_TIMEOUT"):
        with PROCESS_WORKER._worker_wall_watchdog(60.0):
            try:
                signal.raise_signal(signal.SIGALRM)
            except PROCESS_WORKER.WorkerWallTimeoutError:
                pass

    assert signal.getsignal(signal.SIGALRM) is previous_handler
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_whole_worker_watchdog_overrides_downstream_timeout_translation() -> None:
    with pytest.raises(PROCESS_WORKER.WorkerWallTimeoutError, match="WORKER_WALL_TIMEOUT"):
        with PROCESS_WORKER._worker_wall_watchdog(60.0):
            try:
                signal.raise_signal(signal.SIGALRM)
            except PROCESS_WORKER.WorkerWallTimeoutError:
                raise ValueError("downstream translated the timer") from None


def test_dry_run_creates_one_content_bound_snapshot_and_never_starts_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    geometry_path = tmp_path / "source.json"
    geometry_sha256 = _write_geometry(geometry_path)

    def forbidden_runner(*args, **kwargs):
        del args, kwargs
        raise AssertionError("dry run must not start a service")

    outcome = LAUNCHER.launch_fixed_geometry_router(
        geometry_path,
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        dry_run=True,
        now=NOW,
        lock_path=tmp_path / "lock",
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=forbidden_runner,
    )

    assert outcome.dry_run is True
    assert outcome.run_dir.name == "run-20260720T050607Z-ea407fa"
    assert outcome.attempt_dir.name == "a001"
    assert outcome.geometry_path.name == f"geometry.{geometry_sha256}.json"
    assert outcome.geometry_path.read_bytes() == geometry_path.read_bytes()
    assert not outcome.result_path.exists()
    header = json.loads((outcome.attempt_dir / "header.json").read_text())
    assert header["geometry"]["sha256"] == geometry_sha256
    assert header["geometry"]["required_placement_count"] == 266
    assert set(header["sources"]) == set(LAUNCHER._SOURCE_RELATIVE_PATHS)
    assert {
        "binding_subproblem",
        "canonical_rules",
        "canonical_rules_schema",
        "commodity_throughput",
        "cp_sat_worker_config",
        "cpsat_compat",
        "geometry",
        "interchange_init",
        "interchange_preprocess_context",
        "io_strict_json",
        "network_router",
        "operation_profiles",
        "port_binding",
        "preprocess_plan",
        "preprocess_plan_schema",
        "requirements_lock",
        "route_adapter",
        "routing_binding_context",
        "routing_subproblem",
        "strict_contract",
        "witness_io",
    } <= set(header["sources"])
    assert header["worker_wall_time_limit_seconds"] == 4500.0
    assert header["service_runtime_max_seconds"] == 4530
    assert header["service_stop_timeout_seconds"] == 15
    assert header["client_wait_timeout_seconds"] == 4560.0
    assert header["wait_contract"].endswith("bounded_systemd_wait_and_unit_state_query")
    command = json.loads((outcome.attempt_dir / "command.json").read_text())["argv"]
    assert "--property=RuntimeMaxSec=4530s" in command

    with pytest.raises(SUPERVISOR.ArtifactExistsError, match="refusing to reuse run"):
        LAUNCHER.launch_fixed_geometry_router(
            geometry_path,
            project_root=LAUNCHER.PROJECT_ROOT,
            run_root=tmp_path / "runs",
            dry_run=True,
            now=NOW,
            lock_path=tmp_path / "lock",
            unit_query=lambda: (),
            process_query=_empty_process_query,
        )


def test_busy_preflight_does_not_create_a_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    geometry_path = tmp_path / "source.json"
    _write_geometry(geometry_path)
    run_root = tmp_path / "runs"

    with pytest.raises(SUPERVISOR.BusyError, match="related prod-scale work"):
        LAUNCHER.launch_fixed_geometry_router(
            geometry_path,
            project_root=LAUNCHER.PROJECT_ROOT,
            run_root=run_root,
            dry_run=True,
            now=NOW,
            lock_path=tmp_path / "lock",
            unit_query=lambda: ("zmd-r45-live.service",),
            process_query=_empty_process_query,
        )
    assert not run_root.exists()


def test_structured_rejection_is_classified_while_outer_lock_is_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    geometry_path = tmp_path / "source.json"
    _write_geometry(geometry_path)
    lock_path = tmp_path / "lock"
    original_write_json = SUPERVISOR.write_json_exclusive

    def guarded_write(path, payload):
        if Path(path).name == "classification.json":
            with pytest.raises(SUPERVISOR.BusyError):
                with SUPERVISOR.acquire_prod_scale_lock(lock_path):
                    pass
        return original_write_json(path, payload)

    def runner(command, **kwargs):
        assert kwargs == {
            "check": False,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": LAUNCHER.PROJECT_ROOT,
            "timeout": 4560.0,
        }
        with pytest.raises(SUPERVISOR.BusyError):
            with SUPERVISOR.acquire_prod_scale_lock(lock_path):
                pass
        ROUTER.write_result_exclusive(_result_path_from_command(command), _rejected_result())
        return subprocess.CompletedProcess(command, 0, stdout=b"worker out\n", stderr=b"")

    monkeypatch.setattr(SUPERVISOR, "write_json_exclusive", guarded_write)
    outcome = LAUNCHER.launch_fixed_geometry_router(
        geometry_path,
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        now=NOW,
        lock_path=lock_path,
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=runner,
    )

    assert outcome.classification_code == LAUNCHER.CLEAN_REJECTED_RESULT
    assert outcome.successful is False
    assert outcome.route_ready is False
    record = json.loads(outcome.classification_path.read_text())
    assert record["result"]["schema_valid"] is True
    assert record["result"]["integrity_valid"] is True
    assert record["classification"]["detail"] == "ROUTING_PRECHECK_REJECTED"
    with SUPERVISOR.acquire_prod_scale_lock(lock_path):
        pass


def test_client_wait_timeout_is_bounded_and_records_nonterminal_unit_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    geometry_path = tmp_path / "source.json"
    _write_geometry(geometry_path)
    observed: dict[str, object] = {}

    def runner(command, **kwargs):
        observed["timeout"] = kwargs["timeout"]
        raise subprocess.TimeoutExpired(
            command,
            kwargs["timeout"],
            output=b"client stdout\n",
            stderr=b"client stderr\n",
        )

    def unit_state(unit_name: str) -> dict[str, str]:
        assert unit_name == UNIT
        return {"LoadState": "loaded", "ActiveState": "active", "SubState": "running"}

    outcome = LAUNCHER.launch_fixed_geometry_router(
        geometry_path,
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        now=NOW,
        lock_path=tmp_path / "lock",
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=runner,
        unit_state_query=unit_state,
    )

    assert observed["timeout"] == 4560.0
    assert outcome.classification_code == LAUNCHER.LAUNCH_TIMEOUT
    assert outcome.route_ready is False
    record = json.loads(outcome.classification_path.read_text())
    assert record["timeout_unit_state"] == {
        "query_status": "OK",
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "terminal": False,
    }
    assert "manual resolution required" in record["classification"]["detail"]
    assert (outcome.attempt_dir / "stdout.log").read_bytes() == b"client stdout\n"
    assert (outcome.attempt_dir / "stderr.log").read_bytes() == b"client stderr\n"


def test_exact_unit_state_query_is_itself_bounded() -> None:
    observed: dict[str, object] = {}

    def runner(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="LoadState=loaded\nActiveState=inactive\nSubState=dead\n",
            stderr="",
        )

    assert LAUNCHER._query_unit_state(UNIT, runner=runner) == {
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
    }
    assert observed["command"][:3] == ["systemctl", "--user", "show"]
    assert observed["kwargs"] == {
        "check": False,
        "capture_output": True,
        "text": True,
        "timeout": LAUNCHER.UNIT_STATE_QUERY_TIMEOUT_SECONDS,
    }


def test_feasible_result_requires_exact_cgroup_contract_and_geometry_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    geometry_path = tmp_path / "source.json"
    geometry_sha256 = _write_geometry(geometry_path)

    def runner(command, **kwargs):
        del kwargs
        ROUTER.write_result_exclusive(
            _result_path_from_command(command),
            _feasible_result(geometry_sha256=geometry_sha256),
        )
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    outcome = LAUNCHER.launch_fixed_geometry_router(
        geometry_path,
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        now=NOW,
        lock_path=tmp_path / "lock",
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=runner,
    )
    assert outcome.classification_code == SUPERVISOR.SUCCESS
    assert outcome.route_ready is True

    bad = _cgroup()
    bad["contract_start"]["leaf"]["memory.max"] = SUPERVISOR.MEMORY_MAX_BYTES - 1
    with pytest.raises(LAUNCHER.FixedRouterLaunchError, match="CGROUP_CONTRACT_INVALID"):
        LAUNCHER._validate_cgroup_telemetry(bad, unit_name=UNIT)


def test_geometry_snapshot_mutation_discards_otherwise_clean_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    geometry_path = tmp_path / "source.json"
    _write_geometry(geometry_path)

    def runner(command, **kwargs):
        del kwargs
        result_path = _result_path_from_command(command)
        geometry_snapshot = Path(command[command.index("--geometry") + 1])
        ROUTER.write_result_exclusive(result_path, _rejected_result())
        geometry_snapshot.write_bytes(b"{}\n")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    outcome = LAUNCHER.launch_fixed_geometry_router(
        geometry_path,
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        now=NOW,
        lock_path=tmp_path / "lock",
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=runner,
    )
    assert outcome.classification_code == SUPERVISOR.RESULT_INTEGRITY_INVALID
    assert outcome.route_ready is False
    inspection = json.loads(outcome.classification_path.read_text())["result"]
    assert any("GEOMETRY_SNAPSHOT_DRIFT" in error for error in inspection["errors"])


def test_semantic_source_drift_discards_otherwise_clean_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(LAUNCHER, "RESEARCH_ROOT", tmp_path)
    geometry_path = tmp_path / "source.json"
    _write_geometry(geometry_path)
    baseline_sources = LAUNCHER._source_records(LAUNCHER.PROJECT_ROOT)
    calls = 0

    def changing_source_records(project_root: Path):
        nonlocal calls
        assert project_root == LAUNCHER.PROJECT_ROOT
        calls += 1
        if calls == 1:
            return baseline_sources
        changed = dict(baseline_sources)
        original = changed["network_router"]
        changed["network_router"] = SUPERVISOR.FileRecord(
            path=original.path,
            sha256="f" * 64,
            size_bytes=original.size_bytes,
        )
        return changed

    def runner(command, **kwargs):
        del kwargs
        ROUTER.write_result_exclusive(_result_path_from_command(command), _rejected_result())
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(LAUNCHER, "_source_records", changing_source_records)
    outcome = LAUNCHER.launch_fixed_geometry_router(
        geometry_path,
        project_root=LAUNCHER.PROJECT_ROOT,
        run_root=tmp_path / "runs",
        now=NOW,
        lock_path=tmp_path / "lock",
        unit_query=lambda: (),
        process_query=_empty_process_query,
        systemd_runner=runner,
    )

    assert calls == 2
    assert outcome.classification_code == SUPERVISOR.RESULT_INTEGRITY_INVALID
    assert outcome.route_ready is False
    inspection = json.loads(outcome.classification_path.read_text())["result"]
    assert any("SOURCE_DRIFT" in error for error in inspection["errors"])


def test_outer_classification_preserves_worker_wall_timeout_as_unproven() -> None:
    inspection = LAUNCHER.ResultInspection(
        present=True,
        parse_valid=True,
        schema_valid=True,
        integrity_valid=True,
        worker_status="REJECTED",
        worker_classification="WORKER_WALL_TIMEOUT_UNPROVEN",
        oom_attribution=None,
        sha256="a" * 64,
        size_bytes=1,
        errors=(),
    )
    classification = LAUNCHER._classify_attempt(
        timed_out=False,
        returncode=0,
        inspection=inspection,
    )
    assert classification.code == LAUNCHER.WORKER_WALL_TIMEOUT
    assert classification.successful is False
    assert classification.detail == "WORKER_WALL_TIMEOUT_UNPROVEN"


@pytest.mark.parametrize(
    "payload",
    [
        b'{"status":"FEASIBLE","status":"REJECTED"}',
        b'{"status":NaN}',
        b"[]",
        b"\xff",
    ],
)
def test_strict_json_rejects_duplicate_nonfinite_nonobject_and_nonutf8(payload: bytes) -> None:
    with pytest.raises(LAUNCHER.FixedRouterLaunchError, match="JSON_INVALID"):
        LAUNCHER._strict_json_object(payload, label="test")
