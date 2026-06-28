"""PR2-b true verifier child for L0 supervisor sealing.

This module is loaded from the L0 hashed source snapshot.  It owns domain
verification only: candidate replay, terminal frontier rebuilding, fixed-witness
verification, and project precheck.  It never builds the supervisor seal and
never receives a checkpoint write handle.
"""

from __future__ import annotations

import base64
from collections.abc import Iterable
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import sys
import sysconfig
import tempfile
import traceback
from typing import Any, Mapping

SEALED = "SEALED"
REJECTED = "REJECTED"
DOMAIN_AUTHORITY = "pr2_l0_true_supervisor_domain_v1"
DOMAIN_SCHEMA_VERSION = 1
FLOOR_AUTHORITY = "pr2_l0_dependency_floor_manifest_v1"
FLOOR_ROOT_SENTINEL = "PYTHON_SYSCONFIG_PURELIB"
IMPORT_FILE_SUFFIXES = tuple(
    importlib.machinery.SOURCE_SUFFIXES + importlib.machinery.EXTENSION_SUFFIXES
)


def verify(request: dict[str, object]) -> dict[str, object]:
    nonce = str(request.get("nonce", ""))
    payload = request.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    if payload.get("action") != "supervisor_domain":
        return {"verdict": REJECTED, "nonce": nonce, "reason": "unsupported_action"}
    try:
        _install_third_party_floor(payload.get("dependency_floor"))
        domain = _verify_supervisor_domain(payload, nonce=nonce)
    except Exception as exc:  # noqa: BLE001
        detail = "|".join(traceback.format_exc(limit=8).splitlines()[-8:])
        return {
            "verdict": REJECTED,
            "nonce": nonce,
            "reason": f"true_verifier_exception:{type(exc).__name__}:{exc}:{detail}",
        }
    return {
        "verdict": SEALED,
        "nonce": nonce,
        "reason": "domain_verified",
        "domain": domain,
    }


class _StdlibOnlyPathFinder:
    def __init__(self, stdlib_paths: list[Path]) -> None:
        self.stdlib_paths = [path.resolve() for path in stdlib_paths]

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> object:
        if path is None:
            search_path = [str(path) for path in self.stdlib_paths]
        elif isinstance(path, (list, tuple)):
            search_path = []
            for raw_path in path:
                candidate = Path(str(raw_path)).resolve()
                if _is_within_any(candidate, self.stdlib_paths):
                    search_path.append(str(candidate))
        else:
            return None
        if not search_path:
            return None
        return importlib.machinery.PathFinder.find_spec(fullname, search_path, target)


class _RestrictedThirdPartyFinder:
    def __init__(
        self,
        floor_root: Path,
        *,
        allowed_top_level: frozenset[str],
        allowed_files: Mapping[Path, str],
        allowed_package_dirs: frozenset[Path],
        allowed_namespace_dirs: Mapping[str, frozenset[Path]],
    ) -> None:
        self.floor_root = floor_root.resolve()
        self.allowed_top_level = allowed_top_level
        self.allowed_files = {
            path.resolve(): str(sha256) for path, sha256 in allowed_files.items()
        }
        self.allowed_package_dirs = frozenset(path.resolve() for path in allowed_package_dirs)
        self.allowed_namespace_dirs = {
            str(name): frozenset(path.resolve() for path in paths)
            for name, paths in allowed_namespace_dirs.items()
        }

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> object:
        top_level = fullname.split(".", 1)[0]
        if top_level not in self.allowed_top_level:
            return None
        if path is None:
            search_path = [str(self.floor_root)]
        elif isinstance(path, Iterable) and not isinstance(path, (str, bytes)):
            search_path = [str(item) for item in path]
        else:
            return None
        for raw_path in search_path:
            candidate = Path(raw_path).resolve()
            try:
                if os.path.commonpath([str(self.floor_root), str(candidate)]) != str(self.floor_root):
                    return None
            except ValueError:
                return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, search_path, target)
        if spec is None:
            return None
        locations = getattr(spec, "submodule_search_locations", None)
        if locations is not None:
            package_dirs: list[Path] = []
            for raw_location in list(locations):
                location = Path(str(raw_location)).resolve()
                if location not in self.allowed_package_dirs:
                    return None
                package_dirs.append(location)
        origin = getattr(spec, "origin", None)
        if origin in {None, "namespace"}:
            namespace_dirs = self.allowed_namespace_dirs.get(fullname)
            if namespace_dirs is None or not locations:
                return None
            if any(path not in namespace_dirs for path in package_dirs):
                return None
        elif origin in {"built-in", "frozen"}:
            return None
        else:
            origin_path = Path(str(origin)).resolve()
            expected_sha256 = self.allowed_files.get(origin_path)
            if expected_sha256 is None:
                return None
            origin_suffix = origin_path.suffix
            if origin_suffix in importlib.machinery.SOURCE_SUFFIXES:
                spec.loader = _RehashingSourceFileLoader(
                    fullname, str(origin_path), expected_sha256=expected_sha256
                )
            elif origin_suffix in importlib.machinery.EXTENSION_SUFFIXES:
                spec.loader = _RehashingExtensionFileLoader(
                    fullname, str(origin_path), expected_sha256=expected_sha256
                )
            else:
                return None
        return spec


