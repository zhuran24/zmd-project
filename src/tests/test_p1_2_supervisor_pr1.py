from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search import exact_campaign as exact_campaign_module
from src.search import outer_search as outer_search_module
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    SUPERVISOR_PROPOSAL_STATE_KEY,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    load_proposal_ready_marker,
    proposal_ready_marker_violation,
    validate_exact_campaign_resume_state,
)
from src.tests.test_exact_contract import _build_toy_exact_project


def _proposal_final_result() -> dict[str, Any]:
    return {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": {
                "facility_type": "tiny_facility",
                "pose_idx": 0,
                "pose_id": "tiny_left",
                "anchor": {"x": 0, "y": 0},
                "orientation": 0,
                "port_mode": "default",
            }
        },
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"solve_mode": "certified_exact", "campaign_resumed": False},
    }


def _proposal_terminal_frontier_evidence() -> dict[str, Any]:
    return {"candidate_generation": {"domain_authority": "test_supervisor_replay"}}


def _install_supervisor_candidate_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        exact_campaign_module,
        "candidate_generation_kwargs",
        lambda _candidate_generation: {
            "max_w": 1,
            "max_h": 1,
            "min_side": 1,
            "max_aspect_ratio": None,
            "area_upper_bound": 1,
            "start_area": None,
        },
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "generate_candidate_sizes",
        lambda **_kwargs: [(1, 1, 1)],
    )


def _prepare_candidate_proposed_campaign(
    project_root: Path,
    *,
    run_id: str,
) -> tuple[ExactCampaign, dict[str, Any], dict[str, Any]]:
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    final_result = _proposal_final_result()
    terminal_frontier_evidence = _proposal_terminal_frontier_evidence()
    campaign.set_supervisor_proposal_run_id(run_id)
    campaign.state["final_result"] = final_result
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=CANDIDATE_PROPOSED_STATUS,
    )
    campaign.state["terminal_frontier_evidence"] = terminal_frontier_evidence
    campaign.save()
    return campaign, final_result, terminal_frontier_evidence


