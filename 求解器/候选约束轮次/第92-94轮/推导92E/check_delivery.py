#!/usr/bin/env python3
"""Read-only validation of the report, input fingerprints, and handoff schema."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REPO = HERE.parents[3]
result = json.loads((HERE / 'result.json').read_text())
report = Path(result['report_path'])
body = report.read_text()
assert report == BASE / '推导92E.md'
assert set(result) <= {'report_path', 'candidates', 'summary', 'status', 'error'}
assert all(isinstance(result[k], str) for k in ['report_path', 'summary', 'status', 'error'])
assert isinstance(result['candidates'], list) and len(result['candidates']) == 7
required = {'name', 'kind', 'text', 'basis', 'derivation', 'relation'}
names = []
old = '\n'.join((REPO / name).read_text() for name in
                ['候选约束.txt', '候选简化.txt', '候选充分条件.txt'])
old += (BASE / '前提快照/求解约束.txt').read_text()
old += (BASE / '前提快照/求解充分条件.txt').read_text()
old_names = {line.split('：', 1)[0] for line in old.splitlines()
             if line and not line.startswith((' ', '\t')) and '：' in line}
for candidate in result['candidates']:
    assert set(candidate) == required
    assert all(isinstance(v, str) and v for v in candidate.values())
    assert candidate['kind'] in {'必要条件', '简化', '充分条件'}
    assert candidate['name'] in body
    assert candidate['name'] not in old_names
    names.append(candidate['name'])
assert len(set(names)) == len(names)

fingerprints = json.loads((HERE / 'full_rate_checks.json').read_text())['snapshots']
for name, expected in fingerprints.items():
    content = (BASE / '前提快照' / name).read_bytes()
    assert hashlib.sha256(content).hexdigest() == expected['sha256']
    assert len(content.splitlines()) == expected['lines']

links = re.findall(r'\]\(([^)]+)\)', body)
checked_links = []
for target in links:
    assert not target.startswith(('http:', 'https:'))
    assert (report.parent / target).is_file(), target
    checked_links.append(target)
artifacts = list(HERE.rglob('*'))
assert all(p.suffix in {'.py', '.json', '.md', '.log', '.gz'}
           for p in artifacts if p.is_file())
assert all(p.stat().st_size <= 100 * 1024 * 1024 for p in artifacts if p.is_file())
qa = {'status': 'PASS', 'candidate_count': len(names),
      'names_unique_and_new': True, 'schema_fields_valid': True,
      'snapshot_fingerprints_unchanged': True,
      'checked_report_links': checked_links,
      'all_artifact_extensions_allowed': True,
      'all_artifacts_under_100MiB': True,
      'report_bytes': report.stat().st_size,
      'scope': 'Artifact consistency checks; mathematical proofs reviewed separately.'}
(HERE / 'delivery_checks.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in qa.items() if k != 'checked_report_links'}, ensure_ascii=False))
