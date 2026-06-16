from __future__ import annotations

import json
from pathlib import Path

from src.search.exact_campaign import compute_exact_artifact_hashes


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _write_minimal_exact_project(root: Path) -> None:
    _write_json(root / "rules" / "canonical_rules.json", {"facility_templates": {}})
    _write_json(root / "rules" / "preprocess_plan.json", {"utility_operations": {}})
    _write_json(root / "data" / "preprocessed" / "candidate_placements.json", {"facility_pools": {}})
    _write_json(root / "data" / "preprocessed" / "mandatory_exact_instances.json", [])
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )


def test_exact_artifact_hashes_bind_preprocess_plan_when_present(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_minimal_exact_project(project_root)

    before = compute_exact_artifact_hashes(project_root)
    _write_json(
        project_root / "rules" / "preprocess_plan.json",
        {"utility_operations": {"boundary_io": {"generic_output_slots": 999}}},
    )
    after = compute_exact_artifact_hashes(project_root)

    assert "preprocess_plan" in before
    assert before["preprocess_plan"] != after["preprocess_plan"]
    assert {k: v for k, v in before.items() if k != "preprocess_plan"} == {
        k: v for k, v in after.items() if k != "preprocess_plan"
    }
