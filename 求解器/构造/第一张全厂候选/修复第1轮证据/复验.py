#!/usr/bin/env python3
"""顺序复验当前候选与修复后的A，B只读；全部写入本修复证据目录。"""
import os, sys, json, hashlib, subprocess, copy
from pathlib import Path
from collections import Counter

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE.parents[2]
CAND=BASE/'生成/候选.json'
env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args, stem, expected):
    proc=subprocess.run([sys.executable,'-B',*map(str,args)],cwd=ROOT,env=env,capture_output=True,text=True)
    (HERE/(stem+'.log')).write_text(proc.stdout+proc.stderr)
    assert proc.returncode==expected,(stem,proc.returncode,proc.stderr)
    return proc

before=json.loads((HERE/'候选-修复前.json').read_text())
now=json.loads(CAND.read_text());tmp=copy.deepcopy(now)
tmp['design']['restrictions']=before['design']['restrictions']
geometry_unchanged=(tmp==before)
start_sha=sha(CAND)
run([BASE/'检查器A/check_full.py',CAND,'--out',HERE/'A复验.json'],'A复验',1)
run([BASE/'检查器B/check.py',CAND,'--output',HERE/'B复验.json'],'B复验',1)
cert=run([BASE/'检查器A/verify_certificate.py',CAND,HERE/'A复验.json'],'A证书回放',0)
(HERE/'A证书回放.json').write_text(json.dumps(json.loads(cert.stdout),ensure_ascii=False,indent=2)+'\n')
a=json.loads((HERE/'A复验.json').read_text());b=json.loads((HERE/'B复验.json').read_text())
def edge_set(items):
    def ref(p):return p['unit'],p['side'],p['offset']
    return {(ref(e['from']),ref(e['to'])) for e in items}
aa=edge_set(a['recomputed']['channels']);bb=edge_set(b['geometry']['physical_channels_rebuilt'])
assert aa==bb==edge_set(now['design']['physical_channels'])
assert a['candidate_sha256']==b['candidate_sha256']==sha(CAND)==start_sha
ac={v['id']:v for v in a['checks']}
assert ac['recipe_restriction_registration']['status']=='checked'
assert all(v['status']!='unresolved' for v in a['checks'])
assert 'B_feeds' not in ac and ac['P2']['status']=='blocked'
assert not any(v['status']=='UNIMPLEMENTED' for v in b['checks'])
assert next(v for v in b['checks'] if v['check']=='recipe-restriction-register')['status']=='PASS'
assert b['flow']['status']=='INFEASIBLE_EXACT'
initial=json.loads((HERE/'起始哈希.json').read_text())
protected=[p for p in initial if Path(p).is_relative_to(BASE/'检查器B') or not Path(p).is_relative_to(BASE)]
assert all(sha(Path(p))==initial[p] for p in protected)
# The independent LP must be rebuilt for the exact current candidate.
orig_lp=json.loads((HERE/'独立LP.json').read_text())
assert orig_lp['candidate_sha256']==start_sha
assert edge_set(orig_lp['geometry']['physical_channels_rebuilt'])==aa
result={
    'task_complete':False,'pass':False,'candidate_sha256':start_sha,
    'changes_scope':'候选限制登记规范化及新摆放布线；A修复D1/D2/D3/D7和单端桥；候选仍未达标',
    'A':{'status':a['status'],'check_status_counts':dict(Counter(x['status'] for x in a['checks'])),'formal_constraints':len(a['formal_constraints']),'P2_structure':ac['P2_structure']['status'],'P2':ac['P2']['status'],'certificate':json.loads(cert.stdout)},
    'B':{'status':b['status'],'summary':b['summary'],'check_status_counts':dict(Counter(x['status'] for x in b['checks'])),'flow':b['flow']},
    'exact_channel_sets_equal':True,'channels':len(aa),'geometry_unchanged':geometry_unchanged,
    'independent_LP_recomputed_for_current_candidate':True,
    'independent_LP_note':'已重新运行严格LP、去预处理LP、放宽矿源但保留目标LP、19物品诊断及总通道流诊断；A精确证书另行重放。',
    'remaining_defects':{'disconnected_sources':len(orig_lp['geometry']['disconnected_sources']),'S':orig_lp['geometry']['S'],'R':orig_lp['geometry']['R'],'capsule_warehouse_paths':sum(p['item']=='精选荞愈胶囊' for p in orig_lp['product_paths']),'battery_warehouse_paths':sum(p['item']=='高容谷地电池' for p in orig_lp['product_paths'])},
    'B_and_formal_files_unchanged':True,'protected_files_checked':len(protected),
    'solver_policy':'CP-SAT最多5 workers，LP/BLAS/OMP均1线程；LP调用顺序执行，合计配置不超过6。',
}
(HERE/'复验汇总.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
