from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from ortools.sat.python import cp_model

import src.search.phase3b_forced_anchor_model_slice as slice_module
from src.search.phase3b_forced_anchor_model_slice import (
    build_phase3b_forced_anchor_model_slice_diagnostic,
    render_phase3b_forced_anchor_model_slice_markdown,
    render_phase3b_forced_anchor_model_slice_text,
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


def _patch_slice(monkeypatch) -> None:
    fake_model = SimpleNamespace(
        u_vars={56: _FakeVar(100)},
        _coordinate_delegate=SimpleNamespace(
            residual_optional_slots={
                "protocol_storage_box": [_FakeSlot(201)],
                "power_pole": [_FakeSlot(301), _FakeSlot(302)],
            },
            power_pole_family_count_vars={"family_009": _FakeVar(901)},
            _power_pole_family_membership={
                "family_009": [_FakeVar(911), _FakeVar(912)],
                "family_010": [_FakeVar(913), _FakeVar(914)],
            },
            _power_pole_family_name_by_int={0: "family_009", 1: "family_010"},
            _power_pole_family_coefficients={
                "family_009": {
                    "manufacturing_3x3": 2,
                    "protocol_storage_box": 1,
                },
                "family_010": {"manufacturing_3x3": 1},
            },
        ),
        _power_pole_family_count_vars={
            "family_009": _FakeVar(901),
            "family_010": _FakeVar(902),
        },
        _exact_powered_template_demands=lambda: {
            "manufacturing_3x3": 132,
            "protocol_storage_box": 1,
        },
    )
    monkeypatch.setattr(
        slice_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )

    def fake_solve(
        base_proto,
        *,
        anchor_idx,
        variant,
        disabled_active_var_indices,
        **kwargs,
    ):
        variant_text = str(variant)
        if variant_text in {"base", "no_protocol_lower_bound_core"}:
            status = "UNKNOWN"
        elif variant_text.startswith("skip_power_coverage"):
            status = "OPTIMAL"
        elif variant_text == "target_power_family_bound_relaxed":
            status = "OPTIMAL"
        elif variant_text == "target_power_family_bound_relaxed_protocol_boxes_inactive":
            status = "INFEASIBLE"
        elif variant_text == "target_power_family_bound_direct_after_force":
            status = "OPTIMAL"
        elif variant_text == "target_power_family_bound_direct_after_force_protocol_boxes_inactive":
            status = "OPTIMAL"
        elif variant_text == "all_conditioned_family_bounds_direct_after_force":
            status = "OPTIMAL"
        elif variant_text == "all_conditioned_family_bounds_direct_after_force_protocol_boxes_inactive":
            status = "INFEASIBLE"
        elif variant_text == "power_coverage_active_requirement_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_coverage_geometry_bounds_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_active_and_geometry_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_coverage_witness_element_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_witness_element_and_linear_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_pole_no_overlap_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_coupling_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_coverage_dynamic_and_family_count_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_membership_count_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_coverage_dynamic_and_family_table_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_linear_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_coverage_dynamic_and_family_sentinel_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_membership_linear_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_ordering_linear_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_other_linear_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_lookup_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_distance_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_lookup_distance_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_coverage_dynamic_and_family_assignment_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_family_assignment_and_gvi_relaxed":
            status = "OPTIMAL"
        elif variant_text == "family_active_domain_channeling_added":
            status = "UNKNOWN"
        elif variant_text == "family_membership_active_channeling_added":
            status = "UNKNOWN"
        elif variant_text == "family_active_and_membership_channeling_added":
            status = "OPTIMAL"
        elif variant_text == "family_shell_pair_tables_added":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_shell_pair_tables_added":
            status = "OPTIMAL"
        elif variant_text == "family_lookup_rebuilt_channeling":
            status = "UNKNOWN"
        elif variant_text == "power_coverage_dynamic_and_family_lookup_rebuilt_channeling":
            status = "OPTIMAL"
        elif (
            variant_text
            == "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only"
        ):
            status = "UNKNOWN"
        elif (
            variant_text
            == "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only"
        ):
            status = "OPTIMAL"
        elif (
            variant_text
            == "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only"
        ):
            status = "UNKNOWN"
        elif (
            variant_text
            == "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair"
        ):
            status = "UNKNOWN"
        elif (
            variant_text
            == "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering"
        ):
            status = "OPTIMAL"
        elif (
            variant_text
            == "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering"
        ):
            status = "UNKNOWN"
        elif variant_text == "power_capacity_gvi_protocol_storage_box_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_capacity_gvi_mandatory_templates_relaxed":
            status = "INFEASIBLE"
        elif variant_text == "power_capacity_gvi_all_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_family_count_constraints_relaxed":
            status = "UNKNOWN"
        elif variant_text == "power_family_membership_and_count_constraints_relaxed":
            status = "OPTIMAL"
        elif variant_text == "power_family_assignment_layer_relaxed":
            status = "OPTIMAL"
        else:
            status = "INFEASIBLE"
        return {
            "anchor_idx": int(anchor_idx),
            "u_var_index": int(kwargs.get("u_var_index", 0)),
            "variant": variant_text,
            "evaluated": True,
            "status": status,
            "wall_time": 0.1,
            "user_time": 0.1,
            "branches": 0 if status == "UNKNOWN" else 7,
            "conflicts": 0,
            "disabled_active_var_count": len(disabled_active_var_indices),
            "relaxed_power_family": kwargs.get("relaxed_power_family_name"),
            "relaxed_power_family_count_value": 7
            if kwargs.get("relaxed_power_family_count_var_index") is not None
            else None,
            "relaxed_conditioned_power_family_bound_constraints_removed": 1
            if kwargs.get("relaxed_power_family_count_var_index") is not None
            else 0,
            "replacement_bound_mode": kwargs.get("replacement_bound_mode"),
            "replacement_conditioned_power_family_bound": 5
            if kwargs.get("replacement_bound_mode") == "direct_after_force"
            else None,
            "direct_power_family_bound_replacement_count": len(
                kwargs.get("direct_power_family_count_var_indices") or {}
            ),
            "power_coverage_relaxation_mode": kwargs.get(
                "power_coverage_relaxation_mode"
            ),
            "relaxed_power_coverage_linear_constraint_count": 3
            if kwargs.get("power_coverage_relaxation_mode")
            else 0,
            "power_coverage_dynamic_relaxation_mode": kwargs.get(
                "power_coverage_dynamic_relaxation_mode"
            ),
            "relaxed_power_coverage_dynamic_constraint_count": 9
            if kwargs.get("power_coverage_dynamic_relaxation_mode")
            else 0,
            "power_capacity_gvi_relax_templates": list(
                kwargs.get("power_capacity_gvi_relax_templates") or []
            ),
            "relaxed_power_capacity_gvi_constraint_count": len(
                kwargs.get("power_capacity_gvi_relax_templates") or []
            ),
            "power_family_layer_relaxation_mode": kwargs.get(
                "power_family_layer_relaxation_mode"
            ),
            "relaxed_power_family_layer_constraint_count": 5
            if kwargs.get("power_family_layer_relaxation_mode")
            else 0,
            "power_family_channeling_mode": kwargs.get("power_family_channeling_mode"),
            "added_power_family_channeling_constraint_count": 6
            if kwargs.get("power_family_channeling_mode")
            else 0,
            "power_family_shell_pair_table_mode": kwargs.get(
                "power_family_shell_pair_table_mode"
            ),
            "added_power_family_shell_pair_table_constraint_count": 8
            if kwargs.get("power_family_shell_pair_table_mode")
            else 0,
            "power_family_lookup_rebuild_mode": kwargs.get(
                "power_family_lookup_rebuild_mode"
            ),
            "added_power_family_lookup_rebuild_constraint_count": 11
            if kwargs.get("power_family_lookup_rebuild_mode")
            else 0,
        }

    monkeypatch.setattr(slice_module, "_solve_slice_clone", fake_solve)


def _patch_custom_core(monkeypatch) -> None:
    fake_model = SimpleNamespace(
        u_vars={56: _FakeVar(100)},
        _coordinate_delegate=SimpleNamespace(
            residual_optional_slots={
                "protocol_storage_box": [_FakeSlot(401)],
                "power_pole": [_FakeSlot(501), _FakeSlot(502)],
            }
        ),
    )

    def fake_custom_overlay(*args, **kwargs):
        return fake_model, object()

    monkeypatch.setattr(
        slice_module,
        "_build_custom_core_overlay",
        fake_custom_overlay,
    )


def test_model_slice_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_forced_anchor_model_slice_diagnostic(tmp_path / "project")

    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_model_slice_counts_variants_and_marks_diagnostic_semantics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    before = campaign_path.read_text(encoding="utf-8")
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=["base", "protocol_boxes_inactive", "power_poles_inactive"],
    )

    assert campaign_path.read_text(encoding="utf-8") == before
    assert report["campaign_state_unchanged"] is True
    assert report["metadata"]["diagnostic_semantics"] == (
        "mutated_model_slice_not_proof_source"
    )
    assert report["slice_matrix"]["status_counts"] == {
        "UNKNOWN": 1,
        "INFEASIBLE": 2,
    }
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:protocol_boxes_drive_unknown",
        "anchor_56:power_poles_drive_unknown",
    ]
    assert "protocol_boxes_drive_unknown" in report["status"]["recommendation"]
    assert report["slice_matrix"]["entries"][1]["disabled_active_var_count"] == 1
    assert report["slice_matrix"]["entries"][2]["disabled_active_var_count"] == 2

    markdown = render_phase3b_forced_anchor_model_slice_markdown(report)
    text = render_phase3b_forced_anchor_model_slice_text(report)
    assert "Model-Slice Diagnostic" in markdown
    assert "Diagnostic findings:" in markdown
    assert "mutated_model_slice_not_proof_source" in text
    assert "diagnostic_findings=" in text


