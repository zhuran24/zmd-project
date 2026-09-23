"""B production byte comparison, two safe rounds, and guarded copy isolation."""
import json,os,re,shutil,subprocess,sys
from pathlib import Path
from continuation_guard import *
from continuation_closure import dependencies
from continuation_runtime import verify as verify_runtime,audit_trace

f=json.loads((RUN/'continuation-freeze.json').read_text());S=Path(f['source_root']);F=Path(f['root'])

def frozen(snapshot):
    diff=g.changes(snapshot,g.scan(F))
    assert not diff,('frozen source changed',diff)

def cargo_args(profile):
    return ['--locked','--offline','-j','2','--profile',profile,'--config',f'profile.{profile}.inherits="dev"','--config',f'profile.{profile}.codegen-units=1']

def artifacts(label):
    rows=[json.loads(x) for x in (RUN/(label+'.stdout.log')).read_text().splitlines() if x.startswith('{')]
    return [x for x in rows if x.get('reason')=='compiler-artifact' and str(S) in x.get('manifest_path','')]

def stage_b():
    assert json.loads((RUN/'continuation-a-final.json').read_text())['passed'],'A must finish before replacing its source context'
    for row in f['files']:assert sha(F/row['path'])==row['sha256']
    verify_runtime()
    from continuation_build_inputs import bind,verify as verify_build
    bound=bind();verify_build()
    command('continue-rustc-version',['rustc','-Vv'],S)
    command('continue-cargo-version',['cargo','-V'],S)
    for crate in ['kernel','topology']:
        for name in ['lib.rs','main.rs']:os.utime(S/'crates'/crate/'src'/name,None)
    command('continue-production-a-rebound',['cargo','build','--workspace','--bins',*cargo_args(f['continuation_profile']),'--message-format=json'],S)
    rebound=artifacts('continue-production-a-rebound');old=json.loads((RUN/'continuation-production-a-artifacts.json').read_text())
    for a in rebound:
        if a.get('executable'):
            before=next(x for x in old if x['target']['name']==a['target']['name'] and x.get('executable'))
            assert not a['fresh'] and sha(a['executable'])==before['sha256'] and Path(a['executable']).read_bytes()==Path(before['sealed']).read_bytes()
    verify_build();write(RUN/'continuation-production-a-rebound.json',dict(passed=True,artifacts=rebound,build_input_manifest_sha256=sha(RUN/'continuation-build-inputs.json'),reason='A source context still intact; current toolchain-bound rebuild is byte-identical to the A binary used in all sealed captures'))
    check('b-overlay-before')
    paths=['数据/工具/test_formal_catalog.py','crates/kernel/tests/evidence_paths.py','crates/kernel/tests/support/mod.rs','crates/kernel/tests/benchmark_round6.py']
    for name in ['revision_cli','revision_r2_cli','revision_r3_cli','revision_r4_cli','revision_r5_cli','round5_cli','round6_cli']:
        paths.append('crates/kernel/tests/'+name+'.rs')
        if name!='round5_cli':paths.append('crates/kernel/tests/'+name+'.py')
    overlay=[];seal=REPO/'target/health-capture/continuation-20260923/production-a-test-sources';seal.mkdir()
    for rel in paths:
        source=REPO/rel;dest=S/rel;old=sha(dest) if dest.exists() else None
        if dest.exists():backup=seal/rel;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,backup)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        overlay.append(dict(path=rel,before=old,after=sha(dest)))
    write(RUN/'continuation-b-overlay.json',overlay)
    # Force actual recompilation while preserving source bytes; same physical root/profile/environment as A.
    for crate in ['kernel','topology']:
        for name in ['lib.rs','main.rs']:os.utime(S/'crates'/crate/'src'/name,None)
    snapshot=g.scan(F);write(RUN/'continuation-b-source.json',snapshot);check('b-overlay-after')
    label='continue-production-b';command(label,['cargo','build','--workspace','--bins',*cargo_args(f['continuation_profile']),'--message-format=json'],S)
    art=artifacts(label);before=json.loads((RUN/'continuation-production-a-artifacts.json').read_text());results=[]
    for a in art:
        assert not a['fresh'];assert Path(a['manifest_path']).resolve().is_relative_to(S)
        if a.get('executable'):
            old=next(x for x in before if x['target']['name']==a['target']['name'] and x.get('executable'))
            assert old['executable']==a['executable'];equal=Path(old['sealed']).read_bytes()==Path(a['executable']).read_bytes()
            results.append(dict(name=a['target']['name'],before=old['sha256'],after=sha(a['executable']),byte_equal=equal,path=a['executable']))
    write(RUN/'production-byte-equivalence.json',dict(passed=all(x['byte_equal'] for x in results),profile=f['continuation_profile'],source_root=str(S),binaries=results));assert len(results)==2 and all(x['byte_equal'] for x in results)
    write(RUN/'continuation-production-b-artifacts.json',art);frozen(snapshot);verify_runtime();verify_build();return snapshot

