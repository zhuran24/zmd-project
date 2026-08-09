"""Semantic alignment helpers for endfield-calc snapshot catalogs.

The raw upstream catalog and the local `rules/canonical_rules.json` document do
not share IDs. This module keeps the explicit, build-time-only mapping layer
that projects the verified overlapping production slice into the repository's
canonical ID space for comparison and regression testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from src.interchange.normalized_catalog import build_catalog_metadata, normalize_catalog_payload

CURRENT_REPOSITORY_SEMANTIC_TARGET = "current_repository_rules"
_SEMANTIC_PROJECTION_VERSION = "1.0"


@dataclass(frozen=True)
class ItemSemanticMapping:
    canonical_id: str
    upstream_id: str
    reason: str
    alternates: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecipeSemanticMapping:
    canonical_id: str
    upstream_id: str
    upstream_facility_id: str
    canonical_facility_type: str
    reason: str
    alternates: tuple[str, ...] = ()


@dataclass(frozen=True)
class FacilitySemanticGroup:
    canonical_id: str
    upstream_ids: tuple[str, ...]
    footprint: tuple[int, int]
    port_rule: str
    reason: str
    rotatable: bool = True
    needs_power: bool = True


_CURRENT_REPOSITORY_ITEM_MAPPINGS: tuple[ItemSemanticMapping, ...] = (
    ItemSemanticMapping("blue_iron_block", "item_iron_nugget", "Exact intermediate between ore/powder and the enriched iron chain."),
    ItemSemanticMapping("blue_iron_ore", "item_iron_ore", "Raw iron ore is the exact single-input precursor of the iron nugget chain."),
    ItemSemanticMapping("blue_iron_powder", "item_iron_powder", "Exact powder stage of the iron chain."),
    ItemSemanticMapping(
        "buckwheat",
        "item_plant_moss_1",
        "Selected the moss_1 agricultural line because it feeds the healing capsule branch exactly.",
        alternates=("item_plant_moss_2",),
    ),
    ItemSemanticMapping(
        "buckwheat_powder",
        "item_plant_moss_powder_1",
        "Selected the moss_1 powder line because it feeds the healing capsule branch exactly.",
        alternates=("item_plant_moss_powder_2",),
    ),
    ItemSemanticMapping(
        "buckwheat_seed",
        "item_plant_moss_seed_1",
        "Selected the moss_1 seed loop because it feeds the healing capsule branch exactly.",
        alternates=("item_plant_moss_seed_2",),
    ),
    ItemSemanticMapping("dense_blue_iron_powder", "item_iron_enr_powder", "Exact enriched powder stage of the iron chain."),
    ItemSemanticMapping("dense_source_powder", "item_originium_enr_powder", "Exact enriched powder stage of the originium chain."),
    ItemSemanticMapping(
        "fine_buckwheat_powder",
        "item_plant_moss_enr_powder_1",
        "Selected the medicinal enriched powder because it participates in the exact restorative capsule recipe.",
        alternates=("item_plant_moss_enr_powder_2",),
    ),
    ItemSemanticMapping(
        "qiaoyu_capsule",
        "item_bottled_rec_hp_3",
        "Selected the restorative bottled_rec_hp_3 line because it is the exact 10-bottle + 10-enriched-powder capsule recipe.",
        alternates=("item_bottled_food_3",),
    ),
    ItemSemanticMapping("sandleaf", "item_plant_moss_3", "Exact catalyst agricultural line consumed by every thickener in the mapped slice."),
    ItemSemanticMapping("sandleaf_powder", "item_plant_moss_powder_3", "Exact catalyst powder consumed by every thickener in the mapped slice."),
    ItemSemanticMapping("sandleaf_seed", "item_plant_moss_seed_3", "Exact catalyst agricultural seed loop for the thickener catalyst chain."),
    ItemSemanticMapping("source_ore", "item_originium_ore", "Exact raw ore for the originium powder chain."),
    ItemSemanticMapping("source_powder", "item_originium_powder", "Exact powder stage of the originium chain."),
    ItemSemanticMapping("steel_block", "item_iron_enr", "Exact forged block stage immediately after enriched iron powder."),
    ItemSemanticMapping("steel_bottle", "item_iron_enr_bottle", "Exact bottle output built from two enriched iron blocks."),
    ItemSemanticMapping("steel_part", "item_iron_enr_cmpt", "Exact component output built from one enriched iron block."),
    ItemSemanticMapping("valley_battery", "item_proc_battery_3", "Exact enriched iron + enriched originium battery recipe."),
)

_CURRENT_REPOSITORY_RECIPE_MAPPINGS: tuple[RecipeSemanticMapping, ...] = (
    RecipeSemanticMapping(
        "crusher_blue_iron",
        "grinder_iron_powder_1",
        "item_port_grinder_1",
        "manufacturing_3x3",
        "Exact 1 -> 1 powder conversion inside the iron chain.",
    ),
    RecipeSemanticMapping(
        "crusher_buckwheat",
        "grinder_plant_moss_powder_1_1",
        "item_port_grinder_1",
        "manufacturing_3x3",
        "Exact 1 -> 2 plant-to-powder conversion for the mapped capsule feedstock.",
        alternates=("grinder_plant_moss_powder_2_1",),
    ),
    RecipeSemanticMapping(
        "crusher_sandleaf",
        "grinder_plant_moss_powder_3_1",
        "item_port_grinder_1",
        "manufacturing_3x3",
        "Exact 1 -> 3 catalyst plant-to-powder conversion.",
    ),
    RecipeSemanticMapping(
        "crusher_source",
        "grinder_originium_powder_1",
        "item_port_grinder_1",
        "manufacturing_3x3",
        "Exact 1 -> 1 ore-to-powder conversion for the originium chain.",
    ),
    RecipeSemanticMapping(
        "filling_capsule",
        "filling_bottled_rec_hp_3_1",
        "item_port_filling_pd_mc_1",
        "manufacturing_6x4",
        "Exact 10 bottle + 10 enriched medicinal powder restorative line.",
        alternates=("filling_bottled_food_3_1",),
    ),
    RecipeSemanticMapping(
        "grinder_dense_blue_iron",
        "thickener_iron_enr_powder_1",
        "item_port_thickener_1",
        "manufacturing_6x4",
        "Exact 2 powder + 1 catalyst -> 1 enriched powder conversion in the iron chain.",
    ),
    RecipeSemanticMapping(
        "grinder_dense_source",
        "thickener_originium_enr_powder_1",
        "item_port_thickener_1",
        "manufacturing_6x4",
        "Exact 2 powder + 1 catalyst -> 1 enriched powder conversion in the originium chain.",
    ),
    RecipeSemanticMapping(
        "grinder_fine_buckwheat",
        "thickener_plant_moss_enr_powder_1_1",
        "item_port_thickener_1",
        "manufacturing_6x4",
        "Exact 2 powder + 1 catalyst -> 1 enriched medicinal powder conversion.",
        alternates=("thickener_plant_moss_enr_powder_2_1",),
    ),
    RecipeSemanticMapping(
        "molding_bottle",
        "shaper_iron_enr_bottle_1",
        "item_port_shaper_1",
        "manufacturing_3x3",
        "Exact 2 enriched iron blocks -> 1 bottle conversion.",
    ),
    RecipeSemanticMapping(
        "packaging_battery",
        "tools_proc_battery_3_1",
        "item_port_tools_asm_mc_1",
        "manufacturing_6x4",
        "Exact 10 enriched components + 15 enriched originium powder battery line.",
    ),
    RecipeSemanticMapping(
        "parts_maker",
        "component_iron_enr_cmpt_1",
        "item_port_cmpt_mc_1",
        "manufacturing_3x3",
        "Exact 1 enriched iron block -> 1 component conversion.",
    ),
    RecipeSemanticMapping(
        "planter_buckwheat",
        "planter_plant_moss_1_1",
        "item_port_planter_1",
        "manufacturing_5x5",
        "Exact 1 seed -> 1 crop agricultural loop for the mapped capsule feedstock.",
        alternates=("planter_plant_moss_2_1",),
    ),
    RecipeSemanticMapping(
        "planter_sandleaf",
        "planter_plant_moss_3_1",
        "item_port_planter_1",
        "manufacturing_5x5",
        "Exact 1 seed -> 1 catalyst crop agricultural loop.",
    ),
    RecipeSemanticMapping(
        "refinery_blue_iron",
        "furnance_iron_nugget_1",
        "item_port_furnance_1",
        "manufacturing_3x3",
        "Exact 1 ore -> 1 forged block conversion in the iron chain.",
    ),
    RecipeSemanticMapping(
        "refinery_steel",
        "furnance_iron_enr_1",
        "item_port_furnance_1",
        "manufacturing_3x3",
        "Exact 1 enriched powder -> 1 enriched iron block conversion.",
    ),
    RecipeSemanticMapping(
        "seed_collector_buckwheat",
        "seedcollector_plant_moss_1_1",
        "item_port_seedcol_1",
        "manufacturing_5x5",
        "Exact 1 crop -> 2 seeds agricultural loop for the mapped capsule feedstock.",
        alternates=("seedcollector_plant_moss_2_1",),
    ),
    RecipeSemanticMapping(
        "seed_collector_sandleaf",
        "seedcollector_plant_moss_3_1",
        "item_port_seedcol_1",
        "manufacturing_5x5",
        "Exact 1 crop -> 2 seeds agricultural loop for the catalyst chain.",
    ),
)

_CURRENT_REPOSITORY_FACILITY_GROUPS: tuple[FacilitySemanticGroup, ...] = (
    FacilitySemanticGroup(
        canonical_id="manufacturing_3x3",
        upstream_ids=(
            "item_port_cmpt_mc_1",
            "item_port_furnance_1",
            "item_port_grinder_1",
            "item_port_shaper_1",
        ),
        footprint=(3, 3),
        port_rule="opposite_parallel_sides",
        reason="Mapped exact 3x3 processor slice used by the canonical 3x3 manufacturing recipes.",
    ),
    FacilitySemanticGroup(
        canonical_id="manufacturing_5x5",
        upstream_ids=(
            "item_port_planter_1",
            "item_port_seedcol_1",
        ),
        footprint=(5, 5),
        port_rule="opposite_parallel_sides",
        reason="Mapped exact agricultural planter / seed-collector slice used by the canonical 5x5 recipes.",
    ),
    FacilitySemanticGroup(
        canonical_id="manufacturing_6x4",
        upstream_ids=(
            "item_port_filling_pd_mc_1",
            "item_port_thickener_1",
            "item_port_tools_asm_mc_1",
        ),
        footprint=(6, 4),
        port_rule="long_sides",
        reason="Mapped exact thickener / filler / tool-assembler slice used by the canonical 6x4 recipes.",
    ),
)

_ITEM_MAPPING_BY_CANONICAL = {mapping.canonical_id: mapping for mapping in _CURRENT_REPOSITORY_ITEM_MAPPINGS}
_ITEM_MAPPING_BY_UPSTREAM = {mapping.upstream_id: mapping for mapping in _CURRENT_REPOSITORY_ITEM_MAPPINGS}
_RECIPE_MAPPING_BY_CANONICAL = {mapping.canonical_id: mapping for mapping in _CURRENT_REPOSITORY_RECIPE_MAPPINGS}


@dataclass(frozen=True)
class SemanticRegistry:
    item_mappings: tuple[ItemSemanticMapping, ...]
    recipe_mappings: tuple[RecipeSemanticMapping, ...]
    facility_groups: tuple[FacilitySemanticGroup, ...]


def current_repository_semantic_registry() -> SemanticRegistry:
    return SemanticRegistry(
        item_mappings=tuple(_CURRENT_REPOSITORY_ITEM_MAPPINGS),
        recipe_mappings=tuple(_CURRENT_REPOSITORY_RECIPE_MAPPINGS),
        facility_groups=tuple(_CURRENT_REPOSITORY_FACILITY_GROUPS),
    )


def current_repository_item_semantic_mappings() -> tuple[ItemSemanticMapping, ...]:
    return tuple(_CURRENT_REPOSITORY_ITEM_MAPPINGS)


def current_repository_recipe_semantic_mappings() -> tuple[RecipeSemanticMapping, ...]:
    return tuple(_CURRENT_REPOSITORY_RECIPE_MAPPINGS)


def current_repository_facility_semantic_groups() -> tuple[FacilitySemanticGroup, ...]:
    return tuple(_CURRENT_REPOSITORY_FACILITY_GROUPS)


def item_mapping_by_canonical_id() -> dict[str, ItemSemanticMapping]:
    return dict(_ITEM_MAPPING_BY_CANONICAL)


def item_mapping_by_upstream_id() -> dict[str, ItemSemanticMapping]:
    return dict(_ITEM_MAPPING_BY_UPSTREAM)


def recipe_mapping_by_canonical_id() -> dict[str, RecipeSemanticMapping]:
    return dict(_RECIPE_MAPPING_BY_CANONICAL)


def available_semantic_targets() -> tuple[str, ...]:
    return (CURRENT_REPOSITORY_SEMANTIC_TARGET,)


def project_catalog_to_semantic_target(
    catalog: Mapping[str, Any],
    *,
    target: str = CURRENT_REPOSITORY_SEMANTIC_TARGET,
) -> dict[str, Any]:
    normalized = normalize_catalog_payload(catalog)
    if target != CURRENT_REPOSITORY_SEMANTIC_TARGET:
        raise ValueError(f"unsupported semantic target: {target}")
    return _project_catalog_to_current_repository_semantics(normalized)


def project_catalog_to_current_repository_semantics(catalog: Mapping[str, Any]) -> dict[str, Any]:
    return project_catalog_to_semantic_target(catalog, target=CURRENT_REPOSITORY_SEMANTIC_TARGET)


def _project_catalog_to_current_repository_semantics(catalog: Mapping[str, Any]) -> dict[str, Any]:
    items_by_id = {str(item.get("id", "")): item for item in catalog["items"]}
    recipes_by_id = {str(recipe.get("id", "")): recipe for recipe in catalog["recipes"]}
    facilities_by_id = {str(facility.get("id", "")): facility for facility in catalog["facilities"]}
    canonical_item_by_upstream_id = {
        mapping.upstream_id: mapping.canonical_id
        for mapping in _CURRENT_REPOSITORY_ITEM_MAPPINGS
    }

    projected_items = [
        _project_item_entry(_require_entry(items_by_id, mapping.upstream_id, kind="item"), mapping)
        for mapping in _CURRENT_REPOSITORY_ITEM_MAPPINGS
    ]
    projected_recipes = [
        _project_recipe_entry(
            _require_entry(recipes_by_id, mapping.upstream_id, kind="recipe"),
            mapping,
            canonical_item_by_upstream_id,
        )
        for mapping in _CURRENT_REPOSITORY_RECIPE_MAPPINGS
    ]
    projected_facilities = [
        _project_facility_group(facilities_by_id, group)
        for group in _CURRENT_REPOSITORY_FACILITY_GROUPS
    ]

    raw_metadata = catalog.get("metadata") if isinstance(catalog.get("metadata"), Mapping) else {}
    raw_extensions = raw_metadata.get("extensions") if isinstance(raw_metadata.get("extensions"), Mapping) else {}
    notes = [str(note) for note in raw_metadata.get("notes", [])] if raw_metadata else []
    notes.extend(
        [
            "Partial semantic alignment projected the verified overlapping endfield-calc production slice into current_repository_rules IDs.",
            "The aligned catalog intentionally keeps only the mapped 17-recipe slice; unmatched upstream entities remain available in the raw normalized catalog.",
        ]
    )
    extensions: dict[str, Any] = dict(raw_extensions)
    extensions.update(
        {
            "semantic_target": CURRENT_REPOSITORY_SEMANTIC_TARGET,
            "semantic_projection_version": _SEMANTIC_PROJECTION_VERSION,
            "semantic_raw_item_count": len(catalog["items"]),
            "semantic_raw_recipe_count": len(catalog["recipes"]),
            "semantic_raw_facility_count": len(catalog["facilities"]),
            "semantic_mapped_item_count": len(projected_items),
            "semantic_mapped_recipe_count": len(projected_recipes),
            "semantic_mapped_facility_count": len(projected_facilities),
            "semantic_partial_projection": True,
            "semantic_coverage_scope": "current_repository_rules_frozen_slice",
            "semantic_ambiguity_notes": [
                "The capsule branch selects moss_1 / bottled_rec_hp_3 over the structurally identical moss_2 / bottled_food_3 branch because the canonical end-product is medicinal.",
            ],
        }
    )
    metadata = build_catalog_metadata(
        source=f"{raw_metadata.get('source', 'JamboChen/endfield-calc snapshot')} (semantic alignment: {CURRENT_REPOSITORY_SEMANTIC_TARGET})",
        generated_at=str(raw_metadata.get("generated_at")) if raw_metadata.get("generated_at") else None,
        source_version=raw_metadata.get("source_version"),
        source_commit=raw_metadata.get("source_commit"),
        source_license=raw_metadata.get("source_license"),
        notes=notes,
        extensions=extensions,
    )

    return normalize_catalog_payload(
        {
            "metadata": metadata,
            "items": projected_items,
            "recipes": projected_recipes,
            "facilities": projected_facilities,
            "power": [],
            "port_rules": _build_port_rules(projected_facilities),
        }
    )


def _project_item_entry(raw_item: Mapping[str, Any], mapping: ItemSemanticMapping) -> dict[str, Any]:
    aliases = set(_as_aliases(raw_item.get("aliases")))
    aliases.add(str(raw_item.get("id", "")))
    raw_item_metadata = raw_item.get("metadata") if isinstance(raw_item.get("metadata"), Mapping) else {}
    metadata: dict[str, Any] = {
        "semantic_source_id": str(raw_item.get("id", "")),
        "semantic_mapping_reason": mapping.reason,
    }
    if mapping.alternates:
        metadata["semantic_alternates"] = list(mapping.alternates)
    if raw_item_metadata:
        metadata["semantic_source_metadata"] = dict(raw_item_metadata)
    raw_category = str(raw_item.get("category", "")).strip()
    if raw_category and raw_category != "recipe_commodity":
        metadata["semantic_source_category"] = raw_category
    return {
        "id": mapping.canonical_id,
        "name": mapping.canonical_id,
        "category": "recipe_commodity",
        "unit": "item",
        "aliases": sorted(alias for alias in aliases if alias),
        "metadata": metadata,
    }


def _project_recipe_entry(
    raw_recipe: Mapping[str, Any],
    mapping: RecipeSemanticMapping,
    canonical_item_by_upstream_id: Mapping[str, str],
) -> dict[str, Any]:
    raw_facility_type = str(raw_recipe.get("facility_type", ""))
    if raw_facility_type != mapping.upstream_facility_id:
        raise ValueError(
            f"recipe {mapping.upstream_id} expected upstream facility {mapping.upstream_facility_id!r} "
            f"but saw {raw_facility_type!r}"
        )
    inputs = [_project_flow_entry(entry, canonical_item_by_upstream_id) for entry in raw_recipe.get("inputs", [])]
    outputs = [_project_flow_entry(entry, canonical_item_by_upstream_id) for entry in raw_recipe.get("outputs", [])]
    raw_recipe_metadata = raw_recipe.get("metadata") if isinstance(raw_recipe.get("metadata"), Mapping) else {}
    metadata: dict[str, Any] = {
        "semantic_source_id": str(raw_recipe.get("id", "")),
        "semantic_source_facility_id": raw_facility_type,
        "semantic_mapping_reason": mapping.reason,
    }
    if mapping.alternates:
        metadata["semantic_alternates"] = list(mapping.alternates)
    if raw_recipe_metadata:
        metadata["semantic_source_metadata"] = dict(raw_recipe_metadata)
    raw_power = raw_recipe.get("power") if isinstance(raw_recipe.get("power"), Mapping) else {}
    if raw_power and any(float(raw_power.get(key, 0.0)) != 0.0 for key in ("consumption_kw", "generation_kw")):
        metadata["semantic_source_power"] = {
            "consumption_kw": float(raw_power.get("consumption_kw", 0.0)),
            "generation_kw": float(raw_power.get("generation_kw", 0.0)),
        }
    return {
        "id": mapping.canonical_id,
        "name": mapping.canonical_id,
        "facility_type": mapping.canonical_facility_type,
        "cycle_seconds": float(raw_recipe.get("cycle_seconds", 0.0)),
        "inputs": inputs,
        "outputs": outputs,
        "power": {"consumption_kw": 0.0, "generation_kw": 0.0},
        "metadata": metadata,
    }


def _project_flow_entry(raw_flow: Mapping[str, Any], canonical_item_by_upstream_id: Mapping[str, str]) -> dict[str, Any]:
    upstream_item_id = str(raw_flow.get("item_id", ""))
    if upstream_item_id not in canonical_item_by_upstream_id:
        raise ValueError(f"no canonical semantic item mapping registered for upstream item {upstream_item_id!r}")
    return {
        "item_id": canonical_item_by_upstream_id[upstream_item_id],
        "amount": float(raw_flow.get("amount", 0.0)),
    }


def _project_facility_group(
    facilities_by_id: Mapping[str, Mapping[str, Any]],
    group: FacilitySemanticGroup,
) -> dict[str, Any]:
    source_power_profiles: list[dict[str, Any]] = []
    for upstream_id in group.upstream_ids:
        raw_facility = _require_entry(facilities_by_id, upstream_id, kind="facility")
        raw_power = raw_facility.get("power") if isinstance(raw_facility.get("power"), Mapping) else {}
        source_power_profiles.append(
            {
                "facility_id": upstream_id,
                "consumption_kw": float(raw_power.get("consumption_kw", 0.0)),
                "generation_kw": float(raw_power.get("generation_kw", 0.0)),
            }
        )
    metadata = {
        "semantic_source_ids": list(group.upstream_ids),
        "semantic_mapping_reason": group.reason,
        "semantic_source_power_profiles": source_power_profiles,
    }
    return {
        "id": group.canonical_id,
        "name": group.canonical_id,
        "footprint": {"w": int(group.footprint[0]), "h": int(group.footprint[1])},
        "rotatable": bool(group.rotatable),
        "needs_power": bool(group.needs_power),
        "power": {"consumption_kw": 0.0, "generation_kw": 0.0},
        "port_rule": group.port_rule,
        "metadata": metadata,
    }


def _build_port_rules(facilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _port_rule_sides(port_rule: str) -> tuple[list[str], list[str]]:
    if port_rule in {"opposite_parallel_sides", "long_sides"}:
        return ["N", "S"], ["N", "S"]
    if port_rule in {"omni", "omni_wireless", "core_specific", "core"}:
        return ["N", "E", "S", "W"], ["N", "E", "S", "W"]
    if port_rule == "inward_facing":
        return ["N", "W"], ["E", "S"]
    return [], []


def _as_aliases(raw_aliases: Any) -> list[str]:
    if isinstance(raw_aliases, list):
        return [str(alias) for alias in raw_aliases if str(alias)]
    if raw_aliases:
        return [str(raw_aliases)]
    return []


def _require_entry(lookup: Mapping[str, Mapping[str, Any]], entry_id: str, *, kind: str) -> Mapping[str, Any]:
    entry = lookup.get(entry_id)
    if entry is None:
        raise ValueError(f"missing upstream {kind} required for semantic alignment: {entry_id}")
    return entry