def test_model_slice_routes_custom_core_variants(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)
    _patch_custom_core(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "no_protocol_lower_bound_core",
            "skip_power_coverage_no_protocol_lower_bound_core",
            "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive",
        ],
    )

    assert report["status"]["outcome"] == "slice_unknown_remaining"
    assert [entry["variant"] for entry in report["slice_matrix"]["entries"]] == [
        "base",
        "no_protocol_lower_bound_core",
        "skip_power_coverage_no_protocol_lower_bound_core",
        "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive",
    ]
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:protocol_lower_bound_not_primary",
        "anchor_56:skip_power_coverage_unlocks_feasible_core",
    ]
    assert report["slice_matrix"]["entries"][-1]["disabled_active_var_count"] == 3


def test_model_slice_routes_target_power_family_bound_relaxation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "target_power_family_bound_relaxed",
            "target_power_family_bound_relaxed_protocol_boxes_inactive",
        ],
        target_power_family="family_009",
    )

    assert report["profile"]["target_power_family"] == "family_009"
    assert [entry["variant"] for entry in report["slice_matrix"]["entries"]] == [
        "base",
        "target_power_family_bound_relaxed",
        "target_power_family_bound_relaxed_protocol_boxes_inactive",
    ]
    relaxed = report["slice_matrix"]["entries"][1]
    combined = report["slice_matrix"]["entries"][2]
    assert relaxed["relaxed_power_family"] == "family_009"
    assert relaxed["relaxed_power_family_count_value"] == 7
    assert relaxed["relaxed_conditioned_power_family_bound_constraints_removed"] == 1
    assert combined["disabled_active_var_count"] == 1
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:target_power_family_bound_relaxation_unlocks_feasible_core",
        "anchor_56:target_power_family_relaxed_protocol_boxes_still_infeasible",
    ]


