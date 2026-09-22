#!/usr/bin/env python3
"""第4轮公开CLI证据：库存年龄、trigger封闭、空分支、未用轴和停止锚点。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'crates/kernel/evidence/revision-r4/cli'
BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
CFG = ROOT / '规格/内核配置-v1.json'


def read(path):
    return json.loads(path.read_text())


def save(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def source(name):
    path = ROOT / f'数据/样例/{name}.json'
    value = read(path)
    for ref in [value['catalog'], value['parameters']['axis_registry']]:
        ref['path'] = str((path.parent / ref['path']).resolve())
    return value


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []

    def invoke(name, mode, path, expected, *options):
        output = OUT / (name + '-result.json')
        command = [str(BIN), mode, str(path), '--config', str(CFG), '--out', str(output), *options]
        if mode in ('run', 'cycle') and '--ticks' not in options:
            command += ['--ticks', '2']
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        value = read(output)
        status = value.get('status', value.get('schema'))
        assert status == expected, (name, result.returncode, value)
        assert result.returncode == (0 if expected in ('completed', 'kernel-input-v3') else 2)
        assert 'panicked' not in result.stderr
        cases.append(dict(name=name, command=command, exit_code=result.returncode,
                          output=str(output), status=status, stderr=result.stderr))
        return value, output

    raw = source('桥接器双通路')
    rows = raw['initial_state']['nonwarehouse']['value']['inventory']
    box = next(r for r in rows if r['slot'] == 'south_box:storage:0')
    first = copy.deepcopy(box['contents'][0]); first['quantity']['value'] = '1'
    first['entered_at']['value']['value'] = '-2'
    second = copy.deepcopy(first); second['entered_at']['value']['value'] = '-1'
    box['contents'] = [first, second]
    seeded, path = invoke('age-cohorts-seed', 'seed', save('age-cohorts-input', raw), 'kernel-input-v3')
    assert next(r for r in seeded['initial_state']['nonwarehouse']['value']['inventory'] if r['slot'] == box['slot'])['contents'] == box['contents']
    invoke('age-cohorts-run', 'run', path, 'completed', '--ticks', '3')

    raw = source('分流器三路轮询')
    raw['parameters']['fixedness_unproven']['damping.branch']['value']['choices'] = []
    for row in raw['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
        if row['axis'] == 'damping.branch':
            row['value']['value']['choices'] = []
    _, path = invoke('empty-branch-seed', 'seed', save('empty-branch-input', raw), 'kernel-input-v3')
    empty, _ = invoke('empty-branch-run', 'run', path, 'completed', '--ticks', '12')
    full, _ = invoke('full-branch-run', 'run', save('full-branch-input', source('分流器三路轮询')), 'completed', '--ticks', '12')
    for a, b in zip(empty['trace']['ticks'], full['trace']['ticks']):
        a = copy.deepcopy(a); b = copy.deepcopy(b)
        for tick in (a, b):
            tick['state']['semantic_context']['parameter_values'] = []
        assert a == b

    original = source('研磨混做核验')
    run, _ = invoke('working-prefix', 'run', save('working-input', original), 'completed', '--ticks', '12')
    state = next(t['state'] for t in run['trace']['ticks'] if t['state']['semantic_context']['pending_events']['value'])
    original['initial_state']['nonwarehouse']['value'] = copy.deepcopy(state)
    original['initial_state']['nonwarehouse']['value']['semantic_context']['pending_events']['value'][0]['trigger']['extra'] = True
    path = save('extra-trigger-input', original)
    for mode in ('seed', 'run', 'cycle'):
        value, _ = invoke('extra-trigger-' + mode, mode, path, 'invalid_input')
        assert 'trigger' in json.dumps(value['open_items'])

    prefix, _ = invoke('closed-prefix', 'run', save('closed-input', source('混做粉碎机两下游')), 'completed', '--ticks', '2')
    raw = source('混做粉碎机两下游')
    state = prefix['trace']['ticks'][-1]['state']
    raw['initial_state']['nonwarehouse']['value'] = state
    seeded, path = invoke('closed-seed', 'seed', save('closed-checkpoint-input', raw), 'kernel-input-v3')
    assert seeded['initial_state']['nonwarehouse']['value'] == state
    for fmt in ('full_state_each_instant', 'checkpoint_delta'):
        result, _ = invoke('closed-stop-' + fmt, 'run', path, 'inconclusive', '--ticks', '1', '--max-sweeps', '1', '--format', fmt)
        assert result['trace']['start_state'] == state and result['trace']['ticks'] == []
        assert result['trace']['end_time'] == state['environment']['time']
        assert result['validation_scope']['through'] == state['environment']['time']
        assert 'instant=2' in str(result['open_items'])

    record, path = invoke('path-runs', 'run', save('path-runs-input', source('阻尼连续带核验')), 'completed', '--ticks', '3')
    axis = next(a for a in record['uncovered_axes'] if a['axis'] == 'damping.belt_adjacency')
    assert axis['coverage_status'] == 'not_exercised' and not any('belt_adjacency:' in b for t in record['trace']['ticks'] for e in t['events'] for b in e['basis'])
    valid = subprocess.run([str(BIN), 'verify-record', str(path), '--config', str(CFG)], capture_output=True, text=True)
    assert valid.returncode == 0, valid.stderr
    axis['coverage_status'] = 'exercised'
    invalid = subprocess.run([str(BIN), 'verify-record', str(save('forged-adjacency', record)), '--config', str(CFG)], capture_output=True, text=True)
    assert invalid.returncode == 2

    raw = source('生产循环环带')
    row = next(r for r in raw['initial_state']['nonwarehouse']['value']['inventory'] if r['contents'])
    row['contents'][0]['entered_at']['value']['value'] = str(-(2**63))
    result, _ = invoke('age-overflow-cycle', 'cycle', save('age-overflow-input', raw), 'inconclusive')
    assert result['stop']['kind'] == 'resource' and result['budget']['completed_ticks'] == 0
    assert all(result[k] is None for k in ('seed', 'parameter_point', 'replay_input_ref', 'run_record_ref', 'last_state', 'cycle'))

    # 独立AJV2020直接读当前schema，不以仓库手写schema验收器替代。
    schema_path = ROOT / '规格/内核输出.schema.json'
    documents = [dict(name=c['name'], value=read(Path(c['output']))) for c in cases if c['status'] != 'kernel-input-v3']
    script = """const fs=require('fs'),Ajv=require(process.argv[1]);
const payload=JSON.parse(fs.readFileSync(0,'utf8'));
const validate=new Ajv({strict:false,allErrors:true}).compile(payload.schema);
console.log(JSON.stringify(payload.documents.map(d=>({name:d.name,valid:validate(d.value),errors:validate.errors}))));"""
    checked = subprocess.run(['node', '-e', script, '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'],
                             input=json.dumps(dict(schema=read(schema_path), documents=documents)),
                             capture_output=True, text=True, check=True)
    schema_results = json.loads(checked.stdout)
    failures = [r for r in schema_results if not r['valid']]
    assert failures == [], failures
    report = dict(status='pass', cases=cases,
                  schema_sha256=hashlib.sha256(schema_path.read_bytes()).hexdigest(), schema_results=schema_results,
                  open_schema_gaps=[],
                  forged_coverage_rejected=True, full_and_empty_branch_ticks_equal_except_parameter_point=True)
    save('results', report)
    print(json.dumps(dict(status=report['status'], calls=len(cases), schema_passed=len(schema_results)-len(failures), schema_failed=len(failures)), ensure_ascii=False))


if __name__ == '__main__':
    main()
