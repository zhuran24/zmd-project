from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import src.search.phase3b_forced_anchor_proto_reduction as reduction_module
from src.search.phase3b_forced_anchor_proto_reduction import (
    build_phase3b_forced_anchor_proto_reduction,
    render_phase3b_forced_anchor_proto_reduction_markdown,
    render_phase3b_forced_anchor_proto_reduction_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "67x13": {
                "ghost_rect": {"w": 67, "h": 13, "area": 871},
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 1,
                        "failed_anchor_samples": [{"anchor_idx": 119}],
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


def test_proto_reduction_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_forced_anchor_proto_reduction(tmp_path / "project")

    assert report["metadata"]["source"] == "phase3b_forced_anchor_proto_reduction_v1"
    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_proto_reduction_aggregates_unlocking_variant(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    fake_model = SimpleNamespace(u_vars={119: _FakeVar(1000)})
    monkeypatch.setattr(
        reduction_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )
    monkeypatch.setattr(reduction_module, "_clone_model_proto", lambda proto: proto)
    monkeypatch.setattr(
        reduction_module,
        "_proto_profile",
        lambda proto: {"variable_count": 10, "constraint_count": 20},
    )

    def fake_solve(base_proto: object, **kwargs: Any) -> dict[str, Any]:
        status = "OPTIMAL" if kwargs["variant"] == "remove_family_lookup_all" else "UNKNOWN"
        return {
            "anchor_idx": kwargs["anchor_idx"],
            "variant": kwargs["variant"],
            "evaluated": True,
            "status": status,
            "removed_constraint_count": 7 if status == "OPTIMAL" else 0,
            "wall_time": 0.1,
            "branches": 3 if status == "OPTIMAL" else 0,
            "conflicts": 0,
        }

    monkeypatch.setattr(reduction_module, "_solve_proto_reduction_variant", fake_solve)

    report = build_phase3b_forced_anchor_proto_reduction(
        project_root,
        candidate="67x13",
        anchor_indices=[119],
        variants=["base", "remove_family_lookup_all"],
    )

    assert report["status"]["outcome"] == "proto_reduction_terminal_found"
    assert report["reduction"]["status_counts"] == {"UNKNOWN": 1, "OPTIMAL": 1}
    assert report["reduction"]["best_terminal_entry"]["variant"] == "remove_family_lookup_all"
    assert report["reduction"]["unlocking_variants"] == [
        {
            "variant": "remove_family_lookup_all",
            "status": "OPTIMAL",
            "removed_constraint_count": 7,
            "wall_time": 0.1,
            "branches": 3,
            "conflicts": 0,
        }
    ]
    assert report["campaign_state_unchanged"] is True

    markdown = render_phase3b_forced_anchor_proto_reduction_markdown(report)
    text = render_phase3b_forced_anchor_proto_reduction_text(report)
    assert "Forced-Anchor Proto Reduction" in markdown
    assert "variant=remove_family_lookup_all" in text


def test_proto_reduction_aggregates_infeasible_terminal_status() -> None:
    entries = [
        {
            "variant": "base",
            "evaluated": True,
            "status": "INFEASIBLE",
            "removed_constraint_count": 0,
            "wall_time": 0.2,
            "branches": 0,
            "conflicts": 0,
        }
    ]

    status = reduction_module._status_from_entries(entries)

    assert status["outcome"] == "proto_reduction_terminal_found"
    assert status["status_counts"] == {"INFEASIBLE": 1}
    assert reduction_module._best_terminal_entry(entries)["status"] == "INFEASIBLE"
    assert reduction_module._unlocking_variants(entries) == []


def test_proto_reduction_mixed_unknown_and_infeasible_is_terminal() -> None:
    entries = [
        {
            "variant": "base",
            "evaluated": True,
            "status": "UNKNOWN",
            "branches": 0,
            "conflicts": 0,
        },
        {
            "variant": "remove_family_lookup_table",
            "evaluated": True,
            "status": "INFEASIBLE",
            "branches": 0,
            "conflicts": 0,
        },
    ]

    status = reduction_module._status_from_entries(entries)

    assert status["outcome"] == "proto_reduction_terminal_found"
    assert status["status_counts"] == {"UNKNOWN": 1, "INFEASIBLE": 1}


def test_proto_reduction_zero_branch_unknown_outcome_unchanged() -> None:
    status = reduction_module._status_from_entries(
        [
            {
                "variant": "base",
                "evaluated": True,
                "status": "UNKNOWN",
                "branches": 0,
                "conflicts": 0,
            }
        ]
    )

    assert status["outcome"] == "proto_reduction_zero_branch_unknown_remaining"
    assert status["status_counts"] == {"UNKNOWN": 1}


def test_proto_reduction_search_progress_without_terminal_unchanged() -> None:
    status = reduction_module._status_from_entries(
        [
            {
                "variant": "base",
                "evaluated": True,
                "status": "UNKNOWN",
                "branches": 4,
                "conflicts": 1,
            }
        ]
    )

    assert status["outcome"] == "proto_reduction_search_progress_without_terminal"
    assert status["status_counts"] == {"UNKNOWN": 1}


def test_proto_reduction_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_forced_anchor_proto_reduction.py"

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

    assert "phase3b forced-anchor proto reduction" in no_write.stdout
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

    assert "forced_anchor_proto_reduction_json=" in write.stdout
    payload = json.loads(
        (output_dir / "forced_anchor_proto_reduction.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_forced_anchor_proto_reduction_v1"
    assert (output_dir / "forced_anchor_proto_reduction.md").exists()
    assert (output_dir / "forced_anchor_proto_reduction.txt").exists()


def test_proto_reduction_cli_accepts_solver_profile_json_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    profile_path = tmp_path / "solver_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "profile_id": "unit_file_profile",
                "search_branching": "fixed",
                "worker_count": 1,
            }
        ),
        encoding="utf-8",
    )
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_forced_anchor_proto_reduction.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(tmp_path / "project"),
            "--output-dir",
            str(output_dir),
            "--solver-profile-json",
            f"@{profile_path}",
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b forced-anchor proto reduction" in result.stdout
    assert not output_dir.exists()


def _check_status(report: Mapping[str, Any], check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])


def test_proto_reduction_accepts_dynamic_sparse_slot_variants() -> None:
    variants = reduction_module._normalize_variants(
        [
            "base",
            "replace_power_coverage_elements_with_selected_coord_literals",
            "replace_family_lookup_table_with_linear_shell_guards",
            "replace_power_coverage_elements_and_family_lookup_table_with_linear_shell_guards",
            "remove_power_coverage_elements_and_family_lookup_table_every_16_offset_3",
            "remove_power_coverage_elements_and_family_lookup_table_mod_8_7",
            "remove_power_coverage_elements_and_family_lookup_table_hash_bucket_8_6",
            "remove_power_coverage_elements_and_family_lookup_table_rows_family_mod_5_2",
            "remove_power_coverage_elements_template_protocol_storage_box_and_family_lookup_table",
            "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_keep_family_lookup_table",
            "remove_power_coverage_elements_template_protocol_storage_box_target_active_y_element_linear_and_family_lookup_table",
            "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_layer_final_slot_window_0_264_keep_family_lookup_table",
            "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_layer_block_slot_window_0_264_keep_family_lookup_table",
            "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_slot_window_128_32_keep_family_lookup_table",
            "remove_power_coverage_elements_except_template_protocol_storage_box_and_family_lookup_table",
            "remove_power_coverage_elements_except_templates_manufacturing_3x3+manufacturing_5x5_and_family_lookup_table",
            "replace_power_coverage_elements_template_protocol_storage_box_with_selected_coord_literals_and_family_lookup_table",
            "replace_power_coverage_elements_only_template_protocol_storage_box_with_selected_coord_literals_and_family_lookup_table",
            "remove_power_coverage_elements_except_template_protocol_storage_box_and_template_active_x_and_family_lookup_table",
            "remove_power_coverage_elements_except_template_protocol_storage_box_and_template_active_y_element_linear_and_family_lookup_table",
            "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_first_32_and_family_lookup_table",
            "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_last_32_and_family_lookup_table",
            "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_window_128_32_and_family_lookup_table",
            "remove_power_coverage_elements_except_template_protocol_storage_box_and_add_template_index_active_prefix_guard_and_family_lookup_table",
        ]
    )

    assert variants == (
        "base",
        "replace_power_coverage_elements_with_selected_coord_literals",
        "replace_family_lookup_table_with_linear_shell_guards",
        "replace_power_coverage_elements_and_family_lookup_table_with_linear_shell_guards",
        "remove_power_coverage_elements_and_family_lookup_table_every_16_offset_3",
        "remove_power_coverage_elements_and_family_lookup_table_mod_8_7",
        "remove_power_coverage_elements_and_family_lookup_table_hash_bucket_8_6",
        "remove_power_coverage_elements_and_family_lookup_table_rows_family_mod_5_2",
        "remove_power_coverage_elements_template_protocol_storage_box_and_family_lookup_table",
        "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_keep_family_lookup_table",
        "remove_power_coverage_elements_template_protocol_storage_box_target_active_y_element_linear_and_family_lookup_table",
        "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_layer_final_slot_window_0_264_keep_family_lookup_table",
        "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_layer_block_slot_window_0_264_keep_family_lookup_table",
        "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_slot_window_128_32_keep_family_lookup_table",
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_family_lookup_table",
        "remove_power_coverage_elements_except_templates_manufacturing_3x3+manufacturing_5x5_and_family_lookup_table",
        "replace_power_coverage_elements_template_protocol_storage_box_with_selected_coord_literals_and_family_lookup_table",
        "replace_power_coverage_elements_only_template_protocol_storage_box_with_selected_coord_literals_and_family_lookup_table",
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_template_active_x_and_family_lookup_table",
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_template_active_y_element_linear_and_family_lookup_table",
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_first_32_and_family_lookup_table",
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_last_32_and_family_lookup_table",
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_window_128_32_and_family_lookup_table",
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_add_template_index_active_prefix_guard_and_family_lookup_table",
    )


def test_family_lookup_sparse_selector_profiles_non_contiguous_slots() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    for slot_idx in range(6):
        family = model.NewIntVar(
            0,
            3,
            f"family__residual_optional::power_pole::slot::{slot_idx}",
        )
        d_lo = model.NewIntVar(0, 2, f"d_lo__slot::{slot_idx}")
        d_hi = model.NewIntVar(0, 2, f"d_hi__slot::{slot_idx}")
        model.AddAllowedAssignments(
            [d_lo, d_hi, family],
            [(0, 0, 0), (0, 1, 1), (1, 1, 2), (1, 2, 3)],
        )
    proto = model.Proto()

    payload = reduction_module._remove_family_lookup_table_constraints_by_slot_selector_payload(
        proto,
        selector={"kind": "every", "step": 2, "offset": 1},
    )

    assert payload["candidate_table_constraint_count"] == 6
    assert payload["removed_constraint_count"] == 3
    assert payload["removed_slot_indices"] == [1, 3, 5]
    assert payload["slot_selection_profile"]["selected_fraction"] == 0.5
    assert payload["table_shape_profile"]["arity_counts"] == {"3": 6}
    assert payload["table_shape_profile"]["family_column_counts"] == {"2": 6}


def test_proto_profile_reports_cover_choice_modes_by_template() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    model.NewIntVar(
        0,
        9,
        "cover_choice_idx__residual_optional::protocol_storage_box::slot::0",
    )
    model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    model.NewIntVar(
        0,
        4,
        "cover_choice_block_idx__mandatory::manufacturing_3x3::slot::1",
    )
    model.NewIntVar(
        0,
        63,
        "cover_choice_local_idx__mandatory::manufacturing_3x3::slot::1",
    )
    model.NewBoolVar(
        "cover_choice_block_active__mandatory::manufacturing_3x3::slot::1"
    )
    model.NewIntVar(
        0,
        4,
        "cover_choice_block_idx__group::manufacturing_5x5::crusher_blue_iron::1::slot::2",
    )

    profile = reduction_module._proto_profile(model.Proto())
    cover_profile = profile["cover_choice_profile"]

    assert cover_profile["total_cover_choice_variables"] == 6
    assert cover_profile["mode_counts"]["wide_idx"] == 1
    assert cover_profile["mode_counts"]["wide_target"] == 1
    assert cover_profile["mode_counts"]["block_idx"] == 2
    assert cover_profile["mode_counts"]["block_local_idx"] == 1
    assert cover_profile["mode_counts"]["block_target"] == 1
    assert cover_profile["role_counts"]["wide_selector"] == 1
    assert cover_profile["role_counts"]["final_target_channel"] == 1
    assert cover_profile["role_counts"]["block_selector"] == 2
    assert cover_profile["role_counts"]["local_selector"] == 1
    assert cover_profile["role_counts"]["block_intermediate_target_channel"] == 1
    assert cover_profile["target_channel_profile"] == {
        "final_target_channel_variables": 1,
        "block_intermediate_target_channel_variables": 1,
        "wide_selector_variables": 1,
        "block_selector_variables": 2,
        "local_selector_variables": 1,
        "block_selected_literal_variables": 0,
        "note": (
            "cover_choice_active/x/y are final selected-pole target channels; "
            "they remain in block_element encoding even when wide selectors "
            "are eliminated."
        ),
    }
    assert cover_profile["template_counts"]["protocol_storage_box"] == {
        "wide_idx": 1,
        "wide_target": 1,
    }
    assert cover_profile["template_counts"]["manufacturing_3x3"] == {
        "block_idx": 1,
        "block_local_idx": 1,
        "block_target": 1,
    }
    assert cover_profile["template_counts"]["manufacturing_5x5"] == {
        "block_idx": 1,
    }
    assert cover_profile["template_slot_samples"]["manufacturing_3x3"] == [1]
    assert cover_profile["template_slot_samples"]["manufacturing_5x5"] == [2]


def test_family_lookup_row_reduction_reports_strengthening_warning() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    family = model.NewIntVar(
        0,
        3,
        "family__residual_optional::power_pole::slot::42",
    )
    d_lo = model.NewIntVar(0, 2, "d_lo__slot::42")
    d_hi = model.NewIntVar(0, 2, "d_hi__slot::42")
    model.AddAllowedAssignments(
        [d_lo, d_hi, family],
        [(0, 0, 0), (0, 1, 1), (1, 1, 2), (1, 2, 3)],
    )
    proto = model.Proto()

    payload = reduction_module._remove_family_lookup_table_rows_payload(
        proto,
        selector={"kind": "family_mod", "modulus": 2, "remainder": 1},
    )

    assert payload["candidate_table_constraint_count"] == 1
    assert payload["touched_constraint_count"] == 1
    assert payload["removed_row_count"] == 2
    assert payload["rows_before_total"] == 4
    assert payload["rows_after_total"] == 2
    assert "not proof-source" in payload["diagnostic_warning"]


def test_power_coverage_element_template_reduction_only_removes_selected_template() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    manufacturing_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__mandatory::manufacturing_3x3::slot::0",
    )
    model.AddElement(choice, [0, 1], protocol_active)
    model.AddElement(choice, [3, 4], protocol_x)
    model.AddElement(choice, [0, 1], manufacturing_active)
    model.AddElement(choice, [5, 6], manufacturing_x)
    proto = model.Proto()

    payload = reduction_module._remove_power_coverage_element_template_constraints_payload(
        proto,
        powered_template="protocol_storage_box",
    )

    assert payload["removed_constraint_count"] == 2
    assert payload["removed_by_prefix"] == {
        "cover_choice_active__": 1,
        "cover_choice_x__": 1,
        "cover_choice_y__": 0,
    }
    remaining_names = [
        proto.variables[int(var_idx)].name
        for constraint in proto.constraints
        if reduction_module._constraint_has_field(constraint, "element")
        for var_idx in reduction_module._element_target_var_indices(constraint.element)
        if proto.variables[int(var_idx)].name.startswith(
            ("cover_choice_active__", "cover_choice_x__", "cover_choice_y__")
        )
    ]
    assert remaining_names == [
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0",
        "cover_choice_x__mandatory::manufacturing_3x3::slot::0",
    ]


