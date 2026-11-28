from fractions import Fraction as Q
from itertools import product
from math import ceil
from pathlib import Path
import re

root = Path(__file__).resolve().parents[4]
rules = (root / "《明日方舟：终末地》游戏规则.txt").read_text()
old = next(Path(__file__).resolve().parents[1].glob("旧规则*.txt")).read_text()
def recipes(s):
    return [re.sub(r"\s+", "", r) for r in re.findall(r"\d+ [^：\n；]+?→[^\n；]+?tick",s) if "→" in r]
assert recipes(old)==recipes(rules) and len(recipes(rules))==18
bat,cap = Q(18,30),Q(33,60)
steel = 10*bat+2*10*cap
grind = steel+15*bat+10*cap
flowers,leaves = 2*10*cap/2,grind/3
harvest = flowers+leaves
plants = 2*harvest
transport = ceil((2*plants+4)/2)
print("粉碎植株、种植、占地",flowers,leaves,plants,(ceil(plants)+ceil(harvest))*25+ceil(harvest)*9+transport)
def ports(gap):
    cells=[i for i in range(70) if i!=gap]
    return set(cells[1::3])
hmax=max(h for gap in range(0,70,3) for b in range(2,65) for h in range(6,71-b)
         if len(ports(gap)&set(range(b,b+h)))<=6)
print("矿带高度",hmax)
print("接口",sum([95,51,32,6,6,32,32,3,3])+52,sum([68,51,95,11,6,32,16,15,11])+2)
mx=0
for u,v in product(range(0,70,3),repeat=2):
    if u and v: continue
    ore={(1,j) for j in ports(u)}|{(j,1) for j in ports(v)}
    count=46
    for x,y in ore:
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            for offset in range(-2,1):
                block={(x+k*dx+(offset+j)*dy,y+k*dy+(offset+j)*dx)
                       for j in range(3) for k in range(1,4)}
                if all(1<=a<70 and 1<=b<70 for a,b in block) and not block&ore:
                    count+=1
                    break
    mx=max(mx,count)
print("矿石接口上界、常数",mx,619-mx+3*46)
print("各类跨线亏额下界",[(h-k) for h,k in [(3,1),(3,1),(4,2),(3,3),(2,0),(3,0),(5,0),(4,0),(9,0)]])
def fleet(length,cap,total,start,end):
    # 流量以半件为一单位，权重亦同。线性分段的端点在整数。
    local=[999]*(2*cap+1)
    for vec in product(range(3),repeat=length):
        d=sum(vec)
        if d>=len(local): continue
        pos=[i for i,r in enumerate(vec) if r]
        w=sum(vec[i]+vec[j] for i,j in zip(pos,pos[1:]) if j-i<=3)
        local[d]=min(local[d],w)
    dp=[0]+[9999]*int(total*2)
    result=[]
    for n in range(1,end+1):
        dp=[min(x+dp[t-k] for k,x in enumerate(local) if k<=t) for t in range(len(dp))]
        if n>=start: result.append(Q(dp[-1],2))
    return result
tables=[fleet(*p) for p in [(6,3,3*grind,32,48),(3,2,11,6,11),(6,5,15,3,8),(6,4,11,3,6)]]
for seq,area in zip(tables,[24,9,24,24]):
    print("权重、逐台净增下界",list(map(str,seq)),min(4*area+b-a for a,b in zip(seq,seq[1:])))
area=9*(68+51+6+6)+25*(32+16)+24*(32+3+3)
base=70**2-area-9**2-46*3
i=2*69-1
print("占地、余地、常数",area,base,619+90+8,717+i-46-3+4,4*base-809,829+i-46-3+4)
print("下限配置权重",sum(t[0] for t in tables))
five={"源矿","源石粉末","蓝铁矿","蓝铁块","蓝铁粉末"}
def weight(terms):
    return sum(int(n) for n,kind in re.findall(r"(\d+)([^\d＋]+)",terms) if kind in five)
loss=[]
for row in recipes(rules):
    lhs,rhs=row.split("，")[0].split("→")
    loss.append(weight(lhs)-weight(rhs))
print("18配方五物净减少（现行表顺序）",loss)
assert loss==[0]*7+[2,2,0]+[0]*8
print("方形穿越最小势增量",min(q-abs(i-j) for q in (3,5) for i in range(q) for j in range(q)))
print("窄走廊离带面积分界",max((70-2)*9,(70-3)*15))
