#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json,re,hashlib
B=Path('/home/zhuran24/zmd-research-fresh/求解器');E=Path(__file__).resolve().parent
cat=json.loads((B/'数据/正式静态目录.json').read_text());cfg=json.loads((B/'规格/内核配置-v1.json').read_text());checks=[]
def ck(n,c,d=None):checks.append({'name':n,'passed':bool(c),'detail':d});assert c,(n,d)
formal=[]
for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']:
 p=B.parent/name;h=hashlib.sha256(p.read_bytes()).hexdigest();entry=next(x for x in cat['sources'] if x['sha256']==h)
 formal.append({'path':str(p),'sha256':h,'line_count':len(p.read_text().splitlines())})
 lines=entry['lines'];actual=p.read_text().splitlines()
 if isinstance(lines,list) and lines and isinstance(lines[0],dict):
  # Current catalog stores line numbers explicitly.
  lk='text' if 'text' in lines[0] else 'content';ck('formal_lines:'+name,[r[lk] for r in lines]==actual)
 else:ck('formal_lines:'+name,lines==actual)
 ck('secondary_source_registry:'+name,h in (B/'数据/样例/check_examples.py').read_text())
axes=cfg['axes'];ck('99_axes',len(axes)==cfg['axis_count']==99)
for file in ['选择点参数轴.md','受限模型声明.md','内核输入.md']:
 s=(B/'规格'/file).read_text();rows={}
 for line in s.splitlines():
  m=re.match(r'^\| `([^`]+)` \| (.*) \|$',line)
  if m and m[1] in axes:assert m[1] not in rows;rows[m[1]]=m[2].split(' | ')
 ck('axis_set:'+file,set(rows)==set(axes))
 for k,v in axes.items():
  if file=='选择点参数轴.md':assert rows[k][1]==v['lifetime']
  if file=='内核输入.md':assert v['lifetime'] in rows[k][0]
  if file=='受限模型声明.md':assert rows[k][0]==v['disposition'] and '`'+json.dumps(v['value'],ensure_ascii=False,separators=(',',':'))+'`' in rows[k][1]
ck('disposition_counts',Counter(v['disposition'] for v in axes.values())=={'已定':22,'本版选值':44,'超出覆盖即停':18,'由输入全称量化':15})
for k,v in [('polling.both_failure','advance_authorized'),('transfer.failure_cooldown','every_attempt'),('judgment.order_scope','fixed_run_order'),('connection.port_meeting','shared_edge_opposite')]:ck(k,axes[k]['value']==v and axes[k]['disposition']=='已定')
active=['运行语义','选择点清单','选择点参数轴','受限模型声明','受限转移定义','内核输入','内核输出','四件前置义务对照']
for f in active:
 s=(B/'规格'/(f+'.md')).read_text();ck('current_hash:'+f,'d150b86b398f' in s and '31ced2a24fef' not in s and 'abc7a5867f64' not in s)
ck('debug_permissions','动作权限覆盖增建、拆除、清理、手工放料和改设定' in (B/'规格/内核输入.md').read_text())
# Verify the implementer's build binding against live source bytes independently.
binding=json.loads((B/'会议成果/任务书7执行/证据/内核/build-binding.json').read_text())
for p,h in binding['source_sha256'].items():ck('source_binding:'+Path(p).name,hashlib.sha256(Path(p).read_bytes()).hexdigest()==h)
ck('rebuilt_binary',hashlib.sha256((B/'target/release/kernel').read_bytes()).hexdigest()==binding['sha256'])
(E/'contracts-independent.json').write_text(json.dumps({'checks':checks,'formal_sources':formal,'catalog_sha256':hashlib.sha256((B/'数据/正式静态目录.json').read_bytes()).hexdigest(),'binary_sha256':binding['sha256'],'dispositions':dict(Counter(v['disposition'] for v in axes.values())),'scope':'current published contracts and current binary/source; historical references classified in report'},ensure_ascii=False,indent=2)+'\n')
print('PASS',len(checks),'checks; current sources/99 axes/source-binary binding')
