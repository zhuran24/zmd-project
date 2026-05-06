from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_grouped_block_xy_candidate import (
    build_phase3b_grouped_block_xy_candidate,
    render_phase3b_grouped_block_xy_candidate_markdown,
    render_phase3b_grouped_block_xy_candidate_text,
)
from src.search.phase3b_grouped_block_xy_equivalence_oracle import (
    build_phase3b_grouped_block_xy_equivalence_oracle,
)


def test_grouped_block_xy_candidate_builds_source_backed_candidate(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)

    report = build_phase3b_grouped_block_xy_candidate(
        tmp_path,
        scale_equivalence_path=paths["scale"],
        selected_block_equivalence_path=paths["selected"],
        proto_shape_audit_path=paths["proto"],
        grouped_oracle_path=paths["oracle"],
    )

    relation = report["grouped_relation"]
    semantic = relation["semantic_projection_equivalence"]
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["status"]["outcome"] == "grouped_block_xy_candidate_built"
    assert relation["relation_row_count"] == 32
    assert semantic["equivalent"] is True
    assert semantic["original_relation_hash"] == semantic["candidate_relation_hash"]
    assert report["source_artifacts"]["scale_equivalence"]["sha256"]
    assert "grouped_relation.semantic_projection_equivalence" in report["field_sources"]
    assert "Grouped Block X/Y Candidate" in render_phase3b_grouped_block_xy_candidate_markdown(report)
    assert "projection_equivalent=True" in render_phase3b_grouped_block_xy_candidate_text(report)


def test_grouped_block_xy_candidate_passes_grouped_oracle(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    candidate = build_phase3b_grouped_block_xy_candidate(
        tmp_path,
        scale_equivalence_path=paths["scale"],
        selected_block_equivalence_path=paths["selected"],
        proto_shape_audit_path=paths["proto"],
        grouped_oracle_path=paths["oracle"],
    )
    candidate_path = tmp_path / "candidate.json"
    atomic_write_json(candidate_path, candidate)

    oracle = build_phase3b_grouped_block_xy_equivalence_oracle(
        tmp_path,
        scale_equivalence_path=paths["scale"],
        proto_shape_audit_path=paths["proto"],
        residual_surface_path=paths["residual"],
        selected_block_equivalence_path=paths["selected"],
        grouped_candidate_path=candidate_path,
    )

    assert oracle["status"]["outcome"] == "grouped_block_xy_equivalence_oracle_ready"
    assert oracle["status"]["oracle_ready_for_default_off_implementation"] is True


def test_grouped_block_xy_candidate_handles_missing_inputs(tmp_path: Path) -> None:
    report = build_phase3b_grouped_block_xy_candidate(
        tmp_path,
        scale_equivalence_path=tmp_path / "missing_scale.json",
        selected_block_equivalence_path=tmp_path / "missing_selected.json",
        proto_shape_audit_path=tmp_path / "missing_proto.json",
        grouped_oracle_path=tmp_path / "missing_oracle.json",
    )

    assert report["status"]["outcome"] == "grouped_block_xy_candidate_incomplete"
    assert report["checks"][2]["status"] == "fail"


def test_grouped_block_xy_candidate_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_grouped_block_xy_candidate.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--scale-equivalence",
            str(paths["scale"]),
            "--selected-block-equivalence",
            str(paths["selected"]),
            "--proto-shape-audit",
            str(paths["proto"]),
            "--grouped-oracle",
            str(paths["oracle"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "phase3b grouped block x/y candidate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--scale-equivalence",
            str(paths["scale"]),
            "--selected-block-equivalence",
            str(paths["selected"]),
            "--proto-shape-audit",
            str(paths["proto"]),
            "--grouped-oracle",
            str(paths["oracle"]),
            "--output-dir",
            str(output_dir),
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "grouped_block_xy_candidate_json=" in write.stdout
    payload = json.loads(
        (output_dir / "grouped_block_xy_candidate.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_grouped_block_xy_candidate_v1"
    assert (output_dir / "grouped_block_xy_candidate.md").exists()
    assert (output_dir / "grouped_block_xy_candidate.txt").exists()


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "scale": tmp_path / "scale.json",
        "selected": tmp_path / "selected.json",
        "proto": tmp_path / "proto.json",
        "oracle": tmp_path / "oracle.json",
        "residual": tmp_path / "residual.json",
    }
    atomic_write_json(
        paths["scale"],
        {
            "metadata": {"source": "scale_source"},
            "status": {"outcome": "active_guard_block_xy_scale_equivalence_estimated"},
            "baseline": {
                "powered_slot_count": 2,
                "pole_slot_count": 10,
                "block_size": 4,
                "block_count_per_powered_slot": 4,
                "padded_pole_position_count": 16,
                "relation_row_count": 32,
            },
            "candidate_estimates": {"direct_guarded_geometry": {"risk": "too_large"}},
        },
    )
    atomic_write_json(
        paths["selected"],
        {
            "metadata": {"source": "selected_source"},
            "status": {"outcome": "relations_equivalent"},
            "relation_equivalence": {
                "active_guard_relation": {
                    "equivalent": True,
                    "relation_row_count": 32,
                    "inactive_powered_slot_guard_equivalent": True,
                }
            },
        },
    )
    atomic_write_json(
        paths["proto"],
        {
            "metadata": {"source": "proto_source"},
            "status": {"outcome": "active_guard_proto_shape_valid"},
            "active_guard_shape": {
                "expected_signature_bijection_valid": True,
                "expected_signature_hash": "abc",
            },
        },
    )
    atomic_write_json(
        paths["oracle"],
        {
            "metadata": {"source": "oracle_source"},
            "status": {"outcome": "grouped_block_xy_equivalence_oracle_blocked"},
            "semantic_contract": ["family lookup unchanged", "default-off"],
        },
    )
    atomic_write_json(
        paths["residual"],
        {
            "metadata": {"source": "residual_source"},
            "status": {"outcome": "active_guard_residual_surface_synthesized"},
            "relationship": {
                "shared_power_pole_slot_surface": True,
                "direct_proto_edge": False,
                "missing_family_bound_anchors": [],
            },
        },
    )
    return paths
