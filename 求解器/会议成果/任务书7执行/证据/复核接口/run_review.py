#!/usr/bin/env python3
"""Read reviewed inputs; write all reproduction outputs under this review evidence directory."""
from pathlib import Path
import sys,json,subprocess,datetime,hashlib,types,runpy
sys.dont_write_bytecode=True
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器')
E=Path(__file__).resolve().parent

def run(label,argv,expected=0):
 argv=list(map(str,argv)); started=datetime.datetime.now().astimezone().isoformat()
 p=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True)
 row={'label':label,'cwd':str(ROOT),'argv':argv,'started':started,'exit_code':p.returncode,'expected_exit_code':expected,'stdout':p.stdout,'stderr':p.stderr}
 dest=E/'commands.json'; rows=json.loads(dest.read_text()) if dest.exists() else [];rows.append(row);dest.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
 (E/(label+'.log')).write_text(p.stdout+p.stderr)
 print(label,'exit',p.returncode,flush=True)
 assert p.returncode==expected,row
 return p

if __name__=='__main__':
 what=sys.argv[1]
 if what=='build':
  run('build',['cargo','build','--release','-p','kernel','--target-dir',ROOT/'target'])
  b=ROOT/'target/release/kernel';(E/'build-binding.json').write_text(json.dumps({'binary':str(b),'sha256':hashlib.sha256(b.read_bytes()).hexdigest()},indent=2)+'\n')
 elif what in ('author-cases','supplemental'):
  module=types.ModuleType('run_command');module.ROOT=ROOT;module.E=E;module.run=run;sys.modules['run_command']=module
  script='validate_cases.py' if what=='author-cases' else 'supplemental_checks.py'
  runpy.run_path(str(ROOT/'会议成果/任务书7执行/证据/内核'/script),run_name='__main__')
 elif what=='original-batch':
  run('original-batch',[ROOT/'target/release/kernel','verify-batch',ROOT/'会议成果/任务书7执行/证据/内核/runs','--config',ROOT/'规格/内核配置-v1.json'])
