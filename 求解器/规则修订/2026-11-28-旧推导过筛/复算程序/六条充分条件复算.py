from fractions import Fraction as F
from itertools import product
from math import gcd
from pathlib import Path
import re

rules = (Path(__file__).resolve().parents[4] / '《明日方舟：终末地》游戏规则.txt').read_text()
capacity = int(re.search(r'存货/取货物品格：制造单位的物品格（上限 (\d+)）', rules)[1])
for machine, routes in [('研磨机', 6), ('封装机', 5), ('灌装机', 6)]:
    row = re.search(r'^  '+machine+r'：(.+)$', rules, re.M)[1]
    for recipe in row.split('；'):
        a,b = map(int,re.findall(r'\d+',recipe.split('→')[0]))
        z = capacity*(b-a)
        inventories = list(product(range(capacity+1), repeat=2))
        low = max(b*x-a*y for x,y in inventories if x<a and y==capacity)
        high = min(b*x-a*y for x,y in inventories if y<b and x==capacity)
        margin = min(high-z,z-low)
        per = a*b//gcd(a,b)
        dead = [(x,y) for x,y in inventories if x==capacity and y==capacity and (x<a or y<b)]
        for x,y in inventories:
            restx,resty = x,y
            while restx>=a and resty>=b:
                restx-=a
                resty-=b
            n=min(x//a,y//b)
            assert (restx,resty)==(x-a*n,y-b*n)
        print(machine,a,b,z,low,high,margin,per,2*routes*per,(margin-1)//(2*per),len(inventories),len(dead))
print('箱半开、闭区间',3*len(range(0,40,8)),3*len(range(0,41,8)))
print('误料',sum(i<capacity for i in range(51)), '件收下')
print('目标', F(18,30),F(33,60))
# 在每个八步窗口内，一批首次可送的步号 v 与各路首次腾空步号任取。
# 从有效库存 0 起逐步出货；一条路在同一窗口中至多领一次。
for k in (2,3):
    count=0
    for v in range(8):
        for ready in product(range(8),repeat=k):
            stock=0
            taken=set()
            for step in range(8):
                if step==v:
                    stock+=k
                for j,r in enumerate(ready):
                    if r<=step and j not in taken and stock:
                        stock-=1
                        taken.add(j)
            assert len(taken)==k and stock==0
            count+=1
    print('全就绪单批窗口',k,count)
