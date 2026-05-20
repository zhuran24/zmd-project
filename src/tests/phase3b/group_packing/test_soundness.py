from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.group_packing.soundness import (
    build_phase3b_group_packing_soundness_gate,
    render_phase3b_group_packing_soundness_markdown,
    render_phase3b_group_packing_soundness_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _runtime_payload(*, prefix_conditioned: bool) -> dict:
    if prefix_conditioned:
        surviving_after_blocked = 100
        surviving_at_failure = 14
    else:
        surviving_after_blocked = 14
        surviving_at_failure = 14
    return {
        "metadata": {"source": "phase3b_runtime_group_packing_diagnostic_v1"},
        "candidate": {"key": "69x19"},
        "diagnostics": {
            "group_packing_probe": {
                "sample_count": 1,
                "infeasible_count": 1,
                "feasible_count": 0,
                "unknown_count": 0,
                "skipped_count": 0,
                "samples": [
                    {
                        "anchor_idx": 53,
                        "group_id": "group_a",
                        "facility_type": "manufacturing_3x3",
                        "required_count": 17,
                        "surviving_after_blocked_count": surviving_after_blocked,
                        "surviving_at_failure_count": surviving_at_failure,
                        "greedy_selected_count": 3,
                        "exact_feasible": False,
                        "solver_status": "CANDIDATE_COUNT_BELOW_REQUIRED",
                    }
                ],
            }
        },
    }


def test_soundness_gate_blocks_prefix_conditioned_group_packing(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    runtime_path = project_root / "runtime.json"
    _write_json(runtime_path, _runtime_payload(prefix_conditioned=True))

    report = build_phase3b_group_packing_soundness_gate(
        project_root,
        runtime_diagnostic_path=runtime_path,
    )

    assert report["soundness"]["all_samples_infeasible"] is True
    assert report["soundness"]["terminal_elimination_sound"] is False
    assert report["soundness"]["prefix_conditioned_sample_count"] == 1
    assert report["sample_assessments"][0]["soundness_class"] == "prefix_conditioned_only"
    assert "prefix_conditioned_evidence_not_terminal_safe" in report["soundness"]["blocked_by"]

    markdown = render_phase3b_group_packing_soundness_markdown(report)
    text = render_phase3b_group_packing_soundness_text(report)
    assert "Terminal elimination sound: False" in markdown
    assert "class=prefix_conditioned_only" in text


def test_soundness_gate_passes_ghost_only_candidate_count_below_required(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    runtime_path = project_root / "runtime.json"
    _write_json(runtime_path, _runtime_payload(prefix_conditioned=False))

    report = build_phase3b_group_packing_soundness_gate(
        project_root,
        runtime_diagnostic_path=runtime_path,
    )

    assert report["soundness"]["terminal_elimination_sound"] is True
    assert report["soundness"]["blocked_by"] == []
    assert report["sample_assessments"][0]["soundness_class"] == (
        "ghost_only_candidate_count_below_required"
    )
    assert _check_status(report, "terminal_safe_coverage") == "pass"


def test_soundness_gate_reports_missing_runtime_diagnostic(tmp_path: Path) -> None:
    report = build_phase3b_group_packing_soundness_gate(tmp_path / "project")

    assert report["soundness"]["runtime_diagnostic_present"] is False
    assert "runtime_group_packing_missing" in report["soundness"]["blocked_by"]
    assert _check_status(report, "runtime_group_packing_present") == "fail"


def test_soundness_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    runtime_path = project_root / "runtime.json"
    output_dir = tmp_path / "out"
    _write_json(runtime_path, _runtime_payload(prefix_conditioned=True))
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "group_packing" / "build_soundness.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--runtime-diagnostic",
            str(runtime_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b group-packing soundness gate" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--runtime-diagnostic",
            str(runtime_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "soundness_gate_json=" in write.stdout
    payload = json.loads((output_dir / "soundness_gate.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_group_packing_soundness_gate_v1"
    assert (output_dir / "soundness_gate.md").exists()
    assert (output_dir / "soundness_gate.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
