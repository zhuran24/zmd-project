#!/usr/bin/env python3
"""从工作区运行命令并保存argv、退出码和日志；编译仅使用共享target。"""
from pathlib import Path
import subprocess,json,os,sys,time
R=Path.cwd();O=R/'内核维护/2026-09-22'; env=os.environ.copy();env.update(CARGO_TARGET_DIR=str(R/'target'),PYTHONDONTWRITEBYTECODE='1',KERNEL_TEST_EVIDENCE_DIR=str(O/'cargo-test-evidence'));env['PATH']=str(O/'bin')+os.pathsep+env['PATH']
commands={
 'build':['cargo','build','--workspace'],
 'build-release':['cargo','build','--release','--workspace'],
 'test':['cargo','test','--workspace'],
 'integration':['cargo','test','--workspace','--tests','--no-fail-fast'],
 'clippy':['cargo','clippy','--workspace','--all-targets','--message-format=json'],
 'catalog':['/usr/bin/python','-B','数据/工具/formal_catalog.py'],
 'catalog-tests':['/usr/bin/python','-B','数据/工具/test_formal_catalog.py'],
 'samples':['/usr/bin/python','-B','数据/样例/check_examples.py','--self-test','--report',str(O/'sample-check.json')],
}
for name in sys.argv[1:]:
 start=time.monotonic();argv=commands[name]
 log_path=O/(name+'.log')
 if log_path.exists():
  i=1
  while (O/(name+f'.attempt-{i}.log')).exists():i+=1
  log_path.rename(O/(name+f'.attempt-{i}.log'))
 with log_path.open('w') as log:p=subprocess.run(argv,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT)
 row={'name':name,'argv':argv,'cwd':str(R),'exit_code':p.returncode,'seconds':round(time.monotonic()-start,3),'log':name+'.log','CARGO_TARGET_DIR':env['CARGO_TARGET_DIR']}
 with (O/'commands.jsonl.log').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 print(json.dumps(row,ensure_ascii=False),flush=True)
