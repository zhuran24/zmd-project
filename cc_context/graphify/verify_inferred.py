# ruff: noqa: E702, E741  (工具脚本紧凑写法, 豁免分号/单字母变量)
import json
import ast
import os
import collections
import sys

base = r"C:\claude pj\zmd_pj\cc_context\graphify\out"
MIR = base + r"\src_mirror"
g = json.load(open(base + r"\graphify-out\graph.json", encoding="utf-8"))
nodes = {n["id"]: n for n in g["nodes"]}
links = g["links"]

def real_path(source_file):
    rel = source_file.replace("src_mirror/", "").replace("/", os.sep)
    return os.path.join(MIR, rel)

def clean_label(lbl):
    # ".from_exact_core()" -> "from_exact_core"; "now_iso()" -> "now_iso"; "BState" -> "BState"
    return (lbl or "").split("(")[0].lstrip(".").strip()

# 全局索引: 符号名 -> 定义它的源文件集合 (用来判断名字是否全局唯一)
def_files = collections.defaultdict(set)
for n in g["nodes"]:
    lbl = clean_label(n.get("label"))
    sf = n.get("source_file")
    if lbl and sf:
        def_files[lbl].add(sf)

# 每个文件的 import 名单 (缓存)
_imp = {}
def imports_of(path):
    if path in _imp:
        return _imp[path]
    imp = {}
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for a in node.names:
                    imp[a.asname or a.name] = mod
            elif isinstance(node, ast.Import):
                for a in node.names:
                    imp[(a.asname or a.name).split(".")[0]] = a.name
    except Exception:
        pass
    _imp[path] = imp
    return imp

def module_tail(source_file):
    # src_mirror/models/master_model.py -> master_model
    return source_file.replace("src_mirror/", "").rsplit(".py", 1)[0].replace("/", ".").split(".")[-1]

total = verified = 0
reason = collections.Counter()
verified_edges = []
unverified_samples = []
for e in links:
    if e.get("confidence") != "INFERRED":
        continue
    total += 1
    s = nodes.get(e["source"], {}); t = nodes.get(e["target"], {})
    sf, tf = s.get("source_file", ""), t.get("source_file", "")
    tl = clean_label(t.get("label"))
    ok = False
    if not sf or not tl:
        reason["缺字段"] += 1
    elif sf == tf:
        ok = True; reason["✓同文件作用域"] += 1
    else:
        imp = imports_of(real_path(sf))
        if tl not in imp:
            reason["✗source没import该名字"] += 1
            if len(unverified_samples) < 12:
                unverified_samples.append(f"{s.get('label')}  [{sf}]  --{e.get('relation')}-->  {t.get('label')}  [{tf}]")
        else:
            deffiles = def_files.get(tl, set())
            if len(deffiles) == 1:
                ok = True; reason["✓import+名字全局唯一"] += 1
            else:
                mod_tail = imp[tl].split(".")[-1] if imp[tl] else ""
                if mod_tail and mod_tail == module_tail(tf):
                    ok = True; reason["✓import+模块路径匹配"] += 1
                else:
                    reason["✗import但歧义未坐实"] += 1
                    if len(unverified_samples) < 12:
                        unverified_samples.append(f"{s.get('label')}  [{sf}]  --{e.get('relation')}-->  {t.get('label')}  [{tf}] (歧义)")
    if ok:
        verified += 1
        verified_edges.append(e)

print(f"INFERRED 边总数: {total}")
print(f"可坐实成 VERIFIED: {verified}  ({round(100*verified/total,1)}%)")
print(f"仍保持 INFERRED:   {total - verified}  ({round(100*(total-verified)/total,1)}%)")
print("\n明细:")
for r, c in reason.most_common():
    print(f"  {c:>5}  {r}")

if unverified_samples:
    print("\n=== 未坐实的边样本 (graphify 可能连错的同名巧合) ===")
    for s in unverified_samples:
        print("  " + s)

if "--apply" in sys.argv:
    for e in verified_edges:
        e["confidence"] = "VERIFIED"
    json.dump(g, open(base + r"\graphify-out\graph.json", "w", encoding="utf-8"), ensure_ascii=False)
    dist = collections.Counter(e.get("confidence") for e in links)
    print(f"\nAPPLIED: 写回 graph.json。边置信分布 -> {dict(dist)}")
