#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 校验报告.md 每一行里的数字抽出来，和独立复算的值逐项比。"""
import json, re, sys
from collections import Counter, defaultdict
from fractions import Fraction as F
sys.path.insert(0, ".")
DATA = "/home/zhuran24/zmd-research-fresh/求解器/数据"
C = json.load(open(f"{DATA}/候选B/contract.json", encoding="utf-8"))
rep = open(f"{DATA}/候选B/校验报告.md", encoding="utf-8").read()
rows = {}
for m in re.finditer(r"^\| ([^|]+) \| ([^|]*) \|$", rep, re.M):
    n, d = m.group(1).strip(), m.group(2).strip()
    if n == "检查项／据":
        continue
    rows.setdefault(n, d)

RECIPES = json.load(open(f"{DATA}/正式静态目录.json", encoding="utf-8"))["recipes"]
REC = {r["id"]: r for r in RECIPES}
q = lambda x: F(x["value"])
cm = {m["id"]: m for m in C["machines"]}
cin, cout = defaultdict(F), defaultdict(F)
deg_in, deg_out = defaultdict(set), defaultdict(set)
for e in C["logical_feeds"]:
    cout[(e["source"], e["item"])] += q(e["planned_rate"])
    cin[(e["target"], e["item"])] += q(e["planned_rate"])
    deg_out[e["source"]].add(e["source_port"])
    deg_in[e["target"]].add(e["target_port"])

bad = []
# 1) 逐机配方守恒行
n = 0
for name, det in rows.items():
    m = re.match(r"^逐机配方守恒/(M\d+)/([^/]+)/(输入|输出)/(.+)$", name)
    if not m:
        continue
    mid, rec, side, item = m.groups()
    got = re.search(r"计划通道合计 (\S+)，配方要求 (\S+) 件/tick", det)
    a, b = F(got.group(1)), F(got.group(2))
    br = q(cm[mid]["recipes"][0]["planned_batch_rate"])
    coef = F(REC[rec]["inputs" if side == "输入" else "outputs"][item]["value"])
    mine_a = (cin if side == "输入" else cout)[(mid, item)]
    if (a, b) != (mine_a, br * coef):
        bad.append(("逐机配方守恒", name, det, (a, b), (mine_a, br * coef)))
    n += 1
print(f"逐机配方守恒行 {n} 条，全部数字与复算一致：{not [x for x in bad if x[0]=='逐机配方守恒']}")

# 2) 端口数行
n = 0
for name, det in rows.items():
    m = re.match(r"^端口数/(M\d+)$", name)
    if not m:
        continue
    mid = m.group(1)
    g = re.search(r"存货 (\d+)、取货 (\d+)、存货上限 (\d+)、取货上限 (\d+)", det)
    a = tuple(int(x) for x in g.groups())
    b = (len(deg_in[mid]), len(deg_out[mid]),
         int(cm[mid]["input_ports"]["value"]), int(cm[mid]["output_ports"]["value"]))
    if a != b:
        bad.append(("端口数", name, det, a, b))
    n += 1
print(f"端口数行 {n} 条，一致：{not [x for x in bad if x[0]=='端口数']}")

# 3) 端口速率逐端口行
n = 0
prate = defaultdict(F)
for e in C["logical_feeds"]:
    prate[("取货", e["source"], e["source_port"])] += q(e["planned_rate"])
    prate[("存货", e["target"], e["target_port"])] += q(e["planned_rate"])
for name, det in rows.items():
    m = re.match(r"^端口速率/(存货|取货)/([^/]+)/(.+)$", name)
    if not m:
        continue
    side, owner, pid = m.groups()
    g = re.search(r"端口各记录合计 (\S+) 件/tick", det)
    if F(g.group(1)) != prate[(side, owner, pid)]:
        bad.append(("端口速率", name, det, g.group(1), str(prate[(side, owner, pid)])))
    n += 1
print(f"端口速率逐端口行 {n} 条，一致：{not [x for x in bad if x[0]=='端口速率']}")

