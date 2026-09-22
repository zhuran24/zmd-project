"""内核第三轮第一否证席：当前源码公开入口的独立对照，产物限本目录。"""
from pathlib import Path
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import subprocess

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
SAMPLES = ROOT / '数据/样例'
CALLS = []
CHECKS = {}
SOURCES = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    SOURCES[str(path)] = digest(path)
    return json.loads(path.read_text())


def save(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def source(path):
    path = Path(path)
    value = read(path)
    for ref in [value['catalog'], value['parameters']['axis_registry']]:
        ref['path'] = str((path.parent / ref['path']).resolve())
    reach = value['initial_state']['reachability'].get('value')
    if isinstance(reach, dict) and 'document' in reach:
        reach['document'] = str((path.parent / reach['document']).resolve())
    return value


def call(name, command, path, *options):
    result_path = OUT / (name + '.json')
    result_path.unlink(missing_ok=True)
    cmd = [str(BIN), command, str(path), '--config', str(CFG),
           *map(str, options), '--out', str(result_path)]
    process = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    result = json.loads(result_path.read_text()) if result_path.exists() else None
    row = dict(name=name, command=cmd, exit_code=process.returncode,
               output_exists=result_path.exists(), stdout=process.stdout,
               stderr=process.stderr, status=result and result.get('status'),
               stop=result and result.get('stop'),
               open_items=result and result.get('open_items'))
    CALLS.append(row)
    (OUT / (name + '.log')).write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    save('calls', CALLS)
    print(name, process.returncode, row['status'], flush=True)
    return result


def state(value):
    return value['initial_state']['nonwarehouse']['value']


def change_phase(value, remaining):
    phase = value['parameters']['fixedness_unproven']['transfer.phase']
    phase['value']['values'][0]['remaining'] = remaining
    for row in state(value)['semantic_context']['parameter_values']:
        if row['axis'] == 'transfer.phase':
            row['value'] = deepcopy(phase)


def rational(value):
    return {'kind': 'rational', 'value': {'value': str(value), 'category': '候选'}}


def checkpoint_cases():
    crusher = source(SAMPLES / '混做粉碎机两下游.json')
    record = call('crusher-control', 'run', save('crusher-input', crusher), '--ticks', 4)
    assert record['status'] == 'completed'
    checkpoint = deepcopy(crusher)
    checkpoint['initial_state']['nonwarehouse']['value'] = deepcopy(record['trace']['ticks'][1]['state'])
    control = call('crusher-checkpoint-seed', 'seed', save('crusher-checkpoint', checkpoint))
    CHECKS['crusher_checkpoint_preserved'] = state(control) == state(checkpoint)
    for name in ['missing', 'supply-conflict']:
        altered = deepcopy(checkpoint)
        if name == 'missing':
            state(altered)['semantic_context']['parameter_values'] = []
        else:
            altered['parameters']['fixedness_unproven']['warehouse.external_supply']['value'] = {'kind': 'sufficient'}
        path = save('crusher-' + name + '-input', altered)
        call('crusher-' + name + '-direct', 'run', path, '--ticks', 1)
        seeded = call('crusher-' + name + '-seed', 'seed', path)
        CHECKS['crusher_' + name + '_parameter_count'] = len(state(seeded)['semantic_context']['parameter_values'])
        call('crusher-' + name + '-resumed', 'run', OUT / ('crusher-' + name + '-seed.json'), '--ticks', 1)

    bridge = source(SAMPLES / '桥接器双通路.json')
    bridge_record = call('bridge-control', 'run', save('bridge-input', bridge), '--ticks', 30)
    call('bridge-record-verification', 'verify-record', OUT / 'bridge-control.json')
    bridge['initial_state']['nonwarehouse']['value'] = deepcopy(bridge_record['trace']['ticks'][5]['state'])
    for name in ['control', 'missing', 'mirror-conflict', 'top-conflict']:
        altered = deepcopy(bridge)
        if name == 'missing':
            state(altered)['semantic_context']['parameter_values'] = []
        elif name == 'mirror-conflict':
            row = next(r for r in state(altered)['semantic_context']['parameter_values'] if r['axis'] == 'transfer.phase')
            row['value']['value']['values'][0]['remaining'] = rational(4)
        elif name == 'top-conflict':
            altered['parameters']['fixedness_unproven']['transfer.phase']['value']['values'][0]['remaining'] = rational(4)
        path = save('bridge-' + name + '-checkpoint', altered)
        call('bridge-' + name + '-direct', 'run', path, '--ticks', 2)
        seeded = call('bridge-' + name + '-seed', 'seed', path)
        CHECKS['bridge_' + name + '_state_preserved'] = state(seeded) == state(altered)
    for name, value in [('valid-zero', rational(0)), ('negative', rational(-1)),
                        ('six', rational(6)), ('fraction', rational('1/2')), ('string', 'not-a-Time')]:
        altered = deepcopy(bridge)
        change_phase(altered, value)
        call('phase-' + name, 'run', save('phase-' + name + '-input', altered), '--ticks', 2)
    coverage(bridge_record)
    return crusher


def gate_cases():
    splitter = source(SAMPLES / '分流器三路轮询.json')
    record = call('splitter-control', 'run', save('splitter-input', splitter), '--ticks', 7)
    splitter['initial_state']['nonwarehouse']['value'] = deepcopy(record['trace']['ticks'][5]['state'])
    call('gate-valid-seed', 'seed', save('gate-valid-input', splitter))
    for gate in state(splitter)['logistics']['gate_counters']:
        if gate['window_started_at'] is not None:
            gate['window_started_at']['value']['value'] = '0'
            pending = next(p for p in state(splitter)['semantic_context']['pending_events']['value'] if p['target'] == gate['unit'])
            pending['trigger']['value'] = rational(5)
            pending['event'] = 'W|5|' + gate['unit']
    path = save('gate-expired-input', splitter)
    call('gate-expired-seed', 'seed', path)
    record = call('gate-expired-run', 'run', path, '--ticks', 1)
    CHECKS['expired_gate_events'] = [{'time': tick['time'], 'event': event} for tick in record['trace']['ticks']
                                    for event in tick['events'] if event['operation'] == 'gate_window_expiry']
    call('gate-expired-verification', 'verify-record', OUT / 'gate-expired-run.json')

    # 隔离门输入只复用布局，检查点与异常待办由本次执行后独立构造。
    tiny = source(ROOT / 'crates/kernel/复核/r3-规格保真-证据/tiny-control-input.json')
    record = call('tiny-control', 'run', save('tiny-control-input', tiny), '--ticks', 6)
    tiny['initial_state']['nonwarehouse']['value'] = deepcopy(record['trace']['ticks'][-1]['state'])
    tiny['settings']['gates'][0].update(item='源矿', window_limit={'value': '1', 'category': '候选'})
    gate = state(tiny)['logistics']['gate_counters'][0]
    gate.update(total_received={'value': '1', 'category': '候选'}, window_received={'value': '1', 'category': '候选'},
                window_started_at=rational(0), blocked_reasons=['window_exhausted'])
    state(tiny)['semantic_context']['pending_events']['value'] = [dict(event='W|5|gate', operation='gate_window_expiry',
        target='gate', trigger={'kind': 'at_time', 'value': rational(5)}, predecessors=[], status='waiting')]
    result = call('tiny-expired-cycle', 'cycle', save('tiny-expired-input', tiny), '--max-ticks', 3)
    call('tiny-expired-cycle-verification', 'verify-cycle', OUT / 'tiny-expired-cycle.json')
    call('tiny-embedded-verification', 'verify-record', save('tiny-embedded-record', result['run_record']))
    CHECKS['tiny_cycle'] = {key: result['cycle'][key] for key in ['period', 'start_time', 'end_time']}


def ring_cases():
    ring = source(SAMPLES / '生产循环环带.json')
    result = call('ring-control-cycle', 'cycle', save('ring-input', ring), '--max-ticks', 25)
    call('ring-control-verification', 'verify-cycle', OUT / 'ring-control-cycle.json')
    altered = deepcopy(ring)
    altered['initial_state']['nonwarehouse']['value'] = deepcopy(result['cycle']['start_state'])
    change_phase(altered, 'not-a-Time')
    result = call('phase-string-cycle', 'cycle', save('phase-string-cycle-input', altered), '--max-ticks', 25)
    call('phase-string-cycle-verification', 'verify-cycle', OUT / 'phase-string-cycle.json')
    CHECKS['phase_string_period'] = result['cycle']['period']
    zero = deepcopy(ring)
    for row in state(zero)['warehouse']['slots']:
        if row['item'] == '源矿':
            row['quantity']['value'] = '0'
            row['item'] = None
            row['empty_identity'] = {'status': 'specified', 'value': '源矿', 'basis': ['否证探针：只有历史身份，无实际库存']}
    call('zero-ore-seed', 'seed', save('zero-ore-input', zero))
    call('zero-ore-run', 'run', OUT / 'zero-ore-seed.json', '--ticks', 1)
    overflow = deepcopy(ring)
    row = next(r for r in state(overflow)['inventory'] if r['slot'] == 'a:transport:0')
    row['contents'][0]['entered_at'] = rational(-(2**63))
    path = save('overflow-input', overflow)
    for mode in ['run', 'cycle']:
        call('overflow-' + mode, mode, path, '--ticks', 2)


def panic_cases(crusher):
    for name, label in [('bad-slot', 'bad'), ('bad-unit', 'bad:input:0')]:
        altered = deepcopy(crusher)
        state(altered)['inventory'][0]['slot'] = label
        call(name, 'run', save(name + '-input', altered), '--ticks', 1)
    altered = deepcopy(crusher)
    altered['initial_state']['nonwarehouse']['value'] = True
    call('boolean-seed', 'seed', save('boolean-seed-input', altered))


def coverage(record):
    raw = source(SAMPLES / '桥接器双通路.json')
    axis = next(row for row in record['uncovered_axes'] if row['axis'] == 'connection.bridge_first_contact')
    selected = [{'time': tick['time'], 'event': e} for tick in record['trace']['ticks']
                for e in tick['events'] if e['event'] in axis['evidence']]
    bridges = {u['id']: u['bridge_axes'] for u in raw['layout']['units'] if u['kind'] == '桥接器'}
    bridge_moves = Counter()
    wireless = Counter()
    for tick in record['trace']['ticks']:
        for event in tick['events']:
            if event['operation'] == 'move' and event['outcome'] == 'success' and 'bridge:' in event['target']:
                bridge_moves[event['target']] += 1
        for row in tick['warehouse_ledger']['wireless_inbound']:
            wireless[row['item']] += int(row['quantity']['value'])
    audit = read(ROOT / 'crates/kernel/evidence/round5/audit-results.json')
    save('bridge-coverage', dict(axis=axis, selected_events=selected, bridge_axes=bridges,
         connection_events=raw['timeline']['connection_events'], history=raw['timeline']['events'],
         first_time=record['trace']['ticks'][0]['time'], last_time=record['trace']['ticks'][-1]['time'],
         successful_bridge_moves=bridge_moves, wireless_inbound=wireless,
         audit_bridge_cases=audit['coverage'].get('connection.bridge_first_contact'),
         audit_missing=audit['required_unexercised']))


def directory_scan():
    binaries = []
    special_dirs = []
    for base in [ROOT / 'crates/kernel/复核', ROOT / 'crates/kernel/evidence']:
        for path in sorted(base.rglob('*')):
            if path.is_symlink():
                continue
            if path.is_dir() and path.name in ['target', '.cargo-home', 'registry', 'snapshot']:
                special_dirs.append(dict(path=str(path), symlink=False))
            if path.is_file():
                with path.open('rb') as stream:
                    header = stream.read(8)
                kind = 'ELF' if header.startswith(b'\x7fELF') else 'archive' if header == b'!<arch>\n' else None
                if kind:
                    stat = path.stat()
                    binaries.append(dict(path=str(path), kind=kind, bytes=stat.st_size,
                        mtime_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()))
    snapshot = ROOT / 'crates/kernel/复核/r2-测试与证据/snapshot'
    files = [p for p in sorted(snapshot.rglob('*')) if p.is_file()]
    target = snapshot / '求解器/target'
    save('directory-scan', dict(binaries=binaries, count=len(binaries), bytes=sum(r['bytes'] for r in binaries),
         special_dirs=special_dirs, snapshot=dict(path=str(snapshot), count=len(files), bytes=sum(p.stat().st_size for p in files),
         files=[str(p.relative_to(snapshot)) for p in files], target_exists=target.is_dir(), target_symlink=target.is_symlink(),
         target_children=[p.name for p in target.iterdir()] if target.is_dir() else [])))


def main():
    protected = list((ROOT / 'crates/kernel/src').glob('*.rs')) + list((ROOT / '规格').glob('*.md'))
    protected += list((ROOT / '规格').glob('*.json')) + list((ROOT / 'crates/kernel/tests').glob('*.py'))
    protected += [ROOT.parent / name for name in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']]
    protected += [ROOT / 'crates/kernel/复核' / name for name in ['复核-r3-规格保真.md', '复核-r3-测试与证据.md', '复核-r3-工程.md']]
    for path in protected:
        SOURCES[str(path)] = digest(path)
    save('source-hashes-before', SOURCES)
    crusher = checkpoint_cases()
    gate_cases()
    ring_cases()
    panic_cases(crusher)
    directory_scan()
    changes = [path for path, value in SOURCES.items() if digest(Path(path)) != value]
    save('source-hashes-final', dict(files=SOURCES, changed=changes, binary=dict(path=str(BIN), sha256=digest(BIN))))
    save('checks', CHECKS)
    assert not changes, changes
    print('finished', len(CALLS), 'calls', flush=True)


if __name__ == '__main__':
    main()
