"""Read-only review probes. Only writes JSON/logs beside this script."""
import ast
import collections
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

SOLVER = Path('/home/zhuran24/zmd-research-fresh/求解器')
ROOT = SOLVER.parent
OUT = Path(__file__).resolve().parent
D = SOLVER / '内核维护/2026-09-22d'
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS='0', PYTHONDONTWRITEBYTECODE='1',
           CARGO_TARGET_DIR=str(SOLVER / 'target'), CARGO_BUILD_JOBS='1',
           RUST_TEST_THREADS='1', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1')

def sha(b): return hashlib.sha256(b).hexdigest()
def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
def command(argv):
    p = subprocess.run(argv, cwd=SOLVER, env=ENV, capture_output=True)
    with (OUT / 'commands.jsonl.log').open('a') as f:
        f.write(json.dumps(dict(argv=argv, returncode=p.returncode,
                               stdout=p.stdout.decode(), stderr=p.stderr.decode()), ensure_ascii=False) + '\n')
    return p
def git(*args):
    p = command(['git', '-C', str(ROOT), *args])
    p.check_returncode()
    return p.stdout
def snapshot():
    rows = {}
    skip = {'.git', '.codegraph', 'target', '__pycache__', 'node_modules', '.venv'}
    allow = {SOLVER / '内核维护/代码体检方案.md', D / '审查处理.md'}
    for base in [SOLVER / p for p in ('crates', '数据', '规格', '内核维护')]:
        for parent, dirs, files in os.walk(base, followlinks=False):
            parent = Path(parent)
            dirs[:] = [n for n in dirs if n not in skip and parent / n != OUT]
            for p in [parent] + [parent / n for n in files]:
                if p in allow: continue
                rel = str(p.relative_to(ROOT))
                st = p.lstat()
                if p.is_symlink(): rows[rel] = dict(type='symlink', target=os.readlink(p))
                elif p.is_file():
                    with p.open('rb') as f: h = hashlib.file_digest(f, 'sha256').hexdigest()
                    rows[rel] = dict(type='file', size=st.st_size, mode=st.st_mode, sha256=h)
                else: rows[rel] = dict(type='directory', mode=st.st_mode)
    for p in list(ROOT.glob('*.txt')) + [ROOT / '.gitignore']:
        rows[str(p.relative_to(ROOT))] = dict(type='file', sha256=sha(p.read_bytes()))
    return rows

def probe():
    report = {}
    report['head'] = git('rev-parse', 'HEAD').decode().strip()
    report['plan_before_sha256'] = sha((SOLVER / '内核维护/代码体检方案.md').read_bytes())
    for script, args, dest in [
        ('restore_dryrun.py', [], 'restore-dryrun.json'),
        ('fingerprint_vs_f8.py', ['求解器/crates/kernel/evidence/round6/cli/referenced-zero-prefix.record.json'], 'fingerprint-vs-f8.json')]:
        p = command([sys.executable, '-B', str(D / '审查-opus' / script), *args])
        p.check_returncode()
        dump(dest, json.loads(p.stdout))
    report['commits'] = {}
    for rev in ['7da52a7','a7539f5','220f7b6']:
        lines = git('diff-tree', '--no-commit-id', '--name-status', '-r', rev, '--', '求解器/crates/kernel/evidence').decode().splitlines()
        report['commits'][rev] = dict(collections.Counter(x.split('\t')[0] for x in lines))
    patterns = ["ROOT / 'crates/kernel/evidence/revision-r2'", "ROOT / 'crates/kernel/evidence/round6/regressions/revision-r3'", "ROOT / 'crates/kernel/evidence/revision-r4/cli'", "ROOT / 'crates/kernel/evidence/round6/revision-r5/cli'", "ROOT/'crates/kernel/evidence/round6/cli'"]
    report['wrapper_matches'] = {n: [(SOLVER / 'crates/kernel/tests' / n).read_text().count(p) for p in patterns] for n in ['revision_cli.py','revision_r2_cli.py','revision_r3_cli.py','revision_r4_cli.py','revision_r5_cli.py','round6_cli.py']}
    record = json.loads((D / 'R2-来源与计时/aa/batch/cycle-found.json').read_text())
    report['stale_R2_fingerprints'] = [r['path'] for r in record['fingerprints'] if not Path(r['path']).is_file() or sha(Path(r['path']).read_bytes()) != r['sha256']]
    cert = json.loads((D / 'R2-来源与计时/aa/cycle-found-referenced/a.certificate.json').read_text())
    refs = []
    def walk(x, path=''):
        if isinstance(x, dict):
            if {'path','sha256'} <= x.keys() and not path.startswith(('/fingerprints','/evidence_scope/context_bindings')): refs.append(path)
            for k,v in x.items(): walk(v, path+'/'+str(k))
        elif isinstance(x,list):
            for k,v in enumerate(x): walk(v, path+'/'+str(k))
    walk(cert)
    report['reference_leaves'] = refs
    report['reference_transfer'] = {}
    for name in ['混做粉碎机两下游','分流器三路轮询']:
        d = json.loads((SOLVER / ('数据/样例/'+name+'-参考运行记录.json')).read_text())
        c = collections.Counter((e.get('outcome'),e.get('reason')) for t in d['trace']['ticks'] for e in t['events'] if e.get('operation') == 'transfer')
        report['reference_transfer'][name] = {str(k):v for k,v in c.items()}
    report['new_helpers_exist'] = {p:(SOLVER/p).exists() for p in ['crates/kernel/tests/support/mod.rs','crates/kernel/tests/evidence_paths.py']}
    large = D / 'R4-资源/ring-full-1000.artifact.json'
    report['large_artifact'] = dict(bytes=large.stat().st_size, check_ignore_returncode=command(['git','check-ignore','-v',str(large)]).returncode)
    report['new_output_ignore'] = command(['git','check-ignore','-v',str(SOLVER/'内核维护/体检-example/cargo-test-evidence/output.json')]).stdout.decode()
    dep = SOLVER/'target/debug/deps/kernel-26241e85d1128675.d'
    if dep.exists():
        text = dep.read_text()
        report['dep_info'] = dict(path=str(dep), embedded_catalog='数据/正式静态目录.json' in text, embedded_config='规格/内核配置-v1.json' in text, main_rs='src/main.rs' in text)
    p = command(['cargo','metadata','--locked','--offline','--no-deps','--format-version','1'])
    p.check_returncode()
    report['targets'] = {pkg['name']:[dict(name=t['name'],kind=t['kind']) for t in pkg['targets']] for pkg in json.loads(p.stdout)['packages']}
    p = command(['git','rev-parse','--git-path','hooks/post-commit'])
    hook = Path(p.stdout.decode().strip())
    if not hook.is_absolute(): hook = SOLVER / hook
    report['hook'] = dict(path=str(hook.resolve()), exists=hook.is_file(), text=hook.read_text() if hook.is_file() else None)
    dump('facts.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    if sys.argv[1] == 'before':
        rows = snapshot(); dump('protected-before.json',rows)
        print('protected_entries',len(rows))
    elif sys.argv[1] == 'after':
        before = json.loads((OUT/'protected-before.json').read_text()); after = snapshot()
        diff = {p:dict(before=before.get(p),after=after.get(p)) for p in before.keys()|after.keys() if before.get(p)!=after.get(p)}
        dump('protection-diff.json',diff); print('protected_differences',len(diff))
    else: probe()
