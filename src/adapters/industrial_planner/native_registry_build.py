"""Builder for the IndustrialPlanner native (schemaVersion 4) registry snapshot.

The three legacy registry JSON files in this package (`device_type_registry.json`,
`base_registry.json`, `item_registry.json`) are a 2026-03-28 snapshot and stay the
truth source of the v1 intermediate representation; they are deliberately left
untouched by the native lowering path.  This module derives a *separate* fourth
registry (`native_registry_v3.json`) that describes the current upstream
(schemaVersion 4) world: the definition id universe, the base geometry with the
built-in entities each base injects on its own, and the admission rate ceilings.

The evidence input is the upstream fact dump captured at
`.artifacts/ip_adapter_v3_20260805/registry_facts.json` (upstream HEAD
`7b946c16e3a0e9004b65391c1dd86abe6130cc29`).  Run::

    python -m src.adapters.industrial_planner.native_registry_build \
        --registry-facts .artifacts/ip_adapter_v3_20260805/registry_facts.json \
        --output src/adapters/industrial_planner/native_registry_v3.json

Everything the builder cannot ground in the fact dump fails closed: the payload is
never completed with guessed defaults.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from src.io.strict_json import load_strict_json
from src.search.exact_campaign import atomic_write_json

NATIVE_REGISTRY_SCHEMA = "industrial-planner-native-registry/v1"
NATIVE_REGISTRY_UPSTREAM_HEAD = "7b946c16e3a0e9004b65391c1dd86abe6130cc29"
NATIVE_REGISTRY_UPSTREAM_BRANCH = "v3"

# Upstream `src/shared/blueprint-device-id-migration.ts:8-12` plus
# `ADMISSION_RATE_WINDOWS_PER_MINUTE` in
# `src/domain/registry/types/logistics-constants.ts:18`.  These two facts are not
# part of the registry fact dump, so they are carried here with their provenance
# and re-stated in the generated payload.
ADMISSION_RATE_WINDOWS_PER_MINUTE = 6
ADMISSION_PER_MINUTE_LIMIT_CAPS: dict[str, int] = {
    "log_admission": 30,
    "pipe_admission": 120,
}
_ADMISSION_RATE_SOURCE = (
    "upstream src/shared/blueprint-device-id-migration.ts:8-12; "
    "src/domain/registry/types/logistics-constants.ts:18"
)

_EXPECTED_BLUEPRINT_SCHEMA_VERSION = 4
_EXPECTED_DEVICE_ID_SCHEMA_VERSION = 4

_DEFAULT_REGISTRY_FACTS_PATH = Path(".artifacts/ip_adapter_v3_20260805/registry_facts.json")
_DEFAULT_OUTPUT_PATH = Path("src/adapters/industrial_planner/native_registry_v3.json")


def build_native_registry_payload(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Project the upstream fact dump into the native registry payload."""

    if not isinstance(facts, Mapping):
        raise ValueError("registry facts payload must be a mapping")

    blueprint_schema_version = facts.get("BLUEPRINT_SCHEMA_VERSION")
    device_id_schema_version = facts.get("BLUEPRINT_DEVICE_ID_SCHEMA_VERSION")
    if blueprint_schema_version != _EXPECTED_BLUEPRINT_SCHEMA_VERSION:
        raise ValueError(
            "registry facts BLUEPRINT_SCHEMA_VERSION must be "
            f"{_EXPECTED_BLUEPRINT_SCHEMA_VERSION}, got {blueprint_schema_version!r}"
        )
    if device_id_schema_version != _EXPECTED_DEVICE_ID_SCHEMA_VERSION:
        raise ValueError(
            "registry facts BLUEPRINT_DEVICE_ID_SCHEMA_VERSION must be "
            f"{_EXPECTED_DEVICE_ID_SCHEMA_VERSION}, got {device_id_schema_version!r}"
        )

    definition_ids = _normalize_definition_ids(facts)
    bases = _normalize_bases(facts, definition_ids=definition_ids)

    unknown_admission_ids = sorted(set(ADMISSION_PER_MINUTE_LIMIT_CAPS) - definition_ids)
    if unknown_admission_ids:
        raise ValueError(
            "admission rate caps reference definition ids missing from the fact dump: "
            + ", ".join(unknown_admission_ids)
        )

    return {
        "metadata": {
            "schema": NATIVE_REGISTRY_SCHEMA,
            "source": "IndustrialPlanner native registry snapshot",
            "upstream_branch": NATIVE_REGISTRY_UPSTREAM_BRANCH,
            "upstream_head": NATIVE_REGISTRY_UPSTREAM_HEAD,
            "blueprint_schema_version": int(blueprint_schema_version),
            "device_id_schema_version": int(device_id_schema_version),
            "generated_by": "src/adapters/industrial_planner/native_registry_build.py",
            "notes": (
                "Native (schemaVersion 4) counterpart of the 2026-03-28 legacy registry "
                "snapshot. The legacy registry files stay authoritative for the v1 "
                "intermediate representation and are not replaced by this file."
            ),
        },
        "definition_ids": sorted(definition_ids),
        "bases": bases,
        "admission_rate": {
            "windows_per_minute": int(ADMISSION_RATE_WINDOWS_PER_MINUTE),
            "per_minute_limit_caps": dict(sorted(ADMISSION_PER_MINUTE_LIMIT_CAPS.items())),
            "source": _ADMISSION_RATE_SOURCE,
        },
    }


