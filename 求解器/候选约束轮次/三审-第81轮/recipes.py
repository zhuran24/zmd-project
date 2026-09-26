"""三审自写：从正式规则文件解析配方，逐物品列循环收支，有理数消元。

核：第 81 轮 C 组「全面积配方批次与蓝铁粉末回炼费用」（秩、唯一自由量 r、九机型批率、
物理出货 305.65+2r）、「任意台数的多通道机器下限」（五类总进出料率与代回台数）、
「植物时间平均存量去台数前提」（植物批率与 22、42）。只读正式规则文件，不导入别处脚本。
"""
from fractions import Fraction as Fr
import json, re, pathlib, math

ROOT = pathlib.Path(__file__).resolve().parents[3]
RULES = ROOT / "《明日方舟：终末地》游戏规则.txt"
OUT = pathlib.Path(__file__).with_name("out") / "recipes.json"

MACHINES = ["粉碎机", "精炼炉", "研磨机", "塑形机", "配件机", "种植机", "采种机", "封装机", "灌装机"]


def parse():
    lines = RULES.read_text(encoding="utf-8").splitlines()
    start = lines.index("配方")
    recipes, cur = [], None
    for ln in lines[start + 1:]:
        s = ln.strip()
        if not s:
            continue
        if s in MACHINES:
            cur = s
            continue
        m = re.fullmatch(r"(.+?)→(.+?)，\s*(\d+)\s*tick", s)
        assert m and cur, s

        def side(t):
            out = {}
            for part in re.split(r"[＋+]", t):
                part = part.strip()
                q, name = re.fullmatch(r"(\d+)\s*(\S+)", part).groups()
                out[name] = out.get(name, 0) + int(q)
            return out
        recipes.append({"机型": cur, "入": side(m.group(1)), "出": side(m.group(2)), "时长": int(m.group(3))})
    return recipes


def rref(M):
    M = [row[:] for row in M]
    rows, cols = len(M), len(M[0])
    piv, r = [], 0
    for c in range(cols - 1):
        p = next((i for i in range(r, rows) if M[i][c] != 0), None)
        if p is None:
            continue
        M[r], M[p] = M[p], M[r]
        pv = M[r][c]
        M[r] = [x / pv for x in M[r]]
        for i in range(rows):
            if i != r and M[i][c] != 0:
                f = M[i][c]
                M[i] = [a - f * b for a, b in zip(M[i], M[r])]
        piv.append(c)
        r += 1
    return M, piv


