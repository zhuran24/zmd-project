#!/usr/bin/env python3
"""证据目录内的版本适配诊断。保留原A/B字节，不替换原始CLI认证结果。
只允许本轮已审查的72条版本转换，且只适用于本轮无箱候选。
"""
import os,sys,json,hashlib
from pathlib import Path
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[k]='1'
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
which=sys.argv[1]
assert which in ['A','B']
raw=(HERE/'候选只读快照.json').read_bytes();d=json.loads(raw)
old='a67c18dec5f6ae59c41e8620d270007f20c2d3e5b202521d0cca12f616bca3df'
new='0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f'
assert not d['layout']['storage_boxes'] and d['source_fingerprints']['constraints']==new
current=(HERE/'正式文件快照/求解约束.txt').read_text()
assert hashlib.sha256(current.encode()).hexdigest()==new
tail='；仓库已经满格且不会再出库的非成品，不因开启传输而被禁止经箱子的物理端口中转'
anchor='此条件分别适用于每种传输相位和固定判定次序'
assert current.count(anchor)==1
restored=current.replace(anchor+'。',anchor+tail+'。')
assert hashlib.sha256(restored.encode()).hexdigest()==old
sys.path.insert(0,str(HERE/('检查器'+which)))
import catalog
assert catalog.HASHES['constraints']==old
catalog.ROOT=HERE/'正式文件快照'
catalog.HASHES={**catalog.HASHES,'constraints':new}
adaptation={'kind':'reviewed version adapter; diagnostic only','original_checker_unchanged':True,
 'original_supported_constraints':old,'reviewed_constraints':new,'change':'仅第33条删除仓库满格非成品物理中转说明句；当前无箱，前件不成立。',
 'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'not_original_cli_acceptance':True}
if which=='A':
    import check_full
    result=check_full.make_output(raw,60)
    code=0 if result['static_pass'] else 1 if result['status']=='rejected' else 2
else:
    rows=json.loads((catalog.BASE/'constraint_catalog.json').read_text())
    lines=current.splitlines();parsed=[]
    for i,s in enumerate(lines):
        if i+1<len(lines) and lines[i+1].lstrip().startswith('据：'):
            parsed.append({'number':len(parsed)+1,'name':s.split('：')[0],
              'statement':s,'basis':lines[i+1].strip()[2:],'line':i+1})
    assert len(rows)==len(parsed)==72
    differences=[i+1 for i,(a,b) in enumerate(zip(rows,parsed)) if a!=b]
    assert differences==[33]
    assert {k:v for k,v in rows[32].items() if k!='statement'}=={k:v for k,v in parsed[32].items() if k!='statement'}
    assert rows[32]['statement'].replace(tail,'')==parsed[32]['statement']
    catpath=HERE/'当前约束目录.json';catpath.write_text(json.dumps(parsed,ensure_ascii=False,indent=2)+'\n')
    catalog.CONSTRAINT_PROFILES={**catalog.CONSTRAINT_PROFILES,new:str(catpath)}
    import check
    result=check.check_document(d,verify_sources=True,time_limit=60)
    result['candidate_sha256']=hashlib.sha256(raw).hexdigest()
    result['candidate_hash_basis']='exact input file bytes'
    code=0 if result['status']=='STATIC_PASS' else 1 if result['status']=='REJECTED' else 2
result['version_adapter']=adaptation
(HERE/(which+'适配复核.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'exit_code':code,'version_adapter':True,'flow_status':(result.get('flow') or {}).get('status')},ensure_ascii=False))
sys.exit(code)
