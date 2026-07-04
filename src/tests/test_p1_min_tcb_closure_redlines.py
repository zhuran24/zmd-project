from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.generate_pr2_dependency_floor_manifest import build_manifest
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search import exact_campaign as exact_campaign_module
from src.search import pr2_l0_micro_verifier_core as l0_module
from src.search.candidate_proof_replay import (
    CANDIDATE_PROOF_FIELD,
    canonical_digest as replay_canonical_digest,
)
from src.search.exact_campaign import (
    CAMPAIGN_INSTANCE_ID_KEY,
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    SUPERVISOR_PROPOSAL_STATE_KEY,
    SUPERVISOR_SEAL_STATE_KEY,
)
from src.search.terminal_fixed_witness_capsule import (
    build_terminal_fixed_witness_projection_at_sink,
)
from src.search.terminal_fixed_witness_verifier import (
    TERMINAL_FIXED_WITNESS_AUDIT_FIELD,
    TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD,
    TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD,
    TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD,
)
from src.tests.test_exact_contract import _build_toy_exact_project
from src.tests.test_p1_2_supervisor_pr1 import _run_toy_candidate_proposal


GOLDEN_CANDIDATE_REPLAY_RECORDS_DIGEST = (
    "cd9db9b2f68c053759f948581d02ea4af781afe3c19398ed443462af328064c5"
)
GOLDEN_FIXED_WITNESS_PROJECTION_DIGEST = (
    "a1770e6d14dd400dd62b38cbbb7ac5a4e8fd4ec0a9a57b323022011b177c08fa"
)
GOLDEN_TERMINAL_FRONTIER_EVIDENCE_DIGEST = (
    "9ad6f5d08fe9ccc940f284f27e47f2ecdcab996ba505dee18d1db67480d86f6e"
)

_FORBIDDEN_TARGET_MODULES = (
    "src.search.certified_frontier",
    "src.search.exact_campaign",
    "src.search.terminal_fixed_witness_capsule",
)
_VOLATILE_RECORD_KEYS = frozenset(
    {
        "core_build_seconds",
        "cut_replay_seconds",
        "deterministic_time",
        "finished_at",
        "ghost_constraint_seconds",
        "observed_at",
        "overlay_build_seconds",
        "routing_core_build_seconds",
        "routing_overlay_build_seconds",
        "started_at",
        "updated_at",
        "user_time",
        "wall_time",
    }
)
_FIXED_WITNESS_PROJECTION_FIELDS = frozenset(
    {
        "candidate_records",
        "durable_candidate_records",
        "candidate_key",
        "publishable",
        "projected_status",
        "rejected_reason",
        "verdict",
        "capsule_response",
    }
)
_FIXED_WITNESS_CAPSULE_RESPONSE_FIELDS = (
    "schema_version",
    "authority",
    "project_root",
    "artifact_hashes",
    "source_digest",
)
_FIXED_WITNESS_VERDICT_FIELDS = (
    "schema_version",
    "authority",
    "publishable",
    "projected_status",
    "candidate_key",
    "solution_digest",
    "ghost_rect_digest",
    "ghost_cells_digest",
    "witness_input_digest",
    "binding_assignment_digest",
    "port_specs_digest",
    "routing_occupancy_digest",
    "binding_status",
    "routing_status",
    "reason",
    "details",
)
_FIXED_WITNESS_RECORD_TERMINAL_FIELDS = (
    TERMINAL_FIXED_WITNESS_PUBLISHABLE_FIELD,
    TERMINAL_FIXED_WITNESS_PROJECTED_STATUS_FIELD,
    TERMINAL_FIXED_WITNESS_REJECTED_REASON_FIELD,
)


