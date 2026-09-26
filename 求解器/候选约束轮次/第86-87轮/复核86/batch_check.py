"""Exhaustive abstract unit-interval split recurrence, independently derived."""
import itertools
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
rows=[]
for k in range(2,7):
    visited_count=edges=worst=0
    for initial in range(51):
        start=(initial,(0,)*k)
        seen={start};todo=[start]
        while todo:
            r,diff=todo.pop()
            for batch in (0,1):
                total=r+batch*k
                taken=min(total,k)
                remaining=total-taken
                # Capacity is respected, including delayed admission of a completed batch.
                if remaining>50:continue
                for ports in itertools.combinations(range(k),taken):
                    x=list(diff)
                    for j in ports:x[j]+=1
                    base=min(x);x=tuple(a-base for a in x)
                    edges+=1;worst=max(worst,max(x))
                    assert max(x)<=1
                    if initial%k==0:assert max(x)==0
                    s=(remaining,x)
                    if s not in seen:seen.add(s);todo.append(s)
        visited_count+=len(seen)
    rows.append(dict(k=k,initial_counts=51,visited_states=visited_count,edges=edges,
                     largest_pair_difference=worst,multiple_start_violations=0))
(HERE/'batch_check.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows))
