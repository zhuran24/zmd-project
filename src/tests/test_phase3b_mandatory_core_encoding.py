from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from ortools.sat.python import cp_model

import src.search.phase3b_mandatory_core_encoding as encoding_module
from src.search.phase3b_mandatory_core_encoding import (
    build_phase3b_mandatory_core_encoding_inventory,
    render_phase3b_mandatory_core_encoding_markdown,
    render_phase3b_mandatory_core_encoding_text,
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


def _patch_overlay(monkeypatch) -> None:
    proto_model = cp_model.CpModel()
    x = proto_model.NewIntVar(0, 5, "x__group_a::slot::0")
    y = proto_model.NewIntVar(0, 5, "y__group_a::slot::0")
    mode = proto_model.NewIntVar(0, 1, "mode__group_a::slot::0")
    order_key = proto_model.NewIntVar(0, 99, "order_key__group_a::slot::0")
    signature = proto_model.NewIntVar(0, 2, "signature__group_a::slot::0")
    is_sig = proto_model.NewBoolVar("is_sig__group_a::slot::0__bucket_0")
    region = proto_model.NewBoolVar("region__group_a::slot::0__bucket_0__0")
    group_count = proto_model.NewIntVar(
        0,
        2,
        "group_signature_count__group_a__bucket_0",
    )
    active = proto_model.NewBoolVar("active__residual_optional::power_pole::slot::0")
    proto_model.Add(order_key == x + y + mode)
    proto_model.Add(signature == 0).OnlyEnforceIf(is_sig)
    proto_model.Add(group_count == is_sig)
    proto_model.Add(region == is_sig)

    mode_domain = SimpleNamespace(
        mode_id=0,
        orientation="N",
        port_mode="default",
        x_min=0,
        x_max=5,
        y_min=0,
        y_max=5,
        pose_count=12,
    )
    mandatory_slots = {
        "group_a": [
            SimpleNamespace(
                key="group_a::slot::0",
                candidate_pose_count=12,
                mode_rect_domains={0: mode_domain},
                use_domain_table=False,
                x=x,
                y=y,
                mode=mode,
                order_key=order_key,
                signature=signature,
                active=None,
                family=None,
            )
        ]
    }
    fake_model = SimpleNamespace(
        build_stats={
            "master_slot_counts": {
                "mandatory": 1,
                "required_optionals": {},
                "residual_optionals": {"power_pole": 1},
            },
            "domain_activation": {
                "mandatory_slot_count": 1,
                "residual_optional_slot_count": 1,
            },
            "search_guidance": {
                "decision_strategy_phases": [
                    "mandatory_signature_counts",
                    "mandatory_slots",
                    "ghost",
                ],
                "mandatory_group_order": ["group_a"],
                "mandatory_signature_count_literals": 1,
                "mandatory_mode_literals": 2,
            },
            "coordinate_symmetry": {
                "enabled": True,
                "mandatory_signature_monotonic_constraints": 0,
                "slot_order_key_monotonic_constraints": 0,
            },
        },
        _mandatory_groups=[
            {
                "group_id": "group_a",
                "facility_type": "assembler",
                "operation_type": "craft",
                "count": 1,
                "instance_ids": ["a0"],
            }
        ],
        _ghost_domains=[{} for _ in range(57)],
        _coordinate_delegate=SimpleNamespace(
            mandatory_slots=mandatory_slots,
            required_optional_slots={},
            residual_optional_slots={"power_pole": [SimpleNamespace(active=active)]},
            _mandatory_group_mode_rect_domains={"group_a": {0: mode_domain}},
            _mandatory_group_pose_counts={"group_a": 12},
            _mandatory_group_bucket_pose_counts={"group_a": {"bucket_0": 12}},
            _mandatory_group_bucket_count_upper_bounds={"group_a": {"bucket_0": 1}},
            _mandatory_group_uses_domain_table={"group_a": False},
            _mandatory_group_uses_signature_table={"group_a": False},
            mandatory_signature_count_vars={"group_a": {"bucket_0": group_count}},
            _mandatory_signature_membership={"group_a": {"bucket_0": [is_sig]}},
        ),
    )

    monkeypatch.setattr(
        encoding_module,
        "_build_mandatory_core_overlay",
        lambda *args, **kwargs: (fake_model, proto_model.Proto()),
    )
    monkeypatch.setattr(
        encoding_module,
        "_anchor_domain_report",
        lambda model, idx: {
            "anchor_idx": int(idx),
            "present": True,
            "summary": {"mandatory_surviving_total": 7},
            "tightest_mandatory_group": {
                "group_id": "group_a",
                "surviving_count": 7,
            },
        },
    )


def test_mandatory_core_encoding_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_mandatory_core_encoding_inventory(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_mandatory_core_encoding_summarizes_groups_proto_and_anchor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")
    _patch_overlay(monkeypatch)

    report = build_phase3b_mandatory_core_encoding_inventory(
        project_root,
        campaign_state_path=campaign_path,
        anchor_indices=[56],
    )

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["status"]["outcome"] == "mandatory_core_encoding_inventory_built"
    summary = report["encoding"]["mandatory_core_summary"]
    assert summary["group_count"] == 1
    assert summary["slot_count"] == 1
    assert summary["signature_bucket_total"] == 1
    assert report["encoding"]["residual_disabled"]["active_var_count"] == 1
    base_proto = report["encoding"]["proto"]["base_overlay"]
    diagnostic_proto = report["encoding"]["proto"]["diagnostic_residual_all_inactive"]
    assert base_proto["variable_prefix_counts"]["x"] == 1
    assert base_proto["variable_prefix_counts"]["group_signature_count"] == 1
    assert diagnostic_proto["constraint_count"] == base_proto["constraint_count"] + 1
    assert report["anchors"][0]["tightest_mandatory_group"]["group_id"] == "group_a"

    markdown = render_phase3b_mandatory_core_encoding_markdown(report)
    text = render_phase3b_mandatory_core_encoding_text(report)
    assert "Mandatory-Core Encoding Inventory" in markdown
    assert "mutated_mandatory_core_not_proof_source" in text


def test_mandatory_core_encoding_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_mandatory_core_encoding.py"

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

    assert "phase3b mandatory-core encoding inventory" in no_write.stdout
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

    assert "mandatory_core_encoding_json=" in write.stdout
    payload = json.loads(
        (output_dir / "mandatory_core_encoding_69x19.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == (
        "phase3b_mandatory_core_encoding_inventory_v1"
    )
    assert (output_dir / "mandatory_core_encoding_69x19.md").exists()
    assert (output_dir / "mandatory_core_encoding_69x19.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
