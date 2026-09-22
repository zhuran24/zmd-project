#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核席第 1 轮独立复算。

不读校验报告、不读 contract.json 的结论性字段以外的任何解释文本；
配方与容量从仓库根三份正式文件人工转录（见 FORMAL_* 常量，逐条标注行号），
候选 B 的计划从 seat-opus-4/design.py 的 DESIGN 字面量独立重建，
再与 求解器/数据/候选B/contract.json 逐项比对。

全部用 fractions.Fraction（有理数），不用浮点。
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from fractions import Fraction as F

ROOT = "/home/zhuran24/zmd-research-fresh"
SRC = "/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4"
CONTRACT = f"{ROOT}/求解器/数据/候选B/contract.json"

# ---------------------------------------------------------------------------
# 一、从正式规则文件人工转录的常量（括号内为《明日方舟：终末地》游戏规则.txt 行号）
# ---------------------------------------------------------------------------
# 制造单位尺寸与端口数（第 44、50、54 行）
KIND_GEOM = {
    # 机型 -> (占格, 存货端口数, 取货端口数)
    "粉碎机": (9, 3, 3),
    "精炼炉": (9, 3, 3),
    "配件机": (9, 3, 3),
    "塑形机": (9, 3, 3),
    "采种机": (25, 5, 5),
    "种植机": (25, 5, 5),
    "研磨机": (24, 6, 6),   # 6x4，长边 6 全为存货端口，对边全为取货端口
    "封装机": (24, 6, 6),
    "灌装机": (24, 6, 6),
}

