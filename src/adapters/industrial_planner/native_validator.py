"""Offline validator for the native (schemaVersion 4) IndustrialPlanner document.

Upstream's `normalizeBlueprintDocument`
(`src/shared/blueprints/blueprint-document-codec.ts:4-55`) is the only gate an
imported document must pass, and it is extremely permissive: it checks the twelve
top-level fields and then passes entities and slot links through untouched.  A
document with an empty `entityOrder`, a `rotation` of 45, an unknown
`definitionId` or a nonsense slot link is accepted and only misbehaves later, at
placement or simulation time, with no diagnostic at all.

So this validator has two halves:

* **N1-N6** re-implement what upstream really rejects;
* **N7-N13** cover what upstream accepts but cannot execute - the silent-failure
  set documented in the upstream spec (`§9`).

Placement geometry (outer ring, inner ring, overlap, hub connectivity) is
deliberately *not* re-checked here: that is `blueprint_validator`'s job on the v1
intermediate representation, and a second geometry implementation would produce a
second, unarbitrable verdict.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from src.adapters.industrial_planner.native_document import (
    INDUSTRIAL_PLANNER_NATIVE_SCHEMA_VERSION,
    NATIVE_DOCUMENT_TOP_LEVEL_KEYS,
    WAREHOUSE_SENTINEL_ENTITY_ID,
)

_REGISTRY_DIR = Path(__file__).resolve().parent
_NATIVE_REGISTRY_PATH = _REGISTRY_DIR / "native_registry_v3.json"

_VALID_ROTATIONS = (0, 90, 180, 270)
_VALID_LINK_TYPES = ("share-all", "share-cap")
_ENDPOINT_KEYS = ("entityId", "storageSlotGroupId", "slotId")
_SENTINEL_ENTITY_ID_PREFIXES = ("warehouse:", "base-builtin:")

_INDEXED_CONFIG_KEY_PATTERNS = (
    re.compile(r"^storageSlotGroups\[\d+\]\.slots\[\d+\]\.[A-Za-z][A-Za-z0-9_]*$"),
    re.compile(r"^portGroups\[\d+\]\.ports\[\d+\]\.[A-Za-z][A-Za-z0-9_]*$"),
    re.compile(r"^recipeChannels\[\d+\]\.[A-Za-z][A-Za-z0-9_]*$"),
)
_BARE_CONFIG_KEYS = frozenset({
    "channelRecipes",
    "portPriorityGroups",
    "customPortPriorityGroups",
    "darkPipeInletMode",
})
_ADMISSION_RULE_CONFIG_KEY_PATTERN = re.compile(r"^portGroups\[\d+\]\.ports\[\d+\]\.admissionRule$")


@dataclass(frozen=True)
class NativeRegistry:
    definition_ids: frozenset[str]
    base_ids: frozenset[str]
    builtin_signatures_by_base: dict[str, frozenset[tuple[str, int, int, int]]]
    admission_per_minute_limit_caps: dict[str, int]
    admission_rate_windows_per_minute: int


@dataclass
class NativeValidationReport:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    entity_count: int = 0
    slot_link_count: int = 0
    base_builtin_conflict_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=4)
def load_native_registry(registry_path: str | None = None) -> NativeRegistry:
    path = Path(registry_path) if registry_path is not None else _NATIVE_REGISTRY_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))

    definition_ids = frozenset(str(entry) for entry in payload.get("definition_ids", []))
    if not definition_ids:
        raise ValueError(f"native registry {path} declares no definition ids")

    base_ids: set[str] = set()
    builtin_signatures: dict[str, frozenset[tuple[str, int, int, int]]] = {}
    for base in payload.get("bases", []):
        base_id = str(base.get("id", "")).strip()
        if not base_id:
            continue
        base_ids.add(base_id)
        builtin_signatures[base_id] = frozenset(
            (
                str(entity.get("definitionId", "")),
                int(entity.get("position", {}).get("x", 0)),
                int(entity.get("position", {}).get("y", 0)),
                int(entity.get("rotation", 0)),
            )
            for entity in base.get("builtinEntities", [])
        )
    if not base_ids:
        raise ValueError(f"native registry {path} declares no bases")

    admission_rate = payload.get("admission_rate", {})
    caps = {
        str(key): int(value)
        for key, value in dict(admission_rate.get("per_minute_limit_caps", {})).items()
    }
    if not caps:
        raise ValueError(f"native registry {path} declares no admission rate caps")

    return NativeRegistry(
        definition_ids=definition_ids,
        base_ids=frozenset(base_ids),
        builtin_signatures_by_base=builtin_signatures,
        admission_per_minute_limit_caps=caps,
        admission_rate_windows_per_minute=int(admission_rate.get("windows_per_minute", 6)),
    )


def validate_native_blueprint_document(
    document: Mapping[str, Any],
    *,
    registry_path: Path | None = None,
) -> NativeValidationReport:
    registry = load_native_registry(str(registry_path) if registry_path is not None else None)
    errors: list[str] = []

    if not isinstance(document, Mapping):
        return NativeValidationReport(is_valid=False, errors=["N1: native document must be a mapping"])

    # N1 - exact top-level key set.
    actual_keys = set(document)
    expected_keys = set(NATIVE_DOCUMENT_TOP_LEVEL_KEYS)
    missing = sorted(expected_keys - actual_keys)
    unexpected = sorted(actual_keys - expected_keys)
    if missing:
        errors.append(f"N1: native document is missing top-level field(s) {missing}")
    if unexpected:
        errors.append(f"N1: native document carries unexpected top-level field(s) {unexpected}")

    # N2 - schemaVersion is exactly the integer 4.
    schema_version = document.get("schemaVersion")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        errors.append(f"N2: schemaVersion must be an int, got {schema_version!r}")
    elif int(schema_version) != int(INDUSTRIAL_PLANNER_NATIVE_SCHEMA_VERSION):
        errors.append(
            f"N2: schemaVersion must be {int(INDUSTRIAL_PLANNER_NATIVE_SCHEMA_VERSION)}, "
            f"got {schema_version!r}"
        )

    # N3 - non-empty strings.
    for field_name in ("blueprintId", "name", "baseId", "createdAt", "updatedAt"):
        value = document.get(field_name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"N3: {field_name} must be a non-empty string, got {value!r}")

    # N4 - strings that may be empty.
    for field_name in ("version", "description"):
        if not isinstance(document.get(field_name), str):
            errors.append(
                f"N4: {field_name} must be a string, got {document.get(field_name)!r}"
            )

    # N5 - integer grid point.
    grid_point = document.get("initialGridPoint")
    if not isinstance(grid_point, Mapping):
        errors.append(f"N5: initialGridPoint must be a mapping, got {grid_point!r}")
    else:
        for axis in ("x", "y"):
            value = grid_point.get(axis)
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"N5: initialGridPoint.{axis} must be an int, got {value!r}")

    # N6 - container types.
    entities = document.get("entities")
    entity_order = document.get("entityOrder")
    slot_links = document.get("slotLinks")
    if not isinstance(entities, Mapping):
        errors.append(f"N6: entities must be a mapping, got {type(entities).__name__}")
        entities = {}
    if not isinstance(entity_order, list) or any(not isinstance(entry, str) for entry in entity_order):
        errors.append("N6: entityOrder must be a list of strings")
        entity_order = []
    if not isinstance(slot_links, list):
        errors.append(f"N6: slotLinks must be a list, got {type(slot_links).__name__}")
        slot_links = []

    # N7 - entityOrder mirrors entities exactly.
    errors.extend(_check_entity_order(entities, entity_order))

    # N8/N9/N10 - entity records.
    errors.extend(_check_entities(entities, registry=registry))

    # N11 - slot links.
    errors.extend(_check_slot_links(slot_links, entities=entities))

    # N12 - baseId is a known base.
    base_id = document.get("baseId")
    if isinstance(base_id, str) and base_id.strip() and base_id not in registry.base_ids:
        errors.append(
            f"N12: baseId {base_id!r} is not one of the {len(registry.base_ids)} known bases"
        )

    # N13 - no entity collides with a base builtin signature.
    conflicts = _base_builtin_conflicts(entities, base_id=base_id, registry=registry)
    for entity_id, signature in conflicts:
        errors.append(
            f"N13: entity {entity_id!r} duplicates base builtin signature {signature}; "
            "base builtins are provided by the base itself and must not be exported"
        )

    return NativeValidationReport(
        is_valid=not errors,
        errors=errors,
        entity_count=len(entities),
        slot_link_count=len(slot_links),
        base_builtin_conflict_count=len(conflicts),
    )


def _check_entity_order(entities: Mapping[str, Any], entity_order: Sequence[str]) -> list[str]:
    errors: list[str] = []
    duplicates = sorted({entry for entry in entity_order if list(entity_order).count(entry) > 1})
    if duplicates:
        errors.append(f"N7: entityOrder contains duplicate id(s) {duplicates}")
    missing = sorted(set(entities) - set(entity_order))
    if missing:
        errors.append(
            f"N7: entityOrder is missing entity id(s) {missing}; upstream silently drops them"
        )
    unknown = sorted(set(entity_order) - set(entities))
    if unknown:
        errors.append(f"N7: entityOrder references unknown entity id(s) {unknown}")
    if not errors and len(entity_order) != len(entities):
        errors.append(
            f"N7: entityOrder length {len(entity_order)} does not match {len(entities)} entities"
        )
    return errors


def _check_entities(entities: Mapping[str, Any], *, registry: NativeRegistry) -> list[str]:
    errors: list[str] = []
    for entity_id, entity in entities.items():
        if not isinstance(entity, Mapping):
            errors.append(f"N8: entity {entity_id!r} must be a mapping")
            continue
        if entity.get("id") != entity_id:
            errors.append(
                f"N8: entity {entity_id!r} declares id {entity.get('id')!r}; the record key wins "
                "upstream, so a mismatch is a silent rename"
            )
        definition_id = entity.get("definitionId")
        if not isinstance(definition_id, str) or definition_id not in registry.definition_ids:
            errors.append(
                f"N8: entity {entity_id!r} definitionId {definition_id!r} is not a known "
                "native definition id"
            )
        rotation = entity.get("rotation")
        if isinstance(rotation, bool) or rotation not in _VALID_ROTATIONS:
            errors.append(
                f"N8: entity {entity_id!r} rotation {rotation!r} is not one of {list(_VALID_ROTATIONS)}"
            )
        position = entity.get("position")
        if not isinstance(position, Mapping):
            errors.append(f"N8: entity {entity_id!r} position must be a mapping")
        else:
            for axis in ("x", "y"):
                value = position.get(axis)
                if isinstance(value, bool) or not isinstance(value, int):
                    errors.append(f"N8: entity {entity_id!r} position.{axis} must be an int")
        tags = entity.get("tags")
        if tags != []:
            errors.append(f"N8: entity {entity_id!r} tags must be an empty list, got {tags!r}")
        config = entity.get("config")
        if not isinstance(config, Mapping):
            errors.append(f"N8: entity {entity_id!r} config must be a mapping, got {config!r}")
            continue
        errors.extend(_check_entity_config(entity_id, config, definition_id, registry=registry))
    return errors


def _check_entity_config(
    entity_id: str,
    config: Mapping[str, Any],
    definition_id: Any,
    *,
    registry: NativeRegistry,
) -> list[str]:
    errors: list[str] = []
    for key, value in config.items():
        key_text = str(key)
        if key_text not in _BARE_CONFIG_KEYS and not any(
            pattern.match(key_text) for pattern in _INDEXED_CONFIG_KEY_PATTERNS
        ):
            errors.append(
                f"N9: entity {entity_id!r} config key {key_text!r} does not match any known "
                "native config key shape"
            )
            continue
        if _ADMISSION_RULE_CONFIG_KEY_PATTERN.match(key_text):
            errors.extend(
                _check_admission_rule(entity_id, value, definition_id, registry=registry)
            )
    return errors


def _check_admission_rule(
    entity_id: str,
    rule: Any,
    definition_id: Any,
    *,
    registry: NativeRegistry,
) -> list[str]:
    if not isinstance(rule, Mapping):
        return [f"N10: entity {entity_id!r} admissionRule must be a mapping, got {rule!r}"]
    per_minute_limit = rule.get("perMinuteLimit")
    if per_minute_limit is None:
        return []
    if isinstance(per_minute_limit, bool) or not isinstance(per_minute_limit, int):
        return [
            f"N10: entity {entity_id!r} admissionRule.perMinuteLimit must be an int or null, "
            f"got {per_minute_limit!r}"
        ]
    errors: list[str] = []
    window = registry.admission_rate_windows_per_minute
    if per_minute_limit <= 0 or per_minute_limit % window != 0:
        errors.append(
            f"N10: entity {entity_id!r} admissionRule.perMinuteLimit {per_minute_limit} must be a "
            f"positive multiple of {window}"
        )
    cap = registry.admission_per_minute_limit_caps.get(str(definition_id))
    if cap is not None and per_minute_limit > cap:
        errors.append(
            f"N10: entity {entity_id!r} admissionRule.perMinuteLimit {per_minute_limit} exceeds the "
            f"{definition_id} cap of {cap}"
        )
    return errors


def _check_slot_links(slot_links: Sequence[Any], *, entities: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, link in enumerate(slot_links):
        label = f"slotLinks[{index}]"
        if not isinstance(link, Mapping):
            errors.append(f"N11: {label} must be a mapping, got {link!r}")
            continue
        link_id = link.get("id")
        if not isinstance(link_id, str) or not link_id.strip():
            errors.append(f"N11: {label} id must be a non-empty string, got {link_id!r}")
        elif link_id in seen_ids:
            errors.append(f"N11: {label} id {link_id!r} is duplicated in the document")
        else:
            seen_ids.add(link_id)
        if link.get("linkType") not in _VALID_LINK_TYPES:
            errors.append(
                f"N11: {label} linkType {link.get('linkType')!r} is not one of {list(_VALID_LINK_TYPES)}"
            )
        for endpoint_name in ("source", "target"):
            endpoint = link.get(endpoint_name)
            if not isinstance(endpoint, Mapping):
                errors.append(f"N11: {label} {endpoint_name} must be a mapping, got {endpoint!r}")
                continue
            for endpoint_key in _ENDPOINT_KEYS:
                value = endpoint.get(endpoint_key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(
                        f"N11: {label} {endpoint_name}.{endpoint_key} must be a non-empty string, "
                        f"got {value!r}"
                    )
            entity_id = endpoint.get("entityId")
            if isinstance(entity_id, str) and entity_id.strip() and not _is_known_link_entity(
                entity_id,
                entities=entities,
            ):
                errors.append(
                    f"N11: {label} {endpoint_name}.entityId {entity_id!r} is neither an exported "
                    "entity nor a recognised sentinel"
                )
    return errors


def _is_known_link_entity(entity_id: str, *, entities: Mapping[str, Any]) -> bool:
    if entity_id in entities:
        return True
    if entity_id == WAREHOUSE_SENTINEL_ENTITY_ID:
        return True
    return any(entity_id.startswith(prefix) for prefix in _SENTINEL_ENTITY_ID_PREFIXES)


def _base_builtin_conflicts(
    entities: Mapping[str, Any],
    *,
    base_id: Any,
    registry: NativeRegistry,
) -> list[tuple[str, tuple[str, int, int, int]]]:
    signatures = registry.builtin_signatures_by_base.get(str(base_id))
    if not signatures:
        return []
    conflicts: list[tuple[str, tuple[str, int, int, int]]] = []
    for entity_id, entity in entities.items():
        if not isinstance(entity, Mapping):
            continue
        position = entity.get("position")
        if not isinstance(position, Mapping):
            continue
        try:
            signature = (
                str(entity.get("definitionId", "")),
                int(position.get("x", 0)),
                int(position.get("y", 0)),
                int(entity.get("rotation", 0)),
            )
        except (TypeError, ValueError):
            continue
        if signature in signatures:
            conflicts.append((str(entity_id), signature))
    return conflicts
