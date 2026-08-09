"""Commodity translation and precise recipe/device inference for IndustrialPlanner export."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.adapters.endfield_calc.semantic_mapping import (
    SemanticRegistry,
    current_repository_semantic_registry,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CANONICAL_RULES_PATH = _PROJECT_ROOT / "rules" / "canonical_rules.json"
_ITEM_REGISTRY_PATH = Path(__file__).resolve().parent / "item_registry.json"


@dataclass(frozen=True)
class CommodityTranslationResult:
    raw_item_id: str
    translated_item_id: str | None
    source_namespace: str
    warnings: tuple[str, ...] = ()
    is_translation_miss: bool = False
    is_registry_passthrough: bool = False


@dataclass(frozen=True)
class CommoditySetTranslation:
    translated_item_ids: frozenset[str]
    warnings: tuple[str, ...] = ()
    translation_miss_count: int = 0


@dataclass(frozen=True)
class ConfigTranslationAudit:
    translated_config: dict[str, Any]
    warnings: tuple[str, ...] = ()
    translation_miss_count: int = 0
    dropped_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateRecipeResolution:
    canonical_recipe_id: str
    upstream_recipe_id: str
    upstream_facility_id: str
    canonical_facility_type: str
    translated_input_ids: frozenset[str]
    translated_output_ids: frozenset[str]


@dataclass(frozen=True)
class FacilityRecipeResolution:
    resolved: bool
    upstream_facility_id: str | None
    resolved_recipe_id: str | None
    resolution_mode: str
    reason: str
    warnings: tuple[str, ...] = ()
    translated_input_ids: tuple[str, ...] = ()
    translated_output_ids: tuple[str, ...] = ()
    translation_miss_count: int = 0


@lru_cache(maxsize=1)
def canonical_rules_payload() -> dict[str, Any]:
    return json.loads(_CANONICAL_RULES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def valid_upstream_item_ids() -> frozenset[str]:
    payload = json.loads(_ITEM_REGISTRY_PATH.read_text(encoding="utf-8"))
    item_entries = payload.get("items") if isinstance(payload.get("items"), list) else []
    return frozenset(
        str(entry.get("id", "")).strip()
        for entry in item_entries
        if isinstance(entry, Mapping) and str(entry.get("id", "")).strip()
    )


@lru_cache(maxsize=1)
def candidate_recipe_library() -> tuple[CandidateRecipeResolution, ...]:
    semantic_registry = current_repository_semantic_registry()
    rules_payload = canonical_rules_payload()
    recipe_rules = rules_payload.get("recipes") if isinstance(rules_payload.get("recipes"), Mapping) else {}

    item_by_canonical = {mapping.canonical_id: mapping for mapping in semantic_registry.item_mappings}
    candidates: list[CandidateRecipeResolution] = []
    for mapping in semantic_registry.recipe_mappings:
        canonical_rule = recipe_rules.get(mapping.canonical_id)
        if not isinstance(canonical_rule, Mapping):
            continue

        inputs_raw = canonical_rule.get("inputs") if isinstance(canonical_rule.get("inputs"), Mapping) else {}
        outputs_raw = canonical_rule.get("outputs") if isinstance(canonical_rule.get("outputs"), Mapping) else {}
        translated_inputs = frozenset(
            item_by_canonical[item_id].upstream_id
            for item_id in inputs_raw.keys()
            if item_id in item_by_canonical
        )
        translated_outputs = frozenset(
            item_by_canonical[item_id].upstream_id
            for item_id in outputs_raw.keys()
            if item_id in item_by_canonical
        )
        candidates.append(
            CandidateRecipeResolution(
                canonical_recipe_id=mapping.canonical_id,
                upstream_recipe_id=mapping.upstream_id,
                upstream_facility_id=mapping.upstream_facility_id,
                canonical_facility_type=mapping.canonical_facility_type,
                translated_input_ids=translated_inputs,
                translated_output_ids=translated_outputs,
            )
        )
    return tuple(candidates)


@lru_cache(maxsize=1)
def upstream_item_id_hints() -> frozenset[str]:
    semantic_registry = current_repository_semantic_registry()
    values = {mapping.upstream_id for mapping in semantic_registry.item_mappings}
    return frozenset(values)


@lru_cache(maxsize=1)
def facility_group_by_canonical_id() -> dict[str, tuple[str, ...]]:
    semantic_registry = current_repository_semantic_registry()
    return {
        group.canonical_id: tuple(group.upstream_ids)
        for group in semantic_registry.facility_groups
    }


def _semantic_item_maps(semantic_registry: SemanticRegistry) -> tuple[dict[str, Any], dict[str, Any]]:
    by_canonical = {mapping.canonical_id: mapping for mapping in semantic_registry.item_mappings}
    by_upstream = {mapping.upstream_id: mapping for mapping in semantic_registry.item_mappings}
    return by_canonical, by_upstream


def _normalize_commodity_token(raw_item_id: Any) -> str:
    if raw_item_id is None:
        return ""
    return str(raw_item_id).strip()


def translate_canonical_item_id(
    raw_item_id: Any,
    *,
    semantic_registry: SemanticRegistry | None = None,
    allow_upstream_passthrough: bool = True,
) -> CommodityTranslationResult:
    semantic_registry = semantic_registry or current_repository_semantic_registry()
    normalized = _normalize_commodity_token(raw_item_id)
    if not normalized:
        return CommodityTranslationResult(
            raw_item_id=normalized,
            translated_item_id=None,
            source_namespace="empty",
            warnings=("empty commodity id cannot be translated",),
            is_translation_miss=True,
        )
    if normalized == "[TBD]":
        return CommodityTranslationResult(
            raw_item_id=normalized,
            translated_item_id=None,
            source_namespace="placeholder",
            warnings=("placeholder commodity [TBD] cannot be translated",),
            is_translation_miss=True,
        )

    by_canonical, by_upstream = _semantic_item_maps(semantic_registry)
    if normalized in by_canonical:
        return CommodityTranslationResult(
            raw_item_id=normalized,
            translated_item_id=by_canonical[normalized].upstream_id,
            source_namespace="canonical",
        )

    if normalized in by_upstream:
        return CommodityTranslationResult(
            raw_item_id=normalized,
            translated_item_id=normalized,
            source_namespace="upstream",
        )

    if allow_upstream_passthrough and normalized.startswith("item_") and normalized in valid_upstream_item_ids():
        return CommodityTranslationResult(
            raw_item_id=normalized,
            translated_item_id=normalized,
            source_namespace="upstream_registry",
            is_registry_passthrough=True,
        )

    if normalized.startswith("item_"):
        return CommodityTranslationResult(
            raw_item_id=normalized,
            translated_item_id=None,
            source_namespace="upstream_invalid",
            warnings=(
                f"invalid upstream-like commodity id {normalized!r} is not present in IndustrialPlanner item_registry.json",
            ),
            is_translation_miss=True,
        )

    return CommodityTranslationResult(
        raw_item_id=normalized,
        translated_item_id=None,
        source_namespace="unknown",
        warnings=(f"commodity {normalized!r} could not be translated into the IndustrialPlanner item namespace",),
        is_translation_miss=True,
    )


def translate_commodity_set(
    commodity_ids: Iterable[str],
    *,
    semantic_registry: SemanticRegistry | None = None,
) -> CommoditySetTranslation:
    translated: set[str] = set()
    warnings: list[str] = []
    translation_miss_count = 0
    for raw_item_id in commodity_ids:
        result = translate_canonical_item_id(raw_item_id, semantic_registry=semantic_registry)
        warnings.extend(result.warnings)
        translation_miss_count += int(result.is_translation_miss)
        if result.translated_item_id is not None:
            translated.add(result.translated_item_id)
    return CommoditySetTranslation(
        translated_item_ids=frozenset(sorted(translated)),
        warnings=tuple(sorted(set(warnings))),
        translation_miss_count=int(translation_miss_count),
    )


def translate_config_item_ids(
    config: Mapping[str, Any],
    *,
    semantic_registry: SemanticRegistry | None = None,
) -> ConfigTranslationAudit:
    """Translate known item-id bearing config fields into upstream namespace.

    The export adapter is fail-closed for unknown item-bearing config values: unresolved
    values are dropped from the serialized config instead of being passed through.
    """

    semantic_registry = semantic_registry or current_repository_semantic_registry()
    warnings: list[str] = []
    dropped_paths: list[str] = []
    translation_miss_count = 0
    translated = json.loads(json.dumps(config, ensure_ascii=False))

    def _translate_value(raw_value: Any, *, context: str) -> tuple[bool, str | None]:
        nonlocal translation_miss_count
        if raw_value is None:
            return False, None
        result = translate_canonical_item_id(str(raw_value), semantic_registry=semantic_registry)
        warnings.extend(f"{context}: {warning}" for warning in result.warnings)
        if result.is_translation_miss:
            translation_miss_count += 1
        if result.translated_item_id is None:
            dropped_paths.append(context)
            return False, None
        return True, result.translated_item_id

    for key in (
        "pickupItemId",
        "admissionItemId",
        "pumpOutputItemId",
        "preloadInputItemId",
    ):
        if key not in translated:
            continue
        kept, value = _translate_value(translated.get(key), context=f"config.{key}")
        if kept and value is not None:
            translated[key] = value
        else:
            translated.pop(key, None)

    def _translate_list_item_ids(list_key: str, item_key: str) -> None:
        raw_values = translated.get(list_key)
        if not isinstance(raw_values, list):
            return
        kept_entries: list[Any] = []
        for index, entry in enumerate(raw_values):
            if not isinstance(entry, Mapping):
                kept_entries.append(entry)
                continue
            entry_dict = dict(entry)
            if item_key not in entry_dict or entry_dict.get(item_key) is None:
                kept_entries.append(entry_dict)
                continue
            kept, value = _translate_value(entry_dict.get(item_key), context=f"config.{list_key}[{index}].{item_key}")
            if not kept or value is None:
                continue
            entry_dict[item_key] = value
            kept_entries.append(entry_dict)
        if kept_entries:
            translated[list_key] = kept_entries
        else:
            translated.pop(list_key, None)

    for key in ("preloadInputs", "storagePreloadInputs"):
        _translate_list_item_ids(key, "itemId")

    _translate_list_item_ids("protocolHubOutputs", "itemId")

    if isinstance(translated.get("storageSlots"), list):
        kept_entries: list[Any] = []
        for index, entry in enumerate(translated["storageSlots"]):
            if not isinstance(entry, Mapping):
                kept_entries.append(entry)
                continue
            entry_dict = dict(entry)
            for item_key in ("pinnedItemId", "preloadItemId"):
                if item_key not in entry_dict or entry_dict.get(item_key) is None:
                    continue
                kept, value = _translate_value(
                    entry_dict.get(item_key),
                    context=f"config.storageSlots[{index}].{item_key}",
                )
                if kept and value is not None:
                    entry_dict[item_key] = value
                else:
                    entry_dict.pop(item_key, None)
            if entry_dict:
                kept_entries.append(entry_dict)
        if kept_entries:
            translated["storageSlots"] = kept_entries
        else:
            translated.pop("storageSlots", None)

    reactor_pool = translated.get("reactorPool")
    if isinstance(reactor_pool, Mapping):
        reactor_pool_dict = dict(reactor_pool)
        for key in (
            "solidOutputItemId",
            "liquidOutputItemId",
            "liquidOutputItemIdA",
            "liquidOutputItemIdB",
        ):
            if key not in reactor_pool_dict or reactor_pool_dict.get(key) is None:
                continue
            kept, value = _translate_value(
                reactor_pool_dict.get(key),
                context=f"config.reactorPool.{key}",
            )
            if kept and value is not None:
                reactor_pool_dict[key] = value
            else:
                reactor_pool_dict.pop(key, None)
        if reactor_pool_dict:
            translated["reactorPool"] = reactor_pool_dict
        else:
            translated.pop("reactorPool", None)

    return ConfigTranslationAudit(
        translated_config=translated,
        warnings=tuple(sorted(set(warnings))),
        translation_miss_count=int(translation_miss_count),
        dropped_paths=tuple(dict.fromkeys(dropped_paths)),
    )


def resolve_recipe_for_facility(
    facility: Mapping[str, Any],
    *,
    semantic_registry: SemanticRegistry | None = None,
) -> FacilityRecipeResolution:
    semantic_registry = semantic_registry or current_repository_semantic_registry()
    facility_type = str(facility.get("facility_type", "")).strip()
    facility_instance_id = str(facility.get("instance_id", "")).strip() or "<unknown>"

    allowed_type_ids = set(facility_group_by_canonical_id().get(facility_type, ()))
    candidate_pool = [
        candidate
        for candidate in candidate_recipe_library()
        if candidate.canonical_facility_type == facility_type
        and (not allowed_type_ids or candidate.upstream_facility_id in allowed_type_ids)
    ]
    if not candidate_pool:
        return FacilityRecipeResolution(
            resolved=False,
            upstream_facility_id=None,
            resolved_recipe_id=None,
            resolution_mode="fallback",
            reason=f"no semantic recipe candidates are registered for facility_type={facility_type!r}",
        )

    active_ports = facility.get("active_ports")
    if not isinstance(active_ports, Sequence):
        active_ports = []

    raw_output_items = [
        _normalize_commodity_token(port.get("commodity", ""))
        for port in active_ports
        if str(port.get("type", "")).lower() == "output"
    ]
    raw_input_items = [
        _normalize_commodity_token(port.get("commodity", ""))
        for port in active_ports
        if str(port.get("type", "")).lower() == "input"
    ]

    translated_outputs = translate_commodity_set(raw_output_items, semantic_registry=semantic_registry)
    translated_inputs = translate_commodity_set(raw_input_items, semantic_registry=semantic_registry)
    translated_output_ids = translated_outputs.translated_item_ids
    translated_input_ids = translated_inputs.translated_item_ids
    warnings = list(translated_outputs.warnings) + list(translated_inputs.warnings)
    translation_miss_count = (
        translated_outputs.translation_miss_count + translated_inputs.translation_miss_count
    )

    if not translated_output_ids:
        return FacilityRecipeResolution(
            resolved=False,
            upstream_facility_id=None,
            resolved_recipe_id=None,
            resolution_mode="fallback",
            reason="no translated output commodities were available for precise device inference",
            warnings=tuple(sorted(set(warnings))),
            translated_input_ids=tuple(sorted(translated_input_ids)),
            translated_output_ids=tuple(sorted(translated_output_ids)),
            translation_miss_count=int(translation_miss_count),
        )

    exact_output_matches = [
        candidate
        for candidate in candidate_pool
        if candidate.translated_output_ids == translated_output_ids
    ]
    if len(exact_output_matches) == 1:
        candidate = exact_output_matches[0]
        return FacilityRecipeResolution(
            resolved=True,
            upstream_facility_id=candidate.upstream_facility_id,
            resolved_recipe_id=candidate.canonical_recipe_id,
            resolution_mode="precise",
            reason=(
                f"resolved via exact translated output-set match for facility {facility_instance_id}: "
                f"{sorted(translated_output_ids)} -> {candidate.canonical_recipe_id}"
            ),
            warnings=tuple(sorted(set(warnings))),
            translated_input_ids=tuple(sorted(translated_input_ids)),
            translated_output_ids=tuple(sorted(translated_output_ids)),
            translation_miss_count=int(translation_miss_count),
        )

    if len(exact_output_matches) > 1 and translated_input_ids:
        scored = []
        for candidate in exact_output_matches:
            overlap = len(candidate.translated_input_ids & translated_input_ids)
            symmetric_gap = len(candidate.translated_input_ids ^ translated_input_ids)
            exact_input = candidate.translated_input_ids == translated_input_ids
            scored.append((exact_input, overlap, -symmetric_gap, candidate.canonical_recipe_id, candidate))
        scored.sort(reverse=True)
        best = scored[0]
        if len(scored) == 1 or best[:3] > scored[1][:3]:
            candidate = best[4]
            return FacilityRecipeResolution(
                resolved=True,
                upstream_facility_id=candidate.upstream_facility_id,
                resolved_recipe_id=candidate.canonical_recipe_id,
                resolution_mode="precise",
                reason=(
                    f"resolved via exact translated output-set match plus input-set scoring for facility {facility_instance_id}: "
                    f"{candidate.canonical_recipe_id}"
                ),
                warnings=tuple(sorted(set(warnings))),
                translated_input_ids=tuple(sorted(translated_input_ids)),
                translated_output_ids=tuple(sorted(translated_output_ids)),
                translation_miss_count=int(translation_miss_count),
            )

    if len(exact_output_matches) > 1:
        candidate_ids = ", ".join(sorted(candidate.canonical_recipe_id for candidate in exact_output_matches))
        warnings.append(
            f"precise resolution remained ambiguous for facility {facility_instance_id}; candidates were [{candidate_ids}]"
        )
        return FacilityRecipeResolution(
            resolved=False,
            upstream_facility_id=None,
            resolved_recipe_id=None,
            resolution_mode="fallback",
            reason="multiple semantic recipe candidates shared the same translated output-set and input evidence did not break the tie",
            warnings=tuple(sorted(set(warnings))),
            translated_input_ids=tuple(sorted(translated_input_ids)),
            translated_output_ids=tuple(sorted(translated_output_ids)),
            translation_miss_count=int(translation_miss_count),
        )

    warnings.append(
        f"no exact translated output-set candidate matched facility {facility_instance_id}; outputs={sorted(translated_output_ids)}"
    )
    return FacilityRecipeResolution(
        resolved=False,
        upstream_facility_id=None,
        resolved_recipe_id=None,
        resolution_mode="fallback",
        reason="no semantic recipe candidate matched the translated output-set exactly",
        warnings=tuple(sorted(set(warnings))),
        translated_input_ids=tuple(sorted(translated_input_ids)),
        translated_output_ids=tuple(sorted(translated_output_ids)),
        translation_miss_count=int(translation_miss_count),
    )
