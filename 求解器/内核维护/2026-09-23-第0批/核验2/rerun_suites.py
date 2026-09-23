import json,re,sys,os
from audit_guard import *
R=module('suite_runner',REPO/'数据/工具/kernel_regression.py');a=json.loads((IMPL/'isolation-accepted.json').read_text());S=Path(a['source_root'])
def binding():R.check_isolation(IMPL/'isolation-accepted.json',S,a['profile'])
binding()
sys.path.insert(0,str(IMPL));from continuation_runtime import audit_trace
run=OUT/'内核维护/独立回归 中文';run.mkdir(parents=True);evidence=run/'cargo-test-evidence';evidence.mkdir()
(run/'run-registration.json').write_text(json.dumps(dict(run=str(run),evidence=str(evidence),created_empty=True)))
env={'HEALTH_RUN':str(run),'KERNEL_TEST_EVIDENCE_DIR':str(evidence)}
results=[]
def harness(label,h,cwd,environment,expected=0):
    binding();trace=OUT/(label+'.trace.log')
    row=command(label,['strace','-f','-qq','-yy','-s','4096','-e','trace=openat,openat2,execve,chdir','-o',str(trace),h['executable'],'--test-threads=1','--nocapture'],cwd,expected,environment)
    binding();reads=audit_trace(trace,S.parent,[OUT,REPO/'target/health-tests'],executables=[x['executable'] for x in a['harnesses']+a['binaries']]);save(label+'-reads.json',reads)
    if expected==0:
        text=(OUT/(label+'.stdout.log')).read_text();m=re.search(r'test result: ok\. (\d+) passed; (\d+) failed;',text);assert m and int(m[1])==h['listed_tests'] and int(m[2])==0
        row['passed_tests']=int(m[1])
    return row
for round_ in [1,2]:
    for i,h in enumerate(a['harnesses']):
        row=harness(f'guarded-{round_}-{i}-{h["target"]["name"]}',h,S if round_==1 else S.parent,env)
        row.update(round=round_,target=h['target']);results.append(row);save('guarded-suite-results.json',results)
save('guarded-suite-passed.json',dict(passed=True,rounds=2,per_round=[sum(x['passed_tests'] for x in results if x['round']==r) for r in [1,2]],harnesses=len(a['harnesses'])))
h=next(x for x in a['harnesses'] if x['target']['name']=='revision_cli');matrix=[]
matrix.append(harness('matrix-default',h,Path('/tmp'),{}))
for name,value in [('relative','relative'),('history',str(REPO/'crates/kernel/evidence')),('traversal',str(run/'../escape'))]:
    matrix.append(harness('matrix-'+name,h,S,{**env,'KERNEL_TEST_EVIDENCE_DIR':value},101))
shim=OUT/'failing-child';shim.mkdir();p=shim/'python';p.write_text('#!/usr/bin/python -B\nimport os,sys\nif len(sys.argv)>2 and sys.argv[2].endswith("/evidence_paths.py"):os.execv("/usr/bin/python",["/usr/bin/python",*sys.argv[1:]])\nsys.exit(23)\n');p.chmod(0o755)
# The failed shim is a registered executable in this audit output, and its output is retained.
matrix.append(harness('matrix-child-failure',h,S,{**env,'PATH':str(shim)+':'+os.environ['PATH']},101))
code='import subprocess,sys\np=[subprocess.Popen([sys.argv[1],"--test-threads=1","--nocapture"]) for _ in range(2)]\nassert all(x.wait()==0 for x in p)'
binding();matrix.append(command('matrix-concurrent',[sys.executable,'-B','-c',code,h['executable']],S,env=env));binding()
save('matrix-results.json',dict(passed=True,commands=matrix,explicit_chinese_space_and_different_cwd='both guarded rounds',run=str(run)))
