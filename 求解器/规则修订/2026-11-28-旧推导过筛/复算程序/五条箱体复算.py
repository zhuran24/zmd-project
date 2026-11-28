from pathlib import Path
from fractions import Fraction as F
from math import ceil
from itertools import permutations
import re
root=Path(__file__).resolve().parents[4]
current=(root/'《明日方舟：终末地》游戏规则.txt').read_text().split('\n配方\n')[1]
old=(Path(__file__).resolve().parents[1]/'旧规则-2026-09-26.txt').read_text().split('\n配方\n')[1]
def terms(s):
    return {name:int(n) for n,name in re.findall(r'(\d+)\s*([^\s＋]+)',s)}
recipes=[]
for line in current.strip().splitlines():
    machine, entries=line.strip().split('：')
    for entry in entries.split('；'):
        a,b=re.sub(r'，.*','',entry).split('→')
        recipes.append((machine,terms(a),terms(b)))
normalize=lambda s:re.sub(r'\s+','',s)
for line in current.strip().splitlines():
    for entry in line.split('：')[1].split('；'):
        assert normalize(entry) in normalize(old)
# 在 r=0、r=1 解两次同一线性系统，常数与斜率分别读出。
def flows(r):
    external={'蓝铁矿':34,'源矿':18,'高容谷地电池':-F(3,5),'精选荞愈胶囊':-F(11,20)}
    items=sorted(set().union(*(a.keys()|b.keys() for _,a,b in recipes)))
    matrix=[[F(b.get(x,0)-a.get(x,0)) for _,a,b in recipes]+[-F(external.get(x,0))] for x in items]
    matrix.append([F(m=='精炼炉' and '蓝铁粉末' in a) for m,a,b in recipes]+[F(r)])
    for col in range(len(recipes)):
        pivot=next(i for i in range(col,len(matrix)) if matrix[i][col])
        matrix[col],matrix[pivot]=matrix[pivot],matrix[col]
        matrix[col]=[v/matrix[col][col] for v in matrix[col]]
        for i,row in enumerate(matrix):
            if i!=col:
                matrix[i]=[v-row[col]*w for v,w in zip(row,matrix[col])]
    assert all(not any(row) for row in matrix[len(recipes):])
    rates=[row[-1] for row in matrix[:len(recipes)]]
    return 52+sum(q*sum(b.values()) for q,(_,a,b) in zip(rates,recipes))
base=flows(0)
print('物料',len(recipes),base,flows(1)-base,ceil(base+52),ceil(base+8))
s=sum([95,51,32,6,6,32,32,3,3])+52
r=sum([68,51,95,11,6,32,16,15,11])
g=4*46-93+4*6-16
h=g+sum([54,62,10,14,24])//2
print('接口',s,r,g,h,s+r+2,s+r+2+g,s+r+2+h,ceil((718+5)/2),ceil((800+5)/2))
area=(68+51+6+6)*9+(32+16)*25+(32+3+3)*24
fixed=area+9**2+46*3+ceil(217/23)*4
print('面积',area,fixed,fixed+200,4900-fixed-200-1)
for eta in range(4):
    a=max(1149-ceil(eta/4),1150-ceil((eta+3)/4))
    assert a==1149-(eta+2)//4
print('特例',fixed+200+9+ceil(2/4),1149-9-(2+2)//4)
print('前缀容量',[50*j for j in range(6)])
print('三口中两口接受，箱头起有三件时，各排列能取的件数',
      [sum(i<2 for i in order) for order in permutations(range(3))])