def _dependency_floor_root(raw_root: object) -> Path:
    if raw_root == FLOOR_ROOT_SENTINEL:
        configured = sysconfig.get_paths().get("purelib")
        if not configured:
            raise ValueError("dependency floor sysconfig purelib unavailable")
        return Path(configured).resolve()
    return Path(str(raw_root)).resolve()


def _install_third_party_floor(raw_floor: object) -> None:
    if not isinstance(raw_floor, Mapping):
        raise ValueError("dependency floor missing")
    required = {
        "schema_version",
        "authority",
        "floor_root",
        "allowed_top_level",
        "files",
        "manifest_digest",
        "named_tcb",
    }
    if set(raw_floor.keys()) != required:
        raise ValueError("dependency floor fields invalid")
    if _strict_int(raw_floor.get("schema_version"), "dependency_floor.schema_version") != 1:
        raise ValueError("dependency floor schema invalid")
    if raw_floor.get("authority") != FLOOR_AUTHORITY:
        raise ValueError("dependency floor authority invalid")
    allowed = raw_floor.get("allowed_top_level")
    allowed_values = [str(item) for item in allowed] if isinstance(allowed, list) else []
    if (
        not allowed_values
        or allowed_values != sorted(set(allowed_values))
        or any(not _valid_top_level_name(item) for item in allowed_values)
    ):
        raise ValueError("dependency floor allowed roots invalid")
    named_tcb = raw_floor.get("named_tcb")
    named_tcb_violation = _dependency_named_tcb_violation(named_tcb, allowed_values)
    if named_tcb_violation is not None:
        raise ValueError(named_tcb_violation)
    manifest_digest = raw_floor.get("manifest_digest")
    manifest_without_digest = {
        "schema_version": raw_floor.get("schema_version"),
        "authority": raw_floor.get("authority"),
        "floor_root": raw_floor.get("floor_root"),
        "allowed_top_level": allowed_values,
        "files": raw_floor.get("files"),
        "named_tcb": named_tcb,
    }
    if not _is_lower_sha256(manifest_digest) or _canonical_digest(manifest_without_digest) != str(manifest_digest):
        raise ValueError("dependency floor manifest digest mismatch")
    root = _dependency_floor_root(raw_floor.get("floor_root"))
    if not root.is_dir():
        raise ValueError("dependency floor root invalid")
    files = raw_floor.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ValueError("dependency floor files invalid")
    allowed_files: dict[Path, str] = {}
    allowed_package_dirs: set[Path] = {root}
    allowed_namespace_dirs: dict[str, set[Path]] = {}
    file_top_level: set[str] = set()
    for raw_rel, raw_entry in sorted(files.items()):
        rel = _safe_rel(raw_rel)
        top_level = _dependency_file_top_level(rel)
        if top_level is not None:
            file_top_level.add(top_level)
        if not isinstance(raw_entry, Mapping) or set(raw_entry.keys()) != {"sha256", "size"}:
            raise ValueError(f"dependency floor entry invalid:{rel}")
        expected_sha = str(raw_entry.get("sha256"))
        expected_size = _strict_int(raw_entry.get("size"), f"dependency_floor.{rel}.size")
        if not _is_lower_sha256(expected_sha) or expected_size < 0:
            raise ValueError(f"dependency floor digest invalid:{rel}")
        path = (root / Path(*rel.split("/"))).resolve()
        if os.path.commonpath([str(root), str(path)]) != str(root):
            raise ValueError(f"dependency floor path escapes root:{rel}")
        data = path.read_bytes()
        if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError(f"dependency floor digest mismatch:{rel}")
        allowed_files[path] = expected_sha
        _index_dependency_package_dirs(
            root=root,
            rel=rel,
            allowed_package_dirs=allowed_package_dirs,
            allowed_namespace_dirs=allowed_namespace_dirs,
        )
    missing_top_level = sorted(file_top_level - set(allowed_values))
    if missing_top_level:
        raise ValueError(f"dependency floor allowed roots missing:{missing_top_level[0]}")
    restricted_finder = _RestrictedThirdPartyFinder(
        root,
        allowed_top_level=frozenset(allowed_values),
        allowed_files=allowed_files,
        allowed_package_dirs=frozenset(allowed_package_dirs),
        allowed_namespace_dirs={
            name: frozenset(paths) for name, paths in allowed_namespace_dirs.items()
        },
    )
    stdlib_finder = _StdlibOnlyPathFinder(_stdlib_paths())
    sys.meta_path[:] = [
        finder
        for finder in sys.meta_path
        if finder is not importlib.machinery.PathFinder
        and not isinstance(finder, (_RestrictedThirdPartyFinder, _StdlibOnlyPathFinder))
    ]
    sys.meta_path.extend([restricted_finder, stdlib_finder])


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        return os.path.commonpath([str(root), str(candidate.resolve())]) == str(root)
    except ValueError:
        return False


