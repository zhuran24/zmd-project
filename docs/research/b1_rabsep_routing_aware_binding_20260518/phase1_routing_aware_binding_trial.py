"""RAB-SEP Phase 1 — production routing-aware binding domain filter trial.

env:
- EXACT_USE_POSE_BOOL_MASTER=1
- EXACT_B1_ROUTING_AWARE_BINDING=1  (new)

GO 条件:
- master 53s OPTIMAL
- binding 端 routing-aware filter 实施正确 (raw_total - filtered_total > 0)
- binding solve FEASIBLE → routing precheck front_blocked=0 (paradigm 通!)
  或 binding INFEASIBLE → 加 cert cut (Phase 3 工作)

NO-GO 条件:
- env on 导致 master 变化 (vars/constraints)
- filter 实施 bug (binding FEASIBLE 后 routing precheck 仍 front_blocked > 0)
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> int:
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_B1_ROUTING_AWARE_BINDING"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = "22,28"
    for k in (
        "EXACT_B1_DELETION_CORE_CUT", "EXACT_B1_LAZY_DEMAND_CUT",
        "EXACT_B1_BYPASS_ROUTING_PRECHECK", "EXACT_B1_BINDING_ALT_CAP",
        "EXACT_B1_ITER_ON_ROUTING_INFEASIBLE",
    ):
        os.environ.pop(k, None)

    print("=== RAB-SEP Phase 1 — routing-aware binding filter trial ===")
    print("27×15 anchor (22,28), max_iter=1, env EXACT_B1_ROUTING_AWARE_BINDING=1")

    # monkey-patch binding build 拿 filter stats (build 之后 stats 才 populated)
    import src.models.binding_subproblem as bm
    import json
    orig_build = bm.PortBindingModel.build
    captured = {"done": False}

    def patched_build(self):
        orig_build(self)
        if not captured["done"]:
            captured["done"] = True
            s = self.routing_aware_filter_stats
            print(f"[filter] enabled={s['enabled']}")
            print(f"[filter] fixed-op patterns: raw={s['raw_patterns_total']} filtered={s['filtered_patterns_total']} pruned={s['front_blocked_patterns_pruned']}")
            print(f"[filter] empty filtered owners: {len(s['empty_filtered_owners'])}")
            print(f"[filter] generic_output slots: pre={s['generic_output_slots_pre_filter']} post={s['generic_output_slots_post_filter']}")
            print(f"[filter] generic_input slots: pre={s['generic_input_slots_pre_filter']} post={s['generic_input_slots_post_filter']}")
            out = Path("docs/research/b1_rabsep_routing_aware_binding_20260518/phase1_filter_stats.json")
            with open(out, "w") as f:
                json.dump({**s, "empty_filtered_owners": list(s["empty_filtered_owners"])}, f, indent=2, ensure_ascii=False)
            print(f"[filter] dumped {out}", flush=True)

    bm.PortBindingModel.build = patched_build

    from src.search.benders_loop import run_benders_for_ghost_rect

    t0 = time.perf_counter()
    status, _ = run_benders_for_ghost_rect(
        ghost_w=27, ghost_h=15,
        max_iterations=1,
        project_root=Path("."),
        solve_mode="certified_exact",
        master_seconds=120.0,
        binding_seconds=30.0,
        routing_seconds=60.0,
        flow_seconds=10.0,
        campaign=None,
        session=None,
        disable_master_warm_start=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n=== Phase 1 trial → {status} in {elapsed:.1f}s ===")
    if status == "CERTIFIED":
        print(">>> ✅ CERTIFIED FEASIBLE — paradigm 通!")
        return 0
    if status == "INFEASIBLE":
        print(">>> ✅ certified INFEASIBLE — Phase 1 OK")
        return 0
    print(f">>> {status} — 进 Phase 3 cert design")
    return 1


if __name__ == "__main__":
    sys.exit(main())
