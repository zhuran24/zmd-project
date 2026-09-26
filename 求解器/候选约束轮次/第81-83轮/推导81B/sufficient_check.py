#!/usr/bin/env python3
"""第81轮B：核对充分条件「纯料通道与单主料研磨机」。
取编码A列出的全部首件死锁 (状态, 首件种类集合H)。条件（一）意味着首件都被占时 H 含该配方全部原料；
条件（二）意味着研磨机的 H 与存货格里只出现一种主料。检查满足这两条的首件死锁一个都没有。"""
import json, os
from pathlib import Path
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
HERE = Path(__file__).resolve().parent
A = json.loads((HERE / 'dead_states_A.json').read_text())
PR = {'蓝铁粉末', '源石粉末', '荞花粉末'}
res = {}
for mach in ('研磨机', '封装机', '灌装机'):
    recs = A[mach]['recipes']
    bad = []
    for x in A[mach]['head_dead_list']:
        st, H = x.split('#')
        H = set(H.split(','))
        kinds = {p.split(':')[0] for p in st.split('|') if p != '空'}
        for r in recs:
            ings = set(r)
            if mach == '研磨机':
                P = (ings & PR).pop()
                if not ((H | kinds) - {'砂叶粉末'} <= {P}):
                    continue  # 条件（二）不成立
            if ings <= H:
                bad.append((x, sorted(ings)))
    res[mach] = dict(head_dead_checked=len(A[mach]['head_dead_list']), violations=len(bad), sample=bad[:5])
    print(mach, res[mach]['head_dead_checked'], 'violations', len(bad))
(HERE / 'sufficient_check.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
