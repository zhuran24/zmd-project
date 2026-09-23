import json,os,sys,shutil,tempfile
from audit_guard import *
sys.path.insert(0,str(IMPL))
import continuation_aa as aa
from continuation_closure import dependencies,compare_checker
from continuation_runtime import verify as verify_runtime,audit_trace
f=json.loads((OUT/'own-freeze.json').read_text());F=Path(f['root']);S=Path(f['source_root']);profile='healthaudit2prod'+str(os.getpid())
capturebase=REPO/'target/health-capture'/('audit2-'+str(os.getpid()));capturebase.mkdir()
def args(p):return ['--locked','--offline','-j','2','--profile',p,'--config',f'profile.{p}.inherits="dev"','--config',f'profile.{p}.codegen-units=1']
def artifacts(label,source):
    return [r for line in (OUT/(label+'.stdout.log')).read_text().splitlines() if line.startswith('{') and (r:=json.loads(line)).get('reason')=='compiler-artifact' and Path(r['manifest_path']).is_relative_to(source)]
def sourcecheck():
    for r in f['files']:assert sha(F/r['path'])==r['sha256']
def buildcheck():
    b=json.loads((IMPL/'continuation-build-inputs.json').read_text())
    for p,h in b['files'].items():assert sha(p)==h,('build dependency changed',p)
    verify_runtime()
sourcecheck();buildcheck();command('production-a',['cargo','build','--workspace','--bins',*args(profile),'--message-format=json'],S)
art=artifacts('production-a',S);bins={};seal=capturebase/'production-a';seal.mkdir()
for a in art:
    assert not a['fresh']
    if a.get('executable'):
        p=Path(a['executable']);assert str(S).encode() in p.read_bytes();shutil.copyfile(p,seal/a['target']['name'])
        bins[a['target']['name']]=dict(path=str(p),sha256=sha(p),source_root=str(S),profile=profile,sealed=str(seal/a['target']['name']))
save('own-binaries.json',bins);save('production-a-artifacts.json',art)
sourcecheck();buildcheck()
oldf=json.loads((IMPL/'continuation-freeze.json').read_text());oldbins=json.loads((IMPL/'binaries.json').read_text());cases=json.loads((IMPL/'cases.json').read_text())
def replace(v,oldcase,newcase):
    if isinstance(v,str):
        for name,b in oldbins.items():v=v.replace(b['path'],bins[name]['path'])
        return v.replace(oldf['root'],str(F)).replace(oldcase,newcase)
    if isinstance(v,list):return [replace(x,oldcase,newcase) for x in v]
    if isinstance(v,dict):return {replace(k,oldcase,newcase):replace(x,oldcase,newcase) for k,x in v.items()}
    return v
cases=[replace(c,c['root'],str(capturebase/'cases'/c['id'])) for c in cases];(capturebase/'cases').mkdir()
for c in cases:
    c['input_hashes']={p:sha(p) for p in c['input_hashes']};assert c['cwd']==str(S)
fields=json.loads((IMPL/'comparison-fields.json').read_text())
save('own-cases.json',cases);save('own-fields.json',fields)
aa.RUN=OUT;aa.command=command;aa.check=protect
results=[];captures=[]
for case in cases:
    a=aa.capture_case(case,'a',f,bins);b=aa.capture_case(case,'b',f,bins)
    results.append(aa.compare_capture(a,b,fields));captures.extend([a,b]);save('own-aa-results.json',results);save('own-capture-index.json',captures)
    print('A/A',case['id'],'PASS',flush=True)
sourcecheck();buildcheck()
# Same-version validators run while A source bytes still exist. Restore only our own sealed files.
receipts=[]
for label in ['a','b']:
    docs=[];roots=[];caps=[x for x in captures if x['label']==label]
    for cap in caps:
        root=Path(cap['root']);assert not root.exists();shutil.copytree(cap['sealed'],root);roots.append(root)
        for rel,row in cap['files'].items():
            p=root/rel;assert sha(p)==row['sha256'];raw=p.read_bytes()
            if raw.lstrip().startswith(b'{'):
                obj=aa.strict_loads(raw)
                if obj.get('schema') in ['kernel-output-v4','kernel-cycle-v3']:docs.append((cap['case_id'],p,obj))
    schema_code='import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from verify_all import schema_check;schema_check([Path(x) for x in sys.argv[2:]])'
    command('schema-all-'+label,[sys.executable,'-B','-c',schema_code,str(S/'crates/kernel/tests'),*[str(p) for _,p,_ in docs]],S,env={'KERNEL_BIN':bins['kernel']['path']})
    covered={(p.parent/o['run_record_ref']['path']).resolve() for _,p,o in docs if o['schema']=='kernel-cycle-v3' and o.get('run_record_ref')}
    for i,(cid,p,obj) in enumerate(docs):
        if p.resolve() in covered:
            receipts.append(dict(case_id=cid,label=label,path=str(p),sha256=sha(p),verified_by='containing cycle'));continue
        mode='verify-cycle' if obj['schema']=='kernel-cycle-v3' else 'verify-record';expected=2 if mode=='verify-record' and obj['status']!='completed' else 0
        row=command(f'verify-{label}-{i}',[bins['kernel']['path'],mode,str(p),'--config',str(S/'规格/内核配置-v1.json')],S,expected)
        receipts.append(dict(case_id=cid,label=label,path=str(p),sha256=sha(p),mode=mode,expected=expected,returncode=row['returncode']));save('own-validation-receipts.json',receipts)
    for cap,root in zip(caps,roots):
        dest=capturebase/'validated'/label/cap['case_id'];dest.parent.mkdir(parents=True,exist_ok=True);root.rename(dest)
