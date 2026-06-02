# -*- coding: utf-8 -*-
"""P1.2 spike sizing gate v5 — LSB-correct + constraint-kind bytes + concrete-literal proxy.

Run from project root:

    python docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py

This is a cheap sizing gate, not a full translator. It deliberately reports both:

1. type-pool counts:
   overlap over candidate_placements facility type pools. This is the v25 metric.

2. concrete/group-expanded proxy counts:
   type-pool overlaps multiplied by the number of concrete master operation groups
   from data/preprocessed/mandatory_exact_instances.json, with non-mandatory pools
   counted once as optional/pose-level proxies.

P1.3A must cap/budget the final literal vector emitted by the real translator, after
group/template/optional expansion. Type-pool counts are only a lower/proxy signal.

History:
  - v2 (v23 review): MSB-first -> LSB-first bitset decode, matching
    src/cuts/oracles/region_capacity_oracle._encode_region_bitset.
  - v3 (v24 review): bytes/term split by constraint kind; F9 runs all rows.
  - v4/v5 (v25 review union):
    * A-F1: type-pool vs concrete/group-expanded literal counts (group multipliers
      from mandatory_exact_instances.json). The headline all-type UB numbers
      (F9 3341, F4 5429, ~16-18K) are type-pool proxies, NOT real-master literal bounds.
    * A-F2: density_envelope window_rect is [x, y, h, w], not [x, y, w, h].
    * B-F1: the family summary density_envelope row no longer falls back to the
      compact witness (4); it carries the real window->pose overlap.
    * B-F2: optional OR-Tools incremental-proto measurement (uses ExportToFile, since
      the 9.15 CpModelProto pybind has no ByteSize/SerializeToString); fail-soft.
"""

from __future__ import annotations

import base64
import collections
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

Cell = Tuple[int, int]
FacilityType = str

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "data" / "cuts" / "spike" / "oracle_emit_fixture_45cert.jsonl"
PLACEMENTS = REPO / "data" / "preprocessed" / "candidate_placements.json"
MANDATORY = REPO / "data" / "preprocessed" / "mandatory_exact_instances.json"

# Region/group families whose cert payload identifies a real facility type in master.
GROUP_FACILITY_TYPE = {
    "region_capacity": "boundary_storage_port",
    "power_hitting_set": "power_pole",
    "power_grid_reach": "power_pole",
}


def load_fixture() -> List[dict]:
    if not FIXTURE.exists():
        sys.exit(
            f"fixture not found: {FIXTURE}\n"
            "Run from the unpacked review package's project/ root."
        )
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_pools() -> Mapping[str, Sequence[dict]]:
    if not PLACEMENTS.exists():
        sys.exit(f"candidate placements not found: {PLACEMENTS}")
    obj = json.loads(PLACEMENTS.read_text(encoding="utf-8"))
    return obj["facility_pools"]


def load_group_multipliers(pools: Mapping[str, Sequence[dict]]) -> Dict[str, int]:
    """Return concrete master group multiplier by facility type.

    The pose-bool master groups mandatory exact instances by
    (facility_type, operation_type), so one type-level pose may correspond to
    several concrete group literals. Facility types absent from the mandatory
    file are retained with multiplier 1 as optional/pose-level proxies.
    """
    multipliers = {ft: 1 for ft in pools}
    if not MANDATORY.exists():
        print(f"WARNING: {MANDATORY} missing; using multiplier=1 for every pool", file=sys.stderr)
        return multipliers

    instances = json.loads(MANDATORY.read_text(encoding="utf-8"))
    ops_by_type: DefaultDict[str, Set[str]] = collections.defaultdict(set)
    for inst in instances:
        ft = inst.get("facility_type")
        op = inst.get("operation_type")
        if isinstance(ft, str) and isinstance(op, str):
            ops_by_type[ft].add(op)

    for ft, ops in ops_by_type.items():
        if ft in multipliers:
            multipliers[ft] = max(1, len(ops))
    return multipliers


