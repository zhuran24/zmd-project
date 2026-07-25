#!/usr/bin/env python3
"""Ordinary-user lifecycle epoch checkpoints for CUTS_GATE1_V4.

This module does not launch systemd units or solvers.  Its only production
operation is to capture the cuts-local user-manager/boot epoch through the
authority-selected read-only attestor and write one pre-registered lifecycle
checkpoint with O_EXCL/O_NOFOLLOW semantics.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sys
import time
from typing import Any

import campaign_authority_v4 as authority


CHECKPOINT_SCHEMA = "noncert-cuts-gate1-v4-manager-epoch-checkpoint-v2"
CHECKPOINT_PHASES = (
    "prelaunch",
    "preterminal",
    "terminal",
    "cleanup",
    "detached-replay",
)
UNIT_SLOTS = authority.GATE1_SLOTS
GATE_ADMISSION_SLOT = "gate-admission"
GATE_ADMISSION_PHASE = "gate-admission"
ALL_CHECKPOINT_SLOTS = (*UNIT_SLOTS, GATE_ADMISSION_SLOT)
ALL_CHECKPOINT_PHASES = (*CHECKPOINT_PHASES, GATE_ADMISSION_PHASE)
SELECTED_CAPTURE_TOOL_ROLES = (
    "attestor_python",
    "busctl",
    "campaign_authority_v4",
    "gate1_campaign_driver_v4",
    "manager_attestor_v4",
    "sudo",
)


class DriverError(RuntimeError):
    """A selected authority or live manager epoch failed closed."""


def _is_gate_admission(unit_slot: str, phase: str) -> bool:
    return unit_slot == GATE_ADMISSION_SLOT and phase == GATE_ADMISSION_PHASE


def _require_selected_slot_phase(unit_slot: str, phase: str) -> None:
    if _is_gate_admission(unit_slot, phase):
        return
    if unit_slot not in UNIT_SLOTS or phase not in CHECKPOINT_PHASES:
        raise DriverError("manager epoch slot/phase combination is not selected")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch_digest(epoch: object) -> str:
    return hashlib.sha256(authority.canonical_json(epoch)).hexdigest()


def _detached_projection(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "path": value["path"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
    }


def _selected_capture_tools(selection: Mapping[str, Any]) -> dict[str, object]:
    tools = selection["tools"]
    selected = {
        role: dict(
            authority.validate_detached_identity(
                tools[role],
                f"selected capture tool {role}",
            )
        )
        for role in SELECTED_CAPTURE_TOOL_ROLES
    }
    epoch = authority.validate_manager_epoch(selection["manager_epoch"])
    expected = {
        "attestor_python": _detached_projection(epoch["attestation_toolchain"]["python"]),
        "busctl": _detached_projection(epoch["observation_toolchain"]["busctl"]),
        "manager_attestor_v4": _detached_projection(epoch["attestation_toolchain"]["attestor"]),
        "sudo": _detached_projection(epoch["attestation_toolchain"]["sudo"]),
    }
    mismatched = sorted(role for role, identity in expected.items() if selected[role] != identity)
    if mismatched:
        raise DriverError("selected capture tools do not join the manager epoch: " + ",".join(mismatched))
    return selected


def _transcript_binding(
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    unit_slot: str,
    phase: str,
    selected_tool_identities: Mapping[str, object],
    transcript: Mapping[str, object],
) -> str:
    return hashlib.sha256(
        authority.canonical_json(
            {
                "campaign_id": root["campaign_id"],
                "capture_transcript": transcript,
                "phase": phase,
                "run_nonce": root["run_nonce"],
                "selected_tool_identities": selected_tool_identities,
                "selection_id": selection["selection_id"],
                "unit_slot": unit_slot,
            }
        )
    ).hexdigest()


def _load_bound_authorities(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    authority.Snapshot,
    authority.Snapshot,
]:
    """Read both authorities through stable same-FD snapshots and join them."""

    checked_root_identity = authority.validate_detached_identity(
        campaign_root_identity,
        "campaign root identity",
    )
    checked_selection_identity = authority.validate_detached_identity(
        selection_identity,
        "Gate 1 selection identity",
    )
    root_snapshot = authority.snapshot_regular(checked_root_identity["path"])
    if authority.detached_identity(root_snapshot) != checked_root_identity:
        raise DriverError("campaign root detached identity drifted")
    root_value = authority.strict_loads(root_snapshot.data, "campaign root")
    if authority.canonical_json(root_value) != root_snapshot.data:
        raise DriverError("campaign root JSON is not canonical")
    root = authority.validate_campaign_root(
        root_value,
        campaign_dir=Path(str(checked_root_identity["path"])).parent,
    )

    selection_snapshot = authority.snapshot_regular(checked_selection_identity["path"])
    if authority.detached_identity(selection_snapshot) != checked_selection_identity:
        raise DriverError("Gate 1 selection detached identity drifted")
    selection = authority.load_gate1_selection_bytes(
        selection_snapshot.data,
        checked_selection_identity,
    )
    authority.validate_gate1_selection(selection, root=root)
    if selection["campaign_root_identity"] != checked_root_identity:
        raise DriverError("Gate 1 selection does not bind the supplied campaign root")
    return root, selection, root_snapshot, selection_snapshot


def _snapshot_signature(snapshot: authority.Snapshot) -> tuple[int, ...]:
    metadata = snapshot.stat_result
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _require_unchanged_authorities(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    root_snapshot: authority.Snapshot,
    selection_snapshot: authority.Snapshot,
) -> None:
    """Re-read both bound authorities after live capture and require exact bytes."""

    for label, identity, baseline in (
        ("campaign root", campaign_root_identity, root_snapshot),
        ("Gate 1 selection", selection_identity, selection_snapshot),
    ):
        snapshot = authority.snapshot_regular(identity["path"])
        if (
            authority.detached_identity(snapshot) != identity
            or snapshot.data != baseline.data
            or _snapshot_signature(snapshot) != _snapshot_signature(baseline)
        ):
            raise DriverError(f"{label} drifted during manager epoch capture")


def _expected_checkpoint_path(
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    unit_slot: str,
    phase: str,
) -> Path:
    _require_selected_slot_phase(unit_slot, phase)
    if _is_gate_admission(unit_slot, phase):
        gate = root["stage_topology"]["gate1_v4"]
        root_path = Path(str(gate["gate_admission_epoch_path"]))
        expected_path = Path(str(gate["selection_path"])).parent / "authority" / "manager-epoch-gate-admission.json"
        if (
            gate["gate_admission_epoch_schema"] != CHECKPOINT_SCHEMA
            or not root_path.is_absolute()
            or root_path != expected_path
        ):
            raise DriverError("gate-admission manager epoch path/schema is not exactly pre-registered")
        return root_path
    root_path = Path(str(root["stage_topology"]["gate1_v4"]["units"][unit_slot]["epoch_checkpoint_paths"][phase]))
    selection_path = Path(str(selection["units"][unit_slot]["epoch_checkpoint_paths"][phase]))
    if (
        not root_path.is_absolute()
        or root_path != selection_path
        or root_path
        != Path(str(selection["units"][unit_slot]["attempt_dir"])) / "authority" / f"manager-epoch-{phase}.json"
    ):
        raise DriverError("manager epoch checkpoint path is not exactly pre-registered")
    return root_path


def _checkpoint_unit_name(
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    unit_slot: str,
    phase: str,
) -> str:
    _require_selected_slot_phase(unit_slot, phase)
    if _is_gate_admission(unit_slot, phase):
        return f"{root['unit_namespace']}-gate-admission.authority"
    return str(selection["units"][unit_slot]["unit_name"])


def _gate_admission_predecessor_monotonic_ns(
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> int:
    """Replay all unit endpoints and return their latest detached-replay clock."""

    clocks: list[int] = []
    for slot in UNIT_SLOTS:
        predecessor_phase = "detached-replay"
        predecessor_path = Path(str(selection["units"][slot]["epoch_checkpoint_paths"][predecessor_phase]))
        try:
            snapshot = authority.snapshot_regular(predecessor_path)
        except authority.AuthorityError as exc:
            raise DriverError("gate-admission checkpoint requires every unit detached replay") from exc
        value = authority.strict_loads(
            snapshot.data,
            f"{slot} {predecessor_phase} manager epoch checkpoint",
        )
        if authority.canonical_json(value) != snapshot.data:
            raise DriverError("gate-admission predecessor manager checkpoint is not canonical")
        checked = _validate_checkpoint_value(
            value,
            root=root,
            selection=selection,
            unit_slot=slot,
            phase=predecessor_phase,
        )
        clocks.append(int(checked["captured_monotonic_ns"]))
    return max(clocks)


def _validate_predecessor(
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    unit_slot: str,
    phase: str,
) -> int:
    """Require the selected phase order and return the previous monotonic clock."""

    _require_selected_slot_phase(unit_slot, phase)
    if _is_gate_admission(unit_slot, phase):
        output_path = _expected_checkpoint_path(
            root=root,
            selection=selection,
            unit_slot=unit_slot,
            phase=phase,
        )
        if os.path.lexists(output_path):
            raise DriverError("gate-admission manager epoch checkpoint already exists")
        gate = root["stage_topology"]["gate1_v4"]
        if any(os.path.lexists(gate[field]) for field in ("gate_path", "continuation_path")):
            raise DriverError("gate-admission manager epoch must precede gate publication")
        return _gate_admission_predecessor_monotonic_ns(
            root=root,
            selection=selection,
        )
    phase_index = CHECKPOINT_PHASES.index(phase)
    checkpoints = selection["units"][unit_slot]["epoch_checkpoint_paths"]
    later = CHECKPOINT_PHASES[phase_index + 1 :]
    if any(os.path.lexists(checkpoints[item]) for item in later):
        raise DriverError("a later manager epoch checkpoint already exists")
    if phase_index == 0:
        if any(os.path.lexists(checkpoints[item]) for item in CHECKPOINT_PHASES):
            raise DriverError("prelaunch checkpoint is not the first selected phase")
        return 0
    predecessor_phase = CHECKPOINT_PHASES[phase_index - 1]
    predecessor_path = Path(str(checkpoints[predecessor_phase]))
    try:
        snapshot = authority.snapshot_regular(predecessor_path)
    except authority.AuthorityError as exc:
        raise DriverError("predecessor manager epoch checkpoint is absent or unreadable") from exc
    value = authority.strict_loads(
        snapshot.data,
        f"{unit_slot} {predecessor_phase} manager epoch checkpoint",
    )
    if authority.canonical_json(value) != snapshot.data:
        raise DriverError("predecessor manager epoch checkpoint is not canonical")
    checked = _validate_checkpoint_value(
        value,
        root=root,
        selection=selection,
        unit_slot=unit_slot,
        phase=predecessor_phase,
    )
    return int(checked["captured_monotonic_ns"])


def _validate_checkpoint_value(
    value: object,
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    unit_slot: str,
    phase: str,
) -> Mapping[str, Any]:
    _require_selected_slot_phase(unit_slot, phase)
    if not isinstance(value, Mapping) or set(value) != {
        "campaign_id",
        "capture_transcript",
        "captured_at_utc",
        "captured_monotonic_ns",
        "manager_epoch",
        "manager_epoch_digest",
        "phase",
        "run_nonce",
        "schema_version",
        "selected_tool_identities",
        "selection_id",
        "transcript_binding_sha256",
        "unit_name",
        "unit_slot",
    }:
        raise DriverError("manager epoch checkpoint schema drifted")
    selected_tools = _selected_capture_tools(selection)
    transcript = authority.validate_manager_epoch_capture_transcript(
        value["capture_transcript"],
        expected_epoch=root["manager_epoch"],
    )
    transcript_finished_ns = transcript["rounds"][-1]["observation_finished_monotonic_ns"]
    expected = {
        "schema_version": CHECKPOINT_SCHEMA,
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "selection_id": selection["selection_id"],
        "unit_slot": unit_slot,
        "unit_name": _checkpoint_unit_name(
            root=root,
            selection=selection,
            unit_slot=unit_slot,
            phase=phase,
        ),
        "phase": phase,
        "manager_epoch_digest": _epoch_digest(root["manager_epoch"]),
        "selected_tool_identities": selected_tools,
    }
    expected_binding = _transcript_binding(
        root=root,
        selection=selection,
        unit_slot=unit_slot,
        phase=phase,
        selected_tool_identities=selected_tools,
        transcript=transcript,
    )
    captured_monotonic_ns = value.get("captured_monotonic_ns")
    if (
        type(captured_monotonic_ns) is not int
        or captured_monotonic_ns <= 0
        or captured_monotonic_ns <= transcript_finished_ns
    ):
        raise DriverError("manager epoch checkpoint timeline drifted")
    if _is_gate_admission(unit_slot, phase):
        predecessor_ns = _gate_admission_predecessor_monotonic_ns(
            root=root,
            selection=selection,
        )
        transcript_started_ns = transcript["rounds"][0]["observation_started_monotonic_ns"]
        if transcript_started_ns <= predecessor_ns:
            raise DriverError("gate-admission manager transcript did not follow all unit replays")
    if (
        any(value.get(key) != expected_value for key, expected_value in expected.items())
        or value.get("transcript_binding_sha256") != expected_binding
        or not authority.same_manager_epoch(
            value.get("manager_epoch"),
            root["manager_epoch"],
        )
        or type(value.get("captured_at_utc")) is not str
    ):
        raise DriverError("manager epoch checkpoint semantics drifted")
    try:
        parsed_time = datetime.fromisoformat(str(value["captured_at_utc"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DriverError("manager epoch checkpoint timestamp is invalid") from exc
    if parsed_time.tzinfo is None:
        raise DriverError("manager epoch checkpoint timestamp lacks a timezone")
    epoch = authority.validate_manager_epoch(root["manager_epoch"])
    for transcript_round in transcript["rounds"]:
        if (
            transcript_round["observation_toolchain"] != epoch["observation_toolchain"]
            or transcript_round["attestation_toolchain"] != epoch["attestation_toolchain"]
            or transcript_round["attestor_ast_audit"] != epoch["attestor_ast_audit"]
        ):
            raise DriverError("manager transcript tool identities drifted")
    return value


def replay_lifecycle_epoch_checkpoint(
    *,
    checkpoint_raw: bytes,
    checkpoint_identity: Mapping[str, object],
    campaign_root_raw: bytes,
    campaign_root_identity: Mapping[str, object],
    selection_raw: bytes,
    selection_identity: Mapping[str, object],
    unit_slot: str,
    phase: str,
) -> Mapping[str, Any]:
    """Independently replay one exact checkpoint and its two live transcripts."""

    authority.verify_bytes_identity(campaign_root_raw, campaign_root_identity)
    root_value = authority.strict_loads(campaign_root_raw, "campaign root")
    if authority.canonical_json(root_value) != campaign_root_raw:
        raise DriverError("campaign root JSON is not canonical")
    root = authority.validate_campaign_root(
        root_value,
        campaign_dir=Path(str(campaign_root_identity["path"])).parent,
    )
    selection = authority.load_gate1_selection_bytes(
        selection_raw,
        selection_identity,
    )
    authority.validate_gate1_selection(selection, root=root)
    if selection["campaign_root_identity"] != dict(campaign_root_identity):
        raise DriverError("Gate 1 selection does not bind the campaign root")
    authority.verify_bytes_identity(checkpoint_raw, checkpoint_identity)
    value = authority.strict_loads(checkpoint_raw, f"{unit_slot} {phase} checkpoint")
    if authority.canonical_json(value) != checkpoint_raw:
        raise DriverError("manager epoch checkpoint JSON is not canonical")
    expected_path = _expected_checkpoint_path(
        root=root,
        selection=selection,
        unit_slot=unit_slot,
        phase=phase,
    )
    detached = authority.validate_detached_identity(
        checkpoint_identity,
        f"{unit_slot} {phase} checkpoint identity",
    )
    if detached["path"] != str(expected_path):
        raise DriverError("manager epoch checkpoint path is not pre-registered")
    return _validate_checkpoint_value(
        value,
        root=root,
        selection=selection,
        unit_slot=unit_slot,
        phase=phase,
    )


def _capture_lifecycle_epoch_checkpoint_with(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    unit_slot: str,
    phase: str,
    attestor_path: Path,
    busctl_path: Path,
    python_path: Path,
    sudo_path: Path,
    capture_manager_epoch_transcript: Callable[..., Mapping[str, object]] = (
        authority.capture_manager_epoch_with_transcript
    ),
    now_utc: Callable[[], str] = _utc_now,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    before_write: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Fixture-capable implementation behind the selected production surface."""

    root, selection, root_snapshot, selection_snapshot = _load_bound_authorities(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
    )
    if not authority.same_manager_epoch(root["manager_epoch"], selection["manager_epoch"]):
        raise DriverError("campaign root and selection manager epochs differ")
    output_path = _expected_checkpoint_path(
        root=root,
        selection=selection,
        unit_slot=unit_slot,
        phase=phase,
    )
    previous_monotonic_ns = _validate_predecessor(
        root=root,
        selection=selection,
        unit_slot=unit_slot,
        phase=phase,
    )
    if os.path.lexists(output_path):
        raise DriverError("selected manager epoch checkpoint already exists")
    if not output_path.parent.is_dir():
        if os.path.lexists(output_path.parent):
            raise DriverError("selected manager epoch checkpoint parent is not a directory")
        if not _is_gate_admission(unit_slot, phase):
            raise DriverError("selected manager epoch checkpoint parent is absent")
        authority.mkdir_exclusive(output_path.parent)

    captured = dict(
        capture_manager_epoch_transcript(
            attestor_path=attestor_path,
            busctl_path=busctl_path,
            python_path=python_path,
            sudo_path=sudo_path,
        )
    )
    if set(captured) != {"manager_epoch", "transcript"}:
        raise DriverError("live manager capture result schema drifted")
    observed = dict(captured["manager_epoch"])
    transcript = authority.validate_manager_epoch_capture_transcript(
        captured["transcript"],
        expected_epoch=observed,
    )
    if transcript["rounds"][0]["observation_started_monotonic_ns"] <= previous_monotonic_ns:
        raise DriverError("live manager transcript did not follow its predecessor")
    authority.validate_manager_epoch(observed)
    if not authority.same_manager_epoch(observed, root["manager_epoch"]) or not authority.same_manager_epoch(
        observed, selection["manager_epoch"]
    ):
        raise DriverError("live manager/boot epoch does not join campaign authority")
    captured_monotonic_ns = monotonic_ns()
    if type(captured_monotonic_ns) is not int or captured_monotonic_ns <= previous_monotonic_ns:
        raise DriverError("manager epoch checkpoint monotonic clock did not advance")
    captured_at_utc = now_utc()
    if type(captured_at_utc) is not str:
        raise DriverError("manager epoch checkpoint timestamp is invalid")
    try:
        parsed_time = datetime.fromisoformat(captured_at_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DriverError("manager epoch checkpoint timestamp is invalid") from exc
    if parsed_time.tzinfo is None:
        raise DriverError("manager epoch checkpoint timestamp lacks a timezone")

    _require_unchanged_authorities(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        root_snapshot=root_snapshot,
        selection_snapshot=selection_snapshot,
    )
    if before_write is not None:
        before_write()
    _require_unchanged_authorities(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        root_snapshot=root_snapshot,
        selection_snapshot=selection_snapshot,
    )
    selected_tool_identities = _selected_capture_tools(selection)
    checkpoint = {
        "schema_version": CHECKPOINT_SCHEMA,
        "captured_at_utc": captured_at_utc,
        "captured_monotonic_ns": captured_monotonic_ns,
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "selection_id": selection["selection_id"],
        "unit_slot": unit_slot,
        "unit_name": _checkpoint_unit_name(
            root=root,
            selection=selection,
            unit_slot=unit_slot,
            phase=phase,
        ),
        "phase": phase,
        "manager_epoch": observed,
        "manager_epoch_digest": _epoch_digest(root["manager_epoch"]),
        "selected_tool_identities": selected_tool_identities,
        "capture_transcript": transcript,
        "transcript_binding_sha256": _transcript_binding(
            root=root,
            selection=selection,
            unit_slot=unit_slot,
            phase=phase,
            selected_tool_identities=selected_tool_identities,
            transcript=transcript,
        ),
    }
    _validate_checkpoint_value(
        checkpoint,
        root=root,
        selection=selection,
        unit_slot=unit_slot,
        phase=phase,
    )
    raw = authority.canonical_json(checkpoint)
    identity = authority.write_exclusive(output_path, raw)
    replay = authority.snapshot_regular(output_path)
    if replay.data != raw or authority.detached_identity(replay) != identity:
        raise DriverError("manager epoch checkpoint did not replay after O_EXCL write")
    return identity


def capture_lifecycle_epoch_checkpoint(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    unit_slot: str,
    phase: str,
    attestor_path: Path,
    busctl_path: Path,
    python_path: Path,
    sudo_path: Path,
) -> dict[str, object]:
    """Capture one live selected lifecycle epoch with no injectable observer."""

    return _capture_lifecycle_epoch_checkpoint_with(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        unit_slot=unit_slot,
        phase=phase,
        attestor_path=attestor_path,
        busctl_path=busctl_path,
        python_path=python_path,
        sudo_path=sudo_path,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--campaign-root-size", required=True, type=int)
    parser.add_argument("--campaign-root-sha256", required=True)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--selection-size", required=True, type=int)
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--unit-slot", required=True, choices=ALL_CHECKPOINT_SLOTS)
    parser.add_argument("--phase", required=True, choices=ALL_CHECKPOINT_PHASES)
    parser.add_argument("--attestor", required=True, type=Path)
    parser.add_argument("--busctl", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--sudo", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    capture_lifecycle_epoch_checkpoint(
        campaign_root_identity={
            "path": str(arguments.campaign_root.absolute()),
            "size_bytes": arguments.campaign_root_size,
            "sha256": arguments.campaign_root_sha256,
        },
        selection_identity={
            "path": str(arguments.selection.absolute()),
            "size_bytes": arguments.selection_size,
            "sha256": arguments.selection_sha256,
        },
        unit_slot=arguments.unit_slot,
        phase=arguments.phase,
        attestor_path=arguments.attestor,
        busctl_path=arguments.busctl,
        python_path=arguments.python,
        sudo_path=arguments.sudo,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DriverError, authority.AuthorityError) as exc:
        print(f"CUTS_GATE1_V4_EPOCH_CHECKPOINT_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
