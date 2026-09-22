"""补核可否反驳发现的合法边界与历史覆盖证据。"""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('local_probe', HERE / 'reproduce.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
# 保存主运行的完整调用账，补充调用顺次追加。
probe.CALLS.extend(probe.read(HERE / 'calls.json'))
tiny = probe.read(HERE / 'tiny-expired-input.json')
probe.state(tiny)['semantic_context']['judgment_context']['value']['phase'] = 'before_boundary'
result = probe.call('tiny-before-boundary', 'run', probe.save('tiny-before-boundary-input', tiny), '--ticks', 1)
verification = probe.call('tiny-before-boundary-verification', 'verify-record', HERE / 'tiny-before-boundary.json')
audit = probe.read(probe.ROOT / 'crates/kernel/evidence/round5/audit-results.json')
coverage = []
for name in audit['coverage']['connection.bridge_first_contact']:
    raw = probe.source(probe.SAMPLES / (name + '.json'))
    record = probe.read(probe.SAMPLES / (name + '-运行记录-v3-kernel.json'))
    axis = next(r for r in record['uncovered_axes'] if r['axis'] == 'connection.bridge_first_contact')
    by_id = {e['id']: e for e in raw['timeline']['events']}
    contacts = [by_id[r['event']] for r in raw['timeline']['connection_events'] if 'bridge' in r['channel']]
    selected = [e for tick in record['trace']['ticks'] for e in tick['events'] if e['event'] in axis['evidence']]
    coverage.append(dict(name=name, status=axis['coverage_status'], first_time=record['trace']['ticks'][0]['time'],
        bridge_axes=[u['bridge_axes'] for u in raw['layout']['units'] if u['kind'] == '桥接器'],
        evidence_count=len(selected), operations=sorted({e['operation'] for e in selected}),
        outcomes=sorted({e['outcome'] for e in selected}), contact_events=contacts))
state = probe.read(HERE / 'phase-valid-zero-input.json')['initial_state']['nonwarehouse']['value']
phases = next(r for r in state['semantic_context']['parameter_values'] if r['axis'] == 'transfer.phase')['value']['value']['values']
progress = {r['unit']: r['cooldowns'] for r in state['progress']}
phase_comparison = [dict(unit=r['unit'], initial=r['remaining'], current=progress[r['unit']][0]['remaining']) for r in phases]
probe.save('supplement-results', dict(before_boundary_status=result['status'],
    before_boundary_time=result['trace']['ticks'][0]['time'],
    before_boundary_events=result['trace']['ticks'][0]['events'],
    before_boundary_verified=verification['status'], phase_comparison=phase_comparison,
    aggregate_bridge_cases=coverage, source_hashes=probe.SOURCES))
print(json.dumps(dict(before_boundary_verified=verification['status'], aggregate_bridge_cases=len(coverage),
    all_evidence_moves=all(r['operations'] == ['move'] for r in coverage)), ensure_ascii=False))
