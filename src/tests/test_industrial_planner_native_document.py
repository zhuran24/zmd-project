"""Tests for the native (schemaVersion 4) IndustrialPlanner document lowering."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from src.adapters.industrial_planner.export_blueprint import (
    INDUSTRIAL_PLANNER_BUNDLE_FILENAMES,
    build_industrial_planner_export_bundle,
    write_industrial_planner_export_bundle,
)
import src.adapters.industrial_planner.native_export_entry as native_export_entry_module
from src.adapters.industrial_planner.native_export_entry import (
    INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME,
    build_native_blueprint_export,
    export_native_blueprint,
    render_native_blueprint_json,
)
from src.adapters.industrial_planner.native_document import (
    NATIVE_BLUEPRINT_LOWERING,
    STORAGER_SUBMIT_DISABLED_WARNING,
    NativeLoweringResult,
    lower_v1_blueprint_to_native,
)
from src.adapters.industrial_planner.native_validator import (
    load_native_registry,
    validate_native_blueprint_document,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FIXTURE_DIR = _REPO_ROOT / "data" / "examples" / "industrial_planner"
_ADAPTER_DIR = _REPO_ROOT / "src" / "adapters" / "industrial_planner"
_DEVICE_REGISTRY_PATH = _ADAPTER_DIR / "device_type_registry.json"
# Byte copy of the upstream converter's own output for the source blueprint below,
# produced by `convert-legacy-blueprint.ts` at upstream HEAD 7b946c16.  It is the
# only cross-engine evidence in the tree, so a missing copy is a loud failure.
_GOLDEN_PATH = Path(__file__).resolve().parent / "industrial_planner_native_golden_v1_sample.json"
_GOLDEN_SOURCE_BLUEPRINT_PATH = (
    _FIXTURE_DIR
    / "generated_outer_base_bundle_valley4_protocol_core"
    / "industrial_planner.blueprint.json"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _golden_native_document() -> dict[str, Any]:
    if not _GOLDEN_PATH.exists():
        raise AssertionError(f"native golden fixture is missing: {_GOLDEN_PATH}")
    return _load_json(_GOLDEN_PATH)


def _v1_document(devices: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    document = {
        "schema": "industrial-planner-blueprint",
        "id": "ExactExport-4c3bc6df05c3",
        "version": "1.0",
        "name": "Exact Export 2026-03-30T12:00:00Z",
        "createdAt": "2026-03-30T12:00:00Z",
        "baseId": "valley4_protocol_core",
        "devices": devices,
        "blueprintVersion": "1",
    }
    document.update(overrides)
    return document


def _minimal_native_document(**overrides: Any) -> dict[str, Any]:
    document = lower_v1_blueprint_to_native(
        _v1_document(
            [
                {"typeId": "item_port_grinder_1", "rotation": 0, "origin": {"x": 10, "y": 10}},
                {
                    "typeId": "item_log_admission",
                    "rotation": 90,
                    "origin": {"x": 12, "y": 10},
                    "config": {"admissionItemId": "item_iron_ore"},
                },
            ]
        )
    ).document
    document.update(overrides)
    return document


def _entity_multiset(document: dict[str, Any]) -> list[tuple[Any, ...]]:
    return sorted(
        (
            entity["definitionId"],
            entity["position"]["x"],
            entity["position"]["y"],
            entity["rotation"],
            json.dumps(entity["config"], sort_keys=True, ensure_ascii=False),
            tuple(entity["tags"]),
        )
        for entity in document["entities"].values()
    )


def _slot_link_multiset(document: dict[str, Any]) -> list[tuple[Any, ...]]:
    links = []
    for link in document["slotLinks"]:
        source_entity = document["entities"][link["source"]["entityId"]]
        links.append(
            (
                link["linkType"],
                source_entity["definitionId"],
                source_entity["position"]["x"],
                source_entity["position"]["y"],
                link["source"]["storageSlotGroupId"],
                link["source"]["slotId"],
                link["target"]["entityId"],
                link["target"]["storageSlotGroupId"],
                link["target"]["slotId"],
            )
        )
    return sorted(links)


# --- T1: golden equivalence against the upstream converter ---------------------


def test_lowering_matches_upstream_converter_golden_document() -> None:
    source = _load_json(_GOLDEN_SOURCE_BLUEPRINT_PATH)
    golden = _golden_native_document()

    lowered = lower_v1_blueprint_to_native(source).document

    assert lowered["schemaVersion"] == golden["schemaVersion"] == 4
    assert lowered["version"] == golden["version"]
    assert lowered["description"] == golden["description"]
    assert lowered["name"] == golden["name"]
    assert lowered["baseId"] == golden["baseId"]
    assert lowered["initialGridPoint"] == golden["initialGridPoint"] == {"x": 35, "y": 35}
    assert len(lowered["entities"]) == len(golden["entities"]) == 279
    assert len(lowered["entityOrder"]) == len(golden["entityOrder"]) == 279
    assert len(lowered["slotLinks"]) == len(golden["slotLinks"]) == 52
    assert _entity_multiset(lowered) == _entity_multiset(golden)
    assert _slot_link_multiset(lowered) == _slot_link_multiset(golden)
    assert validate_native_blueprint_document(lowered).is_valid is True


# --- T2: differential table completeness --------------------------------------


def test_lowering_table_covers_every_registered_v1_type_id() -> None:
    device_registry = _load_json(_DEVICE_REGISTRY_PATH)
    v1_type_ids = {str(entry["id"]) for entry in device_registry["device_types"]}
    registry = load_native_registry()

    assert len(v1_type_ids) == 43
    assert set(NATIVE_BLUEPRINT_LOWERING) == v1_type_ids
    assert len(registry.definition_ids) == 62
    orphans = sorted(
        definition_id
        for definition_id, _ in NATIVE_BLUEPRINT_LOWERING.values()
        if definition_id not in registry.definition_ids
    )
    assert orphans == []
    assert all(offset in (0, 90, 180, 270) for _, offset in NATIVE_BLUEPRINT_LOWERING.values())


# --- T3: rotation compensation ------------------------------------------------


@pytest.mark.parametrize(
    ("v1_type_id", "v1_rotation", "expected_definition_id", "expected_rotation"),
    [
        ("item_port_unloader_1", 90, "unloader_1", 270),
        ("item_log_splitter", 0, "log_splitter", 90),
        ("item_log_converger", 270, "log_converger", 0),
        ("belt_turn_ccw_1x1", 0, "belt_turn_cw_1x1", 270),
        ("pipe_turn_ccw_1x1", 180, "pipe_turn_cw_1x1", 90),
        ("belt_turn_cw_1x1", 90, "belt_turn_ccw_1x1", 90),
        ("item_pipe_splitter", 0, "pipe_splitter", 90),
    ],
)
def test_rotation_compensation_is_pinned_per_device(
    v1_type_id: str,
    v1_rotation: int,
    expected_definition_id: str,
    expected_rotation: int,
) -> None:
    device: dict[str, Any] = {
        "typeId": v1_type_id,
        "rotation": v1_rotation,
        "origin": {"x": 3, "y": 4},
    }
    if v1_type_id == "item_port_unloader_1":
        device["config"] = {"pickupItemId": "item_iron_ore", "pickupIgnoreInventory": True}

    lowered = lower_v1_blueprint_to_native(_v1_document([device])).document
    entity = next(iter(lowered["entities"].values()))

    assert entity["definitionId"] == expected_definition_id
    assert entity["rotation"] == expected_rotation
    assert entity["position"] == {"x": 3, "y": 4}


# --- T4: entityOrder invariant ------------------------------------------------


def test_entity_order_mirrors_entities_without_gaps_or_duplicates() -> None:
    lowered = lower_v1_blueprint_to_native(_load_json(_GOLDEN_SOURCE_BLUEPRINT_PATH)).document

    entity_order = lowered["entityOrder"]
    assert set(entity_order) == set(lowered["entities"])
    assert len(entity_order) == len(lowered["entities"])
    assert len(set(entity_order)) == len(entity_order)
    assert all(lowered["entities"][entity_id]["id"] == entity_id for entity_id in entity_order)


# --- T5: JavaScript half-up rounding -----------------------------------------


def test_initial_grid_point_uses_javascript_half_up_rounding() -> None:
    devices = [
        {"typeId": "item_port_grinder_1", "rotation": 0, "origin": {"x": 0, "y": 0}},
        {"typeId": "item_port_grinder_1", "rotation": 0, "origin": {"x": 68, "y": 68}},
    ]

    lowered = lower_v1_blueprint_to_native(_v1_document(devices)).document

    # 0 + (68 - 0 + 1) / 2 == 34.5 -> JS Math.round gives 35, Python round() gives 34.
    assert lowered["initialGridPoint"] == {"x": 35, "y": 35}
    assert round(34.5) == 34


def test_initial_grid_point_defaults_to_origin_for_an_empty_device_list() -> None:
    lowered = lower_v1_blueprint_to_native(_v1_document([])).document

    assert lowered["initialGridPoint"] == {"x": 0, "y": 0}
    assert lowered["entities"] == {}
    assert lowered["entityOrder"] == []


# --- T6: determinism ----------------------------------------------------------


def test_lowering_is_byte_deterministic_for_identical_inputs() -> None:
    source = _load_json(_GOLDEN_SOURCE_BLUEPRINT_PATH)

    first = lower_v1_blueprint_to_native(source).document
    second = lower_v1_blueprint_to_native(copy.deepcopy(source)).document

    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second, sort_keys=True, ensure_ascii=False
    )


# --- T7: the three config shapes the exporter can emit ------------------------


def test_unloader_config_lowers_to_ignore_stock_plus_one_warehouse_link() -> None:
    devices = [
        {
            "typeId": "item_port_unloader_1",
            "rotation": 0,
            "origin": {"x": 0, "y": 10},
            "config": {
                "pickupItemId": "item_iron_ore",
                "pickupIgnoreInventory": True,
                "protocolHubOutputs": [
                    {"portId": "p_out_mid", "itemId": "item_iron_ore", "ignoreInventory": True}
                ],
            },
        }
    ]

    result = lower_v1_blueprint_to_native(_v1_document(devices))
    entity = next(iter(result.document["entities"].values()))

    assert entity["config"] == {"storageSlotGroups[0].slots[0].ignoreStock": True}
    assert "pickupItemId" not in entity["config"]
    assert "protocolHubOutputs" not in entity["config"]
    assert len(result.document["slotLinks"]) == 1
    link = result.document["slotLinks"][0]
    assert link["linkType"] == "share-all"
    assert link["source"] == {
        "entityId": entity["id"],
        "storageSlotGroupId": "unloader_buffer",
        "slotId": "slot_1",
    }
    assert link["target"] == {
        "entityId": "warehouse",
        "storageSlotGroupId": "warehouse",
        "slotId": "item_iron_ore",
    }
    assert result.warnings == ()


def test_admission_config_lowers_to_accept_and_admission_rules() -> None:
    devices = [
        {
            "typeId": "item_log_admission",
            "rotation": 270,
            "origin": {"x": 64, "y": 1},
            "config": {"admissionItemId": "item_bottled_rec_hp_3"},
        }
    ]

    lowered = lower_v1_blueprint_to_native(_v1_document(devices)).document
    entity = next(iter(lowered["entities"].values()))

    assert entity["config"] == {
        "portGroups[0].ports[0].acceptRule": {
            "base": {"kind": "item", "itemId": "item_bottled_rec_hp_3"},
            "exclude": [],
        },
        "portGroups[0].ports[0].admissionRule": {
            "itemId": "item_bottled_rec_hp_3",
            "limit": None,
            "perMinuteLimit": None,
        },
    }
    assert lowered["slotLinks"] == []


def test_storager_submit_disabled_lowers_to_empty_config_and_warns() -> None:
    devices = [
        {
            "typeId": "item_port_storager_1",
            "rotation": 0,
            "origin": {"x": 5, "y": 5},
            "config": {"submitToWarehouse": False},
        }
    ]

    result = lower_v1_blueprint_to_native(_v1_document(devices))
    entity = next(iter(result.document["entities"].values()))

    assert entity["definitionId"] == "storager_1"
    assert entity["config"] == {}
    assert result.warnings == (STORAGER_SUBMIT_DISABLED_WARNING,)


def test_storager_submit_enabled_lowers_to_warehouse_submit_channel_recipe() -> None:
    devices = [
        {
            "typeId": "item_port_storager_1",
            "rotation": 0,
            "origin": {"x": 5, "y": 5},
            "config": {"submitToWarehouse": True},
        }
    ]

    result = lower_v1_blueprint_to_native(_v1_document(devices))
    entity = next(iter(result.document["entities"].values()))

    assert entity["config"] == {"channelRecipes": {"warehouse_submit": "r_warehouse_submit"}}
    assert result.warnings == ()


# --- T8: the exporter stays a v1-only surface ---------------------------------


def _module_level_imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_sealed_exporter_modules_never_import_the_native_chain() -> None:
    native_modules = {
        f"src.adapters.industrial_planner.{name}"
        for name in ("native_document", "native_validator", "native_export_entry")
    }

    for sealed_name in ("__init__.py", "export_blueprint.py", "mapping_registry.py"):
        offenders = _module_level_imports(_ADAPTER_DIR / sealed_name) & native_modules
        assert not offenders, (
            f"{sealed_name} imports {sorted(offenders)} at module level. Those three files are "
            "close-kernel sealed sources, so an import-time edge would pull the native chain into "
            "the kernel's import-time closure and turn every later native change into a full P1.2 "
            "reseal. The native chain runs downstream of the exporter on purpose - see "
            "native_export_entry's module docstring."
        )


def test_native_lowering_does_not_disturb_the_v1_intermediate_representation() -> None:
    bundle_dir = _FIXTURE_DIR / "generated_full_demand_bundle"
    payload = _load_json(_FIXTURE_DIR / "full_demand_recipe_capacity_canonical_blueprint.json")

    bundle = build_industrial_planner_export_bundle(blueprint_payload=payload)

    # These four checked-in artifacts are reproducible from the current code at HEAD;
    # they carry every number the CI comparison files derive from, so byte equality
    # here is the earliest signal that the native batch perturbed the IR.
    for key, filename in (
        ("blueprint", "industrial_planner.blueprint.json"),
        ("throughput_report", "throughput_report.json"),
    ):
        expected = (bundle_dir / filename).read_text(encoding="utf-8")
        assert json.dumps(bundle[key], indent=2, ensure_ascii=False) == expected
    for key, filename in (
        ("validation_report_markdown", "validation_report.md"),
        ("throughput_report_markdown", "throughput_report.md"),
    ):
        assert bundle[key] == (bundle_dir / filename).read_text(encoding="utf-8")
    assert "native_blueprint" not in bundle
    assert build_native_blueprint_export(bundle["blueprint"]).validation_report["is_valid"] is True


def test_native_lowering_warnings_never_reach_the_v1_bundle() -> None:
    payload = _load_json(_FIXTURE_DIR / "minimal_canonical_blueprint.json")
    payload = copy.deepcopy(payload)
    payload["facilities"].append(
        {
            "instance_id": "storage_box_native_probe",
            "facility_type": "protocol_storage_box",
            "anchor": {"x": 20, "y": 20},
            "orientation": 0,
        }
    )

    bundle = build_industrial_planner_export_bundle(blueprint_payload=payload)
    lowering = lower_v1_blueprint_to_native(bundle["blueprint"])

    assert any(
        device["typeId"] == "item_port_storager_1" for device in bundle["blueprint"]["devices"]
    )
    assert STORAGER_SUBMIT_DISABLED_WARNING in lowering.warnings
    assert STORAGER_SUBMIT_DISABLED_WARNING not in bundle["warnings"]
    assert STORAGER_SUBMIT_DISABLED_WARNING not in bundle["compatibility_manifest"]["warnings"]


# --- T9 / T10: lowering fails closed ------------------------------------------


def test_lowering_rejects_an_unregistered_v1_type_id() -> None:
    devices = [{"typeId": "item_port_unknown_9", "rotation": 0, "origin": {"x": 0, "y": 0}}]

    with pytest.raises(ValueError, match="unregistered v1 typeId"):
        lower_v1_blueprint_to_native(_v1_document(devices))


def test_lowering_rejects_an_unregistered_config_key() -> None:
    devices = [
        {
            "typeId": "item_port_storager_1",
            "rotation": 0,
            "origin": {"x": 0, "y": 0},
            "config": {"submitMode": "every-tick"},
        }
    ]

    with pytest.raises(ValueError, match="unregistered v1 config key"):
        lower_v1_blueprint_to_native(_v1_document(devices))


def test_lowering_rejects_config_on_a_device_without_a_registered_config_shape() -> None:
    devices = [
        {
            "typeId": "item_port_grinder_1",
            "rotation": 0,
            "origin": {"x": 0, "y": 0},
            "config": {"pickupItemId": "item_iron_ore"},
        }
    ]

    with pytest.raises(ValueError, match="unregistered v1 config key"):
        lower_v1_blueprint_to_native(_v1_document(devices))


def test_lowering_rejects_unloader_config_without_a_pickup_item() -> None:
    devices = [
        {
            "typeId": "item_port_unloader_1",
            "rotation": 0,
            "origin": {"x": 0, "y": 0},
            "config": {"pickupIgnoreInventory": True},
        }
    ]

    with pytest.raises(ValueError, match="without a usable pickupItemId"):
        lower_v1_blueprint_to_native(_v1_document(devices))


# --- T11-T17: the native validator --------------------------------------------


@pytest.mark.parametrize("schema_version", [3, 5, 0, 3.5, "4", None])
def test_native_validator_rejects_every_non_four_schema_version(schema_version: Any) -> None:
    document = _minimal_native_document()
    if schema_version is None:
        document.pop("schemaVersion")
    else:
        document["schemaVersion"] = schema_version

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert any(error.startswith(("N1", "N2")) for error in report.errors)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("drop_description", "N1"),
        ("numeric_version", "N4"),
        ("blank_name", "N3"),
        ("extra_top_level_field", "N1"),
    ],
)
def test_native_validator_rejects_broken_top_level_fields(
    mutation: str,
    expected_code: str,
) -> None:
    document = _minimal_native_document()
    if mutation == "drop_description":
        document.pop("description")
    elif mutation == "numeric_version":
        document["version"] = 1
    elif mutation == "blank_name":
        document["name"] = "   "
    else:
        document["schema"] = "industrial-planner-blueprint"

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert any(error.startswith(expected_code) for error in report.errors)


@pytest.mark.parametrize("mutation", ["missing", "unknown", "duplicate"])
def test_native_validator_rejects_entity_order_drift(mutation: str) -> None:
    document = _minimal_native_document()
    if mutation == "missing":
        document["entityOrder"] = document["entityOrder"][:-1]
    elif mutation == "unknown":
        document["entityOrder"] = [*document["entityOrder"], "exact_ffffffff_9999"]
    else:
        document["entityOrder"] = [document["entityOrder"][0], *document["entityOrder"]]

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert any(error.startswith("N7") for error in report.errors)


@pytest.mark.parametrize(
    "mutation",
    ["rotation", "definition_id", "id_mismatch", "tags", "float_position"],
)
def test_native_validator_rejects_broken_entities(mutation: str) -> None:
    document = _minimal_native_document()
    entity_id = document["entityOrder"][0]
    entity = document["entities"][entity_id]
    if mutation == "rotation":
        entity["rotation"] = 45
    elif mutation == "definition_id":
        entity["definitionId"] = "nope"
    elif mutation == "id_mismatch":
        entity["id"] = "exact_ffffffff_0001"
    elif mutation == "tags":
        entity["tags"] = ["x"]
    else:
        entity["position"] = {"x": 1.5, "y": 2}

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert any(error.startswith("N8") for error in report.errors)


@pytest.mark.parametrize("mutation", ["nonsense", "dangling_entity", "duplicate_id"])
def test_native_validator_rejects_broken_slot_links(mutation: str) -> None:
    document = _minimal_native_document()
    entity_id = document["entityOrder"][0]
    link = {
        "id": "warehouse-link:probe:unloader_buffer:slot_1",
        "linkType": "share-all",
        "source": {
            "entityId": entity_id,
            "storageSlotGroupId": "unloader_buffer",
            "slotId": "slot_1",
        },
        "target": {
            "entityId": "warehouse",
            "storageSlotGroupId": "warehouse",
            "slotId": "item_iron_ore",
        },
    }
    if mutation == "nonsense":
        document["slotLinks"] = [{"nonsense": True}]
    elif mutation == "dangling_entity":
        link["source"]["entityId"] = "exact_ffffffff_0001"
        document["slotLinks"] = [link]
    else:
        document["slotLinks"] = [link, copy.deepcopy(link)]

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert any(error.startswith("N11") for error in report.errors)


@pytest.mark.parametrize(
    ("definition_id", "per_minute_limit"),
    [("log_admission", 7), ("log_admission", 36), ("pipe_admission", 126)],
)
def test_native_validator_rejects_illegal_admission_rates(
    definition_id: str,
    per_minute_limit: int,
) -> None:
    document = _minimal_native_document()
    entity = next(
        entity
        for entity in document["entities"].values()
        if entity["definitionId"] == "log_admission"
    )
    entity["definitionId"] = definition_id
    entity["config"]["portGroups[0].ports[0].admissionRule"]["perMinuteLimit"] = per_minute_limit

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert any(error.startswith("N10") for error in report.errors)


def test_native_validator_accepts_a_legal_admission_rate() -> None:
    document = _minimal_native_document()
    entity = next(
        entity
        for entity in document["entities"].values()
        if entity["definitionId"] == "log_admission"
    )
    entity["config"]["portGroups[0].ports[0].admissionRule"]["perMinuteLimit"] = 30

    assert validate_native_blueprint_document(document).is_valid is True


def test_native_validator_rejects_an_unknown_base_id() -> None:
    document = _minimal_native_document(baseId="nonexistent_base")

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert any(error.startswith("N12") for error in report.errors)


# --- T18: base builtin collisions ---------------------------------------------


def test_native_validator_rejects_entities_that_duplicate_base_builtins() -> None:
    document = _minimal_native_document()
    entity_id = document["entityOrder"][0]
    document["entities"][entity_id].update(
        {
            "definitionId": "log_hongs_bus_source",
            "position": {"x": -4, "y": -4},
            "rotation": 0,
        }
    )

    report = validate_native_blueprint_document(document)

    assert report.is_valid is False
    assert report.base_builtin_conflict_count == 1
    assert any(error.startswith("N13") for error in report.errors)


def test_real_export_never_collides_with_valley4_base_builtins() -> None:
    payload = _load_json(_FIXTURE_DIR / "full_demand_recipe_capacity_canonical_blueprint.json")

    bundle = build_industrial_planner_export_bundle(blueprint_payload=payload)
    document = build_native_blueprint_export(bundle["blueprint"]).document
    report = validate_native_blueprint_document(document)

    assert report.base_builtin_conflict_count == 0
    assert report.is_valid is True
    assert any(
        entity["definitionId"] == "log_hongs_bus" for entity in document["entities"].values()
    )


# --- T19: the entry point refuses to emit an invalid native document ----------


def _v1_blueprint_from_minimal_fixture() -> dict[str, Any]:
    payload = _load_json(_FIXTURE_DIR / "minimal_canonical_blueprint.json")
    return build_industrial_planner_export_bundle(blueprint_payload=payload)["blueprint"]


def test_entry_point_fails_closed_when_the_native_document_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken_lowering(*args: Any, **kwargs: Any) -> NativeLoweringResult:
        document = lower_v1_blueprint_to_native(*args, **kwargs).document
        document["schemaVersion"] = 5
        return NativeLoweringResult(document=document, warnings=())

    v1_blueprint = _v1_blueprint_from_minimal_fixture()
    v1_path = tmp_path / "industrial_planner.blueprint.json"
    v1_path.write_text(json.dumps(v1_blueprint), encoding="utf-8")
    output_path = tmp_path / "native" / INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME
    monkeypatch.setattr(
        native_export_entry_module,
        "lower_v1_blueprint_to_native",
        broken_lowering,
    )

    with pytest.raises(ValueError, match="native blueprint document failed validation"):
        build_native_blueprint_export(v1_blueprint)
    with pytest.raises(ValueError, match="native blueprint document failed validation"):
        export_native_blueprint(v1_blueprint_path=v1_path, output_path=output_path)

    assert not output_path.exists()
    assert list(tmp_path.glob("**/*.tmp")) == []


def test_the_v1_bundle_never_carries_the_native_document(tmp_path: Path) -> None:
    payload = _load_json(_FIXTURE_DIR / "minimal_canonical_blueprint.json")
    output_dir = tmp_path / "exports" / "industrial_planner"

    written = write_industrial_planner_export_bundle(
        output_dir=output_dir,
        blueprint_payload=payload,
    )

    # The bundle is a six-file v1 surface and stays one; the native document is a
    # separate deliverable produced by the entry point below.
    assert len(INDUSTRIAL_PLANNER_BUNDLE_FILENAMES) == 6
    assert INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME not in INDUSTRIAL_PLANNER_BUNDLE_FILENAMES
    assert not (output_dir / INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME).exists()

    result = export_native_blueprint(v1_blueprint_path=written.blueprint_path)

    assert result.output_path == output_dir / INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME
    on_disk = _load_json(result.output_path)
    assert on_disk == result.document
    assert on_disk["schemaVersion"] == 4
    assert "schema" not in on_disk
    assert "blueprintVersion" not in on_disk


def test_entry_point_writes_canonical_sorted_bytes(tmp_path: Path) -> None:
    v1_path = tmp_path / "industrial_planner.blueprint.json"
    v1_path.write_text(json.dumps(_v1_blueprint_from_minimal_fixture()), encoding="utf-8")

    first = export_native_blueprint(v1_blueprint_path=v1_path, output_path=tmp_path / "a.json")
    second = export_native_blueprint(v1_blueprint_path=v1_path, output_path=tmp_path / "b.json")

    text = (tmp_path / "a.json").read_text(encoding="utf-8")
    assert text == (tmp_path / "b.json").read_text(encoding="utf-8")
    assert text == render_native_blueprint_json(first.document)
    assert text == json.dumps(second.document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    assert text.endswith("}\n") and "\r" not in text


def test_entry_point_command_line_writes_next_to_the_input(tmp_path: Path) -> None:
    v1_path = tmp_path / "industrial_planner.blueprint.json"
    v1_path.write_text(json.dumps(_v1_blueprint_from_minimal_fixture()), encoding="utf-8")

    assert native_export_entry_module.main([str(v1_path)]) == 0

    written = tmp_path / INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME
    assert written.exists()
    assert validate_native_blueprint_document(_load_json(written)).is_valid is True
