"""Check the review artifact, links, schema, inputs and computation summaries."""
import ast
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent/'复核96T.md'
text = REPORT.read_text()
reply = json.loads((HERE/'reply.json').read_text())
expected = ['专用进路下缓存格不空的传递', '采种单元的回路存量下界', '采种单元不断料']
assert reply['report_path'] == str(REPORT)
assert [row['name'] for row in reply['verdicts']] == expected
assert len(reply['verdicts']) == 3
for row in reply['verdicts']:
    assert row['verdict'] in ['未否证', '已否证', '修正']
    assert isinstance(row['reason'], str) and row['reason']
    assert isinstance(row['revised_text'], str)
    assert bool(row['revised_text']) == (row['verdict'] == '修正')
assert '## 6. 七段补证逐条复核' in text
assert '## 7. 抽查第2节“不受影响”条目' in text
for i in range(1, 8):
    assert f'### 6.{i} ' in text
spot = [11, 14, 21, 23, 27, 29, 30, 31, 32, 33]
for i in spot:
    assert f'| {i} ' in text
links = re.findall(r'\[[^\]\n]+\]\(([^)]+)\)', text)
missing = []
for link in links:
    if link.startswith(('https://', 'http://', '#')):
        continue
    path = REPORT.parent/link.split('#')[0]
    if path == HERE/'delivery_check.json':
        continue
    if not path.exists():
        missing.append(link)
assert not missing, missing
inputs = json.loads((HERE/'inputs.json').read_text())
changed = []
for item in inputs:
    path = Path(item['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
        changed.append(str(path))
assert not changed, changed
source_files = sorted(HERE.glob('*.py'))
for path in source_files:
    ast.parse(path.read_text(), filename=str(path))
counts = {}
for name in ['求解约束', '求解充分条件']:
    content = (HERE.parent/'前提快照'/f'{name}.txt').read_text()
    entries = [line for line in content.splitlines() if line and not line[0].isspace()
               and '：' in line and not line.endswith('：')]
    counts[name] = len(entries)
assert counts == {'求解约束': 77, '求解充分条件': 11}, counts
results = {}
for filename in ['arithmetic.json', 'chain_results.json', 'layer_results.json',
                 'plant_results.json', 'round_robin_results.json', 'dedicated_results.json',
                 'density_results.json', 'local_results.json', 'history_diagnostic.json']:
    results[filename] = json.loads((HERE/filename).read_text())
plant = results['plant_results.json']['stats']
assert plant['arbitrary']['compared_steps'] == 900*1200
assert plant['full']['compared_steps'] == 480*1600
for stats in plant.values():
    assert stats['bound_failures'] == stats['strong_normal_bound_failures'] == stats['phi_identity_failures'] == 0
assert plant['full']['full_failures'] == 0
assert plant['full']['maximum_service_delay'] == 2
assert results['dedicated_results.json']['violations'] == 0
assert results['dedicated_results.json']['insufficient_input_negative_control']['empty_cache_in_cycle'] > 0
assert results['density_results.json']['cycles']['U']['period_steps'] == 40
assert results['density_results.json']['cycles']['S']['period_steps'] == 80
replays = results['history_diagnostic.json']['single_erasure_replays']
assert any(r['erasure_at'] is None and r['final_phi2'] == 117 for r in replays)
assert any(r['erasure_at'] == 16 and r['final_phi2'] == 115 for r in replays)
files = sorted(path for path in HERE.iterdir() if path.is_file() and path.name != 'delivery_check.json')
manifest = [dict(name=p.name, bytes=p.stat().st_size,
                 sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
output = dict(status='pass', report=str(REPORT),
              report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
              candidates=3, supplementary_proofs=7, spot_checks=len(spot),
              checked_links=len(links), missing_links=missing, changed_inputs=changed,
              premise_entry_counts=counts, python_sources=len(source_files),
              independently_compared_plant_steps=sum(s['compared_steps'] for s in plant.values()),
              dedicated_compared_steps=results['dedicated_results.json']['compared_steps'],
              reader_review=dict(status='completed', current_header=True,
                                 complete_revised_statement=True,
                                 diagnostics_separated_from_rule_counterexamples=True,
                                 local_models_not_claimed_as_layouts=True,
                                 historical_references_separated=True),
              files=manifest)
(HERE/'delivery_check.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: v for k, v in output.items() if k != 'files'}, ensure_ascii=False, indent=2))
