#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核席第 2 轮（数值复算视角）独立复算。

纪律：
  * 规则、配方、容量、下限等常量全部从仓库根三份正式文件人工转录，逐条标行号；
    不从 正式静态目录.json 读取任何数值（目录是被复核对象之一）。
  * 候选 B 的计划从 seat-opus-4/design.py 的 DESIGN / ORE 字面量重建，
    并与 channels.csv、machines.csv、fanout.json 对照；不执行 design.py（它会改写源表）。
  * 全部用 fractions.Fraction，不用浮点。
  * 先独立算，再与 contract.json、校验报告.md 比对。

第 1 轮脚本 复算-r1/recompute.py 已自核：其 KIND_GEOM、FORMAL_* 常量与本脚本逐项相等；
其余差异见 复核-r2-数值复算.md §0。本脚本另行实现，不 import 它。
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from fractions import Fraction as F

ROOT = "/home/zhuran24/zmd-research-fresh"
SRC = "/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4"
DATA = f"{ROOT}/求解器/数据"
CONTRACT = f"{DATA}/候选B/contract.json"
CATALOG = f"{DATA}/正式静态目录.json"
REPORT = f"{DATA}/候选B/校验报告.md"

findings = []


def bad(tag, msg):
    findings.append((tag, msg))
    print(f"  !! [{tag}] {msg}")


def ok(msg):
    print(f"  ok {msg}")


# =============================================================================
# 一、正式常量（人工转录，括号内为行号）
# =============================================================================
# 游戏规则.txt L44/L50/L54：小 3x3、中 5x5、大 6x4；一条（长）边全为存货端口、对边全为取货端口
# 游戏规则.txt L12：端口占一格宽 ⇒ 端口数 = 该边格数
KIND = {
    # 机型 -> (宽, 高, 存货端口数, 取货端口数, 存货物品格数, 取货物品格数)
    "粉碎机": (3, 3, 3, 3, 1, 1),
    "精炼炉": (3, 3, 3, 3, 1, 1),
    "配件机": (3, 3, 3, 3, 1, 1),
    "塑形机": (3, 3, 3, 3, 1, 1),
    "种植机": (5, 5, 5, 5, 1, 1),
    "采种机": (5, 5, 5, 5, 1, 1),
    "研磨机": (6, 4, 6, 6, 2, 1),
    "封装机": (6, 4, 6, 6, 2, 1),
    "灌装机": (6, 4, 6, 6, 2, 1),
}
KIND_AREA = {k: v[0] * v[1] for k, v in KIND.items()}

# 游戏规则.txt L80-114：配方
RECIPES = {
    "粉碎-源矿":     ("粉碎机", {"源矿": 1}, {"源石粉末": 1}, 1),
    "粉碎-蓝铁块":   ("粉碎机", {"蓝铁块": 1}, {"蓝铁粉末": 1}, 1),
    "粉碎-荞花":     ("粉碎机", {"荞花": 1}, {"荞花粉末": 2}, 1),
    "粉碎-砂叶":     ("粉碎机", {"砂叶": 1}, {"砂叶粉末": 3}, 1),
    "精炼-蓝铁矿":   ("精炼炉", {"蓝铁矿": 1}, {"蓝铁块": 1}, 1),
    "精炼-致密蓝铁": ("精炼炉", {"致密蓝铁粉末": 1}, {"钢块": 1}, 1),
    "精炼-蓝铁粉末": ("精炼炉", {"蓝铁粉末": 1}, {"蓝铁块": 1}, 1),   # L89，候选未用
    "研磨-致密蓝铁": ("研磨机", {"蓝铁粉末": 2, "砂叶粉末": 1}, {"致密蓝铁粉末": 1}, 1),
    "研磨-致密源石": ("研磨机", {"源石粉末": 2, "砂叶粉末": 1}, {"致密源石粉末": 1}, 1),
    "研磨-细磨荞花": ("研磨机", {"荞花粉末": 2, "砂叶粉末": 1}, {"细磨荞花粉末": 1}, 1),
    "塑形-钢质瓶":   ("塑形机", {"钢块": 2}, {"钢质瓶": 1}, 1),
    "配件-钢制零件": ("配件机", {"钢块": 1}, {"钢制零件": 1}, 1),
    "种植-荞花":     ("种植机", {"荞花种子": 1}, {"荞花": 1}, 1),
    "种植-砂叶":     ("种植机", {"砂叶种子": 1}, {"砂叶": 1}, 1),
    "采种-荞花":     ("采种机", {"荞花": 1}, {"荞花种子": 2}, 1),
    "采种-砂叶":     ("采种机", {"砂叶": 1}, {"砂叶种子": 2}, 1),
    "封装-电池":     ("封装机", {"钢制零件": 10, "致密源石粉末": 15}, {"高容谷地电池": 1}, 5),
    "灌装-胶囊":     ("灌装机", {"钢质瓶": 10, "细磨荞花粉末": 10}, {"精选荞愈胶囊": 1}, 5),
}

# 求解任务.txt L2：目标
TARGETS = {"高容谷地电池": F(18, 30), "精选荞愈胶囊": F(33, 60)}
# 求解约束.txt L30 端口速率：每端口每 tick 至多 1 件
PORT_CAP = F(1)
# 求解约束.txt L41 协议核心：存货端口 14、取货端口 6、格上限 80000
CORE_IN, CORE_OUT = 14, 6
# 求解约束.txt L32 出库上限：左、下各 23 个仓库取货口，核心 6 个取货端口，共 52
DOM_LEFT, DOM_BOTTOM, DOM_CORE = 23, 23, 6
# 求解约束.txt L46 机型下限
MIN_MACHINES = {"粉碎机": 68, "精炼炉": 51, "研磨机": 32, "塑形机": 6, "配件机": 6,
                "种植机": 32, "采种机": 16, "封装机": 3, "灌装机": 3}
MIN_AREA_TOTAL = 3291
# 求解约束.txt L48 通道下限
MIN_IN_CH = {"粉碎机": 68, "精炼炉": 51, "研磨机": 95, "塑形机": 11, "配件机": 6,
             "种植机": 32, "采种机": 16, "封装机": 15, "灌装机": 11}
MIN_OUT_CH = {"粉碎机": 95, "精炼炉": 51, "研磨机": 32, "塑形机": 6, "配件机": 6,
              "种植机": 32, "采种机": 32, "封装机": 1, "灌装机": 1}
