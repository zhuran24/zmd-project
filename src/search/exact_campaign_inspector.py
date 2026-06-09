from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.io.delivery_manifest import delivery_manifest_output_path
from src.search.campaign_telemetry import campaign_telemetry_output_path
from src.search.exact_campaign import (
    EXACT_HASH_FILES,
    compute_exact_artifact_hashes,
    has_terminal_full_frontier_certified_evidence,
    has_valid_terminal_full_frontier_certified_evidence,
    now_iso,
    validate_exact_campaign_resume_state,
)

INSPECTION_SCHEMA_SOURCE = "phase3b_exact_campaign_inspector_v1"
_CANDIDATE_STATUS_ORDER = ("RUNNING", "CERTIFIED", "INFEASIBLE", "UNKNOWN", "UNPROVEN")


def build_exact_campaign_inspection(
    project_root: Path,
    campaign_state_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path
        if campaign_state_path is not None
        else Path("data/checkpoints/exact_campaign_state.json"),
    )
    telemetry_path = campaign_telemetry_output_path(campaign_path)
    manifest_path = delivery_manifest_output_path(project_root)
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    optimal_blueprint_path = project_root / "data" / "blueprints" / "optimal_blueprint.json"

    current_hashes, hash_error = _current_hashes(project_root)
    checks: list[Dict[str, str]] = []
    state, state_error = _load_json_mapping(campaign_path)
    state_present = state is not None and state_error is None

    checks.append(
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            _present_detail(campaign_path, project_root)
            if state_present
            else state_error or _missing_detail(campaign_path, project_root),
        )
    )

    resume_reason: Optional[str]
    if state is None:
        resume_reason = state_error or "campaign_state_missing"
    elif hash_error is not None:
        resume_reason = hash_error
    else:
        resume_reason = validate_exact_campaign_resume_state(
            state,
            current_hashes,
            project_root=project_root,
        )

    resume_compatible = state is not None and resume_reason is None
    checks.append(
        _check(
            "campaign_resume_compatible",
            "pass" if resume_compatible else ("skipped" if state is None else "fail"),
            "campaign state is compatible with current exact artifact hashes"
            if resume_compatible
            else resume_reason or "campaign state unavailable",
        )
    )

    telemetry, telemetry_error = _load_json_mapping(telemetry_path)
    telemetry_present = telemetry is not None and telemetry_error is None
    checks.append(
        _check(
            "campaign_telemetry_present",
            "pass" if telemetry_present else "fail",
            _present_detail(telemetry_path, project_root)
            if telemetry_present
            else telemetry_error or _missing_detail(telemetry_path, project_root),
        )
    )

    delivery_manifest, delivery_manifest_error = _load_json_mapping(manifest_path)
    delivery_manifest_present = (
        delivery_manifest is not None and delivery_manifest_error is None
    )
    checks.append(
        _check(
            "delivery_manifest_present",
            "pass" if delivery_manifest_present else "fail",
            _present_detail(manifest_path, project_root)
            if delivery_manifest_present
            else delivery_manifest_error or _missing_detail(manifest_path, project_root),
        )
    )

    for check_id, path in (
        ("final_solution_present", final_solution_path),
        ("optimal_blueprint_present", optimal_blueprint_path),
    ):
        checks.append(
            _check(
                check_id,
                "pass" if path.exists() else "fail",
                _present_detail(path, project_root)
                if path.exists()
                else _missing_detail(path, project_root),
            )
        )

    return {
        "metadata": {
            "source": INSPECTION_SCHEMA_SOURCE,
            "generated_at": now_iso(),
            "project_root": str(project_root),
        },
        "paths": {
            "campaign_state": _display_path(project_root, campaign_path),
            "campaign_telemetry": _display_path(project_root, telemetry_path),
            "delivery_manifest": _display_path(project_root, manifest_path),
            "final_solution": _display_path(project_root, final_solution_path),
            "optimal_blueprint": _display_path(project_root, optimal_blueprint_path),
        },
        "campaign": _campaign_summary(
            state,
            current_hashes=current_hashes,
            resume_compatible=resume_compatible,
            resume_validation_reason=resume_reason,
        ),
        "telemetry": _telemetry_summary(telemetry),
        "delivery_manifest": _delivery_manifest_summary(delivery_manifest),
        "checks": checks,
    }


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _current_hashes(project_root: Path) -> tuple[Dict[str, str], Optional[str]]:
    try:
        return compute_exact_artifact_hashes(project_root), None
    except Exception as exc:
        hashes: Dict[str, str] = {}
        for key in EXACT_HASH_FILES:
            hashes[str(key)] = ""
        return hashes, f"exact_artifact_hash_error:{type(exc).__name__}:{exc}"


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


