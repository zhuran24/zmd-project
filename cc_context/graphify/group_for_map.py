import json
import collections
sem = json.load(open(r"C:\claude pj\zmd_pj\cc_context\graphify\out\graphify-out\community_semantics.json", encoding="utf-8"))
groups = collections.defaultdict(list)
for cid, v in sem.items():
    d = v["dominant_dir"]
    segs = [s for s in d.split("/") if s and s != "src"]
    top = segs[0] if segs else "misc"
    # collapse tests/* into the subsystem they test for a cleaner index
    groups[top].append((v["size"], int(cid), v["name"], v["named_by"], d))
for top in sorted(groups, key=lambda t: -sum(x[0] for x in groups[t])):
    rows = sorted(groups[top], reverse=True)
    llm = [r for r in rows if r[3] == "llm"]
    print(f"\n#### {top}  ({len(rows)} 社区 / {sum(r[0] for r in rows)} 节点, llm-named {len(llm)})")
    for size, cid, name, nb, d in llm[:14]:
        print(f"  c{cid} [{size}] {name}")