def safe(snapshot):
    profile='health0bsafe'+str(os.getpid());results=[]
    steps=[('build',['build','--workspace']),('check',['check','--workspace','--all-targets']),('clippy',['clippy','--workspace','--all-targets','--message-format=json']),('kernel-lib',['test','-p','kernel','--lib']),('topology-lib',['test','-p','topology','--lib']),('reference',['test','-p','kernel','--test','reference']),('validation',['test','-p','topology','--test','validation']),('kernel-doc',['test','-p','kernel','--doc']),('topology-doc',['test','-p','topology','--doc'])]
    for round_ in [1,2]:
        for name,args in steps:
            frozen(snapshot);verify_runtime();argv=['cargo',*args,*cargo_args(profile)]
            if args[0]=='test':argv+=['--','--test-threads=1']
            row=command(f'continue-frozen-safe-{round_}-{name}',argv,S);frozen(snapshot);verify_runtime();results.append(row);write(RUN/'continuation-frozen-safe-results.json',results)
    write(RUN/'continuation-safe-passed.json',dict(passed=True,rounds=2,commands=18,profile=profile,source_root=str(S),source_manifest_sha256=sha(RUN/'continuation-b-source.json')))

def harnesses(snapshot):
    profile='health0isolation'+str(os.getpid());label='continue-copy-test-build'
    command(label,['cargo','test','--workspace','--tests','--no-run',*cargo_args(profile),'--message-format=json'],S)
    art=artifacts(label);tests=[a for a in art if a.get('executable') and a['profile']['test']]
    command('continue-copy-metadata',['cargo','metadata','--locked','--offline','--no-deps','--format-version','1'],S)
    metadata=json.loads((RUN/'continue-copy-metadata.stdout.log').read_text())
    expected={(p['manifest_path'],t['name'],tuple(t['kind'])) for p in metadata['packages'] for t in p['targets'] if t['test']}
    actual={(a['manifest_path'],a['target']['name'],tuple(a['target']['kind'])) for a in tests};assert expected==actual,(expected,actual)
    for a in art:
        assert not a['fresh'] and Path(a['manifest_path']).resolve().is_relative_to(S) and Path(a['target']['src_path']).resolve().is_relative_to(S)
        if a.get('executable'):
            path=Path(a['executable']);assert str(S).encode() in path.read_bytes();a['sha256']=sha(path)
            if a['profile']['test']:
                d=path.with_suffix('.d');raw=d.read_text().replace('\\\n','');from continuation_closure import words
                hits=[]
                for line in raw.splitlines():
                    match=re.search(r'(?<!\\):(?:\s|$)',line)
                    if match and str(path) in words(line[:match.start()]):hits.append(words(line[match.start()+1:]))
                assert len(hits)==1
                deps=[(S/x).resolve() for x in hits[0]];assert len(deps)==len(set(deps)) and all(x.is_relative_to(F) and x.is_file() for x in deps)
                a['dep_info']=dict(path=str(d),sha256=sha(d),files={str(x):sha(x) for x in deps})
    write(RUN/'test-harnesses.json',tests);write(RUN/'continuation-test-artifacts.json',art);write(RUN/'continuation-test-profile.json',dict(profile=profile,source_root=str(S),metadata=metadata))
    frozen(snapshot)
    for i,a in enumerate(tests):
        command('continue-list-'+str(i),[a['executable'],'--list'],S)
        listing=(RUN/('continue-list-'+str(i)+'.stdout.log')).read_text();count=re.search(r'(\d+) tests?, (\d+) benchmarks?',listing);assert count;a['listed_tests']=int(count[1])
    write(RUN/'test-harnesses.json',tests)
    return profile,tests,art

def run_harness(label,a,snapshot,cwd,env,expected=0,argv=None):
    assert sha(a['executable'])==a['sha256'];frozen(snapshot);verify_runtime();trace=RUN/(label+'.trace.log')
    row=command(label,['strace','-f','-qq','-yy','-s','4096','-e','trace=openat,openat2,execve,chdir','-o',str(trace),*(argv or [a['executable'],'--test-threads=1','--nocapture'])],cwd,expected,env)
    reads=audit_trace(trace,F,[RUN,REPO/'target/health-tests'],executables=[x['executable'] for x in json.loads((RUN/'continuation-test-artifacts.json').read_text()) if x.get('executable')])
    write(RUN/(label+'.reads.json'),reads);frozen(snapshot);verify_runtime()
    if expected==0:
        stdout=(RUN/(label+'.stdout.log')).read_text();match=re.search(r'test result: ok\. (\d+) passed; (\d+) failed;',stdout);assert match and int(match[1])==a['listed_tests'] and int(match[2])==0
    return row

