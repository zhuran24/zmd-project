"""B2 scale ramp — 81K BoolVar toy master × {0, 1K, 10K, 50K, 100K} cuts.

Per MERGER §5.4 G1-G9:
- G1: 81K BoolVar + 0 cut build ≤ 10s
- G2: 81K + 1K cut build ≤ 20s
- G3: 81K + 10K cut build ≤ 30s
- G4: 81K + 50K cut build ≤ 300s
- G4b: 81K + 100K cut build ≤ 600s
- G5: 0 cut feasibility ≤ 30s
- G7: 100K solve wall measure (no hard cap; INFEASIBLE allowed unless wall
  ≤ 1s + INFEASIBLE → N2 trigger)
- G8: RSS peak ≤ 20 GB (100K 挡位必 measure)
- G9: proto ≤ 500 MB @ 50K, ≤ 1 GB @ 100K
- N3: G8 RSS > 30 GB

Cut source: A3 fixture jsonl (50 cert after F3 special-case rerun). For ramps
> 50, oversample with replacement using deterministic seed.

This file is spike-only. Off-limits paths untouched.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ortools.sat.python import cp_model

def _resolve_repo_root() -> Path:
    """Return the project root in production and review-mirror layouts.

    Production modules live under project/scripts/spike_prod_scale_lib/.
    Review-package mirrors live under project/code_context/spike/spike_prod_scale_lib/.
    """
    here = Path(__file__).resolve()
    candidates = (here.parent.parent.parent, here.parent.parent.parent.parent)
    for root in candidates:
        if (root / "data" / "preprocessed" / "candidate_placements.json").exists() and (root / "src").is_dir():
            return root
    return candidates[0]


REPO_ROOT = _resolve_repo_root()
sys.path.insert(0, str(REPO_ROOT))

from scripts.spike_prod_scale_lib.telemetry import (  # noqa: E402
    TelemetryBuffer,
    emit_dark_matter,
    emit_proto_sample,
    emit_rss_after_solve,
)
from scripts.spike_prod_scale_lib.toy_translator import (  # noqa: E402
    PoseRegistry,
    build_toy_master,
    load_pose_registry,
    measure_proto_bytesize,
    translate_certs_to_constraints,
)


FIXTURE_PATH = REPO_ROOT / "data" / "cuts" / "spike" / "oracle_emit_fixture_45cert.jsonl"


# ============================================================================
# G criteria thresholds
# ============================================================================


G_THRESHOLDS = {
    "G1_build_0cut_s":      10.0,
    "G2_build_1K_s":        20.0,
    "G3_build_10K_s":       30.0,
    "G4_build_50K_s":      300.0,
    "G4b_build_100K_s":    600.0,
    "G5_solve_0cut_s":      30.0,
    "G8_rss_peak_gb":       20.0,
    "N3_rss_critical_gb":   30.0,
    "G9_proto_50K_mb":     500.0,
    "G9_proto_100K_mb":   1024.0,
    "G6b_random_min_wall_s": 1.0,  # < 1s + INFEASIBLE = N2 trigger
}


# ============================================================================
# Cut sampling — oversample with replacement to hit ramp size
# ============================================================================


def load_fixture_certs(path: Path = FIXTURE_PATH) -> List[dict]:
    """Load all cert records from A3 jsonl."""
    if not path.exists():
        raise FileNotFoundError(f"A3 fixture not found: {path}")
    out: List[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def oversample_certs(certs: List[dict], target_count: int, seed: int = 0xC0FFEE) -> List[dict]:
    """Sample with replacement to land at target_count.

    Each draw modifies the ``cut_id`` to make it unique (so translator
    treats each draw as a new cert and emits a new constraint).
    """
    rng = random.Random(seed)
    out: List[dict] = []
    for i in range(target_count):
        base = rng.choice(certs)
        rec = dict(base)
        rec["cut_id"] = f"{base.get('cut_id', 'unk')}__draw{i}"
        out.append(rec)
    return out


# ============================================================================
# Per-tier measurement
# ============================================================================


@dataclass
class RampTierReport:
    tier_label: str
    cut_count_target: int
    cut_count_applied: int
    n_vars: int
    n_constraints_total: int  # demand + translated cuts
    build_wall_s: float
    translation_wall_s: float
    proto_bytesize: int
    rss_peak_gb_during_build: float
    solve_wall_s: float
    solve_status_label: str
    rss_peak_gb_after_solve: float
    notes: List[str] = field(default_factory=list)
    # v24 (v23 外审 F5): 暴露 translator 的 unknown-pose remap, 让 cut_count_applied 不再
    # 静默掩盖 "literal 没绑真 registry"。n_pairs_remapped > 0 => applied 是 synthetic/remap
    # 吞吐量, 不是真 registry-bound cut-body sizing。
    n_pairs_total: int = 0
    n_pairs_remapped: int = 0
    per_family_remapped: Dict[str, int] = field(default_factory=dict)

    @property
    def proto_mb(self) -> float:
        return self.proto_bytesize / (1024 ** 2)


@dataclass
class ScaleRampReport:
    tiers: List[RampTierReport] = field(default_factory=list)
    g_pass: Dict[str, bool] = field(default_factory=dict)
    n_trigger: Dict[str, bool] = field(default_factory=dict)
    raw_jsonl_path: Optional[Path] = None

    @property
    def all_g_pass(self) -> bool:
        return all(self.g_pass.values()) if self.g_pass else False

    @property
    def any_n_trigger(self) -> bool:
        return any(self.n_trigger.values())

    def format_human(self) -> str:
        verdict = "scale ramp DONE"
        lines = [f"{verdict}  (G_pass={self.g_pass}, N_trigger={self.n_trigger})"]
        for t in self.tiers:
            lines.append(
                f"  [{t.tier_label:>6}] vars={t.n_vars}, cons={t.n_constraints_total}, "
                f"build={t.build_wall_s:.2f}s, xlate={t.translation_wall_s:.2f}s, "
                f"solve={t.solve_wall_s:.2f}s ({t.solve_status_label}), "
                f"proto={t.proto_mb:.1f}MB, rss_peak={t.rss_peak_gb_during_build:.2f}GB"
            )
            for n in t.notes:
                lines.append(f"    note: {n}")
        return "\n".join(lines)


# ============================================================================
# RSS peak tracker (lightweight — sample inline at milestone points)
# ============================================================================


def _rss_gb_now() -> float:
    import psutil
    return psutil.Process(os.getpid()).memory_info().rss / (1024 ** 3)


# ============================================================================
# Single tier runner
# ============================================================================


def run_one_tier(
    tier_label: str,
    cut_count: int,
    registry: PoseRegistry,
    fixture_certs: List[dict],
    buf: TelemetryBuffer,
    solve_seconds_cap: float = 60.0,
) -> RampTierReport:
    """Build toy master + apply ``cut_count`` cuts + solve once."""
    notes: List[str] = []

    # Fresh registry vars (reset BoolVar list since we build a fresh model).
    registry.var_by_idx = []

    # Stage 1: build (vars + demand constraints).
    rss_before = _rss_gb_now()
    t0 = time.monotonic()
    model, build_rpt = build_toy_master(registry, add_demand_constraints=True)
    build_wall = time.monotonic() - t0
    rss_after_build = _rss_gb_now()

    emit_proto_sample(
        buf, f"{tier_label}_post_build_0cut",
        build_rpt.proto_bytesize,
        build_rpt.n_vars,
        build_rpt.n_demand_constraints,
    )

    # Stage 2: oversample certs to target cut_count + translate.
    if cut_count == 0:
        cut_records: List[dict] = []
    else:
        cut_records = oversample_certs(fixture_certs, cut_count)

    t1 = time.monotonic()
    tr_rpt = translate_certs_to_constraints(model, registry, cut_records)
    xlate_wall = time.monotonic() - t1
    rss_after_xlate = _rss_gb_now()

    n_constraints_total = build_rpt.n_demand_constraints + tr_rpt.n_constraints_added

    if tr_rpt.n_certs_skipped:
        notes.append(f"translator skipped {tr_rpt.n_certs_skipped} certs")
    if tr_rpt.n_pairs_remapped:
        notes.append(
            f"{tr_rpt.n_pairs_remapped}/{tr_rpt.n_pairs_total} pairs unknown-remapped "
            "(synthetic/remap throughput, NOT true registry-bound cut-body sizing)"
        )

    # Stage 3: proto size measurement (after all cuts applied — milestone).
    proto_size = measure_proto_bytesize(model)
    emit_proto_sample(
        buf, f"{tier_label}_post_cuts",
        proto_size,
        build_rpt.n_vars,
        n_constraints_total,
    )

    # Stage 4: solve (feasibility).
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solve_seconds_cap
    solver.parameters.num_search_workers = 1  # spike single-worker per MERGER
    t2 = time.monotonic()
    status = solver.Solve(model)
    solve_wall = time.monotonic() - t2
    # GPT pro v15 三审 finding 4: emit explicit RSS at solve completion so the
    # after-solve peak appears in raw telemetry (not only in
    # ``phase_b_results.json`` aggregated snapshot).
    import psutil as _psutil
    _proc = _psutil.Process(os.getpid())
    _mem = _proc.memory_info()
    rss_after_solve = _mem.rss / (1024 ** 3)
    emit_rss_after_solve(
        buf,
        tier=tier_label,
        rss_bytes=int(_mem.rss),
        vms_bytes=int(_mem.vms),
    )

    status_label = {
        cp_model.OPTIMAL:    "OPTIMAL",
        cp_model.FEASIBLE:   "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN:    "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
    }.get(status, f"status={status}")

    rss_peak_build = max(rss_before, rss_after_build, rss_after_xlate)
    rss_peak_solve = max(rss_peak_build, rss_after_solve)

    # Emit dark_matter on INFEASIBLE or UNKNOWN.
    if status in (cp_model.INFEASIBLE, cp_model.UNKNOWN):
        emit_dark_matter(
            buf,
            context=f"scale_ramp tier {tier_label}",
            status_label=status_label,
            wall_s=solve_wall,
            extra={
                "tier": tier_label,
                "cut_count_applied": tr_rpt.n_certs_applied,
                "n_constraints_total": n_constraints_total,
            },
        )

    return RampTierReport(
        tier_label=tier_label,
        cut_count_target=cut_count,
        cut_count_applied=tr_rpt.n_certs_applied,
        n_vars=build_rpt.n_vars,
        n_constraints_total=n_constraints_total,
        build_wall_s=build_wall,
        translation_wall_s=xlate_wall,
        proto_bytesize=proto_size,
        rss_peak_gb_during_build=rss_peak_build,
        solve_wall_s=solve_wall,
        solve_status_label=status_label,
        rss_peak_gb_after_solve=rss_peak_solve,
        notes=notes,
        n_pairs_total=tr_rpt.n_pairs_total,
        n_pairs_remapped=tr_rpt.n_pairs_remapped,
        per_family_remapped=dict(tr_rpt.per_family_remapped),
    )


# ============================================================================
# Full ramp runner — 0 / 1K / 10K / 50K / 100K
# ============================================================================


RAMP_TIERS = (
    ("0",    0),
    ("1K",   1_000),
    ("10K",  10_000),
    ("50K",  50_000),
    ("100K", 100_000),
)


def run_scale_ramp(
    *,
    fixture_path: Path = FIXTURE_PATH,
    out_jsonl: Optional[Path] = None,
    buf: Optional[TelemetryBuffer] = None,
    solve_seconds_cap: float = 60.0,
    tiers=RAMP_TIERS,
) -> ScaleRampReport:
    """Run scale ramp + verify G criteria."""
    if buf is None:
        # Standalone run: create a temp telemetry buffer.
        out_telemetry = REPO_ROOT / "data" / "cuts" / "spike" / f"telemetry_scale_ramp_{os.getpid()}.jsonl"
        buf = TelemetryBuffer(out_path=out_telemetry)

    registry = load_pose_registry()
    fixture_certs = load_fixture_certs(fixture_path)

    report = ScaleRampReport()
    if out_jsonl is not None:
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.write_text("")

    for tier_label, count in tiers:
        tr = run_one_tier(
            tier_label=tier_label,
            cut_count=count,
            registry=registry,
            fixture_certs=fixture_certs,
            buf=buf,
            solve_seconds_cap=solve_seconds_cap,
        )
        report.tiers.append(tr)
        if out_jsonl is not None:
            with out_jsonl.open("a") as f:
                f.write(json.dumps({
                    "tier": tr.tier_label,
                    "cut_count_target": tr.cut_count_target,
                    "cut_count_applied": tr.cut_count_applied,
                    "n_vars": tr.n_vars,
                    "n_constraints_total": tr.n_constraints_total,
                    "build_wall_s": round(tr.build_wall_s, 4),
                    "translation_wall_s": round(tr.translation_wall_s, 4),
                    "proto_bytesize": tr.proto_bytesize,
                    "proto_mb": round(tr.proto_mb, 3),
                    "rss_peak_gb_during_build": round(tr.rss_peak_gb_during_build, 3),
                    "solve_wall_s": round(tr.solve_wall_s, 4),
                    "solve_status_label": tr.solve_status_label,
                    "n_pairs_total": tr.n_pairs_total,
                    "n_pairs_remapped": tr.n_pairs_remapped,
                    "per_family_remapped": tr.per_family_remapped,
                    "true_registry_bound": (tr.n_pairs_remapped == 0),
                    "notes": tr.notes,
                }) + "\n")

    # G/N verdicts.
    by_tier = {t.tier_label: t for t in report.tiers}
    # G1-G4b: build wall thresholds
    if "0" in by_tier:
        report.g_pass["G1_build_0cut"] = by_tier["0"].build_wall_s <= G_THRESHOLDS["G1_build_0cut_s"]
    if "1K" in by_tier:
        wall_1k = by_tier["1K"].build_wall_s + by_tier["1K"].translation_wall_s
        report.g_pass["G2_build_1K"] = wall_1k <= G_THRESHOLDS["G2_build_1K_s"]
    if "10K" in by_tier:
        wall_10k = by_tier["10K"].build_wall_s + by_tier["10K"].translation_wall_s
        report.g_pass["G3_build_10K"] = wall_10k <= G_THRESHOLDS["G3_build_10K_s"]
    if "50K" in by_tier:
        wall_50k = by_tier["50K"].build_wall_s + by_tier["50K"].translation_wall_s
        report.g_pass["G4_build_50K"] = wall_50k <= G_THRESHOLDS["G4_build_50K_s"]
    if "100K" in by_tier:
        wall_100k = by_tier["100K"].build_wall_s + by_tier["100K"].translation_wall_s
        report.g_pass["G4b_build_100K"] = wall_100k <= G_THRESHOLDS["G4b_build_100K_s"]
    # G5: 0-cut solve wall
    if "0" in by_tier:
        report.g_pass["G5_solve_0cut"] = by_tier["0"].solve_wall_s <= G_THRESHOLDS["G5_solve_0cut_s"]
    # G8: max rss across tiers
    max_rss = max((t.rss_peak_gb_after_solve for t in report.tiers), default=0.0)
    report.g_pass["G8_rss_peak"] = max_rss <= G_THRESHOLDS["G8_rss_peak_gb"]
    report.n_trigger["N3_rss_critical"] = max_rss > G_THRESHOLDS["N3_rss_critical_gb"]
    # G9: proto size thresholds
    if "50K" in by_tier:
        report.g_pass["G9_proto_50K"] = by_tier["50K"].proto_mb <= G_THRESHOLDS["G9_proto_50K_mb"]
    if "100K" in by_tier:
        report.g_pass["G9_proto_100K"] = by_tier["100K"].proto_mb <= G_THRESHOLDS["G9_proto_100K_mb"]
    # G6b/N2: at 10K/50K/100K random cuts — INFEASIBLE wall must > 1s
    for tag in ("1K", "10K", "50K", "100K"):
        if tag not in by_tier:
            continue
        t = by_tier[tag]
        if t.solve_status_label == "INFEASIBLE" and t.solve_wall_s <= G_THRESHOLDS["G6b_random_min_wall_s"]:
            report.n_trigger[f"N2_random_presolve_crash_{tag}"] = True
    # N1: any build wall > 2× threshold
    for tag, count in tiers:
        if tag not in by_tier:
            continue
        t = by_tier[tag]
        thr_key = {
            "0": "G1_build_0cut_s",
            "1K": "G2_build_1K_s",
            "10K": "G3_build_10K_s",
            "50K": "G4_build_50K_s",
            "100K": "G4b_build_100K_s",
        }.get(tag)
        if thr_key:
            limit = G_THRESHOLDS[thr_key] * 2.0
            if (t.build_wall_s + t.translation_wall_s) > limit:
                report.n_trigger[f"N1_build_overlimit_{tag}"] = True

    report.raw_jsonl_path = out_jsonl
    return report


if __name__ == "__main__":
    out = REPO_ROOT / "data" / "cuts" / "spike" / "scale_ramp_results.jsonl"
    rep = run_scale_ramp(out_jsonl=out)
    print(rep.format_human())
    print()
    print("g_pass:", rep.g_pass)
    print("n_trigger:", rep.n_trigger)
    raise SystemExit(0 if rep.all_g_pass and not rep.any_n_trigger else 1)
