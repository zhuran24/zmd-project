import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import src.search.phase3b.protocol.protocol_witness_prefix_audit as audit_module
from src.search.phase3b.protocol.protocol_witness_prefix_audit import (
    build_phase3b_protocol_witness_prefix_audit,
    render_phase3b_protocol_witness_prefix_audit_markdown,
    render_phase3b_protocol_witness_prefix_audit_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "candidates": {
            "67x13": {
                "ghost_rect": {"w": 67, "h": 13, "area": 871},
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_samples": [{"anchor_idx": 119}]
                    }
                },
            }
        }
    }


def _proto_reduction_payload(entries: list[dict]) -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_proto_reduction_v1"},
        "status": {"outcome": "proto_reduction_terminal_found"},
        "reduction": {"entries": entries},
    }


def _entry(
    variant: str,
    *,
    status: str,
    branches: int,
    conflicts: int,
    replacement: dict | None = None,
) -> dict:
    return {
        "variant": variant,
        "status": status,
        "branches": branches,
        "conflicts": conflicts,
        "wall_time": 12.5,
        "deterministic_time": 3.0,
        "replacement_payload": replacement or {"added_constraint_count": 0},
        "response_stats_parsed": {"status": status},
    }


class _FakeDelegate:
    residual_optional_slots = {
        "power_pole": [object() for _ in range(763)],
        "protocol_storage_box": [object() for _ in range(544)],
    }
    _power_pole_family_order = ["family_034", "family_001"]
    _power_pole_family_coefficients = {
        "family_034": {
            "manufacturing_3x3": 24,
            "manufacturing_5x5": 12,
            "manufacturing_6x4": 16,
            "protocol_storage_box": 24,
        },
        "family_001": {
            "manufacturing_3x3": 8,
            "manufacturing_5x5": 3,
            "manufacturing_6x4": 4,
            "protocol_storage_box": 8,
        },
    }
    _power_pole_family_pose_counts = {"family_034": 2401, "family_001": 16}

    def _power_pole_family_count_upper_bound(self, family_name: str) -> int:
        if family_name == "family_034":
            return 763
        return int(self._power_pole_family_pose_counts.get(family_name, 0))


class _FakeModel:
    _coordinate_delegate = _FakeDelegate()
    build_stats = {
        "global_valid_inequalities": {
            "powered_template_demands": {
                "manufacturing_3x3": 132,
                "manufacturing_5x5": 49,
                "manufacturing_6x4": 38,
                "protocol_storage_box": 1,
            },
            "optional_cardinality_bounds": {
                "power_pole": {
                    "mode": "selected_powered_upper_bound",
                    "slot_pool_upper_bound": 763,
                },
                "protocol_storage_box": {
                    "lower": 1,
                    "slot_pool_upper_bound": 544,
                },
            }
        },
        "coordinate_symmetry": {"power_pole_family_order_constraints": 762},
    }


