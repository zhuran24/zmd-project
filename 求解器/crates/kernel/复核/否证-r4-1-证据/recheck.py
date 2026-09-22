"""内核否证第4轮第1席：从当前样例构造对照，调用公开入口独立复验。"""
from pathlib import Path
import copy
import hashlib
import json
import subprocess

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = Path(__file__).resolve().parent
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
COMMANDS = []


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def call(command, stdin=None):
    process = subprocess.run([str(x) for x in command], input=stdin,
                             capture_output=True, text=True, timeout=60)
    COMMANDS.append(dict(command=[str(x) for x in command],
                         exit_code=process.returncode,
                         stdout=process.stdout, stderr=process.stderr))
    write('commands', COMMANDS)
    return process


def invoke(name, mode, source, *extra):
    path = write(name + '-input', source) if isinstance(source, dict) else source
    target = OUT / (name + '-result.json')
    process = call([BIN, mode, path, '--config', CFG, '--out', target, *extra])
    return read(target), process.returncode


def sample(name):
    path = ROOT / '数据/样例' / (name + '.json')
    raw = read(path)
    for reference in [raw['catalog'], raw['parameters']['axis_registry']]:
        reference['path'] = str((path.parent / reference['path']).resolve())
    return raw


def state(raw):
    return raw['initial_state']['nonwarehouse']['value']


def set_axis(raw, name, value):
    for group in ['fixed', 'after_reconnect', 'fixedness_unproven']:
        if name in raw['parameters'].get(group, {}):
            raw['parameters'][group][name]['value'] = copy.deepcopy(value)
    for row in state(raw)['semantic_context']['parameter_values']:
        if row['axis'] == name:
            row['value']['value'] = copy.deepcopy(value)


def time(value):
    return dict(kind='rational', value=dict(value=str(value), category='候选'))


def content(quantity, age):
    return dict(item='高容谷地电池',
                quantity=dict(value=str(quantity), category='候选'), entered_at=time(age))


def axis_coverage(record, name):
    return next(row for row in record['uncovered_axes'] if row['axis'] == name)


