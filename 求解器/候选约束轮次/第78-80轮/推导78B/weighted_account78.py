"""Exact port-support enumeration and independent continuous capacity LPs.

All numeric results are derived using fractions, integer masks, or LPs whose
primal/dual are checked again with exact fractions. No kernel tests.
"""
from fractions import Fraction as Q
from itertools import combinations,product
from pathlib import Path
import os,json
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
OUT=Path(__file__).resolve().parent

def coefficients(length,mask):
    p=[i for i in range(length) if mask>>i&1];a={i:0 for i in p}
    for u,v in zip(p,p[1:]):
        if v-u<=3:a[u]+=1;a[v]+=1
    return p,list(a.values())

def profile(length,d):
    # On a fixed support, assigning rate to the lowest coefficient first
    # is the exact continuous linear minimum, not rate sampling.
    best=None;winning=[]
    for mask in range(1,1<<length):
        p,a=coefficients(length,mask)
        if len(p)<d:continue
        remaining=d;v=Q(0)
        for c in sorted(a):
            f=min(Q(1),remaining);v+=f*c;remaining-=f
        if best is None or v<best:best=v;winning=[mask]
        elif v==best:winning.append(mask)
    return best,winning

def dp(n,total,lo,hi,length):
    # Every per-support linear problem has integer endpoints. The single
    # total-rate equation and half-integral total therefore have a vertex
    # on this half grid; enumerating it is exact for the union of supports.
    tab={0:Q(0)}
    choices={k:profile(length,Q(k,2))[0] for k in range(lo,hi+1)}
    for _ in range(n):
        nxt={}
        for amount,val in tab.items():
            for k,cost in choices.items():
                if amount+k>total:continue
                v=val+cost
                if amount+k not in nxt or v<nxt[amount+k]:nxt[amount+k]=v
        tab=nxt
    return tab[total]

def main():
    support=[];old_bound_vertices=0
    for length in (3,6):
        for mask in range(1,1<<length):
            p,a=coefficients(length,mask)
            if length==6 and len(p)>=3:assert a.count(0)<=1
            if length==6 and len(p)>=4:assert a.count(0)==0 and sum(c==1 for c in a)==2
            if length==3 and len(p)>=2:assert min(a)>=1
            # Linear inequalities are checked at all cube vertices cut by
            # integer total-rate bounds; those polytopes are integral.
            for flow in product((0,1),repeat=len(a)):
                d=sum(flow);w=sum(f*c for f,c in zip(flow,a));old_bound_vertices+=1
                if length==6 and d<=3:assert w>=2*d-4
                if length==6 and d<=4:assert w>=4*d-10
                if length==6 and d==5:assert w>=8
                if length==3 and d<=2:assert w>=2*d-2
            support.append(dict(length=length,positions=[x+1 for x in p],coefficients=a))
    data={
      '研磨机':(32,189,3,6,6,Q(61)),
      '塑形机':(6,22,2,4,3,Q(10)),
      '封装机':(3,30,10,10,6,Q(24)),
      '灌装机':(3,22,6,8,6,Q(14))}
    computed={k:dp(*args[:5]) for k,args in data.items()}
    assert computed=={'研磨机':Q(123,2),'塑形机':Q(10),'封装机':Q(24),'灌装机':Q(14)}
    # Independent encoding: explicit continuous flow variables per machine
    # and a partition into low-support and high-support regimes. Here the
    # number in the low regime can only be 0 or 1, by total missing rate.
    from scipy.optimize import linprog
    independent={};details=[]
    for name,n,total,lo,hi,threshold,slope,intercept,lowW in [
      ('研磨机',32,Q(189,2),Q(3,2),Q(3),Q(2),Q(1),Q(-1),Q(0)),
      ('塑形机',6,Q(11),Q(1),Q(2),Q(1),Q(1),Q(0),Q(0)),
      ('灌装机',3,Q(11),Q(3),Q(4),Q(3),Q(2),Q(-2),Q(2))]:
        vals=[]
        for k in (0,1):
            bounds=[(float(lo),float(threshold))]*k+[(float(threshold),float(hi))]*(n-k)
            cost=[0.]*k+[float(slope)]*(n-k)
            r=linprog(cost,A_eq=[[1.]*n],b_eq=[float(total)],bounds=bounds,method='highs',options={'threads':1})
            assert r.success
            x=[Q(float(v)).limit_denominator(1000) for v in r.x]
            assert sum(x)==total
            lower=[Q(v[0]) for v in bounds];upper=[Q(v[1]) for v in bounds]
            assert all(l<=v<=h for l,v,h in zip(lower,x,upper))
            y=Q(float(r.eqlin.marginals[0])).limit_denominator(1000)
            dl=[Q(float(v)).limit_denominator(1000) for v in r.lower.marginals]
            du=[Q(float(v)).limit_denominator(1000) for v in r.upper.marginals]
            cq=list(map(Q,cost))
            assert all(y+l+u==c and l>=0 and u<=0 for c,l,u in zip(cq,dl,du))
            primal=sum(c*v for c,v in zip(cq,x));dual=y*total+sum(l*b for l,b in zip(dl,lower))+sum(u*b for u,b in zip(du,upper))
            assert primal==dual
            value=primal+(n-k)*intercept+k*lowW;vals.append(value)
            details.append(dict(machine=name,low_regime_count=k,minimum=str(value),rates=list(map(str,x)),dual_y=str(y),dual_lower=list(map(str,dl)),dual_upper=list(map(str,du))))
        independent[name]=min(vals)
    independent['封装机']=Q(24)
    assert independent==computed
    base=sum(v[-1] for v in data.values());exact=sum(computed.values())
    result=dict(port_supports=support,old_linear_bound_vertices_checked=old_bound_vertices,dp_minima={k:str(v) for k,v in computed.items()},continuous_LP_certificates=details,
      old_total=str(base),new_total=str(exact),extra=str(exact-base),two_independent_encodings_agree=True,
      exact_area={'manufacturing':131*9+48*25+38*24,'transport_plus_empty':70*70-1113-(131*9+48*25+38*24)-81-46*3-10*4},
      branch_slack=[dict(S=s,XY=s-158,delta=187-s,after_minimum_weight=str(Q(187-s)-Q(1,2))) for s in (185,186,187)])
    (OUT/'weighted_account.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ('port_supports','continuous_LP_certificates')},flush=True)
if __name__=='__main__':main()
