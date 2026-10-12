#!/usr/bin/env python3
"""查论文的小工具：OpenAlex / arXiv / Crossref 检索，OpenAlex 引用链扩展，取开放全文。

用法（每条记录一行 JSON 追加进 --pool 指定的文件，按 DOI、arXiv 号、标题去重；屏幕上打印简表）：
  lit.py search "查询词" --pool P [--src openalex|arxiv|crossref] [--n 25]
  lit.py refs  KEY --pool P            # KEY 的参考文献
  lit.py cites KEY --pool P [--n 100]  # 引了 KEY 的论文，按被引数从高到低
  lit.py chain KEY1 KEY2 ... --pool P [--top 40]
        # 引用链扩展：取这些种子的全部参考文献和前 100 篇施引文献，去掉 pool 里已有的，
        # 按「连到几个种子」再按被引数排序，前 --top 篇追加进 pool（字段 chain_links 记连到的种子数）
  lit.py show --pool P [--grep 词]      # 打印 pool 简表
  lit.py full KEY                       # 下载开放获取 PDF 转成文本，打印文本文件路径
  lit.py budget                         # OpenAlex 今天还剩多少检索额度
KEY 可以是 OpenAlex 号（W123…）、DOI（10.…）或 arXiv 号（arXiv:2401.01234）。
OpenAlex 没有 key 时每天约 0.1 美元：检索一次 0.001，列表 0.0001，单篇 0。剩不到 0.005 时 search 自动改用 arXiv。
"""
import argparse, json, os, re, sys, time, hashlib, subprocess, urllib.parse
import xml.etree.ElementTree as ET
import requests

ROOT = '/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索/run1/块6/sol'
CACHE = os.path.join(ROOT, "cache")
os.makedirs(CACHE, exist_ok=True)
OA = "https://api.openalex.org"
SEL = "id,doi,title,publication_year,cited_by_count,primary_location,abstract_inverted_index,open_access,authorships,ids"
UA = {"User-Agent": "lit-review-script/1.0"}
BUDGET_FILE = os.path.join(CACHE, "_openalex_budget.json")


def _get(url, params=None, kind="json", tries=4):
    key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    path = os.path.join(CACHE, key + (".json" if kind == "json" else ".txt"))
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f) if kind == "json" else f.read()
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=40)
        except requests.RequestException as e:
            time.sleep(3 * (i + 1)); err = e; continue
        if "openalex" in url:
            rem = r.headers.get("x-ratelimit-remaining-usd")
            if rem is not None:
                json.dump({"remaining_usd": float(rem), "at": time.time()}, open(BUDGET_FILE, "w"))
        if r.status_code == 429:
            time.sleep(5 * (i + 1)); err = "429"; continue
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code} {url} {r.text[:200]}")
        data = r.json() if kind == "json" else r.text
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f) if kind == "json" else f.write(data)
        return data
    raise RuntimeError(f"请求失败 {url}: {err}")


def budget():
    try:
        b = json.load(open(BUDGET_FILE))
        return b["remaining_usd"]
    except Exception:
        return 0.1


def _abstract(inv):
    if not inv:
        return ""
    pos = {}
    for w, ps in inv.items():
        for p in ps:
            pos[p] = w
    return " ".join(pos[i] for i in sorted(pos))


def _norm_oa(w):
    loc = w.get("primary_location") or {}
    src = (loc.get("source") or {}).get("display_name") or ""
    ids = w.get("ids") or {}
    doi = (w.get("doi") or "").replace("https://doi.org/", "")
    arx = ""
    m = re.search(r"arxiv\.org/abs/([\w.\-/]+)", json.dumps(loc))
    if m:
        arx = m.group(1)
    if doi.lower().startswith("10.48550/arxiv."):
        arx = doi[len("10.48550/arxiv."):]
    oa = (w.get("open_access") or {}).get("oa_url") or ""
    au = [a["author"]["display_name"] for a in (w.get("authorships") or [])[:3] if a.get("author")]
    return {"key": w["id"].rsplit("/", 1)[-1], "title": w.get("title") or "", "year": w.get("publication_year"),
            "venue": src, "cites": w.get("cited_by_count", 0), "authors": au, "doi": doi, "arxiv": arx,
            "oa_url": oa, "abstract": _abstract(w.get("abstract_inverted_index"))[:1500], "src": "openalex"}


