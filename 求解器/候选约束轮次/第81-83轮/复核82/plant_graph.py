"""第二种植物编码：两个回路机器、两格专线、任意外送服务。

枚举闭合状态和全部外送/源端次序，缓存时钟可取分数 tick。
小容量全图仅核辅助机制，不替代容量 50 的解析证明。
"""
import os
os.sched_setaffinity(0,{1})
for v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[v]='1'
from pathlib import Path
from itertools import product
import heapq,json,argparse
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
OUT=Path(__file__).resolve().parent

def settle(s,q,m,allow_b,b_first):
    # inA,outA,cacheA,inC,outC,cacheC,CA,AC,B冷却；-1为空缓存/运输格。
    v=list(s)
    while True:
        before=v[:]
        for i,o,c,k in [(0,1,2,1),(3,4,5,2)]:
            if v[c]==0 and v[o]+k<=m: v[o]+=k; v[c]=-1
            if v[c]==-1 and v[i]>0: v[i]-=1; v[c]=q
        if v[6]==0 and v[0]<m: v[6]=-1; v[0]+=1
        if v[7]==0 and v[3]<m: v[7]=-1; v[3]+=1
        if v[7]==-1 and v[1]>0: v[1]-=1; v[7]=q
        for branch in ([1,0] if b_first else [0,1]):
            if branch==0 and v[6]==-1 and v[4]>0: v[4]-=1; v[6]=q
            if branch==1 and allow_b and v[8]==0 and v[4]>0: v[4]-=1; v[8]=q
        if before==v: return tuple(v)

def phi2(s): return 2*(s[0]+s[1]+int(s[2]>=0)+s[3]+int(s[5]>=0)+int(s[6]>=0)+int(s[7]>=0))+s[4]
def run(q,m):
    states=[]
    for stocks in product(range(m+1),repeat=4):
        ia,oa,ic,oc=stocks
        for ca,cc,la,lc,lb in product(range(-1,q+1),range(-1,q+1),range(-1,q+1),range(-1,q+1),range(q+1)):
            s=(ia,oa,ca,ic,oc,cc,la,lc,lb)
            if settle(s,q,m,False,False)==s: states.append(s)
    ids={s:i for i,s in enumerate(states)}; rev=[[] for _ in states]; edges=[]
    for i,s in enumerate(states):
        v=list(s)
        for j in [2,5,6,7,8]:
            if v[j]>0: v[j]-=1
        dest=set()
        for a,b in product([False,True],repeat=2):
            nxt=settle(v,q,m,a,b); assert nxt in ids; dest.add(ids[nxt])
        for j in dest: rev[j].append(i); edges.append((i,j))
    values=[phi2(s) for s in states]; minimum=values[:]
    heap=[(v,i) for i,v in enumerate(values)]; heapq.heapify(heap)
    while heap:
        val,j=heapq.heappop(heap)
        if minimum[j]!=val: continue
        for i in rev[j]:
            if minimum[i]>val: minimum[i]=val; heapq.heappush(heap,(val,i))
    lower_constant=4+7*m+2
    bad=[{'state':s,'initial_phi2':values[i],'minimum_phi2':minimum[i],'claimed_lower_phi2':min(values[i]-1,lower_constant)} for i,s in enumerate(states) if minimum[i]<min(values[i]-1,lower_constant)]
    # 检查一直留在 Φ>=S=4 的循环中的 C 空手。
    high={i:j for j,i in enumerate(i for i,v in enumerate(values) if v>=8)}
    ee=[(high[i],high[j]) for i,j in edges if i in high and j in high]
    g=csr_matrix((np.ones(len(ee)),([i for i,j in ee],[j for i,j in ee])),shape=(len(high),len(high)))
    count,lab=connected_components(g,directed=True,connection='strong')
    sizes=np.bincount(lab); selfloops={i for i,j in ee if i==j}
    cbad=[states[i] for i,j in high.items() if states[i][5]<0 and (sizes[lab[j]]>1 or j in selfloops)]
    result={'q':q,'capacity':m,'closed_states':len(states),'edges':len(edges),'lower_bound_violations':len(bad),'lower_bound_examples':bad[:3],'high_sccs':int(count),'C_empty_in_high_cycles':len(cbad),'C_examples':cbad[:3]}
    (OUT/f'plant_graph_m{m}_q{q}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--q',type=int,default=2);p.add_argument('--m',type=int,default=3);a=p.parse_args();run(a.q,a.m)
