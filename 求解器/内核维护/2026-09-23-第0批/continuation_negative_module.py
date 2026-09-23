import json,os,tempfile,shutil
from pathlib import Path
from continuation_guard import *
from continuation_closure import dependencies,compare_checker
f=json.loads((RUN/'continuation-freeze.json').read_text());copy=Path(tempfile.mkdtemp(prefix='kernel-health-unregistered-'));original=Path(f['root'])
for row in f['files']:
 p=original/row['path'];assert sha(p)==row['sha256'];dst=copy/row['path'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
S=copy/'求解器';p=S/'crates/kernel/src/lib.rs';p.write_bytes(p.read_bytes()+b'\nmod health_unregistered;\n');(p.parent/'health_unregistered.rs').write_text('pub const OMITTED_FROM_CHECKER: u8 = 0;\n')
profile='health0negative'+str(os.getpid());args=['cargo','build','--locked','--offline','--workspace','--bins','-j','2','--profile',profile,'--config',f'profile.{profile}.inherits="dev"','--config',f'profile.{profile}.codegen-units=1','--message-format=json']
command('continue-negative-module-build',args,S)
rows=[json.loads(x) for x in (RUN/'continue-negative-module-build.stdout.log').read_text().splitlines() if x.startswith('{')]
art=[x for x in rows if x.get('reason')=='compiler-artifact' and str(S) in x.get('manifest_path','')]
closures={};info=[]
for a in art:
 assert not a['fresh'];d,deps=dependencies(a,S);closures[a['target']['name']+':'+a['target']['kind'][0]]=deps;info.append(dict(artifact=a,dep_info=str(d),sha256=sha(d),dependencies=sorted(deps)))
binding=json.loads((RUN/'continuation-probe-binding.json').read_text());record=json.loads((Path(binding['output'])/'record.json').read_text())
try:compare_checker(closures,record,S)
except AssertionError as error:result=dict(passed=True,rejected=True,error=str(error),injected_module=str(S/'crates/kernel/src/health_unregistered.rs'),source_root=str(S),profile=profile,artifacts=info)
else:raise AssertionError('Unregistered production module accepted')
assert str(S/'crates/kernel/src/health_unregistered.rs') in closures['kernel:lib']
write(RUN/'continuation-compile-closure-negative.json',result);check('negative-module-final');print('Unregistered compiled module rejected')
