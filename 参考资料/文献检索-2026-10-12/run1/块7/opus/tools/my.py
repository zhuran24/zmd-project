import sys, json, os
D = "/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索"
sys.path.insert(0, D)
import lit
P = os.path.join(D, "run1/块7/opus/pool.jsonl")
cmd = sys.argv[1]
if cmd == "drop":  # drop keys from pool
    keys = set(sys.argv[2:])
    recs = lit.load_pool(P)
    keep = [r for r in recs if r["key"] not in keys]
    with open(P, "w", encoding="utf-8") as f:
        for r in keep: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"dropped {len(recs)-len(keep)}, pool {len(keep)}")
elif cmd == "add":  # add by KEY via free resolve
    tag = "manual:web"
    out = []
    for k in sys.argv[2:]:
        try:
            w = lit.resolve(k); out.append(lit._norm_oa(w))
        except Exception as e:
            print("fail", k, e)
    new = lit.add_pool(P, out, tag); lit.brief(new)
elif cmd == "info":
    for k in sys.argv[2:]:
        try:
            w = lit.resolve(k); r = lit._norm_oa(w)
            print(f'[{r["key"]}] {r["title"]} ({r["year"]}, {r["venue"]}, cites {r["cites"]}) doi={r["doi"]} arxiv={r["arxiv"]} refs={len(w.get("referenced_works") or [])}')
            print("   ", r["abstract"][:600])
        except Exception as e:
            print("fail", k, e)
