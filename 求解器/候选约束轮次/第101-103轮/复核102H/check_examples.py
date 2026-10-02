"""Rule-realizable, finite belt examples for old polling claims."""
from pathlib import Path
from copy import deepcopy
import json

OUT=Path(__file__).resolve().parent

def run(k,mode):
    # Sandleaf crusher: output=3 at t=0; one plant travels four belts, arriving
    # at t=32, then a manufacture finishes at 40. Iron refinery: twenty batches.
    if k==3:
        output,raw,finish=3,0,None
        incoming=[0,None,None,None]
        initial_age=[0,None,None,None]
        last_step=49
    else:
        output,raw,finish=0,19,0
        incoming=[]; initial_age=[]
        last_step=159
    lanes=[[None]*22 for _ in range(3)]
    last=[None]*3; order=[0,1,2]
    # Independent countdown/integer age state.
    q,stock,work=output,raw,finish
    road=initial_age[:]
    other=[[None]*22 for _ in range(3)]
    unused=[0,1,2]; used=[]
    trace=[]
    for t in range(last_step+1):
        offline=(t==30) if k==3 else (t>0 and t%8==0)
        if t:
            if work is not None and work>0: work-=1
            for r in [road]+other:
                for p in range(len(r)):
                    if r[p] is not None: r[p]=min(8,r[p]+1)
        if offline:
            order=[2,1,0] if k==3 else [0,1,2]
            if mode=='clear':
                last=[None]*3; unused=list(order); used=[]
            else: unused=[j for j in order if j in unused]
        if finish is not None and finish<=t and output+k<=50:
            output+=k; finish=None
        if work==0 and q+k<=50: q+=k; work=None
        for r in [incoming]+lanes:
            if not r: continue
            if r is incoming and r[-1] is not None and t-r[-1]>=8 and raw<50:
                r[-1]=None; raw+=1
            for p in reversed(range(len(r)-1)):
                if r[p] is not None and t-r[p]>=8 and r[p+1] is None:
                    r[p+1]=t; r[p]=None
        if road and road[-1]==8 and stock<50:
            road[-1]=None; stock+=1
        for r in [road]+other:
            for p in reversed(range(len(r)-1)):
                if r[p]==8 and r[p+1] is None: r[p+1]=0; r[p]=None
        keys=lambda j:(0,order.index(j)) if last[j] is None else (1,last[j])
        picked=next((j for j in sorted(range(3),key=keys) if output and lanes[j][0] is None),None)
        picked2=next((j for j in unused+used if q and other[j][0] is None),None)
        assert picked==picked2
        if picked is not None:
            output-=1; lanes[picked][0]=t; last[picked]=t
            q-=1; other[picked][0]=0
            if picked in unused: unused.remove(picked)
            else: used.remove(picked)
            used.append(picked)
            trace.append([t,picked+1])
            if finish is not None and finish<=t and output+k<=50:
                output+=k; finish=None
            if work==0 and q+k<=50: q+=k; work=None
        if finish is None and raw:
            raw-=1; finish=t+8
        if work is None and stock:
            stock-=1; work=8
        assert [raw,output,None if finish is None else max(0,finish-t)]==[stock,q,work]
        assert [[None if v is None else min(8,t-v) for v in r] for r in [incoming]+lanes]==[road]+other
    return trace

def main():
    crusher={m:run(3,m) for m in ['retain','clear']}
    refinery={m:run(1,m) for m in ['retain','clear']}
    assert crusher['clear']==[[0,1],[1,2],[2,3],[40,3],[41,2],[42,1]]
    assert [sum(j==i for t,j in refinery['clear']) for i in [1,2,3]]==[20,0,0]
    # Geometry can be read directly: west-input/east-output machine and belts.
    out=dict(crusher=crusher,refinery=refinery,geometry={
        'machine':[10,10,3,3], 'power_pole':[8,14,2,2], 'core':[0,30,9,9],
        'crusher_input':[[x,11] for x in range(6,10)],
        'outputs':[[[x,y] for x in range(13,35)] for y in [10,11,12]],
        'construction':'Machine first; before reset heads in row order 10,11,12; after crusher reset 12,11,10; all other belts later.',
        'refinery_initial':'19 blue iron ore in input and one finished batch in cache, output empty.',
        'crusher_initial':'3 sandleaf powder in output; one sandleaf at first input belt with age 0; input/cache empty.'})
    # No overlap and correct port contacts, independently of the simulator.
    cells=[(x,y) for x in range(10,13) for y in range(10,13)]
    cells += [(x,y) for x in range(8,10) for y in range(14,16)]
    cells += [(x,y) for x in range(9) for y in range(30,39)]
    cells += [tuple(p) for p in out['geometry']['crusher_input']]
    cells += [tuple(p) for row in out['geometry']['outputs'] for p in row]
    assert len(cells)==len(set(cells)) and all(0<=x<70 and 0<=y<70 for x,y in cells)
    for y in [10,11,12]: assert (12,y) in cells and (13,y) in cells
    (OUT/'examples.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(crusher=crusher,refinery_clear_count=[20,0,0]),ensure_ascii=False))

if __name__=='__main__': main()