# 求解约束.txt L44 物料流量（件/tick）
FLOW = {
    "蓝铁矿": F(34), "源矿": F(18), "蓝铁块": F(34), "蓝铁粉末": F(34), "源石粉末": F(18),
    "砂叶粉末": F(63, 2), "砂叶": F(21), "砂叶种子": F(21), "荞花": F(11), "荞花种子": F(11),
    "荞花粉末": F(11), "致密蓝铁粉末": F(17), "钢块": F(17), "致密源石粉末": F(9),
    "细磨荞花粉末": F(11, 2), "钢制零件": F(6), "钢质瓶": F(11, 2),
    "高容谷地电池": F(3, 5), "精选荞愈胶囊": F(11, 20),
}
FLOW_TOTAL = F(30565, 100)   # 求解约束.txt L44「合计 305.65 件」
# 求解约束.txt L22 单位矿耗
ORE_PER_BATTERY = {"蓝铁矿": 20, "源矿": 30}
ORE_PER_CAPSULE = {"蓝铁矿": 40}
# 求解约束.txt L76 运输端口收支
S_MIN, R_MIN = 312, 307

# =============================================================================
# 二、独立重建候选 B（design.py 的 DESIGN / ORE 字面量，件/20tick）
# =============================================================================
P = 20
DESIGN = [
    ("粉碎-源矿",     [(20, 1)] * 18),
    ("粉碎-蓝铁块",   [(20, 1)] * 34),
    ("粉碎-荞花",     [(20, 2)] * 5 + [(10, 1)]),
    ("粉碎-砂叶",     [(20, 3)] * 10 + [(10, 3)]),
    ("精炼-蓝铁矿",   [(20, 1)] * 34),
    ("精炼-致密蓝铁", [(20, 1)] * 17),
    ("研磨-致密蓝铁", [(20, 1)] * 17),
    ("研磨-致密源石", [(20, 1)] * 9),
    ("研磨-细磨荞花", [(20, 1)] * 5 + [(10, 1)]),
    ("塑形-钢质瓶",   [(20, 1)] * 5 + [(10, 1)]),
    ("配件-钢制零件", [(20, 1)] * 6),
    ("种植-荞花",     [(20, 1)] * 10 + [(20, 2)]),
    ("种植-砂叶",     [(20, 1)] * 20 + [(20, 2)]),
    ("采种-荞花",     [(20, 2)] * 5 + [(10, 1)]),
    ("采种-砂叶",     [(20, 2)] * 10 + [(10, 1)]),
    ("封装-电池",     [(4, 1)] * 3),
    ("灌装-胶囊",     [(4, 1), (4, 1), (3, 1)]),
]
ORE = {"蓝铁矿": 34, "源矿": 18}


class Inst:
    def __init__(self, mid, group, batches, nports):
        self.mid, self.group, self.batches, self.nports = mid, group, batches, nports
        self.kind = RECIPES[group][0]
        self.out_ports = []
        self.in_ch = []

    @property
    def rate(self):                       # 批/tick
        return F(self.batches, P)


insts = []
for g, spec in DESIGN:
    for b, n in spec:
        insts.append(Inst(f"M{len(insts):03d}", g, b, n))
by_id = {i.mid: i for i in insts}

print("=" * 78)
print("A. 独立重建：机器、端口、通道")
print("=" * 78)

# A1 制造能力上限：批次率×耗时 ≤1（据：制造，一次制造的用量进缓存格后立刻开始、无冷却）
for it in insts:
    if it.rate * RECIPES[it.group][3] > 1:
        bad("制造能力", f"{it.mid} {it.group} 负荷 {it.rate*RECIPES[it.group][3]}>1")

