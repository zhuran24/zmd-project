"""Focused tests for routed-witness finalization and publication."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


finalizer = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.finalize_routed_witness"
)
objective_audit = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.objective_audit"
)
witness_campaign = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.witness_campaign"
)
witness_io = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.witness_io"
)

UNIT = "zmd-witness-fixed-router-20260720T050607Z.service"


def test_finalizer_api_and_cli_require_pinned_launcher_evidence() -> None:
    signature = inspect.signature(finalizer.finalize_router_result)
    for name in (
        "launcher_header_path",
        "expected_launcher_header_sha256",
        "launcher_classification_path",
        "expected_launcher_classification_sha256",
    ):
        assert signature.parameters[name].default is inspect.Parameter.empty

    with pytest.raises(SystemExit):
        finalizer._build_parser().parse_args(["router.json", "--expected-sha256", "0" * 64])


def test_pinned_router_result_rejects_hash_mismatch_and_duplicate_keys(tmp_path: Path) -> None:
    source = tmp_path / "router.json"
    source.write_text('{"status":"FEASIBLE"}\n', encoding="utf-8")

    with pytest.raises(finalizer.FinalizationError) as exc_info:
        finalizer._load_pinned_source(source, "0" * 64)
    assert exc_info.value.code == "ROUTER_RESULT_HASH_MISMATCH"

    duplicate = b'{"status":"FEASIBLE","status":"REJECTED"}\n'
    source.write_bytes(duplicate)
    digest = hashlib.sha256(duplicate).hexdigest()
    with pytest.raises(finalizer.strict_contract.InputContractError):
        finalizer._load_pinned_source(source, digest)


def _checker(rectangle: objective_audit.EmptyRectangle) -> witness_io.CheckerProcessResult:
    objective = {
        "x": rectangle.x,
        "y": rectangle.y,
        "width": rectangle.width,
        "height": rectangle.height,
        "area": rectangle.area,
        "min_side": rectangle.min_side,
    }
    return witness_io.CheckerProcessResult(
        classification="LAYOUT_FEASIBLE",
        exit_code=0,
        status="LAYOUT_FEASIBLE",
        report={
            "status": "LAYOUT_FEASIBLE",
            "categories": {
                "J": "strict_json",
                "S": "document_shape",
                "I": "instance_integrity",
                "F": "facility_geometry",
                "P": "port_binding",
                "PW": "power",
                "R": "routing",
                "O": "objective",
            },
            "errors": [],
            "recomputed_objective": objective,
        },
        stdout="",
        stderr="",
        checker_trusted=True,
        checker_sha256=witness_io.EXPECTED_CHECKER_SHA256,
        checker_source_path=str(witness_io.EXPECTED_CHECKER_PATH),
        checker_source_identity=(1, 2, 0o100444, 1, 123, 4, 5),
        checker_snapshot_size_bytes=123,
        checker_python_executable=str(Path(sys.executable).resolve()),
        checker_execution_mode=witness_io.PINNED_CHECKER_EXECUTION_MODE,
    )


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


def _write_launch_bundle(tmp_path: Path, project_root: Path) -> SimpleNamespace:
    geometry_path = tmp_path / "geometry.json"
    geometry_payload = b'{"geometry":true}\n'
    geometry_path.write_bytes(geometry_payload)
    geometry_sha256 = hashlib.sha256(geometry_payload).hexdigest()
    geometry = {
        "source_path": str(geometry_path),
        "snapshot_path": str(geometry_path),
        "sha256": geometry_sha256,
        "size_bytes": len(geometry_payload),
        "required_placement_count": 266,
        "pole_count": 35,
    }

    router_result = {
        "schema_version": "fixed_geometry_router_result.v1",
        "status": "FEASIBLE",
        "telemetry": {
            "input_snapshot": {"geometry_sha256": geometry_sha256},
            "cgroup": {
                "expected_unit_name": UNIT,
                "oom_attribution": "NO_CGROUP_OOM",
            },
        },
    }
    router_payload = _json_bytes(router_result)
    router_path = tmp_path / "router.json"
    router_path.write_bytes(router_payload)
    router_sha256 = hashlib.sha256(router_payload).hexdigest()

    source_records: dict[str, dict[str, object]] = {}
    for name in sorted(finalizer._ROUTER_SOURCE_NAMES):
        source_path = project_root / "router_sources" / f"{name}.py"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_payload = f"# {name}\n".encode("utf-8")
        source_path.write_bytes(source_payload)
        source_records[name] = {
            "path": source_path.relative_to(project_root).as_posix(),
            "sha256": hashlib.sha256(source_payload).hexdigest(),
            "size_bytes": len(source_payload),
        }

    header = {
        "schema_version": "fixed_geometry_router_launch.v1",
        "created_utc": "2026-07-20T05:06:07+00:00",
        "baseline_head": finalizer.EXPECTED_BASELINE_HEAD,
        "observed_head": finalizer.EXPECTED_BASELINE_HEAD,
        "unit_name": UNIT,
        "dry_run": False,
        "pid": 123,
        "active_units": [],
        "active_processes": [],
        "sources": source_records,
        "geometry": geometry,
        "result_path": str(router_path),
        "time_limit_seconds": 60.0,
        "workers": 8,
        "wait_contract": "worker_internal_time_limit_then_systemd_wait",
        "lock_path": str(tmp_path / "lock"),
    }
    header_payload = _json_bytes(header)
    header_path = tmp_path / "header.json"
    header_path.write_bytes(header_payload)

    classification = {
        "schema_version": "fixed_geometry_router_classification.v1",
        "dry_run": False,
        "classification": {
            "code": "CLEAN_RESULT",
            "successful": True,
            "detail": "STRICT_ROUTES_INDEPENDENTLY_REACHABLE",
        },
        "route_ready": True,
        "launch_error": None,
        "process": {"timed_out": False, "returncode": 0},
        "geometry": geometry,
        "result": {
            "present": True,
            "parse_valid": True,
            "schema_valid": True,
            "integrity_valid": True,
            "worker_status": "FEASIBLE",
            "worker_classification": "STRICT_ROUTES_INDEPENDENTLY_REACHABLE",
            "oom_attribution": "NO_CGROUP_OOM",
            "sha256": router_sha256,
            "size_bytes": len(router_payload),
            "errors": [],
        },
    }
    classification_payload = _json_bytes(classification)
    classification_path = tmp_path / "classification.json"
    classification_path.write_bytes(classification_payload)
    return SimpleNamespace(
        router_path=router_path,
        router_sha256=router_sha256,
        header_path=header_path,
        header_sha256=hashlib.sha256(header_payload).hexdigest(),
        classification_path=classification_path,
        classification_sha256=hashlib.sha256(classification_payload).hexdigest(),
        geometry_sha256=geometry_sha256,
    )


def _install_success_fakes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, SimpleNamespace, objective_audit.ObjectiveAudit, dict[str, object]]:
    project_root = tmp_path / "project"
    project_root.mkdir()
    instance_path = project_root / "instance.json"
    instance_payload = b"{}\n"
    instance_path.write_bytes(instance_payload)
    instance_sha256 = hashlib.sha256(instance_payload).hexdigest()
    rectangle = objective_audit.EmptyRectangle(1, 63, 6, 7, 42, 6)
    audit = objective_audit.ObjectiveAudit(rectangle, rectangle, 3656)
    built = witness_campaign.BuiltWitness(
        witness={"strict": "layout"},
        objective=audit,
        route_component_count=100,
        route_cell_count=100,
        terminal_count=628,
        source_count=316,
        sink_count=312,
        pole_count=35,
        box_count=0,
    )
    bundle = SimpleNamespace(
        strict_instance=SimpleNamespace(path=instance_path, sha256=instance_sha256),
        hashes={"strict_instance": instance_sha256},
    )
    reconciliation = SimpleNamespace(
        counts=lambda: {"required": 266},
        hashes={"strict_instance": instance_sha256},
    )
    checker = _checker(rectangle)
    observed_checker_paths: dict[str, object] = {}

    monkeypatch.setattr(
        finalizer.construct_witness,
        "_repository_head",
        lambda _root: finalizer.EXPECTED_BASELINE_HEAD,
    )
    monkeypatch.setattr(
        finalizer.strict_contract,
        "load_and_reconcile",
        lambda _root: (bundle, reconciliation),
    )
    monkeypatch.setattr(
        finalizer.witness_campaign,
        "build_routed_witness",
        lambda _result, bundle: built,
    )
    monkeypatch.setattr(
        finalizer.construct_witness,
        "_audit_layout_file",
        lambda _bundle, _path: audit,
    )

    def fake_checker(instance_path, layout_path, **kwargs):
        observed_checker_paths.update(
            {
                "instance_path": Path(instance_path),
                "layout_path": Path(layout_path),
                "kwargs": kwargs,
            }
        )
        return checker

    monkeypatch.setattr(finalizer.witness_io, "run_independent_checker", fake_checker)
    return project_root, built, audit, observed_checker_paths


def test_finalize_publishes_only_after_independent_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, _audit, checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)

    outcome = finalizer.finalize_router_result(
        launch.router_path,
        expected_router_result_sha256=launch.router_sha256,
        launcher_header_path=launch.header_path,
        expected_launcher_header_sha256=launch.header_sha256,
        launcher_classification_path=launch.classification_path,
        expected_launcher_classification_sha256=launch.classification_sha256,
        project_root=project_root,
        run_root=tmp_path / "runs",
        publish_root=tmp_path / "artifacts",
    )

    assert outcome.accepted
    assert outcome.layout_path is not None and outcome.layout_path.is_file()
    assert outcome.manifest_path is not None and outcome.manifest_path.is_file()
    summary = json.loads(outcome.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "LAYOUT_ACCEPTED"
    assert summary["feasible_lower_bound"] == {"area": 42, "min_side": 6}
    assert summary["router_geometry_sha256"] == launch.geometry_sha256
    assert summary["commit_authority"] == {
        "rule": "effective_only_when_named_by_exact_manifest_commit",
        "manifest_logical_name": "finalization_summary",
    }
    assert checker_paths["instance_path"].parent == outcome.layout_path.parent
    assert checker_paths["instance_path"].name.startswith("strict_instance.")
    assert checker_paths["instance_path"] != project_root / "instance.json"
    assert checker_paths["layout_path"] == outcome.layout_path
    manifest = json.loads(outcome.manifest_path.read_text(encoding="utf-8"))
    assert set(manifest["files"]) == {
        "acceptance",
        "checker_inputs",
        "checker_process",
        "checker_report",
        "finalization_summary",
        "layout",
        "launcher_classification",
        "launcher_header",
        "objective_audit",
        "router_diagnostics",
        "router_geometry",
        "router_result",
        "router_source_cgroup_telemetry",
        "router_source_fixed_geometry_router",
        "router_source_launcher",
        "router_source_run_supervisor",
        "router_source_worker",
        "strict_instance",
    }
    summary_artifact = outcome.manifest_path.parent / manifest["files"]["finalization_summary"]["path"]
    assert outcome.summary_path == summary_artifact
    assert not (outcome.run_dir / "summary.json").exists()
    assert not (outcome.layout_path.parent / "result.json").exists()
    checker_inputs_path = outcome.manifest_path.parent / manifest["files"]["checker_inputs"]["path"]
    checker_inputs = json.loads(checker_inputs_path.read_text(encoding="utf-8"))
    assert checker_inputs["layout"]["sha256"] == summary["layout_sha256"]
    assert checker_inputs["instance"]["sha256"] == summary["input_reconciliation"]["input_sha256"][
        "strict_instance"
    ]


def test_finalizer_rejects_launcher_result_identity_mismatch_before_run_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, _audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)
    classification = json.loads(launch.classification_path.read_text(encoding="utf-8"))
    classification["result"]["sha256"] = "0" * 64
    payload = _json_bytes(classification)
    launch.classification_path.write_bytes(payload)

    with pytest.raises(finalizer.FinalizationError) as exc_info:
        finalizer.finalize_router_result(
            launch.router_path,
            expected_router_result_sha256=launch.router_sha256,
            launcher_header_path=launch.header_path,
            expected_launcher_header_sha256=launch.header_sha256,
            launcher_classification_path=launch.classification_path,
            expected_launcher_classification_sha256=hashlib.sha256(payload).hexdigest(),
            project_root=project_root,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )
    assert exc_info.value.code == "LAUNCH_RESULT_IDENTITY_MISMATCH"
    assert not (tmp_path / "runs").exists()


def test_checker_instance_snapshot_mutation_fails_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)

    def mutating_checker(instance_path, _layout_path, **_kwargs):
        Path(instance_path).write_bytes(b'{"changed":true}\n')
        return _checker(audit.computed)

    monkeypatch.setattr(finalizer.witness_io, "run_independent_checker", mutating_checker)
    with pytest.raises(finalizer.FinalizationError) as exc_info:
        finalizer.finalize_router_result(
            launch.router_path,
            expected_router_result_sha256=launch.router_sha256,
            launcher_header_path=launch.header_path,
            expected_launcher_header_sha256=launch.header_sha256,
            launcher_classification_path=launch.classification_path,
            expected_launcher_classification_sha256=launch.classification_sha256,
            project_root=project_root,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )
    assert exc_info.value.code == "INSTANCE_DRIFT_AFTER_CHECKER"
    assert not (tmp_path / "artifacts").exists()


def test_publish_rejects_layout_changed_after_checker_and_never_commits_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, _audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)
    original_publish = finalizer.run_supervisor.publish_content_addressed

    def mutating_publish(path, publish_root, *, logical_name=None):
        if logical_name == "layout.json":
            Path(path).write_bytes(b'{"unchecked":true}\n')
        return original_publish(path, publish_root, logical_name=logical_name)

    monkeypatch.setattr(finalizer.run_supervisor, "publish_content_addressed", mutating_publish)
    with pytest.raises(finalizer.FinalizationError) as exc_info:
        finalizer.finalize_router_result(
            launch.router_path,
            expected_router_result_sha256=launch.router_sha256,
            launcher_header_path=launch.header_path,
            expected_launcher_header_sha256=launch.header_sha256,
            launcher_classification_path=launch.classification_path,
            expected_launcher_classification_sha256=launch.classification_sha256,
            project_root=project_root,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )
    assert exc_info.value.code == "PUBLISHED_SOURCE_DRIFT"
    assert not list((tmp_path / "artifacts").glob("manifest.*.json"))


def test_manifest_commit_is_last_and_an_after_link_error_cannot_reverse_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, _audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)
    original_commit = finalizer.run_supervisor.publish_verified_manifest_content_addressed
    committed_paths: list[Path] = []

    def commit_then_raise(*args, **kwargs):
        _manifest, record = original_commit(*args, **kwargs)
        committed_paths.append(record.path)
        assert record.path.is_file()
        raise RuntimeError("injected return-path failure after exact marker link")

    monkeypatch.setattr(
        finalizer.run_supervisor,
        "publish_verified_manifest_content_addressed",
        commit_then_raise,
    )
    outcome = finalizer.finalize_router_result(
        launch.router_path,
        expected_router_result_sha256=launch.router_sha256,
        launcher_header_path=launch.header_path,
        expected_launcher_header_sha256=launch.header_sha256,
        launcher_classification_path=launch.classification_path,
        expected_launcher_classification_sha256=launch.classification_sha256,
        project_root=project_root,
        run_root=tmp_path / "runs",
        publish_root=tmp_path / "artifacts",
    )

    assert outcome.accepted is True
    assert committed_paths == [outcome.manifest_path]
    assert outcome.manifest_path is not None and outcome.manifest_path.is_file()
    assert json.loads(outcome.summary_path.read_text(encoding="utf-8"))["status"] == "LAYOUT_ACCEPTED"
    assert not (outcome.run_dir / "summary.json").exists()
    assert outcome.layout_path is not None
    assert not (outcome.layout_path.parent / "result.json").exists()


def test_manifest_failure_before_marker_writes_one_rejection_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, _audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)

    def fail_before_commit(*_args, **_kwargs):
        raise RuntimeError("injected pre-marker commit failure")

    monkeypatch.setattr(
        finalizer.run_supervisor,
        "publish_verified_manifest_content_addressed",
        fail_before_commit,
    )
    with pytest.raises(RuntimeError, match="pre-marker"):
        finalizer.finalize_router_result(
            launch.router_path,
            expected_router_result_sha256=launch.router_sha256,
            launcher_header_path=launch.header_path,
            expected_launcher_header_sha256=launch.header_sha256,
            launcher_classification_path=launch.classification_path,
            expected_launcher_classification_sha256=launch.classification_sha256,
            project_root=project_root,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )

    assert not list((tmp_path / "artifacts").glob("manifest.*.json"))
    run_dir = next((tmp_path / "runs").iterdir())
    result = json.loads((run_dir / "a001" / "result.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert result == summary
    assert result["status"] == "FINALIZATION_REJECTED"
    assert result["classification"] == "UNEXPECTED_EXCEPTION"
    assert result["exception_type"] == "RuntimeError"
    assert result["phase"] == "manifest_commit"


def test_checker_rejection_is_classified_and_cannot_publish_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)
    base = _checker(audit.computed)
    rejected_report = json.loads(json.dumps(base.report))
    rejected_report["status"] = "LAYOUT_INVALID"
    rejected_report["errors"] = [
        {"category": "R", "pointer": "/route_components/0", "message": "disconnected"}
    ]
    rejected = replace(
        base,
        classification="LAYOUT_INVALID",
        exit_code=1,
        status="LAYOUT_INVALID",
        report=rejected_report,
    )
    monkeypatch.setattr(finalizer.witness_io, "run_independent_checker", lambda *_args, **_kwargs: rejected)

    with pytest.raises(finalizer.witness_campaign.WitnessCampaignError) as exc_info:
        finalizer.finalize_router_result(
            launch.router_path,
            expected_router_result_sha256=launch.router_sha256,
            launcher_header_path=launch.header_path,
            expected_launcher_header_sha256=launch.header_sha256,
            launcher_classification_path=launch.classification_path,
            expected_launcher_classification_sha256=launch.classification_sha256,
            project_root=project_root,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )

    assert exc_info.value.code == "INDEPENDENT_CHECKER_REJECTED"
    assert not (tmp_path / "artifacts").exists()
    run_dir = next((tmp_path / "runs").iterdir())
    failure = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert failure["classification"] == "INDEPENDENT_CHECKER_REJECTED"
    assert failure["phase"] == "independent_acceptance"
    checker_report = json.loads((run_dir / "a001" / "checker_report.json").read_text(encoding="utf-8"))
    assert checker_report["errors"][0]["category"] == "R"


def test_objective_disagreement_is_classified_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)
    base = _checker(audit.computed)
    mismatched_report = json.loads(json.dumps(base.report))
    mismatched_report["recomputed_objective"].update({"height": 8, "area": 48})
    mismatched = replace(base, report=mismatched_report)
    assert mismatched.accepted is True
    monkeypatch.setattr(finalizer.witness_io, "run_independent_checker", lambda *_args, **_kwargs: mismatched)

    with pytest.raises(finalizer.witness_campaign.WitnessCampaignError) as exc_info:
        finalizer.finalize_router_result(
            launch.router_path,
            expected_router_result_sha256=launch.router_sha256,
            launcher_header_path=launch.header_path,
            expected_launcher_header_sha256=launch.header_sha256,
            launcher_classification_path=launch.classification_path,
            expected_launcher_classification_sha256=launch.classification_sha256,
            project_root=project_root,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )

    assert exc_info.value.code == "OBJECTIVE_AUDIT_DISAGREEMENT"
    assert not (tmp_path / "artifacts").exists()
    run_dir = next((tmp_path / "runs").iterdir())
    failure = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert failure["classification"] == "OBJECTIVE_AUDIT_DISAGREEMENT"
    assert failure["phase"] == "independent_acceptance"


def test_unexpected_exception_has_stable_phase_and_never_overwrites_existing_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _built, _audit, _checker_paths = _install_success_fakes(tmp_path, monkeypatch)
    launch = _write_launch_bundle(tmp_path, project_root)
    sentinel = {"status": "PREEXISTING_ATTEMPT_RECORD", "unchanged": True}

    def explode_with_existing_result(_result, *, bundle):
        del bundle
        attempt_dir = next((tmp_path / "runs").glob("run-*/a001"))
        finalizer.run_supervisor.write_json_exclusive(attempt_dir / "result.json", sentinel)
        raise RuntimeError("injected unexpected build failure")

    monkeypatch.setattr(finalizer.witness_campaign, "build_routed_witness", explode_with_existing_result)
    with pytest.raises(RuntimeError, match="unexpected build"):
        finalizer.finalize_router_result(
            launch.router_path,
            expected_router_result_sha256=launch.router_sha256,
            launcher_header_path=launch.header_path,
            expected_launcher_header_sha256=launch.header_sha256,
            launcher_classification_path=launch.classification_path,
            expected_launcher_classification_sha256=launch.classification_sha256,
            project_root=project_root,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )

    run_dir = next((tmp_path / "runs").iterdir())
    assert json.loads((run_dir / "a001" / "result.json").read_text(encoding="utf-8")) == sentinel
    failure = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert failure["classification"] == "UNEXPECTED_EXCEPTION"
    assert failure["exception_type"] == "RuntimeError"
    assert failure["phase"] == "build_routed_witness"
    assert not (tmp_path / "artifacts").exists()
