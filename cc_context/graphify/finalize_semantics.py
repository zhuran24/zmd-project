# ruff: noqa: E702, E741  (工具脚本紧凑写法, 豁免分号/单字母变量)
import json
import collections
import shutil
import os
base = r"C:\claude pj\zmd_pj\cc_context\graphify\out"
g = json.load(open(base + r"\graphify-out\graph.json", encoding="utf-8"))
nodes = g["nodes"]; links = g["links"]
deg = collections.Counter()
for e in links:
    deg[e["source"]] += 1; deg[e["target"]] += 1
by = collections.defaultdict(list)
for n in nodes:
    by[n["community"]].append(n)

def is_noise(n):
    nid = n.get("id", ""); lbl = n.get("label", "")
    return "_rationale_" in nid or len(lbl) > 55 or "\n" in lbl

def dom(ms):
    c = collections.Counter()
    for m in ms:
        sf = m.get("source_file", "").replace("src_mirror/", "src/")
        c["/".join(sf.split("/")[:-1])] += 1
    return c.most_common(1)[0][0] if c else ""

def tops(ms, k=6):
    out = []
    for m in sorted(ms, key=lambda m: deg.get(m["id"], 0), reverse=True):
        if is_noise(m):
            continue
        out.append(m["label"])
        if len(out) >= k:
            break
    return out

named = json.load(open(base + r"\chunks\named_merged_partial.json", encoding="utf-8"))
sem = {}; auto = 0; llm = 0
for cid, ms in by.items():
    size = len(ms); d = dom(ms); t = tops(ms)
    key = str(cid)
    if key in named:
        sem[cid] = {"name": named[key]["name"], "role": named[key]["role"], "size": size, "dominant_dir": d, "top_symbols": t, "named_by": "llm"}
        llm += 1
    else:
        segs = [s for s in d.split("/") if s and s != "src"]
        short = "/".join(segs[-2:]) if segs else "misc"
        sem[cid] = {"name": f"[{short}] 细碎簇", "role": f"小社区({size}节点), 主要在 {d}", "size": size, "dominant_dir": d, "top_symbols": t, "named_by": "auto"}
        auto += 1

sem_sorted = {str(k): sem[k] for k in sorted(sem, key=lambda c: sem[c]["size"], reverse=True)}
json.dump(sem_sorted, open(base + r"\graphify-out\community_semantics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

lp = base + r"\graphify-out\.graphify_labels.json"
if not os.path.exists(lp + ".orig"):
    shutil.copy(lp, lp + ".orig")
labels = json.load(open(lp, encoding="utf-8"))
for cid, v in sem.items():
    labels[str(cid)] = v["name"]
json.dump(labels, open(lp, "w", encoding="utf-8"), ensure_ascii=False)

print(f"total communities: {len(sem)}  llm-named: {llm}  auto-named(size<10): {auto}")
print("wrote community_semantics.json + backfilled .graphify_labels.json (.orig backup kept)\n")
print("=== top 40 communities by size (for SEMANTIC_MAP) ===")
for k in list(sem_sorted)[:40]:
    v = sem_sorted[k]
    print(f"  c{k:>3} [{v['size']:>3}] {v['dominant_dir']:<42} | {v['name']}")
