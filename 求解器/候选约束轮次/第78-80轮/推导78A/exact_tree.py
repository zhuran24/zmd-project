"""Optional solver-free binary tree certificate for the score-55 equality case.

Nonnegative rational multipliers certify score <=55. Equality fixes slack
variables and tight rows. The remaining 0/1 system is checked by exhaustive
binary branching plus exact integer bound propagation. No SAT/MIP library.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
import json,time,argparse,sys,hashlib
OUT=Path(__file__).resolve().parent
sys.setrecursionlimit(10000)

def prepare():
    data=json.loads((OUT/'final_general_model_a.json').read_text())
    dual=json.loads((OUT/'local_face55_v2_dual.json').read_text())
    assert dual['coefficients']==data['coefficients'] and not dual['wall']
    co=[F(0)]*len(data['objects']);rhs=F(0);tight=set()
    for i,n,d in dual['rows']:
        assert n>0 and d>0;v=F(n,d);tight.add(i);row=data['rows'][i];rhs+=v*row['rhs']
        for j,a in row['terms']:co[j]+=v*a
    assert not dual['bounds']
    assert rhs==55 and all(x>=y for x,y in zip(co,data['coefficients']))
    zero=sum(1<<i for i,(x,y) in enumerate(zip(co,data['coefficients'])) if x>y)
    constraints=[]
    for i,row in enumerate(data['rows']):
        groups=defaultdict(int)
        for j,a in row['terms']:
            if not(zero>>j&1):groups[a]|=1<<j
        if groups:constraints.append((tuple(groups.items()),row['rhs'] if i in tight else 0,row['rhs']))
        else:assert i not in tight or row['rhs']==0
    groups=defaultdict(int)
    for j,a in enumerate(data['coefficients']):
        if not(zero>>j&1):groups[a]|=1<<j
    constraints.append((tuple(groups.items()),55,55))
    # Deduplicate equal left sides; intersect their valid domains exactly.
    unique={}
    for gs,lo,hi in constraints:
        gs=tuple(sorted(gs));a,b=unique.get(gs,(0,10**9));unique[gs]=(max(a,lo),min(b,hi))
    constraints=[(gs,lo,hi) for gs,(lo,hi) in unique.items()]
    degree=defaultdict(int)
    for gs,lo,hi in constraints:
        if lo:
            for a,mask in gs:
                while mask:
                    bit=mask&-mask;degree[bit]+=1;mask-=bit
    return constraints,zero,degree,dict(dual_upper='55',tight_rows=len(tight),forced_zero=zero.bit_count(),constraints=len(constraints),variables=len(co))

def propagate(constraints,one,zero):
    while True:
        changed=False
        for ri,(groups,lo,hi) in enumerate(constraints):
            low=sum(a*(mask&one).bit_count() for a,mask in groups)
            high=sum(a*(mask&~zero).bit_count() for a,mask in groups)
            if low>hi or high<lo:return one,zero,ri
            for a,mask in groups:
                free=mask&~(one|zero)
                if not free:continue
                if low+a>hi:
                    zero|=free;changed=True
                elif high-a<lo:
                    one|=free;changed=True
            if one&zero:return one,zero,ri
        if not changed:return one,zero,None

def choose(constraints,one,zero,degree):
    best=None;bestcount=10**9
    for groups,lo,hi in constraints:
        low=sum(a*(mask&one).bit_count() for a,mask in groups)
        if low>=lo:continue
        free=0
        for a,mask in groups:free|=mask&~(one|zero)
        count=free.bit_count()
        if count<bestcount:bestcount=count;best=free
    if best is None:return None
    bits=[]
    while best:
        bit=best&-best;bits.append(bit);best-=bit
    return max(bits,key=lambda b:degree.get(b,0))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=int,default=120);ap.add_argument('--check',action='store_true');ap.add_argument('--probe-root',action='store_true');args=ap.parse_args()
    start=time.monotonic();constraints,initial_zero,degree,meta=prepare();print(meta,flush=True)
    visited=0
    if args.check:
        saved=json.loads((OUT/'general54_tree.json').read_text())
        nodes=saved['nodes']
        def check(k,one,zero):
            nonlocal visited;visited+=1
            one,zero,bad=propagate(constraints,one,zero);node=nodes[k]
            if node[0]=='leaf':assert bad is not None;return
            assert bad is None
            _,v,left,right=node;bit=1<<v;assert not(bit&(one|zero))
            check(left,one|bit,zero);check(right,one,zero|bit)
        check(saved['root'],0,initial_zero);assert visited==len(nodes)
        result=dict(status='VERIFIED',nodes=visited,seconds=time.monotonic()-start,**meta)
        (OUT/'general54_tree_check.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True);return
    nodes=[]
    def search(one,zero):
        nonlocal visited;visited+=1
        if time.monotonic()-start>args.seconds:raise TimeoutError()
        one,zero,bad=propagate(constraints,one,zero)
        if bad is not None:
            k=len(nodes);nodes.append(['leaf',bad]);return k
        bit=choose(constraints,one,zero,degree)
        if bit is None:raise ValueError('satisfying assignment in purported unsatisfiable system')
        a=search(one|bit,zero);b=search(one,zero|bit)
        k=len(nodes);nodes.append(['split',bit.bit_length()-1,a,b]);return k
    try:
        one,zero=0,initial_zero;chain=[]
        if args.probe_root:
            for iteration in range(3):
                one,zero,bad=propagate(constraints,one,zero)
                if bad is not None:break
                changed=False
                for bit in sorted(degree,key=lambda q:-degree[q]):
                    if bit&(one|zero):continue
                    if time.monotonic()-start>args.seconds:raise TimeoutError()
                    a,b,bad1=propagate(constraints,one|bit,zero)
                    if bad1 is not None:
                        leaf=len(nodes);nodes.append(['leaf',bad1]);chain.append((bit,1,leaf));zero|=bit;changed=True
                        one,zero,bad=propagate(constraints,one,zero)
                        if bad is not None:break
                        continue
                    a,b,bad0=propagate(constraints,one,zero|bit)
                    if bad0 is not None:
                        leaf=len(nodes);nodes.append(['leaf',bad0]);chain.append((bit,0,leaf));one|=bit;changed=True
                        one,zero,bad=propagate(constraints,one,zero)
                        if bad is not None:break
                print('probe',iteration,'forced',len(chain),'seconds',time.monotonic()-start,flush=True)
                if not changed or bad is not None:break
        root=search(one,zero)
        for bit,assumption,leaf in reversed(chain):
            k=len(nodes);nodes.append(['split',bit.bit_length()-1,leaf if assumption else root,root if assumption else leaf]);root=k
        result=dict(status='UNSAT',root=root,nodes=nodes,seconds=time.monotonic()-start,**meta)
        (OUT/'general54_tree.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
        print({**meta,'status':'UNSAT','nodes':len(nodes),'seconds':result['seconds']},flush=True)
    except TimeoutError:
        result=dict(status='UNKNOWN',visited=visited,seconds=time.monotonic()-start,**meta)
        (OUT/('general54_tree_probe_attempt.json' if args.probe_root else 'general54_tree_attempt.json')).write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
if __name__=='__main__':main()
