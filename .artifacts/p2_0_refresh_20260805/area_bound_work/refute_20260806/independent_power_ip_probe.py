#!/usr/bin/env python3
"""Independent audit of OB4's single-pole packing bound.

The repository is read-only.  This probe lives in the requested scratchpad and:

* rebuilds candidates from the production four-inequality bbox predicate;
* proves by exhaustive enumeration that every legal 70x70 pole/rectangle pair
  normalizes into the OB4 relaxation candidate universe;
* solves the set-packing problem with OR-Tools' SCIP MIP backend (not CP-SAT);
* rechecks the archived CP-SAT witness against cells, dimensions, inventory,
  the four inequalities, the 2x2 pole body, and a realizable interior anchor.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from ortools.linear_solver import pywraplp


ROOT = Path("/home/zhuran24/zmd-pj")
CANON = ROOT / "rules/canonical_rules.json"
INSTANCES = ROOT / "data/preprocessed/mandatory_exact_instances.json"
RECEIPT = (
    ROOT
    / ".artifacts/p2_0_refresh_20260805/area_bound_work/ob4_pole_lower_bound_receipt.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells(x: int, y: int, w: int, h: int) -> frozenset[tuple[int, int]]:
    return frozenset((x + dx, y + dy) for dx in range(w) for dy in range(h))


def bbox_intersects_coverage(
    x: int,
    y: int,
    w: int,
    h: int,
    pole_x: int,
    pole_y: int,
    radius: int,
) -> bool:
    """Literal transcription of exact_coordinate_master.py:6184-6195."""
    return (
        x <= pole_x + 2 + radius - 1
        and pole_x - radius <= x + w - 1
        and y <= pole_y + 2 + radius - 1
        and pole_y - radius <= y + h - 1
    )


def normalized_candidates(
    shapes: list[tuple[str, int, int]],
    width: int,
    height: int,
    radius: int,
    pole_w: int,
    pole_h: int,
) -> list[tuple[str, int, int, int, int, frozenset[tuple[int, int]]]]:
    pole_x = radius
    pole_y = radius
    pole_body = cells(pole_x, pole_y, pole_w, pole_h)
    coverage = cells(0, 0, width, height)
    result = []
    for template, w, h in shapes:
        for x in range(1 - w, width):
            for y in range(1 - h, height):
                body = cells(x, y, w, h)
                by_cells = bool(body & coverage)
                by_inequalities = bbox_intersects_coverage(
                    x, y, w, h, pole_x, pole_y, radius
                )
                assert by_cells == by_inequalities
                assert by_cells  # guaranteed by the candidate ranges
                if body & pole_body:
                    continue
                result.append((template, w, h, x, y, body))
    return result


def solve_scip(
    cands: list[tuple[str, int, int, int, int, frozenset[tuple[int, int]]]],
    inventory: Counter[str] | None,
) -> tuple[int, float, Counter[tuple[str, int, int]], list[int]]:
    solver = pywraplp.Solver.CreateSolver("SCIP")
    assert solver is not None
    choice = [solver.BoolVar(f"x_{i}") for i in range(len(cands))]
    by_cell: dict[tuple[int, int], list[int]] = defaultdict(list)
    by_template: dict[str, list[int]] = defaultdict(list)
    for i, (template, _w, _h, _x, _y, body) in enumerate(cands):
        by_template[template].append(i)
        for cell in body:
            by_cell[cell].append(i)
    for indexes in by_cell.values():
        solver.Add(sum(choice[i] for i in indexes) <= 1)
    if inventory is not None:
        for template, indexes in by_template.items():
            solver.Add(sum(choice[i] for i in indexes) <= inventory[template])
    objective = solver.Objective()
    for i, (_template, w, h, _x, _y, _body) in enumerate(cands):
        objective.SetCoefficient(choice[i], w * h)
    objective.SetMaximization()
    status = solver.Solve()
    assert status == pywraplp.Solver.OPTIMAL, status
    chosen = [i for i, var in enumerate(choice) if var.solution_value() > 0.5]
    tally = Counter((cands[i][0], cands[i][1], cands[i][2]) for i in chosen)
    return int(round(objective.Value())), objective.BestBound(), tally, chosen


def main() -> None:
    canon = json.loads(CANON.read_text())
    instances = json.loads(INSTANCES.read_text())
    receipt = json.loads(RECEIPT.read_text())
    stencil = canon["semantics"]["power_coverage_stencil"]
    templates = canon["facility_templates"]
    grid_w = int(canon["globals"]["grid"]["width"])
    grid_h = int(canon["globals"]["grid"]["height"])
    width = int(stencil["coverage_shape"]["width"])
    height = int(stencil["coverage_shape"]["height"])
    radius = int(stencil["power_coverage_radius"])
    pole_w = int(stencil["anchor_footprint"]["w"])
    pole_h = int(stencil["anchor_footprint"]["h"])
    assert (grid_w, grid_h, width, height, radius, pole_w, pole_h) == (
        70,
        70,
        12,
        12,
        5,
        2,
        2,
    )

    inventory: Counter[str] = Counter(
        str(instance["facility_type"]) for instance in instances
    )
    mandatory_powered = sorted(
        template
        for template in inventory
        if bool(templates[template]["needs_power"])
    )
    assert mandatory_powered == [
        "manufacturing_3x3",
        "manufacturing_5x5",
        "manufacturing_6x4",
    ]
    shapes: list[tuple[str, int, int]] = []
    for template in mandatory_powered:
        payload = templates[template]
        w = int(payload["dimensions"]["w"])
        h = int(payload["dimensions"]["h"])
        orientations = {(w, h)}
        if bool(payload["rotatable"]):
            orientations.add((h, w))
        for oriented_w, oriented_h in sorted(orientations):
            shapes.append((template, oriented_w, oriented_h))

    cands = normalized_candidates(shapes, width, height, radius, pole_w, pole_h)
    candidate_keys = {
        (template, w, h, x, y) for template, w, h, x, y, _body in cands
    }
    assert len(candidate_keys) == len(cands)
    by_shape = Counter((template, w, h) for template, w, h, _x, _y, _body in cands)
    assert by_shape == Counter(
        {
            ("manufacturing_3x3", 3, 3): 180,
            ("manufacturing_5x5", 5, 5): 220,
            ("manufacturing_6x4", 4, 6): 220,
            ("manufacturing_6x4", 6, 4): 220,
        }
    )
    assert len(cands) == receipt["K_candidates"] == 840

    # Exhaust every legal 2x2 pole anchor and every in-grid machine bbox that
    # intersects its (possibly clipped) coverage.  Translation by the nominal
    # un-clipped window origin must land in the OB4 universe.
    pole_anchor_count = 0
    actual_pair_count = 0
    max_actual_candidates = 0
    anchors_reaching_full_universe = 0
    for pole_x in range(grid_w - pole_w + 1):
        for pole_y in range(grid_h - pole_h + 1):
            pole_anchor_count += 1
            pole_body = cells(pole_x, pole_y, pole_w, pole_h)
            local_count = 0
            for template, w, h in shapes:
                x_lo = max(0, pole_x - radius - (w - 1))
                x_hi = min(grid_w - w, pole_x + 2 + radius - 1)
                y_lo = max(0, pole_y - radius - (h - 1))
                y_hi = min(grid_h - h, pole_y + 2 + radius - 1)
                for x in range(x_lo, x_hi + 1):
                    for y in range(y_lo, y_hi + 1):
                        if not bbox_intersects_coverage(
                            x, y, w, h, pole_x, pole_y, radius
                        ):
                            continue
                        body = cells(x, y, w, h)
                        if body & pole_body:
                            continue
                        normalized = (
                            template,
                            w,
                            h,
                            x - (pole_x - radius),
                            y - (pole_y - radius),
                        )
                        assert normalized in candidate_keys, (
                            pole_x,
                            pole_y,
                            normalized,
                        )
                        local_count += 1
            actual_pair_count += local_count
            max_actual_candidates = max(max_actual_candidates, local_count)
            if local_count == len(cands):
                anchors_reaching_full_universe += 1
    assert pole_anchor_count == 69 * 69 == 4761
    assert max_actual_candidates == len(cands)
    assert anchors_reaching_full_universe > 0

    unconstrained_k, unconstrained_bound, unconstrained_tally, _ = solve_scip(
        cands, inventory=None
    )
    inventory_k, inventory_bound, inventory_tally, _ = solve_scip(
        cands, inventory=inventory
    )
    assert unconstrained_k == unconstrained_bound == 396
    assert inventory_k == inventory_bound == 396
    assert unconstrained_k == receipt["K_single_pole_max_covered_body_cells"]

    # Independent check of the archived CP-SAT witness, then embed it at an
    # interior production anchor to show the un-clipped relaxation is realizable.
    archived = receipt["optimal_packing_witness"]
    pole_body = cells(radius, radius, pole_w, pole_h)
    coverage = cells(0, 0, width, height)
    used: set[tuple[int, int]] = set()
    witness_counts: Counter[str] = Counter()
    witness_area = 0
    for raw in archived:
        template = str(raw["template"])
        w, h, x, y = (int(raw[key]) for key in ("w", "h", "x", "y"))
        assert (template, w, h, x, y) in candidate_keys
        assert (template, w, h) in shapes
        body = cells(x, y, w, h)
        assert body & coverage
        assert not (body & pole_body)
        assert not (body & used)
        assert bbox_intersects_coverage(x, y, w, h, radius, radius, radius)
        used.update(body)
        witness_counts[template] += 1
        witness_area += len(body)
    assert all(witness_counts[t] <= inventory[t] for t in witness_counts)
    assert witness_area == unconstrained_k == 396

    production_anchor = (20, 20)
    origin = (production_anchor[0] - radius, production_anchor[1] - radius)
    actual_used: set[tuple[int, int]] = set()
    actual_pole = cells(*production_anchor, pole_w, pole_h)
    for raw in archived:
        w, h = int(raw["w"]), int(raw["h"])
        x, y = origin[0] + int(raw["x"]), origin[1] + int(raw["y"])
        body = cells(x, y, w, h)
        assert all(0 <= cx < grid_w and 0 <= cy < grid_h for cx, cy in body)
        assert not (body & actual_pole)
        assert not (body & actual_used)
        assert bbox_intersects_coverage(
            x, y, w, h, production_anchor[0], production_anchor[1], radius
        )
        actual_used.update(body)

    powered_body = sum(
        inventory[template]
        * int(templates[template]["dimensions"]["w"])
        * int(templates[template]["dimensions"]["h"])
        for template in mandatory_powered
    )
    assert powered_body == receipt["powered_body_cells"] == 3325
    assert math.ceil(powered_body / unconstrained_k) == receipt["P_min"] == 9

    audit_receipt = {
        "input_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (CANON, INSTANCES, RECEIPT)
        },
        "mandatory_powered": [
            {
                "template": template,
                "count": inventory[template],
                "dimensions": templates[template]["dimensions"],
                "rotatable": templates[template]["rotatable"],
            }
            for template in mandatory_powered
        ],
        "candidate_by_shape": {
            f"{template}:{w}x{h}": count
            for (template, w, h), count in sorted(by_shape.items())
        },
        "candidate_total": len(cands),
        "all_anchor_subset_check": {
            "anchors": pole_anchor_count,
            "actual_pairs": actual_pair_count,
            "max_actual_candidates": max_actual_candidates,
            "anchors_reaching_full_universe": anchors_reaching_full_universe,
        },
        "scip_unconstrained": {
            "status": "OPTIMAL",
            "objective": unconstrained_k,
            "best_bound": unconstrained_bound,
            "tally": {
                f"{template}:{w}x{h}": count
                for (template, w, h), count in sorted(unconstrained_tally.items())
            },
        },
        "scip_inventory_capped": {
            "status": "OPTIMAL",
            "objective": inventory_k,
            "best_bound": inventory_bound,
            "tally": {
                f"{template}:{w}x{h}": count
                for (template, w, h), count in sorted(inventory_tally.items())
            },
        },
        "archived_witness": {
            "area": witness_area,
            "counts": dict(sorted(witness_counts.items())),
            "realizable_interior_anchor": list(production_anchor),
        },
        "powered_body": powered_body,
        "K": unconstrained_k,
        "P_min": math.ceil(powered_body / unconstrained_k),
    }
    audit_receipt_path = Path(__file__).with_name(
        "independent_power_ip_probe_receipt.json"
    )
    audit_receipt_path.write_text(
        json.dumps(audit_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )

    print("inputs_sha256", {str(p.relative_to(ROOT)): sha256(p) for p in (CANON, INSTANCES, RECEIPT)})
    print("mandatory_powered", [(t, inventory[t], templates[t]["dimensions"], templates[t]["rotatable"]) for t in mandatory_powered])
    print("candidate_by_shape", dict(sorted(by_shape.items())))
    print("candidate_total", len(cands))
    print(
        "all_anchor_subset_check",
        {
            "anchors": pole_anchor_count,
            "actual_pairs": actual_pair_count,
            "max_actual_candidates": max_actual_candidates,
            "anchors_reaching_full_universe": anchors_reaching_full_universe,
        },
    )
    print("scip_unconstrained", {"objective": unconstrained_k, "best_bound": unconstrained_bound, "tally": dict(unconstrained_tally)})
    print("scip_inventory_capped", {"objective": inventory_k, "best_bound": inventory_bound, "tally": dict(inventory_tally)})
    print("archived_witness", {"area": witness_area, "counts": dict(witness_counts), "interior_anchor": production_anchor})
    print("powered_body_and_pmin", {"powered_body": powered_body, "K": unconstrained_k, "P_min": math.ceil(powered_body / unconstrained_k)})
    print("audit_receipt", audit_receipt_path)


if __name__ == "__main__":
    main()