save('own-validation-receipts.json',receipts)
record=json.loads((Path(next(x for x in captures if x['case_id']=='run-full' and x['label']=='a')['sealed'])/'artifacts/run-full.json').read_text())
closures={};closed=[]
for a in art:
    d,deps=dependencies(a,S);closures[a['target']['name']+':'+a['target']['kind'][0]]=deps
    closed.append(dict(target=a['target'],dep_info=str(d),dep_info_sha256=sha(d),dependencies={p:sha(p) for p in sorted(deps)}))
checker_paths=[str(Path(x['path']).resolve()) for x in record['fingerprints'] if x['role']=='checker' and x['path'].endswith('.rs')]
assert len(checker_paths)==len(set(checker_paths)) and all(Path(x).is_relative_to(S/'crates/kernel/src') for x in checker_paths)
assert {p for p in closures['kernel:bin'] if p.endswith('.rs')}==set(checker_paths)
assert {p for p in closures['kernel:lib'] if p.endswith('.rs')}==set(checker_paths)-{str(S/'crates/kernel/src/main.rs')}
assert compare_checker(closures,record,S);save('own-closure-positive.json',dict(passed=True,artifacts=closed,checker_files=len(checker_paths)))
# Preserve the original retained A binaries too; compare their actual bytes independently.
oldart=json.loads((IMPL/'continuation-production-a-artifacts.json').read_text());oldcompare=[]
for a in oldart:
    if a.get('executable'):
        p=Path(a['executable']);q=Path(a['sealed']);oldcompare.append(dict(name=a['target']['name'],sealed=str(q),current=str(p),sha256=sha(q),byte_equal=q.read_bytes()==p.read_bytes(),expected=a['sha256']))
assert len(oldcompare)==2 and all(x['byte_equal'] and x['sha256']==x['expected'] for x in oldcompare);save('retained-production-bytes.json',oldcompare)
sourcecheck();buildcheck();overlay=[]
for row in json.loads((IMPL/'continuation-b-overlay.json').read_text()):
    dest=S/row['path'];before=sha(dest) if dest.exists() else None;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/row['path'],dest)
    overlay.append(dict(path=row['path'],before=before,after=sha(dest)))
for crate in ['kernel','topology']:
    for name in ['lib.rs','main.rs']:os.utime(S/'crates'/crate/'src'/name,None)
command('production-b',['cargo','build','--workspace','--bins',*args(profile),'--message-format=json'],S)
bb=artifacts('production-b',S);comparisons=[]
for a in bb:
    assert not a['fresh']
    if a.get('executable'):
        old=bins[a['target']['name']];assert old['path']==a['executable'];equal=Path(old['sealed']).read_bytes()==Path(a['executable']).read_bytes()
        comparisons.append(dict(name=a['target']['name'],a_sha256=old['sha256'],b_sha256=sha(a['executable']),byte_equal=equal))
assert len(comparisons)==2 and all(x['byte_equal'] for x in comparisons);buildcheck()
save('own-production-equivalence.json',dict(passed=True,source_root=str(S),profile=profile,overlay=overlay,binaries=comparisons))
# Real compilation of an omitted module in another disposable source copy.
negative=Path(tempfile.mkdtemp(prefix='kernel-audit2-negative-'));shutil.copytree(F,negative/'tree');N=negative/'tree/求解器'
p=N/'crates/kernel/src/lib.rs';p.write_bytes(p.read_bytes()+b'\nmod audit_unregistered;\n');(p.parent/'audit_unregistered.rs').write_text('pub const AUDIT_MODULE: u8 = 0;\n')
np='healthaudit2negative'+str(os.getpid());command('negative-module',['cargo','build','--workspace','--bins',*args(np),'--message-format=json'],N)
nc={};nd=[]
for a in artifacts('negative-module',N):
    d,deps=dependencies(a,N);nc[a['target']['name']+':'+a['target']['kind'][0]]=deps;nd.append(dict(target=a['target'],dep_info=str(d),dependencies=sorted(deps)))
try:compare_checker(nc,record,N)
except AssertionError as e:reason=str(e)
else:raise AssertionError('Unregistered compiled module accepted')
assert str(N/'crates/kernel/src/audit_unregistered.rs') in nc['kernel:lib']
assert 'audit_unregistered.rs' in reason and 'lib_missing' in reason
save('own-closure-negative.json',dict(passed=True,rejected=True,reason=reason,source_root=str(N),profile=np,artifacts=nd))
save('production-aa-passed.json',dict(passed=True,aa_pairs=len(results),same_path_same_profile=True,compiled_negative_rejected=True))
