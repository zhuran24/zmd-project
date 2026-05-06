from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ortools.sat.python import cp_model

from src.search import phase3b_protocol_target_channel_slot_audit as audit


def test_protocol_target_map_groups_template_slots_and_targets() -> None:
    model = cp_model.CpModel()
    idx = model.NewIntVar(0, 1, "idx")
    source0 = model.NewIntVar(0, 10, "source0")
    source1 = model.NewIntVar(0, 10, "source1")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_block_active = model.NewBoolVar(
        "cover_choice_block_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_x = model.NewIntVar(
        0,
        70,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    protocol_block_x = model.NewIntVar(
        0,
        70,
        "cover_choice_block_x__residual_optional::protocol_storage_box::slot::1",
    )
    protocol_y = model.NewIntVar(
        0,
        70,
        "cover_choice_y__residual_optional::protocol_storage_box::slot::1",
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    for target in (
        protocol_active,
        protocol_block_active,
        protocol_x,
        protocol_block_x,
        protocol_y,
        manufacturing_active,
    ):
        model.AddElement(idx, [source0, source1], target)

    payload = audit._build_protocol_target_channel_map(
        model.Proto(),
        powered_template="protocol_storage_box",
        target_tokens=("active_x", "active_y", "active_xy"),
        sample_limit=8,
    )

    assert payload["mapped_protocol_slot_count"] == 2
    assert payload["by_prefix"]["cover_choice_active__"]["constraint_count"] == 1
    assert payload["by_prefix"]["cover_choice_block_active__"]["constraint_count"] == 1
    assert payload["by_prefix"]["cover_choice_x__"]["constraint_count"] == 1
    assert payload["by_prefix"]["cover_choice_block_x__"]["constraint_count"] == 1
    assert payload["by_prefix"]["cover_choice_y__"]["constraint_count"] == 1
    assert payload["by_target_token"]["active_x"]["constraint_count"] == 4
    assert payload["by_target_token"]["active_y"]["constraint_count"] == 3
    assert payload["by_target_token"]["active_xy"]["constraint_count"] == 5


def test_forced_status_by_anchor_target_extracts_template_variants() -> None:
    proto_reduction = {
        "reduction": {
            "entries": [
                {
                    "anchor_idx": 118,
                    "variant": "base",
                    "evaluated": True,
                    "status": "UNKNOWN",
                    "removed_constraint_count": 0,
                    "branches": 0,
                    "conflicts": 0,
                },
                {
                    "anchor_idx": 118,
                    "variant": "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_keep_family_lookup_table",
                    "evaluated": True,
                    "status": "INFEASIBLE",
                    "removed_constraint_count": 4,
                    "branches": 2,
                    "conflicts": 1,
                    "reduction_payload": {"family_lookup_table_removed": False},
                },
                {
                    "anchor_idx": 125,
                    "variant": "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_keep_family_lookup_table",
                    "evaluated": True,
                    "status": "UNKNOWN",
                    "removed_constraint_count": 4,
                    "branches": 10,
                    "conflicts": 3,
                },
                {
                    "anchor_idx": 118,
                    "variant": "remove_power_coverage_elements_template_manufacturing_3x3_target_active_x_keep_family_lookup_table",
                    "evaluated": True,
                    "status": "OPTIMAL",
                    "removed_constraint_count": 99,
                },
            ]
        }
    }

    payload = audit._forced_status_by_anchor_target(
        proto_reduction,
        powered_template="protocol_storage_box",
        target_tokens=("active_x",),
        anchor_indices=(118, 125),
    )

    assert payload["118"]["base"]["status"] == "UNKNOWN"
    assert payload["118"]["active_x"]["status"] == "INFEASIBLE"
    assert payload["125"]["active_x"]["branches"] == 10
    assert "manufacturing_3x3" not in payload["118"]


def test_family_bounds_by_anchor_extracts_requested_family() -> None:
    anchor_differential = {
        "anchors": [
            {
                "anchor_idx": 118,
                "family_count_linear_refs": [
                    {
                        "active_family_count_bounds": [
                            {
                                "family_name": "family_009",
                                "implied_upper_when_anchor_active": 480.0,
                                "family_domain_upper": 612,
                            }
                        ]
                    }
                ],
            },
            {
                "anchor_idx": 125,
                "family_count_linear_refs": [
                    {
                        "active_family_count_bounds": [
                            {
                                "family_name": "family_009",
                                "implied_upper_when_anchor_active": 547.0,
                                "family_domain_upper": 612,
                            }
                        ]
                    }
                ],
            },
        ]
    }

    payload = audit._family_bounds_by_anchor(
        anchor_differential,
        family_names=("family_009",),
        anchor_indices=(118, 125),
    )

    assert payload["118"]["family_009"]["implied_upper_when_anchor_active"] == 480.0
    assert payload["125"]["family_009"]["implied_upper_when_anchor_active"] == 547.0


def test_build_report_with_fake_overlay_and_synthetic_artifacts(tmp_path, monkeypatch) -> None:
    project_root = tmp_path
    campaign_path = project_root / "campaign.json"
    proto_path = project_root / "proto.json"
    diff_path = project_root / "diff.json"
    campaign_path.write_text(
        json.dumps(
            {
                "candidates": {
                    "67x13": {
                        "status": "UNKNOWN",
                        "ghost_rect": {"w": 67, "h": 13, "area": 871},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    proto_path.write_text(
        json.dumps(
            {
                "reduction": {
                    "entries": [
                        {
                            "anchor_idx": 118,
                            "variant": "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_keep_family_lookup_table",
                            "evaluated": True,
                            "status": "INFEASIBLE",
                            "removed_constraint_count": 2,
                            "branches": 2,
                            "conflicts": 1,
                        },
                        {
                            "anchor_idx": 125,
                            "variant": "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_keep_family_lookup_table",
                            "evaluated": True,
                            "status": "UNKNOWN",
                            "removed_constraint_count": 2,
                            "branches": 20,
                            "conflicts": 2,
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    diff_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "anchor_idx": 118,
                        "family_count_linear_refs": [
                            {
                                "active_family_count_bounds": [
                                    {
                                        "family_name": "family_009",
                                        "implied_upper_when_anchor_active": 1,
                                    }
                                ]
                            }
                        ],
                    },
                    {
                        "anchor_idx": 125,
                        "family_count_linear_refs": [
                            {
                                "active_family_count_bounds": [
                                    {
                                        "family_name": "family_009",
                                        "implied_upper_when_anchor_active": 3,
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    model = cp_model.CpModel()
    idx = model.NewIntVar(0, 1, "idx")
    source0 = model.NewIntVar(0, 10, "source0")
    source1 = model.NewIntVar(0, 10, "source1")
    active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    x = model.NewIntVar(
        0,
        70,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    model.AddElement(idx, [source0, source1], active)
    model.AddElement(idx, [source0, source1], x)

    monkeypatch.setattr(
        audit,
        "_build_exact_overlay",
        lambda *args, **kwargs: (object(), model.Proto()),
    )

    report = audit.build_phase3b_protocol_target_channel_slot_audit(
        project_root,
        campaign_state_path=campaign_path,
        proto_reduction_path=proto_path,
        anchor_differential_path=diff_path,
        target_tokens=("active_x",),
        family_names=("family_009",),
        anchor_indices=(118, 125),
    )

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["evaluated"] is True
    assert report["target_channel_map"]["by_target_token"]["active_x"]["constraint_count"] == 2
    assert report["comparison"]["divergent_targets"] == ["active_x"]
    assert report["comparison"]["family_bound_deltas"][0]["delta_second_minus_first"] == 2.0
    assert report["campaign_state_unchanged"] is True


def test_cli_no_write_with_missing_campaign_does_not_create_output(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "scripts" / "build_phase3b_protocol_target_channel_slot_audit.py"
    out_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(out_dir),
            "--no-write",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "campaign_state_missing" in completed.stdout
    assert not out_dir.exists()


def test_cli_default_write_with_missing_campaign_creates_reports(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "scripts" / "build_phase3b_protocol_target_channel_slot_audit.py"
    out_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path),
            "--output-dir",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (out_dir / "protocol_target_channel_slot_audit.json").exists()
    assert (out_dir / "protocol_target_channel_slot_audit.md").exists()
    assert (out_dir / "protocol_target_channel_slot_audit.txt").exists()
