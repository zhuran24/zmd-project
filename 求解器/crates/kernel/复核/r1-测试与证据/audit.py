#!/usr/bin/env python3
"""第四轮测试复核：只读原产物，所有新增证据写在本目录。"""
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
KERNEL = ROOT / 'crates/kernel'
CONFIG = ROOT / '规格/内核配置-v1.json'
BINARY = OUT / 'target/debug/kernel'
sys.path.insert(0, str(ROOT / '数据/样例'))
spec = importlib.util.spec_from_file_location('kernel_verify', KERNEL / 'tests/verify_outputs.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def run_input(name, data, ticks):
    """走公开命令行入口，不绕过装载器或直接注入引擎内部。"""
    data = copy.deepcopy(data)
    data['catalog']['path'] = str(ROOT / '数据/正式静态目录.json')
    data['parameters']['axis_registry']['path'] = str(ROOT / '规格/选择点参数轴.md')
    source = write(name + '-input.json', data)
    target = OUT / (name + '-record.json')
    command = [str(BINARY), 'run', str(source), '--config', str(CONFIG), '--ticks', str(ticks), '--out', str(target)]
    process = subprocess.run(command, capture_output=True, text=True)
    write(name + '-process.json', {'command': command, 'returncode': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr})
    return read(target)


def integrity():
    """核原实现的两个清单，不重新生成或覆盖它们。"""
    baseline = read(KERNEL / 'evidence/baseline.json')
    changes = [p for p, h in baseline.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != h]
    manifest = read(KERNEL / 'evidence/deliverables.json')['files']
    changed_deliverables = [r['path'] for r in manifest if hashlib.sha256(Path(r['path']).read_bytes()).hexdigest() != r['sha256']]
    return {'baseline_count': len(baseline), 'baseline_changes': changes, 'deliverable_entries': len(manifest), 'deliverable_changes': changed_deliverables}


def record_checks():
    """调用交付的 verify 函数，正例和篡改负例都另存，不调用会覆盖旧证据的 main。"""
    result = []
    for name in ['混做粉碎机两下游', '分流器三路轮询']:
        data = read(ROOT / f'数据/样例/{name}.json')
        expected = verify.run(data)
        for suffix in ['运行记录-kernel', '运行记录-checkpoint_delta-kernel']:
            path = ROOT / f'数据/样例/{name}-{suffix}.json'
            report = verify.verify(path, data, expected)
            result.append({'case': name + suffix, 'expected_accept': True, 'accepted': True, 'report': report})
        base = read(ROOT / f'数据/样例/{name}-运行记录-kernel.json')
        mutations = {}
        value = copy.deepcopy(base)
        value['fingerprints'] = [r for r in value['fingerprints'] if r['role'] != 'formal_source']
        mutations['删除三份正式源指纹'] = value
        value = copy.deepcopy(base)
        value['validation_scope']['through']['value']['value'] = '999'
        value['validation_scope']['manufacturing_cycles_completed']['value'] = '999'
        value['validation_scope']['golden_match'] = not value['validation_scope']['golden_match']
        mutations['伪造验证范围与批数'] = value
        value = copy.deepcopy(base)
        value['trace']['ticks'][-1]['summary']['warehouse_ore'] = '999'
        mutations['篡改轨迹摘要对照'] = value
        for label, value in mutations.items():
            path = write(name + '-' + label + '.json', value)
            try:
                verify.verify(path, data, expected)
                accepted, error = True, None
            except Exception as exc:
                accepted, error = False, f'{type(exc).__name__}: {exc}'
            result.append({'case': name + label, 'expected_accept': False, 'accepted': accepted, 'error': error, 'path': str(path)})
    return result


def manual_bridge():
    """先写独立手算预期，之后才调用内核；同种双轴场景扩大到四刻。"""
    data = read(KERNEL / 'evidence/bridge-manual-input.json')
    for row in data['initial_state']['nonwarehouse']['value']['inventory']:
        if row['slot'] == 'west_box:storage:0':
            row['contents'][0]['item'] = '源矿'
    south = 'PC|south_box:north:2|bridge:south:0'
    north = 'PC|bridge:north:0|north_box:south:0'
    east = 'PC|bridge:east:0|east_box:south:0'
    west = 'PC|west_box:north:2|bridge:west:0'
    def contents(at):
        return [{'item': '源矿', 'quantity': '1', 'entered_at': str(at)}]
    expected = [
        {'time': '0', 'nonempty': {'bridge:vertical:0': contents(0), 'west_box:storage:0': contents(0)}, 'successes': [south], 'rounds': 2},
        {'time': '1', 'nonempty': {'north_box:storage:0': contents(1), 'bridge:horizontal:0': contents(1)}, 'successes': [north, west], 'rounds': 2},
        {'time': '2', 'nonempty': {'north_box:storage:0': contents(1), 'east_box:storage:0': contents(2)}, 'successes': [east], 'rounds': 2},
        {'time': '3', 'nonempty': {'north_box:storage:0': contents(1), 'east_box:storage:0': contents(2)}, 'successes': [], 'rounds': 1},
    ]
    write('手推同种桥接-expected.json', expected)
    record = run_input('手推同种桥接', data, 4)
    actual = [{'time': t['time']['value']['value'], 'nonempty': t['summary']['nonempty'], 'successes': [e['target'] for e in t['events'] if e['operation'] == 'move' and e['outcome'] == 'success'], 'rounds': t['closure']['scan_rounds']} for t in record['trace']['ticks']]
    warehouse = data['initial_state']['nonwarehouse']['value']['warehouse']
    invariant = []
    for index, tick in enumerate(record['trace']['ticks']):
        state = tick['state']
        total = {}
        for row in state['warehouse']['slots']:
            if row['item']:
                total[row['item']] = total.get(row['item'], 0) + int(row['quantity']['value'])
        for row in state['inventory']:
            for item in row['contents']:
                total[item['item']] = total.get(item['item'], 0) + int(item['quantity']['value'])
        usage = state['semantic_context']['tick_context']['value']['port_usage']
        nonempty = {r['slot']: [{'item': c['item'], 'quantity': c['quantity']['value'], 'entered_at': c['entered_at']['value']['value']} for c in r['contents']] for r in state['inventory'] if r['contents']}
        movements = state['semantic_context']['tick_context']['value']['movements']
        invariant.append({'time': tick['time'], 'warehouse_unchanged': state['warehouse'] == warehouse, 'state_inventory_matches_manual': nonempty == expected[index]['nonempty'], 'movement_ledger_matches_manual': [r['channel'] for r in movements] == expected[index]['successes'] and all(r['item'] == '源矿' and r['quantity']['value'] == '1' for r in movements), 'total': total, 'all_port_usage_at_most_one': all(int(r['quantity']['value']) <= 1 for r in usage), 'port_usage_entries_equal_twice_successes': len(usage) == 2 * len(expected[index]['successes']), 'no_transfer_success': all(e['outcome'] != 'success' for e in tick['events'] if e['operation'] == 'transfer')})
    return {'status': record['status'], 'expected_equals_actual': expected == actual, 'expected': expected, 'actual': actual, 'invariants': invariant}


def supply_exhaustion():
    """把源矿种子改成一件，显式补矿史仍为空；完整公开入口检验耗尽处置。"""
    data = read(ROOT / '数据/样例/混做粉碎机两下游.json')
    seed = data['initial_state']['nonwarehouse']['value']
    for row in seed['warehouse']['slots']:
        if row['item'] == '源矿':
            row['quantity'] = {'value': '1', 'category': '候选'}
    supply = data['parameters']['fixedness_unproven']['warehouse.external_supply']['value']
    supply['basis'] = '复核负例：当前有限种子仅余1源矿，0至3时刻不给补矿，用于检验持续充分前件，预期拒绝该不足历史'
    for row in seed['semantic_context']['parameter_values']:
        if row['axis'] == 'warehouse.external_supply':
            row['value']['value'] = copy.deepcopy(supply)
    data['initial_state']['reachability'] = {'status': 'specified', 'value': {'kind': 'conditional_history', 'document': str(OUT.parent / '复核-r1-测试与证据.md'), 'scope': '独立合成条件种子，不主张真实调试可达；负例故意违反回放段外部过程'}, 'basis': ['受限转移定义§1允许有限条件种子；§2.1必须核显式补矿史是否持续充分']}
    record = run_input('空补矿史耗尽', data, 4)
    return {'status': record['status'], 'open_items': record['open_items'], 'summaries': [t['summary'] for t in record['trace']['ticks']] if record['trace'] else None}


def short_coverage():
    """两刻仅启动首批，尚未执行 completed 输出分支。"""
    data = read(ROOT / '数据/样例/混做粉碎机两下游.json')
    record = run_input('仅开工未完成', data, 2)
    events = [e for t in record['trace']['ticks'] for e in t['events']]
    return {'status': record['status'], 'completed_events': [e for e in events if e['operation'] == 'manufacture_complete'], 'manufacture_success': [e for e in events if e['operation'] == 'manufacture' and e['outcome'] == 'success'], 'claimed_output_blocked': next(r for r in record['uncovered_axes'] if r['axis'] == 'manufacturing.output_blocked'), 'crusher_phases': [t['summary']['crusher_phase'] for t in record['trace']['ticks']]}


def permutation_checks():
    """同路径重复执行逐字节比对；实际反转三个非语义数组并延长至全部参考前缀。"""
    reports = []
    for name, ticks in [('混做粉碎机两下游', 4), ('分流器三路轮询', 12)]:
        data = read(ROOT / f'数据/样例/{name}.json')
        original = run_input('排列-' + name, data, ticks)
        path = OUT / ('排列-' + name + '-record.json')
        first_bytes = path.read_bytes()
        again = run_input('排列-' + name, data, ticks)
        second_bytes = path.read_bytes()
        modified = copy.deepcopy(data)
        changes = {}
        for field in ['units', 'physical_channels', 'buffer_channels']:
            modified['layout'][field].reverse()
            changes[field] = {'length': len(data['layout'][field]), 'changed': data['layout'][field] != modified['layout'][field]}
        shuffled = run_input('反转-' + name, modified, ticks)
        reports.append({'name': name, 'ticks': ticks, 'actual_permutation': changes, 'repeat_bytes_equal': first_bytes == second_bytes, 'repeat_trace_equal': original['trace'] == again['trace'], 'permuted_trace_equal': original['trace'] == shuffled['trace']})
    return reports


def main():
    report = {'integrity': integrity(), 'record_checks': record_checks(), 'manual_bridge': manual_bridge(), 'supply_exhaustion': supply_exhaustion(), 'short_coverage': short_coverage(), 'permutation_checks': permutation_checks()}
    write('独立检查结果.json', report)
    print(json.dumps({'integrity': report['integrity'], 'record_checks': [{k: r[k] for k in ['case','expected_accept','accepted']} for r in report['record_checks']], 'manual_match': report['manual_bridge']['expected_equals_actual'], 'supply_status': report['supply_exhaustion']['status'], 'short_coverage': report['short_coverage'], 'permutation_checks': report['permutation_checks']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
