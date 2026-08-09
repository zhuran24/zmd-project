from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib
from pathlib import Path
import subprocess

import pytest


SUPERVISOR = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.run_supervisor"
)


def _events(**updates: int) -> dict[str, int]:
    values = {
        "low": 0,
        "high": 0,
        "max": 0,
        "oom": 0,
        "oom_kill": 0,
        "oom_group_kill": 0,
    }
    values.update(updates)
    return values


def _evidence(**updates):
    values = {
        "timed_out": False,
        "returncode": 0,
        "solver_status": "FEASIBLE",
        "result_present": True,
        "result_parse_valid": True,
        "schema_valid": True,
        "integrity_valid": True,
        "memory_events_before": _events(),
        "memory_events_after": _events(),
    }
    values.update(updates)
    return SUPERVISOR.AttemptEvidence(**values)


def test_run_and_attempt_directories_are_exclusive(tmp_path: Path) -> None:
    moment = datetime(2026, 7, 20, 1, 2, 3, tzinfo=timezone.utc)
    base = tmp_path / "runs"
    run_dir = SUPERVISOR.create_run_directory(base, "ea407fa", now=moment)
    assert run_dir.name == "run-20260720T010203Z-ea407fa"
    assert run_dir.is_dir()
    with pytest.raises(SUPERVISOR.ArtifactExistsError, match="refusing to reuse run"):
        SUPERVISOR.create_run_directory(base, "ea407fa", now=moment)

    attempt = SUPERVISOR.create_attempt_directory(run_dir, 1)
    assert attempt.name == "a001"
    with pytest.raises(SUPERVISOR.ArtifactExistsError, match="refusing to reuse attempt"):
        SUPERVISOR.create_attempt_directory(run_dir, 1)
    with pytest.raises(SUPERVISOR.SupervisorError, match="1..999"):
        SUPERVISOR.create_attempt_directory(run_dir, 0)


def test_exclusive_atomic_writes_never_replace_existing_bytes(tmp_path: Path) -> None:
    text_path = tmp_path / "record.txt"
    SUPERVISOR.write_text_exclusive(text_path, "first\n")
    with pytest.raises(SUPERVISOR.ArtifactExistsError):
        SUPERVISOR.write_text_exclusive(text_path, "second\n")
    assert text_path.read_text(encoding="utf-8") == "first\n"

    json_path = tmp_path / "record.json"
    SUPERVISOR.write_json_exclusive(json_path, {"z": 1, "a": 2})
    assert json_path.read_text(encoding="utf-8") == '{\n  "a": 2,\n  "z": 1\n}\n'
    with pytest.raises(SUPERVISOR.ArtifactExistsError):
        SUPERVISOR.write_json_exclusive(json_path, {"different": True})
    assert not list(tmp_path.glob(".*.tmp.*"))

    invalid_path = tmp_path / "invalid.json"
    with pytest.raises(SUPERVISOR.SupervisorError, match="strict JSON"):
        SUPERVISOR.write_json_exclusive(invalid_path, {"bad": float("nan")})
    assert not invalid_path.exists()


