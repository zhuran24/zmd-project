"""Sink-side replay authority for proof-bearing certified_exact candidates.

A candidate record is only a claim.  Neither the Python function that wrote it,
its closure cells, its globals, nor process-local freshness metadata is proof
authority.  Every certified sink replays strong claims in a fresh isolated
interpreter from the on-disk source tree and current project artifacts before it
may use them for pruning or publication.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

CANDIDATE_PROOF_SCHEMA_VERSION = 1
CANDIDATE_PROOF_RESPONSE_SCHEMA_VERSION = 1
CANDIDATE_PROOF_AUTHORITY = "certified_exact_isolated_solver_replay_v1"
CANDIDATE_PROOF_FIELD = "candidate_proof"
_STRONG_STATUSES = frozenset({"CERTIFIED", "INFEASIBLE"})
_SOURCE_DIGEST_KEY = "certified_exact_source_tree"
_MISSING_OPTIONAL_ARTIFACT_HASH = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"

# This is intentionally fixed by the sink, not chosen by a record writer.
# Finite replay can fail closed as UNKNOWN/UNPROVEN; it may never turn such a
# result into a strong conclusion.
_REPLAY_CONFIG: Dict[str, Any] = {
    "solve_mode": "certified_exact",
    "max_iterations": 30,
    "master_seconds": 600.0,
    "binding_seconds": 600.0,
    "routing_seconds": 600.0,
    "flow_seconds": 60.0,
    "master_search_profile": "exact_coordinate_guided_branching_v4",
    "preloaded_exact_safe_cuts": [],
    "disable_master_warm_start": True,
    "cp_sat_workers": 1,
    "random_seed": 0,
}

_PROOF_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "authority",
        "candidate",
        "claimed_status",
        "project_binding",
        "artifact_hashes",
        "source_digest",
        "campaign_context",
        "campaign_context_digest",
        "replay_config",
        "solution_digest",
        "request_digest",
    }
)
_PROOF_ALLOWED_KEYS = _PROOF_REQUIRED_KEYS
_CANDIDATE_KEYS = frozenset({"key", "w", "h", "area"})
_PROJECT_BINDING_KEYS = frozenset({"project_root", "campaign_path"})
_CAMPAIGN_CONTEXT_KEYS = frozenset(
    {"project_root", "campaign_path", "state_context"}
)
_REQUEST_KEYS = frozenset(
    {"schema_version", "authority", "nonce", "project_root", "expected_proofs"}
)
_RESPONSE_KEYS = frozenset(
    {
        "schema_version",
        "authority",
        "nonce",
        "project_root",
        "artifact_hashes",
        "source_digest",
        "results",
    }
)
_REPLAY_RESULT_KEYS = frozenset(
    {
        "candidate_key",
        "claimed_status",
        "replay_status",
        "request_digest",
        "solution",
        "solution_digest",
    }
)
_CAMPAIGN_CONTEXT_FIELDS = (
    "schema_version",
    "solve_mode",
    "artifact_hashes",
    "master_domain_contract",
    "proof_summary_schema_version",
    "declare_mode",
)

_ISOLATED_REPLAY_BOOTSTRAP = r"""
import sys
from pathlib import Path
source_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(source_root))
from src.search.candidate_proof_replay import isolated_replay_main
raise SystemExit(isolated_replay_main())
"""


def canonical_digest(payload: Any) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _json_copy(payload: Any) -> Any:
    return json.loads(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _reject_duplicate_json_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _strict_json_loads(payload: str) -> Any:
    return json.loads(
        payload,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_non_finite_json_constant,
    )


def _strict_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _strict_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _strict_sha256(value: Any, field: str) -> str:
    digest = _strict_string(value, field)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError(f"{field} must be a lowercase sha256 digest")
    return digest


def _normalized_artifact_hashes(
    value: Any,
    *,
    field: str,
) -> Dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{field} must be a non-empty mapping")
    result: Dict[str, str] = {}
    for raw_key, raw_digest in value.items():
        key = _strict_string(raw_key, f"{field}.key")
        if key in result:
            raise ValueError(f"{field} contains duplicate normalized key: {key}")
        if isinstance(raw_digest, str) and raw_digest == _MISSING_OPTIONAL_ARTIFACT_HASH:
            result[key] = raw_digest
        else:
            result[key] = _strict_sha256(raw_digest, f"{field}.{key}")
    return result


def _resolved_campaign_path(campaign: Any, project_root: Path) -> Path:
    raw_path = Path(getattr(campaign, "path", project_root / "data/checkpoints/exact_campaign_state.json"))
    if not raw_path.is_absolute():
        raw_path = project_root / raw_path
    return raw_path.resolve()


def _campaign_context_from_state(
    state: Mapping[str, Any],
    *,
    project_root: Path,
    campaign_path: Path,
) -> Dict[str, Any]:
    return {
        "project_root": str(project_root.resolve()),
        "campaign_path": str(campaign_path.resolve()),
        "state_context": {
            field: _json_copy(state.get(field)) for field in _CAMPAIGN_CONTEXT_FIELDS
        },
    }


def build_candidate_replay_proof(
    campaign: Any,
    ghost_w: int,
    ghost_h: int,
    status: str,
    *,
    solution: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an untrusted replay request bound to campaign/project inputs.

    This function does not certify anything.  Any caller, including a test helper,
    may construct the request.  Only a later sink-side isolated replay can accept
    its claimed status.
    """

    normalized_status = str(status)
    if normalized_status not in _STRONG_STATUSES:
        raise ValueError("candidate replay proof only supports CERTIFIED/INFEASIBLE")
    width = _strict_int(ghost_w, "ghost_w")
    height = _strict_int(ghost_h, "ghost_h")
    if width <= 0 or height <= 0:
        raise ValueError("candidate dimensions must be positive")
    if normalized_status == "CERTIFIED" and not isinstance(solution, Mapping):
        raise ValueError("CERTIFIED replay request requires a solution mapping")
    if normalized_status != "CERTIFIED" and solution is not None:
        raise ValueError("INFEASIBLE replay request must not carry a solution")

    state = getattr(campaign, "state", None)
    if not isinstance(state, Mapping):
        raise ValueError("campaign state must be a mapping")
    project_root = Path(getattr(campaign, "project_root", "")).resolve()
    campaign_path = _resolved_campaign_path(campaign, project_root)
    raw_artifact_hashes = state.get("artifact_hashes")
    if not isinstance(raw_artifact_hashes, Mapping):
        raise ValueError("campaign artifact_hashes missing")
    artifact_hashes = dict(
        sorted(
            _normalized_artifact_hashes(
                raw_artifact_hashes,
                field="artifact_hashes",
            ).items()
        )
    )
    source_digest = _strict_string(
        artifact_hashes.get(_SOURCE_DIGEST_KEY),
        f"artifact_hashes.{_SOURCE_DIGEST_KEY}",
    )
    context = _campaign_context_from_state(
        state,
        project_root=project_root,
        campaign_path=campaign_path,
    )
    proof: Dict[str, Any] = {
        "schema_version": CANDIDATE_PROOF_SCHEMA_VERSION,
        "authority": CANDIDATE_PROOF_AUTHORITY,
        "candidate": {
            "key": f"{width}x{height}",
            "w": width,
            "h": height,
            "area": width * height,
        },
        "claimed_status": normalized_status,
        "project_binding": {
            "project_root": str(project_root),
            "campaign_path": str(campaign_path),
        },
        "artifact_hashes": artifact_hashes,
        "source_digest": source_digest,
        "campaign_context": context,
        "campaign_context_digest": canonical_digest(context),
        "replay_config": _json_copy(_REPLAY_CONFIG),
        "solution_digest": (
            canonical_digest(solution) if normalized_status == "CERTIFIED" else None
        ),
    }
    proof["request_digest"] = canonical_digest(proof)
    return proof


