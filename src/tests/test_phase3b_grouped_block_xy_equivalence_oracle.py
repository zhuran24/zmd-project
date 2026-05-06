from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_grouped_block_xy_equivalence_oracle import (
    build_phase3b_grouped_block_xy_equivalence_oracle,
    render_phase3b_grouped_block_xy_equivalence_oracle_markdown,
    render_phase3b_grouped_block_xy_equivalence_oracle_text,
)


def test_grouped_block_xy_oracle_blocks_when_candidate_missing(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    report = build_phase3b_grouped_block_xy_equivalence_oracle(
        tmp_path,
        scale_equivalence_path=paths["scale"],
        proto_shape_audit_path=paths["proto"],
        residual_surface_path=paths["residual"],
        selected_block_equivalence_path=paths["selected"],
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["status"]["outcome"] == "grouped_block_xy_equivalence_oracle_blocked"
    assert report["status"]["oracle_ready_for_default_off_implementation"] is False
    assert report["recommendation"]["classification"] == "grouped_relation_candidate_missing"
    assert any(
        gate["gate_id"] == "grouped_relation_candidate_present"
        and gate["status"] == "fail"
        for gate in report["gates"]
    )
    assert report["implementation_blockers"]
    assert "Grouped Block X/Y" in render_phase3b_grouped_block_xy_equivalence_oracle_markdown(report)
    assert "grouped_candidate_present=False" in render_phase3b_grouped_block_xy_equivalence_oracle_text(report)


def test_grouped_block_xy_oracle_accepts_complete_candidate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    candidate = tmp_path / "candidate.json"
    atomic_write_json(candidate, _valid_candidate())

    report = build_phase3b_grouped_block_xy_equivalence_oracle(
        tmp_path,
        scale_equivalence_path=paths["scale"],
        proto_shape_audit_path=paths["proto"],
        residual_surface_path=paths["residual"],
        selected_block_equivalence_path=paths["selected"],
        grouped_candidate_path=candidate,
    )

    assert report["status"]["outcome"] == "grouped_block_xy_equivalence_oracle_ready"
    assert report["status"]["oracle_ready_for_default_off_implementation"] is True
    assert report["implementation_blockers"] == []
    assert all(
        gate["status"] == "pass"
        for gate in report["gates"]
        if gate["blocking"]
    )


def test_grouped_block_xy_oracle_rejects_xy_decoupled_candidate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    candidate_payload = _valid_candidate()
    candidate_payload["grouped_relation"]["same_pole_xy_coupling"] = False
    candidate_payload["grouped_relation"]["relation_row_count"] = 31
    candidate = tmp_path / "candidate.json"
    atomic_write_json(candidate, candidate_payload)

    report = build_phase3b_grouped_block_xy_equivalence_oracle(
        tmp_path,
        scale_equivalence_path=paths["scale"],
        proto_shape_audit_path=paths["proto"],
        residual_surface_path=paths["residual"],
        selected_block_equivalence_path=paths["selected"],
        grouped_candidate_path=candidate,
    )

    assert report["status"]["oracle_ready_for_default_off_implementation"] is False
    assert report["recommendation"]["classification"] == "grouped_relation_candidate_failed_gates"
    assert any(
        gate["gate_id"] == "same_pole_xy_coupling_gate"
        and gate["status"] == "fail"
        for gate in report["gates"]
    )
    assert any(
        gate["gate_id"] == "grouped_relation_row_count_matches"
        and gate["status"] == "fail"
        for gate in report["gates"]
    )


def test_grouped_block_xy_oracle_rejects_counts_only_candidate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    candidate_payload = _valid_candidate()
    candidate_payload["grouped_relation"].pop("semantic_projection_equivalence")
    candidate = tmp_path / "candidate.json"
    atomic_write_json(candidate, candidate_payload)

    report = build_phase3b_grouped_block_xy_equivalence_oracle(
        tmp_path,
        scale_equivalence_path=paths["scale"],
        proto_shape_audit_path=paths["proto"],
        residual_surface_path=paths["residual"],
        selected_block_equivalence_path=paths["selected"],
        grouped_candidate_path=candidate,
    )

    assert report["status"]["oracle_ready_for_default_off_implementation"] is False
    assert any(
        gate["gate_id"] == "semantic_projection_equivalence_gate"
        and gate["status"] == "fail"
        for gate in report["gates"]
    )


def test_grouped_block_xy_oracle_handles_missing_inputs(tmp_path: Path) -> None:
    report = build_phase3b_grouped_block_xy_equivalence_oracle(
        tmp_path,
        scale_equivalence_path=tmp_path / "missing_scale.json",
        proto_shape_audit_path=tmp_path / "missing_proto.json",
        residual_surface_path=tmp_path / "missing_residual.json",
        selected_block_equivalence_path=tmp_path / "missing_selected.json",
    )

    assert report["status"]["outcome"] == "grouped_block_xy_equivalence_oracle_incomplete"
    assert report["checks"][3]["status"] == "fail"


def test_grouped_block_xy_oracle_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    paths = _write_inputs(tmp_path)
    output_dir = tmp_path / "out"
    script = repo_root / "scripts" / "build_phase3b_grouped_block_xy_equivalence_oracle.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--scale-equivalence",
            str(paths["scale"]),
            "--proto-shape-audit",
            str(paths["proto"]),
            "--residual-surface",
            str(paths["residual"]),
            "--selected-block-equivalence",
            str(paths["selected"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "phase3b grouped block x/y equivalence oracle" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--scale-equivalence",
            str(paths["scale"]),
            "--proto-shape-audit",
            str(paths["proto"]),
            "--residual-surface",
            str(paths["residual"]),
            "--selected-block-equivalence",
            str(paths["selected"]),
            "--output-dir",
            str(output_dir),
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "grouped_block_xy_equivalence_oracle_json=" in write.stdout
    payload = json.loads(
        (output_dir / "grouped_block_xy_equivalence_oracle.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_grouped_block_xy_equivalence_oracle_v1"
    assert (output_dir / "grouped_block_xy_equivalence_oracle.md").exists()
    assert (output_dir / "grouped_block_xy_equivalence_oracle.txt").exists()


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "scale": tmp_path / "scale.json",
        "proto": tmp_path / "proto.json",
        "residual": tmp_path / "residual.json",
        "selected": tmp_path / "selected.json",
    }
    atomic_write_json(
        paths["scale"],
        {
            "status": {"outcome": "active_guard_block_xy_scale_equivalence_estimated"},
            "baseline": {
                "powered_slot_count": 2,
                "pole_slot_count": 10,
                "block_size": 64,
                "block_count_per_powered_slot": 1,
                "padded_pole_position_count": 16,
                "relation_row_count": 32,
                "current_block_xy_target_variables": 8,
                "current_block_xy_element_constraints": 8,
                "current_selected_geometry_constraints": 16,
                "current_active_guard_bool_or_clauses": 32,
            },
            "candidate_estimates": {
                "direct_guarded_geometry": {
                    "risk": "too_large",
                    "net_constraint_delta": 104,
                }
            },
        },
    )
    atomic_write_json(
        paths["proto"],
        {
            "status": {"outcome": "active_guard_proto_shape_audit_passed"},
            "active_guard_shape": {
                "expected_signature_bijection_valid": True,
                "missing_expected_signature_count": 0,
                "unexpected_signature_count": 0,
                "duplicate_signature_count": 0,
                "pole_key_mismatch_count": 0,
            },
            "witness_stats": {"selected_interval_encoding": "bounds"},
        },
    )
    atomic_write_json(
        paths["residual"],
        {
            "status": {"outcome": "active_guard_residual_surface_synthesized"},
            "relationship": {
                "shared_power_pole_slot_surface": True,
                "direct_proto_edge": False,
                "missing_family_bound_anchors": [],
            },
        },
    )
    atomic_write_json(
        paths["selected"],
        {
            "status": {"outcome": "selected_block_equivalence_established"},
            "relation_equivalence": {
                "active_guard_relation": {
                    "equivalent": True,
                    "relation_row_count": 32,
                    "inactive_powered_slot_guard_equivalent": True,
                }
            },
        },
    )
    return paths


def _valid_candidate() -> dict[str, object]:
    return {
        "metadata": {
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "default_off": True,
        },
        "source_artifacts": {
            "scale_equivalence": {"path": "scale.json", "sha256": "0" * 64},
            "selected_block_equivalence": {"path": "selected.json", "sha256": "1" * 64},
            "proto_shape_audit": {"path": "proto.json", "sha256": "2" * 64},
            "grouped_oracle": {"path": "oracle.json", "sha256": "3" * 64},
        },
        "grouped_relation": {
            "powered_slot_count": 2,
            "pole_slot_count": 10,
            "block_size": 64,
            "padded_pole_position_count": 16,
            "relation_row_count": 32,
            "same_pole_xy_coupling": True,
            "semantic_projection_equivalence": {
                "evaluated": True,
                "equivalent": True,
                "relation_row_count": 32,
                "same_pole_xy_coupling_checked": True,
                "padding_identity_checked": True,
                "original_relation_hash": "a" * 64,
                "candidate_relation_hash": "a" * 64,
                "relation_hash_algorithm": "sha256:test",
                "evidence_refs": [
                    {
                        "artifact": "selected_block_equivalence",
                        "json_pointer": "/relation_equivalence/active_guard_relation",
                    },
                    {
                        "artifact": "proto_shape_audit",
                        "json_pointer": "/active_guard_shape/expected_signature_bijection_valid",
                    },
                ],
            },
            "padding_identity_preserved": True,
            "optional_inactive_guard_preserved": True,
            "mandatory_powered_behavior_preserved": True,
            "block_selector_partition_preserved": True,
            "local_selector_partition_preserved": True,
            "bounds_interval_semantics_preserved": True,
            "delta_interval_semantics_gate": "separate_gate_required",
            "family_lookup_count_unchanged": True,
            "default_off": True,
            "degenerates_to_direct_guarded_geometry": False,
            "degenerates_to_pairwise_cover_literals": False,
        },
        "field_sources": {
            "grouped_relation.powered_slot_count": [
                {"artifact": "scale_equivalence", "json_pointer": "/baseline/powered_slot_count"}
            ],
            "grouped_relation.pole_slot_count": [
                {"artifact": "scale_equivalence", "json_pointer": "/baseline/pole_slot_count"}
            ],
            "grouped_relation.block_size": [
                {"artifact": "scale_equivalence", "json_pointer": "/baseline/block_size"}
            ],
            "grouped_relation.padded_pole_position_count": [
                {"artifact": "scale_equivalence", "json_pointer": "/baseline/padded_pole_position_count"}
            ],
            "grouped_relation.relation_row_count": [
                {"artifact": "scale_equivalence", "json_pointer": "/baseline/relation_row_count"}
            ],
            "grouped_relation.same_pole_xy_coupling": [
                {"artifact": "selected_block_equivalence", "json_pointer": "/relation_equivalence/active_guard_relation"}
            ],
            "grouped_relation.semantic_projection_equivalence": [
                {"artifact": "selected_block_equivalence", "json_pointer": "/relation_equivalence/active_guard_relation"}
            ],
            "grouped_relation.family_lookup_count_unchanged": [
                {"artifact": "grouped_oracle", "json_pointer": "/semantic_contract"}
            ],
            "grouped_relation.default_off": [
                {"artifact": "grouped_oracle", "json_pointer": "/semantic_contract"}
            ],
        },
    }
