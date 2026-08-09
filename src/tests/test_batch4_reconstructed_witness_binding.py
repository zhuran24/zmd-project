from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from docs.research.front_offset_incident_20260718.batch4_harness import (
    validate_reconstructed_witness_binding as validator,
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tiny_project(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "project"
    candidate_path = root / "data/preprocessed/candidate_placements.json"
    mandatory_path = root / "data/preprocessed/mandatory_exact_instances.json"
    generic_path = root / "data/preprocessed/generic_io_requirements.json"
    rules_path = root / "rules/canonical_rules.json"
    preprocess_path = root / "rules/preprocess_plan.json"
    witness_path = root / "run/result.json"

    _write_json(
        candidate_path,
        {
            "facility_pools": {
                "maker": [
                    {
                        "anchor": {"x": 1, "y": 2},
                        "input_port_cells": [],
                        "occupied_cells": [[1, 2]],
                        "output_port_cells": [],
                        "pose_id": "pose-1",
                    }
                ]
            }
        },
    )
    _write_json(
        mandatory_path,
        [
            {
                "facility_type": "maker",
                "instance_id": "maker_001",
                "is_mandatory": True,
                "operation_type": "maker_operation",
            }
        ],
    )
    _write_json(
        generic_path,
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )
    _write_json(
        rules_path,
        {"commodity_metadata": {}, "globals": {"grid": {"height": 5, "width": 6}}},
    )
    _write_json(preprocess_path, {"utility_operations": {}})
    _write_json(
        witness_path,
        {
            "harness": "tiny_reconstructed",
            "placed": 1,
            "solution": {
                "maker_001": {
                    "anchor": {"x": 1, "y": 2},
                    "facility_type": "maker",
                    "pose_id": "pose-1",
                    "pose_idx": 0,
                }
            },
            "unplaced": [],
        },
    )

    recorded_inputs: dict[str, dict[str, Any]] = {}
    for relative_path in validator.INPUT_RELATIVE_PATHS[:4]:
        path = root / relative_path
        recorded_inputs[relative_path.as_posix()] = {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
    _write_json(
        witness_path.with_name("run_record.json"),
        {
            "binding_enabled": False,
            "hash_seed": 0,
            "input_sha256s": recorded_inputs,
            "outputs": {
                "result": {
                    "exists": True,
                    "filename": "result.json",
                    "sha256": _sha256(witness_path),
                    "size_bytes": witness_path.stat().st_size,
                }
            },
            "revision": {"commit": "a" * 40, "dirty": True},
            "schema": validator.EXPECTED_WITNESS_RUN_SCHEMA,
            "source": validator.PROVENANCE_LABEL,
            "source_sha256s": {"constructor.py": {"sha256": "b" * 64, "size_bytes": 1}},
        },
    )
    return root, witness_path, _sha256(candidate_path)


class _FakePortBindingModel:
    last_instance: _FakePortBindingModel | None = None

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        type(self).last_instance = self
        self.build_override: bool | None = None
        self.solve_limit: float | None = None
        self.worker_env_during_build: str | None = None
        self.model = SimpleNamespace(
            Proto=lambda: SimpleNamespace(variables=[1, 2], constraints=[1, 2, 3])
        )
        self.routing_aware_filter_stats = {
            "enabled": True,
            "filtered_patterns_total": 7,
            "front_blocked_patterns_pruned": 2,
        }
        self.generic_input_slots = [
            {"instance_id": "maker_001", "slot_id": "in:0", "x": 1, "y": 2}
        ]
        self.generic_output_slots = [
            {"instance_id": "maker_001", "slot_id": "out:0", "x": 2, "y": 2}
        ]

    def build(self, *, use_overload_separation: bool | None = None) -> None:
        self.build_override = use_overload_separation
        self.worker_env_during_build = validator.os.environ.get(validator.WORKER_ENV)

    def solve(self, time_limit_seconds: float) -> str:
        self.solve_limit = time_limit_seconds
        return "FEASIBLE"

    def extract_conflict_summary(self) -> dict[str, Any]:
        return {
            "binding_domain_count": 7,
            "binding_instance_count": 1,
            "empty_binding_domain_count": 0,
            "nested_omitted_from_scalars": {"x": 1},
            "solver_status": "OPTIMAL",
        }

    def extract_empty_binding_domain_instances(self) -> list[dict[str, Any]]:
        return []

    def extract_selection(self) -> dict[str, dict[str, Any]]:
        return {
            "binding_choice": {"maker_001": 0},
            "generic_inputs": {"in:0": "product"},
            "generic_outputs": {"out:0": "__unused__"},
        }


def _fake_context(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(
        cells_by_component={0: {(0, 0)}},
        occupied_cells=frozenset({(1, 2)}),
        occupied_owner_by_cell={(1, 2): "maker_001"},
    )


def test_full_validation_records_current_binding_provenance_and_stats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, witness_path, candidate_sha = _tiny_project(tmp_path)
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setattr(validator, "PortBindingModel", _FakePortBindingModel)
    monkeypatch.setattr(validator, "build_routing_binding_context", _fake_context)
    monkeypatch.setattr(
        validator,
        "_loaded_repository_source_records",
        lambda **_kwargs: {"validator.py": {"sha256": "c" * 64, "size_bytes": 1}},
    )

    report = validator.validate_reconstructed_witness_binding(
        witness_path,
        expected_candidate_sha256=candidate_sha,
        time_limit=4.5,
        workers=3,
        project_root=root,
        process_argv=["validator.py", str(witness_path)],
        revision={"commit": "d" * 40, "dirty": True, "status_porcelain_v1": ["?? x"]},
    )

    model = _FakePortBindingModel.last_instance
    assert model is not None
    assert model.build_override is False
    assert model.solve_limit == 4.5
    assert model.worker_env_during_build == "3"
    assert report["label"] == "reconstructed_new_baseline"
    assert report["schema_version"] == validator.SCHEMA_VERSION
    assert report["candidate_binding"]["selected_pose_count"] == 1
    assert report["candidate_binding"]["entries_with_pose_id"] == 1
    assert report["candidate_binding"]["entries_with_anchor"] == 1
    assert report["binding"]["status"] == "FEASIBLE"
    assert report["binding"]["build_stats"]["cp_model_variable_count"] == 2
    assert report["binding"]["build_stats"]["cp_model_constraint_count"] == 3
    assert report["binding"]["empty_binding_domains"] == []
    assert report["binding"]["selection_count"] == {
        "binding_choice_count": 1,
        "binding_choice_non_unused_count": 1,
        "generic_inputs_count": 1,
        "generic_inputs_non_unused_count": 1,
        "generic_outputs_count": 1,
        "generic_outputs_non_unused_count": 0,
        "non_unused_total": 2,
        "total": 3,
    }
    assert report["solver_determinism"]["cp_sat_seed_api_exposed"] is False
    assert report["solver_determinism"]["cp_sat_seed_requested"] is None
    assert report["execution"]["environment"][validator.WORKER_ENV] == "3"
    assert report["provenance"]["witness"]["source"] == "reconstructed_new_baseline"
    assert report["limitations"]["not_included"] == [
        "power optional placement",
        "routing solve",
        "certification",
    ]


def test_candidate_sha_gate_fails_before_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, witness_path, _candidate_sha = _tiny_project(tmp_path)
    monkeypatch.setenv("PYTHONHASHSEED", "0")

    with pytest.raises(validator.BindingValidationError, match="candidate pool SHA-256 mismatch"):
        validator.validate_reconstructed_witness_binding(
            witness_path,
            expected_candidate_sha256="0" * 64,
            project_root=root,
            revision={"commit": "a" * 40, "dirty": True},
        )


@pytest.mark.parametrize(
    ("field", "value", "error_fragment"),
    [
        ("pose_id", "wrong-pose", "carries pose_id"),
        ("anchor", {"x": 9, "y": 9}, "carries anchor"),
    ],
)
def test_solution_carried_pose_identity_must_match_candidate(
    field: str,
    value: Any,
    error_fragment: str,
) -> None:
    pools = {
        "maker": [
            {
                "anchor": {"x": 1, "y": 2},
                "occupied_cells": [[1, 2]],
                "pose_id": "pose-1",
            }
        ]
    }
    instances = [{"instance_id": "maker_001", "facility_type": "maker"}]
    entry = {
        "facility_type": "maker",
        "pose_idx": 0,
        field: value,
    }

    with pytest.raises(validator.BindingValidationError, match=error_fragment):
        validator._validate_placement_solution(
            {"solution": {"maker_001": entry}},
            pools,
            instances,
        )


def test_companion_run_record_must_bind_exact_witness_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, witness_path, candidate_sha = _tiny_project(tmp_path)
    run_record_path = witness_path.with_name("run_record.json")
    run_record = json.loads(run_record_path.read_text(encoding="utf-8"))
    run_record["outputs"]["result"]["sha256"] = "0" * 64
    _write_json(run_record_path, run_record)
    monkeypatch.setenv("PYTHONHASHSEED", "0")

    with pytest.raises(validator.BindingValidationError, match="result SHA-256"):
        validator.validate_reconstructed_witness_binding(
            witness_path,
            expected_candidate_sha256=candidate_sha,
            project_root=root,
            revision={"commit": "a" * 40, "dirty": True},
        )


def test_cli_refuses_existing_output_before_reading_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "binding_validation.json"
    output_path.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        validator.main(
            [
                str(tmp_path / "missing-result.json"),
                "--expected-candidate-sha256",
                "0" * 64,
                "--output",
                str(output_path),
            ]
        )

    assert "refusing to overwrite" in capsys.readouterr().err
    assert output_path.read_text(encoding="utf-8") == "sentinel\n"