def test_conditioned_power_family_bound_removal_matches_anchor_and_count_var() -> None:
    model = cp_model.CpModel()
    count = model.NewIntVar(0, 10, "power_pole_family_count__family_009")
    other_count = model.NewIntVar(0, 10, "power_pole_family_count__family_010")
    ghost = model.NewBoolVar("ghost__2_3_67_13")
    model.Add(count <= 5 + 10 * (1 - ghost))
    model.Add(other_count <= 4 + 10 * (1 - ghost))
    model.Add(count >= 0)
    proto = model.Proto()
    before = len(proto.constraints)

    removed = slice_module._remove_conditioned_power_family_bound_constraints(
        proto,
        count_var_index=count.Index(),
        u_var_index=ghost.Index(),
    )

    assert removed == 1
    assert len(proto.constraints) == before


def test_conditioned_power_family_bound_removal_can_run_sequentially() -> None:
    model = cp_model.CpModel()
    count_a = model.NewIntVar(0, 10, "power_pole_family_count__family_009")
    count_b = model.NewIntVar(0, 10, "power_pole_family_count__family_010")
    ghost = model.NewBoolVar("ghost__2_3_67_13")
    model.Add(count_a <= 5 + 10 * (1 - ghost))
    model.Add(count_b <= 4 + 10 * (1 - ghost))
    model.Add(count_a + count_b >= 0)
    proto = model.Proto()
    before = len(proto.constraints)

    removed_a = slice_module._remove_conditioned_power_family_bound_constraints(
        proto,
        count_var_index=count_a.Index(),
        u_var_index=ghost.Index(),
    )
    removed_b = slice_module._remove_conditioned_power_family_bound_constraints(
        proto,
        count_var_index=count_b.Index(),
        u_var_index=ghost.Index(),
    )

    assert removed_a == 1
    assert removed_b == 1
    assert len(proto.constraints) == before


def test_model_slice_routes_target_power_family_direct_bound_replacement(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "target_power_family_bound_direct_after_force",
            "target_power_family_bound_direct_after_force_protocol_boxes_inactive",
        ],
        target_power_family="family_009",
    )

    direct = report["slice_matrix"]["entries"][1]
    assert direct["u_var_index"] == 100
    assert direct["replacement_bound_mode"] == "direct_after_force"
    assert direct["replacement_conditioned_power_family_bound"] == 5
    assert direct["relaxed_conditioned_power_family_bound_constraints_removed"] == 1
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:target_power_family_direct_bound_unlocks_feasible_core",
        "anchor_56:target_power_family_direct_bound_protocol_boxes_unlock_feasible_core",
    ]


def test_model_slice_routes_all_conditioned_family_direct_bound_replacement(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "all_conditioned_family_bounds_direct_after_force",
            "all_conditioned_family_bounds_direct_after_force_protocol_boxes_inactive",
        ],
        target_power_family="family_009",
    )

    direct = report["slice_matrix"]["entries"][1]
    assert direct["direct_power_family_bound_replacement_count"] == 2
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:all_conditioned_family_direct_bounds_unlock_feasible_core",
        "anchor_56:all_conditioned_family_direct_bounds_protocol_boxes_still_infeasible",
    ]


