#!/usr/bin/env python3
"""Manifest-driven regression entry point. Run implementations must be hash-bound.

The cases directory contains runner-binding.json and the reviewed capture/guard
implementation. No implicit workspace, profile, output cleanup, or source mapping.
"""
import argparse,hashlib,importlib.util,json,os,stat,sys,uuid
from pathlib import Path

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def implementations(root):
    binding=read(root/'runner-binding.json')
    for rel,expected in binding['files'].items():assert sha(root/rel)==expected,('runner changed',rel)
    sys.path.insert(0,str(root))
    import continuation_aa,continuation_guard
    assert Path(continuation_aa.__file__).resolve().parent==root
    return continuation_aa,continuation_guard

def check_isolation(path,source,profile):
    path=Path(path).resolve();a=read(path);root=path.parent
    assert a['passed'] is True and a['profile']==profile and Path(a['source_root']).resolve()==Path(source).resolve(),'isolation binding mismatch'
    manifest=root/a['source_manifest'];assert sha(manifest)==a['source_manifest_sha256']
    frozen=read(manifest);source_root=Path(frozen['root']);actual={str(p.relative_to(source_root)) for p in source_root.rglob('*')};actual.add('.')
    assert actual==set(frozen['entries']),'source structure changed'
    for rel,row in frozen['entries'].items():
        p=source_root/rel;assert stat.S_IMODE(p.lstat().st_mode)==row['mode']
        assert not p.is_symlink(),'source symlink'
        if row['kind']=='file':assert p.is_file() and sha(p)==row['sha256']
        else:assert row['kind']=='directory' and p.is_dir()
    for h in a['harnesses']+a['binaries']:
        assert sha(h['executable'])==h['sha256'],'binary changed'
        if 'dep_info' in h:
            assert sha(h['dep_info']['path'])==h['dep_info']['sha256']
            for p,digest in h['dep_info']['files'].items():assert sha(p)==digest
    for p,digest in a['scripts'].items():assert sha(p)==digest,'test entry changed'
    runtime=root/a['runtime_manifest'];assert sha(runtime)==a['runtime_manifest_sha256']
    for p,row in read(runtime)['files'].items():assert sha(p)==row['sha256'],'runtime dependency changed'
    implementations(root)
    return a

def field_contract(fields):
    valid={'run-no-output','run-no-output-no-cache','run-no-output-zero','run-no-output-stop','run-no-output-out'};seen=set()
    for row in fields:
        identity=(row['case_id'],row['artifact'],row['pointer']);assert identity not in seen;seen.add(identity)
        assert row['case_id'] in valid and row['pointer']=='/elapsed_ns','unsupported field mapping'
        expected='artifacts/run-no-output-out.json' if row['case_id']=='run-no-output-out' else 'main.stdout.log'
        assert row['artifact']==expected,'wrong measurement artifact'

