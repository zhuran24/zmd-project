from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from unittest.mock import patch

import pytest

from src.io import delivery_manifest as delivery_manifest_module
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search import certified_surface as certified_surface_module
from src.search import exact_campaign as exact_campaign_module
from src.search.certified_surface import (
    P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX,
    evaluate_certified_delivery_surface,
    export_and_verify_certified_delivery_manifest,
    publish_verified_certified_delivery_surface,
    resolve_p1_2_publish_open_gate,
)
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
)
from src.search.exact_campaign_inspector import build_exact_campaign_inspection
from src.tests.certified_frontier_helpers import (
    attach_terminal_frontier_evidence,
    write_closed_phase_review_gate,
)
from src.tests.test_delivery_manifest import (
    _V89_GHOST_PICK,
    _build_manifest_project,
)

# Design note (test isolation + speed):
# Building a real publishable surface drives the sink-side isolated subprocess
# replay, which is slow (~seconds each) and, under heavy co-execution, can
# intermittently degrade to an upstream `canonical_grid_invalid` (pre-existing
# flaky #15 — never a gate bypass, the verdict is always publishable=False).
# To keep this file fast and not amplify that flaky, the real publishable
# surface is built ONCE per module (`publishable_surface` fixture); each test
# only rewrites the small gate file.  Every gate-reason branch is covered
# deterministically by `test_resolve_p1_2_publish_open_gate_fail_closed_branches`
# (resolver-direct, no surface).  Surface-level tests assert robust invariants:
# `publishable is False` always holds when the gate is open, and the exact
# gate blocked_reason is asserted only when the surface actually reached the
# gate (`publish_open_gate_open`), so an upstream flaky degradation can never
# produce a false RED.


def _gate_path(project_root: Path) -> Path:
    return project_root / "data" / "review_gates" / "phase_1_2_spike_close.json"


def _write_gate_text(project_root: Path, text: str) -> Path:
    path = _gate_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Always start from a clean path so a prior test's symlink/file cannot make
    # this write land through a symlink (shared module-scoped project root).
    if path.is_symlink() or path.exists():
        path.unlink()
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _write_gate_payload(project_root: Path, payload: object) -> Path:
    return _write_gate_text(
        project_root,
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )


def _minimal_gate_payload(
    *,
    status: str = "blocked_manual_review_count",
    next_allowed: bool = False,
    owner_decision: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 2,
        "gate_id": "phase_1_2_spike_close",
        "status": status,
        "next_phase_entry": {"allowed": next_allowed},
    }
    if owner_decision is not None:
        payload["owner_manual_decision"] = owner_decision
    return payload


def _clear_gate(project_root: Path) -> None:
    path = _gate_path(project_root)
    if path.is_symlink() or path.exists():
        path.unlink()