def test_model_slice_routes_power_coverage_linear_relaxation_variants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "power_coverage_active_requirement_relaxed",
            "power_coverage_geometry_bounds_relaxed",
            "power_coverage_active_and_geometry_relaxed",
        ],
    )

    entries = report["slice_matrix"]["entries"]
    assert [entry["variant"] for entry in entries] == [
        "base",
        "power_coverage_active_requirement_relaxed",
        "power_coverage_geometry_bounds_relaxed",
        "power_coverage_active_and_geometry_relaxed",
    ]
    assert entries[1]["power_coverage_relaxation_mode"] == (
        "power_coverage_active_requirement_relaxed"
    )
    assert entries[1]["relaxed_power_coverage_linear_constraint_count"] == 3
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:power_coverage_active_requirement_drives_unknown",
        "anchor_56:power_coverage_geometry_bounds_relaxation_still_unknown",
        "anchor_56:power_coverage_active_and_geometry_relaxation_unlocks_core",
    ]


def test_power_coverage_linear_constraint_removal_matches_prefixes() -> None:
    model = cp_model.CpModel()
    active = model.NewBoolVar("cover_choice_active__slot_a")
    x_var = model.NewIntVar(0, 10, "cover_choice_x__slot_a")
    y_var = model.NewIntVar(0, 10, "cover_choice_y__slot_a")
    other = model.NewBoolVar("other_var")
    model.Add(active == 1)
    model.Add(x_var <= 5)
    model.Add(y_var <= 5)
    model.Add(other == 1)
    proto = model.Proto()
    before = len(proto.constraints)

    payload = slice_module._remove_power_coverage_linear_constraints_payload(
        proto,
        mode="power_coverage_active_and_geometry_relaxed",
    )

    assert payload["removed_constraint_count"] == 3
    assert len(proto.constraints) == before
    assert payload["removed_by_prefix"] == {
        "cover_choice_active__": 1,
        "cover_choice_x__": 1,
        "cover_choice_y__": 1,
    }


def test_model_slice_routes_power_coverage_dynamic_relaxation_variants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "power_coverage_witness_element_relaxed",
            "power_coverage_witness_element_and_linear_relaxed",
            "power_pole_no_overlap_relaxed",
            "power_coverage_dynamic_coupling_relaxed",
            "power_coverage_dynamic_and_family_count_relaxed",
            "power_coverage_dynamic_and_family_membership_count_relaxed",
            "power_coverage_dynamic_and_family_table_relaxed",
            "power_coverage_dynamic_and_family_linear_relaxed",
            "power_coverage_dynamic_and_family_sentinel_relaxed",
            "power_coverage_dynamic_and_family_membership_linear_relaxed",
            "power_coverage_dynamic_and_family_ordering_linear_relaxed",
            "power_coverage_dynamic_and_family_other_linear_relaxed",
            "power_coverage_dynamic_and_family_lookup_relaxed",
            "power_coverage_dynamic_and_family_distance_relaxed",
            "power_coverage_dynamic_and_family_lookup_distance_relaxed",
            "power_coverage_dynamic_and_family_assignment_relaxed",
            "power_coverage_dynamic_family_assignment_and_gvi_relaxed",
        ],
    )

    entries = report["slice_matrix"]["entries"]
    assert entries[1]["power_coverage_dynamic_relaxation_mode"] == (
        "power_coverage_witness_element_relaxed"
    )
    assert entries[1]["relaxed_power_coverage_dynamic_constraint_count"] == 9
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:power_coverage_witness_element_relaxation_still_unknown",
        "anchor_56:power_coverage_witness_element_and_linear_relaxation_still_unknown",
        "anchor_56:power_pole_no_overlap_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_coupling_relaxation_unlocks_core",
        "anchor_56:power_coverage_dynamic_and_family_count_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_membership_count_relaxation_unlocks_core",
        "anchor_56:power_coverage_dynamic_and_family_table_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_linear_relaxation_unlocks_core",
        "anchor_56:power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_other_linear_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_lookup_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_distance_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_lookup_distance_relaxation_unlocks_core",
        "anchor_56:power_coverage_dynamic_and_family_assignment_relaxation_still_unknown",
        "anchor_56:power_coverage_dynamic_family_assignment_and_gvi_relaxation_unlocks_core",
    ]


