#!/usr/bin/env python3
"""Authority-aware Gate-1 positive-control classifier.

Qualification receipts are derived evidence.  The no-overwrite launch
selection is the direct authority root.  A historical-replay selection can
authorize an overlay evaluation only; it can never authorize arm launch or an
experiment verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import types
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SELECTION_SCHEMA = "noncert-cuts-gate1-launch-selection-v3"
GATE_SCHEMA = "noncert-cuts-gate1-positive-control-gate-v3"
QUALIFICATION_RECEIPT_SCHEMA = "noncert-cuts-gate1-qualification-receipt-v1"
EVIDENCE_PATHS_SCHEMA = "noncert-cuts-gate1-evidence-path-manifest-v3"
HISTORICAL_PURPOSE = "historical_replay"
PAIRED_PURPOSE = "paired_arm_launch"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
RESOURCE_VERIFICATION_SCHEMA = "noncert-cuts-gate1-resource-verification-v2"
RESOURCE_CONTRACT = {
    "memory_high_bytes": 35 * 1024**3,
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "kill_mode": "control-group",
    "send_sigkill": True,
    "runtime_max_seconds": 1500,
    "internal_timeout_seconds": 1470,
}

COMMON_MISSING_GATES = (
    "resource_authority_missing",
    "paired_arm_launch_authority_missing",
    "arm_result_join_missing",
    "resource_inner_raw_authority_missing",
    "resource_terminal_authority_missing",
    "selector_model_binary_authority_missing",
    "selector_solver_response_binary_authority_missing",
)


class GateV3Error(RuntimeError):
    """Fail-closed selection or gate error."""


_REPLAY_SENTINEL = object()


class _GateOwnedReplay:
    """A semantic result that only this module's replay path can construct."""

    __slots__ = (
        "arm_results",
        "checker_classification",
        "checker_report",
        "inner_raw_results",
        "model_binary_identities",
        "resource_report",
        "response_binary_identities",
        "terminal_envelopes",
        "_sentinel",
    )

    def __init__(
        self,
        sentinel: object,
        *,
        checker_classification: str | None,
        checker_report: Mapping[str, object] | None,
        resource_report: Mapping[str, object] | None,
        arm_results: Mapping[str, object] | None = None,
        inner_raw_results: Mapping[str, object] | None = None,
        terminal_envelopes: Mapping[str, object] | None = None,
        model_binary_identities: Mapping[str, object] | None = None,
        response_binary_identities: Mapping[str, object] | None = None,
    ) -> None:
        if sentinel is not _REPLAY_SENTINEL:
            raise GateV3Error("semantic replay result is not gate-owned")
        self._sentinel = sentinel
        self.checker_classification = checker_classification
        self.checker_report = dict(checker_report) if checker_report is not None else None
        self.resource_report = dict(resource_report) if resource_report is not None else None
        self.arm_results = dict(arm_results) if arm_results is not None else None
        self.inner_raw_results = dict(inner_raw_results) if inner_raw_results is not None else None
        self.terminal_envelopes = dict(terminal_envelopes) if terminal_envelopes is not None else None
        self.model_binary_identities = dict(model_binary_identities) if model_binary_identities is not None else None
        self.response_binary_identities = (
            dict(response_binary_identities) if response_binary_identities is not None else None
        )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _canonical_digest_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_chain(path: Path, *, allow_missing_leaf: bool = False) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    parts = absolute.parts[1:]
    for part in parts:
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            if allow_missing_leaf:
                return
            raise
        if stat.S_ISLNK(mode):
            raise GateV3Error(f"symlink path component rejected: {current}")


