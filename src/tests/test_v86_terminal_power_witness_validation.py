from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.search.exact_campaign import terminal_certified_final_result_project_precheck_violation
import src.io.delivery_manifest as delivery_manifest_module
import src.search.certified_surface as certified_surface_module
import src.search.exact_campaign as exact_campaign_module
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    ExactCampaign,
    terminal_certified_final_result_violation_for_project,
)
from src.tests.certified_frontier_helpers import install_accepting_l0_supervisor_seal
from src.tests.verified_producer_test_support import seal_test_candidate_status


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _write_power_project(root: Path, *, include_selected_covering_pole: bool) -> dict[str, object]:
    data_dir = root / "data" / "preprocessed"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.mkdir(parents=True, exist_ok=True)

    rules = {
        "globals": {
            "grid": {"width": 3, "height": 1},
            "empty_rectangle": {
                "objective": "max_lex_area_min_side",
                "min_side_admissibility": 1,
            },
        },
        "facility_templates": {
            "powered_sink": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 0,
            },
        },
    }
    facility_pools = {
        "powered_sink": [
            {
                "pose_id": "sink_at_0_0",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "power_pole": [
            {
                "pose_id": "pole_at_1_0",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0]],
            }
        ],
    }
    mandatory_instances = [
        {
            "instance_id": "sink_001",
            "facility_type": "powered_sink",
            "operation_type": "",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(rules_dir / "canonical_rules.json", rules)
    _write_json(rules_dir / "preprocess_plan.json", {"utility_operations": {}})
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(data_dir / "mandatory_exact_instances.json", mandatory_instances)
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )

    placement_solution: dict[str, object] = {
        "sink_001": {"facility_type": "powered_sink", "pose_idx": 0},
    }
    if include_selected_covering_pole:
        placement_solution["pose_optional::power_pole::pole_at_1_0"] = {
            "facility_type": "power_pole",
            "pose_idx": 0,
            "pose_id": "pole_at_1_0",
            "is_mandatory": False,
            "bound_type": "exact_pose_optional",
            "solve_mode": "certified_exact",
        }
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 2, "anchor_y": 0},
        "placement_solution": placement_solution,
        "search_stats": {"campaign_resumed": False},
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 1,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 2,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 2,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    candidate_records = {}
    for area, ghost_w, ghost_h in candidates:
        status = "CERTIFIED" if (ghost_w, ghost_h) == (1, 1) else "INFEASIBLE"
        record: dict[str, object] = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "terminal power witness validation"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = {
                **placement_solution,
                "ghost_pick": {
                    "facility_type": "ghost_rect",
                    "pose_idx": 2,
                    "pose_id": "ghost_anchor::2,0",
                    "anchor": {"x": 2, "y": 0},
                },
            }
        candidate_records[f"{ghost_w}x{ghost_h}"] = record

    return {
        "declare_mode": "strict",
        "final_status": "CERTIFIED",
        "last_stop_reason": {
            "status": "CERTIFIED",
            "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        },
        "final_result": final_result,
        "candidates": candidate_records,
        "terminal_frontier_evidence": build_terminal_frontier_evidence(
            candidates=candidates,
            candidate_records=candidate_records,
            final_result=final_result,
            candidate_generation=candidate_generation,
        ),
    }


def test_terminal_project_validator_rejects_powered_facility_without_selected_power_coverer(
    tmp_path: Path,
) -> None:
    state = _write_power_project(tmp_path, include_selected_covering_pole=False)

    assert (
        terminal_certified_final_result_project_precheck_violation(state, project_root=tmp_path)
        == "terminal_certified_final_result_solution_power_coverage_missing"
    )


def test_terminal_project_validator_accepts_selected_power_coverer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ④b sink replay: the CERTIFIED 1x1 witness (which selects the covering power
    # pole) must be independently re-derived by an isolated solver before the
    # validator accepts it.  The acceptance of a selected power coverer must still
    # hold under that replay.  On this toy 3x1 project 1x1 is genuinely CERTIFIED
    # (anchor 2,0) and 2x1 is genuinely INFEASIBLE, so every strong record is
    # replay-consistent.
    state = _write_power_project(tmp_path, include_selected_covering_pole=True)

    # Install the test-only L0 supervisor seal and accepting terminal evidence checks.
    # This keeps supervisor_seal() on the seal path while still exercising the
    # power-coverage precheck and the public terminal validator.
    install_accepting_l0_supervisor_seal(monkeypatch, project_root=tmp_path)

    def accept_terminal_evidence(
        s: dict[str, Any],
        *,
        project_root: Path,
        campaign_path: Path | None = None,
        serialized_state_bytes: bytes | None = None,
    ) -> bool:
        assert campaign_path is not None
        if serialized_state_bytes is None:
            assert Path(campaign_path).exists()
        else:
            decoded = json.loads(serialized_state_bytes.decode("utf-8"))
            assert decoded.get("final_status") == "CERTIFIED"
        return (
            s.get("final_status") == "CERTIFIED"
            and s.get("final_result") is not None
            and s.get("terminal_frontier_evidence") is not None
        )

    for mod in (exact_campaign_module, certified_surface_module, delivery_manifest_module):
        monkeypatch.setattr(
            mod,
            "has_valid_terminal_full_frontier_certified_evidence_for_project",
            accept_terminal_evidence,
        )

    # Also bypass the internal authority validator called from
    # _validate_supervisor_certified_state_before_commit, which runs the full
    # isolated-solver subprocess.  Precheck (power coverage) still fires before
    # this point, so the power-coverage assertion is exercised.
    monkeypatch.setattr(
        exact_campaign_module,
        "_terminal_certified_final_result_violation_for_project_authority",
        lambda *_args, **_kwargs: None,
    )

    # Build a CANDIDATE_PROPOSED checkpoint on disk following the same sequence
    # used by _prepare_candidate_proposed_campaign in test_p1_2_supervisor_pr1.py.
    proposal_final_result = dict(state["final_result"])
    proposal_final_result["search_status"] = CANDIDATE_PROPOSED_STATUS

    campaign = ExactCampaign.load_or_create(tmp_path, campaign_hours=1.0, resume=False)
    campaign.state["declare_mode"] = "strict"
    campaign.state["candidates"] = state["candidates"]
    campaign.state["final_result"] = proposal_final_result

    run_id = campaign.set_supervisor_proposal_run_id()
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON, status=CANDIDATE_PROPOSED_STATUS
    )
    campaign.state["terminal_frontier_evidence"] = state["terminal_frontier_evidence"]

    for key, record in campaign.state["candidates"].items():
        seal_test_candidate_status(campaign, key, str(record["status"]))

    campaign.save()
    campaign.write_proposal_ready_marker(run_id=run_id, exit_code=0)

    # Load the proposal checkpoint and seal it.  supervisor_seal runs
    # terminal_certified_final_result_project_precheck_violation (not patched),
    # which exercises the power-coverage check on the placement_solution that
    # includes the selected covering pole.
    sealed_campaign = ExactCampaign.load_or_create(tmp_path, campaign_hours=1.0, resume=True)
    sealed_campaign.supervisor_seal()

    assert (
        terminal_certified_final_result_violation_for_project(
            sealed_campaign.state,
            project_root=tmp_path,
            campaign_path=sealed_campaign.path,
        )
        is None
    )
