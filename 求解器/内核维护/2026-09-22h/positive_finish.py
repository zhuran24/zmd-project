from guard import ROOT, OUT, run, digest, save, guard
import json,sys,copy
directory=OUT/'positive';binary=ROOT/'target/debug/kernel';config=ROOT/'规格/内核配置-v1.json'
for name,args in [
    ('positive-run-delivery',['run',str(directory/'seed-output.json'),'--ticks','6','--out',str(directory/'positive-run-delivery.json')]),
    ('positive-verify-record-delivery',['verify-record',str(directory/'positive-run-delivery.json')])]:
    assert run(name,[str(binary),*args,'--config',str(config)])==0
record=json.loads((directory/'positive-run-delivery.json').read_text())
last=record['trace']['ticks'][-1]['state'];inv={r['slot']:r['contents'] for r in last['inventory']}
assert [sum(int(c['quantity']['value']) for c in inv[s]) for s in ['north_box:storage:0','east_box:storage:0']]==[4,4]
guard('schema-before')
sys.path.insert(0,str(ROOT/'数据/样例'))
from test_runtime_input import validate_schema
schema=json.loads((ROOT/'规格/内核输出.schema.json').read_text())
validate_schema(record,schema,schema)
guard('schema-after')
document=json.loads((directory/'positive-input.json').read_text())
document['catalog']['sha256']='b573a299c5853dada4189f53b629733f826a535ca011c969c6d658256d9af74c'
(directory/'stale-catalog-input.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
code=run('stale-catalog-negative',[str(binary),'seed',str(directory/'stale-catalog-input.json'),'--config',str(config)])
response=json.loads((OUT/'stale-catalog-negative.log').read_text())
assert code==2 and response['status']=='invalid_input' and any('源文件指纹不符' in x for x in response['open_items']),response
save('positive-validation.json',{'final_record':str(directory/'positive-run-delivery.json'),'negative':response,'binary_sha256':digest(binary),'ticks':6,'delivered_north':4,'delivered_east':4,'schema_valid':True,'schema_checker':'repository strict validator; complete schema passed without projection'})
