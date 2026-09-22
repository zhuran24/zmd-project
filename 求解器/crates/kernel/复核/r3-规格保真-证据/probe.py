"""第3轮规格保真复核：仅在本目录落盘，调用现有内核形成最小对照。"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import subprocess
import sys

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
BIN = ROOT / 'target/debug/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
RESULTS = []

def load(path):
    return json.loads(Path(path).read_text())

def save(name, data):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return path

def source(name):
    path = ROOT / '数据/样例' / (name + '.json')
    data = load(path)
    for obj in [data['catalog'], data['parameters']['axis_registry']]:
        obj['path'] = str((path.parent / obj['path']).resolve())
    reach = data['initial_state']['reachability'].get('value')
    if isinstance(reach, dict) and 'document' in reach:
        reach['document'] = str((path.parent / reach['document']).resolve())
    return data

def call(name, command, path, *args):
    output = OUT / (name + '.json')
    cmd = [str(BIN), command, str(path), '--config', str(CFG), *map(str, args), '--out', str(output)]
    process = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    data = load(output) if output.exists() else None
    RESULTS.append(dict(name=name, command=cmd, exit_code=process.returncode,
                        status=data and data.get('status'), schema=data and data.get('schema'),
                        open_items=data and data.get('open_items'), stdout=process.stdout, stderr=process.stderr))
    (OUT / (name + '.log')).write_text(json.dumps(RESULTS[-1], ensure_ascii=False, indent=2) + '\n')
    return data

def main():
    # 用现场生成的已闭包检查点构造参数冲突，普通装载应拒收，派生器也应拒收。
    raw = source('混做粉碎机两下游')
    base = save('crusher-input', raw)
    record = call('crusher-control', 'run', base, '--ticks', 4)
    assert record['status'] == 'completed'
    raw['initial_state']['nonwarehouse']['value'] = deepcopy(record['trace']['ticks'][1]['state'])
    checkpoint = save('checkpoint-control-input', raw)
    canonical = call('checkpoint-control-seed', 'seed', checkpoint)
    assert canonical['schema'] == 'kernel-input-v3'
    assert canonical['initial_state']['nonwarehouse']['value'] == raw['initial_state']['nonwarehouse']['value']
    resumed = call('checkpoint-control-run', 'run', checkpoint, '--ticks', 2)
    matches = {field: all(a[field] == b[field] for a, b in zip(record['trace']['ticks'][2:4], resumed['trace']['ticks']))
               for field in ('time', 'state', 'events', 'warehouse_ledger', 'closure')}
    assert all(matches.values())
    save('检查点续跑逐字段对照', matches)
    drift = deepcopy(raw)
    drift['parameters']['fixedness_unproven']['warehouse.external_supply']['value'] = {'kind': 'sufficient'}
    drift_path = save('checkpoint-parameter-drift-input', drift)
    call('checkpoint-parameter-drift-run', 'run', drift_path, '--ticks', 1)
    derived = call('checkpoint-parameter-drift-seed', 'seed', drift_path)
    if derived.get('schema') == 'kernel-input-v3':
        call('checkpoint-parameter-drift-after-seed-run', 'run', OUT/'checkpoint-parameter-drift-seed.json', '--ticks', 2)
    missing = deepcopy(raw)
    missing['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values'] = []
    call('checkpoint-parameter-missing-seed', 'seed', save('checkpoint-parameter-missing-input', missing))

    # 同一个窗口在第5刻必须已经到期；只把旧窗口起点移早一刻构成到期尚待办的闭包后态。
    split = source('分流器三路轮询')
    split_record = call('splitter-control', 'run', save('splitter-input', split), '--ticks', 7)
    assert split_record['status'] == 'completed'
    state = deepcopy(split_record['trace']['ticks'][5]['state'])
    split['initial_state']['nonwarehouse']['value'] = state
    call('gate-checkpoint-control-seed', 'seed', save('gate-checkpoint-control-input', split))
    for gate in state['logistics']['gate_counters']:
        if gate['window_started_at'] is not None:
            gate['window_started_at']['value']['value'] = str(int(gate['window_started_at']['value']['value']) - 1)
            pending = next(p for p in state['semantic_context']['pending_events']['value'] if p['target'] == gate['unit'])
            pending['trigger']['value']['value']['value'] = str(int(pending['trigger']['value']['value']['value']) - 1)
            pending['event'] = f"W|{pending['trigger']['value']['value']['value']}|{gate['unit']}"
    expired = save('gate-expired-after-closure-input', split)
    call('gate-expired-after-closure-seed', 'seed', expired)
    call('gate-expired-after-closure-no-output', 'run', expired, '--ticks', 1, '--no-output')
    call('gate-expired-after-closure-record', 'run', expired, '--ticks', 1)
    call('gate-expired-record-verification', 'verify-record', OUT/'gate-expired-after-closure-record.json')
    # sufficient明确要求种子两矿为正；历史空身份不等于可取货物。
    zero = source('生产循环环带')
    for row in zero['initial_state']['nonwarehouse']['value']['warehouse']['slots']:
        if row['item'] == '源矿':
            row['quantity']['value'] = '0'
            row['item'] = None
            row['empty_identity'] = {'status': 'specified', 'value': '源矿', 'basis': ['空矿历史格复核探针']}
    call('zero-ore-sufficient-seed', 'seed', save('zero-ore-sufficient-input', zero))
    # 最小隔离门：非法闭包种子只污染搜索前缀，后续静止周期用于检查证书验收链。
    sys.path.insert(0, str(ROOT/'crates/kernel/tests'))
    import build_fixtures as fixtures
    from generate_examples import unit
    from migrate_round5 import migrate
    fixtures.OUT = OUT
    tiny = fixtures.generate('tiny-gate-generated', [unit('gate', '物品准入口', 10, 10)])
    tiny['parameters']['fixedness_unproven']['warehouse.external_supply']['value'] = {'kind': 'sufficient'}
    tiny = migrate(tiny)
    initial = call('tiny-control', 'run', save('tiny-control-input', tiny), '--ticks', 6)
    assert initial['status'] == 'completed'
    state = deepcopy(initial['trace']['ticks'][-1]['state'])
    tiny['initial_state']['nonwarehouse']['value'] = state
    tiny['settings']['gates'][0].update(item='源矿', window_limit={'value': '1', 'category': '候选'})
    gate = state['logistics']['gate_counters'][0]
    gate.update(total_received={'value': '1', 'category': '候选'}, window_received={'value': '1', 'category': '候选'},
                window_started_at={'kind': 'rational', 'value': {'value': '0', 'category': '候选'}}, blocked_reasons=['window_exhausted'])
    state['semantic_context']['pending_events']['value'] = [dict(event='W|5|gate', operation='gate_window_expiry', target='gate',
        trigger={'kind': 'at_time', 'value': {'kind': 'rational', 'value': {'value': '5', 'category': '候选'}}}, predecessors=[], status='waiting')]
    tiny_path = save('tiny-expired-after-closure-input', tiny)
    certificate = call('tiny-expired-cycle', 'cycle', tiny_path, '--max-ticks', 3)
    call('tiny-expired-cycle-verification', 'verify-cycle', OUT/'tiny-expired-cycle.json')
    if certificate.get('run_record'):
        embedded = save('tiny-expired-embedded-record', certificate['run_record'])
        call('tiny-expired-embedded-record-verification', 'verify-record', embedded)
    save('probe-results', dict(binary=str(BIN), binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), cases=RESULTS))
    print(json.dumps([dict(name=r['name'], exit_code=r['exit_code'], status=r['status'], schema=r['schema']) for r in RESULTS], ensure_ascii=False))

if __name__ == '__main__':
    main()
