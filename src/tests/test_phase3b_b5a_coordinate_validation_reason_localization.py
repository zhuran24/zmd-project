from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_b5a_coordinate_validation_reason_localization import (
    build_phase3b_b5a_coordinate_validation_reason_localization,
    render_phase3b_b5a_coordinate_validation_reason_localization_markdown,
    render_phase3b_b5a_coordinate_validation_reason_localization_text,
)


def test_b5a_reason_localization_uses_current_source_telemetry(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    workspace = tmp_path / "workspace"
    _write_json(
        project_root / ".artifacts/post/b5a_post_acceptance_blocker_summary.json",
        {"preflight": {"failed_checks": ["b5a_anchor_found"]}},
    )
    _write_failed_inventory(project_root / ".artifacts/inventory/failed_anchor_inventory.json")
    _write_telemetry(workspace, reasons=_localized_reasons())

    report = build_phase3b_b5a_coordinate_validation_reason_localization(
        project_root,
        workspace_roots=[workspace],
        post_acceptance_blocker_summary_path=Path(
            ".artifacts/post/b5a_post_acceptance_blocker_summary.json"
        ),
        failed_anchor_inventory_path=Path(".artifacts/inventory/failed_anchor_inventory.json"),
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["reason_localization_ready"] is True
    assert report["candidate"] == {
        "key": "67x13",
        "expected_key": "67x13",
        "matches_expected": True,
    }
    assert report["status"]["certified_anchor_found"] is False
    assert report["reason_localization"]["category_counts"] == {
        "ghost_overlap_forced_domain": 1,
        "signature_monotonic_forced_label": 7,
    }
    rows = report["reason_localization"]["anchor_rows"]
    assert rows[0]["anchor_idx"] == 118
    assert rows[0]["category"] == "ghost_overlap_forced_domain"
    assert rows[1]["anchor_idx"] == 119
    assert rows[1]["category"] == "signature_monotonic_forced_label"
    assert rows[1]["forced_anchor_status_counts"] == {"UNKNOWN": 3}
    assert "Reason Localization" in render_phase3b_b5a_coordinate_validation_reason_localization_markdown(report)
    assert "reason_localization_ready=True" in render_phase3b_b5a_coordinate_validation_reason_localization_text(report)


def test_b5a_reason_localization_rejects_generic_only_samples(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    workspace = tmp_path / "workspace"
    _write_json(
        project_root / ".artifacts/post/b5a_post_acceptance_blocker_summary.json",
        {"preflight": {"failed_checks": ["b5a_anchor_found"]}},
    )
    _write_failed_inventory(project_root / ".artifacts/inventory/failed_anchor_inventory.json")
    _write_telemetry(
        workspace,
        reasons={idx: "coordinate_validation_infeasible" for idx in range(118, 126)},
    )

    report = build_phase3b_b5a_coordinate_validation_reason_localization(
        project_root,
        workspace_roots=[workspace],
        post_acceptance_blocker_summary_path=Path(
            ".artifacts/post/b5a_post_acceptance_blocker_summary.json"
        ),
        failed_anchor_inventory_path=Path(".artifacts/inventory/failed_anchor_inventory.json"),
    )

    assert report["status"]["reason_localization_ready"] is False
    assert report["status"]["generic_anchor_count"] == 8
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "requested_anchor_reason_coverage" in failed


def test_b5a_reason_localization_rejects_missing_candidate_key(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    workspace = tmp_path / "workspace"
    _write_json(
        project_root / ".artifacts/post/b5a_post_acceptance_blocker_summary.json",
        {"preflight": {"failed_checks": ["b5a_anchor_found"]}},
    )
    _write_failed_inventory(project_root / ".artifacts/inventory/failed_anchor_inventory.json")
    _write_telemetry(workspace, reasons=_localized_reasons(), candidate_key=None)

    report = build_phase3b_b5a_coordinate_validation_reason_localization(
        project_root,
        workspace_roots=[workspace],
        post_acceptance_blocker_summary_path=Path(
            ".artifacts/post/b5a_post_acceptance_blocker_summary.json"
        ),
        failed_anchor_inventory_path=Path(".artifacts/inventory/failed_anchor_inventory.json"),
    )

    assert report["status"]["reason_localization_ready"] is False
    assert report["candidate"]["key"] is None
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "candidate_locked_to_67x13" in failed


def test_b5a_reason_localization_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    project_root = tmp_path / "project"
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "out"
    _write_json(
        project_root / ".artifacts/post/b5a_post_acceptance_blocker_summary.json",
        {"preflight": {"failed_checks": ["b5a_anchor_found"]}},
    )
    _write_failed_inventory(project_root / ".artifacts/inventory/failed_anchor_inventory.json")
    _write_telemetry(workspace, reasons=_localized_reasons())
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_b5a_coordinate_validation_reason_localization.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--workspace-root",
            str(workspace),
            "--post-acceptance-blocker-summary",
            ".artifacts/post/b5a_post_acceptance_blocker_summary.json",
            "--failed-anchor-inventory",
            ".artifacts/inventory/failed_anchor_inventory.json",
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "reason localization ready: True" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--workspace-root",
            str(workspace),
            "--post-acceptance-blocker-summary",
            ".artifacts/post/b5a_post_acceptance_blocker_summary.json",
            "--failed-anchor-inventory",
            ".artifacts/inventory/failed_anchor_inventory.json",
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "b5a_coordinate_validation_reason_localization_json=" in write.stdout
    payload = json.loads(
        (
            output_dir / "b5a_coordinate_validation_reason_localization.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["reason_localization_ready"] is True
    assert (output_dir / "b5a_coordinate_validation_reason_localization.md").exists()
    assert (output_dir / "b5a_coordinate_validation_reason_localization.txt").exists()


def _localized_reasons() -> dict[int, str]:
    return {
        118: "coordinate_validation_ghost_overlap_forced_domain_infeasible",
        **{
            idx: "coordinate_validation_signature_monotonic_forced_label_infeasible"
            for idx in range(119, 126)
        },
    }


def _write_telemetry(
    workspace: Path,
    *,
    reasons: dict[int, str],
    candidate_key: str | None = "67x13",
) -> None:
    samples = [
        {
            "anchor_idx": idx,
            "failure_reason": reason,
            "blocked_cell_count": 871,
            "first_failed_group_required_count": 0,
            "first_failed_group_candidate_count": 0,
            "first_failed_group_surviving_at_failure_count": 0,
        }
        for idx, reason in sorted(reasons.items())
    ]
    counts: dict[str, int] = {}
    for reason in reasons.values():
        counts[reason] = counts.get(reason, 0) + 1
    _write_json(
        workspace / "data/checkpoints/exact_campaign_telemetry.json",
        {
            "waves": [
                {
                    "candidate_results": [
                        {
                            **(
                                {"candidate_key": candidate_key}
                                if candidate_key is not None
                                else {}
                            ),
                            "proof_status_summary": {
                                "master_start_failure_attribution": {
                                    "attempted_anchor_count": 8,
                                    "failed_anchor_count": 8,
                                    "failure_reason_counts": counts,
                                    "failed_anchor_samples": samples,
                                }
                            },
                        }
                    ]
                }
            ],
            "aggregate": {},
        },
    )


def _write_failed_inventory(path: Path) -> None:
    samples = []
    for idx in range(118, 126):
        if idx == 118:
            evidence = {"status_counts": {"INFEASIBLE": 3}, "zero_branch_unknown_count": 0}
        else:
            evidence = {"status_counts": {"UNKNOWN": 3}, "zero_branch_unknown_count": 3}
        samples.append({"anchor_idx": idx, "forced_anchor_evidence": evidence})
    _write_json(path, {"samples": samples})


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