def candidate_proof_shape_violation(
    *,
    proof: Any,
    record_key: str,
    record: Mapping[str, Any],
    state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Optional[Path] = None,
) -> Optional[str]:
    """Validate all data bindings before launching an isolated replay."""

    key = str(record_key)
    if not isinstance(proof, Mapping):
        return f"candidate_sink_replay_proof_missing:{key}"
    if set(proof.keys()) != _PROOF_ALLOWED_KEYS:
        return f"candidate_sink_replay_proof_fields_invalid:{key}"
    try:
        if _strict_int(proof.get("schema_version"), "schema_version") != CANDIDATE_PROOF_SCHEMA_VERSION:
            return f"candidate_sink_replay_proof_schema_invalid:{key}"
    except Exception:
        return f"candidate_sink_replay_proof_schema_invalid:{key}"
    if str(proof.get("authority", "")) != CANDIDATE_PROOF_AUTHORITY:
        return f"candidate_sink_replay_authority_invalid:{key}"

    raw_candidate = proof.get("candidate")
    if not isinstance(raw_candidate, Mapping) or set(raw_candidate.keys()) != _CANDIDATE_KEYS:
        return f"candidate_sink_replay_candidate_invalid:{key}"
    raw_rect = record.get("ghost_rect")
    if not isinstance(raw_rect, Mapping):
        return f"candidate_sink_replay_candidate_invalid:{key}"
    try:
        width = _strict_int(raw_candidate.get("w"), "candidate.w")
        height = _strict_int(raw_candidate.get("h"), "candidate.h")
        area = _strict_int(raw_candidate.get("area"), "candidate.area")
        record_width = _strict_int(raw_rect.get("w"), "record.ghost_rect.w")
        record_height = _strict_int(raw_rect.get("h"), "record.ghost_rect.h")
        record_area = _strict_int(raw_rect.get("area"), "record.ghost_rect.area")
    except Exception:
        return f"candidate_sink_replay_candidate_invalid:{key}"
    if (
        width <= 0
        or height <= 0
        or area != width * height
        or record_area != record_width * record_height
        or str(raw_candidate.get("key", "")) != key
        or key != f"{width}x{height}"
        or (width, height, area) != (record_width, record_height, record_area)
    ):
        return f"candidate_sink_replay_candidate_binding_mismatch:{key}"

    status = str(record.get("status", ""))
    if status not in _STRONG_STATUSES or str(proof.get("claimed_status", "")) != status:
        return f"candidate_sink_replay_status_binding_mismatch:{key}"

    binding = proof.get("project_binding")
    if not isinstance(binding, Mapping) or set(binding.keys()) != _PROJECT_BINDING_KEYS:
        return f"candidate_sink_replay_project_binding_invalid:{key}"
    expected_root = Path(project_root).resolve()
    try:
        bound_root = Path(_strict_string(binding.get("project_root"), "project_root")).resolve()
        bound_campaign = Path(
            _strict_string(binding.get("campaign_path"), "campaign_path")
        ).resolve()
    except Exception:
        return f"candidate_sink_replay_project_binding_invalid:{key}"
    if bound_root != expected_root:
        return f"candidate_sink_replay_project_binding_mismatch:{key}"
    if campaign_path is not None and bound_campaign != Path(campaign_path).resolve():
        return f"candidate_sink_replay_campaign_binding_mismatch:{key}"

    raw_state_hashes = state.get("artifact_hashes")
    raw_proof_hashes = proof.get("artifact_hashes")
    if not isinstance(raw_state_hashes, Mapping) or not isinstance(raw_proof_hashes, Mapping):
        return f"candidate_sink_replay_artifact_binding_invalid:{key}"
    try:
        state_hashes = _normalized_artifact_hashes(
            raw_state_hashes,
            field="state.artifact_hashes",
        )
        proof_hashes = _normalized_artifact_hashes(
            raw_proof_hashes,
            field="proof.artifact_hashes",
        )
    except Exception:
        return f"candidate_sink_replay_artifact_binding_invalid:{key}"
    if proof_hashes != state_hashes:
        return f"candidate_sink_replay_artifact_binding_mismatch:{key}"
    if str(proof.get("source_digest", "")) != str(proof_hashes.get(_SOURCE_DIGEST_KEY, "")):
        return f"candidate_sink_replay_source_binding_mismatch:{key}"

    raw_context = proof.get("campaign_context")
    if not isinstance(raw_context, Mapping):
        return f"candidate_sink_replay_campaign_context_invalid:{key}"
    expected_context = _campaign_context_from_state(
        state,
        project_root=expected_root,
        campaign_path=bound_campaign,
    )
    if _json_copy(raw_context) != expected_context:
        return f"candidate_sink_replay_campaign_context_mismatch:{key}"
    if str(proof.get("campaign_context_digest", "")) != canonical_digest(raw_context):
        return f"candidate_sink_replay_campaign_context_digest_mismatch:{key}"
    if _json_copy(proof.get("replay_config")) != _REPLAY_CONFIG:
        return f"candidate_sink_replay_config_invalid:{key}"

    expected_solution_digest: Optional[str]
    if status == "CERTIFIED":
        solution = record.get("solution")
        if not isinstance(solution, Mapping):
            return f"candidate_sink_replay_solution_missing:{key}"
        expected_solution_digest = canonical_digest(solution)
    else:
        if "solution" in record:
            return f"candidate_sink_replay_infeasible_solution_present:{key}"
        expected_solution_digest = None
    if proof.get("solution_digest") != expected_solution_digest:
        return f"candidate_sink_replay_solution_binding_mismatch:{key}"

    request_without_digest = dict(proof)
    supplied_digest = str(request_without_digest.pop("request_digest", ""))
    if supplied_digest != canonical_digest(request_without_digest):
        return f"candidate_sink_replay_request_digest_mismatch:{key}"
    return None


