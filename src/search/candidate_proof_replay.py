"""Candidate-proof replay producer and sink facade."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from src.search.pr2_l0_replay_core import (
    CANDIDATE_PROOF_AUTHORITY,
    CANDIDATE_PROOF_FIELD,
    CANDIDATE_PROOF_RESPONSE_SCHEMA_VERSION,
    CANDIDATE_PROOF_SCHEMA_VERSION,
    _CAMPAIGN_CONTEXT_FIELDS,
    _CAMPAIGN_CONTEXT_KEYS,
    _CANDIDATE_KEYS,
    _ISOLATED_REPLAY_BOOTSTRAP,
    _MISSING_OPTIONAL_ARTIFACT_HASH,
    _PROJECT_BINDING_KEYS,
    _PROOF_ALLOWED_KEYS,
    _PROOF_REQUIRED_KEYS,
    _REPLAY_CONFIG,
    _REPLAY_RESULT_KEYS,
    _REQUEST_KEYS,
    _RESPONSE_KEYS,
    _SOURCE_DIGEST_KEY,
    _STRONG_STATUSES,
    _campaign_context_from_state,
    _execute_isolated_replay_request,
    _json_copy,
    _materialize_replay_snapshot,
    _normalized_artifact_hashes,
    _reject_duplicate_json_keys,
    _reject_non_finite_json_constant,
    _replay_one_proof,
    _replay_response_violation,
    _strict_int,
    _strict_json_loads,
    _strict_sha256,
    _strict_string,
    _validate_child_proof,
    candidate_proof_shape_violation,
    canonical_digest,
)

__all__ = (
    "CANDIDATE_PROOF_AUTHORITY",
    "CANDIDATE_PROOF_FIELD",
    "CANDIDATE_PROOF_RESPONSE_SCHEMA_VERSION",
    "CANDIDATE_PROOF_SCHEMA_VERSION",
    "_CAMPAIGN_CONTEXT_FIELDS",
    "_CAMPAIGN_CONTEXT_KEYS",
    "_CANDIDATE_KEYS",
    "_ISOLATED_REPLAY_BOOTSTRAP",
    "_MISSING_OPTIONAL_ARTIFACT_HASH",
    "_PROJECT_BINDING_KEYS",
    "_PROOF_ALLOWED_KEYS",
    "_PROOF_REQUIRED_KEYS",
    "_REPLAY_CONFIG",
    "_REPLAY_RESULT_KEYS",
    "_REQUEST_KEYS",
    "_RESPONSE_KEYS",
    "_SOURCE_DIGEST_KEY",
    "_STRONG_STATUSES",
    "_campaign_context_from_state",
    "_execute_isolated_replay_request",
    "_invoke_isolated_replay",
    "_json_copy",
    "_materialize_replay_snapshot",
    "_normalized_artifact_hashes",
    "_reject_duplicate_json_keys",
    "_reject_non_finite_json_constant",
    "_replay_one_proof",
    "_replay_response_violation",
    "_resolved_campaign_path",
    "_strict_int",
    "_strict_json_loads",
    "_strict_sha256",
    "_strict_string",
    "_strong_record_keys",
    "_validate_child_proof",
    "build_candidate_replay_proof",
    "candidate_proof_shape_violation",
    "canonical_digest",
    "isolated_replay_main",
    "project_candidate_records_for_sink",
    "terminal_candidate_proof_replay_violation",
    "verify_candidate_records_at_sink",
)


def _resolved_campaign_path(campaign: Any, project_root: Path) -> Path:
    raw_path = Path(getattr(campaign, "path", project_root / "data/checkpoints/exact_campaign_state.json"))
    if not raw_path.is_absolute():
        raw_path = project_root / raw_path
    return raw_path.resolve()
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
    pycache_prefix_dir = tempfile.mkdtemp(prefix="zmd_candidate_replay_pycache_")
    try:
        # -I implies -E, so PYTHONPYCACHEPREFIX would be ignored.  The CLI
        # -X pycache_prefix flag redirects bytecode lookup to this fresh empty
        # directory; -B keeps it empty, forcing execution from hashed .py source.
        completed = subprocess.run(
            [
                str(executable),
                "-I",
                "-B",
                "-X",
                f"pycache_prefix={pycache_prefix_dir}",
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
    finally:
        shutil.rmtree(pycache_prefix_dir, ignore_errors=True)
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
