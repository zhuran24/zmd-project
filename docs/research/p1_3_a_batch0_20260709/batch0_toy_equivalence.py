"""A 批 0 第一关：C6 vs witness 玩具等价性验证。

小世界（含 needs_power 模板 + 杆池），两种编码各建模求解，断言判决一致：
- 可解场景两边都可解；关键 INFEASIBLE 场景（杆位全被堵）两边都判死。
"""
import sys

sys.path.insert(0, "/home/zhuran24/zmd-pj")
from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel
import c6_encoding_patch


def build_toy(*, pole_xs, block_pole_cells=False):
    """3×3 盘、1 个需电 miner（唯一 pose 在 (0,0)）、杆池在指定位置。"""
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    blocker_poses = []
    if block_pole_cells:
        # 占位设施把所有杆位堵死 → 无杆可放 → 需电设施必死
        instances.append(
            {
                "instance_id": "rock_001",
                "facility_type": "rock",
                "operation_type": "mining",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        )
        blocker_poses = [
            {
                "pose_id": f"rock_x{x}",
                "anchor": {"x": x, "y": 1},
                "occupied_cells": [[x, 1] for x in ([x])],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for x in pole_xs
        ]
    radius = 1
    pools = {
        "miner": [
            {
                "pose_id": "miner_p0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "power_pole": [
            {
                "pose_id": f"pole_x{x}",
                "anchor": {"x": x, "y": 1},
                "occupied_cells": [[x, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [
                    [cx, cy]
                    for cx in range(max(0, x - radius), min(2, x + 1 + radius) + 1)
                    for cy in range(max(0, 1 - radius), min(2, 1 + 1 + radius) + 1)
                ],
            }
            for x in pole_xs
        ],
    }
    if blocker_poses:
        pools["rock"] = blocker_poses
    rules = {
        "globals": {"grid": {"width": 3, "height": 3}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": radius,
            },
            **(
                {"rock": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}}
                if blocker_poses
                else {}
            ),
        },
    }
    core = MasterPlacementModel.build_exact_core(instances, pools, rules)
    return MasterPlacementModel.from_exact_core(core, ghost_rect=None)


def solve_status(master):
    return master.solve(time_limit_seconds=10.0)


def run_case(name, **kw):
    c6_encoding_patch.revert_c6_patch()
    witness = solve_status(build_toy(**kw))
    c6_encoding_patch.apply_c6_patch()
    c6 = solve_status(build_toy(**kw))
    c6_encoding_patch.revert_c6_patch()
    agree = (witness in (cp_model.OPTIMAL, cp_model.FEASIBLE)) == (
        c6 in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    )
    print(f"{name}: witness={witness} c6={c6} {'一致 ✓' if agree else '不一致 ✗'}")
    return agree


ok = True
ok &= run_case("可解（杆可覆盖）", pole_xs=[0, 1])
ok &= run_case("必死（杆位全被堵）", pole_xs=[0], block_pole_cells=True)
print("TOY_EQUIVALENCE", "PASS" if ok else "FAIL")