def test_power_coverage_element_constraint_removal_matches_cover_choice_vars() -> None:
    model = cp_model.CpModel()
    idx = model.NewIntVar(0, 1, "cover_choice_idx__slot_a")
    target = model.NewBoolVar("cover_choice_active__slot_a")
    pole_a = model.NewBoolVar("power_pole_active_a")
    pole_b = model.NewBoolVar("power_pole_active_b")
    other_idx = model.NewIntVar(0, 1, "other_idx")
    other_target = model.NewBoolVar("other_target")
    model.AddElement(idx, [pole_a, pole_b], target)
    model.AddElement(other_idx, [pole_a, pole_b], other_target)
    proto = model.Proto()
    before = len(proto.constraints)

    payload = slice_module._remove_power_coverage_element_constraints_payload(proto)

    rebuilt = slice_module.cp_model_from_proto(proto)
    validate = getattr(rebuilt, "Validate", None) or getattr(rebuilt, "validate", None)
    assert payload["removed_constraint_count"] == 1
    assert payload["removed_by_prefix"]["cover_choice_idx__"] == 1
    assert payload["removed_by_prefix"]["cover_choice_active__"] == 1
    assert len(proto.constraints) == before
    assert callable(validate)
    assert validate() == ""


def test_power_pole_no_overlap_relaxation_removes_pairs_without_shifting() -> None:
    model = cp_model.CpModel()
    core_x = model.NewIntVar(0, 5, "core_x")
    core_y = model.NewIntVar(0, 5, "core_y")
    pole_x = model.NewIntVar(0, 5, "pole_x")
    pole_y = model.NewIntVar(0, 5, "pole_y")
    core_x_iv = model.NewFixedSizeIntervalVar(
        core_x,
        1,
        "x_iv__group::manufacturing_3x3::slot::0",
    )
    core_y_iv = model.NewFixedSizeIntervalVar(
        core_y,
        1,
        "y_iv__group::manufacturing_3x3::slot::0",
    )
    pole_x_iv = model.NewFixedSizeIntervalVar(
        pole_x,
        1,
        "x_iv__residual_optional::power_pole::slot::0",
    )
    pole_y_iv = model.NewFixedSizeIntervalVar(
        pole_y,
        1,
        "y_iv__residual_optional::power_pole::slot::0",
    )
    model.AddNoOverlap2D([core_x_iv, pole_x_iv], [core_y_iv, pole_y_iv])
    proto = model.Proto()
    no_overlap_idx = next(
        idx
        for idx, constraint in enumerate(proto.constraints)
        if constraint.has_no_overlap_2d()
    )
    before = len(proto.constraints)

    payload = slice_module._remove_power_pole_intervals_from_no_overlap_2d_payload(
        proto,
    )

    rebuilt = slice_module.cp_model_from_proto(proto)
    validate = getattr(rebuilt, "Validate", None) or getattr(rebuilt, "validate", None)
    no_overlap = proto.constraints[no_overlap_idx].no_overlap_2d
    assert payload["removed_interval_pair_count"] == 1
    assert payload["touched_constraint_count"] == 1
    assert len(no_overlap.x_intervals) == 1
    assert len(no_overlap.y_intervals) == 1
    assert len(proto.constraints) == before
    assert callable(validate)
    assert validate() == ""


def test_model_slice_routes_power_family_channeling_addition_variants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "family_active_domain_channeling_added",
            "family_membership_active_channeling_added",
            "family_active_and_membership_channeling_added",
            "family_shell_pair_tables_added",
            "power_coverage_dynamic_and_family_shell_pair_tables_added",
            "family_lookup_rebuilt_channeling",
            "power_coverage_dynamic_and_family_lookup_rebuilt_channeling",
        ],
    )

    entries = report["slice_matrix"]["entries"]
    assert entries[1]["power_family_channeling_mode"] == (
        "family_active_domain_channeling_added"
    )
    assert entries[1]["added_power_family_channeling_constraint_count"] == 6
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:family_active_domain_channeling_still_unknown",
        "anchor_56:family_membership_active_channeling_still_unknown",
        "anchor_56:family_active_and_membership_channeling_unlocks_core",
        "anchor_56:family_shell_pair_tables_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_shell_pair_tables_unlocks_core",
        "anchor_56:family_lookup_rebuilt_channeling_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_unlocks_core",
    ]


def test_model_slice_routes_power_family_lookup_rebuild_component_variants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only",
            "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only",
            "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only",
            "power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair",
            "power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering",
            "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering",
        ],
    )

    entries = report["slice_matrix"]["entries"]
    assert entries[1]["power_family_lookup_rebuild_mode"] == (
        "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only"
    )
    assert entries[1]["power_coverage_dynamic_relaxation_mode"] == (
        "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only"
    )
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_unlocks_core",
        "anchor_56:power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair_still_unknown",
        "anchor_56:power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering_unlocks_core",
        "anchor_56:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering_still_unknown",
    ]


