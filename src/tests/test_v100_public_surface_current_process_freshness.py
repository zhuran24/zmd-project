from __future__ import annotations

import gc
import json
from pathlib import Path

import pytest

from src.io.delivery_manifest import export_certified_delivery_manifest
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.certified_surface import save_certified_final_solution_and_blueprint
from src.search.exact_campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    PROOF_SUMMARY_SCHEMA_VERSION,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    ExactCampaign,
    compute_exact_artifact_hashes,
    _mark_candidate_status_fresh_for_current_process,
    terminal_proof_bearing_candidate_freshness_violation,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_v100_manifest_rejects_structural_frontier_without_current_process_statuses(
    tmp_path: Path,
) -> None:
    root = tmp_path / "structural_frontier_not_fresh"
    data_dir = root / "data" / "preprocessed"
    checkpoint_dir = root / "data" / "checkpoints"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    checkpoint_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    rules = {
        "globals": {
            "grid": {"width": 3, "height": 3},
            "empty_rectangle": {
                "objective": "max_lex_area_min_side",
                "min_side_admissibility": 1,
            },
        },
        "facility_templates": {"T": {"dimensions": {"w": 1, "h": 1}}},
    }
    facility_pools = {
        "T": [
            {
                "pose_id": "T_center",
                "anchor": {"x": 1, "y": 1},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[1, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
            },
            {
                "pose_id": "T_corner",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            },
        ]
    }
    _write_json(rules_dir / "canonical_rules.json", rules)
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(
        data_dir / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "must_place",
                "facility_type": "T",
                "operation_type": "op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )

    final_result = {
        "ghost_rect": {"w": 3, "h": 1, "area": 3, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {
            "must_place": {
                "facility_type": "T",
                "pose_idx": 0,
                "pose_id": "T_center",
                "anchor": {"x": 1, "y": 1},
            }
        },
        "search_status": "CERTIFIED",
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 3,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 8,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 8,
        "min_side_admissibility": 1,
    }
    candidate_records: dict[str, dict[str, object]] = {}
    for area, w, h in generate_candidate_sizes(
        **candidate_generation_kwargs(candidate_generation)
    ):
        key = f"{w}x{h}"
        status = "CERTIFIED" if key == "3x1" else "INFEASIBLE"
        record: dict[str, object] = {
            "ghost_rect": {"w": w, "h": h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "forged-alt-layout-frontier"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = {
                "ghost_pick": {
                    "pose_idx": 0,
                    "pose_id": "ghost_anchor::0,0",
                    "anchor": {"x": 0, "y": 0},
                    "facility_type": "ghost_rect",
                },
                "must_place": final_result["placement_solution"]["must_place"],
            }
        candidate_records[key] = record

    evidence = build_terminal_frontier_evidence(
        candidates=generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation)),
        candidate_records=candidate_records,
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    state = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": 168.0,
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:01Z",
        "artifact_hashes": compute_exact_artifact_hashes(root),
        "master_domain_contract": {
            "schema_version": 1,
            "ghost_anchor_domain": "full_unfiltered",
            "ghost_anchor_filter": None,
        },
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": None,
        "final_result": final_result,
        "final_status": "CERTIFIED",
        "last_stop_reason": {
            "status": "CERTIFIED",
            "reason": "search_exhausted_all_candidates",
            "updated_at": "2026-06-10T00:00:01Z",
        },
        "terminal_frontier_evidence": evidence,
        "declare_mode": "strict",
        "candidates": candidate_records,
    }
    checkpoint_path = checkpoint_dir / "exact_campaign_state.json"
    _write_json(checkpoint_path, state)
    save_certified_final_solution_and_blueprint(
        project_root=root,
        result=final_result,
        facility_pools=facility_pools,
    )

    with pytest.raises(ValueError):
        export_certified_delivery_manifest(
            project_root=root,
            campaign_state=state,
            campaign_path=checkpoint_path,
        )


def test_v102_public_candidate_result_writer_cannot_self_mint_strong_freshness(
    tmp_path: Path,
) -> None:
    state = {
        "candidates": {},
        "declare_mode": "strict",
        "final_status": None,
        "final_result": None,
        "last_stop_reason": None,
    }
    campaign = ExactCampaign(
        project_root=tmp_path,
        path=tmp_path / "data" / "checkpoints" / "exact_campaign_state.json",
        state=state,
        resumed=False,
        compatible_hashes=True,
    )

    campaign.mark_candidate_result(
        6,
        6,
        "INFEASIBLE",
        proof_summary={"producer": "untrusted-public-writer"},
    )
    state["final_status"] = "CERTIFIED"
    state["final_result"] = {
        "ghost_rect": {"w": 6, "h": 6, "area": 36},
        "placement_solution": {},
        "search_status": "CERTIFIED",
    }
    state["last_stop_reason"] = {
        "status": "CERTIFIED",
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    }

    assert terminal_proof_bearing_candidate_freshness_violation(state) == (
        "terminal_candidate_status_not_current_process_fresh:6x6"
    )


def test_v100_current_process_freshness_rejects_in_place_candidate_record_mutation(
    tmp_path: Path,
) -> None:
    state = {
        "candidates": {},
        "declare_mode": "strict",
        "final_status": None,
        "final_result": None,
        "last_stop_reason": None,
    }
    campaign = ExactCampaign(
        project_root=tmp_path,
        path=tmp_path / "data" / "checkpoints" / "exact_campaign_state.json",
        state=state,
        resumed=False,
        compatible_hashes=True,
    )

    campaign.mark_candidate_result(
        6,
        6,
        "INFEASIBLE",
        proof_summary={"producer": "current-process-regression"},
    )
    _mark_candidate_status_fresh_for_current_process(campaign, "6x6", "INFEASIBLE")
    state["final_status"] = "CERTIFIED"
    state["final_result"] = {
        "ghost_rect": {"w": 6, "h": 6, "area": 36},
        "placement_solution": {},
        "search_status": "CERTIFIED",
    }
    state["last_stop_reason"] = {
        "status": "CERTIFIED",
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    }

    assert terminal_proof_bearing_candidate_freshness_violation(state) is None

    # The freshness seal must bind the strong proof-bearing record content, not just
    # the Python object identity.  A same-dict mutation after mark_candidate_result
    # is not a current-process proof of the mutated CERTIFIED claim.
    record = state["candidates"]["6x6"]
    record["status"] = "CERTIFIED"
    record["solution"] = {"forged": True}
    record["proof_summary"] = {"producer": "post-mark-in-place-mutation"}

    assert terminal_proof_bearing_candidate_freshness_violation(state) == (
        "terminal_candidate_status_not_current_process_fresh:6x6"
    )


def test_v100_current_process_freshness_is_bound_to_campaign_proof_context(
    tmp_path: Path,
) -> None:
    donor_root = tmp_path / "donor"
    target_root = tmp_path / "target"
    state = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "artifact_hashes": {"candidate_placements": "donor-hash"},
        "master_domain_contract": {
            "schema_version": 1,
            "ghost_anchor_domain": "full_unfiltered",
            "ghost_anchor_filter": None,
        },
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "candidates": {},
        "declare_mode": "strict",
        "final_status": None,
        "final_result": None,
        "last_stop_reason": None,
    }
    campaign = ExactCampaign(
        project_root=donor_root,
        path=donor_root / "data" / "checkpoints" / "exact_campaign_state.json",
        state=state,
        resumed=False,
        compatible_hashes=True,
    )

    campaign.mark_candidate_result(
        6,
        6,
        "INFEASIBLE",
        proof_summary={"producer": "donor-project"},
    )
    _mark_candidate_status_fresh_for_current_process(campaign, "6x6", "INFEASIBLE")
    state["final_status"] = "CERTIFIED"
    state["final_result"] = {
        "ghost_rect": {"w": 6, "h": 6, "area": 36},
        "placement_solution": {},
        "search_status": "CERTIFIED",
    }
    state["last_stop_reason"] = {
        "status": "CERTIFIED",
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    }

    assert terminal_proof_bearing_candidate_freshness_violation(state) is None

    # The record was genuinely produced in this process, but only for the donor
    # artifact universe.  Repointing the same live state at another project's
    # hashes must not preserve its proof-bearing status.
    state["artifact_hashes"] = {"candidate_placements": "target-hash"}
    assert terminal_proof_bearing_candidate_freshness_violation(state) == (
        "terminal_candidate_status_not_current_process_fresh:6x6"
    )

    state["artifact_hashes"] = {"candidate_placements": "donor-hash"}
    campaign.project_root = target_root
    campaign.path = target_root / "data" / "checkpoints" / "exact_campaign_state.json"
    assert terminal_proof_bearing_candidate_freshness_violation(state) == (
        "terminal_candidate_status_not_current_process_fresh:6x6"
    )


def test_v100_current_process_freshness_does_not_transfer_after_identity_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale integer identities must not act as reusable proof provenance."""

    import src.search.exact_campaign as exact_campaign_module

    # Deterministically model allocator address reuse.  The original registry
    # stored only integer id(...) values, so equal integers plus equal JSON
    # digests transferred freshness to unrelated mappings after the donor died.
    monkeypatch.setattr(exact_campaign_module, "id", lambda _value: 7, raising=False)

    state = {
        "candidates": {},
        "declare_mode": "strict",
        "final_status": None,
        "final_result": None,
        "last_stop_reason": None,
    }
    campaign = ExactCampaign(
        project_root=tmp_path,
        path=tmp_path / "data" / "checkpoints" / "exact_campaign_state.json",
        state=state,
        resumed=False,
        compatible_hashes=True,
    )
    campaign.mark_candidate_result(
        6,
        6,
        "INFEASIBLE",
        proof_summary={"producer": "identity-reuse-donor"},
    )
    _mark_candidate_status_fresh_for_current_process(campaign, "6x6", "INFEASIBLE")
    state["final_status"] = "CERTIFIED"
    state["final_result"] = {
        "ghost_rect": {"w": 6, "h": 6, "area": 36},
        "placement_solution": {},
        "search_status": "CERTIFIED",
    }
    state["last_stop_reason"] = {
        "status": "CERTIFIED",
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    }

    assert terminal_proof_bearing_candidate_freshness_violation(state) is None
    record_json = json.dumps(state["candidates"]["6x6"])

    del campaign
    del state
    gc.collect()

    forged_record = json.loads(record_json)
    forged_state = {
        "candidates": {"6x6": forged_record},
        "declare_mode": "strict",
        "final_status": "CERTIFIED",
        "final_result": {
            "ghost_rect": {"w": 6, "h": 6, "area": 36},
            "placement_solution": {},
            "search_status": "CERTIFIED",
        },
        "last_stop_reason": {
            "status": "CERTIFIED",
            "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        },
    }

    assert terminal_proof_bearing_candidate_freshness_violation(forged_state) == (
        "terminal_candidate_status_not_current_process_fresh:6x6"
    )
