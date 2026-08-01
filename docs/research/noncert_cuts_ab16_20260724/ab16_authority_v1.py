#!/usr/bin/env python3
"""Append-only retry authority for the research-only AB16 campaign.

The scientific preregistration is immutable.  Execution attempts are not:
an incomplete attempt remains as evidence and the same fixed slot may be
retried after a clean committed code repair.  No record produced here grants
cut, witness, bound, production, certified, or Stage-B authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ab16_campaign_bootstrap_v1 as bootstrap  # noqa: E402
import ab16_contract_v1 as contract  # noqa: E402


INPUT_SET_SCHEMA = "noncert-cuts-ab16-attempt-input-set-v1"
ATTEMPT_OPEN_SCHEMA = "noncert-cuts-ab16-attempt-open-v1"
SELECTION_BINDING_SCHEMA = "noncert-cuts-ab16-attempt-selection-binding-v1"
RESULT_ENVELOPE_SCHEMA = "noncert-cuts-ab16-attempt-result-envelope-v1"
REPLAY_SCHEMA = "noncert-cuts-ab16-retry-campaign-replay-v1"

CREDIBLE_TERMINAL = "CREDIBLE_TERMINAL"
CREDIBILITY_INCOMPLETE = "CREDIBILITY_INCOMPLETE"
ATTEMPT_RE = re.compile(r"attempt-([0-9]{4,})\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_HEAD_RE = re.compile(r"[0-9a-f]{40}\Z")
ROLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")

RESEARCH_ONLY_AUTHORIZATIONS = {
    "cut_authorized": False,
    "family_global_soundness_authorized": False,
    "global_claim_authorized": False,
    "lower_bound_authorized": False,
    "mathematical_claim_authorized": False,
    "optimality_authorized": False,
    "production_certified_authorized": False,
    "stage_b_promotion_authorized": False,
    "upper_bound_authorized": False,
    "witness_authorized": False,
}

EXECUTION_TOOL_FILES = {
    "ab16_authority": "ab16_authority_v1.py",
    "ab16_campaign_bootstrap": "ab16_campaign_bootstrap_v1.py",
    "ab16_contract": "ab16_contract_v1.py",
    "ab16_terminal_gate": "ab16_terminal_gate_v1.py",
    "baseline_admission": "baseline_admission_v1.py",
    "baseline_rebuild": "baseline_rebuild_v1.py",
    "cut_free_incumbent_replay": "cut_free_incumbent_replay_v1.py",
    "organic_arm_replay": "organic_arm_replay_v1.py",
    "organic_arm_runner": "organic_arm_runner_v1.py",
    "organic_resource_lifecycle": "organic_resource_lifecycle_v1.py",
    "organic_resource_verifier": "organic_resource_verifier_v1.py",
    "organic_unit_orchestrator": "organic_unit_orchestrator_v1.py",
}


class AuthorityError(RuntimeError):
    """The retry campaign could not be interpreted without ambiguity."""


def canonical_json(value: object) -> bytes:
    return contract.canonical_json_bytes(value)


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise AuthorityError(f"{label} must have the exact key set")
    return value


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _snapshot(path: Path | str) -> tuple[bytes, dict[str, object]]:
    absolute = _absolute(path)
    try:
        descriptor = os.open(absolute, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise AuthorityError(f"cannot open regular input: {absolute}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AuthorityError(f"input is not a regular file: {absolute}")
        chunks: list[bytes] = []
        while block := os.read(descriptor, 1024 * 1024):
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    raw = b"".join(chunks)
    if any(getattr(before, field) != getattr(after, field) for field in fields) or len(raw) != after.st_size:
        raise AuthorityError(f"input changed during read: {absolute}")
    return raw, {
        "mode": stat.S_IMODE(after.st_mode),
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _load_record(path: Path | str, label: str) -> tuple[Mapping[str, Any], dict[str, object]]:
    raw, identity = _snapshot(path)
    try:
        value = contract.strict_loads(raw)
    except contract.ContractError as exc:
        raise AuthorityError(f"{label} is not canonical strict JSON") from exc
    if type(value) is not dict:
        raise AuthorityError(f"{label} must be a JSON object")
    return value, identity


def _write_bytes_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    absolute = _absolute(path)
    try:
        parent_fd = os.open(absolute.parent, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise AuthorityError(f"output parent is unavailable: {absolute.parent}") from exc
    try:
        descriptor = os.open(
            absolute.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise AuthorityError(f"short write: {absolute}")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(parent_fd)
    except OSError as exc:
        raise AuthorityError(f"no-overwrite publication failed: {absolute}") from exc
    finally:
        os.close(parent_fd)
    _raw, identity = _snapshot(absolute)
    if _raw != raw:
        raise AuthorityError(f"published bytes changed: {absolute}")
    return identity


def _write_record(path: Path, value: object) -> dict[str, object]:
    return _write_bytes_exclusive(path, canonical_json(value))


def _make_directory(path: Path) -> None:
    absolute = _absolute(path)
    try:
        absolute.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise AuthorityError(f"no-overwrite directory already exists: {absolute}") from exc
    metadata = absolute.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or absolute.is_symlink():
        raise AuthorityError(f"created path is not a real directory: {absolute}")


def _existing_directory(path: Path, label: str) -> Path:
    absolute = _absolute(path)
    try:
        metadata = absolute.lstat()
    except OSError as exc:
        raise AuthorityError(f"{label} is unavailable: {absolute}") from exc
    if absolute.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise AuthorityError(f"{label} is not a real directory: {absolute}")
    return absolute


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _exact_mapping(value, {"mode", "path", "sha256", "size_bytes"}, label)
    if (
        type(record["mode"]) is not int
        or not 0 <= record["mode"] <= 0o7777
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise AuthorityError(f"{label} is malformed")
    return record


def _verify_identity(value: object, label: str) -> Mapping[str, Any]:
    expected = _identity(value, label)
    _raw, actual = _snapshot(expected["path"])
    if actual != expected:
        raise AuthorityError(f"{label} bytes or metadata drifted")
    return expected


def _identity_map(value: object, label: str, *, verify: bool) -> Mapping[str, Mapping[str, Any]]:
    if type(value) is not dict or not value:
        raise AuthorityError(f"{label} must be a non-empty object")
    result: dict[str, Mapping[str, Any]] = {}
    for role, member in value.items():
        if type(role) is not str or ROLE_RE.fullmatch(role) is None:
            raise AuthorityError(f"{label} contains an invalid role")
        result[role] = _verify_identity(member, f"{label}.{role}") if verify else _identity(member, f"{label}.{role}")
    return result


def _load_preregistration(path: Path | str) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _load_record(path, "scientific preregistration")
    try:
        bootstrap.validate_path_preregistration(record, campaign_dir=record.get("campaign_dir", ""))
    except (bootstrap.BootstrapError, TypeError, ValueError) as exc:
        raise AuthorityError("scientific preregistration drifted") from exc
    if record["arm_sequence"] != list(contract.ARM_SEQUENCE):
        raise AuthorityError("scientific arm order differs from the classifier")
    return record, identity


def _scientific_source_paths(
    preregistration_path: Path,
    preregistration: Mapping[str, Any],
    slot: str,
) -> dict[str, Path]:
    return {
        "baseline_admission": Path(preregistration["baseline_admission_path"]),
        "baseline_fixed_replay": Path(preregistration["baseline_fixed_replay_path"]),
        "baseline_incumbent": Path(preregistration["baseline_incumbent_path"]),
        "baseline_rebuilt_metadata": Path(preregistration["baseline_rebuilt_metadata_path"]),
        "baseline_rebuilt_model": Path(preregistration["baseline_rebuilt_model_path"]),
        "classification_contract": Path(preregistration["classification_contract_path"]),
        "common_prestate": Path(preregistration["common_prestate_path"]),
        "scientific_manifest": Path(preregistration["manifest_path"]),
        "scientific_preregistration": preregistration_path,
        "selected_binding": Path(preregistration["binding_paths"][slot]),
        "suite_selection": Path(preregistration["suite_selection_path"]),
    }


def _execution_tool_paths(extra: Mapping[str, Path | str] | None) -> dict[str, Path]:
    paths = {role: RESEARCH_DIR / filename for role, filename in EXECUTION_TOOL_FILES.items()}
    for role, path in (extra or {}).items():
        if ROLE_RE.fullmatch(role) is None or role in paths:
            raise AuthorityError(f"invalid or duplicate execution-tool role: {role}")
        paths[role] = _absolute(path)
    return paths


def _capture_sources(paths: Mapping[str, Path], label: str) -> dict[str, tuple[bytes, dict[str, object]]]:
    if not paths:
        raise AuthorityError(f"{label} set is empty")
    result: dict[str, tuple[bytes, dict[str, object]]] = {}
    for role in sorted(paths):
        if ROLE_RE.fullmatch(role) is None:
            raise AuthorityError(f"{label} role is invalid: {role}")
        result[role] = _snapshot(paths[role])
    return result


def _observe_clean_head(repository_root: Path | str) -> str:
    root = _existing_directory(_absolute(repository_root), "repository root")
    commands = (
        ("git", "diff", "--quiet", "--"),
        ("git", "diff", "--cached", "--quiet", "--"),
    )
    for command in commands:
        completed = subprocess.run(command, cwd=root, check=False, capture_output=True)
        if completed.returncode != 0:
            raise AuthorityError("repository tracked tree or index is not clean")
    completed = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    head = completed.stdout.strip()
    if completed.returncode != 0 or GIT_HEAD_RE.fullmatch(head) is None:
        raise AuthorityError("repository HEAD observation failed")
    return head


def _projection_digest(schema: str, identities: Mapping[str, Mapping[str, Any]]) -> str:
    projection = {
        "members": {
            role: {
                "mode": identities[role]["mode"],
                "sha256": identities[role]["sha256"],
                "size_bytes": identities[role]["size_bytes"],
            }
            for role in sorted(identities)
        },
        "schema": schema,
    }
    return hashlib.sha256(canonical_json(projection)).hexdigest()


def _attempt_directories(slot_root: Path) -> list[tuple[int, Path]]:
    if not slot_root.exists() and not slot_root.is_symlink():
        return []
    _existing_directory(slot_root, "slot root")
    members: list[tuple[int, Path]] = []
    for child in slot_root.iterdir():
        match = ATTEMPT_RE.fullmatch(child.name)
        if match is None or child.is_symlink() or not child.is_dir():
            raise AuthorityError(f"unknown or unsafe slot-root child: {child}")
        ordinal = int(match.group(1))
        if ordinal < 1 or child.name != f"attempt-{ordinal:04d}":
            raise AuthorityError(f"noncanonical attempt name: {child}")
        members.append((ordinal, child))
    members.sort()
    if [ordinal for ordinal, _path in members] != list(range(1, len(members) + 1)):
        raise AuthorityError(f"attempt ordinal gap under {slot_root}")
    return members


def _validate_input_set(
    attempt_dir: Path,
    preregistration_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _load_record(attempt_dir / "attempt-input-set.json", "attempt input set")
    checked = _exact_mapping(
        record,
        {
            "authorizations",
            "input_set_sha256",
            "preregistration_identity",
            "preregistration_sha256",
            "repository_head",
            "schema_version",
            "scientific_input_set_sha256",
            "source_strict_input_identities",
            "source_tool_identities",
            "strict_input_identities",
            "tool_identities",
        },
        "attempt input set",
    )
    strict_inputs = _identity_map(checked["strict_input_identities"], "strict input snapshots", verify=True)
    tools = _identity_map(checked["tool_identities"], "tool snapshots", verify=True)
    source_inputs = _identity_map(checked["source_strict_input_identities"], "strict input sources", verify=False)
    source_tools = _identity_map(checked["source_tool_identities"], "tool sources", verify=False)
    if set(strict_inputs) != set(source_inputs) or set(tools) != set(source_tools):
        raise AuthorityError("source and snapshot role sets differ")
    for snapshots, sources in ((strict_inputs, source_inputs), (tools, source_tools)):
        for role in snapshots:
            if any(snapshots[role][field] != sources[role][field] for field in ("sha256", "size_bytes")):
                raise AuthorityError(f"source/snapshot bytes differ for role {role}")
    if (
        checked["schema_version"] != INPUT_SET_SCHEMA
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["preregistration_identity"] != preregistration_identity
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or type(checked["repository_head"]) is not str
        or GIT_HEAD_RE.fullmatch(checked["repository_head"]) is None
        or checked["scientific_input_set_sha256"]
        != _projection_digest("noncert-cuts-ab16-scientific-input-set-v1", strict_inputs)
        or checked["input_set_sha256"]
        != contract.attempt_input_set_sha256(
            preregistration_sha256=checked["preregistration_sha256"],
            repository_head=checked["repository_head"],
            strict_input_identities=strict_inputs,
            tool_identities=tools,
        )
    ):
        raise AuthorityError("attempt input-set joins drifted")
    return checked, identity


def _validate_open(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, object]]:
    inputs, input_identity = _validate_input_set(attempt_dir, preregistration_identity)
    record, identity = _load_record(attempt_dir / "attempt-open.json", "attempt-open receipt")
    checked = _exact_mapping(
        record,
        {
            "attempt_dir",
            "attempt_ordinal",
            "authorizations",
            "input_set_identity",
            "input_set_sha256",
            "preregistration_sha256",
            "repository_head",
            "schema_version",
            "slot",
            "status",
        },
        "attempt-open receipt",
    )
    if (
        checked["schema_version"] != ATTEMPT_OPEN_SCHEMA
        or checked["status"] != "OPEN"
        or checked["slot"] != slot
        or checked["attempt_ordinal"] != ordinal
        or checked["attempt_dir"] != str(attempt_dir)
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["input_set_identity"] != input_identity
        or checked["input_set_sha256"] != inputs["input_set_sha256"]
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["repository_head"] != inputs["repository_head"]
    ):
        raise AuthorityError("attempt-open receipt drifted")
    return checked, inputs, identity


def _optional_selection(attempt_dir: Path) -> tuple[Mapping[str, Any] | None, dict[str, object] | None]:
    path = attempt_dir / "selection-binding.json"
    if not path.exists() and not path.is_symlink():
        return None, None
    record, identity = _load_record(path, "selection binding")
    checked = _exact_mapping(
        record,
        {"authorizations", "schema_version", "selection_identity", "status"},
        "selection binding",
    )
    _verify_identity(checked["selection_identity"], "bound selection")
    if (
        checked["schema_version"] != SELECTION_BINDING_SCHEMA
        or checked["status"] != "BOUND"
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
    ):
        raise AuthorityError("selection binding drifted")
    return checked, identity


def _optional_envelope(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration_identity: Mapping[str, Any],
    input_record: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    selection_identity: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any] | None, dict[str, object] | None]:
    path = attempt_dir / "attempt-result.json"
    if not path.exists() and not path.is_symlink():
        return None, None
    record, identity = _load_record(path, "attempt result envelope")
    checked = _exact_mapping(
        record,
        {
            "attempt_ordinal",
            "authorizations",
            "envelope_id",
            "evidence_identities",
            "failure_code",
            "input_set_identity",
            "input_set_sha256",
            "outcome",
            "preregistration_identity",
            "preregistration_sha256",
            "repository_head",
            "retry_disposition",
            "schema_version",
            "selection_binding_identity",
            "slot",
        },
        "attempt result envelope",
    )
    evidence = checked["evidence_identities"]
    if type(evidence) is not dict:
        raise AuthorityError("attempt evidence identities must be an object")
    for role, member in evidence.items():
        if type(role) is not str or ROLE_RE.fullmatch(role) is None:
            raise AuthorityError("attempt evidence role is invalid")
        _verify_identity(member, f"attempt evidence {role}")
    without_id = dict(checked)
    without_id["envelope_id"] = ""
    expected_id = hashlib.sha256(canonical_json(without_id)).hexdigest()
    if (
        checked["schema_version"] != RESULT_ENVELOPE_SCHEMA
        or checked["slot"] != slot
        or checked["attempt_ordinal"] != ordinal
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["envelope_id"] != expected_id
        or checked["preregistration_identity"] != preregistration_identity
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["input_set_identity"] != input_identity
        or checked["input_set_sha256"] != input_record["input_set_sha256"]
        or checked["repository_head"] != input_record["repository_head"]
        or checked["selection_binding_identity"] != selection_identity
    ):
        raise AuthorityError("attempt result envelope joins drifted")
    if checked["outcome"] == CREDIBLE_TERMINAL:
        if checked["failure_code"] is not None or checked["retry_disposition"] != "SLOT_CLOSED":
            raise AuthorityError("credible envelope terminal fields drifted")
        if selection_identity is None or "arm_gate" not in evidence:
            raise AuthorityError("credible envelope lacks selection or arm gate")
    elif checked["outcome"] == CREDIBILITY_INCOMPLETE:
        if (
            type(checked["failure_code"]) is not str
            or not checked["failure_code"]
            or checked["retry_disposition"] != "SAME_SLOT_RETRY_ALLOWED"
        ):
            raise AuthorityError("incomplete envelope terminal fields drifted")
    else:
        raise AuthorityError("attempt outcome is unsupported")
    return checked, identity


def replay_campaign(preregistration_path: Path | str) -> dict[str, object]:
    """Rebuild retry state from immutable attempt receipts on disk."""

    preregistration_path = _absolute(preregistration_path)
    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    state = contract.new_consumption_state()
    active: dict[str, object] | None = None
    attempts_summary: list[dict[str, object]] = []
    slot_attempt_counts: dict[str, int] = {}
    slot_scientific_digests: dict[str, str] = {}

    for slot_index, slot in enumerate(contract.ARM_SEQUENCE):
        slot_root = Path(preregistration["slot_roots"][slot])
        attempts = _attempt_directories(slot_root)
        slot_attempt_counts[slot] = len(attempts)
        if slot_index > state["next_index"] and attempts:
            raise AuthorityError("future slot contains an attempt")
        for attempt_index, (ordinal, attempt_dir) in enumerate(attempts):
            if state["next_index"] >= len(contract.ARM_SEQUENCE) or contract.ARM_SEQUENCE[state["next_index"]] != slot:
                raise AuthorityError("attempt exists after its slot closed or out of order")
            _open, inputs, _open_identity = _validate_open(
                attempt_dir,
                slot=slot,
                ordinal=ordinal,
                preregistration_identity=preregistration_identity,
            )
            input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
            previous_digest = slot_scientific_digests.setdefault(slot, inputs["scientific_input_set_sha256"])
            if previous_digest != inputs["scientific_input_set_sha256"]:
                raise AuthorityError("scientific inputs changed between retries")
            _selection, selection_binding_identity = _optional_selection(attempt_dir)
            envelope, envelope_identity = _optional_envelope(
                attempt_dir,
                slot=slot,
                ordinal=ordinal,
                preregistration_identity=preregistration_identity,
                input_record=inputs,
                input_identity=input_identity,
                selection_identity=selection_binding_identity,
            )
            summary = {
                "attempt_ordinal": ordinal,
                "envelope_identity": envelope_identity,
                "input_set_sha256": inputs["input_set_sha256"],
                "outcome": None if envelope is None else envelope["outcome"],
                "repository_head": inputs["repository_head"],
                "slot": slot,
            }
            attempts_summary.append(summary)
            if envelope is None:
                if attempt_index != len(attempts) - 1:
                    raise AuthorityError("unresolved attempt has a later sibling")
                if selection_binding_identity is not None:
                    state = contract.transition_consumption_state(
                        state,
                        {"attempt_ordinal": ordinal, "event": "SELECTION_CREATED", "reason": None, "slot": slot},
                    )
                active = {"attempt_dir": str(attempt_dir), "attempt_ordinal": ordinal, "slot": slot}
                break
            if selection_binding_identity is None:
                if envelope["outcome"] != CREDIBILITY_INCOMPLETE:
                    raise AuthorityError("credible attempt lacks a selection")
                state = contract.transition_consumption_state(
                    state,
                    {
                        "attempt_ordinal": ordinal,
                        "event": "PRESELECTION_FAILURE",
                        "reason": envelope["failure_code"],
                        "slot": slot,
                    },
                )
            else:
                state = contract.transition_consumption_state(
                    state,
                    {"attempt_ordinal": ordinal, "event": "SELECTION_CREATED", "reason": None, "slot": slot},
                )
                event = "ARM_CREDIBILITY_PASS" if envelope["outcome"] == CREDIBLE_TERMINAL else "ARM_CREDIBILITY_INCOMPLETE"
                state = contract.transition_consumption_state(
                    state,
                    {
                        "attempt_ordinal": ordinal,
                        "event": event,
                        "reason": None if event == "ARM_CREDIBILITY_PASS" else envelope["failure_code"],
                        "slot": slot,
                    },
                )
            if envelope["outcome"] == CREDIBLE_TERMINAL and attempt_index != len(attempts) - 1:
                raise AuthorityError("credible attempt has a later retry")
        if active is not None or state["next_index"] == slot_index:
            for future_slot in contract.ARM_SEQUENCE[slot_index + 1 :]:
                if _attempt_directories(Path(preregistration["slot_roots"][future_slot])):
                    raise AuthorityError("future slot contains an attempt")
            break

    return {
        "active_attempt": active,
        "attempts": attempts_summary,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "consumption_state": state,
        "preregistration_identity": preregistration_identity,
        "schema_version": REPLAY_SCHEMA,
        "slot_attempt_counts": slot_attempt_counts,
        "status": "PASS",
    }


def prepare_attempt(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    slot: str | None = None,
    additional_strict_inputs: Mapping[str, Path | str] | None = None,
    additional_execution_tools: Mapping[str, Path | str] | None = None,
) -> dict[str, object]:
    """Create the next append-only attempt and bind its actual input bytes."""

    preregistration_path = _absolute(preregistration_path)
    replay = replay_campaign(preregistration_path)
    if replay["active_attempt"] is not None:
        raise AuthorityError("the current attempt must close before retry")
    state = replay["consumption_state"]
    next_index = state["next_index"]
    if next_index == len(contract.ARM_SEQUENCE):
        raise AuthorityError("all preregistered slots are already complete")
    expected_slot = contract.ARM_SEQUENCE[next_index]
    if slot is not None and slot != expected_slot:
        raise AuthorityError(f"next preregistered slot is {expected_slot}")
    slot = expected_slot
    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    ordinal = replay["slot_attempt_counts"].get(slot, 0) + 1

    scientific_paths = _scientific_source_paths(preregistration_path, preregistration, slot)
    for role, path in (additional_strict_inputs or {}).items():
        if ROLE_RE.fullmatch(role) is None or role in scientific_paths:
            raise AuthorityError(f"invalid or duplicate strict-input role: {role}")
        scientific_paths[role] = _absolute(path)
    tool_paths = _execution_tool_paths(additional_execution_tools)

    head_before = _observe_clean_head(repository_root)
    scientific_sources = _capture_sources(scientific_paths, "strict input")
    tool_sources = _capture_sources(tool_paths, "execution tool")
    head_after = _observe_clean_head(repository_root)
    if head_before != head_after:
        raise AuthorityError("repository HEAD changed during input capture")

    prospective_scientific_identities = {
        role: {
            "mode": 0o600,
            "path": source_identity["path"],
            "sha256": source_identity["sha256"],
            "size_bytes": source_identity["size_bytes"],
        }
        for role, (_raw, source_identity) in scientific_sources.items()
    }
    scientific_digest = _projection_digest(
        "noncert-cuts-ab16-scientific-input-set-v1",
        prospective_scientific_identities,
    )

    slot_root = Path(preregistration["slot_roots"][slot])
    prior_attempts = _attempt_directories(slot_root)
    if prior_attempts:
        prior_input, _prior_identity = _validate_input_set(prior_attempts[0][1], preregistration_identity)
        if prior_input["scientific_input_set_sha256"] != scientific_digest:
            raise AuthorityError("scientific inputs changed between retries")
    if not slot_root.exists() and not slot_root.is_symlink():
        parent = slot_root.parent
        if not parent.exists() and not parent.is_symlink():
            grandparent = _existing_directory(parent.parent, "prospective AB16 directory")
            if grandparent != Path(preregistration["campaign_dir"]) / "prospective-ab16":
                raise AuthorityError("slot-root parent is outside the preregistered topology")
            _make_directory(parent)
        else:
            _existing_directory(parent, "slot-root parent")
        _make_directory(slot_root)
    else:
        _existing_directory(slot_root, "slot root")
    attempt_dir = slot_root / f"attempt-{ordinal:04d}"
    _make_directory(attempt_dir)
    input_snapshot_dir = attempt_dir / "input-snapshots"
    tool_snapshot_dir = attempt_dir / "tool-snapshots"
    work_dir = attempt_dir / "work"
    for directory in (input_snapshot_dir, tool_snapshot_dir, work_dir):
        _make_directory(directory)

    def publish_snapshots(
        sources: Mapping[str, tuple[bytes, dict[str, object]]],
        directory: Path,
    ) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        snapshots: dict[str, dict[str, object]] = {}
        source_identities: dict[str, dict[str, object]] = {}
        for index, role in enumerate(sorted(sources)):
            raw, source_identity = sources[role]
            snapshots[role] = _write_bytes_exclusive(directory / f"{index:04d}.bin", raw)
            source_identities[role] = source_identity
        return snapshots, source_identities

    strict_inputs, source_strict_inputs = publish_snapshots(scientific_sources, input_snapshot_dir)
    tools, source_tools = publish_snapshots(tool_sources, tool_snapshot_dir)
    if _projection_digest("noncert-cuts-ab16-scientific-input-set-v1", strict_inputs) != scientific_digest:
        raise AuthorityError("published scientific snapshots differ from captured inputs")
    input_set_sha256 = contract.attempt_input_set_sha256(
        preregistration_sha256=preregistration_identity["sha256"],
        repository_head=head_before,
        strict_input_identities=strict_inputs,
        tool_identities=tools,
    )
    input_record = {
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "input_set_sha256": input_set_sha256,
        "preregistration_identity": preregistration_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": head_before,
        "schema_version": INPUT_SET_SCHEMA,
        "scientific_input_set_sha256": scientific_digest,
        "source_strict_input_identities": source_strict_inputs,
        "source_tool_identities": source_tools,
        "strict_input_identities": strict_inputs,
        "tool_identities": tools,
    }
    input_identity = _write_record(attempt_dir / "attempt-input-set.json", input_record)
    open_record = {
        "attempt_dir": str(attempt_dir),
        "attempt_ordinal": ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "input_set_identity": input_identity,
        "input_set_sha256": input_set_sha256,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": head_before,
        "schema_version": ATTEMPT_OPEN_SCHEMA,
        "slot": slot,
        "status": "OPEN",
    }
    open_identity = _write_record(attempt_dir / "attempt-open.json", open_record)
    return {
        "attempt_dir": str(attempt_dir),
        "attempt_open_identity": open_identity,
        "attempt_ordinal": ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "input_set_identity": input_identity,
        "input_set_sha256": input_set_sha256,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": head_before,
        "slot": slot,
        "status": "ATTEMPT_PREPARED",
        "work_dir": str(work_dir),
    }


def bind_selection(
    preregistration_path: Path | str,
    *,
    slot: str,
    attempt_ordinal: int,
    selection_path: Path | str,
) -> dict[str, object]:
    replay = replay_campaign(preregistration_path)
    active = replay["active_attempt"]
    if active != {
        "attempt_dir": str(Path(replay["preregistration_identity"]["path"]).parent),
        "attempt_ordinal": attempt_ordinal,
        "slot": slot,
    }:
        # Compare the stable fields separately; the preregistration file need
        # not live beside the attempt tree.
        if active is None or active["slot"] != slot or active["attempt_ordinal"] != attempt_ordinal:
            raise AuthorityError("selection does not target the active attempt")
    attempt_dir = Path(active["attempt_dir"])
    _raw, selection_identity = _snapshot(selection_path)
    record = {
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "schema_version": SELECTION_BINDING_SCHEMA,
        "selection_identity": selection_identity,
        "status": "BOUND",
    }
    identity = _write_record(attempt_dir / "selection-binding.json", record)
    return {"selection_binding_identity": identity, "status": "SELECTION_BOUND"}


def _validate_credible_gate(path: Path | str, *, slot: str, selection_identity: Mapping[str, Any]) -> dict[str, object]:
    gate, identity = _load_record(path, "arm credibility gate")
    authorizations = gate.get("authorizations")
    if (
        gate.get("schema_version") != "noncert-cuts-ab16-arm-credibility-gate-v1"
        or gate.get("status") != "PASS"
        or gate.get("credibility_status") != "PASS"
        or gate.get("slot") != slot
        or type(authorizations) is not dict
        or not authorizations
        or any(value is not False for value in authorizations.values())
        or gate.get("selection_identity") != selection_identity
    ):
        raise AuthorityError("arm credibility gate is not a research-only PASS for the selected attempt")
    return identity


def close_attempt(
    preregistration_path: Path | str,
    *,
    slot: str,
    attempt_ordinal: int,
    outcome: str,
    failure_code: str | None = None,
    evidence_paths: Mapping[str, Path | str] | None = None,
) -> dict[str, object]:
    """Close the active attempt; incomplete closure leaves its slot retryable."""

    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    replay = replay_campaign(preregistration_path)
    active = replay["active_attempt"]
    if active is None or active["slot"] != slot or active["attempt_ordinal"] != attempt_ordinal:
        raise AuthorityError("only the active attempt may be closed")
    attempt_dir = Path(active["attempt_dir"])
    _open, inputs, _open_identity = _validate_open(
        attempt_dir,
        slot=slot,
        ordinal=attempt_ordinal,
        preregistration_identity=preregistration_identity,
    )
    input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
    selection, selection_binding_identity = _optional_selection(attempt_dir)
    evidence_identities: dict[str, dict[str, object]] = {}
    for role, path in sorted((evidence_paths or {}).items()):
        if ROLE_RE.fullmatch(role) is None:
            raise AuthorityError(f"invalid evidence role: {role}")
        _raw, evidence_identities[role] = _snapshot(path)
    if outcome == CREDIBLE_TERMINAL:
        if failure_code is not None or selection is None or "arm_gate" not in evidence_identities:
            raise AuthorityError("credible closure requires a bound selection and arm_gate only, with no failure code")
        gate_identity = _validate_credible_gate(
            evidence_paths["arm_gate"],
            slot=slot,
            selection_identity=selection["selection_identity"],
        )
        if gate_identity != evidence_identities["arm_gate"]:
            raise AuthorityError("arm gate identity changed during validation")
        retry_disposition = "SLOT_CLOSED"
    elif outcome == CREDIBILITY_INCOMPLETE:
        if type(failure_code) is not str or not failure_code:
            raise AuthorityError("incomplete closure requires a failure code")
        retry_disposition = "SAME_SLOT_RETRY_ALLOWED"
    else:
        raise AuthorityError("attempt outcome is unsupported")
    envelope: dict[str, object] = {
        "attempt_ordinal": attempt_ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "envelope_id": "",
        "evidence_identities": evidence_identities,
        "failure_code": failure_code,
        "input_set_identity": input_identity,
        "input_set_sha256": inputs["input_set_sha256"],
        "outcome": outcome,
        "preregistration_identity": preregistration_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": inputs["repository_head"],
        "retry_disposition": retry_disposition,
        "schema_version": RESULT_ENVELOPE_SCHEMA,
        "selection_binding_identity": selection_binding_identity,
        "slot": slot,
    }
    envelope["envelope_id"] = hashlib.sha256(canonical_json(envelope)).hexdigest()
    envelope_identity = _write_record(attempt_dir / "attempt-result.json", envelope)
    return {
        "attempt_result_identity": envelope_identity,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "outcome": outcome,
        "retry_disposition": retry_disposition,
        "status": "ATTEMPT_CLOSED",
    }


def _role_paths(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        role, separator, path = value.partition("=")
        if not separator or ROLE_RE.fullmatch(role) is None or role in result or not path:
            raise AuthorityError(f"expected unique ROLE=PATH value, got {value!r}")
        result[role] = _absolute(path)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--preregistration", type=Path, required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--preregistration", type=Path, required=True)
    prepare_parser.add_argument("--repository-root", type=Path, required=True)
    prepare_parser.add_argument("--slot")
    prepare_parser.add_argument("--strict-input", action="append", default=[])
    prepare_parser.add_argument("--execution-tool", action="append", default=[])
    bind_parser = subparsers.add_parser("bind-selection")
    bind_parser.add_argument("--preregistration", type=Path, required=True)
    bind_parser.add_argument("--slot", required=True)
    bind_parser.add_argument("--attempt-ordinal", type=int, required=True)
    bind_parser.add_argument("--selection", type=Path, required=True)
    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--preregistration", type=Path, required=True)
    close_parser.add_argument("--slot", required=True)
    close_parser.add_argument("--attempt-ordinal", type=int, required=True)
    close_parser.add_argument("--outcome", choices=(CREDIBLE_TERMINAL, CREDIBILITY_INCOMPLETE), required=True)
    close_parser.add_argument("--failure-code")
    close_parser.add_argument("--evidence", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "replay":
        result = replay_campaign(args.preregistration)
    elif args.command == "prepare":
        result = prepare_attempt(
            args.preregistration,
            repository_root=args.repository_root,
            slot=args.slot,
            additional_strict_inputs=_role_paths(args.strict_input),
            additional_execution_tools=_role_paths(args.execution_tool),
        )
    elif args.command == "bind-selection":
        result = bind_selection(
            args.preregistration,
            slot=args.slot,
            attempt_ordinal=args.attempt_ordinal,
            selection_path=args.selection,
        )
    else:
        result = close_attempt(
            args.preregistration,
            slot=args.slot,
            attempt_ordinal=args.attempt_ordinal,
            outcome=args.outcome,
            failure_code=args.failure_code,
            evidence_paths=_role_paths(args.evidence),
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