def test_power_coverage_element_template_slot_window_reduction_limits_slots() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    source_a = model.NewIntVar(0, 9, "source_a")
    source_b = model.NewIntVar(0, 9, "source_b")
    targets = [
        model.NewBoolVar(
            "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
        ),
        model.NewIntVar(
            0,
            9,
            "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
        ),
        model.NewBoolVar(
            "cover_choice_active__residual_optional::protocol_storage_box::slot::1"
        ),
        model.NewIntVar(
            0,
            9,
            "cover_choice_x__residual_optional::protocol_storage_box::slot::1",
        ),
        model.NewIntVar(
            0,
            9,
            "cover_choice_block_x__residual_optional::protocol_storage_box::slot::1__block::007",
        ),
        model.NewBoolVar(
            "cover_choice_active__mandatory::manufacturing_3x3::slot::1"
        ),
    ]
    for target in targets:
        model.AddElement(choice, [source_a, source_b], target)
    proto = model.Proto()

    payload = reduction_module._remove_power_coverage_element_template_slot_window_constraints_payload(
        proto,
        powered_template="protocol_storage_box",
        target_prefixes=("cover_choice_active__", "cover_choice_x__"),
        start=1,
        count=1,
    )

    assert payload["removed_constraint_count"] == 3
    assert payload["removed_slot_indices"] == [1]
    assert payload["removed_by_prefix"] == {
        "cover_choice_active__": 1,
        "cover_choice_block_x__": 1,
        "cover_choice_x__": 1,
    }
    remaining_target_names = [
        proto.variables[int(var_idx)].name
        for constraint in proto.constraints
        if reduction_module._constraint_has_field(constraint, "element")
        for var_idx in reduction_module._element_target_var_indices(constraint.element)
        if proto.variables[int(var_idx)].name.startswith(
            ("cover_choice_active__", "cover_choice_x__")
        )
    ]
    assert remaining_target_names == [
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0",
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
        "cover_choice_active__mandatory::manufacturing_3x3::slot::1",
    ]


