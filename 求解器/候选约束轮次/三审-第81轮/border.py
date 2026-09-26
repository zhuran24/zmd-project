"""三审自写：面积 1110（30×37 或 37×30）时右、上外边界的 X0 下界与两端点论证，以及标量分支。

核第 81 轮 C 组「面积至少1110的增机增箱排除与十三桩界」：
 - 无占边桩（J=0）时，沿第 69 行第 1…69 列与第 69 列第 1…69 行（右上角两边各计一次）逐格铺：
   在产制造单位（贴上边界端口必左右、贴右边界端口必上下，沿边长 3、4、5，不占角，两台不相邻），
   协议核心（至多 1 台，沿边长 9，不占角），一件额外 3×3 单位（可占角，此时两边各 3 格），
   空矩形，其余格计入 X0。求 X0 最小值（放宽：不另加核心、在产机器与矩形、额外单位的相邻限制）。
   条文：同时贴两边 ≥7（无额外单位 ≥8）、只贴一边 ≥10、都不贴 ≥17。
 - 端点：同时贴右、上两边时，矩形左侧紧邻的上边界格 u 与下方紧邻的右边界格 v 不能是在产制造单位
   或核心（其端口边整条对着空矩形）；求 X0+[u 计入]+[v 计入] 最小值，条文要 ≥8（即 X0+Y0≤7 不可能）。
 - 标量：A=1110 时 4E+Ω 上界、剩余 (P,J) 分支与 X+Y 上界。
"""
import json, pathlib
from functools import lru_cache
from fractions import Fraction as Fr

OUT = pathlib.Path(__file__).with_name("out") / "border.json"
N = 70
TOP = [(x, 69) for x in range(1, 70)]            # 路径位置 0..68
RIGHT = [(69, y) for y in range(69, 0, -1)]      # 路径位置 69..137
PATH = TOP + RIGHT
CORNER = (68, 69)


def part(p):
    return 0 if p <= 68 else 1


def solve(rect, extra_allowed, forbid_adjacent_rect=False, charge=()):
    a, b, W, H = rect
    inR = [a <= x <= a + W - 1 and b <= y <= b + H - 1 for (x, y) in PATH]
    assert inR[68] == inR[69]
    L = len(PATH)
    charge = set(charge)

    @lru_cache(maxsize=None)
    def f(p, lastM, core, extra):
        # lastM：上一格是在产机器（用于不相邻）；lastR：上一格是矩形由 inR[p-1] 判断
        if p == L:
            return 0
        best = None

        def upd(v):
            nonlocal best
            if v is not None and (best is None or v < best):
                best = v
        prevR = p > 0 and inR[p - 1] and part(p - 1) == part(p)
        if inR[p]:
            if forbid_adjacent_rect and lastM:
                return None
            if p == 68:
                return f(70, False, core, extra)
            return f(p + 1, False, core, extra)
        # 角格：只能整体计入 X0（两次）或被角上的额外单位盖住（从位置 66 起的 6 格）
        if p == 68:
            upd(add(2, f(70, False, core, extra)))
            return best
        # 计入 X0
        upd(add(1 + (1 if p in charge else 0), f(p + 1, False, core, extra)))
        # 在产制造单位：长 3、4、5，同一边、不占角、不与前一台相邻
        if not lastM and not (forbid_adjacent_rect and prevR):
            for ln in (3, 4, 5):
                q = p + ln
                cells = range(p, q)
                if q > L or any(inR[c] for c in cells) or any(c in CORNER for c in cells):
                    continue
                if part(p) != part(q - 1):
                    continue
                if forbid_adjacent_rect and q < L and inR[q] and part(q) == part(q - 1):
                    continue
                upd(f(q, True, core, extra))
        # 协议核心：长 9，至多一台
        if not core and not (forbid_adjacent_rect and prevR):
            q = p + 9
            cells = range(p, q)
            if q <= L and not any(inR[c] for c in cells) and not any(c in CORNER for c in cells) and part(p) == part(q - 1):
                if not (forbid_adjacent_rect and q < L and inR[q] and part(q) == part(q - 1)):
                    upd(f(q, False, True, extra))
        # 额外 3×3 单位：沿边 3 格，或占角（位置 66..71）
        if extra_allowed and not extra:
            q = p + 3
            cells = range(p, q)
            if q <= L and not any(inR[c] for c in cells) and not any(c in CORNER for c in cells) and part(p) == part(q - 1):
                upd(f(q, False, core, True))
            if p == 66 and not any(inR[c] for c in range(66, 72)):
                upd(f(72, False, core, True))
        return best

    def add(c, v):
        return None if v is None else c + v
    return f(0, False, False, False)