def _assert_supervisor_failure_kept_proposal(campaign: ExactCampaign) -> None:
    assert campaign.state["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert campaign.state["last_stop_reason"]["status"] == CANDIDATE_PROPOSED_STATUS
    assert campaign.state.get("final_result") is not None
    assert campaign.state.get("terminal_frontier_evidence") is not None
    assert not (campaign.project_root / "data" / "solutions" / "final_solution.json").exists()
    persisted = json.loads(campaign.path.read_text(encoding="utf-8"))
    assert persisted["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert persisted["last_stop_reason"]["status"] == CANDIDATE_PROPOSED_STATUS


def test_certified_campaign_stop_cannot_bypass_supervisor_seal(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "certified_stop_bypass")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    with pytest.raises(RuntimeError, match="supervisor_seal"):
        campaign.mark_campaign_stopped(
            TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
            status=RUN_STATUS_CERTIFIED,
        )

    assert campaign.state["final_status"] is None


def test_candidate_proposed_resume_is_nonterminal_until_supervisor_seal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "candidate_proposed_resume")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    final_result = _proposal_final_result()
    terminal_frontier_evidence = _proposal_terminal_frontier_evidence()
    proposal_run_id = campaign.set_supervisor_proposal_run_id("resume-test-run")

    campaign.state["final_result"] = final_result
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=CANDIDATE_PROPOSED_STATUS,
    )
    campaign.state["terminal_frontier_evidence"] = terminal_frontier_evidence
    campaign.save()

    assert (
        validate_exact_campaign_resume_state(
            campaign.state,
            campaign.artifact_hashes,
            project_root=project_root,
        )
        is None
    )

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is True
    assert resumed.state["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert resumed.state["final_result"] == final_result
    assert resumed.state[SUPERVISOR_PROPOSAL_STATE_KEY]["run_id"] == proposal_run_id
    assert resumed.best_certified_result() is None

    def accept_supervisor_scratch_state(
        state: Mapping[str, Any],
        *,
        project_root: Path,
        campaign_path: Path | None = None,
    ) -> bool:
        del project_root, campaign_path
        return state.get("final_status") == RUN_STATUS_CERTIFIED

    replay_calls: list[dict[str, Any]] = []

    def accept_sink_replay_bundle(**kwargs: Any) -> dict[str, Any]:
        replay_calls.append(dict(kwargs))
        assert kwargs["campaign_state"]["final_status"] == RUN_STATUS_CERTIFIED
        assert kwargs["project_root"] == project_root
        assert kwargs["campaign_path"] == resumed.path
        assert kwargs["final_result"] == final_result
        assert kwargs["candidate_generation"] == terminal_frontier_evidence["candidate_generation"]
        return {
            "evidence": terminal_frontier_evidence,
            "candidate_records": {},
            "sink_replay_violations": {},
            "fixed_witness_publishable": True,
            "fixed_witness_violations": {},
        }

    _install_supervisor_candidate_generation(monkeypatch)
    monkeypatch.setattr(
        exact_campaign_module,
        "build_sink_verified_terminal_frontier_evidence",
        accept_sink_replay_bundle,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        accept_supervisor_scratch_state,
    )

    resumed.supervisor_seal(
        final_result=final_result,
        terminal_frontier_evidence=terminal_frontier_evidence,
        candidate_records={},
    )

    assert resumed.state["final_status"] == RUN_STATUS_CERTIFIED
    assert resumed.state["last_stop_reason"]["status"] == RUN_STATUS_CERTIFIED
    assert SUPERVISOR_PROPOSAL_STATE_KEY not in resumed.state
    assert len(replay_calls) == 1


def test_supervisor_seal_rejects_sink_replay_violations_without_mint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_replay_reject")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    final_result = _proposal_final_result()
    terminal_frontier_evidence = _proposal_terminal_frontier_evidence()
    campaign.set_supervisor_proposal_run_id("replay-reject-run")
    campaign.state["final_result"] = final_result
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=CANDIDATE_PROPOSED_STATUS,
    )
    campaign.state["terminal_frontier_evidence"] = terminal_frontier_evidence

    _install_supervisor_candidate_generation(monkeypatch)

    def reject_sink_replay_bundle(**_kwargs: Any) -> dict[str, Any]:
        return {
            "evidence": terminal_frontier_evidence,
            "candidate_records": {},
            "sink_replay_violations": {
                "1x1": "candidate_sink_replay_status_mismatch:1x1"
            },
            "fixed_witness_publishable": True,
            "fixed_witness_violations": {},
        }

    def forbidden_validity_check(*_args: Any, **_kwargs: Any) -> bool:
        raise AssertionError("supervisor_seal must stop before evidence validity")

    monkeypatch.setattr(
        exact_campaign_module,
        "build_sink_verified_terminal_frontier_evidence",
        reject_sink_replay_bundle,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        forbidden_validity_check,
    )

    with pytest.raises(RuntimeError, match="terminal candidate sink replay failed"):
        campaign.supervisor_seal(
            final_result=final_result,
            terminal_frontier_evidence=terminal_frontier_evidence,
            candidate_records={},
        )

    assert campaign.state["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert campaign.state["last_stop_reason"]["status"] == CANDIDATE_PROPOSED_STATUS


def test_supervisor_seal_rejects_fixed_witness_failure_without_mint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_fixed_witness_reject")
    campaign, final_result, terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="fixed-witness-reject-run",
    )
    _install_supervisor_candidate_generation(monkeypatch)

    def reject_fixed_witness_bundle(**_kwargs: Any) -> dict[str, Any]:
        return {
            "evidence": terminal_frontier_evidence,
            "candidate_records": {},
            "sink_replay_violations": {},
            "fixed_witness_publishable": False,
            "fixed_witness_violations": {
                "1x1": "terminal_fixed_witness_solution_mismatch"
            },
        }

    def forbidden_validity_check(*_args: Any, **_kwargs: Any) -> bool:
        raise AssertionError("supervisor_seal must stop before evidence validity")

    monkeypatch.setattr(
        exact_campaign_module,
        "build_sink_verified_terminal_frontier_evidence",
        reject_fixed_witness_bundle,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        forbidden_validity_check,
    )

    with pytest.raises(RuntimeError, match="terminal fixed witness verifier failed"):
        campaign.supervisor_seal(
            final_result=final_result,
            terminal_frontier_evidence=terminal_frontier_evidence,
            candidate_records={},
        )

    _assert_supervisor_failure_kept_proposal(campaign)


