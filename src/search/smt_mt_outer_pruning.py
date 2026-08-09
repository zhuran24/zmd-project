"""SMT-MT (SAT Modulo Monotonic Theories) outer-search pruning engine.

Phase 1 of the SMT-MT outer pruning paradigm investigation (commits leading
up to 2026-05-21). Phase 0 cheap gate (~360 LOC standalone probe under
``docs/research/smt_mt_outer_pruning_phase0_20260521/``) measured a 76.7%
monotone prune ratio on a Dummy inner oracle over 2.35M (w, h, anchor)
candidates with R-tree containment queries in p95 = 293ms. GO 8/8.

Phase 1 wires the monotone propagation into ``outer_search.run_outer_search``
behind ``EXACT_SMT_MT_OUTER_PRUNING`` env flag. The outer loop enumerates
candidates as ``(area, w, h)`` size-only triples (anchor selection is
delegated to the inner solver), so this engine indexes candidates by their
``(w, h)`` size pair.

Monotone property (textbook 2D-poset upper-set closure):

    if ghost (w, h) is INFEASIBLE, then any (w', h') with w' >= w and h' >= h
    is also INFEASIBLE.

Reason: a larger ghost rectangle reserves more empty cells, leaving fewer
cells for the 266 mandatory facilities, so geometric containment monotonically
preserves infeasibility. PROJECT_LOCK forbids any positive non-monotone
constraint in certified mode (the ghost-rect has no exterior-path
requirement, no "we want room for power poles" reservation, etc.), so
monotonicity is sound in certified_exact mode.

The engine is shadow-friendly: it never modifies certification semantics,
never writes proof artifacts, and is fully env-gated. Off by default.

Interface:

    engine = OuterPruningEngine.build(candidates)
    engine.notify_infeasible(w, h)          # call when inner returns INFEASIBLE
    pruned_keys = engine.pruned_candidate_keys()  # set of "WxH" strings
    engine.write_telemetry(path)            # JSONL-style telemetry dump

Engine acts as a *centralized log + R-tree index*; the existing
``_compute_exact_frontier_state`` size-level monotone check
(``any(ghost_w >= inf_w and ghost_h >= inf_h)``) continues to drive frontier
pruning. SMT-MT engine's job in Phase 1 is to:

1. Record monotone propagation per INFEASIBLE verdict via R-tree (O(log N)
   query vs O(N) linear scan in the frontier helper) for telemetry.
2. Provide a clean callable surface for Phase 2+ when we may extend outer
   to (w, h, anchor) enumeration, where the centralized R-tree becomes the
   only practical lookup.
3. Surface metrics (real prune ratio, query wall, RSS) to verify Phase 0
   numbers hold with the real B1 inner solver.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Env flag — Phase 1 default OFF. Existing outer_search behavior unchanged
# when the engine is not constructed (helpers below all early-return).
# ---------------------------------------------------------------------------
ENV_SMT_MT_OUTER_PRUNING: str = "EXACT_SMT_MT_OUTER_PRUNING"


def is_enabled() -> bool:
    """Return True iff EXACT_SMT_MT_OUTER_PRUNING is set to a truthy value."""
    raw = os.environ.get(ENV_SMT_MT_OUTER_PRUNING, "")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Candidate key helper. Mirrors outer_search._candidate_key (without import
# cycle): "{w}x{h}" string.
# ---------------------------------------------------------------------------
def candidate_key(w: int, h: int) -> str:
    return f"{int(w)}x{int(h)}"


@dataclass
class EngineMetrics:
    """Aggregate telemetry collected over the lifetime of one OuterPruningEngine.

    Fields are append-only; ``snapshot()`` returns a JSON-safe dict.
    """

    candidate_count: int = 0
    rtree_build_seconds: float = 0.0
    rtree_build_rss_delta_gb: float = 0.0
    infeasible_notifications: int = 0
    monotone_query_count: int = 0
    monotone_query_walls_ms: List[float] = field(default_factory=list)
    total_pruned_unique: int = 0
    per_event_log: List[Dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> Dict[str, Any]:
        walls = sorted(self.monotone_query_walls_ms)
        p50 = walls[len(walls) // 2] if walls else 0.0
        p95 = walls[int(len(walls) * 0.95)] if walls else 0.0
        p99 = walls[int(len(walls) * 0.99)] if walls else 0.0
        return {
            "schema_version": 1,
            "paradigm": "smt_mt_outer_pruning",
            "phase": "phase1",
            "candidate_count": int(self.candidate_count),
            "rtree_build_seconds": float(self.rtree_build_seconds),
            "rtree_build_rss_delta_gb": float(self.rtree_build_rss_delta_gb),
            "infeasible_notifications": int(self.infeasible_notifications),
            "monotone_query_count": int(self.monotone_query_count),
            "monotone_query_p50_ms": float(p50),
            "monotone_query_p95_ms": float(p95),
            "monotone_query_p99_ms": float(p99),
            "total_pruned_unique": int(self.total_pruned_unique),
            "real_prune_ratio": (
                float(self.total_pruned_unique) / float(max(1, self.candidate_count))
            ),
            "per_event_log": [dict(entry) for entry in self.per_event_log],
        }


class OuterPruningEngine:
    """R-tree-backed monotone containment engine for size-only ghost candidates.

    The R-tree indexes 2D bboxes ``(w, h, w, h)`` — degenerate boxes
    interpreted as points, since each candidate is a single (w, h) size.
    To query "all candidates (w', h') with w' >= w and h' >= h" we use the
    rtree intersection with the upper-right quadrant bbox
    ``(w, h, +infinity, +infinity)``; rtree handles open intervals via a
    large sentinel (GRID_MAX_SENTINEL).

    The engine is stateful: ``notify_infeasible`` records the verdict and
    triggers a containment query that propagates the INFEASIBLE label to
    the entire upper set. ``pruned_candidate_keys()`` returns the union of
    all propagated keys including the original notification.
    """

    # rtree expects finite bboxes; pick a sentinel larger than the 70x70 grid
    # but still well within float bounds.
    GRID_MAX_SENTINEL: int = 10_000

    def __init__(
        self,
        *,
        candidates: Sequence[Tuple[int, int, int]],
        rtree_index: Any,
        bbox_by_id: Dict[int, Tuple[int, int, int, int]],
        key_by_id: Dict[int, str],
        metrics: EngineMetrics,
    ) -> None:
        self._candidates: List[Tuple[int, int, int]] = [tuple(c) for c in candidates]
        self._rtree_index = rtree_index
        self._bbox_by_id = dict(bbox_by_id)
        self._key_by_id = dict(key_by_id)
        self._pruned_keys: set[str] = set()
        self._directly_infeasible_keys: set[str] = set()
        self._metrics: EngineMetrics = metrics

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def build(
        cls,
        candidates: Sequence[Tuple[int, int, int]],
    ) -> "OuterPruningEngine":
        """Construct an engine from outer_search.generate_candidate_sizes output.

        ``candidates`` is a list of ``(area, w, h)`` triples; we discard area
        and index by ``(w, h)``.
        """
        # Lazy rtree import so module loads even when rtree is unavailable;
        # engine is only built when the env flag is on so the import lands.
        from rtree import index as rtree_index_mod  # type: ignore

        try:
            import psutil  # type: ignore
        except ImportError:  # pragma: no cover
            psutil = None  # type: ignore

        rss_before = 0.0
        if psutil is not None:
            rss_before = psutil.Process().memory_info().rss / (1024**3)

        props = rtree_index_mod.Property()
        props.dimension = 2
        props.leaf_capacity = 100
        props.fill_factor = 0.7
        idx = rtree_index_mod.Index(properties=props)
        bbox_by_id: Dict[int, Tuple[int, int, int, int]] = {}
        key_by_id: Dict[int, str] = {}

        t0 = time.perf_counter()
        for cand_id, candidate in enumerate(candidates):
            _area, w, h = candidate
            bbox = (int(w), int(h), int(w), int(h))
            idx.insert(cand_id, bbox)
            bbox_by_id[cand_id] = bbox
            key_by_id[cand_id] = candidate_key(int(w), int(h))
        build_seconds = time.perf_counter() - t0

        rss_after = 0.0
        if psutil is not None:
            rss_after = psutil.Process().memory_info().rss / (1024**3)

        metrics = EngineMetrics(
            candidate_count=len(candidates),
            rtree_build_seconds=float(build_seconds),
            rtree_build_rss_delta_gb=max(0.0, rss_after - rss_before),
        )
        return cls(
            candidates=candidates,
            rtree_index=idx,
            bbox_by_id=bbox_by_id,
            key_by_id=key_by_id,
            metrics=metrics,
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------
    def notify_infeasible(self, w: int, h: int) -> List[str]:
        """Record an INFEASIBLE verdict for ghost (w, h) and propagate.

        Returns the list of *newly* pruned candidate keys (excluding ones
        already pruned). The notification candidate itself is included in
        the returned list iff it wasn't already pruned.
        """
        w_i = int(w)
        h_i = int(h)
        key_self = candidate_key(w_i, h_i)

        # Query upper-right quadrant: w' >= w AND h' >= h
        query_bbox = (w_i, h_i, self.GRID_MAX_SENTINEL, self.GRID_MAX_SENTINEL)
        t0 = time.perf_counter()
        hit_ids = list(self._rtree_index.intersection(query_bbox))
        # Filter to true containment in case of degenerate edges
        containing_ids: List[int] = []
        for hit_id in hit_ids:
            bx0, by0, _bx1, _by1 = self._bbox_by_id[hit_id]
            if bx0 >= w_i and by0 >= h_i:
                containing_ids.append(hit_id)
        wall_ms = (time.perf_counter() - t0) * 1000.0

        newly_pruned: List[str] = []
        for hit_id in containing_ids:
            key = self._key_by_id[hit_id]
            if key not in self._pruned_keys:
                self._pruned_keys.add(key)
                newly_pruned.append(key)

        # Always mark the notified candidate as directly infeasible.
        self._directly_infeasible_keys.add(key_self)

        self._metrics.infeasible_notifications += 1
        self._metrics.monotone_query_count += 1
        self._metrics.monotone_query_walls_ms.append(wall_ms)
        self._metrics.total_pruned_unique = len(self._pruned_keys)
        self._metrics.per_event_log.append(
            {
                "trigger_w": w_i,
                "trigger_h": h_i,
                "trigger_key": key_self,
                "newly_pruned_count": int(len(newly_pruned)),
                "query_wall_ms": float(wall_ms),
                "cumulative_pruned": int(len(self._pruned_keys)),
            }
        )
        return newly_pruned

    def is_pruned(self, w: int, h: int) -> bool:
        """Check whether (w, h) has been marked INFEASIBLE via monotone propagation."""
        return candidate_key(int(w), int(h)) in self._pruned_keys

    def pruned_candidate_keys(self) -> set[str]:
        """Return the full set of pruned candidate keys (frozen view)."""
        return set(self._pruned_keys)

    def directly_infeasible_keys(self) -> set[str]:
        return set(self._directly_infeasible_keys)

    def metrics_snapshot(self) -> Dict[str, Any]:
        return self._metrics.snapshot()

    # ------------------------------------------------------------------
    # Telemetry persistence
    # ------------------------------------------------------------------
    def write_telemetry(self, output_path: Path) -> Path:
        """Write metrics snapshot to ``output_path`` (JSON) atomically.

        Path follows ``.artifacts/smt_mt_outer_pruning/<filename>.json`` by
        convention; caller controls exact name.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = self.metrics_snapshot()
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        tmp_path.replace(output_path)
        return output_path


# ---------------------------------------------------------------------------
# Convenience helpers for outer_search integration
# ---------------------------------------------------------------------------
def maybe_build_engine(
    candidates: Sequence[Tuple[int, int, int]],
) -> Optional[OuterPruningEngine]:
    """Build engine iff env-gate is on. Returns None when off."""
    if not is_enabled():
        return None
    return OuterPruningEngine.build(candidates)


def maybe_notify_infeasible(
    engine: Optional[OuterPruningEngine],
    w: int,
    h: int,
) -> List[str]:
    """No-op if engine is None; else propagate and return newly pruned keys."""
    if engine is None:
        return []
    return engine.notify_infeasible(int(w), int(h))


def maybe_write_telemetry(
    engine: Optional[OuterPruningEngine],
    project_root: Path,
    *,
    wave_index: int,
) -> Optional[Path]:
    """Write telemetry snapshot if engine is not None.

    Output: ``.artifacts/smt_mt_outer_pruning/phase1_metrics_wave_{idx:04d}.json``.
    """
    if engine is None:
        return None
    output_dir = project_root / ".artifacts" / "smt_mt_outer_pruning"
    output_path = output_dir / f"phase1_metrics_wave_{int(wave_index):04d}.json"
    return engine.write_telemetry(output_path)