def test_power_coverage_element_template_slot_window_can_filter_channel_layer() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    source_a = model.NewIntVar(0, 9, "source_a")
    source_b = model.NewIntVar(0, 9, "source_b")
    targets = [
        model.NewBoolVar(
            "cover_choice_active__residual_optional::protocol_storage_box::slot::1"
        ),
        model.NewIntVar(
            0,
            9,
            "cover_choice_x__residual_optional::protocol_storage_box::slot::1",
        ),
        model.NewBoolVar(
            "cover_choice_block_active__residual_optional::protocol_storage_box::slot::1__block::007"
        ),
        model.NewIntVar(
            0,
            9,
            "cover_choice_block_x__residual_optional::protocol_storage_box::slot::1__block::007",
        ),
    ]
    for target in targets:
        model.AddElement(choice, [source_a, source_b], target)
    proto = model.Proto()

    payload = reduction_module._remove_power_coverage_element_template_slot_window_constraints_payload(
        proto,
        powered_template="protocol_storage_box",
        target_prefixes=("cover_choice_active__", "cover_choice_x__"),
        channel_layer="block",
        start=1,
        count=1,
    )

    assert payload["removed_constraint_count"] == 2
    assert payload["channel_layer"] == "block"
    assert payload["removed_by_prefix"] == {
        "cover_choice_block_active__": 1,
        "cover_choice_block_x__": 1,
    }
    remaining_target_names = [
        proto.variables[int(var_idx)].name
        for constraint in proto.constraints
        if reduction_module._constraint_has_field(constraint, "element")
        for var_idx in reduction_module._element_target_var_indices(constraint.element)
        if proto.variables[int(var_idx)].name.startswith(
            (
                "cover_choice_active__",
                "cover_choice_x__",
                "cover_choice_block_active__",
                "cover_choice_block_x__",
            )
        )
    ]
    assert remaining_target_names == [
        "cover_choice_active__residual_optional::protocol_storage_box::slot::1",
        "cover_choice_x__residual_optional::protocol_storage_box::slot::1",
    ]


