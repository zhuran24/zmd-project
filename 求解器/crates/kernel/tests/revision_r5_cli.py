"""修订r5公共入口回归；仅在round6/revision-r5内保存试样、JSON和原始日志。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from verify_all import schema_check
from checkpoint_delta import encode_trace
from check_golden_trace import run as reference_run
from runtime_record import build_record

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '数据/样例'
E = ROOT / 'crates/kernel/evidence/round6/revision-r5/cli'
BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
CFG = ROOT / '规格/内核配置-v1.json'
CASES = []


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def call(name, *args, code=0, cwd=ROOT):
    command = [str(BIN), *map(str, args), '--config', str(CFG)]
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    (E / (name + '.log')).write_text(json.dumps(dict(command=command, cwd=str(cwd),
        exit=result.returncode), ensure_ascii=False) + '\n' + result.stdout + result.stderr)
    assert result.returncode == code, (name, result.returncode, result.stdout, result.stderr)
    assert 'panicked' not in result.stderr
    value = json.loads(result.stdout)
    CASES.append(dict(name=name, exit=result.returncode, result=value))
    return value


def relative_record(record, directory):
    result = copy.deepcopy(record)
    for row in result['fingerprints']:
        row['path'] = os.path.relpath(row['path'], directory)
    result['producer']['path'] = os.path.relpath(result['producer']['path'], directory)
    return result


def main():
    E.mkdir(parents=True, exist_ok=True)
    positives = []
    source = BASE / '生产循环环带.json'
    certificate = E / 'original-cycle.json'
    call('generate-cycle', 'cycle', source, '--max-ticks', 50, '--out', certificate)
    cycle = read(certificate)
    record = read(Path(cycle['run_record_ref']['path']))
    # 证书与记录分属不同子目录，所有相对路径必须使用各自基目录。
    package = E / 'package'
    for encoding in ('full_state_each_instant', 'checkpoint_delta'):
        directory = package / encoding / 'records'
        given = copy.deepcopy(record)
        if encoding == 'checkpoint_delta':
            given['trace'] = encode_trace(given['trace'], 3)
        relative = save(directory / 'record.json', relative_record(given, directory))
        positives.append(relative)
        for label, cwd in [('root', ROOT), ('local', directory), ('foreign', ROOT.parent)]:
            call(encoding + '-verify-' + label, 'verify-record', relative, cwd=cwd)
        resumed = E / (encoding + '-checkpoint.json')
        call(encoding + '-checkpoint', 'checkpoint', relative, '--out', resumed, cwd=ROOT.parent)
        assert read(resumed)['initial_state']['nonwarehouse']['value'] == cycle['cycle']['end_state']
        continuation = E / (encoding + '-continued.json')
        call(encoding + '-continue', 'run', resumed, '--ticks', 2, '--out', continuation)
        assert int(read(continuation)['trace']['ticks'][0]['time']['value']['value']) == int(record['trace']['end_time']['value']['value']) + 1
        cert_dir = package / encoding / 'certificates'
        cert = copy.deepcopy(cycle)
        cert['run_record_ref'].update(path=str(relative.resolve()),
            sha256=hashlib.sha256(relative.read_bytes()).hexdigest(),
            format='kernel-output-v4/' + encoding)
        for key in ('run_record_ref', 'replay_input_ref'):
            cert[key]['path'] = os.path.relpath(cert[key]['path'], cert_dir)
            cert[key]['producer']['path'] = os.path.relpath(cert[key]['producer']['path'], cert_dir)
        for row in cert['fingerprints']:
            row['path'] = os.path.relpath(row['path'], cert_dir)
        definition = cert['cycle']['normalization']['definition']
        definition['path'] = os.path.relpath(definition['path'], cert_dir)
        cert_path = save(cert_dir / 'cycle.json', cert)
        positives.append(cert_path)
        assert call(encoding + '-cycle-verify', 'verify-cycle', cert_path, cwd=ROOT.parent)['cycle_replayed']
        call(encoding + '-cycle-checkpoint', 'checkpoint', cert_path, '--out', E / (encoding + '-cycle-input.json'))
    call('relative-production-batch', 'verify-batch', package, cwd=ROOT.parent)

    # 当前batch只接kernel v4；路径等价正例和参考生产者拒收分别验证。
    reference_dir = E / 'reference-package'
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        raw = read(BASE / (name + '.json'))
        expected = reference_run(raw)
        generated = E / (name + '-absolute.json')
        call(name + '-finite', 'run', BASE / (name + '.json'), '--ticks', len(expected), '--out', generated)
        for encoding in ('full_state_each_instant', 'checkpoint_delta'):
            given = read(generated)
            if encoding == 'checkpoint_delta': given['trace'] = encode_trace(given['trace'], 3)
            p = save(reference_dir / (name + '-' + encoding + '.json'), relative_record(given, reference_dir))
            positives.append(p)
            call(name + '-' + encoding, 'verify-record', p, cwd=ROOT.parent)
        bounded = build_record(raw, expected, read(BASE / '混做粉碎机两下游-黄金轨迹.json') if name.startswith('混做') else None)
        p = save(E / 'bounded-reference-package' / (name + '-reference.json'), relative_record(bounded, E / 'bounded-reference-package'))
        positives.append(p)
    call('relative-reference-batch', 'verify-batch', reference_dir, cwd=ROOT.parent)
    rejected = subprocess.run([str(BIN), 'verify-batch', str(E / 'bounded-reference-package'),
                               '--config', str(CFG)], cwd=ROOT.parent, capture_output=True, text=True)
    assert rejected.returncode == 2 and not rejected.stdout.strip()
    assert '当前批量入口仅支持kernel生产者' in rejected.stderr
    (E / 'bounded-reference-batch-unsupported.log').write_text(rejected.stderr)
    CASES.append(dict(name='bounded-reference-batch-unsupported', exit_code=2))

    # 有限模式允许矿量影响容量；生产装载含交叉游标试样一律先停于D.2。
    raw = read(ROOT / 'crates/kernel/tests/fixtures/core_inbound.json')
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if 'warehouse.external_supply' in raw['parameters'][group]:
            raw['parameters'][group]['warehouse.external_supply']['value'] = {'kind': 'sufficient'}
    state = raw['initial_state']['nonwarehouse']['value']
    next(r for r in state['inventory'] if r['slot'] == 'belt:transport:0')['contents'] = [
        dict(item='源矿', quantity=dict(value='1', category='候选'),
            entered_at=dict(kind='rational', value=dict(value='-1', category='候选')))]
    seeds = []
    for quantity in (79999, 80000):
        next(r for r in state['warehouse']['slots'] if r['item'] == '源矿')['quantity']['value'] = str(quantity)
        raw_path = save(E / f'ore-{quantity}-raw.json', raw)
        seed_path = E / f'ore-{quantity}-seed.json'
        call(f'ore-{quantity}-seed', 'seed', raw_path, '--out', seed_path)
        seeds.append(read(seed_path))
        call(f'ore-{quantity}-finite', 'run', seed_path, '--ticks', 2, '--out', E / f'ore-{quantity}-finite.json')
    memories = [s['initial_state']['nonwarehouse']['value']['logistics']['poll_memory'] for s in seeds]
    assert memories[0] != memories[1]
    crossed = copy.deepcopy(seeds[0])
    crossed['initial_state']['nonwarehouse']['value']['warehouse'] = seeds[1]['initial_state']['nonwarehouse']['value']['warehouse']
    save(E / 'ore-crossed-seed.json', crossed)
    for label in ('79999', '80000', 'crossed'):
        seed_path = E / f'ore-{label}-seed.json'
        before = seed_path.read_bytes()
        report = call(f'ore-{label}-domain', 'check', seed_path, '--cycle-domain', code=2)
        assert report['trajectory_executed'] is False and report['domain_report'][1]['status'] == 'fail'
        assert report['domain_report'][3]['status'] == 'unresolved'
        assert all(r['scope'] == 'static' for r in report['domain_report'])
        shell = E / f'ore-{label}-cycle.json'
        call(f'ore-{label}-cycle', 'cycle', seed_path, '--max-ticks', 2, '--no-record', '--out', shell, code=2)
        assert read(shell)['stop']['axis'] == 'cycle.domain.D2'
        assert call(f'ore-{label}-verify', 'verify-cycle', shell)['diagnostic_replayed']
        assert before == seed_path.read_bytes()
        positives.append(shell)
    save(E / 'ore-memory-comparison.json', dict(finite_memory_equal=False, memories=memories,
        production_stop='cycle.domain.D2', scope='两种有限容量与交叉游标；生产装载先于可动级校验停止'))

    # 合法装载诊断不等于可恢复状态，三种停止分类均须结构化拒收checkpoint。
    raw = read(source)
    for ref in (raw['catalog'], raw['parameters']['axis_registry']):
        ref['path'] = str((BASE / ref['path']).resolve())
    for kind in ('resource', 'invalid', 'unsupported'):
        bad = copy.deepcopy(raw)
        state = bad['initial_state']['nonwarehouse']['value']
        if kind == 'resource':
            next(r for r in state['inventory'] if r['contents'])['contents'][0]['entered_at']['value']['value'] = str(-(2 ** 63))
        elif kind == 'invalid':
            bad['initial_state']['nonwarehouse']['value'] = True
        else:
            state['semantic_context']['judgment_context']['value']['phase'] = 'in_closure'
        bad_path = save(E / (kind + '-input.json'), bad)
        shell = E / (kind + '-shell.json')
        call(kind + '-shell-generate', 'cycle', bad_path, '--max-ticks', 2, '--out', shell, code=2)
        verified = call(kind + '-diagnostic', 'verify-cycle', shell)
        assert verified['diagnostic_replayed'] and not verified['cycle_replayed']
        rejected = E / (kind + '-checkpoint-result.json')
        call(kind + '-checkpoint', 'checkpoint', shell, '--out', rejected, code=2)
        result = read(rejected)
        assert result['status'] == 'invalid_input' and result['trace'] is None
        assert 'checkpoint.recovery' in json.dumps(result, ensure_ascii=False)
        positives.append(shell)
    # 已装载零刻前缀确实有输入和状态，仍允许续跑；不能把所有inconclusive都拒收。
    zero = E / 'zero-prefix.json'
    call('zero-generate', 'cycle', source, '--max-ticks', 2, '--max-sweeps', 1, '--no-record', '--out', zero)
    checkpoint = E / 'zero-checkpoint.json'
    call('zero-checkpoint', 'checkpoint', zero, '--out', checkpoint)
    assert read(checkpoint)['initial_state']['nonwarehouse']['value'] == read(zero)['last_state']

    # 规范路径不能掩盖来源缺失、摘要错误、producer冒名、删依赖或轨迹篡改。
    for name, mutate in [
        ('hash', lambda r: r['fingerprints'][0].update(sha256='0' * 64)),
        ('missing', lambda r: r['fingerprints'][0].update(path='missing.json')),
        ('dependency', lambda r: r['fingerprints'].pop()),
        ('producer', lambda r: r['producer'].update(claim='冒名')),
        ('state', lambda r: r['trace']['ticks'][-1]['state']['warehouse']['slots'][0]['quantity'].update(value='7')),
    ]:
        bad = relative_record(record, E / 'negative')
        mutate(bad)
        p = save(E / 'negative' / (name + '.json'), bad)
        call('reject-' + name, 'verify-record', p, code=2, cwd=ROOT.parent)
    schema_check(positives)
    save(E / 'results.json', dict(status='pass', cases=CASES, positive_schema_documents=len(positives)))
    print(json.dumps(dict(status='pass', cases=len(CASES), positive_schema_documents=len(positives)), ensure_ascii=False))


if __name__ == '__main__':
    main()
