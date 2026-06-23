"""Isolated fixed-witness terminal proof capsule.

The in-process fixed-witness verifier is diagnostic code.  Public terminal
publication authority comes only from this sink-side capsule: the parent builds
a nonce-bound request, a fresh ``python -I`` child replays the stored terminal
``(R*, pi*)`` from a hash-bound artifact snapshot, and the parent rechecks the
response envelope before projecting records.

The capsule child also runs with ``-B`` and a command-line
``-X pycache_prefix=<fresh empty dir>`` after ``-I``.  That prevents repository
``__pycache__`` bytecode from being read, so executed Python bytecode is compiled
from the ``.py`` source covered by ``compute_certified_exact_source_digest``.
The remaining named TCB is the ``sys.executable`` interpreter, standard library,
and native extensions such as OR-Tools ``.pyd``/``.so`` modules; those lower
layers are trusted rather than covered by this PYC-EXEC-DIGEST fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple

from src.io.strict_json import loads_strict_json
from src.search.candidate_proof_replay import _materialize_replay_snapshot
from src.search.terminal_fixed_witness_verifier import (
    TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
    TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
    TerminalFixedWitnessVerdict,
    _apply_terminal_fixed_witness_audit_fields,
    _copy_candidate_records,
    _identity_from_current_records,
    _project_terminal_fixed_witness_records_from_capsule,
    canonical_state_bytes_for_fixed_witness,
)

TERMINAL_FIXED_WITNESS_CAPSULE_SCHEMA_VERSION = 1
TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION = 1
TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY = (
    "terminal_fixed_witness_isolated_capsule_v1"
)

_PROJECTED_UNPROVEN = "UNPROVEN"
_SOURCE_DIGEST_KEY = "certified_exact_source_tree"
_MISSING_OPTIONAL_EXACT_ARTIFACT_HASH = "__MISSING_OPTIONAL_EXACT_ARTIFACT__"

_REQUEST_KEYS = frozenset(
    {
        "schema_version",
        "authority",
        "nonce",
        "project_root",
        "artifact_hashes",
        "source_digest",
        "authority_state",
    }
)
_RESPONSE_KEYS = frozenset(
    {
        "schema_version",
        "authority",
        "nonce",
        "project_root",
        "artifact_hashes",
        "source_digest",
        "verdict",
    }
)
_VERDICT_KEYS = frozenset(
    {
        "schema_version",
        "authority",
        "fresh_run_token",
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
    }
)

_ISOLATED_CAPSULE_BOOTSTRAP = r"""
import sys
from pathlib import Path
source_root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(source_root))
from src.search.terminal_fixed_witness_capsule import isolated_capsule_main
raise SystemExit(isolated_capsule_main())
"""


@dataclass(frozen=True)
class TerminalFixedWitnessCapsuleProjection:
    candidate_records: Dict[str, Dict[str, Any]]
    durable_candidate_records: Dict[str, Dict[str, Any]]
    candidate_key: Optional[str]
    publishable: bool
    projected_status: str
    rejected_reason: Optional[str]
    verdict: TerminalFixedWitnessVerdict
    capsule_response: Mapping[str, Any] = field(default_factory=dict)


def build_terminal_fixed_witness_projection_at_sink(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    candidate_records: MutableMapping[str, dict[str, Any]],
    final_result: Mapping[str, Any],
    campaign_path: Path | None = None,
    serialized_state_bytes: bytes | None = None,
) -> TerminalFixedWitnessCapsuleProjection:
    """Return public projection after isolated fixed-witness capsule replay."""

    authority_state_reason: str | None = None
    try:
        authority_state = _authority_state_for_capsule(
            state=state,
            candidate_records=candidate_records,
            final_result=final_result,
            serialized_state_bytes=serialized_state_bytes,
        )
    except Exception as exc:  # noqa: BLE001
        authority_state = dict(state)
        authority_state_reason = (
            "terminal_fixed_witness_capsule_authority_state_invalid:"
            f"{type(exc).__name__}"
        )

    if authority_state_reason is not None:
        return _failure_capsule_projection(
            candidate_records=candidate_records,
            final_result=final_result,
            reason=authority_state_reason,
        )

    try:
        expected_artifact_hashes, expected_source_digest = _expected_hashes_from_state(
            authority_state
        )
    except Exception as exc:  # noqa: BLE001
        return _failure_capsule_projection(
            candidate_records=candidate_records,
            final_result=final_result,
            reason=(
                "terminal_fixed_witness_capsule_artifact_binding_invalid:"
                f"{type(exc).__name__}"
            ),
        )

    try:
        nonce = secrets.token_hex(32)
        response = _invoke_isolated_capsule(
            project_root=Path(project_root).resolve(),
            authority_state=authority_state,
            expected_artifact_hashes=expected_artifact_hashes,
            expected_source_digest=expected_source_digest,
            nonce=nonce,
        )
    except Exception as exc:  # noqa: BLE001
        return _failure_capsule_projection(
            candidate_records=candidate_records,
            final_result=final_result,
            reason=(
                "terminal_fixed_witness_capsule_invocation_failed:"
                f"{type(exc).__name__}"
            ),
        )

    try:
        projected_records = _copy_candidate_records(candidate_records)
        identity = _identity_from_current_records(projected_records, final_result)
    except Exception as exc:  # noqa: BLE001
        return _failure_capsule_projection(
            candidate_records=candidate_records,
            final_result=final_result,
            reason=(
                "terminal_fixed_witness_capsule_identity_invalid:"
                f"{type(exc).__name__}"
            ),
            capsule_response=response,
        )

    try:
        verdict = _verdict_from_capsule_response(response.get("verdict"))
    except Exception as exc:  # noqa: BLE001
        return _failure_capsule_projection(
            candidate_records=candidate_records,
            final_result=final_result,
            reason=(
                "terminal_fixed_witness_capsule_verdict_invalid:"
                f"{type(exc).__name__}"
            ),
            capsule_response=response,
        )

    response_violation = _capsule_response_violation(
        response=response,
        expected_nonce=nonce,
        project_root=Path(project_root).resolve(),
        expected_artifact_hashes=expected_artifact_hashes,
        expected_source_digest=expected_source_digest,
        identity_fields={
            "candidate_key": identity.candidate_key,
            "solution_digest": identity.solution_digest,
            "ghost_rect_digest": identity.ghost_rect_digest,
            "ghost_cells_digest": identity.ghost_cells_digest,
            "witness_input_digest": identity.witness_input_digest,
        },
        verdict=verdict,
    )
    if response_violation is not None:
        return _failure_capsule_projection(
            candidate_records=candidate_records,
            final_result=final_result,
            reason=response_violation,
            verdict=verdict,
            capsule_response=response,
        )

    durable_records = _copy_candidate_records(candidate_records)
    _attach_audit_fields(
        durable_records,
        final_result=final_result,
        verdict=verdict,
    )
    public_projection = _project_terminal_fixed_witness_records_from_capsule(
        candidate_records=projected_records,
        final_result=final_result,
        verdict=verdict,
    )
    return TerminalFixedWitnessCapsuleProjection(
        candidate_records=public_projection.candidate_records,
        durable_candidate_records=durable_records,
        candidate_key=public_projection.candidate_key,
        publishable=public_projection.publishable,
        projected_status=public_projection.projected_status,
        rejected_reason=public_projection.rejected_reason,
        verdict=verdict,
        capsule_response=_json_copy(response),
    )


def _authority_state_for_capsule(
    *,
    state: Mapping[str, Any],
    candidate_records: Mapping[str, Any],
    final_result: Mapping[str, Any],
    serialized_state_bytes: bytes | None,
) -> Dict[str, Any]:
    if serialized_state_bytes is None:
        authority_state = _json_copy(state)
    else:
        loaded = loads_strict_json(bytes(serialized_state_bytes).decode("utf-8"))
        if not isinstance(loaded, Mapping):
            raise ValueError("serialized authority state must be a mapping")
        authority_state = _json_copy(loaded)
    authority_state["candidates"] = _copy_candidate_records(candidate_records)
    authority_state["final_result"] = _json_copy(final_result)
    return authority_state


def _failure_capsule_projection(
    *,
    candidate_records: MutableMapping[str, dict[str, Any]],
    final_result: Mapping[str, Any],
    reason: str,
    verdict: TerminalFixedWitnessVerdict | None = None,
    capsule_response: Mapping[str, Any] | None = None,
) -> TerminalFixedWitnessCapsuleProjection:
    failure_verdict = verdict or _failure_verdict_for_records(
        candidate_records=candidate_records,
        final_result=final_result,
        reason=reason,
    )
    durable_records: Dict[str, Dict[str, Any]]
    try:
        durable_records = _copy_candidate_records(candidate_records)
        _attach_audit_fields(
            durable_records,
            final_result=final_result,
            verdict=failure_verdict,
        )
    except Exception:  # noqa: BLE001
        durable_records = {}
    projection = _project_terminal_fixed_witness_records_from_capsule(
        candidate_records=candidate_records,
        final_result=final_result,
        verdict=failure_verdict,
        forced_rejected_reason=reason,
    )
    return TerminalFixedWitnessCapsuleProjection(
        candidate_records=projection.candidate_records,
        durable_candidate_records=durable_records,
        candidate_key=projection.candidate_key,
        publishable=False,
        projected_status=projection.projected_status,
        rejected_reason=projection.rejected_reason,
        verdict=failure_verdict,
        capsule_response=_json_copy(capsule_response or {}),
    )


def _failure_verdict_for_records(
    *,
    candidate_records: Mapping[str, Any],
    final_result: Mapping[str, Any],
    reason: str,
) -> TerminalFixedWitnessVerdict:
    fields: Dict[str, Optional[str]] = {
        "candidate_key": None,
        "solution_digest": None,
        "ghost_rect_digest": None,
        "ghost_cells_digest": None,
        "witness_input_digest": None,
    }
    try:
        copied = _copy_candidate_records(candidate_records)
        identity = _identity_from_current_records(copied, final_result)
        fields = {
            "candidate_key": identity.candidate_key,
            "solution_digest": identity.solution_digest,
            "ghost_rect_digest": identity.ghost_rect_digest,
            "ghost_cells_digest": identity.ghost_cells_digest,
            "witness_input_digest": identity.witness_input_digest,
        }
    except Exception:  # noqa: BLE001
        pass
    return TerminalFixedWitnessVerdict(
        schema_version=TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
        authority=TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
        fresh_run_token="",
        publishable=False,
        projected_status=_PROJECTED_UNPROVEN,
        candidate_key=fields["candidate_key"],
        solution_digest=fields["solution_digest"],
        ghost_rect_digest=fields["ghost_rect_digest"],
        ghost_cells_digest=fields["ghost_cells_digest"],
        witness_input_digest=fields["witness_input_digest"],
        reason=str(reason),
        details={"capsule_rejected_reason": str(reason)},
    )


def _attach_audit_fields(
    candidate_records: MutableMapping[str, dict[str, Any]],
    *,
    final_result: Mapping[str, Any],
    verdict: TerminalFixedWitnessVerdict,
) -> None:
    identity = _identity_from_current_records(candidate_records, final_result)
    record = candidate_records.get(identity.candidate_key)
    if isinstance(record, MutableMapping):
        _apply_terminal_fixed_witness_audit_fields(
            record,
            verdict=verdict,
            publishable=bool(verdict.publishable),
            projected_status=(
                "CERTIFIED" if verdict.publishable else _PROJECTED_UNPROVEN
            ),
            rejected_reason=verdict.reason,
        )


def _expected_hashes_from_state(state: Mapping[str, Any]) -> Tuple[Dict[str, str], str]:
    hashes = _normalized_artifact_hashes(
        state.get("artifact_hashes"),
        field="state.artifact_hashes",
    )
    if not hashes:
        raise ValueError("state artifact_hashes missing")
    source_digest = _strict_sha256(
        hashes.get(_SOURCE_DIGEST_KEY),
        f"state.artifact_hashes.{_SOURCE_DIGEST_KEY}",
    )
    return dict(sorted(hashes.items())), source_digest


def _invoke_isolated_capsule(
    *,
    project_root: Path,
    authority_state: Mapping[str, Any],
    expected_artifact_hashes: Mapping[str, str],
    expected_source_digest: str,
    nonce: str,
) -> Mapping[str, Any]:
    source_root = Path(__file__).resolve().parent.parent.parent
    request = {
        "schema_version": TERMINAL_FIXED_WITNESS_CAPSULE_SCHEMA_VERSION,
        "authority": TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
        "nonce": nonce,
        "project_root": str(Path(project_root).resolve()),
        "artifact_hashes": dict(sorted(expected_artifact_hashes.items())),
        "source_digest": str(expected_source_digest),
        "authority_state": _json_copy(authority_state),
    }
    env = {
        "PATH": os.defpath,
        "PYTHONHASHSEED": "0",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "EXACT_CP_SAT_WORKERS": "1",
        "EXACT_MASTER_CP_SAT_WORKERS": "1",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "1",
        "EXACT_BINDING_CP_SAT_WORKERS": "1",
        "EXACT_ROUTING_CP_SAT_WORKERS": "1",
        "EXACT_D2_CP_SAT_WORKERS": "1",
        "EXACT_PATCH_ROUTING_CP_SAT_WORKERS": "1",
        "EXACT_MASTER_RANDOM_SEED": "0",
        "EXACT_MASTER_RANDOM_SEED_BASE": "0",
    }
    pycache_prefix_dir = tempfile.mkdtemp(prefix="zmd_fixed_witness_capsule_pycache_")
    try:
        # -I ignores PYTHON* env, including PYTHONPYCACHEPREFIX.  Use the CLI
        # -X pycache_prefix flag and -B so this authority process misses repo
        # __pycache__ entries and executes bytecode compiled from hashed source.
        completed = subprocess.run(
            [
                str(Path(os.path.abspath(sys.executable))),
                "-I",
                "-B",
                "-X",
                f"pycache_prefix={pycache_prefix_dir}",
                "-c",
                _ISOLATED_CAPSULE_BOOTSTRAP,
                str(source_root),
            ],
            input=json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False),
            text=True,
            capture_output=True,
            env=env,
            cwd=str(source_root),
            timeout=1500.0,
            check=False,
        )
    finally:
        shutil.rmtree(pycache_prefix_dir, ignore_errors=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
        raise RuntimeError(f"isolated fixed-witness capsule exited {completed.returncode}: {detail}")
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("isolated fixed-witness capsule returned no response")
    response = loads_strict_json(lines[-1])
    if not isinstance(response, Mapping):
        raise RuntimeError("isolated fixed-witness capsule response must be an object")
    if str(response.get("nonce", "")) != nonce:
        raise RuntimeError("isolated fixed-witness capsule nonce mismatch")
    return response


def _capsule_response_violation(
    *,
    response: Mapping[str, Any],
    expected_nonce: str | None,
    project_root: Path,
    expected_artifact_hashes: Mapping[str, str],
    expected_source_digest: str,
    identity_fields: Mapping[str, str],
    verdict: TerminalFixedWitnessVerdict,
) -> Optional[str]:
    if set(response.keys()) != _RESPONSE_KEYS:
        return "terminal_fixed_witness_capsule_response_fields_invalid"
    try:
        schema_version = _strict_int(
            response.get("schema_version"),
            "response.schema_version",
        )
    except Exception:
        return "terminal_fixed_witness_capsule_response_schema_invalid"
    if schema_version != TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION:
        return "terminal_fixed_witness_capsule_response_schema_invalid"
    if str(response.get("authority", "")) != TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY:
        return "terminal_fixed_witness_capsule_response_authority_invalid"
    if expected_nonce is not None and str(response.get("nonce", "")) != str(expected_nonce):
        return "terminal_fixed_witness_capsule_response_nonce_mismatch"
    if Path(str(response.get("project_root", ""))).resolve() != Path(project_root).resolve():
        return "terminal_fixed_witness_capsule_response_project_mismatch"
    try:
        response_hashes = _normalized_artifact_hashes(
            response.get("artifact_hashes"),
            field="response.artifact_hashes",
        )
        expected_hashes = _normalized_artifact_hashes(
            expected_artifact_hashes,
            field="expected_artifact_hashes",
        )
    except Exception:
        return "terminal_fixed_witness_capsule_response_artifact_binding_invalid"
    if response_hashes != expected_hashes:
        return "terminal_fixed_witness_capsule_response_artifact_binding_mismatch"
    if str(response.get("source_digest", "")) != str(expected_source_digest):
        return "terminal_fixed_witness_capsule_response_source_binding_mismatch"
    for field_name, expected_value in identity_fields.items():
        if str(getattr(verdict, field_name, "")) != str(expected_value):
            return f"terminal_fixed_witness_capsule_{field_name}_mismatch"
    if verdict.publishable:
        if str(verdict.projected_status) != "CERTIFIED":
            return "terminal_fixed_witness_capsule_projected_status_invalid"
        if str(verdict.binding_status) != "FEASIBLE":
            return "terminal_fixed_witness_capsule_binding_status_invalid"
        if str(verdict.routing_status) != "FEASIBLE":
            return "terminal_fixed_witness_capsule_routing_status_invalid"
    return None


def _verdict_from_capsule_response(payload: Any) -> TerminalFixedWitnessVerdict:
    if not isinstance(payload, Mapping) or set(payload.keys()) != _VERDICT_KEYS:
        raise ValueError("verdict fields invalid")
    if (
        _strict_int(payload.get("schema_version"), "verdict.schema_version")
        != TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION
    ):
        raise ValueError("verdict schema invalid")
    if str(payload.get("authority", "")) != TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY:
        raise ValueError("verdict authority invalid")
    publishable = payload.get("publishable")
    if not isinstance(publishable, bool):
        raise ValueError("verdict publishable must be bool")
    details = payload.get("details")
    if not isinstance(details, Mapping):
        raise ValueError("verdict details invalid")
    return TerminalFixedWitnessVerdict(
        schema_version=TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
        authority=TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
        fresh_run_token=_strict_string(
            payload.get("fresh_run_token"),
            "verdict.fresh_run_token",
        ),
        publishable=publishable,
        projected_status=str(payload.get("projected_status", "")),
        candidate_key=_optional_string(payload.get("candidate_key")),
        solution_digest=_optional_string(payload.get("solution_digest")),
        ghost_rect_digest=_optional_string(payload.get("ghost_rect_digest")),
        ghost_cells_digest=_optional_string(payload.get("ghost_cells_digest")),
        witness_input_digest=_optional_string(payload.get("witness_input_digest")),
        binding_assignment_digest=_optional_string(
            payload.get("binding_assignment_digest")
        ),
        port_specs_digest=_optional_string(payload.get("port_specs_digest")),
        routing_occupancy_digest=_optional_string(
            payload.get("routing_occupancy_digest")
        ),
        binding_status=_optional_string(payload.get("binding_status")),
        routing_status=_optional_string(payload.get("routing_status")),
        reason=_optional_string(payload.get("reason")),
        details=_json_copy(details),
    )


def _execute_isolated_capsule_request(request: Mapping[str, Any]) -> Dict[str, Any]:
    if set(request.keys()) != _REQUEST_KEYS:
        raise ValueError("request fields invalid")
    if (
        _strict_int(request.get("schema_version"), "request.schema_version")
        != TERMINAL_FIXED_WITNESS_CAPSULE_SCHEMA_VERSION
    ):
        raise ValueError("request schema invalid")
    if str(request.get("authority", "")) != TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY:
        raise ValueError("request authority invalid")
    nonce = _strict_string(request.get("nonce"), "request.nonce")
    project_root = Path(_strict_string(request.get("project_root"), "request.project_root")).resolve()
    expected_hashes = _normalized_artifact_hashes(
        request.get("artifact_hashes"),
        field="request.artifact_hashes",
    )
    expected_source_digest = _strict_sha256(
        request.get("source_digest"),
        "request.source_digest",
    )
    if str(expected_hashes.get(_SOURCE_DIGEST_KEY, "")) != expected_source_digest:
        raise ValueError("request source binding mismatch")
    authority_state = request.get("authority_state")
    if not isinstance(authority_state, Mapping):
        raise ValueError("request authority_state invalid")

    from src.search.exact_campaign import compute_exact_artifact_hashes
    from src.search.terminal_fixed_witness_verifier import verify_terminal_fixed_witness

    current_hashes = compute_exact_artifact_hashes(project_root)
    normalized_current_hashes = _normalized_artifact_hashes(
        current_hashes,
        field="current_artifact_hashes",
    )
    if normalized_current_hashes != expected_hashes:
        raise ValueError("request artifact binding mismatch")
    if str(normalized_current_hashes.get(_SOURCE_DIGEST_KEY, "")) != expected_source_digest:
        raise ValueError("request current source binding mismatch")

    with tempfile.TemporaryDirectory(prefix="zmd_fixed_witness_capsule_") as temp_dir:
        replay_project_root = Path(temp_dir) / "project"
        replay_hashes = _materialize_replay_snapshot(
            project_root=project_root,
            replay_project_root=replay_project_root,
            current_artifact_hashes=normalized_current_hashes,
        )
        if _normalized_artifact_hashes(replay_hashes, field="replay_hashes") != expected_hashes:
            raise ValueError("request replay snapshot hash mismatch")
        state_copy = _json_copy(authority_state)
        verdict = verify_terminal_fixed_witness(
            state=state_copy,
            project_root=replay_project_root,
            serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state_copy),
        )
    return {
        "schema_version": TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION,
        "authority": TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
        "nonce": nonce,
        "project_root": str(project_root),
        "artifact_hashes": dict(sorted(normalized_current_hashes.items())),
        "source_digest": expected_source_digest,
        "verdict": verdict.to_dict(),
    }


def isolated_capsule_main() -> int:
    """Child-process entry point.  Reads one request and prints one response."""

    try:
        request = loads_strict_json(sys.stdin.read())
        if not isinstance(request, Mapping):
            raise ValueError("request must be an object")
        response = _execute_isolated_capsule_request(request)
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "schema_version": TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION,
                    "authority": TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
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


def _normalized_artifact_hashes(value: Any, *, field: str) -> Dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    result: Dict[str, str] = {}
    for raw_key, raw_digest in value.items():
        key = _strict_string(raw_key, f"{field}.key")
        if key in result:
            raise ValueError(f"{field} contains duplicate normalized key: {key}")
        if isinstance(raw_digest, str) and raw_digest == _MISSING_OPTIONAL_EXACT_ARTIFACT_HASH:
            result[key] = raw_digest
        else:
            result[key] = _strict_sha256(raw_digest, f"{field}.{key}")
    return result


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


def _optional_string(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _json_copy(payload: Any) -> Any:
    return loads_strict_json(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    raise SystemExit(isolated_capsule_main())