def test_power_coverage_element_except_template_reduction_keeps_excluded_template() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    manufacturing_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__mandatory::manufacturing_3x3::slot::0",
    )
    model.AddElement(choice, [0, 1], protocol_active)
    model.AddElement(choice, [3, 4], protocol_x)
    model.AddElement(choice, [0, 1], manufacturing_active)
    model.AddElement(choice, [5, 6], manufacturing_x)
    proto = model.Proto()

    payload = reduction_module._remove_power_coverage_element_except_template_constraints_payload(
        proto,
        excluded_powered_template="protocol_storage_box",
    )

    assert payload["removed_constraint_count"] == 2
    assert payload["removed_by_prefix"] == {
        "cover_choice_active__": 1,
        "cover_choice_x__": 1,
        "cover_choice_y__": 0,
    }
    assert payload["kept_by_prefix"] == {
        "cover_choice_active__": 1,
        "cover_choice_x__": 1,
        "cover_choice_y__": 0,
    }
    remaining_names = [
        proto.variables[int(var_idx)].name
        for constraint in proto.constraints
        if reduction_module._constraint_has_field(constraint, "element")
        for var_idx in reduction_module._element_target_var_indices(constraint.element)
        if proto.variables[int(var_idx)].name.startswith(
            ("cover_choice_active__", "cover_choice_x__", "cover_choice_y__")
        )
    ]
    assert remaining_names == [
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0",
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    ]


