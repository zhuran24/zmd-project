"""Differential fuzz harness — port-binding model fidelity (tier ② slice 3).

Hunts soundness bugs in the certified port-binding subproblem
(`src.models.binding_subproblem.PortBindingModel` + the pose-level enumeration
in `src.models.port_binding`). Two error directions, mirroring the other slices:

  * false-FEASIBLE (more dangerous): the model returns FEASIBLE + a selection
    whose generic-output / generic-input commodity counts do NOT match the
    required totals exactly, or whose chosen fixed-operation binding pattern is
    not a legal commodity-to-port-cell assignment, or whose extract_port_specs()
    leaks a routing-free wireless commodity / a virtual input slot into the
    routing terminal set.
  * false-INFEASIBLE (over-constrained): the model returns INFEASIBLE although
    an exact-count assignment provably exists.

INDEPENDENCE (the whole point — see README design principle #1):
The verifier NEVER imports the code under test's combinatorial / constraint
logic. It re-derives the binding domain with its own itertools combinations +
product, AND cross-checks the domain size against a closed-form multinomial
coefficient — a THIRD independent witness so that even if the verifier's
backtracking happened to share the SUT's backtracking skeleton, a conceptual
enumeration bug shared by both would still be caught by the formula (addresses
the isomorphic-blind-spot risk head-on). Feasibility is re-derived from first
principles:

    The three variable families (fixed pose-level binding / generic output slots
    / generic input slots) are mutually un-coupled, and a fixed-operation domain
    is never empty unless a pose has too few port cells (which raises, it does
    not return INFEASIBLE). Each generic side is "distribute interchangeable
    slots among commodities + an unlimited __unused__ bucket", so

        FEASIBLE  <=>  sum(required_outputs) <= #output_slots
                  AND  sum(required_inputs)  <= #input_slots
                  AND  every fixed-operation pose has enough port cells.

This is an exact characterization (verified against build() constraint assembly),
so the reverse direction needs no pinned adjudication (unlike the master slice's
ghost-rectangle gap). The iff is valid ONLY with EXACT_BINDING_USE_OVERLOAD_-
SEPARATION OFF (an env-gated HARD nogood that can legitimately make the model
INFEASIBLE); run_binding() guards that env is unset.

What stays "truth/data" (the verifier may read it) vs "logic under test" (the
verifier must re-implement) is split deliberately: the per-commodity *required
slot counts* of each fixed operation (profile.input_slots / output_slots) and
the generic I/O *required totals* are the spec contract — inputs to binding,
computed by the preprocess layer (operation_profiles._rate_to_slots), consumed
not recomputed by the system under test. The *assignment enumeration* and the
*CP-SAT constraint assembly* are the system under test. The generator reads the
profile table to build valid inputs; the verifier receives only the resulting
case data and re-derives everything itself, so it stays self-testable with
synthetic operation types too.

SCOPE (explicitly NOT covered by this slice — see README待做):
  * The RAB-SEP routing_context!=None path (front-blocked binding-pattern
    pruning, which can cause false-INFEASIBLE) — needs its own slice with an
    independently re-derived port-front-status oracle.
  * Duplicate physical port cells (same x,y,dir on one side): physically
    degenerate; the SUT enumerates them by index (so two identical cells => two
    patterns) while this verifier uses (x,y,dir)-set semantics. The generator
    never emits duplicates; if one is ever seen the verifier emits a [NOTE] and
    skips the set comparison rather than producing a wrong verdict.

Usage (run from repo root):
    python cc_context/verification/diff_fuzz/binding_model_diff.py --self-test
    python cc_context/verification/diff_fuzz/binding_model_diff.py --batch 120 --seed 0
    python cc_context/verification/diff_fuzz/binding_model_diff.py --seed 0 --inspect 7
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from collections import Counter
from itertools import combinations, product
from math import factorial
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.models.binding_subproblem import PortBindingModel  # noqa: E402

# Spec facts (NOT computed — the contract of which utility operations are the
# generic I/O hubs; encoding the correct set here is what gives the slot-count
# checks their discriminating power against a "forgot protocol_core" bug).
GENERIC_OUTPUT_OPERATIONS = {"boundary_io", "protocol_core"}
GENERIC_INPUT_OPERATIONS = {"wireless_sink"}
UNUSED = "__unused__"

PortCell = Tuple[int, int, str]  # (x, y, dir)
# Canonical port atom used to compare patterns order-independently.
PortAtom = Tuple[str, str, int, int, str]  # (side, commodity, x, y, dir)
# Canonical port-spec atom: instance_id-aware so two instances emitting an
# identical (type, commodity, x, y, dir) cannot cancel in the Counter diff.
SpecAtom = Tuple[str, str, str, int, int, str]  # (instance_id, type, commodity, x, y, dir)


# --------------------------------------------------------------------------- #
# Independent re-derivation of the pose-level binding domain
# --------------------------------------------------------------------------- #
def _independent_side_domain(
    slot_counts: Dict[str, int],
    cells: List[PortCell],
) -> Optional[Set[frozenset]]:
    """All legal assignments of one side's required commodity slots to cells.

    Returns a set of frozensets of (commodity, x, y, dir) atoms, or None if the
    pose has fewer port cells than required slots (the code under test raises
    ValueError in that case — never returns INFEASIBLE).

    Re-implemented from scratch with itertools.combinations: assign each
    commodity its count of cells, all distinct ways, across all commodities.
    Sorted commodity order intentionally differs from the SUT's dict-insertion
    order so an order-sensitive bug would surface as a set mismatch.
    """
    required = sorted((c, n) for c, n in slot_counts.items() if n > 0)
    total = sum(n for _, n in required)
    if total > len(cells):
        return None
    if not required:
        return {frozenset()}

    results: Set[frozenset] = set()

    def rec(idx: int, remaining: List[PortCell], chosen: List[Tuple[str, int, int, str]]) -> None:
        if idx == len(required):
            results.add(frozenset(chosen))
            return
        commodity, count = required[idx]
        for combo in combinations(remaining, count):
            chosen_next = chosen + [(commodity, cx, cy, cd) for (cx, cy, cd) in combo]
            remaining_next = [cell for cell in remaining if cell not in combo]
            rec(idx + 1, remaining_next, chosen_next)

    rec(0, list(cells), [])
    return results


def _multinomial_side_count(slot_counts: Dict[str, int], n_cells: int) -> Optional[int]:
    """Closed-form pattern count for one side: n! / ((n-Σk)! · Πk!).

    This is an INDEPENDENT witness derived from combinatorics, not from the
    backtracking. If the verifier's recursion and the SUT's recursion shared a
    conceptual bug, this formula would still disagree with the wrong count.
    Returns None on insufficient cells (mirrors _independent_side_domain).
    """
    parts = [n for n in slot_counts.values() if n > 0]
    total = sum(parts)
    if total > n_cells:
        return None
    denom = factorial(n_cells - total)
    for k in parts:
        denom *= factorial(k)
    return factorial(n_cells) // denom


def independent_binding_domain(
    input_slots: Dict[str, int],
    output_slots: Dict[str, int],
    input_cells: List[PortCell],
    output_cells: List[PortCell],
) -> Optional[Set[frozenset]]:
    """Cartesian product of the two side domains; canonical pattern frozensets."""
    in_dom = _independent_side_domain(input_slots, input_cells)
    out_dom = _independent_side_domain(output_slots, output_cells)
    if in_dom is None or out_dom is None:
        return None
    domain: Set[frozenset] = set()
    for in_pat, out_pat in product(in_dom, out_dom):
        atoms: Set[PortAtom] = set()
        for (c, x, y, d) in in_pat:
            atoms.add(("in", c, x, y, d))
        for (c, x, y, d) in out_pat:
            atoms.add(("out", c, x, y, d))
        domain.add(frozenset(atoms))
    return domain


def _expected_domain_count(spec: Dict[str, Any], pose: Dict[str, Any]) -> Optional[int]:
    in_n = _multinomial_side_count(spec["input_slots"], len(pose.get("input_port_cells", [])))
    out_n = _multinomial_side_count(spec["output_slots"], len(pose.get("output_port_cells", [])))
    if in_n is None or out_n is None:
        return None
    return in_n * out_n


def _canon_model_pattern(pattern: Dict[str, Any]) -> frozenset:
    atoms: Set[PortAtom] = set()
    for port in pattern.get("input_ports", []):
        atoms.add(("in", str(port["commodity"]), int(port["x"]), int(port["y"]), str(port["dir"])))
    for port in pattern.get("output_ports", []):
        atoms.add(("out", str(port["commodity"]), int(port["x"]), int(port["y"]), str(port["dir"])))
    return frozenset(atoms)


def _active_ports_consistent(pattern: Dict[str, Any]) -> bool:
    """active_ports must equal input_ports + output_ports (port_binding contract)."""
    def atom(side: str, port: Dict[str, Any]) -> PortAtom:
        return (side, str(port["commodity"]), int(port["x"]), int(port["y"]), str(port["dir"]))
    expected = (
        {atom("in", p) for p in pattern.get("input_ports", [])}
        | {atom("out", p) for p in pattern.get("output_ports", [])}
    )
    active = set()
    for p in pattern.get("active_ports", []):
        side = "in" if str(p.get("type")) == "input" else "out"
        active.add(atom(side, p))
    return active == expected


def _has_duplicate_cells(pose: Dict[str, Any]) -> bool:
    for key in ("input_port_cells", "output_port_cells"):
        cells = _cells(pose, key)
        if len(cells) != len(set(cells)):
            return True
    return False


# --------------------------------------------------------------------------- #
# Independent feasibility characterization
# --------------------------------------------------------------------------- #
def independent_status(case: Dict[str, Any]) -> str:
    """Exact expected status: 'FEASIBLE' / 'INFEASIBLE' / 'ERROR'.

    'ERROR' = some fixed-operation pose has too few port cells, which makes the
    enumeration raise (the harness should see an exception, not INFEASIBLE).
    """
    for iid, spec in case["fixed_ops"].items():
        pose = case["poses"][iid]
        if _multinomial_side_count(spec["input_slots"], len(pose.get("input_port_cells", []))) is None:
            return "ERROR"
        if _multinomial_side_count(spec["output_slots"], len(pose.get("output_port_cells", []))) is None:
            return "ERROR"

    out_slots = sum(len(case["poses"][iid].get("output_port_cells", [])) for iid in case["output_ops"])
    in_slots = len(case["input_ops"]) * int(case["wireless_slots"])
    if sum(case["req_out"].values()) > out_slots:
        return "INFEASIBLE"
    if sum(case["req_in"].values()) > in_slots:
        return "INFEASIBLE"
    return "FEASIBLE"


def _cells(pose: Dict[str, Any], key: str) -> List[PortCell]:
    return [(int(p["x"]), int(p["y"]), str(p["dir"])) for p in pose.get(key, [])]


# --------------------------------------------------------------------------- #
# Selection / port-specs validity (forward direction)
# --------------------------------------------------------------------------- #
def verify_outcome(
    case: Dict[str, Any],
    *,
    status: str,
    binding_domains: Dict[str, List[Dict[str, Any]]],
    selection: Dict[str, Any],
    port_specs: List[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Independent check of a binding model run. Pure over `case` data.

    Reasons prefixed '[NOTE]' are informational (out-of-scope skips), not
    mismatches; callers filter them before deciding pass/fail.
    """
    reasons: List[str] = []
    expected = independent_status(case)
    routing_free = {str(c) for c, n in case["req_in"].items() if int(n) > 0}

    # --- (A) enumeration fidelity: model's fixed-op domains == independent ---
    if expected != "ERROR":
        for iid, spec in case["fixed_ops"].items():
            pose = case["poses"][iid]
            model_list = binding_domains.get(iid)
            if model_list is None:
                reasons.append(f"[A] {iid}: model has no binding domain")
                continue
            # active_ports contract holds regardless of cell uniqueness.
            for p in model_list:
                if not _active_ports_consistent(p):
                    reasons.append(f"[A] {iid}: a pattern's active_ports != input_ports+output_ports")
                    break
            if _has_duplicate_cells(pose):
                reasons.append(f"[NOTE] {iid}: duplicate port cell — [A] set-comparison skipped (out of scope)")
                continue
            mine = independent_binding_domain(
                spec["input_slots"], spec["output_slots"],
                _cells(pose, "input_port_cells"), _cells(pose, "output_port_cells"),
            ) or set()
            model_set = {_canon_model_pattern(p) for p in model_list}
            formula = _expected_domain_count(spec, pose)
            if model_set != mine:
                missing = mine - model_set
                extra = model_set - mine
                reasons.append(
                    f"[A] {iid}: domain mismatch missing={len(missing)} extra={len(extra)} "
                    f"(model {len(model_list)} vs independent {len(mine)})"
                )
            elif len(model_list) != len(model_set):
                reasons.append(f"[A] {iid}: model domain has duplicate patterns ({len(model_list)} vs {len(model_set)} unique)")
            # closed-form independent count witness (isomorphism breaker)
            if formula is not None:
                if len(mine) != formula:
                    reasons.append(f"[A] {iid}: VERIFIER self-error — backtrack count {len(mine)} != multinomial {formula}")
                if len(model_set) != formula:
                    reasons.append(f"[A] {iid}: model domain count {len(model_set)} != multinomial {formula}")

    # --- feasibility-direction mismatch (independent vs model status) ---
    if status == "FEASIBLE" and expected == "INFEASIBLE":
        reasons.append(f"[FEAS] model FEASIBLE but independent characterization is INFEASIBLE: {_feas_detail(case)}")
    if status == "INFEASIBLE" and expected == "FEASIBLE":
        reasons.append(f"[FEAS] model INFEASIBLE but exact characterization is FEASIBLE: {_feas_detail(case)}")

    if status != "FEASIBLE":
        return (not _is_mismatch(reasons)), reasons

    # --- (C) selection validity on FEASIBLE ---
    # C1: binding_choice covers exactly the fixed-operation instances, each idx
    # legal and the chosen pattern a legal commodity-to-cell assignment.
    choice = selection.get("binding_choice", {})
    expected_fixed = set(case["fixed_ops"])
    if set(choice) != expected_fixed:
        reasons.append(f"[C1] binding_choice keys {sorted(set(choice) ^ expected_fixed)} differ from fixed ops")
    for iid in expected_fixed & set(choice):
        idx = int(choice[iid])
        model_list = binding_domains.get(iid, [])
        if idx < 0 or idx >= len(model_list):
            reasons.append(f"[C1] {iid}: binding_choice idx {idx} out of range (domain {len(model_list)})")
            continue
        if _has_duplicate_cells(case["poses"][iid]):
            continue  # set semantics unsafe for dup cells; covered by [NOTE] above
        chosen = _canon_model_pattern(model_list[idx])
        spec = case["fixed_ops"][iid]
        pose = case["poses"][iid]
        mine = independent_binding_domain(
            spec["input_slots"], spec["output_slots"],
            _cells(pose, "input_port_cells"), _cells(pose, "output_port_cells"),
        ) or set()
        if chosen not in mine:
            reasons.append(f"[C1] {iid}: chosen pattern idx {idx} is not a legal commodity-to-cell assignment")

    # C2: generic output slots — exact per-commodity counts + single assignment.
    out_assign = selection.get("generic_outputs", {})
    expected_out_slots = _expected_output_slot_ids(case)
    if set(out_assign) != expected_out_slots:
        reasons.append(f"[C2] generic_outputs slot set differs: {sorted(set(out_assign) ^ expected_out_slots)[:4]}")
    if len(out_assign) != len(expected_out_slots):
        reasons.append(f"[C2] generic_outputs has {len(out_assign)} entries, expected {len(expected_out_slots)} (slot multi-assigned?)")
    for slot_id, commodity in out_assign.items():
        if commodity != UNUSED and commodity not in case["req_out"]:
            reasons.append(f"[C2] output slot {slot_id} assigned non-required commodity {commodity!r}")
    out_counts = Counter(c for c in out_assign.values() if c != UNUSED)
    for commodity, required in case["req_out"].items():
        if out_counts.get(commodity, 0) != int(required):
            reasons.append(f"[C2] output commodity {commodity!r}: {out_counts.get(commodity, 0)} slots != required {required}")

    # C3: generic input slots — exact per-commodity counts + single assignment.
    in_assign = selection.get("generic_inputs", {})
    expected_in_slots = _expected_input_slot_ids(case)
    if set(in_assign) != expected_in_slots:
        reasons.append(f"[C3] generic_inputs slot set differs: {sorted(set(in_assign) ^ expected_in_slots)[:4]}")
    if len(in_assign) != len(expected_in_slots):
        reasons.append(f"[C3] generic_inputs has {len(in_assign)} entries, expected {len(expected_in_slots)} (slot multi-assigned?)")
    for slot_id, commodity in in_assign.items():
        if commodity != UNUSED and commodity not in case["req_in"]:
            reasons.append(f"[C3] input slot {slot_id} assigned non-required commodity {commodity!r}")
    in_counts = Counter(c for c in in_assign.values() if c != UNUSED)
    for commodity, required in case["req_in"].items():
        if in_counts.get(commodity, 0) != int(required):
            reasons.append(f"[C3] input commodity {commodity!r}: {in_counts.get(commodity, 0)} slots != required {required}")

    # --- (D) extract_port_specs filtering: reconstruct + compare, then explicit invariants.
    expected_specs = _independent_port_specs(case, binding_domains, selection, routing_free)
    model_specs = Counter(_canon_spec(s) for s in port_specs)
    if expected_specs != model_specs:
        missing = expected_specs - model_specs
        extra = model_specs - expected_specs
        reasons.append(f"[D-recon] port_specs mismatch: missing={list(missing)[:3]} extra={list(extra)[:3]}")
    # Defence-in-depth invariants (independent of the reconstruction; tagged
    # separately so a single root cause is attributable, not double-counted).
    for s in port_specs:
        if s.get("type") == "out" and str(s.get("commodity")) in routing_free:
            reasons.append(f"[D-inv] routing-free commodity {s.get('commodity')!r} leaked into output port_spec")
        if str(s.get("instance_id")) in case["input_ops"]:
            reasons.append(f"[D-inv] wireless_sink (virtual input) {s.get('instance_id')} leaked into port_specs")

    return (not _is_mismatch(reasons)), reasons