@pytest.fixture(scope="session")
def _host_dependency_floor_manifest(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, int, str]:
    manifest_path = tmp_path_factory.mktemp("p1_min_tcb_floor") / "manifest.json"
    raw = (
        json.dumps(build_manifest(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    manifest_path.write_bytes(raw)
    return manifest_path, len(raw), hashlib.sha256(raw).hexdigest()


@pytest.fixture(autouse=True)
def _host_floor_patched(
    monkeypatch: pytest.MonkeyPatch,
    _host_dependency_floor_manifest: tuple[Path, int, str],
) -> None:
    """These redlines exercise seal semantics, not the production Linux floor."""

    manifest_path, size_bytes, sha256 = _host_dependency_floor_manifest
    monkeypatch.setattr(l0_module, "DEPENDENCY_FLOOR_MANIFEST_REL", str(manifest_path))
    monkeypatch.setattr(l0_module, "DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES", size_bytes)
    monkeypatch.setattr(l0_module, "DEPENDENCY_FLOOR_MANIFEST_SHA256", sha256)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _normalize_path_bound_values(
    payload: Any,
    *,
    project_root: Path,
    campaign_path: Path,
) -> Any:
    if isinstance(payload, dict):
        normalized: dict[str, Any] = {}
        for key, value in payload.items():
            key_str = str(key)
            if key_str in _VOLATILE_RECORD_KEYS:
                normalized[key_str] = "<VOLATILE>"
            else:
                normalized[key_str] = _normalize_path_bound_values(
                    value,
                    project_root=project_root,
                    campaign_path=campaign_path,
                )
        return normalized
    if isinstance(payload, list):
        return [
            _normalize_path_bound_values(
                value,
                project_root=project_root,
                campaign_path=campaign_path,
            )
            for value in payload
        ]
    if isinstance(payload, str):
        return payload.replace(
            str(campaign_path.resolve()),
            "<CAMPAIGN_PATH>",
        ).replace(str(project_root.resolve()), "<PROJECT_ROOT>")
    return payload


def _stable_candidate_records_digest(
    records: dict[str, Any],
    *,
    project_root: Path,
    campaign_path: Path,
) -> str:
    projected = l0_module._stable_fixed_witness_candidate_records_l0(records)  # type: ignore[attr-defined]
    normalized = _normalize_path_bound_values(
        projected,
        project_root=project_root,
        campaign_path=campaign_path,
    )
    if isinstance(normalized, dict):
        for record in normalized.values():
            if not isinstance(record, dict):
                continue
            proof = record.get(CANDIDATE_PROOF_FIELD)
            if not isinstance(proof, dict):
                continue
            campaign_context = proof.get("campaign_context")
            if isinstance(campaign_context, dict):
                proof["campaign_context_digest"] = l0_module._canonical_digest(  # type: ignore[attr-defined]
                    campaign_context
                )
            request_without_digest = dict(proof)
            request_without_digest.pop("request_digest", None)
            proof["request_digest"] = l0_module._canonical_digest(  # type: ignore[attr-defined]
                request_without_digest
            )
    return l0_module._canonical_digest(  # type: ignore[attr-defined]
        normalized
    )


def _stable_fixed_witness_verdict_payload(
    verdict: Any,
    *,
    project_root: Path,
    campaign_path: Path,
) -> dict[str, Any]:
    payload = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict)
    fresh_run_token = payload.pop("fresh_run_token", None)
    if fresh_run_token is not None:
        assert isinstance(fresh_run_token, str) and fresh_run_token
    assert set(payload) == set(_FIXED_WITNESS_VERDICT_FIELDS)
    return {
        field: _normalize_path_bound_values(
            payload[field],
            project_root=project_root,
            campaign_path=campaign_path,
        )
        for field in _FIXED_WITNESS_VERDICT_FIELDS
    }


def _fixed_witness_fresh_run_token_present(verdict: Any) -> bool:
    payload = verdict.to_dict() if hasattr(verdict, "to_dict") else dict(verdict)
    return isinstance(payload.get("fresh_run_token"), str) and bool(
        payload["fresh_run_token"]
    )


def _stable_fixed_witness_capsule_response_payload(
    response: Any,
    *,
    project_root: Path,
    campaign_path: Path,
) -> dict[str, Any]:
    payload = dict(response)
    expected_fields = set(_FIXED_WITNESS_CAPSULE_RESPONSE_FIELDS) | {
        "nonce",
        "verdict",
    }
    assert set(payload) == expected_fields
    nonce = payload["nonce"]
    assert isinstance(nonce, str) and nonce
    return {
        **{
            field: _normalize_path_bound_values(
                payload[field],
                project_root=project_root,
                campaign_path=campaign_path,
            )
            for field in _FIXED_WITNESS_CAPSULE_RESPONSE_FIELDS
        },
        "nonce_present": True,
        "verdict_fresh_run_token_present": _fixed_witness_fresh_run_token_present(
            payload["verdict"]
        ),
        "verdict": _stable_fixed_witness_verdict_payload(
            payload["verdict"],
            project_root=project_root,
            campaign_path=campaign_path,
        ),
    }


def _fixed_witness_record_terminal_payload(
    records: dict[str, Any],
    *,
    candidate_key: str,
    project_root: Path,
    campaign_path: Path,
) -> dict[str, Any]:
    record = records[candidate_key]
    proof_summary = record["proof_summary"]
    audit = proof_summary[TERMINAL_FIXED_WITNESS_AUDIT_FIELD]
    return {
        "status": record.get("status"),
        "terminal_fields": {
            field: proof_summary.get(field)
            for field in _FIXED_WITNESS_RECORD_TERMINAL_FIELDS
        },
        "audit": _stable_fixed_witness_verdict_payload(
            audit,
            project_root=project_root,
            campaign_path=campaign_path,
        ),
    }


def _stable_fixed_witness_projection_payload(
    projection: Any,
    *,
    project_root: Path,
    campaign_path: Path,
) -> dict[str, Any]:
    assert set(vars(projection)) == _FIXED_WITNESS_PROJECTION_FIELDS
    candidate_key = projection.candidate_key
    assert isinstance(candidate_key, str) and candidate_key
    verdict = _stable_fixed_witness_verdict_payload(
        projection.verdict,
        project_root=project_root,
        campaign_path=campaign_path,
    )
    capsule_response = _stable_fixed_witness_capsule_response_payload(
        projection.capsule_response,
        project_root=project_root,
        campaign_path=campaign_path,
    )
    assert capsule_response["verdict"] == verdict
    projected_record = _fixed_witness_record_terminal_payload(
        projection.candidate_records,
        candidate_key=candidate_key,
        project_root=project_root,
        campaign_path=campaign_path,
    )
    durable_record = _fixed_witness_record_terminal_payload(
        projection.durable_candidate_records,
        candidate_key=candidate_key,
        project_root=project_root,
        campaign_path=campaign_path,
    )
    assert projected_record["audit"] == verdict
    assert durable_record["audit"] == verdict
    return {
        "projection_fields": sorted(_FIXED_WITNESS_PROJECTION_FIELDS),
        "candidate_key": candidate_key,
        "publishable": projection.publishable,
        "projected_status": projection.projected_status,
        "rejected_reason": projection.rejected_reason,
        "verdict_fresh_run_token_present": _fixed_witness_fresh_run_token_present(
            projection.verdict
        ),
        "verdict": verdict,
        "capsule_response": capsule_response,
        "candidate_records_digest": _stable_candidate_records_digest(
            projection.candidate_records,
            project_root=project_root,
            campaign_path=campaign_path,
        ),
        "durable_candidate_records_digest": _stable_candidate_records_digest(
            projection.durable_candidate_records,
            project_root=project_root,
            campaign_path=campaign_path,
        ),
        "projected_record_terminal": projected_record,
        "durable_record_terminal": durable_record,
    }


def _stable_fixed_witness_projection_digest(
    projection: Any,
    *,
    project_root: Path,
    campaign_path: Path,
) -> str:
    return l0_module._canonical_digest(  # type: ignore[attr-defined]
        _stable_fixed_witness_projection_payload(
            projection,
            project_root=project_root,
            campaign_path=campaign_path,
        )
    )


def _prepare_real_toy_proposal(project_root: Path) -> ExactCampaign:
    _build_toy_exact_project(project_root)
    _run_toy_candidate_proposal(project_root)
    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )
    assert campaign.state["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert campaign.state["final_result"]["search_status"] == CANDIDATE_PROPOSED_STATUS
    return campaign


def _rewrite_proposal_and_marker(campaign: ExactCampaign) -> None:
    run_id = campaign.state[SUPERVISOR_PROPOSAL_STATE_KEY]["run_id"]
    exact_campaign_module.atomic_write_json(campaign.path, campaign.state)
    campaign.write_proposal_ready_marker(run_id=run_id, exit_code=0)


def _run_l0_supervisor_seal(campaign: ExactCampaign) -> l0_module.L0MicroVerdict:
    return l0_module.run_l0_supervisor_seal(
        l0_module.L0SupervisorSealRequest(
            project_root=campaign.project_root,
            campaign_path=campaign.path,
            marker_path=campaign.proposal_ready_marker_path,
            expected_campaign_instance_id=campaign.state[CAMPAIGN_INSTANCE_ID_KEY],
            timeout_seconds=120.0,
        )
    )


def _assert_rejected_without_durable_certified(
    campaign: ExactCampaign,
    verdict: l0_module.L0MicroVerdict,
    *,
    reason_tokens: tuple[str, ...],
) -> None:
    assert verdict.status == l0_module.REJECTED
    for token in reason_tokens:
        assert token in verdict.reason
    persisted = _load_json(campaign.path)
    assert persisted["final_status"] == CANDIDATE_PROPOSED_STATUS
    assert persisted["last_stop_reason"]["status"] == CANDIDATE_PROPOSED_STATUS
    assert persisted["final_result"]["search_status"] == CANDIDATE_PROPOSED_STATUS
    assert SUPERVISOR_SEAL_STATE_KEY not in persisted


def _refresh_candidate_proof_solution_digest(record: dict[str, Any]) -> None:
    proof = record[CANDIDATE_PROOF_FIELD]
    proof["solution_digest"] = replay_canonical_digest(record["solution"])
    request_without_digest = dict(proof)
    request_without_digest.pop("request_digest", None)
    proof["request_digest"] = replay_canonical_digest(request_without_digest)


def _mutate_forged_candidate_proof(state: dict[str, Any]) -> None:
    state["candidates"]["1x1"][CANDIDATE_PROOF_FIELD][
        "authority"
    ] = "forged_candidate_proof"


def _mutate_wrong_solution_digest(state: dict[str, Any]) -> None:
    state["candidates"]["1x1"][CANDIDATE_PROOF_FIELD]["solution_digest"] = "0" * 64


def _mutate_wrong_artifact_hash(state: dict[str, Any]) -> None:
    artifact_hashes = state["candidates"]["1x1"][CANDIDATE_PROOF_FIELD][
        "artifact_hashes"
    ]
    artifact_hashes[sorted(artifact_hashes)[0]] = "0" * 64


def _mutate_binding_infeasible_witness(state: dict[str, Any]) -> None:
    record = state["candidates"]["1x1"]
    state["final_result"]["placement_solution"]["tiny_001"]["pose_idx"] = 99
    record["solution"]["tiny_001"]["pose_idx"] = 99
    _refresh_candidate_proof_solution_digest(record)


def _mutate_routing_blocked_witness(state: dict[str, Any]) -> None:
    state["final_result"]["ghost_rect"]["anchor_x"] = 0


def _mutate_connector_body_claim(state: dict[str, Any]) -> None:
    audit = state["candidates"]["1x1"]["proof_summary"][
        TERMINAL_FIXED_WITNESS_AUDIT_FIELD
    ]
    audit["publishable"] = False
    audit["reason"] = "terminal_fixed_witness_connector_cell_occupied_by_other_body"


def _mutate_sliced_candidate_generation(state: dict[str, Any]) -> None:
    state["terminal_frontier_evidence"]["candidate_generation"]["max_w"] = 1


def _mutate_source_digest_drift(state: dict[str, Any]) -> None:
    state["candidates"]["1x1"][CANDIDATE_PROOF_FIELD]["source_digest"] = "0" * 64


_MaliciousMutator = Callable[[dict[str, Any]], None]

MALICIOUS_FIXTURES = (
    pytest.param(
        "forged candidate proof",
        _mutate_forged_candidate_proof,
        ("terminal candidate sink replay failed", "candidate_sink_replay_authority_invalid"),
        id="forged-candidate-proof",
    ),
    pytest.param(
        "wrong solution digest",
        _mutate_wrong_solution_digest,
        (
            "terminal candidate sink replay failed",
            "candidate_sink_replay_solution_binding_mismatch",
        ),
        id="wrong-solution-digest",
    ),
    pytest.param(
        "wrong artifact hash",
        _mutate_wrong_artifact_hash,
        (
            "terminal candidate sink replay failed",
            "candidate_sink_replay_artifact_binding_mismatch",
        ),
        id="wrong-artifact-hash",
    ),
    # Known weak fixture: it currently collapses to a broad fixed-witness
    # exception, not a precise binding infeasibility verdict.
    pytest.param(
        "binding infeasible witness",
        _mutate_binding_infeasible_witness,
        ("terminal fixed witness verifier failed", "terminal_fixed_witness_exception"),
        id="binding-infeasible",
    ),
    # Known weak fixture: it currently collapses to a broad fixed-witness
    # exception, not a precise routing infeasibility verdict.
    pytest.param(
        "routing blocked / disconnected witness",
        _mutate_routing_blocked_witness,
        ("terminal fixed witness verifier failed", "terminal_fixed_witness_exception"),
        id="routing-blocked",
    ),
    # Known weak fixture: this mutates the audit claim to trigger a candidate
    # records mismatch; it is not yet a real connector/body physical construction.
    pytest.param(
        "connector body occupied claim",
        _mutate_connector_body_claim,
        ("proposal candidate_records mismatch after domain verification",),
        id="connector-body-occupied",
    ),
    pytest.param(
        "sliced candidate generation domain",
        _mutate_sliced_candidate_generation,
        (
            "terminal project precheck failed",
            "terminal_frontier_candidate_generation_grid_mismatch",
        ),
        id="sliced-candidate-generation",
    ),
    pytest.param(
        "source digest drift",
        _mutate_source_digest_drift,
        (
            "terminal candidate sink replay failed",
            "candidate_sink_replay_source_binding_mismatch",
        ),
        id="source-digest-drift",
    ),
)


def test_golden_toy_supervisor_seal_semantic_digests(tmp_path: Path) -> None:
    project_root = tmp_path / "golden_toy_supervisor_seal"
    campaign = _prepare_real_toy_proposal(project_root)
    proposal_state = _load_json(campaign.path)
    proposal_bytes = campaign.path.read_bytes()

    projection = build_terminal_fixed_witness_projection_at_sink(
        state=proposal_state,
        project_root=project_root,
        campaign_path=campaign.path,
        candidate_records=json.loads(json.dumps(proposal_state["candidates"])),
        final_result=proposal_state["final_result"],
        serialized_state_bytes=proposal_bytes,
    )

    assert projection.publishable is True
    assert projection.rejected_reason is None
    assert (
        _stable_candidate_records_digest(
            proposal_state["candidates"],
            project_root=project_root,
            campaign_path=campaign.path,
        )
        == GOLDEN_CANDIDATE_REPLAY_RECORDS_DIGEST
    )
    assert (
        _stable_candidate_records_digest(
            projection.durable_candidate_records,
            project_root=project_root,
            campaign_path=campaign.path,
        )
        == GOLDEN_CANDIDATE_REPLAY_RECORDS_DIGEST
    )
    assert (
        _stable_fixed_witness_projection_digest(
            projection,
            project_root=project_root,
            campaign_path=campaign.path,
        )
        == GOLDEN_FIXED_WITNESS_PROJECTION_DIGEST
    )
    assert (
        l0_module._canonical_digest(proposal_state["terminal_frontier_evidence"])  # type: ignore[attr-defined]
        == GOLDEN_TERMINAL_FRONTIER_EVIDENCE_DIGEST
    )

    campaign.supervisor_seal()
    sealed_state = _load_json(campaign.path)

    assert sealed_state["final_status"] == RUN_STATUS_CERTIFIED
    assert sealed_state["final_result"]["search_status"] == RUN_STATUS_CERTIFIED
    assert SUPERVISOR_SEAL_STATE_KEY in sealed_state
    assert (
        _stable_candidate_records_digest(
            sealed_state["candidates"],
            project_root=project_root,
            campaign_path=campaign.path,
        )
        == GOLDEN_CANDIDATE_REPLAY_RECORDS_DIGEST
    )
    assert (
        l0_module._canonical_digest(sealed_state["terminal_frontier_evidence"])  # type: ignore[attr-defined]
        == GOLDEN_TERMINAL_FRONTIER_EVIDENCE_DIGEST
    )


@pytest.mark.parametrize(
    ("case_name", "mutate", "reason_tokens"),
    MALICIOUS_FIXTURES,
)
def test_malicious_fixture_fail_closed(
    tmp_path: Path,
    case_name: str,
    mutate: _MaliciousMutator,
    reason_tokens: tuple[str, ...],
) -> None:
    project_root = tmp_path / case_name.replace(" ", "_").replace("/", "_")
    campaign = _prepare_real_toy_proposal(project_root)

    mutate(campaign.state)
    _rewrite_proposal_and_marker(campaign)

    verdict = _run_l0_supervisor_seal(campaign)

    _assert_rejected_without_durable_certified(
        campaign,
        verdict,
        reason_tokens=reason_tokens,
    )


@pytest.mark.xfail(reason="#1 抽 core 后转 pass", strict=False)
def test_target_l0_child_runtime_excludes_scripts_from_snapshot() -> None:
    source_root = Path(l0_module.__file__).resolve().parents[2]
    snapshot_modules = l0_module._discover_project_snapshot_modules(source_root)  # type: ignore[attr-defined]

    verdict = l0_module.run_l0_micro_verifier_round_trip(
        {"action": "probe_import", "module": "scripts.run_supervisor_seal"},
        extra_snapshot_modules=snapshot_modules,
        timeout_seconds=30.0,
    )

    assert verdict.status == l0_module.REJECTED
    assert "ModuleNotFoundError" in verdict.reason


@pytest.mark.xfail(reason="#1 抽 core 后转 pass", strict=False)
def test_target_l0_snapshot_manifest_is_explicit_minimal_whitelist() -> None:
    source_root = Path(l0_module.__file__).resolve().parents[2]
    snapshot_modules = set(l0_module._discover_project_snapshot_modules(source_root))  # type: ignore[attr-defined]

    assert snapshot_modules.isdisjoint(_FORBIDDEN_TARGET_MODULES)
    assert not any(module.startswith("scripts.") for module in snapshot_modules)
    assert len(snapshot_modules) < 120
