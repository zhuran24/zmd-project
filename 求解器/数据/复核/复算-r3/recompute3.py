#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核席（数值复算视角）第 3 轮的独立复算。

纪律：
- 规则口径只来自三份正式文件（游戏规则、求解任务、求解约束），本文件把配方、
  机型尺寸、端口数手抄进 RULES_* 常量，抄写处标了规则行号，供逐字核对。
- 候选 B 的原始文件是 seat-opus-4/{design.py, channels.csv, machines.csv, fanout.json}，
  本脚本不调用 design.py，也不复用 复算-r1/r2 的脚本；对 channels.csv/machines.csv
  只做「校验」（逐台逐物品核供需、端口数、速率），不重跑它的贪心分配。
- 全部用 Fraction，不用浮点。
"""
from fractions import Fraction as F
from collections import defaultdict, Counter
import csv, json, os, sys

ROOT = "/home/zhuran24/zmd-research-fresh"
SRC = "/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4"
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def frac(x):
    """把 '3/2'、'1.5'、20 一律读成 Fraction。"""
    if isinstance(x, F):
        return x
    return F(str(x))


# ---------------------------------------------------------------- 规则常量
# 规则 L80-L114：配方表。值为 (输入 dict, 输出 dict, 每批 tick 数, 机型)
RULES_RECIPES = {
    "粉碎-源矿": ({"源矿": 1}, {"源石粉末": 1}, 1, "粉碎机"),
    "粉碎-蓝铁块": ({"蓝铁块": 1}, {"蓝铁粉末": 1}, 1, "粉碎机"),
    "粉碎-荞花": ({"荞花": 1}, {"荞花粉末": 2}, 1, "粉碎机"),
    "粉碎-砂叶": ({"砂叶": 1}, {"砂叶粉末": 3}, 1, "粉碎机"),
    "精炼-蓝铁矿": ({"蓝铁矿": 1}, {"蓝铁块": 1}, 1, "精炼炉"),
    "精炼-致密蓝铁": ({"致密蓝铁粉末": 1}, {"钢块": 1}, 1, "精炼炉"),
    "精炼-蓝铁粉末": ({"蓝铁粉末": 1}, {"蓝铁块": 1}, 1, "精炼炉"),
    "研磨-致密蓝铁": ({"蓝铁粉末": 2, "砂叶粉末": 1}, {"致密蓝铁粉末": 1}, 1, "研磨机"),
    "研磨-致密源石": ({"源石粉末": 2, "砂叶粉末": 1}, {"致密源石粉末": 1}, 1, "研磨机"),
    "研磨-细磨荞花": ({"荞花粉末": 2, "砂叶粉末": 1}, {"细磨荞花粉末": 1}, 1, "研磨机"),
    "塑形-钢质瓶": ({"钢块": 2}, {"钢质瓶": 1}, 1, "塑形机"),
    "配件-钢制零件": ({"钢块": 1}, {"钢制零件": 1}, 1, "配件机"),
    "种植-荞花": ({"荞花种子": 1}, {"荞花": 1}, 1, "种植机"),
    "种植-砂叶": ({"砂叶种子": 1}, {"砂叶": 1}, 1, "种植机"),
    "采种-荞花": ({"荞花": 1}, {"荞花种子": 2}, 1, "采种机"),
    "采种-砂叶": ({"砂叶": 1}, {"砂叶种子": 2}, 1, "采种机"),
    "封装-电池": ({"钢制零件": 10, "致密源石粉末": 15}, {"高容谷地电池": 1}, 5, "封装机"),
    "灌装-胶囊": ({"钢质瓶": 10, "细磨荞花粉末": 10}, {"精选荞愈胶囊": 1}, 5, "灌装机"),
}
# 规则 L44-L57：机型 → (尺寸串, 占格, 存货物品格数, 取货物品格数, 存货端口数, 取货端口数)
RULES_KIND = {
    "粉碎机": ("3x3", 9, 1, 1, 3, 3),
    "精炼炉": ("3x3", 9, 1, 1, 3, 3),
    "配件机": ("3x3", 9, 1, 1, 3, 3),
    "塑形机": ("3x3", 9, 1, 1, 3, 3),
    "采种机": ("5x5", 25, 1, 1, 5, 5),
    "种植机": ("5x5", 25, 1, 1, 5, 5),
    "研磨机": ("6x4", 24, 2, 1, 6, 6),
    "封装机": ("6x4", 24, 2, 1, 6, 6),
    "灌装机": ("6x4", 24, 2, 1, 6, 6),
}
PORT_RATE = F(1)          # 求解约束「端口速率」：每端口每 tick 至多 1 件
TARGET = {"高容谷地电池": F(3, 5), "精选荞愈胶囊": F(11, 20)}   # 求解任务 L2

say("=" * 78)
say("第一部分：只从规则与任务重算稳态物料流量（件/tick），与 求解约束「物料流量」对照")
say("=" * 78)

# 稳态需求：从成品倒推。候选 B 的工艺选择（蓝铁矿→蓝铁块→蓝铁粉末，不用 精炼-蓝铁粉末
# 这条把粉末变回块的配方）是候选的选择；这里按同一工艺链倒推，用来核 物料流量 一行。
need = defaultdict(F)
need["高容谷地电池"] = TARGET["高容谷地电池"]
need["精选荞愈胶囊"] = TARGET["精选荞愈胶囊"]
# 逐级展开（拓扑序手写，含义见 求解约束「物料流量」）
need["钢制零件"] = 10 * need["高容谷地电池"]
need["致密源石粉末"] = 15 * need["高容谷地电池"]
need["钢质瓶"] = 10 * need["精选荞愈胶囊"]
need["细磨荞花粉末"] = 10 * need["精选荞愈胶囊"]
need["钢块"] = 1 * need["钢制零件"] + 2 * need["钢质瓶"]
need["致密蓝铁粉末"] = 1 * need["钢块"]
need["源石粉末"] = 2 * need["致密源石粉末"]
need["荞花粉末"] = 2 * need["细磨荞花粉末"]
need["蓝铁粉末"] = 2 * need["致密蓝铁粉末"]
need["砂叶粉末"] = (need["致密蓝铁粉末"] + need["致密源石粉末"] + need["细磨荞花粉末"])
need["源矿"] = 1 * need["源石粉末"]
need["蓝铁块"] = 1 * need["蓝铁粉末"]
need["蓝铁矿"] = 1 * need["蓝铁块"]
need["砂叶"] = need["砂叶粉末"] / 3          # 粉碎用
need["荞花"] = need["荞花粉末"] / 2          # 粉碎用
# 种子自给：采种率 a、种植率 p 解 p = 粉碎用量 + a、2a = p
for plant, seed in (("荞花", "荞花种子"), ("砂叶", "砂叶种子")):
    crush = need[plant]
    a = crush            # 由 2a = crush + a 得 a = crush
    p = 2 * a
    need[plant] = p      # 植株总产量（= 总消耗：粉碎 + 采种）
    need[seed] = p       # 种子产量 2a = p，消耗 p
    say(f"  {plant}：粉碎用 {crush}，采种 {a}，种植 {p}，{seed} {p}")

official_flow = {   # 求解约束 L44「物料流量」逐项抄录
    "蓝铁矿": 34, "源矿": 18, "蓝铁块": 34, "蓝铁粉末": 34, "源石粉末": 18,
    "砂叶粉末": F(63, 2), "砂叶": 21, "砂叶种子": 21, "荞花": 11, "荞花种子": 11,
    "荞花粉末": 11, "致密蓝铁粉末": 17, "钢块": 17, "致密源石粉末": 9,
    "细磨荞花粉末": F(11, 2), "钢制零件": 6, "钢质瓶": F(11, 2),
    "高容谷地电池": F(3, 5), "精选荞愈胶囊": F(11, 20),
}
bad = [k for k in official_flow if frac(official_flow[k]) != need[k]]
say(f"  与 物料流量 逐项比对：{'全部相等' if not bad else '不等项 ' + str(bad)}")
tot = sum(frac(v) for v in official_flow.values())
say(f"  合计 {tot}（约束写 305.65）  一致：{tot == F(30565, 100)}")
say(f"  矿石合计 {need['蓝铁矿'] + need['源矿']}（出库上限 52）")

say("")
say("=" * 78)
say("第二部分：从候选 B 的设计表独立重算台数、占地、端口与扇出")
say("=" * 78)

# design.py 的 DESIGN 表（配方, [(每 20tick 批次数, 取货端口条数), ...]）手抄，作为候选定义
P = 20
DESIGN = [
    ("粉碎-源矿", [(20, 1)] * 18),
    ("粉碎-蓝铁块", [(20, 1)] * 34),
    ("粉碎-荞花", [(20, 2)] * 5 + [(10, 1)]),
    ("粉碎-砂叶", [(20, 3)] * 10 + [(10, 3)]),
    ("精炼-蓝铁矿", [(20, 1)] * 34),
    ("精炼-致密蓝铁", [(20, 1)] * 17),
    ("研磨-致密蓝铁", [(20, 1)] * 17),
    ("研磨-致密源石", [(20, 1)] * 9),
    ("研磨-细磨荞花", [(20, 1)] * 5 + [(10, 1)]),
    ("塑形-钢质瓶", [(20, 1)] * 5 + [(10, 1)]),
    ("配件-钢制零件", [(20, 1)] * 6),
    ("种植-荞花", [(20, 1)] * 10 + [(20, 2)]),
    ("种植-砂叶", [(20, 1)] * 20 + [(20, 2)]),
    ("采种-荞花", [(20, 2)] * 5 + [(10, 1)]),
    ("采种-砂叶", [(20, 2)] * 10 + [(10, 1)]),
    ("封装-电池", [(4, 1)] * 3),
    ("灌装-胶囊", [(4, 1), (4, 1), (3, 1)]),
]
design_inst = []           # (mid, recipe, batches_per_20, nports)
for g, spec in DESIGN:
    for b, n in spec:
        design_inst.append((f"M{len(design_inst):03d}", g, b, n))
say(f"  设计表实例数 {len(design_inst)}")

kind_cnt = Counter(RULES_RECIPES[r][3] for _, r, _, _ in design_inst)
area = sum(RULES_KIND[RULES_RECIPES[r][3]][1] for _, r, _, _ in design_inst)
low = {"粉碎机": 68, "精炼炉": 51, "研磨机": 32, "塑形机": 6, "配件机": 6,
       "种植机": 32, "采种机": 16, "封装机": 3, "灌装机": 3}     # 求解约束 L46
for k in low:
    say(f"    {k}: {kind_cnt[k]} 台（下限 {low[k]}，差 {kind_cnt[k] - low[k]}）")
say(f"  合计 {sum(kind_cnt.values())} 台 / {area} 格（下限 217 台 / 3291 格）")

# 批次率上限：规则 L35 制造无冷却，一次制造耗 t tick ⇒ 每 20 tick 至多 20/t 批
for mid, g, b, n in design_inst:
    cap = P // RULES_RECIPES[g][2]
    assert b <= cap, f"{mid} 批次 {b} 超 {cap}"
say("  批次率上限（每 20tick ≤ 20/配方 tick 数）：全部通过")

# 产能与需求配平（按候选自己的配方分配）
prod, cons = defaultdict(F), defaultdict(F)
for mid, g, b, n in design_inst:
    rate = F(b, P)                                   # 批/tick
    for it, q in RULES_RECIPES[g][1].items():
        prod[it] += rate * q
    for it, q in RULES_RECIPES[g][0].items():
        cons[it] += rate * q
say("  候选产能 vs 需求：")
for it in sorted(set(prod) | set(cons)):
    p, c = prod[it], cons[it]
    tag = ""
    if it in ("源矿", "蓝铁矿"):
        tag = f"（外部供 {c}）"
    elif it in TARGET:
        tag = f"（目标 {TARGET[it]}，达标 {p >= TARGET[it]}）"
    elif p != c:
        tag = "  ← 不配平"
    say(f"    {it:10s} 产 {str(p):>8s} 耗 {str(c):>8s}{tag}")
imbalance = [it for it in set(prod) | set(cons)
             if it not in TARGET and it not in ("源矿", "蓝铁矿") and prod[it] != cons[it]]
say(f"  中间物不配平项：{imbalance if imbalance else '无'}")

# 扇出点分类（规则无「批间隔」一词；这里按候选自定义的三分类复算）
fanout_calc = []
for mid, g, b, n in design_inst:
    if n < 2:
        continue
    for it, q in RULES_RECIPES[g][1].items():
        total = b * q                                # 每 20tick 件数
        assert total % n == 0, f"{mid} {total} 不能被 {n} 均分"
        port_rate = F(total, n * P)                  # 件/tick/端口
        interval = F(P, b)                           # 平均批间隔 tick
        if port_rate > PORT_RATE:
            say(f"    !! {mid} 端口速率 {port_rate} 超 1 件/tick")
        cls = ("A" if port_rate == PORT_RATE else
               "B" if interval == 1 and 2 * q <= n else "C")
        fanout_calc.append((mid, g, it, n, port_rate, interval, q, cls))
say(f"  扇出点 {len(fanout_calc)} 处，分类 " +
    str(dict(sorted(Counter(c[-1] for c in fanout_calc).items()))))
for f_ in fanout_calc:
    if f_[-1] != "A":
        say(f"    {f_[-1]}  {f_[0]} {f_[1]} → {f_[2]}：k={f_[3]}、每端口 {f_[4]}/tick、"
            f"平均批间隔 {f_[5]}、每批 {f_[6]} 件")

say("")
say("=" * 78)
say("第三部分：校验 channels.csv / machines.csv（不重跑贪心，只核结果）")
say("=" * 78)
chan = list(csv.DictReader(open(os.path.join(SRC, "channels.csv"), encoding="utf-8")))
mach = list(csv.DictReader(open(os.path.join(SRC, "machines.csv"), encoding="utf-8")))
say(f"  channels.csv {len(chan)} 行、machines.csv {len(mach)} 行")

design_by_id = {mid: (g, b, n) for mid, g, b, n in design_inst}
# machines.csv 与设计表逐台一致？
mm = [m for m in mach if design_by_id.get(m["机器id"], (None,))[0] != m["配方"]
      or int(m["批次每20tick"]) != design_by_id[m["机器id"]][1]
      or int(m["取货通道数"]) != design_by_id[m["机器id"]][2]]
say(f"  machines.csv 与设计表不一致的台数：{len(mm)}")

# 逐条通道：速率 ≤ 20/20tick，端口速率上限
over = [c for c in chan if F(int(c["件每20tick"]), P) > PORT_RATE]
say(f"  超端口速率（>1 件/tick）的通道：{len(over)}")

# 每台的存货通道是否恰好满足其配方需求
in_sum = defaultdict(lambda: defaultdict(F))
out_sum = defaultdict(lambda: defaultdict(F))
in_cnt, out_cnt = Counter(), Counter()
ore_edges, core_edges = 0, 0
for c in chan:
    r = F(int(c["件每20tick"]), P)
    s, d = c["源机器id"], c["目标机器id"]
    if s == "仓库出矿口":
        ore_edges += 1
    else:
        out_sum[s][c["物品"]] += r
        out_cnt[s] += 1
    if d == "协议核心":
        core_edges += 1
    else:
        in_sum[d][c["物品"]] += r
        in_cnt[d] += 1
say(f"  出矿通道 {ore_edges} 条、进核心通道 {core_edges} 条")

err_in, err_out = [], []
for mid, g, b, n in design_inst:
    rate = F(b, P)
    for it, q in RULES_RECIPES[g][0].items():
        if in_sum[mid][it] != rate * q:
            err_in.append((mid, it, str(in_sum[mid][it]), str(rate * q)))
    for it, q in RULES_RECIPES[g][1].items():
        if out_sum[mid][it] != rate * q:
            err_out.append((mid, it, str(out_sum[mid][it]), str(rate * q)))
    kind = RULES_RECIPES[g][3]
    if in_cnt[mid] > RULES_KIND[kind][4]:
        err_in.append((mid, "存货端口数", in_cnt[mid], RULES_KIND[kind][4]))
    if out_cnt[mid] > RULES_KIND[kind][5]:
        err_out.append((mid, "取货端口数", out_cnt[mid], RULES_KIND[kind][5]))
    if out_cnt[mid] != n:
        err_out.append((mid, "取货通道数≠设计", out_cnt[mid], n))
say(f"  进料不足/过量的 (机器,物品)：{err_in if err_in else '无'}")
say(f"  出料不符的 (机器,物品)：{err_out if err_out else '无'}")

S = sum(out_cnt.values()) + ore_edges      # 非运输 → 运输
R = sum(in_cnt.values()) + core_edges      # 运输 → 非运输
say(f"  S = {S}（运输端口收支 要求 ≥312）、R = {R}（要求 ≥307）、通道总数 {len(chan)}")
say(f"  机器取货通道 {sum(out_cnt.values())}、机器存货通道 {sum(in_cnt.values())}")

say("")
say("  贴边核对（求解约束 研磨进料 / 封装进料 / 成品汇入）：")
gr = [m for m, g, b, n in design_inst if g.startswith("研磨")]
say(f"    研磨机 32 台中存货通道 ≥3 的：{sum(1 for m in gr if in_cnt[m] >= 3)}（要 ≥31）"
    f"；分布 {dict(sorted(Counter(in_cnt[m] for m in gr).items()))}")
sh = [m for m, g, b, n in design_inst if g.startswith("塑形")]
say(f"    塑形机 6 台中存货通道 ≥2 的：{sum(1 for m in sh if in_cnt[m] >= 2)}（要 ≥5）"
    f"；分布 {dict(sorted(Counter(in_cnt[m] for m in sh).items()))}")
pk = [m for m, g, b, n in design_inst if g.startswith("封装")]
say(f"    封装机存货通道数 {[in_cnt[m] for m in pk]}（要每台 ≥5）；"
    f"各条速率 {[sorted(str(F(int(c['件每20tick']), P)) for c in chan if c['目标机器id'] == m) for m in pk]}")
fl = [m for m, g, b, n in design_inst if g.startswith("灌装")]
say(f"    灌装机存货通道数 {[in_cnt[m] for m in fl]}（要至少 2 台各 ≥4）；"
    f"各条速率 {[sorted(str(F(int(c['件每20tick']), P)) for c in chan if c['目标机器id'] == m) for m in fl]}")
say(f"    成品来源 K={core_edges}、B=0、C=0 ⇒ K+3B+2C={core_edges}（成品汇入 要 ≥6）")

say("")
say("  满载配置 / 矿线专机 / 混做清空 的静态前提：")
say(f"    粉碎机 {kind_cnt['粉碎机']} 台 ≠ 下限 68 ⇒ 满载配置 的粉碎机分句前提不成立")
say(f"    采种机 {kind_cnt['采种机']} 台 ≠ 下限 16 ⇒ 满载配置 / 研磨进料 的采种机分句前提不成立")
say(f"    精炼炉 {kind_cnt['精炼炉']} 台 = 下限 51、配件机 {kind_cnt['配件机']} = 6、"
    f"种植机 {kind_cnt['种植机']} = 32、封装机 3、灌装机 3 ⇒ 满载配置 对这些机型成立")
mixers = [m for m, g, b, n in design_inst if b < P and RULES_RECIPES[g][2] == 1]
say(f"    不满载的 1tick 机（批次 < 20/20tick）：{len(mixers)} 台 {mixers}")

say("")
say("=" * 78)
say("第四部分：与 contract.json 逐字段对照")
say("=" * 78)
ct = json.load(open(os.path.join(ROOT, "求解器/数据/候选B/contract.json"), encoding="utf-8"))
say(f"  schema={ct['schema']} candidate={ct['candidate']} "
    f"rate_window={ct['rate_window']['value']}（{ct['rate_window']['category']}）")
say(f"  machines {len(ct['machines'])}、sources {len(ct['sources'])}、"
    f"logical_feeds {len(ct['logical_feeds'])}、fanouts {len(ct['fanouts'])}")

# 机器：配方、批次率、端口数、占地
diff = []
for m in ct["machines"]:
    mid = m["id"]
    if mid not in design_by_id:
        diff.append((mid, "设计表里没有", "", ""))
        continue
    g, b, n = design_by_id[mid]
    kind = RULES_RECIPES[g][3]
    if m["kind"] != kind:
        diff.append((mid, "kind", m["kind"], kind))
    rs = m["recipes"]
    if len(rs) != 1 or rs[0]["recipe"] != g:
        diff.append((mid, "recipe", str(rs), g))
        continue
    if frac(rs[0]["planned_batch_rate"]["value"]) != F(b, P):
        diff.append((mid, "planned_batch_rate", rs[0]["planned_batch_rate"]["value"], str(F(b, P))))
    if frac(rs[0]["planned_mean_batch_interval"]["value"]) != F(P, b):
        diff.append((mid, "planned_mean_batch_interval",
                     rs[0]["planned_mean_batch_interval"]["value"], str(F(P, b))))
    if int(m["input_ports"]["value"]) != RULES_KIND[kind][4]:
        diff.append((mid, "input_ports", m["input_ports"]["value"], RULES_KIND[kind][4]))
    if int(m["output_ports"]["value"]) != RULES_KIND[kind][5]:
        diff.append((mid, "output_ports", m["output_ports"]["value"], RULES_KIND[kind][5]))
    if int(m["area"]["value"]) != RULES_KIND[kind][1]:
        diff.append((mid, "area", m["area"]["value"], RULES_KIND[kind][1]))
say(f"  机器字段不一致：{len(diff)} 处" + ("" if not diff else " " + str(diff[:10])))
say(f"  contract 机器占地合计 {sum(int(m['area']['value']) for m in ct['machines'])}（复算 {area}）")

# 多料机：38 台大机是否都带 multi_material 三栏
big = [m for m in ct["machines"] if m["kind"] in ("研磨机", "封装机", "灌装机")]
withmm = [m for m in big if m.get("multi_material")]
say(f"  大机（研磨/封装/灌装）{len(big)} 台，带 multi_material 的 {len(withmm)} 台")
if withmm:
    say(f"    字段样本：{json.dumps(withmm[0]['multi_material'], ensure_ascii=False)}")
nonbig_mm = [m["id"] for m in ct["machines"]
             if m["kind"] not in ("研磨机", "封装机", "灌装机") and m.get("multi_material")]
say(f"  非大机带 multi_material 的：{len(nonbig_mm)} 台 {nonbig_mm[:5]}")

# 逻辑送料记录：与 channels.csv 逐条对照
by_key = defaultdict(list)
for c in chan:
    by_key[(c["源机器id"], c["目标机器id"], c["物品"], c["件每20tick"])].append(c)
lf_diff = []
lf_key = defaultdict(list)
for lf in ct["logical_feeds"]:
    src = lf["source"]
    tgt = lf["target"]
    rate20 = frac(lf["planned_rate"]["value"]) * P
    if rate20.denominator != 1:
        lf_diff.append((lf["id"], "速率非整数/20tick", str(rate20), ""))
        continue
    src_csv = "仓库出矿口" if src.startswith("ORE") else src
    tgt_csv = "协议核心" if tgt in ("CORE", "核心", "协议核心") else tgt
    lf_key[(src_csv, tgt_csv, lf["item"], str(int(rate20)))].append(lf["id"])
for k, v in by_key.items():
    if len(lf_key.get(k, [])) != len(v):
        lf_diff.append((k, "条数不同", len(v), len(lf_key.get(k, []))))
for k, v in lf_key.items():
    if k not in by_key:
        lf_diff.append((k, "契约多出", 0, len(v)))
say(f"  logical_feeds 与 channels.csv 不一致：{len(lf_diff)} 处" +
    ("" if not lf_diff else " " + str(lf_diff[:10])))
say(f"  proven_actual_rate 非空的条数：{sum(1 for lf in ct['logical_feeds'] if lf.get('proven_actual_rate') is not None)}")
via_keys = Counter()
for lf in ct["logical_feeds"]:
    via_keys[tuple(sorted(lf.get("via", {}).keys()))] += 1
say(f"  via 字段键集合分布：{dict(via_keys)}")

# 扇出：与 fanout.json 对照，并与复算的 30/2/1 对照
fj = json.load(open(os.path.join(SRC, "fanout.json"), encoding="utf-8"))
say(f"  fanout.json {len(fj)} 条，类别 {dict(sorted(Counter(r['类别'] for r in fj).items()))}")
shape = Counter(f_["planned_shape"] for f_ in ct["fanouts"])
say(f"  contract fanouts 形状分布 {dict(shape)}")
cert = Counter(f_.get("certification") for f_ in ct["fanouts"])
say(f"  contract fanouts 认证状态 {dict(cert)}")
calc_by_m = {(f_[0], f_[2]): f_ for f_ in fanout_calc}
fo_diff = []
for f_ in ct["fanouts"]:
    key = (f_["machine"], f_["item"])
    if key not in calc_by_m:
        fo_diff.append((key, "复算里没有这个扇出点", "", ""))
        continue
    mid, g, it, n, pr, iv, q, cls = calc_by_m[key]
    if int(f_["ports"]["value"]) != n:
        fo_diff.append((key, "ports", f_["ports"]["value"], n))
    if frac(f_["planned_port_rate"]["value"]) != pr:
        fo_diff.append((key, "planned_port_rate", f_["planned_port_rate"]["value"], str(pr)))
    if frac(f_["planned_mean_batch_interval"]["value"]) != iv:
        fo_diff.append((key, "interval", f_["planned_mean_batch_interval"]["value"], str(iv)))
    if int(f_["batch_size"]["value"]) != q:
        fo_diff.append((key, "batch_size", f_["batch_size"]["value"], q))
    want = {"A": "满速扇出定则型", "B": "轮询均分型", "C": "两者都不落"}[cls]
    if f_["planned_shape"] != want:
        fo_diff.append((key, "planned_shape", f_["planned_shape"], want))
say(f"  fanouts 字段不一致：{len(fo_diff)} 处" + ("" if not fo_diff else " " + str(fo_diff[:10])))

# 来源端口身份
ids = ct["sources"]
say(f"  sources {len(ids)} 条，item 分布 {dict(Counter(s['item'] for s in ids))}")
st = Counter(s["identity"]["status"] for s in ids)
say(f"  来源身份状态 {dict(st)}；source_domain = {json.dumps(ct['source_domain'], ensure_ascii=False)}")
say(f"  core = {json.dumps(ct['core'], ensure_ascii=False)}")
say(f"  targets = {json.dumps(ct['targets'], ensure_ascii=False)}")
say(f"  planned_absent = {ct['planned_absent']}")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "复算输出-r3.txt"),
          "w", encoding="utf-8") as f:
    f.write("\n".join(OUT) + "\n")
