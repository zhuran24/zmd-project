from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


materializer = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.materialize_reduced_geometry"
)


OPERATION_SPECS = (
    ("crusher_blue_iron", "manufacturing_3x3", 34, 1, 1),
    ("crusher_buckwheat", "manufacturing_3x3", 6, 1, 2),
    ("crusher_sandleaf", "manufacturing_3x3", 11, 1, 3),
    ("crusher_source", "manufacturing_3x3", 18, 1, 1),
    ("molding_bottle", "manufacturing_3x3", 6, 2, 1),
    ("parts_maker", "manufacturing_3x3", 6, 1, 1),
    ("refinery_blue_iron", "manufacturing_3x3", 34, 1, 1),
    ("refinery_steel", "manufacturing_3x3", 17, 1, 1),
    ("planter_buckwheat", "manufacturing_5x5", 11, 1, 1),
    ("planter_sandleaf", "manufacturing_5x5", 21, 1, 1),
    ("seed_collector_buckwheat", "manufacturing_5x5", 6, 1, 2),
    ("seed_collector_sandleaf", "manufacturing_5x5", 11, 1, 2),
    ("filling_capsule", "manufacturing_6x4", 3, 4, 1),
    ("grinder_dense_blue_iron", "manufacturing_6x4", 17, 3, 1),
    ("grinder_dense_source", "manufacturing_6x4", 9, 3, 1),
    ("grinder_fine_buckwheat", "manufacturing_6x4", 6, 3, 1),
    ("packaging_battery", "manufacturing_6x4", 3, 5, 1),
)


def _strict_ports(max_inputs: int, max_outputs: int) -> list[dict[str, object]]:
    return [
        {
            "id": f"input_E_{index}",
            "kind": "input",
            "direction": "E",
            "body_cell": {"x": 0, "y": 0},
        }
        for index in range(max_inputs)
    ] + [
        {
            "id": f"output_W_{index}",
            "kind": "output",
            "direction": "W",
            "body_cell": {"x": 0, "y": 0},
        }
        for index in range(max_outputs)
    ]


def _manufacturing_mode(template: str) -> dict[str, object]:
    needs = [(inputs, outputs) for _operation, row_template, _count, inputs, outputs in OPERATION_SPECS if row_template == template]
    return {
        "id": "north_to_south",
        "body": {"width": 1, "height": 1},
        "ports": _strict_ports(max(value[0] for value in needs), max(value[1] for value in needs)),
    }


def _candidate_pose(anchor: tuple[int, int], *, max_inputs: int, max_outputs: int) -> dict[str, object]:
    x, y = anchor
    return {
        "anchor": {"x": x, "y": y},
        "pose_params": {"port_mode": "TB"},
        "occupied_cells": [[x, y]],
        "input_port_cells": [{"x": x + 1, "y": y, "dir": "E"} for _ in range(max_inputs)],
        "output_port_cells": [{"x": x - 1, "y": y, "dir": "W"} for _ in range(max_outputs)],
    }


def _active_ports(anchor: tuple[int, int], input_need: int, output_need: int) -> list[dict[str, object]]:
    x, y = anchor
    return [
        {
            "port_id": f"input_E_{index}",
            "kind": "input",
            "direction": "E",
            "access": [x + 1, y],
            "component_kind": "output",
            "component_side": "W",
        }
        for index in range(input_need)
    ] + [
        {
            "port_id": f"output_W_{index}",
            "kind": "output",
            "direction": "W",
            "access": [x - 1, y],
            "component_kind": "input",
            "component_side": "E",
        }
        for index in range(output_need)
    ]


@dataclass(frozen=True)
class _Case:
    snapshot: SimpleNamespace
    relabel_result: dict[str, object]
    worker_result: dict[str, object]
    required_ids: frozenset[str]


