#!/usr/bin/env python3
"""Execution and evidence assembly for an existing CUTS_GATE1_V4 campaign.

This module never creates a campaign root or Gate-1 child selection.  It
consumes their detached identities, executes authority-selected Python bytes
from the same snapshots used to verify them, and exposes four explicit
operations:

* prepare the formal-positive pair selection, common prestate, and both arm
  bindings at their pre-registered paths;
* orchestrate the four Gate-1 units in their fixed order;
* independently rebuild the arithmetic and lifecycle inputs to the final
  Gate-1 gate, then publish either an unprivileged drill observation or the
  formal gate plus continuation.
* passively seal a post-admission terminal-assembly failure as non-authorizing
  evidence, without executing or adopting the failed campaign's selected code.

The disposable mode is intentionally non-authorizing.  It accepts only a
``dev-drill-*`` campaign directory, never writes the pre-registered gate or
continuation, and publishes an observation with every authorization flag
false.  Formal publication accepts only ``run-*`` and requires a separate
explicit boolean authorization from the caller.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sys
import types
from typing import Any

import campaign_authority_v4 as authority


DISPOSABLE = "disposable"
FORMAL = "formal"
MODES = (DISPOSABLE, FORMAL)
UNIT_ORDER = (
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
RESOURCE_MEMBERS = (
    "inner",
    "payload_result",
    "payload_seal",
    "preterminal",
    "resource",
    "release",
    "terminal",
    "cleanup",
)
RESOURCE_FILENAMES = {
    "inner": ("raw", "inner-lifecycle.json"),
    "payload_seal": ("raw", "payload-seal.json"),
    "preterminal": ("terminal", "preterminal.json"),
    "resource": ("terminal", "resource-verification.json"),
    "release": ("terminal", "release-token.json"),
    "terminal": ("terminal", "terminal.json"),
    "cleanup": ("terminal", "cleanup.json"),
}
LAUNCH_FILENAME = "systemd-run-launch.json"
OBSERVATION_SCHEMA = "noncert-cuts-gate1-v4-dev-drill-observation-v1"
OBSERVATION_RESULT_SCHEMA = "noncert-cuts-gate1-v4-dev-drill-replay-result-v1"
FORMAL_SELECTION_SCHEMA = "noncert-cuts-gate1-v4-formal-positive-selection-v2"
FORMAL_PURPOSE = "gate1_v4_formal_campaign_positive_control"
DRILL_SELECTION_SCHEMA = "noncert-cuts-gate1-v4-production-drill-positive-selection-v2"
DRILL_PURPOSE = "gate1_v4_disposable_production_positive_control"
FORMAL_SOLVE_SECONDS = 5.0
DETACHED_REPLAY_FILENAME = "detached-resource-replay.json"
GATE_ADMISSION_SLOT = "gate-admission"
GATE_ADMISSION_PHASE = "gate-admission"


class ExecutionError(RuntimeError):
    """Campaign execution or evidence assembly failed closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise ExecutionError(f"{label} must be an exact mapping")
    return value


def _validate_mode(
    campaign_dir: Path,
    *,
    mode: str,
    formal_authorized: bool,
) -> None:
    if mode not in MODES:
        raise ExecutionError("campaign execution mode is invalid")
    name = campaign_dir.name
    if mode == DISPOSABLE:
        if not name.startswith("dev-drill-") or formal_authorized:
            raise ExecutionError("disposable execution requires dev-drill-* and no authorization")
    elif not name.startswith("run-") or formal_authorized is not True:
        raise ExecutionError("formal execution requires run-* and explicit authorization")


