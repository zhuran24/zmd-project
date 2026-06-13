"""Differential fuzz harness — coordinate master geometry/power (tier ② slice 2).

Hunts two soundness classes mechanically:
  * B-01 class (false CERTIFIED): master accepts a placement whose REAL pose
    footprints overlap, leave the grid, or leave a powered facility uncovered.
  * over-cut class (false INFEASIBLE): master claims INFEASIBLE on a tiny
    instance although brute-force enumeration over the same pose pools finds a
    valid assignment.

The verifier is DELIBERATELY INDEPENDENT of the master's interval/table
encodings: it re-reads each selected pose's occupied_cells straight from the
pool and checks pairwise disjointness / bounds / power coverage with plain set
algebra. Power-coverage criterion mirrors the build_exact_core cover-table
semantics (pole covers a powered pose iff pole.power_coverage_cells intersects
the powered pose's occupied_cells; geometric overlap is excluded separately by
the no-overlap check).

Usage (run from repo root):
    python cc_context/verification/diff_fuzz/master_geometry_diff.py --self-test
    python cc_context/verification/diff_fuzz/master_geometry_diff.py --batch 60 --seed 0
"""
from __future__ import annotations

import argparse
import random
import sys
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ortools.sat.python import cp_model  # noqa: E402

from src.models.master_model import MasterPlacementModel  # noqa: E402

Cell = Tuple[int, int]

EMPTY_IO = {"required_generic_outputs": {}, "required_generic_inputs": {}}


def _cells(pose: Dict[str, Any]) -> Set[Cell]:
    return {(int(c[0]), int(c[1])) for c in pose.get("occupied_cells") or []}


def _coverage(pose: Dict[str, Any]) -> Set[Cell]:
    return {(int(c[0]), int(c[1])) for c in pose.get("power_coverage_cells") or []}


def verify_selected_placement(
    selected: List[Tuple[str, str, Dict[str, Any]]],
    *,
    grid_w: int,
    grid_h: int,
    powered_templates: Set[str],
) -> Tuple[bool, List[str]]:
    """Independent check of a selected placement.

    selected: list of (instance_id, template, pose_dict).
    """
    reasons: List[str] = []
    occupied_by: Dict[Cell, str] = {}
    for instance_id, tpl, pose in selected:
        cells = _cells(pose)
        if not cells:
            reasons.append(f"{instance_id}: empty occupied_cells")
            continue
        for cell in cells:
            x, y = cell
            if not (0 <= x < grid_w and 0 <= y < grid_h):
                reasons.append(f"{instance_id}: cell {cell} outside {grid_w}x{grid_h}")
            prior = occupied_by.get(cell)
            if prior is not None:
                reasons.append(f"overlap at {cell}: {prior} vs {instance_id}")
            occupied_by[cell] = str(instance_id)

    pole_coverages = [
        _coverage(pose) for _iid, tpl, pose in selected if tpl == "power_pole"
    ]
    for instance_id, tpl, pose in selected:
        if tpl not in powered_templates or tpl == "power_pole":
            continue
        cells = _cells(pose)
        if not any(cov & cells for cov in pole_coverages):
            reasons.append(f"{instance_id}: powered but no selected pole coverage touches it")
    return (not reasons), reasons


def brute_force_feasible(
    instance_pools: List[Tuple[str, str, List[Dict[str, Any]]]],
    *,
    grid_w: int,
    grid_h: int,
    powered_templates: Set[str],
    combo_cap: int = 200_000,
) -> Optional[List[Tuple[str, str, Dict[str, Any]]]]:
    """Exhaustively search pose assignments; return a valid one or None.

    instance_pools: list of (instance_id, template, candidate poses).
    Returns None both when infeasible and when the product exceeds combo_cap
    (caller must treat cap-skip as 'unknown', not 'infeasible').
    """
    total = 1
    for _iid, _tpl, poses in instance_pools:
        total *= max(1, len(poses))
        if total > combo_cap:
            return None
    for combo in product(*[poses for _iid, _tpl, poses in instance_pools]):
        selected = [
            (iid, tpl, pose)
            for (iid, tpl, _poses), pose in zip(instance_pools, combo)
        ]
        ok, _reasons = verify_selected_placement(
            selected,
            grid_w=grid_w,
            grid_h=grid_h,
            powered_templates=powered_templates,
        )
        if ok:
            return selected
    return None


