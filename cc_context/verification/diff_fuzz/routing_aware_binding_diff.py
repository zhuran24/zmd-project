"""Differential fuzz — routing-aware binding (RAB-SEP) (tier ② slice 4).

Covers the `PortBindingModel` path with `routing_context != None` (the RAB-SEP
front-blocked binding-pattern pruning), which the slice-3 binding oracle
explicitly left out, AND the clear-deficit cut certificates it emits — the most
tractable slice of cut-soundness, since these certs are exposed via the public
`extract_routing_aware_certificates()`.

Two soundness directions:
  * filter soundness (false-INFEASIBLE if OVER-pruned): a raw pose-level binding
    pattern must be pruned iff some routing-visible port has an UNUSABLE front
    (out-of-grid or occupied by another facility). If the model prunes a pattern
    whose fronts are all usable, the owner can wrongly lose its whole domain ->
    false INFEASIBLE -> the master loses a legal placement.
  * cut-cert soundness (unsound nogood removes real master solutions): each
    emitted certificate forbids (owner_pose, blocker_poses) from coexisting. It
    is only valid if those blockers, ALONE, genuinely empty the owner's binding
    domain. If some owner pattern survives with only the cert's blockers present,
    the nogood forbids a feasible combination -> removes a true solution.

INDEPENDENCE: the verifier re-derives port-front geometry itself
(front = port + dir-delta; usable = in-grid and not occupied) and reuses the
slice-3 independent pose-level binding enumeration. It never imports the SUT's
`port_front_status` / `_filter_pose_binding_domain` judgment logic.
`build_routing_binding_context` is used only to CONSTRUCT the model's input
(like RoutingGrid), not as an oracle.

Scope note: req_in is kept empty so routing_free_sink_commodities = {} (every
port is routing-visible). The routing-free-output nuance (a wireless final
commodity's output port is NOT a routing terminal, so its blocked front must
NOT prune) is a documented sub-gap, not yet fuzzed here.

Usage (repo root):
    python cc_context/verification/diff_fuzz/routing_aware_binding_diff.py --self-test
    python cc_context/verification/diff_fuzz/routing_aware_binding_diff.py --batch 120 --seed 0
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from binding_model_diff import _canon_model_pattern, independent_binding_domain  # noqa: E402
from src.models.binding_subproblem import PortBindingModel  # noqa: E402
from src.models.routing_binding_context import build_routing_binding_context  # noqa: E402

# Must match src/models/routing_binding_context._DIR_DELTA exactly (re-derived,
# not imported — this is the geometry under test on the SUT side).
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
GRID = 70


def _front(x: int, y: int, d: str) -> Tuple[int, int]:
    dx, dy = DIR_DELTA[d]
    return (x + dx, y + dy)


def _pattern_front_free(
    atoms: frozenset,
    *,
    routing_free: Set[str],
    occupied: Set[Tuple[int, int]],
    gw: int = GRID,
    gh: int = GRID,
) -> bool:
    """A pattern survives RAB filtering iff every routing-visible port has an
    in-grid, free front. Output ports carrying a routing-free commodity are not
    routing terminals and are skipped."""
    for (side, commodity, x, y, d) in atoms:
        if side == "out" and commodity in routing_free:
            continue
        fx, fy = _front(x, y, d)
        if not (0 <= fx < gw and 0 <= fy < gh):
            return False
        if (fx, fy) in occupied:
            return False
    return True


def _independent_filtered_domain(
    raw_domain: Set[frozenset],
    *,
    routing_free: Set[str],
    occupied: Set[Tuple[int, int]],
) -> Set[frozenset]:
    return {p for p in raw_domain if _pattern_front_free(p, routing_free=routing_free, occupied=occupied)}


# --------------------------------------------------------------------------- #
# Verifier (pure over case data + model outputs)
# --------------------------------------------------------------------------- #
def verify_rab(
    case: Dict[str, Any],
    *,
    status: str,
    binding_domains: Dict[str, List[Dict[str, Any]]],
    certs: List[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    owner = case["owner_id"]
    spec = case["owner_slots"]
    in_cells = case["owner_in_cells"]
    out_cells = case["owner_out_cells"]
    routing_free: Set[str] = set()  # req_in empty by construction
    raw = independent_binding_domain(spec["input_slots"], spec["output_slots"], in_cells, out_cells) or set()

    # --- (A) filter soundness: model post-filter domain == independent filter ---
    full_occ = case["blocker_cells"]  # owner body excluded (self never blocks own front)
    mine = _independent_filtered_domain(raw, routing_free=routing_free, occupied=full_occ)
    model_list = binding_domains.get(owner, [])
    model_set = {_canon_model_pattern(p) for p in model_list}
    if model_set != mine:
        over = model_set - mine   # model kept a pattern an independent filter would prune
        under = mine - model_set  # model PRUNED a pattern that should survive (false-INFEASIBLE risk)
        reasons.append(
            f"[RAB-FILTER] {owner}: post-filter domain mismatch "
            f"over_kept={len(over)} over_pruned={len(under)} (model {len(model_set)} vs independent {len(mine)})"
        )

    # status cross-check: empty independent domain <=> model should be INFEASIBLE.
    if not mine and status == "FEASIBLE":
        reasons.append(f"[RAB-FEAS] independent filter empties {owner} but model FEASIBLE")
    if mine and status == "INFEASIBLE":
        reasons.append(f"[RAB-FEAS] independent filter leaves {len(mine)} pattern(s) for {owner} but model INFEASIBLE")

    # --- (B) cut-cert soundness: blockers must, ALONE, empty the owner domain ---
    for cert in certs:
        if str(cert.get("owner_instance_id")) != owner:
            continue
        occ_cert: Set[Tuple[int, int]] = set()
        for bid in cert.get("blocker_instance_ids", []):
            occ_cert |= case["cells_by_instance"].get(str(bid), set())
        survivors = _independent_filtered_domain(raw, routing_free=routing_free, occupied=occ_cert)
        if survivors:
            reasons.append(
                f"[RAB-CERT] unsound cert for {owner}: blockers {cert.get('blocker_instance_ids')} leave "
                f"{len(survivors)} usable pattern(s) -> nogood forbids a feasible (owner,blockers) combo"
            )
    return (not reasons), reasons


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #
def _load_owner_profiles() -> List[Dict[str, Any]]:
    from binding_model_diff import _FIXED_PROFILES
    # owners with >=1 routing-visible port and small slot counts (tractable layout)
    return [p for p in _FIXED_PROFILES
            if 1 <= sum(p["input_slots"].values()) + sum(p["output_slots"].values()) <= 4]


_OWNER_PROFILES = _load_owner_profiles()


def gen_instance(rng: random.Random) -> Dict[str, Any]:
    prof = rng.choice(_OWNER_PROFILES)
    in_need = sum(prof["input_slots"].values())
    out_need = sum(prof["output_slots"].values())
    bx, by = rng.randint(20, 40), rng.randint(20, 40)

    # Owner port cells laid out so each front is a distinct in-grid cell.
    # Inputs point W (front to the left), outputs point E (front to the right);
    # +extra cells give multiple raw patterns to filter.
    in_extra = rng.randint(0, 2)
    out_extra = rng.randint(0, 2)
    in_cells: List[Tuple[int, int, str]] = [(bx, by + i, "W") for i in range(in_need + in_extra)]
    out_cells: List[Tuple[int, int, str]] = [(bx + 4, by + i, "E") for i in range(out_need + out_extra)]
    in_fronts = [_front(*c) for c in in_cells]
    out_fronts = [_front(*c) for c in out_cells]
    all_fronts = in_fronts + out_fronts

    owner_pose = {
        "pose_id": "owner_p0",
        "anchor": {"x": bx + 2, "y": by},
        "occupied_cells": [[bx + 2, by]],  # 1-cell body, distinct from ports/fronts
        "input_port_cells": [{"x": x, "y": y, "dir": d} for (x, y, d) in in_cells],
        "output_port_cells": [{"x": x, "y": y, "dir": d} for (x, y, d) in out_cells],
    }

    # Plant 0..len(all_fronts) blockers, each a 1-cell wireless_sink body sitting
    # exactly on one chosen front (so it blocks that port). Random subset size so
    # a healthy share of cases fully blocks the owner (empty domain -> cert).
    n_block = rng.randint(0, len(all_fronts)) if all_fronts else 0
    chosen = rng.sample(all_fronts, n_block) if n_block else []
    chosen = list(dict.fromkeys(chosen))  # de-dup (distinct fronts already, but be safe)

    instances: List[Dict[str, Any]] = [
        {"instance_id": "owner", "facility_type": "owner_tpl", "operation_type": prof["operation_type"],
         "is_mandatory": True, "bound_type": "exact"}
    ]
    pools: Dict[str, List[Dict[str, Any]]] = {"owner_tpl": [owner_pose]}
    placement: Dict[str, Dict[str, Any]] = {
        "owner": {"pose_idx": 0, "pose_id": "owner_p0", "anchor": owner_pose["anchor"], "facility_type": "owner_tpl"}
    }
    cells_by_instance: Dict[str, Set[Tuple[int, int]]] = {}
    blocker_cells: Set[Tuple[int, int]] = set()
    for i, (fx, fy) in enumerate(chosen):
        bid = f"blk_{i:02d}"
        tpl = f"blk_tpl_{i:02d}"
        bpose = {"pose_id": f"{bid}_p0", "anchor": {"x": fx, "y": fy},
                 "occupied_cells": [[fx, fy]], "input_port_cells": [], "output_port_cells": []}
        pools[tpl] = [bpose]
        instances.append({"instance_id": bid, "facility_type": tpl, "operation_type": "wireless_sink",
                          "is_mandatory": False, "bound_type": "exact"})
        placement[bid] = {"pose_idx": 0, "pose_id": bpose["pose_id"], "anchor": bpose["anchor"], "facility_type": tpl}
        cells_by_instance[bid] = {(fx, fy)}
        blocker_cells.add((fx, fy))

    return {
        "owner_id": "owner",
        "owner_slots": {"input_slots": prof["input_slots"], "output_slots": prof["output_slots"]},
        "owner_in_cells": in_cells,
        "owner_out_cells": out_cells,
        "blocker_cells": blocker_cells,
        "cells_by_instance": cells_by_instance,
        "instances": instances,
        "pools": pools,
        "placement": placement,
    }


def run_rab(case: Dict[str, Any]) -> Tuple[str, Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    ctx = build_routing_binding_context(case["placement"], case["pools"], GRID, GRID)
    model = PortBindingModel(
        case["placement"], case["pools"], case["instances"],
        required_generic_outputs={}, required_generic_inputs={},
        wireless_sink_generic_input_slots=1, routing_context=ctx,
    )
    model.build()
    status = model.solve(time_limit_seconds=10.0)
    binding_domains = {iid: list(dom) for iid, dom in model.binding_domains.items()}
    certs = model.extract_routing_aware_certificates()
    return status, binding_domains, certs


# --------------------------------------------------------------------------- #
# Self-test of the verifier (no solver)
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    rc = 0
    # front geometry + usability
    if _front(5, 5, "E") != (6, 5) or _front(5, 5, "W") != (4, 5) or _front(5, 5, "N") != (5, 6):
        print("[self-test] FAIL: front geometry")
        rc = 1

    # a single-pattern domain: 1 input cell @ (10,10,W) front (9,10), 1 output @ (14,10,E) front (15,10)
    raw = independent_binding_domain({"a": 1}, {"z": 1}, [(10, 10, "W")], [(14, 10, "E")]) or set()
    # no blockers -> survives
    if _independent_filtered_domain(raw, routing_free=set(), occupied=set()) != raw:
        print("[self-test] FAIL: clean domain should fully survive")
        rc = 1
    # block the input front (9,10) -> domain empties
    if _independent_filtered_domain(raw, routing_free=set(), occupied={(9, 10)}):
        print("[self-test] FAIL: blocked input front should empty domain")
        rc = 1
    # routing-free output: blocking the OUTPUT front must NOT prune when z is routing-free
    if _independent_filtered_domain(raw, routing_free={"z"}, occupied={(15, 10)}) != raw:
        print("[self-test] FAIL: routing-free output front must not prune")
        rc = 1
    print("[self-test] front/filter primitives OK")

    # verifier: over-prune (false-INFEASIBLE) detection — model pruned a pattern
    # an independent filter would keep.
    case = {
        "owner_id": "owner",
        "owner_slots": {"input_slots": {"a": 1}, "output_slots": {}},
        "owner_in_cells": [(10, 10, "W"), (10, 11, "W")],  # 2 raw patterns (1-of-2 cells)
        "owner_out_cells": [],
        "blocker_cells": set(),            # nothing blocked
        "cells_by_instance": {},
        "instances": [], "pools": {}, "placement": {},
    }
    full_raw = independent_binding_domain({"a": 1}, {}, [(10, 10, "W"), (10, 11, "W")], []) or set()
    model_overpruned = [next(_pattern_to_dict(p) for p in [list(full_raw)[0]])]  # keep only 1 of 2
    ok, reasons = verify_rab(case, status="FEASIBLE", binding_domains={"owner": model_overpruned}, certs=[])
    print(f"[self-test] over-prune flagged={not ok} ({[r for r in reasons if r.startswith('[RAB-FILTER]')][:1]})")
    if ok or not any(r.startswith("[RAB-FILTER]") for r in reasons):
        rc = 1

    # verifier: unsound cert detection — cert claims a blocker that does NOT
    # empty the owner domain (a different cell), so a pattern survives.
    case2 = {
        "owner_id": "owner",
        "owner_slots": {"input_slots": {"a": 1}, "output_slots": {}},
        "owner_in_cells": [(10, 10, "W")],
        "owner_out_cells": [],
        "blocker_cells": {(99, 99)},
        "cells_by_instance": {"blk": {(99, 99)}},   # blocker far away, blocks nothing
        "instances": [], "pools": {}, "placement": {},
    }
    raw2 = independent_binding_domain({"a": 1}, {}, [(10, 10, "W")], []) or set()
    model_dom2 = [_pattern_to_dict(p) for p in raw2]   # domain non-empty (front (9,10) free)
    bad_cert = [{"owner_instance_id": "owner", "owner_pose_idx": 0, "blocker_instance_ids": ["blk"]}]
    ok2, reasons2 = verify_rab(case2, status="FEASIBLE", binding_domains={"owner": model_dom2}, certs=bad_cert)
    print(f"[self-test] unsound-cert flagged={not ok2} ({[r for r in reasons2 if r.startswith('[RAB-CERT]')][:1]})")
    if ok2 or not any(r.startswith("[RAB-CERT]") for r in reasons2):
        rc = 1

    print("[self-test] PASS" if rc == 0 else "[self-test] FAIL")
    return rc


def _pattern_to_dict(atoms: frozenset) -> Dict[str, Any]:
    pat: Dict[str, Any] = {"input_ports": [], "output_ports": [], "active_ports": []}
    for (side, c, x, y, d) in atoms:
        port = {"type": "input" if side == "in" else "output", "commodity": c, "x": x, "y": y, "dir": d}
        pat["input_ports" if side == "in" else "output_ports"].append(port)
    pat["active_ports"] = pat["input_ports"] + pat["output_ports"]
    return pat


# --------------------------------------------------------------------------- #
# Batch
# --------------------------------------------------------------------------- #
def _batch(n: int, seed: int) -> int:
    rng = random.Random(seed)
    feasible = infeasible = errors = certs_seen = empty_owner = 0
    mismatches: List[str] = []
    for i in range(n):
        case = gen_instance(rng)
        try:
            status, binding_domains, certs = run_rab(case)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            mismatches.append(f"iter {i}: EXC {type(exc).__name__}: {exc}")
            continue
        certs_seen += len(certs)
        if status == "FEASIBLE":
            feasible += 1
        elif status == "INFEASIBLE":
            infeasible += 1
        if case["owner_id"] not in binding_domains:
            empty_owner += 1
        ok, reasons = verify_rab(case, status=status, binding_domains=binding_domains, certs=certs)
        if not ok:
            mismatches.append(f"iter {i}: status={status} reasons={reasons[:3]}")
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{n} feasible={feasible} infeasible={infeasible} "
                  f"certs={certs_seen} mm={len(mismatches)} err={errors}")
    print("=" * 60)
    print(f"batch={n} seed={seed}: feasible={feasible} infeasible={infeasible} "
          f"empty_owner={empty_owner} certs_seen={certs_seen} mismatches={len(mismatches)} errors={errors}")
    for line in mismatches[:20]:
        print("  MISMATCH:", line)
    return 1 if mismatches else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rc = 0
    if args.self_test:
        rc |= _self_test()
    if args.batch:
        rc |= _batch(args.batch, args.seed)
    if not args.self_test and not args.batch:
        rc |= _self_test()
        rc |= _batch(80, 0)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
