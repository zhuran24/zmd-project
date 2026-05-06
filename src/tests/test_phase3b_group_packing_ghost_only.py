from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b_group_packing_ghost_only as ghost_only_module
from src.search.phase3b_group_packing_ghost_only import (
    build_phase3b_group_packing_ghost_only_verifier,
    render_phase3b_group_packing_ghost_only_markdown,
    render_phase3b_group_packing_ghost_only_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "69x19": {
                "ghost_rect": {"w": 69, "h": 19, "area": 1311},
                "attempts": 1,
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 1,
                        "failed_anchor_samples": [
                            {
                                "anchor_idx": 0,
                                "first_failed_group_position": 0,
                                "first_failed_group_id": "group_a",
                                "first_failed_group_template": "tpl",
                                "first_failed_group_required_count": 2,
                            }
                        ],
                    }
                },
            }
        },
    }


class _FakeModel:
    def __init__(self, pose_cells: dict[int, set[tuple[int, int]]]) -> None:
        self._pose_cells_by_idx = pose_cells
        self._ghost_domains = [{"cells": [[0, 0]]}]
        self._mandatory_groups = [
            {"group_id": "group_a", "facility_type": "tpl", "count": 2}
        ]

    def _candidate_pose_indices_for_group(self, group: dict) -> list[int]:
        return sorted(self._pose_cells_by_idx)

    def _ordered_mandatory_groups_for_greedy(
        self,
        candidates_by_group: dict,
    ) -> list[dict]:
        return list(self._mandatory_groups)

    def _pose_cells(self, tpl: str, pose_idx: int) -> set[tuple[int, int]]:
        return set(self._pose_cells_by_idx[int(pose_idx)])


def _patch_fake_model(monkeypatch, model: _FakeModel) -> None:
    monkeypatch.setattr(
        ghost_only_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        ghost_only_module.MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: model),
    )


def test_ghost_only_verifier_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_group_packing_ghost_only_verifier(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_ghost_only_verifier_finds_greedy_feasible_counterexample(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")
    _patch_fake_model(
        monkeypatch,
        _FakeModel(
            {
                0: {(1, 0)},
                1: {(2, 0)},
                2: {(3, 0)},
            }
        ),
    )

    report = build_phase3b_group_packing_ghost_only_verifier(
        project_root,
        sample_limit=1,
    )

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["status"]["outcome"] == "ghost_only_feasible_counterexample_found"
    sample = report["ghost_only_verifier"]["samples"][0]
    assert sample["ghost_only_feasible"] is True
    assert sample["solver_status"] == "GREEDY_FEASIBLE_WITNESS"

    markdown = render_phase3b_group_packing_ghost_only_markdown(report)
    text = render_phase3b_group_packing_ghost_only_text(report)
    assert "Ghost-only feasible: 1" in markdown
    assert "outcome=ghost_only_feasible_counterexample_found" in text


def test_ghost_only_verifier_can_report_candidate_count_infeasible(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_fake_model(
        monkeypatch,
        _FakeModel(
            {
                0: {(0, 0)},
                1: {(1, 0)},
            }
        ),
    )

    report = build_phase3b_group_packing_ghost_only_verifier(
        project_root,
        sample_limit=1,
    )

    assert report["status"]["outcome"] == "ghost_only_uniformly_infeasible"
    sample = report["ghost_only_verifier"]["samples"][0]
    assert sample["ghost_only_feasible"] is False
    assert sample["solver_status"] == "CANDIDATE_COUNT_BELOW_REQUIRED"


def test_ghost_only_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_group_packing_ghost_only.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b ghost-only group-packing verifier" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "ghost_only_group_packing_json=" in write.stdout
    payload = json.loads(
        (output_dir / "ghost_only_group_packing_69x19.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_group_packing_ghost_only_verifier_v1"
    assert (output_dir / "ghost_only_group_packing_69x19.md").exists()
    assert (output_dir / "ghost_only_group_packing_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
