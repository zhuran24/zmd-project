"""Semantic Scholar 引用链：s2.py chain ID1 ID2 ... -> 打印按连到种子数排序的候选；结果缓存到 s2cache/"""
import sys, json, os, time, hashlib, requests
O = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = os.path.join(O, "s2cache"); os.makedirs(C, exist_ok=True)
F = "title,year,externalIds,citationCount,venue,abstract"
def get(url, params):
    k = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    p = os.path.join(C, k + ".json")
    if os.path.exists(p): return json.load(open(p))
    for i in range(6):
        r = requests.get(url, params=params, timeout=60, headers={"User-Agent": "curl/8.0"})
        if r.status_code == 429: print("429", file=sys.stderr); time.sleep(3 + 2 * i); continue
        if r.status_code >= 400: raise RuntimeError(f"{r.status_code} {url} {r.text[:200]}")
        d = r.json(); json.dump(d, open(p, "w")); time.sleep(1.2); return d
    raise RuntimeError("429 forever " + url)
B = "https://api.semanticscholar.org/graph/v1/paper/"
def paper(pid): return get(B + pid, {"fields": F + ",referenceCount,citationCount"})
def links(pid, kind, cap=1000):
    out, off = [], 0
    key = "citedPaper" if kind == "references" else "citingPaper"
    while off < cap:
        d = get(B + pid + "/" + kind, {"fields": F, "limit": 100 if kind=="references" else 1000, "offset": off})
        data = d.get("data") or []
        out += [x[key] for x in data if x.get(key) and x[key].get("title")]
        if "next" not in d or not data: break
        off = d["next"]
    return out
def ident(p):
    e = p.get("externalIds") or {}
    if e.get("DOI"): return e["DOI"]
    if e.get("ArXiv"): return "arXiv:" + e["ArXiv"]
    return "S2:" + str(p.get("paperId"))
if __name__ == "__main__":
    cmd, ids = sys.argv[1], sys.argv[2:]
    if cmd == "info":
        for i in ids:
            p = paper(i); print(ident(p), p["title"], p.get("year"), "refs", p.get("referenceCount"), "cites", p.get("citationCount"))
    elif cmd in ("chain", "refs", "cites"):
        cnt, rec, src = {}, {}, {}
        for i in ids:
            ls = []
            if cmd in ("chain", "refs"): ls += [(x, "R") for x in links(i, "references")]
            if cmd in ("chain", "cites"): ls += [(x, "C") for x in links(i, "citations")]
            seen = set()
            for x, t in ls:
                k = x.get("paperId")
                if k in seen: continue
                seen.add(k); cnt[k] = cnt.get(k, 0) + 1; rec[k] = x; src.setdefault(k, []).append(t + ":" + i)
        items = sorted(cnt, key=lambda k: (cnt[k], rec[k].get("citationCount") or 0), reverse=True)
        outp = os.path.join(O, "s2_" + cmd + ".jsonl")
        with open(outp, "a") as f:
            for k in items:
                r = dict(rec[k]); r["links"] = cnt[k]; r["via"] = src[k]; f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for k in items:
            r = rec[k]
            print(f'{cnt[k]} [{ident(r)}] {r["title"]} ({r.get("year")}, {(r.get("venue") or "")[:30]}, c={r.get("citationCount")}) {",".join(src[k])[:60]}')
