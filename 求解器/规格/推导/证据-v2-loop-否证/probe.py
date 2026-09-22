"""Independent finite kernel probes. Writes only beside this script; python -B."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOLVER = ROOT / '求解器'
sys.path.insert(0, str(SOLVER / 'crates/kernel/tests'))
import build_fixtures as bf
bf.OUT = OUT
from runtime_example import quantity, time_value
from generate_examples import unit

BIN = SOLVER / 'target/release/kernel'
CFG = SOLVER / '规格/内核配置-v1.json'
COMMANDS = []

def save(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path

def put(data, slot, item, n):
    s = data['initial_state']['nonwarehouse']['value']
    row = next(r for r in s['inventory'] if r['slot'] == slot)
    row['contents'] = [] if not n else [dict(item=item, quantity=quantity(n),
        entered_at=time_value(-1) if ':transport:' in slot else None)]

def enable(data):
    for row in data['settings']['switches']:
        row['enabled'] = True

def invoke(mode, src, name, ticks=None):
    dest = OUT / (name + '.json')
    cmd = [str(BIN), mode, str(src), '--config', str(CFG), '--out', str(dest)]
    if ticks is not None:
        cmd += ['--ticks', str(ticks)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=55)
    result = json.loads(dest.read_text())
    COMMANDS.append(dict(command=cmd, exit=p.returncode, stdout=p.stdout,
                         stderr=p.stderr, status=result.get('status', result.get('schema'))))
    save('commands', COMMANDS)
    return dest, result

def run(name, data, ticks):
    seed = save(name + '-seed', data)
    canonical, derived = invoke('seed', seed, name + '-canonical')
    if derived.get('status') == 'invalid_input':
        return derived
    record, result = invoke('run', canonical, name + '-run', ticks)
    invoke('verify-record', record, name + '-verified')
    return result

def compact(result):
    if result.get('status') != 'completed':
        return dict(status=result.get('status'), open_items=result.get('open_items'), trajectory_executed=False)
    rows = []
    for tick in result['trace']['ticks']:
        state = tick['state']
        rows.append(dict(time=tick['time'],
            inventory={r['slot']: {c['item']: int(c['quantity']['value']) for c in r['contents']}
                       for r in state['inventory'] if r['contents']},
            progress=state['progress']))
    return rows

def main():
    protected = [ROOT / n for n in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    save('protected-before', hashes)
    # Same machine and same item totals; front-of-line order alone differs.
    mixed = bf.generate('mixed-layout', [unit('grinder', '研磨机', 10, 10),
        unit('front', '传送带', 12, 9), unit('middle', '传送带', 12, 8),
        unit('back', '传送带', 12, 7), unit('power', '供电桩', 17, 11)])
    enable(mixed)
    put(mixed, 'grinder:input:0', '蓝铁粉末', 50)
    results = {}
    for name, seq, full in [('head-block', ['蓝铁粉末', '蓝铁粉末', '砂叶粉末'], False),
                            ('head-release', ['砂叶粉末', '蓝铁粉末', '蓝铁粉末'], False),
                            ('full-inputs', ['蓝铁粉末', '蓝铁粉末', '砂叶粉末'], True)]:
        data = copy.deepcopy(mixed)
        if full:
            put(data, 'grinder:input:1', '砂叶粉末', 50)
        for uid, item in zip(['front', 'middle', 'back'], seq):
            put(data, uid + ':transport:0', item, 1)
        results[name] = compact(run(name, data, 12))
    # H has old completed seeds. The window admits at 0 and 5, not every tick.
    gate = bf.generate('gate-layout', [unit('harvest', '采种机', 10, 10),
        unit('gate', '物品准入口', 12, 15), unit('planter', '种植机', 10, 16),
        unit('crusher', '粉碎机', 18, 13), unit('power', '供电桩', 16, 17)])
    enable(gate)
    gate['settings']['gates'][0].update(item='荞花种子', window_limit=quantity(1))
    put(gate, 'harvest:input:0', '荞花', 50)
    put(gate, 'harvest:output:0', '荞花种子', 50)
    put(gate, 'harvest:buffer:0', '荞花种子', 2)
    put(gate, 'crusher:input:0', '荞花', 10)
    pr = next(p for p in gate['initial_state']['nonwarehouse']['value']['progress'] if p['unit'] == 'harvest')
    pr.update(phase='completed', recipe='采种-荞花', locked_recipe='采种-荞花',
              candidate_recipes=['采种-荞花'], remaining=time_value(0))
    results['gate-first-release'] = compact(run('gate-first-release', gate, 8))
    save('probe-results', results)
    assert all(r['status'] == 'invalid_input' and not r['trajectory_executed'] for r in results.values())
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    assert after == hashes
    save('protected-after-probes', after)
    print(json.dumps({'status': 'blocked_before_execution', 'cases': list(results), 'kernel_sha256': hashlib.sha256(BIN.read_bytes()).hexdigest()}, ensure_ascii=False))

if __name__ == '__main__':
    main()
