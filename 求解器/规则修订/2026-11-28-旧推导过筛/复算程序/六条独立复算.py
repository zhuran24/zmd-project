from collections import Counter
from fractions import Fraction as F
from itertools import combinations, product
from math import ceil
from pathlib import Path
import re

root = Path(__file__).resolve().parents[4]
scratch = Path(__file__).resolve().parents[1]
old = next(scratch.glob('旧规则*.txt')).read_text().split('\n配方\n')[1]
now = (root/'《明日方舟：终末地》游戏规则.txt').read_text().split('\n配方\n')[1]
pattern = r'(?:(\d+) ([^\s，；]+)\s*＋\s*)?(\d+) ([^\s，；]+) → (\d+) ([^\s，；]+)，(\d+) tick'
def recipes(s):
    out=[]
    for line in s.splitlines():
        line=line.strip()
        if not line: continue
        if '：' in line: machine, line=line.split('：')
        elif '→' not in line:
            machine=line
            continue
        for recipe in line.split('；'):
            n,a,m,b,q,c,t=re.fullmatch(pattern,recipe).groups()
            inputs={b:int(m)}
            if a: inputs[a]=int(n)
            out.append((machine,inputs,c,int(q),int(t)))
    return out
rs=recipes(now)
assert rs==recipes(old) and len(rs)==18
items=sorted({i for _,ins,c,_,_ in rs for i in [*ins,c]})
machines='粉碎机 精炼炉 研磨机 塑形机 配件机 种植机 采种机 封装机 灌装机'.split()
target={'高容谷地电池':F(3,5),'精选荞愈胶囊':F(11,20),'蓝铁矿':-34,'源矿':-18}
rows=[[F(q*(c==i)-ins.get(i,0)) for _,ins,c,q,_ in rs]+[F(target.get(i,0))] for i in items]
def solve(rows):
    A=[row.copy() for row in rows]
    piv=[]
    for col in range(len(rs)):
        k=len(piv)
        p=next((j for j in range(k,len(A)) if A[j][col]),None)
        if p is None: continue
        A[k],A[p]=A[p],A[k]
        A[k]=[x/A[k][col] for x in A[k]]
        for j in range(len(A)):
            if j!=k:
                v=A[j][col]
                A[j]=[a-v*b for a,b in zip(A[j],A[k])]
        piv.append(col)
    assert all(not any(row) for row in A[len(piv):])
    return piv,[row[-1] for row in A[:len(piv)]]
print('守恒秩',len(solve(rows)[0]))
for r in (0,1):
    pin=[F(ins=={'蓝铁粉末':1} and c=='蓝铁块') for _,ins,c,_,_ in rs]
    piv,rates=solve(rows+[pin+[F(r)]])
    assert len(piv)==18
    flow=Counter({'蓝铁矿':34,'源矿':18})
    batches,work,feed,outputs=[Counter() for _ in range(4)]
    for (m,ins,c,q,t),x in zip(rs,rates):
        flow[c]+=q*x
        batches[m]+=x
        work[m]+=t*x
        feed[m]+=sum(ins.values())*x
        outputs[m]+=q*x
    print('r',r,'物料', {i:str(v) for i,v in flow.items()},'总计',sum(flow.values()))
    print('批次',[str(batches[m]) for m in machines])
    if not r:
        count=[ceil(work[m]) for m in machines]
        print('台数',count,sum(count),'面积',sum(a*b for a,b in zip(count,[9,9,24,9,9,25,25,24,24])))
        for cs in (feed,outputs):
            v=[ceil(cs[m]) for m in machines]; print('通道',v,sum(v))
        print('入库',ceil(target['高容谷地电池']+target['精选荞愈胶囊']))
        print('取等机型',[m for m in machines if work[m]==ceil(work[m])])
        print('植物批次',[(m,i,str(x)) for (m,ins,_,_,_),x in zip(rs,rates) for i in ins if i in ('荞花','砂叶')])
for m in machines:
    inputs=[ins for k,ins,*_ in rs if k==m]
    kinds=set.union(*(set(ins) for ins in inputs))
    size=max(map(len,inputs))
    assert all(len(ins)==size for ins in inputs)
    good=anyhead=0
    for filled in range(1,size+1):
        for ks in combinations(kinds,filled):
            if m=='研磨机' and filled==2 and '砂叶粉末' not in ks: continue
            for counts in product(range(1,51),repeat=filled):
                s=dict(zip(ks,counts))
                if any(all(s.get(i,0)>=v for i,v in ins.items()) for ins in inputs): continue
                refused=sum(s.get(i)==50 or (filled==size and i not in s) for i in kinds)
                good+=2**refused-1
                anyhead+=2**(refused+(filled==size))-1
    print('首件分类',m,good,anyhead)
grinds=[ins for m,ins,*_ in rs if m=='研磨机']
all_feed=set().union(*grinds)
common=set.intersection(*map(set,grinds))
main=all_feed-common
slots=[None]+list(product(all_feed,range(1,51)))
states=arrivals=starts=0
for pair in product(slots, repeat=2):
    occupied=[v for v in pair if v is not None]
    inv=dict(occupied)
    if len(inv)!=len(occupied): continue
    states+=1
    if len(inv)==2 and set(inv)<=main:
        assert not any(all(inv.get(k,0)>=n for k,n in ins.items()) for ins in grinds)
        continue
    if len(inv)==1 and set(inv)<=main:
        arrivals+=len(main-inv.keys())
    for ins in grinds:
        if all(inv.get(k,0)>=n for k,n in ins.items()):
            after={k for k,n in inv.items() if n>ins.get(k,0)}
            starts+=int(len(after)==2 and after<=main)
print('研磨状态、收件进入、开批进入',states,arrivals,starts)