def test_manifest_and_content_addressed_publish_are_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "run" / "layout.json"
    source.parent.mkdir()
    source.write_bytes(b'{"layout":true}\n')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = SUPERVISOR.build_sha256_manifest({"layout": source}, relative_to=tmp_path)
    assert manifest["files"]["layout"] == {
        "path": "run/layout.json",
        "sha256": digest,
        "size_bytes": source.stat().st_size,
    }
    assert len(manifest["manifest_sha256"]) == 64

    publish_dir = tmp_path / "published"
    first = SUPERVISOR.publish_content_addressed(source, publish_dir)
    assert first.created is True
    assert first.path.name == f"layout.{digest}.json"
    second = SUPERVISOR.publish_content_addressed(source, publish_dir)
    assert second.created is False
    assert second.path == first.path

    manifest_payload, manifest_record = SUPERVISOR.publish_manifest_content_addressed(
        {"layout": source},
        publish_dir,
        relative_to=tmp_path,
    )
    assert manifest_payload == manifest
    assert manifest_record.created is True
    _, repeated_manifest = SUPERVISOR.publish_manifest_content_addressed(
        {"layout": source},
        publish_dir,
        relative_to=tmp_path,
    )
    assert repeated_manifest.created is False

    committed_manifest, committed_record = SUPERVISOR.publish_verified_manifest_content_addressed(
        {"layout": first},
        publish_dir,
        relative_to=publish_dir,
    )
    assert committed_manifest["files"]["layout"] == {
        "path": first.path.name,
        "sha256": first.sha256,
        "size_bytes": first.size_bytes,
    }
    assert committed_record.created is True
    _, repeated_commit = SUPERVISOR.publish_verified_manifest_content_addressed(
        {"layout": second},
        publish_dir,
        relative_to=publish_dir,
    )
    assert repeated_commit.path == committed_record.path
    assert repeated_commit.created is False

    first.path.write_bytes(b"corrupt")
    with pytest.raises(SUPERVISOR.ArtifactIntegrityError, match="different bytes"):
        SUPERVISOR.publish_content_addressed(source, publish_dir)


def test_verified_manifest_detects_drift_before_commit_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "layout.json"
    source.write_bytes(b'{"layout":true}\n')
    publish_dir = tmp_path / "published"
    publication = SUPERVISOR.publish_content_addressed(source, publish_dir)
    original_verify = SUPERVISOR._verify_content_addressed_publications
    verification_calls = 0

    def mutate_before_second_verification(*args, **kwargs):
        nonlocal verification_calls
        verification_calls += 1
        if verification_calls == 2:
            publication.path.write_bytes(b"drifted after first PublishRecord check\n")
        return original_verify(*args, **kwargs)

    monkeypatch.setattr(
        SUPERVISOR,
        "_verify_content_addressed_publications",
        mutate_before_second_verification,
    )
    with pytest.raises(SUPERVISOR.ArtifactIntegrityError, match="first PublishRecord"):
        SUPERVISOR.publish_verified_manifest_content_addressed(
            {"layout": publication},
            publish_dir,
            relative_to=publish_dir,
        )

    assert verification_calls == 2
    assert not list(publish_dir.glob("manifest.*.json"))
    assert not list(publish_dir.glob(".manifest.*.pending.*"))


def test_verified_manifest_rejects_non_content_addressed_record_path(tmp_path: Path) -> None:
    source = tmp_path / "layout.json"
    source.write_bytes(b'{"layout":true}\n')
    publish_dir = tmp_path / "published"
    publication = SUPERVISOR.publish_content_addressed(source, publish_dir)
    wrong_path = publish_dir / "layout.not-content-addressed.json"
    wrong_path.write_bytes(publication.path.read_bytes())
    wrong_record = SUPERVISOR.PublishRecord(
        path=wrong_path,
        sha256=publication.sha256,
        size_bytes=publication.size_bytes,
        created=True,
    )

    with pytest.raises(SUPERVISOR.ArtifactIntegrityError, match="filename is not bound"):
        SUPERVISOR.publish_verified_manifest_content_addressed(
            {"layout": wrong_record},
            publish_dir,
            relative_to=publish_dir,
        )
    assert not list(publish_dir.glob("manifest.*.json"))


def test_publish_uses_one_stable_source_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "layout.json"
    original_payload = b'{"generation":1}\n'
    source.write_bytes(original_payload)
    original_reader = SUPERVISOR._read_stable_snapshot
    calls = 0

    def snapshot_then_mutate(path: Path):
        nonlocal calls
        calls += 1
        snapshot = original_reader(path)
        source.write_bytes(b'{"generation":2}\n')
        return snapshot

    monkeypatch.setattr(SUPERVISOR, "_read_stable_snapshot", snapshot_then_mutate)
    published = SUPERVISOR.publish_content_addressed(source, tmp_path / "published")

    assert calls == 1
    assert published.sha256 == hashlib.sha256(original_payload).hexdigest()
    assert published.path.read_bytes() == original_payload


