#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核席（数值复算）第 3 轮：两个由契约自身数据直接算出、但报告没写的投影。

一、运输端口收支（求解约束）在 M=0 时给出 T+b ≥ S+E ≥ S，本候选 S=315，
    故 T+b ≥315；它严格强于 箱体过站 在 Q=0 时给出的 T+b ≥⌈305.65⌉=306。
二、满速独占 的主语是「每 tick 恰通过 1 件的通道」，不止条文举例的 52 条矿石通道；
    本候选计划速率恰 1 件/tick 的逻辑送料记录有多少条。
全部用 Fraction。
"""
from fractions import Fraction as F
from collections import Counter
import json, math, os

C = "/home/zhuran24/zmd-research-fresh/求解器/数据/候选B/contract.json"
d = json.load(open(C, encoding="utf-8"))
out = []


def say(s=""):
    out.append(s)
    print(s)


feeds = d["logical_feeds"]
rates = [F(f["planned_rate"]["value"]) for f in feeds]

# ---- 一、S 与 T+b 下界
srcs = {(f["source"], f["source_port"]) for f in feeds if F(f["planned_rate"]["value"]) > 0}
tgts = {(f["target"], f["target_port"]) for f in feeds if F(f["planned_rate"]["value"]) > 0}
S, R = len(srcs), len(tgts)
say(f"一、S（非运输端点取货接口，去重后）= {S}；R = {R}")
say(f"   planned_absent = {d['planned_absent']} ⇒ 分流器 D=0、汇流器 M=0（契约自述的受限模型）")
say("   运输端口收支：T+b+2M ≥ S+E；M=0、E ≥0 ⇒ T+b ≥ S = %d" % S)
flow = sum(rates)          # 计划总流量（件/tick），不含矿口→仓库外的重复计数
say(f"   契约计划的逐条速率之和 = {flow} 件/tick（求解约束 物料流量 的合计为 6113/20 = 305.65）")
say(f"   箱体过站：Q=0（无箱）⇒ T+b ≥⌈305.65+0⌉ = {math.ceil(F(6113,20))}")
say(f"   ⇒ 本候选的紧下界是 {S}，比 306 多 {S - 306} 个运输物品格；报告两处都没有把它写出来")

# ---- 二、满速独占 的适用条数
full = [f for f in feeds if F(f["planned_rate"]["value"]) == 1]
rest = Counter(str(F(f["planned_rate"]["value"])) for f in feeds if F(f["planned_rate"]["value"]) != 1)
say("")
say(f"二、计划速率恰 1 件/tick 的逻辑送料记录：{len(full)} / {len(feeds)}")
say(f"   其余速率分布：{dict(rest)}")
ore = [f for f in full if f["source"].startswith("ORE")]
say(f"   其中矿石取货记录 {len(ore)} 条（条文举例的那一批），非矿石的满速记录 {len(full) - len(ore)} 条")
kinds = Counter()
mk = {m["id"]: m for m in d["machines"]}
for f in full:
    kinds[mk[f["source"]]["kind"] if f["source"] in mk else "矿石来源"] += 1
say(f"   按源端分类：{dict(kinds)}")

open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "派生投影-r3.txt"),
     "w", encoding="utf-8").write("\n".join(out) + "\n")
