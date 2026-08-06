"""Regression contract for the research-only band22-witness/2 adapter batch."""
from __future__ import annotations

from collections import defaultdict
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from docs.research.band22_registration_20260805 import band22_v2_adapter as adapter

ROOT = Path(__file__).resolve().parents[2]
DRIVER_PATH = ROOT / "docs/research/band22_registration_20260805/registration_driver.py"
R2 = (
    ROOT
    / ".artifacts/band22_strict_redesign_replies_20260805/r2_strict_empty_v2"
    / "band22_strict_empty_v2_delivery/band22_strict_witness_v2.json"
)
CANDIDATES = ROOT / "data/preprocessed/candidate_placements.json"
MANDATORY = ROOT / "data/preprocessed/mandatory_exact_instances.json"
RULES = ROOT / "rules/canonical_rules.json"


def _load_driver() -> ModuleType:
    spec = importlib.util.spec_from_file_location("band22_registration_driver_v2_test", DRIVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver() -> ModuleType:
    return _load_driver()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_schema_dispatch_v2_legacy_and_unknown(
    driver: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    v2 = tmp_path / "v2.json"
    _write_json(v2, {"witness_schema_version": "band22-witness/2"})
    sentinel = ({"mapped": {"pose_idx": 7}}, {"schema_dispatch": "sentinel"})
    monkeypatch.setattr(adapter, "load_band22_v2_witness", lambda *_args, **_kwargs: sentinel)
    assert driver.load_witness_solution(v2) == sentinel

    legacy = tmp_path / "legacy.json"
    _write_json(legacy, {"solution": {"legacy_001": {"pose_idx": 3}}})
    solution, meta = driver.load_witness_solution(legacy)
    assert solution == {"legacy_001": {"pose_idx": 3}}
    assert meta["schema_dispatch"] == "legacy_solution"

    unknown = tmp_path / "unknown.json"
    _write_json(unknown, {"witness_schema_version": "band22-witness/999", "solution": {}})
    with pytest.raises(ValueError, match="unsupported witness_schema_version"):
        driver.load_witness_solution(unknown)


@pytest.mark.parametrize(
    ("facility_type", "mode", "expected"),
    [
        ("boundary_storage_port", "bottom_boundary", (1, "bottom_base")),
        ("boundary_storage_port", "left_boundary", (0, "left_base")),
        ("manufacturing_3x3", "north_to_south", (0, "TB")),
        ("manufacturing_3x3", "south_to_north", (0, "BT")),
        ("manufacturing_5x5", "north_to_south", (0, "TB")),
        ("manufacturing_5x5", "south_to_north", (0, "BT")),
        ("manufacturing_6x4", "north_to_south", (0, "TB")),
        ("manufacturing_6x4", "south_to_north", (0, "BT")),
        ("manufacturing_6x4", "west_to_east", (1, "LR")),
        ("protocol_core", "inputs_east_west", (1, "core_TB_out")),
    ],
)
def test_mode_mapping_table(
    facility_type: str, mode: str, expected: tuple[int, str]
) -> None:
    assert adapter.official_pose_params_for_mode(facility_type, mode) == expected


def _pose(pose_id: str, x: int, y: int, orientation: int, port_mode: str) -> dict[str, Any]:
    return {
        "pose_id": pose_id,
        "anchor": {"x": x, "y": y},
        "pose_params": {"orientation": orientation, "port_mode": port_mode},
        "occupied_cells": [],
        "input_port_cells": [],
        "output_port_cells": [],
    }


def test_pool_lookup_is_facility_scoped_unique_and_fail_closed() -> None:
    shared_a = _pose("shared", 4, 5, 0, "TB")
    shared_b = _pose("shared", 4, 5, 0, "TB")
    pools = {"manufacturing_3x3": [shared_a], "manufacturing_5x5": [shared_b]}
    index = adapter.build_pose_index(pools)
    assert adapter.match_unique_pose(index, ("manufacturing_3x3", 4, 5, 0, "TB"))[0] == 0
    assert adapter.match_unique_pose(index, ("manufacturing_5x5", 4, 5, 0, "TB"))[0] == 0

    duplicate = adapter.build_pose_index({"manufacturing_3x3": [shared_a, dict(shared_a)]})
    with pytest.raises(ValueError, match="matches=2"):
        adapter.match_unique_pose(duplicate, ("manufacturing_3x3", 4, 5, 0, "TB"))
    with pytest.raises(ValueError, match="matches=0"):
        adapter.match_unique_pose(index, ("manufacturing_3x3", 9, 9, 0, "TB"))


def test_binding_projection_requires_one_exact_multiset_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    witness_port = {"kind": "input", "commodity": "ore", "front": [8, 9], "direction": "N"}
    entry = {
        "input_ports": [{"type": "input", "commodity": "ore", "x": 8, "y": 9, "dir": "N"}],
        "output_ports": [],
        "active_ports": [{"type": "input", "commodity": "ore", "x": 8, "y": 9, "dir": "N"}],
    }
    monkeypatch.setattr(adapter, "enumerate_pose_level_port_bindings", lambda *_args: [entry])
    projected = adapter.project_unique_binding("official_op", {}, [witness_port])
    assert projected["matching_domain_index"] == 0
    assert projected["input_ports"] == entry["input_ports"]

    monkeypatch.setattr(adapter, "enumerate_pose_level_port_bindings", lambda *_args: [entry, entry])
    with pytest.raises(ValueError, match="matches=2"):
        adapter.project_unique_binding("official_op", {}, [witness_port])
    monkeypatch.setattr(adapter, "enumerate_pose_level_port_bindings", lambda *_args: [])
    with pytest.raises(ValueError, match="matches=0"):
        adapter.project_unique_binding("official_op", {}, [witness_port])


def _witness_port(kind: str, commodity: str, x: int, y: int, direction: str) -> dict[str, Any]:
    return {"kind": kind, "commodity": commodity, "front": [x, y], "direction": direction}


def _synthetic_v2_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mandatory: list[dict[str, Any]] = []
    boundary: list[dict[str, Any]] = []
    machines: list[dict[str, Any]] = []
    top_active: list[dict[str, Any]] = []

    def add_top(iid: str, port: dict[str, Any]) -> None:
        top_active.append(
            {
                "instance_id": iid,
                **port,
                "component_direction": adapter.OPPOSITE[str(port["direction"])],
            }
        )

    for index in range(46):
        iid = f"boundary_{index:03d}"
        anchor = [index, 50]
        port = _witness_port("output", "blue", index, 49, "S")
        boundary.append(
            {"instance_id": iid, "template": "boundary_storage_port", "anchor": anchor,
             "mode": "bottom_boundary", "active_ports": [port]}
        )
        pose = _pose(f"boundary_pose_{index}", *anchor, 1, "bottom_base")
        pose["output_port_cells"] = [{"x": index, "y": 49, "dir": "S"}]
        pools["boundary_storage_port"].append(pose)
        mandatory.append({"instance_id": iid, "facility_type": "boundary_storage_port",
                          "operation_type": "boundary_io", "is_mandatory": True})
        add_top(iid, port)

    core_id = "protocol_core_001"
    core_ports: list[dict[str, Any]] = []
    core_pose = _pose("core_pose", 60, 30, 1, "core_TB_out")
    for index in range(14):
        commodity = ("q1", "q2")[index] if index < 2 else None
        row = {**_witness_port("input", commodity or "placeholder", 55, 20 + index, "W"),
               "active": index < 2, "commodity": commodity}
        core_ports.append(row)
        core_pose["input_port_cells"].append({"x": 55, "y": 20 + index, "dir": "W"})
        if index < 2:
            add_top(core_id, row)
    for index in range(6):
        row = {**_witness_port("output", "source", 65, 20 + index, "E"), "active": True}
        core_ports.append(row)
        core_pose["output_port_cells"].append({"x": 65, "y": 20 + index, "dir": "E"})
        add_top(core_id, row)
    core = {"instance_id": core_id, "template": "protocol_core", "anchor": [60, 30],
            "mode": "inputs_east_west", "ports": core_ports}
    pools["protocol_core"].append(core_pose)
    mandatory.append({"instance_id": core_id, "facility_type": "protocol_core",
                      "operation_type": "protocol_hub", "is_mandatory": True})

    for index in range(219):
        iid = f"machine_{index:03d}"
        anchor = [index % 70, 10 + index // 70]
        ports = [
            _witness_port("input", "ore", index % 70, 15 + index // 70 + offset, "N")
            for offset in range(3 if index < 136 else 2)
        ]
        machines.append({"instance_id": iid, "template": "manufacturing_3x3", "anchor": anchor,
                         "mode": "north_to_south", "active_ports": ports, "operation_type": "witness_lie"})
        pools["manufacturing_3x3"].append(_pose(f"machine_pose_{index}", *anchor, 0, "TB"))
        mandatory.append({"instance_id": iid, "facility_type": "manufacturing_3x3",
                          "operation_type": "official_machine_op", "is_mandatory": True})
        for port in ports:
            add_top(iid, port)

    pole_pose = _pose("pole_pose", 69, 69, 0, "omni")
    pools["power_pole"].append(pole_pose)
    payload = {
        "witness_schema_version": "band22-witness/2",
        "grid": {"width": 70, "height": 70},
        "hole": {"x_range": [0, 6], "y_range": [0, 5], "width": 7, "height": 6, "area": 42},
        "facilities": {"boundary_ports": boundary, "protocol_core": core, "manufacturing": machines,
                       "power_poles": [{"id": "pole_1", "anchor": [69, 69]}], "storage_boxes": []},
        "active_ports": top_active,
        "route_components": [],
        "source_hashes": {"self_reported": "untrusted"},
    }
    rules = {"globals": {"empty_rectangle": {"min_side_admissibility": 6}}}
    generic = {"required_generic_inputs": {"q1": 1, "q2": 1},
               "required_generic_outputs": {"blue": 46, "source": 6}}
    return payload, dict(pools), mandatory, rules, generic


def test_synthetic_full_projection_accounts_unused_and_ignores_witness_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, pools, mandatory, rules, generic = _synthetic_v2_inputs()
    calls: list[str] = []

    def fake_projection(operation_type: str, _pose: Any, _ports: Any) -> dict[str, Any]:
        calls.append(operation_type)
        return {"domain_size": 1, "matching_domain_index": 0, "input_ports": [], "output_ports": []}

    monkeypatch.setattr(adapter, "project_unique_binding", fake_projection)
    solution, meta = adapter.adapt_band22_v2_payload(
        payload, facility_pools=pools, mandatory_instances=mandatory,
        canonical_rules=rules, generic_io_requirements=generic,
    )
    accounting = meta["binding_projection"]["accounting"]
    assert len(solution) == 267
    assert calls == ["official_machine_op"] * 219
    assert accounting == {
        "pose_level_unique_matches": 219,
        "generic_input_slots": 14,
        "generic_input_active": 2,
        "generic_input_unused": 12,
        "generic_output_active": 52,
    }
    assert list(meta["binding_projection"]["generic_inputs"].values()).count("__unused__") == 12

    with pytest.raises(ValueError, match="witness IDs must exactly equal"):
        adapter.adapt_band22_v2_payload(
            payload, facility_pools=pools, mandatory_instances=mandatory[:-1],
            canonical_rules=rules, generic_io_requirements=generic,
        )

    payload["facilities"]["boundary_ports"][0]["active_ports"][0]["kind"] = "input"
    next(row for row in payload["active_ports"] if row["instance_id"] == "boundary_000")["kind"] = "input"
    with pytest.raises(ValueError, match="boundary_000:out:0 must uniquely match"):
        adapter.adapt_band22_v2_payload(
            payload, facility_pools=pools, mandatory_instances=mandatory,
            canonical_rules=rules, generic_io_requirements=generic,
        )


def test_route_schema_rejects_cross_shape() -> None:
    with pytest.raises(ValueError, match="no-cross/arity"):
        adapter.audit_route_components([
            {"x": 1, "y": 2, "kind": "merger", "inputs": ["N", "E"], "outputs": ["S", "W"]}
        ])


def _minimal_structure_master(port_cells: list[dict[str, Any]]) -> tuple[SimpleNamespace, dict[str, Any]]:
    pose = {
        "pose_id": "p0", "anchor": {"x": 10, "y": 10}, "occupied_cells": [[10, 10]],
        "input_port_cells": port_cells, "output_port_cells": [],
    }
    master = SimpleNamespace(
        source_instances=[{"instance_id": "machine_001", "facility_type": "manufacturing_3x3",
                           "operation_type": "official_op", "is_mandatory": True}],
        facility_pools={"manufacturing_3x3": [pose]},
    )
    solution = {"machine_001": {"instance_id": "machine_001", "facility_type": "manufacturing_3x3",
                                "operation_type": "official_op", "pose_idx": 0,
                                "pose_id": "p0", "anchor": {"x": 10, "y": 10}}}
    return master, solution


def test_inactive_candidate_ports_inside_hole_are_telemetry_but_active_is_rejected(
    driver: ModuleType,
) -> None:
    ports = [{"x": x, "y": y, "dir": "N"} for x, y in [(0, 0), (1, 0), (2, 0), (3, 0),
             (4, 0), (5, 0), (6, 0), (0, 1), (1, 1), (2, 1), (3, 1)]]
    master, solution = _minimal_structure_master(ports)
    accepted = driver.validate_layout_structure(
        solution=solution, master=master, ghost_w=7, ghost_h=6,
        ghost_anchor_x=0, ghost_anchor_y=0, active_terminal_cells=[], route_component_cells=[],
    )
    assert accepted["ok"] is True
    assert accepted["candidate_physical_ports_inside_ghost"] == 11
    assert accepted["inactive_candidate_ports_inside_ghost"] == 11

    rejected = driver.validate_layout_structure(
        solution=solution, master=master, ghost_w=7, ghost_h=6,
        ghost_anchor_x=0, ghost_anchor_y=0, active_terminal_cells=[[0, 0]], route_component_cells=[],
    )
    assert rejected["ok"] is False
    assert {problem["reason"] for problem in rejected["problems"]} == {
        "ghost_rect_contains_active_terminal"
    }


def test_ghost_live_and_canonical_indices_are_distinct_contracts(driver: ModuleType) -> None:
    master = SimpleNamespace(u_vars={0: object()}, _ghost_domains=[{"anchor": {"x": 3, "y": 30}}])
    live = driver.resolve_live_ghost_domain_index(master, anchor_x=3, anchor_y=30)
    canonical = driver.build_ghost_pick(ghost_w=7, ghost_h=6, anchor_x=3, anchor_y=30)["pose_idx"]
    assert live == 0
    assert canonical == 225
    assert canonical not in master.u_vars

    mixed = SimpleNamespace(u_vars={225: object()}, _ghost_domains=[{"anchor": {"x": 3, "y": 30}}])
    with pytest.raises(ValueError, match="invalid live ghost-domain index"):
        driver.resolve_live_ghost_domain_index(mixed, anchor_x=3, anchor_y=30)


def test_master_timeout_is_censored_not_harness_error(driver: ModuleType) -> None:
    verdict = driver.classify_verdict(
        controller_status=None, gate_returned_solution=None, proof_summary={},
        binding_seconds=600.0, routing_seconds=600.0, harness_exception=None,
        master_validation={"confirmed": False, "status": "UNKNOWN", "time_limit_seconds": 17.0},
        stop_after="master",
    )
    assert verdict["verdict"] == "UNKNOWN_CENSORED"
    assert verdict["censored_stage"] == "master_validation"
    assert verdict["censored_at_seconds"] == 17.0


def test_source_hash_and_witness_snapshot_drift_fail_closed(driver: ModuleType) -> None:
    actual = {key: f"hash-{key}" for key in adapter.SOURCE_PATHS}
    assert adapter.verify_against_session_pins(actual, dict(actual))["ok"] is True
    drifted = dict(actual)
    drifted["canonical_rules"] = "different"
    with pytest.raises(ValueError, match="source snapshot drift"):
        adapter.verify_against_session_pins(actual, drifted)
    driver.verify_witness_snapshot_identity("same", "same")
    with pytest.raises(ValueError, match="witness bytes drifted"):
        driver.verify_witness_snapshot_identity("provenance", "adapter")


@pytest.mark.parametrize(
    "raw",
    [
        '{"witness_schema_version":"band22-witness/2","witness_schema_version":"band22-witness/2"}',
        '{"witness_schema_version":"band22-witness/2","bad":NaN}',
    ],
)
def test_strict_json_rejects_duplicate_keys_and_nan(
    driver: ModuleType, tmp_path: Path, raw: str
) -> None:
    path = tmp_path / "hostile.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        driver.load_witness_solution(path)
    with pytest.raises(ValueError):
        adapter.load_band22_v2_witness(path, project_root=ROOT)


def test_real_r2_adapter_if_untracked_inputs_are_present() -> None:
    missing = [path for path in (R2, CANDIDATES, MANDATORY, RULES) if not path.is_file()]
    if missing:
        pytest.skip(
            "real R2/candidate inputs are untracked or unavailable; synthetic contract remains covered: "
            + ", ".join(str(path) for path in missing)
        )
    solution, meta = adapter.load_band22_v2_witness(R2)
    assert len(solution) == 289
    assert meta["mandatory_instance_count"] == 266
    assert meta["power_pole_count"] == 23
    assert meta["ghost"]["canonical_unfiltered_ghost_idx"] == 225
    assert meta["binding_projection"]["accounting"]["pose_level_unique_matches"] == 219
    assert meta["binding_projection"]["accounting"]["generic_input_unused"] == 12
    assert meta["route_schema_audit"]["cross_count"] == 0
