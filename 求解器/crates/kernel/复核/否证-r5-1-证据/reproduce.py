"""独立复核三条发现；只写本目录，编译探针只写共享 target。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
CALLS = []


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def call(name, command, cwd=ROOT, stdin=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    proc = subprocess.run(list(map(str, command)), cwd=cwd, input=stdin,
                          capture_output=True, text=True, env=env, timeout=120)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    entry = dict(name=name, command=list(map(str, command)), cwd=str(cwd),
                 exit_code=proc.returncode, result=data, stderr=proc.stderr)
    CALLS.append(entry)
    (HERE / f'{name}.log').write_text(json.dumps(entry, ensure_ascii=False, indent=2)
                                    + '\nSTDOUT\n' + proc.stdout + '\nSTDERR\n' + proc.stderr)
    save(HERE / 'commands.json', CALLS)
    return entry


def kernel(name, *args, cwd=ROOT):
    return call(name, [BIN, *args, '--config', CFG], cwd)


def probe_constructor():
    # 通过公开 API 观察真实构造后记忆，不改被审源码或插桩。
    source = r'''
use kernel::{Config, Engine, Input, value::read_json};
use serde_json::json;
use std::path::Path;
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let config = Config::parse(read_json(Path::new(&args[1])).unwrap()).unwrap();
    let rows: Vec<_> = args[2..].iter().map(|path| {
        let input = Input::load(Path::new(path), &config, false).unwrap();
        match Engine::new(input) {
            Ok(engine) => json!({"path":path,"constructor":"ok",
                "production_abstraction":engine.production_abstraction,
                "memory":engine.memory,"domain_report":engine.domain_report("static")}),
            Err(stop) => json!({"path":path,"constructor":"error","stop":stop}),
        }
    }).collect();
    println!("{}", serde_json::to_string_pretty(&rows).unwrap());
}
'''
    deps = ROOT / 'target/release/deps'
    # rlib 若有多版，逐个尝试链接；只使用当前 kernel 库依赖的同一版。
    binary = ROOT / 'target/r5_seat1_constructor_probe'
    for index, library in enumerate(sorted(deps.glob('libserde_json-*.rlib'))):
        built = call(f'constructor-build-{index}', [
            'rustc', '--edition=2021', '--crate-name', 'r5_seat1_constructor_probe', '-',
            '-L', f'dependency={deps}', '--extern', f'kernel={ROOT}/target/release/libkernel.rlib',
            '--extern', f'serde_json={library}', '-o', binary], stdin=source)
        if built['exit_code'] == 0:
            return binary
    raise AssertionError('构造探针编译失败')


def ore_cases():
    fixture = ROOT / 'crates/kernel/tests/fixtures/core_inbound.json'
    raw = read(fixture)
    # 将依赖路径以原输入目录解算，搬到本席目录不改变来源对象。
    raw['catalog']['path'] = str((fixture.parent / raw['catalog']['path']).resolve())
    raw['parameters']['axis_registry']['path'] = str(
        (fixture.parent / raw['parameters']['axis_registry']['path']).resolve())
    state = raw['initial_state']['nonwarehouse']['value']
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if 'warehouse.external_supply' in raw['parameters'][group]:
            raw['parameters'][group]['warehouse.external_supply']['value'] = {'kind': 'sufficient'}
    for row in state['semantic_context']['parameter_values']:
        if row['axis'] == 'warehouse.external_supply':
            row['value']['value'] = {'kind': 'sufficient'}
    next(row for row in state['inventory'] if row['slot'] == 'belt:transport:0')['contents'] = [
        {'item': '源矿', 'quantity': {'value': '1', 'category': '候选'},
         'entered_at': {'kind': 'rational', 'value': {'value': '-1', 'category': '候选'}}}]
    seeds = []
    for amount in (79999, 80000):
        variant = copy.deepcopy(raw)
        slots = variant['initial_state']['nonwarehouse']['value']['warehouse']['slots']
        next(row for row in slots if row['item'] == '源矿')['quantity']['value'] = str(amount)
        input_path = save(HERE / f'ore-{amount}-raw.json', variant)
        seed_path = HERE / f'ore-{amount}-seed.json'
        assert kernel(f'ore-{amount}-seed', 'seed', input_path, '--out', seed_path)['exit_code'] == 0
        seeds.append(seed_path)
        kernel(f'ore-{amount}-check', 'check', seed_path, '--cycle-domain')
        kernel(f'ore-{amount}-cycle', 'cycle', seed_path, '--max-ticks', 1,
               '--no-record', '--out', HERE / f'ore-{amount}-cycle.json')
        kernel(f'ore-{amount}-finite-run', 'run', seed_path, '--ticks', 1,
               '--out', HERE / f'ore-{amount}-finite-record.json')
    binary = probe_constructor()
    result = call('constructor-observation', [binary, CFG, *seeds])
    assert result['exit_code'] == 0
    observations = result['result']
    summary = []
    for amount, row in zip((79999, 80000), observations):
        assert row['constructor'] == 'ok' and not row['production_abstraction']
        core = next(s for s in row['memory']['sides'] if s['unit'] == 'core' and s['side'] == 'input')
        d2 = next(d for d in row['domain_report'] if d['condition'] == 'D.2')
        assert d2['status'] == 'fail'
        record = read(HERE / f'ore-{amount}-finite-record.json')
        summary.append(dict(ore=amount, constructor=row['constructor'],
                            production_abstraction=row['production_abstraction'],
                            core_current_level=core['current_level'], d2=d2,
                            finite_core_inbound=record['trace']['ticks'][0]['warehouse_ledger']['core_inbound']))
    assert summary[0]['core_current_level'] == 'L|core|input|other'
    assert summary[1]['core_current_level'] is None
    return save(HERE / 'ore-results.json', summary)


def relative_cases():
    absolute_dir = HERE / 'absolute-package'
    relative_dir = HERE / 'relative-package'
    absolute_dir.mkdir(exist_ok=True)
    relative_dir.mkdir(exist_ok=True)
    certificate_path = absolute_dir / 'certificate.json'
    generated = kernel('cycle-generate', 'cycle', ROOT / '数据/样例/生产循环环带.json',
                       '--max-ticks', 50, '--search-checkpoint-interval', 7, '--out', certificate_path)
    assert generated['exit_code'] == 0
    certificate = read(certificate_path)
    record_path = Path(certificate['run_record_ref']['path'])
    original = read(record_path)
    relative = copy.deepcopy(original)
    for row in relative['fingerprints']:
        row['path'] = os.path.relpath(row['path'], relative_dir)
    relative['producer']['path'] = os.path.relpath(relative['producer']['path'], relative_dir)
    relative_path = save(relative_dir / 'record.json', relative)
    relative_certificate = copy.deepcopy(certificate)
    relative_certificate['run_record_ref']['path'] = relative_path.name
    relative_certificate['run_record_ref']['sha256'] = sha(relative_path)
    relative_certificate['run_record_ref']['producer'] = copy.deepcopy(relative['producer'])
    relative_certificate_path = save(relative_dir / 'certificate.json', relative_certificate)
    canonical = copy.deepcopy(relative)
    for row in canonical['fingerprints']:
        row['path'] = str((relative_dir / row['path']).resolve())
        assert sha(Path(row['path'])) == row['sha256']
    canonical['producer']['path'] = str((relative_dir / canonical['producer']['path']).resolve())
    assert canonical == original
    save(HERE / 'relative-equality.json', dict(
        canonical_records_equal=True, unchanged_trace=relative['trace'] == original['trace'],
        source_fingerprints_unchanged=[r['sha256'] for r in relative['fingerprints']] ==
                                    [r['sha256'] for r in original['fingerprints']],
        raw_record_sha256_before=sha(record_path), raw_record_sha256_after=sha(relative_path)))
    for label, folder, rec, cert in [
            ('absolute', absolute_dir, record_path, certificate_path),
            ('relative', relative_dir, relative_path, relative_certificate_path)]:
        kernel(f'{label}-verify-cycle', 'verify-cycle', cert)
        kernel(f'{label}-verify-record-root', 'verify-record', rec)
        kernel(f'{label}-verify-record-local', 'verify-record', rec, cwd=folder)
        kernel(f'{label}-checkpoint', 'checkpoint', rec, '--out', HERE / f'{label}-checkpoint.json')
        kernel(f'{label}-batch', 'verify-batch', folder)
    return [record_path, certificate_path, relative_path, relative_certificate_path]


def shell_case():
    shell_path = ROOT / 'crates/kernel/evidence/round6/cli/overflow.json'
    shell = read(shell_path)
    assert shell['replay_input_ref'] is None and shell['last_state'] is None and shell['cycle'] is None
    kernel('load-shell-verify', 'verify-cycle', shell_path)
    destination = HERE / 'load-shell-checkpoint.json'
    kernel('load-shell-checkpoint', 'checkpoint', shell_path, '--out', destination)
    save(HERE / 'load-shell-state.json', dict(source=str(shell_path), sha256=sha(shell_path),
        status=shell['status'], stop=shell['stop'], replay_input_ref=shell['replay_input_ref'],
        last_state=shell['last_state'], cycle=shell['cycle'], checkpoint_created=destination.exists()))
    return shell_path


def schema_cases(paths):
    script = '''const fs=require('fs'),Ajv=require(process.argv[1]);
const request=JSON.parse(fs.readFileSync(0,'utf8'));
const validate=new Ajv({strict:false,allErrors:true}).compile(JSON.parse(fs.readFileSync(request.schema,'utf8')));
const rows=request.paths.map(path=>({path,valid:validate(JSON.parse(fs.readFileSync(path,'utf8'))),errors:validate.errors}));
console.log(JSON.stringify(rows));if(rows.some(r=>!r.valid))process.exit(1);'''
    result = call('schema-validation', ['node', '-e', script,
        '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'],
        stdin=json.dumps(dict(schema=str(ROOT/'规格/内核输出.schema.json'), paths=list(map(str, paths)))))
    assert result['exit_code'] == 0
    save(HERE / 'schema-results.json', result['result'])


def main():
    ore_cases()
    paths = relative_cases()
    paths.append(shell_case())
    schema_cases(paths)
    summary = [{k: c[k] for k in ('name', 'exit_code')} for c in CALLS]
    save(HERE / 'results.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