# 4) 全局守恒 / 物料流量 / 占地 / 制造能力
prod, cons, ext, deliv = defaultdict(F), defaultdict(F), defaultdict(F), defaultdict(F)
for mm in C["machines"]:
    rec = mm["recipes"][0]["recipe"]; br = q(mm["recipes"][0]["planned_batch_rate"])
    for i, v in REC[rec]["inputs"].items():
        cons[i] += br * F(v["value"])
    for i, v in REC[rec]["outputs"].items():
        prod[i] += br * F(v["value"])
srcids = {s["id"] for s in C["sources"]}
for e in C["logical_feeds"]:
    if e["source"] in srcids:
        ext[e["item"]] += q(e["planned_rate"])
    if e["target"] == "CORE":
        deliv[e["item"]] += q(e["planned_rate"])
n = 0
for name, det in rows.items():
    m = re.match(r"^全局守恒/(.+)$", name)
    if not m: continue
    it = m.group(1)
    g = re.search(r"产出\+出库 (\S+) = 消耗\+入库 (\S+) 件/tick", det)
    a, b = F(g.group(1)), F(g.group(2))
    if (a, b) != (prod[it] + ext[it], cons[it] + deliv[it]):
        bad.append(("全局守恒", name, det, (a, b), (prod[it]+ext[it], cons[it]+deliv[it])))
    n += 1
print(f"全局守恒行 {n} 条，一致：{not [x for x in bad if x[0]=='全局守恒']}")
thr = defaultdict(F)
for e in C["logical_feeds"]:
    thr[e["item"]] += q(e["planned_rate"])
n = 0
for name, det in rows.items():
    m = re.match(r"^物料流量/(.+)$", name)
    if not m: continue
    it = m.group(1)
    g = re.search(r"^(\S+) ≥ (\S+) 件/tick", det)
    if F(g.group(1)) != thr[it]:
        bad.append(("物料流量", name, det, g.group(1), str(thr[it])))
    n += 1
print(f"物料流量行 {n} 条，一致：{not [x for x in bad if x[0]=='物料流量']}")
n = 0
for name, det in rows.items():
    m = re.match(r"^制造能力/(M\d+)$", name)
    if not m: continue
    mid = m.group(1)
    g = re.search(r"之和 (\S+) ≤1", det)
    rec = cm[mid]["recipes"][0]["recipe"]
    want = q(cm[mid]["recipes"][0]["planned_batch_rate"]) * F(REC[rec]["duration"]["value"])
    if F(g.group(1)) != want:
        bad.append(("制造能力", name, det, g.group(1), str(want)))
    n += 1
print(f"制造能力行 {n} 条，一致：{not [x for x in bad if x[0]=='制造能力']}")
n = 0
for name, det in rows.items():
    m = re.match(r"^扇出/计划分类/(M\d+)$", name)
    if not m: continue
    n += 1
print(f"扇出分类行 {n} 条")
# 5) 通道下限 / 机型下限行
for name, det in rows.items():
    m = re.match(r"^通道下限/(.+)$", name)
    if not m: continue
    k = m.group(1)
    g = re.search(r"存货 (\d+) ≥(\d+)；取货 (\d+) ≥(\d+)", det)
    ids = [x["id"] for x in C["machines"] if x["kind"] == k]
    a = (sum(len(deg_in[i]) for i in ids), sum(len(deg_out[i]) for i in ids))
    if (int(g.group(1)), int(g.group(3))) != a:
        bad.append(("通道下限", name, det, g.groups(), a))
for name, det in rows.items():
    m = re.match(r"^机型下限/(.+)$", name)
    if not m: continue
    k = m.group(1)
    g = re.search(r"^(\d+) ≥ (\d+)", det)
    a = sum(1 for x in C["machines"] if x["kind"] == k)
    if int(g.group(1)) != a:
        bad.append(("机型下限", name, det, g.group(1), a))
print(f"通道下限/机型下限一致：{not [x for x in bad if x[0] in ('通道下限','机型下限')]}")
print()
print(f"不一致合计 {len(bad)} 项")
for x in bad[:20]:
    print("  !!", x)
