from __future__ import annotations

import base64
import hashlib
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
    CAMPAIGN_INSTANCE_ID_KEY,
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
        "search_status": CANDIDATE_PROPOSED_STATUS,
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
    write_marker: bool = True,
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
    if write_marker:
        campaign.write_proposal_ready_marker(run_id=run_id, exit_code=0)
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


def test_reflected_supervisor_token_cannot_bypass_supervisor_seal(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "reflected_token_bypass")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    reflected_token = getattr(exact_campaign_module, "_SUPERVISOR_SEAL_TOKEN", object())

    with pytest.raises(RuntimeError, match="supervisor_seal"):
        campaign.mark_campaign_stopped(
            TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
            status=RUN_STATUS_CERTIFIED,
            _supervisor_seal_token=reflected_token,
        )

    assert campaign.state["final_status"] is None


def test_save_rejects_caller_memory_terminal_certified_checkpoint(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "save_rejects_memory_certified")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state["final_result"] = dict(_proposal_final_result(), search_status=RUN_STATUS_CERTIFIED)
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    campaign.state["last_stop_reason"] = {
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        "status": RUN_STATUS_CERTIFIED,
        "updated_at": "2026-06-24T00:00:00Z",
    }

    with pytest.raises(RuntimeError, match="supervisor_seal"):
        campaign.save()

    assert not campaign.path.exists()


def test_checkpoint_write_lock_fails_closed_when_already_held(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "checkpoint_write_lock")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    with exact_campaign_module._checkpoint_write_lock(campaign.path):
        with pytest.raises(RuntimeError, match="checkpoint write lock unavailable"):
            with exact_campaign_module._checkpoint_write_lock(
                campaign.path,
                timeout_seconds=0.0,
            ):
                raise AssertionError("nested checkpoint lock must not be acquired")


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
    campaign.write_proposal_ready_marker(run_id=proposal_run_id, exit_code=0)

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
        serialized_state_bytes: bytes | None = None,
    ) -> bool:
        assert project_root == resumed.project_root
        assert campaign_path is not None
        assert campaign_path.exists()
        assert serialized_state_bytes is None
        serialized_state = json.loads(Path(campaign_path).read_text(encoding="utf-8"))
        return (
            state.get("final_status") == RUN_STATUS_CERTIFIED
            and serialized_state.get("final_status") == RUN_STATUS_CERTIFIED
            and isinstance(serialized_state.get("supervisor_seal"), dict)
        )

    def accept_precommit_authority(
        state: Mapping[str, Any],
        *,
        project_root: Path,
        campaign_path: Path,
        authority_state: Mapping[str, Any],
        authority_bytes: bytes,
    ) -> None:
        assert project_root == resumed.project_root
        assert campaign_path == resumed.path
        assert state.get("final_status") == RUN_STATUS_CERTIFIED
        decoded = json.loads(authority_bytes.decode("utf-8"))
        assert decoded.get("final_status") == RUN_STATUS_CERTIFIED
        assert authority_state.get("final_status") == RUN_STATUS_CERTIFIED
        return None

    replay_calls: list[dict[str, Any]] = []

    def accept_sink_replay_bundle(**kwargs: Any) -> dict[str, Any]:
        replay_calls.append(dict(kwargs))
        assert kwargs["campaign_state"]["final_status"] == CANDIDATE_PROPOSED_STATUS
        assert kwargs["project_root"] == project_root
        assert kwargs["campaign_path"] == resumed.path
        assert kwargs["serialized_state_bytes"] == resumed.path.read_bytes()
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
        "terminal_certified_final_result_project_precheck_violation",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        accept_supervisor_scratch_state,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "_terminal_certified_final_result_violation_for_project_authority",
        accept_precommit_authority,
    )

    proposal_bytes = resumed.path.read_bytes()
    proposal_sha256 = hashlib.sha256(proposal_bytes).hexdigest()
    resumed.supervisor_seal()

    assert resumed.state["final_status"] == RUN_STATUS_CERTIFIED
    assert resumed.state["last_stop_reason"]["status"] == RUN_STATUS_CERTIFIED
    assert resumed.state["final_result"]["search_status"] == RUN_STATUS_CERTIFIED
    assert SUPERVISOR_PROPOSAL_STATE_KEY not in resumed.state
    seal_record = resumed.state["supervisor_seal"]
    assert seal_record["transition"] == "proposal_to_certified_v1"
    assert seal_record["proposal_run_id"] == proposal_run_id
    assert seal_record["proposal_checkpoint_sha256"] == proposal_sha256
    assert base64.b64decode(
        seal_record["proposal_authority_b64"].encode("ascii"),
        validate=True,
    ) == proposal_bytes
    decoded_proposal = json.loads(
        base64.b64decode(seal_record["proposal_authority_b64"]).decode("utf-8")
    )
    assert decoded_proposal["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert (
        exact_campaign_module._supervisor_seal_state_violation(
            seal_record,
            state=resumed.state,
        )
        is None
    )
    all_zero_sha_seal = dict(seal_record)
    all_zero_sha_seal["proposal_checkpoint_sha256"] = "0" * 64
    assert (
        exact_campaign_module._supervisor_seal_state_violation(
            all_zero_sha_seal,
            state=resumed.state,
        )
        == "supervisor_seal_proposal_authority_sha256_mismatch"
    )
    fake_run_seal = dict(seal_record)
    fake_run_seal["proposal_run_id"] = "fake-run"
    assert (
        exact_campaign_module._supervisor_seal_state_violation(
            fake_run_seal,
            state=resumed.state,
        )
        == "supervisor_seal_proposal_run_id_mismatch"
    )
    diverged_state = json.loads(json.dumps(resumed.state))
    diverged_state["final_result"]["ghost_rect"]["w"] = 2
    assert (
        exact_campaign_module._supervisor_seal_state_violation(
            seal_record,
            state=diverged_state,
        )
        == "supervisor_seal_transition_mismatch"
    )
    assert len(replay_calls) == 1