def _is_within_any(candidate: Path, roots: list[Path]) -> bool:
    return any(_is_within(root, candidate) for root in roots)


def _stdlib_paths() -> list[Path]:
    paths: list[Path] = []
    for raw_path in sys.path:
        try:
            candidate = Path(str(raw_path)).resolve()
        except Exception:
            continue
        lowered = str(candidate).lower()
        if not candidate.exists():
            continue
        if "site-packages" in lowered or "dist-packages" in lowered:
            continue
        paths.append(candidate)
    return paths


def _valid_top_level_name(value: object) -> bool:
    return isinstance(value, str) and value.isidentifier()


def _dependency_file_top_level(rel: str) -> str | None:
    first = rel.split("/", 1)[0]
    first_path = Path(first)
    if first_path.suffix in {".py", ".pyi", *importlib.machinery.EXTENSION_SUFFIXES}:
        if first_path.stem.isidentifier():
            return first_path.stem
    if first.isidentifier():
        return first
    return None


def _dependency_named_tcb_violation(named_tcb: object, allowed_top_level: list[str]) -> str | None:
    if not isinstance(named_tcb, Mapping):
        return "dependency floor named_tcb invalid"
    closure = named_tcb.get("third_party_closure")
    if not isinstance(closure, Mapping):
        return "dependency floor third_party_closure missing"
    allowed = set(allowed_top_level)
    if set(str(key) for key in closure.keys()) != allowed:
        return "dependency floor third_party_closure mismatch"
    for key, value in closure.items():
        if str(key) not in allowed or value != "NAMED-TCB":
            return "dependency floor third_party_closure invalid"
    return None


def _index_dependency_package_dirs(
    *,
    root: Path,
    rel: str,
    allowed_package_dirs: set[Path],
    allowed_namespace_dirs: dict[str, set[Path]],
) -> None:
    parts = rel.split("/")
    if not parts:
        return
    filename = parts[-1]
    package_parts = parts[:-1]
    if "." not in filename and package_parts:
        return
    if filename == "__init__.py":
        package_parts = parts[:-1]
    if not package_parts or not all(part.isidentifier() for part in package_parts):
        return
    for index in range(1, len(package_parts) + 1):
        prefix = package_parts[:index]
        module_name = ".".join(prefix)
        directory = (root / Path(*prefix)).resolve()
        allowed_package_dirs.add(directory)
        allowed_namespace_dirs.setdefault(module_name, set()).add(directory)