def _build_publishable_surface(
    project_root: Path,
) -> tuple[Path, ExactCampaign, Optional[dict[str, Any]]]:
    # PR1: best_certified_result() now reads the disk publish surface and requires a
    # real supervisor_seal.  The fixture must transition the campaign through
    # CANDIDATE_PROPOSED → supervisor_seal() → publish instead of the legacy forge path.
    project_root, facility_pools = _build_manifest_project(project_root)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }

    # 1. Set up campaign state in CANDIDATE_PROPOSED status with ghost-pick evidence.
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**_V89_GHOST_PICK, **solution},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": CANDIDATE_PROPOSED_STATUS,
        "search_stats": {"campaign_resumed": False},
    }
    run_id = campaign.set_supervisor_proposal_run_id()
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=CANDIDATE_PROPOSED_STATUS,
    )
    attach_terminal_frontier_evidence(campaign, project_root)
    campaign.save()
    campaign.write_proposal_ready_marker(run_id=run_id, exit_code=0)

    # 2. Accepting mock helpers used during the seal-only window.
    #    Post-fixture evaluation in each test runs the real validator (including the
    #    real isolated subprocess replay), matching the pre-PR1 behaviour.

    def _accept_sink_replay(**kwargs: Any) -> dict[str, Any]:
        cs = kwargs["campaign_state"]
        return {
            "evidence": dict(cs["terminal_frontier_evidence"]),
            "candidate_records": {
                str(k): dict(v) for k, v in cs.get("candidates", {}).items()
            },
            "sink_replay_violations": {},
            "fixed_witness_publishable": True,
            "fixed_witness_violations": {},
        }

    def _accept_terminal_evidence(
        state: Any,
        *,
        project_root: Any,
        campaign_path: Any = None,
        serialized_state_bytes: Any = None,
    ) -> bool:
        return (
            state.get("final_status") == RUN_STATUS_CERTIFIED
            and state.get("final_result") is not None
            and state.get("terminal_frontier_evidence") is not None
        )

    def _accept_authority_violation(*args: Any, **kwargs: Any) -> None:
        # Bypass the pre-commit isolated subprocess replay during fixture sealing.
        return None

    # 3. Seal with mocked replay, then publish all delivery artifacts.
    with (
        patch.object(
            exact_campaign_module,
            "build_sink_verified_terminal_frontier_evidence",
            _accept_sink_replay,
        ),
        patch.object(
            exact_campaign_module,
            "_terminal_certified_final_result_violation_for_project_authority",
            _accept_authority_violation,
        ),
        patch.object(
            exact_campaign_module,
            "has_valid_terminal_full_frontier_certified_evidence_for_project",
            _accept_terminal_evidence,
        ),
        patch.object(
            delivery_manifest_module,
            "has_valid_terminal_full_frontier_certified_evidence_for_project",
            _accept_terminal_evidence,
        ),
        patch.object(
            certified_surface_module,
            "has_valid_terminal_full_frontier_certified_evidence_for_project",
            _accept_terminal_evidence,
        ),
    ):
        campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=True)
        campaign.supervisor_seal()
        assert campaign.state["final_status"] == RUN_STATUS_CERTIFIED

        # The publisher checks the open gate.  Write a valid closed gate so the
        # fixture produces a properly sealed + gate-passed surface for tests to
        # interrogate (individual tests that probe gate rejection do their own
        # gate manipulation afterwards).
        write_closed_phase_review_gate(project_root)

        surface = publish_verified_certified_delivery_surface(
            project_root=project_root,
            campaign_path=campaign.path,
            facility_pools=facility_pools,
            campaign_state=campaign.state,
        )

    assert surface.publishable
    manifest = surface.delivery_manifest_payload
    return project_root, campaign, manifest


@pytest.fixture(scope="module")
def publishable_surface(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, ExactCampaign, Optional[dict[str, Any]]]:
    """Build ONE real publishable surface for the whole module (slow replay once)."""

    root = tmp_path_factory.mktemp("p1_2_open_gate_surface")
    return _build_publishable_surface(root)


def _evaluate(
    surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
) -> Any:
    project_root, campaign, manifest = surface
    return evaluate_certified_delivery_surface(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
        delivery_manifest=manifest,
    )


def _assert_resolver_open(project_root: Path, expected_reason: str) -> None:
    is_open, reason = resolve_p1_2_publish_open_gate(project_root=project_root)
    assert is_open is True
    assert reason == expected_reason


def _assert_surface_blocked_by_open_gate(
    surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
    expected_reason: str,
) -> None:
    """Robust surface assertion: an open gate always blocks publication; the exact
    gate reason is only asserted when the surface actually reached the gate, so a
    pre-existing replay flaky (which blocks earlier, still publishable=False) cannot
    turn this into a false RED."""

    verdict = _evaluate(surface)
    assert verdict.publishable is False, verdict.as_summary()
    if verdict.publish_open_gate_open:
        assert verdict.blocked_reason == expected_reason
        assert verdict.publish_open_gate_reason == expected_reason


