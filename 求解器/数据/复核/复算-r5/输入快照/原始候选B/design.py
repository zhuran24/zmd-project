#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
design.py —— 一份显式的逻辑层设计，外加一个检查器。
不是搜索出来的，是手写的；程序只负责**验证**它，并把不合格处列出来。

设计纪律（每条都可逐台查）：
 N1 无混做：每台制造单位只做一条配方。
 N2 无分流器、无汇流器、无协议储存箱、无物品准入口。
    扇出靠源机器自己的多个取货端口，扇入靠目标机器自己的多个存货端口，交叉靠桥接器。
 N3 每个扇出点的各端口速率**相等**（不等比的分配比在规则里没有依据）。
 N4 每条通道是「一个取货端口 → 一个存货端口」的专用直连，速率两端相同。

扇出点分三类（供几何层逐处核 轮询均分 的前提）：
 A 满速扇出：各端口都 20/20tick。分配比由端口速率上限（每端口每 tick 至多 1 件）强制，
   **不依赖 轮询均分**。
 B 落在 轮询均分 原文前提内：批间隔恰 1 tick，且相邻两组件数之和 ≤k。
 C 超出原文前提：批间隔 >1 tick。需要一条推广版候选（见文件末尾 候选：轮询均分（松））。

覆盖范围：只做速率层（件/20 tick）配平、端口度数、扇出均分与分类检查。
**不涉及几何**（没检查这些通道能否在 70×70 无冲突走通）；
**不涉及执行语义**（没模拟轮询、优先级、缓存格闸门、滞留、判定先后）；
结论只能说「速率层上这组通道自洽」，**不能说布局存在，更不能说达标**。
"""
import csv, json, os
from collections import Counter

P = 20                      # 周期 tick 数（周期倍数：周期是 20 tick 的倍数）
PORTS = {"小": (3, 3), "中": (5, 5), "大": (6, 6)}
SIZE = {"小": 9, "中": 25, "大": 24}
DIM = {"小": "3x3", "中": "5x5", "大": "6x4"}

RECIPE = {
    "粉碎-源矿":      ("小", {"源矿": 1},                          {"源石粉末": 1}, 1),
    "粉碎-蓝铁块":    ("小", {"蓝铁块": 1},                        {"蓝铁粉末": 1}, 1),
    "粉碎-荞花":      ("小", {"荞花": 1},                          {"荞花粉末": 2}, 1),
    "粉碎-砂叶":      ("小", {"砂叶": 1},                          {"砂叶粉末": 3}, 1),
    "精炼-蓝铁矿":    ("小", {"蓝铁矿": 1},                        {"蓝铁块": 1}, 1),
    "精炼-致密蓝铁":  ("小", {"致密蓝铁粉末": 1},                  {"钢块": 1}, 1),
    "研磨-致密蓝铁":  ("大", {"蓝铁粉末": 2, "砂叶粉末": 1},       {"致密蓝铁粉末": 1}, 1),
    "研磨-致密源石":  ("大", {"源石粉末": 2, "砂叶粉末": 1},       {"致密源石粉末": 1}, 1),
    "研磨-细磨荞花":  ("大", {"荞花粉末": 2, "砂叶粉末": 1},       {"细磨荞花粉末": 1}, 1),
    "塑形-钢质瓶":    ("小", {"钢块": 2},                          {"钢质瓶": 1}, 1),
    "配件-钢制零件":  ("小", {"钢块": 1},                          {"钢制零件": 1}, 1),
    "种植-荞花":      ("中", {"荞花种子": 1},                      {"荞花": 1}, 1),
    "种植-砂叶":      ("中", {"砂叶种子": 1},                      {"砂叶": 1}, 1),
    "采种-荞花":      ("中", {"荞花": 1},                          {"荞花种子": 2}, 1),
    "采种-砂叶":      ("中", {"砂叶": 1},                          {"砂叶种子": 2}, 1),
    "封装-电池":      ("大", {"钢制零件": 10, "致密源石粉末": 15},  {"高容谷地电池": 1}, 5),
    "灌装-胶囊":      ("大", {"钢质瓶": 10, "细磨荞花粉末": 10},    {"精选荞愈胶囊": 1}, 5),
}

# 显式设计：每组 = (配方, [(该台每 20 tick 的批次数, 该台取货端口的条数), ...])
# 取货端口条数 n 决定每端口速率 = 产出 / n，必须整除且 ≤20。
DESIGN = [
    ("粉碎-源矿",      [(20, 1)] * 18),
    ("粉碎-蓝铁块",    [(20, 1)] * 34),
    ("粉碎-荞花",      [(20, 2)] * 5 + [(10, 1)]),     # 40 件 → 2 端口×20；20 件 → 1 端口×20
    ("粉碎-砂叶",      [(20, 3)] * 10 + [(10, 3)]),    # 60 → 3×20（满速）；30 → 3×10（C 类）
    ("精炼-蓝铁矿",    [(20, 1)] * 34),
    ("精炼-致密蓝铁",  [(20, 1)] * 17),
    ("研磨-致密蓝铁",  [(20, 1)] * 17),
    ("研磨-致密源石",  [(20, 1)] * 9),
    ("研磨-细磨荞花",  [(20, 1)] * 5 + [(10, 1)]),
    ("塑形-钢质瓶",    [(20, 1)] * 5 + [(10, 1)]),
    ("配件-钢制零件",  [(20, 1)] * 6),
    ("种植-荞花",      [(20, 1)] * 10 + [(20, 2)]),    # 1 台劈成 2×10（B 类）
    ("种植-砂叶",      [(20, 1)] * 20 + [(20, 2)]),    # 1 台劈成 2×10（B 类）
    ("采种-荞花",      [(20, 2)] * 5 + [(10, 1)]),
    ("采种-砂叶",      [(20, 2)] * 10 + [(10, 1)]),
    ("封装-电池",      [(4, 1)] * 3),
    ("灌装-胶囊",      [(4, 1), (4, 1), (3, 1)]),
]
ORE = {"蓝铁矿": 34, "源矿": 18}      # 46 仓库取货口 + 核心 6 取货端口，全部满速


class Inst:
    def __init__(self, mid, group, batches, nports):
        self.mid, self.group, self.batches, self.nports = mid, group, batches, nports
        self.size = RECIPE[group][0]
        self.out_ports, self.in_ch = [], []


insts, errs = [], []
for g, spec in DESIGN:
    for b, n in spec:
        insts.append(Inst(f"M{len(insts):03d}", g, b, n))

# 批次上限：1 tick 配方每 20 tick 至多 20 批；5 tick 配方至多 4 批
for it in insts:
    cap = P // RECIPE[it.group][3]
    if it.batches > cap:
        errs.append(f"{it.mid} {it.group} 批次 {it.batches} 超上限 {cap}")

# ---- 取货端口：均分 ----
fanout = []
for it in insts:
    for item, q in RECIPE[it.group][2].items():
        total = it.batches * q
        if total % it.nports:
            errs.append(f"{it.mid} {it.group} 产出 {total} 不能被 {it.nports} 个端口均分")
            continue
        rate = total // it.nports
        if rate > P:
            errs.append(f"{it.mid} 端口速率 {rate} >20")
        it.out_ports += [(item, rate)] * it.nports
        if it.nports >= 2:
            interval = P / it.batches
            cls = ("A 满速" if rate == P else
                   "B 原文前提内" if interval == 1 and 2 * q <= it.nports else
                   "C 需推广版")
            fanout.append(dict(机器=it.mid, 配方=it.group, 物品=item, k=it.nports,
                               每端口速率=rate, 批间隔tick=interval, 每批件数=q, 类别=cls))

# ---- 逐物品把取货端口配给存货通道，速率必须相等 ----
edges = []
for item in sorted({i for g in RECIPE for i in (set(RECIPE[g][1]) | set(RECIPE[g][2]))}):
    sup = [[it, r] for it in insts for (i2, r) in it.out_ports if i2 == item]
    sup += [[None, P] for _ in range(ORE.get(item, 0))]
    dem = [[it, it.batches * RECIPE[it.group][1][item]]
           for it in insts if item in RECIPE[it.group][1]]
    if item in ("高容谷地电池", "精选荞愈胶囊"):
        dem = [["核心", sum(s[1] for s in sup)]]
    if not sup and not dem:
        continue
    if sum(s[1] for s in sup) != sum(d[1] for d in dem):
        errs.append(f"{item} 不配平：供 {sum(s[1] for s in sup)} 需 {sum(d[1] for d in dem)}")
        continue
    sup.sort(key=lambda x: -x[1])
    for s in sup:
        dem.sort(key=lambda x: -x[1])
        if not dem or dem[0][1] < s[1]:
            errs.append(f"{item} 端口速率 {s[1]} 配不进任何剩余需求"); break
        edges.append((item, s[0], dem[0][0], s[1]))
        dem[0][1] -= s[1]
        if dem[0][1] == 0:
            dem.pop(0)

for item, s, d, r in edges:
    if d != "核心":
        d.in_ch.append((item, r))

for it in insts:
    pin, pout = PORTS[it.size]
    if len(it.in_ch) > pin or len(it.out_ports) > pout:
        errs.append(f"{it.mid} {it.group} 存货 {len(it.in_ch)}/{pin} 取货 {len(it.out_ports)}/{pout}")

n_out = sum(len(i.out_ports) for i in insts)
n_in = sum(len(i.in_ch) for i in insts)
core_in = sum(1 for e in edges if e[2] == "核心")
ore_out = sum(1 for e in edges if e[1] is None)

print("=== 检查 ===")
print("  错误：", "无" if not errs else "")
for e in errs:
    print("   !!", e)
print(f"\n  制造单位 {len(insts)} 台 / {sum(SIZE[i.size] for i in insts)} 格"
      f"（机型下限 217 台 / 3291 格）")
print(f"  通道 {len(edges)} 条；机器取货通道 {n_out}、机器存货通道 {n_in}、"
      f"出矿 {ore_out}、成品进核心 {core_in}")
print(f"  S = {n_out + ore_out}（运输端口收支 要求 ≥312）")
print(f"  R = {n_in + core_in}（要求 ≥307）")
print("  分流器 0、汇流器 0、协议储存箱 0、物品准入口 0")

print("\n=== 扇出点（机器把产出分到多个取货端口的地方）===")
for k, v in sorted(Counter(r["类别"] for r in fanout).items()):
    print(f"  {k}: {v} 处")
for r in fanout:
    if r["类别"].startswith(("B", "C")):
        print(f"    {r['类别']}  {r['机器']} {r['配方']} → {r['物品']}："
              f"k={r['k']}、每批 {r['每批件数']} 件、批间隔 {r['批间隔tick']:.0f} tick、"
              f"每端口 {r['每端口速率']}/20tick")

print("\n=== 各机型台数与对照 ===")
low = {"粉碎机": 68, "精炼炉": 51, "研磨机": 32, "塑形机": 6, "配件机": 6,
       "种植机": 32, "采种机": 16, "封装机": 3, "灌装机": 3}
mp = {"粉碎": "粉碎机", "精炼": "精炼炉", "研磨": "研磨机", "塑形": "塑形机",
      "配件": "配件机", "种植": "种植机", "采种": "采种机", "封装": "封装机", "灌装": "灌装机"}
cnt = Counter(mp[i.group.split("-")[0]] for i in insts)
for k in low:
    print(f"  {k}: {cnt[k]}（下限 {low[k]}，差 {cnt[k]-low[k]}）")

print("\n=== 与正式约束的贴边核对 ===")
gr = [i for i in insts if i.group.startswith("研磨")]
print(f"  研磨机 ≥3 条存货通道的台数 {sum(1 for i in gr if len(i.in_ch)>=3)}/32"
      f"（研磨进料 要 ≥31）")
sh = [i for i in insts if i.group.startswith("塑形")]
print(f"  塑形机 ≥2 条存货通道的台数 {sum(1 for i in sh if len(i.in_ch)>=2)}/6（要 ≥5）")
pk = [i for i in insts if i.group.startswith("封装")]
print(f"  封装机存货通道数 {[len(i.in_ch) for i in pk]}（封装进料 要每台 ≥5；恰 5 条时每条满速）"
      f"  各条速率 {[sorted(r for _,r in i.in_ch) for i in pk][0]}")
fl = [i for i in insts if i.group.startswith("灌装")]
print(f"  灌装机存货通道数 {[len(i.in_ch) for i in fl]}"
      f"（封装进料 要 ≥2 台各 ≥4；灌装混线 前提是「恰 2 台各 ≥4」，此处 3 台各 4 ⇒ 不适用）")
print(f"  成品来源 K={core_in}、B=0、C=0 ⇒ K+3B+2C={core_in}（成品汇入 要 ≥6）")

d = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(d, "channels.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["通道id", "源机器id", "源机型", "源配方", "物品", "件每20tick",
                "目标机器id", "目标机型", "目标配方", "是否满速"])
    for n, (item, s, dd, r) in enumerate(edges):
        w.writerow([f"C{n:03d}",
                    "仓库出矿口" if s is None else s.mid, "" if s is None else DIM[s.size],
                    "" if s is None else s.group, item, r,
                    "协议核心" if dd == "核心" else dd.mid,
                    "" if dd == "核心" else DIM[dd.size],
                    "" if dd == "核心" else dd.group, "是" if r == P else "否"])
with open(os.path.join(d, "machines.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["机器id", "机型", "配方", "批次每20tick", "存货通道数", "取货通道数",
                "存货通道速率", "取货通道速率", "扇出类别"])
    fo = {r["机器"]: r["类别"] for r in fanout}
    for it in insts:
        w.writerow([it.mid, DIM[it.size], it.group, it.batches, len(it.in_ch),
                    len(it.out_ports),
                    ";".join(f"{i}:{r}" for i, r in it.in_ch),
                    ";".join(f"{i}:{r}" for i, r in it.out_ports),
                    fo.get(it.mid, "单端口")])
with open(os.path.join(d, "fanout.json"), "w", encoding="utf-8") as f:
    json.dump(fanout, f, ensure_ascii=False, indent=1)
print(f"\n导出 channels.csv（{len(edges)} 行）、machines.csv（{len(insts)} 行）、fanout.json")
