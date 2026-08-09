#!/usr/bin/env python3
"""Reproduce the 4-cell de-mix soundness counterexample.

Usage:
    python repro_demix_no_filter_slot.py /path/to/extracted/review/package

The directory must contain routing_subproblem.BEFORE.py and
routing_subproblem.AFTER.py. OR-Tools must be installed.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _install_isolated_worker_config_stub() -> None:
    """Supply only the unrelated worker/memory helpers missing from the review bundle."""
    src = sys.modules.setdefault("src", types.ModuleType("src"))
    models = sys.modules.setdefault("src.models", types.ModuleType("src.models"))
    setattr(src, "models", models)

    cfg = types.ModuleType("src.models.cp_sat_worker_config")
    cfg.DEFAULT_ROUTING_CP_SAT_WORKERS = 1

    def resolve_cp_sat_worker_count(*, env_name: str, default: int) -> int:
        del env_name
        return int(default)

    def apply_subproblem_memory_cap(solver: object) -> None:
        del solver

    cfg.resolve_cp_sat_worker_count = resolve_cp_sat_worker_count
    cfg.apply_subproblem_memory_cap = apply_subproblem_memory_cap
    sys.modules["src.models.cp_sat_worker_config"] = cfg


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run(module):
    # M=(5,5) is a content-blind merger, D=(6,5) a content-blind splitter.
    # Both post-split branches contain only a corner terminal belt, so the
    # documented straight-only item filter has no legal placement cell.
    free = {(5, 5), (6, 5), (7, 5), (6, 6)}
    occupied = {
        (x, y)
        for x in range(module.GRID_W)
        for y in range(module.GRID_H)
        if (x, y) not in free
    }
    ports = [
        {"x": 5, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 5, "y": 5, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        # A branch terminal: W -> N corner.
        {"x": 7, "y": 5, "dir": "S", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        # B branch terminal: S -> W corner.
        {"x": 6, "y": 6, "dir": "E", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    grid = module.RoutingGrid(occupied, ports)
    analysis = module.analyze_exact_routing_domain(grid)
    routing = module.RoutingSubproblem(grid, ["a", "b"], domain_analysis=analysis)
    routing.build()
    status = routing.solve(time_limit=10.0)
    routes = routing.extract_routes()
    connectivity = None
    if status == "FEASIBLE":
        connected, summary = routing._validate_selected_route_connectivity(routing._solver)
        connectivity = {"connected": connected, "summary": summary}
    return status, routes, connectivity


def main() -> int:
    review_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    before_path = review_dir / "routing_subproblem.BEFORE.py"
    after_path = review_dir / "routing_subproblem.AFTER.py"
    for path in (before_path, after_path):
        if not path.is_file():
            raise SystemExit(f"missing file: {path}")

    _install_isolated_worker_config_stub()
    before = _load("review_routing_before", before_path)
    after = _load("review_routing_after", after_path)

    before_status, _before_routes, _before_conn = _run(before)
    after_status, after_routes, after_conn = _run(after)

    print("before_status:", before_status)
    print("after_status:", after_status)
    print("after_connectivity:", after_conn)
    print("after_routes:")
    for route in after_routes:
        print(route)

    assert before_status == "INFEASIBLE", before_status
    assert after_status == "FEASIBLE", after_status
    assert after_conn is not None and after_conn["connected"] is True, after_conn
    assert after_conn["summary"]["failure_count"] == 0, after_conn
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
