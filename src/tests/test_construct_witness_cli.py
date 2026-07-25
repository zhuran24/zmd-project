"""Focused lifecycle tests for the no-overwrite witness CLI."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest


RUNNER = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.construct_witness"
)
OBJECTIVE = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.objective_audit"
)
WITNESS_IO = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.witness_io"
)


@dataclass(frozen=True)
class _Reconciliation:
    candidate_counts: dict[str, int]
    hashes: dict[str, str]

    def counts(self) -> dict[str, int]:
        return {"mandatory_instances": 266, "active_terminals": 628}


class _Built:
    def __init__(self, audit: Any) -> None:
        self.witness = {
            "schema_version": 1,
            "instance_digest": "sha256:" + "1" * 64,
            "required_placements": [],
            "optional_placements": [],
            "route_components": [],
            "claimed_objective": {
                "rectangle": {"x": 1, "y": 63, "width": 6, "height": 7},
                "area": 42,
                "min_side": 6,
            },
        }
        self.objective = audit

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "WITNESS_BUILT",
            "pole_count": 9,
            "box_count": 0,
            "claim_boundary": RUNNER.CLAIM_BOUNDARY,
        }


def _audit() -> Any:
    rectangle = OBJECTIVE.EmptyRectangle(1, 63, 6, 7, 42, 6)
    return OBJECTIVE.ObjectiveAudit(rectangle, rectangle, 3553)


def _checker() -> Any:
    report = {
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
        "recomputed_objective": {
            "x": 1,
            "y": 63,
            "width": 6,
            "height": 7,
            "area": 42,
            "min_side": 6,
        },
    }
    return WITNESS_IO.CheckerProcessResult(
        classification="LAYOUT_FEASIBLE",
        exit_code=0,
        status="LAYOUT_FEASIBLE",
        report=report,
        stdout=json.dumps(report),
        stderr="",
        checker_trusted=True,
        checker_sha256=WITNESS_IO.EXPECTED_CHECKER_SHA256,
        checker_source_path=str(WITNESS_IO.EXPECTED_CHECKER_PATH),
        checker_source_identity=(1, 2, 0o100444, 1, 123, 4, 5),
        checker_snapshot_size_bytes=123,
        checker_python_executable=str(Path(sys.executable).resolve()),
        checker_execution_mode=WITNESS_IO.PINNED_CHECKER_EXECUTION_MODE,
    )


def _install_success_fakes(monkeypatch: Any, tmp_path: Path) -> tuple[Any, Any, Any, Path]:
    instance_path = tmp_path / "problem_instance.json"
    instance_path.write_text("{}\n", encoding="utf-8")
    geometry_result = tmp_path / "geometry-worker-result.json"
    geometry_result.write_text('{"status":"FEASIBLE","cgroup_telemetry":{}}\n', encoding="utf-8")
    hashes = {
        "strict_instance": "a" * 64,
        "canonical_rules": "b" * 64,
        "mandatory_instances": "c" * 64,
        "generic_io": "d" * 64,
        "candidate_poses": "e" * 64,
    }
    bundle = SimpleNamespace(
        strict_instance=SimpleNamespace(path=instance_path, value={}),
        hashes=hashes,
    )
    reconciliation = _Reconciliation({"power_pole": 4761}, hashes)
    candidate = SimpleNamespace(
        protected_rect=SimpleNamespace(x=1, y=63, width=6, height=7),
        boundary_pattern=SimpleNamespace(left_gap=69, bottom_gap=0),
        diagnostics={"required_count": 266, "pole_count": 9},
    )
    built = _Built(_audit())
    monkeypatch.setattr(RUNNER.strict_contract, "load_and_reconcile", lambda _root: (bundle, reconciliation))
    monkeypatch.setattr(RUNNER, "_repository_head", lambda _root: RUNNER.EXPECTED_BASELINE_HEAD)
    monkeypatch.setattr(
        RUNNER.shelf_constructor,
        "construct_shelf_candidate",
        lambda *, project_root, result_path: candidate,
    )
    monkeypatch.setattr(
        RUNNER.witness_campaign,
        "build_witness",
        lambda observed_candidate, *, bundle: built,
    )
    monkeypatch.setattr(RUNNER, "_audit_layout_file", lambda _bundle, _path: built.objective)
    return bundle, candidate, built, geometry_result


def test_success_stops_after_a001_and_publishes_full_acceptance_set(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    bundle, candidate, built, geometry_result = _install_success_fakes(monkeypatch, tmp_path)
    checker_calls: list[tuple[Path, Path, dict[str, Any]]] = []
    geometry_replays: list[tuple[Path, Path]] = []

    def replay(*, project_root: Path, result_path: Path) -> Any:
        geometry_replays.append((project_root, result_path))
        return candidate

    def check(instance_path: Path, layout_path: Path, **kwargs: Any) -> Any:
        checker_calls.append((instance_path, layout_path, kwargs))
        return _checker()

    monkeypatch.setattr(RUNNER.witness_io, "run_independent_checker", check)
    monkeypatch.setattr(RUNNER.shelf_constructor, "construct_shelf_candidate", replay)
    monkeypatch.setattr(
        RUNNER.witness_campaign,
        "accept_independent_checker",
        lambda observed_built, checker: {"status": "INDEPENDENT_ACCEPTANCE_OK"},
    )
    outcome = RUNNER.run_campaign(
        geometry_result=geometry_result,
        project_root=tmp_path,
        run_root=tmp_path / "runs",
        publish_root=tmp_path / "artifacts",
        checker_timeout_seconds=7.0,
    )

    assert outcome.accepted is True
    assert outcome.accepted_attempt == 1
    assert (outcome.run_dir / "a001").is_dir()
    assert not (outcome.run_dir / "a002").exists()
    assert not (outcome.run_dir / "a003").exists()
    assert outcome.layout_path is not None
    assert json.loads(outcome.layout_path.read_text(encoding="ascii")) == built.witness
    assert len(geometry_replays) == 1
    assert geometry_replays[0][0] == tmp_path.resolve()
    assert geometry_replays[0][1] != geometry_result
    assert geometry_replays[0][1].read_bytes() == geometry_result.read_bytes()
    run_header = json.loads((outcome.run_dir / "run_header.json").read_text())
    assert run_header["geometry_result_source"]["size_bytes"] == geometry_result.stat().st_size
    assert checker_calls == [
        (
            bundle.strict_instance.path,
            outcome.layout_path,
            {"timeout_seconds": 7.0},
        )
    ]
    attempt = outcome.run_dir / "a001"
    attempt_header = json.loads((attempt / "attempt_header.json").read_text())
    assert attempt_header["geometry_result_source"]["sha256"] == attempt_header[
        "geometry_result_snapshot"
    ]["sha256"]
    assert json.loads((attempt / "checker_report.json").read_text())["errors"] == []
    checker_process = json.loads((attempt / "checker_process.json").read_text())
    assert checker_process["checker_sha256"] == WITNESS_IO.EXPECTED_CHECKER_SHA256
    assert checker_process["checker_source_path"] == str(WITNESS_IO.EXPECTED_CHECKER_PATH)
    assert checker_process["checker_source_identity"]["size_bytes"] == 123
    assert checker_process["checker_execution_mode"] == WITNESS_IO.PINNED_CHECKER_EXECUTION_MODE
    assert checker_process["stderr"] == ""
    assert json.loads((attempt / "objective_audit.json").read_text())["computed"]["area"] == 42
    assert json.loads((attempt / "candidate_diagnostics.json").read_text())["constructor_diagnostics"] == {
        "pole_count": 9,
        "required_count": 266,
    }
    summary = json.loads(outcome.summary_path.read_text())
    assert summary["status"] == "LAYOUT_ACCEPTED"
    assert summary["box_schedule"] == [0, 1, 2]
    assert summary["claim_boundary"] == RUNNER.CLAIM_BOUNDARY
    assert summary["feasible_lower_bound"] == {"area": 42, "min_side": 6}
    assert outcome.manifest_path is not None
    manifest = json.loads(outcome.manifest_path.read_text())
    assert set(manifest["files"]) == {
        "acceptance",
        "candidate_diagnostics",
        "checker_process",
        "checker_report",
        "geometry_result",
        "layout",
        "objective_audit",
    }
    published_geometry = (tmp_path / "artifacts" / manifest["files"]["geometry_result"]["path"])
    assert published_geometry.read_bytes() == geometry_result.read_bytes()


def test_failed_box_zero_creates_later_attempts_as_explicitly_unsupported(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _bundle, _candidate, _built, geometry_result = _install_success_fakes(monkeypatch, tmp_path)

    class GeometryFailure(RuntimeError):
        code = "GEOMETRY_NO_SOLUTION"

    def fail_geometry(*, project_root: Path, result_path: Path) -> Any:
        raise GeometryFailure(f"failed under {project_root}")

    monkeypatch.setattr(RUNNER.shelf_constructor, "construct_shelf_candidate", fail_geometry)
    outcome = RUNNER.run_campaign(
        geometry_result=geometry_result,
        project_root=tmp_path,
        run_root=tmp_path / "runs",
        publish_root=tmp_path / "artifacts",
    )

    assert outcome.accepted is False
    assert [path.name for path in sorted(outcome.run_dir.glob("a*"))] == ["a001", "a002", "a003"]
    first = json.loads((outcome.run_dir / "a001" / "attempt_result.json").read_text())
    assert first["classification"] == "GEOMETRY_NO_SOLUTION"
    for ordinal, box_count in ((2, 1), (3, 2)):
        result = json.loads((outcome.run_dir / f"a{ordinal:03d}" / "attempt_result.json").read_text())
        assert result["status"] == "ATTEMPT_NOT_RUN"
        assert result["classification"] == "UNSUPPORTED_BOX_GEOMETRY"
        assert result["box_count"] == box_count
        assert "not evidence" in result["schedule_interpretation"]
    summary = json.loads(outcome.summary_path.read_text())
    assert summary["status"] == "NO_ACCEPTED_LAYOUT"
    assert summary["unsupported_box_counts"] == [1, 2]
    assert summary["schedule_interpretation"] == "unsupported branches carry no feasibility conclusion"


def test_layout_mutation_after_audit_cannot_reach_checker_or_publication(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _bundle, _candidate, built, geometry_result = _install_success_fakes(monkeypatch, tmp_path)
    checker_called = False

    def mutate_after_read(_bundle: Any, path: Path) -> Any:
        path.write_text("{}\n", encoding="utf-8")
        return built.objective

    def unexpected_checker(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal checker_called
        checker_called = True
        return _checker()

    monkeypatch.setattr(RUNNER, "_audit_layout_file", mutate_after_read)
    monkeypatch.setattr(RUNNER.witness_io, "run_independent_checker", unexpected_checker)
    outcome = RUNNER.run_campaign(
        geometry_result=geometry_result,
        project_root=tmp_path,
        run_root=tmp_path / "runs",
        publish_root=tmp_path / "artifacts",
    )

    assert outcome.accepted is False
    assert checker_called is False
    first = json.loads((outcome.run_dir / "a001" / "attempt_result.json").read_text())
    assert first["classification"] == "LAYOUT_DRIFT_AFTER_OBJECTIVE_AUDIT"
    assert not (tmp_path / "artifacts").exists()


def test_independent_checker_rejection_cannot_publish_layout(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _bundle, _candidate, _built, geometry_result = _install_success_fakes(monkeypatch, tmp_path)
    report = _checker().report
    assert report is not None
    report["status"] = "LAYOUT_INVALID"
    report["errors"] = [
        {
            "category": "R",
            "pointer": "/route_components/0",
            "message": "route mutation disconnected an active terminal",
        }
    ]
    rejected = WITNESS_IO.CheckerProcessResult(
        classification="LAYOUT_INVALID",
        exit_code=1,
        status="LAYOUT_INVALID",
        report=report,
        stdout=json.dumps(report),
        stderr="",
        checker_trusted=True,
        checker_sha256=WITNESS_IO.EXPECTED_CHECKER_SHA256,
    )
    monkeypatch.setattr(
        RUNNER.witness_io,
        "run_independent_checker",
        lambda *_args, **_kwargs: rejected,
    )

    outcome = RUNNER.run_campaign(
        geometry_result=geometry_result,
        project_root=tmp_path,
        run_root=tmp_path / "runs",
        publish_root=tmp_path / "artifacts",
    )

    assert outcome.accepted is False
    first_attempt = outcome.run_dir / "a001"
    failure = json.loads((first_attempt / "attempt_result.json").read_text())
    assert failure["phase"] == "independent_acceptance"
    assert failure["classification"] == "INDEPENDENT_CHECKER_REJECTED"
    assert failure["checker_classification"] == "LAYOUT_INVALID"
    checker_report = json.loads((first_attempt / "checker_report.json").read_text())
    assert checker_report["errors"][0]["category"] == "R"
    assert not (tmp_path / "artifacts").exists()


def test_verify_reruns_audit_and_pinned_checker_and_writes_exclusive_report(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    bundle, _candidate, built, _geometry_result = _install_success_fakes(monkeypatch, tmp_path)
    layout = tmp_path / "existing-layout.json"
    layout.write_text("{}\n", encoding="utf-8")
    audit_calls: list[Path] = []
    checker_calls: list[tuple[Path, Path, dict[str, Any]]] = []

    def audit(_bundle: Any, path: Path) -> Any:
        audit_calls.append(path)
        return built.objective

    def check(instance_path: Path, path: Path, **kwargs: Any) -> Any:
        checker_calls.append((instance_path, path, kwargs))
        return _checker()

    monkeypatch.setattr(RUNNER, "_audit_layout_file", audit)
    monkeypatch.setattr(RUNNER.witness_io, "run_independent_checker", check)
    outcome = RUNNER.verify_layout(
        layout,
        project_root=tmp_path,
        run_root=tmp_path / "runs",
        checker_timeout_seconds=9.0,
    )

    assert outcome.accepted is True
    assert len(audit_calls) == 1
    checked_layout = audit_calls[0]
    assert checked_layout != layout.resolve()
    assert checked_layout.read_bytes() == layout.read_bytes()
    assert checker_calls == [
        (bundle.strict_instance.path, checked_layout, {"timeout_seconds": 9.0})
    ]
    report = json.loads(outcome.report_path.read_text())
    assert report["status"] == "LAYOUT_ACCEPTED"
    assert report["objective_audit"]["computed"]["area"] == 42
    assert report["checker"]["report"]["errors"] == []
    assert report["checker"]["stderr"] == ""
    assert report["layout_source"]["sha256"] == report["checked_layout_snapshot"]["sha256"]
    assert report["claim_boundary"] == RUNNER.CLAIM_BOUNDARY


def test_exact_agreement_rejects_checker_objective_drift() -> None:
    checker = _checker()
    checker.report["recomputed_objective"]["height"] = 8
    checker.report["recomputed_objective"]["area"] = 48

    try:
        RUNNER._require_exact_checker_agreement(_audit(), checker)
    except RUNNER.ConstructWitnessError as exc:
        assert exc.code == "OBJECTIVE_AUDIT_DISAGREEMENT"
    else:
        raise AssertionError("objective drift was accepted")


def test_direct_script_cli_requires_explicit_geometry_result() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(RUNNER.__file__)), "run", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "--geometry-result GEOMETRY_RESULT" in completed.stdout
    assert "no latest-" in completed.stdout
    assert "result discovery" in completed.stdout


def test_campaign_has_no_head_override_and_rejects_live_head_drift(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _bundle, _candidate, _built, geometry_result = _install_success_fakes(monkeypatch, tmp_path)
    monkeypatch.setattr(RUNNER, "_repository_head", lambda _root: "0" * 40)

    with pytest.raises(RUNNER.ConstructWitnessError) as exc_info:
        RUNNER.run_campaign(
            geometry_result=geometry_result,
            project_root=tmp_path,
            run_root=tmp_path / "runs",
            publish_root=tmp_path / "artifacts",
        )

    assert exc_info.value.code == "BASELINE_HEAD_MISMATCH"
