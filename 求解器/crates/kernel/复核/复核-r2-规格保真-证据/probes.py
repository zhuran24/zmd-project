"""第2轮规格复核：所有输入、执行记录和结果只写本证据目录。"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
CONFIG = ROOT / '规格/内核配置-v1.json'
BIN = OUT / 'target/debug/kernel'
PROBE = OUT / 'target/debug/spec_review_probe'
sys.path.insert(0, str(ROOT / '数据/样例'))
from runtime_example import quantity, time_value, decision


def write(name, data):
    """原始字节与输入一起保存，供复跑定位。"""
    p = OUT / (name + '.json')
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return p


def load(name):
    """只读正式样例，副本将相对来源路径转为绝对路径。"""
    source = ROOT / ('数据/样例/' + name + '.json')
    data = json.loads(source.read_text())
    for ref in (data['catalog'], data['parameters']['axis_registry']):
        ref['path'] = str((source.parent / ref['path']).resolve())
    return data


def set_axis(data, name, value):
    """显式参数与种子当前参数保持一致。"""
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if name in data['parameters'][group]:
            data['parameters'][group][name]['value'] = copy.deepcopy(value)
    for row in data['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
        if row['axis'] == name:
            row['value']['value'] = copy.deepcopy(value)


def invoke(name, data, ticks=2, query=None):
    """公开CLI及库入口；不直接改引擎内存来制造后效。"""
    source = write(name + '-input', data)
    record = OUT / (name + '-record.json')
    command = [str(BIN), 'run', str(source), '--config', str(CONFIG), '--ticks', str(ticks), '--out', str(record)]
    proc = subprocess.run(command, capture_output=True, text=True)
    result = {'case': name, 'command': command, 'exit_code': proc.returncode, 'stderr': proc.stderr}
    rec = json.loads(record.read_text())
    result.update(status=rec['status'], open_items=rec['open_items'])
    if rec['trace']:
        result['events'] = [[e['event'] for e in t['events'] if e['operation'] in ('manufacture_complete', 'ore_supply')] for t in rec['trace']['ticks']]
        audit = subprocess.run([str(PROBE),str(source),str(CONFIG),'verify',str(record)],capture_output=True,text=True)
        result['record_verification'] = json.loads(audit.stdout)
    if query:
        process = subprocess.run([str(PROBE), str(source), str(CONFIG), str(ticks), query], capture_output=True, text=True)
        probe = json.loads(process.stdout)
        write(name + '-library', probe)
        result['damping'] = [r.get('damping', r.get('stop')) for r in probe.get('observations', [])]
        result['load_error'] = probe.get('load_error')
    return result


def main():
    """关系交集、历史拥有关系与固定分支的有效对照/反例。"""
    results = []
    data = load('混做粉碎机两下游')
    seed = data['initial_state']['nonwarehouse']['value']
    for r in seed['inventory']:
        if r['slot'] == 'crusher:buffer:0':
            r['contents'] = [{'item': '源矿', 'quantity': quantity(1), 'entered_at': time_value(-1)}]
    for p in seed['progress']:
        if p['unit'] == 'crusher':
            p.update(phase='working', recipe='粉碎-源矿', locked_recipe='粉碎-源矿', candidate_recipes=['粉碎-源矿'], remaining=time_value(1))
    seed['semantic_context']['pending_events'] = decision([{'event': 'completion_probe', 'operation': 'manufacture_complete', 'target': 'crusher', 'trigger': {'kind': 'at_time', 'value': time_value(1)}, 'predecessors': [], 'status': 'waiting'}], '受限转移§1：恰一批在制种子')
    supply = copy.deepcopy(data['parameters']['fixedness_unproven']['warehouse.external_supply']['value'])
    supply['events'] = [{'event': 'supply_probe', 'time': time_value(1), 'item': '源矿', 'quantity': quantity(1)}]
    set_axis(data, 'warehouse.external_supply', supply)
    data['timeline']['events'] += [{'id': e, 'kind': 'runtime', 'time': time_value(1)} for e in ('completion_probe', 'supply_probe')]
    for name, first, last in [('phase-control', 'completion_probe', 'supply_probe'), ('phase-conflict', 'supply_probe', 'completion_probe')]:
        variant = copy.deepcopy(data)
        variant['timeline']['relations'].append({'before': first, 'after': last, 'relation': 'occurs_before', 'basis': ['输入§3.1：显式同刻关系']})
        results.append(invoke(name, variant))

    for kind in ('runtime', 'connection_close'):
        data = load('混做粉碎机两下游')
        data['timeline']['events'].append({'id': 'unowned_probe', 'kind': kind, 'time': time_value(1)})
        results.append(invoke('unowned-' + kind, data))

    # 复用既有布局构造函数的编码，不把其运行结论当规格。
    spec = importlib.util.spec_from_file_location('review_fixture_builder', ROOT / 'crates/kernel/tests/build_fixtures.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.OUT = OUT
    unit = builder.unit
    origin = 'PC|source:north:0|merge_a:south:0'
    chosen = 'PC|fork:north:0|gate:south:0'
    builder.generate('branch-base', [unit('source','协议储存箱',10,7), unit('merge_a','汇流器',10,10), unit('fork','分流器',10,11), unit('gate','物品准入口',10,12), unit('sink_a','协议储存箱',10,13), unit('sink_b','协议储存箱',7,9,'r90'), unit('merge_b','汇流器',12,10,'r270'), unit('sink_c','协议储存箱',13,8,'r270')], [{'channel':origin,'fork_unit':'fork','outgoing_channel':chosen}])
    data = json.loads((OUT/'branch-base.json').read_text())
    seed = data['initial_state']['nonwarehouse']['value']
    for row in seed['inventory']:
        if row['slot'] in ('source:storage:0','fork:transport:0'):
            row['contents']=[{'item':'源矿','quantity':quantity(5 if row['slot'].startswith('source:') else 1),'entered_at':time_value(-1)}]
    data['settings']['gates'][0].update(item='源矿', total_limit=quantity(1))
    movable = {c['id'] for c in data['layout']['physical_channels'] if c['source_port'].startswith(('source:', 'fork:'))}
    for side in seed['logistics']['poll_memory']['value']['sides']:
        if side['unit']=='fork' and side['side']=='output':
            side['levels'][0]['next_channel']=chosen
        if side['graded']:
            eligible=[l for l in side['levels'] if any(c in movable for c in l['members'])]
            if side['unit']=='source' and side['side']=='output':
                eligible=[l for l in eligible if any('merge_b:' in c for c in l['members'])]
            side['current_level']=eligible[0]['id'] if eligible else None
    order=copy.deepcopy(data['parameters']['fixed']['judgment.order']['value'])
    order['template_order'].sort(key=lambda t:0 if t['target']==chosen else 1)
    set_axis(data,'judgment.order',order)
    results.append(invoke('branch-cut',data,1,origin))
    control=copy.deepcopy(data)
    control['settings']['gates'][0]['total_limit']=None
    results.append(invoke('branch-retained',control,1,origin))
    write('探针结果',results)
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
