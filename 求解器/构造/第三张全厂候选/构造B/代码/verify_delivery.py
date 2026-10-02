#!/usr/bin/env python3
"""Recheck the delivered failing candidate. Exit 0 means the evidence agrees, never layout feasibility."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import json,hashlib,subprocess,sys,re
from pathlib import Path
from datetime import datetime,timezone
B=Path(__file__).resolve().parents[1];ROOT=B.parents[3];cand=B/'候选布局.json';report=B.parent/'构造B.md';code=B/'代码';evidence=B/'证据'
def run(script,*args):
 r=subprocess.run([sys.executable,'-B',str(code/script),*map(str,args)],capture_output=True,text=True,env=os.environ.copy())
 if r.returncode:raise RuntimeError((script,r.returncode,r.stdout,r.stderr))
 return r.stdout
run('static_check.py',cand,B/'静态检查结果.json')
run('check_metrics_independent.py',cand,evidence/'独立数字复核.json')
run('route_obstructions.py',cand)
run('check_obstructions_independent.py',cand)
run('summarize_bridges.py')
run('run_legacy_geometry.py','A',cand)
run('run_legacy_geometry.py','B',cand)
run('check_modules.py')
run('checker_mutations.py')
run('draw_layout.py',cand,B/'布局图.svg')
r=subprocess.run(['rsvg-convert',str(B/'布局图.svg'),'-o',str(B/'布局图.png')],capture_output=True,text=True)
assert r.returncode==0,r.stderr
raw=json.loads(cand.read_text());a=json.loads((B/'静态检查结果.json').read_text());z=json.loads((evidence/'独立数字复核.json').read_text());obs=json.loads((evidence/'固定几何卡点.json').read_text());ob2=json.loads((evidence/'卡点独立复核.json').read_text());bridge=json.loads((evidence/'桥接器结构.json').read_text())
assert a['static_pass'] is False
st=a['stats'];assert st['machines']==230 and st['completed_routes']==195 and st['missing_routes']==130
for ka,kb in [('machine_area','machine_area'),('occupied_cells','occupied_area'),('power_poles','power_poles'),('transport','transport'),('bridges','bridges'),('adjacent_bridge_pairs','adjacent_bridge_pairs'),('structural_channels','physical_channels'),('reverse_bridge_channels','reverse_channels'),('completed_routes','route_count')]:assert st[ka]==z[kb],(ka,kb)
assert z['powered']==230 and not z['overlap'] and all(z['identities'].values())
assert st['empty_rectangle']['area']==z['maximum_empty_rectangle']['area']==36
assert obs['counts']==ob2['missing_route_counts'] and len(obs['port_deficits'])==ob2['port_deficit_machine_count']==52
assert ob2['E3']['all_occupied_by_core'] and not ob2['core_incoming_channels'] and ob2['finished_routes']==0
assert bridge['bridge_count']==6 and bridge['adjacent_pairs']==1 and bridge['longest_straight_run']==2
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();candidate_sha=sha(cand)
assert candidate_sha==a['candidate_sha256']==z['candidate_sha256']==ob2['candidate_sha256']
for seat in ['A','B']:
 q=json.loads((evidence/f'旧检查器{seat}-几何.json').read_text());assert q['candidate_sha256']==candidate_sha and q['channels_equal_claimed'] and q['channels']==527 and q['occupied_cells']==4211 and q['powered_machines']==230 and q['maximum_empty_rectangle']['area']==36
replay=json.loads((evidence/'构造重放结果.json').read_text());assert replay['candidate_sha256']==candidate_sha and replay['byte_identical']
original_inputs=json.loads((B/'依据/输入指纹.json').read_text());inputs=[]
for v in original_inputs:
 pp=ROOT/v['path'];inputs.append(dict(path=v['path'],unchanged=sha(pp)==v['sha256']))
assert all(v['unchanged'] for v in inputs)
legacy=[]
for v in json.loads((evidence/'旧几何适配清单.json').read_text())['files']:
 legacy.append(dict(path=v['source'],unchanged=sha(ROOT/v['source'])==v['sha256']))
assert all(v['unchanged'] for v in legacy)
# Validate local Markdown links in the report and extension document.
broken=[]
for doc in [report,B/'格式扩展.md']:
 for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
  if '://' in target or target.startswith('#'):continue
  target=target.split('#')[0]
  resolved=(doc.parent/target).resolve()
  if not resolved.exists() and resolved not in {(evidence/'交付核验.json').resolve(),(evidence/'文件清单.json').resolve()}:broken.append(dict(document=str(doc),target=target))
assert not broken,broken
started=datetime(2026,10,2,13,15,6,tzinfo=timezone.utc);now=datetime.now(timezone.utc)
result=dict(status='evidence_consistent_candidate_rejected',static_pass=False,candidate_sha256=candidate_sha,report_sha256=sha(report),summary=dict(machines=230,powered=230,completed_routes=195,missing_routes=130,empty_rectangle_area_on_failing_candidate=36),original_inputs=inputs,original_checkers=legacy,local_links_valid=True,replay_byte_identical=True,started_utc=started.isoformat(),checked_utc=now.isoformat(),elapsed_seconds=(now-started).total_seconds(),configured_max_compute_workers=4,ran_cargo_tests=False,used_git=False,notes='验证脚本成功退出仅表示证据一致；未给出达标全厂，不更新 L。')
(evidence/'交付核验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
files=[]
for p in sorted(B.rglob('*')):
 if not p.is_file() or p==evidence/'文件清单.json':continue
 files.append(dict(path=str(p.relative_to(B)),bytes=p.stat().st_size,sha256=sha(p)))
files.append(dict(path='../构造B.md',bytes=report.stat().st_size,sha256=sha(report)))
(evidence/'文件清单.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n')
assert (evidence/'交付核验.json').exists() and (evidence/'文件清单.json').exists()
print(json.dumps({k:v for k,v in result.items() if k not in ['original_inputs','original_checkers']},ensure_ascii=False))