def captures(path):
    p=Path(path);data=read(p/'index.json' if p.is_dir() else p)
    return data if isinstance(data,list) else [data]

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    c=sub.add_parser('check-isolation');c.add_argument('--acceptance',required=True);c.add_argument('--source-root',required=True);c.add_argument('--profile',required=True)
    t=sub.add_parser('tests');t.add_argument('--out',required=True);t.add_argument('--acceptance')
    for action in ['aa','capture']:
        p=sub.add_parser(action);p.add_argument('--cases',required=True);p.add_argument('--binaries',required=True);p.add_argument('--fields',required=action=='aa');p.add_argument('--out',required=True)
    p=sub.add_parser('compare');p.add_argument('--baseline',required=True);p.add_argument('--candidate',required=True);p.add_argument('--fields',required=True);p.add_argument('--out',required=True)
    args=parser.parse_args()
    if args.action=='check-isolation':
        check_isolation(args.acceptance,args.source_root,args.profile);print('isolation binding verified');return
    raw=Path(args.out);assert raw.is_absolute() and '..' not in raw.parts,'absolute output path required'
    assert not any(x.is_symlink() for x in [raw,*raw.parents]),'symlink output path'
    out=raw.resolve()
    owner=(Path(args.cases).resolve().parent if hasattr(args,'cases') else Path(args.fields).resolve().parent if hasattr(args,'fields') else Path(args.acceptance).resolve().parent if args.acceptance else out.parent)
    assert out.is_relative_to(owner) and out!=owner,'output must belong to manifest run'
    module,guard=implementations(owner);guard.check('entry-output-before')
    assert not out.exists(),'output must be new';out.mkdir(parents=True)
    guard.check('entry-output-after')
    if args.action=='tests':
        receipt=Path(args.acceptance).resolve() if args.acceptance else out.parent/'isolation-accepted.json';a=read(receipt)
        check_isolation(receipt,a['source_root'],a['profile']);module,guard=implementations(receipt.parent);results=[];uid=uuid.uuid4().hex[:12];profile='healthreg'+uid
        shared=['--locked','--offline','-j','2','--profile',profile,'--config',f'profile.{profile}.inherits="dev"','--config',f'profile.{profile}.codegen-units=1']
        steps=[['build','--workspace'],['check','--workspace','--all-targets'],['clippy','--workspace','--all-targets','--message-format=json'],['test','-p','kernel','--lib'],['test','-p','topology','--lib'],['test','-p','kernel','--test','reference'],['test','-p','topology','--test','validation'],['test','-p','kernel','--doc'],['test','-p','topology','--doc']]
        for i,step in enumerate(steps):
            check_isolation(receipt,a['source_root'],a['profile']);argv=['cargo',*step,*shared]
            if step[0]=='test':argv+=['--','--test-threads=1']
            results.append(guard.command('tests-'+uid+'-'+str(i),argv,a['source_root']));check_isolation(receipt,a['source_root'],a['profile'])
        for name in ['revision_cli','revision_r2_cli','revision_r3_cli','revision_r4_cli','revision_r5_cli','round5_cli','round6_cli']:
            h=next(h for h in a['harnesses'] if h['target']['name']==name);check_isolation(receipt,a['source_root'],a['profile'])
            results.append(guard.command('suite-'+uid+'-'+name,[h['executable'],'--test-threads=1'],a['source_root'],env={'HEALTH_RUN':str(receipt.parent),'KERNEL_TEST_EVIDENCE_DIR':str(receipt.parent/'cargo-test-evidence')}));check_isolation(receipt,a['source_root'],a['profile'])
        save(out/'results.json',results);return
    if args.action=='compare':
        root=Path(args.fields).resolve().parent;module,guard=implementations(root);fields=read(args.fields);field_contract(fields)
        aa=captures(args.baseline);bb=captures(args.candidate);assert [x['case_id'] for x in aa]==[x['case_id'] for x in bb]
        save(out/'results.json',[module.compare_capture(a,b,fields) for a,b in zip(aa,bb)]);return
    root=Path(args.cases).resolve().parent;module,guard=implementations(root);cases=read(args.cases);bins=read(args.binaries)
    # The manifest contains every frozen file, not just commit identity.
    frozen_path=Path(bins['kernel'].get('freeze_manifest',root/'continuation-freeze.json'));f=read(frozen_path)
    for row in f['files']:assert sha(Path(f['root'])/row['path'])==row['sha256'],'frozen context changed; rebuild binding before capture'
    for row in bins.values():assert sha(row['path'])==row['sha256'] and row['source_root']==f['source_root']
    uid=uuid.uuid4().hex;results=[];index=[]
    fields=read(args.fields) if args.action=='aa' else []
    if fields:field_contract(fields)
    for case in cases:
        assert case['cwd']==f['source_root'];a=module.capture_case(case,uid+'-a',f,bins);index.append(a)
        if args.action=='aa':b=module.capture_case(case,uid+'-b',f,bins);results.append(module.compare_capture(a,b,fields))
    save(out/'index.json',index)
    if args.action=='aa':save(out/'results.json',results)

if __name__=='__main__':
    try:main()
    except (AssertionError,KeyError,ValueError,OSError) as error:
        print('regression rejected: '+str(error),file=sys.stderr);raise SystemExit(2)