def _campaign_summary(
    state: Optional[Mapping[str, Any]],
    *,
    current_hashes: Mapping[str, str],
    resume_compatible: bool,
    resume_validation_reason: Optional[str],
) -> Dict[str, Any]:
    if state is None:
        return {
            "present": False,
            "final_status": None,
            "last_stop_reason": None,
            "terminal_full_frontier_certified": False,
            "reset_reason": None,
            "candidate_count": 0,
            "candidate_status_counts": {},
            "top_candidates": [],
            "best_certified_result": None,
            "artifact_hashes": {},
            "current_exact_artifact_hashes": dict(current_hashes),
            "resume_compatible_with_current_hashes": False,
            "resume_validation_reason": resume_validation_reason,
        }

    candidates = dict(state.get("candidates", {})) if isinstance(state.get("candidates"), Mapping) else {}
    status_counts: Counter[str] = Counter()
    for record in candidates.values():
        if isinstance(record, Mapping):
            status_counts[str(record.get("status", ""))] += 1

    terminal_certified = (
        has_terminal_full_frontier_certified_evidence(state)
        and has_valid_terminal_full_frontier_certified_evidence(state)
    )
    return {
        "present": True,
        "final_status": state.get("final_status"),
        "last_stop_reason": _mapping_or_none(state.get("last_stop_reason")),
        "terminal_full_frontier_certified": terminal_certified,
        "reset_reason": state.get("reset_reason"),
        "candidate_count": int(len(candidates)),
        "candidate_status_counts": _ordered_counter(status_counts),
        "top_candidates": _top_candidates(candidates),
        "best_certified_result": _best_certified_summary(state.get("final_result"))
        if terminal_certified
        else None,
        "artifact_hashes": dict(state.get("artifact_hashes", {}))
        if isinstance(state.get("artifact_hashes"), Mapping)
        else {},
        "current_exact_artifact_hashes": dict(current_hashes),
        "resume_compatible_with_current_hashes": bool(resume_compatible),
        "resume_validation_reason": resume_validation_reason,
    }