def test_resume_false_invalidates_old_proposal_marker(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "resume_false_invalidates_marker")
    old_campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="old-proposal-run",
    )
    old_campaign_instance_id = old_campaign.state[CAMPAIGN_INSTANCE_ID_KEY]
    assert old_campaign.proposal_ready_marker_path.exists()

    fresh = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    assert fresh.state[CAMPAIGN_INSTANCE_ID_KEY] != old_campaign_instance_id
    assert not fresh.proposal_ready_marker_path.exists()
    with pytest.raises(RuntimeError, match="proposal_ready_marker_unreadable"):
        fresh.supervisor_seal()


def test_supervisor_seal_requires_proposal_ready_marker(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_missing_marker")
    campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="missing-marker-run",
        write_marker=False,
    )

    with pytest.raises(RuntimeError, match="proposal_ready_marker_unreadable"):
        campaign.supervisor_seal()

    _assert_supervisor_failure_kept_proposal(campaign)


def test_supervisor_seal_requires_checkpoint_file(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_missing_checkpoint")
    campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="missing-checkpoint-run",
    )
    campaign.path.unlink()

    with pytest.raises(RuntimeError, match="proposal_ready_marker_checkpoint_missing"):
        campaign.supervisor_seal()

    assert campaign.state["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert campaign.state["last_stop_reason"]["status"] == CANDIDATE_PROPOSED_STATUS
    assert not campaign.path.exists()


def test_supervisor_seal_rejects_checkpoint_digest_mismatch(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_digest_mismatch")
    campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="digest-mismatch-run",
    )
    campaign.path.write_text(
        campaign.path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="proposal_ready_marker_checkpoint_sha256_mismatch"):
        campaign.supervisor_seal()

    _assert_supervisor_failure_kept_proposal(campaign)


def test_supervisor_seal_rejects_marker_run_id_mismatch(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_marker_run_id_mismatch")
    campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="proposal-run",
    )
    marker = json.loads(campaign.proposal_ready_marker_path.read_text(encoding="utf-8"))
    marker["run_id"] = "other-run"
    campaign.proposal_ready_marker_path.write_text(json.dumps(marker), encoding="utf-8")

    with pytest.raises(RuntimeError, match="proposal_ready_marker_run_id_mismatch"):
        campaign.supervisor_seal()

    _assert_supervisor_failure_kept_proposal(campaign)


def test_supervisor_seal_rejects_marker_campaign_instance_id_mismatch(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_marker_instance_mismatch")
    campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="proposal-run",
    )
    marker = json.loads(campaign.proposal_ready_marker_path.read_text(encoding="utf-8"))
    marker[CAMPAIGN_INSTANCE_ID_KEY] = "0" * 32
    campaign.proposal_ready_marker_path.write_text(json.dumps(marker), encoding="utf-8")

    with pytest.raises(RuntimeError, match="proposal_ready_marker_campaign_instance_id_mismatch"):
        campaign.supervisor_seal()

    _assert_supervisor_failure_kept_proposal(campaign)


def test_supervisor_seal_rejects_nonzero_marker_exit_code(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_marker_exit_code")
    campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="proposal-run",
    )
    marker = json.loads(campaign.proposal_ready_marker_path.read_text(encoding="utf-8"))
    marker["exit_code"] = 1
    campaign.proposal_ready_marker_path.write_text(json.dumps(marker), encoding="utf-8")

    with pytest.raises(RuntimeError, match="proposal_ready_marker_exit_code_invalid"):
        campaign.supervisor_seal()

    _assert_supervisor_failure_kept_proposal(campaign)


def test_memory_certified_disk_proposal_does_not_publish_best_result(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "memory_disk_splice")
    campaign, _final_result, _terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="memory-disk-splice-run",
    )
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    campaign.state["last_stop_reason"] = {
        "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        "status": RUN_STATUS_CERTIFIED,
        "updated_at": "2026-06-24T00:00:00Z",
    }

    assert campaign.best_certified_result() is None