def isolation(snapshot,profile,tests,art):
    explicit={'HEALTH_RUN':str(RUN),'KERNEL_TEST_EVIDENCE_DIR':str(RUN/'cargo-test-evidence')}
    results=[]
    for round_ in [1,2]:
        for i,a in enumerate(tests):
            label=f'continue-isolation-{round_}-{i}-{a["target"]["name"]}'
            row=run_harness(label,a,snapshot,S if round_==1 else F,explicit)
            results.append(dict(round=round_,target=a['target'],count=a['listed_tests'],command=label,passed=True));write(RUN/'continuation-isolation-rounds.json',results)
    a=next(a for a in tests if a['target']['name']=='revision_cli')
    # No-config path, Chinese/space path and failed subprocess use the same built harness.
    assert 'KERNEL_TEST_EVIDENCE_DIR' not in os.environ
    run_harness('continue-matrix-default',a,snapshot,Path('/tmp'),{})
    run=RUN/'matrix/内核维护/中文 空格';run.mkdir(parents=True);evidence=run/'cargo-test-evidence';evidence.mkdir()
    write(run/'run-registration.json',dict(run=str(run),evidence=str(evidence),created_empty=True));chinese={'HEALTH_RUN':str(run),'KERNEL_TEST_EVIDENCE_DIR':str(evidence)}
    run_harness('continue-matrix-chinese',a,snapshot,F,chinese)
    shim=RUN/'matrix/failing-child';shim.mkdir();p=shim/'python';p.write_text('#!/usr/bin/python -B\nimport os,sys\nif len(sys.argv)>2 and sys.argv[2].endswith("/evidence_paths.py"): os.execv("/usr/bin/python",["/usr/bin/python",*sys.argv[1:]])\nsys.exit(23)\n');p.chmod(0o755)
    run_harness('continue-matrix-child-failure',a,snapshot,S,{**explicit,'PATH':str(shim)+':'+os.environ['PATH']},expected=101)
    for name,value in [('relative','relative'),('history',str(REPO/'crates/kernel/evidence')),('traversal',str(RUN/'../escape'))]:
        run_harness('continue-matrix-illegal-'+name,a,snapshot,S,{**explicit,'KERNEL_TEST_EVIDENCE_DIR':value},expected=101)
    # Concurrent instances, both within the observer's same four-CPU affinity.
    runner=RUN/'matrix/concurrent.py';runner.write_text('import os,subprocess,sys\np=[subprocess.Popen([sys.argv[1],"--test-threads=1","--nocapture"],env=os.environ.copy()) for _ in range(2)]\nassert all(x.wait()==0 for x in p)\n')
    row=command('continue-matrix-concurrent',[sys.executable,'-B',str(runner),a['executable']],S,env=explicit);frozen(snapshot);verify_runtime()
    scripts={str(REPO/row['path']):sha(REPO/row['path']) for row in json.loads((RUN/'continuation-b-overlay.json').read_text())}
    acceptance=dict(passed=True,source_root=str(S),profile=profile,source_manifest='continuation-b-source.json',source_manifest_sha256=sha(RUN/'continuation-b-source.json'),harnesses=tests,binaries=[x for x in art if x.get('executable') and not x['profile']['test']],runtime_manifest='continuation-runtime-dependencies.json',runtime_manifest_sha256=sha(RUN/'continuation-runtime-dependencies.json'),scripts=scripts,runner_sha256=sha(__file__),bounded_probes_sha256=sha(RUN/'continuation-fresh-isolation-probes.json'),matrix=['two_full_rounds','explicit','default','different_cwd','Chinese_space','child_failure','illegal_relative','illegal_history','illegal_traversal','two_concurrent_instances'],actual_passed_per_round=sum(a['listed_tests'] for a in tests),original_workspace_suites=False,context='frozen formal sources verified equal to active formal sources; external research-file drift separately recorded')
    write(RUN/'isolation-accepted.json',acceptance);check('isolation-final');print('ISOLATION PASSED',acceptance['actual_passed_per_round'])


def bounded_probes(snapshot):
    source=(RUN/'核验/probe_isolation.py').read_text()
    old='from audit_files import ROOT,OUT,IMPL,save,sha'
    assert source.count(old)==1
    replacement="from continuation_guard import RUN,sha,write\nROOT=Path("+repr(str(F))+")\nIMPL=RUN\nOUT=Path(tempfile.mkdtemp(prefix='kernel-health-bounded-'))\ndef save(name,data): write(RUN/('continuation-fresh-'+name),data)"
    source=source.replace(old,replacement)
    path=RUN/'continuation_bounded_probes.py';path.write_text(source)
    command('continue-fresh-bounded-probes',[sys.executable,'-B',str(path)],S)
    result=json.loads((RUN/'continuation-fresh-isolation-probes.json').read_text());assert result['all_bounded_checks_pass']
    frozen(snapshot)

def main():
    snapshot=stage_b();bounded_probes(snapshot);safe(snapshot);profile,tests,art=harnesses(snapshot);isolation(snapshot,profile,tests,art)

if __name__=='__main__':main()