def test_lock_path_and_nonblocking_flock_contract(tmp_path: Path) -> None:
    assert SUPERVISOR.prod_scale_lock_path(1234) == Path(
        "/run/user/1234/zmd-pj-prod-scale-solve.lock"
    )
    lock_path = tmp_path / "zmd-pj-prod-scale-solve.lock"
    with SUPERVISOR.acquire_prod_scale_lock(lock_path):
        with pytest.raises(SUPERVISOR.BusyError, match="mutex is busy"):
            with SUPERVISOR.acquire_prod_scale_lock(lock_path):
                raise AssertionError("unreachable")
    with SUPERVISOR.acquire_prod_scale_lock(lock_path):
        pass


def test_systemd_command_builder_has_exact_cgroup_contract(tmp_path: Path) -> None:
    command = SUPERVISOR.build_systemd_run_command(
        unit_name="zmd-witness-deadbeef-a001.service",
        working_directory=tmp_path.resolve(),
        command=("/usr/bin/python3", "worker.py"),
    )
    assert command == (
        "systemd-run",
        "--user",
        "--wait",
        "--pipe",
        "--unit=zmd-witness-deadbeef-a001.service",
        "--service-type=exec",
        "--collect",
        "--expand-environment=no",
        f"--working-directory={tmp_path.resolve()}",
        "--property=MemoryHigh=35G",
        "--property=MemoryMax=39G",
        "--property=MemorySwapMax=16G",
        "--property=OOMPolicy=continue",
        "/usr/bin/python3",
        "worker.py",
    )
    SUPERVISOR.validate_cgroup_property_values(
        memory_high=35 * 1024**3,
        memory_max=39 * 1024**3,
        memory_swap_max=16 * 1024**3,
        oom_policy="continue",
    )
    with pytest.raises(SUPERVISOR.SupervisorError, match="cgroup property mismatch"):
        SUPERVISOR.validate_cgroup_property_values(
            memory_high=34 * 1000**3,
            memory_max=39 * 1024**3,
            memory_swap_max=16 * 1024**3,
            oom_policy="continue",
        )
    with pytest.raises(SUPERVISOR.SupervisorError, match="unsafe systemd unit"):
        SUPERVISOR.build_systemd_run_command(
            unit_name="../../bad.service",
            working_directory=tmp_path.resolve(),
            command=("true",),
        )