def test_supervisor_seal_rechecks_marker_before_mint_and_preserves_concurrent_proposal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_marker_race")
    campaign, _final_result, terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="proposal-p-run",
    )
    _install_supervisor_candidate_generation(monkeypatch)

    def accept_sink_replay_bundle(**_kwargs: Any) -> dict[str, Any]:
        return {
            "evidence": terminal_frontier_evidence,
            "candidate_records": {},
            "sink_replay_violations": {},
            "fixed_witness_publishable": True,
            "fixed_witness_violations": {},
        }

    def accept_terminal_evidence(
        state: Mapping[str, Any],
        *,
        project_root: Path,
        campaign_path: Path | None = None,
        serialized_state_bytes: bytes | None = None,
    ) -> bool:
        del project_root, serialized_state_bytes
        assert state["final_status"] == RUN_STATUS_CERTIFIED
        assert campaign_path is not None
        return True

    def write_concurrent_proposal(
        _scratch_state: Mapping[str, Any],
        *,
        authority_bytes: bytes,
    ) -> None:
        assert json.loads(authority_bytes.decode("utf-8"))["final_status"] == RUN_STATUS_CERTIFIED
        campaign.set_supervisor_proposal_run_id("proposal-q-run")
        campaign.state["final_result"] = dict(
            _proposal_final_result(),
            diagnostic_status="concurrent-q",
        )
        campaign.mark_campaign_stopped(
            TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
            status=CANDIDATE_PROPOSED_STATUS,
        )
        campaign.state["terminal_frontier_evidence"] = terminal_frontier_evidence
        campaign.save()
        campaign.write_proposal_ready_marker(run_id="proposal-q-run", exit_code=0)

    monkeypatch.setattr(
        exact_campaign_module,
        "build_sink_verified_terminal_frontier_evidence",
        accept_sink_replay_bundle,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "terminal_certified_final_result_project_precheck_violation",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        accept_terminal_evidence,
    )
    monkeypatch.setattr(
        campaign,
        "_validate_supervisor_certified_state_before_commit",
        write_concurrent_proposal,
    )

    with pytest.raises(RuntimeError, match="proposal authority changed before mint"):
        campaign.supervisor_seal()

    persisted = json.loads(campaign.path.read_text(encoding="utf-8"))
    marker, violation = load_proposal_ready_marker(
        campaign.proposal_ready_marker_path,
        checkpoint_path=campaign.path,
        expected_run_id="proposal-q-run",
    )
    assert violation is None
    assert marker is not None
    assert persisted["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert persisted["final_result"]["diagnostic_status"] == "concurrent-q"


def test_supervisor_seal_rejects_sink_replay_violations_without_mint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "supervisor_replay_reject")
    campaign, _final_result, terminal_frontier_evidence = _prepare_candidate_proposed_campaign(
        project_root,
        run_id="replay-reject-run",
    )

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
        campaign.supervisor_seal()

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
        campaign.supervisor_seal()

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
            campaign.supervisor_seal()

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
        serialized_state_bytes: bytes | None = None,
    ) -> bool:
        assert serialized_state_bytes is None
        assert campaign_path is not None
        serialized_state = json.loads(Path(campaign_path).read_text(encoding="utf-8"))
        validity_calls.append(
            {
                "final_status": state.get("final_status"),
                "project_root": project_root,
                "campaign_path": campaign_path,
                "serialized_final_status": serialized_state.get("final_status"),
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
        "terminal_certified_final_result_project_precheck_violation",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        reject_terminal_evidence,
    )
    monkeypatch.setattr(
        exact_campaign_module,
        "_terminal_certified_final_result_violation_for_project_authority",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="supervisor_seal rejected terminal CERTIFIED evidence"):
        campaign.supervisor_seal()

    assert validity_calls == [
        {
            "final_status": RUN_STATUS_CERTIFIED,
            "project_root": project_root,
            "campaign_path": validity_calls[0]["campaign_path"],
            "serialized_final_status": RUN_STATUS_CERTIFIED,
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
