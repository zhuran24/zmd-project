#!/usr/bin/env python3
"""Fail-closed final integration gate for CUTS_GATE1_V4.

This module is deliberately an integration layer.  It executes the exact
campaign-authority, resource-verifier, and independent-arithmetic checker
bytes selected by the campaign, compares their recomputed results with the
detached receipts, and joins those results to the same campaign root,
selection, manager/boot epoch, and positive-control prestate.

A PASS establishes only ``MECHANISM_CREDIBLE``.  It keeps the campaign open
and does not authorize an organic arm, a mathematical claim, or production
use of any cut family.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import sys
import types
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any


GATE_SCHEMA = "noncert-cuts-gate1-v4-final-gate-v1"
CHECKPOINT_SCHEMA = "noncert-cuts-gate1-v4-manager-epoch-checkpoint-v2"
GATE_STATUS = "CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS"
GATE_VERDICT = "MECHANISM_CREDIBLE"
GATE_SLOTS = (
    "q-success",
    "q-postseal-fail",
    "forced-control",
    "forced-treatment",
)
CHECKPOINT_PHASES = (
    "prelaunch",
    "preterminal",
    "terminal",
    "cleanup",
    "detached-replay",
)
REPLAY_TOOL_ROLES = (
    "campaign_authority_v4",
    "gate1_campaign_driver_v4",
    "resource_lifecycle_v4",
    "resource_verifier_v4",
    "gate1_unit_orchestrator_v4",
    "independent_arithmetic_v4",
    "positive_control_gate_v4",
)
EXPECTED_TERMINAL_CLASS = {
    "q-success": "success",
    "q-postseal-fail": "postseal-failure",
    "forced-control": "success",
    "forced-treatment": "success",
}
EXPECTED_PAYLOAD_RETURNCODE = {
    "q-success": 0,
    "q-postseal-fail": 7,
    "forced-control": 0,
    "forced-treatment": 0,
}
DETACHED_RESOURCE_SCHEMA = "noncert-cuts-gate1-v4-detached-lifecycle-v1"
PAYLOAD_RESULT_SCHEMA = "noncert-cuts-gate1-v4-payload-result-v1"
PAYLOAD_SEAL_SCHEMA = "noncert-cuts-gate1-v4-payload-seal-v1"
ARITHMETIC_SCHEMA = "noncert-cuts-gate1-v4-formal-independent-arithmetic-receipt-v1"
SHA256_HEX = frozenset("0123456789abcdef")
MAX_JSON_BYTES = 64 * 1024 * 1024


class GateError(RuntimeError):
    """One admission condition failed closed."""


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_json(raw: bytes, label: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise GateError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    if len(raw) > MAX_JSON_BYTES:
        raise GateError(f"{label}: JSON exceeds the byte limit")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(GateError(f"{label}: non-finite JSON token {token}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateError(f"{label}: malformed JSON") from exc


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise GateError(f"{label}: expected an exact JSON object")
    return value


def _keys(value: object, expected: set[str], label: str) -> Mapping[str, Any]:
    record = _mapping(value, label)
    if set(record) != expected:
        raise GateError(f"{label}: field set drifted")
    return record


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _keys(value, {"path", "size_bytes", "sha256"}, label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or type(record["sha256"]) is not str
        or len(record["sha256"]) != 64
        or not set(record["sha256"]) <= SHA256_HEX
    ):
        raise GateError(f"{label}: detached identity is malformed")
    return record


def _verify_bytes(raw: bytes, identity: object, label: str) -> Mapping[str, Any]:
    record = _identity(identity, label)
    if len(raw) != record["size_bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise GateError(f"{label}: detached byte identity drifted")
    return record


def _bound_json(
    raw: bytes,
    identity: object,
    label: str,
    *,
    newline: bool,
) -> Mapping[str, Any]:
    _verify_bytes(raw, identity, label)
    payload = raw[:-1] if newline and raw.endswith(b"\n") else raw
    if newline and not raw.endswith(b"\n"):
        raise GateError(f"{label}: required canonical newline is absent")
    value = _strict_json(payload, label)
    if canonical_json(value) != payload:
        raise GateError(f"{label}: JSON bytes are not canonical")
    return _mapping(value, label)


def _utc(value: object, label: str) -> str:
    if type(value) is not str:
        raise GateError(f"{label}: timestamp is not a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateError(f"{label}: timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise GateError(f"{label}: timestamp lacks a timezone")
    return value


def _epoch_digest(epoch: object) -> str:
    return hashlib.sha256(canonical_json(epoch) + b"\n").hexdigest()


def _strict_sha256(value: object, label: str) -> str:
    if type(value) is not str or len(value) != 64 or not set(value) <= SHA256_HEX:
        raise GateError(f"{label}: expected a lowercase SHA-256 digest")
    return value


def _tool_namespace(
    role: str,
    bound: Mapping[str, object],
    selected_identity: object,
    *,
    module_aliases: Mapping[str, types.ModuleType] | None = None,
) -> dict[str, object]:
    member = _keys(bound, {"raw", "identity"}, f"tool source {role}")
    raw = member["raw"]
    if type(raw) is not bytes:
        raise GateError(f"tool source {role}: raw bytes are absent")
    identity = _verify_bytes(raw, member["identity"], f"tool source {role}")
    if dict(identity) != dict(_identity(selected_identity, f"selected tool {role}")):
        raise GateError(f"tool source {role}: selection identity drifted")
    module_name = f"_cuts_gate1_v4_exact_{role}_{str(identity['sha256'])[:16]}"
    module = types.ModuleType(module_name)
    module.__file__ = str(identity["path"])
    module.__package__ = None
    namespace = module.__dict__
    prior = sys.modules.get(module_name)
    prior_aliases = {name: sys.modules.get(name) for name in (module_aliases or {})}
    sys.modules[module_name] = module
    sys.modules.update(module_aliases or {})
    try:
        code = compile(
            raw,
            f"<authority-selected:{role}:{identity['sha256']}>",
            "exec",
            dont_inherit=True,
        )
        exec(code, namespace, namespace)
    except Exception as exc:
        raise GateError(f"tool source {role}: exact-byte execution failed") from exc
    finally:
        if prior is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = prior
        for name, prior_alias in prior_aliases.items():
            if prior_alias is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior_alias
    return namespace


def _checkpoint(
    *,
    raw: bytes,
    identity: object,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    slot: str,
    phase: str,
    attempt_dir: Path,
    campaign_root_raw: bytes,
    campaign_root_identity: Mapping[str, object],
    selection_raw: bytes,
    selection_identity: Mapping[str, object],
    driver: Mapping[str, object],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    receipt = _bound_json(
        raw,
        identity,
        f"{slot} {phase} manager checkpoint",
        newline=True,
    )
    replay = driver.get("replay_lifecycle_epoch_checkpoint")
    if not callable(replay):
        raise GateError("campaign driver lacks strict checkpoint replay")
    try:
        replayed = replay(
            checkpoint_raw=raw,
            checkpoint_identity=identity,
            campaign_root_raw=campaign_root_raw,
            campaign_root_identity=campaign_root_identity,
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            unit_slot=slot,
            phase=phase,
        )
    except Exception as exc:
        raise GateError(f"{slot} {phase}: strict checkpoint replay failed: {exc}") from exc
    if replayed != receipt:
        raise GateError(f"{slot} {phase}: strict checkpoint replay result drifted")
    exact = receipt
    detached = _identity(identity, f"{slot} {phase} checkpoint identity")
    expected_path = selection["units"][slot]["epoch_checkpoint_paths"][phase]
    if detached["path"] != expected_path or not Path(detached["path"]).is_relative_to(attempt_dir):
        raise GateError(f"{slot} {phase}: checkpoint differs from preregistered path")
    return exact, detached


def _gate_admission_checkpoint(
    *,
    member: Mapping[str, object],
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    campaign_root_raw: bytes,
    campaign_root_identity: Mapping[str, object],
    selection_raw: bytes,
    selection_identity: Mapping[str, object],
    driver: Mapping[str, object],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    evidence = _keys(
        member,
        {"raw", "identity"},
        "gate-admission manager checkpoint member",
    )
    raw = evidence["raw"]
    if type(raw) is not bytes:
        raise GateError("gate-admission manager checkpoint bytes are absent")
    receipt = _bound_json(
        raw,
        evidence["identity"],
        "gate-admission manager checkpoint",
        newline=True,
    )
    replay = driver.get("replay_lifecycle_epoch_checkpoint")
    if not callable(replay):
        raise GateError("campaign driver lacks gate-admission replay")
    try:
        replayed = replay(
            checkpoint_raw=raw,
            checkpoint_identity=evidence["identity"],
            campaign_root_raw=campaign_root_raw,
            campaign_root_identity=campaign_root_identity,
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            unit_slot="gate-admission",
            phase="gate-admission",
        )
    except Exception as exc:
        raise GateError(f"gate-admission manager checkpoint replay failed: {exc}") from exc
    if replayed != receipt:
        raise GateError("gate-admission manager checkpoint replay result drifted")
    identity = _identity(
        evidence["identity"],
        "gate-admission manager checkpoint identity",
    )
    expected_path = root["stage_topology"]["gate1_v4"]["gate_admission_epoch_path"]
    campaign_dir = Path(campaign_root_identity["path"]).parent
    if identity["path"] != expected_path or not Path(identity["path"]).is_relative_to(campaign_dir):
        raise GateError("gate-admission manager checkpoint path differs from preregistration")
    return receipt, identity


def _resource_replay(
    *,
    slot: str,
    member: Mapping[str, object],
    selection_raw: bytes,
    selection_identity: Mapping[str, object],
    selection: Mapping[str, Any],
    verifier_identity: Mapping[str, object],
    verifier: Mapping[str, object],
    expected_forced_profile: str,
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[str, Mapping[str, Any]],
]:
    replay = _keys(
        member,
        {"detached_raw", "detached_identity", "evidence"},
        f"{slot} resource replay",
    )
    detached_raw = replay["detached_raw"]
    if type(detached_raw) is not bytes:
        raise GateError(f"{slot}: detached resource bytes are absent")
    detached = _bound_json(
        detached_raw,
        replay["detached_identity"],
        f"{slot} detached resource replay",
        newline=True,
    )
    evidence = _keys(
        replay["evidence"],
        {
            "inner",
            "payload_result",
            "payload_seal",
            "preterminal",
            "resource",
            "release",
            "terminal",
            "cleanup",
        },
        f"{slot} resource evidence",
    )

    def bound(name: str) -> tuple[bytes, Mapping[str, Any]]:
        item = _keys(evidence[name], {"raw", "identity"}, f"{slot} {name}")
        raw = item["raw"]
        if type(raw) is not bytes:
            raise GateError(f"{slot} {name}: raw bytes are absent")
        identity = _verify_bytes(raw, item["identity"], f"{slot} {name}")
        return raw, identity

    parts = {name: bound(name) for name in evidence}
    if expected_forced_profile not in {"formal_campaign", "disposable_drill"}:
        raise GateError("forced payload replay profile is invalid")
    inner = _bound_json(
        parts["inner"][0],
        parts["inner"][1],
        f"{slot} inner lifecycle",
        newline=True,
    )
    payload_result = _keys(
        _bound_json(
            parts["payload_result"][0],
            parts["payload_result"][1],
            f"{slot} payload result",
            newline=True,
        ),
        {
            "schema_version",
            "created_at_utc",
            "campaign_root_identity",
            "selection_identity",
            "campaign_id",
            "run_nonce",
            "selection_id",
            "unit_slot",
            "unit_name",
            "payload_kind",
            "expected_returncode",
            "delegated_tool_role",
            "delegated_tool_identity",
            "delegated_result",
            "sealed_before_exit",
            "mechanism_credible_authorized",
            "organic_arm_launch_authorized",
            "global_claim_authorized",
        },
        f"{slot} payload result",
    )
    payload_seal = _keys(
        _bound_json(
            parts["payload_seal"][0],
            parts["payload_seal"][1],
            f"{slot} payload seal",
            newline=True,
        ),
        {
            "schema_version",
            "created_at_utc",
            "campaign_id",
            "run_nonce",
            "selection_id",
            "unit_slot",
            "unit_name",
            "result_identity",
            "expected_returncode",
            "delegated_tool_identity",
            "payload_complete",
        },
        f"{slot} payload seal",
    )
    _utc(payload_result["created_at_utc"], f"{slot} payload result created_at")
    _utc(payload_seal["created_at_utc"], f"{slot} payload seal created_at")
    expected_result_path = selection["units"][slot]["result_path"]
    expected_seal_path = str(Path(selection["units"][slot]["raw_dir"]) / "payload-seal.json")
    if (
        inner.get("payload_result_identity") != dict(parts["payload_result"][1])
        or inner.get("payload_seal_identity") != dict(parts["payload_seal"][1])
        or parts["payload_result"][1]["path"] != expected_result_path
        or parts["payload_seal"][1]["path"] != expected_seal_path
        or payload_seal.get("result_identity") != dict(parts["payload_result"][1])
    ):
        raise GateError(f"{slot}: payload result/seal does not join inner lifecycle")
    result_expected = {
        "schema_version": PAYLOAD_RESULT_SCHEMA,
        "campaign_root_identity": selection["campaign_root_identity"],
        "selection_identity": dict(selection_identity),
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "unit_slot": slot,
        "unit_name": selection["units"][slot]["unit_name"],
        "expected_returncode": EXPECTED_PAYLOAD_RETURNCODE[slot],
        "sealed_before_exit": True,
        "mechanism_credible_authorized": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
    }
    if any(payload_result.get(key) != value for key, value in result_expected.items()):
        raise GateError(f"{slot}: payload result semantics drifted")
    if (
        payload_seal.get("schema_version") != PAYLOAD_SEAL_SCHEMA
        or payload_seal.get("campaign_id") != selection["campaign_id"]
        or payload_seal.get("run_nonce") != selection["run_nonce"]
        or payload_seal.get("selection_id") != selection["selection_id"]
        or payload_seal.get("unit_slot") != slot
        or payload_seal.get("unit_name") != selection["units"][slot]["unit_name"]
        or payload_seal.get("expected_returncode") != EXPECTED_PAYLOAD_RETURNCODE[slot]
        or payload_seal.get("payload_complete") is not True
        or payload_seal.get("delegated_tool_identity") != payload_result.get("delegated_tool_identity")
    ):
        raise GateError(f"{slot}: payload seal semantics drifted")
    if slot.startswith("forced-"):
        expected_arm = "control" if slot == "forced-control" else "treatment"
        expected_count = 0 if slot == "forced-control" else 1
        delegated = _keys(
            payload_result.get("delegated_result"),
            {
                "status",
                "profile",
                "arm",
                "common_prestate_id",
                "generated",
                "compiled",
                "applied",
                "support_tool_identity",
                "post_solve_performed",
                "organic_arm_launch_authorized",
                "global_claim_authorized",
            },
            f"{slot} delegated result",
        )
        _strict_sha256(
            delegated["common_prestate_id"],
            f"{slot} delegated common_prestate_id",
        )
        if (
            payload_result.get("payload_kind") != "forced-positive-control"
            or payload_result.get("delegated_tool_role") != "positive_control_formal_v4"
            or payload_result.get("delegated_tool_identity") != selection["tools"]["positive_control_formal_v4"]
            or delegated.get("status") != "PASS"
            or delegated.get("arm") != expected_arm
            or delegated.get("profile") != expected_forced_profile
            or delegated.get("generated") != expected_count
            or delegated.get("compiled") != expected_count
            or delegated.get("applied") != expected_count
            or delegated.get("support_tool_identity") != selection["tools"]["positive_control_v4"]
            or delegated.get("post_solve_performed") is not False
            or delegated.get("organic_arm_launch_authorized") is not False
            or delegated.get("global_claim_authorized") is not False
        ):
            raise GateError(f"{slot}: forced payload result semantics drifted")
    elif (
        payload_result.get("payload_kind") != "synthetic-lifecycle"
        or payload_result.get("delegated_tool_role") is not None
        or payload_result.get("delegated_tool_identity") is not None
        or payload_result.get("delegated_result") is not None
    ):
        raise GateError(f"{slot}: synthetic payload result semantics drifted")
    verify = verifier.get("verify_detached_bytes")
    if not callable(verify):
        raise GateError("resource verifier lacks verify_detached_bytes")
    try:
        recomputed = verify(
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            unit_slot=slot,
            inner_raw=parts["inner"][0],
            inner_identity=parts["inner"][1],
            preterminal_raw=parts["preterminal"][0],
            preterminal_identity=parts["preterminal"][1],
            resource_raw=parts["resource"][0],
            resource_identity=parts["resource"][1],
            release_raw=parts["release"][0],
            release_identity=parts["release"][1],
            terminal_raw=parts["terminal"][0],
            terminal_identity=parts["terminal"][1],
            cleanup_raw=parts["cleanup"][0],
            cleanup_identity=parts["cleanup"][1],
            verifier_identity=verifier_identity,
            created_at_utc=detached["created_at_utc"],
        )
    except Exception as exc:
        raise GateError(f"{slot}: detached resource replay failed") from exc
    if recomputed != detached or canonical_json(recomputed) + b"\n" != detached_raw:
        raise GateError(f"{slot}: detached resource receipt does not match replay")
    expected_scalars = {
        "schema_version": DETACHED_RESOURCE_SCHEMA,
        "status": "PASS",
        "verdict": "LIFECYCLE_DETACHED_PASS",
        "terminal_class": EXPECTED_TERMINAL_CLASS[slot],
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "manager_epoch_digest": _epoch_digest(selection["manager_epoch"]),
        "unit_slot": slot,
        "unit_name": selection["units"][slot]["unit_name"],
        "mechanism_credible_authorized": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
    }
    if any(detached.get(key) != value for key, value in expected_scalars.items()):
        raise GateError(f"{slot}: detached resource semantics drifted")
    if detached.get("selection_identity") != dict(selection_identity):
        raise GateError(f"{slot}: detached selection identity drifted")
    if detached.get("verifier_identity") != dict(verifier_identity):
        raise GateError(f"{slot}: detached verifier identity drifted")
    derived = _mapping(detached.get("derived"), f"{slot} derived resource facts")
    expected_derived = {
        "payload_returncode": EXPECTED_PAYLOAD_RETURNCODE[slot],
        "payload_timed_out": False,
        "keeper_only": True,
        "payload_status_preserved": True,
        "unit_absent": True,
        "cgroup_absent": True,
        "remaining_pids": [],
    }
    if any(derived.get(key) != value for key, value in expected_derived.items()):
        raise GateError(f"{slot}: detached terminal/cleanup facts drifted")
    return (
        detached,
        _identity(
            replay["detached_identity"],
            f"{slot} detached replay identity",
        ),
        payload_result,
        {
            "result": parts["payload_result"][1],
            "seal": parts["payload_seal"][1],
        },
    )


def _checkpoint_lifecycle_join(
    *,
    slot: str,
    checkpoints: Mapping[str, Mapping[str, Any]],
    detached: Mapping[str, Any],
) -> None:
    """Bind live epoch observations to the independently replayed lifecycle."""

    derived = _mapping(detached.get("derived"), f"{slot} derived resource facts")
    required = {
        "systemd_exec_start_monotonic_usec",
        "preterminal_monotonic_ns",
        "released_monotonic_ns",
        "terminal_monotonic_ns",
        "cleanup_monotonic_ns",
    }
    if not required <= set(derived):
        raise GateError(f"{slot}: lifecycle monotonic authority is incomplete")
    values = {name: derived[name] for name in required}
    if any(type(value) is not int or value <= 0 for value in values.values()):
        raise GateError(f"{slot}: lifecycle monotonic authority is malformed")
    start_ns = values["systemd_exec_start_monotonic_usec"] * 1_000
    prelaunch = checkpoints["prelaunch"]["captured_monotonic_ns"]
    preterminal = checkpoints["preterminal"]["captured_monotonic_ns"]
    terminal = checkpoints["terminal"]["captured_monotonic_ns"]
    cleanup = checkpoints["cleanup"]["captured_monotonic_ns"]
    detached_replay = checkpoints["detached-replay"]["captured_monotonic_ns"]
    if not (
        prelaunch
        < start_ns
        < preterminal
        <= values["preterminal_monotonic_ns"]
        < values["released_monotonic_ns"]
        < terminal
        <= values["terminal_monotonic_ns"]
        < cleanup
        <= values["cleanup_monotonic_ns"]
        < detached_replay
    ):
        raise GateError(f"{slot}: manager checkpoints do not bracket lifecycle phases")


def _launch_replay(
    *,
    slot: str,
    member: Mapping[str, object],
    root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    selection: Mapping[str, Any],
    checkpoints: Mapping[str, Mapping[str, Any]],
    orchestrator: Mapping[str, object],
    authority_namespace: Mapping[str, object],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    launch_member = _keys(
        member,
        {"raw", "identity"},
        f"{slot} systemd-run launch member",
    )
    raw = launch_member["raw"]
    if type(raw) is not bytes:
        raise GateError(f"{slot}: systemd-run launch bytes are absent")
    identity = _identity(
        launch_member["identity"],
        f"{slot} systemd-run launch identity",
    )
    launch = _keys(
        _bound_json(
            raw,
            identity,
            f"{slot} systemd-run launch evidence",
            newline=True,
        ),
        {
            "schema_version",
            "created_at_utc",
            "campaign_root_identity",
            "selection_identity",
            "campaign_id",
            "run_nonce",
            "selection_id",
            "manager_epoch_digest",
            "unit_slot",
            "unit_name",
            "argv",
            "argv_sha256",
            "selected_loader_sha256",
            "orchestrator_identity",
            "exit_code",
            "stdout_b64",
            "stderr_b64",
            "started_monotonic_ns",
            "finished_monotonic_ns",
            "systemd_run_identity",
        },
        f"{slot} systemd-run launch evidence",
    )
    _utc(launch["created_at_utc"], f"{slot} launch created_at_utc")
    if type(launch["stdout_b64"]) is not str or type(launch["stderr_b64"]) is not str:
        raise GateError(f"{slot}: launch output encoding drifted")
    try:
        base64.b64decode(launch["stdout_b64"].encode("ascii"), validate=True)
        base64.b64decode(launch["stderr_b64"].encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise GateError(f"{slot}: launch output base64 is malformed") from exc
    expected_path = str(Path(selection["units"][slot]["raw_dir"]) / "systemd-run-launch.json")
    if identity["path"] != expected_path:
        raise GateError(f"{slot}: launch evidence escaped preregistered attempt")
    build = orchestrator.get("build_systemd_run_argv")
    if not callable(build):
        raise GateError("selected unit orchestrator lacks build_systemd_run_argv")
    try:
        expected_argv = tuple(
            build(
                root_identity=root_identity,
                selection_identity=selection_identity,
                selection=selection,
                unit_slot=slot,
            )
        )
    except Exception as exc:
        raise GateError(f"{slot}: selected launch argv reconstruction failed") from exc
    canonical = authority_namespace.get("canonical_json")
    if not callable(canonical):
        raise GateError("selected campaign authority lacks canonical_json")
    loader = orchestrator.get("SELECTED_BYTE_ENTRYPOINT_LOADER")
    launch_schema = orchestrator.get("LAUNCH_SCHEMA")
    expected_scalars = {
        "schema_version": launch_schema,
        "campaign_root_identity": dict(root_identity),
        "selection_identity": dict(selection_identity),
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "manager_epoch_digest": _epoch_digest(selection["manager_epoch"]),
        "unit_slot": slot,
        "unit_name": selection["units"][slot]["unit_name"],
        "argv": list(expected_argv),
        "argv_sha256": hashlib.sha256(canonical(list(expected_argv))).hexdigest(),
        "selected_loader_sha256": (hashlib.sha256(loader.encode("utf-8")).hexdigest() if type(loader) is str else None),
        "orchestrator_identity": selection["tools"]["gate1_unit_orchestrator_v4"],
        "exit_code": 0,
        "systemd_run_identity": selection["tools"]["systemd_run"],
    }
    if any(launch.get(key) != value for key, value in expected_scalars.items()):
        raise GateError(f"{slot}: launch argv or selected tool identity drifted")
    started = launch.get("started_monotonic_ns")
    finished = launch.get("finished_monotonic_ns")
    prelaunch = checkpoints["prelaunch"]["captured_monotonic_ns"]
    preterminal_rounds = _mapping(
        checkpoints["preterminal"]["capture_transcript"],
        f"{slot} preterminal capture transcript",
    ).get("rounds")
    if (
        type(started) is not int
        or type(finished) is not int
        or type(preterminal_rounds) is not list
        or len(preterminal_rounds) != 2
    ):
        raise GateError(f"{slot}: launch timeline fields drifted")
    preterminal_started = _mapping(
        preterminal_rounds[0],
        f"{slot} preterminal first capture round",
    ).get("observation_started_monotonic_ns")
    if not (type(preterminal_started) is int and prelaunch < started <= finished < preterminal_started):
        raise GateError(f"{slot}: launch does not join lifecycle checkpoints")
    return launch, identity


def _arithmetic_replay(
    positive: Mapping[str, object],
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    checker: Mapping[str, object],
) -> tuple[Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    record = _keys(
        positive,
        {
            "bundle",
            "pair_selection_identity",
            "common_prestate_identity",
            "binding_set_identity",
            "arithmetic_raw",
            "arithmetic_identity",
        },
        "positive-control evidence",
    )
    bundle = _mapping(record["bundle"], "positive-control bundle")
    verify = checker.get("verify_formal_bundle")
    if not callable(verify):
        raise GateError("independent arithmetic checker lacks the formal-only verify_formal_bundle API")
    try:
        recomputed = verify(bundle)
    except Exception as exc:
        raise GateError("independent arithmetic replay failed") from exc
    raw = record["arithmetic_raw"]
    if type(raw) is not bytes:
        raise GateError("independent arithmetic receipt bytes are absent")
    receipt = _bound_json(
        raw,
        record["arithmetic_identity"],
        "independent arithmetic receipt",
        newline=True,
    )
    if recomputed != receipt or canonical_json(recomputed) + b"\n" != raw:
        raise GateError("independent arithmetic receipt differs from replay")
    pair_selection = _mapping(bundle.get("selection"), "positive pair selection")
    if (
        pair_selection.get("campaign_id") != root["campaign_id"]
        or pair_selection.get("run_nonce") != root["run_nonce"]
        or pair_selection.get("manager_epoch_digest") != _epoch_digest(root["manager_epoch"])
        or pair_selection.get("gate1_formal_eligible") is not True
    ):
        raise GateError("positive pair is not formally joined to this campaign")
    identities = {
        "pair_selection": _identity(
            record["pair_selection_identity"],
            "positive pair selection identity",
        ),
        "common_prestate": _identity(
            record["common_prestate_identity"],
            "positive common-prestate identity",
        ),
        "binding_set": _identity(
            record["binding_set_identity"],
            "positive binding-set identity",
        ),
        "arithmetic": _identity(
            record["arithmetic_identity"],
            "independent arithmetic receipt identity",
        ),
    }
    positive_topology = _mapping(
        root["stage_topology"]["gate1_v4"].get("positive_control"),
        "positive-control preregistered topology",
    )
    expected_identity_paths = {
        "pair_selection": positive_topology.get("selection_path"),
        "common_prestate": positive_topology.get("common_manifest_path"),
        "binding_set": positive_topology.get("binding_seal_path"),
        "arithmetic": positive_topology.get("arithmetic_receipt_path"),
    }
    if any(identities[role]["path"] != expected_path for role, expected_path in expected_identity_paths.items()):
        raise GateError("positive-control evidence escaped preregistered paths")
    pair_raw, _ = snapshot_regular(
        Path(identities["pair_selection"]["path"]),
        expected_identity=identities["pair_selection"],
    )
    if (
        _bound_json(
            pair_raw,
            identities["pair_selection"],
            "positive pair selection authority",
            newline=True,
        )
        != pair_selection
    ):
        raise GateError("positive pair selection value differs from bound bytes")
    if (
        bundle.get("selection_identity") != dict(identities["pair_selection"])
        or bundle.get("common_identity") != dict(identities["common_prestate"])
        or bundle.get("binding_seal_identity") != dict(identities["binding_set"])
    ):
        raise GateError("positive-control authority identity join drifted")
    common_raw, _ = snapshot_regular(
        Path(identities["common_prestate"]["path"]),
        expected_identity=identities["common_prestate"],
    )
    if _bound_json(
        common_raw,
        identities["common_prestate"],
        "positive common-prestate manifest authority",
        newline=True,
    ) != bundle.get("common"):
        raise GateError("positive common-prestate value differs from bound bytes")
    common = _mapping(bundle.get("common"), "positive common-prestate manifest")
    common_prestate_id = _strict_sha256(
        common.get("common_prestate_id"),
        "positive common_prestate_id",
    )
    common_artifact_identities = _mapping(
        common.get("artifacts"),
        "positive common-prestate artifact identity map",
    )
    expected_common_prestate_id = hashlib.sha256(
        canonical_json(
            {
                "campaign_id": common.get("campaign_id"),
                "run_nonce": common.get("run_nonce"),
                "manager_epoch_digest": common.get("manager_epoch_digest"),
                "selection_identity": bundle.get("selection_identity"),
                "artifacts": common_artifact_identities,
                "phase": "pre_injection",
            }
        )
    ).hexdigest()
    if (
        common.get("phase") != "pre_injection"
        or common.get("campaign_id") != root["campaign_id"]
        or common.get("run_nonce") != root["run_nonce"]
        or common.get("manager_epoch_digest") != _epoch_digest(root["manager_epoch"])
        or common_prestate_id != expected_common_prestate_id
    ):
        raise GateError("positive common_prestate_id derivation drifted")
    binding_seal_raw, _ = snapshot_regular(
        Path(identities["binding_set"]["path"]),
        expected_identity=identities["binding_set"],
    )
    if _bound_json(
        binding_seal_raw,
        identities["binding_set"],
        "positive binding-set authority",
        newline=True,
    ) != bundle.get("binding_seal"):
        raise GateError("positive binding-set value differs from bound bytes")
    common_artifacts = _mapping(
        bundle.get("common_artifacts"),
        "positive common-prestate artifacts",
    )
    expected_artifact_paths = _mapping(
        positive_topology.get("common_artifact_paths"),
        "preregistered positive common artifacts",
    )
    if set(common_artifacts) != set(expected_artifact_paths):
        raise GateError("positive common-prestate artifact role set drifted")
    for role, expected_path in expected_artifact_paths.items():
        member = _mapping(
            common_artifacts[role],
            f"positive common-prestate artifact {role}",
        )
        member_identity = _identity(
            member.get("identity"),
            f"positive common-prestate artifact {role}",
        )
        if member_identity["path"] != expected_path:
            raise GateError("positive common-prestate artifact escaped preregistered path")
        if common_artifact_identities.get(role) != dict(member_identity):
            raise GateError("positive common-prestate artifact identity map drifted")
        member_raw = member.get("raw")
        if type(member_raw) is not bytes:
            raise GateError("positive common-prestate artifact bytes are absent")
        current_raw, _ = snapshot_regular(
            Path(expected_path),
            expected_identity=member_identity,
        )
        if current_raw != member_raw:
            raise GateError("positive common-prestate artifact differs from bound bytes")
    bindings = _mapping(bundle.get("bindings"), "positive arm bindings")
    expected_binding_paths = _mapping(
        positive_topology.get("binding_paths"),
        "preregistered positive bindings",
    )
    if set(bindings) != {"control", "treatment"}:
        raise GateError("positive arm binding role set drifted")
    for arm in ("control", "treatment"):
        binding = _mapping(bindings[arm], f"{arm} positive binding")
        binding_identity = _identity(
            binding.get("identity"),
            f"{arm} positive binding identity",
        )
        if binding_identity["path"] != expected_binding_paths.get(arm):
            raise GateError("positive arm binding escaped preregistered path")
        binding_raw, _ = snapshot_regular(
            Path(binding_identity["path"]),
            expected_identity=binding_identity,
        )
        if _bound_json(
            binding_raw,
            binding_identity,
            f"{arm} positive binding authority",
            newline=True,
        ) != binding.get("value"):
            raise GateError("positive arm binding differs from bound bytes")
    arms = _mapping(bundle.get("arms"), "positive arm evidence")
    expected_arm_dirs = _mapping(
        positive_topology.get("arm_dirs"),
        "preregistered positive arm directories",
    )
    if set(arms) != {"control", "treatment"}:
        raise GateError("positive arm evidence role set drifted")
    member_names = {
        "post_model": "post-injection-model.pb",
        "assignment": "assignment.json",
        "samples": "arithmetic-samples.json",
        "ledger": "ledger.jsonl",
    }
    for arm in ("control", "treatment"):
        arm_member = _mapping(arms[arm], f"{arm} positive arm evidence")
        arm_dir = Path(str(expected_arm_dirs.get(arm)))
        evidence_identity = _identity(
            arm_member.get("evidence_identity"),
            f"{arm} positive evidence identity",
        )
        if Path(evidence_identity["path"]) != arm_dir / "evidence.json":
            raise GateError("positive arm evidence escaped preregistered path")
        evidence_raw, _ = snapshot_regular(
            Path(evidence_identity["path"]),
            expected_identity=evidence_identity,
        )
        if _bound_json(
            evidence_raw,
            evidence_identity,
            f"{arm} positive evidence authority",
            newline=True,
        ) != arm_member.get("evidence"):
            raise GateError("positive arm evidence differs from bound bytes")
        members = _mapping(
            arm_member.get("members"),
            f"{arm} positive evidence members",
        )
        if set(members) != set(member_names):
            raise GateError("positive arm evidence member set drifted")
        for role, filename in member_names.items():
            member = _mapping(members[role], f"{arm} positive {role}")
            member_identity = _identity(
                member.get("identity"),
                f"{arm} positive {role} identity",
            )
            if Path(member_identity["path"]) != arm_dir / filename:
                raise GateError("positive arm member escaped preregistered path")
            member_raw = member.get("raw")
            if type(member_raw) is not bytes:
                raise GateError("positive arm member bytes are absent")
            current_raw, _ = snapshot_regular(
                Path(member_identity["path"]),
                expected_identity=member_identity,
            )
            if current_raw != member_raw:
                raise GateError("positive arm member differs from bound bytes")
    required_checks = [
        "formal_campaign_selection_and_eligibility",
        "common_pre_model_response_solution_incumbent_sealed",
        "both_arm_bindings_precede_post_clone_dependency",
        "production_typed_attach_chain",
        "no_post_attach_solve_or_response",
        "control_applied_zero",
        "treatment_generated_compiled_applied_one_to_one",
        "binary_assignment_model_constraint_ledger_join",
    ]
    selected = _mapping(receipt.get("selected"), "selected inequality")
    expected = {
        "schema": ARITHMETIC_SCHEMA,
        "checker": "independent_arithmetic_v4.verify_formal_bundle",
        "status": "PASS_FORMAL_MECHANISM_POSITIVE_CONTROL",
        "repository_head": selection["repository_head"],
        "selection_identity": dict(identities["pair_selection"]),
        "checks": required_checks,
        "control": {"generated": 0, "compiled": 0, "applied": 0},
        "treatment": {"generated": 1, "compiled": 1, "applied": 1},
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise GateError("independent arithmetic PASS semantics drifted")
    if (
        _strict_sha256(
            receipt.get("common_prestate_id"),
            "arithmetic common_prestate_id",
        )
        != common_prestate_id
    ):
        raise GateError("arithmetic common_prestate_id differs from common authority")
    if (
        selected.get("family") != "region_capacity"
        or selected.get("active") is not True
        or selected.get("violated") is not True
        or type(selected.get("lhs")) is not int
        or type(selected.get("rhs")) is not int
        or selected["lhs"] <= selected["rhs"]
        or selected.get("trigger") != "binding_infeasible"
        or selected.get("iteration") != 1001
        or type(selected.get("epoch_instance_id")) is not str
        or type(selected.get("epoch_semantic_digest")) is not str
        or len(selected["epoch_semantic_digest"]) != 64
        or not set(selected["epoch_semantic_digest"]) <= SHA256_HEX
    ):
        raise GateError("selected APPLIED inequality is not active and violated")
    common = _mapping(receipt.get("common_prestate"), "arithmetic common prestate")
    if common.get("post_solve_performed") is not False:
        raise GateError("positive-control checker reported a post-attach solve")
    return receipt, identities


def evaluate_gate(
    *,
    campaign_root_raw: bytes,
    campaign_root_identity: Mapping[str, object],
    selection_raw: bytes,
    selection_identity: Mapping[str, object],
    gate_admission_epoch: Mapping[str, object],
    tool_sources: Mapping[str, object],
    manager_checkpoints: Mapping[str, object],
    launch_evidence: Mapping[str, object],
    resource_replays: Mapping[str, object],
    positive_control: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    """Replay every Gate 1 condition and return the unique PASS record."""

    _utc(created_at_utc, "Gate 1 created_at_utc")
    if set(tool_sources) != set(REPLAY_TOOL_ROLES):
        raise GateError("Gate 1 replay tool set drifted")
    root_value = _bound_json(
        campaign_root_raw,
        campaign_root_identity,
        "campaign root",
        newline=True,
    )
    selection_value = _bound_json(
        selection_raw,
        selection_identity,
        "Gate 1 selection",
        newline=True,
    )
    selected_tools = _mapping(selection_value.get("tools"), "selected Gate 1 tools")
    authority = _tool_namespace(
        "campaign_authority_v4",
        tool_sources["campaign_authority_v4"],
        selected_tools.get("campaign_authority_v4"),
    )
    authority_module = types.ModuleType("_cuts_gate1_v4_selected_campaign_authority")
    authority_module.__dict__.update(authority)
    lifecycle_namespace = _tool_namespace(
        "resource_lifecycle_v4",
        tool_sources["resource_lifecycle_v4"],
        selected_tools.get("resource_lifecycle_v4"),
    )
    lifecycle_module = types.ModuleType("_cuts_gate1_v4_selected_resource_lifecycle")
    lifecycle_module.__dict__.update(lifecycle_namespace)
    verifier_namespace = _tool_namespace(
        "resource_verifier_v4",
        tool_sources["resource_verifier_v4"],
        selected_tools.get("resource_verifier_v4"),
    )
    verifier_module = types.ModuleType("_cuts_gate1_v4_selected_resource_verifier")
    verifier_module.__dict__.update(verifier_namespace)
    driver_namespace = _tool_namespace(
        "gate1_campaign_driver_v4",
        tool_sources["gate1_campaign_driver_v4"],
        selected_tools.get("gate1_campaign_driver_v4"),
        module_aliases={"campaign_authority_v4": authority_module},
    )
    driver_module = types.ModuleType("_cuts_gate1_v4_selected_checkpoint_driver")
    driver_module.__dict__.update(driver_namespace)
    namespaces = {
        "campaign_authority_v4": authority,
        "resource_lifecycle_v4": lifecycle_namespace,
        "resource_verifier_v4": verifier_namespace,
        "gate1_campaign_driver_v4": driver_namespace,
        "gate1_unit_orchestrator_v4": _tool_namespace(
            "gate1_unit_orchestrator_v4",
            tool_sources["gate1_unit_orchestrator_v4"],
            selected_tools.get("gate1_unit_orchestrator_v4"),
            module_aliases={
                "campaign_authority_v4": authority_module,
                "gate1_campaign_driver_v4": driver_module,
                "resource_lifecycle_v4": lifecycle_module,
                "resource_verifier_v4": verifier_module,
            },
        ),
    }
    for role in REPLAY_TOOL_ROLES:
        if role not in namespaces:
            namespaces[role] = _tool_namespace(
                role,
                tool_sources[role],
                selected_tools.get(role),
            )
    validate_root = authority.get("validate_campaign_root")
    load_selection = authority.get("load_gate1_selection_bytes")
    validate_selection = authority.get("validate_gate1_selection")
    same_epoch = authority.get("same_manager_epoch")
    if not all(callable(item) for item in (validate_root, load_selection, validate_selection, same_epoch)):
        raise GateError("campaign authority replay API is incomplete")
    try:
        root = validate_root(
            root_value,
            campaign_dir=Path(campaign_root_identity["path"]).parent,
        )
        selection = load_selection(selection_raw, selection_identity)
        validate_selection(selection, root=root)
    except Exception as exc:
        raise GateError("campaign root/selection replay failed") from exc
    if selection["campaign_root_identity"] != dict(campaign_root_identity):
        raise GateError("selection does not bind the detached campaign root bytes")
    if root["campaign_closed"] is not False:
        raise GateError("campaign was already closed")
    prospective = root["stage_topology"]["prospective_ab16"]
    future_paths = [
        prospective["manifest_path"],
        prospective["arm_selection_path"],
        prospective["terminal_classification_path"],
        *(arm["attempt_dir"] for arm in prospective["arms"]),
    ]
    if any(Path(path).exists() or Path(path).is_symlink() for path in future_paths):
        raise GateError("prospective AB16 child was created before Gate 1 continuation")

    if set(manager_checkpoints) != set(GATE_SLOTS):
        raise GateError("manager checkpoint unit set drifted")
    if set(launch_evidence) != set(GATE_SLOTS):
        raise GateError("systemd-run launch evidence unit set drifted")
    if set(resource_replays) != set(GATE_SLOTS):
        raise GateError("resource detached replay unit set drifted")
    campaign_dir_name = Path(campaign_root_identity["path"]).parent.name
    if not campaign_dir_name.startswith("run-") or len(campaign_dir_name) == len("run-"):
        raise GateError("formal Gate 1 evaluation requires a nonempty run-* campaign")
    expected_forced_profile = "formal_campaign"
    checkpoint_identities: dict[str, dict[str, Mapping[str, Any]]] = {}
    launch_identities: dict[str, Mapping[str, Any]] = {}
    replay_identities: dict[str, Mapping[str, Any]] = {}
    forced_payload_results: dict[str, Mapping[str, Any]] = {}
    payload_identities: dict[str, Mapping[str, Mapping[str, Any]]] = {}
    checkpoint_records_by_slot: dict[str, Mapping[str, Mapping[str, Any]]] = {}
    checkpoint_paths: set[str] = set()
    launch_paths: set[str] = set()
    replay_paths: set[str] = set()
    for slot in GATE_SLOTS:
        phases = _mapping(manager_checkpoints[slot], f"{slot} manager checkpoints")
        if set(phases) != set(CHECKPOINT_PHASES):
            raise GateError(f"{slot}: manager checkpoint phase set drifted")
        attempt = Path(selection["units"][slot]["attempt_dir"])
        previous_ns = 0
        checkpoint_records: dict[str, Mapping[str, Any]] = {}
        checkpoint_identities[slot] = {}
        for phase in CHECKPOINT_PHASES:
            member = _keys(
                phases[phase],
                {"raw", "identity"},
                f"{slot} {phase} checkpoint member",
            )
            raw = member["raw"]
            if type(raw) is not bytes:
                raise GateError(f"{slot} {phase}: checkpoint bytes are absent")
            checkpoint, identity = _checkpoint(
                raw=raw,
                identity=member["identity"],
                root=root,
                selection=selection,
                slot=slot,
                phase=phase,
                attempt_dir=attempt,
                campaign_root_raw=campaign_root_raw,
                campaign_root_identity=campaign_root_identity,
                selection_raw=selection_raw,
                selection_identity=selection_identity,
                driver=namespaces["gate1_campaign_driver_v4"],
            )
            transcript = _mapping(
                checkpoint.get("capture_transcript"),
                f"{slot} {phase} manager capture transcript",
            )
            rounds = transcript.get("rounds")
            if not isinstance(rounds, list) or len(rounds) != 2:
                raise GateError(f"{slot} {phase}: manager transcript round set drifted")
            first_round = _mapping(
                rounds[0],
                f"{slot} {phase} first manager transcript round",
            )
            last_round = _mapping(
                rounds[-1],
                f"{slot} {phase} last manager transcript round",
            )
            if (
                first_round.get("observation_started_monotonic_ns") <= previous_ns
                or last_round.get("observation_finished_monotonic_ns") >= checkpoint["captured_monotonic_ns"]
                or checkpoint["captured_monotonic_ns"] <= previous_ns
            ):
                raise GateError(f"{slot}: checkpoint phase timeline is not increasing")
            previous_ns = checkpoint["captured_monotonic_ns"]
            if identity["path"] in checkpoint_paths:
                raise GateError("manager checkpoint identity path was reused")
            checkpoint_paths.add(identity["path"])
            checkpoint_records[phase] = checkpoint
            checkpoint_identities[slot][phase] = identity
        checkpoint_records_by_slot[slot] = checkpoint_records
        _, launch_identity = _launch_replay(
            slot=slot,
            member=_mapping(
                launch_evidence[slot],
                f"{slot} systemd-run launch evidence",
            ),
            root_identity=campaign_root_identity,
            selection_identity=selection_identity,
            selection=selection,
            checkpoints=checkpoint_records,
            orchestrator=namespaces["gate1_unit_orchestrator_v4"],
            authority_namespace=authority,
        )
        if launch_identity["path"] in launch_paths:
            raise GateError("systemd-run launch evidence path was reused")
        launch_paths.add(launch_identity["path"])
        launch_identities[slot] = launch_identity
        (
            detached_resource,
            replay_identity,
            payload_result,
            payload_identity_set,
        ) = _resource_replay(
            slot=slot,
            member=_mapping(resource_replays[slot], f"{slot} resource replay"),
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            selection=selection,
            verifier_identity=_identity(
                selected_tools["resource_verifier_v4"],
                "selected resource verifier",
            ),
            verifier=namespaces["resource_verifier_v4"],
            expected_forced_profile=expected_forced_profile,
        )
        _checkpoint_lifecycle_join(
            slot=slot,
            checkpoints=checkpoint_records,
            detached=detached_resource,
        )
        if replay_identity["path"] in replay_paths:
            raise GateError("detached resource replay path was reused")
        if not Path(replay_identity["path"]).is_relative_to(attempt):
            raise GateError(f"{slot}: detached replay escaped its attempt")
        replay_paths.add(replay_identity["path"])
        replay_identities[slot] = replay_identity
        payload_identities[slot] = payload_identity_set
        if slot.startswith("forced-"):
            forced_payload_results[slot] = payload_result

    admission, admission_identity = _gate_admission_checkpoint(
        member=gate_admission_epoch,
        root=root,
        selection=selection,
        campaign_root_raw=campaign_root_raw,
        campaign_root_identity=campaign_root_identity,
        selection_raw=selection_raw,
        selection_identity=selection_identity,
        driver=namespaces["gate1_campaign_driver_v4"],
    )
    if not same_epoch(admission.get("manager_epoch"), root["manager_epoch"]):
        raise GateError("gate-admission manager/boot epoch drifted")
    admission_transcript = _mapping(
        admission.get("capture_transcript"),
        "gate-admission manager transcript",
    )
    admission_rounds = admission_transcript.get("rounds")
    if not isinstance(admission_rounds, list) or len(admission_rounds) != 2:
        raise GateError("gate-admission manager transcript round set drifted")
    admission_first = _mapping(
        admission_rounds[0],
        "gate-admission first manager transcript round",
    )
    latest_unit_ns = max(
        checkpoint_records_by_slot[slot]["detached-replay"]["captured_monotonic_ns"] for slot in GATE_SLOTS
    )
    if (
        admission_first.get("observation_started_monotonic_ns") <= latest_unit_ns
        or admission.get("captured_monotonic_ns") <= latest_unit_ns
    ):
        raise GateError("gate-admission manager observation did not follow all unit replays")

    arithmetic, positive_identities = _arithmetic_replay(
        positive_control,
        root=root,
        selection=selection,
        checker=namespaces["independent_arithmetic_v4"],
    )
    arithmetic_common_id = _strict_sha256(
        arithmetic.get("common_prestate_id"),
        "replayed arithmetic common_prestate_id",
    )
    for slot in ("forced-control", "forced-treatment"):
        delegated = _mapping(
            forced_payload_results[slot].get("delegated_result"),
            f"{slot} delegated result",
        )
        if delegated.get("common_prestate_id") != arithmetic_common_id:
            raise GateError(f"{slot}: delegated common_prestate_id differs from arithmetic")
    treatment_resource = _mapping(
        resource_replays["forced-treatment"],
        "forced-treatment resource replay",
    )
    treatment_evidence = _mapping(
        treatment_resource.get("evidence"),
        "forced-treatment resource evidence",
    )
    treatment_inner_member = _keys(
        treatment_evidence.get("inner"),
        {"raw", "identity"},
        "forced-treatment inner lifecycle member",
    )
    treatment_inner_raw = treatment_inner_member["raw"]
    if type(treatment_inner_raw) is not bytes:
        raise GateError("forced-treatment inner lifecycle bytes are absent")
    treatment_inner = _bound_json(
        treatment_inner_raw,
        treatment_inner_member["identity"],
        "forced-treatment inner lifecycle",
        newline=True,
    )
    payload_pid = treatment_inner.get("payload_pid")
    epoch_instance_id = arithmetic["selected"].get("epoch_instance_id")
    if (
        type(payload_pid) is not int
        or payload_pid <= 0
        or type(epoch_instance_id) is not str
        or not epoch_instance_id.startswith(f"epoch-{payload_pid}-")
    ):
        raise GateError("formal GENERATED epoch instance does not join the forced-treatment payload")
    result = {
        "schema_version": GATE_SCHEMA,
        "status": GATE_STATUS,
        "verdict": GATE_VERDICT,
        "created_at_utc": created_at_utc,
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "repository_head": root["repository_head"],
        "campaign_root_identity": dict(campaign_root_identity),
        "gate1_selection_identity": dict(selection_identity),
        "manager_epoch": dict(admission["manager_epoch"]),
        "manager_epoch_digest": _epoch_digest(admission["manager_epoch"]),
        "gate_admission_epoch_identity": dict(admission_identity),
        "tool_identities": {
            role: dict(_identity(selected_tools[role], f"selected tool {role}")) for role in REPLAY_TOOL_ROLES
        },
        "manager_checkpoint_identities": checkpoint_identities,
        "systemd_run_launch_identities": launch_identities,
        "detached_replay_identities": replay_identities,
        "payload_evidence_identities": payload_identities,
        "forced_payload_profile": expected_forced_profile,
        "positive_control": {
            **{name: dict(identity) for name, identity in positive_identities.items()},
            "common_prestate_id": arithmetic["common_prestate_id"],
            "selected": arithmetic["selected"],
            "control": arithmetic["control"],
            "treatment": arithmetic["treatment"],
            "forced_treatment_payload_pid": payload_pid,
            "epoch_instance_payload_joined": True,
        },
        "mechanism_credible": True,
        "continuation_eligible": True,
        "continuation_authorized": False,
        "campaign_closed": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
        "prospective_ab16_slots_absent": True,
        "claim_boundary": {
            "established": [
                "the four Gate 1 lifecycle/resource replays passed",
                "the forced typed mechanism applied one concrete violated inequality",
                "that concrete inequality excluded the same frozen incumbent",
            ],
            "not_established": [
                "organic cut activation",
                "single-family or bundle runtime usefulness",
                "cut-family global soundness",
                "SAT or UNSAT",
                "witness feasibility",
                "production CERTIFIED",
            ],
        },
    }
    return result


def _reject_symlink_components(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        if stat.S_ISLNK(metadata.st_mode):
            raise GateError(f"symlink path component rejected: {current}")
    return absolute


def snapshot_regular(
    path: Path,
    *,
    expected_identity: Mapping[str, object] | None = None,
) -> tuple[bytes, dict[str, object]]:
    """Read identity and payload from one O_NOFOLLOW fd with fstat bracketing."""

    absolute = _reject_symlink_components(path)
    if not hasattr(os, "O_NOFOLLOW"):
        raise GateError("O_NOFOLLOW is required")
    fd = os.open(absolute, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise GateError(f"not a regular file: {absolute}")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(1 << 20, MAX_JSON_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_JSON_BYTES:
                raise GateError(f"file exceeds snapshot limit: {absolute}")
        after = os.fstat(fd)
    finally:
        os.close(fd)

    def signature(value: os.stat_result) -> tuple[int, ...]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )

    if signature(before) != signature(after):
        raise GateError(f"file changed during same-fd snapshot: {absolute}")
    raw = b"".join(chunks)
    identity = {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if expected_identity is not None and identity != dict(
        _identity(expected_identity, f"expected identity for {absolute}")
    ):
        raise GateError(f"detached identity drifted: {absolute}")
    return raw, identity


def write_exclusive(path: Path, value: Mapping[str, object]) -> dict[str, object]:
    """Publish one canonical result without following links or overwriting."""

    absolute = _reject_symlink_components(path)
    if absolute.exists() or absolute.is_symlink():
        raise GateError(f"refusing to overwrite: {absolute}")
    if not absolute.parent.is_dir():
        raise GateError(f"output parent is absent: {absolute.parent}")
    raw = canonical_json(value) + b"\n"
    if not hasattr(os, "O_NOFOLLOW"):
        raise GateError("O_NOFOLLOW is required")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(absolute, flags, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short Gate 1 result write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    return {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    raise SystemExit(
        "positive_control_gate_v4 is library-driven; the campaign driver must "
        "same-FD snapshot all selected inputs before calling evaluate_gate"
    )


if __name__ == "__main__":
    raise SystemExit(main())
