#!/usr/bin/env python3
"""Independently reconstruct all physical ports, including unused splitter/merger sides.
Checks unintended channel formation, not just the intended adjacency list.
"""
from pathlib import Path
from collections import Counter
import json
D=Path(__file__).resolve().parent
E,W,N,S=(1,0),(-1,0),(0,-1),(0,1)
vecs=[E,W,N,S]
plus=lambda a,b:(a[0]+b[0],a[1]+b[1])
minus=lambda a,b:(a[0]-b[0],a[1]-b[1])
units={};owner={};inputs={};outputs={};expected=set();components={}
def put(name,cells,ins,outs,component):
    units[name]=cells;components[name]=component
    for c in cells:
        assert 0<=c[0]<70 and 0<=c[1]<70
        assert c not in owner,(name,owner.get(c),c)
        owner[c]=name
    for c,v in ins:assert c in cells;inputs[c,v]=name
    for c,v in outs:assert c in cells;outputs[c,v]=name

def belt(name,path,up,down):
    for i,c in enumerate(path):
        prev=path[i-1] if i else up
        nxt=path[i+1] if i+1<len(path) else down
        assert minus(prev,c) in vecs and minus(nxt,c) in vecs
        put(f'{name}{i}',[c],[(c,minus(prev,c))],[(c,minus(nxt,c))],name)
        expected.add((prev,c));expected.add((c,nxt))
    return path
pA=[(x,10) for x in range(1,5)]+[(4,y) for y in range(11,15)]+[(x,14) for x in range(5,9)]+[(8,y) for y in range(13,9,-1)]
pB=[(x,2) for x in range(1,12)]+[(11,y) for y in range(3,8)]
put('取货口甲',[(0,y) for y in range(9,12)],[],[((0,10),E)],'取货口甲')
put('取货口乙',[(0,y) for y in range(1,4)],[],[((0,2),E)],'取货口乙')
core=[(x,y) for x in range(13,22) for y in range(9,18)]
put('协议核心',core,[((x,y),v) for x,v in [(13,W),(21,E)] for y in range(10,17)],
    [((x,y),v) for y,v in [(9,N),(17,S)] for x in [14,17,20]],'协议核心')
belt('甲长带',pA,(0,10),(9,10));belt('乙长带',pB,(0,2),(11,8))
for name,c,inp,out in [('甲限流',(9,10),W,E),('乙限流',(11,8),N,S),('另一准入口',(11,9),N,S)]:
    put(name,[c],[(c,inp)],[(c,out)],name)
put('分流器',[(10,10)],[((10,10),W)],[((10,10),v) for v in [E,N,S]],'分流器')
for name,c in [('甲汇流',(11,10)),('乙汇流',(10,11))]:
    put(name,[c],[(c,v) for v in [W,N,S]],[(c,E)],name)
belt('甲回带',[(12,10)],(11,10),(13,10));belt('乙回带',[(11,11),(12,11)],(10,11),(13,11))
for a,b in [((9,10),(10,10)),((11,8),(11,9)),((11,9),(11,10)),((10,10),(11,10)),((10,10),(10,11))]:expected.add((a,b))
automatic=set()
for (c,v),u in outputs.items():
    nc=plus(c,v);op=(-v[0],-v[1])
    if (nc,op) in inputs:
        other=inputs[nc,op]
        assert other!=u
        assert u not in ['协议核心','取货口甲','取货口乙'] or other not in ['协议核心','取货口甲','取货口乙']
        automatic.add((c,nc))
assert automatic==expected,{'extra':automatic-expected,'missing':expected-automatic}
assert len(pA)==len(pB)==16
# Independent count from rectangular and unit areas (rather than the occupied-cell set).
assert len(owner)==9*9+2*3+2*16+6+3==128
blueprints=[]
for first in ['另一准入口','分流器']:
    built={'协议核心':-3,'取货口甲':-2,'取货口乙':-1,'甲限流':5,'乙限流':6}
    sequence=['甲汇流','另一准入口','分流器','乙汇流'] if first=='另一准入口' else ['甲汇流','分流器','乙汇流','另一准入口']
    built.update({u:i+1 for i,u in enumerate(sequence)})
    for name,start,length in [('甲回带',100,1),('乙回带',101,2),('甲长带',110,16),('乙长带',130,16)]:
        for i in range(length):built[name+str(i)]=start+i
    assert all(built[n]>=100 for n in units if components[n].endswith('带'))
    assert all(built[n]<100 for n in units if not components[n].endswith('带'))
    connection=[]
    for a,b in sorted(automatic):
        u,v=owner[a],owner[b]
        connection.append({'from_cell':a,'to_cell':b,'from':components[u],'to':components[v],
                           'formed':max(built[u],built[v])})
    ch={(e['from'],e['to']):e['formed'] for e in connection if e['from']!=e['to']}
    assert ch['分流器','甲汇流']<ch['分流器','乙汇流']
    assert (ch['另一准入口','甲汇流']<ch['分流器','甲汇流'])==(first=='另一准入口')
    blueprints.append({'first':first,'build_times':built,'channels':connection})
result={'status':'PASS','occupied_cells':len(owner),'physical_channels':len(automatic),'unintended_channels':0,
 'long_belt_lengths':[len(pA),len(pB)],'units':units,'blueprints':blueprints}
(D/'dense_geometry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','occupied_cells','physical_channels','unintended_channels','long_belt_lengths']},ensure_ascii=False))
