from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import stat
import sys

import pytest


harness = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.checker_mutation_harness"
)
witness_io = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.witness_io"
)


CATEGORIES = {
    "J": "strict_json",
    "S": "document_shape",
    "I": "instance_integrity",
    "F": "facility_geometry",
    "P": "port_binding",
    "PW": "power",
    "R": "routing",
    "O": "objective",
}
EXPECTED_BY_NAME = {
    "overlap": "F",
    "placement_boundary": "F",
    "front_block": "P",
    "port_exact_count": "P",
    "route_break": "R",
    "power_removal": "PW",
    "objective_plus_one": "O",
}


def _instance() -> dict:
    return {
        "grid": {"width": 20, "height": 20},
        "objective": {"minimum_side": 6},
        "facility_templates": {
            "machine": {
                "requires_power": True,
                "placement_rule": "any_body_in_grid",
                "modes": [
                    {
                        "id": "fixed",
                        "body": {"width": 2, "height": 2},
                        "ports": [
                            {
                                "id": "input_W_0",
                                "kind": "input",
                                "body_cell": {"x": 0, "y": 0},
                                "direction": "W",
                            },
                            {
                                "id": "output_E_0",
                                "kind": "output",
                                "body_cell": {"x": 1, "y": 0},
                                "direction": "E",
                            },
                        ],
                    }
                ],
            },
            "power_pole": {
                "requires_power": False,
                "placement_rule": "any_body_in_grid",
                "modes": [{"id": "fixed", "body": {"width": 2, "height": 2}, "ports": []}],
            },
        },
        "required_instances": [
            {"id": "machine_001", "template": "machine", "operation": "make"},
            {"id": "machine_002", "template": "machine", "operation": "make"},
        ],
        "power": {
            "pole_template": "power_pole",
            "coverage_from_pole_anchor": {
                "x_min_offset": -5,
                "x_max_offset": 6,
                "y_min_offset": -5,
                "y_max_offset": 6,
            },
        },
    }


def _layout() -> dict:
    return {
        "schema_version": 1,
        "instance_digest": "instance",
        "required_placements": [
            {
                "instance_id": "machine_001",
                "template": "machine",
                "mode": "fixed",
                "anchor": {"x": 5, "y": 5},
                "port_bindings": {"input_W_0": "ore", "output_E_0": "ore"},
            },
            {
                "instance_id": "machine_002",
                "template": "machine",
                "mode": "fixed",
                "anchor": {"x": 10, "y": 5},
                "port_bindings": {"input_W_0": "ore", "output_E_0": "ore"},
            },
        ],
        "optional_placements": [
            {
                "instance_id": "pole_001",
                "template": "power_pole",
                "mode": "fixed",
                "anchor": {"x": 1, "y": 1},
                "port_bindings": {},
            },
            {
                "instance_id": "pole_002",
                "template": "power_pole",
                "mode": "fixed",
                "anchor": {"x": 12, "y": 1},
                "port_bindings": {},
            },
        ],
        "route_components": [
            {
                "cell": {"x": x, "y": y},
                "kind": "straight",
                "inputs": ["W"],
                "outputs": ["E"],
                "commodities": ["ore"],
            }
            for x, y in ((4, 5), (7, 5), (9, 5), (12, 5))
        ],
        "claimed_objective": {
            "rectangle": {"x": 0, "y": 10, "width": 6, "height": 6},
            "area": 36,
            "min_side": 6,
        },
    }


def _checker_result(status: str, category: str | None = None) -> witness_io.CheckerProcessResult:
    if status == "LAYOUT_FEASIBLE":
        errors: list[dict[str, str]] = []
        report = {
            "status": status,
            "categories": CATEGORIES,
            "errors": errors,
            "recomputed_objective": {
                "x": 0,
                "y": 10,
                "width": 6,
                "height": 6,
                "area": 36,
                "min_side": 6,
            },
        }
        exit_code = 0
    else:
        assert category is not None
        report = {
            "status": "LAYOUT_INVALID",
            "categories": CATEGORIES,
            "errors": [{"category": category, "pointer": "/mutation", "message": "targeted mutation"}],
        }
        exit_code = 1
    rendered = json.dumps(report, sort_keys=True)
    return witness_io.CheckerProcessResult(
        classification=status,
        exit_code=exit_code,
        status=status,
        report=report,
        stdout=rendered,
        stderr="",
        checker_trusted=True,
        checker_sha256=witness_io.EXPECTED_CHECKER_SHA256,
        checker_source_path=str(witness_io.EXPECTED_CHECKER_PATH),
        checker_source_identity=(1, 2, stat.S_IFREG | 0o444, 1, 123, 4, 5),
        checker_snapshot_size_bytes=123,
        checker_python_executable=str(Path(sys.executable).resolve()),
        checker_execution_mode=witness_io.PINNED_CHECKER_EXECUTION_MODE,
    )


class _Runner:
    def __init__(self, survivor: str | None = None) -> None:
        self.survivor = survivor
        self.calls: list[tuple[Path, Path, float]] = []

    def __call__(self, instance_path: Path, layout_path: Path, *, timeout_seconds: float):
        self.calls.append((instance_path, layout_path, timeout_seconds))
        name = layout_path.name
        if name.startswith("baseline."):
            return _checker_result("LAYOUT_FEASIBLE")
        mutation_name = next(mutation for mutation in EXPECTED_BY_NAME if f"-{mutation}." in name)
        if mutation_name == self.survivor:
            return _checker_result("LAYOUT_FEASIBLE")
        return _checker_result("LAYOUT_INVALID", EXPECTED_BY_NAME[mutation_name])


