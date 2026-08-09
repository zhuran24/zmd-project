"""Neutral normalized-catalog contract.

The exact solver keeps consuming the current frozen preprocess artifacts. This
module introduces a snapshot-friendly, additive contract for future adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

NORMALIZED_CATALOG_VERSION = "0.1.0"
_VALID_DIRECTIONS = {"N", "E", "S", "W"}
_DIRECTION_ORDER = {"N": 0, "E": 1, "S": 2, "W": 3}


@dataclass(frozen=True)
class NormalizedCatalog:
    payload: dict[str, Any]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "NormalizedCatalog":
        return cls(normalize_catalog_payload(payload))

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.payload, ensure_ascii=False))

    def stable_hash(self) -> str:
        return catalog_stable_hash(self.payload)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_catalog_metadata(
    *,
    source: str,
    generated_at: str | None = None,
    source_version: str | None = None,
    source_commit: str | None = None,
    source_license: str | None = None,
    notes: Sequence[Any] | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "version": NORMALIZED_CATALOG_VERSION,
        "source": str(source),
        "generated_at": generated_at or _now_iso(),
    }
    if source_version is not None:
        metadata["source_version"] = str(source_version)
    if source_commit is not None:
        metadata["source_commit"] = str(source_commit)
    if source_license is not None:
        metadata["source_license"] = str(source_license)
    if notes is not None:
        metadata["notes"] = [str(note) for note in notes]
    if extensions is not None:
        metadata["extensions"] = dict(extensions)
    return metadata


def normalize_catalog_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("normalized catalog payload must be a mapping")

    metadata = _normalize_metadata(payload.get("metadata"))
    items = [_normalize_item(item) for item in _ensure_list(payload.get("items"))]
    recipes = [_normalize_recipe(recipe) for recipe in _ensure_list(payload.get("recipes"))]
    facilities = [_normalize_facility(facility) for facility in _ensure_list(payload.get("facilities"))]
    power = [_normalize_power_entry(entry) for entry in _ensure_list(payload.get("power"))]
    port_rules = [_normalize_port_rule(rule) for rule in _ensure_list(payload.get("port_rules"))]

    items.sort(key=lambda item: item["id"])
    recipes.sort(key=lambda recipe: recipe["id"])
    facilities.sort(key=lambda facility: facility["id"])
    power.sort(key=lambda entry: (entry["facility_id"], entry["mode"], entry["value_kw"]))
    port_rules.sort(key=lambda rule: rule["id"])

    return {
        "metadata": metadata,
        "items": items,
        "recipes": recipes,
        "facilities": facilities,
        "power": power,
        "port_rules": port_rules,
    }


def build_catalog_from_rules_payload(
    rules_payload: Mapping[str, Any],
    *,
    source: str = "current_repository_rules",
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(rules_payload, Mapping):
        raise TypeError("rules payload must be a mapping")

    globals_payload = rules_payload.get("globals") if isinstance(rules_payload.get("globals"), Mapping) else {}
    time_payload = globals_payload.get("time") if isinstance(globals_payload.get("time"), Mapping) else {}
    tick_interval_seconds = float(time_payload.get("tick_interval_seconds", 2.0))

    facility_templates = rules_payload.get("facility_templates") if isinstance(rules_payload.get("facility_templates"), Mapping) else {}
    recipes_payload = rules_payload.get("recipes") if isinstance(rules_payload.get("recipes"), Mapping) else {}

    item_ids: set[str] = set()
    recipes: list[dict[str, Any]] = []
    for recipe_id, raw_recipe in recipes_payload.items():
        if not isinstance(raw_recipe, Mapping):
            continue
        inputs = _normalize_flow_entries(raw_recipe.get("inputs"), default_amount=0.0)
        outputs = _normalize_flow_entries(raw_recipe.get("outputs"), default_amount=0.0)
        for flow in inputs + outputs:
            item_ids.add(flow["item_id"])
        recipes.append(
            {
                "id": str(recipe_id),
                "name": str(recipe_id),
                "facility_type": str(raw_recipe.get("template", "unknown")),
                "cycle_seconds": float(raw_recipe.get("ticks_per_cycle", 1.0)) * tick_interval_seconds,
                "inputs": inputs,
                "outputs": outputs,
                "power": {"consumption_kw": 0.0, "generation_kw": 0.0},
                "metadata": {},
            }
        )

    items = [
        {
            "id": item_id,
            "name": item_id,
            "category": "recipe_commodity",
            "unit": "item",
            "aliases": [],
            "metadata": {},
        }
        for item_id in sorted(item_ids)
    ]

    facilities: list[dict[str, Any]] = []
    port_rules: list[dict[str, Any]] = []
    seen_port_rules: set[str] = set()
    for facility_id, raw_facility in facility_templates.items():
        if not isinstance(raw_facility, Mapping):
            continue
        dimensions = raw_facility.get("dimensions") if isinstance(raw_facility.get("dimensions"), Mapping) else {}
        port_rule = str(raw_facility.get("port_rule", "none"))
        facilities.append(
            {
                "id": str(facility_id),
                "name": str(facility_id),
                "footprint": {
                    "w": int(dimensions.get("w", 1)),
                    "h": int(dimensions.get("h", 1)),
                },
                "rotatable": bool(raw_facility.get("rotatable", False)),
                "needs_power": bool(raw_facility.get("needs_power", False)),
                "power": {"consumption_kw": 0.0, "generation_kw": 0.0},
                "port_rule": port_rule,
                "metadata": {
                    "placement_rule": raw_facility.get("placement_rule"),
                    "core_limits": raw_facility.get("core_limits"),
                    "power_coverage_radius": raw_facility.get("power_coverage_radius"),
                    "is_solid_z": bool(raw_facility.get("is_solid_z", True)),
                },
            }
        )
        if port_rule not in seen_port_rules:
            seen_port_rules.add(port_rule)
            input_sides, output_sides = _infer_port_rule_sides(port_rule)
            port_rules.append(
                {
                    "id": port_rule,
                    "description": port_rule,
                    "input_sides": input_sides,
                    "output_sides": output_sides,
                    "restrictions": {
                        key: value
                        for key, value in {
                            "placement_rule": raw_facility.get("placement_rule"),
                            "core_limits": raw_facility.get("core_limits"),
                        }.items()
                        if value is not None
                    },
                    "metadata": {},
                }
            )

    rules_metadata = rules_payload.get("metadata") if isinstance(rules_payload.get("metadata"), Mapping) else {}
    metadata = build_catalog_metadata(
        source=source,
        generated_at=generated_at,
        source_version=str(rules_metadata.get("version", NORMALIZED_CATALOG_VERSION)),
        notes=[
            "Built from rules/canonical_rules.json without altering the certified exact path.",
            "Frozen preprocess artifacts remain the certified runtime source of truth.",
        ],
    )
    return normalize_catalog_payload(
        {
            "metadata": metadata,
            "items": items,
            "recipes": recipes,
            "facilities": facilities,
            "power": [],
            "port_rules": port_rules,
        }
    )


def catalog_stable_hash(payload: Mapping[str, Any]) -> str:
    normalized = normalize_catalog_payload(payload)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_metadata(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("catalog metadata must be a mapping")
    source = str(raw.get("source", "")).strip()
    generated_at = str(raw.get("generated_at", "")).strip()
    if not source:
        raise ValueError("catalog metadata.source is required")
    if not generated_at:
        raise ValueError("catalog metadata.generated_at is required")
    metadata = {
        "version": str(raw.get("version", NORMALIZED_CATALOG_VERSION)),
        "source": source,
        "generated_at": generated_at,
    }
    for optional_key in ("source_version", "source_commit", "source_license"):
        if raw.get(optional_key) is not None:
            metadata[optional_key] = str(raw.get(optional_key))
    notes = raw.get("notes")
    if notes is not None:
        metadata["notes"] = [str(note) for note in _ensure_list(notes)]
    extensions = raw.get("extensions")
    if isinstance(extensions, Mapping):
        metadata["extensions"] = dict(extensions)
    return metadata


def _normalize_item(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("catalog item must be a mapping")
    item_id = str(raw.get("id", "")).strip()
    if not item_id:
        raise ValueError("catalog item id is required")
    aliases = sorted({str(alias) for alias in _ensure_list(raw.get("aliases"))})
    metadata = dict(raw.get("metadata", {})) if isinstance(raw.get("metadata"), Mapping) else {}
    return {
        "id": item_id,
        "name": str(raw.get("name", item_id)),
        "category": str(raw.get("category", "unknown")),
        "unit": str(raw.get("unit", "item")),
        "aliases": aliases,
        "metadata": metadata,
    }


def _normalize_recipe(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("catalog recipe must be a mapping")
    recipe_id = str(raw.get("id", "")).strip()
    if not recipe_id:
        raise ValueError("catalog recipe id is required")
    cycle_seconds = float(raw.get("cycle_seconds", 0.0))
    if cycle_seconds <= 0.0:
        raise ValueError("catalog recipe cycle_seconds must be positive")
    return {
        "id": recipe_id,
        "name": str(raw.get("name", recipe_id)),
        "facility_type": str(raw.get("facility_type", "unknown")),
        "cycle_seconds": round(cycle_seconds, 6),
        "inputs": _normalize_flow_entries(raw.get("inputs"), default_amount=0.0),
        "outputs": _normalize_flow_entries(raw.get("outputs"), default_amount=0.0),
        "power": _normalize_power_mapping(raw.get("power")),
        "metadata": dict(raw.get("metadata", {})) if isinstance(raw.get("metadata"), Mapping) else {},
    }


def _normalize_facility(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("catalog facility must be a mapping")
    facility_id = str(raw.get("id", "")).strip()
    if not facility_id:
        raise ValueError("catalog facility id is required")
    footprint = raw.get("footprint")
    if not isinstance(footprint, Mapping):
        raise ValueError("catalog facility footprint must be a mapping")
    return {
        "id": facility_id,
        "name": str(raw.get("name", facility_id)),
        "footprint": {
            "w": int(footprint.get("w", 1)),
            "h": int(footprint.get("h", 1)),
        },
        "rotatable": bool(raw.get("rotatable", False)),
        "needs_power": bool(raw.get("needs_power", False)),
        "power": _normalize_power_mapping(raw.get("power")),
        "port_rule": str(raw.get("port_rule", "none")),
        "metadata": dict(raw.get("metadata", {})) if isinstance(raw.get("metadata"), Mapping) else {},
    }


def _normalize_power_entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("catalog power entry must be a mapping")
    facility_id = str(raw.get("facility_id", "")).strip()
    mode = str(raw.get("mode", "")).strip().lower()
    if not facility_id:
        raise ValueError("catalog power entry facility_id is required")
    if mode not in {"consume", "generate"}:
        raise ValueError("catalog power entry mode must be 'consume' or 'generate'")
    return {
        "facility_id": facility_id,
        "mode": mode,
        "value_kw": round(float(raw.get("value_kw", 0.0)), 6),
        "metadata": dict(raw.get("metadata", {})) if isinstance(raw.get("metadata"), Mapping) else {},
    }


def _normalize_port_rule(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("catalog port rule must be a mapping")
    rule_id = str(raw.get("id", "")).strip()
    if not rule_id:
        raise ValueError("catalog port rule id is required")
    return {
        "id": rule_id,
        "description": str(raw.get("description", rule_id)),
        "input_sides": _normalize_direction_values(raw.get("input_sides")),
        "output_sides": _normalize_direction_values(raw.get("output_sides")),
        "restrictions": dict(raw.get("restrictions", {})) if isinstance(raw.get("restrictions"), Mapping) else {},
        "metadata": dict(raw.get("metadata", {})) if isinstance(raw.get("metadata"), Mapping) else {},
    }


def _normalize_power_mapping(raw: Any) -> dict[str, float]:
    if raw is None:
        return {"consumption_kw": 0.0, "generation_kw": 0.0}
    if not isinstance(raw, Mapping):
        raise ValueError("catalog power mapping must be a mapping")
    return {
        "consumption_kw": round(float(raw.get("consumption_kw", 0.0)), 6),
        "generation_kw": round(float(raw.get("generation_kw", 0.0)), 6),
    }


def _normalize_flow_entries(raw: Any, *, default_amount: float) -> list[dict[str, Any]]:
    if raw is None:
        raw_entries: list[Any] = []
    elif isinstance(raw, Mapping):
        raw_entries = [{"item_id": str(item_id), "amount": amount} for item_id, amount in raw.items()]
    elif isinstance(raw, list):
        raw_entries = list(raw)
    else:
        raise ValueError("catalog recipe flows must be a list or mapping")

    normalized: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, Mapping):
            raise ValueError("catalog recipe flow entry must be a mapping")
        item_id = str(entry.get("item_id", entry.get("id", ""))).strip()
        if not item_id:
            raise ValueError("catalog recipe flow item_id is required")
        normalized.append({"item_id": item_id, "amount": round(float(entry.get("amount", default_amount)), 6)})
    normalized.sort(key=lambda entry: (entry["item_id"], entry["amount"]))
    return normalized


def _normalize_direction_values(raw: Any) -> list[str]:
    values: list[str] = []
    for value in _ensure_list(raw):
        direction = str(value).upper()
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(f"invalid direction: {direction}")
        values.append(direction)
    return sorted(set(values), key=lambda direction: _DIRECTION_ORDER[direction])


def _infer_port_rule_sides(port_rule: str) -> tuple[list[str], list[str]]:
    if port_rule in {"opposite_parallel_sides", "long_sides"}:
        return ["N", "S"], ["N", "S"]
    if port_rule == "core_specific":
        return ["N", "S", "E", "W"], ["N", "S", "E", "W"]
    if port_rule == "omni_wireless":
        return ["N", "S", "E", "W"], ["N", "S", "E", "W"]
    if port_rule == "inward_facing":
        return ["N", "W"], ["E", "S"]
    return [], []


def _ensure_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, tuple):
        return list(raw)
    raise ValueError("expected a list-like value")
