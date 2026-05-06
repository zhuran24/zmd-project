from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_power_protocol_interaction import (
    build_phase3b_power_protocol_interaction_diagnostic,
    render_phase3b_power_protocol_interaction_markdown,
    render_phase3b_power_protocol_interaction_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _power_delta_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_coverage_anchor_delta_v1"},
        "candidate": {"key": "67x13"},
        "delta": {
            "power_family_changed_count": 13,
            "power_family_positive_delta_sum": 63,
            "power_family_negative_delta_sum": -14,
            "mandatory_surviving_delta": -3548,
            "optional_surviving_delta": -136,
            "top_power_family_deltas": [
                {"family": "family_009", "baseline": 480, "comparison": 526, "delta": 46}
            ],
            "top_mandatory_group_deltas": [
                {
                    "group_id": "group::manufacturing_5x5::planter_sandleaf::10",
                    "facility_type": "manufacturing_5x5",
                    "baseline_surviving_count": 13128,
                    "comparison_surviving_count": 12868,
                    "surviving_delta": -260,
                }
            ],
            "optional_template_deltas": [
                {
                    "template": "power_pole",
                    "baseline_surviving_count": 3809,
                    "comparison_surviving_count": 3809,
                    "surviving_delta": 0,
                },
                {
                    "template": "protocol_storage_box",
                    "baseline_surviving_count": 14068,
                    "comparison_surviving_count": 13932,
                    "surviving_delta": -136,
                },
            ],
            "diagnostic_findings": [
                "power_family_bounds_shift",
                "power_pole_candidate_domain_stable_despite_family_bound_shift",
                "protocol_storage_box_domain_tightens",
            ],
        },
    }


def _residual_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_residual_optional_encoding_inventory_v1"},
        "candidate": {"key": "67x13"},
        "encoding": {
            "residual_optional_slots": {
                "by_template": {"power_pole": 763, "protocol_storage_box": 544},
                "total": 1307,
            },
            "power_coverage": {
                "representation": "coordinate_geometric",
                "encoding": "geometric_element_witness_v1",
                "powered_slots": 763,
                "pole_slots": 763,
                "witness_indices": 763,
                "element_constraints": 2289,
                "radius": 5,
            },
            "global_valid_inequalities": {
                "optional_cardinality_bounds": {
                    "protocol_storage_box": {"lower": 1, "slot_pool_upper_bound": 544}
                },
                "powered_template_demands": {"protocol_storage_box": 1},
                "lower_bound_optional_powered_demands": {"protocol_storage_box": 1},
                "ghost_aware_via_pole_feasibility": {
                    "enabled": True,
                    "conditioned_family_upper_bound_constraints": 3384,
                },
            },
            "proto": {"variable_count": 57900, "constraint_count": 142247},
        },
    }


def _zero_branch_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_zero_branch_unknown_triage_v1"},
        "candidate": {"key": "67x13"},
        "matrix": {"zero_branch_unknown_count": 21},
        "findings": ["power_coverage_core_is_primary_suspect"],
        "recommendation": "Zero-branch UNKNOWN points at power coverage core.",
    }


def _model_slice_payload(findings: list[str]) -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "slice_matrix": {
            "diagnostic_findings": findings,
            "status_counts_by_variant": {
                "base": {"UNKNOWN": 1},
                "skip_power_coverage_no_protocol_lower_bound_core": {"OPTIMAL": 1},
            },
        },
    }


def _family_audit_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_audit_v1"},
        "status": {"outcome": "family_bound_derivation_consistent"},
        "summary": {"all_bounds_consistent": True, "audit_count": 1},
        "audits": [
            {
                "anchor_idx": 119,
                "target_power_family": "family_009",
                "bounds_consistent": True,
                "derivation": {
                    "family_size": 612,
                    "blocked_family_pose_count": 86,
                    "global_upper_bound": 612,
                    "derived_conditioned_upper_bound": 526,
                    "domain_conditioned_upper_bound": 526,
                },
                "proto_constraint": {
                    "implied_conditioned_upper_bound": 526,
                },
            }
        ],
    }


def _semantic_audit_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_semantic_audit_v1"},
        "classification": "solver_sensitivity_without_bound_violation",
        "family_bound": {
            "target_power_family": "family_009",
            "derived_conditioned_upper_bound": 526,
        },
        "target_family_slice": {
            "relaxed_power_family_count_value": 0,
            "relaxed_family_bound_violation": -526,
        },
        "findings": [
            "target_bound_is_solver_sensitivity_not_semantic_violation"
        ],
        "recommendation": "Solver sensitivity.",
    }


def _solver_profile_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_solver_profile_v1"},
        "classification": "bound_present_unknown_bound_absent_terminal_without_violation",
        "comparison": {
            "base_status": "UNKNOWN",
            "relaxed_status": "OPTIMAL",
            "wall_time_speedup": 200.0,
            "deterministic_time_speedup": 500.0,
            "base_branches": 0,
            "base_conflicts": 0,
            "relaxed_family_bound_violation": -526,
        },
        "recommendation": "Presolve sensitivity.",
    }


