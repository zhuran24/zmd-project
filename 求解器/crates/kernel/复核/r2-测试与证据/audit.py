#!/usr/bin/env python3
"""第二轮测试与证据复核：只读原交付物，探针与结果只写复核目录。"""
import copy
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SOLVER = ROOT / '求解器'
KERNEL = SOLVER / 'crates/kernel'
BIN = HERE / 'target/debug/kernel'
CONFIG = SOLVER / '规格/内核配置-v1.json'
sys.path.insert(0, str(KERNEL / 'tests'))
import verify_outputs as verifier


def load(path):
    return json.loads(path.read_text())


def write(name, value):
    path = HERE / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_copy(source):
    data = load(source)
    for ref in (data['catalog'], data['parameters']['axis_registry']):
        ref['path'] = str((source.parent / ref['path']).resolve())
    return data


def invoke(path, name, ticks):
    output = HERE / (name + '-record.json')
    command = [str(BIN), 'run', str(path), '--config', str(CONFIG), '--ticks', str(ticks), '--out', str(output)]
    process = subprocess.run(command, text=True, capture_output=True, timeout=45)
    write(name + '-process.json', {'command': command, 'exit_code': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr})
    record = load(output)
    assert process.returncode == 0 and record['status'] == 'completed', record['open_items']
    return record


def check_evidence():
    """逐个复算交付清单与保护基线，黄金及参考比较程序不得漂移。"""
    baseline = load(KERNEL / 'evidence/revision-r1/baseline.json')
    protected = [p for p in baseline if (Path(p).parent == ROOT or '/规格/' in p or '/数据/样例/' in p) and not p.endswith('-kernel.json') and not p.endswith('/内核实现-对规格的疑问.md')]
    changed = [p for p in protected if not Path(p).is_file() or digest(Path(p)) != baseline[p]]
    assert not changed, changed
    manifest = load(KERNEL / 'evidence/revision-r1/deliverables.json')
    drift = [r['path'] for r in manifest['files'] if not Path(r['path']).is_file() or digest(Path(r['path'])) != r['sha256']]
    assert not drift, drift
    pin = KERNEL / 'tests/reference.rs'
    assert digest(pin) == baseline[str(pin)]
    return {'protected_baseline_files': len(protected), 'changes': changed, 'manifest_files': len(manifest['files']), 'manifest_drift': drift, 'reference_rs_unchanged': True,
            'golden_sha256': digest(SOLVER / '数据/样例/混做粉碎机两下游-黄金轨迹.json')}


def check_records():
    """调用原始公开验收函数，不执行会覆盖旧证据的main。"""
    controls, mutations = [], []
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        data = verifier.checker.load_json(SOLVER / f'数据/样例/{name}.json')
        expected = verifier.run(data)
        for suffix in ('运行记录-kernel', '运行记录-checkpoint_delta-kernel'):
            path = SOLVER / f'数据/样例/{name}-{suffix}.json'
            controls.append(verifier.verify(path, data, expected))
            for kind in ('unknown_axis', 'fabricated_exercised', 'wrong_disposition', 'missing_evidence', 'wrong_profile', 'wrong_producer_path', 'bad_summary_control'):
                record = load(path)
                if kind == 'unknown_axis':
                    record['uncovered_axes'][0]['axis'] = 'fabricated.axis'
                elif kind == 'fabricated_exercised':
                    row = next(r for r in record['uncovered_axes'] if r['axis'] == 'transfer.cooldown_scope')
                    row['coverage_status'], row['evidence'] = 'exercised', ['never_executed_event']
                elif kind == 'wrong_disposition':
                    row = next(r for r in record['uncovered_axes'] if r['axis'] == 'warehouse.periodic_lift')
                    row['disposition'] = '已定'
                elif kind == 'missing_evidence':
                    for row in record['uncovered_axes']:
                        if row['axis'] in ('warehouse.acceptance', 'warehouse.acceptance_quantifier'):
                            row['evidence'] = ['无逐边界报告']
                elif kind == 'wrong_profile':
                    record['profile_id'] = 'fabricated_profile'
                elif kind == 'wrong_producer_path':
                    record['producer']['path'] = '/nonexistent/fabricated.rs'
                else:
                    record['trace']['ticks'][0]['summary']['warehouse_ore'] = '123'
                bad = write(name + '-' + suffix + '-' + kind + '.json', record)
                try:
                    verifier.verify(bad, data, expected)
                except (AssertionError, ValueError) as error:
                    mutations.append({'sample': name, 'format': suffix, 'mutation': kind, 'accepted': False, 'reason': str(error)})
                else:
                    mutations.append({'sample': name, 'format': suffix, 'mutation': kind, 'accepted': True})
    return {'controls': controls, 'mutations': mutations}


