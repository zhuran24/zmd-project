#!/usr/bin/env python3
"""复核94B 面积算术编码乙：整数穷举与一维动态规划，不调用 area_a.py。
1) 占地常数用机身长宽逐台相乘重算；
2) (A,P,J,S=X+Y) 整数穷举，核 A=1110 的 P、J 结论；
3) 30x37 / 37x30 在 a,b>=4 的全部位置上，用一维 DP 求上、右两边外边格数 X0 的最小值，与「边长式」下界对照；
4) a 或 b 取 2、3 时（按 band_b 的显式矿石格与矩形离带 m<=e(a-1)）空矩形的最大面积。
"""
import json, sys
from functools import lru_cache

out = {}
dims = {"粉碎机": (3, 3, 68), "精炼炉": (3, 3, 51), "研磨机": (6, 4, 32), "塑形机": (3, 3, 6), "配件机": (3, 3, 6),
        "种植机": (5, 5, 32), "采种机": (5, 5, 16), "封装机": (6, 4, 3), "灌装机": (6, 4, 3)}
mach = 0
for k, (w, h, n) in dims.items():
    for _ in range(n):
        mach += w * h
base = 70 * 70 - mach - 9 * 9 - 46 * 3 * 1
out["4900-机身-核心-取货口"] = base

# 2) 整数穷举
def legal(A):
    return any(A % w == 0 and 6 <= w <= 66 and 6 <= A // w <= 66 for w in range(6, 67))

feas = {}
for P in range(10, 25):
    for J in range(0, P + 1):
        if 10 * J > 23 * P - 217 or 54 * P - 25 * J < 520:
            continue
        for S in range(0, 400):
            A = 1110
            if 4 * A + 14 * P <= 4639 and 4 * A + 16 * P - 2 * J + S <= 4639:
                feas.setdefault(P, {}).setdefault(J, S)
                feas[P][J] = S  # 记最大 S
out["A=1110可行(P->J->X+Y上界)"] = feas
# A+4P<=1182 下 A 最大合法值随 P
out["A+4P<=1182 时 P=10 的 A 上界"] = max(A for A in range(0, 1200) if A + 40 <= 1182 and legal(A))

# 3) 一维 DP：外边折线 = 第 69 列第 1..69 行（自下而上）+ 第 69 行第 68..1 列（自右而左），角格 (69,69) 计两次
PATH = [(69, y) for y in range(1, 70)] + [(x, 69) for x in range(68, 0, -1)]
CORNER = PATH.index((69, 69))


def min_X0(a, b, W, H, allow_core, allow_extra):
    inrect = [a <= x < a + W and b <= y < b + H for (x, y) in PATH]
    n = len(PATH)
    INF = 10 ** 9

    @lru_cache(maxsize=None)
    def f(i, core, extra, lastm):
        if i >= n:
            return 0
        if inrect[i]:
            return f(i + 1, core, extra, False)
        best = INF
        # 这一格是 X 格（运输或空格）
        w = 2 if i == CORNER else 1
        best = min(best, w + f(i + 1, core, extra, False))
        # 在产机器：长度 3..5 的一段，不含角格、不进矩形、不紧接上一台在产机器
        if not lastm:
            for L in (3, 4, 5):
                seg = range(i, i + L)
                if i + L <= n and CORNER not in seg and not any(inrect[j] for j in seg):
                    best = min(best, f(i + L, core, extra, True))
        # 协议核心：长度 9，不含角格
        if core:
            L = 9
            seg = range(i, i + L)
            if i + L <= n and CORNER not in seg and not any(inrect[j] for j in seg):
                best = min(best, f(i + L, False, extra, False))
        # 额外 3x3：一边 3 格；或占角，覆盖折线上 5 格
        if extra:
            for L in (3, 5):
                seg = range(i, i + L)
                if i + L > n or any(inrect[j] for j in seg):
                    continue
                if L == 5 and not (i == CORNER - 2):
                    continue
                if L == 3 and CORNER in seg:
                    continue
                best = min(best, f(i + L, core, False, False))
        return best

    return f(0, allow_core, allow_extra, False)


rows = []
summary = {}
for (W, H) in ((30, 37), (37, 30)):
    for a in range(4, 70 - W + 1):
        for b in range(4, 70 - H + 1):
            right = a + W - 1 == 69
            top = b + H - 1 == 69
            kind = "右上" if (right and top) else ("一边" if (right or top) else "不贴")
            for ext in (False, True):
                v = min_X0(a, b, W, H, True, ext)
                key = (kind, ext)
                summary[key] = min(summary.get(key, 10 ** 9), v)
out["X0最小(DP,允许核心)"] = {f"{k[0]}{'有增配' if k[1] else '无增配'}": v for k, v in summary.items()}

# 边长式 L<=6X0+14c+8t+5k 的下界（c<=1；t 为额外单位段数，角上额外机记 2 段）
def ineq_bound(a, b, W, H, t):
    right = a + W - 1 == 69
    top = b + H - 1 == 69
    cells = [p for p in PATH if not (a <= p[0] < a + W and b <= p[1] < b + H)]
    Lc = len(cells)
    # 段数
    idx = [i for i, p in enumerate(PATH) if not (a <= p[0] < a + W and b <= p[1] < b + H)]
    k = 1 + sum(1 for i, j in zip(idx, idx[1:]) if j != i + 1)
    need = Lc - 14 - 8 * t - 5 * k
    return max(0, -(-need // 6))

ib = {}
for (W, H) in ((30, 37), (37, 30)):
    for a in range(4, 70 - W + 1):
        for b in range(4, 70 - H + 1):
            right = a + W - 1 == 69
            top = b + H - 1 == 69
            kind = "右上" if (right and top) else ("一边" if (right or top) else "不贴")
            for t, lab in ((0, "无增配"), (1 if kind == "右上" else 2, "有增配")):
                v = ineq_bound(a, b, W, H, t)
                ib[f"{kind}{lab}"] = min(ib.get(f"{kind}{lab}", 10 ** 9), v)
out["X0最小(边长式)"] = ib

# 4) a 或 b 为 2、3 时的最大面积（矩形离带）
sys.path.insert(0, ".")
from band_b import bands  # 同目录编码乙的边带枚举（本席自写）
best = 0
for p, ores in bands():
    col1 = [y for (x, y) in ores if x == 1]
    row1 = [x for (x, y) in ores if y == 1 and x >= 1]
    for a in (2, 3):
        for b in range(2, 65):
            for H in range(6, 70 - b + 1):
                e = 1 if b + H - 1 == 69 else 2
                m = sum(1 for y in col1 if b <= y < b + H)
                if m > e * (a - 1):
                    continue
                W = 70 - a
                best = max(best, W * H)
    for b in (2, 3):
        for a in range(2, 65):
            for W in range(6, 70 - a + 1):
                e = 1 if a + W - 1 == 69 else 2
                m = sum(1 for x in row1 if a <= x < a + W)
                if m > e * (b - 1):
                    continue
                H = 70 - b
                best = max(best, W * H)
out["a或b<=3时最大面积"] = best
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "area_b.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