def _parameter_probe_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_parameter_probe_v1"},
        "status": {"outcome": "parameter_probe_unknown_remaining"},
        "probe": {
            "status_counts": {"UNKNOWN": 5},
            "best_terminal_entry": None,
            "unknown_diagnostics": {
                "unknown_count": 5,
                "zero_branch_unknown_count": 5,
                "zero_branch_unknown_profiles": ["portfolio_p3_s3_w4"],
            },
        },
    }


def _family_lookup_search_probe_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_lookup_search_probe_v1"},
        "status": {"outcome": "search_probe_zero_branch_unknown_remaining"},
        "probe": {
            "status_counts": {"UNKNOWN": 15},
            "best_terminal_entry": None,
            "unknown_diagnostics": {
                "unknown_count": 15,
                "zero_branch_unknown_count": 15,
                "search_progress_unknown_count": 0,
                "zero_branch_unknown_by_variant": {
                    "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only": 5
                },
                "zero_branch_unknown_by_profile": {
                    "portfolio_probe3_sym3_4w": 3
                },
            },
        },
    }


def _family_lookup_assumption_probe_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_lookup_assumption_probe_v1"},
        "status": {"outcome": "assumption_probe_zero_branch_unknown_remaining"},
        "profile": {"assumption_count": 4},
        "probe": {
            "status_counts": {"UNKNOWN": 8},
            "best_terminal_entry": None,
            "unknown_diagnostics": {
                "unknown_count": 8,
                "zero_branch_unknown_count": 8,
                "search_progress_unknown_count": 0,
                "zero_branch_unknown_by_assumption": {
                    "slot_a:family_000": 2
                },
                "zero_branch_unknown_by_variant": {
                    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only": 4
                },
            },
        },
    }


def _family_lookup_semantic_repro_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_lookup_semantic_repro_v1"},
        "status": {"outcome": "semantic_repro_terminal_without_zero_branch"},
        "extraction": {
            "selected_slot_count": 3,
            "selected_family_ids": [0, 1, 10],
        },
        "repro": {
            "status_counts": {"OPTIMAL": 8},
            "best_terminal_entry": {"variant": "coverage_only", "status": "OPTIMAL"},
            "unknown_diagnostics": {
                "unknown_count": 0,
                "zero_branch_unknown_count": 0,
            },
        },
    }


def _forced_anchor_proto_reduction_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_proto_reduction_v1"},
        "status": {"outcome": "proto_reduction_search_progress_without_terminal"},
        "reduction": {
            "status_counts": {"UNKNOWN": 2},
            "best_terminal_entry": None,
            "unlocking_variants": [],
            "unknown_diagnostics": {
                "unknown_count": 8,
                "zero_branch_unknown_count": 7,
                "search_progress_unknown_count": 1,
                "zero_branch_unknown_by_variant": {
                    "base": 1,
                    "remove_power_coverage_element_active_and_family_lookup_table": 1,
                    "remove_power_coverage_element_x_and_family_lookup_table": 1,
                    "remove_power_coverage_element_y_and_family_lookup_table": 1,
                    "remove_power_coverage_element_xy_and_family_lookup_table": 1,
                    "remove_power_coverage_element_active_x_and_family_lookup_table": 1,
                    "remove_power_coverage_element_active_y_and_family_lookup_table": 1,
                    "remove_power_coverage_elements_and_family_lookup_table_first_512": 1,
                    "remove_power_coverage_elements_and_family_lookup_table_first_640": 1,
                    "remove_power_coverage_elements_and_family_lookup_table_first_700": 1,
                    "remove_power_coverage_elements_and_family_lookup_table_last_512": 1,
                },
                "search_progress_unknown_samples": [
                    {
                        "variant": "remove_power_coverage_elements_and_family_lookup_table",
                        "branches": 25299,
                        "conflicts": 27,
                        "wall_time": 20.0,
                    }
                ],
            },
        },
    }


def _standardized_delta_proto_reduction_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_proto_reduction_v1"},
        "status": {"outcome": "proto_reduction_terminal_found"},
        "reduction": {
            "entries": [
                {
                    "anchor_idx": 118,
                    "variant": "base",
                    "status": "INFEASIBLE",
                    "branches": 4853709,
                    "conflicts": 831,
                    "solver_parameter_profile": {
                        "profile_id": "block64_all_templates_geometry_final_target_interval_delta_low_encoding_linearization0_fixed_1w"
                    },
                },
                {
                    "anchor_idx": 125,
                    "variant": "base",
                    "status": "UNKNOWN",
                    "branches": 4899620,
                    "conflicts": 9096,
                    "solver_parameter_profile": {
                        "profile_id": "block64_all_templates_geometry_final_target_interval_delta_low_encoding_linearization0_fixed_1w"
                    },
                },
            ],
            "status_counts": {"INFEASIBLE": 1, "UNKNOWN": 1},
            "best_terminal_entry": {"anchor_idx": 118, "variant": "base", "status": "INFEASIBLE"},
            "unlocking_variants": [],
            "unknown_diagnostics": {
                "unknown_count": 1,
                "zero_branch_unknown_count": 0,
                "search_progress_unknown_count": 1,
                "zero_branch_unknown_by_variant": {},
                "search_progress_unknown_samples": [
                    {"variant": "base", "branches": 4899620, "conflicts": 9096}
                ],
            },
        },
    }