def _load_authorities(
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> tuple[Mapping[str, Any], Mapping[str, Any], bytes, bytes]:
    checked_root = authority.validate_detached_identity(
        campaign_root_identity,
        "campaign root identity",
    )
    root_snapshot = authority.replay_detached_identity(
        checked_root,
        "campaign root",
    )
    root_value = authority.strict_loads(root_snapshot.data, "campaign root")
    if authority.canonical_json(root_value) != root_snapshot.data:
        raise ExecutionError("campaign root is not canonical JSON")
    root = authority.validate_campaign_root(
        root_value,
        campaign_dir=Path(str(checked_root["path"])).parent,
    )
    checked_selection = authority.validate_detached_identity(
        selection_identity,
        "Gate 1 selection identity",
    )
    selection_snapshot = authority.replay_detached_identity(
        checked_selection,
        "Gate 1 selection",
    )
    selection = authority.load_gate1_selection_bytes(
        selection_snapshot.data,
        checked_selection,
    )
    authority.validate_gate1_selection(selection, root=root)
    if selection["campaign_root_identity"] != dict(checked_root):
        raise ExecutionError("Gate 1 selection does not bind the campaign root")
    selected_self = authority.validate_detached_identity(
        _mapping(selection["tools"], "selected tools").get("gate1_campaign_execution_v4"),
        "selected campaign execution tool",
    )
    current_self = authority.snapshot_regular(Path(__file__))
    if (
        authority.detached_identity(current_self) != dict(selected_self)
        or Path(str(selected_self["path"])) != Path(__file__).absolute()
    ):
        raise ExecutionError("campaign execution is not running from the selected bytes")
    selected_authority = authority.validate_detached_identity(
        _mapping(selection["tools"], "selected tools").get("campaign_authority_v4"),
        "selected campaign authority tool",
    )
    imported_authority_path = Path(str(authority.__file__)).absolute()
    imported_authority = authority.snapshot_regular(imported_authority_path)
    if authority.detached_identity(imported_authority) != dict(selected_authority) or imported_authority_path != Path(
        str(selected_authority["path"])
    ):
        raise ExecutionError("campaign execution imported non-selected authority bytes")
    if os.path.lexists(authority.terminal_assembly_failure_path(root)):
        raise ExecutionError("campaign is sealed as an archived terminal-assembly failure")
    for group in ("tools", "inputs"):
        for role, identity in _mapping(selection[group], f"selected {group}").items():
            authority.replay_detached_identity(identity, f"selected {group}.{role}")
    return root, selection, root_snapshot.data, selection_snapshot.data


def _snapshot_path(path: Path, label: str) -> dict[str, object]:
    snapshot = authority.snapshot_regular(path)
    return {
        "raw": snapshot.data,
        "identity": authority.detached_identity(snapshot),
        "label": label,
    }


def _selected_source(
    selection: Mapping[str, Any],
    role: str,
) -> dict[str, object]:
    selected = _mapping(selection["tools"], "selected tools").get(role)
    identity = authority.validate_detached_identity(selected, f"selected tool {role}")
    snapshot = authority.replay_detached_identity(identity, f"selected tool {role}")
    observed = authority.detached_identity(snapshot)
    if observed != dict(identity):
        raise ExecutionError(f"selected tool {role} identity drifted")
    return {"raw": snapshot.data, "identity": observed}


def _selected_project_root(selection: Mapping[str, Any]) -> Path:
    inputs = _mapping(selection["inputs"], "selected inputs")
    identity = authority.validate_detached_identity(
        inputs.get("project_lock"),
        "selected repository PROJECT_LOCK",
    )
    snapshot = authority.replay_detached_identity(
        identity,
        "selected repository PROJECT_LOCK",
    )
    path = Path(str(identity["path"]))
    if path.name != "PROJECT_LOCK.md" or path != snapshot.path or not path.parent.is_absolute():
        raise ExecutionError("selected repository root binding drifted")
    return path.parent


def _selected_namespace(
    *,
    role: str,
    source: Mapping[str, object],
    initial: Mapping[str, object] | None = None,
    module_aliases: Mapping[str, types.ModuleType] | None = None,
) -> dict[str, object]:
    member = _mapping(source, f"selected source {role}")
    raw = member.get("raw")
    identity = authority.validate_detached_identity(
        member.get("identity"),
        f"selected source {role}",
    )
    if type(raw) is not bytes or authority.identity_from_bytes(identity["path"], raw) != dict(identity):
        raise ExecutionError(f"selected source {role} bytes drifted")
    module_name = f"_cuts_gate1_v4_exec_{role}_{identity['sha256'][:16]}"
    module = types.ModuleType(module_name)
    module.__dict__.update(
        {
            "__file__": str(identity["path"]),
            "__package__": None,
            **dict(initial or {}),
        }
    )
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
        exec(code, module.__dict__, module.__dict__)
    except Exception as exc:
        raise ExecutionError(f"selected source {role} failed exact-byte execution") from exc
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
    return module.__dict__


def _module_from_namespace(
    name: str,
    namespace: Mapping[str, object],
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(namespace)
    return module


def _selected_execution_namespaces(
    selection: Mapping[str, Any],
) -> dict[str, dict[str, object]]:
    """Load the execution graph only from selection-verified source bytes."""

    namespaces: dict[str, dict[str, object]] = {}
    modules: dict[str, types.ModuleType] = {}

    def load(role: str, *, aliases: tuple[str, ...] = ()) -> None:
        namespace = _selected_namespace(
            role=role,
            source=_selected_source(selection, role),
            module_aliases={alias: modules[alias] for alias in aliases},
        )
        namespaces[role] = namespace
        modules[role] = _module_from_namespace(
            f"_cuts_gate1_v4_selected_{role}",
            namespace,
        )

    load("campaign_authority_v4")
    load(
        "gate1_campaign_driver_v4",
        aliases=("campaign_authority_v4",),
    )
    load("resource_lifecycle_v4")
    load("resource_verifier_v4")
    load(
        "gate1_unit_orchestrator_v4",
        aliases=(
            "campaign_authority_v4",
            "gate1_campaign_driver_v4",
            "resource_lifecycle_v4",
            "resource_verifier_v4",
        ),
    )
    load("positive_control_gate_v4")
    return namespaces


def _capture_gate_admission_epoch(
    *,
    root: Mapping[str, Any],
    root_raw: bytes,
    selection: Mapping[str, Any],
    selection_raw: bytes,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    namespaces: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Capture and selected-byte replay the final live epoch before any gate write."""

    driver = namespaces["gate1_campaign_driver_v4"]
    capture = driver.get("capture_lifecycle_epoch_checkpoint")
    replay = driver.get("replay_lifecycle_epoch_checkpoint")
    if not callable(capture) or not callable(replay):
        raise ExecutionError("selected gate-admission epoch APIs are incomplete")
    epoch = authority.validate_manager_epoch(root["manager_epoch"])
    attestation = _mapping(
        epoch["attestation_toolchain"],
        "manager attestation toolchain",
    )
    observation = _mapping(
        epoch["observation_toolchain"],
        "manager observation toolchain",
    )
    identity = capture(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        unit_slot=GATE_ADMISSION_SLOT,
        phase=GATE_ADMISSION_PHASE,
        attestor_path=Path(str(attestation["attestor"]["path"])),
        busctl_path=Path(str(observation["busctl"]["path"])),
        python_path=Path(str(attestation["python"]["path"])),
        sudo_path=Path(str(attestation["sudo"]["path"])),
    )
    expected_path = Path(str(root["stage_topology"]["gate1_v4"]["gate_admission_epoch_path"]))
    member = _snapshot_path(expected_path, "gate-admission manager epoch")
    if member["identity"] != identity:
        raise ExecutionError("gate-admission manager epoch identity drifted")
    value = replay(
        checkpoint_raw=member["raw"],
        checkpoint_identity=member["identity"],
        campaign_root_raw=root_raw,
        campaign_root_identity=campaign_root_identity,
        selection_raw=selection_raw,
        selection_identity=selection_identity,
        unit_slot=GATE_ADMISSION_SLOT,
        phase=GATE_ADMISSION_PHASE,
    )
    checked = _mapping(value, "gate-admission manager epoch checkpoint")
    if not authority.same_manager_epoch(
        checked.get("manager_epoch"),
        root["manager_epoch"],
    ):
        raise ExecutionError("gate-admission manager epoch drifted")
    return {
        "raw": member["raw"],
        "identity": member["identity"],
        "value": dict(checked),
    }


def _positive_namespaces(
    selection: Mapping[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    project_root = _selected_project_root(selection)
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)
    support_source = _selected_source(selection, "positive_control_v4")
    support = _selected_namespace(role="positive_control_v4", source=support_source)
    support_module = types.ModuleType("_cuts_gate1_v4_selected_positive_support")
    support_module.__dict__.update(support)
    formal_source = _selected_source(selection, "positive_control_formal_v4")
    formal = _selected_namespace(
        role="positive_control_formal_v4",
        source=formal_source,
        initial={
            "_SUPPORT": support_module,
            "_SUPPORT_SELECTED_IDENTITY": support_source["identity"],
            "_PROJECT_ROOT": project_root,
        },
    )
    return support, formal


def _profile(mode: str) -> dict[str, object]:
    if mode == DISPOSABLE:
        return {
            "schema": DRILL_SELECTION_SCHEMA,
            "purpose": DRILL_PURPOSE,
            "formal_eligible": False,
            "prepare_entrypoint": "prepare_disposable_positive_common",
            "verify_entrypoint": "verify_production_drill_bundle",
        }
    if mode == FORMAL:
        return {
            "schema": FORMAL_SELECTION_SCHEMA,
            "purpose": FORMAL_PURPOSE,
            "formal_eligible": True,
            "prepare_entrypoint": "prepare_formal_positive_common",
            "verify_entrypoint": "verify_formal_bundle",
        }
    raise ExecutionError("campaign execution profile is invalid")


def _prepare_positive_pair(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    mode: str,
    formal_authorized: bool,
) -> dict[str, object]:
    """Seal selection, common prestate and both bindings before any arm."""

    root, selection, _, _ = _load_authorities(
        campaign_root_identity,
        selection_identity,
    )
    campaign_dir = Path(str(campaign_root_identity["path"])).parent
    _validate_mode(
        campaign_dir,
        mode=mode,
        formal_authorized=formal_authorized,
    )
    profile = _profile(mode)
    positive = _mapping(
        root["stage_topology"]["gate1_v4"]["positive_control"],
        "positive-control topology",
    )
    positive_root = Path(str(positive["root_dir"]))
    if positive_root != campaign_dir / "gate1-v4" / "positive-control-common":
        raise ExecutionError("positive-control root escaped campaign topology")
    if os.path.lexists(positive_root):
        raise ExecutionError("positive-control root already exists")
    authority.mkdir_exclusive(positive_root)
    common_export = Path(str(positive["builder_export_dirs"]["common"]))
    if common_export.parent != positive_root / "builder-exports":
        raise ExecutionError("positive builder export topology drifted")
    authority.mkdir_exclusive(common_export.parent)
    pair_selection = {
        "schema": profile["schema"],
        "purpose": profile["purpose"],
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "manager_epoch_digest": hashlib.sha256(authority.canonical_json(root["manager_epoch"])).hexdigest(),
        "gate1_formal_eligible": profile["formal_eligible"],
        "repository_head": root["repository_head"],
    }
    pair_selection_path = Path(str(positive["selection_path"]))
    pair_selection_identity = authority.write_exclusive(
        pair_selection_path,
        authority.canonical_json(pair_selection),
    )
    pair_replay = authority.snapshot_regular(pair_selection_path)
    if (
        pair_replay.data != authority.canonical_json(pair_selection)
        or authority.detached_identity(pair_replay) != pair_selection_identity
    ):
        raise ExecutionError("positive pair selection failed immediate replay")
    _, formal = _positive_namespaces(selection)
    prepare = formal.get(str(profile["prepare_entrypoint"]))
    if not callable(prepare):
        raise ExecutionError("selected profile-specific common builder is absent")
    prepared = prepare(
        positive_root,
        export_dir=common_export,
        solve_seconds=FORMAL_SOLVE_SECONDS,
    )
    if _mapping(prepared, "positive prepare result").get("post_attach_solve_performed") is not False:
        raise ExecutionError("positive preparation reported a post-attach solve")
    required_paths = {
        "pair_selection": pair_selection_path,
        "common": Path(str(positive["common_manifest_path"])),
        "binding_set": Path(str(positive["binding_seal_path"])),
        "control_binding": Path(str(positive["binding_paths"]["control"])),
        "treatment_binding": Path(str(positive["binding_paths"]["treatment"])),
    }
    identities = {role: _snapshot_path(path, role)["identity"] for role, path in required_paths.items()}
    if any(
        os.path.lexists(path)
        for path in (
            Path(str(positive["arm_dirs"]["control"])),
            Path(str(positive["arm_dirs"]["treatment"])),
        )
    ):
        raise ExecutionError("a post-model arm existed before both bindings were sealed")
    _load_authorities(campaign_root_identity, selection_identity)
    return {
        "mode": mode,
        "pair_selection_identity": pair_selection_identity,
        "identities": identities,
        "both_bindings_sealed_before_arms": True,
        "formal_publication_authorized": mode == FORMAL,
    }


def prepare_disposable_positive_pair(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> dict[str, object]:
    """Prepare only a non-authorizing production-typed disposable pair."""

    return _prepare_positive_pair(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        mode=DISPOSABLE,
        formal_authorized=False,
    )


def prepare_formal_positive_pair(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    formal_authorized: bool,
) -> dict[str, object]:
    """Prepare the campaign-bound formal pair with no injectable callback."""

    if formal_authorized is not True:
        raise ExecutionError("formal positive preparation lacks authorization")
    return _prepare_positive_pair(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        mode=FORMAL,
        formal_authorized=True,
    )


def _orchestrate_units_with(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    orchestrate: Callable[..., Mapping[str, object]],
    runtime_factory: Callable[[str], object],
) -> dict[str, Mapping[str, object]]:
    """Private fixture seam; public execution never accepts replacements."""

    results: dict[str, Mapping[str, object]] = {}
    for slot in UNIT_ORDER:
        results[slot] = _mapping(
            orchestrate(
                campaign_root_identity=campaign_root_identity,
                selection_identity=selection_identity,
                unit_slot=slot,
                runtime=runtime_factory(slot),
            ),
            f"{slot} orchestration result",
        )
        _load_authorities(campaign_root_identity, selection_identity)
    return results


def orchestrate_gate1_units(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    mode: str,
    formal_authorized: bool,
) -> dict[str, Mapping[str, object]]:
    """Run four fixed units through the selected orchestrator and runtime."""

    _, selection, _, _ = _load_authorities(
        campaign_root_identity,
        selection_identity,
    )
    _validate_mode(
        Path(str(campaign_root_identity["path"])).parent,
        mode=mode,
        formal_authorized=formal_authorized,
    )
    selected = _selected_execution_namespaces(selection)["gate1_unit_orchestrator_v4"]
    orchestrate = selected.get("orchestrate_selected_unit")
    if not callable(orchestrate):
        raise ExecutionError("selected unit orchestrator API is incomplete")
    results: dict[str, Mapping[str, object]] = {}
    for slot in UNIT_ORDER:
        results[slot] = _mapping(
            orchestrate(
                campaign_root_identity=campaign_root_identity,
                selection_identity=selection_identity,
                unit_slot=slot,
            ),
            f"{slot} orchestration result",
        )
        _load_authorities(campaign_root_identity, selection_identity)
    return results


def _collect_lifecycle(
    root: Mapping[str, Any],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    checkpoints: dict[str, object] = {}
    launches: dict[str, object] = {}
    replays: dict[str, object] = {}
    units = root["stage_topology"]["gate1_v4"]["units"]
    for slot in UNIT_ORDER:
        unit = units[slot]
        checkpoints[slot] = {}
        for phase in CHECKPOINT_PHASES:
            member = _snapshot_path(
                Path(str(unit["epoch_checkpoint_paths"][phase])),
                f"{slot}.{phase}",
            )
            checkpoints[slot][phase] = {
                "raw": member["raw"],
                "identity": member["identity"],
            }
        launch = _snapshot_path(
            Path(str(unit["raw_dir"])) / LAUNCH_FILENAME,
            f"{slot}.launch",
        )
        launches[slot] = {
            "raw": launch["raw"],
            "identity": launch["identity"],
        }
        evidence: dict[str, object] = {}
        for role in RESOURCE_MEMBERS:
            if role == "payload_result":
                member_path = Path(str(unit["result_path"]))
            else:
                directory, filename = RESOURCE_FILENAMES[role]
                member_path = Path(str(unit[f"{directory}_dir"])) / filename
            member = _snapshot_path(
                member_path,
                f"{slot}.{role}",
            )
            evidence[role] = {
                "raw": member["raw"],
                "identity": member["identity"],
            }
        detached = _snapshot_path(
            Path(str(unit["terminal_dir"])) / DETACHED_REPLAY_FILENAME,
            f"{slot}.detached",
        )
        replays[slot] = {
            "detached_raw": detached["raw"],
            "detached_identity": detached["identity"],
            "evidence": evidence,
        }
    return checkpoints, launches, replays


def _collect_positive(
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    mode: str,
) -> tuple[dict[str, object], dict[str, object]]:
    positive = root["stage_topology"]["gate1_v4"]["positive_control"]
    checker_source = _selected_source(selection, "independent_arithmetic_v4")
    checker = _selected_namespace(
        role="independent_arithmetic_v4",
        source=checker_source,
    )
    load_fixture = checker.get("load_fixture")
    profile = _profile(mode)
    verify = checker.get(str(profile["verify_entrypoint"]))
    if not callable(load_fixture) or not callable(verify):
        raise ExecutionError("selected independent arithmetic profile API is incomplete")
    bundle = load_fixture(Path(str(positive["root_dir"])))
    receipt = verify(bundle)
    receipt_path = Path(str(positive["arithmetic_receipt_path"]))
    receipt_identity = authority.write_exclusive(
        receipt_path,
        authority.canonical_json(receipt),
    )
    receipt_replay = authority.snapshot_regular(receipt_path)
    if receipt_replay.data != authority.canonical_json(receipt):
        raise ExecutionError("independent arithmetic receipt failed immediate replay")
    pair_selection = _mapping(
        bundle.get("selection"),
        "positive pair selection",
    )
    if (
        pair_selection.get("schema") != profile["schema"]
        or pair_selection.get("purpose") != profile["purpose"]
        or pair_selection.get("gate1_formal_eligible") is not profile["formal_eligible"]
    ):
        raise ExecutionError("positive arithmetic purpose crossed profiles")
    record = {
        "bundle": bundle,
        "pair_selection_identity": bundle["selection_identity"],
        "common_prestate_identity": bundle["common_identity"],
        "binding_set_identity": bundle["binding_seal_identity"],
        "arithmetic_raw": receipt_replay.data,
        "arithmetic_identity": receipt_identity,
    }
    return record, {
        "mode": mode,
        "receipt_identity": receipt_identity,
        "checker_identity": checker_source["identity"],
        "status": receipt["status"],
        "common_prestate_id": receipt["common_prestate_id"],
    }


def _join_disposable_payload_common_prestate(
    *,
    payload_results: Mapping[str, Mapping[str, Any]],
    common_prestate_id: object,
) -> None:
    if (
        type(common_prestate_id) is not str
        or len(common_prestate_id) != 64
        or any(character not in "0123456789abcdef" for character in common_prestate_id)
    ):
        raise ExecutionError("disposable arithmetic common_prestate_id is malformed")
    for slot in ("forced-control", "forced-treatment"):
        payload = _mapping(
            payload_results.get(slot),
            f"{slot} payload result",
        )
        delegated = _mapping(
            payload.get("delegated_result"),
            f"{slot} delegated result",
        )
        if delegated.get("common_prestate_id") != common_prestate_id:
            raise ExecutionError("disposable payloads do not join the independently checked common prestate")


def _evaluate_disposable_replay(
    *,
    root: Mapping[str, Any],
    selection: Mapping[str, Any],
    root_raw: bytes,
    selection_raw: bytes,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    namespaces: Mapping[str, Mapping[str, object]],
    checkpoints: Mapping[str, object],
    launch_evidence: Mapping[str, object],
    resource_replays: Mapping[str, object],
    gate_admission_epoch: Mapping[str, object],
    arithmetic_observation: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    """Replay formal-shaped lifecycle evidence without invoking the formal gate."""

    selected_gate = namespaces["positive_control_gate_v4"]
    selected_driver = namespaces["gate1_campaign_driver_v4"]
    selected_verifier = namespaces["resource_verifier_v4"]
    checkpoint_fn = selected_gate.get("_checkpoint")
    launch_fn = selected_gate.get("_launch_replay")
    resource_fn = selected_gate.get("_resource_replay")
    join_fn = selected_gate.get("_checkpoint_lifecycle_join")
    if not all(callable(item) for item in (checkpoint_fn, launch_fn, resource_fn, join_fn)):
        raise ExecutionError("selected disposable replay APIs are incomplete")
    checkpoint_identities: dict[str, object] = {}
    launch_identities: dict[str, object] = {}
    detached_identities: dict[str, object] = {}
    payload_identities: dict[str, object] = {}
    payload_results: dict[str, Mapping[str, Any]] = {}
    verifier_identity = selection["tools"]["resource_verifier_v4"]
    for slot in UNIT_ORDER:
        attempt_dir = Path(str(selection["units"][slot]["attempt_dir"]))
        checked: dict[str, Mapping[str, Any]] = {}
        checkpoint_identities[slot] = {}
        for phase in CHECKPOINT_PHASES:
            member = _mapping(
                _mapping(checkpoints[slot], f"{slot} checkpoints")[phase],
                f"{slot} {phase} checkpoint member",
            )
            value, identity = checkpoint_fn(
                raw=member["raw"],
                identity=member["identity"],
                root=root,
                selection=selection,
                slot=slot,
                phase=phase,
                attempt_dir=attempt_dir,
                campaign_root_raw=root_raw,
                campaign_root_identity=campaign_root_identity,
                selection_raw=selection_raw,
                selection_identity=selection_identity,
                driver=selected_driver,
            )
            checked[phase] = value
            checkpoint_identities[slot][phase] = identity
        _launch, launch_identity = launch_fn(
            slot=slot,
            member=_mapping(
                launch_evidence[slot],
                f"{slot} systemd-run launch evidence",
            ),
            root_identity=campaign_root_identity,
            selection_identity=selection_identity,
            selection=selection,
            checkpoints=checked,
            orchestrator=namespaces["gate1_unit_orchestrator_v4"],
            authority_namespace=namespaces["campaign_authority_v4"],
        )
        (
            detached,
            detached_identity,
            payload_result,
            payload_identity_set,
        ) = resource_fn(
            slot=slot,
            member=_mapping(
                resource_replays[slot],
                f"{slot} resource replay",
            ),
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            selection=selection,
            verifier_identity=verifier_identity,
            verifier=selected_verifier,
            expected_forced_profile="disposable_drill",
        )
        join_fn(slot=slot, checkpoints=checked, detached=detached)
        launch_identities[slot] = launch_identity
        detached_identities[slot] = detached_identity
        payload_identities[slot] = payload_identity_set
        payload_results[slot] = payload_result
    common_prestate_id = arithmetic_observation.get("common_prestate_id")
    _join_disposable_payload_common_prestate(
        payload_results=payload_results,
        common_prestate_id=common_prestate_id,
    )
    admission_member = _mapping(
        gate_admission_epoch,
        "gate-admission manager epoch member",
    )
    replay_gate_admission = selected_driver.get("replay_lifecycle_epoch_checkpoint")
    if not callable(replay_gate_admission):
        raise ExecutionError("selected gate-admission replay API is absent")
    admission_value = _mapping(
        replay_gate_admission(
            checkpoint_raw=admission_member["raw"],
            checkpoint_identity=admission_member["identity"],
            campaign_root_raw=root_raw,
            campaign_root_identity=campaign_root_identity,
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            unit_slot=GATE_ADMISSION_SLOT,
            phase=GATE_ADMISSION_PHASE,
        ),
        "replayed gate-admission manager epoch",
    )
    if not authority.same_manager_epoch(
        admission_value.get("manager_epoch"),
        root["manager_epoch"],
    ):
        raise ExecutionError("disposable gate-admission epoch drifted")
    return {
        "schema_version": OBSERVATION_RESULT_SCHEMA,
        "status": "DEV_DRILL_FULL_REPLAY_PASS_NO_AUTHORITY",
        "created_at_utc": created_at_utc,
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "manager_epoch": root["manager_epoch"],
        "checkpoint_identities": checkpoint_identities,
        "launch_identities": launch_identities,
        "detached_replay_identities": detached_identities,
        "payload_identities": payload_identities,
        "gate_admission_epoch_identity": admission_member["identity"],
        "arithmetic": dict(arithmetic_observation),
        "mechanism_credible_authorized": False,
        "continuation_authorized": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
    }


def assemble_disposable_observation(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> dict[str, object]:
    """Publish a replayable drill result that can never mint formal authority."""

    root, selection, root_raw, selection_raw = _load_authorities(
        campaign_root_identity,
        selection_identity,
    )
    campaign_dir = Path(str(campaign_root_identity["path"])).parent
    _validate_mode(
        campaign_dir,
        mode=DISPOSABLE,
        formal_authorized=False,
    )
    gate_path = Path(str(root["stage_topology"]["gate1_v4"]["gate_path"]))
    continuation_path = Path(str(root["stage_topology"]["gate1_v4"]["continuation_path"]))
    if os.path.lexists(gate_path) or os.path.lexists(continuation_path):
        raise ExecutionError("disposable mode encountered a formal terminal")
    checkpoints, launch_evidence, resource_replays = _collect_lifecycle(root)
    _positive_control, arithmetic_observation = _collect_positive(
        root=root,
        selection=selection,
        mode=DISPOSABLE,
    )
    namespaces = _selected_execution_namespaces(selection)
    gate_admission_epoch = _capture_gate_admission_epoch(
        root=root,
        root_raw=root_raw,
        selection=selection,
        selection_raw=selection_raw,
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        namespaces=namespaces,
    )
    now = _utc_now()
    replay_result = _evaluate_disposable_replay(
        root=root,
        selection=selection,
        root_raw=root_raw,
        selection_raw=selection_raw,
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        namespaces=namespaces,
        checkpoints=checkpoints,
        launch_evidence=launch_evidence,
        resource_replays=resource_replays,
        gate_admission_epoch=gate_admission_epoch,
        arithmetic_observation=arithmetic_observation,
        created_at_utc=now,
    )
    result_path = campaign_dir / "gate1-v4" / "dev-drill-replay-result-a001.json"
    result_identity = authority.write_exclusive(
        result_path,
        authority.canonical_json(replay_result),
    )
    replayed = authority.replay_detached_identity(
        result_identity,
        "disposable replay result",
    )
    if replayed.data != authority.canonical_json(replay_result):
        raise ExecutionError("disposable replay result failed immediate replay")
    observation = {
        "schema_version": OBSERVATION_SCHEMA,
        "status": "DEV_DRILL_REPLAY_PASS_NO_AUTHORITY",
        "created_at_utc": now,
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "replay_result_identity": result_identity,
        "arithmetic_receipt_identity": arithmetic_observation["receipt_identity"],
        "gate_admission_epoch_identity": gate_admission_epoch["identity"],
        "mechanism_credible_authorized": False,
        "continuation_authorized": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
    }
    observation_path = campaign_dir / "gate1-v4" / "dev-drill-observation-a001.json"
    observation_identity = authority.write_exclusive(
        observation_path,
        authority.canonical_json(observation),
    )
    replayed_observation = authority.replay_detached_identity(
        observation_identity,
        "disposable replay observation",
    )
    if replayed_observation.data != authority.canonical_json(observation):
        raise ExecutionError("disposable observation failed immediate replay")
    return {
        "mode": DISPOSABLE,
        "replay_result_identity": result_identity,
        "observation_identity": observation_identity,
        "gate_written": False,
        "continuation_written": False,
    }


def assemble_and_publish_formal_gate(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    formal_authorized: bool,
) -> dict[str, object]:
    """Run the selected formal gate with no callback or caller-supplied result."""

    if formal_authorized is not True:
        raise ExecutionError("formal Gate 1 publication lacks authorization")
    root, selection, root_raw, selection_raw = _load_authorities(
        campaign_root_identity,
        selection_identity,
    )
    _validate_mode(
        Path(str(campaign_root_identity["path"])).parent,
        mode=FORMAL,
        formal_authorized=True,
    )
    checkpoints, launch_evidence, resource_replays = _collect_lifecycle(root)
    positive_control, _arithmetic_observation = _collect_positive(
        root=root,
        selection=selection,
        mode=FORMAL,
    )
    namespaces = _selected_execution_namespaces(selection)
    gate_admission_epoch = _capture_gate_admission_epoch(
        root=root,
        root_raw=root_raw,
        selection=selection,
        selection_raw=selection_raw,
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        namespaces=namespaces,
    )
    selected_gate = namespaces["positive_control_gate_v4"]
    evaluate = selected_gate.get("evaluate_gate")
    replay_roles = selected_gate.get("REPLAY_TOOL_ROLES")
    if not callable(evaluate) or type(replay_roles) is not tuple:
        raise ExecutionError("selected formal Gate 1 API is incomplete")
    tool_sources = {role: _selected_source(selection, role) for role in replay_roles}
    now = _utc_now()
    gate_result = _mapping(
        evaluate(
            campaign_root_raw=root_raw,
            campaign_root_identity=campaign_root_identity,
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            gate_admission_epoch={
                "raw": gate_admission_epoch["raw"],
                "identity": gate_admission_epoch["identity"],
            },
            tool_sources=tool_sources,
            manager_checkpoints=checkpoints,
            launch_evidence=launch_evidence,
            resource_replays=resource_replays,
            positive_control=positive_control,
            created_at_utc=now,
        ),
        "Gate 1 result",
    )
    gate_path = Path(str(root["stage_topology"]["gate1_v4"]["gate_path"]))
    gate_identity = authority.write_exclusive(
        gate_path,
        authority.canonical_json(gate_result),
    )
    detached_identities = {slot: resource_replays[slot]["detached_identity"] for slot in UNIT_ORDER}
    continuation = authority.make_continuation_authorization(
        root,
        campaign_root_identity=campaign_root_identity,
        gate1_selection_identity=selection_identity,
        gate_result=gate_result,
        gate_result_identity=gate_identity,
        detached_replay_identities=detached_identities,
        gate_admission_epoch_identity=gate_admission_epoch["identity"],
        current_manager_epoch=gate_admission_epoch["value"]["manager_epoch"],
        created_at_utc=now,
    )
    continuation_identity = authority.write_continuation_authorization(
        campaign_root_identity["path"],
        campaign_root_identity,
        continuation,
    )
    _load_authorities(campaign_root_identity, selection_identity)
    authority.replay_detached_identity(gate_identity, "formal Gate 1 result")
    authority.replay_detached_identity(
        continuation_identity,
        "formal Gate 1 continuation",
    )
    return {
        "mode": FORMAL,
        "gate_identity": gate_identity,
        "continuation_identity": continuation_identity,
        "gate_written": True,
        "continuation_written": True,
        "campaign_closed": False,
        "organic_arm_launch_authorized": False,
    }


def archive_terminal_assembly_failure(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    failure_evidence_identity: Mapping[str, object],
) -> dict[str, object]:
    """Passively tombstone a failed root; this path can only remove authority."""

    current_execution = authority.detached_identity(
        authority.snapshot_regular(Path(__file__).absolute())
    )
    current_authority = authority.detached_identity(
        authority.snapshot_regular(Path(str(authority.__file__)).absolute())
    )
    archive_identity = authority.archive_terminal_assembly_failure(
        campaign_root_identity=campaign_root_identity,
        gate1_selection_identity=selection_identity,
        failure_evidence_identity=failure_evidence_identity,
        archive_tool_identities={
            "campaign_authority_v4": current_authority,
            "gate1_campaign_execution_v4": current_execution,
        },
        archived_at_utc=_utc_now(),
    )
    archived = authority.replay_terminal_assembly_failure_archive(
        campaign_root_identity=campaign_root_identity,
        archive_identity=archive_identity,
    )
    return {
        "ab16_slot_attempt": False,
        "archive_identity": archive_identity,
        "continuation_authorized": False,
        "failed_package_reuse_authorized": False,
        "global_claim_authorized": False,
        "mode": "archive-only",
        "new_campaign_root_required": True,
        "organic_arm_launch_authorized": False,
        "resume_authorized": False,
        "status": archived["status"],
    }


def _identity_from_arguments(
    arguments: argparse.Namespace,
    prefix: str,
) -> dict[str, object]:
    normalized = prefix.replace("-", "_")
    path = getattr(arguments, normalized)
    return {
        "path": str(path.absolute()),
        "size_bytes": getattr(arguments, f"{normalized}_size"),
        "sha256": getattr(arguments, f"{normalized}_sha256"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_authority(target: argparse.ArgumentParser) -> None:
        target.add_argument("--campaign-root", required=True, type=Path)
        target.add_argument("--campaign-root-size", required=True, type=int)
        target.add_argument("--campaign-root-sha256", required=True)
        target.add_argument("--selection", required=True, type=Path)
        target.add_argument("--selection-size", required=True, type=int)
        target.add_argument("--selection-sha256", required=True)

    for command in (
        "prepare-disposable",
        "orchestrate-disposable",
        "assemble-disposable",
    ):
        add_authority(subparsers.add_parser(command))
    for command in (
        "prepare-formal",
        "orchestrate-formal",
        "assemble-formal",
    ):
        target = subparsers.add_parser(command)
        add_authority(target)
        target.add_argument(
            "--formal-authorized",
            action="store_true",
            required=True,
        )
    archive = subparsers.add_parser("archive-terminal-failure")
    add_authority(archive)
    archive.add_argument("--failure-evidence", required=True, type=Path)
    archive.add_argument("--failure-evidence-size", required=True, type=int)
    archive.add_argument("--failure-evidence-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root_identity = _identity_from_arguments(arguments, "campaign-root")
    selection_identity = _identity_from_arguments(arguments, "selection")
    command = str(arguments.command)
    if command == "prepare-disposable":
        result = prepare_disposable_positive_pair(
            campaign_root_identity=root_identity,
            selection_identity=selection_identity,
        )
    elif command == "prepare-formal":
        result = prepare_formal_positive_pair(
            campaign_root_identity=root_identity,
            selection_identity=selection_identity,
            formal_authorized=arguments.formal_authorized,
        )
    elif command in {"orchestrate-disposable", "orchestrate-formal"}:
        formal = command.endswith("formal")
        result = orchestrate_gate1_units(
            campaign_root_identity=root_identity,
            selection_identity=selection_identity,
            mode=FORMAL if formal else DISPOSABLE,
            formal_authorized=formal,
        )
    elif command == "assemble-disposable":
        result = assemble_disposable_observation(
            campaign_root_identity=root_identity,
            selection_identity=selection_identity,
        )
    elif command == "archive-terminal-failure":
        result = archive_terminal_assembly_failure(
            campaign_root_identity=root_identity,
            selection_identity=selection_identity,
            failure_evidence_identity=_identity_from_arguments(
                arguments,
                "failure-evidence",
            ),
        )
    else:
        result = assemble_and_publish_formal_gate(
            campaign_root_identity=root_identity,
            selection_identity=selection_identity,
            formal_authorized=arguments.formal_authorized,
        )
    print(authority.canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ExecutionError, authority.AuthorityError) as exc:
        print(f"CUTS_GATE1_V4_EXECUTION_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
