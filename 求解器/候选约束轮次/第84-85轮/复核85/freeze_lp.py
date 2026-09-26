#!/usr/bin/env python3
"""复核85：成品拒收冻结范围的独立复算（Farkas / 线性规划）。

仓库外每种物品件数有界（各格有上限，缓存一次至多一批）。一个活动（配方、矿石取货、
可持续的入库去向）在拒收区间内能无限次发生，当且仅当存在非负的平稳活动率 x，
使每种物品净变化为 0 且该活动率为正；否则由 Farkas 引理有一组物品权重，使每个活动
都不减小加权总数、该活动使它严格增加，而加权总数有界，于是该活动只发生有限次。

可持续去向：未被拒收的成品（玩家拿走）；允许入库的矿石（可再被取货口取出，构成回路）。
其余非成品入库受仓库每种 80000 上限，只是有限去向，不算可持续。
配方从前提快照的游戏规则解析。
"""
import json, re
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
RULES = HERE.parent / "前提快照" / "《明日方舟：终末地》游戏规则.txt"

def parse_recipes(text):
    sec = text.split("\n配方\n", 1)[1]
    out = []
    cur = None
    for line in sec.splitlines():
        s = line.strip()
        if not s:
            continue
        if "→" not in s:
            cur = s; continue
        lhs, rhs = s.split("→")
        rhs = rhs.rsplit("，", 1)[0]
        def items(part):
            d = {}
            for tok in part.split("＋"):
                m = re.match(r"(\d+)\s*(\S+)", tok.strip())
                d[m.group(2)] = int(m.group(1))
            return d
        out.append((cur, items(lhs), items(rhs)))
    return out

REC = parse_recipes(RULES.read_text(encoding="utf-8"))
ITEMS = sorted({k for _, l, r in REC for k in list(l) + list(r)})
PRODUCTS = {"高容谷地电池", "精选荞愈胶囊"}
ORES = {"源矿", "蓝铁矿"}

def acts(refused, forbidden):
    A = []
    for m, l, r in REC:
        v = {k: -q for k, q in l.items()}
        for k, q in r.items():
            v[k] = v.get(k, 0) + q
        A.append((f"{m}:{'+'.join(l)}→{'+'.join(r)}", v))
    for o in sorted(ORES):
        A.append((f"取货:{o}", {o: 1}))
    for p in sorted(PRODUCTS - refused):
        A.append((f"入库(可持续):{p}", {p: -1}))
    for o in sorted(ORES - forbidden):
        A.append((f"入库(矿石回取):{o}", {o: -1}))
    return A

def classify(refused, forbidden):
    A = acts(refused, forbidden)
    M = np.array([[a[1].get(i, 0) for a in A] for i in ITEMS], dtype=float)
    res = {}
    for j, (name, _) in enumerate(A):
        c = np.zeros(len(A)); c[j] = -1
        bounds = [(0, None)] * len(A); bounds[j] = (0, 1)
        lp = linprog(c, A_eq=M, b_eq=np.zeros(len(ITEMS)), bounds=bounds, method="highs")
        assert lp.status == 0, lp.message
        res[name] = round(-lp.fun, 9)
    stops = [n for n, v in res.items() if v == 0 and not n.startswith("入库")]
    return stops, res

CASES = {
    "一_电池拒收": ({"高容谷地电池"}, {"源矿", "源石粉末", "致密源石粉末", "钢制零件"}),
    "二_胶囊拒收": ({"精选荞愈胶囊"}, {"钢质瓶", "细磨荞花粉末", "荞花粉末"}),
    "三_两种拒收": (set(PRODUCTS), set(ITEMS) - PRODUCTS),
    # 对照：去掉 源矿 不入库 的前提，看源矿取货是否还必停
    "一_对照_源矿可入库": ({"高容谷地电池"}, {"源石粉末", "致密源石粉末", "钢制零件"}),
}

def main():
    out = {"recipes": len(REC), "items": len(ITEMS)}
    for name, (ref, forb) in CASES.items():
        stops, res = classify(ref, forb)
        out[name] = {"must_stop": stops, "n_recipes_stopped": sum(1 for s in stops if not s.startswith("取货")), "max_rates": res}
        print(name, len(stops), stops)
    (HERE / "freeze_lp.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