def check_permutations():
    """有语义的全序保持不动；仅置换无语义的单位/结构边数组。"""
    result = []
    for name, ticks in [('混做粉碎机两下游', 4), ('分流器三路轮询', 12)]:
        data = source_copy(SOLVER / f'数据/样例/{name}.json')
        path = write(name + '-control-input.json', data)
        control = invoke(path, name + '-control', ticks)
        repeat = invoke(path, name + '-repeat', ticks)
        assert (HERE / (name + '-control-record.json')).read_bytes() == (HERE / (name + '-repeat-record.json')).read_bytes()
        for seed in (19, 29, 39):
            shuffled = copy.deepcopy(data)
            rng = random.Random(seed)
            changes = {}
            for key in ('units', 'physical_channels', 'buffer_channels'):
                rng.shuffle(shuffled['layout'][key])
                changes[key] = shuffled['layout'][key] != data['layout'][key]
                if len(data['layout'][key]) > 1:
                    assert changes[key]
            moved = write(f'{name}-shuffle-{seed}-input.json', shuffled)
            actual = invoke(moved, f'{name}-shuffle-{seed}', ticks)
            assert verifier.same(control['trace'], actual['trace'])
            result.append({'sample': name, 'seed': seed, 'ticks': ticks, 'actual_order_changed': changes, 'full_trace_identical': True, 'same_input_bytes_identical': True})
    return result


def check_manual():
    """先写期望再运行；期望只由手推递推给定，不读取参考执行器或内核结果。"""
    source = SOLVER / '数据/样例/混做粉碎机两下游.json'
    data = source_copy(source)
    next(s for s in data['settings']['switches'] if s['unit'] == 'crusher')['enabled'] = False
    path = write('手推-关闭粉碎机-input.json', data)
    expected = []
    for t in range(4):
        inventory = {row['slot']: [] for row in data['initial_state']['nonwarehouse']['value']['inventory']}
        inventory['feed_belt:transport:0'] = [['源矿', 1, t]]
        if t >= 1:
            inventory['crusher:buffer:0'] = [['源矿', 1, None]]
        if t >= 2:
            inventory['crusher:input:0'] = [['源矿', t - 1, None]]
        successes = ([f'J|{t}|0|0'] if t == 0 else [f'J|{t}|0|1', f'J|{t}|1|0'])
        expected.append({'time': t, 'inventory': inventory, 'warehouse_ore': 79999 - t,
                         'crusher_phase': 'idle' if t == 0 else 'intake', 'remaining': None,
                         'pending': [], 'successes': successes, 'internal_events': ['J|1|0|11'] if t == 1 else [],
                         'scan_rounds': 2 if t == 0 else 3, 'completed': 0})
    write('手推-关闭粉碎机-expected.json', expected)
    actual = invoke(path, '手推-关闭粉碎机', 4)
    projections = []
    for tick in actual['trace']['ticks']:
        state = tick['state']
        # 输入§6允许非运输格entered_at为Time或null；zero读法无额外滞留守卫，手算只核运输年龄。
        inventory = {row['slot']: [[c['item'], int(c['quantity']['value']), None if ':transport:' not in row['slot'] or c['entered_at'] is None else int(c['entered_at']['value']['value'])] for c in row['contents']] for row in state['inventory']}
        progress = {p['unit']: p for p in state['progress']}
        for uid in ('grinder_a', 'grinder_b'):
            assert progress[uid] == next(p for p in data['initial_state']['nonwarehouse']['value']['progress'] if p['unit'] == uid)
        assert all(int(w['quantity']['value']) == 80000 for w in state['warehouse']['slots'] if w['item'] not in ('源矿', None))
        projections.append({'time': int(tick['time']['value']['value']), 'inventory': inventory,
                            'warehouse_ore': int(next(w for w in state['warehouse']['slots'] if w['item'] == '源矿')['quantity']['value']),
                            'crusher_phase': progress['crusher']['phase'], 'remaining': progress['crusher']['remaining'],
                            'pending': state['semantic_context']['pending_events']['value'],
                            'successes': [e['event'] for e in tick['events'] if e['operation'] == 'move' and e['outcome'] == 'success'],
                            'internal_events': [p['event'] for p in state['semantic_context']['tick_context']['value']['internal_passages']],
                            'scan_rounds': tick['closure']['scan_rounds'],
                            'completed': sum(e['operation'] == 'manufacture_complete' for e in tick['events'])})
    write('手推-关闭粉碎机-actual-projection.json', projections)
    assert verifier.same(expected, projections), '手推物理量或事件次序与内核不同'
    return {'status': '通过', 'ticks': 4, 'inventory_slots_each_tick': len(expected[0]['inventory']), 'all_inventory_quantities_and_transport_arrival_times': True, 'successful_movement_event_ids': True, 'internal_passages': True, 'closure_rounds': True, 'pending': True, 'downstream_progress': True}


def main():
    results = {'evidence': check_evidence(), 'records': check_records(), 'determinism': check_permutations(), 'manual': check_manual()}
    write('audit-results.json', results)
    print(json.dumps({'controls': len(results['records']['controls']), 'mutations_accepted': sum(r['accepted'] for r in results['records']['mutations']), 'mutations_total': len(results['records']['mutations']), 'permutations': len(results['determinism']), 'manual': results['manual']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