def test_p1_2_publish_open_gate_closed_manual_decision_allows_publishable_surface(
    publishable_surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
) -> None:
    project_root, _campaign, _manifest = publishable_surface
    write_closed_phase_review_gate(project_root)

    is_open, reason = resolve_p1_2_publish_open_gate(project_root=project_root)
    verdict = _evaluate(publishable_surface)

    assert (is_open, reason) == (False, None)
    assert verdict.publishable is True, verdict.as_summary()
    assert verdict.publish_open_gate_open is False
    assert verdict.publish_open_gate_reason is None


@pytest.mark.parametrize("status", ["open", "blocked", "blocked_manual_review_count"])
def test_p1_2_publish_open_gate_blocks_open_statuses(
    publishable_surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
    status: str,
) -> None:
    project_root, _campaign, _manifest = publishable_surface
    _write_gate_payload(project_root, _minimal_gate_payload(status=status, next_allowed=False))
    expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:status_{status}"
    _assert_resolver_open(project_root, expected_reason)
    _assert_surface_blocked_by_open_gate(publishable_surface, expected_reason)


def test_p1_2_publish_open_gate_missing_file_fails_closed(
    publishable_surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
) -> None:
    project_root, _campaign, _manifest = publishable_surface
    _clear_gate(project_root)
    expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:missing"
    _assert_resolver_open(project_root, expected_reason)
    _assert_surface_blocked_by_open_gate(publishable_surface, expected_reason)


@pytest.mark.parametrize("case", ["duplicate_key", "nan_constant", "top_level_non_object", "symlink"])
def test_p1_2_publish_open_gate_rejects_malformed_gate_files(
    publishable_surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
    case: str,
) -> None:
    project_root, _campaign, _manifest = publishable_surface
    gate_path = _gate_path(project_root)
    _clear_gate(project_root)
    if case == "duplicate_key":
        _write_gate_text(
            project_root,
            '{"schema_version":2,"gate_id":"phase_1_2_spike_close",'
            '"status":"closed_manual_owner_decision","status":"open",'
            '"next_phase_entry":{"allowed":true},'
            '"owner_manual_decision":{"p1_3b_entry_allowed":true}}\n',
        )
        expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:json_error"
    elif case == "nan_constant":
        _write_gate_text(
            project_root,
            '{"schema_version":2,"gate_id":"phase_1_2_spike_close",'
            '"status":"closed_manual_owner_decision",'
            '"next_phase_entry":{"allowed":NaN},'
            '"owner_manual_decision":{"p1_3b_entry_allowed":true}}\n',
        )
        expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:json_error"
    elif case == "top_level_non_object":
        _write_gate_text(project_root, "[]\n")
        expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:json_error"
    else:
        target = gate_path.with_name("closed_gate_target.json")
        if target.is_symlink() or target.exists():
            target.unlink()
        write_closed_phase_review_gate(project_root)
        gate_path.rename(target)
        gate_path.symlink_to(target)
        expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:not_regular_file"
    _assert_resolver_open(project_root, expected_reason)
    _assert_surface_blocked_by_open_gate(publishable_surface, expected_reason)


@pytest.mark.parametrize(
    ("payload", "expected_suffix"),
    [
        (
            _minimal_gate_payload(
                status="closed_manual_owner_decision",
                next_allowed=False,
                owner_decision={"p1_3b_entry_allowed": True},
            ),
            "next_phase_not_allowed",
        ),
        (
            _minimal_gate_payload(
                status="closed_manual_owner_decision",
                next_allowed=True,
                owner_decision=None,
            ),
            "decision_missing",
        ),
    ],
)
def test_p1_2_publish_open_gate_rejects_contradictory_closed_gate(
    publishable_surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
    payload: object,
    expected_suffix: str,
) -> None:
    project_root, _campaign, _manifest = publishable_surface
    _clear_gate(project_root)
    _write_gate_payload(project_root, payload)
    expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:{expected_suffix}"
    _assert_resolver_open(project_root, expected_reason)
    _assert_surface_blocked_by_open_gate(publishable_surface, expected_reason)