def _normalize_definition_ids(facts: Mapping[str, Any]) -> frozenset[str]:
    raw_ids = facts.get("entityIds")
    if not isinstance(raw_ids, Sequence) or isinstance(raw_ids, (str, bytes)):
        raise ValueError("registry facts entityIds must be a list of definition ids")
    definition_ids = {str(entry).strip() for entry in raw_ids if str(entry).strip()}
    if len(definition_ids) != len(raw_ids):
        raise ValueError("registry facts entityIds contain blank or duplicate entries")
    expected_count = facts.get("entityCount")
    if isinstance(expected_count, int) and expected_count != len(definition_ids):
        raise ValueError(
            f"registry facts entityCount {expected_count} disagrees with {len(definition_ids)} ids"
        )
    return frozenset(definition_ids)


def _normalize_bases(
    facts: Mapping[str, Any],
    *,
    definition_ids: frozenset[str],
) -> list[dict[str, Any]]:
    raw_bases = facts.get("bases")
    if not isinstance(raw_bases, Sequence) or isinstance(raw_bases, (str, bytes)):
        raise ValueError("registry facts bases must be a list")

    bases: list[dict[str, Any]] = []
    for raw_base in raw_bases:
        if not isinstance(raw_base, Mapping):
            raise ValueError("registry facts base entry must be a mapping")
        base_id = str(raw_base.get("id", "")).strip()
        if not base_id:
            raise ValueError("registry facts base entry is missing an id")
        bases.append(
            {
                "id": base_id,
                "name": str(raw_base.get("name", "")),
                "placeableArea": _normalize_placeable_area(base_id, raw_base.get("placeableArea")),
                "outerRing": _normalize_outer_ring(base_id, raw_base.get("outerRing")),
                "builtinEntities": _normalize_builtin_entities(
                    base_id,
                    raw_base.get("builtinEntities"),
                    expected_count=raw_base.get("builtinEntityCount"),
                    definition_ids=definition_ids,
                ),
            }
        )

    base_ids = [entry["id"] for entry in bases]
    if len(set(base_ids)) != len(base_ids):
        raise ValueError("registry facts bases contain duplicate ids")
    bases.sort(key=lambda entry: str(entry["id"]))
    return bases


def _normalize_placeable_area(base_id: str, raw_area: Any) -> dict[str, int]:
    if not isinstance(raw_area, Mapping):
        raise ValueError(f"base {base_id!r} is missing placeableArea")
    width = raw_area.get("width")
    height = raw_area.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError(f"base {base_id!r} has a non-positive integer placeableArea")
    return {"width": int(width), "height": int(height)}


def _normalize_outer_ring(base_id: str, raw_ring: Any) -> dict[str, int]:
    if not isinstance(raw_ring, Mapping):
        raise ValueError(f"base {base_id!r} is missing outerRing")
    ring: dict[str, int] = {}
    for side in ("top", "right", "bottom", "left"):
        value = raw_ring.get(side)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"base {base_id!r} outerRing.{side} must be a non-negative integer")
        ring[side] = int(value)
    return ring


def _normalize_builtin_entities(
    base_id: str,
    raw_entities: Any,
    *,
    expected_count: Any,
    definition_ids: frozenset[str],
) -> list[dict[str, Any]]:
    if raw_entities is None:
        raw_entities = []
    if not isinstance(raw_entities, Sequence) or isinstance(raw_entities, (str, bytes)):
        raise ValueError(f"base {base_id!r} builtinEntities must be a list")
    if isinstance(expected_count, int) and expected_count != len(raw_entities):
        raise ValueError(
            f"base {base_id!r} builtinEntityCount {expected_count} disagrees with "
            f"{len(raw_entities)} entries"
        )

    entities: list[dict[str, Any]] = []
    for raw_entity in raw_entities:
        if not isinstance(raw_entity, Mapping):
            raise ValueError(f"base {base_id!r} builtin entity must be a mapping")
        entity_id = str(raw_entity.get("id", "")).strip()
        definition_id = str(raw_entity.get("definitionId", "")).strip()
        if not entity_id:
            raise ValueError(f"base {base_id!r} builtin entity is missing an id")
        if definition_id not in definition_ids:
            raise ValueError(
                f"base {base_id!r} builtin entity {entity_id!r} references unknown "
                f"definitionId {definition_id!r}"
            )
        position = raw_entity.get("position")
        if not isinstance(position, Mapping):
            raise ValueError(f"base {base_id!r} builtin entity {entity_id!r} is missing position")
        x = position.get("x")
        y = position.get("y")
        if not isinstance(x, int) or not isinstance(y, int) or isinstance(x, bool) or isinstance(y, bool):
            raise ValueError(
                f"base {base_id!r} builtin entity {entity_id!r} position must hold integers"
            )
        rotation = raw_entity.get("rotation")
        if rotation not in (0, 90, 180, 270) or isinstance(rotation, bool):
            raise ValueError(
                f"base {base_id!r} builtin entity {entity_id!r} rotation {rotation!r} is not "
                "one of 0/90/180/270"
            )
        entities.append(
            {
                "id": entity_id,
                "definitionId": definition_id,
                "position": {"x": int(x), "y": int(y)},
                "rotation": int(rotation),
            }
        )
    return entities


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive native_registry_v3.json from the upstream registry fact dump.",
    )
    parser.add_argument(
        "--registry-facts",
        type=Path,
        default=_DEFAULT_REGISTRY_FACTS_PATH,
        help="path to the upstream registry fact dump (registry_facts.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT_PATH,
        help="path of the native registry JSON to write",
    )
    args = parser.parse_args(argv)

    facts = load_strict_json(Path(args.registry_facts))
    if not isinstance(facts, Mapping):
        raise SystemExit("registry facts payload must be a JSON object")
    payload = build_native_registry_payload(facts)
    atomic_write_json(Path(args.output), payload)
    print(
        f"wrote {args.output} "
        f"({len(payload['definition_ids'])} definition ids, {len(payload['bases'])} bases)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
