"""C1 vs witness 玩具等价性验证（复用 C6 玩具世界）。"""
import sys

sys.path.insert(0, "/home/zhuran24/zmd-pj")
sys.path.insert(0, "/home/zhuran24/zmd-pj/docs/research/p1_3_a_batch0_20260709")
from ortools.sat.python import cp_model

import c1_encoding_patch
from batch0_toy_equivalence import build_toy


def solve_status(master):
    return master.solve(time_limit_seconds=10.0)


def run_case(name, **kw):
    c1_encoding_patch.revert_c1_patch()
    witness = solve_status(build_toy(**kw))
    c1_encoding_patch.apply_c1_patch()
    try:
        c1 = solve_status(build_toy(**kw))
    finally:
        c1_encoding_patch.revert_c1_patch()
    agree = (witness in (cp_model.OPTIMAL, cp_model.FEASIBLE)) == (
        c1 in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    )
    print(f"{name}: witness={witness} c1={c1} {'一致 ✓' if agree else '不一致 ✗'}")
    return agree


ok = True
ok &= run_case("可解（杆可覆盖）", pole_xs=[0, 1])
ok &= run_case("必死（杆位全被堵）", pole_xs=[0], block_pole_cells=True)
# ghost 场景走 clone→overlay→dedup 全链——专测 v1 修复 1（clone 丢杆 interval
# 会让杆躲进 ghost 白嫖覆盖 → C1 假 FEASIBLE、与 witness 判决翻转）。
ok &= run_case(
    "ghost 钉唯一杆位（必死）",
    pole_xs=[0],
    ghost_rect=(1, 1),
    ghost_anchor_filter=[(0, 1)],
)
ok &= run_case(
    "ghost 在别处（可解）",
    pole_xs=[0],
    ghost_rect=(1, 1),
    ghost_anchor_filter=[(2, 2)],
)
print("TOY_EQUIVALENCE_C1", "PASS" if ok else "FAIL")
