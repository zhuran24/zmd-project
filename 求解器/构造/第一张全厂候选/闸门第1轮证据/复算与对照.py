#!/usr/bin/env python3
"""独立读取落盘矩阵/证书，复算零流上界，并逐名称对齐全部正式条目。"""
import json,hashlib,sys,copy
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict,Counter
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE.parents[2]
def read(name):return json.loads((HERE/name).read_text())
def write(name,data):(HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
a=read('A适配诊断.json');b=read('B原始.json');lp=read('独立LP.json');matrix=read('独立LP矩阵.json');d=json.loads((BASE/'生成/候选.json').read_text())
def edges(xs):return sorted((tuple(e['from'][k] for k in ['unit','side','offset']),tuple(e['to'][k] for k in ['unit','side','offset'])) for e in xs)
aa=edges(a['recomputed']['channels']);bb=edges(b['geometry']['physical_channels_rebuilt']);cc=edges(lp['geometry']['physical_channels_rebuilt']);dd=edges(d['design']['physical_channels'])
assert aa==bb==cc==dd
assert a['recomputed']['power_coverage']==b['geometry']['powered']==lp['geometry']['power']
assert (a['recomputed']['maximum_empty_rectangle']['area'],a['recomputed']['maximum_empty_rectangle']['short_side'])==(48,6)
assert b['geometry']['empty_rectangle']==lp['geometry']['empty_rectangle']
assert a['candidate_sha256']==b['candidate_sha256']==lp['candidate_sha256']==hashlib.sha256((BASE/'生成/候选.json').read_bytes()).hexdigest()
rows={r['name']:r for r in matrix['rows']};assert len(rows)==len(matrix['rows'])
contradictions=[]
for name,r in rows.items():
    if not r['terms'] and (F(r['rhs'])!=0 if r['relation']=='eq' else F(r['rhs'])<0):contradictions.append(name)
assert len(contradictions)==37
cert=lp['source_relaxed_max_total_channel_flow']['certificate'];col=defaultdict(F);rhs=F(0)
for y in cert['multipliers']:
    r=rows[y['row']];v=F(y['value']);assert not r['name'].startswith('target:')
    relation='le' if r['name'].startswith('source:') else r['relation']
    if relation=='le':assert v<=0
    for j,k in r['terms']:col[j]+=v*F(k)
    rhs+=v*F(r['rhs'])
obj=[F(-1) if k[0]=='flow' else F(0) for k in matrix['variables']]
assert all(col[j]<=c for j,c in enumerate(obj)) and rhs==0
# zero is feasible in precisely the source<=1, no target relaxation.
for r in rows.values():
    if r['name'].startswith('target:'):continue
    relation='le' if r['name'].startswith('source:') else r['relation']
    assert (F(r['rhs'])==0 if relation=='eq' else F(r['rhs'])>=0)
for uid,rid in [(u['id'],r) for u in d['layout']['machines'] for r in u['recipe_ids']]:
    # all recipes produce a nonzero output: zero physical flow forces batches zero.
    assert any(r['name'].startswith('machine:'+uid+':out:') and any(matrix['variables'][j]==['batch',uid,rid] and F(v)<0 for j,v in r['terms']) for r in rows.values())
write('独立证书回放.json',{'candidate_sha256':lp['candidate_sha256'],'matrix_variables':len(matrix['variables']),'matrix_rows':len(rows),'zero_row_contradictions':contradictions,'strict_infeasible_exact':True,'relaxed_zero_primal_exact':True,'relaxed_total_flow_upper_bound':'0','dual_columns_checked':len(obj),'dual_multipliers':len(cert['multipliers']),'rhs':'0','all_batches_forced_zero':True})
# B metadata-only counterexample: register the existing single-recipe choice under its required spelling.
sys.path.insert(0,str(BASE/'检查器B'))
import catalog,geometry,interfaces
fixture=read('单端桥测例.json');fc=geometry.Checks();fg=geometry.Geometry(fixture['layout'],fc);geometry.structural(fixture,fg,fc)
ac=read('A单端桥对照.json')
assert len(ac['channels'])==0 and ac['N5a']['status']=='checked'
assert len(fg.edges)==1 and any(v['check']=='N5a' and v['status']=='FAIL' for v in fc.records)
write('B单端桥对照.json',{'scope':'局部组件反例，非全厂候选','channels':fg.edges,'checks':[v for v in fc.records if v['check'] in ['N4a','N5a']]})
c=geometry.Checks();g=geometry.Geometry(d['layout'],c);geometry.structural(d,g,c)
d2=copy.deepcopy(d)
for r in d2['design']['restrictions']:
    if r['id']=='all-single-recipe':r['id']='recipe-subsets';r['statement']=interfaces.EXTRA['recipe-subsets']
c1=geometry.Checks();interfaces.check_interfaces(d,g,c1)
c2=geometry.Checks();interfaces.check_interfaces(d2,g,c2)
reg=lambda c:next(r for r in c.records if r['check']=='recipe-restriction-register')
assert reg(c1)['status']=='FAIL' and reg(c2)['status']=='PASS'
write('B登记拼写对照.json',{'scope':'仅内存中限制ID/statement更名，未改候选文件','geometry_same':d['layout']==d2['layout'],'channel_support_same':d['design']['physical_channels']==d2['design']['physical_channels'],'original':reg(c1),'spelling_normalized':reg(c2),'other_unimplemented_ids':[r['check'] for r in c2.records if r['status']=='UNIMPLEMENTED']})
# Verify current formal file by content, not only catalog numbering.
lines=(ROOT/'求解约束.txt').read_text().splitlines();current=[]
for i,s in enumerate(lines):
    if i+1<len(lines) and lines[i+1].lstrip().startswith('据：'):current.append({'number':len(current)+1,'name':s.split('：')[0],'line':i+1,'text':s})
assert len(current)==72
ar={r['name']:r for r in a['formal_constraints']};br={r['name']:r for r in b['constraints']}
formal=[]
for r in current:
    s=br[r['name']];assert s['line']==r['line'] and s['statement']==r['text']
    formal.append({**r,'A_diagnostic':ar.get(r['name'],{}).get('projection_status','unsupported'),'B_parts':sorted({v['status'] for v in s['checks']}),'A_evidence':ar.get(r['name']),'B_evidence':s})
write('逐条对照.json',{'same_candidate':True,'three_rebuilds_equal':True,'declarations_equal':True,'channels':len(aa),'power_maps_equal':True,'rectangles_equal':True,'formal_constraints':formal,'N_P':{'A':[{k:v for k,v in x.items() if k in ['id','status','derived_from']} for x in a['checks'] if x['id'] in catalog.N_IDS+catalog.P_IDS],'B':[{k:v for k,v in x.items() if k in ['check','status']} for x in b['checks'] if x['check'] in catalog.N_IDS+catalog.P_IDS+['P2-paths','P2-rate']]}})
original=read('输入哈希.json');diff={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p,rec in original.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=rec['sha256']}
baseline=read('最终复跑输入哈希.json');final_diff={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p,rec in baseline.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=rec['sha256']}
assert not final_diff
assert set(diff)=={'求解器/构造/第一张全厂候选/检查器A/projections.py'}
write('输入稳定性.json',{'checked_files':len(original),'changes_since_start':diff,'changes_since_final_rerun':final_diff,'candidate_sha256':lp['candidate_sha256']})
print(json.dumps({'three_rebuilds_equal':True,'channels':len(aa),'constraints_compared':len(formal),'strict_exact_contradictions':len(contradictions),'relaxed_total_flow_exact_max':'0','original_files_unchanged':len(original)-len(diff),'final_run_inputs_unchanged':len(baseline),'metadata_counterexample':'B original FAIL -> spelling-normalized PASS'},ensure_ascii=False))
