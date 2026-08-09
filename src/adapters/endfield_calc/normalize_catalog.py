"""Normalization helpers for endfield-calc-like snapshot payloads."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.adapters.endfield_calc.provenance import build_endfield_calc_catalog_metadata
from src.interchange.normalized_catalog import normalize_catalog_payload


def build_normalized_catalog_from_snapshot_payload(
    *,
    items: Sequence[Mapping[str, Any]],
    recipes: Sequence[Mapping[str, Any]],
    facilities: Sequence[Mapping[str, Any]],
    snapshot_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot_metadata = dict(snapshot_metadata or {})
    tick_interval_seconds = float(snapshot_metadata.get("tick_interval_seconds", 2.0))

    normalized_items = [_normalize_item_entry(item) for item in items]
    normalized_recipes = [
        _normalize_recipe_entry(recipe, tick_interval_seconds=tick_interval_seconds)
        for recipe in recipes
    ]
    normalized_facilities = [_normalize_facility_entry(facility) for facility in facilities]
    port_rules = _derive_port_rules(normalized_facilities)

    return normalize_catalog_payload(
        {
            "metadata": build_endfield_calc_catalog_metadata(snapshot_metadata),
            "items": normalized_items,
            "recipes": normalized_recipes,
            "facilities": normalized_facilities,
            "power": _build_power_entries(normalized_facilities, normalized_recipes),
            "port_rules": port_rules,
        }
    )


def _normalize_item_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    item_id = _first_present(raw, "id", "key", "itemId", "item_id", required=True)
    name = _first_present(raw, "name", "label", "displayName", default=item_id)
    inferred_category = "liquid" if bool(raw.get("isLiquid", False)) else "unknown"
    category = _first_present(raw, "category", "group", "type", default=inferred_category)
    aliases = raw.get("aliases", [])
    if not isinstance(aliases, list):
        aliases = [aliases] if aliases else []
    metadata = {
        key: value
        for key, value in raw.items()
        if key not in {"id", "key", "itemId", "item_id", "name", "label", "displayName", "category", "group", "type", "aliases"}
    }
    return {
        "id": str(item_id),
        "name": str(name),
        "category": str(category),
        "unit": str(raw.get("unit", "item")),
        "aliases": sorted({str(alias) for alias in aliases}),
        "metadata": metadata,
    }


def _normalize_recipe_entry(raw: Mapping[str, Any], *, tick_interval_seconds: float) -> dict[str, Any]:
    recipe_id = _first_present(raw, "id", "key", "recipeId", "recipe_id", required=True)
    cycle_seconds = _resolve_cycle_seconds(raw, tick_interval_seconds=tick_interval_seconds)
    metadata = {
        key: value
        for key, value in raw.items()
        if key not in {
            "id", "key", "recipeId", "recipe_id",
            "name", "label", "displayName",
            "facility_type", "facilityType", "facilityId", "machine", "template",
            "cycle_seconds", "cycleSeconds", "ticks_per_cycle", "ticksPerCycle", "duration", "craftingTime",
            "inputs", "input", "outputs", "output",
            "power", "power_kw", "powerConsumption", "power_consumption_kw", "powerGeneration", "power_generation_kw",
        }
    }
    return {
        "id": str(recipe_id),
        "name": str(_first_present(raw, "name", "label", "displayName", default=recipe_id)),
        "facility_type": str(
            _first_present(
                raw,
                "facility_type",
                "facilityType",
                "facilityId",
                "machine",
                "template",
                default="unknown",
            )
        ),
        "cycle_seconds": cycle_seconds,
        "inputs": _normalize_flow_list(raw.get("inputs", raw.get("input"))),
        "outputs": _normalize_flow_list(raw.get("outputs", raw.get("output"))),
        "power": {
            "consumption_kw": float(_first_present(raw, "powerConsumption", "power_consumption_kw", "power_kw", default=0.0)),
            "generation_kw": float(_first_present(raw, "powerGeneration", "power_generation_kw", default=0.0)),
        },
        "metadata": metadata,
    }


def _normalize_facility_entry(raw: Mapping[str, Any]) -> dict[str, Any]:
    facility_id = _first_present(raw, "id", "key", "facilityId", "facility_id", required=True)
    footprint = raw.get("footprint")
    if not isinstance(footprint, Mapping):
        footprint = raw.get("size") if isinstance(raw.get("size"), Mapping) else raw.get("dimensions")
    if not isinstance(footprint, Mapping):
        footprint = {
            "w": raw.get("width", 1),
            "h": raw.get("height", 1),
        }
    metadata = {
        key: value
        for key, value in raw.items()
        if key not in {
            "id", "key", "facilityId", "facility_id",
            "name", "label", "displayName",
            "footprint", "size", "dimensions", "width", "height",
            "rotatable", "needs_power", "needsPower", "port_rule", "portRule",
            "power", "power_kw", "powerGeneration", "powerConsumption", "tier",
        }
    }
    return {
        "id": str(facility_id),
        "name": str(_first_present(raw, "name", "label", "displayName", default=facility_id)),
        "footprint": {
            "w": int(footprint.get("w", footprint.get("width", 1))),
            "h": int(footprint.get("h", footprint.get("height", 1))),
        },
        "rotatable": bool(raw.get("rotatable", True)),
        "needs_power": bool(raw.get("needs_power", raw.get("needsPower", (_first_present(raw, "powerConsumption", "power_kw", default=0.0) or _first_present(raw, "powerGeneration", default=0.0)) != 0.0))),
        "power": {
            "consumption_kw": float(_first_present(raw, "powerConsumption", "power_kw", default=0.0)),
            "generation_kw": float(_first_present(raw, "powerGeneration", default=0.0)),
        },
        "port_rule": str(_first_present(raw, "port_rule", "portRule", default="none")),
        "metadata": metadata,
    }


def _normalize_flow_list(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, Mapping):
        entries = [{"item_id": item_id, "amount": amount} for item_id, amount in raw.items()]
    elif isinstance(raw, list):
        entries = list(raw)
    else:
        raise ValueError("snapshot flow payload must be a list or mapping")

    normalized = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("snapshot flow entry must be a mapping")
        item_id = _first_present(entry, "item_id", "itemId", "id", required=True)
        amount = float(_first_present(entry, "amount", "value", "count", default=0.0))
        normalized.append({"item_id": str(item_id), "amount": amount})
    normalized.sort(key=lambda entry: (entry["item_id"], entry["amount"]))
    return normalized


def _resolve_cycle_seconds(raw: Mapping[str, Any], *, tick_interval_seconds: float) -> float:
    if raw.get("cycle_seconds") is not None:
        return round(float(raw["cycle_seconds"]), 6)
    if raw.get("cycleSeconds") is not None:
        return round(float(raw["cycleSeconds"]), 6)
    if raw.get("ticks_per_cycle") is not None:
        return round(float(raw["ticks_per_cycle"]) * tick_interval_seconds, 6)
    if raw.get("ticksPerCycle") is not None:
        return round(float(raw["ticksPerCycle"]) * tick_interval_seconds, 6)
    if raw.get("duration") is not None:
        return round(float(raw["duration"]) * tick_interval_seconds, 6)
    if raw.get("craftingTime") is not None:
        return round(float(raw["craftingTime"]), 6)
    raise ValueError("snapshot recipe is missing cycle information")


def _derive_port_rules(facilities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for facility in facilities:
        port_rule = str(facility.get("port_rule", "none"))
        if port_rule in rules:
            continue
        input_sides, output_sides = _port_rule_sides(port_rule)
        rules[port_rule] = {
            "id": port_rule,
            "description": port_rule,
            "input_sides": input_sides,
            "output_sides": output_sides,
            "restrictions": {},
            "metadata": {},
        }
    return [rules[key] for key in sorted(rules.keys())]


def _build_power_entries(
    facilities: Sequence[Mapping[str, Any]],
    recipes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    power_entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float]] = set()
    for facility in facilities:
        facility_id = str(facility.get("id", ""))
        facility_power = facility.get("power", {}) if isinstance(facility.get("power"), Mapping) else {}
        for mode, key in (("consume", "consumption_kw"), ("generate", "generation_kw")):
            value = round(float(facility_power.get(key, 0.0)), 6)
            if value == 0.0:
                continue
            signature = (facility_id, mode, value)
            if signature in seen:
                continue
            seen.add(signature)
            power_entries.append({"facility_id": facility_id, "mode": mode, "value_kw": value, "metadata": {"source": "facility"}})
    for recipe in recipes:
        facility_id = str(recipe.get("facility_type", ""))
        recipe_power = recipe.get("power", {}) if isinstance(recipe.get("power"), Mapping) else {}
        value = round(float(recipe_power.get("consumption_kw", 0.0)), 6)
        if value == 0.0:
            continue
        signature = (facility_id, "consume", value)
        if signature in seen:
            continue
        seen.add(signature)
        power_entries.append({"facility_id": facility_id, "mode": "consume", "value_kw": value, "metadata": {"source": "recipe"}})
    power_entries.sort(key=lambda entry: (entry["facility_id"], entry["mode"], entry["value_kw"]))
    return power_entries


def _port_rule_sides(port_rule: str) -> tuple[list[str], list[str]]:
    if port_rule in {"opposite_parallel_sides", "long_sides"}:
        return ["N", "S"], ["N", "S"]
    if port_rule in {"omni", "omni_wireless"}:
        return ["N", "E", "S", "W"], ["N", "E", "S", "W"]
    if port_rule in {"core_specific", "core"}:
        return ["N", "E", "S", "W"], ["N", "E", "S", "W"]
    return [], []


def _first_present(raw: Mapping[str, Any], *keys: str, default: Any = None, required: bool = False) -> Any:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    if required:
        raise ValueError(f"missing required keys: {keys!r}")
    return default