def _is_mismatch(reasons: List[str]) -> bool:
    return any(not r.startswith("[NOTE]") for r in reasons)


def _feas_detail(case: Dict[str, Any]) -> str:
    out_slots = sum(len(case["poses"][iid].get("output_port_cells", [])) for iid in case["output_ops"])
    in_slots = len(case["input_ops"]) * int(case["wireless_slots"])
    return (
        f"req_out_sum={sum(case['req_out'].values())} out_slots={out_slots} "
        f"req_in_sum={sum(case['req_in'].values())} in_slots={in_slots}"
    )


def _expected_output_slot_ids(case: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for iid in case["output_ops"]:
        pose = case["poses"][iid]
        for local_idx in range(len(pose.get("output_port_cells", []))):
            ids.add(f"{iid}:out:{local_idx}")
    return ids


def _expected_input_slot_ids(case: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for iid in case["input_ops"]:
        for local_idx in range(int(case["wireless_slots"])):
            ids.add(f"{iid}:in:{local_idx}")
    return ids


def _canon_spec(spec: Dict[str, Any]) -> SpecAtom:
    return (
        str(spec.get("instance_id")),
        str(spec.get("type")),
        str(spec.get("commodity")),
        int(spec.get("x")),
        int(spec.get("y")),
        str(spec.get("dir")),
    )


def _independent_port_specs(
    case: Dict[str, Any],
    binding_domains: Dict[str, List[Dict[str, Any]]],
    selection: Dict[str, Any],
    routing_free: Set[str],
) -> Counter:
    """Re-derive extract_port_specs() output from the (validated) selection.

    Rules re-stated from the routing contract: fixed-op input ports always
    surface; fixed-op output ports surface unless routing-free; generic output
    slots surface unless __unused__ / routing-free; generic input slots are
    virtual wireless slots and NEVER surface.
    """
    specs: Counter = Counter()
    choice = selection.get("binding_choice", {})
    for iid in case["fixed_ops"]:
        if iid not in choice:
            continue
        idx = int(choice[iid])
        model_list = binding_domains.get(iid, [])
        if not (0 <= idx < len(model_list)):
            continue
        pattern = model_list[idx]
        for port in pattern.get("input_ports", []):
            specs[(str(iid), "in", str(port["commodity"]), int(port["x"]), int(port["y"]), str(port["dir"]))] += 1
        for port in pattern.get("output_ports", []):
            if str(port["commodity"]) in routing_free:
                continue
            specs[(str(iid), "out", str(port["commodity"]), int(port["x"]), int(port["y"]), str(port["dir"]))] += 1

    out_assign = selection.get("generic_outputs", {})
    for iid in case["output_ops"]:
        pose = case["poses"][iid]
        for local_idx, port in enumerate(pose.get("output_port_cells", [])):
            commodity = out_assign.get(f"{iid}:out:{local_idx}")
            if commodity in (None, UNUSED) or str(commodity) in routing_free:
                continue
            specs[(str(iid), "out", str(commodity), int(port["x"]), int(port["y"]), str(port["dir"]))] += 1
    # generic input slots: virtual -> contribute nothing.
    return specs


# --------------------------------------------------------------------------- #
# Instance generator (uses the real profile table to build VALID inputs)
# --------------------------------------------------------------------------- #
def _load_fixed_profiles() -> List[Dict[str, Any]]:
    """Real recipe operations that support pose-level binding, with slot reqs.

    Reads the canonical profile table (truth data). The predicate is the
    definitional 'no generic hub slots', re-stated here rather than imported.
    """
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES
    rows: List[Dict[str, Any]] = []
    for op, prof in sorted(OPERATION_PORT_PROFILES.items()):
        if prof.generic_input_slots != 0 or prof.generic_output_slots != 0:
            continue
        ins = {c: int(n) for c, n in prof.input_slots.items() if int(n) > 0}
        outs = {c: int(n) for c, n in prof.output_slots.items() if int(n) > 0}
        rows.append({"operation_type": op, "input_slots": ins, "output_slots": outs})
    return rows


_FIXED_PROFILES = _load_fixed_profiles()
_NEXT_COORD = [0]


def _fresh_cells(count: int, rng: random.Random) -> List[Dict[str, int]]:
    """Distinct port cells with unique coordinates (no accidental duplicates)."""
    cells: List[Dict[str, int]] = []
    for _ in range(count):
        c = _NEXT_COORD[0]
        _NEXT_COORD[0] += 1
        cells.append({"x": c % 70, "y": (c // 70) % 70 + 70 * (c // 4900 + 1), "dir": rng.choice(["N", "S", "E", "W"])})
    return cells


def gen_instance(rng: random.Random) -> Dict[str, Any]:
    instances: List[Dict[str, Any]] = []
    placement: Dict[str, Dict[str, Any]] = {}
    pools: Dict[str, List[Dict[str, Any]]] = {}
    poses: Dict[str, Dict[str, Any]] = {}
    fixed_ops: Dict[str, Dict[str, Any]] = {}
    output_ops: List[str] = []
    input_ops: List[str] = []

    def register_pose(iid: str, tpl: str, pose: Dict[str, Any]) -> None:
        pose = dict(pose)
        pose.setdefault("pose_id", f"{iid}_p0")
        pose.setdefault("anchor", {"x": 0, "y": 0})
        pose.setdefault("occupied_cells", [])
        pools.setdefault(tpl, [])
        pose_idx = len(pools[tpl])
        pools[tpl].append(pose)
        poses[iid] = pose
        placement[iid] = {"pose_idx": pose_idx, "pose_id": pose["pose_id"], "anchor": pose["anchor"], "facility_type": tpl}

    def add_instance(iid: str, op: str, pose: Dict[str, Any]) -> None:
        tpl = f"tpl__{iid}"  # unique pool key per instance => no pose_idx collision
        register_pose(iid, tpl, pose)
        instances.append({"instance_id": iid, "facility_type": tpl, "operation_type": op, "is_mandatory": True, "bound_type": "exact"})

    # Fixed-operation (recipe) instances: enough port cells (+extra -> multiple patterns).
    fixed_output_commodities: List[str] = []
    for i in range(rng.randint(0, 2)):
        prof = rng.choice(_FIXED_PROFILES)
        in_need = sum(prof["input_slots"].values())
        out_need = sum(prof["output_slots"].values())
        # Occasionally under-provision to exercise the insufficient-cell path.
        starve = rng.random() < 0.08 and (in_need + out_need) > 0
        in_extra = -1 if (starve and in_need > 0) else rng.randint(0, 2)
        out_extra = 0 if (starve and in_need > 0) else (-1 if starve else rng.randint(0, 2))
        iid = f"fix_{i:02d}"
        pose = {
            "input_port_cells": _fresh_cells(max(0, in_need + in_extra), rng),
            "output_port_cells": _fresh_cells(max(0, out_need + out_extra), rng),
        }
        add_instance(iid, prof["operation_type"], pose)
        fixed_ops[iid] = {"input_slots": prof["input_slots"], "output_slots": prof["output_slots"]}
        fixed_output_commodities.extend(prof["output_slots"].keys())

    # Generic-output (boundary_io / protocol_core) instances.
    for i in range(rng.randint(0, 2)):
        op = rng.choice(sorted(GENERIC_OUTPUT_OPERATIONS))
        iid = f"out_{i:02d}"
        pose = {"input_port_cells": [], "output_port_cells": _fresh_cells(rng.randint(0, 4), rng)}
        add_instance(iid, op, pose)
        output_ops.append(iid)

    # Generic-input (wireless_sink) instances.
    wireless_slots = rng.randint(1, 4)
    for i in range(rng.randint(0, 2)):
        iid = f"in_{i:02d}"
        add_instance(iid, "wireless_sink", {"input_port_cells": [], "output_port_cells": []})
        input_ops.append(iid)

    # pose_optional synthesis path: with some probability, place a
    # protocol_storage_box WITHOUT registering it in the instances list, so the
    # model must synthesize it as wireless_sink (_materialize_pose_optional_-
    # instances). Single one per case to avoid pool-key collisions.
    if rng.random() < 0.25:
        iid = "pose_optional::protocol_storage_box::synth"
        register_pose(iid, "protocol_storage_box", {"input_port_cells": [], "output_port_cells": []})
        input_ops.append(iid)  # synthesized as wireless_sink => virtual input slots

    # Required generic I/O totals. Mostly disjoint synthetic namespaces; with
    # some probability share a namespace so a routing-free input commodity also
    # appears as a required OUTPUT (drives the output-side routing_free filter).
    out_slot_total = sum(len(poses[iid]["output_port_cells"]) for iid in output_ops)
    in_slot_total = len(input_ops) * wireless_slots
    if rng.random() < 0.3:
        out_names = in_names = ["X1", "X2"]
    else:
        out_names, in_names = ["O1", "O2"], ["I1", "I2"]
    req_out = _gen_requirements(out_names, out_slot_total, rng)
    req_in = _gen_requirements(in_names, in_slot_total, rng)

    # With some probability force a fixed-op OUTPUT commodity to be routing-free
    # (req_in>0), which makes that fixed-op output port get filtered from
    # port_specs — exercising the fixed-op output routing_free skip.
    if fixed_output_commodities and in_slot_total >= 1 and rng.random() < 0.25:
        rc = rng.choice(fixed_output_commodities)
        req_in = {rc: 1}
        for n in in_names:
            req_in.setdefault(n, 0)

    if not instances:
        return gen_instance(rng)

    return {
        "instances": instances,
        "placement": placement,
        "pools": pools,
        "poses": poses,
        "fixed_ops": fixed_ops,
        "output_ops": output_ops,
        "input_ops": input_ops,
        "wireless_slots": wireless_slots,
        "req_out": req_out,
        "req_in": req_in,
    }


def _gen_requirements(commodities: List[str], slot_total: int, rng: random.Random) -> Dict[str, int]:
    """Random per-commodity required counts; ~40% chance of intentional overflow."""
    names = list(dict.fromkeys(commodities))
    if rng.random() < 0.4:
        target = slot_total + rng.randint(1, 3)  # overflow
    else:
        target = rng.randint(0, slot_total)
    req = {c: 0 for c in names}
    remaining = target
    for c in names[:-1]:
        take = rng.randint(0, remaining)
        req[c] = take
        remaining -= take
    req[names[-1]] = remaining
    return req


def run_binding(case: Dict[str, Any]) -> Tuple[str, Dict[str, List[Dict[str, Any]]], Dict[str, Any], List[Dict[str, Any]]]:
    # The exact feasibility characterization is only valid with the env-gated
    # overload nogood OFF; guard so an exported env cannot silently break it.
    if os.environ.get("EXACT_BINDING_USE_OVERLOAD_SEPARATION", "").strip().lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("EXACT_BINDING_USE_OVERLOAD_SEPARATION is set; the oracle's exact "
                           "feasibility characterization is invalid with it on. Unset it.")
    model = PortBindingModel(
        case["placement"],
        case["pools"],
        case["instances"],
        required_generic_outputs=case["req_out"],
        required_generic_inputs=case["req_in"],
        wireless_sink_generic_input_slots=case["wireless_slots"],
    )
    model.build()
    status = model.solve(time_limit_seconds=10.0)
    binding_domains = {iid: list(dom) for iid, dom in model.binding_domains.items()}
    selection = model.extract_selection() if status == "FEASIBLE" else {}
    port_specs = model.extract_port_specs() if status == "FEASIBLE" else []
    return status, binding_domains, selection, port_specs


# --------------------------------------------------------------------------- #
# Self-test of the independent verifier (no solver involved)
# --------------------------------------------------------------------------- #
def _self_test() -> int:
    rc = 0

    # Independent enumeration sanity + multinomial agreement.
    if len(independent_binding_domain({"a": 1}, {}, [(0, 0, "E"), (1, 0, "E")], [])) != 2 or _multinomial_side_count({"a": 1}, 2) != 2:
        print("[self-test] FAIL: enum/multinomial single")
        rc = 1
    if len(independent_binding_domain({"a": 1, "b": 1}, {}, [(0, 0, "E"), (1, 0, "E")], [])) != 2 or _multinomial_side_count({"a": 1, "b": 1}, 2) != 2:
        print("[self-test] FAIL: enum/multinomial two-commodity")
        rc = 1
    if _multinomial_side_count({"a": 1}, 3) != 3 or len(independent_binding_domain({"a": 1}, {}, [(0, 0, "E"), (1, 0, "E"), (2, 0, "E")], [])) != 3:
        print("[self-test] FAIL: enum/multinomial 3-choose-1")
        rc = 1
    if _independent_side_domain({"a": 3}, [(0, 0, "E")]) is not None or _multinomial_side_count({"a": 3}, 1) is not None:
        print("[self-test] FAIL: insufficient cells should give None")
        rc = 1
    print(f"[self-test] enum + closed-form multinomial agree: {rc == 0}")

    # Clean synthetic case.
    pose_fix = {"input_port_cells": [{"x": 0, "y": 0, "dir": "W"}, {"x": 1, "y": 0, "dir": "W"}],
                "output_port_cells": [{"x": 2, "y": 0, "dir": "E"}]}
    pose_out = {"input_port_cells": [], "output_port_cells": [{"x": 5, "y": 0, "dir": "N"}, {"x": 6, "y": 0, "dir": "N"}]}
    case = {
        "instances": [], "placement": {}, "pools": {},
        "poses": {"fix_00": pose_fix, "out_00": pose_out, "in_00": {"input_port_cells": [], "output_port_cells": []}},
        "fixed_ops": {"fix_00": {"input_slots": {"a": 1}, "output_slots": {"z": 1}}},
        "output_ops": ["out_00"], "input_ops": ["in_00"], "wireless_slots": 2,
        "req_out": {"O1": 1, "O2": 0}, "req_in": {"I1": 1, "I2": 0},
    }
    bd_correct = independent_binding_domain({"a": 1}, {"z": 1}, [(0, 0, "W"), (1, 0, "W")], [(2, 0, "E")])
    model_domains = {"fix_00": [_pattern_from_atoms(p) for p in bd_correct]}
    selection = {
        "binding_choice": {"fix_00": 0},
        "generic_outputs": {"out_00:out:0": "O1", "out_00:out:1": UNUSED},
        "generic_inputs": {"in_00:in:0": "I1", "in_00:in:1": UNUSED},
    }
    specs_list = _specs_counter_to_list(_independent_port_specs(case, model_domains, selection, {"I1"}))

    def check(name: str, *, status: str = "FEASIBLE", bd=None, sel=None, specs=None,
              want_tag: Optional[str], want_ok: bool) -> None:
        nonlocal rc
        ok, reasons = verify_outcome(
            case, status=status,
            binding_domains=bd if bd is not None else model_domains,
            selection=sel if sel is not None else selection,
            port_specs=specs if specs is not None else specs_list,
        )
        hit = (want_tag is None) or any(r.startswith(want_tag) for r in reasons)
        good = (ok == want_ok) and hit
        print(f"[self-test] {name}: ok={ok} tag={want_tag} -> {'OK' if good else 'FAIL'} ({[r for r in reasons if want_tag and r.startswith(want_tag)][:1]})")
        if not good:
            rc = 1

    check("clean", want_tag=None, want_ok=True)
    check("dropped-pattern", bd={"fix_00": model_domains["fix_00"][:1]}, want_tag="[A]", want_ok=False)
    check("duplicate-pattern", bd={"fix_00": model_domains["fix_00"] + [model_domains["fix_00"][0]]}, want_tag="[A]", want_ok=False)
    check("C1-oob-idx", sel={**selection, "binding_choice": {"fix_00": 9}}, want_tag="[C1]", want_ok=False)
    illegal = _pattern_from_atoms(frozenset({("in", "a", 4, 4, "W"), ("out", "z", 2, 0, "E")}))
    check("C1-illegal-pattern", bd={"fix_00": [illegal]}, sel={**selection, "binding_choice": {"fix_00": 0}},
          want_tag="[C1]", want_ok=False)
    check("C2-wrong-out", sel={**selection, "generic_outputs": {"out_00:out:0": "O1", "out_00:out:1": "O1"}},
          want_tag="[C2]", want_ok=False)
    check("C3-wrong-in", sel={**selection, "generic_inputs": {"in_00:in:0": "I1", "in_00:in:1": "I1"}},
          want_tag="[C3]", want_ok=False)
    check("D-leak", specs=specs_list + [{"instance_id": "out_00", "type": "out", "commodity": "I1", "x": 9, "y": 9, "dir": "E"}],
          want_tag="[D-inv]", want_ok=False)
    if specs_list:
        check("D-missing", specs=specs_list[:-1], want_tag="[D-recon]", want_ok=False)

    # [FEAS] both directions.
    check("false-INFEASIBLE", status="INFEASIBLE", sel={}, specs=[], want_tag="[FEAS]", want_ok=False)
    over = dict(case)
    over["req_out"] = {"O1": 5, "O2": 0}
    ok, reasons = verify_outcome(over, status="FEASIBLE", binding_domains=model_domains, selection=selection, port_specs=specs_list)
    if ok or not any(r.startswith("[FEAS]") for r in reasons):
        print("[self-test] false-FEASIBLE(overflow): FAIL")
        rc = 1
    else:
        print("[self-test] false-FEASIBLE(overflow): OK")

    print("[self-test] PASS" if rc == 0 else "[self-test] FAIL")
    return rc


def _pattern_from_atoms(atoms: frozenset) -> Dict[str, Any]:
    """Turn a canonical pattern frozenset into a model-shaped pattern dict."""
    pattern: Dict[str, Any] = {"input_ports": [], "output_ports": [], "active_ports": []}
    for (side, c, x, y, d) in atoms:
        port = {"type": "input" if side == "in" else "output", "commodity": c, "x": x, "y": y, "dir": d}
        pattern["input_ports" if side == "in" else "output_ports"].append(port)
    pattern["active_ports"] = pattern["input_ports"] + pattern["output_ports"]
    return pattern


def _specs_counter_to_list(specs: Counter) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for (iid, typ, commodity, x, y, d), n in specs.items():
        for _ in range(n):
            out.append({"instance_id": iid, "type": typ, "commodity": commodity, "x": x, "y": y, "dir": d})
    return out


# --------------------------------------------------------------------------- #
# Batch
# --------------------------------------------------------------------------- #
def _batch(n: int, seed: int) -> int:
    rng = random.Random(seed)
    feasible = infeasible = errors = 0
    pose_optional_cases = shared_ns_cases = 0
    forward_mm: List[str] = []
    reverse_mm: List[str] = []
    anomalies: List[str] = []
    for i in range(n):
        case = gen_instance(rng)
        if any(str(iid).startswith("pose_optional::") for iid in case["input_ops"]):
            pose_optional_cases += 1
        if set(case["req_out"]) & set(case["req_in"]):
            shared_ns_cases += 1
        expected = independent_status(case)
        try:
            status, binding_domains, selection, port_specs = run_binding(case)
        except Exception as e:  # noqa: BLE001
            if expected == "ERROR":
                errors += 1
            else:
                anomalies.append(f"iter {i}: unexpected EXC {type(e).__name__}: {e}")
            continue
        if expected == "ERROR":
            anomalies.append(f"iter {i}: expected enumeration ValueError but model returned {status}")
            continue
        if status == "TIMEOUT":
            anomalies.append(f"iter {i}: TIMEOUT on a tiny instance (anomalous)")
            continue
        if status == "FEASIBLE":
            feasible += 1
        else:
            infeasible += 1
        ok, reasons = verify_outcome(case, status=status, binding_domains=binding_domains,
                                     selection=selection, port_specs=port_specs)
        if not ok:
            bucket = reverse_mm if any("INFEASIBLE but" in r for r in reasons) else forward_mm
            bucket.append(f"iter {i}: status={status} reasons={[r for r in reasons if not r.startswith('[NOTE]')][:4]}")
        if (i + 1) % 20 == 0:
            print(f"  ...{i + 1}/{n} feasible={feasible} infeasible={infeasible} "
                  f"fwd_mm={len(forward_mm)} rev_mm={len(reverse_mm)} anom={len(anomalies)}")
    print("=" * 60)
    print(f"batch={n} seed={seed}: feasible={feasible} infeasible={infeasible} expected_errors={errors} "
          f"pose_optional={pose_optional_cases} shared_ns={shared_ns_cases} "
          f"forward_mismatches={len(forward_mm)} reverse_mismatches={len(reverse_mm)} anomalies={len(anomalies)}")
    for line in (forward_mm + reverse_mm + anomalies)[:20]:
        print("  MISMATCH:", line)
    return 1 if (forward_mm or reverse_mm or anomalies) else 0


def _inspect(seed: int, iteration: int) -> int:
    rng = random.Random(seed)
    case = None
    for _ in range(iteration + 1):
        case = gen_instance(rng)
    assert case is not None
    print("instances:", [(i["instance_id"], i["operation_type"]) for i in case["instances"]])
    print("fixed_ops:", case["fixed_ops"])
    print("output_ops:", case["output_ops"], "input_ops:", case["input_ops"], "wireless_slots:", case["wireless_slots"])
    print("req_out:", case["req_out"], "req_in:", case["req_in"])
    print("independent_status:", independent_status(case))
    status, bd, sel, specs = run_binding(case)
    print("model status:", status)
    ok, reasons = verify_outcome(case, status=status, binding_domains=bd, selection=sel, port_specs=specs)
    print("verify ok:", ok)
    for r in reasons:
        print("  -", r)
    return 0 if ok else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--batch", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--inspect", type=int, default=-1)
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
        rc |= _batch(80, 0)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