def test_except_template_target_variant_parses_before_broad_except_template() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    protocol_y = model.NewIntVar(
        0,
        9,
        "cover_choice_y__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    model.AddElement(choice, [0, 1], protocol_active)
    model.AddElement(choice, [3, 4], protocol_x)
    model.AddElement(choice, [5, 6], protocol_y)
    model.AddElement(choice, [0, 1], manufacturing_active)

    payload = reduction_module._apply_dynamic_proto_reduction(
        model.Proto(),
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_template_active_x_and_family_lookup_table",
    )

    assert payload is not None
    parts = payload["parts"]
    assert parts["power_coverage_except_template_elements"]["excluded_powered_template"] == "protocol_storage_box"
    assert parts["power_coverage_except_template_elements"]["removed_constraint_count"] == 1
    assert parts["power_coverage_template_element_targets"]["powered_template"] == "protocol_storage_box"
    assert parts["power_coverage_template_element_targets"]["removed_constraint_count"] == 2


def test_template_target_variant_removes_only_selected_template_targets() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    protocol_y = model.NewIntVar(
        0,
        9,
        "cover_choice_y__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    model.AddElement(choice, [0, 1], protocol_active)
    model.AddElement(choice, [3, 4], protocol_x)
    model.AddElement(choice, [5, 6], protocol_y)
    model.AddElement(choice, [0, 1], manufacturing_active)

    payload = reduction_module._apply_dynamic_proto_reduction(
        model.Proto(),
        "remove_power_coverage_elements_template_protocol_storage_box_target_active_x_keep_family_lookup_table",
    )

    assert payload is not None
    assert payload["family_lookup_table_removed"] is False
    assert "family_lookup_table" not in payload["parts"]
    part = payload["parts"]["power_coverage_template_element_targets"]
    assert part["powered_template"] == "protocol_storage_box"
    assert part["target_prefixes"] == [
        "cover_choice_active__",
        "cover_choice_block_active__",
        "cover_choice_x__",
        "cover_choice_block_x__",
    ]
    assert part["removed_constraint_count"] == 2
    remaining_targets = [
        getattr(model.Proto().variables[int(var_idx)], "name", "")
        for constraint in model.Proto().constraints
        if reduction_module._constraint_has_field(constraint, "element")
        for var_idx in reduction_module._element_target_var_indices(constraint.element)
    ]
    assert "cover_choice_y__residual_optional::protocol_storage_box::slot::0" in remaining_targets
    assert "cover_choice_active__mandatory::manufacturing_3x3::slot::0" in remaining_targets


def test_except_template_target_element_linear_variant_parses_before_target_variant() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_y = model.NewIntVar(
        0,
        9,
        "cover_choice_y__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    model.AddElement(choice, [0, 1], protocol_active)
    model.AddElement(choice, [5, 6], protocol_y)
    model.AddElement(choice, [0, 1], manufacturing_active)
    model.Add(protocol_active == 1)
    model.Add(protocol_y <= 5).OnlyEnforceIf(protocol_active)
    base_proto = reduction_module._clone_model_proto(model.Proto())

    payload = reduction_module._apply_dynamic_proto_reduction(
        reduction_module._clone_model_proto(base_proto),
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_template_active_y_element_linear_and_family_lookup_table",
    )

    assert payload is not None
    parts = payload["parts"]
    assert parts["power_coverage_except_template_elements"]["excluded_powered_template"] == "protocol_storage_box"
    assert parts["power_coverage_except_template_elements"]["removed_constraint_count"] == 1
    assert parts["power_coverage_template_element_targets"]["removed_constraint_count"] == 2
    assert parts["power_coverage_template_linear_targets"]["removed_constraint_count"] == 2
    assert payload["family_lookup_table_removed"] is True

    keep_payload = reduction_module._apply_dynamic_proto_reduction(
        reduction_module._clone_model_proto(base_proto),
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_template_active_y_element_linear_keep_family_lookup_table",
    )

    assert keep_payload is not None
    assert keep_payload["family_lookup_table_removed"] is False
    assert "family_lookup_table" not in keep_payload["parts"]
    assert keep_payload["parts"]["power_coverage_except_template_elements"]["removed_constraint_count"] == 1
    assert keep_payload["parts"]["power_coverage_template_element_targets"]["removed_constraint_count"] == 2
    assert keep_payload["parts"]["power_coverage_template_linear_targets"]["removed_constraint_count"] == 2


def test_except_template_index_restriction_can_keep_family_lookup_table() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    model.AddElement(choice, [0, 1], protocol_active)
    model.AddElement(choice, [0, 1], manufacturing_active)
    base_proto = reduction_module._clone_model_proto(model.Proto())

    keep_lookup_variant = (
        "remove_power_coverage_elements_except_template_protocol_storage_box"
        "_keep_family_lookup_table"
    )
    keep_lookup_payload = reduction_module._apply_dynamic_proto_reduction(
        reduction_module._clone_model_proto(base_proto),
        keep_lookup_variant,
    )
    assert keep_lookup_payload is not None
    assert keep_lookup_payload["family_lookup_table_removed"] is False
    assert "family_lookup_table" not in keep_lookup_payload["parts"]
    assert reduction_module._normalize_variants([keep_lookup_variant]) == (
        keep_lookup_variant,
    )

    variant = (
        "remove_power_coverage_elements_except_template_protocol_storage_box"
        "_and_restrict_template_index_first_4"
    )
    payload = reduction_module._apply_dynamic_proto_reduction(
        reduction_module._clone_model_proto(base_proto),
        variant,
    )

    assert payload is not None
    assert payload["family_lookup_table_removed"] is False
    assert "family_lookup_table" not in payload["parts"]
    assert payload["parts"]["power_coverage_except_template_elements"]["removed_constraint_count"] == 1
    assert reduction_module._normalize_variants([variant]) == (variant,)
    assert reduction_module._template_index_restriction_from_variant(variant) == {
        "powered_template": "protocol_storage_box",
        "mode": "first",
        "limit": 4,
    }


def test_power_coverage_element_except_templates_reduction_keeps_group() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    choice = model.NewIntVar(0, 1, "cover_choice_idx__slot")
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    manufacturing3_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    manufacturing5_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_5x5::slot::0"
    )
    model.AddElement(choice, [0, 1], protocol_active)
    model.AddElement(choice, [0, 1], manufacturing3_active)
    model.AddElement(choice, [0, 1], manufacturing5_active)
    proto = model.Proto()

    payload = reduction_module._remove_power_coverage_element_except_templates_constraints_payload(
        proto,
        excluded_powered_templates=("manufacturing_3x3", "manufacturing_5x5"),
    )

    assert payload["removed_constraint_count"] == 1
    assert payload["kept_by_prefix"]["cover_choice_active__"] == 2
    assert payload["excluded_powered_templates"] == [
        "manufacturing_3x3",
        "manufacturing_5x5",
    ]
    assert reduction_module._template_group_from_token(
        "manufacturing_3x3+manufacturing_5x5"
    ) == ("manufacturing_3x3", "manufacturing_5x5")
    assert reduction_module._cover_choice_target_prefixes_from_token("active_x") == (
        "cover_choice_active__",
        "cover_choice_x__",
    )


def test_power_coverage_linear_template_reduction_only_removes_selected_template() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_active = model.NewBoolVar(
        "cover_choice_active__mandatory::manufacturing_3x3::slot::0"
    )
    manufacturing_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__mandatory::manufacturing_3x3::slot::0",
    )
    model.Add(protocol_active == 1)
    model.Add(protocol_x <= 5).OnlyEnforceIf(protocol_active)
    model.Add(manufacturing_active == 1)
    model.Add(manufacturing_x <= 5).OnlyEnforceIf(manufacturing_active)
    proto = model.Proto()

    payload = reduction_module._remove_power_coverage_linear_template_constraints_payload(
        proto,
        powered_template="protocol_storage_box",
        mode="power_coverage_active_and_geometry_relaxed",
    )

    assert payload["removed_constraint_count"] == 2
    assert payload["removed_by_prefix"] == {
        "cover_choice_active__": 1,
        "cover_choice_x__": 1,
        "cover_choice_y__": 0,
    }
    remaining_var_names = {
        proto.variables[int(var_idx)].name
        for constraint in proto.constraints
        if reduction_module._constraint_has_field(constraint, "linear")
        for var_idx in constraint.linear.vars
    }
    assert "cover_choice_active__mandatory::manufacturing_3x3::slot::0" in remaining_var_names
    assert "cover_choice_x__mandatory::manufacturing_3x3::slot::0" in remaining_var_names
    assert not any("protocol_storage_box" in name for name in remaining_var_names)


def test_power_coverage_linear_template_target_reduction_removes_selected_targets() -> None:
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    protocol_active = model.NewBoolVar(
        "cover_choice_active__residual_optional::protocol_storage_box::slot::0"
    )
    protocol_x = model.NewIntVar(
        0,
        9,
        "cover_choice_x__residual_optional::protocol_storage_box::slot::0",
    )
    protocol_y = model.NewIntVar(
        0,
        9,
        "cover_choice_y__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_y = model.NewIntVar(
        0,
        9,
        "cover_choice_y__mandatory::manufacturing_3x3::slot::0",
    )
    model.Add(protocol_active == 1)
    model.Add(protocol_x <= 5).OnlyEnforceIf(protocol_active)
    model.Add(protocol_y <= 5).OnlyEnforceIf(protocol_active)
    model.Add(manufacturing_y <= 5)
    proto = model.Proto()

    payload = reduction_module._remove_power_coverage_linear_template_target_constraints_payload(
        proto,
        powered_template="protocol_storage_box",
        target_prefixes=reduction_module._cover_choice_target_prefixes_from_token("active_y"),
    )

    assert payload["removed_constraint_count"] == 2
    assert payload["removed_by_prefix"] == {
        "cover_choice_active__": 1,
        "cover_choice_y__": 1,
    }
    remaining_var_names = {
        proto.variables[int(var_idx)].name
        for constraint in proto.constraints
        if reduction_module._constraint_has_field(constraint, "linear")
        for var_idx in constraint.linear.vars
    }
    assert "cover_choice_x__residual_optional::protocol_storage_box::slot::0" in remaining_var_names
    assert "cover_choice_y__mandatory::manufacturing_3x3::slot::0" in remaining_var_names


def test_selected_coord_literal_replacement_adds_expected_constraints() -> None:
    from ortools.sat.python import cp_model

    from src.models._cpsat_compat import cp_model_from_proto

    model = cp_model.CpModel()
    pole_active_0 = model.NewBoolVar("active__residual_optional::power_pole::slot::0")
    pole_x_0 = model.NewIntVar(0, 9, "x__residual_optional::power_pole::slot::0")
    pole_y_0 = model.NewIntVar(0, 9, "y__residual_optional::power_pole::slot::0")
    pole_active_1 = model.NewBoolVar("active__residual_optional::power_pole::slot::1")
    pole_x_1 = model.NewIntVar(0, 9, "x__residual_optional::power_pole::slot::1")
    pole_y_1 = model.NewIntVar(0, 9, "y__residual_optional::power_pole::slot::1")
    powered_x = model.NewIntVar(0, 9, "x__mandatory::manufacturing_3x3::slot::0")
    powered_y = model.NewIntVar(0, 9, "y__mandatory::manufacturing_3x3::slot::0")

    pole_0 = SimpleNamespace(
        key="pole0",
        active=pole_active_0,
        x=pole_x_0,
        y=pole_y_0,
        dims=(2, 2),
    )
    pole_1 = SimpleNamespace(
        key="pole1",
        active=pole_active_1,
        x=pole_x_1,
        y=pole_y_1,
        dims=(2, 2),
    )
    powered = SimpleNamespace(
        key="powered0",
        active=None,
        x=powered_x,
        y=powered_y,
        dims=(3, 3),
    )

    class FakeDelegate:
        residual_optional_slots = {"power_pole": [pole_0, pole_1]}

        def _all_powered_slots(self):
            return [powered]

        def _power_coverage_radius(self):
            return 1

    source_model = SimpleNamespace(
        _coordinate_delegate=FakeDelegate(),
        grid_w=10,
        grid_h=10,
    )
    local_model = cp_model_from_proto(model.Proto())

    payload = reduction_module._add_power_coverage_selected_coord_literal_replacement(
        local_model,
        source_model,
    )

    assert payload["cover_literal_count"] == 2
    assert payload["selected_coord_var_count"] == 2
    assert payload["active_implication_constraint_count"] == 2
    assert payload["selected_coord_channel_constraint_count"] == 4
    assert payload["geometry_constraint_count"] == 4
    assert payload["witness_sum_constraint_count"] == 1
    assert payload["added_constraint_count"] == 11


def test_selected_coord_literal_replacement_filters_powered_template() -> None:
    from ortools.sat.python import cp_model

    from src.models._cpsat_compat import cp_model_from_proto

    model = cp_model.CpModel()
    pole_active = model.NewBoolVar("active__residual_optional::power_pole::slot::0")
    pole_x = model.NewIntVar(0, 9, "x__residual_optional::power_pole::slot::0")
    pole_y = model.NewIntVar(0, 9, "y__residual_optional::power_pole::slot::0")
    protocol_x = model.NewIntVar(
        0,
        9,
        "x__residual_optional::protocol_storage_box::slot::0",
    )
    protocol_y = model.NewIntVar(
        0,
        9,
        "y__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_x = model.NewIntVar(0, 9, "x__mandatory::manufacturing_3x3::slot::0")
    manufacturing_y = model.NewIntVar(0, 9, "y__mandatory::manufacturing_3x3::slot::0")
    pole = SimpleNamespace(
        key="pole0",
        active=pole_active,
        x=pole_x,
        y=pole_y,
        dims=(2, 2),
    )
    protocol = SimpleNamespace(
        key="protocol0",
        template="protocol_storage_box",
        active=None,
        x=protocol_x,
        y=protocol_y,
        dims=(1, 1),
    )
    manufacturing = SimpleNamespace(
        key="manufacturing0",
        template="manufacturing_3x3",
        active=None,
        x=manufacturing_x,
        y=manufacturing_y,
        dims=(3, 3),
    )

    class FakeDelegate:
        residual_optional_slots = {"power_pole": [pole]}

        def _all_powered_slots(self):
            return [protocol, manufacturing]

        def _power_coverage_radius(self):
            return 1

    local_model = cp_model_from_proto(model.Proto())
    payload = reduction_module._add_power_coverage_selected_coord_literal_replacement(
        local_model,
        SimpleNamespace(_coordinate_delegate=FakeDelegate(), grid_w=10, grid_h=10),
        powered_template="protocol_storage_box",
    )

    assert payload["selected_powered_template"] == "protocol_storage_box"
    assert payload["source_powered_slot_count"] == 2
    assert payload["powered_slot_count"] == 1
    assert payload["skipped_powered_slot_count"] == 1
    assert payload["cover_literal_count"] == 1
    assert payload["added_constraint_count"] == 8


def test_template_index_restriction_adds_constraints_for_selected_template() -> None:
    from ortools.sat.python import cp_model

    from src.models._cpsat_compat import cp_model_from_proto

    model = cp_model.CpModel()
    protocol_idx = model.NewIntVar(
        0,
        99,
        "cover_choice_idx__residual_optional::protocol_storage_box::slot::0",
    )
    manufacturing_idx = model.NewIntVar(
        0,
        99,
        "cover_choice_idx__mandatory::manufacturing_3x3::slot::0",
    )
    model.Add(protocol_idx >= 0)
    model.Add(manufacturing_idx >= 0)
    protocol = SimpleNamespace(
        key="residual_optional::protocol_storage_box::slot::0",
        template="protocol_storage_box",
    )
    manufacturing = SimpleNamespace(
        key="mandatory::manufacturing_3x3::slot::0",
        template="manufacturing_3x3",
    )

    class FakeDelegate:
        residual_optional_slots = {"power_pole": [object() for _ in range(100)]}

        def _all_powered_slots(self):
            return [protocol, manufacturing]

    local_model = cp_model_from_proto(model.Proto())
    payload = reduction_module._add_power_coverage_template_index_restriction(
        local_model,
        SimpleNamespace(_coordinate_delegate=FakeDelegate()),
        powered_template="protocol_storage_box",
        mode="first",
        limit=32,
    )

    assert payload["mode"] == "template_cover_choice_index_restriction"
    assert payload["powered_template"] == "protocol_storage_box"
    assert payload["source_powered_slot_count"] == 2
    assert payload["powered_slot_count"] == 1
    assert payload["restriction_mode"] == "first"
    assert payload["limit"] == 32
    assert payload["lower_bound"] == 0
    assert payload["upper_bound"] == 31
    assert payload["window_width"] == 32
    assert payload["added_constraint_count"] == 1
    assert payload["missing_index_var_count"] == 0
    assert reduction_module._template_index_restriction_from_variant(
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_first_32_and_family_lookup_table"
    ) == {"powered_template": "protocol_storage_box", "mode": "first", "limit": 32}
    assert reduction_module._template_index_restriction_from_variant(
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_first_32"
    ) == {"powered_template": "protocol_storage_box", "mode": "first", "limit": 32}
    assert reduction_module._template_index_restriction_from_variant(
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_last_32_and_family_lookup_table"
    ) == {"powered_template": "protocol_storage_box", "mode": "last", "limit": 32}
    assert reduction_module._template_index_restriction_from_variant(
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_last_32"
    ) == {"powered_template": "protocol_storage_box", "mode": "last", "limit": 32}
    assert reduction_module._template_index_restriction_from_variant(
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_window_128_32_and_family_lookup_table"
    ) == {
        "powered_template": "protocol_storage_box",
        "mode": "window",
        "start": 128,
        "count": 32,
    }
    assert reduction_module._template_index_restriction_from_variant(
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_restrict_template_index_window_128_32"
    ) == {
        "powered_template": "protocol_storage_box",
        "mode": "window",
        "start": 128,
        "count": 32,
    }
    assert reduction_module._index_restriction_window(
        mode="last",
        limit=32,
        start=0,
        count=0,
        pole_slot_count=100,
    ) == {"lower_bound": 68, "upper_bound": 99}
    assert reduction_module._index_restriction_window(
        mode="window",
        limit=0,
        start=128,
        count=32,
        pole_slot_count=150,
    ) == {"lower_bound": 128, "upper_bound": 149}


def test_template_index_active_prefix_guard_adds_redundant_index_bounds() -> None:
    from ortools.sat.python import cp_model

    from src.models._cpsat_compat import cp_model_from_proto

    model = cp_model.CpModel()
    pole_active_0 = model.NewBoolVar("active__residual_optional::power_pole::slot::0")
    pole_active_1 = model.NewBoolVar("active__residual_optional::power_pole::slot::1")
    protocol_idx = model.NewIntVar(
        0,
        9,
        "cover_choice_idx__residual_optional::protocol_storage_box::slot::0",
    )
    protocol_active = model.NewBoolVar(
        "active__residual_optional::protocol_storage_box::slot::0"
    )
    manufacturing_idx = model.NewIntVar(
        0,
        9,
        "cover_choice_idx__mandatory::manufacturing_3x3::slot::0",
    )
    model.Add(protocol_idx >= 0)
    model.Add(manufacturing_idx >= 0)
    pole_0 = SimpleNamespace(active=pole_active_0)
    pole_1 = SimpleNamespace(active=pole_active_1)
    protocol = SimpleNamespace(
        key="residual_optional::protocol_storage_box::slot::0",
        template="protocol_storage_box",
        active=protocol_active,
    )
    manufacturing = SimpleNamespace(
        key="mandatory::manufacturing_3x3::slot::0",
        template="manufacturing_3x3",
        active=None,
    )

    class FakeDelegate:
        residual_optional_slots = {"power_pole": [pole_0, pole_1]}

        def _all_powered_slots(self):
            return [protocol, manufacturing]

    local_model = cp_model_from_proto(model.Proto())
    payload = reduction_module._add_power_coverage_template_index_active_prefix_guard(
        local_model,
        SimpleNamespace(_coordinate_delegate=FakeDelegate()),
        powered_template="protocol_storage_box",
    )

    assert payload["mode"] == "template_cover_choice_index_active_prefix_guard"
    assert payload["powered_template"] == "protocol_storage_box"
    assert payload["source_powered_slot_count"] == 2
    assert payload["powered_slot_count"] == 1
    assert payload["pole_active_var_count"] == 2
    assert payload["added_constraint_count"] == 1
    assert payload["powered_active_guard_count"] == 1
    assert payload["missing_index_var_count"] == 0
    assert reduction_module._template_index_active_prefix_guard_from_variant(
        "remove_power_coverage_elements_except_template_protocol_storage_box_and_add_template_index_active_prefix_guard_and_family_lookup_table"
    ) == {"powered_template": "protocol_storage_box"}


def test_family_shell_guard_shape_classifies_rows() -> None:
    assert reduction_module._family_shell_guard_shape([(3, 4)]) == {
        "kind": "single",
        "row_count": 1,
        "d_lo": 3,
        "d_hi": 4,
    }
    rectangle = reduction_module._family_shell_guard_shape(
        [(0, 9), (0, 10), (1, 9), (1, 10)]
    )
    assert rectangle["kind"] == "rectangle"
    assert rectangle["d_lo_min"] == 0
    assert rectangle["d_lo_max"] == 1
    assert rectangle["d_hi_min"] == 9
    assert rectangle["d_hi_max"] == 10
    triangle = reduction_module._family_shell_guard_shape(
        [(0, 0), (0, 1), (1, 1)]
    )
    assert triangle["kind"] == "upper_triangle"
    fallback = reduction_module._family_shell_guard_shape([(3, 4), (4, 5)])
    assert fallback["kind"] == "fallback_table"
    assert fallback["row_count"] == 2


def test_family_lookup_linear_shell_guards_add_compact_constraints(monkeypatch) -> None:
    from ortools.sat.python import cp_model

    from src.models._cpsat_compat import cp_model_from_proto

    model = cp_model.CpModel()
    d_lo = model.NewIntVar(0, 10, "d_lo__slot0")
    d_hi = model.NewIntVar(0, 10, "d_hi__slot0")
    lit_single = model.NewBoolVar("is_family__slot0__family_000")
    lit_rect = model.NewBoolVar("is_family__slot0__family_001")
    lit_tri = model.NewBoolVar("is_family__slot0__family_002")
    lit_fallback = model.NewBoolVar("is_family__slot0__family_003")
    payload = {
        "slots": [
            {
                "slot_key": "slot0",
                "d_lo_var_index": d_lo.Index(),
                "d_hi_var_index": d_hi.Index(),
                "family_lit_indices_by_family_id": {
                    "0": lit_single.Index(),
                    "1": lit_rect.Index(),
                    "2": lit_tri.Index(),
                    "3": lit_fallback.Index(),
                },
            }
        ],
        "rows_by_family_id": {
            "0": [[3, 4]],
            "1": [[0, 9], [0, 10], [1, 9], [1, 10]],
            "2": [[0, 0], [0, 1], [1, 1]],
            "3": [[3, 4], [4, 5]],
        },
    }
    monkeypatch.setattr(
        reduction_module,
        "_power_family_shell_pair_table_payload",
        lambda source_model, local_proto: payload,
    )

    local_model = cp_model_from_proto(model.Proto())
    result = reduction_module._add_family_lookup_linear_shell_guards(
        local_model,
        object(),
        local_model.Proto(),
    )

    assert result["slot_count"] == 1
    assert result["family_lit_count"] == 4
    assert result["shape_counts"] == {
        "fallback_table": 1,
        "rectangle": 1,
        "single": 1,
        "upper_triangle": 1,
    }
    assert result["linear_constraint_count"] == 11
    assert result["fallback_table_constraint_count"] == 1
    assert result["fallback_table_row_total"] == 2
    assert result["added_constraint_count"] == 12