def _verify_supervisor_domain(payload: Mapping[str, Any], *, nonce: str) -> dict[str, Any]:
    required = {
        "action",
        "schema_version",
        "authority",
        "project_root",
        "authority_state",
        "authority_state_b64",
        "strong_keys",
        "proposal_final_result_digest",
        "proposal_terminal_frontier_evidence_digest",
        "proposal_candidate_records_digest",
        "dependency_floor",
    }
    if set(payload.keys()) != required:
        raise ValueError("supervisor domain request fields invalid")
    if _strict_int(payload.get("schema_version"), "domain.schema_version") != DOMAIN_SCHEMA_VERSION:
        raise ValueError("supervisor domain request schema invalid")
    if payload.get("authority") != DOMAIN_AUTHORITY:
        raise ValueError("supervisor domain request authority invalid")
    project_root = Path(_strict_string(payload.get("project_root"), "project_root")).resolve()
    _materialize_import_default_artifacts(project_root)
    authority_state = _json_copy(_require_mapping(payload.get("authority_state"), "authority_state"))
    authority_bytes = base64.b64decode(
        _strict_string(payload.get("authority_state_b64"), "authority_state_b64").encode("ascii"),
        validate=True,
    )
    if _json_copy(json.loads(authority_bytes.decode("utf-8"))) != authority_state:
        raise ValueError("authority_state_bytes_mismatch")
    strong_keys = _string_list(payload.get("strong_keys"))
    if strong_keys != sorted(str(key) for key in strong_keys):
        raise ValueError("strong_keys_not_sorted")

    final_result = _require_mapping(authority_state.get("final_result"), "final_result")
    certified_final_result = dict(final_result)
    certified_final_result["search_status"] = "CERTIFIED"

    replayed_records, replay_violations = _project_candidate_records_direct(
        state=authority_state,
        project_root=project_root,
        strong_keys=strong_keys,
    )
    if replay_violations:
        first_key = sorted(replay_violations)[0]
        raise ValueError(f"terminal candidate sink replay failed:{replay_violations[first_key]}")

    durable_records, public_records, fixed_verdict = _run_fixed_witness_direct(
        state=authority_state,
        project_root=project_root,
        candidate_records=replayed_records,
        final_result=certified_final_result,
    )
    fixed_violations: dict[str, str] = {}
    if getattr(fixed_verdict, "publishable", False) is not True:
        fixed_violations[str(getattr(fixed_verdict, "candidate_key", None) or "*")] = str(
            getattr(fixed_verdict, "reason", None) or "terminal_fixed_witness_rejected"
        )
    if fixed_violations:
        first_key = sorted(fixed_violations)[0]
        raise ValueError(f"terminal fixed witness verifier failed:{fixed_violations[first_key]}")

    from src.search.certified_frontier import (
        build_terminal_frontier_evidence,
        candidate_generation_kwargs,
        generate_candidate_sizes,
    )
    from src.search.exact_campaign import terminal_certified_final_result_project_precheck_violation

    proposal_evidence = _require_mapping(
        authority_state.get("terminal_frontier_evidence"),
        "terminal_frontier_evidence",
    )
    candidate_generation = _require_mapping(
        proposal_evidence.get("candidate_generation"),
        "candidate_generation",
    )
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    evidence = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=public_records,
        final_result=certified_final_result,
        candidate_generation=candidate_generation,
    )
    scratch_state = dict(authority_state)
    scratch_state["final_result"] = certified_final_result
    scratch_state["final_status"] = "CERTIFIED"
    scratch_state["terminal_frontier_evidence"] = evidence
    scratch_state["candidates"] = durable_records
    scratch_state.pop("supervisor_proposal", None)
    precheck_reason = terminal_certified_final_result_project_precheck_violation(
        scratch_state,
        project_root=project_root,
    )
    if precheck_reason is not None:
        raise ValueError(f"terminal project precheck failed:{precheck_reason}")

    final_digest = _canonical_digest(certified_final_result)
    evidence_digest = _canonical_digest(evidence)
    records_digest = _canonical_digest(_stable_fixed_witness_candidate_records(durable_records))
    if final_digest != payload.get("proposal_final_result_digest"):
        raise ValueError("proposal final_result mismatch after domain verification")
    if evidence_digest != payload.get("proposal_terminal_frontier_evidence_digest"):
        raise ValueError("proposal terminal_frontier_evidence mismatch after domain verification")
    if records_digest != payload.get("proposal_candidate_records_digest"):
        raise ValueError("proposal candidate_records mismatch after domain verification")

    return {
        "schema_version": DOMAIN_SCHEMA_VERSION,
        "authority": DOMAIN_AUTHORITY,
        "nonce": nonce,
        "verdict": SEALED,
        "reason": "domain_verified",
        "strong_keys": list(strong_keys),
        "final_result": certified_final_result,
        "terminal_frontier_evidence": evidence,
        "candidate_records": durable_records,
        "final_result_digest": final_digest,
        "terminal_frontier_evidence_digest": evidence_digest,
        "candidate_records_digest": records_digest,
        "fixed_witness_publishable": bool(getattr(fixed_verdict, "publishable", False)),
        "sink_replay_violations": {},
        "fixed_witness_violations": {},
        "tcb": {
            "python_interpreter": "NAMED-TCB",
            "stdlib": "NAMED-TCB",
            "third_party_native": "NAMED-TCB",
            "os_process_file_isolation": "NAMED-TCB",
            "windows_write_isolation_residual": "protocol_only_child_snapshot_no_write_fd_pr2c_linux_uid_namespace_pending",
        },
    }