def build_index(pools: Mapping[str, Sequence[dict]]):
    """Build cell -> facility_type -> local pose indices.

    Counts are local to each facility type. This avoids global-id aliasing when
    multiplying type-level overlaps by concrete master group count.
    """
    by_type: DefaultDict[Cell, DefaultDict[str, Set[int]]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    for ft in sorted(pools):
        for pose_idx, pose in enumerate(pools[ft]):
            for c in pose.get("occupied_cells", []):
                by_type[(int(c[0]), int(c[1]))][ft].add(pose_idx)
    return by_type, {ft: len(list(v)) for ft, v in pools.items()}


def decode_bitset_cells(b64: str) -> List[Cell]:
    """LSB-first decode matching region_capacity_oracle._encode_region_bitset.

    Encoder: arr[idx//8] |= 1 << (idx % 8), idx = x*70 + y.
    """
    raw = base64.b64decode(b64)
    out: List[Cell] = []
    for byte_i, byte in enumerate(raw):
        for bit_i in range(8):
            if byte & (1 << bit_i):
                idx = byte_i * 8 + bit_i
                if idx < 4900:
                    out.append((idx // 70, idx % 70))
    return out


def union_pose_ids(by_type, cells: Iterable[Cell], ft: str) -> Set[int]:
    out: Set[int] = set()
    for c in cells:
        out |= by_type[c].get(ft, set())
    return out


def type_count(by_type, cells: Iterable[Cell], ft: str) -> int:
    return len(union_pose_ids(by_type, cells, ft))


def type_all_count(by_type, cells: Iterable[Cell]) -> int:
    return sum(len(union_pose_ids(by_type, cells, ft)) for ft in all_types_at_cells(by_type, cells))


def concrete_count(
    by_type,
    cells: Iterable[Cell],
    multipliers: Mapping[str, int],
    fts: Iterable[str] | None = None,
) -> int:
    if fts is None:
        fts = all_types_at_cells(by_type, cells)
    return sum(len(union_pose_ids(by_type, cells, ft)) * int(multipliers.get(ft, 1)) for ft in fts)


def all_types_at_cells(by_type, cells: Iterable[Cell]) -> Set[str]:
    out: Set[str] = set()
    for c in cells:
        out |= set(by_type[c].keys())
    return out


def compact_terms(rec: Mapping, payload: Mapping) -> int:
    fam = rec["family"]
    if fam == "port_exposure":
        return 2
    if fam == "pattern_nogood":
        return len(payload.get("forbidden_pose_pattern", []))
    if fam == "density_envelope":
        return len(payload.get("oracle_assignment_witness", []))
    return max(1, int(rec.get("literal_count") or 0))


def cut_cells(rec: Mapping, payload: Mapping) -> List[Cell]:
    fam = rec["family"]
    if fam == "region_capacity" and payload.get("region_cells_bitset_b64"):
        return decode_bitset_cells(payload["region_cells_bitset_b64"])
    if fam == "cutset":
        cells: List[Cell] = []
        for key in ("side_a_bitset_b64", "side_b_bitset_b64"):
            if payload.get(key):
                cells += decode_bitset_cells(payload[key])
        return cells
    if fam == "component_reach":
        return [tuple(c) for c in payload.get("separator_cells", [])]
    if fam in ("power_hitting_set", "power_grid_reach"):
        return [tuple(c) for c in payload.get("facility_cells", [])]
    if fam == "port_exposure":
        return [tuple(payload["port_cell"]), tuple(payload["front_cell"])]
    # B-F1: density_envelope must report its window overlap in the family summary,
    # not fall back to the compact witness (4). Uses the LSB/[x,y,h,w]-correct window_cells.
    if fam == "density_envelope":
        wr = payload.get("window_rect")
        if isinstance(wr, list) and len(wr) >= 4:
            return window_cells(wr)
    return []


def window_cells(window_rect: Sequence[int]) -> List[Cell]:
    """density_envelope schema is [x, y, h, w], not [x, y, w, h]."""
    x0, y0, h, w = [int(v) for v in window_rect[:4]]
    return [
        (x, y)
        for x in range(x0, x0 + h)
        for y in range(y0, y0 + w)
        if 0 <= x < 70 and 0 <= y < 70
    ]


def mean(xs: Sequence[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def project_gb(terms_per_cut: float, bytes_per_term: float, cuts: int = 100_000) -> float:
    return terms_per_cut * cuts * bytes_per_term / 1e9


def print_projection(label: str, terms: float) -> None:
    print(f"  {label}:")
    print(f"    linear  ~4 B/term : {terms:.0f} x 100K x 4  = {project_gb(terms, 4.0):.2f} GB")
    print(f"    BoolOr ~11 B/term : {terms:.0f} x 100K x 11 = {project_gb(terms, 11.0):.2f} GB")


def _proto_bytes(model) -> int:
    """Serialized proto size via ExportToFile.

    The OR-Tools 9.15.6755 CpModelProto pybind wrapper returned by model.Proto()
    has NO ByteSize / SerializeToString / SerializeAsString, so a measurement that
    calls model.Proto().ByteSize() raises AttributeError. ExportToFile(.pb) writes
    the binary proto and we measure the file size instead.
    """
    fd, path = tempfile.mkstemp(suffix=".pb")
    os.close(fd)
    try:
        model.ExportToFile(path)
        return os.path.getsize(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def try_measure_ortools(total_vars: int = 81_795, term_counts: Sequence[int] = (784, 5429)):
    """Optional incremental-proto bytes/term measurement; fail-soft (returns None on any error).

    Measures high-index tail terms (the conservative varint case) so the linear ~4 /
    BoolOr-no-good ~10-11 B/term constants are reproducible rather than only asserted.
    """
    try:
        from ortools.sat.python import cp_model  # type: ignore

        rows = []
        for k in term_counts:
            model = cp_model.CpModel()
            v = [model.NewBoolVar(f"x{i}") for i in range(total_vars)]
            tail = v[-k:]
            before = _proto_bytes(model)
            model.Add(sum(tail) <= k - 1)
            linear_bpt = (_proto_bytes(model) - before) / k

            model2 = cp_model.CpModel()
            v2 = [model2.NewBoolVar(f"x{i}") for i in range(total_vars)]
            tail2 = v2[-k:]
            before2 = _proto_bytes(model2)
            model2.AddBoolOr([x.Not() for x in tail2])
            boolor_bpt = (_proto_bytes(model2) - before2) / k

            rows.append((k, "tail", linear_bpt, boolor_bpt))
        return rows
    except Exception as exc:  # fail-soft: never crash the gate on the optional measurement
        print(f"  (OR-Tools measurement unavailable: {type(exc).__name__}: {exc})", file=sys.stderr)
        return None


def main() -> None:
    recs = load_fixture()
    pools = load_pools()
    by_type, pool_sizes = build_index(pools)
    multipliers = load_group_multipliers(pools)

    print("registry type-pool sizes:", dict(sorted(pool_sizes.items())))
    print("type-pool total poses:", sum(pool_sizes.values()))
    print("concrete/group multipliers:", dict(sorted(multipliers.items())))
    print("concrete master var upper proxy:", sum(pool_sizes[ft] * multipliers.get(ft, 1) for ft in pool_sizes))
    print()

    by = collections.defaultdict(lambda: {"n": 0, "compact": [], "scoped": [], "type_all": [], "group_all": []})

    for rec in recs:
        fam = rec["family"]
        payload = json.loads(base64.b64decode(rec["cert_payload_b64"]))
        cells = cut_cells(rec, payload)
        ft = GROUP_FACILITY_TYPE.get(fam)

        if cells:
            scoped = type_count(by_type, cells, ft) if ft else type_all_count(by_type, cells)
            type_all = type_all_count(by_type, cells)
            group_all = concrete_count(by_type, cells, multipliers)
        else:
            scoped = type_all = group_all = compact_terms(rec, payload)

        by[fam]["n"] += 1
        by[fam]["compact"].append(compact_terms(rec, payload))
        by[fam]["scoped"].append(scoped)
        by[fam]["type_all"].append(type_all)
        by[fam]["group_all"].append(group_all)

    print(
        "family term/cut: compact=witness/no-good; exp_scoped=type-pool scoped; "
        "exp_type_all=type-pool UB; exp_group_all=concrete/group-expanded proxy"
    )
    print("  (density_envelope expanded now carried in summary, not compact-4 fallback — B-F1)")
    print("%-20s %3s %9s %14s %16s %18s" % ("family", "n", "compact", "exp_scoped", "exp_type_all", "exp_group_all"))
    for fam in sorted(by):
        d = by[fam]
        print(
            "%-20s %3d %9.1f %14.1f %16.1f %18.1f"
            % (fam, d["n"], mean(d["compact"]), mean(d["scoped"]), mean(d["type_all"]), mean(d["group_all"]))
        )
    print()

    mfg_types = [ft for ft in sorted(pools) if ft.startswith("manufacturing")]
    print("F9 density_envelope window_rect -> pose overlap (all fixture rows):")
    print("  %-16s %8s %10s %12s %12s %8s" % ("window", "mfg-max", "type-all", "mfg-group", "group-all", "cells"))
    f9_single: List[int] = []
    f9_type_all: List[int] = []
    f9_mfg_group: List[int] = []
    f9_group_all: List[int] = []

    for rec in [r for r in recs if r["family"] == "density_envelope"]:
        payload = json.loads(base64.b64decode(rec["cert_payload_b64"]))
        wr = payload.get("window_rect")
        if not (isinstance(wr, list) and len(wr) >= 4):
            continue
        cells = window_cells(wr)
        single = max((type_count(by_type, cells, ft) for ft in mfg_types), default=0)
        type_all = type_all_count(by_type, cells)
        mfg_group = concrete_count(by_type, cells, multipliers, fts=mfg_types)
        group_all = concrete_count(by_type, cells, multipliers)

        f9_single.append(single)
        f9_type_all.append(type_all)
        f9_mfg_group.append(mfg_group)
        f9_group_all.append(group_all)

        print("  %-16s %8d %10d %12d %12d %8d" % (str(wr), single, type_all, mfg_group, group_all, len(cells)))

    print(
        "  F9 single-group scoped avg=%.0f max=%d ; type-all avg=%.0f max=%d ; "
        "mfg-group UB avg=%.0f max=%d ; group-all avg=%.0f max=%d"
        % (
            mean(f9_single), max(f9_single),
            mean(f9_type_all), max(f9_type_all),
            mean(f9_mfg_group), max(f9_mfg_group),
            mean(f9_group_all), max(f9_group_all),
        )
    )
    print()

    measurement = try_measure_ortools()
    if measurement is None:
        print("OR-Tools bytes/term check skipped (ortools not importable or measurement failed);")
        print("using documented conservative constants linear=4, BoolOr=11.")
    else:
        print("OR-Tools incremental proto bytes/term (ExportToFile; 81,795 vars, high-index tail terms):")
        print("  %-8s %-8s %-14s %-18s" % ("terms", "slice", "linear<=B/t", "BoolOr-no-goodB/t"))
        for k, label, linear_bpt, boolor_bpt in measurement:
            print("  %-8d %-8s %-14.2f %-18.2f" % (k, label, linear_bpt, boolor_bpt))
    print()

    full_mfg_group = sum(pool_sizes[ft] * multipliers.get(ft, 1) for ft in mfg_types)
    full_concrete_proxy = sum(pool_sizes[ft] * multipliers.get(ft, 1) for ft in pool_sizes)
    print("100K proto projections, by constraint kind:")
    print("  compact all families 1-4 terms/cut: about 1-4 MB at 100K")
    print_projection("F9 single-group max", max(f9_single))
    print_projection("F9 mfg group-expanded UB", max(f9_mfg_group))
    print_projection("F4 component_reach group-expanded max", max(by["component_reach"]["group_all"]))
    print_projection("full manufacturing group-expanded pool", full_mfg_group)
    print_projection("full concrete proxy all pools", full_concrete_proxy)
    print()

    print("Conclusion:")
    print("- LSB bitset sizing remains corrected; the old MSB-first 2026-style F1 count is not used.")
    print("- Compact witness/no-good lowering is still cheap across all families.")
    print("- Expanded/geometric lowering must be capped on the final CONCRETE literal vector")
    print("  (after group/template/optional expansion), NOT just the type-pool count.")
    print("- type-pool UBs (F9 3341, F4 5429, ~16-18K) are cheap proxies, not real-master literal bounds.")
    print("- Budgets must remain constraint-kind-specific: linear about 4 B/term, BoolOr/no-good about 11 B/term.")
    print("- P1.3A guard: per-cut max/p99 cap + cumulative proto budget after group/template/optional resolution.")


if __name__ == "__main__":
    main()
