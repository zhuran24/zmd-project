#!/usr/bin/env python3
"""add.py POOL TAG KEY... : 单篇解析（OpenAlex 单篇查询免费）并加入 pool，打印 key/标题/摘要"""
import sys
sys.path.insert(0, "/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索")
import lit
pool, tag = sys.argv[1], sys.argv[2]
for k in sys.argv[3:]:
    try:
        r = lit._norm_oa(lit.resolve(k))
    except Exception as e:
        print(f"!! {k}: {e}"); continue
    lit.add_pool(pool, [r], tag)
    print(f'- [{r["key"]}] doi={r["doi"]} arxiv={r["arxiv"]} | {r["title"]} ({r["year"]}, {r["venue"][:40]}, 被引 {r["cites"]}) oa={bool(r["oa_url"])}')
    print("    " + r["abstract"][:900])
