from collections import Counter
from fractions import Fraction as Q
from math import ceil, lcm
from pathlib import Path
import re

rules = Path('《明日方舟：终末地》游戏规则.txt').read_text()
recipes = {}
for line in rules.split('\n配方\n')[1].strip().splitlines():
    machine, items = line.strip().split('：')
    for recipe in items.split('；'):
        ingredients, product, duration = re.fullmatch(r'(.+) → (.+)，(\d+) tick', recipe).groups()
        def parse(item):
            count, name = item.split()
            return name, int(count)
        name, count = parse(product)
        if name == '蓝铁块' and '矿' not in ingredients:
            continue  # r=0 gives base rates; one refining loop adds one batch to each of two machines
        recipes[name] = machine, dict(map(parse, ingredients.split('＋'))), count, int(duration)

rates, inputs, outputs = Counter(), Counter(), Counter()
ore = Counter()
def demand(product, rate):
    if product not in recipes:
        ore[product] += rate
        return
    machine, materials, amount, ticks = recipes[product]
    batches = rate / amount
    rates[machine] += batches
    outputs[machine] += rate
    for material, units in materials.items():
        inputs[machine] += batches * units
        if machine == '采种机':
            continue
        if machine == '粉碎机' and material in ('砂叶', '荞花'):
            # one harvest is crushed and one is used to reseed both plants
            demand(material, 2 * batches * units)
        else:
            demand(material, batches * units)
demand('高容谷地电池', Q(18,30))
demand('精选荞愈胶囊', Q(33,60))
print('ore', ore, 'ports', 2*(70//3)+6, 'batches', rates)
for machine in ['研磨机','塑形机','采种机','封装机','灌装机']:
    flow = (outputs if machine == '采种机' else inputs)[machine]
    _, materials, amount, ticks = next(r for r in recipes.values() if r[0]==machine)
    capacity = Q(amount if machine=='采种机' else sum(materials.values()),ticks)
    n = ceil(rates[machine]*ticks)
    print(machine, flow, capacity, n, [max(0,ceil(flow-(capacity-1)*j)) for j in (n,n+1)])
last = rates['灌装机']-Q(2,5)
print('last filler',last,'per 20 ticks',last*20,'bottles/powder',last*20*10)
for a,b in ((2,1),(10,15),(10,10)):
    values = [b*s-a*t for s in range(51) for t in range(51)]
    print('stock bounds',a,b,min(values),max(values),max(values)-min(values))
print('period',lcm(5,20))
# Full segments labelled 0..19 on a cyclic period, four steps apiece.
for k in range(6):
    events = [(8*i) for i in range(k)] + [(40+8*i) for i in range(k)]
    if k == 1:
        events[1] += 3
    counts = Counter(t//4 for t in events)
    assert all(sum(counts[(s-i)%20] for i in range(10)) == k for s in range(20))
    if events:
        assert min((b-a)%80 for a,b in zip(events,events[1:]+events[:1]))>=8
    print('ten-segment rate',k,Q(len(events)*8,80),'events',events)
