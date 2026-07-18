"""Central verifier for public certified delivery surfaces.

The exact campaign checkpoint can contain terminal proof evidence, but that
checkpoint alone is not a publishable delivery surface.  Public readers must use
this module's verdict, which binds the checkpoint, exact-artifact hashes,
final_solution.json, optimal_blueprint.json, and certified_delivery_manifest.json
into one fail-closed currentness contract.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.io.delivery_manifest import (
    build_certified_delivery_manifest,
    delivery_manifest_output_path,
    validate_certified_delivery_manifest_matches_campaign,
    validate_delivery_artifacts_match_campaign,
)
from src.io.output_schema import blueprint_output_path
from src.io.serializer import (
    build_blueprint_payload_from_certified_result,
)
from src.search.exact_campaign import (
    DEFAULT_CAMPAIGN_FILENAME,
    PROOF_BEARING_TERMINAL_STATUSES,
    _path_has_symlink_component,
    atomic_write_json,
    compute_exact_artifact_hashes,
    has_certified_export_surface,
    has_terminal_full_frontier_certified_evidence,
    has_valid_terminal_full_frontier_certified_evidence_for_project,
    validate_exact_campaign_resume_state,
)
from src.search.terminal_fixed_witness_verifier import (
    _load_grid_dimensions,
    extract_verified_terminal_active_port_specs,
)

CERTIFIED_SURFACE_VERIFIER_SOURCE = "certified_surface_verifier_v1"
CERTIFIED_SURFACE_BLOCKED_REASON = "certified_delivery_surface_not_current"
P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX = "p1_2_publish_open_gate_open"
P1_2_PUBLISH_GATE_ID = "phase_1_2_spike_close"
P1_2_PUBLISH_GATE_CLOSED_STATUS = "closed_manual_owner_decision"
# The runtime publish authority below must enforce the SAME owner-closed invariants
# as the authoritative phase-review gate checker (scripts/check_phase_review_gate.py),
# otherwise a gate that satisfies only the coarse publish fields but omits the owner
# counting authority / approved review anchor / explicit decision acknowledgements
# would open publication here while the authoritative checker rejects it (split-brain).
# These constants are pinned equal to the checker's by
# test_publish_open_gate_matches_authoritative_gate_constants.
_P1_2_GATE_COUNTING_AUTHORITY = "owner_manual_count_outside_repo"
_P1_2_GATE_APPROVED_REVIEW_ANCHOR = "v99_p1_2_close_kernel_sealing"
_P1_2_GATE_OWNER_CLEAN_COUNT_STATUS = "maintained_outside_repo"


@dataclass(frozen=True)
class CertifiedSurfaceVerdict:
    """Single public CERTIFIED verdict shared by inspector, manifest readers, and B5A."""

    publishable: bool
    blocked_reason: Optional[str]
    campaign_present: bool
    campaign_resume_compatible: bool
    campaign_resume_validation_reason: Optional[str]
    campaign_terminal_full_frontier_claimed: bool
    campaign_terminal_full_frontier_valid: bool
    final_delivery_artifacts_current: bool
    final_delivery_artifacts_error: Optional[str]
    delivery_manifest_present: bool
    delivery_manifest_regular_file: bool
    delivery_manifest_load_error: Optional[str]
    delivery_manifest_terminal_full_frontier_claimed: bool
    delivery_manifest_current: bool
    delivery_manifest_error: Optional[str]
    best_certified_result: Optional[Dict[str, Any]]
    delivery_manifest_payload: Optional[Dict[str, Any]]
    final_solution_payload: Optional[Dict[str, Any]] = None
    optimal_blueprint_payload: Optional[Dict[str, Any]] = None
    publish_open_gate_open: bool = False
    publish_open_gate_reason: Optional[str] = None

    @property
    def reason(self) -> Optional[str]:
        return self.blocked_reason

    @property
    def resume_validation_reason(self) -> Optional[str]:
        return self.campaign_resume_validation_reason

    @property
    def resume_compatible_with_current_hashes(self) -> bool:
        return self.campaign_resume_compatible

    @property
    def terminal_full_frontier_certified(self) -> bool:
        return self.publishable

    @property
    def delivery_manifest_currentness_reason(self) -> Optional[str]:
        return self.delivery_manifest_error or self.blocked_reason

    def as_summary(self) -> Dict[str, Any]:
        return {
            "source": CERTIFIED_SURFACE_VERIFIER_SOURCE,
            "publishable": bool(self.publishable),
            "public_certified": bool(self.publishable),
            "terminal_full_frontier_certified": bool(self.publishable),
            "blocked_reason": self.blocked_reason,
            "reason": self.blocked_reason,
            "campaign_present": bool(self.campaign_present),
            "campaign_resume_compatible": bool(self.campaign_resume_compatible),
            "campaign_resume_validation_reason": self.campaign_resume_validation_reason,
            "campaign_terminal_full_frontier_claimed": bool(
                self.campaign_terminal_full_frontier_claimed
            ),
            "campaign_terminal_full_frontier_valid": bool(
                self.campaign_terminal_full_frontier_valid
            ),
            "final_delivery_artifacts_current": bool(self.final_delivery_artifacts_current),
            "final_delivery_artifacts_error": self.final_delivery_artifacts_error,
            "delivery_manifest_present": bool(self.delivery_manifest_present),
            "delivery_manifest_regular_file": bool(self.delivery_manifest_regular_file),
            "delivery_manifest_load_error": self.delivery_manifest_load_error,
            "delivery_manifest_terminal_full_frontier_claimed": bool(
                self.delivery_manifest_terminal_full_frontier_claimed
            ),
            "delivery_manifest_current": bool(self.delivery_manifest_current),
            "delivery_manifest_error": self.delivery_manifest_error,
            "best_certified_result_present": self.best_certified_result is not None,
            "final_solution_snapshot_present": self.final_solution_payload is not None,
            "optimal_blueprint_snapshot_present": self.optimal_blueprint_payload is not None,
            "publish_open_gate_open": bool(self.publish_open_gate_open),
            "publish_open_gate_reason": self.publish_open_gate_reason,
        }

    def as_dict(self) -> Dict[str, Any]:
        return self.as_summary()


@dataclass(frozen=True)
class _StagedCertifiedDeliverySurfaceArtifacts:
    final_solution_path: Path
    blueprint_path: Path
    manifest_path: Path
    stage_dirs: tuple[Path, ...]


@dataclass(frozen=True)
class _CertifiedDeliverySurfaceBackup:
    target_to_backup: Dict[Path, Optional[Path]]
    backup_dirs: tuple[Path, ...]


# Backward-compatible alias for earlier in-flight patch attempts.
CertifiedSurfaceVerification = CertifiedSurfaceVerdict


def evaluate_certified_delivery_surface(
    *,
    project_root: Path,
    campaign_state: Optional[Mapping[str, Any]],
    campaign_path: Optional[Path] = None,
    delivery_manifest: Optional[Mapping[str, Any]] = None,
    delivery_manifest_error: Optional[str] = None,
    delivery_manifest_load_error: Optional[str] = None,
    campaign_resume_compatible: Optional[bool] = None,
    resume_validation_reason: Optional[str] = None,
    current_hashes: Optional[Mapping[str, str]] = None,
    current_hash_error: Optional[str] = None,
) -> CertifiedSurfaceVerdict:
    """Return the sole publishable CERTIFIED verdict for public read surfaces.

    A publishable verdict means all of these are true at the same time:
    current exact artifacts match the campaign checkpoint, terminal full-frontier
    evidence is valid, final_solution and optimal_blueprint are current raw
    projections of final_result, and the delivery manifest revalidates against
    that same checkpoint/artifact set.  Missing, stale, malformed, symlinked, or
    contradictory members all fail closed.
    """

    project_root = Path(project_root).resolve()
    manifest_path = delivery_manifest_output_path(project_root)
    manifest_load_error = delivery_manifest_load_error or delivery_manifest_error
    manifest_payload, manifest_error, manifest_regular_file = _resolve_manifest_payload(
        manifest_path=manifest_path,
        delivery_manifest=delivery_manifest,
        delivery_manifest_load_error=manifest_load_error,
    )
    manifest_present = manifest_payload is not None and manifest_error is None

    campaign_payload, campaign_error = _resolve_campaign_state_payload(
        project_root=project_root,
        campaign_state=campaign_state,
        campaign_path=campaign_path,
    )
    if campaign_state is None and campaign_payload is not None and campaign_error is None:
        campaign_state = campaign_payload
    elif campaign_state is None:
        return _blocked(
            campaign_error or "campaign_state_missing",
            campaign_present=False,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            delivery_manifest_payload=manifest_payload,
        )
    if campaign_error is not None:
        summary_state = campaign_payload if campaign_payload is not None else _mapping_or_none(campaign_state)
        campaign_terminal_claimed = bool(
            has_terminal_full_frontier_certified_evidence(summary_state)
            if summary_state is not None
            else False
        )
        return _blocked(
            campaign_error,
            campaign_present=campaign_payload is not None,
            campaign_resume_compatible=False,
            campaign_resume_validation_reason=campaign_error,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            # A missing, mismatched, non-canonical, or non-regular checkpoint is
            # never valid terminal evidence.  Structural self-consistency is not
            # a substitute for the project-bound sink replay below.
            campaign_terminal_full_frontier_valid=False,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            delivery_manifest_payload=manifest_payload,
        )
    # Memory and disk are both untrusted representations.  Caller payloads are
    # accepted only as currentness witnesses above; all authority below is the
    # strict plain dict loaded from the canonical checkpoint bytes.
    campaign_state = campaign_payload if campaign_payload is not None else campaign_state

    resolved_resume_reason = _resolve_resume_validation_reason(
        project_root=project_root,
        campaign_state=campaign_state,
        current_hashes=current_hashes,
        current_hash_error=current_hash_error,
        campaign_resume_compatible=campaign_resume_compatible,
        resume_validation_reason=resume_validation_reason,
    )
    resume_current = resolved_resume_reason is None
    campaign_terminal_claimed = has_terminal_full_frontier_certified_evidence(campaign_state)
    resolved_campaign_path = _resolve_campaign_path(
        project_root=project_root,
        campaign_path=campaign_path,
    )
    campaign_terminal_valid = has_valid_terminal_full_frontier_certified_evidence_for_project(
        campaign_state,
        project_root=project_root,
        campaign_path=resolved_campaign_path,
    )

    if not resume_current:
        return _blocked(
            resolved_resume_reason or "campaign_resume_incompatible",
            campaign_present=True,
            campaign_resume_compatible=False,
            campaign_resume_validation_reason=resolved_resume_reason,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=campaign_terminal_valid,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            delivery_manifest_payload=manifest_payload,
        )

    best_certified_result = _mapping_or_none(campaign_state.get("final_result"))
    if not campaign_terminal_valid:
        return _blocked(
            "campaign_terminal_full_frontier_evidence_invalid",
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=False,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
        )

    if best_certified_result is None:
        return _blocked(
            "campaign_final_result_missing",
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=True,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            delivery_manifest_payload=manifest_payload,
        )

    try:
        validate_delivery_artifacts_match_campaign(
            project_root=project_root,
            campaign_state=campaign_state,
        )
    except Exception as exc:  # noqa: BLE001 - public verifier reports fail-closed reason.
        final_artifacts_error = f"delivery_artifacts_not_current:{type(exc).__name__}"
        return _blocked(
            final_artifacts_error,
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=False,
            final_delivery_artifacts_error=final_artifacts_error,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
        )

    if manifest_payload is None:
        missing_reason = manifest_error or "delivery_manifest_missing"
        return _blocked(
            missing_reason,
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=True,
            final_delivery_artifacts_error=None,
            delivery_manifest_present=False,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=None,
        )

    if not manifest_regular_file:
        return _blocked(
            "delivery_manifest_not_regular_file",
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=True,
            final_delivery_artifacts_error=None,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=False,
            delivery_manifest_load_error=manifest_error,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
        )

    if manifest_error is not None:
        return _blocked(
            manifest_error,
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=True,
            final_delivery_artifacts_error=None,
            delivery_manifest_present=True,
            delivery_manifest_regular_file=True,
            delivery_manifest_load_error=manifest_error,
            delivery_manifest_terminal_full_frontier_claimed=False,
            delivery_manifest_current=False,
            delivery_manifest_error=manifest_error,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
        )

    manifest_terminal_claimed = _manifest_claims_terminal_certified(manifest_payload)
    if not manifest_terminal_claimed:
        return _blocked(
            "delivery_manifest_terminal_full_frontier_evidence_invalid",
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=True,
            final_delivery_artifacts_error=None,
            delivery_manifest_present=True,
            delivery_manifest_regular_file=True,
            delivery_manifest_load_error=None,
            delivery_manifest_terminal_full_frontier_claimed=False,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
        )

    try:
        validate_certified_delivery_manifest_matches_campaign(
            project_root=project_root,
            delivery_manifest=manifest_payload,
            campaign_state=campaign_state,
            campaign_path=campaign_path,
        )
    except Exception as exc:  # noqa: BLE001 - public verifier reports fail-closed reason.
        manifest_current_error = f"delivery_manifest_not_current:{type(exc).__name__}"
        return _blocked(
            manifest_current_error,
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=True,
            final_delivery_artifacts_error=None,
            delivery_manifest_present=True,
            delivery_manifest_regular_file=True,
            delivery_manifest_load_error=None,
            delivery_manifest_terminal_full_frontier_claimed=True,
            delivery_manifest_current=False,
            delivery_manifest_error=manifest_current_error,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
        )

    publish_open_gate_open, publish_open_gate_reason = resolve_p1_2_publish_open_gate(
        project_root=project_root,
    )
    if publish_open_gate_open:
        blocked_reason = publish_open_gate_reason or _publish_open_gate_reason("unknown")
        return _blocked(
            blocked_reason,
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=True,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=True,
            final_delivery_artifacts_error=None,
            delivery_manifest_present=True,
            delivery_manifest_regular_file=True,
            delivery_manifest_load_error=None,
            delivery_manifest_terminal_full_frontier_claimed=True,
            delivery_manifest_current=True,
            delivery_manifest_error=None,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
            publish_open_gate_open=True,
            publish_open_gate_reason=blocked_reason,
        )

    snapshot_payloads, snapshot_error = _load_verified_surface_snapshot(
        project_root=project_root,
        delivery_manifest=manifest_payload,
    )
    if snapshot_error is not None or snapshot_payloads is None:
        final_artifacts_error = snapshot_error or "delivery_artifact_snapshot_missing"
        return _blocked(
            final_artifacts_error,
            campaign_present=True,
            campaign_resume_compatible=True,
            campaign_resume_validation_reason=None,
            campaign_terminal_full_frontier_claimed=True,
            campaign_terminal_full_frontier_valid=True,
            final_delivery_artifacts_current=False,
            final_delivery_artifacts_error=final_artifacts_error,
            delivery_manifest_present=True,
            delivery_manifest_regular_file=True,
            delivery_manifest_load_error=None,
            delivery_manifest_terminal_full_frontier_claimed=True,
            delivery_manifest_current=True,
            delivery_manifest_error=None,
            best_certified_result=best_certified_result,
            delivery_manifest_payload=manifest_payload,
        )
    final_solution_payload, optimal_blueprint_payload = snapshot_payloads

    return CertifiedSurfaceVerdict(
        publishable=True,
        blocked_reason=None,
        campaign_present=True,
        campaign_resume_compatible=True,
        campaign_resume_validation_reason=None,
        campaign_terminal_full_frontier_claimed=True,
        campaign_terminal_full_frontier_valid=True,
        final_delivery_artifacts_current=True,
        final_delivery_artifacts_error=None,
        delivery_manifest_present=True,
        delivery_manifest_regular_file=True,
        delivery_manifest_load_error=None,
        delivery_manifest_terminal_full_frontier_claimed=True,
        delivery_manifest_current=True,
        delivery_manifest_error=None,
        best_certified_result=best_certified_result,
        delivery_manifest_payload=manifest_payload,
        final_solution_payload=final_solution_payload,
        optimal_blueprint_payload=optimal_blueprint_payload,
        publish_open_gate_open=False,
        publish_open_gate_reason=None,
    )


# Backward-compatible alias for earlier in-flight patch attempts.
verify_certified_delivery_surface = evaluate_certified_delivery_surface


def resolve_p1_2_publish_open_gate(
    *,
    project_root: Path,
) -> tuple[bool, Optional[str]]:
    """Return whether the manual P1.2 publish gate is open and blocks publication.

    The gate path is NOT a caller-supplied parameter: the public verifier always
    binds to the single authoritative repo file
    ``<project_root>/data/review_gates/phase_1_2_spike_close.json`` so no caller
    can point the publish decision at a forged closed gate.  The only
    publish-allowing state is that authoritative file in the explicit owner-closed
    shape; every missing, malformed, stale, symlinked, contradictory, or
    unexpected shape is treated as open and blocks public CERTIFIED publication.
    """

    try:
        root = Path(project_root).resolve()
        raw_gate_path = root / "data" / "review_gates" / "phase_1_2_spike_close.json"
        if not raw_gate_path.exists():
            return True, _publish_open_gate_reason("missing")
        if not raw_gate_path.is_file() or _path_has_symlink_component(raw_gate_path):
            return True, _publish_open_gate_reason("not_regular_file")

        try:
            gate = _load_strict_json_mapping(raw_gate_path)
        except Exception:  # noqa: BLE001 - strict JSON failures block publication.
            return True, _publish_open_gate_reason("json_error")
        if gate.get("gate_id") != P1_2_PUBLISH_GATE_ID:
            return True, _publish_open_gate_reason("gate_id_mismatch")

        status = gate.get("status")
        if status != P1_2_PUBLISH_GATE_CLOSED_STATUS:
            return True, _publish_open_gate_reason(f"status_{_gate_reason_token(status)}")

        next_phase_entry = gate.get("next_phase_entry")
        next_allowed = (
            next_phase_entry.get("allowed") if isinstance(next_phase_entry, Mapping) else None
        )
        if next_allowed is not True:
            return True, _publish_open_gate_reason("next_phase_not_allowed")

        owner_decision = gate.get("owner_manual_decision")
        if not isinstance(owner_decision, Mapping):
            return True, _publish_open_gate_reason("decision_missing")
        if owner_decision.get("p1_3b_entry_allowed") is not True:
            return True, _publish_open_gate_reason("decision_not_allowed")

        # Split-brain hardening: enforce the SAME owner-closed invariants the
        # authoritative phase-review gate checker requires, so a gate that passes
        # only the coarse fields above (but omits the owner counting authority, the
        # approved review anchor, or the explicit owner decision acknowledgements)
        # cannot open publication here while the authoritative checker rejects it.
        if gate.get("current_review_anchor") != _P1_2_GATE_APPROVED_REVIEW_ANCHOR:
            return True, _publish_open_gate_reason("review_anchor_mismatch")

        owner_state = gate.get("owner_manual_state")
        if not isinstance(owner_state, Mapping):
            return True, _publish_open_gate_reason("owner_state_missing")
        if owner_state.get("counting_authority") != _P1_2_GATE_COUNTING_AUTHORITY:
            return True, _publish_open_gate_reason("owner_state_counting_authority")
        if owner_state.get("current_review_anchor") != _P1_2_GATE_APPROVED_REVIEW_ANCHOR:
            return True, _publish_open_gate_reason("owner_state_review_anchor")
        if owner_state.get("owner_clean_count_status") != _P1_2_GATE_OWNER_CLEAN_COUNT_STATUS:
            return True, _publish_open_gate_reason("owner_state_clean_count_status")
        if owner_state.get("repo_derives_clean_count_from_receipts") is not False:
            return True, _publish_open_gate_reason("owner_state_repo_derives_clean_count")

        if owner_decision.get("counting_authority") != _P1_2_GATE_COUNTING_AUTHORITY:
            return True, _publish_open_gate_reason("decision_counting_authority")
        for _decision_field in ("decision_id", "decided_by", "decided_at", "decision_note"):
            field_value = owner_decision.get(_decision_field)
            if not isinstance(field_value, str) or not field_value.strip():
                return True, _publish_open_gate_reason(f"decision_{_decision_field}_missing")
        if owner_decision.get("acknowledges_repo_does_not_prove_clean_count") is not True:
            return True, _publish_open_gate_reason("decision_ack_repo_not_clean_count")
        if owner_decision.get("acknowledges_owner_verified_three_clean_reviews") is not True:
            return True, _publish_open_gate_reason("decision_ack_three_clean_reviews")

        return False, None
    except Exception:  # noqa: BLE001 - publication governance must fail closed.
        return True, _publish_open_gate_reason("exception")


def certified_delivery_surface_artifact_paths(project_root: Path) -> tuple[Path, Path, Path]:
    project_root = Path(project_root).resolve()
    return (
        project_root / "data" / "solutions" / "final_solution.json",
        blueprint_output_path(project_root),
        delivery_manifest_output_path(project_root),
    )


def clear_certified_delivery_surface_artifacts(project_root: Path) -> None:
    """Remove all files that can advertise a stale certified delivery surface."""

    cleanup_errors: list[str] = []
    for artifact_path in certified_delivery_surface_artifact_paths(project_root):
        try:
            if artifact_path.is_dir() and not artifact_path.is_symlink():
                shutil.rmtree(artifact_path)
            else:
                artifact_path.unlink()
        except FileNotFoundError:
            continue
        except Exception as exc:  # noqa: BLE001 - cleanup must try every artifact.
            cleanup_errors.append(f"{artifact_path}:{type(exc).__name__}:{exc}")
    if cleanup_errors:
        raise RuntimeError(
            "certified delivery surface cleanup failed: " + ";".join(cleanup_errors)
        )


def _remove_artifact_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _cleanup_certified_delivery_surface_temp_dirs(paths: Sequence[Path]) -> None:
    for path in paths:
        try:
            if path.exists():
                shutil.rmtree(path)
        except Exception:
            continue


def _stage_path_for_target(target_path: Path) -> tuple[Path, Path]:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if _path_has_symlink_component(target_path.parent):
        raise RuntimeError("canonical certified surface parent contains symlink")
    stage_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{target_path.name}.stage-",
            dir=str(target_path.parent),
        )
    )
    return stage_dir / target_path.name, stage_dir


def _stage_verified_certified_delivery_surface_artifacts(
    *,
    project_root: Path,
    resolved_campaign_path: Path,
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    final_solution_path: Path,
    blueprint_path: Path,
    manifest_path: Path,
) -> _StagedCertifiedDeliverySurfaceArtifacts:
    staged_final_solution_path, final_stage_dir = _stage_path_for_target(final_solution_path)
    staged_blueprint_path, blueprint_stage_dir = _stage_path_for_target(blueprint_path)
    staged_manifest_path, manifest_stage_dir = _stage_path_for_target(manifest_path)
    staged = _StagedCertifiedDeliverySurfaceArtifacts(
        final_solution_path=staged_final_solution_path,
        blueprint_path=staged_blueprint_path,
        manifest_path=staged_manifest_path,
        stage_dirs=(final_stage_dir, blueprint_stage_dir, manifest_stage_dir),
    )
    try:
        active_port_specs = extract_verified_terminal_active_port_specs(
            campaign_state=state,
            final_result=result,
        )
        atomic_write_json(staged.final_solution_path, result)
        blueprint_payload = build_blueprint_payload_from_certified_result(
            result=result,
            facility_pools=facility_pools,
            active_port_specs=active_port_specs,
            grid_dimensions=_load_grid_dimensions(project_root),
        )
        atomic_write_json(staged.blueprint_path, blueprint_payload)
        manifest_payload = build_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=state,
            campaign_path=resolved_campaign_path,
            final_solution_artifact_path=staged.final_solution_path,
            optimal_blueprint_artifact_path=staged.blueprint_path,
        )
        validate_certified_delivery_manifest_matches_campaign(
            project_root=project_root,
            delivery_manifest=manifest_payload,
            campaign_state=state,
            campaign_path=resolved_campaign_path,
            final_solution_artifact_path=staged.final_solution_path,
            optimal_blueprint_artifact_path=staged.blueprint_path,
        )
        atomic_write_json(staged.manifest_path, manifest_payload)
    except Exception:
        _cleanup_certified_delivery_surface_temp_dirs(staged.stage_dirs)
        raise
    return staged


def _prepare_certified_delivery_surface_backup(
    target_paths: Sequence[Path],
) -> _CertifiedDeliverySurfaceBackup:
    target_to_backup: Dict[Path, Optional[Path]] = {}
    backup_dirs: list[Path] = []
    for target_path in target_paths:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        backup_dir = Path(
            tempfile.mkdtemp(
                prefix=f".{target_path.name}.backup-",
                dir=str(target_path.parent),
            )
        )
        backup_dirs.append(backup_dir)
        backup_path = backup_dir / target_path.name
        if target_path.is_dir() and not target_path.is_symlink():
            shutil.copytree(target_path, backup_path)
            target_to_backup[target_path] = backup_path
        elif target_path.exists() or target_path.is_symlink():
            shutil.copy2(target_path, backup_path, follow_symlinks=False)
            target_to_backup[target_path] = backup_path
        else:
            target_to_backup[target_path] = None
    return _CertifiedDeliverySurfaceBackup(
        target_to_backup=target_to_backup,
        backup_dirs=tuple(backup_dirs),
    )


def _restore_certified_delivery_surface_backup(
    *,
    project_root: Path,
    backup: _CertifiedDeliverySurfaceBackup,
) -> None:
    restore_errors: list[str] = []
    for target_path, backup_path in backup.target_to_backup.items():
        try:
            if target_path.exists() or target_path.is_symlink():
                _remove_artifact_path(target_path)
            if backup_path is None:
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if backup_path.is_dir() and not backup_path.is_symlink():
                shutil.copytree(backup_path, target_path)
            else:
                shutil.copy2(backup_path, target_path, follow_symlinks=False)
        except Exception as exc:  # noqa: BLE001 - every artifact is restored or cleared.
            restore_errors.append(f"{target_path}:{type(exc).__name__}:{exc}")
    if restore_errors:
        try:
            clear_certified_delivery_surface_artifacts(project_root)
        except Exception as cleanup_exc:  # noqa: BLE001
            raise RuntimeError(
                "certified delivery surface rollback failed and fail-closed cleanup failed: "
                f"{';'.join(restore_errors)}; cleanup={cleanup_exc}"
            ) from cleanup_exc
        raise RuntimeError(
            "certified delivery surface rollback failed; public artifacts cleared: "
            + ";".join(restore_errors)
        )


def _discard_certified_delivery_surface_backup(
    backup: Optional[_CertifiedDeliverySurfaceBackup],
) -> None:
    if backup is None:
        return
    _cleanup_certified_delivery_surface_temp_dirs(backup.backup_dirs)


def _commit_staged_certified_delivery_surface_artifacts(
    *,
    project_root: Path,
    staged: _StagedCertifiedDeliverySurfaceArtifacts,
    final_solution_path: Path,
    blueprint_path: Path,
    manifest_path: Path,
) -> _CertifiedDeliverySurfaceBackup:
    target_paths = (final_solution_path, blueprint_path, manifest_path)
    for target_path in target_paths:
        if _path_has_symlink_component(target_path.parent):
            raise RuntimeError("canonical certified surface parent contains symlink")
    backup = _prepare_certified_delivery_surface_backup(target_paths)
    try:
        if final_solution_path.is_dir() and not final_solution_path.is_symlink():
            shutil.rmtree(final_solution_path)
        staged.final_solution_path.replace(final_solution_path)
        if blueprint_path.is_dir() and not blueprint_path.is_symlink():
            shutil.rmtree(blueprint_path)
        staged.blueprint_path.replace(blueprint_path)
        if manifest_path.is_dir() and not manifest_path.is_symlink():
            shutil.rmtree(manifest_path)
        staged.manifest_path.replace(manifest_path)
    except Exception:
        _restore_certified_delivery_surface_backup(
            project_root=project_root,
            backup=backup,
        )
        raise
    return backup


def publish_verified_certified_delivery_surface(
    *,
    project_root: Path,
    campaign_path: Path,
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    campaign_state: Optional[Mapping[str, Any]] = None,
) -> CertifiedSurfaceVerdict:
    """Publish public artifacts only from a sealed, disk-current campaign checkpoint."""

    project_root = Path(project_root).resolve()
    resolved_campaign_path = _resolve_campaign_path(
        project_root=project_root,
        campaign_path=campaign_path,
    )
    staged: Optional[_StagedCertifiedDeliverySurfaceArtifacts] = None
    commit_backup: Optional[_CertifiedDeliverySurfaceBackup] = None
    existing_surface_is_publishable = False
    try:
        existing_surface = evaluate_certified_delivery_surface(
            project_root=project_root,
            campaign_state=None,
            campaign_path=resolved_campaign_path,
        )
        existing_surface_is_publishable = bool(existing_surface.publishable)
        if not existing_surface_is_publishable:
            clear_certified_delivery_surface_artifacts(project_root)

        state = _load_strict_json_mapping(resolved_campaign_path)
        if campaign_state is not None:
            provided_state = _mapping_or_none(campaign_state)
            if provided_state is None:
                raise RuntimeError("campaign_state_missing")
            if not _json_equivalent(provided_state, state):
                raise RuntimeError("campaign_state_payload_mismatch")
        if not has_valid_terminal_full_frontier_certified_evidence_for_project(
            state,
            project_root=project_root,
            campaign_path=resolved_campaign_path,
        ):
            raise RuntimeError("campaign_terminal_full_frontier_evidence_invalid")
        result = _mapping_or_none(state.get("final_result"))
        if result is None:
            raise RuntimeError("campaign_final_result_missing")
        result["search_status"] = "CERTIFIED"
        publish_open_gate_open, publish_open_gate_reason = resolve_p1_2_publish_open_gate(
            project_root=project_root,
        )
        if publish_open_gate_open:
            raise RuntimeError(
                publish_open_gate_reason or _publish_open_gate_reason("unknown")
            )

        final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
        blueprint_path = project_root / "data" / "blueprints" / "optimal_blueprint.json"
        manifest_path = (
            project_root / "data" / "solutions" / "certified_delivery_manifest.json"
        )
        if blueprint_path.resolve() != blueprint_output_path(project_root).resolve():
            raise RuntimeError("canonical blueprint output path mismatch")
        if manifest_path.resolve() != delivery_manifest_output_path(project_root).resolve():
            raise RuntimeError("canonical delivery manifest output path mismatch")

        staged = _stage_verified_certified_delivery_surface_artifacts(
            project_root=project_root,
            resolved_campaign_path=resolved_campaign_path,
            state=state,
            result=result,
            facility_pools=facility_pools,
            final_solution_path=final_solution_path,
            blueprint_path=blueprint_path,
            manifest_path=manifest_path,
        )
        latest_state = _load_strict_json_mapping(resolved_campaign_path)
        if not _json_equivalent(latest_state, state):
            raise RuntimeError("campaign_state_payload_changed_before_commit")
        publish_open_gate_open, publish_open_gate_reason = resolve_p1_2_publish_open_gate(
            project_root=project_root,
        )
        if publish_open_gate_open:
            raise RuntimeError(
                publish_open_gate_reason or _publish_open_gate_reason("unknown")
            )
        commit_backup = _commit_staged_certified_delivery_surface_artifacts(
            project_root=project_root,
            staged=staged,
            final_solution_path=final_solution_path,
            blueprint_path=blueprint_path,
            manifest_path=manifest_path,
        )
        surface = verify_certified_delivery_surface(
            project_root=project_root,
            campaign_state=state,
            campaign_path=resolved_campaign_path,
        )
        if not surface.publishable:
            raise RuntimeError(surface.blocked_reason or CERTIFIED_SURFACE_BLOCKED_REASON)
        _discard_certified_delivery_surface_backup(commit_backup)
        commit_backup = None
    except Exception as exc:  # noqa: BLE001 - publication must fail closed.
        try:
            if commit_backup is not None:
                _restore_certified_delivery_surface_backup(
                    project_root=project_root,
                    backup=commit_backup,
                )
            elif not existing_surface_is_publishable:
                clear_certified_delivery_surface_artifacts(project_root)
        except Exception as rollback_exc:  # noqa: BLE001
            raise RuntimeError(
                "certified delivery surface publication rejected and rollback failed: "
                f"{exc}; rollback={rollback_exc}"
            ) from exc
        raise RuntimeError(
            "certified delivery surface publication rejected: "
            f"{exc}"
        ) from exc
    finally:
        if staged is not None:
            _cleanup_certified_delivery_surface_temp_dirs(staged.stage_dirs)
        _discard_certified_delivery_surface_backup(commit_backup)
    return surface


def save_certified_final_solution_and_blueprint(
    *,
    project_root: Path,
    campaign_path: Path,
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
    campaign_state: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Compatibility wrapper for the verified publisher.

    The old public API accepted an arbitrary result object.  That would let
    producer-side code publish a caller-memory ``CERTIFIED`` value.  The wrapper
    now accepts only campaign authority and delegates to the verifier-backed
    publisher above.
    """

    surface = publish_verified_certified_delivery_surface(
        project_root=project_root,
        campaign_path=campaign_path,
        facility_pools=facility_pools,
        campaign_state=campaign_state,
    )
    if not surface.publishable:
        raise RuntimeError("certified delivery surface publication rejected")
    return Path(project_root).resolve() / "data" / "solutions" / "final_solution.json"


