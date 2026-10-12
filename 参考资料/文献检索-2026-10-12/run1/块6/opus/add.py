#!/usr/bin/env python3
"""把已知 KEY（DOI / arXiv:号 / W号）逐篇用 OpenAlex 单篇查询（免费）加进 pool。用法：add.py POOL TAG KEY..."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.."))
import lit
pool, tag, keys = sys.argv[1], sys.argv[2], sys.argv[3:]
for k in keys:
    try:
        w = lit.resolve(k)
    except Exception as e:
        print(f"!! {k}: {str(e)[:120]}"); continue
    r = lit._norm_oa(w)
    new = lit.add_pool(pool, [r], tag)
    print(("+ " if new else "= ") + f'[{r["key"]}] {r["title"]} ({r["year"]}, {r["venue"][:40]}, 被引 {r["cites"]}) doi={r["doi"]} arxiv={r["arxiv"]}')
    if r.get("abstract"): print("    " + r["abstract"][:400])
