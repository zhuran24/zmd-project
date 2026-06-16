from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.mandatory_core.mandatory_core_matrix as matrix_module
from src.search.phase3b.mandatory_core.mandatory_core_matrix import (
    build_phase3b_mandatory_core_profile_matrix,
    render_phase3b_mandatory_core_profile_matrix_markdown,
    render_phase3b_mandatory_core_profile_matrix_text,
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
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 1,
                        "failed_anchor_samples": [{"anchor_idx": 56}],
                    }
                },
            }
        },
    }


class _FakeVar:
    def __init__(self, index: int) -> None:
        self._index = int(index)

    def Index(self) -> int:
        return int(self._index)


class _FakeSlot:
    def __init__(self, index: int) -> None:
        self.active = _FakeVar(index)


def _patch_matrix(monkeypatch, statuses: dict[tuple[str, bool], str]) -> None:
    def fake_build(*args, master_search_profile, enable_symmetry_breaking, **kwargs):
        model = SimpleNamespace(
            u_vars={56: _FakeVar(100)},
            _coordinate_delegate=SimpleNamespace(
                residual_optional_slots={"power_pole": [_FakeSlot(201)]}
            ),
            build_stats={
                "search_guidance": {
                    "decision_strategy_phases": ["ghost", "mandatory_slots"]
                },
                "coordinate_symmetry": {
                    "enabled": bool(enable_symmetry_breaking),
                    "mandatory_signature_monotonic_constraints": 1
                    if enable_symmetry_breaking
                    else 0,
                },
            },
        )
        return model, object()

    def fake_solve(
        base_proto,
        *,
        master_search_profile,
        symmetry_enabled,
        **kwargs,
    ):
        return {
            "anchor_idx": 56,
            "master_search_profile": str(master_search_profile),
            "symmetry_enabled": bool(symmetry_enabled),
            "evaluated": True,
            "status": statuses[(str(master_search_profile), bool(symmetry_enabled))],
            "branches": 10,
            "conflicts": 1,
            "decision_strategy_phases": ["ghost", "mandatory_slots"],
        }

    monkeypatch.setattr(matrix_module, "_build_mandatory_core_overlay", fake_build)
    monkeypatch.setattr(matrix_module, "_solve_mandatory_core_clone", fake_solve)


def test_mandatory_core_matrix_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_mandatory_core_profile_matrix(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_mandatory_core_matrix_counts_profiles_and_symmetry(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")
    _patch_matrix(
        monkeypatch,
        {
            ("p1", True): "UNKNOWN",
            ("p1", False): "UNKNOWN",
            ("p2", True): "INFEASIBLE",
            ("p2", False): "UNKNOWN",
        },
    )

    report = build_phase3b_mandatory_core_profile_matrix(
        project_root,
        anchor_indices=[56],
        master_profiles=["p1", "p2"],
        symmetry_modes=[True, False],
    )

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["status"]["outcome"] == "mandatory_core_profile_sensitive"
    assert report["matrix"]["status_counts"] == {"UNKNOWN": 3, "INFEASIBLE": 1}
    assert report["matrix"]["status_counts_by_profile"]["p2"] == {
        "INFEASIBLE": 1,
        "UNKNOWN": 1,
    }

    markdown = render_phase3b_mandatory_core_profile_matrix_markdown(report)
    text = render_phase3b_mandatory_core_profile_matrix_text(report)
    assert "Mandatory-Core Profile Matrix" in markdown
    assert "mutated_mandatory_core_not_proof_source" in text


def test_mandatory_core_matrix_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "profile_phase3b_mandatory_core_matrix.py"

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

    assert "phase3b mandatory-core profile matrix" in no_write.stdout
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

    assert "mandatory_core_matrix_json=" in write.stdout
    payload = json.loads(
        (output_dir / "mandatory_core_matrix_69x19.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_mandatory_core_profile_matrix_v1"
    assert (output_dir / "mandatory_core_matrix_69x19.md").exists()
    assert (output_dir / "mandatory_core_matrix_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
