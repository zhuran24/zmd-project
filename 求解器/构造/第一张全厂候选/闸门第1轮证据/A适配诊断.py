#!/usr/bin/env python3
"""仅诊断：同一候选、不改正式文件/原检查器，修正版本入口及旧序号映射。
不是原始 A 的通过证书。新增1113位置不冒充由旧A检查。
"""
import sys, os, json, hashlib, copy
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[k]='1'
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
BASE=HERE.parent
sys.path.insert(0,str(BASE/'检查器A'))
import catalog, check_full
original_constraints=catalog.constraints
live=original_constraints()
assert len(live)==72 and live[63]['name']=='1113 位置'
def old_numbering():
    return [dict(r,number=i+1) for i,r in enumerate(x for x in live if x['name']!='1113 位置')]
catalog.constraints=old_numbering
check_full.constraints=old_numbering
assert catalog.HASHES['constraints']=='cf44821f07779490b9b1d913bfb87d7757ae8abfe784c912bb7891868780f7f3'
catalog.HASHES['constraints']='a67c18dec5f6ae59c41e8620d270007f20c2d3e5b202521d0cca12f616bca3df'
raw=(BASE/'生成/候选.json').read_bytes()
r=check_full.make_output(raw)
r['diagnostic_only']={
    'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'changes':['内存中支持指纹设为已核当前72条指纹','当前正式条文按名称排除1113位置后恢复A旧71项编号；未修改任何条文'],
    'not_checked_by_A':['1113 位置'],
    'candidate_unchanged':True,
}
(HERE/'A适配诊断.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
# 直接回放 A 的 Farkas 行乘子，无再次求解。
from geometry import Geometry
from flow import Flow
rr=check_full.Report();g=Geometry(json.loads(raw),rr).build();f=Flow(g).build();f.add_delta()
f.m.le([(f.delta,1)],0,'基础可行性 delta=0')
cert=r['flow']['certificate'];y=[catalog.Q(0)]*len(f.m.rows)
for a in cert['multipliers']: y[a['row']]=catalog.Q(a['value'])
bound=f.m.dual(y,[0]*len(f.m.keys))
assert bound==catalog.Q(cert['bound']) and bound>0
(HERE/'A证书回放.json').write_text(json.dumps({'bound':str(bound),'rows':len(f.m.rows),'variables':len(f.m.keys),'exact_replay':True,'nonzero_multipliers':len(cert['multipliers'])},ensure_ascii=False,indent=2)+'\n')
# provenance 不等于逐项保持B：只删除这一个来源记录，布局和支持不变。
d=json.loads(raw);d['provenance']=[v for v in d['provenance'] if not v['path'].endswith('/候选B/contract.json')]
rr2=check_full.Report();g2=Geometry(d,rr2).build();check_full.check_design(g2,rr2)
(HERE/'A来源误判对照.json').write_text(json.dumps({'scope':'内存元数据反例，非候选修改或新候选','geometry_same':g.channels==g2.channels,'B_feeds_original':next(v for v in r['checks'] if v['id']=='B_feeds'),'B_feeds_without_provenance':rr2.checks.get('B_feeds'),'checks':list(rr2.checks.values())},ensure_ascii=False,indent=2)+'\n')
fixture=json.loads(raw)
fixture['layout']['machines']=[];fixture['layout']['power_poles']=[]
fixture['layout']['warehouse_outlets']=[u for u in fixture['layout']['warehouse_outlets'] if u['id']=='OUT_L00']
fixture['layout']['transport']=[{'id':'BR_TEST','x':1,'y':2,'type':'bridge','H_in':2,'V_in':None}]
fixture['design']['physical_channels']=[]
rc=check_full.Report();gc=Geometry(fixture,rc).build()
(HERE/'单端桥测例.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2)+'\n')
(HERE/'A单端桥对照.json').write_text(json.dumps({'scope':'局部组件反例，非全厂候选','channels':gc.channels,'N4a':rc.checks['N4a'],'N5a':rc.checks['N5a']},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':r['status'],'diagnostic_only':True,'channels':len(g.channels),'flow':r['flow']['reason'],'exact_bound':str(bound)},ensure_ascii=False))
