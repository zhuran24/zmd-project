from __future__ import annotations

from pathlib import Path

from src.search.phase3b_cover_choice_profile_comparison import (
    COVER_CHOICE_PROFILE_COMPARISON_SOURCE,
    _comparison_payload,
    _final_target_channel_assessment,
    build_phase3b_cover_choice_profile_comparison,
    render_phase3b_cover_choice_profile_comparison_markdown,
    render_phase3b_cover_choice_profile_comparison_text,
)


def _case(
    case_id: str,
    *,
    proto_vars: int,
    elements: int,
    cover_vars: int,
    wide_idx: int,
    wide_target: int,
    block_idx: int,
    local_idx: int,
    block_target: int,
    final_targets: int,
    block_selected: int = 0,
    local_selected: int = 0,
    bool_or: int = 0,
) -> dict:
    cover_profile = {
        "total_cover_choice_variables": cover_vars,
        "mode_counts": {
            "wide_idx": wide_idx,
            "wide_target": wide_target,
            "block_idx": block_idx,
            "block_local_idx": local_idx,
            "block_local_selected": local_selected,
            "block_target": block_target,
            "block_selected": block_selected,
        },
        "role_counts": {
            "wide_selector": wide_idx,
            "final_target_channel": final_targets,
            "block_selector": block_idx,
            "local_selector": local_idx,
            "local_selected_literal": local_selected,
            "block_intermediate_target_channel": block_target,
            "block_selected_literal": block_selected,
        },
        "target_channel_profile": {
            "final_target_channel_variables": final_targets,
            "block_intermediate_target_channel_variables": block_target,
            "wide_selector_variables": wide_idx,
            "block_selector_variables": block_idx,
            "local_selector_variables": local_idx,
            "local_selected_literal_variables": local_selected,
            "block_selected_literal_variables": block_selected,
        },
        "template_counts": {"protocol_storage_box": {"wide_target": wide_target}},
    }
    return {
        "case_id": case_id,
        "solver_invoked": False,
        "proto_variable_count": proto_vars,
        "element_count": elements,
        "proto_profile": {
            "variable_count": proto_vars,
            "constraint_kind_counts": {"element": elements, "bool_or": bool_or},
            "cover_choice_profile": cover_profile,
        },
        "cover_choice_profile": cover_profile,
        "target_channel_profile": cover_profile["target_channel_profile"],
    }


