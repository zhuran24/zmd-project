from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_grouped_block_xy_implementation_preflight import (
    build_phase3b_grouped_block_xy_implementation_preflight,
    render_phase3b_grouped_block_xy_implementation_preflight_markdown,
    render_phase3b_grouped_block_xy_implementation_preflight_text,
)


def test_grouped_block_xy_implementation_preflight_ready(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, oracle_ready=True)

    report = build_phase3b_grouped_block_xy_implementation_preflight(
        tmp_path,
        grouped_candidate_path=paths["candidate"],
        grouped_oracle_path=paths["oracle"],
        scale_equivalence_path=paths["scale"],
    )

    status = report["status"]
    counts = report["expected_no_solve_stats"]
    assert status["outcome"] == "grouped_block_xy_implementation_preflight_ready"
    assert status["ready_for_default_off_model_edit"] is True
    assert report["metadata"]["solver_invoked"] is False
    assert report["proposed_mode"]["value"] == "selected_block_active_guard_grouped_xy"
    assert counts["proposed_grouped_xy_target_variables"] == 4
    assert counts["proposed_grouped_xy_element_constraints"] == 4
    assert counts["proposed_selected_geometry_constraints"] == 8
    assert "Grouped Block X/Y Implementation Preflight" in (
        render_phase3b_grouped_block_xy_implementation_preflight_markdown(report)
    )
    assert "ready_for_default_off_model_edit=True" in (
        render_phase3b_grouped_block_xy_implementation_preflight_text(report)
    )


def test_grouped_block_xy_implementation_preflight_blocks_if_oracle_not_ready(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, oracle_ready=False)

    report = build_phase3b_grouped_block_xy_implementation_preflight(
        tmp_path,
        grouped_candidate_path=paths["candidate"],
        grouped_oracle_path=paths["oracle"],
        scale_equivalence_path=paths["scale"],
    )

    assert report["status"]["outcome"] == "grouped_block_xy_implementation_preflight_blocked"
    assert report["status"]["ready_for_default_off_model_edit"] is False
    assert any(check["check_id"] == "oracle_ready" and check["status"] == "fail" for check in report["checks"])


def test_grouped_block_xy_implementation_preflight_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    paths = _write_inputs(tmp_path, oracle_ready=True)
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_grouped_block_xy_implementation_preflight.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--grouped-candidate",
            str(paths["candidate"]),
            "--grouped-oracle",
            str(paths["oracle"]),
            "--scale-equivalence",
            str(paths["scale"]),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "phase3b grouped block x/y implementation preflight" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--grouped-candidate",
            str(paths["candidate"]),
            "--grouped-oracle",
            str(paths["oracle"]),
            "--scale-equivalence",
            str(paths["scale"]),
            "--output-dir",
            str(output_dir),
        ],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        check=True,
    )
    assert "grouped_block_xy_implementation_preflight_json=" in write.stdout
    payload = json.loads(
        (output_dir / "grouped_block_xy_implementation_preflight.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_grouped_block_xy_implementation_preflight_v1"
    assert (output_dir / "grouped_block_xy_implementation_preflight.md").exists()
    assert (output_dir / "grouped_block_xy_implementation_preflight.txt").exists()


def _write_inputs(tmp_path: Path, *, oracle_ready: bool) -> dict[str, Path]:
    paths = {
        "candidate": tmp_path / "candidate.json",
        "oracle": tmp_path / "oracle.json",
        "scale": tmp_path / "scale.json",
    }
    atomic_write_json(
        paths["candidate"],
        {
            "metadata": {"source": "phase3b_grouped_block_xy_candidate_v1"},
            "status": {"outcome": "grouped_block_xy_candidate_built"},
            "grouped_relation": {
                "powered_slot_count": 2,
                "relation_row_count": 32,
            },
        },
    )
    atomic_write_json(
        paths["oracle"],
        {
            "metadata": {"source": "phase3b_grouped_block_xy_equivalence_oracle_v1"},
            "status": {
                "outcome": "grouped_block_xy_equivalence_oracle_ready"
                if oracle_ready
                else "grouped_block_xy_equivalence_oracle_blocked",
                "oracle_ready_for_default_off_implementation": oracle_ready,
            },
        },
    )
    atomic_write_json(
        paths["scale"],
        {
            "metadata": {"source": "phase3b_active_guard_block_xy_scale_equivalence_v1"},
            "status": {"outcome": "active_guard_block_xy_scale_equivalence_estimated"},
            "baseline": {
                "powered_slot_count": 2,
                "relation_row_count": 32,
                "current_block_xy_target_variables": 8,
                "current_block_xy_element_constraints": 8,
                "current_selected_geometry_constraints": 16,
                "current_active_guard_bool_or_clauses": 32,
                "current_block_selected_literals": 4,
                "current_local_selected_literals": 8,
            },
        },
    )
    return paths
