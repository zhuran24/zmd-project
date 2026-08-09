from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


worker = importlib.import_module("docs.research.witness_constructor_20260717.07_routing_aware.fixed_geometry_router")


def _payload(*, poles: list[list[int]] | None = None) -> dict:
    return {
        "schema_version": worker.INPUT_SCHEMA_VERSION,
        "required_placements": [
            {
                "instance_id": "m1",
                "template": "tiny",
                "mode": "fixed",
                "anchor": {"x": 1, "y": 1},
            }
        ],
        "pole_anchors": [] if poles is None else poles,
        "manufacturing_port_bindings": {"m1": {"in": "ore", "out": "ore"}},
    }


def _instance() -> dict:
    return {
        "grid": {"width": 4, "height": 4},
        "commodities": ["ore"],
        "required_instances": [{"id": "m1", "template": "tiny", "operation": "make"}],
        "operation_groups": [
            {
                "id": "make",
                "template": "tiny",
                "count": 1,
                "instance_ids": ["m1"],
                "port_needs": {"inputs": {"ore": 1}, "outputs": {"ore": 1}},
            }
        ],
    }


@dataclass
class _Context:
    occupied_cells: frozenset
    occupied_owner_by_cell: dict
    component_by_cell: dict


@dataclass
class _L1:
    forbidden_at_terminal: bool


@dataclass(frozen=True)
class _Terminal:
    kind: str
    commodity: str


class _FakeRouter:
    def __init__(
        self,
        calls: list[str],
        status: object,
        build_error: Exception | None,
    ) -> None:
        self.calls = calls
        self.status = status
        self.build_error = build_error
        self.model = object()
        self.phys_vars = {"physical": object()}
        self.build_stats: dict = {}

    def build(self) -> None:
        self.calls.append("router.build")
        if self.build_error is not None:
            raise self.build_error

    def solve(self, *, time_limit: float) -> object:
        self.calls.append(f"router.solve:{time_limit}")
        return self.status

    def extract_routes(self) -> list[dict]:
        self.calls.append("router.extract")
        return [{"production": 1}, {"production": 2}]


