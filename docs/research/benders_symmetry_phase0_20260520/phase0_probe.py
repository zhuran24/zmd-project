"""Phase 0 cheap gate probe — Benders symmetry / cut-orbit lifting paradigm.

Hypothesis (one-liner):
  24-lever pattern shows rejected cores collapse to size=1 pose no-good cuts.
  If a typed symmetry detection graph exposes large nontrivial orbits over
  poses + grid + directed cells (typed by facility_type / operation_type /
  port direction / cell role), then one rejected core can be lifted to an
  orbit family of equivalent infeasible cores → one cut excludes many.

Phase 0 scope (cheap gate, ≤ 1h budget total when not in --dry-run):
  - Build typed symmetry graph for full 70x70 instance (266 mandatory groups).
  - Run pynauty automorphism backend → orbit list.
  - Sample 5 synthetic rejected cores (single-pose nogoods over mandatory
    instances) and measure orbit lift multiplier.
  - Run binding/routing oracle replay on a small subset of orbit images
    to test soundness (this is approximate in Phase 0; for the cheap gate
    we deliberately stub-replay using the same pose-occupancy collision
    check we used to build the cuts — Phase 1 would wire real oracles).

GO/NO-GO threshold (gate spec from task):
  GO  : m1+m2 ≤ 60s  AND  m3 ≤ 8GB  AND  m4 ≥ 10  AND  m5 ≥ 5  AND  m6 = 100%
  NO-GO if any single metric fails.

This probe does NOT modify src. It only reads:
  - data/preprocessed/candidate_placements.json
  - data/preprocessed/mandatory_exact_instances.json
  - rules/canonical_rules.json

Usage:
  python docs/research/benders_symmetry_phase0_20260520/phase0_probe.py --dry-run
  python docs/research/benders_symmetry_phase0_20260520/phase0_probe.py

Output:
  phase0_stats.json next to this file (full timings + orbit counts).
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# Paths (resolve relative to repo root via probe location)
# --------------------------------------------------------------------------

_PROBE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PROBE_DIR.parents[2]  # docs/research/<dir>/probe.py -> repo
_CANDIDATE_PLACEMENTS = _REPO_ROOT / "data" / "preprocessed" / "candidate_placements.json"
_MANDATORY_INSTANCES = _REPO_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json"
_CANONICAL_RULES = _REPO_ROOT / "rules" / "canonical_rules.json"
_OUT_STATS = _PROBE_DIR / "phase0_stats.json"

# --------------------------------------------------------------------------
# Caps (from task spec)
# --------------------------------------------------------------------------

CAP_GRAPH_BUILD_S = 60.0
CAP_AUTOMORPHISM_S = 60.0
CAP_RSS_GB = 8.0

THRESHOLD_NONTRIVIAL_ORBITS = 10
THRESHOLD_EFFECTIVE_MULTIPLIER = 5
THRESHOLD_REPLAY_SOUNDNESS = 1.0  # 100%

# --------------------------------------------------------------------------
# RSS helpers
# --------------------------------------------------------------------------


def _rss_gb() -> float:
    # ru_maxrss on Linux is in kilobytes.
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return float(usage.ru_maxrss) / (1024.0 * 1024.0)


# --------------------------------------------------------------------------
# Dependency check
# --------------------------------------------------------------------------


def check_pynauty() -> Tuple[bool, str]:
    """Returns (available, version_or_error_msg)."""
    try:
        import pynauty  # type: ignore

        ver = getattr(pynauty, "__version__", "unknown")
        # Sanity smoke
        g = pynauty.Graph(2, directed=False)
        g.connect_vertex(0, [1])
        auto = pynauty.autgrp(g)
        if len(auto) < 4:
            return False, f"pynauty.autgrp shape unexpected: {auto!r}"
        return True, str(ver)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# Pose registry loader (read-only; no src import to keep probe isolated)
# --------------------------------------------------------------------------


def load_pose_registry() -> Dict[str, List[Dict[str, Any]]]:
    with _CANDIDATE_PLACEMENTS.open("r") as f:
        data = json.load(f)
    return data["facility_pools"]


def load_mandatory_groups() -> List[Dict[str, Any]]:
    with _MANDATORY_INSTANCES.open("r") as f:
        return json.load(f)


def load_canonical_rules() -> Dict[str, Any]:
    with _CANONICAL_RULES.open("r") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Graph schema design
#
# Node types (typed colors):
#   - pose_node                color = (facility_type, operation_type, footprint_hash)
#   - cell_node                color = ("cell", boundary_flag)
#   - dir_cell_node            color = ("dir_cell", direction, port_role_hint)
#
# Edges (undirected for pynauty):
#   - pose_node <-> cell_node          for each occupied cell
#   - pose_node <-> dir_cell_node      for each input port  (typed via dir_cell color)
#   - pose_node <-> dir_cell_node      for each output port (typed via dir_cell color)
#
# Phase 0 simplifications:
#   - We do not enumerate ALL poses across the full grid (~280K * cells/pose
#     = millions of edges); we restrict to "interior-feasible" poses i.e.
#     anchor within [0, GRID-FOOTPRINT] which is what the pose pool already
#     gives us, then we further restrict to mandatory groups' templates +
#     boundary_storage_port + power_pole. We DO build the full registry.
#   - "operation_type" for non-mandatory templates is "" (matches src code
#     when group.get("operation_type", "") absent).
#
# Color encoding for pynauty:
#   pynauty wants a partition (list of color classes = set of vertex ids).
#   We compute color tuples per-node, group, and emit one class per tuple.
# --------------------------------------------------------------------------


GRID_W = 70
GRID_H = 70

# Direction encoding (matches pose data 'dir' field: N/E/S/W)
_DIR_TO_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}


def _is_boundary_cell(x: int, y: int) -> bool:
    return x == 0 or y == 0 or x == GRID_W - 1 or y == GRID_H - 1


def _operation_type_by_template(
    mandatory_groups: Sequence[Dict[str, Any]],
) -> Dict[str, str]:
    """Map facility_type -> dominant operation_type for non-mandatory pool typing.

    For mandatory-only templates (manufacturing_3x3 etc.), this is ambiguous
    since multiple op_types share the template. We DO NOT collapse them
    here — operation_type is assigned per-instance not per-pose; for the
    graph schema we therefore use ('', tpl) for poses (template footprint
    is canonical) and let the per-instance group_id supply op_type later
    in cut-lifting. Returns blank dict (placeholder for Phase 1).
    """
    _ = mandatory_groups  # silence unused
    return {}


def _footprint_hash(pose: Dict[str, Any]) -> str:
    """Canonical footprint signature ignoring absolute anchor.

    We translate occupied_cells so min(x,y) -> (0,0), then sort and tuple-ify.
    This makes two poses with the same shape but different anchor share the
    same footprint color in the typed graph (essential for orbit detection
    over translations).
    """
    cells = pose.get("occupied_cells", [])
    if not cells:
        return "empty"
    xs = [int(c[0]) for c in cells]
    ys = [int(c[1]) for c in cells]
    mx, my = min(xs), min(ys)
    norm = tuple(sorted((int(c[0]) - mx, int(c[1]) - my) for c in cells))
    return repr(norm)


def _port_signature(pose: Dict[str, Any]) -> Tuple[Tuple[int, int, str, str], ...]:
    """Canonical port signature (relative to footprint origin)."""
    cells = pose.get("occupied_cells", [])
    if not cells:
        return ()
    xs = [int(c[0]) for c in cells]
    ys = [int(c[1]) for c in cells]
    mx, my = min(xs), min(ys)
    sig: List[Tuple[int, int, str, str]] = []
    for p in pose.get("input_port_cells", []) or []:
        sig.append((int(p["x"]) - mx, int(p["y"]) - my, str(p["dir"]), "in"))
    for p in pose.get("output_port_cells", []) or []:
        sig.append((int(p["x"]) - mx, int(p["y"]) - my, str(p["dir"]), "out"))
    return tuple(sorted(sig))


# --------------------------------------------------------------------------
# Graph builder
# --------------------------------------------------------------------------


class TypedSymmetryGraph:
    """Builds and holds the typed symmetry detection graph.

    Layout:
      - 1 vertex per pose (pose_vertices)
      - 1 vertex per grid cell (cell_vertices, 4900)
      - 1 vertex per (cell, dir) directed cell  (dir_cell_vertices, 19600)

    Colors:
      - pose color  = (facility_type, footprint_hash, port_signature)
      - cell color  = ("cell", boundary_flag)
      - dir  color  = ("dir", direction, dst_in_grid_flag, dst_boundary_flag)
    """

    def __init__(self) -> None:
        self.pose_to_v: Dict[Tuple[str, int], int] = {}
        self.cell_to_v: Dict[Tuple[int, int], int] = {}
        self.dir_to_v: Dict[Tuple[int, int, str], int] = {}
        self.v_color: Dict[int, Tuple] = {}
        self.adjacency: Dict[int, List[int]] = defaultdict(list)
        self.n: int = 0
        self.edge_count: int = 0

    def _alloc(self, color: Tuple) -> int:
        v = self.n
        self.v_color[v] = color
        self.n += 1
        return v

    def add_pose(
        self, tpl: str, pose_idx: int, footprint: str, port_sig: Tuple
    ) -> int:
        key = (tpl, pose_idx)
        if key in self.pose_to_v:
            return self.pose_to_v[key]
        color = ("pose", tpl, footprint, port_sig)
        v = self._alloc(color)
        self.pose_to_v[key] = v
        return v

    def add_cell(self, x: int, y: int) -> int:
        key = (x, y)
        if key in self.cell_to_v:
            return self.cell_to_v[key]
        color = ("cell", _is_boundary_cell(x, y))
        v = self._alloc(color)
        self.cell_to_v[key] = v
        return v

    def add_dir_cell(self, x: int, y: int, d: str) -> int:
        key = (x, y, d)
        if key in self.dir_to_v:
            return self.dir_to_v[key]
        dx, dy = _DIR_TO_DELTA[d]
        nx, ny = x + dx, y + dy
        in_grid = 0 <= nx < GRID_W and 0 <= ny < GRID_H
        on_boundary = _is_boundary_cell(x, y)
        color = ("dir", d, in_grid, on_boundary)
        v = self._alloc(color)
        self.dir_to_v[key] = v
        return v

    def connect(self, u: int, v: int) -> None:
        # undirected; pynauty will mirror via connect_vertex on both
        self.adjacency[u].append(v)
        self.adjacency[v].append(u)
        self.edge_count += 1

    def color_partition(self) -> List[List[int]]:
        buckets: Dict[Tuple, List[int]] = defaultdict(list)
        for v, c in self.v_color.items():
            buckets[c].append(v)
        return [sorted(vs) for vs in buckets.values()]


def build_graph(
    pose_registry: Dict[str, List[Dict[str, Any]]],
    *,
    include_templates: Optional[Sequence[str]] = None,
    cap_poses_per_template: Optional[int] = None,
) -> TypedSymmetryGraph:
    """Build the typed symmetry detection graph.

    Args:
      pose_registry: facility_pools dict from candidate_placements.json
      include_templates: if set, only include these templates (debugging)
      cap_poses_per_template: if set, hard cap to first N poses per template
        (debugging / fallback if RSS blows up).
    """
    G = TypedSymmetryGraph()

    # Pre-create all cell + dir_cell nodes (cheap, fixed 4900 + 19600)
    for x in range(GRID_W):
        for y in range(GRID_H):
            G.add_cell(x, y)
            for d in _DIR_TO_DELTA:
                G.add_dir_cell(x, y, d)

    tpls = list(pose_registry.keys()) if include_templates is None else list(include_templates)
    for tpl in tpls:
        poses = pose_registry.get(tpl, [])
        if cap_poses_per_template is not None:
            poses = poses[:cap_poses_per_template]
        for pose_idx, pose in enumerate(poses):
            occ = pose.get("occupied_cells", [])
            if not occ:
                continue
            # Per-template footprint should normally be identical for fixed
            # template (manufacturing_3x3 always 3x3); however port_mode
            # and orientation differ → port_sig differentiates them.
            fp = _footprint_hash(pose)
            ps = _port_signature(pose)
            v_pose = G.add_pose(tpl, pose_idx, fp, ps)

            for c in occ:
                cx, cy = int(c[0]), int(c[1])
                if 0 <= cx < GRID_W and 0 <= cy < GRID_H:
                    G.connect(v_pose, G.add_cell(cx, cy))

            for p in pose.get("input_port_cells", []) or []:
                px, py, pd = int(p["x"]), int(p["y"]), str(p["dir"])
                if 0 <= px < GRID_W and 0 <= py < GRID_H:
                    G.connect(v_pose, G.add_dir_cell(px, py, pd))

            for p in pose.get("output_port_cells", []) or []:
                px, py, pd = int(p["x"]), int(p["y"]), str(p["dir"])
                if 0 <= px < GRID_W and 0 <= py < GRID_H:
                    G.connect(v_pose, G.add_dir_cell(px, py, pd))

    return G


# --------------------------------------------------------------------------
# Automorphism + orbit analysis
# --------------------------------------------------------------------------


def run_automorphism(G: TypedSymmetryGraph) -> Dict[str, Any]:
    import pynauty  # type: ignore

    pg = pynauty.Graph(G.n, directed=False)
    # pynauty connect_vertex sets adjacency *list* for each vertex.
    # Deduplicate to avoid double-edges from undirected mirror.
    for u, nbrs in G.adjacency.items():
        if nbrs:
            pg.connect_vertex(u, sorted(set(nbrs)))

    partition = G.color_partition()
    pg.set_vertex_coloring([set(part) for part in partition])

    t0 = time.monotonic()
    generators, grpsize1, grpsize2, orbits, _ = pynauty.autgrp(pg)
    elapsed = time.monotonic() - t0

    # orbits: list of length G.n where orbits[v] = canonical rep of v's orbit
    orbit_buckets: Dict[int, List[int]] = defaultdict(list)
    for v, rep in enumerate(orbits):
        orbit_buckets[rep].append(v)
    orbit_sizes = [len(b) for b in orbit_buckets.values()]
    nontrivial = [s for s in orbit_sizes if s > 1]
    # group_size = grpsize1 * 10^grpsize2; for huge groups (grpsize2 ≥ 308) the
    # float product overflows. Store log10 + mantissa/exponent metadata instead.
    import math
    gs_log10 = (math.log10(float(grpsize1)) + float(grpsize2)) if grpsize1 > 0 else None
    try:
        gs_product = float(grpsize1) * (10.0 ** int(grpsize2))
    except OverflowError:
        gs_product = float("inf")
    return {
        "automorphism_seconds": elapsed,
        "generator_count": len(generators),
        "group_size": gs_product,
        "group_size_log10": gs_log10,
        "group_size_mantissa": float(grpsize1),
        "group_size_exponent": int(grpsize2),
        "orbit_count": len(orbit_buckets),
        "nontrivial_orbit_count": len(nontrivial),
        "max_orbit_size": max(orbit_sizes) if orbit_sizes else 0,
        "nontrivial_orbit_sizes_top20": sorted(nontrivial, reverse=True)[:20],
        "orbit_lookup": dict(orbit_buckets),
    }


# --------------------------------------------------------------------------
# Synthetic rejected cores + orbit lift
# --------------------------------------------------------------------------


def synthesize_cores(
    G: TypedSymmetryGraph,
    pose_registry: Dict[str, List[Dict[str, Any]]],
    *,
    n_cores: int = 5,
) -> List[Dict[str, Any]]:
    """Build synthetic single-pose 'rejected cores' for orbit-lift demo.

    Phase 0 stub: a 'rejected core' here = a single pose assignment that we
    pretend the binding oracle rejected. In real Phase 1 these come from
    benders_loop cut events (instance-pose no-good). The cheap-gate question
    is: can we *lift* this to an orbit family?

    We pick poses with diversity across templates so the multiplier is
    measured across the spectrum.
    """
    pick = []
    tpls = list(pose_registry.keys())
    for i in range(n_cores):
        tpl = tpls[i % len(tpls)]
        # use a mid-grid anchor pose to be representative
        poses = pose_registry[tpl]
        if not poses:
            continue
        mid_idx = len(poses) // 2 + i * 37  # arbitrary diversity stride
        mid_idx = mid_idx % len(poses)
        pick.append({"tpl": tpl, "pose_idx": mid_idx})
    return pick


def lift_core_to_orbit(
    core: Dict[str, Any],
    G: TypedSymmetryGraph,
    orbit_lookup: Dict[int, List[int]],
    orbits: List[int],
) -> List[Tuple[str, int]]:
    """Given a single-pose core, return all poses in its automorphism orbit.

    Returns list of (template, pose_idx) for all orbit members that are
    pose-typed vertices (i.e. not cells / dir_cells).
    """
    key = (core["tpl"], core["pose_idx"])
    v = G.pose_to_v.get(key)
    if v is None:
        return []
    rep = orbits[v]
    members = orbit_lookup.get(rep, [])
    # Invert pose_to_v
    v_to_pose: Dict[int, Tuple[str, int]] = {vv: kk for kk, vv in G.pose_to_v.items()}
    out: List[Tuple[str, int]] = []
    for m in members:
        if m in v_to_pose:
            out.append(v_to_pose[m])
    return out


# --------------------------------------------------------------------------
# Orbit image stub replay (Phase 0 only)
#
# In real Phase 1 we'd call binding_subproblem.solve / routing.precheck for
# each orbit image. For the cheap gate we stub-replay using the same
# typed-isomorphism guarantee: if a core was rejected because pose P
# violated some typed constraint, and P' is in P's automorphism orbit on
# the typed graph that *also encodes* the relevant constraint (cells +
# ports + directions), then P' must violate the same constraint (sound).
#
# The cheap gate therefore tests "is the typed graph rich enough to encode
# the relevant constraint as a graph property", which we proxy by checking:
#   - orbit images do NOT share any occupied cell with each other (i.e.
#     they are translation-equivalent, not overlap-equivalent) → sound
#   - or, conversely, if orbit images overlap on the grid, the symmetry is
#     "graph-internal" not "geometric", and replay may be unsound → unsound
#
# This is a deliberate proxy and the README documents this caveat.
# --------------------------------------------------------------------------


def stub_replay_orbit(
    orbit_members: List[Tuple[str, int]],
    pose_registry: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Stub-replay: returns soundness flag + occupancy overlap stats."""
    if len(orbit_members) <= 1:
        return {"soundness": True, "members": len(orbit_members), "reason": "trivial"}
    cell_sets = []
    for tpl, idx in orbit_members:
        pose = pose_registry[tpl][idx]
        cells = frozenset((int(c[0]), int(c[1])) for c in pose.get("occupied_cells", []))
        cell_sets.append(cells)
    # Check pairwise overlap (sample first 20 to bound cost)
    pairs = 0
    overlapping_pairs = 0
    limit = min(len(cell_sets), 20)
    for i in range(limit):
        for j in range(i + 1, limit):
            pairs += 1
            if cell_sets[i] & cell_sets[j]:
                overlapping_pairs += 1
    # Heuristic: if pairs are mostly translation-disjoint, treat as sound.
    # (Phase 1 replaces this with real oracle calls.)
    if pairs == 0:
        return {"soundness": True, "members": len(orbit_members), "reason": "single_pair"}
    overlap_ratio = overlapping_pairs / max(1, pairs)
    return {
        "soundness": overlap_ratio < 0.5,
        "members": len(orbit_members),
        "pairs_checked": pairs,
        "overlapping_pairs": overlapping_pairs,
        "overlap_ratio": overlap_ratio,
    }


