import copy,hashlib,json,subprocess,time
from pathlib import Path
v=Path(__file__).resolve().parent;s=v.parents[2]
def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def q(n):return {'value':str(n),'category':'候选'}
def run(label,args,expected=0):
    argv=[str(v/'cargo-target/debug/kernel'),*map(str,args),'--config',str(s/'规格/内核配置-v1.json')]
    p=subprocess.run(argv,cwd=s,capture_output=True)
    (v/'logs'/(label+'.stdout')).write_bytes(p.stdout);(v/'logs'/(label+'.stderr')).write_bytes(p.stderr)
    assert p.returncode==expected,(label,p.returncode,p.stdout,p.stderr)
    commands.append({'label':label,'argv':argv,'exit':p.returncode})
    return p
commands=[];d=v/'positive';d.mkdir(exist_ok=True)
fixture=s/'crates/kernel/tests/fixtures/bridge.json';raw=load(fixture)
raw['catalog']['path']=str((fixture.parent/raw['catalog']['path']).resolve())
raw['parameters']['axis_registry']['path']=str((fixture.parent/raw['parameters']['axis_registry']['path']).resolve())
for row in raw['initial_state']['nonwarehouse']['value']['inventory']:
    row['contents']=[]
    if row['slot'] in ['south_box:storage:0','west_box:storage:0']:
        row['contents']=[{'item':'源矿','quantity':q(4),'entered_at':None}]
save(d/'input.json',raw)
run('positive-seed',['seed',d/'input.json','--out',d/'seed.json'])
run('positive-check',['check',d/'seed.json'])
run('positive-run',['run',d/'seed.json','--ticks','6','--out',d/'record.json'])
run('positive-replay',['verify-record',d/'record.json'])
record=load(d/'record.json');inventory=record['trace']['ticks'][-1]['state']['inventory']
final={r['slot']:sum(int(c['quantity']['value']) for c in r['contents']) for r in inventory}
assert final['north_box:storage:0']==4 and final['east_box:storage:0']==4,final
assert sum(final.values())==8
negatives=[]
head=load(v/'before.json')['head'];oldsha=hashlib.sha256(subprocess.check_output(['git','show',head+':求解器/数据/正式静态目录.json'],cwd=s)).hexdigest()
raw=load(v/'cases/straight/input.json')
for kind in ['old-catalog','axis-overcapacity','legacy-direction']:
    negative=copy.deepcopy(raw)
    if kind=='old-catalog':negative['catalog']['sha256']=oldsha
    elif kind=='axis-overcapacity':
        for row in negative['initial_state']['nonwarehouse']['value']['inventory']:
            row['contents']=[]
            if row['slot']=='b:vertical:0':row['contents']=[{'item':'源矿','quantity':q(2),'entered_at':{'kind':'rational','value':q(-1)}}]
    else:
        next(u for u in negative['layout']['units'] if u['id']=='b')['bridge_axes']={'vertical':{'status':'resolved','input_side':'south','basis':['旧方向负对照']},'horizontal':{'status':'resolved','input_side':'west','basis':['旧方向负对照']}}
    save(d/(kind+'-input.json'),negative)
    run(kind,['seed',d/(kind+'-input.json'),'--out',d/(kind+'-result.json')],2)
    result=load(d/(kind+'-result.json'));assert result['status']=='invalid_input'
    reason='\n'.join(result['open_items'])
    assert {'old-catalog':'源文件指纹不符','axis-overcapacity':'容量','legacy-direction':'bridge_axes'}[kind] in reason,reason
    negatives.append({'case':kind,'status':result['status'],'reason':reason})
save(v/'positive-negative-result.json',{'positive_chain_pass':True,'ticks':6,'north_box':4,'east_box':4,'negative_cases':negatives,'commands':commands})
print(json.dumps({'positive_chain_pass':True,'north_box':4,'east_box':4,'negative_cases':negatives},ensure_ascii=False,indent=2))
