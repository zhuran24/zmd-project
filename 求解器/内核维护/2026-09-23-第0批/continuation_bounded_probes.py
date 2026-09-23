"""Bounded allocator/import/fixture probes; never runs a CLI suite or kernel binary."""
import ast,hashlib,importlib,json,os,subprocess,sys,tempfile,uuid
from pathlib import Path
from continuation_guard import RUN,sha,write
ROOT=Path('/tmp/kernel-health-20260923-_5s65pp9')
IMPL=RUN
OUT=Path(tempfile.mkdtemp(prefix='kernel-health-bounded-'))
def save(name,data): write(RUN/('continuation-fresh-'+name),data)
TESTS=ROOT/'求解器/crates/kernel/tests'
sys.path.insert(0,str(TESTS))
names=['revision_cli','revision_r2_cli','revision_r3_cli','revision_r4_cli','revision_r5_cli','round6_cli']
# Actual imports with writes/process launch denied, in one fresh -B process per module.
code='''import importlib,os,sys\nsys.path.insert(0,sys.argv[1])\ndef guard(event,args):\n if event=='open':\n  mode=args[1];flags=args[2]\n  if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):raise RuntimeError('write denied: '+str(args[0]))\n if event in ['os.mkdir','os.remove','os.rmdir','os.rename','os.symlink','subprocess.Popen','os.system','os.exec','os.posix_spawn']:raise RuntimeError('side effect denied: '+event)\nsys.addaudithook(guard)\nm=importlib.import_module(sys.argv[2]);assert callable(m.main)\nprint('import and explicit main: pass')\n'''
imports=[]
for n in names:
 p=subprocess.run([sys.executable,'-B','-c',code,str(TESTS),n],capture_output=True,text=True,cwd='/tmp',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONOPTIMIZE='0'))
 imports.append({'module':n,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
helper=importlib.import_module('evidence_paths')
run=OUT/'probes/内核维护/中文 空格';run.mkdir(parents=True)
evidence=run/'cargo-test-evidence';evidence.mkdir()
registration={'run':str(run),'evidence':str(evidence),'created_empty':True};(run/'run-registration.json').write_text(json.dumps(registration))
os.environ['HEALTH_RUN']=str(run);os.environ['KERNEL_TEST_EVIDENCE_DIR']=str(evidence);os.environ.pop('KERNEL_TEST_INSTANCE_DIR',None)
first=helper.allocate('audit_probe');second=helper.allocate('audit_probe')
positive={'two_instances_unique':first!=second,'explicit_paths':[str(first),str(second)]}
os.environ['KERNEL_TEST_INSTANCE_DIR']=str(first)
positive['rust_to_python_style_instance']=str(helper.instance_dir('audit_probe'))
negative=[]
def reject(label,fn):
 try:fn()
 except (ValueError,FileNotFoundError,KeyError) as e:negative.append({'case':label,'rejected':True,'error':str(e)})
 else:negative.append({'case':label,'rejected':False})
reject('reused_instance',lambda:helper.instance_dir('audit_probe'))
for value in ['relative',str(ROOT/'求解器/crates/kernel/evidence'),str(OUT/'probes/../escape')]:
 os.environ['KERNEL_TEST_EVIDENCE_DIR']=value;reject('illegal_root:'+value,helper.output_root)
os.environ['KERNEL_TEST_EVIDENCE_DIR']=str(evidence)
link=OUT/'probes/link';link.symlink_to(run,target_is_directory=True)
reject('ancestor_symlink',lambda:helper.real_directory(link/'cargo-test-evidence'))
os.environ.pop('KERNEL_TEST_INSTANCE_DIR',None);os.environ.pop('KERNEL_TEST_EVIDENCE_DIR',None)
positive['default_target_instance']=str(helper.allocate('audit_default'))
# No kernel calls: main is stopped immediately after both required fixture validations.
m=importlib.import_module('revision_r3_cli')
class ReachedAllocation(Exception):pass
def stop(name):raise ReachedAllocation(name)
m.instance_dir=stop
original_root=m.ROOT
fixture_rel=Path('crates/kernel/复核/r3-规格保真-证据')
fns=['gate-expired-after-closure-input.json','tiny-expired-cycle.json'];fixture_checks=[]
tmproot=Path(tempfile.mkdtemp(prefix='kernel-audit-fixtures-'))
for label,missing,wrong in [('both_valid',None,None),('missing_first',0,None),('wrong_first',None,0),('missing_second',1,None),('wrong_second',None,1)]:
 root=tmproot/label;(root/fixture_rel).mkdir(parents=True)
 for i,n in enumerate(fns):
  if i!=missing:(root/fixture_rel/n).write_bytes(b'{}' if i==wrong else (original_root/fixture_rel/n).read_bytes())
 m.ROOT=root
 try:m.main()
 except ReachedAllocation as e:result={'reached_allocator':True,'error':str(e)}
 except (AssertionError,FileNotFoundError) as e:result={'reached_allocator':False,'error':str(e)}
 else:raise AssertionError('main escaped sentinel')
 fixture_checks.append({'case':label,**result,'passed':result['reached_allocator']==(label=='both_valid')})
# Matrix coverage is intentionally not claimed: no harness has been built or accepted.
res={'imports':imports,'positive':positive,'negative':negative,'fixture_prefix':fixture_checks,'fixture_sandbox':str(tmproot),'full_cli_executed':False,'scope':'allocator functions, import side-effect denial, and mandatory fixture prefix only','all_bounded_checks_pass':all(r['exit_code']==0 for r in imports) and all(r['rejected'] for r in negative) and all(r['passed'] for r in fixture_checks)}
save('isolation-probes.json',res);print(json.dumps({'imports_pass':sum(r['exit_code']==0 for r in imports),'negative_root_checks':len(negative),'fixture_checks_pass':sum(r['passed'] for r in fixture_checks),'all_pass':res['all_bounded_checks_pass']},ensure_ascii=False))