def export_and_verify_certified_delivery_manifest(
    *,
    project_root: Path,
    exact_campaign: Any,
) -> Optional[Dict[str, Any]]:
    """Export the manifest and route any publishable claim through the central verifier."""

    if exact_campaign is None:
        return None
    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=exact_campaign.state,
        campaign_path=exact_campaign.path,
    )
    if payload.get("best_certified_result") is not None:
        raise RuntimeError(
            "publishable certified delivery manifests must use "
            "publish_verified_certified_delivery_surface"
        )
    clear_certified_delivery_surface_artifacts(Path(project_root).resolve())
    manifest_path = delivery_manifest_output_path(Path(project_root).resolve())
    atomic_write_json(manifest_path, payload)
    surface = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=exact_campaign.state,
        campaign_path=exact_campaign.path,
        delivery_manifest=payload,
    )
    if payload.get("best_certified_result") is not None and not surface.publishable:
        raise RuntimeError(
            "certified delivery manifest export did not produce a current publishable surface: "
            f"{surface.blocked_reason or CERTIFIED_SURFACE_BLOCKED_REASON}"
        )
    return payload


def redact_certified_status(value: Any, *, surface: CertifiedSurfaceVerdict) -> Any:
    if str(value) in PROOF_BEARING_TERMINAL_STATUSES and not surface.publishable:
        return None
    return value


