#!/usr/bin/env python3
"""交付范围、来源、桥字段、黄金及历史证据字节核对；不扫描模拟器或Git。"""
from pathlib import Path
import json,hashlib,re
R=Path.cwd();O=R/'内核维护/2026-09-22';before=json.loads((O/'before.json').read_text());checks={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks['protected_unchanged']={n:sha(R.parent/n)==v['sha256'] for n,v in before['protected'].items()};assert all(checks['protected_unchanged'].values())
c=json.loads((R/'数据/正式静态目录.json').read_text());checks['source_rows_exact']=all(x['sha256']==sha(R.parent/x['path']) and x['lines']==(R.parent/x['path']).read_text().splitlines() for x in c['sources']);assert checks['source_rows_exact']
bridge=next(u for u in c['units'] if u['id']=='桥接器');assert bridge['inventory_rules']['same_item_across_slots']=='exempt'
l=json.loads((R/'会议成果/任务书7执行/密排布局.json').read_text());routes=[r for r in l['routes'] if r['source_unit'] in [f'M{i}' for i in range(213,219)]];assert len(routes)==6
for r in routes:
 assert r['service_capacity_given_receiving_boundary'] is not None
 assert r['service_contract']['completion_to_box_bound_ticks']==r['transport_slots']+1
 assert r['service_contract']['completion_to_warehouse_bound_ticks']==r['transport_slots']+6
 assert r['service_contract']['preloaded_recovery_bound_ticks']==106
 assert r['actual_rate'] is None
checks['bridge_routes']=[{k:r[k] for k in ['id','actual_rate','service_contract']} for r in routes]
for n in ['运行语义','选择点清单']:
 s=(R/f'规格/{n}.md').read_text().split('主会话补记（2026-09-22）')[1];assert '已退回' in s and '待退回' not in s and '下一轮' not in s
changed=[];history_changes=[];external_changes=[]
for name,v in before['files'].items():
 p=R/name
 if not p.exists() or sha(p)!=v['sha256']:
  row={'path':name,'before':v['sha256'],'after':sha(p) if p.exists() else None}
  if any(x in p.parts for x in ['复核','证据','evidence']):history_changes.append(row)
  if name.startswith(('候选约束轮次/','几何/')):external_changes.append(row)
  else:changed.append(row)
checks['historical_evidence_changes']=history_changes;assert not history_changes
checks['hand_golden_unchanged']=all(sha(R/('数据/样例/混做粉碎机两下游-黄金轨迹'+x))==before['files']['数据/样例/混做粉碎机两下游-黄金轨迹'+x]['sha256'] for x in ['.json','.md']);assert checks['hand_golden_unchanged']
checks['old_reference_records_unchanged']=all(sha(R/f'数据/样例/{n}-运行记录-v3.json')==before['files'][f'数据/样例/{n}-运行记录-v3.json']['sha256'] for n in ['混做粉碎机两下游','分流器三路轮询']);assert checks['old_reference_records_unchanged']
checks['maintained_files']=changed;checks['concurrent_other_work']=external_changes
checks['maintenance_file_types']=sorted({p.suffix for p in O.rglob('*') if p.is_file()});assert set(checks['maintenance_file_types'])<={'','.py','.log','.json','.md'}
# 链接检查只验本轮新写的记录、方案与成品稿；历史链接坏点不顺手改写。
missing=[]
for p in [R/'内核维护/代码体检方案.md',O/'记录.md',R/'会议成果/任务书7执行/成品输出通路.md']:
 if not p.exists():continue
 for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  target=target.split('#')[0]
  if target and not target.startswith(('http:','https:')) and not (p.parent/target).exists() and (p.parent/target).resolve() != O/'final-audit.json':missing.append({'file':str(p),'target':target})
checks['broken_delivery_links']=missing;assert not missing
(O/'final-audit.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n');print('pass',len(changed),'maintained existing files; source/golden/history hashes unchanged')
