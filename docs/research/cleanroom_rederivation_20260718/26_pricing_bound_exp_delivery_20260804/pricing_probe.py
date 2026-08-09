#!/usr/bin/env python3
"""Bucket-weighted local pricing probe for the bundled 14x14 model.

Research-only.  The harness is deliberately separate from any proof registry.  It
extends 11_runnable/probe/area_probe.py with all capability levels, exact bucket
weights, fixed hole/no-hole branches, optional no-connectivity relaxation, and
incumbent/best-bound trajectories.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

Cell = Tuple[int, int]
HERE = Path(__file__).resolve().parent
DEFAULT_BUNDLE = HERE.parent / "pricing_exp" / "11_runnable"
DEFAULT_SAMPLE_TIMES = (0.0, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0, 240.0)


@dataclass(frozen=True)
class Dual:
    name: str
    scale: int
    mu_scaled: Mapping[str, int]
    lambda_scaled: int
    pi_scaled: Mapping[str, int]
    analytic_branch_cap_scaled: Mapping[str, Mapping[str, Optional[int]]]


def load_modules(bundle: Path) -> Dict[str, Any]:
    root = bundle.resolve()
    g1 = root / "docs" / "research" / "w0_front_aware_20260803"
    for item in (str(g1), str(root / "probe")):
        if item not in sys.path:
            sys.path.insert(0, item)
    import g1_pattern_evaluator as evaluator
    import g1_pattern_generator as generator
    import g1_pattern_schema as schema
    import g1_port_semantics as ports
    import g1_region_model as regions
    import independent_region_audit as audit
    return {
        "bundle": root,
        "evaluator": evaluator,
        "generator": generator,
        "schema": schema,
        "ports": ports,
        "regions": regions,
        "audit": audit,
    }


def load_dual(path: Path, name: str) -> Dual:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload["duals"] if isinstance(payload, dict) and "duals" in payload else payload
    for row in rows:
        if row["name"] != name:
            continue
        scale = int(row.get("scale", 1))
        if scale <= 0:
            raise ValueError("scale must be positive")
        return Dual(
            name=name,
            scale=scale,
            mu_scaled={str(k): int(v) for k, v in row["mu_scaled"].items()},
            lambda_scaled=int(row["lambda_scaled"]),
            pi_scaled={str(k): int(v) for k, v in row.get("pi_scaled", {}).items()},
            analytic_branch_cap_scaled={
                str(f): {
                    "nohole": None if caps.get("nohole") is None else int(caps["nohole"]),
                    "hole": None if caps.get("hole") is None else int(caps["hole"]),
                }
                for f, caps in row.get("analytic_branch_cap_scaled", {}).items()
            },
        )
    raise KeyError(f"dual {name!r} not found in {path}")


def template_area(template: str, evaluator: Any) -> int:
    width, height = evaluator.template_footprint(template, 0)
    return int(width * height)


def derive_bucket_weights(dual: Dual, modules: Mapping[str, Any]) -> Dict[str, int]:
    ports = modules["ports"]
    evaluator = modules["evaluator"]
    missing = set(ports.CLASS_ORDER) - set(dual.mu_scaled)
    if missing:
        raise ValueError(f"dual is missing mu values for {sorted(missing)}")
    if any(int(dual.mu_scaled[c]) < 0 for c in ports.CLASS_ORDER):
        raise ValueError("mu must be nonnegative")
    result: Dict[str, int] = {}
    for bucket in ports.BUCKET_ORDER:
        classes = tuple(ports.BUCKET_SERVABLE[bucket])
        template = ports.CLASS_BY_ID[classes[0]].template
        area_scaled = template_area(template, evaluator) * dual.scale
        result[bucket] = area_scaled - min(dual.mu_scaled[c] for c in classes)
    return result


def derive_level_bucket(modules: Mapping[str, Any]) -> Dict[Tuple[str, int], str]:
    ports = modules["ports"]
    generator = modules["generator"]
    mapping: Dict[Tuple[str, int], str] = {}
    for template, levels in generator.TEMPLATE_LEVELS.items():
        rows = [row for row in ports.CLASS_TABLE if row.template == template]
        for level_raw in levels:
            level = int(level_raw)
            servable = frozenset(
                row.class_id for row in rows
                if max(int(row.r_in), int(row.r_out)) <= level
            )
            mapping[(template, level)] = ports.bucket_id_for_servable(
                template, servable, ports.CLASS_TABLE
            )
    return mapping


def _neighbors(cell: Cell) -> Tuple[Cell, Cell, Cell, Cell]:
    u, v = cell
    return ((u + 1, v), (u - 1, v), (u, v + 1), (u, v - 1))


def _kept_levels(
    modules: Mapping[str, Any], weights: Mapping[str, int], level_bucket: Mapping[Tuple[str, int], str]
) -> Dict[str, set[int]]:
    """Exact dual-specific dominance reduction.

    Bucket weights are monotone along each capability chain.  Equal-weight higher
    levels are dominated by the lower level at the same anchor/side.  Nonpositive
    levels are dominated by deleting that body because the empty pattern is legal.
    """
    generator = modules["generator"]
    kept: Dict[str, set[int]] = {}
    for template, raw_levels in generator.TEMPLATE_LEVELS.items():
        levels = sorted(int(level) for level in raw_levels)
        sequence = [int(weights[level_bucket[(template, level)]]) for level in levels]
        if any(sequence[i] > sequence[i + 1] for i in range(len(sequence) - 1)):
            raise AssertionError(f"nonmonotone bucket weights for {template}: {sequence}")
        selected: set[int] = set()
        prior: Optional[int] = None
        for level, weight in zip(levels, sequence):
            if weight > 0 and (prior is None or weight > prior):
                selected.add(level)
            prior = weight if prior is None else max(prior, weight)
        kept[template] = selected
    return kept


def build_model(
    modules: Mapping[str, Any],
    *,
    family: str,
    dual: Dual,
    hole: bool,
    strict: bool,
    relaxed: bool,
    max_poles: Optional[int],
    objective_cap_scaled: Optional[int],
) -> Dict[str, Any]:
    """Build one fixed-hole-state pricing branch.

    Objective, in scaled units:
        sum_b w_b(mu) n_b - lambda * 1[hole].
    Hole/no-hole branches must be maximized separately and then combined with max.
    """
    from ortools.sat.python import cp_model

    generator = modules["generator"]
    evaluator = modules["evaluator"]
    regions = modules["regions"]
    ports = modules["ports"]
    if family not in regions.REGION_CLASSES:
        raise KeyError(f"unknown family {family!r}")
    region = regions.REGION_CLASSES[family]
    weights = derive_bucket_weights(dual, modules)
    level_bucket = derive_level_bucket(modules)
    keep_levels = _kept_levels(modules, weights, level_bucket)

    all_poses = tuple(generator.enumerate_body_poses(region))
    poses = tuple(p for p in all_poses if int(p.level) in keep_levels[p.template])
    pole_anchors = tuple(generator.enumerate_pole_poses(region))
    hole_poses = tuple(generator.enumerate_hole_poses(region)) if hole else ()

    model = cp_model.CpModel()
    pose_vars = {p.key: model.new_bool_var(f"p_{i}") for i, p in enumerate(poses)}
    pole_vars = {a: model.new_bool_var(f"g_{a[0]}_{a[1]}") for a in pole_anchors}

    cells = tuple(
        (u, v)
        for u in range(regions.REGION_SIZE)
        for v in range(regions.REGION_SIZE)
        if (u, v) not in region.fixed_local
    )
    cell_set = set(cells)
    occ = {c: model.new_bool_var(f"o_{c[0]}_{c[1]}") for c in cells}
    conn: Dict[Cell, Any] = {}
    if not relaxed:
        conn = {c: model.new_bool_var(f"q_{c[0]}_{c[1]}") for c in cells}

    covering: Dict[Cell, List[Any]] = {c: [] for c in cells}
    for pose in poses:
        for cell in pose.cells:
            covering[cell].append(pose_vars[pose.key])
    for anchor in pole_anchors:
        for cell in evaluator.pole_cells(anchor):
            covering[cell].append(pole_vars[anchor])
    for cell in cells:
        literals = covering[cell]
        if literals:
            model.add_at_most_one(literals)
            model.add(sum(literals) == occ[cell])
        else:
            model.add(occ[cell] == 0)
        if not relaxed:
            model.add(conn[cell] + occ[cell] <= 1)

    # Fixed reservations remain body/pole-free.
    for cell in region.reserved_local:
        if cell in occ:
            model.add(occ[cell] == 0)

    live_stubs = tuple(c for c in region.live_stubs if c in cell_set)
    fixed_fronts = tuple(c for c in region.fixed_front_local if c in cell_set)
    if not relaxed:
        for cell in (*live_stubs, *fixed_fronts):
            model.add(conn[cell] == 1)

    # Non-dead capability: every selected pose has enough connected free front cells.
    for pose in poses:
        selected = pose_vars[pose.key]
        for front_cells, required_raw in (
            (pose.wide_variable_cells, pose.wide_required),
            (pose.narrow_variable_cells, pose.narrow_required),
        ):
            required = int(required_raw)
            if relaxed:
                model.add(sum(occ[c] for c in front_cells) + required * selected <= len(front_cells))
            else:
                model.add(sum(conn[c] for c in front_cells) >= required * selected)

    # R-POWER-LOCAL.  The primary experiment removes the arbitrary fixed cap 3.
    stencils = {a: evaluator.coverage_cells(a) for a in pole_anchors}
    pole_to_bodies: Dict[Cell, List[Any]] = {a: [] for a in pole_anchors}
    for pose in poses:
        anchors = tuple(
            a for a in pole_anchors if any(cell in stencils[a] for cell in pose.cells)
        )
        model.add_bool_or([pole_vars[a] for a in anchors] + [pose_vars[pose.key].negated()])
        for anchor in anchors:
            pole_to_bodies[anchor].append(pose_vars[pose.key])
    for anchor, pole_var in pole_vars.items():
        bodies = pole_to_bodies[anchor]
        if bodies:
            model.add(pole_var <= sum(bodies))
        else:
            model.add(pole_var == 0)
    if max_poles is not None:
        model.add(sum(pole_vars.values()) <= int(max_poles))

    hole_vars: Dict[Tuple[Cell, int, int], Any] = {}
    if hole:
        for anchor, width, height in hole_poses:
            spec = (anchor, int(width), int(height))
            hvar = model.new_bool_var(f"h_{anchor[0]}_{anchor[1]}_{width}x{height}")
            hole_vars[spec] = hvar
            for dx in range(width):
                for dy in range(height):
                    cell = (anchor[0] + dx, anchor[1] + dy)
                    if relaxed:
                        model.add(occ[cell] == 0).only_enforce_if(hvar)
                    else:
                        model.add(conn[cell] == 1).only_enforce_if(hvar)
        if not hole_vars:
            return {
                "model": None, "reason": "NO_HOLE_POSE", "family": family, "hole": hole,
                "weights": weights, "all_pose_count": len(all_poses), "kept_levels": keep_levels,
            }
        model.add_exactly_one(hole_vars.values())

    # Single-commodity-flow connectivity certificate, copied from the supplied probe.
    flow_vars: Dict[Tuple[Cell, Cell], Any] = {}
    source_vars: Dict[Cell, Any] = {}
    if not relaxed:
        cap = len(cells)
        for cell in cells:
            for nbr in _neighbors(cell):
                if nbr in cell_set:
                    flow_vars[(cell, nbr)] = model.new_int_var(0, cap, f"f_{cell}_{nbr}")
        for (tail, head), flow in flow_vars.items():
            model.add(flow <= cap * conn[tail])
            model.add(flow <= cap * conn[head])
        roots = (live_stubs[:1] or fixed_fronts[:1]) if strict else (live_stubs or fixed_fronts[:1])
        if not roots:
            raise ValueError(f"family {family} has no connectivity root")
        source_vars = {cell: model.new_int_var(0, cap, f"s_{cell[0]}_{cell[1]}") for cell in roots}
        for cell in cells:
            inflow = [flow_vars[(nbr, cell)] for nbr in _neighbors(cell) if (nbr, cell) in flow_vars]
            outflow = [flow_vars[(cell, nbr)] for nbr in _neighbors(cell) if (cell, nbr) in flow_vars]
            source = [source_vars[cell]] if cell in source_vars else []
            model.add(sum(inflow) + sum(source) - sum(outflow) == conn[cell])

    max_bodies = len(cells) // 9
    bucket_counts: Dict[str, Any] = {}
    for bucket in ports.BUCKET_ORDER:
        members = [
            pose_vars[p.key] for p in poses
            if level_bucket[(p.template, int(p.level))] == bucket
        ]
        count = model.new_int_var(0, max_bodies, f"n_{bucket}")
        model.add(count == sum(members))
        bucket_counts[bucket] = count

    objective = sum(int(weights[b]) * bucket_counts[b] for b in ports.BUCKET_ORDER)
    if hole:
        objective += -int(dual.lambda_scaled)
    if objective_cap_scaled is not None:
        model.add(objective <= int(objective_cap_scaled))
    model.maximize(objective)

    signature_payload = {
        "family": family,
        "dual": dual.name,
        "hole": hole,
        "strict": strict,
        "relaxed": relaxed,
        "max_poles": max_poles,
        "objective_cap_scaled": objective_cap_scaled,
        "weights": weights,
        "kept_levels": {k: sorted(v) for k, v in keep_levels.items()},
        "variables": len(model.proto.variables),
        "constraints": len(model.proto.constraints),
    }
    signature_bytes = json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "model": model,
        "reason": None,
        "family": family,
        "region": region,
        "hole": hole,
        "strict": strict,
        "relaxed": relaxed,
        "poses": poses,
        "pose_vars": pose_vars,
        "pole_anchors": pole_anchors,
        "pole_vars": pole_vars,
        "hole_vars": hole_vars,
        "bucket_counts": bucket_counts,
        "weights": weights,
        "level_bucket": level_bucket,
        "objective": objective,
        "objective_cap_scaled": objective_cap_scaled,
        "model_signature_sha256": hashlib.sha256(signature_bytes).hexdigest(),
        "model_size": {
            "variables": len(model.proto.variables),
            "constraints": len(model.proto.constraints),
            "all_semantic_body_pose_literals": len(all_poses),
            "kept_body_pose_literals": len(pose_vars),
            "pole_literals": len(pole_vars),
            "hole_literals": len(hole_vars),
            "occupancy_literals": len(occ),
            "connectivity_literals": len(conn),
            "directed_flow_variables": len(flow_vars),
            "source_variables": len(source_vars),
            "bucket_count_variables": len(bucket_counts),
            "kept_levels": {k: sorted(v) for k, v in keep_levels.items()},
        },
    }


def _footprint_offsets(body: Any, evaluator: Any) -> List[Cell]:
    width, height = evaluator.template_footprint(body.template, body.orientation)
    return [(dx, dy) for dx in range(width) for dy in range(height)]


def extract_and_evaluate(
    handles: Mapping[str, Any], solver: Any, modules: Mapping[str, Any], dual: Dual
) -> Dict[str, Any]:
    evaluator = modules["evaluator"]
    schema = modules["schema"]
    audit = modules["audit"]
    chosen = [p for p in handles["poses"] if solver.value(handles["pose_vars"][p.key])]
    chosen_poles = [a for a in handles["pole_anchors"] if solver.value(handles["pole_vars"][a])]
    hole_spec = None
    for (anchor, width, height), var in handles["hole_vars"].items():
        if solver.value(var):
            hole_spec = schema.HoleSpec(local_anchor=anchor, width=width, height=height)
            break
    bodies = tuple(
        schema.BodySpec(
            bid=i, template=p.template, orientation=p.orientation, local_anchor=p.anchor
        )
        for i, p in enumerate(sorted(chosen, key=lambda p: (p.anchor, p.template, p.orientation)))
    )
    if bodies:
        named = [
            (
                f"b{body.bid}",
                tuple(
                    (body.local_anchor[0] + dx, body.local_anchor[1] + dy)
                    for dx, dy in _footprint_offsets(body, evaluator)
                ),
            )
            for body in bodies
        ]
        try:
            chosen_poles = list(evaluator.minimize_poles(named, sorted(chosen_poles)))
        except ValueError:
            chosen_poles = sorted(chosen_poles)
    spec = schema.PatternSpec(
        region_class=handles["family"],
        bodies=bodies,
        poles=tuple(schema.PoleSpec(local_anchor=a) for a in sorted(chosen_poles)),
        hole=hole_spec,
    )
    evaluation = evaluator.evaluate_pattern(spec)
    independent = audit.audit_pattern(spec)
    actual_counts = dict(sorted(evaluation.bucket_counts.items()))
    actual_without_hole = sum(
        int(handles["weights"][bucket]) * int(count)
        for bucket, count in actual_counts.items()
    )
    actual = actual_without_hole - (dual.lambda_scaled if handles["hole"] else 0)
    credited_counts = {
        bucket: int(solver.value(var))
        for bucket, var in handles["bucket_counts"].items()
        if solver.value(var)
    }
    credited = sum(handles["weights"][b] * n for b, n in credited_counts.items())
    if handles["hole"]:
        credited -= dual.lambda_scaled
    return {
        "evaluator_ok": bool(evaluation.ok),
        "evaluator_violations": list(evaluation.violations),
        "independent_audit_ok": bool(independent["ok"]),
        "independent_audit_issues": independent["issues"],
        "single_component": independent["single_component"],
        "credited_bucket_counts": credited_counts,
        "actual_bucket_counts": actual_counts,
        "credited_objective_scaled": int(credited),
        "actual_objective_scaled": int(actual),
        "actual_ge_credited": bool(actual >= credited),
        "body_count": len(bodies),
        "pole_count_after_minimization": len(chosen_poles),
    }


def _resample_bound(
    events: Sequence[Mapping[str, float]], times: Sequence[float], final_time: float
) -> List[Dict[str, float]]:
    ordered = sorted(events, key=lambda row: float(row["t"]))
    result: List[Dict[str, float]] = []
    for target in times:
        if target > final_time + 1e-9:
            continue
        eligible = [row for row in ordered if float(row["t"]) <= target + 1e-9]
        if not eligible:
            continue
        row = eligible[-1]
        result.append({"t": float(target), "bound_scaled": float(row["bound_scaled"])})
    return result


def run_branch(
    modules: Mapping[str, Any],
    *,
    family: str,
    dual: Dual,
    hole: bool,
    strict: bool,
    relaxed: bool,
    max_poles: Optional[int],
    seconds: float,
    workers: int,
    seed: int,
    cap_scaled: Optional[int],
) -> Dict[str, Any]:
    from ortools.sat.python import cp_model
    import ortools

    if seconds <= 0:
        raise ValueError("seconds must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if cap_scaled is None:
        branch_name = "hole" if hole else "nohole"
        branch_caps = dual.analytic_branch_cap_scaled.get(family, {})
        branch_cap = branch_caps.get(branch_name)
        if branch_cap is not None:
            cap_scaled = int(branch_cap)
            cap_source = "dual_analytic_branch_cap"
        else:
            cap_scaled = dual.pi_scaled.get(family)
            cap_source = "dual_pi"
    else:
        cap_source = "explicit"

    overall_start = time.monotonic()
    build_started = overall_start
    handles = build_model(
        modules,
        family=family,
        dual=dual,
        hole=hole,
        strict=strict,
        relaxed=relaxed,
        max_poles=max_poles,
        objective_cap_scaled=cap_scaled,
    )
    build_wall_seconds = time.monotonic() - build_started
    base = {
        "schema_version": 2,
        "research_only": True,
        "family": family,
        "dual": dual.name,
        "scale": dual.scale,
        "mu_scaled": dict(dual.mu_scaled),
        "lambda_scaled": dual.lambda_scaled,
        "pi_scaled": dual.pi_scaled.get(family),
        "bucket_weights_scaled": derive_bucket_weights(dual, modules),
        "hole": hole,
        "strict": strict,
        "relaxed": relaxed,
        "max_poles": max_poles,
        "seconds_limit": seconds,
        "workers": workers,
        "seed": seed,
        "build_wall_seconds": round(build_wall_seconds, 6),
        "objective_cap_scaled": cap_scaled,
        "cap_source": cap_source,
        "runtime": {
            "python": sys.version.split()[0],
            "ortools": ortools.__version__,
            "bundle": str(modules["bundle"]),
        },
    }
    if handles["model"] is None:
        return {
            **base,
            "status": handles["reason"],
            "model_size": None,
            "model_signature_sha256": None,
            "objective_value_scaled": None,
            "raw_objective_bound_scaled": None,
            "certified_objective_bound_scaled": None,
            "epsilon_bound_scaled": None,
            "solve_wall_seconds": 0.0,
            "wall_seconds": round(time.monotonic() - overall_start, 6),
            "bound_events": [],
            "bound_samples": [],
            "incumbent_events": [],
            "final_validation": None,
        }

    model = handles["model"]
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(seconds)
    solver.parameters.num_workers = int(workers)
    solver.parameters.random_seed = int(seed)
    solver.parameters.log_search_progress = False

    start = time.monotonic()
    lock = threading.Lock()
    bound_events: List[Dict[str, Any]] = []
    incumbent_events: List[Dict[str, Any]] = []
    running_certified = math.inf
    if cap_scaled is not None:
        running_certified = float(cap_scaled)
        bound_events.append({
            "t": 0.0,
            "raw_bound_scaled": None,
            "bound_scaled": running_certified,
            "source": cap_source,
        })

    def on_bound(value: float) -> None:
        nonlocal running_certified
        raw = float(value)
        certified = raw if cap_scaled is None else min(raw, float(cap_scaled))
        with lock:
            running_certified = min(running_certified, certified)
            if not bound_events or abs(float(bound_events[-1]["bound_scaled"]) - running_certified) > 1e-9:
                bound_events.append({
                    "t": round(time.monotonic() - start, 6),
                    "raw_bound_scaled": raw,
                    "bound_scaled": running_certified,
                    "source": "cp_sat_best_bound",
                })

    solver.best_bound_callback = on_bound

    class SolutionCallback(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self) -> None:
            counts = {
                bucket: int(self.value(var))
                for bucket, var in handles["bucket_counts"].items()
                if self.value(var)
            }
            with lock:
                incumbent_events.append({
                    "t": round(time.monotonic() - start, 6),
                    "objective_scaled": float(self.objective_value),
                    "credited_bucket_counts": counts,
                })

    status = solver.solve(model, SolutionCallback())
    elapsed = time.monotonic() - start
    status_name = solver.status_name(status)
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    model_valid = status != cp_model.MODEL_INVALID

    raw_bound: Optional[float] = None
    if model_valid:
        raw_bound = float(solver.best_objective_bound)
    certified_bound: Optional[float]
    if raw_bound is None:
        certified_bound = None if cap_scaled is None else float(cap_scaled)
    else:
        certified_bound = raw_bound if cap_scaled is None else min(raw_bound, float(cap_scaled))
    if certified_bound is not None:
        with lock:
            running_certified = min(running_certified, certified_bound)
            certified_bound = running_certified
            if not bound_events or abs(float(bound_events[-1]["bound_scaled"]) - certified_bound) > 1e-9:
                bound_events.append({
                    "t": round(elapsed, 6),
                    "raw_bound_scaled": raw_bound,
                    "bound_scaled": certified_bound,
                    "source": "final",
                })

    objective_value = float(solver.objective_value) if feasible else None
    final_validation = None
    if feasible and not relaxed:
        final_validation = extract_and_evaluate(handles, solver, modules, dual)
        if not final_validation["evaluator_ok"]:
            raise AssertionError(f"bundled evaluator rejected incumbent: {final_validation['evaluator_violations']}")
        if not final_validation["independent_audit_ok"]:
            raise AssertionError(f"independent audit rejected incumbent: {final_validation['independent_audit_issues']}")
        if not final_validation["actual_ge_credited"]:
            raise AssertionError("evaluator objective is below the credited pose-level objective")
        if certified_bound is not None and final_validation["actual_objective_scaled"] > certified_bound + 1e-6:
            raise AssertionError("validated incumbent exceeds certified best bound")

    epsilon = None
    pi = dual.pi_scaled.get(family)
    if certified_bound is not None and pi is not None:
        epsilon = certified_bound - float(pi)

    return {
        **base,
        "status": status_name,
        "model_size": handles["model_size"],
        "model_signature_sha256": handles["model_signature_sha256"],
        "objective_value_scaled": objective_value,
        "objective_value": None if objective_value is None else objective_value / dual.scale,
        "raw_objective_bound_scaled": raw_bound,
        "raw_objective_bound": None if raw_bound is None else raw_bound / dual.scale,
        "certified_objective_bound_scaled": certified_bound,
        "certified_objective_bound": None if certified_bound is None else certified_bound / dual.scale,
        "epsilon_bound_scaled": epsilon,
        "epsilon_bound": None if epsilon is None else epsilon / dual.scale,
        "solve_wall_seconds": round(elapsed, 6),
        "wall_seconds": round(time.monotonic() - overall_start, 6),
        "bound_events": bound_events,
        "bound_samples": _resample_bound(bound_events, DEFAULT_SAMPLE_TIMES, elapsed),
        "incumbent_events": incumbent_events,
        "final_validation": final_validation,
    }


def atomic_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def parse_max_poles(text: str) -> Optional[int]:
    if text.lower() in {"none", "unbounded", "auto"}:
        return None
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("max-poles must be nonnegative or 'none'")
    return value


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--duals", type=Path, required=True)
    parser.add_argument("--dual", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--hole", action="store_true")
    parser.add_argument("--relaxed", action="store_true", help="omit connectivity for a legal packing relaxation")
    parser.add_argument("--loose", action="store_true", help="multi-root connectivity; default is strict single-root")
    parser.add_argument("--max-poles", type=parse_max_poles, default=None)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cap-scaled", type=int, default=None,
                        help="optional legal objective cap for this fixed branch; defaults to dual pi")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    modules = load_modules(args.bundle)
    dual = load_dual(args.duals, args.dual)
    result = run_branch(
        modules,
        family=args.family,
        dual=dual,
        hole=bool(args.hole),
        strict=not args.loose,
        relaxed=bool(args.relaxed),
        max_poles=args.max_poles,
        seconds=float(args.seconds),
        workers=int(args.workers),
        seed=int(args.seed),
        cap_scaled=args.cap_scaled,
    )
    atomic_write(args.out, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
