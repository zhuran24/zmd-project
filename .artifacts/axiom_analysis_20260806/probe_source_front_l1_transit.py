"""P1 预测检验探针：外商品借 L1 垂直直穿「在用输入口」的 front 格。

几何（手造最小域；坐标系=模型 DIR_DELTA：N=y+1）：
- mach_a 机身 (6,5)，输入口 front=F=(5,5) 朝 W；alpha 从 src_a (3,2) 出发，
  沿 y=5 行东行直进直入（F 地面形状=W→E 直带，满足 cross 兼容条件）。
- beta 从 src_b (5,1) 到 sink_b (5,8)，两侧墙把它困在 x=5 列——必须经 F，
  唯一通路=在 F 格借 L1（十字 NS 通道）垂直过境。
期望：FEASIBLE = 模型接受 P1 构造（第四轮任务书可教此自由度）；
INFEASIBLE = P1 模型侧为假，任务书禁用，转 owner 裁定。
"""
import os, sys
from pathlib import Path

PROJECT_ROOT = Path("/home/zhuran24/zmd-pj")
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["EXACT_CP_SAT_WORKERS"] = "4"

from src.models.routing_subproblem import (
    RoutingPlacementCore,
    RoutingSubproblem,
    analyze_exact_routing_domain,
)

occ = {}
occ[(6, 5)] = "mach_a"
occ[(3, 2)] = "src_a"
occ[(5, 1)] = "src_b"
occ[(5, 8)] = "sink_b"
for cell in [(4, 3), (6, 3), (4, 4), (6, 4), (4, 6), (6, 6), (4, 7), (6, 7)]:
    occ[cell] = f"wall_{cell[0]}_{cell[1]}"

specs = [
    {"instance_id": "src_a", "x": 3, "y": 3, "dir": "N", "commodity": "alpha", "type": "in"},
    {"instance_id": "mach_a", "x": 5, "y": 5, "dir": "W", "commodity": "alpha", "type": "out"},
    {"instance_id": "src_b", "x": 5, "y": 2, "dir": "N", "commodity": "beta", "type": "out"},
    {"instance_id": "sink_b", "x": 5, "y": 7, "dir": "S", "commodity": "beta", "type": "in"},
]

core = RoutingPlacementCore.from_occupied_cells(set(occ), occupied_owner_by_cell=occ)
ana = analyze_exact_routing_domain(
    placement_core=core, port_specs=specs, occupied_owner_by_cell=occ
)
print("domain:", ana["status"], "| blocked:", ana.get("blocked_ports"))
if ana["status"] != "feasible":
    raise SystemExit(1)
m = RoutingSubproblem.from_placement_core(
    core, specs, ["alpha", "beta"], domain_analysis=ana
)
m.build()
status = m.solve(time_limit=60)
print("solve:", status)
# 对照组：把 beta 的 L1 自由度拿掉验证墙是有效的——beta 只剩地面时应 INFEASIBLE
# （地面 F 格已被 alpha 终端占据+排他）。用「墙上再堵 F 以外全部通路」间接验证
# 已由几何保证（x=5 列是 beta 唯一通路），此处不再重复建模。
