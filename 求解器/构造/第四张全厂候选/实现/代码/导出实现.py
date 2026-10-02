#!/usr/bin/env python3
"""把按实际进路优化器的坐标导出为逐格可核查的静态候选。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6})
import sys,json
from pathlib import Path
from export_candidate import make
from static_check import audit,digest
B=Path(__file__).resolve().parents[1]

def convert(path):
    src=json.loads(Path(path).read_text());contract=json.loads((B/'逻辑接法.json').read_text())
    poses={u['id']:dict(x0=u['x'],y0=u['y'],x1=u['x']+u['w']-1,y1=u['y']+u['h']-1,Din=u['d'],kind='machine' if u['type']<=2 else 'core' if u['type']==3 else 'outlet' if u['type']==4 else 'pole') for u in src['units']}
    paths=[]
    for p in src['paths']:
        if not p['cells']:continue
        e=contract['logical_feeds'][p['r']];paths.append(dict(e,start=[*p['source'][:2],(p['source'][2]+2)%4],end=[*p['target'][:2],(p['target'][2]+2)%4],cells=[q[:2] for q in p['cells']]))
    raw=dict(status='FEASIBLE',W=70,H=70,placements=poses,paths=paths)
    data=make(raw,contract,False);data['candidate_id']='s2-fourth-implementation'
    # 桥接器相邻读法与S2B绑定；两轴和所有逆向通道逐条保留。
    data['schema']='full-factory-static-s2-bridges-v2'
    data['temporary_rules_sha256']=digest(B/'依据快照/临时规则.md')
    data['design']['class']='s2_isolated_paths'
    data['design'].setdefault('bridge_reverse_channels',[])
    data['design']['restrictions']=[dict(id='S2B-fixed-contract',source=['dynamic','numeric'],statement='固定第107轮第2节230台、325条进路，桥接器按轴独立；相邻桥逆向通道允许。',coverage_loss='不覆盖其他机器分工、植物分组或共享运输格的布局。',release_obligations='改变接法后须重新给出调试与所有可达循环态达标证明。',failure_scope='只报告本候选实际坐标与通道的检查结果；缺路、搜索超时不证明全类不可行。')]
    return data,contract

if __name__=='__main__':
    data,c=convert(sys.argv[1]);out=Path(sys.argv[2]);out.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n')
    r=audit(data,c,True);r['candidate_sha256']=digest(out);r['source_search_sha256']=digest(sys.argv[1])
    out.with_suffix('.check.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k in ['static_pass','local_checks_pass','statistics']},ensure_ascii=False))
