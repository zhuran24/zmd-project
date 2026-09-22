#!/usr/bin/env python3
"""核对执行中外部发生的三份来源更新；只写本席证据。"""
from pathlib import Path
import json, hashlib
E=Path(__file__).resolve().parent
old=json.loads((E/'输入指纹.json').read_text())
expected={
 '《明日方舟：终末地》游戏规则.txt':'d150b86b398f8e73e57bee1598020e6bcd895e5a13a254b4b11dd1e4416c325a',
 '任务书7草案.md':'6394c5ee4214a7b48057dcd3e916b59e55085895dff06f93b86a00f139d01620',
 '主会话三审-0920.md':'8710bebae67f41b4f323570a54f046bfed71bc28d3c2e2bc4efa002ee20020a2'}
task_old13='| 规则 | [《明日方舟：终末地》游戏规则.txt](../../《明日方舟：终末地》游戏规则.txt)，SHA-256前12位`31ced2a24fef`，114行。owner 2026-09-21 06:18 改了第 36 行一处（储存箱传输改为「能送多少送多少」，删去「即使那个物品格中没有物品也一样」），其余与总结、v46 所审的 `abc7a5867f64` 逐字相同；席位一律读现行文字 |'
task_old29='- 储存箱传输不是整箱一次送：箱子尽量往仓库送，能送进去的部分就送，不像缓存那样整批或不送。owner 已把这句写进规则第 36 行现行文字（「能送多少送多少」），同时删去了「即使那个物品格中没有物品也一样」；箱子空着时 5 tick 冷却怎么算，按现行文字读，读不出唯一含义就登记为缺游戏事实，传输相位本来就是不得依赖量。'
changes=[];current=[]
for x in old:
 p=Path(x['path']);b=p.read_bytes();sha=hashlib.sha256(b).hexdigest()
 if p.name in expected:
  assert sha==expected[p.name],p.name
  if p.name=='《明日方舟：终末地》游戏规则.txt':
   restored=b.replace('，即使那个物品格中没有物品也一样，能送多少送多少'.encode(),'，能送多少送多少'.encode());lines=[36]
  elif p.name=='任务书7草案.md':
   ls=b.decode().splitlines(keepends=True);ls[12]=task_old13+'\n';ls[28]=task_old29+'\n'
   ls[66]=ls[66].replace('规则 `d150b86b398f`（09-21 上午恢复第 36 行后的现行值；任务 1 首次重锁时是 31ced2a24fef，主会话已同步）','规则 `31ced2a24fef`')
   restored=''.join(ls).encode();lines=[13,29,67]
  else:
   restored=b''.join(b.splitlines(keepends=True)[:53]);lines=[54]
  assert hashlib.sha256(restored).hexdigest()==x['sha256'],'increment not exhaustive: '+p.name
  changes.append(dict(path=str(p),old_sha256=x['sha256'],new_sha256=sha,changed_lines=lines,
    reverse_increment_restores_old_sha256=True,
    impact='R36零传输冷却依owner补充已定；本席不使用箱，植物配方、C82、容量、局部运行结论无受影响前件'))
 else:
  assert sha==x['sha256'] and p.stat().st_mtime_ns==x['mtime_ns'],p.name
 s=p.stat();current.append(dict(path=str(p),sha256=sha,bytes=len(b),lines=len(b.splitlines()),mtime_ns=s.st_mtime_ns))
for name,d in [('来源增量.json',changes),('输入当前指纹.json',current)]:
 (E/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('PASS: 16份来源不变；R36、任务书L13/L29/L67、三审新增L54的逆差异各自恢复原SHA-256；绑定19份现行输入。')