class _Fixture:
    def __init__(
        self,
        *,
        status: object = "FEASIBLE",
        oom: str = "NO_CGROUP_OOM",
        final_oom: str | None = None,
        build_error: Exception | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.status = status
        self.oom = oom
        self.final_oom = final_oom
        self.finish_count = 0
        self.build_error = build_error
        self.reachability_error: Exception | None = None
        self.bound_binding_override: dict[str, str] | None = None
        self.selected_port_bindings: dict[str, dict[str, str]] | None = None

    def dependencies(self) -> worker.WorkerDependencies:
        calls = self.calls

        def resolve(**kwargs):
            calls.append("resolve")
            records = [*kwargs["required_placements"], *kwargs["optional_placements"]]
            return {
                record["instance_id"]: {
                    "facility_type": record["template"],
                    "pose_idx": index,
                }
                for index, record in enumerate(records)
            }

        def context(solution, pools, width, height):
            del solution, pools, width, height
            calls.append("context")
            return _Context(
                occupied_cells=frozenset({(1, 1)}),
                occupied_owner_by_cell={(1, 1): "m1"},
                component_by_cell={(0, 0): 0, (0, 1): 0, (0, 2): 0},
            )

        def choose(instance, **kwargs):
            del instance
            calls.append("choose")
            assert kwargs["allowed_access_cells"] == frozenset({(0, 0), (0, 1), (0, 2)})
            return {"m1": {"auto_in": "ore", "auto_out": "ore"}}

        def bind(instance, **kwargs):
            del instance
            calls.append("bind")
            assert kwargs["allowed_access_cells"] == frozenset({(0, 0), (0, 1), (0, 2)})
            self.selected_port_bindings = {
                instance_id: dict(bindings)
                for instance_id, bindings in kwargs["selected_port_bindings"].items()
            }
            active = self.bound_binding_override or self.selected_port_bindings["m1"]
            required = [
                dict(record, port_bindings=dict(active))
                for record in kwargs["required_placements"]
            ]
            optional = [dict(record, port_bindings={}) for record in kwargs["optional_placements"]]
            return {"required_placements": required, "optional_placements": optional}

        def derive(instance, **kwargs):
            del instance, kwargs
            calls.append("derive")
            return [
                {"instance_id": "m1", "x": 0, "y": 0, "dir": "E", "type": "out", "commodity": "ore"},
                {"instance_id": "m1", "x": 0, "y": 1, "dir": "W", "type": "in", "commodity": "ore"},
            ]

        def occupied(instance, placements):
            del instance, placements
            calls.append("strict_occupied")
            return {(1, 1)}

        def make_core(cells, **kwargs):
            calls.append("core")
            return {"cells": cells, "owners": kwargs["occupied_owner_by_cell"]}

        def precheck(**kwargs):
            del kwargs
            calls.append("precheck")
            return {
                "status": "feasible",
                "binding_selection_safe_reject": False,
                "domain_stats": {"tiny": 1},
                "_analysis": {"status": "feasible"},
            }

        def make_grid(core, specs):
            calls.append("grid")
            return {"core": core, "specs": specs}

        def make_router(grid, commodities, **kwargs):
            del grid, commodities, kwargs
            calls.append("router.init")
            return _FakeRouter(calls, self.status, self.build_error)

        def add_l1(model, physical_vars, **kwargs):
            del model
            calls.append("add_l1")
            assert set(physical_vars) == {"physical"}
            assert kwargs["terminal_cells"] == frozenset({(0, 0), (0, 1)})
            return (_L1(True),)

        def adapt(routes, **kwargs):
            calls.append("adapt")
            assert len(routes) == 2
            assert kwargs["terminal_cells"] == frozenset({(0, 0), (0, 1)})
            return [
                {
                    "cell": {"x": 0, "y": 0},
                    "kind": "straight",
                    "inputs": ["W"],
                    "outputs": ["E"],
                    "commodities": ["ore"],
                },
                {
                    "cell": {"x": 0, "y": 1},
                    "kind": "straight",
                    "inputs": ["E"],
                    "outputs": ["W"],
                    "commodities": ["ore"],
                },
            ]

        def terminals(instance, placements):
            del instance, placements
            calls.append("terminals")
            return [_Terminal("output", "ore"), _Terminal("input", "ore")]

        def reachability(components, terminals, commodities):
            del components, terminals, commodities
            calls.append("reachability")
            if self.reachability_error is not None:
                raise self.reachability_error

        def begin(unit):
            calls.append(f"cgroup.begin:{unit}")
            return {"start": True}

        def finish(start):
            assert start == {"start": True}
            calls.append("cgroup.finish")
            self.finish_count += 1
            observed_oom = (
                self.final_oom
                if self.finish_count > 1 and self.final_oom is not None
                else self.oom
            )
            return {"oom_attribution": observed_oom, "memory.peak": 123}

        return worker.WorkerDependencies(
            resolve_placement_solution=resolve,
            build_routing_context=context,
            choose_port_bindings=choose,
            bind_placements=bind,
            derive_port_specs=derive,
            occupied_body_cells=occupied,
            make_placement_core=make_core,
            routing_precheck=precheck,
            make_routing_grid=make_grid,
            make_routing_subproblem=make_router,
            add_l1_support_constraints=add_l1,
            adapt_extracted_routes=adapt,
            terminals_from_witness=terminals,
            assert_terminal_route_reachability=reachability,
            begin_cgroup_telemetry=begin,
            finish_cgroup_telemetry=finish,
        )

    def run(self, *, payload: dict | None = None, **config_overrides):
        values = {
            "time_limit_seconds": 2.5,
            "minimum_poles": 0,
            "required_grid": (4, 4),
            "require_cgroup": True,
            "expected_unit_name": "tiny.service",
        }
        values.update(config_overrides)
        return worker.run_fixed_geometry_router(
            _payload() if payload is None else payload,
            instance=_instance(),
            facility_pools={},
            dependencies=self.dependencies(),
            config=worker.WorkerConfig(**values),
        )


class FixedGeometryRouterWorkerTests(unittest.TestCase):
    def test_feasible_pipeline_orders_l1_before_solve_and_independent_check_after_adapt(self) -> None:
        fixture = _Fixture()
        result = fixture.run()
        self.assertEqual(result["status"], "FEASIBLE")
        self.assertEqual(result["classification"], "STRICT_ROUTES_INDEPENDENTLY_REACHABLE")
        self.assertEqual(len(result["route_components"]), 2)
        self.assertEqual(result["telemetry"]["independent_reachability"]["status"], "PASS")
        self.assertEqual(
            fixture.selected_port_bindings,
            {"m1": {"in": "ore", "out": "ore"}},
        )
        self.assertLess(fixture.calls.index("choose"), fixture.calls.index("bind"))
        self.assertLess(fixture.calls.index("router.build"), fixture.calls.index("add_l1"))
        self.assertLess(fixture.calls.index("add_l1"), fixture.calls.index("router.solve:2.5"))
        self.assertLess(fixture.calls.index("adapt"), fixture.calls.index("reachability"))
        self.assertLess(fixture.calls.index("cgroup.begin:tiny.service"), fixture.calls.index("router.build"))
        self.assertLess(fixture.calls.index("cgroup.begin:tiny.service"), fixture.calls.index("router.solve:2.5"))
        finish_indices = [
            index for index, call in enumerate(fixture.calls) if call == "cgroup.finish"
        ]
        self.assertEqual(len(finish_indices), 2)
        self.assertLess(fixture.calls.index("router.solve:2.5"), finish_indices[0])
        self.assertLess(fixture.calls.index("reachability"), finish_indices[1])

    def test_build_exception_still_finishes_cgroup_telemetry_and_fails_closed(self) -> None:
        fixture = _Fixture(build_error=RuntimeError("synthetic build failure"))
        result = fixture.run()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "FAIL_CLOSED_EXCEPTION")
        self.assertEqual(result["phase"], "routing_build")
        self.assertEqual(result["route_components"], [])
        self.assertLess(fixture.calls.index("cgroup.begin:tiny.service"), fixture.calls.index("router.build"))
        self.assertLess(fixture.calls.index("router.build"), fixture.calls.index("cgroup.finish"))
        self.assertNotIn("router.solve:2.5", fixture.calls)
        self.assertEqual(result["telemetry"]["cgroup"]["oom_attribution"], "NO_CGROUP_OOM")

    def test_timeout_is_unproven_and_never_extracts_routes(self) -> None:
        fixture = _Fixture(status="TIMEOUT")
        result = fixture.run()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "ROUTING_TIMEOUT_UNPROVEN")
        self.assertEqual(result["route_components"], [])
        self.assertNotIn("router.extract", fixture.calls)
        self.assertIn("cgroup.finish", fixture.calls)

    def test_unknown_status_fails_closed(self) -> None:
        fixture = _Fixture(status="MYSTERY")
        result = fixture.run()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "FAIL_CLOSED_CONTRACT_ERROR")
        self.assertEqual(result["error_code"], "ROUTING_STATUS_UNKNOWN")
        self.assertEqual(result["route_components"], [])

    def test_cgroup_oom_overrides_feasible_incumbent_before_extraction(self) -> None:
        fixture = _Fixture(status="FEASIBLE", oom="CGROUP_OOM_KILL")
        result = fixture.run()
        self.assertEqual(result["classification"], "CGROUP_OOM")
        self.assertEqual(result["route_components"], [])
        self.assertNotIn("router.extract", fixture.calls)

    def test_post_route_cgroup_oom_discards_independently_checked_routes(self) -> None:
        fixture = _Fixture(final_oom="CGROUP_OOM_EVENT")
        result = fixture.run()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "CGROUP_OOM")
        self.assertEqual(result["phase"], "post_route_telemetry")
        self.assertEqual(result["route_components"], [])
        self.assertIn("reachability", fixture.calls)
        self.assertEqual(fixture.calls.count("cgroup.finish"), 2)

    def test_post_route_cgroup_oom_overrides_reachability_exception(self) -> None:
        fixture = _Fixture(final_oom="CGROUP_OOM_EVENT")
        fixture.reachability_error = ValueError("not reachable")
        result = fixture.run()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "CGROUP_OOM")
        self.assertEqual(result["phase"], "post_route_telemetry")
        self.assertEqual(result["message"], "CGROUP_OOM_EVENT")
        self.assertEqual(result["route_components"], [])
        self.assertEqual(fixture.calls.count("cgroup.finish"), 2)

    def test_independent_lane_reachability_failure_discards_routes(self) -> None:
        fixture = _Fixture()
        fixture.reachability_error = ValueError("not reachable")
        result = fixture.run()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "FAIL_CLOSED_EXCEPTION")
        self.assertEqual(result["phase"], "independent_reachability")
        self.assertEqual(result["route_components"], [])
        self.assertEqual(result["telemetry"]["cgroup"]["oom_attribution"], "NO_CGROUP_OOM")
        self.assertEqual(fixture.calls.count("cgroup.finish"), 2)

    def test_dependency_exception_fails_closed_before_binding(self) -> None:
        fixture = _Fixture()
        dependencies = fixture.dependencies()

        def explode(**kwargs):
            del kwargs
            raise RuntimeError("dependency unavailable")

        dependencies = replace(dependencies, resolve_placement_solution=explode)
        result = worker.run_fixed_geometry_router(
            _payload(),
            instance=_instance(),
            facility_pools={},
            dependencies=dependencies,
            config=worker.WorkerConfig(
                time_limit_seconds=1.0,
                minimum_poles=0,
                required_grid=(4, 4),
                require_cgroup=False,
            ),
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "FAIL_CLOSED_EXCEPTION")
        self.assertEqual(result["phase"], "pose_replay")
        self.assertEqual(result["route_components"], [])

    def test_default_pole_floor_rejects_before_pose_replay(self) -> None:
        fixture = _Fixture()
        result = worker.run_fixed_geometry_router(
            _payload(),
            instance=_instance(),
            facility_pools={},
            dependencies=fixture.dependencies(),
            config=worker.WorkerConfig(
                time_limit_seconds=1.0,
                minimum_poles=9,
                required_grid=(4, 4),
                require_cgroup=False,
            ),
        )
        self.assertEqual(result["error_code"], "POLE_LOWER_BOUND")
        self.assertNotIn("resolve", fixture.calls)

    def test_geometry_parser_rejects_bool_coordinate_and_unknown_field(self) -> None:
        malformed = _payload()
        malformed["required_placements"][0]["anchor"]["x"] = True
        with self.assertRaises(worker.FixedGeometryRouterError) as caught:
            worker.parse_geometry_payload(malformed, minimum_poles=0)
        self.assertEqual(caught.exception.code, "MALFORMED_INTEGER")

        malformed = _payload()
        malformed["surprise"] = 1
        with self.assertRaises(worker.FixedGeometryRouterError) as caught:
            worker.parse_geometry_payload(malformed, minimum_poles=0)
        self.assertEqual(caught.exception.code, "GEOMETRY_FIELDS")

    def test_v2_parser_requires_strict_manufacturing_binding_map(self) -> None:
        legacy = _payload()
        legacy["schema_version"] = "fixed_geometry_router_input.v1"
        with self.assertRaises(worker.FixedGeometryRouterError) as caught:
            worker.parse_geometry_payload(legacy, minimum_poles=0)
        self.assertEqual(caught.exception.code, "GEOMETRY_SCHEMA")

        malformed = _payload()
        malformed["manufacturing_port_bindings"] = {"m1": {"in": True}}
        with self.assertRaises(worker.FixedGeometryRouterError) as caught:
            worker.parse_geometry_payload(malformed, minimum_poles=0)
        self.assertEqual(caught.exception.code, "MALFORMED_STRING")

        unknown = _payload()
        unknown["manufacturing_port_bindings"] = {"not_m1": {"in": "ore"}}
        with self.assertRaises(worker.FixedGeometryRouterError) as caught:
            worker.parse_geometry_payload(unknown, minimum_poles=0)
        self.assertEqual(caught.exception.code, "UNKNOWN_MANUFACTURING_BINDING_INSTANCE")

    def test_binding_id_drift_rejects_before_automatic_selection(self) -> None:
        fixture = _Fixture()
        payload = _payload()
        payload["manufacturing_port_bindings"] = {}
        result = fixture.run(payload=payload)
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["error_code"], "MANUFACTURING_BINDING_ID_SET")
        self.assertNotIn("choose", fixture.calls)

    def test_bound_manufacturing_binding_drift_is_read_back_and_rejected(self) -> None:
        fixture = _Fixture()
        fixture.bound_binding_override = {"in": "ore"}
        result = fixture.run()
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "FAIL_CLOSED_CONTRACT_ERROR")
        self.assertEqual(result["error_code"], "MANUFACTURING_BINDING_OVERRIDE_DRIFT")
        self.assertNotIn("derive", fixture.calls)

    def test_strict_json_loader_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geometry.json"
            path.write_text('{"schema_version":"a","schema_version":"b"}', encoding="utf-8")
            with self.assertRaises(worker.FixedGeometryRouterError) as caught:
                worker.load_geometry_payload(path)
        self.assertEqual(caught.exception.code, "GEOMETRY_READ_FAILED")

    def test_geometry_loader_requires_exact_raw_hash_when_pinned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geometry.json"
            raw = json.dumps(_payload(), sort_keys=True).encode("utf-8")
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            self.assertEqual(
                worker.load_geometry_payload(path, expected_sha256=digest),
                _payload(),
            )
            with self.assertRaises(worker.FixedGeometryRouterError) as caught:
                worker.load_geometry_payload(path, expected_sha256="0" * 64)
        self.assertEqual(caught.exception.code, "GEOMETRY_HASH_MISMATCH")

    def test_dependency_snapshot_does_not_swallow_external_worker_timeout(self) -> None:
        class ExternalWorkerTimeout(RuntimeError):
            code = "WORKER_WALL_TIMEOUT"

        class FakeStrictContract:
            @staticmethod
            def load_and_reconcile(project_root):
                del project_root
                raise ExternalWorkerTimeout("expired")

        with patch.object(worker.importlib, "import_module", return_value=FakeStrictContract):
            with self.assertRaises(ExternalWorkerTimeout):
                worker.load_production_input_snapshot(Path.cwd())

    def test_supervised_entry_rejects_hash_mismatch_before_dependency_or_solver_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "geometry.json"
            path.write_text(json.dumps(_payload()), encoding="utf-8")
            result = worker.run_supervised_fixed_geometry_router(
                path,
                expected_geometry_sha256="0" * 64,
                project_root=Path.cwd(),
                config=worker.WorkerConfig(
                    time_limit_seconds=1.0,
                    minimum_poles=0,
                    required_grid=(4, 4),
                    require_cgroup=False,
                ),
            )
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["classification"], "INPUT_SNAPSHOT_REJECTED")
        self.assertEqual(result["error_code"], "GEOMETRY_HASH_MISMATCH")
        self.assertEqual(result["route_components"], [])

    def test_no_overwrite_result_and_unique_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            run_dir = worker.create_unique_run_directory(parent, "run-001")
            result_path = run_dir / "result.json"
            worker.write_result_exclusive(result_path, {"status": "ok"})
            self.assertEqual(json.loads(result_path.read_text())["status"], "ok")
            with self.assertRaises(worker.FixedGeometryRouterError) as caught:
                worker.write_result_exclusive(result_path, {"status": "changed"})
            self.assertEqual(caught.exception.code, "RESULT_ALREADY_EXISTS")
            with self.assertRaises(worker.FixedGeometryRouterError) as caught:
                worker.create_unique_run_directory(parent, "run-001")
            self.assertEqual(caught.exception.code, "RUN_DIRECTORY_EXISTS")

    def test_production_dependency_factory_binds_real_router_and_adapter_surfaces(self) -> None:
        dependencies = worker.production_dependencies()
        self.assertEqual(dependencies.make_routing_grid.__qualname__, "RoutingGrid.from_placement_core")
        self.assertEqual(dependencies.make_routing_subproblem.__name__, "RoutingSubproblem")
        self.assertEqual(dependencies.add_l1_support_constraints.__name__, "add_l1_support_constraints")
        self.assertEqual(dependencies.adapt_extracted_routes.__name__, "adapt_extracted_routes")
        self.assertEqual(
            dependencies.assert_terminal_route_reachability.__name__,
            "assert_terminal_route_reachability",
        )

    def test_production_input_snapshot_reconciles_pinned_dependency_hashes(self) -> None:
        snapshot = worker.load_production_input_snapshot(Path.cwd())
        self.assertEqual(
            snapshot.hashes["strict_instance"],
            "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
        )
        self.assertEqual(
            snapshot.hashes["candidate_poses"],
            "f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3",
        )
        self.assertEqual(len(snapshot.facility_pools["power_pole"]), 4_761)

    def test_real_adapter_output_passes_real_lane_reachability_on_tiny_path(self) -> None:
        base = "docs.research.witness_constructor_20260717.07_routing_aware"
        route_adapter = importlib.import_module(f"{base}.route_adapter")
        network_router = importlib.import_module(f"{base}.network_router")

        def route_record(x: int) -> dict:
            return {
                "x": x,
                "y": 1,
                "layer": 0,
                "type": "belt",
                "component_type": "belt",
                "commodities": ["ore"],
                "uses": [{"commodity": "ore", "flow_in": ["W"], "flow_out": ["E"]}],
                "flow_in": ["W"],
                "flow_out": ["E"],
                "flow": {"flow_in": ["W"], "flow_out": ["E"]},
            }

        components = route_adapter.adapt_extracted_routes(
            [route_record(1), route_record(2)],
            terminal_cells={(1, 1), (2, 1)},
        )
        terminals = [
            network_router.Terminal("source", "p", "output", "ore", (1, 1), "E"),
            network_router.Terminal("sink", "p", "input", "ore", (2, 1), "W"),
        ]
        network_router.assert_terminal_route_reachability(components, terminals, ["ore"])
        self.assertEqual([component["kind"] for component in components], ["straight", "straight"])


if __name__ == "__main__":
    unittest.main()