def redact_certified_stop_reason(
    value: Any,
    *,
    surface: CertifiedSurfaceVerdict,
) -> Optional[Dict[str, Any]]:
    payload = _mapping_or_none(value)
    if (
        payload is not None
        and str(payload.get("status")) in PROOF_BEARING_TERMINAL_STATUSES
        and not surface.publishable
    ):
        payload = dict(payload)
        payload["status"] = None
        payload["certified_surface_blocked_reason"] = surface.blocked_reason or (
            CERTIFIED_SURFACE_BLOCKED_REASON
        )
    return payload


# Backward-compatible aliases.
certified_status_for_public_surface = redact_certified_status
certified_stop_reason_for_public_surface = redact_certified_stop_reason


def _resolve_manifest_payload(
    *,
    manifest_path: Path,
    delivery_manifest: Optional[Mapping[str, Any]],
    delivery_manifest_load_error: Optional[str],
) -> tuple[Optional[Dict[str, Any]], Optional[str], bool]:
    regular_file = bool(manifest_path.is_file() and not _path_has_symlink_component(manifest_path))
    if not manifest_path.exists():
        if delivery_manifest_load_error is not None:
            return None, str(delivery_manifest_load_error), False
        return None, None, False
    if not regular_file:
        return None, "delivery_manifest_not_regular_file", False
    try:
        payload = _load_strict_json_mapping(manifest_path)
    except Exception as exc:  # noqa: BLE001 - verifier reports fail-closed reason.
        return None, f"json_load_error:{type(exc).__name__}:{exc}", regular_file
    if delivery_manifest_load_error is not None:
        return payload, str(delivery_manifest_load_error), regular_file
    if delivery_manifest is not None:
        provided_payload = _mapping_or_none(delivery_manifest)
        if provided_payload is None:
            return payload, "delivery_manifest_payload_not_object", regular_file
        if not _json_equivalent(provided_payload, payload):
            return payload, "delivery_manifest_payload_mismatch", regular_file
    return payload, None, regular_file