def test_p1_2_publish_open_gate_inherited_public_surfaces_fail_closed(
    publishable_surface: tuple[Path, ExactCampaign, Optional[dict[str, Any]]],
) -> None:
    project_root, campaign, _manifest = publishable_surface
    _clear_gate(project_root)
    expected_reason = f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:missing"

    inspection = build_exact_campaign_inspection(project_root)
    certified_surface = inspection["certified_surface"]
    assert certified_surface["publishable"] is False
    if certified_surface.get("publish_open_gate_open"):
        assert certified_surface["blocked_reason"] == expected_reason

    # Manifest export routes through the central verdict and refuses to advertise a
    # non-publishable best_certified_result regardless of which check blocked it.
    with pytest.raises(RuntimeError):
        export_and_verify_certified_delivery_manifest(
            project_root=project_root,
            exact_campaign=campaign,
        )


@pytest.mark.parametrize(
    ("case", "expected_suffix"),
    [
        ("missing", "missing"),
        ("directory", "not_regular_file"),
        ("symlink", "not_regular_file"),
        ("duplicate_key", "json_error"),
        ("nan_constant", "json_error"),
        ("top_level_non_object", "json_error"),
        ("gate_id_mismatch", "gate_id_mismatch"),
        ("status_open", "status_open"),
        ("status_blocked", "status_blocked"),
        ("status_blocked_manual_review_count", "status_blocked_manual_review_count"),
        ("next_phase_not_allowed", "next_phase_not_allowed"),
        ("decision_missing", "decision_missing"),
        ("decision_not_allowed", "decision_not_allowed"),
    ],
)
def test_resolve_p1_2_publish_open_gate_fail_closed_branches(
    tmp_path: Path,
    case: str,
    expected_suffix: str,
) -> None:
    project_root = tmp_path / case
    project_root.mkdir()
    gate_path = _gate_path(project_root)

    if case == "missing":
        pass
    elif case == "directory":
        gate_path.mkdir(parents=True)
    elif case == "symlink":
        target = gate_path.with_name("closed_gate_target.json")
        write_closed_phase_review_gate(project_root)
        gate_path.rename(target)
        gate_path.symlink_to(target)
    elif case == "duplicate_key":
        _write_gate_text(
            project_root,
            '{"gate_id":"phase_1_2_spike_close","gate_id":"phase_1_2_spike_close"}\n',
        )
    elif case == "nan_constant":
        _write_gate_text(project_root, '{"gate_id": NaN}\n')
    elif case == "top_level_non_object":
        _write_gate_text(project_root, '"not an object"\n')
    elif case == "gate_id_mismatch":
        _write_gate_payload(project_root, {"gate_id": "wrong_gate", "status": "open"})
    elif case.startswith("status_"):
        status = case.removeprefix("status_")
        _write_gate_payload(project_root, _minimal_gate_payload(status=status))
    elif case == "next_phase_not_allowed":
        _write_gate_payload(
            project_root,
            _minimal_gate_payload(
                status="closed_manual_owner_decision",
                next_allowed=False,
                owner_decision={"p1_3b_entry_allowed": True},
            ),
        )
    elif case == "decision_missing":
        _write_gate_payload(
            project_root,
            _minimal_gate_payload(
                status="closed_manual_owner_decision",
                next_allowed=True,
            ),
        )
    elif case == "decision_not_allowed":
        _write_gate_payload(
            project_root,
            _minimal_gate_payload(
                status="closed_manual_owner_decision",
                next_allowed=True,
                owner_decision={"p1_3b_entry_allowed": False},
            ),
        )
    else:  # pragma: no cover - parametrization sanity.
        raise AssertionError(case)

    is_open, reason = resolve_p1_2_publish_open_gate(project_root=project_root)

    assert is_open is True
    assert reason == f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:{expected_suffix}"
