"""复算块4-1试法遗漏竖向端口对齐时的局部几何反例。

坐标向右、向上；占地采用半开矩形。这是规则几何推导，不是游戏内核。
"""
import json
from pathlib import Path

from scipy.optimize import linprog

# x_A,x_B,x_C,x_P；y固定为10,13,14,10，宽度为3,1,3,2。
# P和A的y投影相交，原来P在A左侧：A >= P+2。
# 固定P为A、C的供电见证；覆盖横向区间[P-5,P+7)。
# 正面积相交、整数坐标：M-P<=6，P-M<=w_M+4=7。
matrix = [[-1, 0, 0, 1], [1, 0, 0, -1], [-1, 0, 0, 1],
          [0, 0, 1, -1], [0, 0, -1, 1]]
rhs = [-2, 6, 7, 6, 7]
bounds = [(0, 67), (0, 69), (0, 67), (0, 68)]


def actual_channels(values):
    a, belt, box, _ = values
    return {"A→B": bool(a <= belt < a + 3),
            "B→C": bool(box <= belt < box + 3)}


def original_pin_channels(values):
    a, belt, box, _ = values
    return {"A中端口→B": bool(belt == a + 1),
            "B→C中端口": bool(belt == box + 1)}


result = linprog([1, 1, 1, 1], A_ub=matrix, b_ub=rhs,
                 bounds=bounds, method="highs")
aligned = linprog([1, 1, 1, 1], A_ub=matrix, b_ub=rhs,
                  A_eq=[[-1, 1, 0, 0], [0, 1, -1, 0]],
                  b_eq=[1, 1], bounds=bounds, method="highs")
assert result.success and aligned.success
original = [10, 11, 10, 6]
evidence = {
    "variables": ["x_A", "x_B", "x_C", "x_P"],
    "original": original,
    "candidate": result.x.tolist(),
    "objective": float(result.fun),
    "original_actual_channels": actual_channels(original),
    "candidate_actual_channels": actual_channels(result.x),
    "original_pin_channels_after_compression": original_pin_channels(result.x),
    "with_original_pin_alignment": aligned.x.tolist(),
    "with_original_pin_alignment_objective": float(aligned.fun),
    "evidence_kind": "按规则原句的几何计算及试法x约束LP；非内核吞吐验证",
}
Path(__file__).with_suffix(".json").write_text(
    json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(evidence, ensure_ascii=False, indent=2))
