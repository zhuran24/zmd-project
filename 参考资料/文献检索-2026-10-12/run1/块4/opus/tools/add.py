#!/usr/bin/env python3
"""按 DOI / W 号 / arXiv 号把单篇加入 pool（OpenAlex 单篇查询免费）。用法：add.py POOL TAG KEY...；或 add.py POOL TAG --title "标题"（用 OpenAlex 标题过滤，按列表计费 0.0001）"""
import sys, json
sys.path.insert(0, "/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索")
import lit
pool, tag = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
recs = []
if args and args[0] == "--title":
    for t in args[1:]:
        import re as _re
        tt = _re.sub(r"[^A-Za-z0-9 \-]", " ", t)
        try:
            d = lit._get(f"{lit.OA}/works", {"filter": "title.search:" + tt, "per-page": 3, "select": lit.SEL})
        except Exception as e:
            print("失败", t, e); continue
        rs = [lit._norm_oa(w) for w in d.get("results", [])]
        if rs:
            rs.sort(key=lambda r: -(r["cites"] or 0))
            recs.append(rs[0])
        else:
            print("没找到：", t)
else:
    for k in args:
        try:
            recs.append(lit._norm_oa(lit.resolve(k)))
        except Exception as e:
            print("失败", k, e)
new = lit.add_pool(pool, recs, tag)
print(f"新进 {len(new)} 篇")
for r in recs:
    print(f'- [{r["key"]}] {r["title"]} ({r["year"]}, {r["venue"][:40]}, 被引 {r["cites"]}) doi={r["doi"]} oa={bool(r["oa_url"])}')
