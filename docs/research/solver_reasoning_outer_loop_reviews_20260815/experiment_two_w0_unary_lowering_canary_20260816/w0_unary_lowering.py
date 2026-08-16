#!/usr/bin/env python3
"""Research-only W0 unary lowering.

The module does not modify production source or register a generic compiler.
It consumes one pinned lowering spec and appends exactly one unit equality to an
already-built ``PortBindingModel``. The independent contract checker audits the
actual CpModel proto delta rather than trusting this module's receipt.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class LoweringError(RuntimeError):
    """The pinned W0 lowering cannot be applied exactly."""


def load_lowering_spec(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LoweringError(f"cannot read lowering spec {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LoweringError("lowering spec must be a JSON object")
    if value.get("schema_version") != "zmd_w0_unary_lowering_spec_v1":
        raise LoweringError("unexpected lowering spec schema")
    if value.get("research_only") is not True:
        raise LoweringError("lowering spec lost research_only=true")
    return value


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def protobuf_sha256(message: Any) -> str:
    """Hash OR-Tools' deterministic text-format view of a pybind proto wrapper."""

    return hashlib.sha256(str(message).encode("utf-8")).hexdigest()


def trigger_is_active(selection: Mapping[str, Any], spec: Mapping[str, Any]) -> bool:
    trigger = spec["trigger"]
    slot_id = str(trigger["slot_id"])
    inactive_value = str(trigger["inactive_value"])
    outputs = selection.get("generic_outputs")
    if not isinstance(outputs, Mapping):
        raise LoweringError("binding selection lacks generic_outputs mapping")
    if slot_id not in outputs:
        raise LoweringError(f"binding selection lacks target slot {slot_id}")
    return str(outputs[slot_id]) != inactive_value


def target_domain_envelope(binding_model: Any, spec: Mapping[str, Any]) -> dict[str, Any]:
    trigger = spec["trigger"]
    slot_id = str(trigger["slot_id"])
    inactive_value = str(trigger["inactive_value"])
    slot_vars = binding_model.generic_output_vars.get(slot_id)
    if not isinstance(slot_vars, Mapping):
        raise LoweringError(f"target slot is absent from built binding model: {slot_id}")
    labels = sorted(str(value) for value in slot_vars)
    expected = sorted(str(value) for value in trigger["expected_baseline_domain"])
    if labels != expected:
        raise LoweringError(
            f"target domain drift: expected {expected}, observed {labels}"
        )
    active_labels = [value for value in labels if value != inactive_value]
    return {
        "slot_id": slot_id,
        "domain_labels": labels,
        "domain_cardinality": len(labels),
        "inactive_value": inactive_value,
        "active_labels": active_labels,
        "active_value_count": len(active_labels),
    }


def apply_w0_unary_lowering(binding_model: Any, spec: Mapping[str, Any]) -> dict[str, Any]:
    """Append the single W0 unit constraint and return a non-authoritative receipt."""

    lowering = spec["lowering"]
    trigger = spec["trigger"]
    if lowering.get("kind") != "force_generic_output_slot_value":
        raise LoweringError("unsupported lowering kind")
    slot_id = str(lowering["slot_id"])
    forced_value = str(lowering["forced_value"])
    if slot_id != str(trigger["slot_id"]):
        raise LoweringError("lowering slot does not match theorem trigger")
    if forced_value != str(trigger["inactive_value"]):
        raise LoweringError("lowering does not force the theorem's inactive value")

    envelope_before = target_domain_envelope(binding_model, spec)
    slot_vars = binding_model.generic_output_vars[slot_id]
    if forced_value not in slot_vars:
        raise LoweringError(f"forced value is absent from target domain: {forced_value}")

    proto_before = binding_model.model.Proto()
    variable_count_before = len(proto_before.variables)
    constraint_count_before = len(proto_before.constraints)
    search_strategy_before = [protobuf_sha256(item) for item in proto_before.search_strategy]

    target_var = slot_vars[forced_value]
    binding_model.model.Add(target_var == 1)

    proto_after = binding_model.model.Proto()
    return {
        "schema_version": "zmd_w0_unary_lowering_application_receipt_v1",
        "research_only": True,
        "judgment_id": spec["judgment"]["id"],
        "contextHash": spec["judgment"]["contextHash"],
        "slot_id": slot_id,
        "forced_value": forced_value,
        "target_variable_index": int(target_var.Index()),
        "target_variable_name": str(target_var.Name()),
        "target_domain_before": envelope_before,
        "variable_count_before": variable_count_before,
        "variable_count_after": len(proto_after.variables),
        "constraint_count_before": constraint_count_before,
        "constraint_count_after": len(proto_after.constraints),
        "new_constraint_count": len(proto_after.constraints) - constraint_count_before,
        "objective_present_before": bool(proto_before.has_objective()),
        "objective_present_after": bool(proto_after.has_objective()),
        "search_strategy_sha256_before": search_strategy_before,
        "search_strategy_sha256_after": [
            protobuf_sha256(item) for item in proto_after.search_strategy
        ],
        "model_proto_sha256_after": protobuf_sha256(proto_after),
        "authority": "non_authoritative_implementation_receipt",
    }
