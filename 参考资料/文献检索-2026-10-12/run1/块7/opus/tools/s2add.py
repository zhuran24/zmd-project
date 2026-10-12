"""把 s2_*.jsonl 里选中的记录（按 DOI/arXiv 标识或标题子串）以 lit.py 的格式加入 pool"""
import sys, json, os
D = "/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索"
sys.path.insert(0, D); import lit
O = os.path.join(D, "run1/块7/opus"); P = os.path.join(O, "pool.jsonl")
src = sys.argv[1]; tag = sys.argv[2]; want = sys.argv[3:]
recs = {}
for l in open(os.path.join(O, src)):
    r = json.loads(l); e = r.get("externalIds") or {}
    ids = {(e.get("DOI") or "").lower(), ("arxiv:" + e["ArXiv"].lower()) if e.get("ArXiv") else ""}
    for w in want:
        wl = w.lower()
        if wl in ids or (len(wl) > 12 and wl in (r.get("title") or "").lower()):
            doi = e.get("DOI") or ""; ax = e.get("ArXiv") or ""
            if doi.lower().startswith("10.48550/arxiv."): ax = ax or doi[15:]
            key = doi if doi else ("arXiv:" + ax if ax else "S2:" + str(r.get("paperId")))
            recs[key] = {"key": key, "title": r["title"], "year": r.get("year"), "venue": r.get("venue") or "",
                         "cites": r.get("citationCount"), "authors": [], "doi": doi, "arxiv": ax, "oa_url": "",
                         "abstract": (r.get("abstract") or "")[:1500], "src": "s2", "chain_links": r.get("links"), "via": r.get("via")}
new = lit.add_pool(P, list(recs.values()), tag)
print("matched", len(recs), "new", len(new))
for r in new: print(" ", r["key"], r["title"][:90])
