"""P1.2-FIX-5 red tests: the certified session snapshots frozen artifacts atomically.

ExactSearchSession.create used to read the frozen artifacts once to parse/build and a
second, independent time to hash (compute_exact_artifact_hashes).  A swap/drift between
those reads produced a session whose recorded artifact_hashes did not attest the bytes
the master core was built from.  FIX-5 reads each artifact's bytes ONCE, hashes those
bytes, and parses/builds from the same bytes, so the recorded hash provably attests the
solved bytes.  These tests pin that property.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from src.models.binding_subproblem import (
    PortBindingModel,
    load_generic_io_requirements_from_text,
    load_generic_input_slots_by_operation,
    load_generic_input_slots_by_operation_from_text,
)
from src.models.master_model import load_project_data, load_project_data_from_texts
from src.search.exact_campaign import (
    EXACT_HASH_FILES,
    compute_exact_artifact_hashes,
    read_once_exact_artifact_snapshot,
    _read_once_regular_file_bytes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENDERS_LOOP_PATH = PROJECT_ROOT / "src" / "search" / "benders_loop.py"

_BUILD_KEYS = (
    "mandatory_exact_instances",
    "candidate_placements",
    "canonical_rules",
    "generic_io_requirements",
    "preprocess_plan",
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )


def _build_tiny_project(root: Path) -> Path:
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 2, "height": 1},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
            },
            "commodity_metadata": {},
        },
    )
    _write_json(
        root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_x0_y0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                ]
            }
        },
    )
    _write_json(
        root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "operation_type": "",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )
    _write_json(
        root / "rules" / "preprocess_plan.json",
        {
            "utility_operations": {
                "box_sink": {"generic_input_slots": 3},
                "protocol_core": {"generic_input_slots": 14},
            }
        },
    )
    return root


def _build_role_validation_project(root: Path) -> Path:
    _build_tiny_project(root)
    canonical_rules = json.loads((root / "rules" / "canonical_rules.json").read_text(
        encoding="utf-8"
    ))
    canonical_rules["commodity_metadata"] = {
        "snapshot_output": {"source_kind": "external_boundary", "sink_kind": "none"},
        "snapshot_input": {"source_kind": "none", "sink_kind": "generic_input"},
    }
    _write_json(root / "rules" / "canonical_rules.json", canonical_rules)
    _write_json(
        root / "data" / "preprocessed" / "generic_io_requirements.json",
        {
            "required_generic_outputs": {"snapshot_output": 1},
            "required_generic_inputs": {"snapshot_input": 1},
        },
    )
    return root


def test_fix5_snapshot_hash_attests_returned_text_bytes(tmp_path: Path) -> None:
    # The core FIX-5 property: each recorded hash is the hash of the exact bytes the
    # caller will parse/build from (single read, no swap window).
    root = _build_tiny_project(tmp_path / "project")
    hashes, texts = read_once_exact_artifact_snapshot(root)
    for key in _BUILD_KEYS:
        assert key in texts, key
        assert hashlib.sha256(texts[key].encode("utf-8")).hexdigest() == hashes[key]


def test_fix5_snapshot_hashes_match_compute_exact_artifact_hashes(tmp_path: Path) -> None:
    # Same hash semantics as the legacy function -> recorded continuity is unchanged
    # for a legitimate single-process run.
    root = _build_tiny_project(tmp_path / "project")
    snapshot_hashes, _texts = read_once_exact_artifact_snapshot(root)
    legacy_hashes = compute_exact_artifact_hashes(root)
    for key in EXACT_HASH_FILES:
        assert snapshot_hashes[key] == legacy_hashes[key]
    assert snapshot_hashes["preprocess_plan"] == legacy_hashes["preprocess_plan"]


def test_fix5_text_loaders_are_faithful_to_path_loaders(tmp_path: Path) -> None:
    # The atomic text-parse path must produce identical project data to the disk path.
    root = _build_tiny_project(tmp_path / "project")
    _hashes, texts = read_once_exact_artifact_snapshot(root)
    instances_t, pools_t, rules_t = load_project_data_from_texts(
        instances_text=texts["mandatory_exact_instances"],
        placements_text=texts["candidate_placements"],
        rules_text=texts["canonical_rules"],
        solve_mode="certified_exact",
    )
    instances_p, pools_p, rules_p = load_project_data(root, solve_mode="certified_exact")
    assert instances_t == instances_p
    assert pools_t == pools_p
    assert rules_t == rules_p
    text_slot_map = load_generic_input_slots_by_operation_from_text(
        text=texts["preprocess_plan"]
    )
    assert text_slot_map == {"box_sink": 3, "protocol_core": 14}
    assert text_slot_map == load_generic_input_slots_by_operation(project_root=root)


def test_fix5_canonical_role_validation_uses_snapshot_after_disk_swap(
    tmp_path: Path,
) -> None:
    root = _build_role_validation_project(tmp_path / "project")
    _hashes, texts = read_once_exact_artifact_snapshot(root)
    snapshot_rules = json.loads(texts["canonical_rules"])

    replacement_rules = json.loads(texts["canonical_rules"])
    replacement_rules["commodity_metadata"]["disk_only_input"] = {
        "source_kind": "none",
        "sink_kind": "generic_input",
    }
    _write_json(root / "rules" / "canonical_rules.json", replacement_rules)

    with pytest.raises(ValueError, match="disk_only_input"):
        load_generic_io_requirements_from_text(
            text=texts["generic_io_requirements"],
            project_root=root,
        )

    requirements = load_generic_io_requirements_from_text(
        text=texts["generic_io_requirements"],
        project_root=root,
        canonical_rules_payload=snapshot_rules,
    )
    assert requirements == {
        "required_generic_outputs": {"snapshot_output": 1},
        "required_generic_inputs": {"snapshot_input": 1},
    }

    binding_model = PortBindingModel(
        placement_solution={},
        facility_pools={},
        instances=[],
        project_root=root,
        required_generic_outputs=requirements["required_generic_outputs"],
        required_generic_inputs=requirements["required_generic_inputs"],
        generic_input_slots_by_operation={"box_sink": 3, "protocol_core": 14},
        utility_operation_by_template={
            "protocol_storage_box": "box_sink",
            "protocol_core": "protocol_core",
        },
        canonical_rules_payload=snapshot_rules,
    )
    assert binding_model.generic_input_commodities == {"snapshot_input"}


def test_fix5_read_once_regular_file_bytes_rejects_non_regular(tmp_path: Path) -> None:
    # Same fail-closed guard as sha256_file: a directory / non-regular path is rejected.
    with pytest.raises(FileNotFoundError):
        _read_once_regular_file_bytes(tmp_path / "missing.json")
    a_dir = tmp_path / "a_dir"
    a_dir.mkdir()
    with pytest.raises(ValueError):
        _read_once_regular_file_bytes(a_dir)


def test_fix5_create_uses_atomic_snapshot_not_second_read() -> None:
    # Durability guard mirror: ExactSearchSession.create must snapshot once and must not
    # recompute hashes from a second disk read (the TOCTOU window).
    tree = ast.parse(BENDERS_LOOP_PATH.read_text(encoding="utf-8"))
    create_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ExactSearchSession":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "create":
                    create_fn = child
    assert create_fn is not None
    called = {
        n.func.id
        for n in ast.walk(create_fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "read_once_exact_artifact_snapshot" in called
    assert "load_project_data_from_texts" in called
    assert "compute_exact_artifact_hashes" not in called
