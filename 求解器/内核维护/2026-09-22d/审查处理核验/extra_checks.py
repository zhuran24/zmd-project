"""Read-only historical search and raw JSON checks; no CLI tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOLVER = Path('/home/zhuran24/zmd-research-fresh/求解器')
D = SOLVER/'内核维护/2026-09-22d'
OUT = Path(__file__).parent
def sha(b): return hashlib.sha256(b).hexdigest()
def run(args):
    p = subprocess.run(args,cwd=SOLVER,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0',PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
    with (OUT/'extra-commands.jsonl.log').open('a') as f:
        f.write(json.dumps(dict(argv=args,returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()),ensure_ascii=False)+'\n')
    return p
rows = json.loads((D/'审查-opus/unresolved_targets.json').read_text())
expr = []
for n in sorted({r['before_bytes'] for r in rows}):
    if expr: expr.append('-o')
    expr.extend(['-size',str(n)+'c'])
p = run(['find','/home','/tmp','/var/tmp','/mnt','/media','/opt','/srv','-xdev','-type','f','(',*expr,')','-print0'])
matches = []
for name in p.stdout.split(b'\0'):
    if not name: continue
    path = Path(os.fsdecode(name))
    try:
        h = sha(path.read_bytes())
        targets = [r['path'] for r in rows if r['before_sha256'] == h]
        matches.append(dict(path=str(path),sha256=h,targets=targets))
    except OSError as exc: matches.append(dict(path=str(path),error=str(exc)))
q = run(['python','-B',str(D/'审查-opus/git_object_search.py'),str(SOLVER.parent),'/home/zhuran24/zmd-project-cc','/home/zhuran24/.claude/skills','/home/zhuran24/文档/ChatGPT/New project'])
record_path = D/'R2-来源与计时/aa/batch/cycle-found.record.json'
raw = record_path.read_bytes()
alternate = raw + b' '
certificate = json.loads((D/'R2-来源与计时/aa/cycle-found-referenced/a.certificate.json').read_text())
historical = json.loads((D/'审查-opus/restore_dryrun-after-1857.json').read_text())
source = json.loads((D/'R2-来源与计时/source/summary.json').read_text())
cache = json.loads((D/'R2-来源与计时/cache-origin/summary.json').read_text())
report = dict(find_returncode=p.returncode,find_stderr=p.stderr.decode(),size_candidates=matches,
    git_objects=json.loads(q.stdout),
    json_byte_probe=dict(parsed_equal=json.loads(raw)==json.loads(alternate),
        bytes_equal=raw==alternate,sha256_equal=sha(raw)==sha(alternate),
        original_reference_matches=certificate['run_record_ref']['sha256']==sha(raw),
        whitespace_variant_matches=certificate['run_record_ref']['sha256']==sha(alternate)),
    historical_1857_changed_again=[r['path'] for r in historical['unresolved'] if not r['current_eq_after']],
    saved_source_probe=source,saved_cache_probe=cache)
(OUT/'extra-facts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if not k.startswith('saved_')},ensure_ascii=False,indent=2))
