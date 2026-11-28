# 独立复核：用 1/12 网格穷举端口流量，求各内部点三列局部最大值
from fractions import Fraction as F
from itertools import product
g=[F(k,12) for k in range(13)]
def cls(x): return 0 if x==0 else (2 if x==1 else 1)
def run(nin,nout,cap):
    best=[None]*3
    for ins in product(g,repeat=nin):
        s=sum(ins)
        if s==0 or s>cap: continue
        for outs in product(g,repeat=nout):
            if sum(outs)!=s: continue
            ci=[cls(x) for x in ins]; co=[cls(x) for x in outs]
            v=((sum(c>0 for c in co)-sum(c>0 for c in ci)),
               (ci.count(2)-co.count(2)),
               (co.count(1)-ci.count(1)))
            best=[v[i] if best[i] is None else max(best[i],v[i]) for i in range(3)]
    return best
print("直通格",run(1,1,1)); print("汇流器",run(3,1,1)); print("分流器",run(1,3,1)); print("箱",run(3,3,3))
print("蓝铁矿",F(18,30)*20+F(33,60)*40,"源矿",F(18,30)*30,"出口",70//3*2+6)
