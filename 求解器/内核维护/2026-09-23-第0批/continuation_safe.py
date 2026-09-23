import json,os
from pathlib import Path
from continuation_guard import *
profile='health0continue'+str(os.getpid())
args=['--locked','--offline','-j','2','--profile',profile,'--config',f'profile.{profile}.inherits="dev"','--config',f'profile.{profile}.codegen-units=1']
steps=[('build',['build','--workspace']),('check',['check','--workspace','--all-targets']),('clippy',['clippy','--workspace','--all-targets','--message-format=json']),('kernel-lib',['test','-p','kernel','--lib']),('topology-lib',['test','-p','topology','--lib']),('reference',['test','-p','kernel','--test','reference']),('validation',['test','-p','topology','--test','validation']),('kernel-doc',['test','-p','kernel','--doc']),('topology-doc',['test','-p','topology','--doc'])]
write(RUN/'continuation-safe-plan.json',dict(source_root=str(REPO),profile=profile,steps=steps,rounds=2))
results=[]
for n in [1,2]:
 for name,cmd in steps:
  argv=['cargo',*cmd,*args]
  if cmd[0]=='test':argv+=['--','--test-threads=1']
  row=command(f'continue-safe-{n}-{name}',argv)
  results.append(row);write(RUN/'continuation-safe-results.json',results)
write(RUN/'continuation-safe-passed.json',dict(passed=True,rounds=2,commands=len(results),profile=profile))