def _formulation_probe_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_formulation_probe_v1"},
        "classification": "target_direct_terminal_enforced_unknown_all_family_direct_infeasible",
        "comparison": {
            "base_status": "UNKNOWN",
            "direct_status": "OPTIMAL",
            "enforced_status": "UNKNOWN",
            "wall_time_speedup": 200.0,
            "direct_bound_value": 526,
            "direct_count_value": 0,
        },
        "recommendation": "Direct bound replacement works.",
    }


def _witness_audit_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_coverage_witness_audit_v1"},
        "classification": "geometric_power_coverage_witness_primary_blocker",
        "witness_encoding": {
            "encoding": "geometric_element_witness_v1",
            "powered_slots": 763,
            "pole_slots": 763,
            "witness_indices": 763,
            "element_constraints": 2289,
            "element_constraints_per_powered_slot": 3.0,
            "cover_choice_vars_complete": True,
        },
        "domain_pressure": {
            "core_blocker_classification": (
                "power_coverage_core_primary_protocol_lower_bound_not_primary"
            ),
            "no_protocol_lower_bound_core_status": "UNKNOWN",
        },
        "recommendation": "Isolate witness-domain feasibility.",
    }


def _witness_domain_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_coverage_witness_domain_v1"},
        "status": {"outcome": "witness_domain_static_support_pass"},
        "summary": {
            "anchor_count": 1,
            "required_unsupported_slot_count": 0,
            "optional_unsupported_slot_count": 0,
            "classification_counts": {"witness_domain_static_support_pass": 1},
        },
        "recommendation": "Static witness support is present.",
    }


def _family_lookup_audit_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_lookup_assignment_audit_v1"},
        "status": {"outcome": "shell_lookup_survivor_rows_consistent"},
        "family_lookup_encoding": {
            "use_shell_lookup": True,
            "shell_lookup_row_count": 630,
            "shell_lookup_family_count": 35,
            "family_variable_count": 763,
            "family_variable_domain": [0, 35],
            "family_constraint_kind_counts": {"table": 763, "linear": 56459},
        },
        "summary": {
            "surviving_pose_count": 3809,
            "missing_lookup_row_count": 0,
        },
        "recommendation": "Survivor rows are consistent.",
    }


def _capacity_gvi_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_capacity_gvi_audit_v1"},
        "classification": "power_capacity_gvi_full_skip_primary_suspect",
        "power_capacity_gvi": {
            "lower_bound_count": 4,
            "aggregated_nonzero_terms": 140,
            "raw_nonzero_terms": 19044,
            "family_count": 35,
            "lower_bounds": [
                {
                    "template": "manufacturing_3x3",
                    "demand": 132,
                    "nonzero_poles": 4761,
                }
            ],
        },
        "recommendation": "Isolate power-capacity lower bounds.",
    }


