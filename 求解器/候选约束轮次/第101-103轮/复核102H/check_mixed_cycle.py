"""A finite, closed two-machine cycle showing reset-induced unfair flow."""
from pathlib import Path
import json

OUT=Path(__file__).resolve().parent

def main():
    # Refinery: blue iron powder -> block. Crusher: block -> powder.
    # Refinery has three equal-priority outputs; the second/third dead-end
    # branches remain empty because records clear before each production.
    paths={
        'R0':[(x,10) for x in range(13,20)],
        'R1':[(x,11) for x in range(13,19)],
        'R2':[(x,12) for x in range(13,19)],
        'KR':[(x,12) for x in range(23,26)]+[(25,y) for y in range(13,17)]
             +[(x,16) for x in range(24,7,-1)]+[(8,y) for y in range(15,9,-1)]+[(9,10)]}
    assert [len(paths[n]) for n in paths]==[7,6,6,31]
    occupied=[(x,y) for x in range(10,13) for y in range(10,13)]
    occupied += [(x,y) for x in range(20,23) for y in range(10,13)]
    occupied += [(x,y) for x in range(14,16) for y in range(13,15)]
    occupied += [(x,y) for x in range(9) for y in range(30,39)]
    occupied += [p for row in paths.values() for p in row]
    assert len(occupied)==len(set(occupied))
    assert all(0<=x<70 and 0<=y<70 for x,y in occupied)
    # Absolute-time encoding.
    a=[[1,0,None],[0,0,None]]
    ra=[[None]*len(p) for p in paths.values()]
    # Countdown/age encoding, with a different state shape and movement loop.
    raw=[1,0]; out=[0,0]; work=[None,None]
    rb=[[None]*len(p) for p in paths.values()]
    log=[]; snapshots={}
    for t in range(961):
        if t:
            work=[None if w is None else max(0,w-1) for w in work]
            rb=[[None if x is None else min(8,x+1) for x in r] for r in rb]
        for i in range(2):
            if a[i][2] is not None and a[i][2]<=t and a[i][1]<50:
                a[i][1]+=1; a[i][2]=None
            if work[i]==0 and out[i]<50:
                out[i]+=1; work[i]=None
        for r,dest in [(0,1),(1,None),(2,None),(3,0)]:
            for p in reversed(range(len(ra[r]))):
                v=ra[r][p]
                if v is None or t-v<8: continue
                if p==len(ra[r])-1:
                    if dest is not None and a[dest][0]<50:
                        a[dest][0]+=1; ra[r][p]=None
                elif ra[r][p+1] is None:
                    ra[r][p+1]=t; ra[r][p]=None
            if dest is not None and rb[r][-1]==8 and raw[dest]<50:
                raw[dest]+=1; rb[r][-1]=None
            for p in reversed(range(len(rb[r])-1)):
                if rb[r][p]==8 and rb[r][p+1] is None:
                    rb[r][p+1]=0; rb[r][p]=None
        for i,routes in [(0,[0,1,2]),(1,[3])]:
            # A reset at each step permits this fixed initial connection order.
            ja=next((r for r in routes if a[i][1] and ra[r][0] is None),None)
            jb=next((r for r in routes if out[i] and rb[r][0] is None),None)
            assert ja==jb
            if ja is not None:
                a[i][1]-=1; ra[ja][0]=t
                out[i]-=1; rb[jb][0]=0
                log.append([t,'R' if i==0 else 'K',ja])
        for i in range(2):
            if a[i][2] is None and a[i][0]: a[i][0]-=1; a[i][2]=t+8
            if work[i] is None and raw[i]: raw[i]-=1; work[i]=8
        ca=[[v[0],v[1],None if v[2] is None else max(0,v[2]-t)] for v in a]
        cb=[[raw[i],out[i],work[i]] for i in range(2)]
        ar=[[None if v is None else min(8,t-v) for v in r] for r in ra]
        assert ca==cb and ar==rb
        if t in [320,640,960]: snapshots[t]=[ca,ar]
    assert snapshots[320]==snapshots[640]==snapshots[960]
    assert 8*(len(paths['R0'])+len(paths['KR'])+2)==320
    refinery=[e for e in log if e[1]=='R']
    assert refinery==[[8,'R',0],[328,'R',0],[648,'R',0]]
    output=dict(period_steps=320,rate_per_tick='1/40',refinery_counts_per_period=[1,0,0],
                compared_steps=961,events=log,repeat_states=snapshots,paths=paths,
                machines={'refinery':[10,10,3,3],'crusher':[20,10,3,3]},
                pole=[14,13,2,2],core=[0,30,9,9],
                construction='Machines first, then R0.0, R1.0, R2.0, KR.0, and remaining belts; same order on every offline event.',
                initial='One blue iron powder in refinery input, both caches/output and all belts empty; obtain powder during debugging.',
                domain='Local closed cycle, not a layout meeting the full-factory delivery target.')
    (OUT/'mixed_cycle.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:output[k] for k in ['period_steps','rate_per_tick','refinery_counts_per_period','compared_steps']}))

if __name__=='__main__': main()