def _write_sources(tmp_path: Path) -> tuple[Path, str, Path, str]:
    instance_path = tmp_path / "instance.json"
    layout_path = tmp_path / "layout.json"
    instance_payload = (json.dumps(_instance(), sort_keys=True) + "\n").encode()
    layout_payload = (json.dumps(_layout(), sort_keys=True) + "\n").encode()
    instance_path.write_bytes(instance_payload)
    layout_path.write_bytes(layout_payload)
    return (
        instance_path,
        hashlib.sha256(instance_payload).hexdigest(),
        layout_path,
        hashlib.sha256(layout_payload).hexdigest(),
    )


def test_generates_all_seven_single_change_mutations() -> None:
    mutations = harness.generate_mutations(_instance(), _layout())

    assert {mutation.name: mutation.expected_category for mutation in mutations} == EXPECTED_BY_NAME
    assert len(mutations) == 7
    baseline = _layout()
    for mutation in mutations:
        assert mutation.layout != baseline


def test_runs_baseline_and_every_mutation_through_trusted_checker(tmp_path: Path) -> None:
    instance_path, instance_sha256, layout_path, layout_sha256 = _write_sources(tmp_path)
    runner = _Runner()
    report_path = tmp_path / "mutation-report.json"

    outcome = harness.run_checker_mutation_harness(
        instance_path,
        layout_path,
        expected_instance_sha256=instance_sha256,
        expected_layout_sha256=layout_sha256,
        report_path=report_path,
        checker_runner=runner,
    )

    assert outcome.accepted
    assert outcome.report["status"] == harness.REPORT_SUCCESS_STATUS
    assert len(runner.calls) == 8
    assert len({call[0] for call in runner.calls}) == 1
    assert runner.calls[0][0] != instance_path
    assert {row["name"]: row["expected_category"] for row in outcome.report["mutations"]} == EXPECTED_BY_NAME
    assert all(row["passed"] for row in outcome.report["mutations"])
    assert all(row["observed_categories"] == [row["expected_category"]] for row in outcome.report["mutations"])
    persisted = json.loads(report_path.read_text(encoding="ascii"))
    assert persisted["summary"] == {
        "mutation_count": 7,
        "passed_count": 7,
        "failed_count": 0,
        "all_rejected_with_expected_category": True,
    }
    assert persisted["source"]["instance"]["sha256"] == instance_sha256
    assert persisted["source"]["layout"]["sha256"] == layout_sha256

    with pytest.raises(harness.CheckerMutationHarnessError) as exc_info:
        harness.run_checker_mutation_harness(
            instance_path,
            layout_path,
            expected_instance_sha256=instance_sha256,
            expected_layout_sha256=layout_sha256,
            report_path=report_path,
            checker_runner=runner,
        )
    assert exc_info.value.code == "REPORT_ALREADY_EXISTS"


def test_checker_accepting_a_mutation_fails_the_harness_but_still_writes_report(tmp_path: Path) -> None:
    instance_path, instance_sha256, layout_path, layout_sha256 = _write_sources(tmp_path)
    runner = _Runner(survivor="objective_plus_one")
    report_path = tmp_path / "survivor-report.json"

    outcome = harness.run_checker_mutation_harness(
        instance_path,
        layout_path,
        expected_instance_sha256=instance_sha256,
        expected_layout_sha256=layout_sha256,
        report_path=report_path,
        checker_runner=runner,
    )

    assert not outcome.accepted
    assert outcome.report["status"] == harness.REPORT_FAILURE_STATUS
    objective = next(row for row in outcome.report["mutations"] if row["name"] == "objective_plus_one")
    assert objective["passed"] is False
    assert objective["checker"]["accepted"] is True
    assert outcome.report["summary"]["failed_count"] == 1
    assert report_path.is_file()


def test_hash_mismatch_stops_before_checker_or_output(tmp_path: Path) -> None:
    instance_path, _instance_sha256, layout_path, layout_sha256 = _write_sources(tmp_path)
    runner = _Runner()
    report_path = tmp_path / "report.json"

    with pytest.raises(harness.CheckerMutationHarnessError) as exc_info:
        harness.run_checker_mutation_harness(
            instance_path,
            layout_path,
            expected_instance_sha256="0" * 64,
            expected_layout_sha256=layout_sha256,
            report_path=report_path,
            checker_runner=runner,
        )

    assert exc_info.value.code == "SOURCE_HASH_MISMATCH"
    assert runner.calls == []
    assert not report_path.exists()


@pytest.mark.parametrize(
    "timeout_seconds",
    [True, False, 0, -1, float("nan"), float("inf"), "1"],
)
def test_invalid_timeout_stops_before_snapshot_or_checker(
    tmp_path: Path,
    timeout_seconds: object,
) -> None:
    instance_path, instance_sha256, layout_path, layout_sha256 = _write_sources(tmp_path)
    runner = _Runner()
    report_path = tmp_path / "report.json"

    with pytest.raises(harness.CheckerMutationHarnessError) as exc_info:
        harness.run_checker_mutation_harness(
            instance_path,
            layout_path,
            expected_instance_sha256=instance_sha256,
            expected_layout_sha256=layout_sha256,
            report_path=report_path,
            checker_timeout_seconds=timeout_seconds,
            checker_runner=runner,
        )

    assert exc_info.value.code == "CHECKER_TIMEOUT_INVALID"
    assert runner.calls == []
    assert not (tmp_path / "report.inputs").exists()
    assert not report_path.exists()


def test_cli_rejects_output_outside_research_subtree_before_reading_inputs(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"

    exit_code = harness.run_cli(
        [
            "--instance",
            str(tmp_path / "missing-instance.json"),
            "--layout",
            str(tmp_path / "missing-layout.json"),
            "--expected-instance-sha256",
            "0" * 64,
            "--expected-layout-sha256",
            "1" * 64,
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 2
    assert not report_path.exists()