def test_cover_choice_profile_comparison_payload_and_renderers() -> None:
    cases = [
        _case(
            "protocol_storage_box_only",
            proto_vars=78028,
            elements=21873,
            cover_vars=23180,
            wide_idx=219,
            wide_target=2289,
            block_idx=544,
            local_idx=544,
            block_target=19584,
            final_targets=2289,
        ),
        _case(
            "all_powered_templates",
            proto_vars=86131,
            elements=29757,
            cover_vars=31283,
            wide_idx=0,
            wide_target=2289,
            block_idx=763,
            local_idx=763,
            block_target=27468,
            final_targets=2289,
        ),
    ]
    report = {
        "metadata": {
            "source": COVER_CHOICE_PROFILE_COMPARISON_SOURCE,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "solver_invoked": False,
        "status": {
            "outcome": "no_solve_profile_comparison_built",
            "recommendation": "compare only",
        },
        "cases": cases,
        "comparison": _comparison_payload(cases),
        "final_target_channel_assessment": _final_target_channel_assessment(cases),
        "checks": [
            {
                "check_id": "no_solve_analysis",
                "status": "pass",
                "detail": "solver_invoked=false",
            }
        ],
    }

    comparison = report["comparison"]
    assert comparison["proto_variable_delta_all_templates_minus_protocol_only"] == 8103
    assert comparison["element_delta_all_templates_minus_protocol_only"] == 7884
    assert comparison["wide_idx_delta_all_templates_minus_protocol_only"] == -219
    assert comparison["final_target_delta_all_templates_minus_protocol_only"] == 0

    assessment = report["final_target_channel_assessment"]
    assert assessment["safe_patch_available"] is False
    assert assessment["diagnostic_deletion_rejected"] is True
    assert assessment["verdict"] == "no_safe_default_off_compact_encoding_identified"

    markdown = render_phase3b_cover_choice_profile_comparison_markdown(report)
    text = render_phase3b_cover_choice_profile_comparison_text(report)
    assert "solver_invoked: False" in markdown
    assert "Final Target Channel Assessment" in markdown
    assert "mode_counts" in markdown
    assert "role_counts" in markdown
    assert "target_channel_profile" in markdown
    assert "template_counts" in markdown
    assert "solver_invoked=False" in text
    assert "final_target=2289" in text
    assert "template_counts" in text


def test_cover_choice_profile_comparison_detects_selected_block_candidate() -> None:
    cases = [
        _case(
            "all_powered_templates",
            proto_vars=86131,
            elements=29757,
            cover_vars=31283,
            wide_idx=0,
            wide_target=2289,
            block_idx=763,
            local_idx=763,
            block_target=27468,
            final_targets=2289,
        ),
        _case(
            "all_powered_templates_selected_block",
            proto_vars=84500,
            elements=27468,
            cover_vars=30520,
            wide_idx=0,
            wide_target=0,
            block_idx=763,
            local_idx=763,
            block_target=27468,
            final_targets=0,
            block_selected=9156,
        ),
        _case(
            "all_powered_templates_selected_block_active_guard",
            proto_vars=124176,
            elements=18312,
            cover_vars=79352,
            wide_idx=0,
            wide_target=0,
            block_idx=763,
            local_idx=763,
            block_target=18312,
            final_targets=0,
            block_selected=9156,
            local_selected=48832,
            bool_or=585984,
        ),
    ]
    comparison = _comparison_payload(cases)
    assessment = _final_target_channel_assessment(cases)

    assert comparison["final_target_delta_selected_block_minus_all_templates"] == -2289
    assert comparison["element_delta_selected_block_minus_all_templates"] == -2289
    assert comparison["block_selected_literal_delta_selected_block_minus_all_templates"] == 9156
    assert comparison["element_delta_active_guard_minus_selected_block"] == -9156
    assert comparison["bool_or_delta_active_guard_minus_selected_block"] == 585984
    assert comparison["block_target_delta_active_guard_minus_selected_block"] == -9156
    assert comparison["local_selected_delta_active_guard_minus_selected_block"] == 48832
    assert assessment["safe_patch_available"] is True
    assert assessment["verdict"] == "active_guard_default_off_candidate_identified"
    assert assessment["active_guard_assessment"]["reduces_block_intermediate_targets"] is True


def test_cover_choice_profile_comparison_missing_campaign_is_no_solve(
    tmp_path: Path,
) -> None:
    report = build_phase3b_cover_choice_profile_comparison(
        tmp_path,
        campaign_state_path=tmp_path / "missing_state.json",
    )

    assert report["solver_invoked"] is False
    assert report["metadata"]["solver_invoked"] is False
    assert report["metadata"]["proof_source"] is False
    assert report["metadata"]["candidate_elimination_claim"] is False
    assert report["status"]["outcome"] == "campaign_state_missing"
    assert report["cases"] == []
    checks = {check["check_id"]: check for check in report["checks"]}
    assert checks["no_solve_analysis"]["status"] == "pass"
    assert checks["diagnostic_not_proof_source"]["status"] == "pass"


def test_cover_choice_profile_comparison_cli_defaults_to_neutral_output() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_text = (
        repo_root / "scripts" / "build_phase3b_cover_choice_profile_comparison.py"
    ).read_text(encoding="utf-8")

    assert "phase3b_cover_choice_profile_comparison" in script_text
    assert "E:/phase3b_workspaces" not in script_text
    assert "cover_choice_profile_comparison.json" in script_text
    assert "cover_choice_profile_comparison.md" in script_text
    assert "cover_choice_profile_comparison.txt" in script_text
    assert "solver_invoked" in script_text
    assert "DEFAULT_COVER_CHOICE_CANDIDATE" in script_text
    assert "build_phase3b_cover_choice_profile_comparison" in script_text
