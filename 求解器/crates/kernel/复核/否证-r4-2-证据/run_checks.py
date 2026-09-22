"""内核第4轮第2否证席：由当前样例新建单因素对照，仅写本证据目录。"""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
BASE = ROOT / '数据/样例'
CFG = ROOT / '规格/内核配置-v1.json'
BIN = ROOT / 'target/debug/kernel'
COMMANDS = []

def read(path):
    return json.loads(Path(path).read_text())

def save(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path

def source(name):
    path = BASE / (name + '.json')
    data = read(path)
    for ref in [data['catalog'], data['parameters']['axis_registry']]:
        ref['path'] = str((path.parent / ref['path']).resolve())
    return data

def state(data):
    return data['initial_state']['nonwarehouse']['value']

def quantity(value):
    return dict(value=str(value), category='候选')

def time(value):
    return dict(kind='rational', value=quantity(value))

def axis(data, name, value):
    matches = 0
    for group in ['fixed', 'offline_mutable', 'fixedness_unproven']:
        if name in data['parameters'][group]:
            data['parameters'][group][name]['value'] = copy.deepcopy(value)
            matches += 1
    assert matches == 1
    for row in state(data)['semantic_context']['parameter_values']:
        if row['axis'] == name:
            row['value']['value'] = copy.deepcopy(value)

def invoke(name, mode, data, *flags):
    path = save(name + '-input', data) if isinstance(data, dict) else data
    target = OUT / (name + '-result.json')
    command = [str(BIN), mode, str(path), '--config', str(CFG), '--out', str(target), *flags]
    proc = subprocess.run(command, text=True, capture_output=True, timeout=60)
    (OUT / (name + '.log')).write_text(proc.stdout + proc.stderr)
    result = read(target)
    COMMANDS.append(dict(case=name, command=command, exit_code=proc.returncode,
                         status=result.get('status', result.get('schema')),
                         open_items=result.get('open_items'), stop=result.get('stop')))
    save('commands', COMMANDS)
    return result, proc.returncode

def differences(left, right, path=''):
    if type(left) is not type(right):
        return [path]
    if isinstance(left, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            child = path + '/' + key
            result += [child] if key not in left or key not in right else differences(left[key], right[key], child)
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [path]
        return [item for i, (a, b) in enumerate(zip(left, right)) for item in differences(a, b, path + '/' + str(i))]
    return [] if left == right else [path]

def build_probe():
    # Rust源码通过标准输入编译，二进制和编译中间产物均进入共享target。
    code = r'''
use kernel::{Config, Engine, Input, Result, value::read_json};
use serde_json::{Value, json};
use std::path::Path;
fn inspect(path: &Path, config_path: &Path) -> Result<Value> {
    let config = Config::parse(read_json(config_path)?)?;
    let input = Input::load(path, &config, false)?;
    let engine = Engine::new(input)?;
    let method_key = engine.cycle_key()?;
    let function_key = kernel::cycle::cycle_key(&engine.state, &engine.input)?;
    Ok(json!({"status":"accepted", "both_interfaces_equal": method_key == function_key, "key":method_key}))
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let result = match inspect(Path::new(&args[1]), Path::new(&args[2])) {
        Ok(value) => value,
        Err(error) => json!({"status":"rejected", "error":error.to_string()})
    };
    println!("{}", result);
}
'''
    deps = ROOT / 'target/debug/deps'
    # 优先使用本次cargo生成的公开库链接；serde_json必须来自同一依赖目录。
    lib = ROOT / 'target/debug/libkernel.rlib'
    serde = max(deps.glob('libserde_json-*.rlib'), key=lambda p: p.stat().st_mtime)
    binary = ROOT / 'target/refutation-r4-2-key-probe'
    command = ['rustc', '--edition=2021', '--crate-name', 'refutation_r4_2_key_probe', '-',
               '--extern', 'kernel=' + str(lib), '--extern', 'serde_json=' + str(serde),
               '-L', 'dependency=' + str(deps), '-o', str(binary)]
    proc = subprocess.run(command, input=code, text=True, capture_output=True, cwd=ROOT / 'target')
    (OUT / 'probe-build.log').write_text(proc.stdout + proc.stderr)
    assert proc.returncode == 0, proc.stderr
    save('probe-build', dict(command=command, exit_code=proc.returncode,
                             kernel_rlib_sha256=hashlib.sha256(lib.read_bytes()).hexdigest()))
    return binary

def validate_schema(cases):
    script = r'''
const fs = require('fs');
const Ajv = require(process.argv[1]).default;
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const ajv = new Ajv({strict:false, allErrors:true});
const validate = ajv.compile(payload.schema);
const rows = payload.cases.map(c => {
  const ok = validate(c.value);
  return {case:c.case, valid:ok, errors:validate.errors || []};
});
process.stdout.write(JSON.stringify(rows));
'''
    module = '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
    proc = subprocess.run(['node', '-e', script, module], text=True, capture_output=True,
                          input=json.dumps(dict(schema=read(ROOT / '规格/内核输出.schema.json'), cases=cases)))
    (OUT / 'schema-validation.log').write_text(proc.stderr)
    assert proc.returncode == 0, proc.stderr
    rows = json.loads(proc.stdout)
    save('schema-results', dict(validator='AJV 2020', module=module, cases=rows))
    return rows

def main():
    summary = {}
    splitter = source('分流器三路轮询')
    control, code = invoke('branch-control', 'run', splitter, '--ticks', '12')
    assert code == 0 and len(control['trace']['ticks']) == 12
    # 按正式分级规则独立计算完整几何图中的级数上界。
    catalog = read(ROOT / '数据/正式静态目录.json')
    family = {row['id']: row['family'] for row in catalog['units']}
    kinds = {row['id']: row['kind'] for row in splitter['layout']['units']}
    levels = {uid: set() for uid, kind in kinds.items() if family[kind] not in ['transport', 'power']}
    for channel in splitter['layout']['physical_channels']:
        src = channel['source_port'].split(':')[0]
        dst = channel['target_port'].split(':')[0]
        if src in levels:
            levels[src].add('direct:' + channel['id'] if kinds[dst] == '汇流器' else 'other')
    assert max(map(len, levels.values())) == 1
    empty = copy.deepcopy(splitter)
    branch = copy.deepcopy(empty['parameters']['fixedness_unproven']['damping.branch']['value'])
    branch['choices'] = []
    axis(empty, 'damping.branch', branch)
    missing, code = invoke('branch-empty', 'run', empty, '--ticks', '12')
    assert code == 2 and missing['status'] == 'unresolved'
    summary['branch_scope'] = dict(control_ticks=12, full_geometry_output_levels={k: sorted(v) for k, v in levels.items()},
                                  input_differences=differences(splitter, empty), empty_status=missing['status'],
                                  empty_reason=missing['open_items'])

    ages = []
    for name, contents in [
        ('age-single', [dict(item='高容谷地电池', quantity=quantity(2), entered_at=time(-2))]),
        ('age-cohorts', [dict(item='高容谷地电池', quantity=quantity(1), entered_at=time(t)) for t in [-2, -1]]),
        ('age-mixed-control', [dict(item=item, quantity=quantity(1), entered_at=time(-2)) for item in ['高容谷地电池', '精选荞愈胶囊']]),
    ]:
        trial = copy.deepcopy(splitter)
        next(row for row in state(trial)['inventory'] if row['slot'] == 'south_box:storage:0')['contents'] = contents
        result, code = invoke(name, 'seed', trial)
        ages.append(dict(case=name, exit_code=code, status=result.get('status', result['schema']),
                         reason=result.get('open_items'), contents=contents))
    assert [r['exit_code'] for r in ages] == [0, 2, 2]
    summary['age_cohorts'] = ages

    crusher = source('混做粉碎机两下游')
    record, code = invoke('crusher-control', 'run', crusher, '--ticks', '3')
    assert code == 0
    checkpoint = copy.deepcopy(crusher)
    checkpoint['initial_state']['nonwarehouse']['value'] = copy.deepcopy(record['trace']['ticks'][1]['state'])
    checked, code = invoke('checkpoint-seed', 'seed', checkpoint)
    assert code == 0 and state(checked) == state(checkpoint)
    resumed, code = invoke('checkpoint-resume-control', 'run', checkpoint, '--ticks', '1')
    assert code == 0 and resumed['trace']['ticks'][0]['time'] == time(2)
    stopped, code = invoke('checkpoint-budget', 'run', checkpoint, '--ticks', '1', '--max-sweeps', '1')
    assert code == 2 and stopped['status'] == 'inconclusive' and stopped['trace'] is None
    delta, code = invoke('checkpoint-budget-delta', 'run', checkpoint, '--ticks', '1', '--max-sweeps', '1', '--format', 'checkpoint_delta')
    assert code == 2 and delta['trace'] is None
    summary['checkpoint_budget'] = dict(seed_verified_unchanged=True, start_time=state(checkpoint)['environment']['time'],
                                        phase=state(checkpoint)['semantic_context']['judgment_context']['value']['phase'],
                                        successful_control_first_time=resumed['trace']['ticks'][0]['time'],
                                        status=stopped['status'], trace=stopped['trace'], reason=stopped['open_items'],
                                        delta_trace=delta['trace'])

    keybase = copy.deepcopy(checkpoint)
    axis(keybase, 'warehouse.external_supply', dict(kind='sufficient'))
    probe = build_probe()
    keys = []
    for name, extra in [('key-control', False), ('key-extra', True)]:
        trial = copy.deepcopy(keybase)
        if extra:
            state(trial)['semantic_context']['pending_events']['value'][0]['trigger']['extra'] = '未定义扩展'
        result, code = invoke(name + '-seed', 'seed', trial)
        assert code == 0
        path = OUT / (name + '-seed-input.json')
        command = [str(probe), str(path), str(CFG)]
        proc = subprocess.run(command, text=True, capture_output=True)
        key = json.loads(proc.stdout)
        save(name, key)
        assert key['status'] == 'accepted' and key['both_interfaces_equal']
        keys.append(key['key'])
        COMMANDS.append(dict(case=name, command=command, exit_code=proc.returncode, status=key['status']))
    changes = differences(*keys)
    assert changes == ['/state/semantic_context/pending_events/value/0/trigger/extra']
    summary['unknown_trigger'] = dict(seed_cli_accepted=True, both_public_key_interfaces_accepted=True, only_key_differences=changes)
    invalid_trigger = copy.deepcopy(keybase)
    state(invalid_trigger)['semantic_context']['pending_events']['value'][0]['trigger']['kind'] = 'unknown_kind'
    result, code = invoke('key-kind-negative-control', 'seed', invalid_trigger)
    assert code == 2
    summary['unknown_trigger']['known_kind_check_control'] = result['status']

    adjacency, code = invoke('adjacency-three-ticks', 'run', source('阻尼连续带核验'), '--ticks', '3')
    assert code == 0
    verified, code = invoke('adjacency-verify', 'verify-record', OUT / 'adjacency-three-ticks-result.json')
    assert code == 0 and verified['status'] == 'input_checked'
    axis_row = next(row for row in adjacency['uncovered_axes'] if row['axis'] == 'damping.belt_adjacency')
    assert axis_row['coverage_status'] == 'exercised'
    event = next(event for tick in adjacency['trace']['ticks'] for event in tick['events'] if event['event'] == axis_row['evidence'][0])
    original = read(BASE / '阻尼连续带核验-运行记录-v3-kernel.json')
    old_axis = next(row for row in original['uncovered_axes'] if row['axis'] == 'damping.belt_adjacency')
    audit = read(ROOT / 'crates/kernel/evidence/round5/audit-results.json')
    summary['adjacency'] = dict(new_axis=axis_row, first_event=event, verify=verified,
                               selected_component_rule=source('阻尼连续带核验')['parameters']['fixedness_unproven']['damping.belt_component_rule'],
                               original_evidence_count=len(old_axis['evidence']),
                               aggregate_coverage=audit.get('coverage', {}).get('damping.belt_adjacency'),
                               aggregate_missing=audit.get('required_unexercised'))

    ring = source('生产循环环带')
    cycle_control, code = invoke('cycle-control', 'cycle', ring, '--max-ticks', '2')
    # 正常预算用尽返回一个成功构造的循环结果，CLI退出0；结果仍是inconclusive。
    assert code == 0 and cycle_control['status'] == 'inconclusive' and cycle_control['run_record'] is not None
    overflow = copy.deepcopy(ring)
    next(row for row in state(overflow)['inventory'] if row['slot'] == 'a:transport:0')['contents'][0]['entered_at'] = time(-(2**63))
    cycle_bad, code = invoke('cycle-overflow', 'cycle', overflow, '--max-ticks', '2')
    assert code == 2 and cycle_bad['status'] == 'inconclusive' and cycle_bad['stop']['kind'] == 'resource'
    run_bad, code = invoke('run-overflow', 'run', overflow, '--ticks', '2')
    assert code == 2
    schema_rows = validate_schema([dict(case=name, value=value) for name, value in [
        ('cycle-control', cycle_control), ('cycle-overflow', cycle_bad), ('run-overflow', run_bad),
        ('checkpoint-budget', stopped), ('adjacency-three-ticks', adjacency)]])
    assert [row['valid'] for row in schema_rows] == [True, False, True, True, True]
    summary['load_resource_schema'] = dict(status=cycle_bad['status'], stop=cycle_bad['stop'], budget=cycle_bad['budget'],
                                          null_context=[k for k in ['seed', 'parameter_point', 'replay_input', 'run_record'] if cycle_bad[k] is None],
                                          schema_valid=False, ordinary_budget_schema_valid=True,
                                          input_differences=differences(ring, overflow))
    save('results', summary)
    save('commands', COMMANDS)
    print(json.dumps(dict(status='completed', commands=len(COMMANDS), sections=list(summary)), ensure_ascii=False))

if __name__ == '__main__':
    main()
