import json, subprocess, time
from pathlib import Path
v=Path(__file__).resolve().parent;s=v.parents[2]
binary=v/'cargo-target/debug/kernel';config=s/'规格/内核配置-v1.json'
def run(dir,label,args,expected=0):
    cmd=[str(binary),*map(str,args),'--config',str(config)]
    start=time.monotonic();p=subprocess.run(cmd,cwd=s,capture_output=True)
    (dir/(label+'.stdout')).write_bytes(p.stdout);(dir/(label+'.stderr')).write_bytes(p.stderr)
    row={'label':label,'argv':cmd,'exit':p.returncode,'expected':expected,'seconds':time.monotonic()-start}
    with (v/'case-commands.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    if p.returncode!=expected:
        diagnostic=None
        if '--out' in cmd:
            output=Path(cmd[cmd.index('--out')+1])
            if output.exists():diagnostic=json.loads(output.read_text()).get('open_items')
        raise AssertionError({'label':label,'exit':p.returncode,'diagnostic':diagnostic})
    return p
results=[]
for case in json.loads((v/'cases.json').read_text()):
    d=v/'cases'/case['name']
    try:
        run(d,'seed',['seed',d/'input.json','--out',d/'seed.json'])
        run(d,'check',['check',d/'seed.json'])
        run(d,'run',['run',d/'seed.json','--ticks',case['ticks'],'--out',d/'record.json'])
        run(d,'verify-record',['verify-record',d/'record.json'])
        results.append({'case':case['name'],'cli_pass':True})
    except Exception as e:results.append({'case':case['name'],'cli_pass':False,'error':str(e)})
    print(json.dumps(results[-1]),flush=True)
(v/'case-cli-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
