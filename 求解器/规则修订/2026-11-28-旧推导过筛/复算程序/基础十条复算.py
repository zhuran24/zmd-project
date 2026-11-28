from pathlib import Path
from fractions import Fraction as F
from math import lcm
import re

root = Path(__file__).resolve().parents[4]
rules = (root / '《明日方舟：终末地》游戏规则.txt').read_text()
task = (root / '求解任务.txt').read_text()
old = Path(__file__).resolve().parents[1]
def recipes(text):
    return re.findall(r'(\d+ [\u4e00-\u9fff]+(?:\s*＋\s*\d+ [\u4e00-\u9fff]+)?) → (\d+) ([\u4e00-\u9fff]+)，(\d+) tick', text.replace(' ＋ ', '＋'))
rr = recipes(rules)
assert rr == recipes(next(old.glob('旧规则*.txt')).read_text()) and len(rr) == 18
weights = {'源矿':(0,1), '蓝铁矿':(1,0), '荞花':(0,0), '砂叶':(0,0)}
for _ in rr:
    for left, n, right, _ in rr:
        inputs = [(int(q),item) for q,item in re.findall(r'(\d+) (\w+)', left)]
        if all(item in weights for q,item in inputs):
            w = tuple(sum(q*weights[item][i] for q,item in inputs)/F(n) for i in (0,1))
            assert weights.setdefault(right,w) == w
assert len(weights)==19
b,c = (F(v) for v in re.search(r'（([\d.]+) 个/tick 与 ([\d.]+) 个/tick）',task).groups())
wb,wc = [weights[k] for k in ('高容谷地电池','精选荞愈胶囊')]
a,d = (b*x+c*y for x,y in zip(wb,wc))
print('电池、胶囊',wb,wc,'矿流',a,d,a+d)
print('种植采种', [row[:3] for row in rr if '种子' in str(row)])
side=int(re.search(r'基地：(\d+)×',rules)[1])
width=int(re.search(r'仓库取货口：大小 (\d+)×1',rules)[1])
core=int(re.search(r'取货端口（共 (\d+) 个',rules)[1])
per=side//width
print('每边、两边、总口、两种指向',per,2*per,2*per+core,a,d)
step=int(re.search(r'每 1/(\d+) tick 为一步',rules)[1])
cycles=[n for n in range(1,step*40+1) if (b*n/step).denominator==(c*n/step).denominator==1]
print('前40 tick的整件周期步数',cycles,'首周期',[(v*cycles[0]/step) for v in (b,c,a,d)])
from itertools import combinations
dwell=int(re.search(r'必须停留至少 (\d+) tick',rules)[1])*step
print('8个连续步、同一方向相邻过件至少8步，最多过件',
      max(k for k in range(step+1) for times in combinations(range(step),k)
          if all(y-x>=dwell for x,y in zip(times,times[1:]))))
