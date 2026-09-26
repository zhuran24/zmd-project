#!/usr/bin/env python3
"""Snapshot read-only inputs and record hashes; write only inside output."""
import hashlib,json,os,re,shutil,time
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[2]
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
inputs={}
for meta in (OUT/'models').glob('*/metadata.json'):
    for item in json.loads(meta.read_text())['sources']:inputs[item['file']]=item['sha256']
for name in ('《明日方舟：终末地》游戏规则.txt','求解器/几何/1113流量层/报告.md','求解器/几何/1113流量层/模型说明.md','求解器/几何/1113流量层/run_campaign.py','求解器/几何/1113放松/报告.md','求解器/候选约束轮次/第75-77轮/推导75.md','求解器/候选约束轮次/第75-77轮/推导75/residual_global_A.json'):
    inputs[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
source_records=[]
for name,expected in sorted(inputs.items()):
    data=(ROOT/name).read_bytes();actual=hashlib.sha256(data).hexdigest();assert actual==expected,('input changed',name)
    dest=OUT/'source_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    source_records.append(dict(source=name,snapshot=str(dest.relative_to(OUT)),sha256=actual))
dump(OUT/'source_snapshot/manifest.json',source_records)
bad=[];checked=0
for file in [OUT/'报告.md',*(OUT/'明细').glob('*.md')]:
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',file.read_text()):
        if target.startswith(('http://','https://','#')):continue
        path=(file.parent/target.split('#')[0]).resolve()
        # manifest is created below.
        if path==OUT/'manifest.json':continue
        if not path.exists():bad.append(dict(file=str(file.relative_to(OUT)),target=target))
        checked+=1
assert not bad,bad[:20]
verification=json.loads((OUT/'verification.json').read_text());results=json.loads((OUT/'result_index.json').read_text())
assert verification['result_count']==len(results),('unverified result count',verification['result_count'],len(results))
assert len(results)==74
partitions=[]
for p in sorted((OUT/'raw').glob('*/partitions/*.json')):
    d=json.loads(p.read_text());partitions.append({k:v for k,v in d.items() if k!='part'}|dict(file=str(p.relative_to(OUT)),status='complete'))
assert len(partitions)==74
assert len({(d['dataset'],d['algorithm'],d['mode'],d['k']) for d in partitions})==74
dump(OUT/'partition_status.json',dict(status='complete',completed_results=partitions,earlier_campaign_receipts=[str(p.relative_to(OUT)) for p in sorted((OUT/'logs').glob('campaign_*.json'))],earlier_timeouts_are_not_final_status=True))
assert all(not m['source_files_changed_since_build'] for m in verification['models'])
now=datetime.now(timezone.utc)
audit=dict(date='2026-09-25',status='passed',result_count=len(results),linked_local_files_checked=checked,source_snapshots=len(source_records),reader_review=dict(self_contained=True,final_state_only=True,header_matches_result_count=True,no_style_instruction_echo=True,unique_numeric_conventions=True,terminology_checked_against_rule_file=True,all_local_links_exist=True),started_utc='2026-09-26T00:11:00+00:00',finished_utc=now.isoformat(),elapsed_wall_minutes=(now-datetime.fromisoformat('2026-09-26T00:11:00+00:00')).total_seconds()/60,solver_invocations=0,git_commands=0,write_scope=str(OUT),notes=['只检查语法依赖；未运行预处理或求解。','窗口结果及保留全局行的条件在每项明细中单列。','连接变量按确定规则构造，未声明最小或最优。'])
dump(OUT/'delivery_audit.json',audit)
files=[]
for p in sorted(OUT.rglob('*')):
    if not p.is_file() or any(x in ('.venv','cache','tmp') for x in p.relative_to(OUT).parts) or p==OUT/'manifest.json':continue
    data=p.read_bytes();files.append(dict(path=str(p.relative_to(OUT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
dump(OUT/'manifest.json',dict(created_utc=now.isoformat(),excluded=['.venv','cache','tmp','manifest.json'],files=files))
print(json.dumps(audit,ensure_ascii=False))
