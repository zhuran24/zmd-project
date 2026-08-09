from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from scripts import preflight_gate
from src.preprocess.material_skeleton import (
    DEFAULT_SKELETON_RELATIVE_PATH,
    build_material_connection_skeleton,
    material_skeleton_digest,
)
from src.preprocess.material_skeleton_verifier import verify_material_skeleton_file
from src.search import certified_artifact_contract, exact_campaign

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _copy_material_inputs(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "rules").mkdir(parents=True)
    (root / "data" / "preprocessed").mkdir(parents=True)
    for rel_path in (
        "rules/canonical_rules.json",
        "rules/canonical_rules.schema.json",
        "rules/preprocess_plan.json",
        "rules/preprocess_plan.schema.json",
        "data/preprocessed/machine_counts.json",
        "data/preprocessed/mandatory_exact_instances.json",
        "data/preprocessed/generic_io_requirements.json",
        "data/preprocessed/commodity_demands.json",
    ):
        source = PROJECT_ROOT / rel_path
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return root


def test_material_skeleton_sidecar_matches_independent_recompute() -> None:
    sidecar_path = PROJECT_ROOT / DEFAULT_SKELETON_RELATIVE_PATH
    sidecar = _load_json(sidecar_path)
    recomputed = build_material_connection_skeleton(PROJECT_ROOT)
    verification = verify_material_skeleton_file(sidecar_path, project_root=PROJECT_ROOT)

    assert sidecar == recomputed
    assert verification.ok is True
    assert verification.actual_digest == verification.expected_digest


def test_material_skeleton_records_current_contract_counts_and_pool_edges() -> None:
    skeleton = build_material_connection_skeleton(PROJECT_ROOT)

    assert skeleton["totals"]["recipe_group_count"] == 17
    assert skeleton["totals"]["manufacturing_instance_count"] == 219
    assert skeleton["totals"]["boundary_port_instance_count"] == 46
    assert skeleton["totals"]["protocol_core_instance_count"] == 1
    assert skeleton["totals"]["mandatory_exact_instance_count"] == 266
    assert skeleton["warehouses"]["generic_output_requirements"] == {
        "blue_iron_ore": 34,
        "source_ore": 18,
    }
    assert skeleton["warehouses"]["generic_input_requirements"] == {
        "qiaoyu_capsule": 1,
        "valley_battery": 1,
    }

    edges = {edge["commodity_id"]: edge for edge in skeleton["material_edges"]}
    assert [producer["group_id"] for producer in edges["steel_block"]["producers"]] == [
        "operation:refinery_steel"
    ]
    assert [consumer["group_id"] for consumer in edges["steel_block"]["consumers"]] == [
        "operation:molding_bottle",
        "operation:parts_maker",
    ]
    assert edges["steel_block"]["pool_exchangeable"] is True
    assert {group["cycle_group"] for group in skeleton["cycle_material_groups"]} == {
        "buckwheat_cycle",
        "sandleaf_cycle",
    }
    assert all(check["passed"] for check in skeleton["consistency_checks"])


def test_material_skeleton_digest_changes_when_source_inputs_change(tmp_path: Path) -> None:
    baseline = build_material_connection_skeleton(PROJECT_ROOT)
    baseline_digest = material_skeleton_digest(baseline)

    canonical_root = _copy_material_inputs(tmp_path / "canonical")
    canonical_rules = _load_json(canonical_root / "rules" / "canonical_rules.json")
    canonical_rules["recipes"]["parts_maker"]["inputs"]["steel_block"] = 2
    _write_json(canonical_root / "rules" / "canonical_rules.json", canonical_rules)
    assert material_skeleton_digest(build_material_connection_skeleton(canonical_root)) != baseline_digest

    counts_root = _copy_material_inputs(tmp_path / "counts")
    machine_counts = _load_json(counts_root / "data" / "preprocessed" / "machine_counts.json")
    machine_counts["crusher_blue_iron"] += 1
    _write_json(counts_root / "data" / "preprocessed" / "machine_counts.json", machine_counts)
    instances = _load_json(counts_root / "data" / "preprocessed" / "mandatory_exact_instances.json")
    added = copy.deepcopy(instances[0])
    added["instance_id"] = "crusher_blue_iron_035"
    instances.append(added)
    _write_json(counts_root / "data" / "preprocessed" / "mandatory_exact_instances.json", instances)
    assert material_skeleton_digest(build_material_connection_skeleton(counts_root)) != baseline_digest

    generic_root = _copy_material_inputs(tmp_path / "generic")
    generic_io = _load_json(generic_root / "data" / "preprocessed" / "generic_io_requirements.json")
    generic_io["required_generic_outputs"]["source_ore"] += 1
    _write_json(generic_root / "data" / "preprocessed" / "generic_io_requirements.json", generic_io)
    assert material_skeleton_digest(build_material_connection_skeleton(generic_root)) != baseline_digest


def test_material_skeleton_is_not_registered_as_certified_artifact() -> None:
    sidecar = DEFAULT_SKELETON_RELATIVE_PATH.as_posix()

    assert sidecar not in preflight_gate.FROZEN_ARTIFACTS
    assert sidecar not in preflight_gate.EXTERNAL_FROZEN_ARTIFACTS
    assert sidecar not in exact_campaign.EXACT_HASH_FILES.values()
    assert sidecar not in exact_campaign.OPTIONAL_EXACT_HASH_FILES.values()
    assert sidecar not in certified_artifact_contract.LOCKED_EXACT_ARTIFACT_PATHS.values()


def test_material_skeleton_has_no_certified_runtime_consumers() -> None:
    # (a) No runtime/postprocess module reads the diagnostic sidecar file by path.
    scanned_roots = (
        "src/search",
        "src/models",
        "src/io",
        "src/cuts",
        "src/runtime",
        "src/adapters",
        "src/render",
    )
    sidecar_hits: list[str] = []
    for root_name in scanned_roots:
        root = PROJECT_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "material_connection_skeleton.json" in path.read_text(encoding="utf-8"):
                sidecar_hits.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert sidecar_hits == [], f"diagnostic skeleton sidecar read by runtime modules: {sidecar_hits}"

    # (b) The proof-bearing certified modules must not reference the skeleton at all
    #     (neither the sidecar literal nor the `material_skeleton` module import), so it
    #     can never become a proof input. The diagnostic consumer (topology_guidance) and
    #     the producers (src/preprocess/material_skeleton*) are intentionally excluded.
    proof_bearing_modules = (
        "src/search/exact_campaign.py",
        "src/search/outer_search.py",
        "src/search/certified_frontier.py",
        "src/search/certified_surface.py",
        "src/search/candidate_proof_replay.py",
        "src/cuts/lifecycle.py",
    )
    proof_hits: list[str] = []
    for rel in proof_bearing_modules:
        path = PROJECT_ROOT / rel
        if path.exists() and "material_skeleton" in path.read_text(encoding="utf-8"):
            proof_hits.append(rel)
    assert proof_hits == [], f"proof-bearing module references material_skeleton: {proof_hits}"