# A2 取货端口均分
fanout = []
for it in insts:
    for item, q in RECIPES[it.group][2].items():
        total = it.batches * q                      # 件/20tick
        if total % it.nports:
            bad("扇出不能均分", f"{it.mid} {total}/{it.nports}")
            continue
        rate = F(total // it.nports, P)              # 件/tick
        if rate > PORT_CAP:
            bad("端口超速", f"{it.mid} {rate}>1")
        it.out_ports += [(item, rate)] * it.nports
        if it.nports >= 2:
            fanout.append(dict(machine=it.mid, recipe=it.group, item=item,
                               k=it.nports, port_rate=rate,
                               interval=F(P, it.batches), q=q))

# A3 逐物品配边（复现 design.py 的贪心，用于得到与源 CSV 同一张通道表）
edges = []
items_all = sorted({i for g in RECIPES for i in (set(RECIPES[g][1]) | set(RECIPES[g][2]))})
for item in items_all:
    sup = [[it, r] for it in insts for (i2, r) in it.out_ports if i2 == item]
    sup += [[None, F(1)] for _ in range(ORE.get(item, 0))]
    dem = [[it, it.rate * RECIPES[it.group][1][item]]
           for it in insts if item in RECIPES[it.group][1]]
    if item in TARGETS:
        dem = [["核心", sum((s[1] for s in sup), F(0))]]
    if not sup and not dem:
        continue
    if sum((s[1] for s in sup), F(0)) != sum((d[1] for d in dem), F(0)):
        bad("物品不配平", f"{item} 供 {sum((s[1] for s in sup),F(0))} 需 {sum((d[1] for d in dem),F(0))}")
        continue
    sup.sort(key=lambda x: -x[1])
    for s in sup:
        dem.sort(key=lambda x: -x[1])
        if not dem or dem[0][1] < s[1]:
            bad("配不进", f"{item} rate={s[1]}")
            break
        edges.append((item, s[0], dem[0][0], s[1]))
        dem[0][1] -= s[1]
        if dem[0][1] == 0:
            dem.pop(0)
for item, s, d, r in edges:
    if d != "核心":
        d.in_ch.append((item, r))

# A4 端口数不超机型容量
for it in insts:
    _, _, cin, cout, _, _ = KIND[it.kind]
    if len(it.in_ch) > cin or len(it.out_ports) > cout:
        bad("端口数超限", f"{it.mid} 存货 {len(it.in_ch)}/{cin} 取货 {len(it.out_ports)}/{cout}")

n_out = sum(len(i.out_ports) for i in insts)
n_in = sum(len(i.in_ch) for i in insts)
core_in = sum(1 for e in edges if e[2] == "核心")
ore_out = sum(1 for e in edges if e[1] is None)
area = sum(KIND_AREA[i.kind] for i in insts)
kind_cnt = Counter(i.kind for i in insts)
size_cnt = Counter(KIND_AREA[i.kind] for i in insts)

mine = {
    "制造单位": len(insts), "制造占格": area, "逻辑送料记录": len(edges),
    "S": n_out + ore_out, "R": n_in + core_in,
    "机器取货端口": n_out, "机器存货端口": n_in, "矿石来源": ore_out, "成品进核心": core_in,
}
for k, v in mine.items():
    print(f"  {k}: {v}")
print(f"  机型台数: {dict(sorted(kind_cnt.items()))}")
print(f"  按占格分组: {dict(sorted(size_cnt.items()))}  (9*n+25*n+24*n = {area})")

gr = [i for i in insts if i.kind == "研磨机"]
sh = [i for i in insts if i.kind == "塑形机"]
pk = [i for i in insts if i.kind == "封装机"]
fl = [i for i in insts if i.kind == "灌装机"]
g3 = sum(1 for i in gr if len(i.in_ch) >= 3)
s2 = sum(1 for i in sh if len(i.in_ch) >= 2)
print(f"  研磨机 ≥3 存货通道 {g3}/{len(gr)}；例外 {[(i.mid,len(i.in_ch)) for i in gr if len(i.in_ch)!=3]}")
print(f"  塑形机 ≥2 存货通道 {s2}/{len(sh)}；例外 {[(i.mid,len(i.in_ch)) for i in sh if len(i.in_ch)!=2]}")
print(f"  封装机存货通道 {[len(i.in_ch) for i in pk]}  逐条速率 {[sorted(str(r) for _,r in i.in_ch) for i in pk]}")
print(f"  灌装机存货通道 {[len(i.in_ch) for i in fl]}  逐条速率 {[sorted(str(r) for _,r in i.in_ch) for i in fl]}")
print(f"  成品来源 K={core_in}、B=0、C=0 ⇒ K+3B+2C={core_in}")
multi_ids = [i.mid for i in insts if len(RECIPES[i.group][1]) >= 2]
print(f"  多料机（配方投入 ≥2 种）{len(multi_ids)}：{dict(Counter(by_id[m].kind for m in multi_ids))}")

# A5 扇出分类（独立按「满速 / 批间隔 1 且 2q≤k / 其余」实现）
for f in fanout:
    f["shape"] = ("满速扇出定则型" if f["port_rate"] == PORT_CAP else
                  "轮询均分型" if f["interval"] == 1 and 2 * f["q"] <= f["k"] else
                  "两者都不落")
shape_cnt = Counter(f["shape"] for f in fanout)
print(f"  扇出点 {len(fanout)} 处，分类 {dict(sorted(shape_cnt.items()))}")
for f in fanout:
    if f["shape"] != "满速扇出定则型":
        print(f"    {f['shape']}  {f['machine']} {f['recipe']}→{f['item']} "
              f"k={f['k']} 每批 {f['q']} 件 平均批间隔 {f['interval']} 每端口 {f['port_rate']}/tick")

# =============================================================================
# 三、守恒与正式条目的静态投影
# =============================================================================
print()
print("=" * 78)
print("B. 守恒与正式条目投影（件/tick，有理数）")
print("=" * 78)
prod, cons = defaultdict(F), defaultdict(F)
batch_by_recipe = defaultdict(F)
for it in insts:
    batch_by_recipe[it.group] += it.rate
    for item, q in RECIPES[it.group][2].items():
        prod[item] += it.rate * q
    for item, q in RECIPES[it.group][1].items():
        cons[item] += it.rate * q
ext = {k: F(v) for k, v in ORE.items()}
deliver = {k: prod[k] for k in TARGETS}
for item in sorted(set(prod) | set(cons) | set(ext)):
    src = prod[item] + ext.get(item, F(0))
    snk = cons[item] + deliver.get(item, F(0))
    if src != snk:
        bad("全局守恒", f"{item} 供 {src} ≠ 耗 {snk}")
    need = FLOW.get(item)
    mark = ""
    if need is not None:
        mark = f"  物料流量 ≥{need} {'ok' if snk >= need else '!! 低于'}"
        if snk < need:
            bad("物料流量", f"{item} {snk} < {need}")
    print(f"  {item:8s} 供 {str(src):8s} 耗 {str(snk):8s}{mark}")
tot = sum((min(prod[i] + ext.get(i, F(0)), FLOW[i]) if False else FLOW[i]) for i in FLOW)
print(f"  物料流量表合计（正式）= {tot} （条文写 {FLOW_TOTAL}） "
      f"{'ok' if tot == FLOW_TOTAL else '!! 不符'}")
if tot != FLOW_TOTAL:
    bad("物料流量合计", f"{tot} != {FLOW_TOTAL}")
for item, t in TARGETS.items():
    print(f"  目标 {item}: 计划 {deliver[item]}  正式 {t}  {'ok' if deliver[item]==t else '!! 不符'}")
    if deliver[item] != t:
        bad("目标", f"{item} {deliver[item]} != {t}")

# 单位矿耗 / 矿石需求
b, c_ = deliver["高容谷地电池"], deliver["精选荞愈胶囊"]
want_fe = b * ORE_PER_BATTERY["蓝铁矿"] + c_ * ORE_PER_CAPSULE["蓝铁矿"]
want_yk = b * ORE_PER_BATTERY["源矿"]
print(f"  单位矿耗：蓝铁矿 需 {want_fe} 计划 {ext['蓝铁矿']}；源矿 需 {want_yk} 计划 {ext['源矿']}；"
      f"合计 {ext['蓝铁矿']+ext['源矿']}（出库上限 52）")
if want_fe != ext["蓝铁矿"] or want_yk != ext["源矿"]:
    bad("单位矿耗", f"{want_fe}/{want_yk} vs {ext['蓝铁矿']}/{ext['源矿']}")
if ext["蓝铁矿"] + ext["源矿"] != 52:
    bad("出库上限", f"矿石出库 {ext['蓝铁矿']+ext['源矿']} != 52")

# 回路守恒
for plant in ("荞花", "砂叶"):
    seed = batch_by_recipe[f"采种-{plant}"]
    crush = batch_by_recipe[f"粉碎-{plant}"]
    grow = batch_by_recipe[f"种植-{plant}"]
    print(f"  回路守恒 {plant}：采种 {seed}、粉碎 {crush}、种植 {grow}；入库 0")
    if seed != crush or grow != 2 * seed:
        bad("回路守恒", f"{plant} 采种 {seed} 粉碎 {crush} 种植 {grow}")
exp = {"荞花": (F(11, 2), F(11)), "砂叶": (F(21, 2), F(21))}
for plant, (s_, g_) in exp.items():
    got = (batch_by_recipe[f"采种-{plant}"], batch_by_recipe[f"种植-{plant}"])
    if got != (s_, g_):
        bad("回路守恒/定值", f"{plant} {got} != {(s_,g_)}")

# 机型下限 / 通道下限
in_by_kind = Counter()
out_by_kind = Counter()
for it in insts:
    in_by_kind[it.kind] += len(it.in_ch)
    out_by_kind[it.kind] += len(it.out_ports)
print("  机型 / 台数 ≥下限 / 存货通道 ≥下限 / 取货通道 ≥下限")
for k in MIN_MACHINES:
    r1 = kind_cnt[k] >= MIN_MACHINES[k]
    r2 = in_by_kind[k] >= MIN_IN_CH[k]
    r3 = out_by_kind[k] >= MIN_OUT_CH[k]
    print(f"    {k}: {kind_cnt[k]}≥{MIN_MACHINES[k]} {r1} | "
          f"{in_by_kind[k]}≥{MIN_IN_CH[k]} {r2} | {out_by_kind[k]}≥{MIN_OUT_CH[k]} {r3}")
    for cond, tag in ((r1, "机型下限"), (r2, "存货通道下限"), (r3, "取货通道下限")):
        if not cond:
            bad(tag, k)
print(f"    合计 存货 {sum(in_by_kind.values())}（下限 305）、取货 {sum(out_by_kind.values())}（下限 256）")

# 满载配置（只对恰为下限的机型）
for k in ("粉碎机", "精炼炉", "配件机", "种植机", "采种机", "封装机"):
    if kind_cnt[k] == MIN_MACHINES[k]:
        loads = {str(i.rate * RECIPES[i.group][3]) for i in insts if i.kind == k}
        print(f"  满载配置触发 {k}（{kind_cnt[k]} 台）：逐台负荷集合 {loads}")
        if loads != {"1"}:
            bad("满载配置", f"{k} 负荷 {loads}")
    else:
        print(f"  满载配置不触发 {k}（{kind_cnt[k]} 台 ≠ 下限 {MIN_MACHINES[k]}）")

# 研磨进料 / 封装进料
if kind_cnt["研磨机"] == 32 and g3 < 31:
    bad("研磨进料", f"研磨 ≥3 存货通道仅 {g3}")
if kind_cnt["塑形机"] == 6 and s2 < 5:
    bad("研磨进料", f"塑形 ≥2 存货通道仅 {s2}")
if kind_cnt["采种机"] == 16 and any(len(i.out_ports) < 2 for i in insts if i.kind == "采种机"):
    bad("研磨进料", "采种恰 16 台但有台取货通道 <2")
if kind_cnt["封装机"] == 3:
    for i in pk:
        if len(i.in_ch) < 5:
            bad("封装进料", f"{i.mid} 存货通道 {len(i.in_ch)}<5")
        if len(i.in_ch) == 5 and any(r != 1 for _, r in i.in_ch):
            bad("封装进料", f"{i.mid} 恰 5 条但非每条 1 件/tick")
if kind_cnt["灌装机"] == 3:
    n4 = sum(1 for i in fl if len(i.in_ch) >= 4)
    print(f"  灌装机 ≥4 存货通道台数 {n4}（封装进料要 ≥2；灌装混线前件是「恰 2」）")
    if n4 < 2:
        bad("封装进料", f"灌装 ≥4 存货通道仅 {n4}")

# 矿线专机
ore_targets = [(e[0], e[2]) for e in edges if e[1] is None]
prof = Counter()
for item, tgt in ore_targets:
    want = "粉碎-源矿" if item == "源矿" else "精炼-蓝铁矿"
    if tgt.group != want or tgt.rate != 1 or len(tgt.in_ch) != 1:
        bad("矿线专机", f"{tgt.mid} {tgt.group} 批率 {tgt.rate} 存货通道 {len(tgt.in_ch)}")
    prof[tgt.group] += 1
print(f"  矿线专机：{dict(prof)}；专机身份互异 {len({t.mid for _,t in ore_targets})} 台")
if prof.get("精炼-蓝铁矿") != 34 or prof.get("粉碎-源矿") != 18:
    bad("矿线专机", f"专机分布 {dict(prof)} 不是 34 精炼 + 18 粉碎")

# 运输端口收支 / 箱体接口（B0=B1=0、D=M=0）
S, R = mine["S"], mine["R"]
H = max(2, 0)
eta = 2 * 0 + max(H - 2, 5 - 2 * 0, 2 * H - 9 - 2 * 0)
print(f"  运输端口收支：S={S}≥{S_MIN}、R={R}≥{R_MIN}、R−S={R-S}（D=M=0 ⇒ 须为 0）")
if not (S >= S_MIN and R >= R_MIN and R - S == 0):
    bad("运输端口收支", f"S={S} R={R}")
print(f"  箱体接口：H={H}、η={eta}、S+R={S+R} ≥ 619+η={619+eta} "
      f"{'ok' if S+R >= 619+eta else '!! 不足'}")
if S + R < 619 + eta:
    bad("箱体接口", f"S+R={S+R} < {619+eta}")
print(f"  箱体过站：C矿={len({t.mid for _,t in ore_targets})}、D矿=0 ⇒ Q≥{52-len({t.mid for _,t in ore_targets})-0}")

# 成品汇入
print(f"  成品汇入：K={core_in} ≤ 核心存货端口 {CORE_IN}，K+3B+2C={core_in} ≥6 "
      f"{'ok' if core_in>=6 else '!! 不足'}")

# =============================================================================
# 四、与 contract.json 逐项比对
# =============================================================================
print()
print("=" * 78)
print("C. 与 contract.json（feeding-v2）比对")
print("=" * 78)
C = json.load(open(CONTRACT, encoding="utf-8"))


def q(x):
    return None if x is None else F(x["value"])


def cat_of(x):
    return None if x is None else x["category"]


print(f"  schema={C['schema']} candidate={C['candidate']} rate_window={q(C['rate_window'])}")
print(f"  machines {len(C['machines'])}  logical_feeds {len(C['logical_feeds'])}"
      f"  sources {len(C['sources'])}  fanouts {len(C['fanouts'])}")
if "channels" in C:
    bad("旧字段", "contract.json 仍有 channels 顶层字段")
cm = {m["id"]: m for m in C["machines"]}
if set(cm) != set(by_id):
    bad("机器集合", f"差异 {sorted(set(cm) ^ set(by_id))[:10]}")
for mid, m in sorted(cm.items()):
    it = by_id.get(mid)
    if it is None:
        continue
    if m["kind"] != it.kind:
        bad("机型", f"{mid} {m['kind']} != {it.kind}")
    if len(m["recipes"]) != 1 or m["recipes"][0]["recipe"] != it.group:
        bad("配方", f"{mid} {m['recipes']} != {it.group}")
    if q(m["recipes"][0]["planned_batch_rate"]) != it.rate:
        bad("批次率", f"{mid} {q(m['recipes'][0]['planned_batch_rate'])} != {it.rate}")
    if q(m["recipes"][0]["planned_mean_batch_interval"]) != 1 / it.rate:
        bad("平均批间隔", f"{mid} {q(m['recipes'][0]['planned_mean_batch_interval'])} != {1/it.rate}")
    _, _, cin, cout, _, _ = KIND[it.kind]
    if q(m["input_ports"]) != cin or q(m["output_ports"]) != cout:
        bad("端口容量", f"{mid} {q(m['input_ports'])}/{q(m['output_ports'])} != {cin}/{cout}")
    if q(m["area"]) != KIND_AREA[it.kind]:
        bad("占格", f"{mid} {q(m['area'])} != {KIND_AREA[it.kind]}")
    want_multi = len(RECIPES[it.group][1]) >= 2
    if want_multi != (m["multi_material"] is not None):
        bad("多料标记", f"{mid} 应为 {want_multi}")
    if want_multi and any(m["multi_material"][k] != "待验"
                          for k in ("arrival_composition_per_tick", "synchronization", "same_source")):
        bad("多料栏", f"{mid} {m['multi_material']}")

# 逻辑送料记录多重集比对
mine_ms = Counter()
for item, s, d, r in edges:
    mine_ms[(item, "ORE" if s is None else s.mid, "CORE" if d == "核心" else d.mid, r)] += 1
theirs_ms = Counter()
for e in C["logical_feeds"]:
    src = "ORE" if e["source"].startswith("ORE") else e["source"]
    theirs_ms[(e["item"], src, e["target"], q(e["planned_rate"]))] += 1
if mine_ms == theirs_ms:
    ok("逻辑送料多重集（物品/源/目标/速率）与独立重建完全一致")
else:
    d1 = mine_ms - theirs_ms
    d2 = theirs_ms - mine_ms
    bad("送料表", f"独立重建多 {sum(d1.values())} 条、契约多 {sum(d2.values())} 条："
                  f"{list(d1.items())[:5]} / {list(d2.items())[:5]}")

# id 规范与与原 C 编号的对应
bad_id = [e["id"] for e in C["logical_feeds"]
          if not re.fullmatch(r"LF\d+", e["id"])]
if bad_id:
    bad("LF 身份", f"{len(bad_id)} 条不合 LF+数字：{bad_id[:5]}")
nums = sorted(int(e["id"][2:]) for e in C["logical_feeds"])
if nums != list(range(len(nums))):
    bad("LF 编号", f"不是 0..{len(nums)-1} 连续：缺 {set(range(len(nums)))-set(nums)}")

# proven_actual_rate / via
nz = [e["id"] for e in C["logical_feeds"] if e["proven_actual_rate"] is not None]
if nz:
    bad("已证速率", f"{len(nz)} 条非空")
via_bad = [e["id"] for e in C["logical_feeds"]
           if set(e["via"]) != {"bridge", "splitter", "merger", "gate"}
           or any(e["via"][k] not in (None, False) for k in ("splitter", "merger", "gate"))]
if via_bad:
    bad("via", f"{len(via_bad)} 条不合：{via_bad[:5]}")

# 端口负荷与身份
port_rate = defaultdict(F)
port_feeds = defaultdict(list)
for e in C["logical_feeds"]:
    port_rate[("out", e["source"], e["source_port"])] += q(e["planned_rate"])
    port_rate[("in", e["target"], e["target_port"])] += q(e["planned_rate"])
    port_feeds[("out", e["source"], e["source_port"])].append(e["id"])
    port_feeds[("in", e["target"], e["target_port"])].append(e["id"])
over = {k: v for k, v in port_rate.items() if v > PORT_CAP}
print(f"  端口身份 {len(port_rate)} 个（取货 {sum(1 for k in port_rate if k[0]=='out')}、"
      f"存货 {sum(1 for k in port_rate if k[0]=='in')}）；超 1 件/tick 的 {len(over)}")
if over:
    bad("端口速率", f"{len(over)} 个端口 >1：{list(over.items())[:5]}")
share = {k: v for k, v in port_feeds.items() if len(v) > 1}
if share:
    print(f"  多条记录共用同一端口的端口数 {len(share)}")
# 端口 id 前缀须与所属单位一致
mism = [(k, ) for k in port_rate if not k[2].startswith(k[1] + ":")]
if mism:
    bad("端口身份前缀", f"{len(mism)} 个端口 id 与单位不符：{mism[:5]}")
# 每单位每侧端口身份数 ≤ 容量
side_ports = defaultdict(set)
for side, owner, pid in port_rate:
    side_ports[(side, owner)].add(pid)
for (side, owner), pids in sorted(side_ports.items()):
    if owner == "CORE":
        cap = CORE_IN if side == "in" else CORE_OUT
    elif owner.startswith("ORE"):
        cap = 1
    else:
        _, _, cin, cout, _, _ = KIND[cm[owner]["kind"]]
        cap = cin if side == "in" else cout
    if len(pids) > cap:
        bad("端口数", f"{owner} {side} 用 {len(pids)} > {cap}")

# 用 contract 的记录重算逐机逐配方守恒
cin_map, cout_map = defaultdict(F), defaultdict(F)
for e in C["logical_feeds"]:
    if not e["source"].startswith("ORE"):
        cout_map[(e["source"], e["item"])] += q(e["planned_rate"])
    if e["target"] != "CORE":
        cin_map[(e["target"], e["item"])] += q(e["planned_rate"])
n_bal = 0
for mid, m in cm.items():
    rec = m["recipes"][0]["recipe"]
    br = q(m["recipes"][0]["planned_batch_rate"])
    for item, n in RECIPES[rec][1].items():
        if cin_map[(mid, item)] != br * n:
            bad("逐机进料", f"{mid} {item} {cin_map[(mid,item)]} != {br*n}")
            n_bal += 1
    for item, n in RECIPES[rec][2].items():
        if cout_map[(mid, item)] != br * n:
            bad("逐机出料", f"{mid} {item} {cout_map[(mid,item)]} != {br*n}")
            n_bal += 1
    extra_in = {i for (mm, i) in cin_map if mm == mid and cin_map[(mm, i)] != 0} - set(RECIPES[rec][1])
    if extra_in:
        bad("多余进料", f"{mid} {extra_in}")
print(f"  逐机逐配方守恒不符 {n_bal} 项")

# 38 台多料机逐台进料复算
print()
print("  38 台多料机进料复算：")
mm = sorted([m for m in C["machines"] if m["multi_material"] is not None], key=lambda x: x["id"])
print(f"    多料机 {len(mm)} 台 {dict(Counter(m['kind'] for m in mm))}")
if len(mm) != 38:
    bad("多料机台数", f"{len(mm)} != 38")
if {m["id"] for m in mm} != set(multi_ids):
    bad("多料机身份", "与独立重建不同")
agg = Counter()
for m in mm:
    rec = m["recipes"][0]["recipe"]
    br = q(m["recipes"][0]["planned_batch_rate"])
    want = {i: br * n for i, n in RECIPES[rec][1].items()}
    got = {i: cin_map[(m["id"], i)] for i in want}
    chn = [e for e in C["logical_feeds"] if e["target"] == m["id"]]
    per_item_ch = Counter(e["item"] for e in chn)
    agg[(rec, tuple(sorted((i, str(v)) for i, v in want.items())), tuple(sorted(per_item_ch.items())))] += 1
    if want != got:
        bad("多料进料", f"{m['id']} 应 {want} 实 {got}")
    # 每种原料的通道数必须够（每端口 ≤1 件/tick）
    for i, v in want.items():
        import math
        need = math.ceil(v)
        if per_item_ch[i] < need:
            bad("多料进料端口数", f"{m['id']} {i} 需 ≥{need} 条，实 {per_item_ch[i]}")
for key, n in sorted(agg.items(), key=lambda x: -x[1]):
    print(f"    {n:2d} 台  {key[0]}  每 tick 应到 {dict(key[1])}  通道数 {dict(key[2])}")

# 扇出比对
print()
fo_mine = {f["machine"]: f for f in fanout}
fo_c = {f["machine"]: f for f in C["fanouts"]}
if set(fo_mine) != set(fo_c):
    bad("扇出集合", f"{sorted(set(fo_mine) ^ set(fo_c))}")
for k, f in fo_mine.items():
    g = fo_c.get(k)
    if not g:
        continue
    for name, a, b2 in (("ports", F(f["k"]), q(g["ports"])),
                        ("port_rate", f["port_rate"], q(g["planned_port_rate"])),
                        ("interval", f["interval"], q(g["planned_mean_batch_interval"])),
                        ("batch_size", F(f["q"]), q(g["batch_size"]))):
        if a != b2:
            bad("扇出字段", f"{k}.{name} 契约 {b2} != 复算 {a}")
    if g["planned_shape"] != f["shape"]:
        bad("扇出分类", f"{k} 契约 {g['planned_shape']} != 复算 {f['shape']}")
    if g["certification"] != "待验":
        bad("扇出认证栏", f"{k} {g['certification']}")
    if g["item"] != f["item"] or g["recipe"] != f["recipe"]:
        bad("扇出引用", f"{k} {g['recipe']}/{g['item']}")
print(f"  契约扇出分类 {dict(sorted(Counter(g['planned_shape'] for g in C['fanouts']).items()))}"
      f"；复算 {dict(sorted(shape_cnt.items()))}")

# 来源变量
srcs = C["sources"]
print(f"  来源变量 {len(srcs)}，物品 {dict(Counter(s['item'] for s in srcs))}，"
      f"身份 {dict(Counter(s['identity']['status'] for s in srcs))}")
if dict(Counter(s["item"] for s in srcs)) != {"源矿": 18, "蓝铁矿": 34}:
    bad("来源物品", str(Counter(s["item"] for s in srcs)))
if (q(C["source_domain"]["left"]), q(C["source_domain"]["bottom"]), q(C["source_domain"]["core"])) \
        != (F(DOM_LEFT), F(DOM_BOTTOM), F(DOM_CORE)):
    bad("来源域", str(C["source_domain"]))
print(f"  来源域类别：left={cat_of(C['source_domain']['left'])}、"
      f"bottom={cat_of(C['source_domain']['bottom'])}、core={cat_of(C['source_domain']['core'])}")
# targets
for item, t in TARGETS.items():
    if q(C["targets"][item]) != t:
        bad("targets", f"{item} {q(C['targets'][item])} != {t}")
if (q(C["core"]["input_ports"]), q(C["core"]["output_ports"])) != (F(CORE_IN), F(CORE_OUT)):
    bad("核心端口", str(C["core"]))
# 按契约自身的 S/R 定义（不同端点端口去重）复算
s_set = {(e["source"], e["source_port"]) for e in C["logical_feeds"]}
r_set = {(e["target"], e["target_port"]) for e in C["logical_feeds"]}
print(f"  契约 S={len(s_set)}、R={len(r_set)}（复算 S={S}、R={R}）")
if len(s_set) != S or len(r_set) != R:
    bad("S/R", f"契约 {len(s_set)}/{len(r_set)} != 复算 {S}/{R}")

# =============================================================================
# 五、与原 CSV / fanout.json 比对
# =============================================================================
print()
print("=" * 78)
print("D. 与 seat-opus-4 原表比对")
print("=" * 78)
rows = list(csv.DictReader(open(f"{SRC}/channels.csv", encoding="utf-8")))
csv_ms = Counter()
for r in rows:
    s = "ORE" if r["源机器id"] == "仓库出矿口" else r["源机器id"]
    d = "CORE" if r["目标机器id"] == "协议核心" else r["目标机器id"]
    csv_ms[(r["物品"], s, d, F(int(r["件每20tick"]), P))] += 1
print(f"  channels.csv {len(rows)} 行；与独立重建一致 {csv_ms==mine_ms}；与契约一致 {csv_ms==theirs_ms}")
if csv_ms != mine_ms:
    bad("原 CSV", "channels.csv 与独立重建不一致")
# 逐条 C 编号 → LF 编号
csv_by_id = {r["通道id"]: r for r in rows}
lf_by_id = {e["id"]: e for e in C["logical_feeds"]}
mapped = 0
for cid, r in csv_by_id.items():
    lid = "LF" + cid[1:]
    e = lf_by_id.get(lid)
    if e is None:
        bad("C→LF 映射", f"{cid} 无 {lid}")
        continue
    src = "ORE" if r["源机器id"] == "仓库出矿口" else r["源机器id"]
    tgt = "CORE" if r["目标机器id"] == "协议核心" else r["目标机器id"]
    esrc = "ORE" if e["source"].startswith("ORE") else e["source"]
    if (r["物品"], src, tgt, F(int(r["件每20tick"]), P)) != \
       (e["item"], esrc, e["target"], q(e["planned_rate"])):
        bad("C→LF 逐条", f"{cid}→{lid} 不符")
    else:
        mapped += 1
print(f"  逐条 C→LF 编号对应且内容相同：{mapped}/{len(rows)}")
mrows = list(csv.DictReader(open(f"{SRC}/machines.csv", encoding="utf-8")))
deg_bad = [r["机器id"] for r in mrows
           if int(r["存货通道数"]) != len(by_id[r["机器id"]].in_ch)
           or int(r["取货通道数"]) != len(by_id[r["机器id"]].out_ports)]
print(f"  machines.csv {len(mrows)} 行；度数不符 {len(deg_bad)}")
if deg_bad:
    bad("machines.csv", str(deg_bad[:5]))
fj = json.load(open(f"{SRC}/fanout.json", encoding="utf-8"))
print(f"  fanout.json {len(fj)} 条；原分类 {dict(sorted(Counter(x['类别'] for x in fj).items()))}")
map_shape = {"A 满速": "满速扇出定则型", "B 原文前提内": "轮询均分型", "C 需推广版": "两者都不落"}
for x in fj:
    mid = x["机器"]
    if map_shape.get(x["类别"]) != fo_mine[mid]["shape"]:
        bad("扇出原分类映射", f"{mid} {x['类别']} → {fo_mine[mid]['shape']}")
    if F(x["每端口速率"], P) != fo_mine[mid]["port_rate"]:
        bad("扇出原速率", f"{mid} {x['每端口速率']}/20 != {fo_mine[mid]['port_rate']}")
    if F(str(x["批间隔tick"])) != fo_mine[mid]["interval"]:
        bad("扇出原批间隔", f"{mid} {x['批间隔tick']} != {fo_mine[mid]['interval']}")

# =============================================================================
# 六、与 正式静态目录.json 的数值比对（目录也是被复核对象）
# =============================================================================
print()
print("=" * 78)
print("E. 正式静态目录.json 的数值")
print("=" * 78)
CAT = json.load(open(CATALOG, encoding="utf-8"))
units = {u["id"]: u for u in CAT["units"]}
for k, (w, h, cin, cout, ninv, noutv) in KIND.items():
    u = units[k]
    got = (q(u["dimensions"]["width"]), q(u["dimensions"]["height"]),
           q(u["area"]), q(u["ports"]["input_count"]), q(u["ports"]["output_count"]))
    want = (F(w), F(h), F(w * h), F(cin), F(cout))
    if got != want:
        bad("目录机型", f"{k} {got} != {want}")
    inv = {x["role"]: x for x in u["inventory"]}
    if q(inv["input"]["count"]) != ninv or q(inv["output"]["count"]) != noutv:
        bad("目录物品格", f"{k} in={q(inv['input']['count'])} out={q(inv['output']['count'])}"
                        f" 应 {ninv}/{noutv}")
    if q(inv["input"]["capacity"]) != 50 or q(inv["output"]["capacity"]) != 50:
        bad("目录格上限", f"{k}")
    slb = u["static_lower_bounds"]
    got = (q(slb["machines"]), q(slb["input_channels"]), q(slb["output_channels"]))
    want = (F(MIN_MACHINES[k]), F(MIN_IN_CH[k]), F(MIN_OUT_CH[k]))
    if got != want:
        bad("目录下限", f"{k} {got} != {want}")
core = units["协议核心"]
if (q(core["ports"]["input_count"]), q(core["ports"]["output_count"])) != (F(CORE_IN), F(CORE_OUT)):
    bad("目录核心端口", str(core["ports"]))
if q(core["dimensions"]["width"]) != 9 or q(core["area"]) != 81:
    bad("目录核心尺寸", "")
warehouse = [x for x in core["inventory"] if x["role"] == "warehouse"][0]
if q(warehouse["capacity"]) != 80000:
    bad("目录仓库格上限", str(warehouse))
# 运输/仓储/供电
simple = {"传送带": (1, 1, 1, 1), "桥接器": (1, 1, 2, 2), "物品准入口": (1, 1, 1, 1),
          "分流器": (1, 1, 1, 3), "汇流器": (1, 1, 3, 1),
          "协议储存箱": (3, 3, 3, 3), "仓库取货口": (3, 1, 0, 1), "供电桩": (2, 2, 0, 0)}
for k, (w, h, cin, cout) in simple.items():
    u = units[k]
    got = (q(u["dimensions"]["width"]), q(u["dimensions"]["height"]), q(u["area"]),
           q(u["ports"]["input_count"]), q(u["ports"]["output_count"]))
    want = (F(w), F(h), F(w * h), F(cin), F(cout))
    if got != want:
        bad("目录单位", f"{k} {got} != {want}")
box = [x for x in units["协议储存箱"]["inventory"] if x["role"] == "storage"][0]
if (q(box["count"]), q(box["capacity"])) != (F(6), F(50)):
    bad("目录储存箱格", str(box))
# 类别标注自洽：同一推理链的端口数与端口位置类别应一致
cat_mismatch = []
for k, u in units.items():
    ic = u["ports"].get("input_count")
    lay = u["ports"].get("layouts") or []
    poscats = {z["category"] for e in (lay[0] if lay else []) for z in e["positions"]}
    if ic and poscats and cat_of(ic) not in poscats:
        cat_mismatch.append((k, cat_of(ic), sorted(poscats)))
print(f"  端口数类别 vs 端口位置类别 不一致的单位：{cat_mismatch}")
# 配方表
crec = {r["id"]: r for r in CAT["recipes"]}
if set(crec) != set(RECIPES):
    bad("目录配方集", f"{sorted(set(crec) ^ set(RECIPES))}")
for rid, (kind, ins, outs, dur) in RECIPES.items():
    r = crec.get(rid)
    if not r:
        continue
    if r["kind"] != kind or q(r["duration"]) != dur:
        bad("目录配方", f"{rid} {r['kind']}/{q(r['duration'])}")
    if {k: q(v) for k, v in r["inputs"].items()} != {k: F(v) for k, v in ins.items()}:
        bad("目录配方投入", rid)
    if {k: q(v) for k, v in r["outputs"].items()} != {k: F(v) for k, v in outs.items()}:
        bad("目录配方产出", rid)
print(f"  目录配方 {len(crec)} 条，与正式规则逐项相等")
# 约束条文
formal = open(f"{ROOT}/求解约束.txt", encoding="utf-8").read().splitlines()
names = []
for i, line in enumerate(formal):
    m = re.match(r"^(\S+?)：(.*)$", line)
    if m and not line.startswith(" ") and not line.startswith("\t") and "据：" not in line:
        names.append((m.group(1), m.group(2)))
cat_rules = {r["name"]: r["text"] for r in CAT["constraints"]}
print(f"  求解约束.txt 顶格条目 {len(names)} 条；目录 constraints {len(cat_rules)} 条")
missing = [n for n, _ in names if n not in cat_rules]
extra = [n for n in cat_rules if n not in {x for x, _ in names}]
if missing or extra:
    bad("目录约束集合", f"缺 {missing}；多 {extra}")
diff_text = [n for n, t in names if cat_rules.get(n) not in (None, t)]
if diff_text:
    bad("目录约束原文", f"{len(diff_text)} 条与正式文件不同字：{diff_text[:5]}")
else:
    ok("目录 56 条约束名与条文与 求解约束.txt 逐字相同")

# =============================================================================
# 七、与 校验报告.md 比对（复算完成后才读）
# =============================================================================
print()
print("=" * 78)
print("F. 与 校验报告.md 比对")
print("=" * 78)
rep = open(REPORT, encoding="utf-8").read()
sec = {}
for m in re.finditer(r"^## (能检且通过|能检且不通过|不能静态检)（(\d+) 项", rep, re.M):
    sec[m.group(1)] = int(m.group(2))
print(f"  报告分组计数 {sec}")
rows_rep = re.findall(r"^\| ([^|]+) \| ([^|]*) \|$", rep, re.M)
names_rep = [a.strip() for a, b in rows_rep if a.strip() != "检查项／据"]
print(f"  报告表格行 {len(names_rep)}（应 = {sum(sec.values())}）")
if len(names_rep) != sum(sec.values()):
    bad("报告行数", f"{len(names_rep)} != {sum(sec.values())}")
# 预期项数独立推算
exp_checks = (
    6                                   # 版本/身份/窗口/核心端口/来源域/受限模型
    + len(C["sources"])                 # 来源端口身份
    + 6 * len(C["logical_feeds"])       # 逐记录 6 项
    + len(s_set) + len(r_set)           # 端口速率逐端口
    + 5 * len(C["machines"])            # 端口数/占地/配方集/制造能力/多料栏
    + sum(len(m["recipes"]) for m in C["machines"])          # 配方/
    + sum(len(RECIPES[m["recipes"][0]["recipe"]][1]) + len(RECIPES[m["recipes"][0]["recipe"]][2])
          for m in C["machines"])                            # 逐机配方守恒
    + 19 + 2 + 1                        # 全局守恒 + 目标 + 目标项目集
    + 2 * 9                             # 机型下限 + 通道下限
    + sum(kind_cnt[k] for k in ("粉碎机", "精炼炉", "配件机", "种植机", "采种机", "封装机")
          if kind_cnt[k] == MIN_MACHINES[k])                 # 满载配置/计划占用
    + 3 + 2 + 1                         # 研磨进料×3、封装进料×2、灌装混线
    + 1 + 1 + 1 + 1                     # 取货口配置、矿线专机、矿石分流、单位矿耗
    + 2 + 19 + 1 + 1                    # 回路守恒×2、物料流量×19、矿系不入库、成品汇入
    + 1 + 1 + 1 + 2                     # 运输端口收支、箱体接口、箱体过站、回路转弯×2
    + 1 + len(C["fanouts"]) + 1         # 扇出完整性、扇出分类、交接件数
)
print(f"  独立推算「能检」项数 = {exp_checks}；报告 = {sec.get('能检且通过',0)+sec.get('能检且不通过',0)}")
if exp_checks != sec.get("能检且通过", 0) + sec.get("能检且不通过", 0):
    bad("报告项数", f"复算 {exp_checks} != 报告 {sec.get('能检且通过',0)+sec.get('能检且不通过',0)}")
if sec.get("不能静态检") != len(cat_rules) + 1:
    bad("报告未知项数", f"{sec.get('不能静态检')} != {len(cat_rules)}+1")
# 报告里的关键数字
for pat, want in [(r"S=(\d+)、R=(\d+)", (str(S), str(R))),
                  (r"制造 (\d+) 台、面积 (\d+) 格、逻辑记录 (\d+)",
                   (str(len(insts)), str(area), str(len(edges))))]:
    m = re.search(pat, rep)
    if not m:
        bad("报告缺数字", pat)
    elif m.groups() != want:
        bad("报告数字", f"{pat} 报告 {m.groups()} != 复算 {want}")
m = re.search(r"多料 (\d+)", rep)
print(f"  报告中的多料台数 {m.group(1) if m else '缺'}")
m = re.search(r"扇出 \{([^}]*)\}", rep)
print(f"  报告中的扇出分类 {m.group(1) if m else '缺'}")
# 报告不应把任何正式条目算成通过
for n in cat_rules:
    if f"正式条目/{n}" not in rep:
        bad("报告条目缺失", n)

print()
print("=" * 78)
print(f"复算结束，问题 {len(findings)} 条")
for t, m in findings:
    print(f"  !! [{t}] {m}")
sys.exit(0)
