from fractions import Fraction as F
from pathlib import Path
import re
rules=Path("《明日方舟：终末地》游戏规则.txt").read_text()
recipes={}
for ingredients, count, product, ticks in re.findall(r'((?:\d+ [\u4e00-\u9fff]+＋)*\d+ [\u4e00-\u9fff]+) → (\d+) ([\u4e00-\u9fff]+)，(\d+) tick',rules):
    recipes[product,ingredients]=int(count),int(ticks)
def recipe(product):
    return next((s,n,d) for (p,s),(n,d) in recipes.items() if p==product)
cap=int(re.search(r'制造单位的物品格（上限 (\d+)）',rules)[1])
for p in ('荞花','荞花种子','荞花粉末','砂叶粉末'):
    s,k,d=recipe(p)
    print(p,k,d,cap-k,cap-3*k)
block=3*cap+2+F(cap-1,2)
print("卡住、续段、最大、起值偏移",block, block-F(1,2),3*cap+2+F(cap,2),2+F(1,2))
blue,ore,sand,flower=34,18,11,6
mills=blue//2+ore//2+flower
machines=(blue+ore+sand+flower,blue+blue//2,mills,6,6,2*(sand+flower),sand+flower,3,3)
print(machines,sum(machines),sum(a*b for a,b in zip(machines,(9,9,24,9,9,25,25,24,24))))
out=blue+ore+(blue//2)+(blue+ore)+32+2*flower+mills+6+6+2*(sand+flower)+2*(sand+flower)+6
print("各起点出路合计",out+blue)
battery=F(3,recipe('高容谷地电池')[2])
bottle_demand=int(recipe('精选荞愈胶囊')[0].split()[0])
capsule=F(2,recipe('精选荞愈胶囊')[2])+(1+F(1,2))/bottle_demand
print('条件产率及30tick数量',battery,capsule,30*battery,30*capsule)