def _project_candidate_records_direct(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    strong_keys: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    from src.search.candidate_proof_replay import (
        CANDIDATE_PROOF_AUTHORITY,
        CANDIDATE_PROOF_FIELD,
        CANDIDATE_PROOF_SCHEMA_VERSION,
        _execute_isolated_replay_request,
        _json_copy,
        _replay_response_violation,
        candidate_proof_shape_violation,
        canonical_digest,
    )

    raw_records = state.get("candidates")
    if not isinstance(raw_records, Mapping):
        return {}, {"*": "candidate_sink_replay_records_missing"}
    expected_proofs: dict[str, dict[str, Any]] = {}
    violations: dict[str, str] = {}
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
            campaign_path=None,
        )
        if violation is not None:
            violations[key] = violation
            continue
        expected_proofs[key] = _json_copy(proof)
    if set(expected_proofs) | set(violations) != set(strong_keys):
        violations["*"] = "candidate_sink_replay_strong_key_coverage_mismatch"
    if violations:
        return {}, violations
    if not expected_proofs:
        return {
            str(key): _json_copy(value)
            for key, value in raw_records.items()
            if isinstance(value, Mapping)
        }, {}
    request = {
        "schema_version": CANDIDATE_PROOF_SCHEMA_VERSION,
        "authority": CANDIDATE_PROOF_AUTHORITY,
        "nonce": hashlib.sha256(_canonical_bytes(expected_proofs)).hexdigest(),
        "project_root": str(project_root),
        "expected_proofs": [_json_copy(expected_proofs[key]) for key in sorted(expected_proofs)],
    }
    response = _execute_isolated_replay_request(request)
    envelope_violation = _replay_response_violation(
        response=response,
        project_root=project_root,
        expected_proofs=expected_proofs,
    )
    if envelope_violation is not None:
        return {}, {key: envelope_violation for key in expected_proofs}
    results = response.get("results")
    if not isinstance(results, list):
        return {}, {"*": "candidate_sink_replay_response_result_invalid"}
    results_by_key = {
        str(item.get("candidate_key")): item for item in results if isinstance(item, Mapping)
    }
    verified: dict[str, dict[str, Any]] = {}
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
            stored_solution = record.get("solution")
            if not isinstance(stored_solution, Mapping):
                violations[key] = f"candidate_sink_replay_solution_missing:{key}"
                continue
            if proof.get("solution_digest") != canonical_digest(stored_solution):
                violations[key] = f"candidate_sink_replay_solution_binding_mismatch:{key}"
                continue
            replayed_record["solution"] = _json_copy(stored_solution)
        else:
            replayed_record.pop("solution", None)
        verified[key] = replayed_record
    if violations:
        return {}, violations
    projected: dict[str, dict[str, Any]] = {}
    for raw_key, raw_record in raw_records.items():
        key = str(raw_key)
        if not isinstance(raw_record, Mapping):
            continue
        projected[key] = verified.get(key, _json_copy(raw_record))
    return projected, {}


def _materialize_import_default_artifacts(project_root: Path) -> None:
    del project_root


def _run_fixed_witness_direct(
    *,
    state: Mapping[str, Any],
    project_root: Path,
    candidate_records: dict[str, dict[str, Any]],
    final_result: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], Any]:
    from src.search.candidate_proof_replay import _materialize_replay_snapshot
    from src.search.exact_campaign import compute_exact_artifact_hashes
    from src.search.terminal_fixed_witness_verifier import (
        _apply_terminal_fixed_witness_audit_fields,
        _copy_candidate_records,
        _identity_from_current_records,
        _project_terminal_fixed_witness_records_from_capsule,
        canonical_state_bytes_for_fixed_witness,
        verify_terminal_fixed_witness,
    )

    authority_state = _json_copy(state)
    authority_state["candidates"] = _json_copy(candidate_records)
    authority_state["final_result"] = _json_copy(final_result)
    current_hashes = compute_exact_artifact_hashes(project_root)
    with tempfile.TemporaryDirectory(prefix="zmd_pr2_true_fixed_witness_") as temp_dir:
        replay_project_root = Path(temp_dir) / "project"
        _materialize_replay_snapshot(
            project_root=project_root,
            replay_project_root=replay_project_root,
            current_artifact_hashes=current_hashes,
        )
        state_copy = _json_copy(authority_state)
        verdict = verify_terminal_fixed_witness(
            state=state_copy,
            project_root=replay_project_root,
            serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state_copy),
        )
    durable_records = _copy_candidate_records(candidate_records)
    identity = _identity_from_current_records(durable_records, final_result)
    record = durable_records.get(identity.candidate_key)
    if isinstance(record, dict):
        _apply_terminal_fixed_witness_audit_fields(
            record,
            verdict=verdict,
            publishable=bool(verdict.publishable),
            projected_status="CERTIFIED" if verdict.publishable else "UNPROVEN",
            rejected_reason=verdict.reason,
        )
    public_projection = _project_terminal_fixed_witness_records_from_capsule(
        candidate_records=_copy_candidate_records(candidate_records),
        final_result=final_result,
        verdict=verdict,
    )
    return durable_records, public_projection.candidate_records, verdict