def rects():
    out = []
    for W, H in ((30, 37), (37, 30)):
        for a in range(4, 70 - W + 1):
            for b in range(4, 70 - H + 1):
                out.append((a, b, W, H))
    return out


def main():
    res = {"逐类最小": {}, "端点": {}, "标量": {}}
    cls_min = {}
    for r in rects():
        a, b, W, H = r
        top = b + H - 1 == 69
        right = a + W - 1 == 69
        cls = "同时贴两边" if top and right else ("只贴一边" if top or right else "都不贴")
        m1 = solve(r, True)
        m0 = solve(r, False)
        c = cls_min.setdefault(cls, {"有额外单位": 10**9, "无额外单位": 10**9, "位置数": 0})
        c["有额外单位"] = min(c["有额外单位"], m1)
        c["无额外单位"] = min(c["无额外单位"], m0)
        c["位置数"] += 1
        if top and right:
            u = TOP.index((a - 1, 69))
            v = PATH.index((69, b - 1))
            me = solve(r, True, forbid_adjacent_rect=True, charge=(u, v))
            res["端点"][f"{W}x{H}@({a},{b})"] = {"u": (a - 1, 69), "v": (69, b - 1), "X0+[u]+[v]最小": me}
    res["逐类最小"] = cls_min
    # 标量：A=1110，方向预算 4A+16P−2J+4E+Ω+X0+Y0 ≤4751；供电 54P−25J≥520、10J≤23P−217；A+4P≤1182
    A = 1110
    rows = []
    for P in range(10, 19):
        if A + 4 * P > 1182:
            continue
        Js = [J for J in range(0, P + 1) if 54 * P - 25 * J >= 520 and 10 * J <= 23 * P - 217]
        if not Js:
            continue
        rows.append({"P": P, "J": Js, "4E+Ω上界": max(4751 - 4 * A - 16 * P + 2 * J for J in Js)})
    res["标量"]["4E+Ω上界"] = rows
    base = Fr(219, 2)
    single = {"粉碎机": 36, "精炼炉": 36, "配件机": 36, "协议储存箱": 36, "塑形机": 34,
              "研磨机": 92, "封装机": 90, "灌装机": 88, "种植机": 100, "采种机": 100}
    res["标量"]["单项增配4E+Ω"] = {k: str(base + v) for k, v in single.items()}
    res["标量"]["单项增配X0+Y0上限(P=10,J=0)"] = {k: int(Fr(4751 - 4 * A - 160) - base - v) for k, v in single.items()
                                               if base + v <= 4751 - 4 * A - 160}
    # 九机型恰下限、无箱后的主支：4A+16P−2J+X+Y≤4639
    rem = []
    for P in range(10, 19):
        for J in range(0, P + 1):
            if 54 * P - 25 * J < 520 or 10 * J > 23 * P - 217:
                continue
            xy = 4639 - 4 * A - 16 * P + 2 * J
            if xy < 0:
                continue
            rem.append({"P": P, "J": J, "X+Y上限": xy})
    res["标量"]["主支剩余"] = rem
    # 1110 以下的合法面积（两边 6…68）
    def legal(Ar):
        return [(w, Ar // w) for w in range(6, 69) if Ar % w == 0 and 6 <= Ar // w <= 68 and w <= Ar // w]
    res["标量"]["面积1107至1113的整数边长"] = {Ar: legal(Ar) for Ar in range(1107, 1114)}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(json.dumps({"逐类最小": cls_min, "端点最小": min(v["X0+[u]+[v]最小"] for v in res["端点"].values()),
                      "端点位置数": len(res["端点"]), "标量": res["标量"]}, ensure_ascii=False, indent=1, default=list))


if __name__ == "__main__":
    main()