def _resolve_campaign_state_payload(
    *,
    project_root: Path,
    campaign_state: Optional[Mapping[str, Any]],
    campaign_path: Optional[Path],
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    raw_state_path = _campaign_path_for_regular_file_check(
        project_root=project_root,
        campaign_path=campaign_path,
    )
    state_path = raw_state_path.resolve()
    provided_payload = _mapping_or_none(campaign_state)
    try:
        state_path.relative_to(project_root)
    except ValueError:
        return provided_payload, "campaign_state_path_outside_project"
    if not raw_state_path.exists():
        return provided_payload, "campaign_state_file_missing"
    if not raw_state_path.is_file() or _path_has_symlink_component(raw_state_path):
        return provided_payload, "campaign_state_not_regular_file"
    try:
        disk_payload = _load_strict_json_mapping(raw_state_path)
    except Exception as exc:  # noqa: BLE001 - verifier reports fail-closed reason.
        return (
            provided_payload,
            f"campaign_state_json_load_error:{type(exc).__name__}:{exc}",
        )
    if campaign_state is None:
        return disk_payload, None
    if provided_payload is None:
        return disk_payload, "campaign_state_payload_not_object"
    if has_certified_export_surface(provided_payload):
        canonical_state_path = _canonical_campaign_state_path(project_root)
        if state_path != canonical_state_path:
            return disk_payload, "campaign_state_path_not_canonical"
    if not _json_equivalent(provided_payload, disk_payload):
        return disk_payload, "campaign_state_payload_mismatch"
    return disk_payload, None


def _campaign_path_for_regular_file_check(
    *,
    project_root: Path,
    campaign_path: Optional[Path],
) -> Path:
    project_root = Path(project_root).resolve()
    if campaign_path is None:
        return project_root / "data" / "checkpoints" / DEFAULT_CAMPAIGN_FILENAME
    path = Path(campaign_path)
    if path.is_absolute():
        return path
    return project_root / path


def _canonical_campaign_state_path(project_root: Path) -> Path:
    return (
        Path(project_root).resolve()
        / "data"
        / "checkpoints"
        / DEFAULT_CAMPAIGN_FILENAME
    ).resolve()


def _resolve_campaign_path(*, project_root: Path, campaign_path: Optional[Path]) -> Path:
    return _campaign_path_for_regular_file_check(
        project_root=project_root,
        campaign_path=campaign_path,
    ).resolve()


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _reject_non_finite_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number: {value}")
    return number


def _load_strict_json_mapping(path: Path) -> Dict[str, Any]:
    payload = json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
        parse_float=_reject_non_finite_json_float,
    )
    if not isinstance(payload, Mapping):
        raise ValueError("json_payload_not_object")
    return dict(payload)