def test_power_family_shell_pair_table_constraints_add_family_implications() -> None:
    model = cp_model.CpModel()
    d_lo = model.NewIntVar(0, 2, "d_lo__slot")
    d_hi = model.NewIntVar(0, 2, "d_hi__slot")
    lit_a = model.NewBoolVar("is_family__slot__family_000")
    lit_b = model.NewBoolVar("is_family__slot__family_001")

    payload = slice_module._add_power_family_shell_pair_table_constraints(
        model,
        mode="family_shell_pair_tables_added",
        payload={
            "rows_by_family_id": {
                "0": [[0, 0], [0, 1]],
                "1": [[1, 1]],
            },
            "slots": [
                {
                    "d_lo_var_index": d_lo.Index(),
                    "d_hi_var_index": d_hi.Index(),
                    "family_lit_indices_by_family_id": {
                        "0": lit_a.Index(),
                        "1": lit_b.Index(),
                    },
                }
            ],
        },
    )

    validate = getattr(model, "Validate", None) or getattr(model, "validate", None)
    assert payload["added_constraint_count"] == 2
    assert payload["enforced_row_total"] == 3
    assert callable(validate)
    assert validate() == ""


def test_power_family_lookup_rebuild_constraints_add_alternative_encoding() -> None:
    model = cp_model.CpModel()
    active_0 = model.NewBoolVar("active__slot_0")
    family_0 = model.NewIntVar(0, 2, "family__slot_0")
    d_lo_0 = model.NewIntVar(0, 2, "d_lo__slot_0")
    d_hi_0 = model.NewIntVar(0, 2, "d_hi__slot_0")
    lit_00 = model.NewBoolVar("is_family__slot_0__family_000")
    lit_01 = model.NewBoolVar("is_family__slot_0__family_001")
    active_1 = model.NewBoolVar("active__slot_1")
    family_1 = model.NewIntVar(0, 2, "family__slot_1")
    d_lo_1 = model.NewIntVar(0, 2, "d_lo__slot_1")
    d_hi_1 = model.NewIntVar(0, 2, "d_hi__slot_1")
    lit_10 = model.NewBoolVar("is_family__slot_1__family_000")
    lit_11 = model.NewBoolVar("is_family__slot_1__family_001")

    payload = slice_module._add_power_family_lookup_rebuild_constraints(
        model,
        mode="family_lookup_rebuilt_channeling",
        payload={
            "rows_by_family_id": {
                "0": [[0, 0], [0, 1]],
                "1": [[1, 1]],
            },
            "slots": [
                {
                    "active_var_index": active_0.Index(),
                    "family_var_index": family_0.Index(),
                    "d_lo_var_index": d_lo_0.Index(),
                    "d_hi_var_index": d_hi_0.Index(),
                    "family_lit_indices_by_family_id": {
                        "0": lit_00.Index(),
                        "1": lit_01.Index(),
                    },
                },
                {
                    "active_var_index": active_1.Index(),
                    "family_var_index": family_1.Index(),
                    "d_lo_var_index": d_lo_1.Index(),
                    "d_hi_var_index": d_hi_1.Index(),
                    "family_lit_indices_by_family_id": {
                        "0": lit_10.Index(),
                        "1": lit_11.Index(),
                    },
                },
            ],
        },
    )

    validate = getattr(model, "Validate", None) or getattr(model, "validate", None)
    assert payload["active_domain_constraint_count"] == 4
    assert payload["membership_reification_constraint_count"] == 8
    assert payload["membership_sum_constraint_count"] == 2
    assert payload["shell_pair_table_constraint_count"] == 4
    assert payload["family_ordering_constraint_count"] == 1
    assert payload["added_constraint_count"] == 19
    assert callable(validate)
    assert validate() == ""


def test_power_family_channeling_constraints_add_redundant_links() -> None:
    model = cp_model.CpModel()
    active = model.NewBoolVar("active__slot")
    family = model.NewIntVar(0, 2, "family__slot")
    lit_a = model.NewBoolVar("is_family__slot__family_000")
    lit_b = model.NewBoolVar("is_family__slot__family_001")

    payload = slice_module._add_power_family_channeling_constraints(
        model,
        mode="family_active_and_membership_channeling_added",
        slots=[
            {
                "active_var_index": active.Index(),
                "family_var_index": family.Index(),
                "family_lit_indices": [lit_a.Index(), lit_b.Index()],
                "sentinel_family_id": 2,
            }
        ],
    )

    validate = getattr(model, "Validate", None) or getattr(model, "validate", None)
    assert payload["added_constraint_count"] == 3
    assert payload["active_domain_constraint_count"] == 2
    assert payload["membership_sum_constraint_count"] == 1
    assert callable(validate)
    assert validate() == ""


def test_model_slice_routes_power_capacity_gvi_relaxation_variants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "power_capacity_gvi_protocol_storage_box_relaxed",
            "power_capacity_gvi_mandatory_templates_relaxed",
            "power_capacity_gvi_all_relaxed",
        ],
    )

    entries = report["slice_matrix"]["entries"]
    assert entries[1]["power_capacity_gvi_relax_templates"] == [
        "protocol_storage_box"
    ]
    assert entries[2]["power_capacity_gvi_relax_templates"] == [
        "manufacturing_3x3"
    ]
    assert entries[3]["power_capacity_gvi_relax_templates"] == [
        "manufacturing_3x3",
        "protocol_storage_box",
    ]
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:protocol_storage_box_power_capacity_gvi_relaxation_still_unknown",
        "anchor_56:all_power_capacity_gvi_relaxation_unlocks_core",
    ]


