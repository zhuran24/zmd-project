# 只读：第四张全厂候选的 98 条缺路，按源、汇所在区块分类；并量供电桩挡住多少端口邻格、撤桩后空格连通块数
import json, collections, sys
B = "/home/zhuran24/zmd-research-fresh/求解器/构造/第四张全厂候选/"
plan = json.load(open(B + "规划/粗坐标.json"))
lay = json.load(open(B + "实现/布局.json"))["layout"]
chk = json.load(open(B + "实现/证据/逐路与端口核查.json"))
blk = {}
for m in plan["machines"]:
    if "模块" in m: blk[m["id"]] = m["模块"]
for name, ids in plan["blocks"].items():
    for i in ids: blk.setdefault(i, name.split("(")[0])
for w in lay["warehouse_outlets"]: blk.setdefault(w["id"], "边带取货口")
blk["core"] = "核心"
cls = collections.Counter(); unknown = set()
pairs = collections.Counter()
for r in chk["routes"]:
    if r["built"]: continue
    s, t = r["source"], r["target"]
    bs, bt = blk.get(s), blk.get(t)
    if bs is None: unknown.add(s)
    if bt is None: unknown.add(t)
    same = (bs == bt) and bs is not None
    cls[("同区块" if same else "跨区块")] += 1
    if not same: pairs[(bs, bt)] += 1
print("缺路", sum(cls.values()), dict(cls))
print("区块未知的单位", sorted(unknown)[:20], len(unknown))
for k, v in pairs.most_common(12): print(k, v)

# 端口不足的边：邻格被什么占着（边号 0E 1N 2W 3S，Din 为存货边外法向）
occ = {}
def mark(kind, u, x0, y0, x1, y1):
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1): occ[(x, y)] = kind
for m in lay["machines"]: mark("机器", m["id"], m["x0"], m["y0"], m["x1"], m["y1"])
for w in lay["warehouse_outlets"]: mark("取货口", w["id"], w["x0"], w["y0"], w["x1"], w["y1"])
c = lay["core"]; mark("核心", "core", c["x0"], c["y0"], c["x1"], c["y1"])
for p in lay["power_poles"]: mark("供电桩", p["id"], p["x0"], p["y0"], p["x1"], p["y1"])
M = {m["id"]: m for m in lay["machines"]}
def nb(m, s):
    x0, y0, x1, y1 = m["x0"], m["y0"], m["x1"], m["y1"]
    return {0: [(x1 + 1, y) for y in range(y0, y1 + 1)], 1: [(x, y1 + 1) for x in range(x0, x1 + 1)],
            2: [(x0 - 1, y) for y in range(y0, y1 + 1)], 3: [(x, y0 - 1) for x in range(x0, x1 + 1)]}[s]
cnt = collections.Counter(); sides = 0; pole_sides = 0
for u in chk["port_shortage_units"]:
    m = M.get(u["id"])
    if not m: continue
    for s, f, q in [(m["Din"], u["free_input_neighbors"], u["required_inputs"]),
                    ((m["Din"] + 2) % 4, u["free_output_neighbors"], u["required_outputs"])]:
        if f >= q: continue
        sides += 1; k = collections.Counter()
        for cell in nb(m, s):
            k["基地外" if not (0 <= cell[0] < 70 and 0 <= cell[1] < 70) else occ.get(cell, "空")] += 1
        cnt.update(k); pole_sides += bool(k.get("供电桩"))
print("端口不足的边", sides, "邻格占用", dict(cnt), "邻格里有桩的边", pole_sides)

def comps(with_poles):
    b = {c for c, k in occ.items() if with_poles or k != "供电桩"}
    seen = set(); n = 0
    for x in range(70):
        for y in range(70):
            if (x, y) in b or (x, y) in seen: continue
            n += 1; st = [(x, y)]; seen.add((x, y))
            while st:
                cx, cy = st.pop()
                for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                    if 0 <= nx < 70 and 0 <= ny < 70 and (nx, ny) not in b and (nx, ny) not in seen:
                        seen.add((nx, ny)); st.append((nx, ny))
    return 4900 - len(b), n
print("撤去运输单位后 空格数、连通块数：有桩", comps(True), "撤去全部桩", comps(False))
