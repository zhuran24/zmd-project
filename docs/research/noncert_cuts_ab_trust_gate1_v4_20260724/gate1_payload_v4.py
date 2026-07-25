#!/usr/bin/env python3
"""Selected payload entry point for the CUTS_GATE1_V4 child suite.

The two synthetic payloads publish their selected result and seal with
``O_EXCL`` before returning their pre-registered status.  The two forced
positive-control payloads may delegate to exactly one authority-selected
Python tool.  Prospective/organic arms are deliberately outside this entry
point.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import types
from typing import Any

import campaign_authority_v4 as authority
import resource_lifecycle_v4 as lifecycle


RESULT_SCHEMA = "noncert-cuts-gate1-v4-payload-result-v1"
SEAL_SCHEMA = "noncert-cuts-gate1-v4-payload-seal-v1"
SYNTHETIC_SLOTS = ("q-success", "q-postseal-fail")
FORCED_SLOTS = ("forced-control", "forced-treatment")
GATE1_SLOTS = (*SYNTHETIC_SLOTS, *FORCED_SLOTS)
EXPECTED_RETURNCODE = {
    "q-success": 0,
    "q-postseal-fail": 7,
    "forced-control": 0,
    "forced-treatment": 0,
}
DEFAULT_DELEGATE_ROLE = "positive_control_formal_v4"
DEFAULT_DELEGATE_ENTRYPOINT = "run_forced_payload_v4"


class PayloadError(RuntimeError):
    """A payload authority, delegation, or publication check failed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _exact_mapping(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise PayloadError(f"{label} must be an exact mapping")
    return value


def _json_value(value: object, label: str) -> object:
    """Accept only deterministic JSON values and reject floats/subclasses."""

    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is list:
        return [_json_value(item, f"{label}[]") for item in value]
    if type(value) is dict:
        result: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str or not key or key in result:
                raise PayloadError(f"{label} has an invalid key")
            result[key] = _json_value(item, f"{label}.{key}")
        return result
    raise PayloadError(f"{label} contains a non-canonical JSON value")


def _identity_equal(left: object, right: object) -> bool:
    try:
        return dict(authority.validate_detached_identity(left, "left identity")) == dict(
            authority.validate_detached_identity(right, "right identity")
        )
    except authority.AuthorityError:
        return False


def _load_bound_authorities(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> tuple[Mapping[str, Any], lifecycle.DetachedDocument]:
    root_identity = authority.validate_detached_identity(
        campaign_root_identity,
        "payload campaign root identity",
    )
    selection_identity_checked = authority.validate_detached_identity(
        selection_identity,
        "payload Gate 1 selection identity",
    )
    root_snapshot = authority.replay_detached_identity(
        root_identity,
        "payload campaign root",
    )
    root_value = authority.strict_loads(root_snapshot.data, "payload campaign root")
    if authority.canonical_json(root_value) != root_snapshot.data:
        raise PayloadError("payload campaign root is not canonical")
    root = authority.validate_campaign_root(
        root_value,
        campaign_dir=Path(str(root_identity["path"])).parent,
    )
    selection_snapshot = authority.replay_detached_identity(
        selection_identity_checked,
        "payload Gate 1 selection",
    )
    selection = lifecycle.load_gate1_selection_bytes(
        selection_snapshot.data,
        selection_identity_checked,
    )
    authority.validate_gate1_selection(selection.value, root=root)
    if selection.value["campaign_root_identity"] != dict(root_identity):
        raise PayloadError("payload selection does not bind the campaign root")
    return root, selection


def _replay_selected_tool(
    selection: Mapping[str, Any],
    role: str,
) -> tuple[bytes, dict[str, object]]:
    tools = _exact_mapping(selection.get("tools"), "selected tools")
    if role not in tools:
        raise PayloadError(f"selected tool role is absent: {role}")
    expected = authority.validate_detached_identity(
        tools[role],
        f"selected tool {role}",
    )
    snapshot = authority.replay_detached_identity(expected, f"selected tool {role}")
    observed = authority.detached_identity(snapshot)
    if observed != dict(expected):
        raise PayloadError(f"selected tool identity drifted: {role}")
    return snapshot.data, observed


def _selected_project_root(selection: Mapping[str, Any]) -> Path:
    inputs = _exact_mapping(selection.get("inputs"), "selected inputs")
    identity = authority.validate_detached_identity(
        inputs.get("project_lock"),
        "selected repository PROJECT_LOCK",
    )
    snapshot = authority.replay_detached_identity(
        identity,
        "selected repository PROJECT_LOCK",
    )
    path = Path(str(identity["path"]))
    if path.name != "PROJECT_LOCK.md" or snapshot.path != path or not path.parent.is_absolute():
        raise PayloadError("selected repository root binding drifted")
    return path.parent


def _load_delegate_from_selected_bytes(
    raw: bytes,
    identity: Mapping[str, object],
    entrypoint: str,
    *,
    support_raw: bytes,
    support_identity: Mapping[str, object],
    project_root: Path,
) -> Callable[..., Mapping[str, object]]:
    """Execute the verified formal builder and support bytes without path rereads."""

    if type(entrypoint) is not str or not entrypoint.isidentifier() or entrypoint.startswith("_"):
        raise PayloadError("forced delegate entrypoint is invalid")
    support_module = types.ModuleType(f"cuts_gate1_v4_selected_support_{str(support_identity['sha256'])[:16]}")
    support_module.__file__ = str(support_identity["path"])
    support_module.__package__ = None
    try:
        support_code = compile(
            support_raw,
            f"<selected:{support_identity['sha256']}>",
            "exec",
            dont_inherit=True,
        )
        exec(support_code, support_module.__dict__, support_module.__dict__)
    except Exception as exc:
        raise PayloadError("selected forced support failed to load") from exc
    namespace: dict[str, object] = {
        "__name__": "cuts_gate1_v4_selected_payload_delegate",
        "__file__": str(identity["path"]),
        "__package__": None,
        "_SUPPORT": support_module,
        "_SUPPORT_SELECTED_IDENTITY": dict(support_identity),
        "_PROJECT_ROOT": project_root,
    }
    try:
        code = compile(
            raw,
            f"<selected:{identity['sha256']}>",
            "exec",
            dont_inherit=True,
        )
        exec(code, namespace, namespace)
    except Exception as exc:
        raise PayloadError("selected forced delegate failed to load") from exc
    callback = namespace.get(entrypoint)
    if not callable(callback):
        raise PayloadError("selected forced delegate entrypoint is absent")
    return callback


def publish_selected_payload(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    unit_slot: str,
    delegate: Callable[..., Mapping[str, object]] | None = None,
    delegate_role: str = DEFAULT_DELEGATE_ROLE,
    now_utc: Callable[[], str] = _utc_now,
) -> int:
    """Publish one selected payload result and seal, returning its exit status."""

    if os.geteuid() != os.getuid() or os.geteuid() == 0:
        raise PayloadError("Gate 1 payload must run as the ordinary selected user")
    if unit_slot not in GATE1_SLOTS:
        raise PayloadError("organic or unknown arm is not a Gate 1 payload")
    root, selection_document = _load_bound_authorities(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
    )
    selection = selection_document.value
    unit = _exact_mapping(selection["units"][unit_slot], f"selected unit {unit_slot}")
    lifecycle_paths = lifecycle.lifecycle_paths(selection, unit_slot)
    result_path = lifecycle_paths["result"]
    seal_path = lifecycle_paths["payload_seal"]
    if result_path != Path(str(unit["result_path"])):
        raise PayloadError("selected result path drifted")
    if result_path.parent != Path(str(unit["attempt_dir"])) or seal_path.parent != Path(str(unit["raw_dir"])):
        raise PayloadError("selected payload path topology drifted")
    if not result_path.parent.is_dir() or not seal_path.parent.is_dir():
        raise PayloadError("selected payload output parents are absent")
    if os.path.lexists(result_path) or os.path.lexists(seal_path):
        raise PayloadError("selected payload result or seal already exists")

    payload_kind: str
    delegated_identity: dict[str, object] | None = None
    delegated_result: object = None
    if unit_slot in SYNTHETIC_SLOTS:
        if delegate is not None:
            raise PayloadError("synthetic payload cannot use a forced delegate")
        payload_kind = "synthetic-lifecycle"
    else:
        if delegate is None:
            raise PayloadError("forced payload requires the selected delegate")
        payload_kind = "forced-positive-control"
        _, delegated_identity = _replay_selected_tool(selection, delegate_role)
        delegated_result = _json_value(
            delegate(
                campaign_root=root,
                campaign_root_identity=dict(campaign_root_identity),
                selection=selection,
                selection_identity=dict(selection_identity),
                unit_slot=unit_slot,
                selected_tool_identity=dict(delegated_identity),
            ),
            "forced delegate result",
        )
        result_mapping = _exact_mapping(delegated_result, "forced delegate result")
        expected_arm = "control" if unit_slot == "forced-control" else "treatment"
        expected_count = 0 if expected_arm == "control" else 1
        campaign_name = Path(str(campaign_root_identity["path"])).parent.name
        if campaign_name.startswith("dev-drill-"):
            expected_profile = "disposable_drill"
        elif campaign_name.startswith("run-"):
            expected_profile = "formal_campaign"
        else:
            raise PayloadError("forced payload campaign directory has no selected profile")
        support_identity = selection["tools"].get("positive_control_v4")
        if (
            result_mapping.get("status") != "PASS"
            or result_mapping.get("arm") != expected_arm
            or result_mapping.get("profile") != expected_profile
            or result_mapping.get("generated") != expected_count
            or result_mapping.get("compiled") != expected_count
            or result_mapping.get("applied") != expected_count
            or result_mapping.get("support_tool_identity") != support_identity
            or result_mapping.get("post_solve_performed") is not False
            or result_mapping.get("organic_arm_launch_authorized") is not False
            or result_mapping.get("global_claim_authorized") is not False
        ):
            raise PayloadError("forced delegate result semantics failed closed")
        # Re-read after the callback so its selected bytes cannot drift unnoticed.
        _, replayed_identity = _replay_selected_tool(selection, delegate_role)
        if replayed_identity != delegated_identity:
            raise PayloadError("forced delegate bytes drifted during execution")
        _, replayed_support = _replay_selected_tool(
            selection,
            "positive_control_v4",
        )
        if replayed_support != support_identity:
            raise PayloadError("forced support bytes drifted during execution")

    created_at = now_utc()
    expected_returncode = EXPECTED_RETURNCODE[unit_slot]
    result = {
        "schema_version": RESULT_SCHEMA,
        "created_at_utc": created_at,
        "campaign_root_identity": dict(campaign_root_identity),
        "selection_identity": dict(selection_identity),
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "unit_slot": unit_slot,
        "unit_name": unit["unit_name"],
        "payload_kind": payload_kind,
        "expected_returncode": expected_returncode,
        "delegated_tool_role": delegate_role if delegated_identity is not None else None,
        "delegated_tool_identity": delegated_identity,
        "delegated_result": delegated_result,
        "sealed_before_exit": True,
        "mechanism_credible_authorized": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
    }
    result_identity = authority.write_exclusive(
        result_path,
        authority.canonical_json(result),
    )
    seal = {
        "schema_version": SEAL_SCHEMA,
        "created_at_utc": now_utc(),
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "unit_slot": unit_slot,
        "unit_name": unit["unit_name"],
        "result_identity": result_identity,
        "expected_returncode": expected_returncode,
        "delegated_tool_identity": delegated_identity,
        "payload_complete": True,
    }
    seal_identity = authority.write_exclusive(
        seal_path,
        authority.canonical_json(seal),
    )
    result_replay = authority.replay_detached_identity(
        result_identity,
        "payload result replay",
    )
    seal_replay = authority.replay_detached_identity(
        seal_identity,
        "payload seal replay",
    )
    if result_replay.data != authority.canonical_json(result) or seal_replay.data != authority.canonical_json(seal):
        raise PayloadError("payload result or seal failed immediate replay")
    return expected_returncode


def _identity_from_args(arguments: argparse.Namespace, prefix: str) -> dict[str, object]:
    path = getattr(arguments, prefix.replace("-", "_"))
    return {
        "path": str(path.absolute()),
        "size_bytes": getattr(arguments, f"{prefix.replace('-', '_')}_size"),
        "sha256": getattr(arguments, f"{prefix.replace('-', '_')}_sha256"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--campaign-root-size", required=True, type=int)
    parser.add_argument("--campaign-root-sha256", required=True)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--selection-size", required=True, type=int)
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--unit-slot", required=True, choices=GATE1_SLOTS)
    parser.add_argument("--delegate-role", default=DEFAULT_DELEGATE_ROLE)
    parser.add_argument("--delegate-entrypoint", default=DEFAULT_DELEGATE_ENTRYPOINT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root_identity = _identity_from_args(arguments, "campaign-root")
    selection_identity = _identity_from_args(arguments, "selection")
    delegate: Callable[..., Mapping[str, object]] | None = None
    if arguments.unit_slot in FORCED_SLOTS:
        _, selection = _load_bound_authorities(
            campaign_root_identity=root_identity,
            selection_identity=selection_identity,
        )
        raw, identity = _replay_selected_tool(selection.value, arguments.delegate_role)
        support_raw, support_identity = _replay_selected_tool(
            selection.value,
            "positive_control_v4",
        )
        project_root = _selected_project_root(selection.value)
        project_root_text = str(project_root)
        if project_root_text not in sys.path:
            sys.path.insert(0, project_root_text)
        delegate = _load_delegate_from_selected_bytes(
            raw,
            identity,
            arguments.delegate_entrypoint,
            support_raw=support_raw,
            support_identity=support_identity,
            project_root=project_root,
        )
    return publish_selected_payload(
        campaign_root_identity=root_identity,
        selection_identity=selection_identity,
        unit_slot=arguments.unit_slot,
        delegate=delegate,
        delegate_role=arguments.delegate_role,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PayloadError, authority.AuthorityError, lifecycle.LifecycleError) as exc:
        print(f"CUTS_GATE1_V4_PAYLOAD_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