def test_power_capacity_gvi_constraint_removal_matches_template_coefficients() -> None:
    model = cp_model.CpModel()
    family_a = model.NewIntVar(0, 10, "power_pole_family_count__family_001")
    family_b = model.NewIntVar(0, 10, "power_pole_family_count__family_002")
    other = model.NewIntVar(0, 10, "other_count")
    model.Add(2 * family_a + family_b >= 5)
    model.Add(family_a + 3 * family_b >= 4)
    model.Add(other >= 1)
    proto = model.Proto()
    before = len(proto.constraints)

    payload = slice_module._remove_power_capacity_gvi_constraints_payload(
        proto,
        templates=["protocol_storage_box"],
        template_coefficients={
            "protocol_storage_box": {
                family_a.Index(): 2,
                family_b.Index(): 1,
            }
        },
        template_demands={"protocol_storage_box": 5},
    )

    assert payload["removed_constraint_count"] == 1
    assert payload["removed_templates"] == ["protocol_storage_box"]
    assert len(proto.constraints) == before


def test_power_capacity_gvi_constraint_removal_uses_demand_to_disambiguate() -> None:
    model = cp_model.CpModel()
    family_a = model.NewIntVar(0, 10, "power_pole_family_count__family_001")
    family_b = model.NewIntVar(0, 10, "power_pole_family_count__family_002")
    model.Add(2 * family_a + family_b >= 5)
    model.Add(2 * family_a + family_b >= 7)
    proto = model.Proto()

    payload = slice_module._remove_power_capacity_gvi_constraints_payload(
        proto,
        templates=["protocol_storage_box"],
        template_coefficients={
            "protocol_storage_box": {
                family_a.Index(): 2,
                family_b.Index(): 1,
            }
        },
        template_demands={"protocol_storage_box": 7},
    )

    assert payload["removed_constraint_count"] == 1
    assert payload["removed_templates"] == ["protocol_storage_box"]
    assert len(proto.constraints) == 2


def test_model_slice_routes_power_family_layer_relaxation_variants(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    _patch_slice(monkeypatch)

    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        anchor_indices=[56],
        variants=[
            "base",
            "power_family_count_constraints_relaxed",
            "power_family_membership_and_count_constraints_relaxed",
            "power_family_assignment_layer_relaxed",
        ],
    )

    entries = report["slice_matrix"]["entries"]
    assert entries[1]["power_family_layer_relaxation_mode"] == (
        "power_family_count_constraints_relaxed"
    )
    assert entries[1]["relaxed_power_family_layer_constraint_count"] == 5
    assert report["slice_matrix"]["diagnostic_findings"] == [
        "anchor_56:power_family_count_constraints_relaxation_still_unknown",
        "anchor_56:power_family_membership_and_count_constraints_drive_unknown",
        "anchor_56:power_family_assignment_layer_drives_unknown",
    ]


def test_power_family_layer_constraint_removal_matches_prefixes() -> None:
    model = cp_model.CpModel()
    count = model.NewIntVar(0, 10, "power_pole_family_count__family_001")
    lit = model.NewBoolVar("is_family__slot_a__family_001")
    other = model.NewIntVar(0, 10, "other")
    model.Add(count == lit)
    model.Add(lit == 1)
    family = model.NewIntVar(0, 2, "family__slot_a")
    model.AddAllowedAssignments([family], [(0,), (1,)])
    model.Add(other >= 1)
    proto = model.Proto()
    before = len(proto.constraints)

    payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_membership_and_count_constraints_relaxed",
    )

    assert payload["removed_constraint_count"] == 2
    assert payload["removed_by_prefix"] == {
        "is_family__": 2,
        "power_pole_family_count__": 1,
    }
    assert len(proto.constraints) == before

    assignment_payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_assignment_layer_relaxed",
    )

    assert assignment_payload["removed_constraint_count"] == 1
    assert assignment_payload["removed_by_prefix"]["family__"] == 1