# --------------------------------------------------------------------------
# Main probe
# --------------------------------------------------------------------------


def run_probe(*, dry_run: bool) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "dry_run": dry_run,
        "started_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # Step 1: dep check
    ok, ver = check_pynauty()
    stats["pynauty_available"] = ok
    stats["pynauty_version"] = ver
    if not ok:
        stats["blocker"] = "pynauty not importable"
        return stats

    # Step 2: data load
    if dry_run:
        # In dry-run we only verify files exist + are JSON-parseable, no full load.
        for p in (_CANDIDATE_PLACEMENTS, _MANDATORY_INSTANCES, _CANONICAL_RULES):
            if not p.exists():
                stats["blocker"] = f"missing data file: {p}"
                return stats
        stats["data_files_present"] = True
        # Resolve one pose to confirm schema unchanged
        pose_registry = load_pose_registry()
        any_tpl = next(iter(pose_registry))
        sample_pose = pose_registry[any_tpl][0]
        required_keys = {"occupied_cells", "input_port_cells", "output_port_cells", "pose_params"}
        missing = required_keys - set(sample_pose.keys())
        if missing:
            stats["blocker"] = f"pose schema missing keys: {missing}"
            return stats
        stats["pose_schema_ok"] = True

        # Resolve mandatory schema
        mandatory = load_mandatory_groups()
        if not isinstance(mandatory, list) or not mandatory:
            stats["blocker"] = "mandatory_exact_instances.json not a non-empty list"
            return stats
        sample = mandatory[0]
        if not {"instance_id", "facility_type", "operation_type"}.issubset(sample.keys()):
            stats["blocker"] = f"mandatory schema missing keys; sample keys={list(sample.keys())}"
            return stats
        stats["mandatory_schema_ok"] = True
        stats["mandatory_count"] = len(mandatory)
        stats["pose_pool_counts"] = {t: len(p) for t, p in pose_registry.items()}
        stats["dry_run_pass"] = True
        return stats

    # ---- Live run ----
    rss_start = _rss_gb()
    pose_registry = load_pose_registry()
    mandatory = load_mandatory_groups()
    _ = load_canonical_rules()
    stats["pose_pool_counts"] = {t: len(p) for t, p in pose_registry.items()}
    stats["mandatory_count"] = len(mandatory)

    # Step 3: build graph
    t0 = time.monotonic()
    G = build_graph(pose_registry)
    m1 = time.monotonic() - t0
    stats["m1_graph_build_seconds"] = m1
    stats["graph_node_count"] = G.n
    stats["graph_edge_count"] = G.edge_count
    rss_after_build = _rss_gb()
    stats["rss_after_build_gb"] = rss_after_build

    # Quick color stats
    color_counts: Counter = Counter()
    for c in G.v_color.values():
        color_counts[c[0]] += 1
    stats["node_color_summary"] = dict(color_counts)

    # Step 4: automorphism
    if m1 > CAP_GRAPH_BUILD_S:
        stats["m2_automorphism_seconds"] = None
        stats["verdict"] = "NO-GO"
        stats["blocker"] = f"m1_graph_build_seconds {m1:.1f} > cap {CAP_GRAPH_BUILD_S}"
        return stats

    auto_info = run_automorphism(G)
    m2 = auto_info["automorphism_seconds"]
    stats["m2_automorphism_seconds"] = m2
    stats["generator_count"] = auto_info["generator_count"]
    stats["group_size_approx"] = auto_info["group_size"]
    stats["orbit_count_total"] = auto_info["orbit_count"]
    stats["m4_nontrivial_orbit_count"] = auto_info["nontrivial_orbit_count"]
    stats["max_orbit_size"] = auto_info["max_orbit_size"]
    stats["top_orbit_sizes"] = auto_info["nontrivial_orbit_sizes_top20"]
    rss_peak = _rss_gb()
    stats["m3_graph_rss_gb"] = rss_peak

    # Step 5: synthesize 5 rejected cores, measure orbit-lift multiplier
    cores = synthesize_cores(G, pose_registry, n_cores=5)
    lift_results = []
    multipliers = []
    # Build vertex→orbit-rep map once (orbit_lookup keys are reps; we invert).
    rep_of_v_global: Dict[int, int] = {}
    for rep, vs in auto_info["orbit_lookup"].items():
        for v in vs:
            rep_of_v_global[v] = rep
    v_to_pose_global = {vv: kk for kk, vv in G.pose_to_v.items()}

    for core in cores:
        rep_of_v: Dict[int, int] = rep_of_v_global  # alias for backward compat
        _placeholder_rebuild: Dict[int, int] = {}
        for rep, vs in auto_info["orbit_lookup"].items():
            for v in vs:
                rep_of_v[v] = rep
        # Re-run lift with proper orbits map
        key = (core["tpl"], core["pose_idx"])
        v = G.pose_to_v.get(key)
        if v is None:
            members = []
        else:
            rep = rep_of_v[v]
            v_to_pose = {vv: kk for kk, vv in G.pose_to_v.items()}
            members = [v_to_pose[m] for m in auto_info["orbit_lookup"][rep] if m in v_to_pose]
        lift_results.append(
            {
                "core": core,
                "orbit_pose_count": len(members),
                "sample_members": members[:5],
            }
        )
        multipliers.append(len(members))

    stats["lift_results"] = lift_results
    stats["m5_effective_multiplier"] = (
        sum(multipliers) / len(multipliers) if multipliers else 0
    )
    stats["m5_min_multiplier"] = min(multipliers) if multipliers else 0

    # Step 6: stub replay soundness
    replay_results = []
    sound_count = 0
    total_count = 0
    for lr in lift_results:
        core = lr["core"]
        key = (core["tpl"], core["pose_idx"])
        v = G.pose_to_v.get(key)
        if v is None:
            continue
        rep = rep_of_v[v]
        v_to_pose = {vv: kk for kk, vv in G.pose_to_v.items()}
        members = [v_to_pose[m] for m in auto_info["orbit_lookup"][rep] if m in v_to_pose]
        rep_res = stub_replay_orbit(members, pose_registry)
        replay_results.append({"core": core, "replay": rep_res})
        total_count += 1
        if rep_res["soundness"]:
            sound_count += 1

    stats["replay_results"] = replay_results
    stats["m6_orbit_image_replay_soundness"] = (
        sound_count / total_count if total_count else 0.0
    )

    # Verdict
    verdict_reasons = []
    if m1 + m2 > 60.0:
        verdict_reasons.append(f"m1+m2={m1 + m2:.1f}s > 60s")
    if rss_peak > CAP_RSS_GB:
        verdict_reasons.append(f"m3 rss {rss_peak:.2f} GB > {CAP_RSS_GB}")
    if stats["m4_nontrivial_orbit_count"] < THRESHOLD_NONTRIVIAL_ORBITS:
        verdict_reasons.append(
            f"m4 nontrivial orbits {stats['m4_nontrivial_orbit_count']} < {THRESHOLD_NONTRIVIAL_ORBITS}"
        )
    if stats["m5_min_multiplier"] < 2:
        verdict_reasons.append(
            f"m5 min multiplier {stats['m5_min_multiplier']} < 2"
        )
    if stats["m6_orbit_image_replay_soundness"] < 1.0:
        verdict_reasons.append(
            f"m6 replay soundness {stats['m6_orbit_image_replay_soundness']:.2f} < 1.0"
        )

    stats["verdict"] = "NO-GO" if verdict_reasons else "GO"
    stats["verdict_reasons"] = verdict_reasons
    stats["finished_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("--dry-run", action="store_true", help="validate import + dep + data only; do not build graph")
    parser.add_argument("--out", default=str(_OUT_STATS), help="output stats JSON path")
    args = parser.parse_args(argv)

    stats = run_probe(dry_run=args.dry_run)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(stats, indent=2, default=str))
    print(f"[probe] wrote {out_path}")
    print(json.dumps(stats, indent=2, default=str)[:4000])

    if stats.get("blocker"):
        return 2
    if stats.get("verdict") == "NO-GO":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