def _strict_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return int(value)


def _strict_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return dict(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("expected string list")
    return [str(item) for item in value]


def _json_copy(payload: Any) -> Any:
    return json.loads(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


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


def _stable_fixed_witness_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_fields = set(payload.keys())
    missing = sorted(_FIXED_WITNESS_STABLE_FIELDS - raw_fields)
    if missing:
        raise ValueError(f"terminal fixed witness verdict missing stable field:{missing[0]}")
    unexpected = sorted(raw_fields - _FIXED_WITNESS_STABLE_FIELDS - _FIXED_WITNESS_VOLATILE_FIELDS)
    if unexpected:
        raise ValueError(f"terminal fixed witness verdict unknown durable field:{unexpected[0]}")
    return {field: _json_copy(payload[field]) for field in _FIXED_WITNESS_STABLE_FIELD_ORDER}


def _stable_fixed_witness_candidate_records(records: Mapping[str, Any]) -> dict[str, Any]:
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
            summary[_FIXED_WITNESS_AUDIT_FIELD] = _stable_fixed_witness_payload(raw_verdict)
            record["proof_summary"] = summary
        projected[str(raw_key)] = record
    return projected


def _is_lower_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _safe_rel(raw_path: Any) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("dependency floor path invalid")
    rel = raw_path.replace("\\", "/")
    if rel.startswith("/") or ":" in rel or rel in {".", ".."} or rel.startswith("../") or "/../" in rel:
        raise ValueError("dependency floor path escapes root")
    return rel


class _RehashingSourceFileLoader(importlib.machinery.SourceFileLoader):
    """Source loader that re-reads the file ONCE at load time and re-verifies its
    sha256 against the floor-pinned digest, then compiles from those exact bytes.

    Closes the install-time -> load-time TOCTOU window: ``_install_third_party_floor``
    hashes every floor file when the floor is installed, but a standard
    ``SourceFileLoader`` re-reads the file from disk at import time without
    re-hashing, so a same-path swap between install and import would otherwise
    load unverified Python code into the deciding verifier.  Always compiles
    straight from the re-verified source bytes and never trusts a cached ``.pyc``
    (bytecode files are not part of the floor)."""

    def __init__(self, fullname: str, path: str, *, expected_sha256: str) -> None:
        super().__init__(fullname, path)
        self._expected_sha256 = expected_sha256

    def get_data(self, path: str) -> bytes:
        data = super().get_data(path)
        if hashlib.sha256(data).hexdigest() != self._expected_sha256:
            raise ImportError(f"dependency floor load-time digest mismatch:{path}")
        return data

    def get_code(self, fullname: str) -> Any:
        source_bytes = self.get_data(self.path)
        return compile(source_bytes, self.path, "exec", dont_inherit=True)


class _RehashingExtensionFileLoader(importlib.machinery.ExtensionFileLoader):
    """Native loader that re-hashes the extension file immediately before the
    dynamic load.  This narrows the TOCTOU window for native dependencies but
    cannot eliminate it (the OS dynamic linker re-reads the path, not our
    bytes); native third-party code therefore stays a declared NAMED-TCB
    pending PR2-c OS-level isolation."""

    def __init__(self, fullname: str, path: str, *, expected_sha256: str) -> None:
        super().__init__(fullname, path)
        self._expected_sha256 = expected_sha256

    def create_module(self, spec: Any) -> Any:
        data = Path(self.path).read_bytes()
        if hashlib.sha256(data).hexdigest() != self._expected_sha256:
            raise ImportError(f"dependency floor load-time digest mismatch:{self.path}")
        return super().create_module(spec)
