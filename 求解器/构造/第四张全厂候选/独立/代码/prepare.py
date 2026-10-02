#!/usr/bin/env python3
import json,hashlib,shutil
from pathlib import Path
from fractions import Fraction as F
BASE=Path(__file__).resolve().parents[1]; ROOT=BASE.parents[3]
ms=[];edges=[]
def m(i,model,recipe,rate=1):
 kind='中' if model in ['种植机','采种机'] else '大' if model in ['研磨机','封装机','灌装机'] else '小'
 ms.append(dict(id=i,model=model,kind=kind,recipe_id=recipe,batch_rate=str(F(rate))))
def e(s,t,item,r=1):edges.append(dict(id=f'L{len(edges):03}',source=s,target=t,item=item,rate=str(F(r))))
for k in range(1,35):
 m(f'T{k}','精炼炉','精炼-蓝铁矿');m(f'KB{k}','粉碎机','粉碎-蓝铁块')
 e(f'OB{k}',f'T{k}','蓝铁矿');e(f'T{k}',f'KB{k}','蓝铁块');e(f'KB{k}',f'B{(k+1)//2}','蓝铁粉末')
for k in range(1,19):
 m(f'U{k}','粉碎机','粉碎-源矿');e('CORE' if k<=6 else f'OO{k}',f'U{k}','源矿');e(f'U{k}',f'O{(k+1)//2}','源石粉末')
for k in range(1,18):
 m(f'B{k}','研磨机','研磨-致密蓝铁');m(f'R{k}','精炼炉','精炼-致密蓝铁')
 e(f'B{k}',f'R{k}','致密蓝铁粉末');e(f'R{k}',f'P{k}' if k<=6 else f'H{(k-7)//2+1}','钢块')
for k in range(1,10):m(f'O{k}','研磨机','研磨-致密源石');e(f'O{k}',f'E{(k-1)//3+1}','致密源石粉末')
for k in range(1,7):
 m(f'P{k}','配件机','配件-钢制零件');m(f'H{k}','塑形机','塑形-钢质瓶',F(1,2) if k==6 else 1);m(f'Q{k}','研磨机','研磨-细磨荞花',F(1,2) if k==6 else 1)
 e(f'P{k}',f'E{(k+1)//2}','钢制零件')
 f=(k+1)//2 if k<=4 else k-2
 e(f'H{k}',f'F{f}','钢质瓶',F(1,2) if k==6 else 1);e(f'Q{k}',f'F{f}','细磨荞花粉末',F(1,2) if k==6 else 1)
for k in range(1,4):m(f'E{k}','封装机','封装-电池',F(1,5));e(f'E{k}','CORE','高容谷地电池',F(1,5))
for k,rate in enumerate([F(1,5),F(1,5),F(1,10),F(1,20)],1):m(f'F{k}','灌装机','灌装-胶囊',rate);e(f'F{k}','CORE','精选荞愈胶囊',rate)
groups=['B1 B2 O1','O2 O3','B3 B4 O4','O5 O6','B5 B6 O7','O8 O9','B7 B8 B9','B10 Q1 Q2','B11 B12 B13','B14 Q3 Q4','B15 B16 Q5','B17','Q6']
for p,n,it in [('S',13,'砂叶'),('Q',6,'荞花')]:
 for k in range(1,n+1):
  targets=groups[k-1].split() if p=='S' else [f'Q{k}']*(1 if k==6 else 2)
  rates=[F(1,2) if p=='S' and t=='Q6' else F(1) for t in targets]
  rate=sum(rates)/(3 if p=='S' else 2)
  cr=f'S{k}' if p=='S' else f'KQ{k}'
  m(f'{p}C{k}','采种机','采种-'+it,rate);m(f'{p}A{k}','种植机','种植-'+it,rate);m(f'{p}B{k}','种植机','种植-'+it,rate);m(cr,'粉碎机','粉碎-'+it,rate)
  for a,b,item in [(p+'C',p+'A',it+'种子'),(p+'C',p+'B',it+'种子'),(p+'A',p+'C',it),(p+'B',cr,it)]:
   e(f'{a}{k}',f'{b}{k}' if b!=cr else cr,item,rate)
  for t,r in zip(targets,rates):e(cr,t,it+'粉末',r)
assert len(ms)==230 and len(edges)==325
contract=dict(schema='s2b-independent-contract-v1',machines=ms,feeds=edges)
(BASE/'逻辑接法.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
# Source snapshots are evidence, never imported as instructions.
inputs=[ROOT/'求解器/候选约束轮次/第107-109轮/推导107S2B.md', ROOT/'求解器/候选约束轮次/第107-109轮/临时规则.md',ROOT/'求解器/构造/第一张全厂候选/格式.md']
inputs += list((ROOT/'求解器/候选约束轮次/第107-109轮/前提快照').glob('*.txt'))
fps=[]
for p in inputs:
 q=BASE/'依据'/p.name;shutil.copyfile(p,q);fps.append(dict(path=str(p),copy=str(q),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
(BASE/'依据/指纹.json').write_text(json.dumps(fps,ensure_ascii=False,indent=2)+'\n')
# Generic integer input for the native search; no dependency on a previous layout.
u=[]
for a in ms:
 kind={'小':0,'中':1,'大':2}[a['kind']];u.append((a['id'],kind))
u.append(('CORE',3))
for k in range(1,35):u.append((f'OB{k}',4))
for k in range(7,19):u.append((f'OO{k}',4))
for k in range(25):u.append((f'POWER{k}',5))
idx={n:i for i,(n,k) in enumerate(u)}
with (BASE/'输入.txt').open('w') as o:
 print(len(u),len(edges),file=o)
 for n,k in u:print(n,k,file=o)
 for z in edges:print(idx[z['source']],idx[z['target']],file=o)
print({'machines':len(ms),'feeds':len(edges),'units':len(u)})
