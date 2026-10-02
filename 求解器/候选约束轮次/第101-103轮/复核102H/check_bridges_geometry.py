"""Fresh graph/path checks plus physical certificate for the stock witness."""
from itertools import product
from random import Random
from pathlib import Path
import json

OUT=Path(__file__).resolve().parent

def bridge_checks():
    rng=Random(281024)
    topologies=steps=reverse_rejected=0
    for length in range(1,9):
        for word in product('TX',repeat=length):
            groups=[]
            for i,letter in enumerate(word):
                if letter=='T' and i and word[i-1]=='T': groups[-1].append(i)
                else: groups.append([i])
            owner={cell:j for j,g in enumerate(groups) for cell in g}
            graph={j:set() for j in range(len(groups))}
            for j,g in enumerate(groups):
                last=g[-1]
                if last+1<length: graph[j].add(owner[last+1])
                else: graph[j].add(-1)  # Forward termination at a nontransport unit.
                if word[last]=='X' and last>0 and word[last-1]=='X': graph[j].add(owner[last-1])
            # Explicit non-returning walks. A dead end caused by 'seen' is not
            # an ordinary terminal component and yields no finite count.
            def paths(v,seen):
                if v==-1: return {0}
                values=set()
                for nxt in graph[v]-seen:
                    values.update(d+1 for d in paths(nxt,seen|{nxt}))
                return values
            levels={v:paths(v,{v}) for v in graph}
            independent={j:{len(groups)-j} for j in graph}
            assert levels==independent,(word,levels,independent)
            for clear in [False,True]:
                # A: real bridge reverse channel and previous UNIT identity.
                a=[None if rng.randrange(4)==0 else (-rng.randrange(9),i-1) for i in range(length)]
                # B: unidirectional cell recurrence, item ages only.
                b=[None if v is None else min(8,-v[0]) for v in a]
                for t in range(1,97):
                    b=[None if v is None else min(8,v+1) for v in b]
                    accepts=rng.randrange(3)!=0
                    inject=rng.randrange(3)!=0
                    a_deliver=b_deliver=False
                    judged=set()
                    for component in sorted(graph,key=lambda c:next(iter(levels[c]))):
                        if component in judged: continue
                        judged.add(component)
                        g=groups[component]
                        last=g[-1]
                        if a[last] is not None and t-a[last][0]>=8:
                            # Actual forward offer to an adjacent bridge triggers
                            # all non-splitter component upstreams of that UNIT.
                            if last+1<length and word[last+1]=='X':
                                target=last+1
                                upstream={component}
                                if target+1<length and word[target+1]=='X': upstream.add(owner[target+1])
                                assert upstream-{component} <= judged
                            if word[last]=='X' and last>0 and word[last-1]=='X':
                                assert a[last][1]==last-1
                                reverse_rejected+=1
                        for i in reversed(g):
                            if a[i] is None or t-a[i][0]<8: continue
                            if i==length-1:
                                if accepts: a[i]=None; a_deliver=True
                            elif a[i+1] is None:
                                a[i+1]=(t,i); a[i]=None
                    assert len(judged)==len(groups)
                    if b[-1]==8 and accepts: b[-1]=None; b_deliver=True
                    for i in reversed(range(length-1)):
                        if b[i]==8 and b[i+1] is None: b[i+1]=0; b[i]=None
                    if inject and a[0] is None: a[0]=(t,-1)
                    if inject and b[0] is None: b[0]=0
                    assert [None if x is None else min(8,t-x[0]) for x in a]==b
                    assert a_deliver==b_deliver
                    steps+=1
            topologies+=1
    return dict(topologies=topologies,reads=2,compared_steps=steps,reverse_attempts_rejected_by_unit=reverse_rejected)

def rectangle(x,y,w,h):
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}

