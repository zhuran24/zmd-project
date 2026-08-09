"""Phase 0 cheap-gate probe for SMT Modulo Monotonic Theories (SMT-MT) outer pruning.

Hypothesis (monotone property):
    if ghost_A is INFEASIBLE (266 facility can't fit when ghost_A is reserved
    empty), then any ghost_B that geometrically *contains* ghost_A is also
    INFEASIBLE. So one INFEASIBLE inner verdict can prune the whole containing
    superset in O(query) without re-running the inner solver.

This Phase 0 mocks the inner solver (random/threshold-based Dummy) and measures
whether the monotone-pruning yield is high enough to justify Phase 1+
investment.

Hard constraints (per task spec):
- No src/ edits.
- Reuses outer_search.generate_candidate_sizes for (w, h) enumeration logic
  (replicated locally to keep the probe import-light), then explicitly
  enumerates anchors (anchor_x, anchor_y) on the 70x70 grid to form the SMT-MT
  candidate registry (size + position = full 4-tuple).
- Reads no other Phase 0 dirs / GPT v12 plan to avoid contamination.

Outputs phase0_metrics.json with m1..m6 plus per-bucket breakdown.

Usage:
    python -u docs/research/smt_mt_outer_pruning_phase0_20260521/phase0_probe.py \
        --dry-run
    python -u docs/research/smt_mt_outer_pruning_phase0_20260521/phase0_probe.py \
        --infeasible-trials 1000 --seed 42
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None  # type: ignore

try:
    from rtree import index as rtree_index  # type: ignore
except ImportError as exc:  # pragma: no cover
    print(f"FATAL: rtree not importable ({exc}); pip install rtree", file=sys.stderr)
    raise SystemExit(2)


# ---------------------------------------------------------------------------
# Domain constants (must match src/search/outer_search.py:generate_candidate_sizes)
# ---------------------------------------------------------------------------
GRID_W: int = 70
GRID_H: int = 70
MIN_SIDE: int = 6


# ---------------------------------------------------------------------------
# Candidate enumeration (replicates outer_search.generate_candidate_sizes logic
# for (w, h) and adds explicit (anchor_x, anchor_y) for SMT-MT containment).
# ---------------------------------------------------------------------------
def enumerate_size_pairs(
    *, grid_w: int = GRID_W, grid_h: int = GRID_H, min_side: int = MIN_SIDE
) -> List[Tuple[int, int]]:
    """Reproduces outer_search.generate_candidate_sizes (w, h) enumeration.

    Source-of-truth: outer_search.py L240-261 (read-only).
    Pairs satisfy w >= h to avoid duplicate orientation per the upstream loop;
    SMT-MT containment is orientation-agnostic so this is fine for Phase 0.
    """
    pairs: List[Tuple[int, int]] = []
    for w in range(min_side, grid_w + 1):
        for h in range(min_side, min(grid_h, w) + 1):
            pairs.append((w, h))
    return pairs


def enumerate_candidates(
    *, grid_w: int = GRID_W, grid_h: int = GRID_H, min_side: int = MIN_SIDE
) -> List[Tuple[int, int, int, int]]:
    """Full SMT-MT candidate registry: (w, h, anchor_x, anchor_y).

    Anchor is the bottom-left corner. Returned in deterministic order; the
    probe shuffles via a seeded RNG when sampling.
    """
    candidates: List[Tuple[int, int, int, int]] = []
    for w, h in enumerate_size_pairs(grid_w=grid_w, grid_h=grid_h, min_side=min_side):
        for ay in range(grid_h - h + 1):
            for ax in range(grid_w - w + 1):
                candidates.append((w, h, ax, ay))
    return candidates


# ---------------------------------------------------------------------------
# R-tree index: bbox = (ax, ay, ax + w, ay + h)
# ---------------------------------------------------------------------------
def build_rtree(
    candidates: Sequence[Tuple[int, int, int, int]],
) -> Tuple[rtree_index.Index, Dict[int, Tuple[int, int, int, int]]]:
    """Build a 2D R-tree keyed by an integer id and a side dict for bbox lookup.

    rtree.intersection() returns intersecting bboxes; we filter to true
    containment in Python (full containment is rare-enough that the
    intersection prefilter is fast).
    """
    rprops = rtree_index.Property()
    rprops.dimension = 2
    rprops.leaf_capacity = 100
    rprops.fill_factor = 0.7
    idx = rtree_index.Index(properties=rprops)
    bbox_by_id: Dict[int, Tuple[int, int, int, int]] = {}
    for cand_id, (w, h, ax, ay) in enumerate(candidates):
        bbox = (ax, ay, ax + w, ay + h)
        idx.insert(cand_id, bbox)
        bbox_by_id[cand_id] = bbox
    return idx, bbox_by_id


def query_containing(
    idx: rtree_index.Index,
    bbox_by_id: Dict[int, Tuple[int, int, int, int]],
    query_bbox: Tuple[int, int, int, int],
) -> List[int]:
    """Find all candidate ids whose bbox fully contains query_bbox."""
    qx0, qy0, qx1, qy1 = query_bbox
    hits = idx.intersection(query_bbox)
    containing: List[int] = []
    for hit_id in hits:
        bx0, by0, bx1, by1 = bbox_by_id[hit_id]
        if bx0 <= qx0 and by0 <= qy0 and bx1 >= qx1 and by1 >= qy1:
            containing.append(hit_id)
    return containing


# ---------------------------------------------------------------------------
# Dummy inner solver: mock INFEASIBLE/CERTIFIED verdict by area threshold.
# Large rects (more empty cells reserved -> less grid for facilities) are
# more likely INFEASIBLE; small rects are CERTIFIED.
# ---------------------------------------------------------------------------
def dummy_inner(
    w: int, h: int, ax: int, ay: int, rng: random.Random
) -> str:
    area = w * h
    if area >= 500:
        return "INFEASIBLE"
    if area <= 100:
        return "CERTIFIED"
    return rng.choice(["INFEASIBLE", "CERTIFIED"])


# ---------------------------------------------------------------------------
# Main probe loop
# ---------------------------------------------------------------------------
def _rss_gb() -> float:
    if psutil is None:
        return -1.0
    return psutil.Process().memory_info().rss / (1024**3)


def run_probe(
    *,
    infeasible_trials: int,
    seed: int,
    dry_run: bool,
    output_dir: Path,
) -> Dict[str, object]:
    rng = random.Random(seed)
    t0 = time.perf_counter()

    print(f"[probe] enumerating candidates (grid={GRID_W}x{GRID_H}, min_side={MIN_SIDE})")
    candidates = enumerate_candidates()
    m1_total_candidates = len(candidates)
    t_enum = time.perf_counter() - t0
    print(f"[probe] m1_total_candidates = {m1_total_candidates} (enum {t_enum:.2f}s)")

    if dry_run:
        # Toy sanity test of containment query
        toy_candidates = [(10, 10, 0, 0), (20, 20, 0, 0), (8, 8, 1, 1)]
        toy_idx, toy_bbox = build_rtree(toy_candidates)
        # ghost_A = (10,10,0,0) -> bbox (0,0,10,10)
        # who contains it? (20,20,0,0) bbox (0,0,20,20) yes; itself yes; (8,8,1,1) no
        hits = query_containing(toy_idx, toy_bbox, (0, 0, 10, 10))
        toy_ok = sorted(hits) == sorted([0, 1])  # id 0 self + id 1 superset
        print(f"[dry-run] toy containment query hits ids {sorted(hits)} expected [0, 1] -> OK={toy_ok}")
        print(f"[dry-run] candidate sample[0:3]: {candidates[:3]}")
        print(f"[dry-run] candidate sample[-3:]: {candidates[-3:]}")
        print(f"[dry-run] RSS now: {_rss_gb():.3f} GB")
        sample_rng = random.Random(seed)
        verdicts = [dummy_inner(w, h, ax, ay, sample_rng) for (w, h, ax, ay) in candidates[:5]]
        print(f"[dry-run] dummy_inner sample[0:5] verdicts: {verdicts}")
        return {"dry_run": True, "m1_total_candidates": m1_total_candidates, "toy_ok": toy_ok}

    print(f"[probe] building R-tree index over {m1_total_candidates} candidates")
    t_build_start = time.perf_counter()
    rss_before = _rss_gb()
    idx, bbox_by_id = build_rtree(candidates)
    m4_rtree_build_seconds = time.perf_counter() - t_build_start
    rss_after = _rss_gb()
    m5_rtree_rss_gb = max(0.0, rss_after - rss_before)
    print(f"[probe] m4_rtree_build_seconds = {m4_rtree_build_seconds:.2f}s")
    print(f"[probe] m5_rtree_rss_gb (delta) = {m5_rtree_rss_gb:.3f} GB (abs={rss_after:.3f})")

    # Pruning state: each candidate id either UNLABELED, CERTIFIED, INFEASIBLE.
    # SMT-MT rule: on INFEASIBLE for ghost_A, mark all containing candidates INFEASIBLE.
    labels: List[str] = ["UNLABELED"] * m1_total_candidates
    pruned_via_monotone: int = 0
    direct_infeasible: int = 0
    direct_certified: int = 0
    monotone_query_walls_ms: List[float] = []

    # Bucket counters for m6 (area buckets)
    def _bucket(w: int, h: int) -> str:
        a = w * h
        if a >= 2000:
            return ">=2000"
        if a >= 1000:
            return "1000-1999"
        if a >= 500:
            return "500-999"
        if a >= 200:
            return "200-499"
        return "<200"

    bucket_total: Dict[str, int] = {}
    bucket_pruned: Dict[str, int] = {}
    for w, h, _, _ in candidates:
        b = _bucket(w, h)
        bucket_total[b] = bucket_total.get(b, 0) + 1

    # Random sampling of trial candidates (only sample UNLABELED ones to mimic
    # outer-search live behavior)
    unlabeled_ids = list(range(m1_total_candidates))
    rng.shuffle(unlabeled_ids)

    trial_idx = 0
    t_loop_start = time.perf_counter()
    for cand_id in unlabeled_ids:
        if trial_idx >= infeasible_trials:
            break
        if labels[cand_id] != "UNLABELED":
            continue
        w, h, ax, ay = candidates[cand_id]
        verdict = dummy_inner(w, h, ax, ay, rng)
        trial_idx += 1
        if verdict == "CERTIFIED":
            labels[cand_id] = "CERTIFIED"
            direct_certified += 1
            continue
        direct_infeasible += 1
        labels[cand_id] = "INFEASIBLE"
        # Monotone propagation: query containment
        qbbox = (ax, ay, ax + w, ay + h)
        tq0 = time.perf_counter()
        containing = query_containing(idx, bbox_by_id, qbbox)
        monotone_query_walls_ms.append((time.perf_counter() - tq0) * 1000.0)
        for hit_id in containing:
            if labels[hit_id] == "UNLABELED":
                labels[hit_id] = "INFEASIBLE"
                pruned_via_monotone += 1
                cw, ch, _, _ = candidates[hit_id]
                b = _bucket(cw, ch)
                bucket_pruned[b] = bucket_pruned.get(b, 0) + 1

    t_loop = time.perf_counter() - t_loop_start

    # Metrics summary
    total_labeled = direct_infeasible + direct_certified + pruned_via_monotone
    m2_prune_ratio = (pruned_via_monotone + direct_infeasible) / max(1, m1_total_candidates)
    sorted_walls = sorted(monotone_query_walls_ms)
    p50 = sorted_walls[len(sorted_walls) // 2] if sorted_walls else 0.0
    p95 = sorted_walls[int(len(sorted_walls) * 0.95)] if sorted_walls else 0.0
    p99 = sorted_walls[int(len(sorted_walls) * 0.99)] if sorted_walls else 0.0
    m3_query_p95_ms = p95

    # GO/NO-GO check
    go = (
        m2_prune_ratio >= 0.50
        and m3_query_p95_ms <= 1000.0
        and m4_rtree_build_seconds <= 60.0
        and m5_rtree_rss_gb <= 2.0
    )
    no_go = (
        m2_prune_ratio < 0.30
        or m3_query_p95_ms > 5000.0
        or m5_rtree_rss_gb > 8.0
    )

    metrics: Dict[str, object] = {
        "schema_version": 1,
        "phase": "phase0",
        "paradigm": "smt_mt_outer_pruning",
        "seed": seed,
        "infeasible_trials_requested": infeasible_trials,
        "trials_executed": trial_idx,
        "m1_total_candidates": m1_total_candidates,
        "m2_prune_ratio_after_trials": m2_prune_ratio,
        "m2_pruned_via_monotone": pruned_via_monotone,
        "m2_direct_infeasible": direct_infeasible,
        "m2_direct_certified": direct_certified,
        "m2_total_labeled": total_labeled,
        "m3_containment_query_p50_ms": p50,
        "m3_containment_query_p95_ms": p95,
        "m3_containment_query_p99_ms": p99,
        "m3_containment_query_count": len(monotone_query_walls_ms),
        "m4_rtree_build_seconds": m4_rtree_build_seconds,
        "m5_rtree_rss_gb_delta": m5_rtree_rss_gb,
        "m5_rtree_rss_gb_absolute": rss_after,
        "m6_prune_by_area_bucket": {
            b: {
                "total": bucket_total.get(b, 0),
                "pruned": bucket_pruned.get(b, 0),
                "pruned_ratio": (
                    bucket_pruned.get(b, 0) / max(1, bucket_total.get(b, 0))
                ),
            }
            for b in ["<200", "200-499", "500-999", "1000-1999", ">=2000"]
        },
        "go": bool(go),
        "no_go": bool(no_go),
        "verdict": "GO" if go else ("NO-GO" if no_go else "MIXED"),
        "trial_loop_seconds": t_loop,
        "total_wall_seconds": time.perf_counter() - t0,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "phase0_metrics.json"
    out_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    print(f"[probe] wrote {out_path}")
    print(f"[probe] VERDICT={metrics['verdict']} prune_ratio={m2_prune_ratio:.3f} "
          f"p95={p95:.2f}ms build={m4_rtree_build_seconds:.1f}s rss_delta={m5_rtree_rss_gb:.3f}GB")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip full measurement; verify imports, candidate enum, R-tree toy.")
    parser.add_argument("--infeasible-trials", type=int, default=1000,
                        help="Number of Dummy verdicts to sample (default 1000).")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility.")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parent,
                        help="Directory to write phase0_metrics.json into.")
    args = parser.parse_args()

    metrics = run_probe(
        infeasible_trials=args.infeasible_trials,
        seed=args.seed,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )
    if args.dry_run:
        print("[dry-run] complete; no metrics file written")
        return 0
    return 0 if not metrics.get("no_go", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
