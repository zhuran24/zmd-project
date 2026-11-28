from fractions import Fraction as F
from math import ceil
from pathlib import Path
import re

root = Path(__file__).resolve().parents[4]
rule = (root / "《明日方舟：终末地》游戏规则.txt").read_text()
task = (root / "求解任务.txt").read_text()
old = next(Path(__file__).resolve().parents[1].glob("旧规则*")).read_text()
def recipes(doc):
    out = {}
    for a,b,t in re.findall(r'([\d\w ＋]+) → ([\d\w ]+)，(\d+) tick', doc.split('\n配方\n')[-1]):
        left = dict((name,int(n)) for n,name in re.findall(r'(\d+)\s+(\S+)', a.replace('＋',' ')))
        n,name = b.strip().split()
        out[tuple(left.items()),name] = int(n),int(t)
    return out
r = recipes(rule)
assert r == recipes(old) and len(r)==18
def need(product,ingredient):
    for (inputs,output),(n,t) in r.items():
        if output==product and ingredient in dict(inputs):
            return F(dict(inputs)[ingredient],n)
def yield_of(plant):
    return 1/need(plant+'粉末',plant)
battery,capsule=map(F,re.search(r'（([\d.]+) 个/tick 与 ([\d.]+) 个/tick',task).groups())
parts=battery*need('高容谷地电池','钢制零件')
bottle=capsule*need('精选荞愈胶囊','钢质瓶')
fine=capsule*need('精选荞愈胶囊','细磨荞花粉末')
ore=battery*need('高容谷地电池','致密源石粉末')
steel=parts*need('钢制零件','钢块')+bottle*need('钢质瓶','钢块')
sand=(fine+ore+steel)/yield_of('砂叶')
buck=fine*need('细磨荞花粉末','荞花粉末')/yield_of('荞花')
print('矿口',2*steel,2*ore,2*(70//3)+6)
print('粉碎=采种、种植、两类各自平均下界',[(str(f),2*f,4*f) for f in (buck,sand)])
print('种植合计、两 tick 完成',2*(buck+sand),4*(buck+sand))
print('机器、箱、旧新桥增量',50*2+2,50*2+1,6*50,2-1,4-1)
print('交替出口数',[ceil(F(x+y,2)) for x,y in [(3,2),(3,1),(2,1),(2,2)]])
print('采种阈值',1/F(2))
for m in range(1,4):
    slots=list(range(1,8*m+1,8))
    print('砂叶批数、需求、旧新两口容量',m,3*m,2*(m+1),2*len(slots))
