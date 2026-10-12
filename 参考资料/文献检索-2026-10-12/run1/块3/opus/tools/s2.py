#!/usr/bin/env python3
"""s2.py ID... : 从 Semantic Scholar 取摘要（ID 形如 DOI:10.x/yy 或 ARXIV:2401.1 或 search:标题）"""
import sys, json, time, requests, urllib.parse
for k in sys.argv[1:]:
    if k.startswith("search:"):
        u = "https://api.semanticscholar.org/graph/v1/paper/search?limit=3&fields=title,year,abstract,externalIds,citationCount&query=" + urllib.parse.quote(k[7:])
    else:
        u = "https://api.semanticscholar.org/graph/v1/paper/" + k + "?fields=title,year,abstract,externalIds,citationCount,tldr"
    for i in range(4):
        r = requests.get(u, timeout=30)
        if r.status_code == 429: time.sleep(4*(i+1)); continue
        break
    if r.status_code != 200:
        print("!!", k, r.status_code); continue
    d = r.json()
    items = d.get("data", [d]) if k.startswith("search:") else [d]
    for it in items:
        print(f'## {it.get("title")} ({it.get("year")}) ids={it.get("externalIds")} cites={it.get("citationCount")}')
        print("   ", (it.get("abstract") or (it.get("tldr") or {}).get("text") or "")[:1200])
    time.sleep(1.2)
