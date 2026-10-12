#!/usr/bin/env python3
"""s2chain.py POOL TOP SEED... : 用 Semantic Scholar 取种子的参考文献和施引文献（OpenAlex 额度用完时的替代），
按连到几个种子、再按被引数排序，前 TOP 篇（须有 DOI 或 arXiv 号）追加进 POOL。"""
import sys, json, time, requests
sys.path.insert(0, "/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索")
import lit
pool, top, seeds = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
F = "title,year,externalIds,citationCount,abstract,venue,authors"
def get(u):
    for i in range(6):
        r = requests.get(u, timeout=40)
        if r.status_code == 429: time.sleep(5*(i+1)); continue
        if r.status_code != 200: print("!!", r.status_code, u, file=sys.stderr); return {}
        return r.json()
    return {}
cnt, rec = {}, {}
for s in seeds:
    linked = []
    for kind, fld in (("references", "citedPaper"), ("citations", "citingPaper")):
        d = get(f"https://api.semanticscholar.org/graph/v1/paper/{s}/{kind}?fields={F}&limit=100")
        linked += [x[fld] for x in (d.get("data") or []) if x.get(fld)]
        time.sleep(1.5)
    seen=set()
    for p in linked:
        ids = p.get("externalIds") or {}
        doi, arx = (ids.get("DOI") or ""), (ids.get("ArXiv") or "")
        if not (doi or arx) or not p.get("title"): continue
        k = doi.lower() or ("arXiv:" + arx)
        if k in seen: continue
        seen.add(k)
        cnt[k] = cnt.get(k, 0) + 1
        rec[k] = {"key": k if doi else "arXiv:" + arx, "title": p["title"], "year": p.get("year"), "venue": p.get("venue") or "",
                  "cites": p.get("citationCount"), "authors": [a["name"] for a in (p.get("authors") or [])[:3]],
                  "doi": doi, "arxiv": arx, "oa_url": "", "abstract": (p.get("abstract") or "")[:1500], "src": "s2"}
    print(f"seed {s}: {len(seen)} linked", file=sys.stderr)
cand = sorted((dict(rec[k], chain_links=c) for k, c in cnt.items()), key=lambda r: (r["chain_links"], r["cites"] or 0), reverse=True)[:top]
new = lit.add_pool(pool, cand, "s2chain:" + ",".join(seeds))
print(f"新进 {len(new)} 篇")
for r in new:
    print(f'- [{r["key"]}] {r["title"]} ({r["year"]}, 被引 {r["cites"]}, links={r["chain_links"]})')
    if r["abstract"]: print("    " + r["abstract"][:300])