def main():
    # 以正式样例新派生调度起点，避免依赖前席保存的种子答案。
    splitter, code = invoke('splitter-seed', 'seed', sample('分流器三路轮询'))
    assert code == 0
    ages = []
    for name, contents in [('one-age', [content(2, -2)]),
                           ('two-ages', [content(1, -2), content(1, -1)])]:
        raw = copy.deepcopy(splitter)
        row = next(row for row in state(raw)['inventory'] if row['slot'] == 'south_box:storage:0')
        row['contents'] = contents
        result, code = invoke(name, 'seed', raw)
        ages.append(dict(case=name, exit_code=code,
                         status=result.get('status', result['schema']),
                         open_items=result.get('open_items'), contents=contents))
    assert ages[0]['exit_code'] == 0 and ages[1]['status'] == 'invalid_input'
    write('age-results', ages)

    # 按正式取货分级独立枚举完整几何图的最大级集合。
    kinds = {row['id']: row['kind'] for row in splitter['layout']['units']}
    transport = {'传送带', '桥接器', '分流器', '汇流器', '物品准入口'}
    levels = {unit: set() for unit, kind in kinds.items() if kind not in transport | {'供电桩'}}
    for channel in splitter['layout']['physical_channels']:
        source = channel['source_port'].split(':')[0]
        target = channel['target_port'].split(':')[0]
        if source in levels:
            levels[source].add('direct:' + channel['id'] if kinds[target] == '汇流器' else 'other')
    assert all(len(value) <= 1 for value in levels.values())
    full, full_code = invoke('branch-full', 'run', splitter, '--ticks', '12')
    empty = copy.deepcopy(splitter)
    branch = copy.deepcopy(empty['parameters']['fixedness_unproven']['damping.branch']['value'])
    original_count = len(branch['choices'])
    branch['choices'] = []
    set_axis(empty, 'damping.branch', branch)
    empty_result, empty_code = invoke('branch-empty', 'run', empty, '--ticks', '12')
    assert full_code == 0 and empty_result['status'] == 'unresolved'
    write('branch-results', dict(maximum_geometric_output_levels={k: sorted(v) for k, v in levels.items()},
          original_choices=original_count, full_status=full['status'],
          completed_ticks=len(full['trace']['ticks']), empty_status=empty_result['status'],
          empty_exit_code=empty_code, open_items=empty_result['open_items'],
          control_coverage=axis_coverage(full, 'damping.branch')))

    # 实际运行产生t=1检查点，再由seed严格校验，最后测试首个续跑时刻。
    crusher = sample('混做粉碎机两下游')
    run, code = invoke('crusher', 'run', crusher, '--ticks', '3')
    assert code == 0
    closed = copy.deepcopy(crusher)
    closed['initial_state']['nonwarehouse']['value'] = copy.deepcopy(run['trace']['ticks'][1]['state'])
    checkpoint, code = invoke('checkpoint', 'seed', closed)
    assert code == 0 and state(checkpoint) == state(closed)
    resumed, code = invoke('checkpoint-resumed', 'run', checkpoint, '--ticks', '1')
    assert code == 0 and resumed['trace']['ticks'][0]['state'] == run['trace']['ticks'][2]['state']
    prefix_results = []
    for name, format_name in [('full', 'full_state_each_instant'), ('delta', 'checkpoint_delta')]:
        stopped, code = invoke('checkpoint-stop-' + name, 'run', checkpoint,
                               '--ticks', '1', '--max-sweeps', '1', '--format', format_name)
        assert code == 2 and stopped['status'] == 'inconclusive' and stopped['trace'] is None
        prefix_results.append(dict(format=format_name, exit_code=code,
            trace=stopped['trace'], status=stopped['status'],
            parameters_present=stopped['parameter_assignment'] is not None,
            history_present=stopped['input_history'] is not None, open_items=stopped['open_items']))
    write('checkpoint-results', dict(seed_identical=True,
          seed_time=state(checkpoint)['environment']['time'],
          seed_phase=state(checkpoint)['semantic_context']['judgment_context']['value']['phase'],
          full_budget_next_time=resumed['trace']['ticks'][0]['time'],
          full_budget_next_state_matches=True, limited=prefix_results))

    # 未知trigger成员只加一处；公开cycle_key必须经过Engine装载。
    unknown = copy.deepcopy(checkpoint)
    state(unknown)['semantic_context']['pending_events']['value'][0]['trigger']['extra'] = '未定义扩展'
    exported, code = invoke('trigger-extra', 'seed', unknown)
    assert code == 0
    assert state(exported)['semantic_context']['pending_events']['value'][0]['trigger']['extra'] == '未定义扩展'
    key_source = r'''
use kernel::{Config,Engine,Input,Result,value::read_json};
use serde_json::{Value,json};
use std::path::Path;
fn inspect(path: &Path, config_path: &Path) -> Result<Value> {
    let config = Config::parse(read_json(config_path)?)?;
    let engine = Engine::new(Input::load(path, &config, false)?)?;
    Ok(json!({"status":"accepted","key":engine.cycle_key()?}))
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let result = match inspect(Path::new(&args[1]), Path::new(&args[2])) {
        Ok(value) => value,
        Err(error) => json!({"status":"rejected","error":error.to_string()})
    };
    println!("{}", result);
}
'''
    serde = max((ROOT / 'target/release/deps').glob('libserde_json-*.rlib'), key=lambda p: p.stat().st_mtime_ns)
    probe = ROOT / 'target/refutation_r4_seat1_key'
    build = call(['rustc', '--edition=2021', '--crate-name', 'refutation_r4_seat1_key', '-',
                  '--extern', 'kernel=' + str(ROOT / 'target/release/libkernel.rlib'),
                  '--extern', 'serde_json=' + str(serde), '-L',
                  'dependency=' + str(ROOT / 'target/release/deps'), '-o', probe], key_source)
    (OUT / 'key-build.log').write_text(build.stdout + build.stderr)
    assert build.returncode == 0
    keys = []
    for name, raw in [('control', checkpoint), ('extra', unknown)]:
        raw = copy.deepcopy(raw)
        set_axis(raw, 'warehouse.external_supply', {'kind': 'sufficient'})
        path = write('key-' + name + '-input', raw)
        process = call([probe, path, CFG])
        key = json.loads(process.stdout)
        write('key-' + name + '-result', key)
        assert key['status'] == 'accepted'
        keys.append(key['key'])
    altered = copy.deepcopy(keys[1])
    extra = altered['state']['semantic_context']['pending_events']['value'][0]['trigger'].pop('extra')
    assert altered == keys[0]
    write('trigger-results', dict(seed_accepted=True, public_key_accepted=[True, True],
          only_difference='/state/semantic_context/pending_events/value/0/trigger/extra', extra=extra))

    # 新跑连续带样例及公开验收器，检查实际标记和已有聚合报告。
    belts, code = invoke('belts', 'run', sample('阻尼连续带核验'), '--ticks', '3')
    assert code == 0
    verified, code = invoke('belts-verify', 'verify-record', OUT / 'belts-result.json')
    assert code == 0
    coverage = axis_coverage(belts, 'damping.belt_adjacency')
    assert coverage['coverage_status'] == 'exercised'
    first = next(event for row in belts['trace']['ticks'] for event in row['events']
                 if event['event'] == coverage['evidence'][0])
    old = read(ROOT / '数据/样例/阻尼连续带核验-运行记录-v3-kernel.json')
    old_axis = axis_coverage(old, 'damping.belt_adjacency')
    audit = read(ROOT / 'crates/kernel/evidence/round5/audit-results.json')
    write('coverage-results', dict(new_axis=coverage, first_event=first,
          verify_result=verified, old_axis_status=old_axis['coverage_status'],
          old_evidence_count=len(old_axis['evidence']),
          aggregate_missing=audit['required_unexercised'],
          aggregate_claim=audit['coverage'].get('damping.belt_adjacency')))

    # 用实际CLI生成装载资源溢出及正常周期对照，再交给独立AJV2020。
    ring = sample('生产循环环带')
    normal, code = invoke('cycle-control', 'cycle', ring, '--max-ticks', '30')
    assert code == 0 and normal['cycle'] is not None
    overflow = copy.deepcopy(ring)
    row = next(row for row in state(overflow)['inventory'] if row['slot'].endswith(':transport:0') and row['contents'])
    row['contents'][0]['entered_at'] = time(-9223372036854775808)
    failed, code = invoke('cycle-overflow', 'cycle', overflow, '--max-ticks', '30')
    assert code == 2 and failed['status'] == 'inconclusive'
    assert failed['stop']['kind'] == 'resource' and failed['stop']['axis'] == 'resource.integer'
    schema_script = r'''
const fs = require('fs');
const Ajv = require('/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const ajv = new Ajv({strict:false, allErrors:true});
const validate = ajv.compile(payload.schema);
const results = payload.cases.map(row => ({name:row.name, valid:validate(row.data),
    errors:structuredClone(validate.errors || [])}));
process.stdout.write(JSON.stringify(results));
'''
    process = call(['node', '-e', schema_script], json.dumps(dict(
        schema=read(ROOT / '规格/内核输出.schema.json'),
        cases=[dict(name='cycle-control', data=normal), dict(name='cycle-overflow', data=failed),
               dict(name='valid-continuation', data=resumed)]), ensure_ascii=False))
    assert process.returncode == 0
    schema_results = json.loads(process.stdout)
    assert [row['valid'] for row in schema_results] == [True, False, True]
    write('schema-results', dict(validator='AJV2020', cases=schema_results,
          resource_result=dict(status=failed['status'], stop=failed['stop'], budget=failed['budget'],
              null_context=[k for k in ['seed','parameter_point','replay_input','run_record'] if failed[k] is None])))
    write('summary', dict(status='completed', independent_cli_and_probe_calls=len(COMMANDS),
          binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),
          findings_reproduced=['KR-r4-L1-01','KR-r4-L1-02','KR-r4-L1-03',
              'KR-r4-L1-04','KR-r4-L1-05','KR-r4-L2-1','KR-r4-L2-2']))
    print(json.dumps(read(OUT / 'summary.json'), ensure_ascii=False))


if __name__ == '__main__':
    main()
