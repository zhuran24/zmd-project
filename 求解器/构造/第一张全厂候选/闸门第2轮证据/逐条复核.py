#!/usr/bin/env python3
"""对齐本轮三份独立重建、正式逐条台账，并补核无需流见证的否证。"""
import json,hashlib
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent; BASE=HERE.parent; ROOT=BASE.parents[2]
read=lambda n:json.loads((HERE/n).read_text())
def write(n,x):(HERE/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
a=read('A初次.json');b=read('B初次.json');lp=read('独立LP.json');d=read('候选只读快照.json')
sha=hashlib.sha256((HERE/'候选只读快照.json').read_bytes()).hexdigest()
assert a['candidate_sha256']==b['candidate_sha256']==lp['candidate_sha256']==sha
refs=lambda es:sorted((tuple(e['from'][k] for k in ['unit','side','offset']),tuple(e['to'][k] for k in ['unit','side','offset'])) for e in es)
sets=[refs(x) for x in [a['recomputed']['channels'],b['geometry']['physical_channels_rebuilt'],lp['geometry']['physical_channels_rebuilt'],d['design']['physical_channels']]]
assert all(s==sets[0] for s in sets)
assert a['recomputed']['power_coverage']==b['geometry']['powered']==lp['geometry']['power']
g=lp['geometry'];ar=a['recomputed']['maximum_empty_rectangle'];br=b['geometry']['empty_rectangle'];ir=g['empty_rectangle']
assert (ar['area'],ar['short_side'])==(br['area'],br['short_side'])==(ir['area'],ir['short_side'])
assert ar['bounds'] in ir['rectangles'] and br==ir and d['empty_rectangle'] in ir['rectangles']
assert a['recomputed']['occupied_cells']==b['geometry']['occupied_cells']==g['occupied']
lines=(HERE/'正式文件初次快照/求解约束.txt').read_text().splitlines(); formal=[]
for i,s in enumerate(lines):
    if i+1<len(lines) and lines[i+1].lstrip().startswith('据：'):formal.append({'number':len(formal)+1,'name':s.split('：')[0],'line':i+1,'text':s})
assert len(formal)==len(a['formal_constraints'])==len(b['constraints'])
amap={x['name']:x for x in a['formal_constraints']}; bmap={x['name']:x for x in b['constraints']}
bstatus={'PASS_STATIC_PROJECTION':'checked','STATIC_ANTECEDENT_FALSE':'antecedent_false','RUNTIME_PENDING':'runtime_pending','BLOCKED':'blocked','VIOLATION':'violation'}
rank={'violation':0,'blocked':1,'runtime_pending':2,'checked':3,'antecedent_false':4}
comp=[]
for r in formal:
    x=amap[r['name']];y=bmap[r['name']]
    assert x['text']==y['statement']==r['text'] and x['line']==y['line']==r['line'] and x['number']==y['number']==r['number']
    bs=sorted({p['status'] for p in y['checks']});bn=min((bstatus[s] for s in bs),key=rank.get)
    comp.append({**r,'A_status':x['projection_status'],'B_statuses':bs,'B_aggregate_normalized':bn,'status_difference':x['projection_status']!=bn,'A_raw':x,'B_raw':y})
ac={x['id']:x for x in a['checks']}; npids=['N1','N2','N3a','N3b','N4a','N4b','N5a','N5b','P1','P2','P3','P4','P5','P6']
np=[{'id':k,'A':ac.get(k),'B':[x for x in b['checks'] if x['check']==k]} for k in npids]
# Counts are structural upper bounds on any possible positive support, not a claimed flow witness.
inmin=dict(zip(['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机'],[68,51,95,11,6,32,16,15,11]))
outmin=dict(zip(inmin,[95,51,32,6,6,32,32,1,1]))
machines=[]
for u in d['layout']['machines']:
    uid=u['id'];es=d['design']['physical_channels'];inc=[e for e in es if e['to']['unit']==uid];out=[e for e in es if e['from']['unit']==uid]
    machines.append({'id':uid,'model':u['model'],'recipe_ids':u['recipe_ids'],'input_channels':[e['id'] for e in inc],'output_channels':[e['id'] for e in out]})
by_model={m:{'count':g['machine_counts'][m],'input':g['machine_input_channels'][m],'input_min':inmin[m],'output':g['machine_output_channels'][m],'output_min':outmin[m]} for m in inmin}
qualification={m:{'actual':sum(v['model']==m and len(v['input_channels'])>=k for v in machines),'required':n} for m,k,n in [('研磨机',3,31),('塑形机',2,5)]}
# Flow-dependent power upper bounds can be closed by stronger structural bounds on this candidate.
pole_covered=Counter(pid for ids in g['power'].values() for pid in ids)
extra={'machine_channels':by_model,'machines':machines,'qualifying_inputs':qualification,'packaging_inputs':lp['packaging_inputs'],'filling_inputs':lp['filling_inputs'],
       'S':g['S'],'S_min':312,'R':g['R'],'R_min':307,'S_plus_R':g['S']+g['R'],'S_plus_R_min_no_boxes_no_split_merge':624,
       'empty_cells':4900-g['occupied'],'empty_outside_max_rectangle':4900-g['occupied']-ir['area'],
       'max_manufacturers_covered_per_pole':max(pole_covered.values()),'per_pole_cover_count':dict(pole_covered),
       'C59_antecedent_false':d['layout']['core']['x0']!=4 and d['layout']['core']['y0']!=4,
       'C67_no_side_poles':all(v<12 for v in [d['empty_rectangle']['x1']-d['empty_rectangle']['x0']+1,d['empty_rectangle']['y1']-d['empty_rectangle']['y0']+1]),
       'source_ports':g['disconnected_sources'],'product_paths':[x for x in g['path_details'] if x['to']['unit']=='CORE']}
write('结构补核.json',extra)
result={'candidate_sha256':sha,'three_rebuilds_and_declarations_equal':True,'complete_port_refs_compared':len(sets[0]),'power_maps_equal':True,'occupancy_and_rectangle_equal':True,
        'formal_constraints':comp,'normalized_status_difference_numbers':[v['number'] for v in comp if v['status_difference']],'N_P':np,
        'A_checks':dict(Counter(x['status'] for x in a['checks'])),'B_checks':dict(Counter(x['status'] for x in b['checks']))}
write('逐条对照.json',result)
initial=read('输入哈希.json')['files'];changed={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p,h in initial.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h}
version=read('正式版本对照.json')
assert changed=={str(ROOT/'求解约束.txt'):version['current']['求解约束.txt']}
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in version['current'].items())
write('输入稳定性.json',{'files_checked':len(initial),'changed':changed,'candidate_sha256':sha,'live_candidate_matches_snapshot':hashlib.sha256((BASE/'生成/候选.json').read_bytes()).hexdigest()==sha})
write('执行状态.json',{'A初次':{'exit_code':1,'status':a['status']},'B初次':{'exit_code':1,'status':b['status']},'A当前正式版本':{'exit_code':1,'status':read('A当前正式版本.json')['status']},'B当前正式版本':{'exit_code':2,'status':read('B当前正式版本.json')['status']},'独立LP':{'exit_code':0,'strict_solver_status':lp['strict']['status']},'注':'程序退出0表示独立诊断正常完成，不表示LP可行；退出值记录自本轮工具结果。'})
print(json.dumps({k:v for k,v in result.items() if k not in ['formal_constraints','N_P']},ensure_ascii=False))