def main():
    rec = parse()
    items = sorted({k for x in rec for k in list(x["入"]) + list(x["出"])})
    assert len(rec) == 18 and len(items) == 19, (len(rec), len(items))
    # 周期收支：生产 − 消耗 = 外部净出（成品交付 0.6/0.55；两种矿石由仓库供 −34/−18；其余 0）
    ext = {k: Fr(0) for k in items}
    ext["高容谷地电池"] = Fr(3, 5)
    ext["精选荞愈胶囊"] = Fr(11, 20)
    ext["蓝铁矿"] = Fr(-34)
    ext["源矿"] = Fr(-18)
    A = []
    for it in items:
        A.append([Fr(x["出"].get(it, 0) - x["入"].get(it, 0)) for x in rec] + [ext[it]])
    R, piv = rref(A)
    rank = len(piv)
    consistent = all(any(v != 0 for v in row[:-1]) or row[-1] == 0 for row in R)
    free = [c for c in range(18) if c not in piv]
    assert len(free) == 1
    fc = free[0]
    # 通解 x = x0 + r·d
    x0 = [Fr(0)] * 18
    d = [Fr(0)] * 18
    d[fc] = Fr(1)
    for i, c in enumerate(piv):
        x0[c] = R[i][-1]
        d[c] = -R[i][fc]
    by_m = {}
    for i, x in enumerate(rec):
        a, b = by_m.get(x["机型"], (Fr(0), Fr(0)))
        by_m[x["机型"]] = (a + x0[i], b + d[i])
    # 物理出货：各配方产出件数 + 仓库源口 52
    out0 = sum(x0[i] * sum(x["出"].values()) for i, x in enumerate(rec)) + 52
    outd = sum(d[i] * sum(x["出"].values()) for i, x in enumerate(rec))
    # 各物品生产量（= 流量表的件数）
    flow0 = {it: sum(x0[i] * x["出"].get(it, 0) for i, x in enumerate(rec)) for it in items}
    flowd = {it: sum(d[i] * x["出"].get(it, 0) for i, x in enumerate(rec)) for it in items}
    flow0["蓝铁矿"] += 34
    flow0["源矿"] += 18
    # 机器时间需求（台·tick/tick）与在产台数下限（r=0）
    need = {}
    for i, x in enumerate(rec):
        need[x["机型"]] = need.get(x["机型"], Fr(0)) + x0[i] * x["时长"]
    lower = {m: math.ceil(need[m]) for m in MACHINES}
    # 多通道机器下限的五类总量（r 无关，逐项核 d 为零）
    def tot_in(machine, names=None):
        s0 = sum(x0[i] * sum(x["入"].values()) for i, x in enumerate(rec) if x["机型"] == machine)
        sd = sum(d[i] * sum(x["入"].values()) for i, x in enumerate(rec) if x["机型"] == machine)
        return s0, sd
    grind_in = tot_in("研磨机"); shape_in = tot_in("塑形机"); pack_in = tot_in("封装机"); fill_in = tot_in("灌装机")
    seed_out0 = sum(x0[i] * sum(x["出"].values()) for i, x in enumerate(rec) if x["机型"] == "采种机")
    seed_outd = sum(d[i] * sum(x["出"].values()) for i, x in enumerate(rec) if x["机型"] == "采种机")
    # 单机上限：少于 k 条有通过量的通道时的上限 low，达到 k 条时由配方给 high
    classes = {
        "研磨机": (grind_in[0], 3, 2, 3),   # 总量, 需要的通道数, low, high
        "塑形机": (shape_in[0], 2, 1, 2),
        "封装机": (pack_in[0], 5, 4, 5),
        "灌装机": (fill_in[0], 4, 3, 4),
        "采种机": (seed_out0, 2, 1, 2),
    }
    multi = {}
    for m, (F, k, lo, hi) in classes.items():
        n0 = lower[m]
        vals = {}
        for n in range(n0, n0 + 3):
            vals[n] = max(0, math.ceil(F - lo * n))
        # 反证核：k 台多通道机器能承担的最大总量
        multi[m] = {"总量": str(F), "通道数": k, "少于时单机上限": lo, "达到时单机上限": hi, "按台数": vals}
    # 植物批率与时间平均存量（植物沿途存量 + Q_s≥z、Q_p≥a+f）
    plant = {}
    for p, seed in (("荞花", "荞花种子"), ("砂叶", "砂叶种子")):
        z = sum(x0[i] for i, x in enumerate(rec) if x["机型"] == "种植机" and seed in x["入"])
        a = sum(x0[i] for i, x in enumerate(rec) if x["机型"] == "采种机" and p in x["入"])
        f = sum(x0[i] for i, x in enumerate(rec) if x["机型"] == "粉碎机" and p in x["入"])
        dz = sum(d[i] for i, x in enumerate(rec) if x["机型"] == "种植机" and seed in x["入"])
        plant[p] = {"种植": str(z), "采种": str(a), "粉碎": str(f), "r 系数": str(dz),
                    "种子平均至少": str(2 * z), "植株平均至少": str(2 * (a + f))}
    res = {
        "配方数": len(rec), "物品数": len(items), "秩": rank, "相容": consistent,
        "自由配方": f"{rec[fc]['机型']} {rec[fc]['入']}→{rec[fc]['出']}",
        "九机型批率": {m: f"{by_m[m][0]}+{by_m[m][1]}r" for m in MACHINES},
        "物理出货": f"{out0}+{outd}r", "物理出货小数": float(out0),
        "物品流量": {it: f"{flow0[it]}+{flowd[it]}r" for it in items},
        "物品流量合计": f"{sum(flow0.values())}+{sum(flowd.values())}r",
        "在产台数下限(r=0)": lower,
        "多通道机器下限": multi,
        "五类总量的r系数": {"研磨": str(grind_in[1]), "塑形": str(shape_in[1]), "封装": str(pack_in[1]),
                        "灌装": str(fill_in[1]), "采种出": str(seed_outd)},
        "植物": plant,
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