def _publish_open_gate_reason(reason: str) -> str:
    return f"{P1_2_PUBLISH_OPEN_GATE_REASON_PREFIX}:{reason}"


def _gate_reason_token(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    if value is None:
        return "missing"
    return type(value).__name__


def _json_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":"), ensure_ascii=False) == json.dumps(
        right,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _artifact_sha_from_manifest(
    delivery_manifest: Mapping[str, Any],
    artifact_name: str,
) -> Optional[str]:
    artifacts = delivery_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        return None
    artifact = artifacts.get(artifact_name)
    if not isinstance(artifact, Mapping):
        return None
    value = artifact.get("sha256")
    return str(value) if isinstance(value, str) else None


def _load_snapshot_payload(
    path: Path,
    *,
    expected_sha256: Optional[str],
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        raw_bytes = Path(path).read_bytes()
    except Exception as exc:  # noqa: BLE001
        return None, f"snapshot_read_error:{type(exc).__name__}"
    if expected_sha256 is None:
        return None, "snapshot_manifest_sha256_missing"
    if hashlib.sha256(raw_bytes).hexdigest() != expected_sha256:
        return None, "snapshot_sha256_mismatch"
    try:
        payload = json.loads(
            raw_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_json_constant,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"snapshot_json_load_error:{type(exc).__name__}"
    if not isinstance(payload, Mapping):
        return None, "snapshot_payload_not_object"
    return dict(payload), None


def _load_verified_surface_snapshot(
    *,
    project_root: Path,
    delivery_manifest: Mapping[str, Any],
) -> tuple[Optional[tuple[Dict[str, Any], Dict[str, Any]]], Optional[str]]:
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    optimal_blueprint_path = blueprint_output_path(project_root)
    final_solution_payload, final_error = _load_snapshot_payload(
        final_solution_path,
        expected_sha256=_artifact_sha_from_manifest(delivery_manifest, "final_solution"),
    )
    if final_error is not None or final_solution_payload is None:
        return None, f"final_solution_{final_error or 'snapshot_missing'}"
    optimal_blueprint_payload, blueprint_error = _load_snapshot_payload(
        optimal_blueprint_path,
        expected_sha256=_artifact_sha_from_manifest(delivery_manifest, "optimal_blueprint"),
    )
    if blueprint_error is not None or optimal_blueprint_payload is None:
        return None, f"optimal_blueprint_{blueprint_error or 'snapshot_missing'}"
    return (final_solution_payload, optimal_blueprint_payload), None


def _resolve_resume_validation_reason(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
    current_hashes: Optional[Mapping[str, str]],
    current_hash_error: Optional[str],
    campaign_resume_compatible: Optional[bool],
    resume_validation_reason: Optional[str],
) -> Optional[str]:
    if current_hash_error:
        return str(current_hash_error)
    if resume_validation_reason not in (None, "campaign_state_missing"):
        return str(resume_validation_reason)
    if campaign_resume_compatible is False and resume_validation_reason:
        return str(resume_validation_reason)
    if campaign_resume_compatible is False:
        return "campaign_resume_incompatible"
    try:
        hashes = compute_exact_artifact_hashes(project_root)
    except Exception as exc:  # noqa: BLE001 - fail closed and expose reason.
        return f"exact_artifact_hash_error:{type(exc).__name__}:{exc}"
    if current_hashes is not None and dict(current_hashes) != hashes:
        return "provided_exact_artifact_hashes_stale"
    return validate_exact_campaign_resume_state(
        campaign_state,
        hashes,
        project_root=project_root,
    )


def _manifest_claims_terminal_certified(delivery_manifest: Mapping[str, Any]) -> bool:
    campaign = (
        dict(delivery_manifest.get("campaign", {}))
        if isinstance(delivery_manifest.get("campaign"), Mapping)
        else {}
    )
    return has_terminal_full_frontier_certified_evidence(
        {
            "declare_mode": campaign.get("declare_mode"),
            "final_status": campaign.get("final_status"),
            "last_stop_reason": campaign.get("last_stop_reason"),
            "final_result": delivery_manifest.get("best_certified_result"),
        }
    )


def _blocked(
    blocked_reason: str,
    *,
    campaign_present: bool,
    campaign_resume_compatible: bool = False,
    campaign_resume_validation_reason: Optional[str] = None,
    campaign_terminal_full_frontier_claimed: bool = False,
    campaign_terminal_full_frontier_valid: bool = False,
    final_delivery_artifacts_current: bool = False,
    final_delivery_artifacts_error: Optional[str] = None,
    delivery_manifest_present: bool,
    delivery_manifest_regular_file: bool,
    delivery_manifest_load_error: Optional[str],
    delivery_manifest_terminal_full_frontier_claimed: bool = False,
    delivery_manifest_current: bool = False,
    delivery_manifest_error: Optional[str] = None,
    best_certified_result: Optional[Dict[str, Any]] = None,
    delivery_manifest_payload: Optional[Dict[str, Any]] = None,
    publish_open_gate_open: bool = False,
    publish_open_gate_reason: Optional[str] = None,
) -> CertifiedSurfaceVerdict:
    return CertifiedSurfaceVerdict(
        publishable=False,
        blocked_reason=str(blocked_reason),
        campaign_present=bool(campaign_present),
        campaign_resume_compatible=bool(campaign_resume_compatible),
        campaign_resume_validation_reason=campaign_resume_validation_reason,
        campaign_terminal_full_frontier_claimed=bool(campaign_terminal_full_frontier_claimed),
        campaign_terminal_full_frontier_valid=bool(campaign_terminal_full_frontier_valid),
        final_delivery_artifacts_current=bool(final_delivery_artifacts_current),
        final_delivery_artifacts_error=final_delivery_artifacts_error,
        delivery_manifest_present=bool(delivery_manifest_present),
        delivery_manifest_regular_file=bool(delivery_manifest_regular_file),
        delivery_manifest_load_error=delivery_manifest_load_error,
        delivery_manifest_terminal_full_frontier_claimed=bool(
            delivery_manifest_terminal_full_frontier_claimed
        ),
        delivery_manifest_current=bool(delivery_manifest_current),
        delivery_manifest_error=delivery_manifest_error,
        best_certified_result=best_certified_result,
        delivery_manifest_payload=delivery_manifest_payload,
        publish_open_gate_open=bool(publish_open_gate_open),
        publish_open_gate_reason=publish_open_gate_reason,
    )


def _mapping_or_none(value: Any) -> Optional[Dict[str, Any]]:
    return dict(value) if isinstance(value, Mapping) else None