def _snapshot_regular(path: Path) -> tuple[bytes, dict[str, object]]:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute)
    if not hasattr(os, "O_NOFOLLOW"):
        raise GateV3Error("O_NOFOLLOW is required")
    before_path = os.stat(absolute, follow_symlinks=False)
    if not stat.S_ISREG(before_path.st_mode):
        raise GateV3Error(f"input is not a regular file: {absolute}")
    descriptor = os.open(absolute, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before_fd = os.fstat(descriptor)
        fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before_path, field) != getattr(before_fd, field) for field in fields):
            raise GateV3Error(f"input changed before read: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        data = b"".join(chunks)
        after_fd = os.fstat(descriptor)
        after_path = os.stat(absolute, follow_symlinks=False)
        if any(getattr(before_fd, field) != getattr(after_fd, field) for field in fields):
            raise GateV3Error(f"input changed during read: {absolute}")
        if any(getattr(after_fd, field) != getattr(after_path, field) for field in fields):
            raise GateV3Error(f"input path inode changed during read: {absolute}")
        if len(data) != after_fd.st_size:
            raise GateV3Error(f"input length changed during read: {absolute}")
        return data, {
            "path": str(absolute),
            "sha256": _sha256(data),
            "size_bytes": len(data),
        }
    finally:
        os.close(descriptor)


def file_identity(path: Path) -> dict[str, object]:
    _data, identity = _snapshot_regular(path)
    return identity


def _read_regular(path: Path) -> bytes:
    data, _identity = _snapshot_regular(path)
    return data


def _write_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    if absolute.exists() or absolute.is_symlink():
        raise GateV3Error(f"refusing to overwrite {absolute}")
    if not absolute.parent.is_dir():
        raise GateV3Error(f"output parent is invalid: {absolute.parent}")
    if not hasattr(os, "O_NOFOLLOW"):
        raise GateV3Error("O_NOFOLLOW is required")
    descriptor = os.open(absolute, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(_canonical_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _valid_identity(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"path", "sha256", "size_bytes"}
        and isinstance(value.get("path"), str)
        and bool(value.get("path"))
        and isinstance(value.get("size_bytes"), int)
        and not isinstance(value.get("size_bytes"), bool)
        and int(value["size_bytes"]) >= 0
        and isinstance(value.get("sha256"), str)
        and SHA256_PATTERN.fullmatch(str(value["sha256"])) is not None
    )


def _identity_equal(left: object, right: object) -> bool:
    return _valid_identity(left) and _valid_identity(right) and dict(left) == dict(right)


def _validate_identity_map(value: object, label: str) -> dict[str, dict[str, object]]:
    if not isinstance(value, Mapping) or not value:
        raise GateV3Error(f"{label} must be a non-empty mapping")
    result: dict[str, dict[str, object]] = {}
    for role, identity in value.items():
        if not isinstance(role, str) or not role or not _valid_identity(identity):
            raise GateV3Error(f"{label} contains an invalid role/identity")
        result[role] = dict(identity)
    return result


def _validate_common_selection(payload: Mapping[str, object]) -> None:
    if payload.get("schema") != SELECTION_SCHEMA:
        raise GateV3Error("launch selection schema mismatch")
    if payload.get("purpose") not in {HISTORICAL_PURPOSE, PAIRED_PURPOSE}:
        raise GateV3Error("launch selection purpose is invalid")
    if not isinstance(payload.get("run_nonce"), str) or not payload["run_nonce"]:
        raise GateV3Error("launch selection run nonce is invalid")
    if (
        not isinstance(payload.get("repository_head"), str)
        or re.fullmatch(r"[0-9a-f]{40}", str(payload["repository_head"])) is None
        or not isinstance(payload.get("created_at_utc"), str)
        or not str(payload["created_at_utc"]).endswith("Z")
        or payload.get("contract") != RESOURCE_CONTRACT
        or not isinstance(payload.get("selection_id"), str)
        or SHA256_PATTERN.fullmatch(str(payload["selection_id"])) is None
    ):
        raise GateV3Error("launch selection provenance or resource contract is invalid")
    if not isinstance(payload.get("package_id"), str) or SHA256_PATTERN.fullmatch(str(payload["package_id"])) is None:
        raise GateV3Error("launch selection package ID is invalid")
    if not _valid_identity(payload.get("qualification_receipt_identity")):
        raise GateV3Error("launch selection qualification receipt identity is invalid")
    _validate_identity_map(payload.get("tools"), "launch selection tools")
    _validate_identity_map(payload.get("inputs"), "launch selection inputs")
    body = dict(payload)
    selection_id = body.pop("selection_id")
    if _sha256(_canonical_digest_bytes(body)) != selection_id:
        raise GateV3Error("launch selection ID does not rebuild")


def validate_selection_payload(payload: Mapping[str, object]) -> None:
    """Validate purpose-specific selection semantics without touching the filesystem."""

    _validate_common_selection(payload)
    purpose = payload["purpose"]
    common = {
        "arm_directories_absent_at_creation",
        "arm_launch",
        "contract",
        "created_at_utc",
        "inputs",
        "package_id",
        "purpose",
        "qualification_receipt_identity",
        "repository_head",
        "run_nonce",
        "schema",
        "selection_id",
        "tools",
    }
    if purpose == HISTORICAL_PURPOSE:
        expected = common | {"historical_overlay"}
        if set(payload) != expected:
            raise GateV3Error("historical selection key set is not exact")
        if payload.get("arm_launch") is not False:
            raise GateV3Error("historical replay permanently requires arm_launch=false")
        if payload.get("arm_directories_absent_at_creation") is not False:
            raise GateV3Error("historical replay cannot claim prospective arm-directory absence")
        overlay = payload.get("historical_overlay")
        if not isinstance(overlay, Mapping) or not overlay:
            raise GateV3Error("historical overlay binding is missing")
    else:
        expected = common | {"arms", "terminal_observer_tool_role"}
        if set(payload) != expected:
            raise GateV3Error("paired launch selection key set is not exact")
        if payload.get("arm_launch") is not True:
            raise GateV3Error("paired_arm_launch requires arm_launch=true")
        if payload.get("arm_directories_absent_at_creation") is not True:
            raise GateV3Error("paired_arm_launch requires prospective directory absence")
        arms = payload.get("arms")
        if not isinstance(arms, Mapping) or set(arms) != {"control", "treatment"}:
            raise GateV3Error("paired launch arms must be exactly control/treatment")
        attempts: set[str] = set()
        units: set[str] = set()
        for label in ("control", "treatment"):
            record = arms[label]
            if not isinstance(record, Mapping) or set(record) != {
                "arm",
                "attempt_dir",
                "raw_output_path",
                "recorder_tool_role",
                "result_path",
                "runner_tool_role",
                "terminal_envelope_path",
                "unit_name",
            }:
                raise GateV3Error(f"paired launch {label} record is invalid")
            if record.get("arm") != label:
                raise GateV3Error(f"paired launch {label} arm label mismatch")
            attempt = record.get("attempt_dir")
            unit = record.get("unit_name")
            if (
                not isinstance(attempt, str)
                or not Path(attempt).is_absolute()
                or not isinstance(unit, str)
                or not unit.endswith(".service")
            ):
                raise GateV3Error(f"paired launch {label} path/unit is invalid")
            absolute_attempt = _absolute(Path(attempt))
            for field in ("result_path", "raw_output_path", "terminal_envelope_path"):
                output = record.get(field)
                if (
                    not isinstance(output, str)
                    or not Path(output).is_absolute()
                    or not _absolute(Path(output)).is_relative_to(absolute_attempt)
                ):
                    raise GateV3Error(f"paired launch {label} {field} escapes its attempt")
            tools = payload["tools"]
            assert isinstance(tools, Mapping)
            for field in ("runner_tool_role", "recorder_tool_role"):
                role = record.get(field)
                if not isinstance(role, str) or role not in tools:
                    raise GateV3Error(f"paired launch {label} {field} is not tool-bound")
            attempts.add(str(absolute_attempt))
            units.add(unit)
        if len(attempts) != 2 or len(units) != 2:
            raise GateV3Error("paired launch attempt directories and units must be distinct")
        observer_role = payload.get("terminal_observer_tool_role")
        tools = payload["tools"]
        assert isinstance(tools, Mapping)
        if not isinstance(observer_role, str) or observer_role not in tools:
            raise GateV3Error("terminal observer is not bound to a selected tool")


def _seal_selection(body: Mapping[str, object]) -> dict[str, object]:
    payload = dict(body)
    payload["selection_id"] = _sha256(_canonical_digest_bytes(payload))
    validate_selection_payload(payload)
    return payload


def make_historical_selection(
    *,
    package_id: str,
    run_nonce: str,
    created_at_utc: str,
    repository_head: str,
    qualification_receipt_identity: Mapping[str, object],
    tools: Mapping[str, Mapping[str, object]],
    inputs: Mapping[str, Mapping[str, object]],
    historical_overlay: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "arm_directories_absent_at_creation": False,
        "arm_launch": False,
        "contract": dict(RESOURCE_CONTRACT),
        "created_at_utc": created_at_utc,
        "historical_overlay": dict(historical_overlay),
        "inputs": {key: dict(value) for key, value in inputs.items()},
        "package_id": package_id,
        "purpose": HISTORICAL_PURPOSE,
        "qualification_receipt_identity": dict(qualification_receipt_identity),
        "repository_head": repository_head,
        "run_nonce": run_nonce,
        "schema": SELECTION_SCHEMA,
        "tools": {key: dict(value) for key, value in tools.items()},
    }
    return _seal_selection(body)


def make_paired_selection(
    *,
    package_id: str,
    run_nonce: str,
    created_at_utc: str,
    repository_head: str,
    qualification_receipt_identity: Mapping[str, object],
    tools: Mapping[str, Mapping[str, object]],
    inputs: Mapping[str, Mapping[str, object]],
    arms: Mapping[str, Mapping[str, object]],
    terminal_observer_tool_role: str,
) -> dict[str, object]:
    body = {
        "arm_directories_absent_at_creation": True,
        "arm_launch": True,
        "arms": {key: dict(value) for key, value in arms.items()},
        "contract": dict(RESOURCE_CONTRACT),
        "created_at_utc": created_at_utc,
        "inputs": {key: dict(value) for key, value in inputs.items()},
        "package_id": package_id,
        "purpose": PAIRED_PURPOSE,
        "qualification_receipt_identity": dict(qualification_receipt_identity),
        "repository_head": repository_head,
        "run_nonce": run_nonce,
        "schema": SELECTION_SCHEMA,
        "tools": {key: dict(value) for key, value in tools.items()},
        "terminal_observer_tool_role": terminal_observer_tool_role,
    }
    return _seal_selection(body)


def write_launch_selection(path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Create the direct authority root, refusing prospective launch after arm dirs exist."""

    validate_selection_payload(payload)
    absolute_output = _absolute(path)
    receipt = payload["qualification_receipt_identity"]
    assert isinstance(receipt, Mapping)
    receipt_path = _absolute(Path(str(receipt["path"])))
    verification_ancestors = [part for part in receipt_path.parents if part.name == "verifications"]
    if verification_ancestors:
        package_root = verification_ancestors[0].parent / "package"
        if absolute_output.is_relative_to(package_root):
            raise GateV3Error("launch selection must remain outside the immutable package")
    if payload["purpose"] == PAIRED_PURPOSE:
        arms = payload["arms"]
        assert isinstance(arms, Mapping)
        for label in ("control", "treatment"):
            record = arms[label]
            assert isinstance(record, Mapping)
            attempt = _absolute(Path(str(record["attempt_dir"])))
            _reject_symlink_chain(attempt, allow_missing_leaf=True)
            if os.path.lexists(attempt):
                raise GateV3Error(f"paired launch selection must predate arm directory: {attempt}")
            if absolute_output.is_relative_to(attempt):
                raise GateV3Error("launch selection must remain outside every arm directory")
    _write_exclusive(path, payload)
    return file_identity(path)


def _replay_identity_map(value: object) -> tuple[bool, list[dict[str, object]]]:
    try:
        identities = _validate_identity_map(value, "identity map")
    except GateV3Error:
        return False, []
    replayed: list[dict[str, object]] = []
    for role, expected in identities.items():
        try:
            current = file_identity(Path(str(expected["path"])))
        except Exception:  # noqa: BLE001 - identity drift is a closed gate
            return False, replayed
        replayed.append({"role": role, **current})
        if current != expected:
            return False, replayed
    return True, replayed


def _gate_self_bound(selection: Mapping[str, object] | None) -> tuple[bool, dict[str, object]]:
    current = file_identity(Path(__file__))
    tools = selection.get("tools") if isinstance(selection, Mapping) else None
    expected = tools.get("positive_control_gate_v3") if isinstance(tools, Mapping) else None
    return _identity_equal(expected, current), current


def _qualification_pass(
    selection: Mapping[str, object] | None,
    receipt: Mapping[str, object] | None,
    receipt_identity: Mapping[str, object] | None,
) -> bool:
    if selection is None or receipt is None or receipt_identity is None:
        return False
    basic = (
        receipt.get("schema") == QUALIFICATION_RECEIPT_SCHEMA
        and receipt.get("status") == "PASS"
        and receipt.get("authorization_root") is False
        and receipt.get("arm_launch_authorized") is False
        and receipt.get("classification_authorized") is False
        and receipt.get("package_id") == selection.get("package_id")
        and _identity_equal(receipt_identity, selection.get("qualification_receipt_identity"))
        and receipt.get("corpus_errors") == []
        and isinstance(receipt.get("checks"), list)
        and bool(receipt["checks"])
        and all(isinstance(row, Mapping) and row.get("passed") is True for row in receipt["checks"])
    )
    if not basic:
        return False
    current_sources = receipt.get("current_source_identities")
    if not isinstance(current_sources, list):
        return False
    by_role = {
        row.get("role"): {
            "path": row.get("path"),
            "sha256": row.get("sha256"),
            "size_bytes": row.get("size_bytes"),
        }
        for row in current_sources
        if isinstance(row, Mapping) and isinstance(row.get("role"), str)
    }
    selected = {
        **dict(selection.get("tools", {})),
        **dict(selection.get("inputs", {})),
    }
    return bool(selected) and all(role in by_role and by_role[role] == identity for role, identity in selected.items())


def _arm_join_pass(
    selection: Mapping[str, object] | None,
    selection_identity: Mapping[str, object] | None,
    arm_results: Mapping[str, object] | None,
) -> bool:
    if (
        selection is None
        or selection.get("purpose") != PAIRED_PURPOSE
        or not _valid_identity(selection_identity)
        or not isinstance(arm_results, Mapping)
        or set(arm_results) != {"control", "treatment"}
    ):
        return False
    arms = selection.get("arms")
    if not isinstance(arms, Mapping):
        return False
    for label in ("control", "treatment"):
        result = arm_results[label]
        selected = arms[label]
        if not isinstance(result, Mapping) or not isinstance(selected, Mapping):
            return False
        launch = result.get("launch_selection")
        if (
            not isinstance(launch, Mapping)
            or launch.get("package_id") != selection.get("package_id")
            or launch.get("run_nonce") != selection.get("run_nonce")
            or launch.get("selection_id") != selection.get("selection_id")
            or not _identity_equal(launch.get("selection_identity"), selection_identity)
            or launch.get("arm") != label
            or str(_absolute(Path(str(launch.get("attempt_dir")))))
            != str(_absolute(Path(str(selected.get("attempt_dir")))))
            or launch.get("unit_name") != selected.get("unit_name")
            or not _valid_identity(result.get("result_identity"))
            or str(_absolute(Path(str(result["result_identity"]["path"]))))
            != str(_absolute(Path(str(selected.get("result_path")))))
        ):
            return False
        try:
            current_result = file_identity(Path(str(result["result_identity"]["path"])))
        except Exception:  # noqa: BLE001 - missing/drifted result closes the join
            return False
        if current_result != result["result_identity"]:
            return False
    return True


def _paired_semantic_join(value: object, arm_results: object, *, status: str = "PASS") -> bool:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"control", "treatment"}
        or not isinstance(arm_results, Mapping)
        or set(arm_results) != {"control", "treatment"}
    ):
        return False
    for label in ("control", "treatment"):
        record = value[label]
        arm = arm_results[label]
        if (
            not isinstance(record, Mapping)
            or not isinstance(arm, Mapping)
            or record.get("status") != status
            or not _identity_equal(record.get("arm_result_identity"), arm.get("result_identity"))
        ):
            return False
    return True


def _paired_binary_join(value: object, arm_results: object, *, arm_field: str) -> bool:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"control", "treatment"}
        or not isinstance(arm_results, Mapping)
        or set(arm_results) != {"control", "treatment"}
    ):
        return False
    for label in ("control", "treatment"):
        identity = value[label]
        arm = arm_results[label]
        if not isinstance(arm, Mapping) or not _identity_equal(identity, arm.get(arm_field)):
            return False
        try:
            current = file_identity(Path(str(identity["path"])))
        except Exception:  # noqa: BLE001 - binary absence/drift closes the gate
            return False
        if current != identity:
            return False
    return True


def _make_gate_owned_replay(
    *,
    checker_classification: str | None,
    checker_report: Mapping[str, object] | None,
    resource_report: Mapping[str, object] | None,
    arm_results: Mapping[str, object] | None = None,
    inner_raw_results: Mapping[str, object] | None = None,
    terminal_envelopes: Mapping[str, object] | None = None,
    model_binary_identities: Mapping[str, object] | None = None,
    response_binary_identities: Mapping[str, object] | None = None,
) -> _GateOwnedReplay:
    """Construct a private replay result after semantic verification.

    This helper is intentionally private.  Production callers obtain its
    result only through :func:`_replay_exact_path_manifest`; tests may use it
    to isolate the surrounding authority joins without making caller JSON an
    accepted replay result.
    """

    if checker_classification not in {
        None,
        "INJECTED_MECHANISM_POSITIVE_CONTROL",
        "POSITIVE_CONTROL_NEGATIVE",
    }:
        raise GateV3Error("unsupported checker classification")
    if resource_report is not None:
        expected = {
            "arms",
            "claim",
            "contract",
            "receipt_id",
            "receipt_identity",
            "run_nonce",
            "schema_version",
            "selection_identity",
            "status",
        }
        if (
            set(resource_report) != expected
            or resource_report.get("schema_version") != RESOURCE_VERIFICATION_SCHEMA
            or resource_report.get("status") != "PASS"
            or resource_report.get("claim") != "resource_evidence_only"
        ):
            raise GateV3Error("resource replay report does not have complete PASS semantics")
    return _GateOwnedReplay(
        _REPLAY_SENTINEL,
        checker_classification=checker_classification,
        checker_report=checker_report,
        resource_report=resource_report,
        arm_results=arm_results,
        inner_raw_results=inner_raw_results,
        terminal_envelopes=terminal_envelopes,
        model_binary_identities=model_binary_identities,
        response_binary_identities=response_binary_identities,
    )


def _gate_owned_replay(value: object) -> _GateOwnedReplay | None:
    if not isinstance(value, _GateOwnedReplay) or value._sentinel is not _REPLAY_SENTINEL:
        return None
    return value


def _strict_json_bytes(data: bytes, label: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise GateV3Error(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(token: str) -> object:
        raise GateV3Error(f"{label} contains non-finite constant {token}")

    try:
        return json.loads(
            data,
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateV3Error(f"{label} is invalid strict JSON: {exc}") from exc


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise GateV3Error(f"{label} key set is not exact")
    return value


def _selected_role_snapshot(
    selection: Mapping[str, object],
    *,
    section: str,
    role: object,
    expected_basename: str | None = None,
) -> tuple[Path, bytes, dict[str, object]]:
    if not isinstance(role, str) or not role:
        raise GateV3Error(f"{section} replay role is invalid")
    raw = selection.get(section)
    if not isinstance(raw, Mapping) or role not in raw or not _valid_identity(raw[role]):
        raise GateV3Error(f"{section} replay role is not selection-bound: {role!r}")
    identity = raw[role]
    path = _absolute(Path(str(identity["path"])))
    if expected_basename is not None and path.name != expected_basename:
        raise GateV3Error(f"{section} replay role has unexpected tool basename: {path.name}")
    data, observed = _snapshot_regular(path)
    if observed != identity:
        raise GateV3Error(f"{section} replay role identity drift: {role}")
    return path, data, observed


def _load_pinned_module(
    path: Path,
    raw: bytes,
    identity: Mapping[str, object],
    label: str,
) -> Any:
    """Execute exactly one already-qualified tool snapshot."""

    module_name = f"_noncert_gate1_{label}_{identity['sha256']}"
    module = types.ModuleType(module_name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[module_name] = module
    try:
        code = compile(raw, str(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)  # noqa: S102 - executes the selected local tool snapshot
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _resource_replay(
    manifest: Mapping[str, object],
    selection: Mapping[str, object],
    selection_path: Path,
) -> dict[str, object]:
    record = _exact_mapping(
        manifest,
        {
            "control_raw_path",
            "control_terminal_path",
            "receipt_path",
            "treatment_raw_path",
            "treatment_terminal_path",
            "verifier_tool_role",
        },
        "resource replay manifest",
    )
    tool_path, tool_raw, tool_identity = _selected_role_snapshot(
        selection,
        section="tools",
        role=record["verifier_tool_role"],
        expected_basename="independent_resource_verifier_v2.py",
    )
    module = _load_pinned_module(tool_path, tool_raw, tool_identity, "resource")
    try:
        report = module.verify_resource_pair(
            selection_path=selection_path,
            receipt_path=Path(str(record["receipt_path"])),
            control_raw_path=Path(str(record["control_raw_path"])),
            control_terminal_path=Path(str(record["control_terminal_path"])),
            treatment_raw_path=Path(str(record["treatment_raw_path"])),
            treatment_terminal_path=Path(str(record["treatment_terminal_path"])),
        )
    except Exception as exc:  # noqa: BLE001 - semantic failure closes the resource gate
        raise GateV3Error(f"resource verifier rejected exact path manifest: {exc}") from exc
    if not isinstance(report, Mapping):
        raise GateV3Error("resource verifier did not return an object")
    result = dict(report)
    _make_gate_owned_replay(
        checker_classification=None,
        checker_report=None,
        resource_report=result,
    )
    resource_selection = file_identity(selection_path)
    reported_selection = result.get("selection_identity")
    if reported_selection != resource_selection:
        raise GateV3Error("resource verifier selection identity is not the selected input")
    return result


def _json_snapshot(path: Path, label: str) -> tuple[dict[str, Any], dict[str, object]]:
    raw, identity = _snapshot_regular(path)
    value = _strict_json_bytes(raw, label)
    if type(value) is not dict:
        raise GateV3Error(f"{label} must be an object")
    return value, identity


def _arm_replay(
    manifest: Mapping[str, object],
    selection: Mapping[str, object],
) -> dict[str, object]:
    record = _exact_mapping(
        manifest,
        {
            "arm",
            "arm_result_path",
            "checker_tool_role",
            "expected_head",
            "ledger_path",
            "model_path",
            "response_path",
            "selector_contract_input_role",
        },
        "arm replay manifest",
    )
    arm = record["arm"]
    if arm not in {"control", "treatment"} or record["expected_head"] != selection["repository_head"]:
        raise GateV3Error("arm replay label or repository HEAD drifted")
    tool_path, tool_raw, tool_identity = _selected_role_snapshot(
        selection,
        section="tools",
        role=record["checker_tool_role"],
        expected_basename="independent_arithmetic_check_v3.py",
    )
    module = _load_pinned_module(tool_path, tool_raw, tool_identity, f"checker_{arm}")
    _selector_path, selector_raw, _selector_identity = _selected_role_snapshot(
        selection,
        section="inputs",
        role=record["selector_contract_input_role"],
    )
    arm_result_path = _absolute(Path(str(record["arm_result_path"])))
    arm_result, result_identity = _json_snapshot(arm_result_path, f"{arm} arm result")
    ledger_raw, ledger_identity = _snapshot_regular(Path(str(record["ledger_path"])))
    model_raw, model_identity = _snapshot_regular(Path(str(record["model_path"])))
    response_raw, response_identity = _snapshot_regular(Path(str(record["response_path"])))
    selected = selection["arms"][arm]
    assert isinstance(selected, Mapping)
    attempt = _absolute(Path(str(selected["attempt_dir"])))
    for replay_path in (
        arm_result_path,
        Path(str(record["ledger_path"])),
        Path(str(record["model_path"])),
        Path(str(record["response_path"])),
    ):
        if not _absolute(replay_path).is_relative_to(attempt):
            raise GateV3Error(f"{arm} replay path escapes its selected attempt")
    if (
        str(arm_result_path) != str(_absolute(Path(str(selected["result_path"]))))
        or arm_result.get("arm") != arm
        or type(arm_result.get("exact_environment")) is not dict
    ):
        raise GateV3Error(f"{arm} arm result does not match its selected output")
    launch = arm_result.get("launch_selection")
    if (
        type(launch) is not dict
        or launch.get("selection_id") != selection["selection_id"]
        or launch.get("run_nonce") != selection["run_nonce"]
        or launch.get("arm") != arm
        or launch.get("unit_name") != selected["unit_name"]
    ):
        raise GateV3Error(f"{arm} result is not joined to the direct launch selection")
    ledger = arm_result.get("ledger")
    if type(ledger) is not dict or str(_absolute(Path(str(ledger.get("path"))))) != str(
        _absolute(Path(str(record["ledger_path"])))
    ):
        raise GateV3Error(f"{arm} result does not bind the replayed ledger path")
    try:
        counts = module.verify_arm_cut_counts(
            arm_result=arm_result,
            ledger_raw=ledger_raw,
            expected_head=str(record["expected_head"]),
        )
        truth = module.verify_binary_prestate(
            model_raw=model_raw,
            response_raw=response_raw,
            selector_contract=_strict_json_bytes(selector_raw, "selector contract"),
            arm_result=arm_result,
            expected_head=str(record["expected_head"]),
        )
    except Exception as exc:  # noqa: BLE001 - semantic failure closes this arm
        raise GateV3Error(f"{arm} arm replay failed: {exc}") from exc
    return {
        "arm": arm,
        "arm_result": arm_result,
        "counts": counts,
        "exact_environment": dict(arm_result["exact_environment"]),
        "ledger_identity": ledger_identity,
        "ledger_raw": ledger_raw,
        "model_binary_identity": model_identity,
        "model_raw": model_raw,
        "response_binary_identity": response_identity,
        "response_raw": response_raw,
        "result_identity": result_identity,
        "binary_truth": {
            "active_rect_idx": truth.active_rect_idx,
            "active_variable_index": truth.active_variable_index,
            "active_variable_name": truth.active_variable_name,
            "rectangle_digest": truth.rectangle_digest,
        },
        "checker_tool_role": record["checker_tool_role"],
        "selector_contract_input_role": record["selector_contract_input_role"],
    }


def _checker_positive_replay(
    manifest: Mapping[str, object],
    selection: Mapping[str, object],
    treatment: Mapping[str, object],
) -> dict[str, object]:
    record = _exact_mapping(
        manifest,
        {
            "candidate_placements_input_role",
            "frozen_assignment_path",
            "mandatory_instances_input_role",
            "sample_corpus_path",
        },
        "positive treatment replay manifest",
    )
    _mandatory_path, mandatory_raw, _mandatory_identity = _selected_role_snapshot(
        selection,
        section="inputs",
        role=record["mandatory_instances_input_role"],
    )
    _candidates_path, candidates_raw, _candidates_identity = _selected_role_snapshot(
        selection,
        section="inputs",
        role=record["candidate_placements_input_role"],
    )
    sample_raw, sample_identity = _snapshot_regular(Path(str(record["sample_corpus_path"])))
    assignment_raw, assignment_identity = _snapshot_regular(Path(str(record["frozen_assignment_path"])))
    sample_corpus = _strict_json_bytes(sample_raw, "arithmetic sample corpus")
    assignment = _strict_json_bytes(assignment_raw, "frozen assignment")
    arm_result = treatment["arm_result"]
    assert isinstance(arm_result, Mapping)
    if (
        arm_result.get("arithmetic_sample_corpus") != sample_identity
        or arm_result.get("frozen_assignment_identity") != assignment_identity
    ):
        raise GateV3Error("treatment result does not byte-bind sample corpus and assignment")
    prestate = arm_result.get("prestate")
    if (
        type(sample_corpus) is not dict
        or type(prestate) is not dict
        or sample_corpus.get("arm") != "treatment"
        or sample_corpus.get("prestate_sha256") != prestate.get("incumbent_sha256")
        or type(sample_corpus.get("samples")) is not list
        or len(sample_corpus["samples"]) != 1
    ):
        raise GateV3Error("sample corpus is not one treatment APPLIED sample")
    injection = arm_result.get("injection")
    compiled_records = injection.get("compiled_records") if isinstance(injection, Mapping) else None
    if type(compiled_records) is not list or len(compiled_records) != 1:
        raise GateV3Error("positive treatment must expose one concrete compiled cut")
    tool_path, tool_raw, tool_identity = _selected_role_snapshot(
        selection,
        section="tools",
        role=treatment["checker_tool_role"],
        expected_basename="independent_arithmetic_check_v3.py",
    )
    module = _load_pinned_module(tool_path, tool_raw, tool_identity, "checker_positive")
    _selector_path, selector_raw, _selector_identity = _selected_role_snapshot(
        selection,
        section="inputs",
        role=treatment["selector_contract_input_role"],
    )
    try:
        report = module.verify_applied_inequality(
            model_raw=treatment["model_raw"],
            response_raw=treatment["response_raw"],
            selector_contract=_strict_json_bytes(selector_raw, "selector contract"),
            arm_result=arm_result,
            compiled_record=compiled_records[0],
            sample=sample_corpus["samples"][0],
            ledger_raw=treatment["ledger_raw"],
            frozen_assignment=assignment,
            mandatory_instances=_strict_json_bytes(mandatory_raw, "mandatory instances"),
            candidate_placements=_strict_json_bytes(candidates_raw, "candidate placements"),
            expected_head=str(selection["repository_head"]),
        )
    except Exception as exc:  # noqa: BLE001 - semantic failure closes the checker gate
        raise GateV3Error(f"arithmetic checker rejected treatment replay: {exc}") from exc
    if (
        not isinstance(report, Mapping)
        or report.get("schema_version") != 3
        or report.get("checker") != "independent_arithmetic_check_v3"
        or report.get("status") != "PASS_APPLIED_VIOLATION"
    ):
        raise GateV3Error("arithmetic checker did not return complete APPLIED PASS semantics")
    return dict(report)


def _replay_exact_path_manifest(
    manifest: object,
    selection: Mapping[str, object],
    selection_path: Path,
) -> _GateOwnedReplay:
    """Replay raw path authorities; caller-rendered PASS objects are ignored."""

    record = _exact_mapping(
        manifest,
        {"arms", "positive_treatment", "resource", "schema"},
        "evidence path manifest",
    )
    if record.get("schema") != EVIDENCE_PATHS_SCHEMA:
        raise GateV3Error("evidence path manifest schema mismatch")
    if selection.get("purpose") == HISTORICAL_PURPOSE:
        if any(record[name] is not None for name in ("arms", "positive_treatment", "resource")):
            raise GateV3Error("historical replay cannot carry prospective experiment evidence")
        return _make_gate_owned_replay(
            checker_classification=None,
            checker_report=None,
            resource_report=None,
        )
    if not isinstance(record["resource"], Mapping) or not isinstance(record["arms"], Mapping):
        raise GateV3Error("paired replay requires resource and both arm path manifests")
    arm_manifests = _exact_mapping(record["arms"], {"control", "treatment"}, "arm manifests")
    resource_report = _resource_replay(record["resource"], selection, selection_path)
    arms = {label: _arm_replay(arm_manifests[label], selection) for label in ("control", "treatment")}
    if arms["control"]["exact_environment"] != arms["treatment"]["exact_environment"]:
        raise GateV3Error("paired arm exact_environment differs")
    control_counts = arms["control"]["counts"]
    treatment_counts = arms["treatment"]["counts"]
    if any(control_counts[name] != 0 for name in ("generated", "compiled", "applied")):
        raise GateV3Error("control arm is not GENERATED/COMPILED/APPLIED zero")
    treatment_vector = tuple(treatment_counts[name] for name in ("generated", "compiled", "applied"))
    checker_report: dict[str, object] | None
    if treatment_vector == (0, 0, 0):
        if record["positive_treatment"] is not None:
            raise GateV3Error("zero treatment cannot carry positive APPLIED evidence")
        classification = "POSITIVE_CONTROL_NEGATIVE"
        checker_report = {
            "checker": "independent_arithmetic_check_v3",
            "status": "NO_APPLIED_CUT",
            "control_counts": [0, 0, 0],
            "treatment_counts": [0, 0, 0],
        }
    elif all(value > 0 for value in treatment_vector):
        if not isinstance(record["positive_treatment"], Mapping):
            raise GateV3Error("positive treatment lacks concrete APPLIED replay paths")
        checker_report = _checker_positive_replay(
            record["positive_treatment"],
            selection,
            arms["treatment"],
        )
        classification = "INJECTED_MECHANISM_POSITIVE_CONTROL"
    else:
        classification = None
        checker_report = {
            "checker": "independent_arithmetic_check_v3",
            "status": "PARTIAL_CUT_PIPELINE",
            "control_counts": [0, 0, 0],
            "treatment_counts": list(treatment_vector),
        }
    arm_results = {
        label: {
            "launch_selection": arms[label]["arm_result"]["launch_selection"],
            "model_binary_identity": arms[label]["model_binary_identity"],
            "response_binary_identity": arms[label]["response_binary_identity"],
            "result_identity": arms[label]["result_identity"],
        }
        for label in ("control", "treatment")
    }
    resource_arms = resource_report["arms"]
    inner = {
        label: {
            "arm_result_identity": resource_arms[label]["result_identity"],
            "status": "PASS",
        }
        for label in ("control", "treatment")
    }
    return _make_gate_owned_replay(
        checker_classification=classification,
        checker_report=checker_report,
        resource_report=resource_report,
        arm_results=arm_results,
        inner_raw_results=inner,
        terminal_envelopes=dict(inner),
        model_binary_identities={label: arms[label]["model_binary_identity"] for label in ("control", "treatment")},
        response_binary_identities={
            label: arms[label]["response_binary_identity"] for label in ("control", "treatment")
        },
    )


def evaluate_gate(
    *,
    selection: Mapping[str, object] | None,
    selection_identity: Mapping[str, object] | None,
    expected_selection_identity: Mapping[str, object] | None,
    qualification_receipt: Mapping[str, object] | None,
    qualification_receipt_identity: Mapping[str, object] | None,
    semantic_replay: object | None,
    arm_results: Mapping[str, object] | None,
    inner_raw_results: Mapping[str, object] | None,
    terminal_envelopes: Mapping[str, object] | None,
    model_binary_identities: Mapping[str, object] | None,
    response_binary_identities: Mapping[str, object] | None,
) -> dict[str, object]:
    """Evaluate every common gate without short-circuiting missing evidence."""

    del (
        arm_results,
        inner_raw_results,
        terminal_envelopes,
        model_binary_identities,
        response_binary_identities,
    )

    selection_valid = False
    selection_error: str | None = None
    if selection is not None:
        try:
            validate_selection_payload(selection)
        except GateV3Error as exc:
            selection_error = str(exc)
        else:
            selection_valid = True
    selection_identity_ok = _identity_equal(selection_identity, expected_selection_identity)
    qualification_ok = (
        selection_valid
        and selection_identity_ok
        and _qualification_pass(selection, qualification_receipt, qualification_receipt_identity)
    )
    tools_ok, replayed_tools = _replay_identity_map(selection.get("tools") if selection_valid else None)
    gate_self_ok, gate_tool_identity = _gate_self_bound(selection if selection_valid else None)
    tools_ok = tools_ok and gate_self_ok
    inputs_ok, replayed_inputs = _replay_identity_map(selection.get("inputs") if selection_valid else None)
    paired_launch = bool(
        selection_valid
        and selection_identity_ok
        and qualification_ok
        and selection is not None
        and selection.get("purpose") == PAIRED_PURPOSE
        and selection.get("arm_launch") is True
        and tools_ok
        and inputs_ok
    )
    replay = _gate_owned_replay(semantic_replay)
    replay_arm_results = replay.arm_results if replay is not None else None
    replay_inner = replay.inner_raw_results if replay is not None else None
    replay_terminal = replay.terminal_envelopes if replay is not None else None
    replay_model = replay.model_binary_identities if replay is not None else None
    replay_response = replay.response_binary_identities if replay is not None else None
    arm_join = paired_launch and _arm_join_pass(selection, selection_identity, replay_arm_results)
    resource_ok = replay is not None and replay.resource_report is not None
    inner_raw_ok = _paired_semantic_join(replay_inner, replay_arm_results)
    terminal_ok = _paired_semantic_join(replay_terminal, replay_arm_results)
    model_ok = _paired_binary_join(
        replay_model,
        replay_arm_results,
        arm_field="model_binary_identity",
    )
    response_ok = _paired_binary_join(
        replay_response,
        replay_arm_results,
        arm_field="response_binary_identity",
    )
    checker_classification = replay.checker_classification if replay is not None else None
    checker_ok = checker_classification is not None

    gates = [
        {"missing_code": "qualification_package_missing", "name": "qualification_package", "passed": qualification_ok},
        {"missing_code": "resource_authority_missing", "name": "resource_authority", "passed": resource_ok},
        {
            "missing_code": "paired_arm_launch_authority_missing",
            "name": "paired_arm_launch",
            "passed": paired_launch,
        },
        {"missing_code": "arm_result_join_missing", "name": "arm_result_join", "passed": arm_join},
        {
            "missing_code": "resource_inner_raw_authority_missing",
            "name": "inner_raw",
            "passed": inner_raw_ok,
        },
        {
            "missing_code": "resource_terminal_authority_missing",
            "name": "terminal_envelope",
            "passed": terminal_ok,
        },
        {
            "missing_code": "selector_model_binary_authority_missing",
            "name": "model_binary",
            "passed": model_ok,
        },
        {
            "missing_code": "selector_solver_response_binary_authority_missing",
            "name": "response_binary",
            "passed": response_ok,
        },
        {"missing_code": "tool_identity_drift", "name": "tool_identity_replay", "passed": tools_ok},
        {"missing_code": "input_identity_drift", "name": "input_identity_replay", "passed": inputs_ok},
    ]
    historical = bool(selection_valid and selection is not None and selection.get("purpose") == HISTORICAL_PURPOSE)
    if not historical:
        gates.append(
            {
                "missing_code": "checker_semantics_missing",
                "name": "checker_semantics",
                "passed": checker_ok,
            }
        )
    missing = [str(row["missing_code"]) for row in gates if not bool(row["passed"])]
    complete = not missing and not historical
    if complete:
        status = str(checker_classification)
        reason = None
        advance = status == "INJECTED_MECHANISM_POSITIVE_CONTROL"
        established = (
            ["post_fix_typed_path_reachable", "one_applied_inequality_excludes_frozen_incumbent"]
            if advance
            else ["no_generated_compiled_or_applied_cut_observed_in_prospectively_launched_pair"]
        )
    else:
        status = "CREDIBILITY_INCOMPLETE"
        reason = missing[0] if missing else "historical_overlay_not_an_experiment"
        advance = False
        established = []
    return {
        "advance_authorized": advance,
        "arm_launch_authorized": paired_launch,
        "classification_complete": complete,
        "claim_boundary": {
            "established": established,
            "not_established": [
                "cut_global_soundness",
                "organic_runtime_usefulness",
                "single_family_usefulness",
                "pic4_or_pic5_closed",
                "b6_authorized",
                "unsat_or_infeasibility_proof",
                "witness_or_lower_bound",
            ],
        },
        "experiment_verdict": complete,
        "gates": gates,
        "gate_tool_identity": gate_tool_identity,
        "historical_overlay": historical,
        "missing_gates": missing,
        "overlay": historical,
        "qualification_receipt_is_authorization_root": False,
        "reason": reason,
        "resource_replay_report": replay.resource_report if replay is not None else None,
        "checker_replay_report": replay.checker_report if replay is not None else None,
        "replayed_inputs": replayed_inputs,
        "replayed_tools": replayed_tools,
        "schema": GATE_SCHEMA,
        "selection_error": selection_error,
        "selection_is_direct_authority_root": selection_valid and selection_identity_ok,
        "semantic_replay_gate_owned": replay is not None,
        "status": status,
    }


def exit_code(result: Mapping[str, object]) -> int:
    return 0 if result.get("classification_complete") is True else 2


def _read_json(path: Path) -> tuple[dict[str, Any], dict[str, object]]:
    data = _read_regular(path)
    value = _strict_json_bytes(data, f"JSON input {path}")
    if type(value) is not dict:
        raise GateV3Error(f"JSON input root must be an object: {path}")
    return value, {"path": str(_absolute(path)), "sha256": _sha256(data), "size_bytes": len(data)}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--expected-selection-size", type=int, required=True)
    parser.add_argument("--expected-selection-sha256", required=True)
    parser.add_argument("--qualification-receipt", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    inputs: dict[str, object] = {}
    try:
        selection, selection_identity = _read_json(args.selection)
        inputs["selection"] = selection_identity
        receipt, receipt_identity = _read_json(args.qualification_receipt)
        inputs["qualification_receipt"] = receipt_identity
        evidence, evidence_identity = _read_json(args.evidence)
        inputs["evidence"] = evidence_identity
        semantic_replay = _replay_exact_path_manifest(evidence, selection, args.selection)
        expected_selection = {
            "path": str(_absolute(args.selection)),
            "sha256": args.expected_selection_sha256,
            "size_bytes": args.expected_selection_size,
        }
        result = evaluate_gate(
            selection=selection,
            selection_identity=selection_identity,
            expected_selection_identity=expected_selection,
            qualification_receipt=receipt,
            qualification_receipt_identity=receipt_identity,
            semantic_replay=semantic_replay,
            arm_results=None,
            inner_raw_results=None,
            terminal_envelopes=None,
            model_binary_identities=None,
            response_binary_identities=None,
        )
        result["inputs"] = inputs
    except Exception as exc:  # noqa: BLE001 - write a fail-closed gate record
        result = {
            "advance_authorized": False,
            "arm_launch_authorized": False,
            "classification_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
            "experiment_verdict": False,
            "historical_overlay": False,
            "inputs": inputs,
            "missing_gates": list(COMMON_MISSING_GATES),
            "overlay": False,
            "reason": "gate_exception",
            "schema": GATE_SCHEMA,
            "status": "CREDIBILITY_INCOMPLETE",
        }
    _write_exclusive(args.output, result)
    print(json.dumps(result, sort_keys=True))
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