def _strong_record_keys(
    candidate_records: Mapping[str, Any],
    candidate_keys: Optional[Iterable[str]],
) -> list[str]:
    selected = None if candidate_keys is None else {str(key) for key in candidate_keys}
    result: list[str] = []
    for raw_key, raw_record in candidate_records.items():
        key = str(raw_key)
        if selected is not None and key not in selected:
            continue
        if isinstance(raw_record, Mapping) and str(raw_record.get("status", "")) in _STRONG_STATUSES:
            result.append(key)
    return sorted(result)


def verify_candidate_records_at_sink(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Optional[Path] = None,
    candidate_keys: Optional[Iterable[str]] = None,
    require_record_solution_match: bool = False,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Return strong records independently accepted by an isolated replay."""

    raw_records = state.get("candidates")
    if not isinstance(raw_records, Mapping):
        return {}, {"*": "candidate_sink_replay_records_missing"}
    strong_keys = _strong_record_keys(raw_records, candidate_keys)
    if not strong_keys:
        return {}, {}

    expected_proofs: Dict[str, Dict[str, Any]] = {}
    violations: Dict[str, str] = {}
    for key in strong_keys:
        record = raw_records.get(key)
        if not isinstance(record, Mapping):
            violations[key] = f"candidate_sink_replay_record_invalid:{key}"
            continue
        proof = record.get(CANDIDATE_PROOF_FIELD)
        violation = candidate_proof_shape_violation(
            proof=proof,
            record_key=key,
            record=record,
            state=state,
            project_root=project_root,
            campaign_path=campaign_path,
        )
        if violation is not None:
            violations[key] = violation
            continue
        expected_proofs[key] = _json_copy(proof)

    if not expected_proofs:
        return {}, violations
    try:
        response = _invoke_isolated_replay(
            project_root=Path(project_root).resolve(),
            expected_proofs=expected_proofs,
        )
    except Exception as exc:  # noqa: BLE001
        reason = f"candidate_sink_replay_invocation_failed:{type(exc).__name__}"
        for key in expected_proofs:
            violations.setdefault(key, reason)
        return {}, violations

    envelope_violation = _replay_response_violation(
        response=response,
        project_root=Path(project_root).resolve(),
        expected_proofs=expected_proofs,
    )
    if envelope_violation is not None:
        for key in expected_proofs:
            violations.setdefault(key, envelope_violation)
        return {}, violations

    raw_results = response.get("results")
    assert isinstance(raw_results, list)
    results_by_key = {str(item.get("candidate_key")): item for item in raw_results if isinstance(item, Mapping)}
    verified: Dict[str, Dict[str, Any]] = {}
    for key, proof in expected_proofs.items():
        record = raw_records.get(key)
        result = results_by_key.get(key)
        if not isinstance(record, Mapping) or not isinstance(result, Mapping):
            violations[key] = f"candidate_sink_replay_result_missing:{key}"
            continue
        claimed_status = str(proof.get("claimed_status", ""))
        replay_status = str(result.get("replay_status", ""))
        if replay_status != claimed_status:
            violations[key] = (
                f"candidate_sink_replay_status_mismatch:{key}:"
                f"claimed={claimed_status}:replayed={replay_status}"
            )
            continue
        replayed_record = _json_copy(record)
        if claimed_status == "CERTIFIED":
            replay_solution = result.get("solution")
            if not isinstance(replay_solution, Mapping):
                violations[key] = f"candidate_sink_replay_solution_missing:{key}"
                continue
            replay_solution_digest = canonical_digest(replay_solution)
            if str(result.get("solution_digest", "")) != replay_solution_digest:
                violations[key] = f"candidate_sink_replay_solution_digest_invalid:{key}"
                continue
            if require_record_solution_match:
                stored_solution = record.get("solution")
                if not isinstance(stored_solution, Mapping):
                    violations[key] = f"candidate_sink_replay_solution_missing:{key}"
                    continue
                # The proof request is already digest-bound to the stored witness.
                # A fresh exact replay establishes the strong status; the terminal
                # project validator independently checks the stored witness.  Do
                # not require two valid deterministic solvers to choose identical
                # witnesses.
                replayed_record["solution"] = _json_copy(stored_solution)
            else:
                # Frontier pruning/incumbency consumes the child witness, never a
                # mutable writer-provided witness.  Rebind the data-only request
                # to that canonical replay witness before it can later become
                # durable terminal evidence.
                replayed_record["solution"] = _json_copy(replay_solution)
                rebound_proof = _json_copy(proof)
                rebound_proof["solution_digest"] = replay_solution_digest
                rebound_proof_without_digest = dict(rebound_proof)
                rebound_proof_without_digest.pop("request_digest", None)
                rebound_proof["request_digest"] = canonical_digest(
                    rebound_proof_without_digest
                )
                replayed_record[CANDIDATE_PROOF_FIELD] = rebound_proof
        else:
            replayed_record.pop("solution", None)
        verified[key] = replayed_record
    return verified, violations


def project_candidate_records_for_sink(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Optional[Path] = None,
    candidate_keys: Optional[Iterable[str]] = None,
    require_record_solution_match: bool = False,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Project candidate records through sink replay, demoting every rejection."""

    raw_records = state.get("candidates")
    if not isinstance(raw_records, Mapping):
        return {}, {"*": "candidate_sink_replay_records_missing"}
    verified, violations = verify_candidate_records_at_sink(
        state=state,
        project_root=project_root,
        campaign_path=campaign_path,
        candidate_keys=candidate_keys,
        require_record_solution_match=require_record_solution_match,
    )
    selected = None if candidate_keys is None else {str(key) for key in candidate_keys}
    projected: Dict[str, Dict[str, Any]] = {}
    for raw_key, raw_record in raw_records.items():
        key = str(raw_key)
        if not isinstance(raw_record, Mapping):
            continue
        record = _json_copy(raw_record)
        status = str(record.get("status", ""))
        if status in _STRONG_STATUSES and (selected is None or key in selected):
            accepted = verified.get(key)
            if accepted is None:
                record["status"] = "UNPROVEN"
                record.pop("solution", None)
                record.pop(CANDIDATE_PROOF_FIELD, None)
                proof_summary = record.get("proof_summary")
                summary = dict(proof_summary) if isinstance(proof_summary, Mapping) else {}
                summary["sink_replay_rejected_reason"] = violations.get(
                    key,
                    f"candidate_sink_replay_not_verified:{key}",
                )
                record["proof_summary"] = summary
            else:
                record = accepted
        projected[key] = record
    return projected, violations


def terminal_candidate_proof_replay_violation(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Optional[Path] = None,
    require_record_solution_match: bool = True,
) -> Optional[str]:
    """Return the first fail-closed terminal replay violation, if any."""

    _projected, violations = project_candidate_records_for_sink(
        state=state,
        project_root=project_root,
        campaign_path=campaign_path,
        require_record_solution_match=require_record_solution_match,
    )
    if not violations:
        return None
    key = sorted(violations)[0]
    return violations[key]


def _invoke_isolated_replay(
    *,
    project_root: Path,
    expected_proofs: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    source_root = Path(__file__).resolve().parent.parent.parent
    nonce = secrets.token_hex(32)
    request = {
        "schema_version": CANDIDATE_PROOF_SCHEMA_VERSION,
        "authority": CANDIDATE_PROOF_AUTHORITY,
        "nonce": nonce,
        "project_root": str(project_root.resolve()),
        "expected_proofs": [
            _json_copy(expected_proofs[key]) for key in sorted(expected_proofs)
        ],
    }
    # Do not inherit arbitrary loader, Python, solver, or test-runner state from
    # the producer process.  The child receives only a small operational
    # environment plus sink-fixed deterministic solver controls.
    env = {
        "PATH": os.defpath,
        "PYTHONHASHSEED": "0",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    env["EXACT_CP_SAT_WORKERS"] = "1"
    env["EXACT_MASTER_CP_SAT_WORKERS"] = "1"
    env["EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS"] = "1"
    env["EXACT_BINDING_CP_SAT_WORKERS"] = "1"
    env["EXACT_ROUTING_CP_SAT_WORKERS"] = "1"
    env["EXACT_D2_CP_SAT_WORKERS"] = "1"
    env["EXACT_PATCH_ROUTING_CP_SAT_WORKERS"] = "1"
    env["EXACT_MASTER_RANDOM_SEED"] = "0"
    env["EXACT_MASTER_RANDOM_SEED_BASE"] = "0"
    executable = Path(os.path.abspath(sys.executable))
    completed = subprocess.run(
        [
            str(executable),
            "-I",
            "-c",
            _ISOLATED_REPLAY_BOOTSTRAP,
            str(source_root),
        ],
        input=json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False),
        text=True,
        capture_output=True,
        env=env,
        cwd=str(source_root),
        timeout=max(900.0, 300.0 * len(expected_proofs)),
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
        raise RuntimeError(f"isolated replay exited {completed.returncode}: {detail}")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("isolated replay returned no response")
    try:
        response = _strict_json_loads(lines[-1])
    except Exception as exc:
        raise RuntimeError("isolated replay response is not JSON") from exc
    if not isinstance(response, Mapping):
        raise RuntimeError("isolated replay response must be an object")
    if str(response.get("nonce", "")) != nonce:
        raise RuntimeError("isolated replay nonce mismatch")
    return response


def _replay_response_violation(
    *,
    response: Mapping[str, Any],
    project_root: Path,
    expected_proofs: Mapping[str, Mapping[str, Any]],
) -> Optional[str]:
    if set(response.keys()) != _RESPONSE_KEYS:
        return "candidate_sink_replay_response_fields_invalid"
    try:
        if _strict_int(response.get("schema_version"), "response.schema_version") != CANDIDATE_PROOF_RESPONSE_SCHEMA_VERSION:
            return "candidate_sink_replay_response_schema_invalid"
    except Exception:
        return "candidate_sink_replay_response_schema_invalid"
    if str(response.get("authority", "")) != CANDIDATE_PROOF_AUTHORITY:
        return "candidate_sink_replay_response_authority_invalid"
    if Path(str(response.get("project_root", ""))).resolve() != Path(project_root).resolve():
        return "candidate_sink_replay_response_project_mismatch"
    expected_artifact_hashes: Optional[Dict[str, str]] = None
    expected_source_digest: Optional[str] = None
    for proof in expected_proofs.values():
        proof_hashes = proof.get("artifact_hashes")
        if not isinstance(proof_hashes, Mapping):
            return "candidate_sink_replay_response_artifact_binding_invalid"
        try:
            normalized_hashes = _normalized_artifact_hashes(
                proof_hashes,
                field="response.expected_proof.artifact_hashes",
            )
        except Exception:
            return "candidate_sink_replay_response_artifact_binding_invalid"
        source_digest = str(proof.get("source_digest", ""))
        if expected_artifact_hashes is None:
            expected_artifact_hashes = normalized_hashes
            expected_source_digest = source_digest
        elif (
            normalized_hashes != expected_artifact_hashes
            or source_digest != expected_source_digest
        ):
            return "candidate_sink_replay_request_artifact_set_mismatch"
    raw_response_hashes = response.get("artifact_hashes")
    if not isinstance(raw_response_hashes, Mapping):
        return "candidate_sink_replay_response_artifact_binding_invalid"
    try:
        response_hashes = _normalized_artifact_hashes(
            raw_response_hashes,
            field="response.artifact_hashes",
        )
    except Exception:
        return "candidate_sink_replay_response_artifact_binding_invalid"
    if response_hashes != (expected_artifact_hashes or {}):
        return "candidate_sink_replay_response_artifact_binding_mismatch"
    if str(response.get("source_digest", "")) != str(expected_source_digest or ""):
        return "candidate_sink_replay_response_source_binding_mismatch"
    raw_results = response.get("results")
    if not isinstance(raw_results, list) or len(raw_results) != len(expected_proofs):
        return "candidate_sink_replay_response_result_count_invalid"
    seen: set[str] = set()
    for raw_result in raw_results:
        if not isinstance(raw_result, Mapping) or set(raw_result.keys()) != _REPLAY_RESULT_KEYS:
            return "candidate_sink_replay_response_result_invalid"
        key = str(raw_result.get("candidate_key", ""))
        if key in seen or key not in expected_proofs:
            return "candidate_sink_replay_response_candidate_invalid"
        seen.add(key)
        expected = expected_proofs[key]
        if str(raw_result.get("request_digest", "")) != str(expected.get("request_digest", "")):
            return f"candidate_sink_replay_response_request_mismatch:{key}"
        if str(raw_result.get("claimed_status", "")) != str(expected.get("claimed_status", "")):
            return f"candidate_sink_replay_response_claim_mismatch:{key}"
        replay_status = str(raw_result.get("replay_status", ""))
        solution = raw_result.get("solution")
        solution_digest = raw_result.get("solution_digest")
        if replay_status == "CERTIFIED":
            if not isinstance(solution, Mapping):
                return f"candidate_sink_replay_response_solution_missing:{key}"
            if solution_digest != canonical_digest(solution):
                return f"candidate_sink_replay_response_solution_digest_invalid:{key}"
        elif solution is not None or solution_digest is not None:
            return f"candidate_sink_replay_response_unexpected_solution:{key}"
    if seen != set(expected_proofs):
        return "candidate_sink_replay_response_candidate_set_invalid"
    return None


def _validate_child_proof(
    proof: Mapping[str, Any],
    *,
    project_root: Path,
    current_artifact_hashes: Mapping[str, str],
) -> None:
    if set(proof.keys()) != _PROOF_ALLOWED_KEYS:
        raise ValueError("proof fields invalid")
    if _strict_int(proof.get("schema_version"), "schema_version") != CANDIDATE_PROOF_SCHEMA_VERSION:
        raise ValueError("proof schema invalid")
    if str(proof.get("authority", "")) != CANDIDATE_PROOF_AUTHORITY:
        raise ValueError("proof authority invalid")
    request_without_digest = dict(proof)
    request_digest = str(request_without_digest.pop("request_digest", ""))
    if request_digest != canonical_digest(request_without_digest):
        raise ValueError("proof request digest mismatch")
    binding = proof.get("project_binding")
    if not isinstance(binding, Mapping) or set(binding.keys()) != _PROJECT_BINDING_KEYS:
        raise ValueError("proof project binding invalid")
    if Path(str(binding.get("project_root", ""))).resolve() != project_root.resolve():
        raise ValueError("proof project binding mismatch")
    campaign_path = Path(
        _strict_string(binding.get("campaign_path"), "project_binding.campaign_path")
    ).resolve()
    proof_hashes = _normalized_artifact_hashes(
        proof.get("artifact_hashes"),
        field="proof.artifact_hashes",
    )
    normalized_current_hashes = _normalized_artifact_hashes(
        current_artifact_hashes,
        field="current_artifact_hashes",
    )
    if proof_hashes != normalized_current_hashes:
        raise ValueError("proof artifact binding mismatch")
    if _strict_sha256(proof.get("source_digest"), "proof.source_digest") != str(
        normalized_current_hashes.get(_SOURCE_DIGEST_KEY, "")
    ):
        raise ValueError("proof source binding mismatch")
    campaign_context = proof.get("campaign_context")
    if (
        not isinstance(campaign_context, Mapping)
        or set(campaign_context.keys()) != _CAMPAIGN_CONTEXT_KEYS
    ):
        raise ValueError("proof campaign context invalid")
    if Path(str(campaign_context.get("project_root", ""))).resolve() != project_root.resolve():
        raise ValueError("proof campaign context project mismatch")
    if Path(str(campaign_context.get("campaign_path", ""))).resolve() != campaign_path:
        raise ValueError("proof campaign context path mismatch")
    state_context = campaign_context.get("state_context")
    if not isinstance(state_context, Mapping) or set(state_context.keys()) != set(
        _CAMPAIGN_CONTEXT_FIELDS
    ):
        raise ValueError("proof campaign state context invalid")
    if str(state_context.get("solve_mode", "")) != "certified_exact":
        raise ValueError("proof campaign solve mode invalid")
    raw_context_hashes = state_context.get("artifact_hashes")
    try:
        normalized_context_hashes = _normalized_artifact_hashes(
            raw_context_hashes,
            field="proof.campaign_context.state_context.artifact_hashes",
        )
    except Exception as exc:
        raise ValueError("proof campaign artifact context invalid") from exc
    if normalized_context_hashes != normalized_current_hashes:
        raise ValueError("proof campaign artifact context mismatch")
    if str(proof.get("campaign_context_digest", "")) != canonical_digest(
        campaign_context
    ):
        raise ValueError("proof campaign context digest mismatch")
    if _json_copy(proof.get("replay_config")) != _REPLAY_CONFIG:
        raise ValueError("proof replay config invalid")
    candidate = proof.get("candidate")
    if not isinstance(candidate, Mapping) or set(candidate.keys()) != _CANDIDATE_KEYS:
        raise ValueError("proof candidate invalid")
    width = _strict_int(candidate.get("w"), "candidate.w")
    height = _strict_int(candidate.get("h"), "candidate.h")
    area = _strict_int(candidate.get("area"), "candidate.area")
    if width <= 0 or height <= 0 or area != width * height:
        raise ValueError("proof candidate dimensions invalid")
    if str(candidate.get("key", "")) != f"{width}x{height}":
        raise ValueError("proof candidate key invalid")
    claimed_status = str(proof.get("claimed_status", ""))
    if claimed_status not in _STRONG_STATUSES:
        raise ValueError("proof claimed status invalid")
    solution_digest = proof.get("solution_digest")
    if claimed_status == "CERTIFIED":
        if (
            not isinstance(solution_digest, str)
            or len(solution_digest) != 64
            or any(character not in "0123456789abcdef" for character in solution_digest)
        ):
            raise ValueError("proof solution digest invalid")
    elif solution_digest is not None:
        raise ValueError("proof infeasible solution digest invalid")


def _replay_one_proof(
    proof: Mapping[str, Any],
    *,
    bound_project_root: Path,
    replay_project_root: Path,
    current_artifact_hashes: Mapping[str, str],
    session: Any,
) -> Dict[str, Any]:
    _validate_child_proof(
        proof,
        project_root=bound_project_root,
        current_artifact_hashes=current_artifact_hashes,
    )
    from src.search.benders_loop import run_benders_for_ghost_rect

    candidate = proof["candidate"]
    config = _REPLAY_CONFIG
    status, solution = run_benders_for_ghost_rect(
        ghost_w=int(candidate["w"]),
        ghost_h=int(candidate["h"]),
        max_iterations=int(config["max_iterations"]),
        project_root=replay_project_root,
        solve_mode="certified_exact",
        master_seconds=float(config["master_seconds"]),
        binding_seconds=float(config["binding_seconds"]),
        routing_seconds=float(config["routing_seconds"]),
        flow_seconds=float(config["flow_seconds"]),
        campaign=None,
        session=session,
        preloaded_exact_safe_cuts=[],
        master_search_profile=str(config["master_search_profile"]),
        disable_master_warm_start=True,
    )
    normalized_solution = _json_copy(solution) if isinstance(solution, Mapping) else None
    return {
        "candidate_key": str(candidate["key"]),
        "claimed_status": str(proof["claimed_status"]),
        "replay_status": str(status),
        "request_digest": str(proof["request_digest"]),
        "solution": normalized_solution,
        "solution_digest": (
            canonical_digest(normalized_solution) if normalized_solution is not None else None
        ),
    }


def _materialize_replay_snapshot(
    *,
    project_root: Path,
    replay_project_root: Path,
    current_artifact_hashes: Mapping[str, str],
) -> Dict[str, str]:
    """Copy only hash-bound exact inputs into a side-effect-isolated workspace."""

    from src.search.exact_campaign import (
        EXACT_HASH_FILES,
        MISSING_OPTIONAL_EXACT_ARTIFACT_HASH,
        OPTIONAL_EXACT_HASH_FILES,
        compute_exact_artifact_hashes,
    )

    replay_project_root.mkdir(parents=True, exist_ok=False)
    artifact_paths = {**EXACT_HASH_FILES, **OPTIONAL_EXACT_HASH_FILES}
    for key, relative_path in artifact_paths.items():
        expected_hash = str(current_artifact_hashes.get(key, ""))
        if expected_hash == MISSING_OPTIONAL_EXACT_ARTIFACT_HASH:
            continue
        source = project_root / relative_path
        destination = replay_project_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination, follow_symlinks=False)
    (replay_project_root / "data" / "checkpoints").mkdir(
        parents=True,
        exist_ok=True,
    )
    replay_hashes = compute_exact_artifact_hashes(replay_project_root)
    normalized_replay_hashes = {str(k): str(v) for k, v in replay_hashes.items()}
    normalized_current_hashes = {
        str(k): str(v) for k, v in current_artifact_hashes.items()
    }
    if normalized_replay_hashes != normalized_current_hashes:
        raise ValueError("replay snapshot artifact binding mismatch")
    return normalized_replay_hashes


def _execute_isolated_replay_request(request: Mapping[str, Any]) -> Dict[str, Any]:
    if set(request.keys()) != _REQUEST_KEYS:
        raise ValueError("request fields invalid")
    if _strict_int(request.get("schema_version"), "request.schema_version") != CANDIDATE_PROOF_SCHEMA_VERSION:
        raise ValueError("request schema invalid")
    if str(request.get("authority", "")) != CANDIDATE_PROOF_AUTHORITY:
        raise ValueError("request authority invalid")
    nonce = _strict_string(request.get("nonce"), "request.nonce")
    project_root = Path(_strict_string(request.get("project_root"), "request.project_root")).resolve()
    raw_proofs = request.get("expected_proofs")
    if not isinstance(raw_proofs, list) or not raw_proofs:
        raise ValueError("request expected_proofs invalid")

    from src.search.benders_loop import create_exact_search_session
    from src.search.exact_campaign import compute_exact_artifact_hashes

    current_artifact_hashes = compute_exact_artifact_hashes(project_root)
    source_digest = str(current_artifact_hashes.get(_SOURCE_DIGEST_KEY, ""))
    with tempfile.TemporaryDirectory(prefix="zmd_candidate_sink_replay_") as temp_dir:
        replay_project_root = Path(temp_dir) / "project"
        _materialize_replay_snapshot(
            project_root=project_root,
            replay_project_root=replay_project_root,
            current_artifact_hashes=current_artifact_hashes,
        )
        session = create_exact_search_session(
            replay_project_root,
            solve_mode="certified_exact",
            master_search_profile=str(_REPLAY_CONFIG["master_search_profile"]),
        )
        results = [
            _replay_one_proof(
                proof,
                bound_project_root=project_root,
                replay_project_root=replay_project_root,
                current_artifact_hashes=current_artifact_hashes,
                session=session,
            )
            for proof in raw_proofs
            if isinstance(proof, Mapping)
        ]
    if len(results) != len(raw_proofs):
        raise ValueError("request proof invalid")
    return {
        "schema_version": CANDIDATE_PROOF_RESPONSE_SCHEMA_VERSION,
        "authority": CANDIDATE_PROOF_AUTHORITY,
        "nonce": nonce,
        "project_root": str(project_root),
        "artifact_hashes": dict(current_artifact_hashes),
        "source_digest": source_digest,
        "results": results,
    }


def isolated_replay_main() -> int:
    """Child-process entry point.  Reads one JSON request and prints one response."""

    try:
        request = _strict_json_loads(sys.stdin.read())
        if not isinstance(request, Mapping):
            raise ValueError("request must be an object")
        response = _execute_isolated_replay_request(request)
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "schema_version": CANDIDATE_PROOF_RESPONSE_SCHEMA_VERSION,
                    "authority": CANDIDATE_PROOF_AUTHORITY,
                    "error": type(exc).__name__,
                    "detail": str(exc),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(response, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(isolated_replay_main())