def _telemetry_summary(telemetry: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if telemetry is None:
        return {
            "present": False,
            "solve_mode": None,
            "campaign_state_path": None,
            "wave_count": 0,
            "aggregate": None,
            "last_wave": None,
        }
    waves = list(telemetry.get("waves", [])) if isinstance(telemetry.get("waves"), Sequence) else []
    return {
        "present": True,
        "solve_mode": telemetry.get("solve_mode"),
        "campaign_state_path": telemetry.get("campaign_state_path"),
        "wave_count": int(len(waves)),
        "aggregate": telemetry.get("aggregate") if isinstance(telemetry.get("aggregate"), Mapping) else None,
        "last_wave": waves[-1] if waves and isinstance(waves[-1], Mapping) else None,
    }


def _delivery_manifest_summary(
    delivery_manifest: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    if delivery_manifest is None:
        return {
            "present": False,
            "campaign_final_status": None,
            "campaign_last_stop_reason": None,
            "terminal_full_frontier_certified": False,
            "best_certified_result": None,
        }
    campaign = (
        dict(delivery_manifest.get("campaign", {}))
        if isinstance(delivery_manifest.get("campaign"), Mapping)
        else {}
    )
    terminal_certified = has_terminal_full_frontier_certified_evidence(
        {
            "declare_mode": campaign.get("declare_mode"),
            "final_status": campaign.get("final_status"),
            "last_stop_reason": campaign.get("last_stop_reason"),
            "final_result": delivery_manifest.get("best_certified_result"),
        }
    )
    return {
        "present": True,
        "campaign_final_status": campaign.get("final_status"),
        "campaign_last_stop_reason": _mapping_or_none(campaign.get("last_stop_reason")),
        "terminal_full_frontier_certified": terminal_certified,
        "best_certified_result": _best_certified_summary(
            delivery_manifest.get("best_certified_result")
        )
        if terminal_certified
        else None,
    }


def _best_certified_summary(raw_result: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_result, Mapping):
        return None
    ghost_rect = raw_result.get("ghost_rect")
    if not isinstance(ghost_rect, Mapping):
        return {
            "ghost_rect": None,
            "objective": None,
            "search_status": raw_result.get("search_status"),
            "has_placement_solution": isinstance(raw_result.get("placement_solution"), Mapping),
        }
    objective = _objective_from_rect(ghost_rect)
    return {
        "ghost_rect": {
            "w": _optional_int(ghost_rect.get("w")),
            "h": _optional_int(ghost_rect.get("h")),
            "area": _optional_int(ghost_rect.get("area")),
        },
        "objective": objective,
        "search_status": raw_result.get("search_status"),
        "has_placement_solution": isinstance(raw_result.get("placement_solution"), Mapping),
    }


def _top_candidates(candidates: Mapping[str, Any], limit: int = 10) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for key, raw_record in candidates.items():
        if not isinstance(raw_record, Mapping):
            continue
        ghost_rect = raw_record.get("ghost_rect")
        objective = _objective_from_rect(ghost_rect) if isinstance(ghost_rect, Mapping) else None
        rows.append(
            {
                "candidate_key": str(key),
                "status": str(raw_record.get("status", "")),
                "attempts": _optional_int(raw_record.get("attempts")) or 0,
                "objective": objective,
                "last_stop_hint": _last_stop_hint(raw_record.get("proof_summary")),
            }
        )
    rows.sort(
        key=lambda row: (
            int((row.get("objective") or {}).get("area", 0)),
            int((row.get("objective") or {}).get("min_side", 0)),
            str(row.get("candidate_key", "")),
        ),
        reverse=True,
    )
    return rows[:limit]


def _objective_from_rect(ghost_rect: Mapping[str, Any]) -> Dict[str, int]:
    w = _optional_int(ghost_rect.get("w")) or 0
    h = _optional_int(ghost_rect.get("h")) or 0
    area = _optional_int(ghost_rect.get("area")) or (w * h)
    return {"area": int(area), "min_side": int(min(w, h))}


def _last_stop_hint(proof_summary: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(proof_summary, Mapping):
        return None
    keys = (
        "master_status",
        "binding_status",
        "routing_status",
        "diagnostic_flow_status",
        "selection_reason",
    )
    payload = {key: proof_summary.get(key) for key in keys if proof_summary.get(key) is not None}
    return payload or None


def _ordered_counter(counter: Mapping[str, int]) -> Dict[str, int]:
    payload: Dict[str, int] = {}
    for key in _CANDIDATE_STATUS_ORDER:
        value = int(counter.get(key, 0))
        if value:
            payload[key] = value
    for key in sorted(str(key) for key in counter if str(key) not in payload):
        value = int(counter.get(key, 0))
        if value:
            payload[key] = value
    return payload


def _mapping_or_none(value: Any) -> Optional[Dict[str, Any]]:
    return dict(value) if isinstance(value, Mapping) else None


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    if status not in {"pass", "fail", "skipped"}:
        raise ValueError(f"invalid check status: {status}")
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _missing_detail(path: Path, project_root: Path) -> str:
    return f"missing artifact `{_display_path(project_root, path)}`"


def _present_detail(path: Path, project_root: Path) -> str:
    return f"found artifact `{_display_path(project_root, path)}`"


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)