def test_power_protocol_interaction_identifies_conditioned_family_protocol_hypothesis(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(
        slice_dir / "slice_core.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_core_required_for_blocker",
                "anchor_119:protocol_lower_bound_not_primary",
                "anchor_119:skip_power_coverage_unlocks_feasible_core",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
    )

    assert report["metadata"]["source"] == "phase3b_power_protocol_interaction_diagnostic_v1"
    assert report["candidate"]["key"] == "67x13"
    assert report["analysis"]["primary_hypothesis"] == (
        "conditioned_power_family_bounds_interact_with_protocol_residuals"
    )
    assert report["analysis"]["next_probe_family"] == "family_009"
    assert report["analysis"]["next_probe_template"] == "protocol_storage_box"
    assert "power_pole_candidate_domain_stable" in report["findings"]
    assert "protocol_domain_tightening_not_lower_bound_primary" in report["findings"]
    assert "ghost_conditioned_power_family_bounds_present" in report["findings"]
    assert _check_status(report, "power_coverage_slice_unlocks_core") == "pass"

    markdown = render_phase3b_power_protocol_interaction_markdown(report)
    text = render_phase3b_power_protocol_interaction_text(report)
    assert "Power/Protocol Interaction" in markdown
    assert "family_009" in markdown
    assert "primary_hypothesis=conditioned_power_family_bounds" in text


def test_power_protocol_interaction_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    proto_reduction_path = project_root / "proto_reduction.json"
    slice_dir = project_root / "slices"
    output_dir = tmp_path / "out"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(proto_reduction_path, _forced_anchor_proto_reduction_payload())
    _write_json(
        slice_dir / "slice_core.json",
        _model_slice_payload(["anchor_119:skip_power_coverage_unlocks_feasible_core"]),
    )
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_power_protocol_interaction.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--power-coverage-anchor-delta",
            str(power_delta_path),
            "--residual-optional-encoding",
            str(residual_path),
            "--zero-branch-unknown-triage",
            str(zero_branch_path),
            "--model-slice-dir",
            str(slice_dir),
            "--forced-anchor-proto-reduction",
            str(proto_reduction_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b power/protocol interaction diagnostic" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--power-coverage-anchor-delta",
            str(power_delta_path),
            "--residual-optional-encoding",
            str(residual_path),
            "--zero-branch-unknown-triage",
            str(zero_branch_path),
            "--model-slice-dir",
            str(slice_dir),
            "--forced-anchor-proto-reduction",
            str(proto_reduction_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "power_protocol_interaction_json=" in write.stdout
    payload = json.loads(
        (output_dir / "power_protocol_interaction.json").read_text(encoding="utf-8")
    )
    assert payload["analysis"]["next_probe_family"] == "family_009"
    assert payload["forced_anchor_proto_reduction"]["present"] is True
    assert (output_dir / "power_protocol_interaction.md").exists()
    assert (output_dir / "power_protocol_interaction.txt").exists()


def test_power_protocol_interaction_prioritizes_target_family_relaxation(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(
        slice_dir / "target_family.json",
        _model_slice_payload(
            [
                "anchor_119:target_power_family_bound_relaxation_unlocks_feasible_core",
                "anchor_119:target_power_family_relaxed_protocol_boxes_unlock_feasible_core",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "target_conditioned_power_family_bound_is_consistent_active_blocker"
    )
    assert "target_power_family_bound_relaxation_unlocks_feasible_slice" in report[
        "findings"
    ]
    assert "active_blocker_bound_is_consistently_derived" in report["findings"]
    assert (
        _check_status(report, "target_power_family_bound_relaxation_unlocks_core")
        == "pass"
    )
    assert _check_status(report, "family_bound_audit_consistent") == "pass"
    assert "internally consistent" in report["recommendation"]


def test_power_protocol_interaction_prioritizes_semantic_solver_sensitivity(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, _semantic_audit_payload())
    _write_json(
        slice_dir / "target_family.json",
        _model_slice_payload(
            ["anchor_119:target_power_family_bound_relaxation_unlocks_feasible_core"]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "target_conditioned_power_family_bound_solver_sensitivity"
    )
    assert "target_bound_solver_sensitivity_without_semantic_violation" in report[
        "findings"
    ]
    assert _check_status(report, "family_bound_semantic_audit_present") == "pass"
    assert "solver/presolve sensitivity" in report["recommendation"]


def test_power_protocol_interaction_prioritizes_solver_profile(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    solver_profile_path = project_root / "solver_profile.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, _semantic_audit_payload())
    _write_json(solver_profile_path, _solver_profile_payload())
    _write_json(
        slice_dir / "target_family.json",
        _model_slice_payload(
            ["anchor_119:target_power_family_bound_relaxation_unlocks_feasible_core"]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
        family_bound_solver_profile_path=solver_profile_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "target_conditioned_power_family_bound_presolve_search_sensitivity"
    )
    assert "bound_present_unknown_absent_terminal_without_violation" in report[
        "findings"
    ]
    assert _check_status(report, "family_bound_solver_profile_present") == "pass"
    assert "confirmed presolve/search sensitivity" in report["recommendation"]


def test_power_protocol_interaction_prioritizes_parameter_probe_failure(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    solver_profile_path = project_root / "solver_profile.json"
    parameter_probe_path = project_root / "parameter_probe.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, _semantic_audit_payload())
    _write_json(solver_profile_path, _solver_profile_payload())
    _write_json(parameter_probe_path, _parameter_probe_payload())
    _write_json(
        slice_dir / "target_family.json",
        _model_slice_payload(
            ["anchor_119:target_power_family_bound_relaxation_unlocks_feasible_core"]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
        family_bound_solver_profile_path=solver_profile_path,
        family_bound_parameter_probe_path=parameter_probe_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "target_conditioned_power_family_bound_formulation_sensitivity"
    )
    assert "bound_present_parameter_probe_all_zero_branch_unknown" in report["findings"]
    assert _check_status(report, "family_bound_parameter_probe_present") == "pass"
    assert "formulation-level solver sensitivity" in report["recommendation"]


def test_power_protocol_interaction_blocks_stale_target_family_slice(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    solver_profile_path = project_root / "solver_profile.json"
    parameter_probe_path = project_root / "parameter_probe.json"
    formulation_probe_path = project_root / "formulation_probe.json"
    slice_dir = project_root / "slices"
    semantic_payload = _semantic_audit_payload()
    semantic_payload["classification"] = "relaxation_not_terminal_feasible"
    semantic_payload["findings"] = []
    semantic_payload["target_family_slice"]["relaxed_power_family_count_value"] = None
    semantic_payload["target_family_slice"]["relaxed_family_bound_violation"] = None
    solver_payload = _solver_profile_payload()
    solver_payload["classification"] = "solver_profile_inconclusive"
    solver_payload["comparison"]["relaxed_status"] = "INFEASIBLE"
    solver_payload["comparison"]["relaxed_family_bound_violation"] = None
    formulation_payload = _formulation_probe_payload()
    formulation_payload["classification"] = "formulation_probe_inconclusive"
    formulation_payload["comparison"]["direct_status"] = "INFEASIBLE"
    formulation_payload["comparison"]["direct_count_value"] = None
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, semantic_payload)
    _write_json(solver_profile_path, solver_payload)
    _write_json(parameter_probe_path, _parameter_probe_payload())
    _write_json(formulation_probe_path, formulation_payload)
    _write_json(slice_dir / "target_family.json", _model_slice_payload([]))

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
        family_bound_solver_profile_path=solver_profile_path,
        family_bound_parameter_probe_path=parameter_probe_path,
        family_bound_formulation_probe_path=formulation_probe_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "target_family_bound_slice_inconclusive_or_stale"
    )
    assert "target_family_relaxation_not_terminal_feasible" in report["findings"]
    assert "target_direct_bound_injection_infeasible" in report["findings"]
    assert "stale" in report["recommendation"]
    assert "keep_anchor_specialized_injection_blocked" in report["analysis"]["next_actions"]


def test_power_protocol_interaction_prioritizes_power_coverage_when_family_injection_blocked(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    solver_profile_path = project_root / "solver_profile.json"
    parameter_probe_path = project_root / "parameter_probe.json"
    formulation_probe_path = project_root / "formulation_probe.json"
    slice_dir = project_root / "slices"
    semantic_payload = _semantic_audit_payload()
    semantic_payload["classification"] = "relaxation_not_terminal_feasible"
    semantic_payload["findings"] = []
    semantic_payload["target_family_slice"]["relaxed_power_family_count_value"] = None
    semantic_payload["target_family_slice"]["relaxed_family_bound_violation"] = None
    solver_payload = _solver_profile_payload()
    solver_payload["classification"] = "solver_profile_inconclusive"
    solver_payload["comparison"]["relaxed_status"] = "INFEASIBLE"
    solver_payload["comparison"]["relaxed_family_bound_violation"] = None
    formulation_payload = _formulation_probe_payload()
    formulation_payload["classification"] = "direct_bound_replacement_infeasible"
    formulation_payload["comparison"]["direct_status"] = "INFEASIBLE"
    formulation_payload["comparison"]["direct_count_value"] = None
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, semantic_payload)
    _write_json(solver_profile_path, solver_payload)
    _write_json(parameter_probe_path, _parameter_probe_payload())
    _write_json(formulation_probe_path, formulation_payload)
    _write_json(
        slice_dir / "core.json",
        _model_slice_payload(["anchor_119:skip_power_coverage_unlocks_feasible_core"]),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
        family_bound_solver_profile_path=solver_profile_path,
        family_bound_parameter_probe_path=parameter_probe_path,
        family_bound_formulation_probe_path=formulation_probe_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_core_primary_family_bound_injection_blocked"
    )
    assert "skip_power_coverage_unlocks_feasible_slice" in report["findings"]
    assert "focus the next diagnostic on the geometric power-coverage core" in report[
        "recommendation"
    ]
    assert "keep_family_bound_injection_blocked" in report["analysis"]["next_actions"]


def test_power_protocol_interaction_prioritizes_witness_audit(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    solver_profile_path = project_root / "solver_profile.json"
    parameter_probe_path = project_root / "parameter_probe.json"
    formulation_probe_path = project_root / "formulation_probe.json"
    witness_audit_path = project_root / "witness_audit.json"
    slice_dir = project_root / "slices"
    semantic_payload = _semantic_audit_payload()
    semantic_payload["classification"] = "relaxation_not_terminal_feasible"
    semantic_payload["findings"] = []
    semantic_payload["target_family_slice"]["relaxed_power_family_count_value"] = None
    semantic_payload["target_family_slice"]["relaxed_family_bound_violation"] = None
    solver_payload = _solver_profile_payload()
    solver_payload["classification"] = "solver_profile_inconclusive"
    solver_payload["comparison"]["relaxed_status"] = "INFEASIBLE"
    solver_payload["comparison"]["relaxed_family_bound_violation"] = None
    formulation_payload = _formulation_probe_payload()
    formulation_payload["classification"] = "direct_bound_replacement_infeasible"
    formulation_payload["comparison"]["direct_status"] = "INFEASIBLE"
    formulation_payload["comparison"]["direct_count_value"] = None
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, semantic_payload)
    _write_json(solver_profile_path, solver_payload)
    _write_json(parameter_probe_path, _parameter_probe_payload())
    _write_json(formulation_probe_path, formulation_payload)
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(
        slice_dir / "core.json",
        _model_slice_payload(["anchor_119:skip_power_coverage_unlocks_feasible_core"]),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
        family_bound_solver_profile_path=solver_profile_path,
        family_bound_parameter_probe_path=parameter_probe_path,
        family_bound_formulation_probe_path=formulation_probe_path,
        power_coverage_witness_audit_path=witness_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "geometric_power_coverage_witness_primary_blocker"
    )
    assert "geometric_power_coverage_witness_primary_blocker" in report["findings"]
    assert _check_status(report, "power_coverage_witness_audit_present") == "pass"
    assert "isolate anchor119 witness-domain feasibility" in report["recommendation"]
    assert "build_minimal_witness_domain_repro" in report["analysis"]["next_actions"]


def test_power_protocol_interaction_uses_witness_domain_probe(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(
        slice_dir / "core.json",
        _model_slice_payload(["anchor_119:skip_power_coverage_unlocks_feasible_core"]),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_dynamic_coupling_blocker"
    )
    assert "power_coverage_static_witness_domain_support_pass" in report["findings"]
    assert _check_status(report, "power_coverage_witness_domain_present") == "pass"
    assert "not a simple empty cover-choice domain" in report["recommendation"]
    assert "build_power_coverage_dynamic_coupling_slice" in report["analysis"]["next_actions"]


def test_power_protocol_interaction_prioritizes_family_assignment_coupling(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(
        slice_dir / "dynamic_family.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_coupling_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_family_assignment_and_gvi_relaxation_unlocks_core",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_assignment_coupling_blocker"
    )
    assert "power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core" in report[
        "findings"
    ]
    assert "GVI lower-bound relaxation does not add a distinct unlock" in report[
        "recommendation"
    ]
    assert "split_power_family_assignment_from_count_constraints_under_dynamic_coverage" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_prioritizes_family_assignment_lookup_coupling(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(
        slice_dir / "dynamic_family_sublayers.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_coupling_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_count_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_membership_count_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_assignment_relaxation_unlocks_core",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_assignment_lookup_coupling_blocker"
    )
    assert "aggregate count or membership totals alone" in report["recommendation"]
    assert "split_family_lookup_table_from_shell_distance_constraints" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_prioritizes_family_lookup_coupling(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(
        slice_dir / "dynamic_family_lookup_distance.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_coupling_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_distance_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_distance_relaxation_unlocks_core",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_coupling_blocker"
    )
    assert "distance bounds alone are not the minimal unlock" in report[
        "recommendation"
    ]
    assert "audit_family__assignment_table_rows_under_anchor119" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_uses_family_lookup_audit(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(
        slice_dir / "dynamic_family_lookup_distance.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_coupling_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_distance_relaxation_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_domain_strength_coupling_blocker"
    )
    assert "family_lookup_survivor_rows_consistent" in report["findings"]
    assert _check_status(report, "family_lookup_assignment_audit_present") == "pass"
    assert "not a missing family__ table row" in report["recommendation"]
    assert "profile_family_lookup_table_propagation_under_dynamic_coverage" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_uses_channeling_negative_result(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(
        slice_dir / "lookup_and_channeling.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_distance_relaxation_still_unknown",
                "anchor_119:family_active_domain_channeling_still_unknown",
                "anchor_119:family_membership_active_channeling_still_unknown",
                "anchor_119:family_active_and_membership_channeling_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_table_propagation_blocker"
    )
    assert "family_active_and_membership_channeling_still_unknown" in report[
        "findings"
    ]
    assert "table propagation structure itself" in report["recommendation"]
    assert "test_split_shell_lookup_table_into_implication_channeling" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_prioritizes_table_linear_combination(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(
        slice_dir / "table_linear.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_table_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_table_linear_combination_blocker"
    )
    assert "both table and linear lookup/channeling constraints" in report[
        "recommendation"
    ]
    assert "split_family_linear_constraints_by_sentinel_membership_ordering" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_prioritizes_full_table_linear_combination(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(
        slice_dir / "linear_categories.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_table_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_table_full_linear_combination_blocker"
    )
    assert "full table-linear propagation combination" in report["recommendation"]
    assert "replace_shell_lookup_table_with_explicit_implication_channeling_in_diagnostic" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_uses_shell_pair_channeling_negative_result(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(
        slice_dir / "shell_pair_tables.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_table_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_shell_pair_tables_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_table_linear_combo_not_redundant_channeling"
    )
    assert "missing redundant family->shell channel" in report["recommendation"]
    assert "test_alternative_exact_family_lookup_encoding_without_original_table" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_uses_lookup_rebuild_negative_result(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(
        slice_dir / "lookup_rebuild.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_table_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_sentinel_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_membership_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_ordering_linear_relaxation_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_shell_pair_tables_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_semantic_combo_rebuild_still_blocked"
    )
    assert "semantic combination" in report["recommendation"]
    assert "split_rebuilt_family_lookup_semantics_by_membership_shell_ordering" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_uses_lookup_rebuild_component_split(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(
        slice_dir / "lookup_rebuild_components.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_membership_shell_pair_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_membership_ordering_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_ordering_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_rebuilt_components_all_zero_branch_blocked"
    )
    assert "isolated family lookup semantics" in report["recommendation"]
    assert (
        "profile_assumption_splitting_on_membership_shell_ordering_variables"
        in report["analysis"]["next_actions"]
    )


def test_power_protocol_interaction_uses_family_lookup_search_probe_zero_branch(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    search_probe_path = project_root / "search_probe.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(search_probe_path, _family_lookup_search_probe_payload())
    _write_json(
        slice_dir / "lookup_rebuild_components.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
        family_lookup_search_probe_path=search_probe_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_search_parameter_insensitive_zero_branch"
    )
    assert "search modes" in report["recommendation"]
    assert _check_status(report, "family_lookup_search_probe_present") == "pass"
    assert "implement_diagnostic_assumption_split_on_family_lookup_literals" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_uses_family_lookup_assumption_probe_zero_branch(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    search_probe_path = project_root / "search_probe.json"
    assumption_probe_path = project_root / "assumption_probe.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(search_probe_path, _family_lookup_search_probe_payload())
    _write_json(assumption_probe_path, _family_lookup_assumption_probe_payload())
    _write_json(
        slice_dir / "lookup_rebuild_components.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
        family_lookup_search_probe_path=search_probe_path,
        family_lookup_assumption_probe_path=assumption_probe_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_assumption_split_still_zero_branch"
    )
    assert "smaller semantic reproduction" in report["recommendation"]
    assert _check_status(report, "family_lookup_assumption_probe_present") == "pass"
    assert "extract_minimal_active_coverage_family_lookup_repro" in report["analysis"][
        "next_actions"
    ]


def test_power_protocol_interaction_uses_terminal_semantic_repro_to_request_proto_reduction(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    search_probe_path = project_root / "search_probe.json"
    assumption_probe_path = project_root / "assumption_probe.json"
    semantic_repro_path = project_root / "semantic_repro.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(search_probe_path, _family_lookup_search_probe_payload())
    _write_json(assumption_probe_path, _family_lookup_assumption_probe_payload())
    _write_json(semantic_repro_path, _family_lookup_semantic_repro_payload())
    _write_json(
        slice_dir / "lookup_rebuild_components.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
        family_lookup_search_probe_path=search_probe_path,
        family_lookup_assumption_probe_path=assumption_probe_path,
        family_lookup_semantic_repro_path=semantic_repro_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_family_lookup_micro_semantics_terminal_proto_reduction_needed"
    )
    assert "actual forced-anchor proto" in report["recommendation"]
    assert _check_status(report, "family_lookup_semantic_repro_present") == "pass"
    assert "reduce_actual_forced_anchor_proto_by_constraint_family" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_uses_proto_reduction_progress(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    witness_audit_path = project_root / "witness_audit.json"
    witness_domain_path = project_root / "witness_domain.json"
    lookup_audit_path = project_root / "lookup_audit.json"
    search_probe_path = project_root / "search_probe.json"
    assumption_probe_path = project_root / "assumption_probe.json"
    semantic_repro_path = project_root / "semantic_repro.json"
    proto_reduction_path = project_root / "proto_reduction.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(witness_domain_path, _witness_domain_payload())
    _write_json(lookup_audit_path, _family_lookup_audit_payload())
    _write_json(search_probe_path, _family_lookup_search_probe_payload())
    _write_json(assumption_probe_path, _family_lookup_assumption_probe_payload())
    _write_json(semantic_repro_path, _family_lookup_semantic_repro_payload())
    _write_json(proto_reduction_path, _forced_anchor_proto_reduction_payload())
    _write_json(
        slice_dir / "lookup_rebuild_components.json",
        _model_slice_payload(
            [
                "anchor_119:power_coverage_dynamic_and_family_lookup_relaxation_unlocks_core",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_channeling_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_membership_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only_still_unknown",
                "anchor_119:power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only_still_unknown",
            ]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        power_coverage_witness_audit_path=witness_audit_path,
        power_coverage_witness_domain_path=witness_domain_path,
        family_lookup_assignment_audit_path=lookup_audit_path,
        family_lookup_search_probe_path=search_probe_path,
        family_lookup_assumption_probe_path=assumption_probe_path,
        family_lookup_semantic_repro_path=semantic_repro_path,
        forced_anchor_proto_reduction_path=proto_reduction_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_coverage_elements_full_family_lookup_table_required_progress_blocker"
    )
    assert "all 763" in report["recommendation"]
    assert "test_sparse_family_lookup_table_removal_patterns" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_marks_standardized_delta_split(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    proto_reduction_path = project_root / "proto_reduction.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(proto_reduction_path, _standardized_delta_proto_reduction_payload())
    _write_json(
        slice_dir / "core.json",
        _model_slice_payload(["anchor_119:skip_power_coverage_unlocks_feasible_core"]),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        forced_anchor_proto_reduction_path=proto_reduction_path,
    )

    assert "standardized_delta_interval_terminal_progress_split" in report["findings"]
    assert report["forced_anchor_proto_reduction"]["profile_ids"] == [
        "block64_all_templates_geometry_final_target_interval_delta_low_encoding_linearization0_fixed_1w"
    ]


def test_power_protocol_interaction_prioritizes_power_capacity_gvi_audit(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    solver_profile_path = project_root / "solver_profile.json"
    parameter_probe_path = project_root / "parameter_probe.json"
    formulation_probe_path = project_root / "formulation_probe.json"
    witness_audit_path = project_root / "witness_audit.json"
    capacity_gvi_path = project_root / "capacity_gvi.json"
    slice_dir = project_root / "slices"
    semantic_payload = _semantic_audit_payload()
    semantic_payload["classification"] = "relaxation_not_terminal_feasible"
    semantic_payload["findings"] = []
    semantic_payload["target_family_slice"]["relaxed_power_family_count_value"] = None
    semantic_payload["target_family_slice"]["relaxed_family_bound_violation"] = None
    solver_payload = _solver_profile_payload()
    solver_payload["classification"] = "solver_profile_inconclusive"
    solver_payload["comparison"]["relaxed_status"] = "INFEASIBLE"
    solver_payload["comparison"]["relaxed_family_bound_violation"] = None
    formulation_payload = _formulation_probe_payload()
    formulation_payload["classification"] = "direct_bound_replacement_infeasible"
    formulation_payload["comparison"]["direct_status"] = "INFEASIBLE"
    formulation_payload["comparison"]["direct_count_value"] = None
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, semantic_payload)
    _write_json(solver_profile_path, solver_payload)
    _write_json(parameter_probe_path, _parameter_probe_payload())
    _write_json(formulation_probe_path, formulation_payload)
    _write_json(witness_audit_path, _witness_audit_payload())
    _write_json(capacity_gvi_path, _capacity_gvi_payload())
    _write_json(
        slice_dir / "core.json",
        _model_slice_payload(["anchor_119:skip_power_coverage_unlocks_feasible_core"]),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
        family_bound_solver_profile_path=solver_profile_path,
        family_bound_parameter_probe_path=parameter_probe_path,
        family_bound_formulation_probe_path=formulation_probe_path,
        power_coverage_witness_audit_path=witness_audit_path,
        power_capacity_gvi_audit_path=capacity_gvi_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "power_capacity_gvi_full_skip_primary_suspect"
    )
    assert "power_capacity_gvi_full_skip_primary_suspect" in report["findings"]
    assert _check_status(report, "power_capacity_gvi_audit_present") == "pass"
    assert "four template lower bounds" in report["recommendation"]
    assert "add_template_specific_power_capacity_gvi_relax_slices" in report[
        "analysis"
    ]["next_actions"]


def test_power_protocol_interaction_prioritizes_formulation_probe(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    power_delta_path = project_root / "power_delta.json"
    residual_path = project_root / "residual.json"
    zero_branch_path = project_root / "zero.json"
    family_audit_path = project_root / "family_audit.json"
    semantic_audit_path = project_root / "semantic_audit.json"
    solver_profile_path = project_root / "solver_profile.json"
    parameter_probe_path = project_root / "parameter_probe.json"
    formulation_probe_path = project_root / "formulation_probe.json"
    slice_dir = project_root / "slices"
    _write_json(power_delta_path, _power_delta_payload())
    _write_json(residual_path, _residual_payload())
    _write_json(zero_branch_path, _zero_branch_payload())
    _write_json(family_audit_path, _family_audit_payload())
    _write_json(semantic_audit_path, _semantic_audit_payload())
    _write_json(solver_profile_path, _solver_profile_payload())
    _write_json(parameter_probe_path, _parameter_probe_payload())
    _write_json(formulation_probe_path, _formulation_probe_payload())
    _write_json(
        slice_dir / "target_family.json",
        _model_slice_payload(
            ["anchor_119:target_power_family_bound_relaxation_unlocks_feasible_core"]
        ),
    )

    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=power_delta_path,
        residual_optional_encoding_path=residual_path,
        zero_branch_unknown_triage_path=zero_branch_path,
        model_slice_dir=slice_dir,
        family_bound_audit_path=family_audit_path,
        family_bound_semantic_audit_path=semantic_audit_path,
        family_bound_solver_profile_path=solver_profile_path,
        family_bound_parameter_probe_path=parameter_probe_path,
        family_bound_formulation_probe_path=formulation_probe_path,
    )

    assert report["analysis"]["primary_hypothesis"] == (
        "target_family_only_direct_bound_injection_candidate"
    )
    assert "target_direct_terminal_all_family_direct_infeasible" in report[
        "findings"
    ]
    assert _check_status(report, "family_bound_formulation_probe_present") == "pass"
    assert "broad substitution is explicitly not validated" in report["recommendation"]


def _check_status(report: dict, check_id: str) -> str:
    for check in report["checks"]:
        if check["check_id"] == check_id:
            return str(check["status"])
    raise AssertionError(f"missing check {check_id}")