def test_supervisor_seal_rejects_non_mapping_terminal_bundle_fields_without_mint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for field_name, expected_message in (
        ("evidence", "supervisor_seal sink replay evidence invalid"),
        ("candidate_records", "supervisor_seal sink replay candidate_records invalid"),
    ):
        project_root = _build_toy_exact_project(
            tmp_path / f"supervisor_non_mapping_{field_name}"
        )
        campaign, final_result, terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
            project_root,
            run_id=f"non-mapping-{field_name}-run",
        )
        _install_supervisor_candidate_generation(monkeypatch)

        def invalid_bundle(**_kwargs: Any) -> dict[str, Any]:
            bundle: dict[str, Any] = {
                "evidence": terminal_frontier_evidence,
                "candidate_records": {},
                "sink_replay_violations": {},
                "fixed_witness_publishable": True,
                "fixed_witness_violations": {},
            }
            bundle[field_name] = []
            return bundle

        def forbidden_validity_check(*_args: Any, **_kwargs: Any) -> bool:
            raise AssertionError("supervisor_seal must stop before evidence validity")

        monkeypatch.setattr(
            exact_campaign_module,
            "build_sink_verified_terminal_frontier_evidence",
            invalid_bundle,
        )
        monkeypatch.setattr(
            exact_campaign_module,
            "has_valid_terminal_full_frontier_certified_evidence_for_project",
            forbidden_validity_check,
        )

        with pytest.raises(RuntimeError, match=expected_message):
            campaign.supervisor_seal(
                final_result=final_result,
                terminal_frontier_evidence=terminal_frontier_evidence,
                candidate_records={},
            )

        _assert_supervisor_failure_kept_proposal(campaign)


def test_supervisor_seal_rejects_has_valid_false_without_mint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_has_valid_false")
    campaign, final_result, terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="has-valid-false-run",
    )
    _install_supervisor_candidate_generation(monkeypatch)
    validity_calls: list[dict[str, Any]] = []

    def accept_sink_replay_bundle(**_kwargs: Any) -> dict[str, Any]:
        return {
            "evidence": terminal_frontier_evidence,
            "candidate_records": {},
            "sink_replay_violations": {},
            "fixed_witness_publishable": True,
            "fixed_witness_violations": {},
        }

    def reject_terminal_evidence(
        state: Mapping[str, Any],
        *,
        project_root: Path,
        campaign_path: Path | None = None,
    ) -> bool:
        validity_calls.append(
            {
                "final_status": state.get("final_status"),
                "project_root": project_root,
                "campaign_path": campaign_path,
            }
        )
        return False

    monkeypatch.setattr(
        exact_campaign_module,
        "build_sink_verified_terminal_frontier_evidence",
        accept_sink_replay_bundle,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        reject_terminal_evidence,
    )

    with pytest.raises(RuntimeError, match="supervisor_seal rejected terminal CERTIFIED evidence"):
        campaign.supervisor_seal(
            final_result=final_result,
            terminal_frontier_evidence=terminal_frontier_evidence,
            candidate_records={},
        )

    assert validity_calls == [
        {
            "final_status": RUN_STATUS_CERTIFIED,
            "project_root": project_root,
            "campaign_path": None,
        }
    ]
    _assert_supervisor_failure_kept_proposal(campaign)