def oa_search(q, n):
    d = _get(f"{OA}/works", {"search": q, "per-page": n, "select": SEL})
    return [_norm_oa(w) for w in d.get("results", [])]


def arxiv_search(q, n):
    terms = " AND ".join(f"all:{t}" for t in q.split())
    txt = _get("https://export.arxiv.org/api/query", {"search_query": terms, "max_results": n}, kind="text")
    time.sleep(3)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in ET.fromstring(txt).findall("a:entry", ns):
        aid = e.find("a:id", ns).text.rsplit("/abs/", 1)[-1]
        aid = re.sub(r"v\d+$", "", aid)
        out.append({"key": "arXiv:" + aid, "title": " ".join(e.find("a:title", ns).text.split()),
                    "year": int(e.find("a:published", ns).text[:4]), "venue": "arXiv", "cites": None,
                    "authors": [a.find("a:name", ns).text for a in e.findall("a:author", ns)[:3]],
                    "doi": "", "arxiv": aid, "oa_url": f"https://arxiv.org/pdf/{aid}",
                    "abstract": " ".join(e.find("a:summary", ns).text.split())[:1500], "src": "arxiv"})
    return out


def crossref_search(q, n):
    d = _get("https://api.crossref.org/works", {"query.bibliographic": q, "rows": n,
             "select": "DOI,title,issued,is-referenced-by-count,container-title,abstract,author"})
    out = []
    for it in d["message"]["items"]:
        yr = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append({"key": it["DOI"], "title": (it.get("title") or [""])[0], "year": yr,
                    "venue": (it.get("container-title") or [""])[0], "cites": it.get("is-referenced-by-count"),
                    "authors": [f'{a.get("given","")} {a.get("family","")}'.strip() for a in (it.get("author") or [])[:3]],
                    "doi": it["DOI"], "arxiv": "", "oa_url": "",
                    "abstract": re.sub(r"<[^>]+>", "", it.get("abstract") or "")[:1500], "src": "crossref"})
    return out


def resolve(key):
    """任意 KEY -> OpenAlex 完整记录（单篇查询免费）。"""
    if re.match(r"^W\d+$", key):
        path = key
    elif key.lower().startswith("arxiv:"):
        path = "doi:10.48550/arXiv." + key.split(":", 1)[1]
    elif key.startswith("10."):
        path = "doi:" + key
    else:
        raise SystemExit(f"认不出的 KEY：{key}")
    return _get(f"{OA}/works/{path}", {"select": SEL + ",referenced_works"})


def _need(usd):
    if budget() < usd:
        raise SystemExit("OpenAlex 今天的额度用完了：引用链这一步改用网页搜索论文标题、看它的参考文献和「被引用」列表")


def oa_batch(ids):
    _need(0.0002)
    out = []
    for i in range(0, len(ids), 50):
        chunk = [x.rsplit("/", 1)[-1] for x in ids[i:i + 50]]
        d = _get(f"{OA}/works", {"filter": "openalex:" + "|".join(chunk), "per-page": 50, "select": SEL})
        out += [_norm_oa(w) for w in d.get("results", [])]
    return out


def refs(key):
    w = resolve(key)
    return oa_batch(w.get("referenced_works") or [])


def cites(key, n=100):
    _need(0.0002)
    wid = resolve(key)["id"].rsplit("/", 1)[-1]
    d = _get(f"{OA}/works", {"filter": f"cites:{wid}", "sort": "cited_by_count:desc", "per-page": min(n, 100), "select": SEL})
    return [_norm_oa(w) for w in d.get("results", [])]


def _tkey(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())[:80]


def load_pool(p):
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def add_pool(p, recs, tag):
    pool = load_pool(p)
    seen = set()
    for r in pool:
        seen |= {x for x in (r.get("doi", "").lower(), r.get("arxiv", ""), _tkey(r["title"]), r["key"]) if x}
    new = []
    for r in recs:
        ks = {x for x in (r.get("doi", "").lower(), r.get("arxiv", ""), _tkey(r["title"]), r["key"]) if x}
        if ks & seen or not r["title"]:
            continue
        seen |= ks
        r["found_by"] = tag
        new.append(r)
    with open(p, "a", encoding="utf-8") as f:
        for r in new:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return new