def geometry():
    rects=dict(C=(10,10,5,5),A=(20,10,5,5),B=(20,2,5,5),K=(30,3,3,3),
               core=(0,30,9,9),pole0=(15,15,2,2),pole1=(25,7,2,2))
    paths={
      'CA':[(x,12) for x in range(15,20)],
      'AC':[(x,12) for x in range(25,28)]+[(27,y) for y in range(13,19)]
           +[(x,18) for x in range(26,7,-1)]+[(8,y) for y in range(17,11,-1)]+[(9,12)],
      'CB':[(x,10) for x in range(15,18)]+[(17,y) for y in range(9,3,-1)]+[(x,4) for x in range(18,20)],
      'BK':[(x,4) for x in range(25,30)],
      'K0':[(x,3) for x in range(33,43)],
      'K1':[(x,5) for x in range(33,43)]}
    endpoints={'CA':((14,12),(20,12)),'AC':((24,12),(10,12)),
               'CB':((14,10),(20,4)),'BK':((24,4),(30,4)),
               'K0':((32,3),(43,3)),'K1':((32,5),(43,5))}
    occupied={}
    for name,(x,y,w,h) in rects.items():
        for pos in rectangle(x,y,w,h):
            assert pos not in occupied and all(0<=z<70 for z in pos)
            occupied[pos]=name
    belts={}
    for road,points in paths.items():
        all_points=[endpoints[road][0]]+points+[endpoints[road][1]]
        for i,p in enumerate(points):
            assert p not in occupied and all(0<=z<70 for z in p)
            occupied[p]=f'{road}.{i}'
            before,after=all_points[i],all_points[i+2]
            assert sum(abs(x-y) for x,y in zip(p,before))==1
            assert sum(abs(x-y) for x,y in zip(p,after))==1
            belts[f'{road}.{i}']={'position':p,'input_neighbor':before,'output_neighbor':after}
    # All ordinary machine input sides west, output sides east.
    inputs=set(); outputs=set()
    for name in ['C','A','B','K']:
        x,y,w,h=rects[name]
        for j in range(y,y+h):
            inputs.add(((x-1,j),(x,j)))
            outputs.add(((x+w-1,j),(x+w,j)))
    actual=set()
    for name,b in belts.items():
        p=tuple(b['position']); q=tuple(b['output_neighbor'])
        other=occupied.get(q)
        if other in belts and tuple(belts[other]['input_neighbor'])==p:
            actual.add((name,other))
        elif (p,q) in inputs:
            actual.add((name,other))
        p0=tuple(b['input_neighbor'])
        if (p0,p) in outputs:
            actual.add((occupied[p0],name))
    expected=set()
    for road,points in paths.items():
        source=road[0] if road not in ['BK'] else 'B'
        if road.startswith('K'): source='K'
        expected.add((source,f'{road}.0'))
        expected.update((f'{road}.{i}',f'{road}.{i+1}') for i in range(len(points)-1))
        if not road.startswith('K'):
            expected.add((f'{road}.{len(points)-1}',road[1]))
    assert actual==expected,(actual-expected,expected-actual)
    # Second geometry encoding: integer cell bit sets and vector endpoint match.
    masks=[]
    for x,y,w,h in rects.values():
        masks.append(sum(1<<(70*j+i) for j in range(y,y+h) for i in range(x,x+w)))
    for points in paths.values(): masks.append(sum(1<<(70*y+x) for x,y in points))
    union=0
    for mask in masks:
        assert not union & mask
        union |= mask
    assert union.bit_count()==len(occupied)
    coverage={}
    for machine in ['C','A','B','K']:
        cells=rectangle(*rects[machine]); hits=[]
        for pole in ['pole0','pole1']:
            x,y,_,_=rects[pole]
            if cells & rectangle(x-5,y-5,12,12): hits.append(pole)
        assert hits
        coverage[machine]=hits
    # Channel time=max(unit build times), with all machines built before belts.
    firsts=['CB.0','AC.0','BK.0','K0.0','CA.0','K1.0']
    order=list(rects)+firsts+[b for b in belts if b not in firsts]
    build={name:i for i,name in enumerate(order)}
    channel_time={f'{u}>{v}':max(build[u],build[v]) for u,v in actual}
    assert channel_time['C>CB.0']<channel_time['C>CA.0']
    assert [min(t for channel,t in channel_time.items() if channel.startswith(n+'>')) for n in ['C','A','B','K']]==sorted(
            min(t for channel,t in channel_time.items() if channel.startswith(n+'>')) for n in ['C','A','B','K'])
    return dict(rectangles=rects,paths=paths,belts=belts,coverage=coverage,
                length={r:len(p) for r,p in paths.items()},occupied_cells=len(occupied),
                exact_channels=sorted(actual),build_order=order,channel_times=channel_time,
                note='Local 24-step witness. K has no output event during this witness; its dead-end belts suffice.')

def main():
    geo=geometry()
    (OUT/'geometry.json').write_text(json.dumps(geo,ensure_ascii=False,indent=2)+'\n')
    result=bridge_checks()
    (OUT/'bridges.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(bridges=result,geometry_lengths=geo['length'],occupied=geo['occupied_cells']),ensure_ascii=False))

if __name__=='__main__': main()