def test_proposal_ready_marker_binds_run_id_exit_code_and_checkpoint_sha(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "proposal_ready_marker")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    final_result = _proposal_final_result()
    run_id = campaign.set_supervisor_proposal_run_id("marker-test-run")
    campaign.state["final_result"] = final_result
    campaign.state["terminal_frontier_evidence"] = {"proposal": "terminal_frontier_evidence"}
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=CANDIDATE_PROPOSED_STATUS,
    )
    campaign.save()

    marker = campaign.write_proposal_ready_marker(run_id=run_id, exit_code=0)

    assert marker["run_id"] == run_id
    assert marker["exit_code"] == 0
    loaded, violation = load_proposal_ready_marker(
        campaign.proposal_ready_marker_path,
        checkpoint_path=campaign.path,
        expected_run_id=run_id,
    )
    assert violation is None
    assert loaded == marker

    campaign.path.write_text(
        campaign.path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    assert (
        proposal_ready_marker_violation(
            marker,
            checkpoint_path=campaign.path,
            expected_run_id=run_id,
        )
        == "proposal_ready_marker_checkpoint_sha256_mismatch"
    )


def test_outer_search_terminal_commit_writes_candidate_proposal_marker_without_supervisor_seal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "outer_commit_proposal_marker")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    final_result = _proposal_final_result()
    replayed_candidate_records = {"1x1": {"status": RUN_STATUS_CERTIFIED}}
    terminal_frontier_evidence = {"proposal": "terminal_frontier_evidence"}

    def fake_project_candidate_records_for_sink(
        *,
        state: Mapping[str, Any],
        project_root: Path,
        campaign_path: Path | None,
        require_record_solution_match: bool,
        candidate_keys: object = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        del candidate_keys
        assert project_root == campaign.project_root
        assert campaign_path == campaign.path
        assert require_record_solution_match is True
        assert state["final_status"] == CANDIDATE_PROPOSED_STATUS
        assert state["final_result"] == dict(final_result)
        return replayed_candidate_records, {}

    def fake_fixed_witness_projection(
        *,
        state: Mapping[str, Any],
        project_root: Path,
        campaign_path: Path | None,
        candidate_records: Mapping[str, Any],
        final_result: Mapping[str, Any],
        serialized_state_bytes: bytes | None = None,
    ) -> SimpleNamespace:
        del serialized_state_bytes
        assert project_root == campaign.project_root
        assert campaign_path == campaign.path
        assert Path(campaign_path).exists()
        stored = json.loads(Path(campaign_path).read_text(encoding="utf-8"))
        assert stored["final_status"] == CANDIDATE_PROPOSED_STATUS
        assert stored["final_result"] == dict(final_result)
        assert stored["candidates"] == replayed_candidate_records
        assert state["candidates"] == replayed_candidate_records
        assert dict(candidate_records) == replayed_candidate_records
        return SimpleNamespace(
            publishable=True,
            candidate_key="1x1",
            rejected_reason=None,
            candidate_records=replayed_candidate_records,
            durable_candidate_records=replayed_candidate_records,
        )

    def fake_build_terminal_frontier_evidence(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["candidate_records"] == replayed_candidate_records
        assert kwargs["final_result"] == final_result
        return terminal_frontier_evidence

    def forbidden_supervisor_seal(self: ExactCampaign, **_kwargs: Any) -> None:
        del self
        raise AssertionError("producer must not call supervisor_seal")

    monkeypatch.setattr(
        outer_search_module,
        "project_candidate_records_for_sink",
        fake_project_candidate_records_for_sink,
    )
    monkeypatch.setattr(
        outer_search_module,
        "build_terminal_fixed_witness_projection_at_sink",
        fake_fixed_witness_projection,
    )
    monkeypatch.setattr(
        outer_search_module,
        "build_terminal_frontier_evidence",
        fake_build_terminal_frontier_evidence,
    )
    monkeypatch.setattr(ExactCampaign, "supervisor_seal", forbidden_supervisor_seal, raising=False)

    outer_search_module._commit_terminal_full_frontier_certified_result(
        campaign,
        final_result,
        candidates=[(1, 1, 1)],
        candidate_generation={"domain_authority": "test"},
    )

    assert campaign.state["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert campaign.state["last_stop_reason"]["status"] == CANDIDATE_PROPOSED_STATUS
    assert campaign.state["terminal_frontier_evidence"] == terminal_frontier_evidence
    assert campaign.state["candidates"] == replayed_candidate_records
    run_id = campaign.state[SUPERVISOR_PROPOSAL_STATE_KEY]["run_id"]
    loaded, violation = load_proposal_ready_marker(
        campaign.proposal_ready_marker_path,
        checkpoint_path=campaign.path,
        expected_run_id=run_id,
    )
    assert violation is None
    assert loaded is not None
    assert loaded["exit_code"] == 0