def test_protocol_witness_prefix_audit_summarizes_prefix_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    monkeypatch.setattr(
        audit_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (_FakeModel(), object()),
    )
    index_path = project_root / "index.json"
    lookup_path = project_root / "lookup_intact.json"
    window_path = project_root / "window.json"
    guard_path = project_root / "guard.json"
    _write_json(
        index_path,
        _proto_reduction_payload(
            [
                _entry(
                    "remove_power_coverage_elements_except_template_protocol_storage_box_and_family_lookup_table",
                    status="UNKNOWN",
                    branches=0,
                    conflicts=0,
                ),
                _entry(
                    "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_first_256_and_family_lookup_table",
                    status="OPTIMAL",
                    branches=33376,
                    conflicts=1271,
                    replacement={
                        "restriction_mode": "first",
                        "lower_bound": 0,
                        "upper_bound": 255,
                        "window_width": 256,
                        "added_constraint_count": 544,
                    },
                ),
            ]
        ),
    )
    _write_json(
        lookup_path,
        _proto_reduction_payload(
            [
                _entry(
                    "remove_power_coverage_elements_except_template_protocol_storage_box_keep_family_lookup_table",
                    status="UNKNOWN",
                    branches=0,
                    conflicts=0,
                ),
                _entry(
                    "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_first_4",
                    status="UNKNOWN",
                    branches=0,
                    conflicts=0,
                    replacement={
                        "restriction_mode": "first",
                        "lower_bound": 0,
                        "upper_bound": 3,
                        "window_width": 4,
                        "added_constraint_count": 544,
                    },
                ),
            ]
        ),
    )
    _write_json(
        window_path,
        _proto_reduction_payload(
            [
                _entry(
                    "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_window_256_256_and_family_lookup_table",
                    status="INFEASIBLE",
                    branches=25959,
                    conflicts=1169,
                    replacement={
                        "restriction_mode": "window",
                        "lower_bound": 256,
                        "upper_bound": 511,
                        "window_width": 256,
                        "added_constraint_count": 1088,
                    },
                )
            ]
        ),
    )
    _write_json(
        guard_path,
        _proto_reduction_payload(
            [
                _entry(
                    "remove_power_coverage_elements_except_template_protocol_storage_box_and_add_template_index_active_prefix_guard_and_family_lookup_table",
                    status="UNKNOWN",
                    branches=0,
                    conflicts=0,
                    replacement={
                        "mode": "template_cover_choice_index_active_prefix_guard",
                        "added_constraint_count": 544,
                    },
                )
            ]
        ),
    )

    report = build_phase3b_protocol_witness_prefix_audit(
        project_root,
        candidate="67x13",
        anchor_indices=[119],
        index_restrict_path=index_path,
        lookup_intact_prefix_path=lookup_path,
        window_restrict_path=window_path,
        active_prefix_guard_path=guard_path,
    )

    assert report["metadata"]["source"] == "phase3b_protocol_witness_prefix_audit_v1"
    assert report["status"]["outcome"] == "semantic_prefix_shrink_candidate"
    assert report["overlay"]["power_pole_slot_count"] == 763
    assert report["overlay"]["protocol_slot_count"] == 544
    assert report["analysis"]["best_terminal_first_limit"] == 256
    assert report["analysis"]["unrestricted_protocol_zero_branch"] is True
    assert report["analysis"]["active_prefix_guard_outcome"] == "zero_branch_unknown"
    assert report["analysis"]["lookup_intact_prefix_outcome"] == "zero_branch_unknown"
    assert (
        report["analysis"]["lookup_intact_prefix_assessment"]["status"]
        == "prefix_requires_family_lookup_change"
    )
    family_prefix = report["overlay"]["family_prefix_capacity"]
    assert family_prefix["first_ordered_family"]["family"] == "family_034"
    assert family_prefix["first_ordered_family"]["minimum_slots_for_all_demands"] == 6
    assert (
        report["analysis"]["family_prefix_capacity_assessment"]["status"]
        == "capacity_consistent_with_terminal_prefix"
    )
    assert _check_status(report, "prefix_evidence_present") == "pass"
    assert "Protocol Witness Prefix Audit" in render_phase3b_protocol_witness_prefix_audit_markdown(report)
    assert "Family Prefix Capacity" in render_phase3b_protocol_witness_prefix_audit_markdown(report)
    assert "best_terminal_first_limit=256" in render_phase3b_protocol_witness_prefix_audit_text(report)
    assert "first_family_min_slots_for_all_demands=6" in render_phase3b_protocol_witness_prefix_audit_text(report)


def test_protocol_witness_prefix_audit_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_protocol_witness_prefix_audit(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_protocol_witness_prefix_audit_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "protocol" / "build_protocol_witness_prefix_audit.py"
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"

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
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b protocol witness-prefix audit" in no_write.stdout
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
        text=True,
        capture_output=True,
        check=True,
    )

    assert "protocol_witness_prefix_audit_json=" in write.stdout
    payload = json.loads(
        (output_dir / "protocol_witness_prefix_audit.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_protocol_witness_prefix_audit_v1"
    assert (output_dir / "protocol_witness_prefix_audit.md").exists()
    assert (output_dir / "protocol_witness_prefix_audit.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    for check in report.get("checks", []):
        if check.get("check_id") == check_id:
            return check.get("status")
    raise AssertionError(f"check not found: {check_id}")
