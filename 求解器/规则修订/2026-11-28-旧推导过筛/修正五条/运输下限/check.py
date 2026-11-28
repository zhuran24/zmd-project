"""独立复核「运输下限」修正版的数字。只读仓库。"""
import itertools, math
from fractions import Fraction as Fr
# 1 物料合计
fl=[34,18,34,34,18,Fr(63,2),21,21,11,11,11,17,17,9,Fr(11,2),6,Fr(11,2),Fr(3,5),Fr(11,20)]
tot=sum(fl); print('物料合计',float(tot),'ceil',math.ceil(tot))
# 2 W(d) 精确最小值：L 格边、正流量位置 S、每个 f in (0,1]、和为 d；相邻所选位置距离<=3 两端各记流量
def W(L,d):
    best=None
    for k in range(1,L+1):
        if d>k+1e-12: continue
        for S in itertools.combinations(range(L),k):
            c=[0]*k
            for i in range(k-1):
                if S[i+1]-S[i]<=3: c[i]+=1;c[i+1]+=1
            # 每格正流量下确界：系数小的先填满到1，其余取极小正量
            cs=sorted(c); rem=d; v=0
            for ci in cs:
                t=min(1,rem); v+=ci*t; rem-=t
            if rem>1e-12: continue
            best=v if best is None else min(best,v)
    return best
def check(L,cap,lin,name):
    ok=True
    for i in range(0,cap*40+1):
        d=i/40
        w=W(L,d) if d>0 else 0
        if w<lin(d)-1e-9: ok=False; print('违反',name,d,w,lin(d))
    print(name,'线性下界', 'OK' if ok else 'FAIL')
check(6,3,lambda d:2*d-4,'研磨 L6 cap3 2d-4')
check(3,2,lambda d:2*d-2,'塑形 L3 cap2 2d-2')
check(6,4,lambda d:4*d-10,'灌装 L6 cap4 4d-10')
print('封装 W(6,5)=',W(6,5))
Wsum=(2*Fr(189,2)-4*32)+(2*11-2*6)+(4*11-10*3)+3*W(6,5)
print('W合计',Wsum)
# 3 计数
print('180',math.ceil(Fr(619+91+8,4)),'200',Fr(619+99+82,4),'207',math.ceil(Fr(619+90+8+109,4)),
      '208',math.ceil(Fr(619+184+8+109-91,4)),'209',math.ceil(Fr(619+184+8+109-91+4,4)),
      '有箱N+u<=92时',math.ceil(Fr(619+184+8+109-92,4)),'加q',math.ceil(Fr(619+184+8+109-92+4,4)),
      '207账+q',math.ceil(Fr(826+4,4)))
# 200 账若源格方向与粉碎取货边间隙方向重合 m 个
for m in range(0,5): print(' 200 账重合',m,'->',math.ceil(Fr(800-m,4)))