def test_active_unit_and_process_detection_is_read_only_and_filtering(tmp_path: Path) -> None:
    stdout = """
zmd-witness-abc-a001.service loaded active running witness
ssh-agent.service loaded active running ssh
zmd-r45-old.service loaded active running old
zmd-witness-abc-a001.service loaded active running duplicate
"""
    assert SUPERVISOR.parse_active_related_units(stdout) == (
        "zmd-r45-old.service",
        "zmd-witness-abc-a001.service",
    )

    def fake_runner(*args, **kwargs):
        assert args[0][0:3] == ["systemctl", "--user", "list-units"]
        assert "--state=active,activating,reloading,deactivating" in args[0]
        assert kwargs == {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": SUPERVISOR.CONTROL_PLANE_QUERY_TIMEOUT_SECONDS,
        }
        return subprocess.CompletedProcess(args[0], 0, stdout=stdout, stderr="")

    assert SUPERVISOR.query_active_related_units(runner=fake_runner) == (
        "zmd-r45-old.service",
        "zmd-witness-abc-a001.service",
    )

    def timeout_runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    with pytest.raises(SUPERVISOR.SupervisorError, match="cannot query active user units"):
        SUPERVISOR.query_active_related_units(runner=timeout_runner)

    proc_root = tmp_path / "proc"
    (proc_root / "101").mkdir(parents=True)
    (proc_root / "102").mkdir()
    (proc_root / "not-a-pid").mkdir()
    (proc_root / "101" / "cmdline").write_bytes(
        b"python3\0/path/run_campaign.py\0execute-arm\0"
    )
    (proc_root / "102" / "cmdline").write_bytes(b"python3\0ordinary.py\0")
    found = SUPERVISOR.detect_active_related_processes(proc_root=proc_root)
    assert found == (
        {
            "pid": 101,
            "argv": ["python3", "/path/run_campaign.py", "execute-arm"],
            "matched": ["run_campaign.py"],
        },
    )

    (proc_root / "103").mkdir()
    (proc_root / "103" / "cmdline").write_bytes(b"python3\0/path/solve_shelf_power.py\0--worker\0")
    found = SUPERVISOR.detect_active_related_processes(proc_root=proc_root)
    assert found[-1] == {
        "pid": 103,
        "argv": ["python3", "/path/solve_shelf_power.py", "--worker"],
        "matched": ["solve_shelf_power.py"],
    }

    (proc_root / "104").mkdir()
    (proc_root / "104" / "cmdline").write_bytes(
        b"python3\0-m\0docs.research.witness_constructor_20260717.07_routing_aware.solve_shelf_power\0"
    )
    found = SUPERVISOR.detect_active_related_processes(proc_root=proc_root)
    assert found[-1] == {
        "pid": 104,
        "argv": [
            "python3",
            "-m",
            "docs.research.witness_constructor_20260717.07_routing_aware.solve_shelf_power",
        ],
        "matched": ["solve_shelf_power.py"],
    }


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"memory_events_before": None}, "OOM_TELEMETRY_MISSING"),
        ({"memory_events_after": _events(oom=1, oom_kill=1)}, "CGROUP_OOM_KILL"),
        ({"memory_events_after": _events(oom=1)}, "CGROUP_OOM_EVENT"),
        ({"timed_out": True}, "SOLVER_TIMEOUT"),
        ({"returncode": -11}, "WORKER_SIGNAL_SIGSEGV"),
        ({"returncode": -15}, "WORKER_SIGNAL_OTHER"),
        ({"returncode": 2}, "PROCESS_NONZERO_EXIT"),
        ({"returncode": None}, "PROCESS_NONZERO_EXIT"),
        ({"result_present": False}, "RESULT_MISSING_OR_INVALID"),
        ({"result_parse_valid": False}, "RESULT_MISSING_OR_INVALID"),
        ({"schema_valid": False}, "RESULT_SCHEMA_INVALID"),
        ({"integrity_valid": False}, "RESULT_INTEGRITY_INVALID"),
        ({"solver_status": "UNKNOWN"}, "SOLVER_UNKNOWN"),
        ({"solver_status": "TIME_LIMIT"}, "SOLVER_TIMEOUT"),
        ({"solver_status": "nonsense"}, "RESULT_SCHEMA_INVALID"),
    ],
)
def test_attempt_classification_is_stable_and_fail_closed(updates, expected: str) -> None:
    classified = SUPERVISOR.classify_attempt(_evidence(**updates))
    assert classified.code == expected
    assert classified.successful is False
    assert classified.code in SUPERVISOR.FAILURE_CLASSES


@pytest.mark.parametrize("status", ["OPTIMAL", "FEASIBLE", "INFEASIBLE"])
def test_only_clean_solver_statuses_pass(status: str) -> None:
    classified = SUPERVISOR.classify_attempt(_evidence(solver_status=status))
    assert classified.code == "CLEAN_RESULT"
    assert classified.successful is True
    assert classified.memory_events_delta == _events()


def test_missing_or_nonmonotone_oom_telemetry_always_fails() -> None:
    missing = _events()
    del missing["oom_kill"]
    classified = SUPERVISOR.classify_attempt(_evidence(memory_events_after=missing))
    assert classified.code == "OOM_TELEMETRY_MISSING"

    nonmonotone = SUPERVISOR.classify_attempt(
        _evidence(
            memory_events_before=_events(oom=2),
            memory_events_after=_events(oom=1),
            returncode=-11,
        )
    )
    assert nonmonotone.code == "OOM_TELEMETRY_MISSING"
