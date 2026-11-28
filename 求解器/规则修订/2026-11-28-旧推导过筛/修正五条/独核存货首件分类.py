from itertools import combinations, product
from pathlib import Path
import re

rules = (Path(__file__).resolve().parents[4]/"《明日方舟：终末地》游戏规则.txt").read_text()
wrong = '误料'
for line in rules.split('\n配方\n')[1].strip().splitlines():
    name, text = line.strip().split('：')
    recipes = [dict((item, int(n)) for n, item in re.findall(r'(\d+) (\S+?)(?=＋|$)', r.split(' → ')[0])) for r in text.split('；')]
    legal = sorted(set.union(*(set(r) for r in recipes)))
    large = name in ('研磨机','封装机','灌装机')
    slots = 2 if large else 1
    counts = [0,0]
    for used in range(slots+1):
        for items in combinations(legal, used):
            if name == '研磨机' and used == 2 and '砂叶粉末' not in items:
                continue
            for amounts in product(range(1,51), repeat=used):
                stock = dict(zip(items, amounts))
                can_make = any(all(stock.get(x,0)>=n for x,n in r.items()) for r in recipes)
                rejected = {x for x in [*legal,wrong] if stock.get(x)==50 or (x not in stock and used==slots)}
                # Independently construct the head types allowed by the proposed classification.
                expected = set()
                if large and amounts == (50,):
                    expected.update(items)
                if name=='塑形机' and amounts==(1,):
                    expected.add(wrong)
                if used==2:
                    if name=='研磨机':
                        under = any(stock[x]==1 for x in items if x!='砂叶粉末')
                    elif name=='封装机':
                        under = stock['钢制零件']<10 or stock['致密源石粉末']<15
                    else:
                        under = min(amounts)<10
                    if under:
                        expected.update(x for x in legal if x not in stock or stock[x]==50)
                        expected.add(wrong)
                actual = set() if can_make else rejected
                assert expected == actual, (name,stock,expected,actual)
                # Each nonempty subset gives one group, ignoring repeated heads.
                counts[0] += 2**len(actual-{wrong})-1
                counts[1] += 2**len(actual)-1
    print(name, *counts)
