from probe_common import *
import shutil
base=json.loads((OUT/'baseline.json').read_text());BIN=Path(base['binaries']['kernel']['path']);TOPO=Path(base['binaries']['topology']['path'])
CFG=ROOT/'规格/内核配置-v1.json';INPUT=ROOT/'数据/样例/生产循环环带.json'
ART=OUT/'aa/artifacts';ART.mkdir(parents=True,exist_ok=True)
BATCH=OUT/'aa/batch';BATCH.mkdir(parents=True,exist_ok=True)
results=[]
def pair(name,args,files=(),expected=None):
 argv=list(map(str,args));captured=[];binary_sha=sha(argv[0]);snapshots=[]
 for label in ['a','b']:
  r=run('aa/'+name+'/'+label,argv);captured.append(r);snap={}
  for key,path in files:
   if Path(path).exists():
    raw=Path(path).read_bytes();(OUT/'aa'/name/(label+'.'+key+'.json')).write_bytes(raw);snap[key]=raw
  snapshots.append(snap)
 row=dict(name=name,argv=argv,shell_command=shlex.join(argv),binary_sha256=binary_sha,exit_codes=[r.returncode for r in captured],exit_equal=captured[0].returncode==captured[1].returncode,stdout=byte_diff(captured[0].stdout,captured[1].stdout),stderr=byte_diff(captured[0].stderr,captured[1].stderr),files={k:byte_diff(snapshots[0].get(k,b''),snapshots[1].get(k,b'')) for k,_ in files},expected_exit=expected)
 row['unexpected_exit']=expected is not None and any(r.returncode!=expected for r in captured)
 assert sha(argv[0])==binary_sha
 results.append(row);dump(OUT/'aa/results.json',results)
 print(name,row['exit_codes'],{k:[d['path'] for d in v.get('json_differences',[])] for k,v in {'stdout':row['stdout'],'stderr':row['stderr'],**row['files']}.items() if not v['byte_equal']},flush=True)
 return captured

def k(name,command,path,opts=(),files=(),expected=0):return pair(name,[BIN,command,path,'--config',CFG,*opts],files,expected)
def main():
 k('seed','seed',INPUT)
 k('seed-out','seed',INPUT,['--out',ART/'seed.json'],[('seed',ART/'seed.json')])
 k('check','check',INPUT)
 k('check-cycle-domain','check',INPUT,['--cycle-domain'])
 k('request-fixed','request','time.domain')
 # Explicit stopped and invalid axis request paths, as well as the accepted request.
 axes=json.loads(CFG.read_text())['axes']
 stop_axis=next(k for k,v in axes.items() if v['disposition']=='超出覆盖即停')
 k('request-stop','request',stop_axis,expected=2)
 k('request-invalid','request','r2.unknown.axis',expected=2)
 for name,input_path,ticks in [('run-full',INPUT,12),('run-grinder',ROOT/'数据/样例/混做粉碎机两下游.json',4),('run-splitter',ROOT/'数据/样例/分流器三路轮询.json',12)]:
  p=ART/(name+'.json');k(name,'run',input_path,['--ticks',ticks,'--out',p],[('record',p)])
 p=ART/'run-delta.json';k('run-delta','run',INPUT,['--ticks',12,'--format','checkpoint_delta','--checkpoint-interval',3,'--out',p],[('record',p)])
 p=ART/'run-no-cache.json';k('run-no-cache','run',INPUT,['--ticks',12,'--no-cache','--out',p],[('record',p)])
 k('run-no-output','run',INPUT,['--ticks',20,'--no-output'])
 k('run-no-output-no-cache','run',INPUT,['--ticks',20,'--no-output','--no-cache'])
 k('run-no-output-zero','run',INPUT,['--ticks',0,'--no-output'])
 k('run-no-output-stop','run',INPUT,['--ticks',20,'--max-sweeps',1,'--no-output'],expected=2)
 p=ART/'run-no-output-out.json';k('run-no-output-out','run',INPUT,['--ticks',20,'--no-output','--out',p],[('measurement',p)])
 p=ART/'run-stopped.json';k('run-stopped','run',INPUT,['--ticks',20,'--max-sweeps',1,'--out',p],[('record',p)],expected=2)
 k('verify-record-full','verify-record',ART/'run-full.json')
 k('verify-record-delta','verify-record',ART/'run-delta.json')
 p=ART/'checkpoint-record.json';k('checkpoint-record','checkpoint',ART/'run-full.json',['--out',p],[('seed',p)])
 p=BATCH/'cycle.json';rp=BATCH/'cycle.record.json';k('cycle-referenced','cycle',INPUT,['--max-ticks',20,'--search-checkpoint-interval',3,'--out',p],[('certificate',p),('record',rp)])
 k('cycle-no-record','cycle',INPUT,['--max-ticks',20,'--no-record'])
 k('cycle-budget','cycle',INPUT,['--max-ticks',1,'--no-record'])
 k('cycle-sweep-stop','cycle',INPUT,['--max-ticks',20,'--max-sweeps',1,'--no-record'])
 k('verify-cycle','verify-cycle',BATCH/'cycle.json')
 p=ART/'checkpoint-cycle.json';k('checkpoint-cycle','checkpoint',BATCH/'cycle.json',['--out',p],[('seed',p)])
 shutil.copyfile(ART/'run-full.json',BATCH/'finite-record.json')
 pair('verify-batch',[BIN,'verify-batch',BATCH,'--config',CFG],expected=0)
 # Malformed input and malformed CLI are separate from normal successful executions.
 bad=ART/'bad-input.json';dump(bad,{})
 for command in ['seed','check','run','cycle','verify-record','verify-cycle','checkpoint']:
  opts=[]
  files=[]
  if command=='run':opts=['--ticks',1,'--no-output']
  if command=='cycle':opts=['--max-ticks',1,'--no-record']
  k(command+'-invalid-input',command,bad,opts,files,expected=2)
 pair('cli-no-args',[BIN],expected=2)
 pair('cli-unknown-command',[BIN,'r2-unknown',INPUT],expected=2)
 pair('topology-contract',[TOPO,ROOT/'数据/候选B/contract.json'])
 pair('topology-invalid',[TOPO,bad],expected=2)
 dump(OUT/'aa/summary.json',{'pairs':len(results),'unexpected_exits':[r['name'] for r in results if r['unexpected_exit']],'unstable':[{'name':r['name'],'output':key,'differences':value.get('json_differences',value)} for r in results for key,value in {'stdout':r['stdout'],'stderr':r['stderr'],**r['files']}.items() if not value['byte_equal']],'binary_sha256_before':base['binaries'],'binary_sha256_after':{'kernel':sha(BIN),'topology':sha(TOPO)}})

if __name__=='__main__':main()
