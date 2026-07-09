"""PR2 L0 micro-verifier core.

The L0 layer stays stdlib-only.  It snapshots hashed Python source, launches the
domain verifier child, owns proposal/checkpoint bytes, builds the supervisor seal,
and is the only writer for the certified checkpoint transition.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import uuid
from typing import Any, Mapping, Sequence

SEALED = "SEALED"
REJECTED = "REJECTED"
AUTHORITY = "pr2_l0_micro_verifier_v1"
SCHEMA_VERSION = 1
DEFAULT_VERIFIER_MODULE = "src.search.pr2_l0_trivial_child"
TRUE_VERIFIER_MODULE = "src.search.pr2_l0_true_verifier_child"
DEFAULT_VERIFIER_FUNCTION = "verify"
SUPERVISOR_DOMAIN_AUTHORITY = "pr2_l0_true_supervisor_domain_v1"
SUPERVISOR_DOMAIN_SCHEMA_VERSION = 1
DEPENDENCY_FLOOR_MANIFEST_REL = "data/proof_obligations/pr2_dependency_floor_manifest.json"
DEPENDENCY_FLOOR_ROOT_SENTINEL = "PYTHON_SYSCONFIG_PURELIB"
# Provenance: regenerated 2026-07-10 with
# scripts/generate_pr2_dependency_floor_manifest.py under the CachyOS
# Python 3.13 venv (uv-installed; the previous pin was a pip-era dev/CI
# placeholder whose dist-info metadata never matched this host). 3620 files,
# 15 allowed top-level packages. The runtime byte-pin and fail-closed
# behavior below are host-independent soundness hardening.
DEPENDENCY_FLOOR_MANIFEST_SHA256 = "a0fe4bdc520cf8aa4b142eb23cf5dc1933c061d973df0be9f3fe1cca1adc2a74"
DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES = 567602
CANDIDATE_PROPOSED_STATUS = "CANDIDATE_PROPOSED"
TERMINAL_CERTIFIED_REASON = "search_exhausted_all_candidates"
CAMPAIGN_INSTANCE_ID_KEY = "campaign_instance_id"
SUPERVISOR_PROPOSAL_STATE_KEY = "supervisor_proposal"
SUPERVISOR_SEAL_STATE_KEY = "supervisor_seal"
PROPOSAL_READY_MARKER_AUTHORITY = "certified_exact_producer_proposal_ready_v1"
PROPOSAL_READY_MARKER_SCHEMA_VERSION = 2
SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION = 2
SUPERVISOR_SEAL_AUTHORITY = "certified_exact_supervisor_seal_v1"
SUPERVISOR_SEAL_SCHEMA_VERSION = 2
PROPOSAL_RUN_ID_ALLOWED_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
)
STRONG_STATUSES = frozenset({"CERTIFIED", "INFEASIBLE"})
CHILD_STAGE_TRACE = (
    "floor_verified",
    "loader_installed",
    "verifier_imported",
    "verifier_ran",
)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _parse_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def loads_l0_strict_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
        parse_float=_parse_json_float,
    )


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class L0MicroVerdict:
    status: str
    nonce: str
    reason: str
    floor_digest: str | None = None
    response: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class L0SupervisorSealRequest:
    project_root: Path
    campaign_path: Path
    marker_path: Path
    expected_campaign_instance_id: str
    timeout_seconds: float = 3600.0
    # No caller-selected dependency floor path (B2): the durable mint always resolves the canonical host-pinned floor.


def run_l0_micro_verifier_round_trip(
    payload: Mapping[str, Any] | None = None,
    *,
    timeout_seconds: float = 10.0,
    verifier_module: str = DEFAULT_VERIFIER_MODULE,
    verifier_function: str = DEFAULT_VERIFIER_FUNCTION,
    extra_snapshot_modules: Sequence[str] = (),
    omit_snapshot_modules: Sequence[str] = (),
    poison_sys_path: Path | str | None = None,
) -> L0MicroVerdict:
    nonce = secrets.token_hex(32)
    source_root = Path(__file__).resolve().parents[2]
    modules = _snapshot_module_paths(
        source_root=source_root,
        verifier_module=verifier_module,
        extra_snapshot_modules=extra_snapshot_modules,
        omit_snapshot_modules=frozenset(omit_snapshot_modules),
    )
    pycache_prefix = tempfile.mkdtemp(prefix="zmd_pr2_l0_pycache_")
    try:
        with tempfile.TemporaryDirectory(prefix="zmd_pr2_l0_snapshot_") as temp_dir:
            snapshot_root = Path(temp_dir) / "snapshot"
            manifest = _materialize_snapshot(
                snapshot_root,
                modules,
                source_root=source_root,
            )
            _materialize_snapshot_import_defaults(snapshot_root, source_root)
            floor_digest = _floor_digest(manifest)
            request = {
                "schema_version": SCHEMA_VERSION,
                "authority": AUTHORITY,
                "nonce": nonce,
                "snapshot_root": str(snapshot_root),
                "manifest": manifest,
                "floor_digest": floor_digest,
                "verifier_module": verifier_module,
                "verifier_function": verifier_function,
                "payload": dict(payload or {}),
                "poison_sys_path": ([] if poison_sys_path is None else [str(poison_sys_path)]),
            }
            try:
                completed = subprocess.run(
                    [
                        str(Path(os.path.abspath(sys.executable))),
                        "-I",
                        "-S",
                        "-B",
                        "-X",
                        f"pycache_prefix={pycache_prefix}",
                        "-c",
                        CHILD_BOOTSTRAP_SOURCE,
                    ],
                    input=_json_bytes(request).decode("utf-8"),
                    text=True,
                    capture_output=True,
                    env=_child_env(),
                    cwd=str(snapshot_root),
                    timeout=float(timeout_seconds),
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return _reject(nonce, "child_timeout", floor_digest=floor_digest)
            return _verdict_from_completed_process(
                completed=completed,
                nonce=nonce,
                floor_digest=floor_digest,
            )
    except Exception as exc:  # noqa: BLE001
        return _reject(nonce, f"parent_exception:{type(exc).__name__}")
    finally:
        shutil.rmtree(pycache_prefix, ignore_errors=True)


def run_l0_supervisor_seal(request: L0SupervisorSealRequest) -> L0MicroVerdict:
    """Validate and atomically mint a supervisor seal through the PR2 L0 path."""

    nonce = secrets.token_hex(32)
    source_root = Path(__file__).resolve().parents[2]
    project_root = Path(request.project_root).resolve()
    campaign_path = Path(request.campaign_path).resolve()
    marker_path = Path(request.marker_path).resolve()
    try:
        # B2: the durable mint loads ONLY the canonical host-pinned floor. The wrapper
        # takes no path argument by construction, so there is no caller-selected-floor
        # entry into this mint (the loader's explicit-path form is reachable only by tests).
        dependency_floor = _load_canonical_dependency_floor_manifest(source_root)
        try:
            marker_bytes = _read_regular_file_bytes(marker_path)
        except Exception:
            return _reject(nonce, "proposal_ready_marker_unreadable")
        try:
            checkpoint_bytes = _read_regular_file_bytes(campaign_path)
        except Exception:
            return _reject(nonce, "proposal_ready_marker_checkpoint_missing")
        checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
        marker = _parse_mapping(marker_bytes, "proposal_ready_marker")
        marker_violation = _proposal_ready_marker_violation(
            marker,
            checkpoint_sha256=checkpoint_sha256,
            expected_campaign_instance_id=str(request.expected_campaign_instance_id),
        )
        if marker_violation is not None:
            return _reject(nonce, marker_violation)
        authority_state = _parse_mapping(checkpoint_bytes, "proposal_checkpoint")
        authority_violation = _proposal_authority_violation(
            authority_state=authority_state,
            marker=marker,
            expected_campaign_instance_id=str(request.expected_campaign_instance_id),
        )
        if authority_violation is not None:
            return _reject(nonce, authority_violation)
        strong_keys = _strong_status_keys(authority_state)
        proof_binding_violation = _strong_proof_binding_violation(
            authority_state=authority_state,
            strong_keys=strong_keys,
            project_root=project_root,
            campaign_path=campaign_path,
        )
        if proof_binding_violation is not None:
            return _reject(nonce, proof_binding_violation)

        proposal_final_result = _require_mapping(
            authority_state.get("final_result"),
            "proposal final_result invalid",
        )
        certified_final_result = dict(proposal_final_result)
        certified_final_result["search_status"] = "CERTIFIED"
        proposal_evidence = _require_mapping(
            authority_state.get("terminal_frontier_evidence"),
            "proposal terminal_frontier_evidence invalid",
        )
        proposal_candidates = _require_mapping(
            authority_state.get("candidates"),
            "proposal candidate_records invalid",
        )
        child_payload = {
            "action": "supervisor_domain",
            "schema_version": SUPERVISOR_DOMAIN_SCHEMA_VERSION,
            "authority": SUPERVISOR_DOMAIN_AUTHORITY,
            "project_root": str(project_root),
            "authority_state": authority_state,
            "authority_state_b64": base64.b64encode(checkpoint_bytes).decode("ascii"),
            "strong_keys": strong_keys,
            "proposal_final_result_digest": _canonical_digest(certified_final_result),
            "proposal_terminal_frontier_evidence_digest": _canonical_digest(proposal_evidence),
            "proposal_candidate_records_digest": _canonical_digest(
                _stable_fixed_witness_candidate_records_l0(proposal_candidates)
            ),
            "dependency_floor": dependency_floor,
        }
        child_verdict = run_l0_micro_verifier_round_trip(
            child_payload,
            timeout_seconds=float(request.timeout_seconds),
            verifier_module=TRUE_VERIFIER_MODULE,
            extra_snapshot_modules=_discover_project_snapshot_modules(source_root),
        )
        if child_verdict.status != SEALED:
            return child_verdict
        domain = child_verdict.response.get("domain")
        domain_violation = _domain_response_violation(
            domain,
            nonce=child_verdict.nonce,
            strong_keys=strong_keys,
            proposal_final_result_digest=str(child_payload["proposal_final_result_digest"]),
            proposal_evidence_digest=str(child_payload["proposal_terminal_frontier_evidence_digest"]),
            proposal_candidate_records_digest=str(child_payload["proposal_candidate_records_digest"]),
        )
        if domain_violation is not None:
            return _reject(nonce, domain_violation, floor_digest=child_verdict.floor_digest)
        assert isinstance(domain, Mapping)

        commit_timestamp = _now_iso()
        scratch_state = dict(authority_state)
        scratch_state["final_result"] = dict(domain["final_result"])  # type: ignore[index]
        scratch_state["final_status"] = "CERTIFIED"
        # PR2 #5 review hardening: the durable CERTIFIED checkpoint must carry the
        # same strict terminal label the child precheck proved under -- otherwise a
        # producer that ships declare_mode="best_effort" lets the parent mint a
        # final_status="CERTIFIED" state that FAILS its own terminal-evidence gate
        # (has_terminal_full_frontier_certified_evidence requires declare_mode=="strict"),
        # i.e. a self-contradictory durable CERTIFIED. declare_mode is a supervisor-owned
        # terminal label here, not a producer fact (the child already proved the substance).
        scratch_state["declare_mode"] = "strict"
        scratch_state["last_stop_reason"] = {
            "reason": TERMINAL_CERTIFIED_REASON,
            "status": "CERTIFIED",
            "updated_at": commit_timestamp,
        }
        scratch_state.pop(SUPERVISOR_PROPOSAL_STATE_KEY, None)
        scratch_state["terminal_frontier_evidence"] = dict(
            domain["terminal_frontier_evidence"]  # type: ignore[index]
        )
        scratch_state["candidates"] = dict(domain["candidate_records"])  # type: ignore[index]
        scratch_state["updated_at"] = commit_timestamp
        seal_record = {
            "schema_version": SUPERVISOR_SEAL_SCHEMA_VERSION,
            "authority": SUPERVISOR_SEAL_AUTHORITY,
            "transition": "proposal_to_certified_v1",
            "proposal_run_id": str(marker["run_id"]),
            "proposal_checkpoint_sha256": checkpoint_sha256,
            "proposal_authority_b64": base64.b64encode(checkpoint_bytes).decode("ascii"),
            CAMPAIGN_INSTANCE_ID_KEY: str(marker[CAMPAIGN_INSTANCE_ID_KEY]),
            "certified_state_sha256": _certified_state_payload_sha256_l0(scratch_state),
            "sealed_at": commit_timestamp,
        }
        scratch_state[SUPERVISOR_SEAL_STATE_KEY] = seal_record
        seal_violation = _supervisor_seal_state_violation_l0(seal_record, state=scratch_state)
        if seal_violation is not None:
            return _reject(nonce, seal_violation, floor_digest=child_verdict.floor_digest)
        pending_state_bytes = _atomic_json_bytes(scratch_state)

        with _checkpoint_write_lock_l0(campaign_path):
            current_marker_bytes = _read_regular_file_bytes(marker_path)
            current_checkpoint_bytes = _read_regular_file_bytes(campaign_path)
            current_marker = _parse_mapping(current_marker_bytes, "proposal_ready_marker")
            if dict(current_marker) != dict(marker):
                return _reject(
                    nonce,
                    "proposal authority changed before mint: proposal_ready_marker_changed_before_mint",
                    floor_digest=child_verdict.floor_digest,
                )
            if hashlib.sha256(current_checkpoint_bytes).hexdigest() != checkpoint_sha256:
                return _reject(
                    nonce,
                    "proposal checkpoint changed before mint",
                    floor_digest=child_verdict.floor_digest,
                )
            try:
                _atomic_replace_bytes(campaign_path, pending_state_bytes)
                disk_bytes = _read_regular_file_bytes(campaign_path)
                if disk_bytes != pending_state_bytes:
                    raise RuntimeError("certified checkpoint bytes mismatch")
                disk_state = _parse_mapping(disk_bytes, "certified_checkpoint")
                postwrite_violation = _postwrite_state_violation(
                    disk_state,
                    expected_domain=domain,
                    expected_payload_sha=str(seal_record["certified_state_sha256"]),
                )
                if postwrite_violation is not None:
                    raise RuntimeError(postwrite_violation)
            except Exception as exc:  # noqa: BLE001
                _atomic_replace_bytes(campaign_path, checkpoint_bytes)
                return _reject(
                    nonce,
                    f"postwrite_validation_failed:{type(exc).__name__}:{exc}",
                    floor_digest=child_verdict.floor_digest,
                )
            try:
                latest_marker = _parse_mapping(
                    _read_regular_file_bytes(marker_path),
                    "proposal_ready_marker",
                )
            except Exception:
                latest_marker = None
            if isinstance(latest_marker, Mapping) and dict(latest_marker) == dict(marker):
                try:
                    marker_path.unlink()
                except FileNotFoundError:
                    pass
        response = dict(child_verdict.response)
        response["l0_seal"] = {
            "schema_version": SUPERVISOR_SEAL_SCHEMA_VERSION,
            "authority": SUPERVISOR_SEAL_AUTHORITY,
            "checkpoint_sha256": hashlib.sha256(pending_state_bytes).hexdigest(),
            "strong_key_count": len(strong_keys),
            "write_isolation": "protocol_l0_parent_writer_child_snapshot_only_named_tcb",
            "third_party_native": "NAMED-TCB",
        }
        return L0MicroVerdict(
            status=SEALED,
            nonce=nonce,
            reason="supervisor_sealed",
            floor_digest=child_verdict.floor_digest,
            response=response,
        )
    except Exception as exc:  # noqa: BLE001
        return _reject(nonce, f"parent_exception:{type(exc).__name__}:{exc}")


def _snapshot_module_paths(
    *,
    source_root: Path,
    verifier_module: str,
    extra_snapshot_modules: Sequence[str],
    omit_snapshot_modules: frozenset[str],
) -> dict[str, Path]:
    names = [__name__, verifier_module, *extra_snapshot_modules]
    paths: dict[str, Path] = {}
    for module in names:
        if module in omit_snapshot_modules:
            continue
        rel_path = _module_relpath(module)
        path = (source_root / rel_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"snapshot module missing: {module}")
        paths[module] = path
    return paths


def _discover_project_snapshot_modules(source_root: Path) -> tuple[str, ...]:
    modules = (
        __name__,
        TRUE_VERIFIER_MODULE,
        "src.interchange.preprocess_context",
        "src.io.strict_json",
        "src.models._cpsat_compat",
        "src.models.binding_subproblem",
        "src.models.cp_sat_worker_config",
        "src.models.exact_coordinate_master",
        "src.models.master_model",
        "src.models.patch_routing_core",
        "src.models.port_binding",
        "src.models.pose_bool_exact_master",
        "src.models.routing_binding_context",
        "src.models.routing_subproblem",
        "src.models.separator_capacity_hull",
        "src.models.solution_hint_parser",
        "src.placement.placement_generator",
        "src.preprocess.operation_profiles",
        "src.search.certified_artifact_contract",
        "src.search.commodity_throughput",
        "src.search.master_hint_persistence",
        "src.search.pr2_l0_artifact_core",
        "src.search.pr2_l0_fixed_witness_core",
        "src.search.pr2_l0_frontier_core",
        "src.search.pr2_l0_replay_core",
    )
    unique_modules = tuple(dict.fromkeys(modules))
    for module in unique_modules:
        path = (source_root / _module_relpath(module)).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"snapshot module missing: {module}")
    return unique_modules


def _module_relpath(module: str) -> Path:
    parts = module.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        raise ValueError(f"invalid module name: {module}")
    return Path(*parts).with_suffix(".py")


def _path_has_symlink_component(path: Path) -> bool:
    candidate = Path(path)
    current = Path(candidate.anchor) if candidate.is_absolute() else Path()
    parts = candidate.parts[1:] if candidate.is_absolute() else candidate.parts
    for part in parts:
        current = current / part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def _read_regular_file_bytes(path: Path) -> bytes:
    candidate = Path(path)
    if _path_has_symlink_component(candidate) or not candidate.is_file():
        raise ValueError(f"expected regular file: {candidate}")
    with candidate.open("rb") as handle:
        return handle.read()


def _parse_mapping(raw: bytes, label: str) -> dict[str, Any]:
    payload = loads_l0_strict_json(raw.decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be an object")
    return dict(payload)


def _require_mapping(value: Any, message: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(message)
    return dict(value)


def _strict_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _is_lower_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_supervisor_proposal_run_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= 128
        and all(character in PROPOSAL_RUN_ID_ALLOWED_CHARS for character in value)
    )


def _valid_campaign_instance_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _proposal_ready_marker_violation(
    marker: Mapping[str, Any],
    *,
    checkpoint_sha256: str,
    expected_campaign_instance_id: str | None = None,
    expected_run_id: str | None = None,
) -> str | None:
    keys = {
        "schema_version",
        "authority",
        "run_id",
        "exit_code",
        "checkpoint_sha256",
        CAMPAIGN_INSTANCE_ID_KEY,
    }
    if set(marker.keys()) != keys:
        return "proposal_ready_marker_fields_invalid"
    try:
        if _strict_int(marker.get("schema_version"), "proposal_ready.schema_version") != PROPOSAL_READY_MARKER_SCHEMA_VERSION:
            return "proposal_ready_marker_schema_invalid"
    except Exception:
        return "proposal_ready_marker_schema_invalid"
    if str(marker.get("authority", "")) != PROPOSAL_READY_MARKER_AUTHORITY:
        return "proposal_ready_marker_authority_invalid"
    run_id = marker.get("run_id")
    if not _valid_supervisor_proposal_run_id(run_id):
        return "proposal_ready_marker_run_id_invalid"
    if expected_run_id is not None and str(run_id) != str(expected_run_id):
        return "proposal_ready_marker_run_id_mismatch"
    campaign_instance_id = marker.get(CAMPAIGN_INSTANCE_ID_KEY)
    if not _valid_campaign_instance_id(campaign_instance_id):
        return "proposal_ready_marker_campaign_instance_id_invalid"
    if (
        expected_campaign_instance_id is not None
        and str(campaign_instance_id) != str(expected_campaign_instance_id)
    ):
        return "proposal_ready_marker_campaign_instance_id_mismatch"
    try:
        if _strict_int(marker.get("exit_code"), "proposal_ready.exit_code") != 0:
            return "proposal_ready_marker_exit_code_invalid"
    except Exception:
        return "proposal_ready_marker_exit_code_invalid"
    if not _is_lower_sha256(marker.get("checkpoint_sha256")):
        return "proposal_ready_marker_checkpoint_sha256_invalid"
    if str(marker.get("checkpoint_sha256")) != str(checkpoint_sha256):
        return "proposal_ready_marker_checkpoint_sha256_mismatch"
    return None


def _proposal_state_violation(
    value: Any,
    *,
    expected_campaign_instance_id: str | None = None,
) -> str | None:
    keys = {"schema_version", "authority", "run_id", CAMPAIGN_INSTANCE_ID_KEY}
    if not isinstance(value, Mapping):
        return "supervisor_proposal_invalid"
    if set(value.keys()) != keys:
        return "supervisor_proposal_fields_invalid"
    try:
        if _strict_int(value.get("schema_version"), "supervisor_proposal.schema_version") != SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION:
            return "supervisor_proposal_schema_invalid"
    except Exception:
        return "supervisor_proposal_schema_invalid"
    if str(value.get("authority", "")) != PROPOSAL_READY_MARKER_AUTHORITY:
        return "supervisor_proposal_authority_invalid"
    if not _valid_supervisor_proposal_run_id(value.get("run_id")):
        return "supervisor_proposal_run_id_invalid"
    campaign_instance_id = value.get(CAMPAIGN_INSTANCE_ID_KEY)
    if not _valid_campaign_instance_id(campaign_instance_id):
        return "supervisor_proposal_campaign_instance_id_invalid"
    if (
        expected_campaign_instance_id is not None
        and str(campaign_instance_id) != str(expected_campaign_instance_id)
    ):
        return "supervisor_proposal_campaign_instance_id_mismatch"
    return None


def _proposal_authority_violation(
    *,
    authority_state: Mapping[str, Any],
    marker: Mapping[str, Any],
    expected_campaign_instance_id: str,
) -> str | None:
    if str(authority_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:
        return "supervisor_seal requires CANDIDATE_PROPOSED proposal"
    if str(authority_state.get(CAMPAIGN_INSTANCE_ID_KEY)) != str(expected_campaign_instance_id):
        return "supervisor_seal proposal_campaign_instance_id_mismatch"
    proposal = authority_state.get(SUPERVISOR_PROPOSAL_STATE_KEY)
    violation = _proposal_state_violation(
        proposal,
        expected_campaign_instance_id=str(expected_campaign_instance_id),
    )
    if violation is not None:
        return f"supervisor_seal {violation}"
    if not isinstance(proposal, Mapping):
        return "supervisor_seal supervisor_proposal_invalid"
    if str(proposal.get("run_id")) != str(marker.get("run_id")):
        return "proposal_ready_marker_run_id_mismatch"
    return None


def _strong_status_keys(authority_state: Mapping[str, Any]) -> list[str]:
    records = authority_state.get("candidates")
    if not isinstance(records, Mapping):
        raise ValueError("proposal candidate_records invalid")
    keys: list[str] = []
    for raw_key, raw_record in records.items():
        if isinstance(raw_record, Mapping) and str(raw_record.get("status", "")) in STRONG_STATUSES:
            keys.append(str(raw_key))
    return sorted(keys)


def _strong_proof_binding_violation(
    *,
    authority_state: Mapping[str, Any],
    strong_keys: Sequence[str],
    project_root: Path,
    campaign_path: Path,
) -> str | None:
    records = authority_state.get("candidates")
    if not isinstance(records, Mapping):
        return "candidate_sink_replay_records_missing"
    for key in strong_keys:
        record = records.get(key)
        if not isinstance(record, Mapping):
            return f"candidate_sink_replay_record_invalid:{key}"
        proof = record.get("candidate_proof")
        if not isinstance(proof, Mapping):
            return f"candidate_sink_replay_proof_missing:{key}"
        binding = proof.get("project_binding")
        if not isinstance(binding, Mapping) or set(binding.keys()) != {"project_root", "campaign_path"}:
            return f"candidate_sink_replay_project_binding_invalid:{key}"
        try:
            if Path(str(binding.get("project_root"))).resolve() != project_root:
                return f"candidate_sink_replay_project_binding_mismatch:{key}"
            if Path(str(binding.get("campaign_path"))).resolve() != campaign_path:
                return f"candidate_sink_replay_campaign_binding_mismatch:{key}"
        except Exception:
            return f"candidate_sink_replay_project_binding_invalid:{key}"
        context = proof.get("campaign_context")
        if not isinstance(context, Mapping):
            return f"candidate_sink_replay_campaign_context_invalid:{key}"
        try:
            if Path(str(context.get("project_root"))).resolve() != project_root:
                return f"candidate_sink_replay_campaign_context_mismatch:{key}"
            if Path(str(context.get("campaign_path"))).resolve() != campaign_path:
                return f"candidate_sink_replay_campaign_context_mismatch:{key}"
        except Exception:
            return f"candidate_sink_replay_campaign_context_invalid:{key}"
    return None


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _atomic_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")


_FIXED_WITNESS_AUDIT_FIELD = "terminal_fixed_witness_verifier"
_FIXED_WITNESS_STABLE_FIELD_ORDER = (
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
_FIXED_WITNESS_STABLE_FIELDS = frozenset(_FIXED_WITNESS_STABLE_FIELD_ORDER)
_FIXED_WITNESS_VOLATILE_FIELDS = frozenset({"fresh_run_token"})


def _stable_fixed_witness_payload_l0(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_fields = set(payload.keys())
    missing = sorted(_FIXED_WITNESS_STABLE_FIELDS - raw_fields)
    if missing:
        raise ValueError(f"terminal fixed witness verdict missing stable field:{missing[0]}")
    unexpected = sorted(raw_fields - _FIXED_WITNESS_STABLE_FIELDS - _FIXED_WITNESS_VOLATILE_FIELDS)
    if unexpected:
        raise ValueError(f"terminal fixed witness verdict unknown durable field:{unexpected[0]}")
    return {field: json.loads(_canonical_bytes(payload[field]).decode("utf-8")) for field in _FIXED_WITNESS_STABLE_FIELD_ORDER}


def _stable_fixed_witness_candidate_records_l0(records: Mapping[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for raw_key, raw_record in records.items():
        if not isinstance(raw_record, Mapping):
            raise ValueError("terminal fixed witness candidate record invalid")
        record = dict(raw_record)
        proof_summary = record.get("proof_summary")
        if isinstance(proof_summary, Mapping) and _FIXED_WITNESS_AUDIT_FIELD in proof_summary:
            summary = dict(proof_summary)
            raw_verdict = summary.get(_FIXED_WITNESS_AUDIT_FIELD)
            if not isinstance(raw_verdict, Mapping):
                raise ValueError("terminal fixed witness verdict projection invalid")
            summary[_FIXED_WITNESS_AUDIT_FIELD] = _stable_fixed_witness_payload_l0(raw_verdict)
            record["proof_summary"] = summary
        projected[str(raw_key)] = record
    return projected


def _domain_response_violation(
    domain: Any,
    *,
    nonce: str,
    strong_keys: Sequence[str],
    proposal_final_result_digest: str,
    proposal_evidence_digest: str,
    proposal_candidate_records_digest: str,
) -> str | None:
    keys = {
        "schema_version",
        "authority",
        "nonce",
        "verdict",
        "reason",
        "strong_keys",
        "final_result",
        "terminal_frontier_evidence",
        "candidate_records",
        "final_result_digest",
        "terminal_frontier_evidence_digest",
        "candidate_records_digest",
        "fixed_witness_publishable",
        "sink_replay_violations",
        "fixed_witness_violations",
        "tcb",
    }
    if not isinstance(domain, Mapping) or set(domain.keys()) != keys:
        return "domain_response_shape_invalid"
    try:
        if _strict_int(domain.get("schema_version"), "domain.schema_version") != SUPERVISOR_DOMAIN_SCHEMA_VERSION:
            return "domain_response_schema_invalid"
    except Exception:
        return "domain_response_schema_invalid"
    if domain.get("authority") != SUPERVISOR_DOMAIN_AUTHORITY:
        return "domain_response_authority_invalid"
    if domain.get("nonce") != nonce:
        return "domain_response_nonce_mismatch"
    if domain.get("verdict") != SEALED:
        return str(domain.get("reason", "domain_rejected"))
    if list(domain.get("strong_keys", [])) != list(str(key) for key in strong_keys):
        return "domain_strong_key_coverage_mismatch"
    if domain.get("fixed_witness_publishable") is not True:
        return "domain_fixed_witness_not_publishable"
    if not isinstance(domain.get("sink_replay_violations"), Mapping) or domain.get("sink_replay_violations"):
        return "domain_sink_replay_violations"
    if not isinstance(domain.get("fixed_witness_violations"), Mapping) or domain.get("fixed_witness_violations"):
        return "domain_fixed_witness_violations"
    for dom_field in ("final_result", "terminal_frontier_evidence", "candidate_records", "tcb"):
        if not isinstance(domain.get(dom_field), Mapping):
            return f"domain_{dom_field}_invalid"
    if domain.get("final_result_digest") != proposal_final_result_digest:
        return "domain_final_result_digest_mismatch"
    if domain.get("terminal_frontier_evidence_digest") != proposal_evidence_digest:
        return "domain_terminal_frontier_evidence_digest_mismatch"
    if domain.get("candidate_records_digest") != proposal_candidate_records_digest:
        return "domain_candidate_records_digest_mismatch"
    return None


def _certified_state_payload_sha256_l0(state: Mapping[str, Any]) -> str:
    payload = dict(state)
    payload.pop(SUPERVISOR_SEAL_STATE_KEY, None)
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _load_sealed_proposal_authority_l0(value: Mapping[str, Any]) -> tuple[dict[str, Any], bytes, str | None]:
    raw_b64 = value.get("proposal_authority_b64")
    if not isinstance(raw_b64, str) or not raw_b64:
        return {}, b"", "supervisor_seal_proposal_authority_missing"
    try:
        proposal_bytes = base64.b64decode(raw_b64.encode("ascii"), validate=True)
    except Exception:
        return {}, b"", "supervisor_seal_proposal_authority_invalid"
    if hashlib.sha256(proposal_bytes).hexdigest() != str(value.get("proposal_checkpoint_sha256")):
        return {}, b"", "supervisor_seal_proposal_authority_sha256_mismatch"
    try:
        proposal_state = _parse_mapping(proposal_bytes, "proposal_authority")
    except Exception:
        return {}, b"", "supervisor_seal_proposal_authority_state_invalid"
    return proposal_state, proposal_bytes, None


def _supervisor_certified_transition_violation_l0(
    *,
    proposal_state: Mapping[str, Any],
    certified_state: Mapping[str, Any],
    seal_record: Mapping[str, Any],
) -> str | None:
    if str(proposal_state.get("final_status")) != CANDIDATE_PROPOSED_STATUS:
        return "supervisor_seal_proposal_status_invalid"
    if SUPERVISOR_SEAL_STATE_KEY in proposal_state:
        return "supervisor_seal_proposal_already_sealed"
    proposal_record = proposal_state.get(SUPERVISOR_PROPOSAL_STATE_KEY)
    proposal_violation = _proposal_state_violation(
        proposal_record,
        expected_campaign_instance_id=str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY)),
    )
    if proposal_violation is not None:
        return f"supervisor_seal_{proposal_violation}"
    if not isinstance(proposal_record, Mapping):
        return "supervisor_seal_supervisor_proposal_invalid"
    if str(proposal_record.get("run_id")) != str(seal_record.get("proposal_run_id")):
        return "supervisor_seal_proposal_run_id_mismatch"
    if str(proposal_state.get(CAMPAIGN_INSTANCE_ID_KEY)) != str(seal_record.get(CAMPAIGN_INSTANCE_ID_KEY)):
        return "supervisor_seal_proposal_campaign_instance_id_mismatch"
    expected = dict(proposal_state)
    expected["final_status"] = "CERTIFIED"
    # PR2 #5 review hardening: the durable CERTIFIED transition canonicalizes
    # declare_mode to the supervisor-owned strict terminal label (matching the
    # parent mint above), so a producer's declare_mode="best_effort" cannot be
    # carried into the sealed state -- and so this byte-equality transition gate
    # does not falsely reject the now-strict durable state.
    expected["declare_mode"] = "strict"
    final_result = proposal_state.get("final_result")
    if not isinstance(final_result, Mapping):
        return "supervisor_seal_proposal_final_result_invalid"
    expected_final_result = dict(final_result)
    expected_final_result["search_status"] = "CERTIFIED"
    expected["final_result"] = expected_final_result
    expected.pop(SUPERVISOR_PROPOSAL_STATE_KEY, None)
    expected[SUPERVISOR_SEAL_STATE_KEY] = dict(seal_record)
    certified_stop = certified_state.get("last_stop_reason")
    if not isinstance(certified_stop, Mapping):
        return "supervisor_seal_certified_stop_invalid"
    try:
        stop_timestamp = _strict_timestamp(certified_stop.get("updated_at"))
        updated_at = _strict_timestamp(certified_state.get("updated_at"))
    except Exception:
        return "supervisor_seal_certified_updated_at_invalid"
    expected["last_stop_reason"] = {
        "reason": TERMINAL_CERTIFIED_REASON,
        "status": "CERTIFIED",
        "updated_at": stop_timestamp,
    }
    expected["updated_at"] = updated_at
    try:
        if _canonical_bytes(expected) != _canonical_bytes(certified_state):
            return "supervisor_seal_transition_mismatch"
    except Exception:
        return "supervisor_seal_transition_invalid"
    return None


def _supervisor_seal_state_violation_l0(value: Any, *, state: Mapping[str, Any]) -> str | None:
    keys = {
        "schema_version",
        "authority",
        "transition",
        "proposal_run_id",
        "proposal_checkpoint_sha256",
        "proposal_authority_b64",
        CAMPAIGN_INSTANCE_ID_KEY,
        "certified_state_sha256",
        "sealed_at",
    }
    if not isinstance(value, Mapping):
        return "supervisor_seal_invalid"
    if set(value.keys()) != keys:
        return "supervisor_seal_fields_invalid"
    try:
        if _strict_int(value.get("schema_version"), "supervisor_seal.schema_version") != SUPERVISOR_SEAL_SCHEMA_VERSION:
            return "supervisor_seal_schema_invalid"
    except Exception:
        return "supervisor_seal_schema_invalid"
    if value.get("authority") != SUPERVISOR_SEAL_AUTHORITY:
        return "supervisor_seal_authority_invalid"
    if value.get("transition") != "proposal_to_certified_v1":
        return "supervisor_seal_transition_invalid"
    if not _valid_supervisor_proposal_run_id(value.get("proposal_run_id")):
        return "supervisor_seal_proposal_run_id_invalid"
    if not _is_lower_sha256(value.get("proposal_checkpoint_sha256")):
        return "supervisor_seal_proposal_checkpoint_sha256_invalid"
    campaign_instance_id = value.get(CAMPAIGN_INSTANCE_ID_KEY)
    if not _valid_campaign_instance_id(campaign_instance_id):
        return "supervisor_seal_campaign_instance_id_invalid"
    if str(campaign_instance_id) != str(state.get(CAMPAIGN_INSTANCE_ID_KEY)):
        return "supervisor_seal_campaign_instance_id_mismatch"
    proposal_state, _proposal_bytes, proposal_reason = _load_sealed_proposal_authority_l0(value)
    if proposal_reason is not None:
        return proposal_reason
    transition_reason = _supervisor_certified_transition_violation_l0(
        proposal_state=proposal_state,
        certified_state=state,
        seal_record=value,
    )
    if transition_reason is not None:
        return transition_reason
    if not _is_lower_sha256(value.get("certified_state_sha256")):
        return "supervisor_seal_certified_state_sha256_invalid"
    if str(value.get("certified_state_sha256")) != _certified_state_payload_sha256_l0(state):
        return "supervisor_seal_certified_state_sha256_mismatch"
    try:
        _strict_timestamp(value.get("sealed_at"))
    except Exception:
        return "supervisor_seal_sealed_at_invalid"
    return None


def _strict_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be ISO UTC")
    time.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return value


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))


@contextmanager
def _checkpoint_write_lock_l0(checkpoint_path: Path):
    lock_path = checkpoint_path.with_name(f".{checkpoint_path.name}.write.lock")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    token = f"{os.getpid()}:{uuid.uuid4().hex}:{time.monotonic_ns()}"
    deadline = time.monotonic() + 30.0
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError("campaign checkpoint write lock unavailable") from exc
            time.sleep(0.05)
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token)
        break
    try:
        yield
    finally:
        try:
            if lock_path.read_text(encoding="utf-8") == token:
                lock_path.unlink()
        except Exception:
            pass


def _atomic_replace_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temp_path), str(path))
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _postwrite_state_violation(
    disk_state: Mapping[str, Any],
    *,
    expected_domain: Mapping[str, Any],
    expected_payload_sha: str,
) -> str | None:
    if _certified_state_payload_sha256_l0(disk_state) != expected_payload_sha:
        return "supervisor_seal_certified_state_sha256_mismatch"
    # PR2 #5 review hardening (defense in depth): the durable CERTIFIED state on
    # disk must self-satisfy the terminal-evidence gate, whose first requirement is
    # declare_mode=="strict". Fail closed if the mint ever regresses and persists a
    # producer-controlled non-strict declare_mode alongside final_status=="CERTIFIED".
    if str(disk_state.get("declare_mode")) != "strict":
        return "postwrite_declare_mode_not_strict"
    if _canonical_digest(disk_state.get("final_result")) != expected_domain.get("final_result_digest"):
        return "postwrite_final_result_digest_mismatch"
    if _canonical_digest(disk_state.get("terminal_frontier_evidence")) != expected_domain.get("terminal_frontier_evidence_digest"):
        return "postwrite_terminal_frontier_evidence_digest_mismatch"
    candidates = disk_state.get("candidates")
    if not isinstance(candidates, Mapping):
        return "postwrite_candidate_records_invalid"
    if _canonical_digest(_stable_fixed_witness_candidate_records_l0(candidates)) != expected_domain.get("candidate_records_digest"):
        return "postwrite_candidate_records_digest_mismatch"
    return _supervisor_seal_state_violation_l0(disk_state.get(SUPERVISOR_SEAL_STATE_KEY), state=disk_state)


def _safe_manifest_relpath(raw_path: Any) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("dependency floor path invalid")
    rel = raw_path.replace("\\", "/")
    if rel.startswith("/") or ":" in rel or rel in {".", ".."} or rel.startswith("../") or "/../" in rel:
        raise ValueError("dependency floor path escapes root")
    return rel


def _valid_dependency_top_level(value: Any) -> bool:
    return isinstance(value, str) and value.isidentifier()


def _dependency_file_top_level(rel: str) -> str | None:
    first = rel.split("/", 1)[0]
    path = Path(first)
    if path.suffix in {".py", ".pyi", ".pyd", ".so", ".dll", ".dylib"} and path.stem.isidentifier():
        return path.stem
    if first.isidentifier():
        return first
    return None


def _dependency_named_tcb_violation(named_tcb: Any, allowed_top_level: Sequence[str]) -> str | None:
    if not isinstance(named_tcb, Mapping):
        return "dependency floor named_tcb invalid"
    closure = named_tcb.get("third_party_closure")
    if not isinstance(closure, Mapping):
        return "dependency floor third_party_closure missing"
    if set(str(key) for key in closure.keys()) != set(allowed_top_level):
        return "dependency floor third_party_closure mismatch"
    for key, value in closure.items():
        if str(key) not in set(allowed_top_level) or value != "NAMED-TCB":
            return "dependency floor third_party_closure invalid"
    return None


def _load_canonical_dependency_floor_manifest(source_root: Path) -> dict[str, Any]:
    """Resolve + load the canonical dependency floor (no caller-selected path).

    The durable mint reaches the floor ONLY through this wrapper, which takes NO
    caller-selected path: it always resolves source_root/DEPENDENCY_FLOOR_MANIFEST_REL,
    a fixed source-tree location derived from the __file__-based source_root, never
    from a caller. That is what closes the B2 caller-selected-floor channel.

    Trust boundary: the current pinned manifest bytes are a dev/CI
    deploy-pending placeholder from an audit Linux environment, not the
    production-reviewed canonical floor. Production deployment must regenerate
    the manifest under the CachyOS Python 3.13 venv, review it, and re-pin the
    SHA/size. The source-pinned constants below still bind exact bytes before
    any floor file is trusted; missing or regenerated bytes fail closed and must
    be resealed by the close-kernel review path.
    """
    manifest_path = source_root / DEPENDENCY_FLOOR_MANIFEST_REL
    raw = _read_regular_file_bytes(manifest_path)
    current_size = len(raw)
    current_sha256 = hashlib.sha256(raw).hexdigest()
    if current_size != DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES:
        raise ValueError(
            "canonical dependency floor manifest size drift:"
            f"{current_size}!={DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES}"
        )
    if current_sha256 != DEPENDENCY_FLOOR_MANIFEST_SHA256:
        raise ValueError(
            "canonical dependency floor manifest hash drift:"
            f"{current_sha256}!={DEPENDENCY_FLOOR_MANIFEST_SHA256}"
        )
    return _load_dependency_floor_manifest_bytes(raw, manifest_path=manifest_path)


def _dependency_floor_root(raw_root: object) -> Path:
    if raw_root == DEPENDENCY_FLOOR_ROOT_SENTINEL:
        configured = sysconfig.get_paths().get("purelib")
        if not configured:
            raise ValueError("dependency floor sysconfig purelib unavailable")
        return Path(configured).resolve()
    return Path(str(raw_root)).resolve()


def _load_dependency_floor_manifest(manifest_path: Path) -> dict[str, Any]:
    """Validate + load a dependency floor manifest from an EXPLICIT path.

    Reached by the durable mint only via _load_canonical_dependency_floor_manifest
    (which supplies the canonical host-pinned path, not a caller path). The explicit-path
    form exists for that wrapper and for tests of the validation logic; there is
    intentionally no caller-selected-path entry into run_l0_supervisor_seal (B2).
    """
    raw = _read_regular_file_bytes(manifest_path)
    return _load_dependency_floor_manifest_bytes(raw, manifest_path=manifest_path)


def _load_dependency_floor_manifest_bytes(raw: bytes, *, manifest_path: Path) -> dict[str, Any]:
    del manifest_path
    manifest = _parse_mapping(raw, "dependency_floor_manifest")
    required = {
        "schema_version",
        "authority",
        "floor_root",
        "allowed_top_level",
        "files",
        "named_tcb",
    }
    if set(manifest.keys()) != required:
        raise ValueError("dependency floor manifest fields invalid")
    if _strict_int(manifest.get("schema_version"), "dependency_floor.schema_version") != 1:
        raise ValueError("dependency floor manifest schema invalid")
    if manifest.get("authority") != "pr2_l0_dependency_floor_manifest_v1":
        raise ValueError("dependency floor manifest authority invalid")
    root = _dependency_floor_root(manifest.get("floor_root"))
    if _path_has_symlink_component(root) or not root.is_dir():
        raise ValueError("dependency floor root invalid")
    allowed = manifest.get("allowed_top_level")
    allowed_values = [str(item) for item in allowed] if isinstance(allowed, list) else []
    if (
        not allowed_values
        or allowed_values != sorted(set(allowed_values))
        or any(not _valid_dependency_top_level(item) for item in allowed_values)
    ):
        raise ValueError("dependency floor allowed roots invalid")
    named_tcb = manifest.get("named_tcb")
    named_tcb_violation = _dependency_named_tcb_violation(named_tcb, allowed_values)
    if named_tcb_violation is not None:
        raise ValueError(named_tcb_violation)
    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ValueError("dependency floor files invalid")
    verified_files: dict[str, dict[str, Any]] = {}
    file_top_level: set[str] = set()
    for raw_rel, raw_entry in sorted(files.items()):
        rel = _safe_manifest_relpath(raw_rel)
        top_level = _dependency_file_top_level(rel)
        if top_level is not None:
            file_top_level.add(top_level)
        if not isinstance(raw_entry, Mapping) or set(raw_entry.keys()) != {"sha256", "size"}:
            raise ValueError(f"dependency floor entry invalid:{rel}")
        expected_sha = raw_entry.get("sha256")
        expected_size = _strict_int(raw_entry.get("size"), f"dependency_floor.{rel}.size")
        if not _is_lower_sha256(expected_sha) or expected_size < 0:
            raise ValueError(f"dependency floor digest invalid:{rel}")
        path = (root / Path(*rel.split("/"))).resolve()
        if os.path.commonpath([str(root), str(path)]) != str(root):
            raise ValueError(f"dependency floor path escapes root:{rel}")
        data = _read_regular_file_bytes(path)
        if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError(f"dependency floor digest mismatch:{rel}")
        verified_files[rel] = {"sha256": str(expected_sha), "size": int(expected_size)}
    missing_top_level = sorted(file_top_level - set(allowed_values))
    if missing_top_level:
        raise ValueError(f"dependency floor allowed roots missing:{missing_top_level[0]}")
    return {
        "schema_version": 1,
        "authority": "pr2_l0_dependency_floor_manifest_v1",
        "floor_root": manifest.get("floor_root"),
        "allowed_top_level": allowed_values,
        "files": verified_files,
        "manifest_digest": hashlib.sha256(_canonical_bytes(manifest)).hexdigest(),
        "named_tcb": dict(named_tcb),
    }



def _materialize_snapshot(
    snapshot_root: Path,
    modules: Mapping[str, Path],
    *,
    source_root: Path,
) -> dict[str, dict[str, str]]:
    manifest: dict[str, dict[str, str]] = {}
    copied_relpaths: set[str] = set()
    for module, source_path in sorted(modules.items()):
        rel_path = _module_relpath(module)
        source_bytes = Path(source_path).read_bytes()
        target_path = snapshot_root / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_bytes)
        copied_relpaths.add(rel_path.as_posix())
        manifest[module] = {
            "path": rel_path.as_posix(),
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
    for rel_path in _source_digest_relpaths(source_root):
        if rel_path in copied_relpaths:
            continue
        source_path = source_root / rel_path
        source_bytes = source_path.read_bytes()
        target_path = snapshot_root / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_bytes)
        manifest[f"@source:{rel_path}"] = {
            "path": rel_path,
            "sha256": hashlib.sha256(source_bytes).hexdigest(),
        }
    return manifest


def _materialize_snapshot_import_defaults(snapshot_root: Path, source_root: Path) -> None:
    # These are project frozen-input defaults copied into the hashed child snapshot
    # for imports that expect rules/*.json beside source. They are not third-party
    # dependency-floor bytes; preflight/campaign frozen-artifact hashes own them.
    rules_root = source_root / "rules"
    for source in rules_root.glob("*.json") if rules_root.exists() else ():
        rel = source.relative_to(source_root)
        destination = snapshot_root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination, follow_symlinks=False)


def _source_digest_relpaths(source_root: Path) -> tuple[str, ...]:
    relative_paths: set[str] = {
        path.relative_to(source_root).as_posix()
        for path in source_root.glob("*.py")
        if path.is_file()
    }
    for path in (source_root / "src").rglob("*.py"):
        relative_path = path.relative_to(source_root).as_posix()
        if relative_path.startswith("src/tests/"):
            continue
        relative_paths.add(relative_path)
    scripts_root = source_root / "scripts"
    if scripts_root.exists():
        for path in scripts_root.rglob("*.py"):
            relative_paths.add(path.relative_to(source_root).as_posix())
    for relative_path in (
        "NO_CLOSE_KERNEL_EXPERIMENT.md",
        "NO_CLOSE_KERNEL_EXPERIMENT.json",
    ):
        if (source_root / relative_path).is_file():
            relative_paths.add(relative_path)
    return tuple(sorted(relative_paths))


def _floor_digest(manifest: Mapping[str, Mapping[str, str]]) -> str:
    return hashlib.sha256(_json_bytes(manifest)).hexdigest()


def _child_env() -> dict[str, str]:
    return {"PATH": os.defpath, "PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


def _verdict_from_completed_process(
    *,
    completed: subprocess.CompletedProcess[str],
    nonce: str,
    floor_digest: str,
) -> L0MicroVerdict:
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-200:]
        return _reject(nonce, f"child_exit:{completed.returncode}:{detail}", floor_digest=floor_digest)
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        return _reject(nonce, "child_no_response", floor_digest=floor_digest)
    try:
        response = loads_l0_strict_json(lines[-1])
    except Exception as exc:  # noqa: BLE001
        return _reject(nonce, f"child_response_json:{type(exc).__name__}", floor_digest=floor_digest)
    violation = _response_violation(response, nonce=nonce, floor_digest=floor_digest)
    if violation is not None:
        return _reject(nonce, violation, floor_digest=floor_digest, response=response if isinstance(response, Mapping) else {})
    verdict = str(response["verdict"])
    reason = str(response["reason"])
    if verdict == SEALED:
        return L0MicroVerdict(
            status=SEALED,
            nonce=nonce,
            reason=reason,
            floor_digest=floor_digest,
            response=dict(response),
        )
    return _reject(nonce, reason, floor_digest=floor_digest, response=dict(response))


def _response_violation(response: Any, *, nonce: str, floor_digest: str) -> str | None:
    keys = {
        "schema_version",
        "authority",
        "nonce",
        "floor_digest",
        "verdict",
        "reason",
        "stage_trace",
        "verifier_module",
        "domain",
    }
    if not isinstance(response, Mapping) or set(response.keys()) != keys:
        return "response_shape_invalid"
    if response["schema_version"] != SCHEMA_VERSION:
        return "response_schema_invalid"
    if response["authority"] != AUTHORITY:
        return "response_authority_invalid"
    if response["nonce"] != nonce:
        return "response_nonce_mismatch"
    if response["floor_digest"] != floor_digest:
        return "response_floor_digest_mismatch"
    if response["verdict"] not in {SEALED, REJECTED}:
        return "response_verdict_invalid"
    if not isinstance(response["reason"], str):
        return "response_reason_invalid"
    if not isinstance(response["verifier_module"], str):
        return "response_verifier_invalid"
    trace = response["stage_trace"]
    if not isinstance(trace, list) or any(not isinstance(item, str) for item in trace):
        return "response_stage_trace_invalid"
    if response["verdict"] == SEALED and tuple(trace) != CHILD_STAGE_TRACE:
        return "response_stage_trace_incomplete"
    return None


def _reject(
    nonce: str,
    reason: str,
    *,
    floor_digest: str | None = None,
    response: Mapping[str, Any] | None = None,
) -> L0MicroVerdict:
    return L0MicroVerdict(
        status=REJECTED,
        nonce=nonce,
        reason=str(reason),
        floor_digest=floor_digest,
        response=dict(response or {}),
    )


CHILD_BOOTSTRAP_SOURCE = r'''
import hashlib, importlib, importlib.machinery, importlib.util, json, math, os, sys, time
SEALED = "SEALED"
REJECTED = "REJECTED"
AUTHORITY = "pr2_l0_micro_verifier_v1"
SCHEMA_VERSION = 1

def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key:" + str(key))
        out[key] = value
    return out

def _bad_constant(value):
    raise ValueError("invalid JSON constant:" + str(value))

def _float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number:" + str(value))
    return parsed

def _loads(text):
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_bad_constant, parse_float=_float)

def _dumps(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)

def _safe_path(root, rel):
    if os.path.isabs(rel) or rel in {"", ".."} or rel.startswith("../") or "/../" in rel:
        raise ValueError("snapshot path escapes root")
    path = os.path.realpath(os.path.join(root, *rel.split("/")))
    if os.path.commonpath([root, path]) != root:
        raise ValueError("snapshot path escapes root")
    return path

def _floor_digest(manifest):
    return hashlib.sha256(_dumps(manifest).encode("utf-8")).hexdigest()

class _SnapshotLoader:
    def __init__(self, path, digest):
        self.path = path
        self.digest = digest
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        source = open(self.path, "rb").read()
        if hashlib.sha256(source).hexdigest() != self.digest:
            raise ImportError("snapshot digest mismatch")
        module.__file__ = self.path
        module.__loader__ = self
        exec(compile(source, self.path, "exec"), module.__dict__)

class _NamespaceLoader:
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        module.__path__ = []

class _SnapshotFinder:
    def __init__(self, root, manifest):
        self.root = root
        self.manifest = manifest
        module_names = [name for name in manifest if not name.startswith("@source:")]
        self.packages = {".".join(name.split(".")[:i]) for name in module_names for i in range(1, len(name.split(".")))}
    def find_spec(self, fullname, path=None, target=None):
        entry = self.manifest.get(fullname)
        if entry is not None:
            origin = _safe_path(self.root, entry["path"])
            return importlib.util.spec_from_loader(fullname, _SnapshotLoader(origin, entry["sha256"]), origin=origin)
        if fullname in self.packages:
            spec = importlib.machinery.ModuleSpec(fullname, _NamespaceLoader(), is_package=True)
            spec.submodule_search_locations = []
            return spec
        return None

def _stdlib_paths():
    out = []
    for raw in sys.path:
        path = os.path.realpath(str(raw))
        low = path.lower()
        if path and "site-packages" not in low and "dist-packages" not in low:
            out.append(path)
    return out

def _install_loader(root, manifest, stdlib_paths):
    sys.path[:] = list(stdlib_paths)
    sys.meta_path[:] = [_SnapshotFinder(root, manifest), importlib.machinery.BuiltinImporter, importlib.machinery.FrozenImporter, importlib.machinery.PathFinder]

def _response(verdict, reason, nonce, floor, trace, verifier, domain=None):
    print(_dumps({"schema_version": SCHEMA_VERSION, "authority": AUTHORITY, "nonce": nonce, "floor_digest": floor, "verdict": verdict, "reason": str(reason), "stage_trace": list(trace), "verifier_module": str(verifier), "domain": ({} if domain is None else domain)}))

def main():
    trace = []
    nonce = floor = verifier_module = ""
    try:
        request = _loads(sys.stdin.read())
        required = {"schema_version", "authority", "nonce", "snapshot_root", "manifest", "floor_digest", "verifier_module", "verifier_function", "payload", "poison_sys_path"}
        if set(request.keys()) != required:
            raise ValueError("request shape invalid")
        if request["schema_version"] != SCHEMA_VERSION or request["authority"] != AUTHORITY:
            raise ValueError("request authority invalid")
        nonce = str(request["nonce"])
        verifier_module = str(request["verifier_module"])
        root = os.path.realpath(str(request["snapshot_root"]))
        manifest = request["manifest"]
        if not isinstance(manifest, dict):
            raise ValueError("manifest invalid")
        for name, entry in manifest.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                raise ValueError("manifest entry invalid")
            if hashlib.sha256(open(_safe_path(root, str(entry["path"])), "rb").read()).hexdigest() != str(entry["sha256"]):
                raise ValueError("manifest digest mismatch")
        floor = _floor_digest(manifest)
        if floor != str(request["floor_digest"]):
            raise ValueError("floor digest mismatch")
        trace.append("floor_verified")
        stdlib_paths = _stdlib_paths()
        for raw_path in request.get("poison_sys_path", []):
            sys.path.insert(0, str(raw_path))
        _install_loader(root, manifest, stdlib_paths)
        trace.append("loader_installed")
        verifier = importlib.import_module(verifier_module)
        trace.append("verifier_imported")
        result = getattr(verifier, str(request["verifier_function"]))({"nonce": nonce, "payload": request["payload"]})
        trace.append("verifier_ran")
        if not isinstance(result, dict) or result.get("verdict") not in {SEALED, REJECTED}:
            raise ValueError("verifier result invalid")
        _response(result["verdict"], result.get("reason", ""), result.get("nonce", nonce), floor, trace, verifier_module, result.get("domain", {}))
    except BaseException as exc:
        _response(REJECTED, type(exc).__name__ + ":" + str(exc), nonce, floor, trace, verifier_module)
    return 0

raise SystemExit(main())
'''
