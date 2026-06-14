# ruff: noqa: E702, E741  (工具脚本紧凑写法, 豁免分号/单字母变量)
import json
import collections
import builtins
import typing
import sys
import os
import shutil

# 停用词 = Python 内置(含所有内置异常/类型/函数) + typing 全部名字 + 几个高频外部类型。
# 这些是"外部依赖符号"(异常/容器/类型注解), 对理解项目自身代码结构零价值, 是 graphify
# 启发式连线("名字相同就连")的噪声来源(raise ValueError 被当成 calls ValueError 等)。
STOP = set(dir(builtins)) | set(dir(typing)) | {
    "Path", "PurePath", "PosixPath", "WindowsPath",
    "MonkeyPatch", "CaptureFixture", "TempPathFactory", "TemporaryDirectory",
    "datetime", "timedelta", "date", "Decimal", "Fraction",
}

base = r"C:\claude pj\zmd_pj\cc_context\graphify\out\graphify-out"
raw = base + r"\graph.json.raw"
src = raw if os.path.exists(raw) else base + r"\graph.json"   # 幂等: 总从原始图出发
g = json.load(open(src, encoding="utf-8"))
nodes = g["nodes"]; links = g["links"]

stop_ids = {n["id"] for n in nodes if n.get("label") in STOP}
stop_labels = collections.Counter(n.get("label") for n in nodes if n.get("label") in STOP)
kept_nodes = [n for n in nodes if n["id"] not in stop_ids]
kept_links = [e for e in links if e.get("source") not in stop_ids and e.get("target") not in stop_ids]

inf_b = sum(1 for e in links if e.get("confidence") == "INFERRED")
inf_a = sum(1 for e in kept_links if e.get("confidence") == "INFERRED")
print(f"读自: {os.path.basename(src)}")
print(f"节点: {len(nodes)} -> {len(kept_nodes)}  (删 {len(stop_ids)} 个通用名节点)")
print(f"边:   {len(links)} -> {len(kept_links)}  (删 {len(links)-len(kept_links)} 条)")
print(f"INFERRED: {inf_b} -> {inf_a}  (噪声砍掉 {round(100*(inf_b-inf_a)/inf_b,1)}%)")

print("\n=== 删除的通用名节点 (去重 top 25, 确认全是外部/内置名) ===")
for l, c in stop_labels.most_common(25):
    print(f"  {c:>3} 个实例  {l}")

print("\n=== 误伤排查: 删的节点里 label 看着像领域类的? ===")
sus = [l for l in stop_labels if l and (l[0].isupper() and l not in (
    set(dir(builtins)) | set(dir(typing))))]
print("  非 builtins/typing 的大写名:", sorted(sus) if sus else "无(全是标准库通用名) ✓")

if "--apply" in sys.argv:
    if not os.path.exists(raw):
        shutil.copy(base + r"\graph.json", raw)
    g["nodes"] = kept_nodes; g["links"] = kept_links
    json.dump(g, open(base + r"\graph.json", "w", encoding="utf-8"), ensure_ascii=False)
    nm = {n["id"]: n for n in kept_nodes}; deg = collections.Counter()
    for e in kept_links:
        deg[e["source"]] += 1; deg[e["target"]] += 1
    rows = sorted(((d, nm[i].get("label")) for i, d in deg.items()
                   if nm.get(i, {}).get("source_file") and not str(nm[i].get("label", "")).endswith(".py")), reverse=True)
    print("\nAPPLIED (写回 graph.json, 原始图 graph.json.raw)。清理后 god-nodes top 10 (符号级):")
    for d, l in rows[:10]:
        print(f"  {d:>4}  {l}")
