from pathlib import Path
from fractions import Fraction as Q
from math import ceil
from collections import Counter
import re

root = Path(__file__).resolve().parents[4]
base = Path(__file__).resolve().parent.parent
def recipes(path):
    body = path.read_text().split('\n配方\n')[1]
    return [(re.findall(r'(\d+)\s*([^\s＋]+)', left),
             int(q), name, int(duration))
            for left, q, name, duration in
            re.findall(r'(\d+ [^；：\n→]+?)\s*→\s*(\d+) (\S+?)，(\d+) tick', body)]

old = recipes(base / '旧规则-2026-09-26.txt')
cur = recipes(root / '《明日方舟：终末地》游戏规则.txt')
assert cur == old and len(cur) == 18
ores = ['蓝铁矿', '源矿']
plants = ['荞花','砂叶']
products = ['高容谷地电池','精选荞愈胶囊']
rates = dict(zip(products,[Q(18,30),Q(33,60)]))
# 按配方传播矿当量，遇到回炼配方时核对同一产物的两条路径。
ore_cost = {ores[0]:(1,0), ores[1]:(0,1)}
for p in plants:
    ore_cost[p] = ore_cost[p+'种子'] = (0,0)
while len(ore_cost) < 19:
    before = len(ore_cost)
    for ins,q,x,_ in cur:
        if all(y in ore_cost for _,y in ins):
            v = tuple(sum(int(n)*ore_cost[y][i] for n,y in ins)//q for i in (0,1))
            assert x not in ore_cost or v == ore_cost[x]
            ore_cost[x] = v
    assert len(ore_cost)>before
print('矿当量',ore_cost)
print('矿需求', [sum(rates[x]*ore_cost[x][i] for x in products) for i in (0,1)])
print('出口', 2*(70//3)+6)
print('成品机器',[ceil(rates[x]*t/q) for _,q,x,t in cur if x in rates])
# 从成品倒推粉碎量。蓝铁粉末的回炼支路在砂叶粉末账上系数为零。
need = Counter(rates)
for ins,q,x,t in reversed(cur):
    if x in plants or x.endswith('种子') or x in ('蓝铁块','蓝铁粉末'):
        continue
    batches = need[x]/Q(q)
    for n,y in ins:
        need[y] += batches*int(n)
# 粉碎配方先后不保证下游已遍历，按三种研磨的批量显式结算。
milling = [need[x]/Q(q) for ins,q,x,t in cur if any(y=='砂叶粉末' for _,y in ins)]
for p in plants:
    inputs,q,_,_ = next(row for row in cur if row[2]==p+'粉末')
    f = (need['荞花粉末'] if p=='荞花' else sum(milling))/q
    print(p,'采种、种植',f,2*f)
    a = next(row for row in cur if row[2]==p+'种子')
    z = next(row for row in cur if row[2]==p)
    print('种子、株增量', (a[1],-int(a[0][0][0])),(-int(z[0][0][0]),z[1]),(0,-int(inputs[0][0])))
# 在有界账目上，若一个权重和仅有同号变化，则严格变化的活动有限。
for stopped, no_return in [([products[0]],[ores[1]]),([products[1]],[]),(products,ores)]:
    acts = {}
    for ins,q,x,t in cur:
        d = Counter({x:q})
        for n,y in ins:
            d[y] -= int(n)
        acts['+'.join(y for n,y in ins)+'→'+x] = d
    for x in ores:
        acts[x+'取货'] = Counter({x:1})
        if x not in no_return:
            acts[x+'入库'] = Counter({x:-1})
    for x in products:
        if x not in stopped:
            acts[x+'拿取'] = Counter({x:-1})
    live = set(acts)
    accounts = [(x,) for x in ore_cost] + [(p,p+'种子') for p in plants] + [('蓝铁块','蓝铁粉末')]
    while True:
        prev = live.copy()
        for group in accounts:
            change = {k:sum(acts[k][x] for x in group) for k in live}
            if min(change.values(), default=0)>=0 or max(change.values(), default=0)<=0:
                live -= {k for k,v in change.items() if v}
        if live == prev: break
    finite = set(acts)-live
    print(stopped, sum('→' in k for k in finite), sorted(finite))
current = (root/'《明日方舟：终末地》游戏规则.txt').read_text()
core = re.search(r'协议核心：[^\n]+',current)[0]
box = re.search(r'协议储存箱：大小 (\d+)×(\d+).*?含 (\d+) 个有编号的物品格（上限 (\d+)）',current)
side, _, slots, capacity = map(int,box.groups())
print('仓库格上限', re.search(r'每格上限 (\d+)',core)[1], '箱容量',slots*capacity)
print('箱可吸收源路上界、中转净减上界',side,side-1)
for n in range(slots*capacity+1):
    for f in range(slots*capacity+2):
        assert (min(n,f)==0)==(n==0 or f==0)
