from collections import Counter
from fractions import Fraction as F
from itertools import combinations, product
from math import ceil
from pathlib import Path
import re

repo = Path(__file__).resolve().parents[4]
old = Path(__file__).resolve().parents[1]
def recipe_rows(s):
    matches = re.findall(r'(\d+ [一-龥]+(?:\s*＋\s*\d+ [一-龥]+)? → \d+ [一-龥]+，\d+ tick)', s)
    return [x.replace(' ', '') for x in matches]
recipes = recipe_rows((repo / '《明日方舟：终末地》游戏规则.txt').read_text())
assert len(recipes) == 18 and recipes == recipe_rows(next(old.glob('旧规则*')).read_text())
# 由两种产品需求向上游回推，额外的蓝铁回炼取零以求下界。
battery, capsule = F(18,30), F(33,60)
parts, source_dust, bottles, flour = 10*battery,15*battery,10*capsule,10*capsule
steel = parts+2*bottles
ore, blue = 2*source_dust,2*steel
sand, buck = (source_dust+steel+flour)/3,flour
crush = ore+blue+sand+buck
plant, seed = 2*(sand+buck),sand+buck
rates = [crush,blue+steel,bottles,parts,plant,seed,source_dust+steel+flour,5*battery,5*capsule]
counts = list(map(ceil,rates))
groups = [sum(counts[:4]),sum(counts[4:6]),sum(counts[6:])]
weight = sum(x*w for x,w in zip(groups,[2,3,3]))
print('配方、在产台数、权',len(recipes),counts,groups,sum(counts),weight,[(54*p-weight)//25 for p in (10,11,12)])
flow = sum([ore, blue, blue, blue, ore, 3*sand,2*sand,2*sand,2*buck,2*buck,2*buck,steel,steel,source_dust,flour,parts,bottles,battery,capsule])
print('两矿、总物料',ore,blue,float(flow))

def ports(g):
    return [3*i+1+(3*i>=g) for i in range(23)]
gaps = range(0,70,3)
def cap(g,h):
    left = {(1,y) for y in ports(g)}
    bottom = {(x,1) for x in ports(h)}
    sources = left|bottom
    assert len(sources)==46
    # 非取货口的有端口单位在指定朝向必包含向里延伸的3×3子块。
    def can_fit(x,y,dx,dy):
        for off in range(3):
            cells = [(x+i*dx+(j-off)*dy,y+i*dy+(j-off)*dx)
                     for i in range(1,4) for j in range(3)]
            if all(1<=a<70 and 1<=b<70 and (a,b) not in sources for a,b in cells):
                return True
        return False
    return 46+sum(can_fit(x,y,dx,dy) for x,y in sources for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))
pairs = [(g,h) for g,h in product(gaps,repeat=2) if min(g,h)==0]
print('间距、最大连续无口段',set(b-a for g in gaps for a,b in zip(ports(g),ports(g)[1:])),max(b-a-1 for g in gaps for a,b in zip([-1]+ports(g),ports(g)+[70])))
print('排布与接口上界',Counter(cap(*pair) for pair in pairs),'双角缺口',cap(0,0))
ms = [(sum(y<=i<y+9 for i in ports(g)),1+(y<61)) for y,g in product(range(2,62),gaps)]
print('m,e',Counter(ms),'各割保留', [sum(m+3*d<=e*w for m,e in ms) for w,d in [(1,0),(2,0),(3,1)]])
overlaps={tuple(i for i in range(9) if a<=i<a+l) for a in range(-70,70) for l in range(6,71) if all(not a<=p<a+l for p in [1,4,7])}
print('取货边重叠',overlaps)
# 每边至少有2个源落在角的第1..5行/列，两个出口扛不住。
print('角内源数', min(sum(p<=5 for p in ports(g)+ports(h)) for g,h in pairs))
def side(L):
    return [min(sum(2 for a,b in zip(s,s[1:]) if b-a<=3) for s in combinations(range(L),k)) for k in range(L+1)]
def incidence(n,L,cap,total):
    costs=side(L)
    dp={0:0}
    for _ in range(n):
        nd={}
        for old,cost in dp.items():
            for k in range(cap+1):
                t=min(old+k,total)
                nd[t]=min(nd.get(t,10**8),cost+costs[k])
        dp=nd
    return dp[total]
print('端口边', [side(L)[1:] for L in [3,5,6]])
for n,L,k,t in [(68,3,3,95),(32,6,3,95),(6,3,2,11),(3,6,4,11),(3,6,5,15)]:
    vals=[incidence(i,L,k,t) for i in range(n,t+1)]
    print('关联及降幅',n,k,vals[:6],[(vals[0]-v)/8 for v in vals[:6]],(vals[0]-vals[-1])/8)
base=sum([95,51,32,6,6,32,32,3,3,52,68,51,95,11,6,32,16,15,11,2])
weighted = 2*F(189,2)-4*32+2*11-2*6+3*8+4*11-10*3
print('接口、权、运输分支',base,weighted,[ceil(t/4) for t in [base+99,base+99+82,base+98+weighted,base+184+8+weighted-91,base+184+8+weighted-91+4]],ceil(flow))
# 中心位于[-1,12]，占边机身限到6，中心至多5。去掉碰桩的中心后数格组。
for xmax,ymax in [(12,12),(5,12),(5,5)]:
    blocks={((x+1)//3,(y+1)//3) for x in range(-1,xmax+1) for y in range(-1,ymax+1)
            if not(4<=x<=7 and 4<=y<=7)}
    print('中心分组',xmax,ymax,len(blocks))
# 固定端口支持集，流量为0..1；线性式的极值可把有利端口先装满。
for L,cap,a,b,exact in [(6,3,2,-4,False),(3,2,2,-2,False),(6,5,0,8,True),(6,4,4,-10,False)]:
    slacks=[]
    for k in range(1,L+1):
        for s in combinations(range(L),k):
            weights=[int(i>0 and x-s[i-1]<=3)+int(i+1<k and s[i+1]-x<=3) for i,x in enumerate(s)]
            for total in range(cap if exact else 0,min(cap,k)+1):
                slacks.append(sum(sorted(weights)[:total])-(a*total+b))
    assert min(slacks)>=0
    print('逐边线性下界最小余量',L,cap,min(slacks))
