"""B4 active filter Hybrid mock loop — pure-Python no-solve sizing test.

Per MERGER §5.4 G11 (round 3 fix):
- Hybrid score = activity_count - 0.1 × age_decay
- 10 iter mock loop, each iter:
  - Simulate cut activity increment (random subset of cuts fire +1 activity)
  - Simulate age increment (all cuts +1 age)
  - Recompute Hybrid score for all cuts
  - Sort + filter (top-K retained)
  - filter wall ≤ 100ms per iter
- Eviction trigger fires when mock cut count > 50K OR mock RSS > 4.5 GB
- Does NOT call CP-SAT solve — pure structural age accumulation test
  (per Gemini round 3 HIGH: single build/solve architecture age永0,
  age_decay物理失效, 必须模拟 multi-iter age 累积才能验 age_decay 逻辑).

This file is spike-only. Off-limits paths untouched.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple


# ============================================================================
# Mock cut representation
# ============================================================================


@dataclass
class MockCut:
    cut_id: int
    family: str
    activity: int = 0
    age: int = 0
    # Approximate body footprint (literals); used for mock RSS estimate.
    body_size: int = 4

    @property
    def hybrid_score(self) -> float:
        return float(self.activity) - 0.1 * float(self.age)


# ============================================================================
# Filter loop report
# ============================================================================


@dataclass
class FilterIterReport:
    iter_idx: int
    n_cuts_in: int
    n_cuts_out: int
    n_evicted: int
    eviction_trigger_fired: bool
    filter_wall_s: float
    mock_rss_gb: float


@dataclass
class FilterLoopReport:
    n_iter: int
    iter_reports: List[FilterIterReport] = field(default_factory=list)
    total_wall_s: float = 0.0
    max_iter_wall_s: float = 0.0
    eviction_count: int = 0
    eviction_triggered_in_iter: List[int] = field(default_factory=list)
    final_cut_count: int = 0

    @property
    def per_iter_wall_pass(self) -> bool:
        return self.max_iter_wall_s <= 0.100  # 100 ms per iter

    @property
    def total_wall_pass(self) -> bool:
        return self.total_wall_s <= 1.000  # 1 s for 10 iter

    @property
    def eviction_fired_without_crash(self) -> bool:
        return self.eviction_count >= 1 or not self.iter_reports

    @property
    def g11_pass(self) -> bool:
        return (
            self.per_iter_wall_pass
            and self.total_wall_pass
            and self.eviction_fired_without_crash
        )

    def format_human(self) -> str:
        verdict = "G11 PASS" if self.g11_pass else "G11 FAIL"
        lines = [f"filter mock loop — {verdict}"]
        lines.append(f"  n_iter             = {self.n_iter}")
        lines.append(f"  total_wall         = {self.total_wall_s:.4f}s  (≤ 1.000s required)")
        lines.append(f"  max_iter_wall      = {self.max_iter_wall_s:.4f}s  (≤ 0.100s per iter)")
        lines.append(f"  eviction_count     = {self.eviction_count}")
        lines.append(f"  eviction_iter(s)   = {self.eviction_triggered_in_iter}")
        lines.append(f"  final_cut_count    = {self.final_cut_count}")
        for ir in self.iter_reports:
            evict_marker = " *EVICTED*" if ir.eviction_trigger_fired else ""
            lines.append(
                f"  iter {ir.iter_idx}: cuts {ir.n_cuts_in}→{ir.n_cuts_out} "
                f"(evicted {ir.n_evicted}), wall {ir.filter_wall_s*1000:.1f}ms, "
                f"rss_est {ir.mock_rss_gb:.2f}GB{evict_marker}"
            )
        return "\n".join(lines)


# ============================================================================
# Mock RSS estimator
# ============================================================================


def estimate_mock_rss_gb(n_cuts: int, avg_body_size: int = 4) -> float:
    """Estimate ~RSS impact of cut count.

    Per ``17_workflow_telemetry`` rough number: ~50-100 KB per active cut at
    100K cut budget. Conservative: use 80 KB / cut for mock to make
    eviction trigger reachable in 10-iter test.
    """
    per_cut_bytes = 80 * 1024
    return (n_cuts * per_cut_bytes) / (1024**3)


# ============================================================================
# Hybrid filter — sort by score, retain top-K
# ============================================================================


def hybrid_filter(
    cuts: List[MockCut],
    top_k: int,
) -> Tuple[List[MockCut], List[MockCut]]:
    """Return (retained, evicted). Retained = top_k by Hybrid score."""
    cuts_sorted = sorted(cuts, key=lambda c: c.hybrid_score, reverse=True)
    retained = cuts_sorted[:top_k]
    evicted = cuts_sorted[top_k:]
    return retained, evicted


# ============================================================================
# Main loop
# ============================================================================


def run_filter_mock_loop(
    *,
    n_iter: int = 10,
    initial_cuts: int = 10_000,
    growth_per_iter: int = 6_000,
    activity_fire_rate: float = 0.3,
    eviction_cut_threshold: int = 50_000,
    eviction_rss_threshold_gb: float = 4.5,
    eviction_target_size: int = 30_000,
    rng_seed: int = 42,
) -> FilterLoopReport:
    """Run 10-iter mock filter loop and report G11 metrics."""
    rng = random.Random(rng_seed)
    next_cut_id = 0
    cuts: List[MockCut] = []
    families = ("F1", "F2", "F4", "F5", "F6", "F7", "F8", "F9")

    # Seed with initial cuts (age 0, activity random small).
    for _ in range(initial_cuts):
        cuts.append(MockCut(
            cut_id=next_cut_id,
            family=rng.choice(families),
            activity=rng.randint(0, 2),
            age=0,
            body_size=rng.randint(2, 8),
        ))
        next_cut_id += 1

    report = FilterLoopReport(n_iter=n_iter)
    t_overall = time.monotonic()

    for it in range(n_iter):
        t_iter = time.monotonic()

        # Inject new cuts (simulate this iter's oracle emit).
        for _ in range(growth_per_iter):
            cuts.append(MockCut(
                cut_id=next_cut_id,
                family=rng.choice(families),
                activity=0,
                age=0,
                body_size=rng.randint(2, 8),
            ))
            next_cut_id += 1

        # Age tick: all cuts +1 age.
        for c in cuts:
            c.age += 1

        # Activity fire: random subset gets +1 activity.
        n_fire = int(len(cuts) * activity_fire_rate)
        if n_fire > 0:
            for c in rng.sample(cuts, n_fire):
                c.activity += 1

        # Estimate RSS.
        mock_rss = estimate_mock_rss_gb(len(cuts))
        cuts_in = len(cuts)

        # Eviction trigger check.
        eviction_triggered = False
        n_evicted = 0
        if cuts_in > eviction_cut_threshold or mock_rss > eviction_rss_threshold_gb:
            retained, evicted = hybrid_filter(cuts, top_k=eviction_target_size)
            cuts = retained
            n_evicted = len(evicted)
            eviction_triggered = True
            report.eviction_count += 1
            report.eviction_triggered_in_iter.append(it)
        else:
            # Even without trigger we apply Hybrid filter cost (sort by score)
            # so wall is representative.
            cuts.sort(key=lambda c: c.hybrid_score, reverse=True)

        cuts_out = len(cuts)
        wall = time.monotonic() - t_iter
        report.iter_reports.append(FilterIterReport(
            iter_idx=it,
            n_cuts_in=cuts_in,
            n_cuts_out=cuts_out,
            n_evicted=n_evicted,
            eviction_trigger_fired=eviction_triggered,
            filter_wall_s=wall,
            mock_rss_gb=mock_rss,
        ))
        if wall > report.max_iter_wall_s:
            report.max_iter_wall_s = wall

    report.total_wall_s = time.monotonic() - t_overall
    report.final_cut_count = len(cuts)
    return report


if __name__ == "__main__":
    rep = run_filter_mock_loop()
    print(rep.format_human())
    raise SystemExit(0 if rep.g11_pass else 1)
