#!/usr/bin/env python3
"""Serial all-residual local queries for the final 35-pole geometry."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path("/home/zhuran24/zmd-pj-codex")
RECOVERY = (
    ROOT
    / "docs/research/witness_constructor_20260717/07_routing_aware/recovery_runs/"
    "restart-20260720T075344Z-kYNVbm"
)
SCRIPTS = RECOVERY / "scripts"
OUT_DIR = RECOVERY / "fixed_bays/final35_small_bay_closure"
EXPECTED = {
    SCRIPTS / "reduced_connected_allocation.py": (
        "2f7382688565c0d3b180b5d41a1c66ae32c1733e83fa4d59bc05f631bc60afcc"
    ),
    SCRIPTS / "reduced_backbone_component_frontiers.py": (
        "15e027d9fc719daa7c904589a2c8cd068b83845bcda7d6393db7f4cf084263e4"
    ),
    SCRIPTS / "component_frontier_patterns.py": (
        "bd00682b3d03656d556073c4c2b4ed2f4cac565df96b9d9c08fa465dbbec1400"
    ),
    SCRIPTS / "current35_component_frontiers.py": (
        "13e1ed5bd5bc386970077ac51abd5eabb8a987dc9010f04c3d3026456f098861"
    ),
    SCRIPTS / "zmd_backbone_front_compact.py": (
        "14b128be038e29d4434e3de822740c961ace7c1d45f24bf4d50dd5f4b101c0be"
    ),
}
Cell = tuple[int, int]
TEMPLATES = ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")
BASELINE_REPRESENTATIVES: Mapping[int, Cell] = {
    4: (49, 2),
    10: (60, 37),
    11: (2, 37),
    12: (13, 60),
    13: (25, 60),
    14: (37, 60),
    15: (2, 60),
    16: (49, 60),
}
QUERIES = (
    (10, (9, 2, 2), "baseline"),
    (11, (9, 1, 2), "baseline"),
    (12, (5, 1, 1), "adder"),
    (13, (5, 1, 1), "adder"),
    (14, (5, 1, 1), "adder"),
    (15, (4, 2, 0), "adder"),
    (16, (4, 2, 0), "adder"),
)
FALLBACK = (4, (11, 4, 4), "fallback")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str, path: Path) -> Any:
    observed = sha256(path)
    require(observed == EXPECTED[path], f"hash drift for {path}: {observed}")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def final_poles(worker: Any) -> set[Cell]:
    baseline = {
        (x, y)
        for x in worker.STATIC.POLE_AXIS
        for y in worker.STATIC.POLE_AXIS
    } - {(65, 65)}
    moved_from = {(x, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    moved_to = {(x + 1, y) for x in (17, 29, 41, 65) for y in (5, 17, 29)}
    result = (baseline - moved_from) | moved_to
    require(len(result) == 35, f"final pole count {len(result)}")
    return result


def final_fixed_geometry(reduced: Any, worker: Any, protected_anchor: Cell) -> dict[str, Any]:
    fixed = dict(reduced.reduced_fixed_geometry(worker, protected_anchor))
    poles = final_poles(worker)
    pole_cells = set().union(*(worker.STATIC.pole_body(anchor) for anchor in poles))
    fixed_body = set(fixed["core"]) | pole_cells | set(fixed["boundary"])
    power = set().union(*(worker.STATIC.pole_coverage(anchor) for anchor in poles))
    require(len(pole_cells) == 140, "final pole bodies overlap")
    require(not pole_cells & set(fixed["core"]), "final pole/core collision")
    require(not pole_cells & set(fixed["boundary"]), "final pole/boundary collision")
    require(not pole_cells & set(fixed["backbone"]), "final pole/backbone collision")
    require(not pole_cells & set(fixed["protected"]), "final pole/protected collision")
    fixed.update(
        {
            "pole_anchors": poles,
            "pole_cells": pole_cells,
            "fixed_body": fixed_body,
            "body_forbidden": fixed_body | set(fixed["backbone"]) | set(fixed["protected"]),
            "power": power,
        }
    )
    return fixed


def output_path(component: int, target: tuple[int, int, int]) -> Path:
    return OUT_DIR / f"c{component}_target_{target[0]}_{target[1]}_{target[2]}.json"


def write_exclusive(path: Path, record: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def terminal(record: Mapping[str, Any], component: int, target: tuple[int, int, int]) -> bool:
    return (
        record.get("schema_version") == "final35_small_bay_query.v1"
        and record.get("requested_component") == component
        and record.get("target") == list(target)
        and record.get("status") in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "MODEL_INVALID"}
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds-per-query", type=float, default=240.0)
    args = parser.parse_args(argv)
    require(args.seconds_per_query > 0, "seconds-per-query must be positive")
    OUT_DIR.mkdir(mode=0o755, parents=False, exist_ok=True)

    worker = load("final35_worker", SCRIPTS / "zmd_backbone_front_compact.py")
    reduced = load("final35_reduced", SCRIPTS / "reduced_backbone_component_frontiers.py")
    helper = load("final35_helper", SCRIPTS / "component_frontier_patterns.py")
    current = load("final35_current", SCRIPTS / "current35_component_frontiers.py")
    solver = load("final35_solver", SCRIPTS / "reduced_connected_allocation.py")
    original_fixed = reduced.reduced_fixed_geometry

    def patched_fixed(worker_arg: Any, protected_anchor: Cell) -> dict[str, Any]:
        reduced.reduced_fixed_geometry = original_fixed
        try:
            return final_fixed_geometry(reduced, worker_arg, protected_anchor)
        finally:
            reduced.reduced_fixed_geometry = patched_fixed

    reduced.reduced_fixed_geometry = patched_fixed
    data = reduced.load_reduced_data(worker, (7, 36))
    components, poses, locality = current.build_local_inputs(
        worker, helper, data, expected_manufacturing_components=17
    )
    outside_main = set(data.fixed["backbone"]) | set(data.fixed["protected"])
    successful_adders = 0
    rows = []
    queue = list(QUERIES)
    for requested_component, target, purpose in queue:
        if purpose == "adder" and successful_adders >= 4:
            break
        representative = BASELINE_REPRESENTATIVES[requested_component]
        observed_component = next(
            index for index, cells in enumerate(components) if representative in cells
        )
        component = set(components[observed_component])
        origin = (min(x for x, _y in component), min(y for _x, y in component))
        component_local = {(x - origin[0], y - origin[1]) for x, y in component}
        gateways_global = {
            cell
            for cell in component
            if any(adjacent in data.fixed["backbone"] for adjacent in solver.neighbours(cell))
        }
        gateways_local = {(x - origin[0], y - origin[1]) for x, y in gateways_global}
        path = output_path(requested_component, target)
        if path.exists():
            result = json.loads(path.read_bytes())
            require(terminal(result, requested_component, target), f"invalid checkpoint: {path}")
        else:
            result = solver.solve_exact(
                poses[observed_component],
                target,
                component_local,
                gateways_local,
                args.seconds_per_query,
            )
            if result["status"] in {"OPTIMAL", "FEASIBLE"}:
                require(result["residual_cells"] == result["residual_reachable_from_gateway"], "residual split")
                require(
                    Counter(row["template"] for row in result["selected"])
                    == Counter(dict(zip(TEMPLATES, target, strict=True))),
                    "selected target drift",
                )
            result.update(
                {
                    "schema_version": "final35_small_bay_query.v1",
                    "classification": "research_local_all_residual_query_no_router",
                    "claim_boundary": (
                        "One final-35-pole local bay only: exact body counts, power-filtered strict pose "
                        "domain, clear weakest-signature fronts, and all residual cells connected to "
                        "the fixed backbone. No global assembly or commodity-routing conclusion."
                    ),
                    "requested_component": requested_component,
                    "observed_component": observed_component,
                    "purpose": purpose,
                    "origin": list(origin),
                    "representative": list(representative),
                    "final_pole_anchors": [list(cell) for cell in sorted(data.fixed["pole_anchors"])],
                    "final_pole_count": len(data.fixed["pole_anchors"]),
                    "final_pole_body_cells": len(data.fixed["pole_cells"]),
                    "outside_main_cells": len(outside_main),
                    "source_sha256": {str(path): digest for path, digest in EXPECTED.items()},
                    "locality": locality,
                }
            )
            write_exclusive(path, result)
        rows.append({"path": str(path), "sha256": sha256(path), "status": result["status"]})
        if purpose == "adder" and result["status"] in {"OPTIMAL", "FEASIBLE"}:
            successful_adders += 1
        print(
            f"component={requested_component} target={target} status={result['status']} "
            f"seconds={result['wall_time_seconds']:.3f}",
            flush=True,
        )

    if successful_adders < 4:
        requested_component, target, purpose = FALLBACK
        representative = BASELINE_REPRESENTATIVES[requested_component]
        observed_component = next(index for index, cells in enumerate(components) if representative in cells)
        component = set(components[observed_component])
        origin = (min(x for x, _y in component), min(y for _x, y in component))
        component_local = {(x - origin[0], y - origin[1]) for x, y in component}
        gateways = {
            (x - origin[0], y - origin[1])
            for x, y in component
            if any(adjacent in data.fixed["backbone"] for adjacent in solver.neighbours((x, y)))
        }
        path = output_path(requested_component, target)
        if path.exists():
            result = json.loads(path.read_bytes())
            require(terminal(result, requested_component, target), f"invalid checkpoint: {path}")
        else:
            result = solver.solve_exact(
                poses[observed_component], target, component_local, gateways, args.seconds_per_query
            )
            result.update(
                {
                    "schema_version": "final35_small_bay_query.v1",
                    "classification": "research_local_all_residual_query_no_router",
                    "claim_boundary": "Fallback final-35-pole local bay only; no global or routing conclusion.",
                    "requested_component": requested_component,
                    "observed_component": observed_component,
                    "purpose": purpose,
                    "origin": list(origin),
                    "representative": list(representative),
                    "final_pole_anchors": [list(cell) for cell in sorted(data.fixed["pole_anchors"])],
                    "final_pole_count": len(data.fixed["pole_anchors"]),
                    "final_pole_body_cells": len(data.fixed["pole_cells"]),
                    "source_sha256": {str(path): digest for path, digest in EXPECTED.items()},
                    "locality": locality,
                }
            )
            write_exclusive(path, result)
        rows.append({"path": str(path), "sha256": sha256(path), "status": result["status"]})
        print(
            f"component={requested_component} target={target} status={result['status']} "
            f"seconds={result['wall_time_seconds']:.3f}",
            flush=True,
        )

    summary = OUT_DIR / "summary.json"
    require(not summary.exists(), f"refusing overwrite: {summary}")
    write_exclusive(
        summary,
        {
            "schema_version": "final35_small_bay_closure_summary.v1",
            "classification": "research_serial_local_all_residual_queries_no_router",
            "successful_adders": successful_adders,
            "rows": rows,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