def _build_case() -> _Case:
    templates: dict[str, dict[str, object]] = {}
    pools: dict[str, list[dict[str, object]]] = {
        "manufacturing_3x3": [],
        "manufacturing_5x5": [],
        "manufacturing_6x4": [],
        "boundary_storage_port": [],
        "protocol_core": [],
        "power_pole": [],
    }
    for template in ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4"):
        templates[template] = {"requires_power": True, "modes": [_manufacturing_mode(template)]}

    boundary_modes = [
        {
            "id": "left_boundary",
            "body": {"width": 1, "height": 3},
            "ports": [
                {
                    "id": "output_E_0",
                    "kind": "output",
                    "direction": "E",
                    "body_cell": {"x": 0, "y": 1},
                }
            ],
        },
        {
            "id": "bottom_boundary",
            "body": {"width": 3, "height": 1},
            "ports": [
                {
                    "id": "output_N_0",
                    "kind": "output",
                    "direction": "N",
                    "body_cell": {"x": 1, "y": 0},
                }
            ],
        },
    ]
    templates["boundary_storage_port"] = {"requires_power": False, "modes": boundary_modes}
    templates["protocol_core"] = {
        "requires_power": False,
        "modes": [{"id": "inputs_north_south", "body": {"width": 1, "height": 1}, "ports": []}],
    }
    templates["power_pole"] = {
        "requires_power": False,
        "modes": [{"id": "fixed", "body": {"width": 1, "height": 1}, "ports": []}],
    }

    anchors = [
        (x, y)
        for y in range(2, 69, 2)
        for x in range(2, 69, 2)
        if not (7 <= x < 13 and 36 <= y < 43)
        and not (x >= 60 and y >= 60)
        and (x, y) != materializer.FIXED_CORE_ANCHOR
    ]
    placements: list[dict[str, object]] = []
    required: list[dict[str, object]] = []
    signature_counts: Counter[str] = Counter()
    expansion: dict[str, list[str]] = defaultdict(list)
    anchor_offset = 0
    template_indices: Counter[str] = Counter()
    for operation_id, template, count, input_need, output_need in OPERATION_SPECS:
        signature = f"{template}__i{input_need}__o{output_need}"
        signature_counts[signature] += count
        expansion[signature].extend([operation_id] * count)
        mode = _manufacturing_mode(template)
        max_inputs = sum(port["kind"] == "input" for port in mode["ports"])
        max_outputs = sum(port["kind"] == "output" for port in mode["ports"])
        for operation_index in range(count):
            anchor = anchors[anchor_offset]
            anchor_offset += 1
            pose_idx = len(pools[template])
            pools[template].append(
                _candidate_pose(anchor, max_inputs=max_inputs, max_outputs=max_outputs)
            )
            placements.append(
                {
                    "signature": signature,
                    "operation_id": operation_id,
                    "template": template,
                    "pose_index": pose_idx,
                    "anchor": list(anchor),
                    "mode": "north_to_south",
                    "candidate_mode": "TB",
                    "active_ports": _active_ports(anchor, input_need, output_need),
                    "component": 0,
                }
            )
            required.append(
                {
                    "id": f"{template}_{operation_id}_{operation_index:03d}",
                    "template": template,
                    "operation": operation_id,
                }
            )
            template_indices[template] += 1

    boundary_ids = [f"boundary_{index:03d}" for index in range(46)]
    required.extend({"id": instance_id, "template": "boundary_storage_port"} for instance_id in boundary_ids)
    for placement in materializer.geometry.place_boundary_instances(
        boundary_ids, materializer.FIXED_BOUNDARY_PATTERN
    ):
        candidate_mode = "left_base" if placement.mode == "left_boundary" else "bottom_base"
        pools["boundary_storage_port"].append(
            {
                "anchor": {"x": placement.anchor[0], "y": placement.anchor[1]},
                "pose_params": {"port_mode": candidate_mode},
                "occupied_cells": [list(cell) for cell in sorted(placement.body_cells)],
                "input_port_cells": [],
                "output_port_cells": [
                    {"x": cell[0], "y": cell[1], "dir": "E" if placement.mode == "left_boundary" else "N"}
                    for cell in placement.front_cells
                ],
            }
        )

    required.append({"id": "protocol_core_001", "template": "protocol_core"})
    pools["protocol_core"].append(
        {
            "anchor": {"x": 60, "y": 60},
            "pose_params": {"port_mode": "core_LR_out"},
            "occupied_cells": [[60, 60]],
            "input_port_cells": [],
            "output_port_cells": [],
        }
    )
    for x, y in materializer.FIXED_POLE_ANCHORS:
        pools["power_pole"].append(
            {
                "anchor": {"x": x, "y": y},
                "pose_params": {"port_mode": "omni"},
                "occupied_cells": [[x, y]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        )

    operation_groups = [
        {
            "id": operation_id,
            "template": template,
            "count": count,
            "instance_ids": [
                str(row["id"])
                for row in required
                if row.get("operation") == operation_id
            ],
            "port_needs": {"inputs": {"ore": input_need}, "outputs": {"ore": output_need}},
        }
        for operation_id, template, count, input_need, output_need in OPERATION_SPECS
    ]
    instance = {
        "grid": {"width": 70, "height": 70},
        "commodities": ["ore"],
        "facility_templates": templates,
        "operation_groups": operation_groups,
        "required_instances": required,
    }
    snapshot = SimpleNamespace(
        instance=instance,
        facility_pools=pools,
        hashes={"strict_instance": "1" * 64, "candidate_poses": "2" * 64},
    )
    relabel_result: dict[str, object] = {
        "schema_version": materializer.RELABEL_SCHEMA_VERSION,
        "status": materializer.RELABEL_READY_STATUS,
        "claim_boundary": "research geometry only",
        "source": {"path": "/tmp/source.json", "sha256": "3" * 64},
        "fixed_geometry": {
            "backbone_cells": 622,
            "fixed_terminal_count": 54,
            "pole_count": 35,
            "protected": [7, 36, 6, 7],
        },
        "manufacturing_count": 219,
        "manufacturing_body_cells": 3325,
        "manufacturing_active_incidences": 574,
        "total_active_incidences_with_fixed": 628,
        "signature_counts": dict(signature_counts),
        "decomposition_audit": {},
        "clear_front_capacity_histograms": {},
        "placements": placements,
    }

    worker_placements = []
    for placement in placements:
        normalized = {key: value for key, value in placement.items() if key != "component"}
        normalized["pose_idx"] = normalized["pose_index"]
        worker_placements.append(normalized)
    worker_result: dict[str, object] = {
        "schema_version": materializer.RESULT_SCHEMA_VERSION,
        "status": materializer.RESULT_ACCEPTED_STATUS,
        "plan": {},
        "input_hashes": {
            "strict_instance": "1" * 64,
            "candidate_placements": "2" * 64,
            "static_evaluator": materializer.STATIC_EVALUATOR_SHA256,
        },
        "operation_expansion": dict(expansion),
        "selected_poles": [list(anchor) for anchor in materializer.FIXED_POLE_ANCHORS],
        "fixed_geometry": {
            "core_anchor": [60, 60],
            "boundary_pattern": {"left_gap": 69, "bottom_gap": 0},
            "protected_rectangle": [7, 36, 6, 7],
            "backbone_vertical_lane_levels": [1, 12, 24, 36, 48, 59],
            "backbone_horizontal_lane_levels": [1, 36, 59],
            "backbone_cells": 622,
        },
        "attempts": [],
        "cgroup_telemetry": {},
        "placements": worker_placements,
        "active_incidences": 628,
        "active_unique_cells": 500,
        "post_audits": {
            "local_component": {"passed": True},
            "free_component": {"passed": True},
            "fixed_power": {"passed": True},
        },
        "body_hint_audit": {},
        "protected_selection_audit": {"rectangle": [7, 36, 6, 7], "fixed_body_collision_cells": 0},
    }
    return _Case(
        snapshot=snapshot,
        relabel_result=relabel_result,
        worker_result=worker_result,
        required_ids=frozenset(str(row["id"]) for row in required),
    )


@pytest.fixture(scope="module")
def synthetic_case() -> _Case:
    return _build_case()


@dataclass
class _Context:
    occupied_cells: frozenset[tuple[int, int]]
    occupied_owner_by_cell: dict[tuple[int, int], str]
    component_by_cell: dict[tuple[int, int], int]


class _DryDependencies:
    """Intentionally has no routing-grid, router-build, or solve attributes."""

    def __init__(self, status: str = "feasible", *, corrupt_manufacturing_binding: bool = False) -> None:
        self.status = status
        self.corrupt_manufacturing_binding = corrupt_manufacturing_binding
        self.calls: list[str] = []

    def resolve_placement_solution(self, **kwargs):
        self.calls.append("resolve")
        records = [*kwargs["required_placements"], *kwargs["optional_placements"]]
        return {str(row["instance_id"]): {"pose_idx": index} for index, row in enumerate(records)}

    def build_routing_context(self, solution, pools, width, height):
        del solution, pools, width, height
        self.calls.append("context")
        return _Context(
            occupied_cells=frozenset({(2, 2)}),
            occupied_owner_by_cell={(2, 2): "owner"},
            component_by_cell={(1, 1): 0},
        )

    def choose_port_bindings(self, instance, **kwargs):
        del instance
        self.calls.append("choose")
        assert kwargs["allowed_access_cells"] == frozenset({(1, 1)})
        return {}

    def bind_placements(self, instance, **kwargs):
        del instance
        self.calls.append("bind")
        assert kwargs["allowed_access_cells"] == frozenset({(1, 1)})
        selected = kwargs["selected_port_bindings"]
        corrupted = False
        required = []
        for record in kwargs["required_placements"]:
            bindings = dict(selected.get(record["instance_id"], {}))
            if self.corrupt_manufacturing_binding and bindings and not corrupted:
                bindings.pop(sorted(bindings)[0])
                corrupted = True
            required.append(dict(record, port_bindings=bindings))
        return {
            "required_placements": required,
            "optional_placements": [
                dict(record, port_bindings=dict(selected.get(record["instance_id"], {})))
                for record in kwargs["optional_placements"]
            ],
        }

    def derive_port_specs(self, instance, **kwargs):
        del instance, kwargs
        self.calls.append("derive")
        return [{"x": 1, "y": 1, "commodity": "ore"}]

    def occupied_body_cells(self, instance, placements):
        del instance, placements
        self.calls.append("occupied")
        return {(2, 2)}

    def make_placement_core(self, occupied, **kwargs):
        self.calls.append("core")
        return {"occupied": occupied, "owners": kwargs["occupied_owner_by_cell"]}

    def routing_precheck(self, **kwargs):
        del kwargs
        self.calls.append("precheck")
        return {
            "status": self.status,
            "binding_selection_safe_reject": self.status in {"front_blocked", "relaxed_disconnected"},
            "domain_stats": {"fixture": 1},
            "_analysis": {"status": self.status},
        }


def test_relabel_materializes_exact_ids_fixed_geometry_and_lattice(synthetic_case: _Case) -> None:
    payload, audit = materializer.materialize_reduced_payload(
        synthetic_case.relabel_result,
        snapshot=synthetic_case.snapshot,
    )

    required = payload["required_placements"]
    assert len(required) == 266
    assert {row["instance_id"] for row in required} == synthetic_case.required_ids
    assert payload["pole_anchors"] == [list(anchor) for anchor in materializer.FIXED_POLE_ANCHORS]
    core = [row for row in required if row["template"] == "protocol_core"]
    assert core == [
        {
            "instance_id": "protocol_core_001",
            "template": "protocol_core",
            "mode": "inputs_north_south",
            "anchor": {"x": 60, "y": 60},
        }
    ]
    boundaries = [row for row in required if row["template"] == "boundary_storage_port"]
    assert len(boundaries) == 46
    assert {row["anchor"]["y"] for row in boundaries if row["mode"] == "left_boundary"} == set(
        materializer.geometry.boundary_anchors(69)
    )
    assert {row["anchor"]["x"] for row in boundaries if row["mode"] == "bottom_boundary"} == set(
        materializer.geometry.boundary_anchors(0)
    )
    assert audit["manufacturing_active_port_count"] == 574
    assert audit["power_uncovered_count"] == 0
    bindings = payload["manufacturing_port_bindings"]
    assert len(bindings) == 219
    assert sum(len(value) for value in bindings.values()) == 574
    assert bindings["manufacturing_3x3_crusher_blue_iron_000"] == {
        "input_E_0": "ore",
        "output_W_0": "ore",
    }
    assert audit["manufacturing_binding_instance_count"] == 219
    assert audit["manufacturing_binding_port_count"] == 574


def test_explicit_bundle_hash_binds_a_relocated_empty_rectangle(synthetic_case: _Case) -> None:
    bundle = materializer._validate_relabel_result_envelope(synthetic_case.relabel_result)
    relocated = replace(bundle, protected_rectangle=(20, 36, 6, 7))

    payload, audit = materializer.materialize_explicit_bundle(
        relocated,
        snapshot=synthetic_case.snapshot,
    )

    assert len(payload["required_placements"]) == 266
    assert audit["protected_rectangle"] == [20, 36, 6, 7]


@pytest.mark.parametrize(
    ("rectangle", "expected_code"),
    (
        ((2, 2, 6, 7), "PROTECTED_RECTANGLE_OCCUPIED"),
        ((20, 36, 7, 6), "EXPLICIT_PROTECTED_RECTANGLE"),
        ((65, 36, 6, 7), "EXPLICIT_PROTECTED_RECTANGLE"),
    ),
)
def test_explicit_bundle_rejects_invalid_or_occupied_relocated_rectangle(
    synthetic_case: _Case,
    rectangle: tuple[int, int, int, int],
    expected_code: str,
) -> None:
    bundle = materializer._validate_relabel_result_envelope(synthetic_case.relabel_result)

    with pytest.raises(materializer.ReducedGeometryMaterializerError) as exc_info:
        materializer.materialize_explicit_bundle(
            replace(bundle, protected_rectangle=rectangle),
            snapshot=synthetic_case.snapshot,
        )

    assert exc_info.value.code == expected_code


def test_active_port_ids_are_hash_bound_and_not_reselected(synthetic_case: _Case) -> None:
    baseline, baseline_audit = materializer.materialize_reduced_payload(
        synthetic_case.relabel_result,
        snapshot=synthetic_case.snapshot,
    )
    changed = deepcopy(synthetic_case.relabel_result)
    first = changed["placements"][0]
    output_port = next(port for port in first["active_ports"] if port["kind"] == "output")
    output_port["port_id"] = "output_W_2"

    rematerialized, changed_audit = materializer.materialize_reduced_payload(
        changed,
        snapshot=synthetic_case.snapshot,
    )

    instance_id = "manufacturing_3x3_crusher_blue_iron_000"
    assert baseline["manufacturing_port_bindings"][instance_id]["output_W_0"] == "ore"
    assert rematerialized["manufacturing_port_bindings"][instance_id]["output_W_2"] == "ore"
    assert "output_W_0" not in rematerialized["manufacturing_port_bindings"][instance_id]
    assert (
        baseline_audit["manufacturing_port_bindings_digest"]
        != changed_audit["manufacturing_port_bindings_digest"]
    )


def test_operation_commodities_zip_by_sorted_name_to_sorted_active_ids(
    synthetic_case: _Case,
) -> None:
    snapshot = deepcopy(synthetic_case.snapshot)
    snapshot.instance["commodities"] = ["ore", "zeta", "alpha"]
    group = next(
        value
        for value in snapshot.instance["operation_groups"]
        if value["id"] == "crusher_buckwheat"
    )
    group["port_needs"]["outputs"] = {"zeta": 1, "alpha": 1}

    payload, _audit = materializer.materialize_reduced_payload(
        synthetic_case.relabel_result,
        snapshot=snapshot,
    )

    assert payload["manufacturing_port_bindings"][
        "manufacturing_3x3_crusher_buckwheat_000"
    ] == {
        "input_E_0": "ore",
        "output_W_0": "alpha",
        "output_W_1": "zeta",
    }


def test_worker_schema_requires_exact_three_hashes_and_fixed_metadata(synthetic_case: _Case) -> None:
    payload, _audit = materializer.materialize_reduced_payload(
        synthetic_case.worker_result,
        snapshot=synthetic_case.snapshot,
        telemetry_validator=lambda _value: None,
    )
    assert len(payload["required_placements"]) == 266

    for mutation, expected_code in (
        (lambda value: value["input_hashes"].update({"candidate_placements": "9" * 64}), "RESULT_INPUT_DRIFT"),
        (lambda value: value["fixed_geometry"].update({"core_anchor": [59, 60]}), "RESULT_FIXED_GEOMETRY"),
        (lambda value: value.update({"selected_poles": value["selected_poles"][:-1]}), "RESULT_POLE_COUNT"),
    ):
        changed = deepcopy(synthetic_case.worker_result)
        mutation(changed)
        with pytest.raises(materializer.ReducedGeometryMaterializerError) as exc_info:
            materializer.materialize_reduced_payload(
                changed,
                snapshot=synthetic_case.snapshot,
                telemetry_validator=lambda _value: None,
            )
        assert exc_info.value.code == expected_code


def test_dry_precheck_accepts_without_accessing_router_interfaces(synthetic_case: _Case) -> None:
    payload, _audit = materializer.materialize_reduced_payload(
        synthetic_case.relabel_result,
        snapshot=synthetic_case.snapshot,
    )
    dependencies = _DryDependencies()

    result = materializer.dry_routing_precheck_only(
        payload,
        snapshot=synthetic_case.snapshot,
        dependencies=dependencies,
    )

    assert result["accepted"] is True
    assert result["classification"] == "ROUTING_PRECHECK_ACCEPTED"
    assert result["stopped_before_router_construction"] is True
    assert dependencies.calls == [
        "resolve",
        "context",
        "choose",
        "bind",
        "derive",
        "occupied",
        "core",
        "precheck",
    ]


def test_dry_precheck_rejects_binding_dependency_that_ignores_explicit_map(
    synthetic_case: _Case,
) -> None:
    payload, _audit = materializer.materialize_reduced_payload(
        synthetic_case.relabel_result,
        snapshot=synthetic_case.snapshot,
    )

    with pytest.raises(materializer.fixed_router.FixedGeometryRouterError) as exc_info:
        materializer.dry_routing_precheck_only(
            payload,
            snapshot=synthetic_case.snapshot,
            dependencies=_DryDependencies(corrupt_manufacturing_binding=True),
        )

    assert exc_info.value.code == "MANUFACTURING_BINDING_OVERRIDE_DRIFT"


def test_rejected_precheck_is_structured_and_does_not_write(
    synthetic_case: _Case, tmp_path: Path
) -> None:
    source = tmp_path / "relabel.json"
    raw = (json.dumps(synthetic_case.relabel_result, sort_keys=True) + "\n").encode()
    source.write_bytes(raw)
    output = tmp_path / "router-input.json"

    report = materializer.materialize_reduced_result(
        result_path=source,
        expected_result_sha256=hashlib.sha256(raw).hexdigest(),
        output_path=output,
        project_root=Path.cwd(),
        snapshot=synthetic_case.snapshot,
        dependencies=_DryDependencies("relaxed_disconnected"),
    )

    assert report["status"] == "REJECTED"
    assert report["output"] is None
    assert report["dry_validation"]["accepted"] is False
    assert report["dry_validation"]["classification"] == "ROUTING_PRECHECK_REJECTED"
    assert not output.exists()


def test_accepted_precheck_writes_once_with_x_open(synthetic_case: _Case, tmp_path: Path) -> None:
    source = tmp_path / "relabel.json"
    raw = (json.dumps(synthetic_case.relabel_result, sort_keys=True) + "\n").encode()
    source.write_bytes(raw)
    output = tmp_path / "router-input.json"

    report = materializer.materialize_reduced_result(
        result_path=source,
        expected_result_sha256=hashlib.sha256(raw).hexdigest(),
        output_path=output,
        project_root=Path.cwd(),
        snapshot=synthetic_case.snapshot,
        dependencies=_DryDependencies(),
    )

    assert report["status"] == "MATERIALIZED"
    written = json.loads(output.read_text(encoding="ascii"))
    assert set(written) == {
        "schema_version",
        "required_placements",
        "pole_anchors",
        "manufacturing_port_bindings",
    }
    assert len(written["required_placements"]) == 266
    assert len(written["manufacturing_port_bindings"]) == 219
    with pytest.raises(materializer.ReducedGeometryMaterializerError) as exc_info:
        materializer._write_exclusive(output, written)
    assert exc_info.value.code == "OUTPUT_ALREADY_EXISTS"
