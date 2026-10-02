#!/usr/bin/env python3
"""Audit inputs/results/report; write only this directory's audit JSON."""
import ast
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent / '推导95S.md'
PROJECT = HERE.parents[3]


def main():
    source_checks = []
    for row in json.loads((HERE / 'inputs.json').read_text()):
        path = PROJECT / row['path']
        same = hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        assert same, ('changed input', str(path))
        source_checks.append(dict(path=row['path'], unchanged=True))
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    for path in HERE.glob('*.json'):
        json.loads(path.read_text())
    text = REPORT.read_text()
    links = re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', text)
    for link in links:
        assert not link.startswith(('http:', 'https:')), ('unexpected web source', link)
        assert (REPORT.parent / link).exists(), ('missing link', link)
    summary = json.loads((HERE / 'factory_summary.json').read_text())
    local = json.loads((HERE / 'shared_send_results.json').read_text())
    certificates = []
    for part in range(3):
        rows = json.loads((HERE / f'cycle_verification_{part}.json').read_text())
        certificates.extend(rows)
    assert len(certificates) == summary['cases'] == 19
    assert len({r['seed'] for r in certificates}) == 19
    for row in certificates:
        path = HERE / row['certificate']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        c = json.loads(path.read_text())
        assert c['equal_raw_states_a'] and c['equal_raw_states_b']
        assert c['end'] - c['start'] == 480
        assert c['deliveries'] == {'高容谷地电池': 36, '精选荞愈胶囊': 33}
        assert c['mineral_counts'] == [60] * 52
    assert sum(r['steps'] for r in certificates) == summary['compared_steps_final_cases'] == 426248
    assert local['positive_cases'] == 7530 and local['compared_steps'] == 623408
    assert local['history_resets'] == 38450
    assert json.loads((HERE / 'candidates.json').read_text()) == []
    assert '全厂充分条件未证成' in text
    assert '685448' in text and '53168' in text and '53648' in text
    assert '$[200,1200)$' in text and '$[1700,2900)$' in text
    files = [p for p in HERE.iterdir() if p.is_file()]
    allowed = {'.py', '.log', '.json', '.md', '.gz'}
    assert all(p.suffix in allowed for p in files)
    assert all(p.stat().st_size <= 100 * 1024 * 1024 or p.suffix == '.gz' for p in files)
    reply = dict(report_path=str(REPORT), candidates=[],
                 summary='共享发送在各末端不拒收时满速已证；19个整厂实例双编码闭合达标。原充分条件仍缺下游反复拒收的联立证明。',
                 status='未证成完整充分条件')
    (HERE / 'reply.json').write_text(json.dumps(reply, ensure_ascii=False, indent=2) + '\n')
    result = dict(status='passed', inputs_unchanged=source_checks,
                  report_links_checked=len(links), whole_factory_cycles=19,
                  raw_state_closure_both_encodings=True, candidates=0,
                  total_artifact_bytes=sum(p.stat().st_size for p in files),
                  maximum_artifact_bytes=max(p.stat().st_size for p in files),
                  python_syntax='passed', json_parse='passed')
    (HERE / 'delivery_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'inputs_unchanged'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