def brute_force_capped(
    instance_pools: List[Tuple[str, str, List[Dict[str, Any]]]],
    combo_cap: int = 200_000,
) -> bool:
    total = 1
    for _iid, _tpl, poses in instance_pools:
        total *= max(1, len(poses))
    return total > combo_cap


# --------------------------------------------------------------------------- #
# Instance generator
# --------------------------------------------------------------------------- #
def _rect_poses(
    tpl: str,
    w: int,
    h: int,
    grid_w: int,
    grid_h: int,
    rng: random.Random,
    max_poses: int,
) -> List[Dict[str, Any]]:
    poses: List[Dict[str, Any]] = []
    dims = {(w, h), (h, w)}
    idx = 0
    for pw, ph in sorted(dims):
        for ax in range(0, grid_w - pw + 1):
            for ay in range(0, grid_h - ph + 1):
                poses.append(
                    {
                        "pose_id": f"{tpl}_p{idx}",
                        "anchor": {"x": ax, "y": ay},
                        "occupied_cells": [
                            [cx, cy]
                            for cx in range(ax, ax + pw)
                            for cy in range(ay, ay + ph)
                        ],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                )
                idx += 1
    if len(poses) > max_poses:
        poses = rng.sample(poses, max_poses)
    return poses


def _pole_poses(
    grid_w: int,
    grid_h: int,
    radius: int,
    rng: random.Random,
    max_poses: int,
    *,
    perturb_coverage: bool,
) -> List[Dict[str, Any]]:
    poses: List[Dict[str, Any]] = []
    for idx, (ax, ay) in enumerate(
        (x, y) for x in range(grid_w) for y in range(grid_h)
    ):
        coverage = [
            [cx, cy]
            for cx in range(max(0, ax - radius), min(grid_w - 1, ax + 1 + radius) + 1)
            for cy in range(max(0, ay - radius), min(grid_h - 1, ay + 1 + radius) + 1)
        ]
        if perturb_coverage and len(coverage) > 1:
            coverage = coverage[:-1]  # drop one corner -> forces exact cover-table path
        poses.append(
            {
                "pose_id": f"pole_p{idx}",
                "anchor": {"x": ax, "y": ay},
                "occupied_cells": [[ax, ay]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": coverage,
            }
        )
    if len(poses) > max_poses:
        poses = rng.sample(poses, max_poses)
    return poses


def gen_instance(rng: random.Random) -> Dict[str, Any]:
    # Tight grids on purpose: a healthy share of instances must be INFEASIBLE
    # so the reverse (false-INFEASIBLE) direction actually gets exercised.
    grid_w = rng.randint(3, 5)
    grid_h = rng.randint(3, 4)
    power_mode = rng.random() < 0.5
    wireless_mode = rng.random() < 0.5
    max_poses = rng.randint(4, 8)

    dim_choices = [(1, 3), (2, 3), (1, 2), (2, 2), (1, 4)]
    a_w, a_h = rng.choice(dim_choices)
    a_w = min(a_w, grid_w)
    a_h = min(a_h, grid_h)
    a_count = rng.randint(2, 3)

    templates: Dict[str, Dict[str, Any]] = {
        "blocka": {"dimensions": {"w": a_w, "h": a_h}, "needs_power": False},
    }
    pools: Dict[str, List[Dict[str, Any]]] = {
        "blocka": _rect_poses("blocka", a_w, a_h, grid_w, grid_h, rng, max_poses),
    }
    instances: List[Dict[str, Any]] = [
        {
            "instance_id": f"blocka_{i:03d}",
            "facility_type": "blocka",
            "operation_type": "manufacturing",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for i in range(1, a_count + 1)
    ]
    powered_templates: Set[str] = set()

    if power_mode:
        b_w, b_h = rng.choice([(1, 2), (2, 2), (1, 3)])
        b_w = min(b_w, grid_w)
        b_h = min(b_h, grid_h)
        templates["pressb"] = {"dimensions": {"w": b_w, "h": b_h}, "needs_power": True}
        templates["power_pole"] = {
            "dimensions": {"w": 1, "h": 1},
            "needs_power": False,
            "power_coverage_radius": 1,
        }
        pools["pressb"] = _rect_poses("pressb", b_w, b_h, grid_w, grid_h, rng, max_poses)
        pools["power_pole"] = _pole_poses(
            grid_w,
            grid_h,
            1,
            rng,
            max_poses,
            perturb_coverage=bool(rng.random() < 0.5),
        )
        instances.append(
            {
                "instance_id": "pressb_001",
                "facility_type": "pressb",
                "operation_type": "manufacturing",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        )
        instances.append(
            {
                "instance_id": "pole_001",
                "facility_type": "power_pole",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        )
        powered_templates.add("pressb")

    if wireless_mode:
        # Wireless protocol-box form under the post-F-01 geometry: a square
        # omni pose set — one pose per anchor (no rotated duplicate), zero
        # physical port cells. Mirrors gen_protocol_storage_box() shape-wise;
        # ports are irrelevant to the master slice, so what this adds is the
        # square no-port template mixed into tight no-overlap/ghost packing.
        side = 3 if (grid_w >= 3 and grid_h >= 3 and rng.random() < 0.7) else 2
        side = min(side, grid_w, grid_h)
        templates["wbox"] = {"dimensions": {"w": side, "h": side}, "needs_power": False}
        pools["wbox"] = _rect_poses("wbox", side, side, grid_w, grid_h, rng, max_poses)
        for i in range(1, rng.randint(1, 2) + 1):
            instances.append(
                {
                    "instance_id": f"wbox_{i:03d}",
                    "facility_type": "wbox",
                    "operation_type": "wireless_sink",
                    "is_mandatory": True,
                    "bound_type": "exact",
                }
            )

    rules = {
        "globals": {"grid": {"width": grid_w, "height": grid_h}},
        "facility_templates": templates,
    }
    # ~40% of cases also demand a small empty ghost rectangle (the certified
    # max-empty-rect objective). The master must keep gw*gh cells facility-free;
    # the forward verifier checks the chosen rect is genuinely empty.
    ghost_rect = None
    if rng.random() < 0.4:
        ghost_rect = (rng.randint(1, min(2, grid_w)), rng.randint(1, min(2, grid_h)))
    return {
        "grid_w": grid_w,
        "grid_h": grid_h,
        "power_mode": power_mode,
        "wireless_mode": wireless_mode,
        "rules": rules,
        "pools": pools,
        "instances": instances,
        "powered_templates": powered_templates,
        "ghost_rect": ghost_rect,
    }


def verify_ghost_emptiness(
    ghost_pick: Optional[Dict[str, Any]],
    ghost_rect: Optional[Tuple[int, int]],
    selected: List[Tuple[str, str, Dict[str, Any]]],
    *,
    grid_w: int,
    grid_h: int,
) -> Tuple[bool, List[str]]:
    """The chosen ghost rectangle (the certified MAX-EMPTY-RECT, the project's
    whole objective) must be a genuine empty rectangle: in-grid and disjoint from
    every selected facility's occupied cells. A facility overlapping the 'empty'
    rect = false CERTIFIED of a non-empty empty-rectangle. Independent: just
    expand anchor+dims and intersect with the occupied set."""
    reasons: List[str] = []
    if ghost_rect is None:
        return True, reasons
    if ghost_pick is None:
        return False, ["ghost_rect set but FEASIBLE solution has no ghost_pick"]
    gw, gh = int(ghost_rect[0]), int(ghost_rect[1])
    ax, ay = int(ghost_pick["anchor"]["x"]), int(ghost_pick["anchor"]["y"])
    ghost_cells = {(ax + dx, ay + dy) for dx in range(gw) for dy in range(gh)}
    for (x, y) in ghost_cells:
        if not (0 <= x < grid_w and 0 <= y < grid_h):
            reasons.append(f"ghost cell {(x, y)} outside {grid_w}x{grid_h}")
    occupied: Set[Cell] = set()
    for _iid, _tpl, pose in selected:
        occupied |= _cells(pose)
    overlap = ghost_cells & occupied
    if overlap:
        reasons.append(f"ghost rect overlaps facility cells {sorted(overlap)[:4]} (non-empty 'empty' rect)")
    return (not reasons), reasons


def run_master(case: Dict[str, Any]) -> Tuple[str, List[Tuple[str, str, Dict[str, Any]]], Optional[Dict[str, Any]]]:
    core = MasterPlacementModel.build_exact_core(
        case["instances"],
        case["pools"],
        case["rules"],
        generic_io_requirements=EMPTY_IO,
        skip_power_coverage=not case["power_mode"],
        enable_symmetry_breaking=False,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=case.get("ghost_rect"))
    status = overlay.solve(time_limit_seconds=10.0)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = overlay.extract_solution()
        selected: List[Tuple[str, str, Dict[str, Any]]] = []
        ghost_pick: Optional[Dict[str, Any]] = None
        for solution_id, entry in solution.items():
            if not isinstance(entry, dict):
                continue
            if solution_id == "ghost_pick":
                ghost_pick = entry
                continue
            tpl = str(entry["facility_type"])
            pose = case["pools"][tpl][int(entry["pose_idx"])]
            selected.append((str(solution_id), tpl, pose))
        return "FEASIBLE", selected, ghost_pick
    if status == cp_model.INFEASIBLE:
        return "INFEASIBLE", [], None
    return "UNKNOWN", [], None


def _instance_pools(case: Dict[str, Any]) -> List[Tuple[str, str, List[Dict[str, Any]]]]:
    return [
        (str(inst["instance_id"]), str(inst["facility_type"]), case["pools"][str(inst["facility_type"])])
        for inst in case["instances"]
    ]


def _pin_case(case: Dict[str, Any], witness: List[Tuple[str, str, Dict[str, Any]]]) -> Dict[str, Any]:
    used_by_tpl: Dict[str, Set[str]] = {}
    for _iid, tpl, pose in witness:
        used_by_tpl.setdefault(tpl, set()).add(str(pose["pose_id"]))
    pinned = dict(case)
    pinned["pools"] = {
        tpl: [p for p in poses if str(p["pose_id"]) in used_by_tpl.get(tpl, set())]
        for tpl, poses in case["pools"].items()
    }
    return pinned


# --------------------------------------------------------------------------- #
# Self-test (verifier only, no solver)
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    def pose(cells: List[List[int]], coverage: Optional[List[List[int]]] = None) -> Dict[str, Any]:
        return {
            "pose_id": "t",
            "anchor": {"x": cells[0][0], "y": cells[0][1]},
            "occupied_cells": cells,
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": coverage,
        }

    # 1. disjoint placement passes
    ok, reasons = verify_selected_placement(
        [
            ("a", "blocka", pose([[0, 0], [0, 1]])),
            ("b", "blocka", pose([[2, 0], [2, 1]])),
        ],
        grid_w=4,
        grid_h=4,
        powered_templates=set(),
    )
    print(f"[self-test] disjoint ok={ok} reasons={reasons}")
    if not ok:
        return 1

    # 2. B-01 shape: two vertical 4x6 footprints overlapping must be flagged
    def vfoot(ay: int) -> List[List[int]]:
        return [[x, y] for x in range(4) for y in range(ay, ay + 6)]

    ok2, reasons2 = verify_selected_placement(
        [("r1", "rot", pose(vfoot(0))), ("r2", "rot", pose(vfoot(4)))],
        grid_w=10,
        grid_h=10,
        powered_templates=set(),
    )
    print(f"[self-test] B-01 overlap ok={ok2} flagged={len(reasons2)}")
    if ok2:
        return 1

    # 3. powered without coverage flagged; with touching coverage passes
    powered = pose([[1, 1], [1, 2]])
    pole_far = pose([[3, 3]], coverage=[[3, 2], [3, 3]])
    pole_near = pose([[0, 0]], coverage=[[0, 1], [1, 1]])
    ok3, _ = verify_selected_placement(
        [("p", "pressb", powered), ("pole", "power_pole", pole_far)],
        grid_w=4,
        grid_h=4,
        powered_templates={"pressb"},
    )
    ok4, reasons4 = verify_selected_placement(
        [("p", "pressb", powered), ("pole", "power_pole", pole_near)],
        grid_w=4,
        grid_h=4,
        powered_templates={"pressb"},
    )
    print(f"[self-test] uncovered flagged={not ok3}, covered ok={ok4} ({reasons4})")
    if ok3 or not ok4:
        return 1

    # 4. brute force finds the unique non-overlapping pair on a tight strip
    pool = [pose([[0, 0], [1, 0]]), pose([[1, 0], [2, 0]]), pose([[2, 0], [3, 0]])]
    found = brute_force_feasible(
        [("a", "blocka", pool), ("b", "blocka", pool)],
        grid_w=4,
        grid_h=1,
        powered_templates=set(),
    )
    print(f"[self-test] brute-force found={found is not None}")
    if found is None:
        return 1

    # 5. wireless-box form: square no-port pose passes standalone; an overlap
    # with another footprint must still be flagged (ports being absent must not
    # weaken the geometry check).
    wbox = pose([[x, y] for x in range(3) for y in range(3)])
    ok5, _ = verify_selected_placement(
        [("w", "wbox", wbox)], grid_w=4, grid_h=4, powered_templates=set()
    )
    ok6, reasons6 = verify_selected_placement(
        [("w", "wbox", wbox), ("a", "blocka", pose([[2, 2], [3, 2]]))],
        grid_w=4,
        grid_h=4,
        powered_templates=set(),
    )
    print(f"[self-test] wbox standalone ok={ok5}, overlap flagged={not ok6} ({len(reasons6)})")
    if not ok5 or ok6:
        return 1

    # 6. ghost-rect emptiness: the chosen empty rectangle must be facility-free.
    gp = {"anchor": {"x": 5, "y": 5}}
    g_ok, _ = verify_ghost_emptiness(gp, (2, 2), [("a", "blocka", pose([[0, 0], [1, 0]]))], grid_w=10, grid_h=10)
    g_bad, _ = verify_ghost_emptiness(gp, (2, 2), [("b", "blocka", pose([[5, 5], [6, 5]]))], grid_w=10, grid_h=10)
    g_none, _ = verify_ghost_emptiness(None, (2, 2), [], grid_w=10, grid_h=10)
    print(f"[self-test] ghost: clean ok={g_ok}, overlap flagged={not g_bad}, no-pick flagged={not g_none}")
    if not g_ok or g_bad or g_none:
        return 1

    print("[self-test] PASS")
    return 0


def _batch(n: int, seed: int) -> int:
    rng = random.Random(seed)
    feasible = infeasible = unknown = 0
    wireless_cases = 0
    forward_mismatches: List[str] = []
    reverse_mismatches: List[str] = []
    errors: List[str] = []
    bf_skipped = 0
    reverse_filtered = 0
    ghost_cases = ghost_feasible = 0
    for i in range(n):
        case = gen_instance(rng)
        if case.get("wireless_mode"):
            wireless_cases += 1
        if case.get("ghost_rect"):
            ghost_cases += 1
        try:
            status, selected, ghost_pick = run_master(case)
            if status == "FEASIBLE":
                feasible += 1
                ok, reasons = verify_selected_placement(
                    selected,
                    grid_w=case["grid_w"],
                    grid_h=case["grid_h"],
                    powered_templates=case["powered_templates"],
                )
                mandatory_ids = {str(inst["instance_id"]) for inst in case["instances"]}
                selected_ids = {iid for iid, _tpl, _pose in selected}
                if not mandatory_ids <= selected_ids:
                    ok = False
                    reasons.append(f"missing mandatory ids: {sorted(mandatory_ids - selected_ids)}")
                if case.get("ghost_rect"):
                    ghost_feasible += 1
                gok, greasons = verify_ghost_emptiness(
                    ghost_pick, case.get("ghost_rect"), selected,
                    grid_w=case["grid_w"], grid_h=case["grid_h"],
                )
                if not gok:
                    ok = False
                    reasons.extend(greasons)
                if not ok:
                    forward_mismatches.append(f"iter {i}: {reasons[:4]}")
            elif status == "INFEASIBLE":
                infeasible += 1
                pools_by_instance = _instance_pools(case)
                if brute_force_capped(pools_by_instance):
                    bf_skipped += 1
                else:
                    witness = brute_force_feasible(
                        pools_by_instance,
                        grid_w=case["grid_w"],
                        grid_h=case["grid_h"],
                        powered_templates=case["powered_templates"],
                    )
                    if witness is not None:
                        # The independent verifier omits ghost-rectangle
                        # admissibility (re-deriving it == reimplementing the
                        # master), so a raw witness is only a SUSPICION — e.g. a
                        # layout that fills the whole grid passes the verifier
                        # but the master rightly rejects it (no empty rect).
                        # Adjudicate with the master itself: pin pools to the
                        # witness poses and re-solve. Only pinned-FEASIBLE proves
                        # the full pool was genuinely over-cut.
                        pinned_status, _, _ = run_master(_pin_case(case, witness))
                        if pinned_status == "FEASIBLE":
                            reverse_mismatches.append(
                                f"iter {i}: master INFEASIBLE on full pool but FEASIBLE when "
                                f"pinned to brute witness {[(iid, pose['pose_id']) for iid, _tpl, pose in witness]}"
                            )
                        else:
                            reverse_filtered += 1
            else:
                unknown += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"iter {i}: EXC {type(exc).__name__}: {exc}")
        if (i + 1) % 10 == 0:
            print(
                f"  ...{i + 1}/{n} feasible={feasible} infeasible={infeasible} "
                f"fwd_mm={len(forward_mismatches)} rev_mm={len(reverse_mismatches)} err={len(errors)}"
            )
    print("=" * 60)
    print(
        f"batch={n} seed={seed}: feasible={feasible} infeasible={infeasible} unknown={unknown} "
        f"wireless_cases={wireless_cases} ghost_cases={ghost_cases} ghost_feasible={ghost_feasible} "
        f"bf_skipped={bf_skipped} reverse_filtered={reverse_filtered} "
        f"forward_mismatches={len(forward_mismatches)} "
        f"reverse_mismatches={len(reverse_mismatches)} errors={len(errors)}"
    )
    for line in (forward_mismatches + reverse_mismatches + errors)[:20]:
        print("  MISMATCH:", line)
    return 1 if (forward_mismatches or reverse_mismatches or errors) else 0


def _inspect(seed: int, iteration: int) -> int:
    rng = random.Random(seed)
    case = None
    for _ in range(iteration + 1):
        case = gen_instance(rng)
    assert case is not None
    print(f"grid {case['grid_w']}x{case['grid_h']} power_mode={case['power_mode']}")
    print("templates:", {k: v["dimensions"] for k, v in case["rules"]["facility_templates"].items()})
    print("instances:", [(i["instance_id"], i["facility_type"]) for i in case["instances"]])
    print("pool sizes:", {k: len(v) for k, v in case["pools"].items()})

    status, selected, _ghost_pick = run_master(case)
    print(f"master status = {status}")
    if status != "INFEASIBLE":
        print("not the INFEASIBLE case; nothing to inspect")
        return 0

    pools_by_instance = _instance_pools(case)
    witness = brute_force_feasible(
        pools_by_instance,
        grid_w=case["grid_w"],
        grid_h=case["grid_h"],
        powered_templates=case["powered_templates"],
    )
    if witness is None:
        print("brute force found no witness -> master INFEASIBLE agrees; no mismatch")
        return 0
    print("brute-force witness:")
    for iid, tpl, pose in witness:
        print(f"  {iid} [{tpl}] {pose['pose_id']} occ={pose['occupied_cells']} cov={pose.get('power_coverage_cells')}")

    # Pin: shrink each template pool to only the witness-used poses, re-solve.
    used_by_tpl: Dict[str, Set[str]] = {}
    for _iid, tpl, pose in witness:
        used_by_tpl.setdefault(tpl, set()).add(str(pose["pose_id"]))
    pinned_pools = {
        tpl: [p for p in poses if str(p["pose_id"]) in used_by_tpl.get(tpl, set())]
        for tpl, poses in case["pools"].items()
    }
    pinned_case = dict(case)
    pinned_case["pools"] = pinned_pools
    pinned_status, _, _ = run_master(pinned_case)
    print(f"pinned-pool master status = {pinned_status}")
    print("=" * 50)
    if pinned_status in ("FEASIBLE",):
        print("VERDICT: master accepts the witness when pools are pinned, but rejected it")
        print("         in the full pool => candidate over-cut / false-INFEASIBLE (REAL bug).")
        return 2
    print("VERDICT: master rejects the witness even when pinned => the witness violates a")
    print("         real master constraint the independent verifier does NOT encode")
    print("         (verifier-incomplete; reverse direction false alarm, NOT a master bug).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--inspect", type=int, default=-1, help="inspect the iter-th reverse case for --seed")
    args = ap.parse_args()
    if args.inspect >= 0:
        return _inspect(args.seed, args.inspect)
    rc = 0
    if args.self_test:
        rc |= _self_test()
    if args.batch:
        rc |= _batch(args.batch, args.seed)
    if not args.self_test and not args.batch:
        rc |= _self_test()
        rc |= _batch(40, 0)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
