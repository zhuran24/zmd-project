"""Lowering from the v1 blueprint IR into the upstream native blueprint document.

The exporter keeps producing the legacy (`schema: "industrial-planner-blueprint"`)
document as its internal intermediate representation - the validator, the
throughput audit and the delivery manifest all read it.  This module lowers that
IR into the document the current upstream application actually writes
(`schemaVersion: 4`, no `schema` string, no `blueprintVersion`).

The lowering is a Python re-implementation of the upstream conversion chain:

* device id remapping and rotation compensation - upstream
  `src/shared/storage/legacy-blueprint-import.ts:34-107` (stage A) followed by
  `src/shared/blueprint-device-id-migration.ts:45-116` (stage B, rotation-neutral);
* config reshaping and the derived warehouse slot links - upstream
  `legacy-blueprint-import.ts:304-351`, `:687-733`, `:787-837`, `:898-925`;
* `initialGridPoint` - upstream `legacy-blueprint-import.ts:1366-1386`.

Everything that cannot be grounded in that chain fails closed: an unregistered
`typeId` or an unregistered config key raises instead of being passed through,
because upstream silently accepts (and then silently mis-simulates) both.

This module is a sidecar: nothing in the exporter imports it, so it stays out of
the close-kernel import-time closure and the native chain can evolve without a
P1.2 reseal.  `native_export_entry` is the operator-facing way in.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Mapping, Sequence

# Native document constants.  They deliberately live here and not next to the
# four legacy constants in `mapping_registry`: that module is a close-kernel
# sealed source file, and this whole native chain stays outside the kernel's
# import-time closure.  `schemaVersion` is the document schema number (4), not
# the application generation (v3); `version` is a free-text label and
# `description` is a required string that may be empty.  A native document has
# deliberately no `schema` string and no `blueprintVersion`.
INDUSTRIAL_PLANNER_NATIVE_SCHEMA_VERSION = 4
INDUSTRIAL_PLANNER_NATIVE_DOCUMENT_VERSION = ""
INDUSTRIAL_PLANNER_NATIVE_DOCUMENT_DESCRIPTION = ""

NATIVE_DOCUMENT_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "schemaVersion",
    "blueprintId",
    "version",
    "name",
    "description",
    "baseId",
    "initialGridPoint",
    "entities",
    "entityOrder",
    "slotLinks",
    "createdAt",
    "updatedAt",
)

# v1 typeId -> (native definitionId, rotation compensation in degrees).
#
# The compensation column exists because this package's device registry snapshot
# (2026-03-28) and the current upstream port geometry disagree; upstream applies
# the very same offsets when it ingests a legacy document
# (`legacy-blueprint-import.ts:34-107`).  The key set must stay exactly equal to
# the 43 ids in `device_type_registry.json` - that equality is asserted by
# `src/tests/test_industrial_planner_native_document.py`.
NATIVE_BLUEPRINT_LOWERING: dict[str, tuple[str, int]] = {
    "belt_straight_1x1": ("belt_straight_1x1", 0),
    "belt_turn_ccw_1x1": ("belt_turn_cw_1x1", 270),
    "belt_turn_cw_1x1": ("belt_turn_ccw_1x1", 0),
    "item_liquid_cleaner_1": ("liquid_cleaner_1", 0),
    "item_log_admission": ("log_admission", 0),
    "item_log_connector": ("log_connector", 0),
    "item_log_converger": ("log_converger", 90),
    "item_log_splitter": ("log_splitter", 90),
    "item_pipe_admission": ("pipe_admission", 0),
    "item_pipe_connector": ("pipe_connector", 0),
    "item_pipe_converger": ("pipe_converger", 90),
    "item_pipe_splitter": ("pipe_splitter", 90),
    "item_port_cmpt_mc_1": ("cmpt_mc_1", 0),
    "item_port_dismantler_1": ("dismantler_1", 0),
    "item_port_filling_pd_mc_1": ("filling_pd_mc_1", 0),
    "item_port_furnance_1": ("furnance_1", 0),
    "item_port_grinder_1": ("grinder_1", 0),
    "item_port_hydro_planter_1": ("hydro_planter_1", 0),
    "item_port_liquid_filling_pd_mc_1": ("liquid_filling_pd_mc_1", 0),
    "item_port_liquid_furnance_1": ("liquid_furnance_1", 0),
    "item_port_liquid_storager_1": ("liquid_storager_1", 0),
    "item_port_loader_1": ("loader_1", 0),
    "item_port_log_hongs_bus": ("log_hongs_bus", 0),
    "item_port_log_hongs_bus_source": ("log_hongs_bus_source", 0),
    "item_port_mix_pool_1": ("mix_pool_1", 0),
    "item_port_planter_1": ("planter_1", 0),
    "item_port_power_diffuser_1": ("power_diffuser_1", 0),
    "item_port_power_sta_1": ("power_sta_1", 0),
    "item_port_seedcol_1": ("seedcol_1", 0),
    "item_port_shaper_1": ("shaper_1", 0),
    "item_port_sp_hub_1": ("sp_hub_1", 0),
    "item_port_storager_1": ("storager_1", 0),
    "item_port_thickener_1": ("thickener_1", 0),
    "item_port_tools_asm_mc_1": ("tools_asm_mc_1", 0),
    "item_port_udpipe_loader_1": ("udpipe_loader_1", 0),
    "item_port_udpipe_unloader_1": ("udpipe_unloader_1", 0),
    "item_port_unloader_1": ("unloader_1", 180),
    "item_port_water_pump_1": ("water_pump_1", 0),
    "item_port_winder_1": ("winder_1", 0),
    "item_port_xiranite_oven_1": ("xiranite_oven_1", 0),
    "pipe_straight_1x1": ("pipe_straight_1x1", 0),
    "pipe_turn_ccw_1x1": ("pipe_turn_cw_1x1", 270),
    "pipe_turn_cw_1x1": ("pipe_turn_ccw_1x1", 0),
}

WAREHOUSE_SENTINEL_ENTITY_ID = "warehouse"
_WAREHOUSE_SLOT_GROUP_ID = "warehouse"
_UNLOADER_BUFFER_SLOT_GROUP_ID = "unloader_buffer"
_UNLOADER_BUFFER_SLOT_ID = "slot_1"
_SHARE_ALL_LINK_TYPE = "share-all"
_WAREHOUSE_SUBMIT_CHANNEL_ID = "warehouse_submit"
_WAREHOUSE_SUBMIT_RECIPE_ID = "r_warehouse_submit"

_UNLOADER_IGNORE_STOCK_CONFIG_KEY = "storageSlotGroups[0].slots[0].ignoreStock"
_ADMISSION_ACCEPT_RULE_CONFIG_KEY = "portGroups[0].ports[0].acceptRule"
_ADMISSION_RULE_CONFIG_KEY = "portGroups[0].ports[0].admissionRule"

# Per-typeId whitelists of the legacy config keys this lowering knows how to
# translate.  Anything else raises - see the module docstring.
_UNLOADER_CONFIG_KEYS = frozenset({"pickupItemId", "pickupIgnoreInventory", "protocolHubOutputs"})
_ADMISSION_CONFIG_KEYS = frozenset({"admissionItemId"})
_STORAGER_CONFIG_KEYS = frozenset({"submitToWarehouse"})
_ADMISSION_TYPE_IDS = frozenset({"item_log_admission", "item_pipe_admission"})

STORAGER_SUBMIT_DISABLED_WARNING = (
    "native lowering: submitToWarehouse=false has no faithful native encoding; "
    "storager placement defaults will re-enable warehouse submission"
)

_HEX_RUN_PATTERN = re.compile(r"[0-9a-f]{8,}")
_ENTITY_ID_PREFIX_FALLBACK_LENGTH = 8


@dataclass(frozen=True)
class NativeLoweringResult:
    """Native document plus every warning raised while lowering into it."""

    document: dict[str, Any]
    warnings: tuple[str, ...]


def lower_v1_blueprint_to_native(
    v1_blueprint: Mapping[str, Any],
    *,
    document_id: str | None = None,
    created_at: str | None = None,
) -> NativeLoweringResult:
    """Lower a v1 IR blueprint document into the native (schemaVersion 4) document.

    Args:
        v1_blueprint: the legacy document produced by the exporter.
        document_id: overrides the native `blueprintId`; defaults to the v1 `id`.
        created_at: overrides `createdAt`/`updatedAt`; defaults to the v1 `createdAt`.
    """

    if not isinstance(v1_blueprint, Mapping):
        raise ValueError("native lowering: v1 blueprint payload must be a mapping")

    raw_devices = v1_blueprint.get("devices")
    if not isinstance(raw_devices, Sequence) or isinstance(raw_devices, (str, bytes)):
        raise ValueError("native lowering: v1 blueprint devices must be a list")

    resolved_document_id = str(document_id if document_id is not None else v1_blueprint.get("id", "")).strip()
    if not resolved_document_id:
        raise ValueError("native lowering: v1 blueprint id is required for blueprintId")
    resolved_created_at = str(
        created_at if created_at is not None else v1_blueprint.get("createdAt", "")
    ).strip()
    if not resolved_created_at:
        raise ValueError("native lowering: v1 blueprint createdAt is required")
    resolved_name = str(v1_blueprint.get("name", "")).strip()
    if not resolved_name:
        raise ValueError("native lowering: v1 blueprint name is required")
    resolved_base_id = str(v1_blueprint.get("baseId", "")).strip()
    if not resolved_base_id:
        raise ValueError("native lowering: v1 blueprint baseId is required")

    entity_id_prefix = _entity_id_prefix(resolved_document_id)
    entities: dict[str, Any] = {}
    entity_order: list[str] = []
    slot_links: list[dict[str, Any]] = []
    warnings: list[str] = []

    for index, device in enumerate(raw_devices, start=1):
        if not isinstance(device, Mapping):
            raise ValueError(f"native lowering: device #{index} must be a mapping")
        entity_id = f"{entity_id_prefix}_{index:04d}"
        entity, device_slot_links, device_warnings = _lower_device(device, entity_id)
        entities[entity_id] = entity
        entity_order.append(entity_id)
        slot_links.extend(device_slot_links)
        warnings.extend(device_warnings)

    if set(entity_order) != set(entities) or len(entity_order) != len(entities):
        raise ValueError("native lowering: entityOrder must mirror the entities record exactly")

    slot_links.sort(key=lambda entry: (str(entry["source"]["entityId"]), str(entry["id"])))

    document = {
        "schemaVersion": int(INDUSTRIAL_PLANNER_NATIVE_SCHEMA_VERSION),
        "blueprintId": resolved_document_id,
        "version": str(INDUSTRIAL_PLANNER_NATIVE_DOCUMENT_VERSION),
        "name": resolved_name,
        "description": str(INDUSTRIAL_PLANNER_NATIVE_DOCUMENT_DESCRIPTION),
        "baseId": resolved_base_id,
        "initialGridPoint": _compute_initial_grid_point(raw_devices),
        "entities": entities,
        "entityOrder": entity_order,
        "slotLinks": slot_links,
        "createdAt": resolved_created_at,
        "updatedAt": resolved_created_at,
    }
    if tuple(document) != NATIVE_DOCUMENT_TOP_LEVEL_KEYS:
        raise ValueError("native lowering: produced an unexpected top-level key set")
    return NativeLoweringResult(
        document=document,
        warnings=tuple(sorted(set(warnings))),
    )


def _lower_device(
    device: Mapping[str, Any],
    entity_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Lower one v1 device into a native entity plus its derived slot links."""

    v1_type_id = str(device.get("typeId", "")).strip()
    lowering = NATIVE_BLUEPRINT_LOWERING.get(v1_type_id)
    if lowering is None:
        raise ValueError(
            f"native lowering: unregistered v1 typeId {v1_type_id!r} for entity {entity_id!r}; "
            "register it in NATIVE_BLUEPRINT_LOWERING instead of passing it through"
        )
    native_definition_id, rotation_offset = lowering

    raw_rotation = device.get("rotation", 0)
    if isinstance(raw_rotation, bool) or not isinstance(raw_rotation, int):
        raise ValueError(
            f"native lowering: entity {entity_id!r} rotation must be an integer, got {raw_rotation!r}"
        )
    if int(raw_rotation) % 90 != 0:
        raise ValueError(
            f"native lowering: entity {entity_id!r} rotation {raw_rotation!r} is not a multiple of 90"
        )
    native_rotation = (int(raw_rotation) + int(rotation_offset)) % 360

    origin = device.get("origin")
    if not isinstance(origin, Mapping):
        raise ValueError(f"native lowering: entity {entity_id!r} is missing an origin")
    position = {"x": _require_int(origin.get("x"), entity_id, "origin.x"),
                "y": _require_int(origin.get("y"), entity_id, "origin.y")}

    raw_config = device.get("config", {})
    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, Mapping):
        raise ValueError(f"native lowering: entity {entity_id!r} config must be a mapping")
    native_config, slot_links, warnings = _lower_config(
        v1_type_id,
        native_definition_id,
        raw_config,
        entity_id=entity_id,
    )

    entity = {
        "id": entity_id,
        "definitionId": native_definition_id,
        "position": position,
        "rotation": int(native_rotation),
        "config": native_config,
        "tags": [],
    }
    return entity, slot_links, warnings


