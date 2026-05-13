from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import compute_exact_artifact_hashes
from src.search.phase3b_anchor119_guard_controls import (
    PHASE3B_ANCHOR119_ADVISORY_ENV,
    PHASE3B_ANCHOR119_ANCHOR_IDX,
    build_phase3b_anchor119_guard_runtime_state,
    phase3b_anchor119_guard_candidate_matches,
)
from src.search.phase3b_anchor119_guarded_precheck_spec import (
    _mapping,
)

ANCHOR119_GUARDED_PRECHECK_RUNTIME_SOURCE = (
    "phase3b_anchor119_guarded_precheck_runtime_v1"
)
ANCHOR119_GUARDED_PRECHECK_ENV = PHASE3B_ANCHOR119_ADVISORY_ENV
DEFAULT_GUARDED_PRECHECK_SPEC_PATH = Path(
    ".artifacts/phase3b_anchor119_guarded_precheck_spec_20260424/"
    "guarded_precheck_spec.json"
)


def evaluate_phase3b_anchor119_guarded_precheck_advisory(
    *,
    project_root: Path,
    ghost_w: int,
    ghost_h: int,
    anchor_idx: Optional[int] = None,
    spec_path: Optional[Path] = None,
    enabled: Optional[bool] = None,
    current_hashes: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Evaluate the anchor119 guard as a default-off advisory.

    This helper intentionally never returns ``triggered=True``. It can report
    ``would_trigger=True`` when all guarded-spec gates pass, but it does not
    short-circuit the exact solve or create a proof-source claim.
    """

    project_root = Path(project_root).resolve()
    runtime_state = build_phase3b_anchor119_guard_runtime_state(
        advisory_env_raw=None if enabled is None else ("1" if bool(enabled) else "")
    )
    is_enabled = bool(runtime_state.get("advisory_enabled", False))
    runtime_precheck_enabled = bool(runtime_state.get("runtime_precheck_enabled", False))
    runtime_activation_allowed = bool(
        runtime_state.get("runtime_activation_allowed", False)
    )
    runtime_apply_enabled = bool(
        runtime_precheck_enabled and runtime_activation_allowed
    )
    base = {
        "metadata": {
            "source": ANCHOR119_GUARDED_PRECHECK_RUNTIME_SOURCE,
            "diagnostic_semantics": (
                "runtime_guard_patch_present_but_default_off"
                if runtime_apply_enabled
                else "advisory_only_not_runtime_proof"
            ),
            "proof_source": bool(runtime_apply_enabled),
            "candidate_elimination_claim": bool(runtime_apply_enabled),
            "runtime_precheck_enabled": bool(runtime_precheck_enabled),
            "runtime_semantics_changed": bool(runtime_apply_enabled),
            "advisory_only": not bool(runtime_apply_enabled),
            "requested_state": runtime_state.get("requested_state"),
            "effective_state": runtime_state.get("effective_state"),
            "runtime_activation_allowed": bool(runtime_activation_allowed),
        },
        "enabled": bool(is_enabled),
        "triggered": False,
        "would_trigger": False,
        "status": None,
        "reason": "disabled",
        "proof_summary": {},
        "runtime_state": dict(runtime_state),
        "checks": [
            _check("runtime_short_circuit_disabled", "pass", "advisory helper never triggers")
        ],
    }
    if not is_enabled:
        return base

    spec_file = _resolve(project_root, spec_path or DEFAULT_GUARDED_PRECHECK_SPEC_PATH)
    spec, load_error = _load_spec(spec_file)
    if spec is None:
        base["reason"] = "spec_load_failed"
        base["checks"].append(_check("spec_loaded", "fail", load_error or str(spec_file)))
        return base
    base["checks"].append(_check("spec_loaded", "pass", _display(project_root, spec_file)))

    spec_status = _mapping(spec.get("status"))
    spec_candidate = _mapping(spec.get("candidate"))
    spec_hashes = _mapping(_mapping(spec.get("artifact_hashes")).get("current_exact_artifact_hashes"))
    if current_hashes is None:
        try:
            current_hashes = compute_exact_artifact_hashes(project_root)
            base["checks"].append(_check("current_hashes_available", "pass", "computed"))
        except Exception as exc:
            base["reason"] = "current_hashes_unavailable"
            base["checks"].append(
                _check("current_hashes_available", "fail", f"{type(exc).__name__}: {exc}")
            )
            return base
    normalized_current = {str(k): str(v) for k, v in dict(current_hashes).items()}
    normalized_spec = {str(k): str(v) for k, v in dict(spec_hashes).items()}

    expected_anchor_idx = int(spec_candidate.get("anchor_idx", -1))
    actual_anchor_idx = (
        int(PHASE3B_ANCHOR119_ANCHOR_IDX) if anchor_idx is None else int(anchor_idx)
    )
    checks = [
        _check(
            "spec_ready_for_review",
            "pass" if spec_status.get("outcome") == "guarded_precheck_spec_ready_for_review" else "fail",
            str(spec_status.get("outcome")),
        ),
        _check(
            "spec_all_gates_pass",
            "pass" if spec_status.get("all_gates_pass") is True else "fail",
            str(spec_status.get("all_gates_pass")),
        ),
        _check(
            "spec_runtime_disabled",
            "pass" if spec_status.get("runtime_precheck_enabled") is False else "fail",
            str(spec_status.get("runtime_precheck_enabled")),
        ),
        _check(
            "candidate_matches",
            "pass"
            if phase3b_anchor119_guard_candidate_matches(
                ghost_w=int(ghost_w),
                ghost_h=int(ghost_h),
                anchor_idx=actual_anchor_idx,
            )
            and int(actual_anchor_idx) == expected_anchor_idx
            else "fail",
            f"ghost={int(ghost_w)}x{int(ghost_h)} anchor={actual_anchor_idx}",
        ),
        _check(
            "artifact_hashes_match",
            "pass" if normalized_current == normalized_spec and bool(normalized_current) else "fail",
            "current exact hashes vs guarded spec hashes",
        ),
    ]
    base["checks"].extend(checks)
    all_checks_pass = all(check["status"] == "pass" for check in checks)
    if not all_checks_pass:
        base["reason"] = "guard_checks_failed"
        return base

    base["would_trigger"] = True
    base["status"] = "INFEASIBLE"
    base["triggered"] = bool(runtime_apply_enabled)
    base["reason"] = (
        "runtime_guard_reject_anchor119"
        if runtime_apply_enabled
        else "advisory_guard_would_reject_anchor119"
    )
    spec_evidence = _mapping(spec.get("evidence"))
    spec_guard = _mapping(spec.get("proposed_guard"))
    spec_controls = _mapping(spec_guard.get("non_trigger_controls"))
    precheck_reason = (
        "anchor119_row_domain_runtime_guard"
        if runtime_apply_enabled
        else "anchor119_mixed_lane_guarded_advisory"
    )

    base["proof_summary"] = {
        "mode": "certified_exact",
        "master_status": "INFEASIBLE",
        "master_candidate_precheck": {
            "triggered": bool(runtime_apply_enabled),
            "would_trigger": True,
            "precheck_reason": precheck_reason,
            "master_solve_skipped": bool(runtime_apply_enabled),
            "supported": True,
            "considered_anchor_count": 1,
            "screened_infeasible_anchor_count": 1,
            "screen_pass_anchor_count": 0,
            "first_infeasible_anchor_idx": int(actual_anchor_idx),
        },
        "anchor119_mixed_lane_guarded_precheck": {
            "advisory_only": not bool(runtime_apply_enabled),
            "runtime_precheck_enabled": bool(runtime_precheck_enabled),
            "runtime_semantics_changed": bool(runtime_apply_enabled),
            "proof_source": bool(runtime_apply_enabled),
            "candidate_elimination_claim": bool(runtime_apply_enabled),
            "requested_state": runtime_state.get("requested_state"),
            "effective_state": runtime_state.get("effective_state"),
            "runtime_activation_allowed": bool(runtime_activation_allowed),
            "runtime_enablement_blockers": list(
                runtime_state.get("runtime_enablement_blockers", [])
            ),
            "spec_path": _display(project_root, spec_file),
            "guard_id": spec_guard.get("guard_id"),
            "payload_id": spec_guard.get("payload_id") or spec_evidence.get("payload_id"),
            "domain_hash": spec_evidence.get("domain_hash"),
            "tiling_outcome": spec_evidence.get("tiling_outcome"),
            "dp_outcome": spec_evidence.get("dp_outcome"),
            "non_trigger_max_slot_count": spec_controls.get("non_trigger_max_slot_count")
            or spec_evidence.get("non_trigger_max_slot_count"),
            "anchored_trigger_min_slot_count": spec_controls.get(
                "anchored_trigger_min_slot_count"
            )
            or spec_evidence.get("anchored_trigger_min_slot_count"),
            "free_ghost_trigger_min_slot_count": spec_controls.get(
                "free_ghost_trigger_min_slot_count"
            )
            or spec_evidence.get("free_ghost_trigger_min_slot_count"),
        },
    }
    return base


def _load_spec(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _resolve(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (Path(project_root) / path).resolve()


def _display(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}