# 配方（第 80-114 行）：名字 -> (机型, 投入 dict, 产出 dict, 耗时 tick)
FORMAL_RECIPES = {
    "粉碎-源矿":     ("粉碎机", {"源矿": 1}, {"源石粉末": 1}, 1),
    "粉碎-蓝铁块":   ("粉碎机", {"蓝铁块": 1}, {"蓝铁粉末": 1}, 1),
    "粉碎-荞花":     ("粉碎机", {"荞花": 1}, {"荞花粉末": 2}, 1),
    "粉碎-砂叶":     ("粉碎机", {"砂叶": 1}, {"砂叶粉末": 3}, 1),
    "精炼-蓝铁矿":   ("精炼炉", {"蓝铁矿": 1}, {"蓝铁块": 1}, 1),
    "精炼-致密蓝铁": ("精炼炉", {"致密蓝铁粉末": 1}, {"钢块": 1}, 1),
    "精炼-蓝铁粉末": ("精炼炉", {"蓝铁粉末": 1}, {"蓝铁块": 1}, 1),   # 第 89 行，候选未用
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

# 目标（求解任务.txt 第 2 行）
FORMAL_TARGETS = {"高容谷地电池": F(18, 30), "精选荞愈胶囊": F(165, 300)}
# 端口速率（求解约束.txt 第 30 行）：每端口每 tick 至多 1 件
PORT_RATE_CAP = F(1)
# 机型下限（求解约束.txt 第 46 行）
FORMAL_MIN_MACHINES = {"粉碎机": 68, "精炼炉": 51, "研磨机": 32, "塑形机": 6,
                       "配件机": 6, "种植机": 32, "采种机": 16, "封装机": 3, "灌装机": 3}
# 通道下限（求解约束.txt 第 48 行）
FORMAL_MIN_IN_CH = {"粉碎机": 68, "精炼炉": 51, "研磨机": 95, "塑形机": 11, "配件机": 6,
                    "种植机": 32, "采种机": 16, "封装机": 15, "灌装机": 11}
FORMAL_MIN_OUT_CH = {"粉碎机": 95, "精炼炉": 51, "研磨机": 32, "塑形机": 6, "配件机": 6,
                     "种植机": 32, "采种机": 32, "封装机": 1, "灌装机": 1}
# 物料流量（求解约束.txt 第 44 行），件/tick
FORMAL_FLOW = {
    "蓝铁矿": F(34), "源矿": F(18), "蓝铁块": F(34), "蓝铁粉末": F(34), "源石粉末": F(18),
    "砂叶粉末": F(63, 2), "砂叶": F(21), "砂叶种子": F(21), "荞花": F(11), "荞花种子": F(11),
    "荞花粉末": F(11), "致密蓝铁粉末": F(17), "钢块": F(17), "致密源石粉末": F(9),
    "细磨荞花粉末": F(11, 2), "钢制零件": F(6), "钢质瓶": F(11, 2),
    "高容谷地电池": F(3, 5), "精选荞愈胶囊": F(11, 20),
}

# ---------------------------------------------------------------------------
# 二、从 design.py 的 DESIGN 字面量独立重建候选 B（P=20 tick 窗口）
# ---------------------------------------------------------------------------
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

problems = []


def note(tag, msg):
    problems.append((tag, msg))
    print(f"[{tag}] {msg}")


class Inst:
    def __init__(self, mid, group, batches, nports):
        self.mid, self.group, self.batches, self.nports = mid, group, batches, nports
        self.kind = FORMAL_RECIPES[group][0]
        self.out_ports = []   # [(item, rate per 20tick)]
        self.in_ch = []       # [(item, rate per 20tick)]


insts = []
for g, spec in DESIGN:
    for b, n in spec:
        insts.append(Inst(f"M{len(insts):03d}", g, b, n))
by_id = {i.mid: i for i in insts}

# 批次上限（制造：一次制造的用量进入缓存格后立刻开始，无冷却；耗时 t ⇒ 20 tick 至多 20/t 批）
for it in insts:
    cap = P // FORMAL_RECIPES[it.group][3]
    if it.batches > cap:
        note("批次超限", f"{it.mid} {it.group} {it.batches}>{cap}")

# 扇出与取货端口速率
fanout = []
for it in insts:
    for item, q in FORMAL_RECIPES[it.group][2].items():
        total = it.batches * q
        if total % it.nports:
            note("不能均分", f"{it.mid} {total}/{it.nports}")
            continue
        rate = total // it.nports
        if rate > P:
            note("端口超速", f"{it.mid} {rate}>20")
        it.out_ports += [(item, rate)] * it.nports
        if it.nports >= 2:
            interval = F(P, it.batches)
            cls = ("满速扇出定则型" if rate == P else
                   "轮询均分型" if interval == 1 and 2 * q <= it.nports else
                   "两者都不落")
            fanout.append(dict(machine=it.mid, recipe=it.group, item=item, k=it.nports,
                               port_rate=rate, interval=interval, q=q, cls=cls))

# 逐物品配边（与 design.py 同一贪心，用于复现候选 B 的通道表）
edges = []
all_items = sorted({i for g in FORMAL_RECIPES
                    for i in (set(FORMAL_RECIPES[g][1]) | set(FORMAL_RECIPES[g][2]))})
for item in all_items:
    sup = [[it, r] for it in insts for (i2, r) in it.out_ports if i2 == item]
    sup += [[None, P] for _ in range(ORE.get(item, 0))]
    dem = [[it, it.batches * FORMAL_RECIPES[it.group][1][item]]
           for it in insts if item in FORMAL_RECIPES[it.group][1]]
    if item in ("高容谷地电池", "精选荞愈胶囊"):
        dem = [["核心", sum(s[1] for s in sup)]]
    if not sup and not dem:
        continue
    if sum(s[1] for s in sup) != sum(d[1] for d in dem):
        note("不配平", f"{item} 供 {sum(s[1] for s in sup)} 需 {sum(d[1] for d in dem)}")
        continue
    sup.sort(key=lambda x: -x[1])
    for s in sup:
        dem.sort(key=lambda x: -x[1])
        if not dem or dem[0][1] < s[1]:
            note("配不进", f"{item} rate={s[1]}")
            break
        edges.append((item, s[0], dem[0][0], s[1]))
        dem[0][1] -= s[1]
        if dem[0][1] == 0:
            dem.pop(0)
for item, s, d, r in edges:
    if d != "核心":
        d.in_ch.append((item, r))

# 端口容量
for it in insts:
    _, pin, pout = KIND_GEOM[it.kind]
    if len(it.in_ch) > pin or len(it.out_ports) > pout:
        note("端口数超限", f"{it.mid} in {len(it.in_ch)}/{pin} out {len(it.out_ports)}/{pout}")

print("=" * 72)
print("A. 独立重建候选 B 的件数")
print("=" * 72)
n_out = sum(len(i.out_ports) for i in insts)
n_in = sum(len(i.in_ch) for i in insts)
core_in = sum(1 for e in edges if e[2] == "核心")
ore_out = sum(1 for e in edges if e[1] is None)
kind_cnt = Counter(i.kind for i in insts)
area = sum(KIND_GEOM[i.kind][0] for i in insts)
recomputed = {
    "制造单位": len(insts), "制造占格": area, "逻辑通道": len(edges),
    "S": n_out + ore_out, "R": n_in + core_in,
    "机器取货端口": n_out, "机器存货通道": n_in, "矿石来源": ore_out, "成品进核心": core_in,
}
for k, v in recomputed.items():
    print(f"  {k}: {v}")
print("  机型台数:", dict(sorted(kind_cnt.items())))
print("  扇出分类:", dict(sorted(Counter(r['cls'] for r in fanout).items())),
      " 合计", len(fanout))
gr = [i for i in insts if i.kind == "研磨机"]
sh = [i for i in insts if i.kind == "塑形机"]
pk = [i for i in insts if i.kind == "封装机"]
fl = [i for i in insts if i.kind == "灌装机"]
print(f"  研磨机 >=3 存货通道: {sum(1 for i in gr if len(i.in_ch) >= 3)}/{len(gr)}"
      f"  例外: {[ (i.mid, len(i.in_ch)) for i in gr if len(i.in_ch) != 3 ]}")
print(f"  塑形机 >=2 存货通道: {sum(1 for i in sh if len(i.in_ch) >= 2)}/{len(sh)}"
      f"  例外: {[ (i.mid, len(i.in_ch)) for i in sh if len(i.in_ch) != 2 ]}")
print(f"  封装机存货通道: {[len(i.in_ch) for i in pk]}  速率 {[sorted(r for _, r in i.in_ch) for i in pk]}")
print(f"  灌装机存货通道: {[len(i.in_ch) for i in fl]}  速率 {[sorted(r for _, r in i.in_ch) for i in fl]}")
print(f"  K={core_in} B=0 C=0 => K+3B+2C={core_in}")
multi = [i for i in insts if len(FORMAL_RECIPES[i.group][1]) >= 2]
print(f"  多料机（配方投入 >=2 种）: {len(multi)}  按机型 {dict(Counter(i.kind for i in multi))}")

# ---------------------------------------------------------------------------
# 三、守恒（件/tick，有理数）
# ---------------------------------------------------------------------------
print()
print("=" * 72)
print("B. 守恒复算（件/tick）")
print("=" * 72)
prod = defaultdict(F)
cons = defaultdict(F)
for it in insts:
    br = F(it.batches, P)
    for item, q in FORMAL_RECIPES[it.group][2].items():
        prod[item] += br * q
    for item, q in FORMAL_RECIPES[it.group][1].items():
        cons[item] += br * q
ore_in = {k: F(v) for k, v in ORE.items()}
deliver = {"高容谷地电池": prod["高容谷地电池"], "精选荞愈胶囊": prod["精选荞愈胶囊"]}
for item in sorted(set(prod) | set(cons)):
    src = prod[item] + ore_in.get(item, F(0))
    snk = cons[item] + (deliver.get(item, F(0)) if item in deliver else F(0))
    flag = "OK" if src == snk else "!! 不配平"
    ref = FORMAL_FLOW.get(item)
    refflag = ""
    if ref is not None:
        refflag = f"  物料流量要求 {ref}  {'>=OK' if snk >= ref else '!! 低于下限'}"
    print(f"  {item:8s} 供 {str(src):8s} 耗 {str(snk):8s} {flag}{refflag}")
    if src != snk:
        note("守恒", f"{item} {src} != {snk}")
for item, t in FORMAL_TARGETS.items():
    got = deliver[item]
    print(f"  目标 {item}: 计划 {got}  正式 {t}  {'OK' if got == t else '!! 不符'}")
    if got != t:
        note("目标", f"{item} {got} != {t}")

# ---------------------------------------------------------------------------
# 四、与 contract.json 逐项比对
# ---------------------------------------------------------------------------
print()
print("=" * 72)
print("C. 与 contract.json 比对")
print("=" * 72)
C = json.load(open(CONTRACT, encoding="utf-8"))


def q(x):
    if x is None:
        return None
    return F(x["value"])


print(f"  machines {len(C['machines'])}  channels {len(C['channels'])}"
      f"  sources {len(C['sources'])}  fanouts {len(C['fanouts'])}")

cm = {m["id"]: m for m in C["machines"]}
if set(cm) != set(by_id):
    note("机器集合", f"差异 {set(cm) ^ set(by_id)}")
for mid, m in cm.items():
    it = by_id.get(mid)
    if it is None:
        continue
    if m["kind"] != it.kind:
        note("机型", f"{mid} {m['kind']} != {it.kind}")
    if len(m["recipes"]) != 1 or m["recipes"][0]["recipe"] != it.group:
        note("配方", f"{mid} {m['recipes']} != {it.group}")
    br = q(m["recipes"][0]["planned_batch_rate"])
    if br != F(it.batches, P):
        note("批次率", f"{mid} {br} != {F(it.batches, P)}")
    iv = q(m["recipes"][0]["planned_mean_batch_interval"])
    if iv != F(P, it.batches):
        note("平均批间隔", f"{mid} {iv} != {F(P, it.batches)}")
    ar, pin, pout = KIND_GEOM[it.kind]
    if q(m["input_ports"]) != pin or q(m["output_ports"]) != pout:
        note("端口容量", f"{mid} {m['input_ports']} {m['output_ports']} != {pin} {pout}")
    if q(m["area"]) != ar:
        note("占格", f"{mid} {m['area']} != {ar}")
    want_multi = len(FORMAL_RECIPES[it.group][1]) >= 2
    if want_multi != (m["multi_material"] is not None):
        note("多料标记", f"{mid} multi={m['multi_material']} 应为 {want_multi}")
    if want_multi:
        for f_ in ("arrival_composition_per_tick", "synchronization", "same_source"):
            if m["multi_material"][f_] != "待验":
                note("多料栏", f"{mid} {f_}={m['multi_material'][f_]}")

# 通道：按 (item, source, target, rate) 多重集比较
mine = Counter()
for item, s, d, r in edges:
    mine[(item, "ORE" if s is None else s.mid, "CORE" if d == "核心" else d.mid, F(r, P))] += 1
theirs = Counter()
for ch in C["channels"]:
    src = ch["source"]
    if src.startswith("ORE"):
        src = "ORE"
    theirs[(ch["item"], src, ch["target"], q(ch["planned_rate"]))] += 1
if mine != theirs:
    diff = (mine - theirs) + (theirs - mine)
    note("通道表", f"与重建不一致，差 {len(diff)} 类：{list(diff.items())[:10]}")
else:
    print("  通道多重集（物品/源/目标/速率）与独立重建完全一致")

# proven_actual_rate 必须存在且为 null
bad = [ch["id"] for ch in C["channels"] if "proven_actual_rate" not in ch or ch["proven_actual_rate"] is not None]
print(f"  proven_actual_rate 非 null 的通道: {len(bad)}")

# 端口负荷：按端口 id 汇总
port_load = defaultdict(F)
port_owner = defaultdict(set)
for ch in C["channels"]:
    port_load[("out", ch["source_port"])] += q(ch["planned_rate"])
    port_load[("in", ch["target_port"])] += q(ch["planned_rate"])
    port_owner[("out", ch["source_port"])].add(ch["source"])
    port_owner[("in", ch["target_port"])].add(ch["target"])
over = {k: v for k, v in port_load.items() if v > PORT_RATE_CAP}
print(f"  超过 1 件/tick 的端口: {len(over)} {list(over.items())[:5]}")
if over:
    note("端口速率", f"{len(over)} 个端口超 1 件/tick")
side_cnt = defaultdict(set)
for (side, pid), owners in port_owner.items():
    for o in owners:
        side_cnt[(side, o)].add(pid)
for (side, owner), pids in side_cnt.items():
    if owner == "CORE":
        cap = q(C["core"]["input_ports"]) if side == "in" else q(C["core"]["output_ports"])
    elif owner.startswith("ORE"):
        cap = F(1)
    else:
        _, pin, pout = KIND_GEOM[cm[owner]["kind"]]
        cap = F(pin if side == "in" else pout)
    if len(pids) > cap:
        note("端口数", f"{owner} {side} 用 {len(pids)} > {cap}")
print(f"  各端点端口身份数均不超容量: {'是' if not [1 for t,_ in problems if t=='端口数'] else '否'}")

# 每台机器逐配方逐物品守恒（用 contract 的通道）
in_by = defaultdict(F)
out_by = defaultdict(F)
for ch in C["channels"]:
    if not ch["source"].startswith("ORE"):
        out_by[(ch["source"], ch["item"])] += q(ch["planned_rate"])
    if ch["target"] != "CORE":
        in_by[(ch["target"], ch["item"])] += q(ch["planned_rate"])
bad_m = 0
for mid, m in cm.items():
    rec = m["recipes"][0]["recipe"]
    br = q(m["recipes"][0]["planned_batch_rate"])
    for item, n in FORMAL_RECIPES[rec][1].items():
        if in_by[(mid, item)] != br * n:
            note("机器进料", f"{mid} {item} {in_by[(mid,item)]} != {br*n}")
            bad_m += 1
    for item, n in FORMAL_RECIPES[rec][2].items():
        if out_by[(mid, item)] != br * n:
            note("机器出料", f"{mid} {item} {out_by[(mid,item)]} != {br*n}")
            bad_m += 1
    extra = {i for (mm, i) in in_by if mm == mid} - set(FORMAL_RECIPES[rec][1])
    if extra:
        note("多余进料", f"{mid} {extra}")
print(f"  逐机逐配方逐物品守恒不符项: {bad_m}")

# 38 台多料机进料复算
print()
print("  多料机进料复算（件/tick，按配方用量核）:")
mm = [m for m in C["machines"] if m["multi_material"] is not None]
print(f"    多料机台数 {len(mm)}  {dict(Counter(m['kind'] for m in mm))}")
for m in sorted(mm, key=lambda x: x["id"])[:3] + sorted(mm, key=lambda x: x["id"])[-3:]:
    rec = m["recipes"][0]["recipe"]
    br = q(m["recipes"][0]["planned_batch_rate"])
    detail = {i: (str(in_by[(m['id'], i)]), str(br * n)) for i, n in FORMAL_RECIPES[rec][1].items()}
    chn = [c for c in C["channels"] if c["target"] == m["id"]]
    print(f"    {m['id']} {rec} 批率 {br} 进料通道 {len(chn)} 实/应 {detail}")

# 扇出比对
print()
fo_mine = {(r["machine"], r["item"]): r for r in fanout}
fo_c = {(f_["machine"], f_["item"]): f_ for f_ in C["fanouts"]}
if set(fo_mine) != set(fo_c):
    note("扇出集合", f"差 {set(fo_mine) ^ set(fo_c)}")
for k, r in fo_mine.items():
    f_ = fo_c.get(k)
    if not f_:
        continue
    if q(f_["ports"]) != r["k"]:
        note("扇出端口数", f"{k} {f_['ports']} != {r['k']}")
    if q(f_["planned_port_rate"]) != F(r["port_rate"], P):
        note("扇出端口速率", f"{k} {f_['planned_port_rate']} != {F(r['port_rate'],P)}")
    if q(f_["planned_mean_batch_interval"]) != r["interval"]:
        note("扇出批间隔", f"{k} {f_['planned_mean_batch_interval']} != {r['interval']}")
    if q(f_["batch_size"]) != r["q"]:
        note("扇出每批件数", f"{k} {f_['batch_size']} != {r['q']}")
    if f_["planned_shape"] != r["cls"]:
        note("扇出分类", f"{k} {f_['planned_shape']} != {r['cls']}")
    if f_["certification"] != "待验":
        note("扇出认证栏", f"{k} {f_['certification']}")
print(f"  contract 扇出分类计数: {dict(sorted(Counter(f_['planned_shape'] for f_ in C['fanouts']).items()))}")

# 来源变量
srcs = C["sources"]
print(f"  来源变量 {len(srcs)}  物品分布 {dict(Counter(s['item'] for s in srcs))}"
      f"  身份状态 {dict(Counter(s['identity']['status'] for s in srcs))}")
if dict(Counter(s["item"] for s in srcs)) != {"源矿": 18, "蓝铁矿": 34}:
    note("来源物品", str(Counter(s["item"] for s in srcs)))

# targets
for item, t in FORMAL_TARGETS.items():
    if q(C["targets"][item]) != t:
        note("targets", f"{item} {C['targets'][item]} != {t}")

# ---------------------------------------------------------------------------
# 五、与原 CSV 资产比对
# ---------------------------------------------------------------------------
print()
print("=" * 72)
print("D. 与 seat-opus-4 原 CSV 比对")
print("=" * 72)
with open(f"{SRC}/channels.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
print(f"  channels.csv {len(rows)} 行")
csv_ms = Counter()
for r in rows:
    s = "ORE" if r["源机器id"] == "仓库出矿口" else r["源机器id"]
    d = "CORE" if r["目标机器id"] == "协议核心" else r["目标机器id"]
    csv_ms[(r["物品"], s, d, F(int(r["件每20tick"]), P))] += 1
print(f"  原 CSV 与独立重建一致: {csv_ms == mine}")
print(f"  原 CSV 与 contract 一致: {csv_ms == theirs}")
with open(f"{SRC}/machines.csv", encoding="utf-8") as f:
    mrows = list(csv.DictReader(f))
print(f"  machines.csv {len(mrows)} 行")
bad_csv = 0
for r in mrows:
    it = by_id[r["机器id"]]
    if int(r["存货通道数"]) != len(it.in_ch) or int(r["取货通道数"]) != len(it.out_ports):
        bad_csv += 1
print(f"  machines.csv 与重建的度数不符: {bad_csv}")
with open(f"{SRC}/fanout.json", encoding="utf-8") as f:
    fj = json.load(f)
print(f"  fanout.json {len(fj)} 条  分类 {dict(sorted(Counter(x['类别'] for x in fj).items()))}")

# ---------------------------------------------------------------------------
print()
print("=" * 72)
print(f"复算结束，异常 {len(problems)} 条")
for t, m in problems:
    print(f"  !! [{t}] {m}")
