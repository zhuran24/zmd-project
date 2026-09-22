"""复核输入探针：只在本文件目录写输入、运行记录和结果。"""
import copy
import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = json.loads((ROOT / '数据/样例/混做粉碎机两下游.json').read_text())


def quantity(value):
    return {'value': str(value), 'category': '候选'}


def time_value(value):
    return {'kind': 'rational', 'value': quantity(value)}


def decision(value):
    return {'status': 'specified', 'value': value, 'basis': ['复核隔离输入']}


def set_axis(data, name, value):
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if name in data['parameters'][group]:
            data['parameters'][group][name]['value'] = copy.deepcopy(value)
    for row in data['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
        if row['axis'] == name:
            row['value']['value'] = copy.deepcopy(value)


def run_case(name, data, ticks=4):
    data['catalog']['path'] = str(ROOT / '数据/正式静态目录.json')
    data['parameters']['axis_registry']['path'] = str(ROOT / '规格/选择点参数轴.md')
    source = OUT / f'{name}-input.json'
    record = OUT / f'{name}-record.json'
    source.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    command = [str(ROOT / 'target/release/kernel'), 'run', str(source), '--config', str(ROOT / '规格/内核配置-v1.json'), '--ticks', str(ticks), '--out', str(record)]
    process = subprocess.run(command, capture_output=True, text=True)
    result = json.loads(record.read_text())
    rows = (result['trace'] or {}).get('ticks', [])
    return {'name': name, 'command': command, 'exit_code': process.returncode, 'status': result['status'], 'ticks': len(rows), 'open_items': result['open_items'], 'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'record_sha256': hashlib.sha256(record.read_bytes()).hexdigest()}


def main():
    reports = []
    data = copy.deepcopy(BASE)
    data['initial_state']['nonwarehouse']['value']['warehouse']['slots'][0]['quantity'] = quantity(1)
    reports.append(run_case('ore-shortage', data))

    # 已给动作记录故意引用错误类型的全局 runtime，必须拒收，不能跳过动作。
    data = copy.deepcopy(BASE)
    data['timeline']['events'].append({'id': 'review_offline', 'kind': 'runtime', 'time': time_value(1)})
    data['environment']['offline']['selected_events'] = [{'event': 'review_offline', 'new_connection_order': decision([]), 'effects': {key: {'status': 'derived', 'value': 'offline.' + axis, 'basis': ['复核引用错误类型负例']} for key, axis in [('cursor', 'cursor_effect'), ('inventory', 'inventory_effect'), ('progress', 'progress_effect'), ('direction', 'direction_effect'), ('gate_total', 'gate_total_effect'), ('gate_window', 'gate_window_effect'), ('gate_window_start', 'gate_window_start_effect')]}}]
    data['environment']['offline']['event_domain'] = decision({'kind': 'selected_history', 'events': ['review_offline']})
    reports.append(run_case('offline-wrong-kind', data))
    data['timeline']['events'][-1]['kind'] = 'offline'
    reports.append(run_case('offline-control', data))

    # 同刻补给数组与统一时间线的执行关系相反。
    data = copy.deepcopy(BASE)
    data['initial_state']['nonwarehouse']['value']['warehouse']['slots'][0]['quantity'] = quantity(79990)
    events = [{'event': name, 'time': time_value(1), 'item': '源矿', 'quantity': quantity(1)} for name in ('supply_a', 'supply_b')]
    supply = copy.deepcopy(data['parameters']['fixedness_unproven']['warehouse.external_supply']['value'])
    supply['events'] = events
    set_axis(data, 'warehouse.external_supply', supply)
    data['timeline']['events'].extend({'id': name, 'kind': 'runtime', 'time': time_value(1)} for name in ('supply_a', 'supply_b'))
    data['timeline']['relations'].append({'before': 'supply_b', 'after': 'supply_a', 'relation': 'occurs_before', 'basis': ['复核同刻显式先后']})
    reports.append(run_case('supply-order-conflict', data))

    # 用真实输出生成已闭包种子；把待完成事件别名成已有建造事件。
    source_record = json.loads((ROOT / '数据/样例/混做粉碎机两下游-运行记录-kernel.json').read_text())
    data = copy.deepcopy(BASE)
    data['initial_state']['nonwarehouse']['value'] = copy.deepcopy(source_record['trace']['ticks'][1]['state'])
    pending = data['initial_state']['nonwarehouse']['value']['semantic_context']['pending_events']['value']
    assert len(pending) == 1
    pending[0]['event'] = data['construction']['moments'][0]['event']
    reports.append(run_case('pending-historical-alias', data, 1))
    data = copy.deepcopy(BASE)
    data['initial_state']['nonwarehouse']['value'] = copy.deepcopy(source_record['trace']['ticks'][1]['state'])
    reports.append(run_case('after-closure-control', data, 1))

    (OUT / 'input-probe-results.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps([{key: row[key] for key in ('name', 'status', 'ticks', 'exit_code')} for row in reports], ensure_ascii=False))


if __name__ == '__main__':
    main()
