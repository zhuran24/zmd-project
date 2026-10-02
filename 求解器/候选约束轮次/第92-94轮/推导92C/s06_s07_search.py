import json, random
from pathlib import Path
random.seed(920607)
base=Path(__file__).parent
found=None
for trial in range(30000):
    k=random.choice([2,3]); q=random.randrange(0,6); due=random.randrange(8)
    entered=[None]*k; release=[None]*k; last=[-100+i for i in range(k)]
    # All first cells initially empty; subsequent downstream delays are >=8 steps.
    rows=[]; bins=[]
    for t in range(160):
        flushed=0
        if t>=due and q+k<=50:
            q+=k; flushed=k; due=t+random.choice([8,8,8,9,12,16,24])
        for i in range(k):
            if release[i] is not None and t>=release[i]: entered[i]=release[i]=None
        ready=[x is None for x in entered]
        sent=None
        for i in sorted(range(k),key=lambda i:last[i]):
            if q and ready[i]:
                sent=i;q-=1;last[i]=t;entered[i]=t;release[i]=t+random.choice([8,8,8,9,12,15]);break
        rows.append(dict(t=t,q=q,ready=ready,sent=sent,flushed=flushed,release=release.copy()))
        if t%8==7:
            rr=rows[-8:]
            bins.append(([any(r['ready'][i] for r in rr) for i in range(k)], [sum(r['sent']==i for r in rr) for i in range(k)]))
    for a in range(len(bins)):
        counts=[0]*k
        for b in range(a,len(bins)):
            if not all(bins[b][0]):break
            counts=[x+y for x,y in zip(counts,bins[b][1])]
            if max(counts)-min(counts)>1:
                found=dict(trial=trial,k=k,first_bin=a,last_bin=b,counts=counts,rows=rows[:(b+1)*8]);break
        if found:break
    if found:break
print(json.dumps(found,ensure_ascii=False))
(base/'s06_s07_search.json').write_text(json.dumps(found,ensure_ascii=False,indent=2))