def _lower_config(
    v1_type_id: str,
    native_definition_id: str,
    config: Mapping[str, Any],
    *,
    entity_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Translate one v1 config blob, deriving slot links where upstream does."""

    if not config:
        return {}, [], []

    if v1_type_id == "item_port_unloader_1":
        _reject_unregistered_config_keys(config, _UNLOADER_CONFIG_KEYS, v1_type_id, entity_id)
        return _lower_unloader_config(config, entity_id=entity_id)
    if v1_type_id in _ADMISSION_TYPE_IDS:
        _reject_unregistered_config_keys(config, _ADMISSION_CONFIG_KEYS, v1_type_id, entity_id)
        return _lower_admission_config(config, entity_id=entity_id), [], []
    if v1_type_id == "item_port_storager_1":
        _reject_unregistered_config_keys(config, _STORAGER_CONFIG_KEYS, v1_type_id, entity_id)
        return _lower_storager_config(config, entity_id=entity_id)

    raise ValueError(
        f"native lowering: unregistered v1 config key(s) "
        f"{sorted(str(key) for key in config)} on typeId {v1_type_id!r} "
        f"(definitionId {native_definition_id!r}, entity {entity_id!r}); "
        "no native encoding is registered for this device's config"
    )


def _lower_unloader_config(
    config: Mapping[str, Any],
    *,
    entity_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Upstream `convertLegacyUnloaderConfig` (`legacy-blueprint-import.ts:687-733`)."""

    pickup_item_id = config.get("pickupItemId")
    if not isinstance(pickup_item_id, str) or not pickup_item_id.strip():
        raise ValueError(
            f"native lowering: unloader entity {entity_id!r} carries pickup config "
            f"{sorted(str(key) for key in config)} without a usable pickupItemId; "
            "the native document has no faithful encoding for that shape"
        )

    hub_outputs = config.get("protocolHubOutputs")
    hub_ignore_inventory = False
    if hub_outputs is not None:
        if not isinstance(hub_outputs, Sequence) or isinstance(hub_outputs, (str, bytes)):
            raise ValueError(
                f"native lowering: unloader entity {entity_id!r} protocolHubOutputs must be a list"
            )
        if hub_outputs and isinstance(hub_outputs[0], Mapping):
            hub_ignore_inventory = hub_outputs[0].get("ignoreInventory") is True

    ignore_stock = config.get("pickupIgnoreInventory") is True or hub_ignore_inventory
    native_config = {_UNLOADER_IGNORE_STOCK_CONFIG_KEY: bool(ignore_stock)}
    slot_link = {
        "id": (
            f"warehouse-link:{entity_id}:{_UNLOADER_BUFFER_SLOT_GROUP_ID}:"
            f"{_UNLOADER_BUFFER_SLOT_ID}"
        ),
        "linkType": _SHARE_ALL_LINK_TYPE,
        "source": {
            "entityId": entity_id,
            "storageSlotGroupId": _UNLOADER_BUFFER_SLOT_GROUP_ID,
            "slotId": _UNLOADER_BUFFER_SLOT_ID,
        },
        "target": {
            "entityId": WAREHOUSE_SENTINEL_ENTITY_ID,
            "storageSlotGroupId": _WAREHOUSE_SLOT_GROUP_ID,
            "slotId": str(pickup_item_id),
        },
    }
    return native_config, [slot_link], []


def _lower_admission_config(config: Mapping[str, Any], *, entity_id: str) -> dict[str, Any]:
    """Upstream `convertLegacyAdmissionConfig` (`legacy-blueprint-import.ts:898-925`)."""

    admission_item_id = config.get("admissionItemId")
    if not isinstance(admission_item_id, str) or not admission_item_id.strip():
        raise ValueError(
            f"native lowering: admission entity {entity_id!r} is missing a usable admissionItemId"
        )
    item_id = str(admission_item_id)
    return {
        _ADMISSION_ACCEPT_RULE_CONFIG_KEY: {
            "base": {"kind": "item", "itemId": item_id},
            "exclude": [],
        },
        # `limit` mirrors upstream's legacy `admissionAmount` handling (absent -> null).
        # `perMinuteLimit` stays null on purpose: writing schemaVersion 4 skips the
        # 3 -> 4 normalization step, so an invented rate would never be corrected.
        _ADMISSION_RULE_CONFIG_KEY: {
            "itemId": item_id,
            "limit": None,
            "perMinuteLimit": None,
        },
    }


def _lower_storager_config(
    config: Mapping[str, Any],
    *,
    entity_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Upstream `convertLegacyStoragerConfig` (`legacy-blueprint-import.ts:787-837`)."""

    submit_to_warehouse = config.get("submitToWarehouse")
    if not isinstance(submit_to_warehouse, bool):
        raise ValueError(
            f"native lowering: storager entity {entity_id!r} submitToWarehouse must be a bool, "
            f"got {submit_to_warehouse!r}"
        )
    if submit_to_warehouse:
        return (
            {"channelRecipes": {_WAREHOUSE_SUBMIT_CHANNEL_ID: _WAREHOUSE_SUBMIT_RECIPE_ID}},
            [],
            [],
        )
    # Upstream drops the key entirely; the storager placement defaults then write
    # `channelRecipes.warehouse_submit` back in, so the exported intent is lost.
    # The official upstream converter behaves identically - the gap is reported,
    # not silently swallowed.
    return {}, [], [STORAGER_SUBMIT_DISABLED_WARNING]


def _reject_unregistered_config_keys(
    config: Mapping[str, Any],
    allowed_keys: frozenset[str],
    v1_type_id: str,
    entity_id: str,
) -> None:
    unregistered = sorted(str(key) for key in config if str(key) not in allowed_keys)
    if unregistered:
        raise ValueError(
            f"native lowering: unregistered v1 config key(s) {unregistered} on typeId "
            f"{v1_type_id!r} (entity {entity_id!r}); registered keys are "
            f"{sorted(allowed_keys)}"
        )


def _compute_initial_grid_point(devices: Sequence[Any]) -> dict[str, int]:
    """Upstream bounding-box centre (`legacy-blueprint-import.ts:1366-1386`).

    Only device anchors participate - the rotated footprint is deliberately not
    considered, matching upstream.  The rounding is JavaScript `Math.round`
    (half-up), which differs from Python's banker's rounding at `.5`.
    """

    xs: list[int] = []
    ys: list[int] = []
    for device in devices:
        if not isinstance(device, Mapping):
            continue
        origin = device.get("origin")
        if not isinstance(origin, Mapping):
            continue
        xs.append(int(origin.get("x", 0)))
        ys.append(int(origin.get("y", 0)))
    if not xs or not ys:
        return {"x": 0, "y": 0}
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {
        "x": _js_round(min_x + (max_x - min_x + 1) / 2),
        "y": _js_round(min_y + (max_y - min_y + 1) / 2),
    }


def _js_round(value: float) -> int:
    """JavaScript `Math.round`: ties go towards positive infinity."""

    return int(math.floor(float(value) + 0.5))


def _entity_id_prefix(document_id: str) -> str:
    """Derive a deterministic, readable entity id prefix from the document id.

    Mirrors upstream's `legacy_<8 hex>` shape (`legacy-blueprint-import.ts:1353-1364`)
    while keeping this repository's export hash visible: `ExactExport-4c3bc6df05c3`
    becomes `exact_4c3bc6df`.  Ids without a usable hex run fall back to a digest of
    the whole document id so the prefix stays deterministic.
    """

    match = _HEX_RUN_PATTERN.search(document_id.lower())
    if match is not None:
        return f"exact_{match.group(0)[:_ENTITY_ID_PREFIX_FALLBACK_LENGTH]}"
    digest = hashlib.sha256(document_id.encode("utf-8")).hexdigest()
    return f"exact_{digest[:_ENTITY_ID_PREFIX_FALLBACK_LENGTH]}"


def _require_int(value: Any, entity_id: str, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"native lowering: entity {entity_id!r} {field_name} must be an integer, got {value!r}"
        )
    return int(value)
