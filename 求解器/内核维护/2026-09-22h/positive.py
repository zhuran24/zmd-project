from guard import ROOT, OUT, run, digest, save
import json

directory=OUT/'positive';directory.mkdir(exist_ok=True)
source=ROOT/'crates/kernel/tests/fixtures/bridge.json'
document=json.loads(source.read_text())
for ref in [document['catalog'],document['parameters']['axis_registry']]:
    ref['path']=str((source.parent/ref['path']).resolve())
for row in document['initial_state']['nonwarehouse']['value']['inventory']:
    if row['slot'] in ('south_box:storage:0','west_box:storage:0'):
        row['contents']=[{'item':'源矿','quantity':{'value':'4','category':'候选'},'entered_at':None}]
(directory/'positive-input.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
binary=ROOT/'target/debug/kernel';config=ROOT/'规格/内核配置-v1.json'
rows=[]
for name,args,status in [
    ('positive-seed',['seed',str(directory/'positive-input.json'),'--out',str(directory/'seed-output.json')],None),
    ('positive-check',['check',str(directory/'seed-output.json')],'input_checked'),
    ('positive-run',['run',str(directory/'seed-output.json'),'--ticks','6','--out',str(directory/'positive-run.json')],'completed'),
    ('positive-verify-record',['verify-record',str(directory/'positive-run.json')],'input_checked')]:
    code=run(name,[str(binary),*args,'--config',str(config)])
    response=json.loads((OUT/(name+'.log')).read_text())
    rows.append({'name':name,'exit_code':code,'status':response.get('status')})
    assert code==0 and response.get('status')==status,response
record=json.loads((directory/'positive-run.json').read_text())
ticks=record['trace']['ticks'];last=ticks[-1]['state'];inv={r['slot']:r['contents'] for r in last['inventory']}
assert [sum(int(c['quantity']['value']) for c in inv[s]) for s in ['north_box:storage:0','east_box:storage:0']]==[4,4]
# Verify schema for the actual full record, including last_unit on bridge contents.
import jsonschema
jsonschema.Draft202012Validator(json.loads((ROOT/'规格/内核输出.schema.json').read_text())).validate(record)
document['catalog']['sha256']='b573a299c5853dada4189f53b629733f826a535ca011c969c6d658256d9af74c'
(directory/'stale-catalog-input.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
code=run('stale-catalog-negative',[str(binary),'seed',str(directory/'stale-catalog-input.json'),'--config',str(config)])
response=json.loads((OUT/'stale-catalog-negative.log').read_text())
assert code==2 and response['status']=='invalid_input' and any('源文件指纹不符' in x for x in response['open_items']),response
save('positive-validation.json',{'commands':rows,'negative':response,'binary_sha256':digest(binary),'ticks':6,'delivered_north':4,'delivered_east':4,'schema_valid':True})
