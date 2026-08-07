"""Production-scale build/solve benchmark for the mixflow surgery.

External review 2026-08-06 finding F-04 item 1: the numbers in `DESIGN.md` §7
were not independently reproducible because the benchmark script was not part
of the review package.  This is that script, in the repository.

Fixture (the same adversarial proxy `DESIGN.md` §7 records): a 70x70 grid with
a pitch-4 lattice of 3x3 machine bodies, which leaves width-1 corridors, plus
one port per body with the commodity rotating and out/in alternating.  Every
corridor is shared by every commodity and terminal-core peeling cannot remove a
single cell, so it is deliberately the worst shape for the surgery, not a
typical one.

Three arms, all built in one process against one fixture:

    pre     the pre-surgery whole-pattern model (`git show <ref>:<path>`)
    post    the surgery without the de-mix ban (ban method neutralized)
    post+3  the shipped model (option 3, conservative de-mix ban)

Usage:
    python docs/research/mixflow_surgery_20260806/bench_mixflow_prodscale.py \
        [--pre-ref 5af80d0] [--solve-seconds 120] [--pitch 4] [--commodities 19]

Reports build wall time, use/phys variable counts, proto constraint rows and
(optionally) the solve status, as JSON on stdout.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_MODULE_PATH = REPO_ROOT / "src" / "models" / "routing_subproblem.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _checkout_pre_surgery(ref: str) -> Path:
    blob = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{ref}:src/models/routing_subproblem.py"],
        check=True,
        capture_output=True,
    ).stdout
    handle = tempfile.NamedTemporaryFile(
        prefix="routing_pre_", suffix=".py", delete=False, dir=tempfile.gettempdir()
    )
    handle.write(blob)
    handle.close()
    return Path(handle.name)


def build_fixture(module, pitch: int, body: int, commodity_count: int, per_axis: int):
    """Pitch-`pitch` lattice of `body`x`body` machines; one port per machine."""
    grid_w, grid_h = module.GRID_W, module.GRID_H
    occupied = set()
    origins: List[Tuple[int, int]] = []
    for ox in range(0, per_axis * pitch, pitch):
        for oy in range(0, per_axis * pitch, pitch):
            if ox + body >= grid_w or oy + body >= grid_h:
                continue
            origins.append((ox, oy))
            for dx in range(body):
                for dy in range(body):
                    occupied.add((ox + dx, oy + dy))

    commodities = [f"c{i}" for i in range(commodity_count)]
    ports = []
    for index, (ox, oy) in enumerate(origins):
        # front cell sits immediately east of the body, so the body is west of
        # it: an output port emits east (receives from its west body side) and
        # an input port sends west into that same body side.
        front = (ox + body, oy + body // 2)
        if front in occupied or not (0 <= front[0] < grid_w):
            continue
        ports.append(
            {
                "x": front[0],
                "y": front[1],
                "dir": "E",
                "commodity": commodities[index % commodity_count],
                "type": "out" if index % 2 == 0 else "in",
                "instance_id": f"body{index}",
            }
        )
    return occupied, ports, commodities, len(origins)


def run_arm(
    module,
    name: str,
    occupied,
    ports,
    commodities,
    solve_seconds: float,
    disable_demix_ban: bool,
) -> Dict[str, Any]:
    saved = getattr(module.RoutingSubproblem, "_add_demix_ban_constraints", None)
    if disable_demix_ban and saved is not None:
        module.RoutingSubproblem._add_demix_ban_constraints = lambda self: None
    try:
        grid = module.RoutingGrid(occupied, ports)
        analysis = module.analyze_exact_routing_domain(grid)
        routing = module.RoutingSubproblem(grid, commodities, domain_analysis=analysis)

        t0 = time.perf_counter()
        routing.build()
        build_seconds = time.perf_counter() - t0

        result: Dict[str, Any] = {
            "arm": name,
            "domain_status": analysis.get("status"),
            "build_seconds": round(build_seconds, 2),
            "use_vars": len(routing.use_vars),
            "phys_vars": len(routing.phys_vars),
            "constraints": len(routing.model.Proto().constraints),
            "demix_ban": routing.build_stats.get("demix_ban"),
        }
        if solve_seconds > 0:
            t1 = time.perf_counter()
            result["solve_status"] = routing.solve(time_limit=solve_seconds)
            result["solve_seconds"] = round(time.perf_counter() - t1, 2)
        return result
    finally:
        if disable_demix_ban and saved is not None:
            module.RoutingSubproblem._add_demix_ban_constraints = saved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-ref", default="5af80d0", help="pre-surgery git ref")
    parser.add_argument("--solve-seconds", type=float, default=0.0)
    parser.add_argument("--pitch", type=int, default=4)
    parser.add_argument("--body", type=int, default=3)
    parser.add_argument("--commodities", type=int, default=19)
    parser.add_argument(
        "--bodies-per-axis",
        type=int,
        default=16,
        help="lattice side; 16 reproduces the 256-body proxy of DESIGN.md section 7",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(REPO_ROOT))
    live = _load_module("bench_routing_live", LIVE_MODULE_PATH)
    pre_path = _checkout_pre_surgery(args.pre_ref)
    pre = _load_module("bench_routing_pre", pre_path)

    occupied, ports, commodities, body_count = build_fixture(
        live, args.pitch, args.body, args.commodities, args.bodies_per_axis
    )

    report = {
        "fixture": {
            "bodies": body_count,
            "ports": len(ports),
            "commodities": len(commodities),
            "pitch": args.pitch,
            "body": args.body,
            "free_cells": live.GRID_W * live.GRID_H - len(occupied),
        },
        "pre_ref": args.pre_ref,
        "arms": [
            run_arm(pre, "pre", occupied, ports, commodities, args.solve_seconds, False),
            run_arm(live, "post", occupied, ports, commodities, args.solve_seconds, True),
            run_arm(live, "post+3", occupied, ports, commodities, args.solve_seconds, False),
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
