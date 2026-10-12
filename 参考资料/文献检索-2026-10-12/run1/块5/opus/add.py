import sys,os
sys.path.insert(0,'/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索')
import lit
P='/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/72c35b29-3230-408e-8d6b-52edea7f688f/scratchpad/文献检索/run1/块5/opus/pool.jsonl'
tag=sys.argv[1]
for k in sys.argv[2:]:
    try:
        r=lit._norm_oa(lit.resolve(k))
    except Exception as e:
        print('FAIL',k,e); continue
    new=lit.add_pool(P,[r],tag)
    print(('NEW ' if new else 'dup ')+f"[{r['key']}] {r['title']} ({r['year']}, {r['venue'][:40]}, cites {r['cites']}) doi={r['doi']}")
