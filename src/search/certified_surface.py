"""Central verifier for public certified delivery surfaces.

The exact campaign checkpoint can contain terminal proof evidence, but that
checkpoint alone is not a publishable delivery surface.  Public readers must use
this module's verdict, which binds the checkpoint, exact-artifact hashes,
final_solution.json, optimal_blueprint.json, and certified_delivery_manifest.json
into one fail-closed currentness contract.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.io.delivery_manifest import (
    delivery_manifest_output_path,
    export_certified_delivery_manifest,
    validate_certified_delivery_manifest_matches_campaign,
    validate_delivery_artifacts_match_campaign,
)
from src.io.output_schema import blueprint_output_path
from src.io.serializer import export_certified_blueprint
from src.search.exact_campaign import (
    DEFAULT_CAMPAIGN_FILENAME,
    atomic_write_json,
    compute_exact_artifact_hashes,
    has_terminal_full_frontier_certified_evidence,
    has_valid_terminal_full_frontier_certified_evidence,
    has_valid_terminal_full_frontier_certified_evidence_for_project,
    validate_exact_campaign_resume_state,
)

CERTIFIED_SURFACE_VERIFIER_SOURCE = "certified_surface_verifier_v1"
CERTIFIED_SURFACE_BLOCKED_REASON = "certified_delivery_surface_not_current"


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
        }

    def as_dict(self) -> Dict[str, Any]:
        return self.as_summary()


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
    if campaign_state is None:
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
        campaign_terminal_valid = bool(
            has_valid_terminal_full_frontier_certified_evidence(summary_state)
            if summary_state is not None
            else False
        )
        return _blocked(
            campaign_error,
            campaign_present=campaign_payload is not None,
            campaign_resume_compatible=False,
            campaign_resume_validation_reason=campaign_error,
            campaign_terminal_full_frontier_claimed=campaign_terminal_claimed,
            campaign_terminal_full_frontier_valid=campaign_terminal_valid,
            delivery_manifest_present=manifest_present,
            delivery_manifest_regular_file=manifest_regular_file,
            delivery_manifest_load_error=manifest_error,
            delivery_manifest_payload=manifest_payload,
        )
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
    campaign_terminal_valid = has_valid_terminal_full_frontier_certified_evidence_for_project(
        campaign_state,
        project_root=project_root,
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
    )


# Backward-compatible alias for earlier in-flight patch attempts.
verify_certified_delivery_surface = evaluate_certified_delivery_surface


def certified_delivery_surface_artifact_paths(project_root: Path) -> tuple[Path, Path, Path]:
    project_root = Path(project_root).resolve()
    return (
        project_root / "data" / "solutions" / "final_solution.json",
        blueprint_output_path(project_root),
        delivery_manifest_output_path(project_root),
    )


def clear_certified_delivery_surface_artifacts(project_root: Path) -> None:
    """Remove all files that can advertise a stale certified delivery surface."""

    for artifact_path in certified_delivery_surface_artifact_paths(project_root):
        try:
            if artifact_path.is_dir() and not artifact_path.is_symlink():
                shutil.rmtree(artifact_path)
            else:
                artifact_path.unlink()
        except FileNotFoundError:
            continue


def save_certified_final_solution_and_blueprint(
    *,
    project_root: Path,
    result: Mapping[str, Any],
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Path:
    """Persist final_solution and optimal_blueprint as one certified surface member."""

    project_root = Path(project_root).resolve()
    output_dir = project_root / "data" / "solutions"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "final_solution.json"
    atomic_write_json(output_path, dict(result))
    export_certified_blueprint(
        project_root=project_root,
        result=dict(result),
        facility_pools=facility_pools,
    )
    return output_path


def export_and_verify_certified_delivery_manifest(
    *,
    project_root: Path,
    exact_campaign: Any,
) -> Optional[Dict[str, Any]]:
    """Export the manifest and route any publishable claim through the central verifier."""

    if exact_campaign is None:
        return None
    _path, payload = export_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=exact_campaign.state,
        campaign_path=exact_campaign.path,
    )
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
    if str(value) == "CERTIFIED" and not surface.publishable:
        return None
    return value


def redact_certified_stop_reason(
    value: Any,
    *,
    surface: CertifiedSurfaceVerdict,
) -> Optional[Dict[str, Any]]:
    payload = _mapping_or_none(value)
    if payload is not None and str(payload.get("status")) == "CERTIFIED" and not surface.publishable:
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
    regular_file = bool(manifest_path.is_file() and not manifest_path.is_symlink())
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
    state_path = _resolve_campaign_path(project_root=project_root, campaign_path=campaign_path)
    try:
        state_path.relative_to(project_root)
    except ValueError:
        return _mapping_or_none(campaign_state), "campaign_state_path_outside_project"
    if campaign_state is None:
        return None, "campaign_state_missing"
    if not state_path.exists():
        return _mapping_or_none(campaign_state), "campaign_state_file_missing"
    if not state_path.is_file() or state_path.is_symlink():
        return _mapping_or_none(campaign_state), "campaign_state_not_regular_file"
    try:
        disk_payload = _load_strict_json_mapping(state_path)
    except Exception as exc:  # noqa: BLE001 - verifier reports fail-closed reason.
        return (
            _mapping_or_none(campaign_state),
            f"campaign_state_json_load_error:{type(exc).__name__}:{exc}",
        )
    provided_payload = _mapping_or_none(campaign_state)
    if provided_payload is None:
        return disk_payload, "campaign_state_payload_not_object"
    if not _json_equivalent(provided_payload, disk_payload):
        return disk_payload, "campaign_state_payload_mismatch"
    return disk_payload, None


def _resolve_campaign_path(*, project_root: Path, campaign_path: Optional[Path]) -> Path:
    if campaign_path is None:
        return (project_root / "data" / "checkpoints" / DEFAULT_CAMPAIGN_FILENAME).resolve()
    path = Path(campaign_path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _load_strict_json_mapping(path: Path) -> Dict[str, Any]:
    payload = json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(payload, Mapping):
        raise ValueError("json_payload_not_object")
    return dict(payload)


def _json_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":"), ensure_ascii=False) == json.dumps(
        right,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


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
    )


def _mapping_or_none(value: Any) -> Optional[Dict[str, Any]]:
    return dict(value) if isinstance(value, Mapping) else None
