from fractions import Fraction as Q
from math import ceil
from pathlib import Path
from collections import Counter
import re
rule = Path('《明日方舟：终末地》游戏规则.txt').read_text().split('\n配方\n')[1]
recipes = {}
for line in rule.strip().splitlines():
    machine, parts = line.strip().split('：')
    for part in parts.split('；'):
        ingredients, result = part.split(' → ')
        out, ticks = result.split('，')
        n, item = out.split()
        if item == '蓝铁块' and '粉末' in ingredients:
            continue
        recipes[item] = machine, int(n), int(ticks.split()[0]), [s.split() for s in ingredients.split('＋')]
work, flows = Counter(), Counter()
def demand(item, rate):
    flows[item] += rate
    if item not in recipes:
        return
    machine, n, ticks, ins = recipes[item]
    if item in ('荞花','砂叶'):
        # 种植量的一半返回采种。额外一份产量供采种，所产种子全部种回。
        rate *= 2
        flows[item] += rate/2
        flows[item+'种子'] += rate
        work['采种机'] += rate/2
        work[machine] += rate
        return
    batches = rate/n
    work[machine] += batches*ticks
    for count, inp in ins:
        demand(inp, batches*int(count))
demand('高容谷地电池',Q(18,30))
demand('精选荞愈胶囊',Q(11,20))
counts = {m:ceil(w) for m,w in work.items()}
s = sum(counts[m] for m in ('粉碎机','精炼炉','配件机','塑形机'))
mid = counts['采种机'] + counts['种植机']
large = sum(counts.values())-s-mid
area=9*s+25*mid+24*large
base=area+81+2*(70//3)*3
print(counts, sum(flows.values()), sum(counts.values()),area,2*s+3*(mid+large))
print('occupancy',base+40+ceil(Q(829,4)),base+40+ceil(sum(flows.values())))
products={w*h for w in range(6,69) for h in range(w,69)}
for limit in (1044,1090,1109,1110,1112):
    val=max(v for v in products if v<=limit)
    print(limit,val,[(w,val//w) for w in range(6,69) if val%w==0 and w<=val//w<=68])
for added in (0,34):
    residual=4900-base-added
    print(residual,4*residual-921,(4*residual-921-140)/4)
print(4900-base-208, [23-c for c in (13,14,14,17,18,19,22)],230-217)
for a in (2,3):
    heights={False:[],True:[]}
    for k in range(24):
        ports = [3*i+1+int(i>=k) for i in range(23)]
        for b in range(2,65):
            for h in range(6,71-b):
                top=b+h==70
                if sum(b<=y<b+h for y in ports)<=(2-top)*(a-1):
                    heights[top].append(h)
    print(a,[max(v,default=0) for v in heights.values()])
print(68*9,67*15,70-4)
for p in range(10,16):
    print(p,[j for j in range(p+1) if 54*p-25*j>=520 and 4*1110+16*p-2*j<=4639 and not(p==12 and j==0)])
print('无桥无箱、有箱', [4900-base-40-t-e for t,e in [(ceil(sum(flows.values())+8),0),(ceil(sum(flows.values())),9)]])
print('四向账', (256+4+52)+(305+2), 619+184+8+109-91, 829+88+4)
print('方向预算和边界余量',4*(4900-base)-809, 4639-4*1110,4639-4*1113,9*54+29)
for offset in range(3):
    groups={}
    for x in range(2,69):
        groups.setdefault((x+offset)//3,[]).append(x)
    assert max(max(xs)-min(xs) for xs in groups.values())==2
