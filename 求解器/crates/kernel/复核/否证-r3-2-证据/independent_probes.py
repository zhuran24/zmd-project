"""第3轮第2否证席：公开入口对照，只向本席证据目录写入。"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import subprocess
import collections

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
RESULTS = []
SOURCES = {}


def read(path):
    path = Path(path)
    data = path.read_bytes()
    SOURCES[str(path)] = hashlib.sha256(data).hexdigest()
    return json.loads(data)


def save(name, data):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return path


def source(name):
    path = ROOT / '数据/样例' / (name + '.json')
    data = read(path)
    for ref in (data['catalog'], data['parameters']['axis_registry']):
        ref['path'] = str((path.parent / ref['path']).resolve())
    reach = data['initial_state']['reachability']['value']
    if isinstance(reach, dict) and 'document' in reach:
        reach['document'] = str((path.parent / reach['document']).resolve())
    return data


def invoke(name, command, data, ticks=None):
    path = save(name + '-input', data) if isinstance(data, dict) else data
    dest = OUT / (name + '-result.json')
    dest.unlink(missing_ok=True)
    args = [str(BIN), command, str(path), '--config', str(CFG), '--out', str(dest)]
    if ticks is not None:
        args += ['--max-ticks' if command == 'cycle' else '--ticks', str(ticks)]
    proc = subprocess.run(args, text=True, capture_output=True, timeout=90)
    value = json.loads(dest.read_text()) if dest.exists() else None
    row = dict(name=name, command=args, exit_code=proc.returncode, stdout=proc.stdout,
               stderr=proc.stderr, result_path=str(dest) if value is not None else None,
               status=value.get('status') if value else None,
               schema=value.get('schema') if value else None,
               stop=value.get('stop') if value else None,
               open_items=value.get('open_items') if value else None)
    RESULTS.append(row)
    (OUT / (name + '.log')).write_text(json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    save('cli-results', RESULTS)
    print(name, proc.returncode, row['status'], flush=True)
    return value


def state(raw):
    return raw['initial_state']['nonwarehouse']['value']


def time(value):
    return {'kind': 'rational', 'value': {'value': str(value), 'category': '候选'}}


def mirror_phase(raw, value):
    decision = raw['parameters']['fixedness_unproven']['transfer.phase']
    decision['value']['values'][0]['remaining'] = value
    next(r for r in state(raw)['semantic_context']['parameter_values']
         if r['axis'] == 'transfer.phase')['value'] = deepcopy(decision)


def main():
    # 真实执行后再取检查点；不借用旧结果中的检查点作为本席正例。
    bridge = source('桥接器双通路')
    bridge_run = invoke('bridge-fresh', 'run', bridge, 30)
    assert bridge_run['status'] == 'completed'
    checkpoint = deepcopy(bridge)
    checkpoint['initial_state']['nonwarehouse']['value'] = deepcopy(bridge_run['trace']['ticks'][5]['state'])
    summaries = []
    for name in ('control', 'missing', 'snapshot-conflict', 'top-conflict'):
        raw = deepcopy(checkpoint)
        values = state(raw)['semantic_context']['parameter_values']
        if name == 'missing':
            state(raw)['semantic_context']['parameter_values'] = []
        elif name == 'snapshot-conflict':
            next(r for r in values if r['axis'] == 'transfer.phase')['value']['value']['values'][0]['remaining'] = time(4)
        elif name == 'top-conflict':
            raw['parameters']['fixedness_unproven']['transfer.phase']['value']['values'][0]['remaining'] = time(4)
        direct = invoke('checkpoint-' + name + '-direct', 'run', raw, 2)
        seeded = invoke('checkpoint-' + name + '-seed', 'seed', raw)
        resumed = invoke('checkpoint-' + name + '-resumed', 'run', OUT / ('checkpoint-' + name + '-seed-result.json'), 2)
        summaries.append(dict(case=name, direct_status=direct['status'], seed_schema=seeded['schema'],
                              state_preserved=state(raw) == state(seeded), resumed_status=resumed['status']))
    save('checkpoint-summary', summaries)
    crusher = source('混做粉碎机两下游')
    crusher_run = invoke('crusher-control', 'run', crusher, 4)
    drift = deepcopy(crusher)
    drift['initial_state']['nonwarehouse']['value'] = deepcopy(crusher_run['trace']['ticks'][1]['state'])
    drift['parameters']['fixedness_unproven']['warehouse.external_supply']['value'] = {'kind': 'sufficient'}
    invoke('supply-conflict-direct', 'run', drift, 1)
    invoke('supply-conflict-seed', 'seed', drift)
    invoke('supply-conflict-resumed', 'run', OUT / 'supply-conflict-seed-result.json', 2)

    # 区分合法历史初相位与非法类型/范围；当前冷却始终不变。
    for name, value in [('valid0', time(0)), ('valid4', time(4)), ('negative', time(-1)),
                        ('large', time(6)), ('fraction', time('1/2')), ('malformed', 'not-a-Time')]:
        raw = deepcopy(checkpoint)
        mirror_phase(raw, value)
        invoke('phase-' + name, 'run', raw, 2)
    ring = source('生产循环环带')
    ring_cycle = invoke('ring-control', 'cycle', ring, 25)
    invoke('ring-control-verify', 'verify-cycle', OUT / 'ring-control-result.json')
    bad_phase = deepcopy(ring)
    bad_phase['initial_state']['nonwarehouse']['value'] = deepcopy(ring_cycle['cycle']['start_state'])
    mirror_phase(bad_phase, 'not-a-Time')
    invoke('phase-cycle', 'cycle', bad_phase, 25)
    invoke('phase-cycle-verify', 'verify-cycle', OUT / 'phase-cycle-result.json')

    # 同一实际第5刻窗口只将起点和截止各提前1；同时检查早于/等于/晚于锚点。
    splitter = source('分流器三路轮询')
    split_run = invoke('splitter-control', 'run', splitter, 7)
    for shift, name in [(0, 'future'), (1, 'equal'), (2, 'past')]:
        raw = deepcopy(splitter)
        raw['initial_state']['nonwarehouse']['value'] = deepcopy(split_run['trace']['ticks'][5]['state'])
        for gate in state(raw)['logistics']['gate_counters']:
            if gate['window_started_at'] is not None:
                gate['window_started_at']['value']['value'] = str(int(gate['window_started_at']['value']['value']) - shift)
                pending = next(p for p in state(raw)['semantic_context']['pending_events']['value'] if p['target'] == gate['unit'])
                due = int(pending['trigger']['value']['value']['value']) - shift
                pending['trigger']['value']['value']['value'] = str(due)
                pending['event'] = f"W|{due}|{gate['unit']}"
        invoke('window-' + name + '-seed', 'seed', raw)
        got = invoke('window-' + name, 'run', raw, 1)
        if got['status'] == 'completed':
            invoke('window-' + name + '-verify', 'verify-record', OUT / ('window-' + name + '-result.json'))

    # 最小布局来自已读复核fixture；重新运行合法对照后才构造非法待办。
    tiny = read(ROOT / 'crates/kernel/复核/r3-规格保真-证据/tiny-control-input.json')
    tiny_run = invoke('tiny-control', 'run', tiny, 6)
    tiny['initial_state']['nonwarehouse']['value'] = deepcopy(tiny_run['trace']['ticks'][-1]['state'])
    tiny['settings']['gates'][0].update(item='源矿', window_limit={'value': '1', 'category': '候选'})
    state(tiny)['logistics']['gate_counters'][0].update(total_received={'value': '1', 'category': '候选'},
        window_received={'value': '1', 'category': '候选'}, window_started_at=time(0), blocked_reasons=['window_exhausted'])
    state(tiny)['semantic_context']['pending_events']['value'] = [dict(event='W|5|gate', operation='gate_window_expiry',
        target='gate', trigger={'kind': 'at_time', 'value': time(5)}, predecessors=[], status='waiting')]
    tiny_cycle = invoke('expired-cycle', 'cycle', tiny, 3)
    invoke('expired-cycle-verify', 'verify-cycle', OUT / 'expired-cycle-result.json')
    invoke('expired-embedded-verify', 'verify-record', save('expired-embedded-record', tiny_cycle['run_record']))

    # 缺矿与历史空格身份分开；初始任务仓库不改，只改调试后种子。
    for ore in ('源矿', '蓝铁矿'):
        zero = deepcopy(ring)
        slot = next(r for r in state(zero)['warehouse']['slots'] if r['item'] == ore)
        slot.update(item=None, quantity={'value': '0', 'category': '候选'},
                    empty_identity={'status': 'specified', 'value': ore, 'basis': ['否证席缺矿负例']})
        invoke('zero-' + ore + '-seed', 'seed', zero)
        invoke('zero-' + ore + '-run', 'run', OUT / ('zero-' + ore + '-seed-result.json'), 1)

    # 输入非法与受支持错误通道对照，记录panic原始stderr而不捕获成正常Stop。
    for label in ('bad', 'bad:input:0'):
        raw = deepcopy(crusher)
        state(raw)['inventory'][0]['slot'] = label
        invoke('slot-' + ('short' if label == 'bad' else 'unknown'), 'run', raw, 1)
    raw = deepcopy(crusher)
    raw['initial_state']['nonwarehouse']['value'] = True
    invoke('seed-bool', 'seed', raw)
    overflow = deepcopy(ring)
    item = next(r['contents'][0] for r in state(overflow)['inventory'] if ':transport:' in r['slot'] and r['contents'])
    item['entered_at'] = time(-(2 ** 63))
    invoke('overflow-run', 'run', overflow, 2)
    invoke('overflow-cycle', 'cycle', overflow, 2)

    # 覆盖标签逐项回溯到真实操作、输入轴状态与历史时刻。
    axis = next(r for r in bridge_run['uncovered_axes'] if r['axis'] == 'connection.bridge_first_contact')
    by_id = {e['event']: dict(time=t['time'], **e) for t in bridge_run['trace']['ticks'] for e in t['events']}
    cited = [by_id[i] for i in axis['evidence']]
    times = {r['id']: r['time'] for r in bridge['timeline']['events']}
    history = [dict(row=r, time=times[r['event']]) for r in bridge['timeline']['connection_events']]
    incoming = collections.Counter()
    outgoing = collections.Counter()
    for tick in bridge_run['trace']['ticks']:
        for move in tick['state']['semantic_context']['tick_context']['value']['movements']:
            a, b = move['channel'].split('|')[1:]
            if b.startswith('bridge:'):
                incoming[b] += int(move['quantity']['value'])
            if a.startswith('bridge:'):
                outgoing[a] += int(move['quantity']['value'])
    wireless = collections.Counter()
    for tick in bridge_run['trace']['ticks']:
        for flow in tick['warehouse_ledger']['wireless_inbound']:
            wireless[flow['item']] += int(flow['quantity']['value'])
    audit = read(ROOT / 'crates/kernel/evidence/round5/audit-results.json')
    save('bridge-coverage', dict(axis=axis, cited_events=cited, bridge_units=[u for u in bridge['layout']['units'] if u['kind'] == '桥接器'],
        history=history, incoming=dict(incoming), outgoing=dict(outgoing), wireless=dict(wireless),
        first_time=bridge_run['trace']['ticks'][0]['time'], last_time=bridge_run['trace']['ticks'][-1]['time'],
        aggregate_axis=audit['coverage'].get('connection.bridge_first_contact'), required_unexercised=audit['required_unexercised']))
    invoke('bridge-fresh-verify', 'verify-record', OUT / 'bridge-fresh-result.json')
    save('source-fingerprints', dict(sources=SOURCES, binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest()))


if __name__ == '__main__':
    main()
