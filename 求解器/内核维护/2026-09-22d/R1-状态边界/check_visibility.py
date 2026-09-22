#!/usr/bin/env python3
"""Compile-only comparison; all source edits are in a disposable /tmp copy."""
import json, os, re, shutil, subprocess, tempfile
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
env={**os.environ,'CARGO_TARGET_DIR':str(ROOT/'target'),'CARGO_BUILD_JOBS':'6','RAYON_NUM_THREADS':'6','OMP_NUM_THREADS':'6','GIT_OPTIONAL_LOCKS':'0'}
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:6])
with tempfile.TemporaryDirectory(prefix='zmd-r1-visibility-',dir='/tmp') as name:
 work=Path(name)
 for rel in ['Cargo.toml','Cargo.lock','crates/kernel/Cargo.toml','crates/topology/Cargo.toml','数据/正式静态目录.json','数据/候选B/contract.json','规格/内核配置-v1.json']:
  dst=work/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dst)
 for rel in ['crates/kernel/src','crates/topology/src','crates/topology/tests']:
  shutil.copytree(ROOT/rel,work/rel)
 (work/'crates/kernel/tests').mkdir()
 for p in (ROOT/'crates/kernel/tests').glob('*.rs'):shutil.copyfile(p,work/'crates/kernel/tests'/p.name)
 changed={}
 for file,cls in [('engine.rs','Engine'),('input.rs','Input')]:
  p=work/'crates/kernel/src'/file;s=p.read_text()
  m=re.search(r'pub struct '+cls+r' \{(.*?)\n\}',s,re.S)
  body,count=re.subn(r'(?m)^    pub (\w+):',r'    pub(crate) \1:',m[1])
  p.write_text(s[:m.start(1)]+body+s[m.end(1):]);changed[cls]=count
 args=['cargo','check','--locked','--offline','--workspace','--all-targets','-j','6','--message-format=json']
 with (OUT/'visibility-check.json').open('w') as out,(OUT/'visibility-check.log').open('w') as err:
  run=subprocess.run(args,cwd=work,env=env,stdout=out,stderr=err)
 diagnostics=[];artifacts=[]
 for line in (OUT/'visibility-check.json').read_text().splitlines():
  msg=json.loads(line)
  if msg['reason']=='compiler-message' and msg['message']['level']=='error':
   m=msg['message'];diagnostics.append({'target':msg['target']['name'],'test':msg['target']['kind'],'code':m.get('code'),'message':m['message'],'spans':m['spans']})
  if msg['reason']=='compiler-artifact':artifacts.append({'target':msg['target']['name'],'kind':msg['target']['kind'],'profile_test':msg['profile']['test']})
 summary={'changes':'Engine and Input public fields only: pub -> pub(crate)','changed_field_counts':changed,'temporary_copy':name,'source_copy_removed_after_check':True,'argv':args,'cwd':name,'environment':{k:env[k] for k in ['CARGO_TARGET_DIR','CARGO_BUILD_JOBS','RAYON_NUM_THREADS','OMP_NUM_THREADS']},'cpu_affinity':sorted(os.sched_getaffinity(0)),'exit_code':run.returncode,'tests_executed':0,'errors':diagnostics,'artifacts':artifacts}
 (OUT/'visibility-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print('exit:',run.returncode,'fields:',changed,'errors:',len(diagnostics))
 for x in diagnostics:
  loc=[f"{s['file_name']}:{s['line_start']}" for s in x['spans'] if s['is_primary']]
  print(x['target'],x['code']['code'] if x['code'] else '',x['message'],','.join(loc))
 print('successful kernel artifacts:',[a for a in artifacts if a['target']=='kernel'])
 assert run.returncode!=0
 assert diagnostics and all(x['code']['code']=='E0616' for x in diagnostics)
