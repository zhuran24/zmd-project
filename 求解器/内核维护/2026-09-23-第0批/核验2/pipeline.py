import json,os,subprocess,sys,time
from pathlib import Path
O=Path(__file__).resolve().parent
pid=json.loads((O/'suite-process.json').read_text())['pid']
while Path('/proc',str(pid)).exists():time.sleep(1)
assert (O/'matrix-results.json').is_file(),'Suite/matrix stage failed; inspect rerun-suites.log'
for script,argv in [('audit_bindings.py',[]),('probe_isolation.py',[]),('probe_comparator.py',[]),('rerun_production.py',[]),('audit_retained.py',['fresh'])]:
    print('START',script,flush=True)
    with (O/(script+'.pipeline.log')).open('wb') as log:
        p=subprocess.run([sys.executable,'-B',str(O/script),*argv],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    print('FINISH',script,p.returncode,flush=True)
    assert p.returncode==0,script
(O/'pipeline-passed.json').write_text(json.dumps({'passed':True}))
