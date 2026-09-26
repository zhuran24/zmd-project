"""单料输出库存：事件状态图与有理数计数两种核对。"""
import os
os.sched_setaffinity(0,{1})
from pathlib import Path
from itertools import combinations,permutations,product
from collections import deque
from fractions import Fraction
from math import floor,ceil
import json
OUT=Path(__file__).resolve().parent
rows=[]
for k in [1,2,3]:
    for scale in [1,2,3]:
        initial={(stock,delay,(0,)*k) for stock in range(50-k,51) for delay in range(scale+1)}
        seen=set(initial); queue=deque(initial); minimum=50; arcs=0
        while queue:
            stock,delay,cool=queue.popleft(); delay=max(0,delay-1); cool=tuple(max(0,c-1) for c in cool)
            avail=[i for i,c in enumerate(cool) if c==0]
            for bits in product([False,True],repeat=len(avail)):
                selected=[i for i,b in zip(avail,bits) if b]
                # 唯一完成批次可在任一取货之前或之后判定；未能入格会重试。
                for order in permutations(selected+[-1]):
                    q=stock; d=delay; cd=list(cool)
                    def flush(q,d): return (q+k,scale) if d==0 and q+k<=50 else (q,d)
                    for action in order:
                        if action==-1:q,d=flush(q,d)
                        else:
                            assert q>0
                            q-=1;cd[action]=scale;minimum=min(minimum,q)
                    q,d=flush(q,d)
                    minimum=min(minimum,q); nxt=(q,d,tuple(cd));arcs+=1
                    if nxt not in seen:seen.add(nxt);queue.append(nxt)
        assert minimum>=50-3*k
        # 第二种算法：低库存区间的完成次数/最大取货次数。
        analytic_min=50
        for numerator in range(0,121):
            T=Fraction(numerator,12)
            expression=50-k+k*max(0,ceil(T)-1)-k*(floor(T)+1)
            analytic_min=min(analytic_min,expression)
        assert analytic_min==50-3*k
        rows.append({'batch':k,'time_division':scale,'states':len(seen),'transitions_including_orders':arcs,'minimum_observed':minimum,'analytic_bound':analytic_min})
(OUT/'buffer_checks.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(rows))