def test_power_family_lookup_relaxation_can_target_table_or_linear_only() -> None:
    def _proto():
        model = cp_model.CpModel()
        family = model.NewIntVar(0, 2, "family__slot_a")
        active = model.NewBoolVar("active__slot_a")
        lit = model.NewBoolVar("is_family__slot_a__family_000")
        other_family = model.NewIntVar(0, 2, "family__slot_b")
        model.AddAllowedAssignments([family], [(0,), (1,)]).OnlyEnforceIf(active)
        model.Add(family == 2).OnlyEnforceIf(active.Not())
        model.Add(family == 0).OnlyEnforceIf(lit)
        model.Add(family != 0).OnlyEnforceIf(lit.Not())
        model.Add(family <= other_family)
        return model.Proto()

    proto = _proto()
    before = len(proto.constraints)

    table_payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_lookup_table_constraints_relaxed",
    )

    assert table_payload["removed_constraint_count"] == 1
    assert len(proto.constraints) == before

    proto = _proto()
    linear_payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_lookup_linear_constraints_relaxed",
    )

    assert linear_payload["removed_constraint_count"] == 4
    assert len(proto.constraints) == before

    proto = _proto()
    sentinel_payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_lookup_sentinel_constraints_relaxed",
    )

    assert sentinel_payload["removed_constraint_count"] == 1

    proto = _proto()
    membership_payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_lookup_membership_linear_constraints_relaxed",
    )

    assert membership_payload["removed_constraint_count"] == 2

    proto = _proto()
    ordering_payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_lookup_ordering_linear_constraints_relaxed",
    )

    assert ordering_payload["removed_constraint_count"] == 1


def test_constraint_relaxation_preserves_interval_indices() -> None:
    model = cp_model.CpModel()
    x = model.NewIntVar(0, 5, "x")
    y = model.NewIntVar(0, 5, "y")
    x_interval = model.NewFixedSizeIntervalVar(x, 1, "x_interval")
    y_interval = model.NewFixedSizeIntervalVar(y, 1, "y_interval")
    count = model.NewIntVar(0, 10, "power_pole_family_count__family_001")
    model.Add(count >= 1)
    model.AddNoOverlap2D([x_interval], [y_interval])
    proto = model.Proto()
    before = len(proto.constraints)

    payload = slice_module._remove_power_family_layer_constraints_payload(
        proto,
        mode="power_family_count_constraints_relaxed",
    )

    rebuilt = slice_module.cp_model_from_proto(proto)
    validate = getattr(rebuilt, "Validate", None) or getattr(rebuilt, "validate", None)
    assert payload["removed_constraint_count"] == 1
    assert len(proto.constraints) == before
    assert callable(validate)
    assert validate() == ""


def test_response_stats_payload_parses_numeric_fields() -> None:
    payload = slice_module._response_stats_payload(
        "CpSolverResponse summary:\n"
        "status: OPTIMAL\n"
        "conflicts: 0\n"
        "branches: 12\n"
        "walltime: 0.25\n"
        "deterministic_time: 1.5e-02\n"
    )

    assert payload["status"] == "OPTIMAL"
    assert payload["conflicts"] == 0
    assert payload["branches"] == 12
    assert payload["walltime"] == 0.25
    assert payload["deterministic_time"] == 0.015


def test_model_slice_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "profile_phase3b_forced_anchor_model_slice.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--solver-profile-json",
            json.dumps(
                {
                    "profile_id": "cli_probe",
                    "search_branching": "fixed",
                    "cp_model_presolve": False,
                }
            ),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b forced-anchor model-slice diagnostic" in no_write.stdout
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

    assert "forced_anchor_model_slice_json=" in write.stdout
    payload = json.loads(
        (output_dir / "forced_anchor_model_slice_69x19.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == (
        "phase3b_forced_anchor_model_slice_diagnostic_v1"
    )
    assert (output_dir / "forced_anchor_model_slice_69x19.md").exists()
    assert (output_dir / "forced_anchor_model_slice_69x19.txt").exists()


def test_solver_profile_preserves_safe_diagnostic_logging_parameters() -> None:
    profile = slice_module._normalize_solver_parameter_profile(
        {
            "profile_id": "log_probe",
            "search_branching": "fixed",
            "log_search_progress": True,
            "log_to_stdout": True,
            "max_presolve_iterations": 3,
            "boolean_encoding_level": 0,
            "max_domain_size_for_linear2_expansion": 0,
            "max_domain_size_when_encoding_eq_neq_constraints": 0,
            "cp_model_use_sat_presolve": False,
            "find_clauses_that_are_exactly_one": False,
            "presolve_use_bva": False,
        },
        default_worker_count=1,
    )

    assert profile["log_search_progress"] is True
    assert profile["log_to_stdout"] is True
    assert profile["max_presolve_iterations"] == 3
    assert profile["boolean_encoding_level"] == 0
    assert profile["max_domain_size_for_linear2_expansion"] == 0
    assert profile["max_domain_size_when_encoding_eq_neq_constraints"] == 0
    assert profile["cp_model_use_sat_presolve"] is False
    assert profile["find_clauses_that_are_exactly_one"] is False
    assert profile["presolve_use_bva"] is False


def test_solver_profile_applies_zero_hint_conflict_limit() -> None:
    solver = cp_model.CpSolver()

    applied = slice_module._apply_solver_parameter_profile(
        solver,
        time_limit_seconds=1.0,
        default_worker_count=1,
        profile={
            "profile_id": "zero_hint_probe",
            "search_branching": "fixed",
            "hint_conflict_limit": 0,
        },
    )

    assert applied["hint_conflict_limit"] == 0
    assert int(solver.parameters.hint_conflict_limit) == 0


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
