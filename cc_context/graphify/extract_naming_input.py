import json
import collections

base = r"C:\claude pj\zmd_pj\cc_context\graphify\out\graphify-out"
g = json.load(open(base + r"\graph.json", encoding="utf-8"))
nodes = g["nodes"]
links = g["links"]

# degree from links
deg = collections.Counter()
for e in links:
    deg[e.get("source")] += 1
    deg[e.get("target")] += 1

by_comm = collections.defaultdict(list)
for n in nodes:
    by_comm[n.get("community")].append(n)

def is_noise(n):
    nid = n.get("id", "")
    lbl = n.get("label", "")
    if "_rationale_" in nid:
        return True
    if len(lbl) > 55 or "\n" in lbl:
        return True
    return False

def dominant_dir(members):
    dirs = collections.Counter()
    for m in members:
        sf = m.get("source_file", "")
        sf = sf.replace("src_mirror/", "src/")
        d = "/".join(sf.split("/")[:-1])
        dirs[d] += 1
    return dirs.most_common(1)[0][0] if dirs else ""

out = []
for cid, members in by_comm.items():
    size = len(members)
    if size < 10:
        continue
    ranked = sorted(members, key=lambda m: deg.get(m.get("id"), 0), reverse=True)
    top = []
    for m in ranked:
        if is_noise(m):
            continue
        top.append({"label": m.get("label"), "file": m.get("source_file", "").replace("src_mirror/", "src/"), "deg": deg.get(m.get("id"), 0)})
        if len(top) >= 10:
            break
    out.append({
        "id": cid,
        "size": size,
        "dominant_dir": dominant_dir(members),
        "top_members": top,
    })

out.sort(key=lambda c: c["size"], reverse=True)
json.dump(out, open(base + r"\community_naming_input.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("communities to name (size>=10):", len(out))
print("total nodes covered:", sum(c["size"] for c in out))
# rough payload size
s = json.dumps(out, ensure_ascii=False)
print("payload chars:", len(s), "~tokens:", len(s)//4)
print("\n=== first 3 communities sample ===")
print(json.dumps(out[:3], ensure_ascii=False, indent=1)[:1500])