def brief(recs, full=False):
    for r in recs:
        extra = f' links={r["chain_links"]}' if "chain_links" in r else ""
        print(f'- [{r["key"]}] {r["title"]} ({r["year"]}, {r["venue"][:40]}, 被引 {r["cites"]}{extra})')
        if r.get("abstract"):
            print("    " + (r["abstract"] if full else r["abstract"][:350]))


def chain(seeds, pool_path, top):
    pool = load_pool(pool_path)
    have = {_tkey(r["title"]) for r in pool} | {r.get("doi", "").lower() for r in pool if r.get("doi")}
    seed_titles = set()
    cnt, rec = {}, {}
    for s in seeds:
        try:
            w = resolve(s)
        except Exception as e:
            print(f"跳过种子 {s}：{e}", file=sys.stderr); continue
        seed_titles.add(_tkey(w.get("title")))
        linked = refs(s) + cites(s, 100)
        for r in {x["key"]: x for x in linked}.values():
            cnt[r["key"]] = cnt.get(r["key"], 0) + 1
            rec[r["key"]] = r
    cand = [dict(rec[k], chain_links=c) for k, c in cnt.items()
            if _tkey(rec[k]["title"]) not in have | seed_titles and rec[k].get("doi", "").lower() not in have]
    cand.sort(key=lambda r: (r["chain_links"], r["cites"] or 0), reverse=True)
    return cand[:top]


def full(key):
    w = resolve(key) if not key.lower().startswith("arxiv:") else None
    urls = []
    if key.lower().startswith("arxiv:"):
        urls.append("https://arxiv.org/pdf/" + key.split(":", 1)[1])
    else:
        r = _norm_oa(w)
        if r["arxiv"]:
            urls.append("https://arxiv.org/pdf/" + r["arxiv"])
        if r["oa_url"]:
            urls.append(r["oa_url"])
    for u in urls:
        out = os.path.join(CACHE, "full_" + hashlib.sha1(u.encode()).hexdigest()[:16])
        if os.path.exists(out + ".txt"):
            return out + ".txt"
        try:
            r = requests.get(u, headers=UA, timeout=60)
        except requests.RequestException:
            continue
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            continue
        open(out + ".pdf", "wb").write(r.content)
        subprocess.run(["pdftotext", "-layout", out + ".pdf", out + ".txt"], check=False)
        if os.path.exists(out + ".txt"):
            return out + ".txt"
    raise SystemExit("没有拿到开放获取的 PDF：" + " ".join(urls or ["无链接"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--pool")
    ap.add_argument("--src", default="openalex")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--grep")
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    if a.cmd == "budget":
        print(f"OpenAlex 今天剩 {budget():.4f} 美元（检索一次 0.001）"); return
    if a.cmd == "full":
        print(full(a.args[0])); return
    if not a.pool:
        raise SystemExit("要给 --pool")
    if a.cmd == "search":
        q = " ".join(a.args)
        src = a.src
        if src == "openalex" and budget() < 0.005:
            print("OpenAlex 今天的额度快用完了，改用 arXiv", file=sys.stderr); src = "arxiv"
        recs = {"openalex": oa_search, "arxiv": arxiv_search, "crossref": crossref_search}[src](q, a.n)
        new = add_pool(a.pool, recs, f"search[{src}]:{q}")
        print(f"{src} 返回 {len(recs)} 篇，新进 pool {len(new)} 篇"); brief(new, a.full)
    elif a.cmd == "refs":
        new = add_pool(a.pool, refs(a.args[0]), f"refs:{a.args[0]}"); print(f"新进 {len(new)} 篇"); brief(new, a.full)
    elif a.cmd == "cites":
        new = add_pool(a.pool, cites(a.args[0], a.n), f"cites:{a.args[0]}"); print(f"新进 {len(new)} 篇"); brief(new, a.full)
    elif a.cmd == "chain":
        cand = chain(a.args, a.pool, a.top)
        new = add_pool(a.pool, cand, "chain:" + ",".join(a.args)); print(f"新进 {len(new)} 篇"); brief(new, a.full)
    elif a.cmd == "show":
        recs = load_pool(a.pool)
        if a.grep:
            recs = [r for r in recs if a.grep.lower() in (r["title"] + r.get("abstract", "")).lower()]
        print(f"共 {len(recs)} 篇"); brief(recs, a.full)
    else:
        raise SystemExit("未知命令 " + a.cmd)


if __name__ == "__main__":
    main()
