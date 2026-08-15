#!/usr/bin/env python3
"""Research-only Phase -1 harness for fixed-placement binding/routing evidence.

This module intentionally bypasses the master and never touches proof-bearing
publish/seal surfaces.  It consumes the frozen protocol and corpus manifest in
this directory, runs each layout in a child process, and writes only research
receipts under the caller-selected output directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.binding_subproblem import (  # noqa: E402
    PortBindingModel,
    load_generic_input_slots_by_operation,
)
from src.models.routing_subproblem import (  # noqa: E402
    GHOST_RESERVED_OWNER_ID,
    ROUTING_DOMAIN_PROOF_REJECT_STATUSES,
    ROUTING_DOMAIN_STATUS_FEASIBLE,
    RoutingPlacementCore,
    RoutingSubproblem,
    run_exact_routing_precheck,
)

HERE = Path(__file__).resolve().parent
MANIFEST_PATH = HERE / "corpus_manifest.json"
PROTOCOL_PATH = HERE / "PHASE_MINUS1_PROTOCOL.md"
PROTOCOL_FREEZE_COMMIT = "2bd28a9848a1b247a96ca2c34b1f83782f2cda11"

BINDING_SECONDS = 20.0
ROUTING_SECONDS = 30.0
LAYOUT_WATCHDOG_SECONDS = 180.0
INJECTED_WATCHDOG_SECONDS = 60.0
BINDING_WORKERS = 1
ROUTING_WORKERS = 1
CP_SAT_RANDOM_SEED = 1

FORBIDDEN_NONEMPTY_ENV = (
    "EXACT_B1_BINDING_ALT_CAP",
    "EXACT_B1_BYPASS_ROUTING_PRECHECK",
    "EXACT_B1_ROUTING_AWARE_BINDING",
    "EXACT_BINDING_USE_OVERLOAD_SEPARATION",
    "EXACT_BINDING_DUMP_STATE",
    "EXACT_CUT_FRAMEWORK_ATTACH",
    "EXACT_B1_DELETION_CORE_CUT",
    "EXACT_B1_LAZY_DEMAND_CUT",
)

CENSOR_STATUSES = {
    "UNCENSORED",
    "INELIGIBLE_INPUT",
    "SOLVER_TIMEOUT_BINDING",
    "SOLVER_TIMEOUT_ROUTING",
    "WALL_TIMEOUT_END_TO_END",
    "INVALID_INPUT",
    "HARNESS_ERROR",
    "EXTERNAL_INTERRUPT",
    "ALT_CAP_PROTOCOL_VIOLATION",
}

REACHABILITY_FAILURE_CLASSES = {
    "NOT_REACHED",
    "REACHED_NO_EFFECT",
    "EFFECT_NO_TERMINAL",
}


class ProtocolViolation(RuntimeError):
    """The frozen evidence protocol cannot be honored."""


class IneligibleInput(RuntimeError):
    """A corpus record does not satisfy the frozen admission contract."""


@dataclass(frozen=True)
class LayoutInput:
    record: Mapping[str, Any]
    solution: dict[str, dict[str, Any]]
    normalized_sha256: str
    ghost_rect: tuple[int, int, int, int]
    ghost_source_receipt: Mapping[str, Any]
    pose_id_remaps: int
    source_identity_receipt: Mapping[str, Any] | None


@dataclass(frozen=True)
class FrozenInputs:
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]]
    instances: Sequence[Mapping[str, Any]]
    instance_by_id: Mapping[str, Mapping[str, Any]]
    generic_io: Mapping[str, Any]
    canonical_rules: Mapping[str, Any]
    generic_input_slots: Mapping[str, int]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value)]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _json_pointer(payload: Any, pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise IneligibleInput(f"JSON pointer must start with '/': {pointer}")
    value = payload
    for raw_token in pointer.split("/")[1:]:
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping):
            if token not in value:
                raise IneligibleInput(f"JSON pointer {pointer} misses key {token!r}")
            value = value[token]
        elif isinstance(value, list):
            if not token.isdigit() or int(token) >= len(value):
                raise IneligibleInput(f"JSON pointer {pointer} has invalid list index {token!r}")
            value = value[int(token)]
        else:
            raise IneligibleInput(f"JSON pointer {pointer} crosses scalar at {token!r}")
    return value


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _assert_protocol_ancestor() -> None:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PROTOCOL_FREEZE_COMMIT, "HEAD"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        raise ProtocolViolation(
            f"protocol freeze commit {PROTOCOL_FREEZE_COMMIT} is not an ancestor of HEAD"
        )


def _assert_clean_environment() -> None:
    contaminated = {
        name: os.environ[name]
        for name in FORBIDDEN_NONEMPTY_ENV
        if os.environ.get(name, "").strip()
    }
    if contaminated:
        if "EXACT_B1_BINDING_ALT_CAP" in contaminated:
            raise ProtocolViolation(
                "ALT_CAP_PROTOCOL_VIOLATION: EXACT_B1_BINDING_ALT_CAP must be absent/empty"
            )
        raise ProtocolViolation(f"forbidden research environment variables are set: {contaminated}")
    os.environ["EXACT_BINDING_CP_SAT_WORKERS"] = str(BINDING_WORKERS)
    os.environ["EXACT_ROUTING_CP_SAT_WORKERS"] = str(ROUTING_WORKERS)


def _load_manifest() -> dict[str, Any]:
    manifest = _read_json(MANIFEST_PATH)
    if manifest.get("status") != "FROZEN_PRE_RUN_V1_1":
        raise ProtocolViolation(f"unexpected manifest status: {manifest.get('status')!r}")
    return manifest


def _record_by_id(manifest: Mapping[str, Any], layout_id: str) -> Mapping[str, Any]:
    matches = [record for record in manifest["records"] if str(record["id"]) == layout_id]
    if len(matches) != 1:
        raise ProtocolViolation(f"layout id {layout_id!r} resolves to {len(matches)} records")
    return matches[0]


def _load_frozen_inputs(manifest: Mapping[str, Any]) -> FrozenInputs:
    identities = manifest["current_input_identities"]
    for relpath, expected in identities.items():
        path = ROOT / str(relpath)
        if not path.is_file():
            raise ProtocolViolation(f"missing frozen input: {relpath}")
        actual = _sha256_file(path)
        if actual != expected:
            raise ProtocolViolation(
                f"frozen input hash mismatch for {relpath}: expected {expected}, got {actual}"
            )

    candidate_payload = _read_json(ROOT / "data/preprocessed/candidate_placements.json")
    facility_pools = candidate_payload["facility_pools"]
    instances = _read_json(ROOT / "data/preprocessed/mandatory_exact_instances.json")
    generic_io = _read_json(ROOT / "data/preprocessed/generic_io_requirements.json")
    canonical_rules = _read_json(ROOT / "rules/canonical_rules.json")
    instance_by_id = {str(item["instance_id"]): item for item in instances}
    if len(instance_by_id) != 266:
        raise ProtocolViolation(f"expected 266 mandatory instances, found {len(instance_by_id)}")
    generic_input_slots = load_generic_input_slots_by_operation(project_root=ROOT)
    return FrozenInputs(
        facility_pools=facility_pools,
        instances=instances,
        instance_by_id=instance_by_id,
        generic_io=generic_io,
        canonical_rules=canonical_rules,
        generic_input_slots=generic_input_slots,
    )


def _verify_side_record(spec: Mapping[str, Any]) -> tuple[Path, Any]:
    path = ROOT / str(spec["path"])
    if not path.is_file():
        raise IneligibleInput(f"missing source-side record: {spec['path']}")
    expected = str(spec["raw_sha256"])
    actual = _sha256_file(path)
    if actual != expected:
        raise IneligibleInput(
            f"source-side record hash mismatch for {spec['path']}: expected {expected}, got {actual}"
        )
    return path, _read_json(path)


def _source_identity_receipt(
    record: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    raw_spec = record.get("source_identity_record")
    if not isinstance(raw_spec, Mapping):
        return None
    path, payload = _verify_side_record(raw_spec)
    observed = str(_json_pointer(payload, str(raw_spec["candidate_pool_json_pointer"])))
    expected = str(
        manifest["current_input_identities"]["data/preprocessed/candidate_placements.json"]
    )
    if observed != expected:
        raise IneligibleInput(
            f"source identity record pins candidate pool {observed}, expected {expected}"
        )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": _sha256_file(path),
        "candidate_pool_sha256": observed,
    }


def _resolve_ghost_rect(
    record: Mapping[str, Any],
    raw_payload: Mapping[str, Any],
    solution: MutableMapping[str, dict[str, Any]],
) -> tuple[tuple[int, int, int, int], Mapping[str, Any]]:
    source = record["ghost_source"]
    if source == "top_level_ghost_list":
        raw = raw_payload.get("ghost")
        if not isinstance(raw, list) or len(raw) != 4:
            raise IneligibleInput("top-level ghost must be [x,y,w,h]")
        x, y, width, height = (int(value) for value in raw)
        solution["ghost_pick"] = {
            "anchor": {"x": x, "y": y},
            "bound_type": "ghost_rect",
            "facility_type": "ghost_rect",
            "instance_id": "ghost_pick",
            "is_mandatory": False,
            "pose_id": f"ghost_anchor::{x},{y}",
            "pose_idx": y * 70 + x,
            "solve_mode": "exploratory",
            "width": width,
            "height": height,
        }
        receipt = {"kind": "top_level_ghost_list", "value": [x, y, width, height]}
    elif isinstance(source, Mapping):
        path, payload = _verify_side_record(source)
        rect = _json_pointer(payload, str(source["json_pointer"]))
        if not isinstance(rect, Mapping):
            raise IneligibleInput("ghost source pointer must resolve to an object")
        x, y = int(rect["x0"]), int(rect["y0"])
        width, height = int(rect["w"]), int(rect["h"])
        solution["ghost_pick"] = {
            "anchor": {"x": x, "y": y},
            "bound_type": "ghost_rect",
            "facility_type": "ghost_rect",
            "instance_id": "ghost_pick",
            "is_mandatory": False,
            "pose_id": f"ghost_anchor::{x},{y}",
            "pose_idx": y * 70 + x,
            "solve_mode": "exploratory",
            "width": width,
            "height": height,
        }
        receipt = {
            "kind": "side_record_rect",
            "path": str(path.relative_to(ROOT)),
            "sha256": _sha256_file(path),
            "json_pointer": source["json_pointer"],
        }
    elif source == "embedded_ghost_pick":
        raw_pick = solution.get("ghost_pick")
        if not isinstance(raw_pick, Mapping):
            raise IneligibleInput("embedded ghost_pick is missing or malformed")
        anchor = raw_pick.get("anchor")
        if not isinstance(anchor, Mapping):
            raise IneligibleInput("embedded ghost_pick lacks anchor")
        x, y = int(anchor["x"]), int(anchor["y"])
        shape_spec = record.get("ghost_shape_source")
        if not isinstance(shape_spec, Mapping):
            raise IneligibleInput("embedded ghost_pick lacks pinned ghost_shape_source")
        path, payload = _verify_side_record(shape_spec)
        pointed = _json_pointer(payload, str(shape_spec["json_pointer"]))
        mapping = str(shape_spec["mapping"])
        if mapping == "w=ghost_w,h=ghost_h":
            if not isinstance(pointed, Mapping):
                raise IneligibleInput("postmem ghost shape pointer must resolve to an object")
            width, height = int(pointed["ghost_w"]), int(pointed["ghost_h"])
        elif mapping == "[w,h]":
            if not isinstance(pointed, list) or len(pointed) != 2:
                raise IneligibleInput("AB16 ghost shape pointer must resolve to [w,h]")
            width, height = int(pointed[0]), int(pointed[1])
        else:
            raise IneligibleInput(f"unsupported ghost shape mapping: {mapping}")
        receipt = {
            "kind": "embedded_anchor_plus_shape_record",
            "path": str(path.relative_to(ROOT)),
            "sha256": _sha256_file(path),
            "json_pointer": shape_spec["json_pointer"],
        }
    else:
        raise IneligibleInput(f"unsupported ghost source: {source!r}")

    if width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > 70 or y + height > 70:
        raise IneligibleInput(f"ghost rectangle is out of bounds: {(x, y, width, height)}")
    return (x, y, width, height), receipt


def _load_layout(
    record: Mapping[str, Any],
    manifest: Mapping[str, Any],
    frozen: FrozenInputs,
) -> LayoutInput:
    path = ROOT / str(record["path"])
    if not path.is_file():
        raise IneligibleInput(f"layout source is missing: {record['path']}")
    actual_raw = _sha256_file(path)
    if actual_raw != record["raw_sha256"]:
        raise IneligibleInput(
            f"layout raw hash mismatch for {record['id']}: expected {record['raw_sha256']}, got {actual_raw}"
        )
    raw_payload = _read_json(path)
    adapter = str(record["adapter"])
    if adapter == "top_level_pose_map":
        raw_solution = raw_payload
    elif adapter in {"solution_pose_map", "solution_pose_map_plus_ghost_list"}:
        if not isinstance(raw_payload, Mapping) or not isinstance(raw_payload.get("solution"), Mapping):
            raise IneligibleInput(f"adapter {adapter} requires top-level solution object")
        raw_solution = raw_payload["solution"]
    else:
        raise IneligibleInput(f"unsupported adapter: {adapter}")
    if not isinstance(raw_solution, Mapping):
        raise IneligibleInput("placement solution must be an object")

    source_identity = _source_identity_receipt(record, manifest)
    pose_lookup = {
        str(facility_type): {
            str(pose["pose_id"]): index
            for index, pose in enumerate(pool)
        }
        for facility_type, pool in frozen.facility_pools.items()
    }

    solution: dict[str, dict[str, Any]] = {}
    remaps = 0
    for raw_id, raw_entry in raw_solution.items():
        instance_id = str(raw_id)
        if not isinstance(raw_entry, Mapping):
            raise IneligibleInput(f"solution entry {instance_id} is not an object")
        entry = dict(raw_entry)
        if instance_id == "ghost_pick":
            solution[instance_id] = entry
            continue
        facility_type = str(entry.get("facility_type", ""))
        if facility_type not in frozen.facility_pools:
            raise IneligibleInput(
                f"solution entry {instance_id} uses unknown facility_type {facility_type!r}"
            )
        pool = frozen.facility_pools[facility_type]
        pose_id = str(entry.get("pose_id", ""))
        resolved_index: int
        if pose_id and pose_id in pose_lookup[facility_type]:
            resolved_index = int(pose_lookup[facility_type][pose_id])
            remaps += resolved_index != entry.get("pose_idx")
        else:
            raw_index = entry.get("pose_idx")
            if isinstance(raw_index, bool) or not isinstance(raw_index, int):
                raise IneligibleInput(f"entry {instance_id} lacks an exact pose identity")
            if raw_index < 0 or raw_index >= len(pool):
                raise IneligibleInput(f"entry {instance_id} pose_idx is out of range: {raw_index}")
            resolved_index = int(raw_index)
            recorded_anchor = entry.get("anchor")
            current_anchor = pool[resolved_index].get("anchor")
            if recorded_anchor is None:
                if source_identity is None:
                    raise IneligibleInput(
                        f"entry {instance_id} lacks anchor and no source identity record proves the pool"
                    )
            elif recorded_anchor != current_anchor:
                raise IneligibleInput(
                    f"entry {instance_id} anchor disagrees with current pose_idx {resolved_index}"
                )
        entry["pose_idx"] = resolved_index
        solution[instance_id] = entry

    ghost_rect, ghost_receipt = _resolve_ghost_rect(record, raw_payload, solution)

    mandatory_ids = set(frozen.instance_by_id)
    observed_ids = set(solution)
    missing = sorted(mandatory_ids - observed_ids)
    if missing:
        raise IneligibleInput(f"layout {record['id']} misses mandatory instances: {missing[:8]}")
    extras = observed_ids - mandatory_ids
    invalid_extras = sorted(
        instance_id
        for instance_id in extras
        if instance_id != "ghost_pick" and not instance_id.startswith("pose_optional::")
    )
    if invalid_extras:
        raise IneligibleInput(f"layout {record['id']} has unrecognized extras: {invalid_extras[:8]}")
    for instance_id, instance in frozen.instance_by_id.items():
        if str(solution[instance_id]["facility_type"]) != str(instance["facility_type"]):
            raise IneligibleInput(f"facility type mismatch for mandatory instance {instance_id}")

    if len(solution) != int(record["expected_record_count"]):
        raise IneligibleInput(
            f"layout {record['id']} normalized record count {len(solution)} != {record['expected_record_count']}"
        )
    if remaps != int(record["expected_pose_id_remaps"]):
        raise IneligibleInput(
            f"layout {record['id']} pose remap count {remaps} != {record['expected_pose_id_remaps']}"
        )
    normalized_digest = _canonical_digest(solution)
    if normalized_digest != record["normalized_sha256"]:
        raise IneligibleInput(
            f"layout {record['id']} normalized hash mismatch: expected {record['normalized_sha256']}, got {normalized_digest}"
        )
    return LayoutInput(
        record=record,
        solution=solution,
        normalized_sha256=normalized_digest,
        ghost_rect=ghost_rect,
        ghost_source_receipt=ghost_receipt,
        pose_id_remaps=remaps,
        source_identity_receipt=source_identity,
    )


def _validate_excluded_candidates(
    manifest: Mapping[str, Any],
    frozen: FrozenInputs,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for record in manifest["excluded_candidates"]:
        path = ROOT / str(record["path"])
        if not path.is_file():
            raise ProtocolViolation(f"excluded sampling-frame source is missing: {record['path']}")
        actual = _sha256_file(path)
        if actual != record["raw_sha256"]:
            raise ProtocolViolation(
                f"excluded source hash mismatch for {record['id']}: expected "
                f"{record['raw_sha256']}, got {actual}"
            )
        reason = str(record["reason"])
        ambiguity_count = 0
        if reason == "AMBIGUOUS_OPTIONAL_STORAGE_BOX_MIGRATION":
            payload = _read_json(path)
            if not isinstance(payload, Mapping):
                raise ProtocolViolation(f"excluded source {record['id']} is not a pose map")
            current_pool = frozen.facility_pools["protocol_storage_box"]
            current_pose_ids = {str(pose["pose_id"]) for pose in current_pool}
            for instance_id, entry in payload.items():
                if not str(instance_id).startswith("pose_optional::protocol_storage_box::"):
                    continue
                if not isinstance(entry, Mapping):
                    continue
                pose_id = str(entry.get("pose_id", ""))
                anchor = entry.get("anchor")
                anchor_matches = [pose for pose in current_pool if pose.get("anchor") == anchor]
                if pose_id not in current_pose_ids and len(anchor_matches) > 1:
                    ambiguity_count += 1
            if ambiguity_count == 0:
                raise ProtocolViolation(
                    f"excluded source {record['id']} no longer exhibits the frozen ambiguity"
                )
        receipts.append(
            {
                "layout_id": record["id"],
                "status": "EXCLUDED_PRE_RUN",
                "reason": reason,
                "raw_sha256": actual,
                "ambiguity_count": ambiguity_count,
            }
        )
    return receipts


def _occupied_core(layout: LayoutInput, frozen: FrozenInputs) -> RoutingPlacementCore:
    occupied: set[tuple[int, int]] = set()
    owners: dict[tuple[int, int], str] = {}
    for instance_id, entry in layout.solution.items():
        if instance_id == "ghost_pick":
            continue
        facility_type = str(entry["facility_type"])
        pose_index = int(entry["pose_idx"])
        pose = frozen.facility_pools[facility_type][pose_index]
        for raw_cell in pose.get("occupied_cells", []):
            cell = (int(raw_cell[0]), int(raw_cell[1]))
            previous = owners.get(cell)
            if previous is not None and previous != instance_id:
                raise IneligibleInput(
                    f"layout {layout.record['id']} body overlap at {cell}: {previous}, {instance_id}"
                )
            occupied.add(cell)
            owners[cell] = instance_id

    x, y, width, height = layout.ghost_rect
    ghost_cells = {
        (x + dx, y + dy)
        for dx in range(width)
        for dy in range(height)
    }
    body_overlap = sorted(ghost_cells & occupied)
    if body_overlap:
        raise IneligibleInput(
            f"layout {layout.record['id']} has mandatory/optional body inside ghost: {body_overlap[:8]}"
        )
    for cell in ghost_cells:
        occupied.add(cell)
        owners[cell] = GHOST_RESERVED_OWNER_ID
    return RoutingPlacementCore.from_occupied_cells(
        occupied,
        occupied_owner_by_cell=owners,
    )


def _new_binding_model(layout: LayoutInput, frozen: FrozenInputs) -> PortBindingModel:
    model = PortBindingModel(
        layout.solution,
        frozen.facility_pools,
        frozen.instances,
        required_generic_outputs=dict(frozen.generic_io["required_generic_outputs"]),
        required_generic_inputs=dict(frozen.generic_io["required_generic_inputs"]),
        project_root=ROOT,
        generic_input_slots_by_operation=dict(frozen.generic_input_slots),
        canonical_rules_payload=frozen.canonical_rules,
    )
    model.build(use_overload_separation=False)
    return model


def _selection_digest(selection: Mapping[str, Any]) -> str:
    return _canonical_digest(_json_safe(selection))


def _selection_literal_count(model: PortBindingModel, selection: Mapping[str, Any]) -> int:
    count = 0
    for instance_id, binding_index in selection.get("binding_choice", {}).items():
        if (
            str(instance_id) in model.binding_vars
            and binding_index in model.binding_vars[str(instance_id)]
        ):
            count += 1
    for slot_id, commodity in selection.get("generic_inputs", {}).items():
        if (
            str(slot_id) in model.generic_input_vars
            and str(commodity) in model.generic_input_vars[str(slot_id)]
        ):
            count += 1
    for slot_id, commodity in selection.get("generic_outputs", {}).items():
        if (
            str(slot_id) in model.generic_output_vars
            and str(commodity) in model.generic_output_vars[str(slot_id)]
        ):
            count += 1
    return count


def _apply_feedback(
    model: PortBindingModel,
    *,
    layout: LayoutInput,
    selection: Mapping[str, Any],
    producer: str,
    diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    envelope = {
        "schema_version": "zmd_phase_minus1_feedback_v1",
        "family_id": "selection_nogood_v1",
        "layout_id": layout.record["id"],
        "layout_digest": layout.normalized_sha256,
        "producer": producer,
        "scope": "current_fixed_layout_and_current_binding_selection",
        "selection_digest": _selection_digest(selection),
        "diagnostics": _json_safe(diagnostics),
    }
    registry_status = "REGISTERED"
    resolver_status = "RESOLVED"
    if envelope["layout_digest"] != layout.normalized_sha256:
        resolver_status = "REJECTED_SCOPE_MISMATCH"
        return {
            "envelope": envelope,
            "registry_status": registry_status,
            "resolver_status": resolver_status,
            "consumer_status": "NOT_REACHED",
            "literal_count": 0,
            "reachabilityFailureClass": "NOT_REACHED",
            "terminalOutcome": None,
        }
    literal_count = _selection_literal_count(model, selection)
    model.add_nogood_cut(dict(selection))
    return {
        "envelope": envelope,
        "registry_status": registry_status,
        "resolver_status": resolver_status,
        "consumer_status": "APPLIED",
        "literal_count": literal_count,
        "reachabilityFailureClass": None,
        "terminalOutcome": None,
    }


def _complete_feedback_receipt(
    receipt: MutableMapping[str, Any],
    *,
    next_status: str,
    next_selection: Mapping[str, Any] | None,
) -> None:
    receipt["next_status"] = str(next_status)
    before_digest = str(receipt["envelope"]["selection_digest"])
    after_digest = _selection_digest(next_selection) if next_selection is not None else None
    receipt["next_selection_digest"] = after_digest
    effect = int(receipt.get("literal_count", 0)) > 0 and (
        after_digest is None or after_digest != before_digest
    )
    receipt["effect"] = effect
    if not effect:
        receipt["reachabilityFailureClass"] = "REACHED_NO_EFFECT"
        return
    if next_status == "INFEASIBLE":
        receipt["reachabilityFailureClass"] = None
        receipt["terminalOutcome"] = "INFEASIBLE"
    else:
        receipt["reachabilityFailureClass"] = "EFFECT_NO_TERMINAL"


def _precheck_projection(precheck: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": str(precheck.get("status", "")),
        "binding_selection_safe_reject": bool(
            precheck.get("binding_selection_safe_reject", False)
        ),
        "placement_level_conflict_set": list(
            precheck.get("placement_level_conflict_set", [])
        ),
        "blocked_ports": list(precheck.get("blocked_ports", [])),
        "disconnected_commodities": list(precheck.get("disconnected_commodities", [])),
        "domain_stats": dict(precheck.get("domain_stats", {})),
    }


def _event(
    *,
    reason: str,
    gate_side: str,
    feedback_form: str,
    support_core_status: str = "UNAVAILABLE",
    diagnostic_replay_status: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "reason": reason,
        "gateSide": gate_side,
        "feedbackForm": feedback_form,
        "censorStatus": "UNCENSORED",
        "supportCoreStatus": support_core_status,
        "diagnosticReplayStatus": diagnostic_replay_status,
        "familyKey": f"{reason}|{gate_side}|{feedback_form}|UNCENSORED",
        "details": _json_safe(details or {}),
    }


def _binding_status_name(status: Any) -> str:
    return str(status)


def _run_layout(layout: LayoutInput, frozen: FrozenInputs) -> dict[str, Any]:
    started = time.perf_counter()
    core = _occupied_core(layout, frozen)
    model = _new_binding_model(layout, frozen)
    build_seconds = time.perf_counter() - started
    events: list[dict[str, Any]] = []
    feedback_receipts: list[dict[str, Any]] = []
    counters = {
        "binding_proposals": 0,
        "binding_solves": 0,
        "routing_prechecks": 0,
        "routing_solves": 0,
        "binding_routing_round_trips": 0,
    }
    timings = {
        "binding_build_seconds": build_seconds,
        "binding_solve_seconds": 0.0,
        "routing_precheck_seconds": 0.0,
        "routing_build_seconds": 0.0,
        "routing_solve_seconds": 0.0,
    }

    terminal_status = "UNKNOWN"
    censor_status = "UNCENSORED"
    final_reason = "unknown_other"
    last_binding_summary: Mapping[str, Any] = model.extract_conflict_summary()
    pending_receipt: MutableMapping[str, Any] | None = None

    while True:
        solve_started = time.perf_counter()
        binding_status = _binding_status_name(model.solve(BINDING_SECONDS))
        timings["binding_solve_seconds"] += time.perf_counter() - solve_started
        counters["binding_solves"] += 1
        last_binding_summary = model.extract_conflict_summary()
        if pending_receipt is not None:
            next_selection = model.extract_selection() if binding_status == "FEASIBLE" else None
            _complete_feedback_receipt(
                pending_receipt,
                next_status=binding_status,
                next_selection=next_selection,
            )
            pending_receipt = None

        if binding_status == "FEASIBLE":
            counters["binding_proposals"] += 1
            selection = model.extract_selection()
            port_specs = model.extract_port_specs()
            counters["routing_prechecks"] += 1
            pre_started = time.perf_counter()
            precheck = run_exact_routing_precheck(
                placement_core=core,
                port_specs=port_specs,
            )
            replay = run_exact_routing_precheck(
                placement_core=core,
                port_specs=port_specs,
            )
            timings["routing_precheck_seconds"] += time.perf_counter() - pre_started
            projection = _precheck_projection(precheck)
            replay_projection = _precheck_projection(replay)
            replay_status = (
                "REPLAYED_IDENTICAL"
                if projection == replay_projection
                else "REPLAY_MISMATCH"
            )
            precheck_status = str(precheck.get("status", ""))

            if precheck_status in ROUTING_DOMAIN_PROOF_REJECT_STATUSES:
                if not bool(precheck.get("binding_selection_safe_reject", False)):
                    raise ProtocolViolation(
                        f"precheck {precheck_status} did not authorize binding-selection reject"
                    )
                reason = (
                    "routing_front_blocked"
                    if precheck_status == "front_blocked"
                    else "routing_relaxed_disconnected"
                )
                conflict_set = list(precheck.get("placement_level_conflict_set", []))
                events.append(
                    _event(
                        reason=reason,
                        gate_side="routing_precheck",
                        feedback_form="binding_selection_family",
                        support_core_status=(
                            "AVAILABLE_NOT_REPLAYED" if conflict_set else "UNAVAILABLE"
                        ),
                        diagnostic_replay_status=replay_status,
                        details=projection,
                    )
                )
                receipt = _apply_feedback(
                    model,
                    layout=layout,
                    selection=selection,
                    producer=f"routing_precheck:{precheck_status}",
                    diagnostics=projection,
                )
                feedback_receipts.append(receipt)
                pending_receipt = receipt
                counters["binding_routing_round_trips"] += 1
                continue

            if precheck_status != ROUTING_DOMAIN_STATUS_FEASIBLE:
                raise ProtocolViolation(f"unexpected routing precheck status: {precheck_status!r}")

            commodities = sorted(
                {
                    str(spec["commodity"])
                    for spec in port_specs
                    if str(spec.get("commodity", ""))
                }
            )
            route_model = RoutingSubproblem.from_placement_core(
                core,
                port_specs,
                commodities,
                domain_analysis=precheck["_analysis"],
            )
            route_build_started = time.perf_counter()
            route_model.build()
            timings["routing_build_seconds"] += time.perf_counter() - route_build_started
            counters["routing_solves"] += 1
            route_solve_started = time.perf_counter()
            routing_status = str(route_model.solve(ROUTING_SECONDS))
            timings["routing_solve_seconds"] += time.perf_counter() - route_solve_started

            if routing_status == "FEASIBLE":
                terminal_status = "FEASIBLE"
                final_reason = "layout_feasible"
                events.append(
                    _event(
                        reason="layout_feasible",
                        gate_side="terminal",
                        feedback_form="none",
                        details={
                            "route_count": len(route_model.extract_routes()),
                            "routing_build_stats": route_model.build_stats,
                        },
                    )
                )
                break

            if routing_status == "INFEASIBLE":
                event_details = {
                    "precheck": projection,
                    "routing_build_stats": route_model.build_stats,
                }
                events.append(
                    _event(
                        reason="routing_model_infeasible",
                        gate_side="routing_solve",
                        feedback_form="point_nogood",
                        details=event_details,
                    )
                )
                receipt = _apply_feedback(
                    model,
                    layout=layout,
                    selection=selection,
                    producer="routing_solve:INFEASIBLE",
                    diagnostics=event_details,
                )
                feedback_receipts.append(receipt)
                pending_receipt = receipt
                counters["binding_routing_round_trips"] += 1
                continue

            terminal_status = "UNKNOWN"
            censor_status = "SOLVER_TIMEOUT_ROUTING"
            final_reason = (
                "routing_connectivity_guard_timeout"
                if str(route_model.build_stats.get("last_solve", {}).get("status", ""))
                == "CONNECTIVITY_GUARD_TIMEOUT"
                else "routing_solver_timeout"
            )
            break

        if binding_status == "INFEASIBLE":
            terminal_status = "INFEASIBLE"
            empty_domains = model.extract_empty_binding_domain_instances()
            final_reason = "binding_empty_domain" if empty_domains else "binding_exhausted"
            events.append(
                _event(
                    reason=final_reason,
                    gate_side="binding_solve",
                    feedback_form="none",
                    support_core_status=(
                        "AVAILABLE_NOT_REPLAYED" if empty_domains else "UNAVAILABLE"
                    ),
                    details={
                        "empty_binding_domain_instances": empty_domains,
                        "binding_summary": last_binding_summary,
                    },
                )
            )
            break
        if binding_status == "INVALID_INPUT":
            terminal_status = "UNKNOWN"
            censor_status = "INVALID_INPUT"
            final_reason = "binding_invalid_input"
            break
        terminal_status = "UNKNOWN"
        censor_status = "SOLVER_TIMEOUT_BINDING"
        final_reason = "unknown_other"
        break

    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v1",
        "research_only": True,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "repository_head": _git("rev-parse", "HEAD"),
        "layout_id": layout.record["id"],
        "stratum": layout.record["stratum"],
        "split": layout.record["role"],
        "normalized_sha256": layout.normalized_sha256,
        "pose_id_remaps": layout.pose_id_remaps,
        "ghost_rect": list(layout.ghost_rect),
        "ghost_source_receipt": layout.ghost_source_receipt,
        "source_identity_receipt": layout.source_identity_receipt,
        "terminalStatus": terminal_status,
        "censorStatus": censor_status,
        "finalReason": final_reason,
        "counters": counters,
        "timings": timings,
        "total_wall_seconds": time.perf_counter() - started,
        "events": events,
        "d2_organic_receipts": feedback_receipts,
        "binding_summary": last_binding_summary,
        "solver_contract": {
            "binding_seconds": BINDING_SECONDS,
            "routing_seconds": ROUTING_SECONDS,
            "binding_workers": BINDING_WORKERS,
            "routing_workers": ROUTING_WORKERS,
            "cp_sat_random_seed": CP_SAT_RANDOM_SEED,
            "alternative_count_cap": None,
        },
    }


def _run_injected(layout: LayoutInput, frozen: FrozenInputs) -> dict[str, Any]:
    started = time.perf_counter()
    model = _new_binding_model(layout, frozen)
    first_status = str(model.solve(BINDING_SECONDS))
    if first_status != "FEASIBLE":
        return {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
            "layout_id": layout.record["id"],
            "producer": "injected_selection_nogood",
            "first_status": first_status,
            "reachabilityFailureClass": "NOT_REACHED",
            "terminalOutcome": None,
            "wall_seconds": time.perf_counter() - started,
        }
    first_selection = model.extract_selection()
    receipt = _apply_feedback(
        model,
        layout=layout,
        selection=first_selection,
        producer="injected_selection_nogood",
        diagnostics={"purpose": "D2 injected consumer canary"},
    )
    second_status = str(model.solve(BINDING_SECONDS))
    second_selection = model.extract_selection() if second_status == "FEASIBLE" else None
    _complete_feedback_receipt(
        receipt,
        next_status=second_status,
        next_selection=second_selection,
    )
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
        "layout_id": layout.record["id"],
        "producer": "injected_selection_nogood",
        "first_status": first_status,
        "second_status": second_status,
        "receipt": receipt,
        "wall_seconds": time.perf_counter() - started,
    }


def _synthetic_timeout_result(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v1",
        "research_only": True,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "repository_head": _git("rev-parse", "HEAD"),
        "layout_id": record["id"],
        "stratum": record["stratum"],
        "split": record["role"],
        "terminalStatus": "UNKNOWN",
        "censorStatus": "WALL_TIMEOUT_END_TO_END",
        "finalReason": "unknown_other",
        "counters": {},
        "timings": {},
        "total_wall_seconds": LAYOUT_WATCHDOG_SECONDS,
        "events": [],
        "d2_organic_receipts": [],
        "watchdog": {"seconds": LAYOUT_WATCHDOG_SECONDS, "action": "child_terminated"},
    }


def _synthetic_error_result(record: Mapping[str, Any], message: str) -> dict[str, Any]:
    return {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v1",
        "research_only": True,
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "repository_head": _git("rev-parse", "HEAD"),
        "layout_id": record["id"],
        "stratum": record["stratum"],
        "split": record["role"],
        "terminalStatus": "UNKNOWN",
        "censorStatus": "HARNESS_ERROR",
        "finalReason": "unknown_other",
        "counters": {},
        "timings": {},
        "events": [],
        "d2_organic_receipts": [],
        "error": message,
    }


def _aggregate(output_dir: Path, manifest: Mapping[str, Any]) -> None:
    results: list[dict[str, Any]] = []
    for record in manifest["records"]:
        result_path = output_dir / "layouts" / f"{record['id']}.json"
        if result_path.is_file():
            results.append(_read_json(result_path))
        else:
            results.append(_synthetic_error_result(record, "missing layout receipt"))

    terminal_counter = Counter(str(item.get("terminalStatus", "UNKNOWN")) for item in results)
    censor_counter = Counter(str(item.get("censorStatus", "HARNESS_ERROR")) for item in results)
    uncensored = [item for item in results if item.get("censorStatus") == "UNCENSORED"]

    family_layouts: dict[str, set[str]] = defaultdict(set)
    family_strata: dict[str, set[str]] = defaultdict(set)
    family_splits: dict[str, set[str]] = defaultdict(set)
    family_replay: dict[str, set[str]] = defaultdict(set)
    for result in uncensored:
        seen_in_layout: set[str] = set()
        for event in result.get("events", []):
            key = str(event.get("familyKey", ""))
            if not key or key in seen_in_layout:
                continue
            seen_in_layout.add(key)
            family_layouts[key].add(str(result["layout_id"]))
            family_strata[key].add(str(result["stratum"]))
            family_splits[key].add(str(result["split"]))
            if event.get("diagnosticReplayStatus"):
                family_replay[key].add(str(event["diagnosticReplayStatus"]))

    families = []
    for key in sorted(family_layouts):
        reason, gate_side, feedback_form, censor_status = key.split("|", 3)
        families.append(
            {
                "familyKey": key,
                "reason": reason,
                "gateSide": gate_side,
                "feedbackForm": feedback_form,
                "censorStatus": censor_status,
                "layout_ids": sorted(family_layouts[key]),
                "layout_count": len(family_layouts[key]),
                "strata": sorted(family_strata[key]),
                "strata_count": len(family_strata[key]),
                "splits": sorted(family_splits[key]),
                "diagnostic_replay_statuses": sorted(family_replay[key]),
            }
        )

    eligible_families = [
        item
        for item in families
        if item["layout_count"] >= 3
        and item["strata_count"] >= 2
        and item["feedbackForm"] not in {"point_nogood", "none"}
        and "holdout" not in item["splits"]
        and "REPLAYED_IDENTICAL" in item["diagnostic_replay_statuses"]
    ]
    eligible_families.sort(key=lambda item: (-int(item["layout_count"]), str(item["familyKey"])))

    spectrum = {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_d1_v1",
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "repository_head": _git("rev-parse", "HEAD"),
        "layout_count": len(results),
        "uncensored_terminal_count": len(uncensored),
        "minimum_uncensored_required": 6,
        "terminal_counts": dict(sorted(terminal_counter.items())),
        "censor_counts": dict(sorted(censor_counter.items())),
        "families": families,
        "d3_eligible_families": eligible_families,
        "d3_triggered": bool(len(uncensored) >= 6 and eligible_families),
        "layout_receipts": [
            {
                "layout_id": item["layout_id"],
                "stratum": item["stratum"],
                "split": item["split"],
                "terminalStatus": item.get("terminalStatus"),
                "censorStatus": item.get("censorStatus"),
                "finalReason": item.get("finalReason"),
                "counters": item.get("counters", {}),
                "total_wall_seconds": item.get("total_wall_seconds"),
            }
            for item in results
        ],
    }
    _write_json(output_dir / "D1_DEATH_SPECTRUM.json", spectrum)

    organic_receipts = [
        {
            "layout_id": result["layout_id"],
            "receipt": receipt,
        }
        for result in results
        for receipt in result.get("d2_organic_receipts", [])
    ]
    injected_path = output_dir / "D2_INJECTED.json"
    injected = _read_json(injected_path) if injected_path.is_file() else None
    d2 = {
        "schema_version": "zmd_reasoning_outer_loop_phase_minus1_d2_v1",
        "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
        "organic_receipt_count": len(organic_receipts),
        "organic_receipts": organic_receipts,
        "injected": injected,
        "required_failure_classes": sorted(REACHABILITY_FAILURE_CLASSES),
        "organic_effect_count": sum(
            bool(item["receipt"].get("effect")) for item in organic_receipts
        ),
        "injected_effect": bool(
            injected
            and isinstance(injected.get("receipt"), Mapping)
            and injected["receipt"].get("effect")
        ),
    }
    _write_json(output_dir / "D2_REACHABILITY_MANIFEST.json", d2)

    lines = [
        "# Phase -1 batch summary",
        "",
        f"- Protocol freeze: `{PROTOCOL_FREEZE_COMMIT}`",
        f"- Layouts: `{len(results)}`; uncensored terminal: `{len(uncensored)}` / minimum `6`.",
        f"- Terminal counts: `{dict(sorted(terminal_counter.items()))}`.",
        f"- Censor counts: `{dict(sorted(censor_counter.items()))}`.",
        f"- D3 trigger: `{'YES' if spectrum['d3_triggered'] else 'NO'}`.",
        f"- Organic D2 receipts/effects: `{len(organic_receipts)}` / `{d2['organic_effect_count']}`.",
        f"- Injected D2 effect: `{d2['injected_effect']}`.",
        "",
        "## Layouts",
        "",
        "| ID | split | terminal | censor | reason | binding proposals | routing solves | wall s |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]
    for item in spectrum["layout_receipts"]:
        counters = item.get("counters", {})
        wall = item.get("total_wall_seconds")
        lines.append(
            f"| `{item['layout_id']}` | `{item['split']}` | `{item['terminalStatus']}` | "
            f"`{item['censorStatus']}` | `{item['finalReason']}` | "
            f"{int(counters.get('binding_proposals', 0))} | "
            f"{int(counters.get('routing_solves', 0))} | "
            f"{float(wall):.2f} |" if isinstance(wall, (int, float)) else
            f"| `{item['layout_id']}` | `{item['split']}` | `{item['terminalStatus']}` | "
            f"`{item['censorStatus']}` | `{item['finalReason']}` | "
            f"{int(counters.get('binding_proposals', 0))} | "
            f"{int(counters.get('routing_solves', 0))} | — |"
        )
    if eligible_families:
        lines.extend(("", "## D3-eligible families", ""))
        for family in eligible_families:
            lines.append(
                f"- `{family['familyKey']}`: {family['layout_count']} discovery layouts, "
                f"{family['strata_count']} strata."
            )
    _write_text(output_dir / "BATCH_SUMMARY.md", "\n".join(lines) + "\n")


def _child_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for name in FORBIDDEN_NONEMPTY_ENV:
        environment.pop(name, None)
    environment["EXACT_BINDING_CP_SAT_WORKERS"] = str(BINDING_WORKERS)
    environment["EXACT_ROUTING_CP_SAT_WORKERS"] = str(ROUTING_WORKERS)
    environment["PYTHONHASHSEED"] = "0"
    return environment


def _run_batch(output_dir: Path) -> int:
    manifest = _load_manifest()
    frozen = _load_frozen_inputs(manifest)
    _assert_protocol_ancestor()
    _assert_clean_environment()
    excluded_receipts = _validate_excluded_candidates(manifest, frozen)

    admission = []
    normalized_seen: set[str] = set()
    for record in manifest["records"]:
        try:
            layout = _load_layout(record, manifest, frozen)
            if layout.normalized_sha256 in normalized_seen:
                raise IneligibleInput(
                    f"duplicate normalized digest in admitted corpus: {layout.normalized_sha256}"
                )
            normalized_seen.add(layout.normalized_sha256)
            admission.append(
                {
                    "layout_id": record["id"],
                    "status": "ADMITTED",
                    "normalized_sha256": layout.normalized_sha256,
                }
            )
        except Exception as exc:  # noqa: BLE001 - admission receipt must preserve failure
            admission.append(
                {
                    "layout_id": record["id"],
                    "status": "INELIGIBLE_INPUT",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    _write_json(
        output_dir / "CORPUS_ADMISSION.json",
        {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_admission_v1",
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "admitted_records": admission,
            "excluded_records": excluded_receipts,
        },
    )
    if any(item["status"] != "ADMITTED" for item in admission):
        return 2

    layout_dir = output_dir / "layouts"
    log_dir = output_dir / "layout_logs"
    layout_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()
    environment = _child_environment()

    for record in manifest["records"]:
        layout_id = str(record["id"])
        output_path = layout_dir / f"{layout_id}.json"
        log_path = log_dir / f"{layout_id}.log"
        command = [
            sys.executable,
            str(script),
            "layout",
            "--layout-id",
            layout_id,
            "--output",
            str(output_path),
        ]
        started = time.perf_counter()
        with log_path.open("w", encoding="utf-8") as log_handle:
            log_handle.write(f"command={command!r}\n")
            log_handle.flush()
            try:
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=environment,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=LAYOUT_WATCHDOG_SECONDS,
                    text=True,
                )
            except subprocess.TimeoutExpired:
                _write_json(output_path, _synthetic_timeout_result(record))
                log_handle.write(
                    f"watchdog_timeout_seconds={LAYOUT_WATCHDOG_SECONDS}\n"
                )
            else:
                log_handle.write(f"child_exit_code={completed.returncode}\n")
                if completed.returncode != 0 and not output_path.is_file():
                    _write_json(
                        output_path,
                        _synthetic_error_result(
                            record,
                            f"child exited {completed.returncode} without receipt",
                        ),
                    )
            log_handle.write(f"parent_wall_seconds={time.perf_counter() - started:.6f}\n")

    injection_path = output_dir / "D2_INJECTED.json"
    injection_log = output_dir / "D2_INJECTED.log"
    injection_command = [
        sys.executable,
        str(script),
        "inject",
        "--layout-id",
        "POSTMEM-00",
        "--output",
        str(injection_path),
    ]
    with injection_log.open("w", encoding="utf-8") as log_handle:
        try:
            completed = subprocess.run(
                injection_command,
                cwd=ROOT,
                env=environment,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=INJECTED_WATCHDOG_SECONDS,
                text=True,
            )
        except subprocess.TimeoutExpired:
            _write_json(
                injection_path,
                {
                    "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
                    "layout_id": "POSTMEM-00",
                    "producer": "injected_selection_nogood",
                    "reachabilityFailureClass": "EFFECT_NO_TERMINAL",
                    "terminalOutcome": None,
                    "censorStatus": "WALL_TIMEOUT_END_TO_END",
                },
            )
        else:
            log_handle.write(f"child_exit_code={completed.returncode}\n")

    _aggregate(output_dir, manifest)
    return 0


def _validate_corpus() -> int:
    manifest = _load_manifest()
    frozen = _load_frozen_inputs(manifest)
    _assert_protocol_ancestor()
    _assert_clean_environment()
    excluded_receipts = _validate_excluded_candidates(manifest, frozen)
    seen: set[str] = set()
    records = []
    failures = 0
    for record in manifest["records"]:
        try:
            layout = _load_layout(record, manifest, frozen)
            if layout.normalized_sha256 in seen:
                raise IneligibleInput(f"duplicate normalized digest {layout.normalized_sha256}")
            seen.add(layout.normalized_sha256)
            records.append(
                {
                    "layout_id": record["id"],
                    "status": "ADMITTED",
                    "normalized_sha256": layout.normalized_sha256,
                    "ghost_rect": list(layout.ghost_rect),
                    "pose_id_remaps": layout.pose_id_remaps,
                }
            )
        except Exception as exc:  # noqa: BLE001 - CLI diagnosis
            failures += 1
            records.append(
                {
                    "layout_id": record["id"],
                    "status": "INELIGIBLE_INPUT",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    print(
        json.dumps(
            {"admitted_records": records, "excluded_records": excluded_receipts},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if failures else 0


def _run_layout_command(layout_id: str, output: Path) -> int:
    manifest = _load_manifest()
    frozen = _load_frozen_inputs(manifest)
    _assert_protocol_ancestor()
    _assert_clean_environment()
    record = _record_by_id(manifest, layout_id)
    try:
        layout = _load_layout(record, manifest, frozen)
        result = _run_layout(layout, frozen)
    except IneligibleInput as exc:
        result = {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_layout_v1",
            "research_only": True,
            "protocol_freeze_commit": PROTOCOL_FREEZE_COMMIT,
            "repository_head": _git("rev-parse", "HEAD"),
            "layout_id": layout_id,
            "stratum": record["stratum"],
            "split": record["role"],
            "terminalStatus": "UNKNOWN",
            "censorStatus": "INELIGIBLE_INPUT",
            "finalReason": "unknown_other",
            "events": [],
            "d2_organic_receipts": [],
            "error": str(exc),
        }
    except ProtocolViolation:
        raise
    except Exception as exc:  # noqa: BLE001 - research receipt preserves traceback
        result = _synthetic_error_result(record, f"{type(exc).__name__}: {exc}")
        result["traceback"] = traceback.format_exc()
    _write_json(output, result)
    print(json.dumps({"layout_id": layout_id, "receipt": str(output)}, ensure_ascii=False))
    return 0


def _run_injected_command(layout_id: str, output: Path) -> int:
    manifest = _load_manifest()
    frozen = _load_frozen_inputs(manifest)
    _assert_protocol_ancestor()
    _assert_clean_environment()
    record = _record_by_id(manifest, layout_id)
    try:
        layout = _load_layout(record, manifest, frozen)
        result = _run_injected(layout, frozen)
    except Exception as exc:  # noqa: BLE001 - preserve injected failure
        result = {
            "schema_version": "zmd_reasoning_outer_loop_phase_minus1_injected_v1",
            "layout_id": layout_id,
            "producer": "injected_selection_nogood",
            "reachabilityFailureClass": "NOT_REACHED",
            "terminalOutcome": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    _write_json(output, result)
    print(json.dumps({"layout_id": layout_id, "receipt": str(output)}, ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the frozen corpus without solving")

    layout = subparsers.add_parser("layout", help="run one fixed layout")
    layout.add_argument("--layout-id", required=True)
    layout.add_argument("--output", type=Path, required=True)

    inject = subparsers.add_parser("inject", help="run the D2 injected feedback canary")
    inject.add_argument("--layout-id", required=True)
    inject.add_argument("--output", type=Path, required=True)

    batch = subparsers.add_parser("batch", help="run all frozen layouts and aggregate")
    batch.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        return _validate_corpus()
    if args.command == "layout":
        return _run_layout_command(args.layout_id, args.output.resolve())
    if args.command == "inject":
        return _run_injected_command(args.layout_id, args.output.resolve())
    if args.command == "batch":
        return _run_batch(args.output_dir.resolve())
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
