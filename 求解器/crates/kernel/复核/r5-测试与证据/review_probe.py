"""第五轮测试与证据席独立复跑；输出仅限本脚本目录。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from fractions import Fraction

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
BASE = ROOT / '数据/样例'
PRODUCTS = ('高容谷地电池', '精选荞愈胶囊')


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def read(path):
    return json.loads(Path(path).read_text())


def call(name, args, expected=0, cwd=ROOT):
    cmd = [str(BIN), *map(str, args), '--config', str(CFG)]
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    save(name + '.json', dict(command=cmd, cwd=str(cwd), returncode=p.returncode,
                             stdout=p.stdout, stderr=p.stderr))
    assert p.returncode == expected, (name, p.returncode, p.stdout, p.stderr)
    return json.loads(p.stdout) if p.stdout.strip() else None


def number(value):
    while isinstance(value, dict):
        value = value['value']
    return Fraction(value)


def period_audit(data):
    c = data['cycle']
    if c is None:
        return dict(status=data['status'], cycle=None, budget=data['budget'])
    period = number(c['period'])
    start, end = number(c['start_time']), number(c['end_time'])
    assert end - start == period
    assert [number(r['time']) for r in c['ledger']] == list(range(int(start) + 1, int(end) + 1))
    buckets = {}
    detail_buckets = {}
    for row in c['ledger']:
        ledger = row['warehouse_ledger']
        for route in ('core_inbound', 'wireless_inbound', 'port_outbound', 'external_supply', 'player_withdrawal', 'representative_adjustment'):
            for item in ledger[route]:
                key = (item['item'], route)
                detail_buckets[key] = detail_buckets.get(key, 0) + number(item['quantity'])
        for entry in ledger['totals']:
            assert number(entry['actual_inbound']) == number(entry['core_inbound']) + number(entry['wireless_inbound'])
            for field, value in entry.items():
                if field != 'item':
                    key = (entry['item'], field)
                    buckets[key] = buckets.get(key, 0) + number(value)
    for key, value in buckets.items():
        if key[1] != 'actual_inbound':
            assert value == detail_buckets.get(key, 0), (key, value)
    for row in c['totals']:
        for field, value in row.items():
            if field != 'item':
                assert number(value) == buckets.get((row['item'], field), 0)
    rates = []
    for product, target in zip(PRODUCTS, (Fraction(3, 5), Fraction(11, 20))):
        inbound = buckets.get((product, 'actual_inbound'), 0)
        average = inbound / period
        comparison = 'lt' if average < target else 'eq' if average == target else 'gt'
        given = next(r for r in c['rates'] if r['item'] == product)
        assert all(number(given[k]) == v for k, v in dict(inbound=inbound, period=period, average=average, target=target).items())
        assert comparison == given['comparison']
        rates.append(dict(item=product, inbound=str(inbound), period=str(period), average=str(average), target=str(target), comparison=comparison))
    return dict(status=data['status'], start=str(start), end=str(end), period=str(period), rates=rates,
                detail_totals=[dict(item=k[0], route=k[1], quantity=str(v)) for k, v in sorted(detail_buckets.items())])


def benchmark():
    reports = []
    paths = [ROOT / 'crates/kernel/tests/fixtures' / (n + '.json') for n in ('benchmark_brick_60', 'benchmark_brick', 'benchmark_candidate_b')]
    paths.append(BASE / '双成品制造砖.json')
    for path in paths:
        ticks = 32 if path.stem == '双成品制造砖' else 12
        modes = {}
        for mode in ('run', 'cycle'):
            dest = OUT / (path.stem + '-benchmark-cycle.json')
            cmd = [str(BIN), mode, str(path), '--config', str(CFG), '--ticks', str(ticks)]
            cmd += ['--no-output'] if mode == 'run' else ['--no-record', '--search-checkpoint-interval', '32', '--out', str(dest)]
            p = subprocess.run([sys.executable, '-B', str(ROOT / 'crates/kernel/tests/measure_command.py'), *cmd], capture_output=True, text=True, check=True)
            measured = json.loads(p.stdout)
            save(path.stem + '-' + mode + '-measurement.json', dict(command=cmd, **measured))
            assert measured['returncode'] == 0
            result = json.loads(measured['stdout']) if mode == 'run' else read(dest)
            modes[mode] = dict(wall_ms_per_tick=measured['wall_ns'] / 1e6 / ticks, max_rss_kb=measured['max_rss_kb'], status=result['status'])
            if mode == 'run':
                modes[mode].update(engine_ms_per_tick=int(result['elapsed_ns']) / 1e6 / ticks, completed_batches=result['completed_batches'], actual_inbound=result['actual_inbound'])
        target = 20 if 'candidate' in path.name else 1
        reports.append(dict(name=path.stem, ticks=ticks, modes=modes, target_ms_per_tick=target,
                            run_target_met=modes['run']['engine_ms_per_tick'] <= target,
                            cycle_wall_target_met=modes['cycle']['wall_ms_per_tick'] <= target))
        print('基准完成', path.stem, flush=True)
    save('benchmark-review.json', dict(binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(), reports=reports))


def cycles():
    audits = {}
    for name, ticks in [('桥接器双通路', 120), ('研磨混做核验', 120), ('生产循环环带', 120), ('双成品满仓起动试作', 512)]:
        dest = OUT / (name + '-cycle.json')
        call(name + '-search', ['cycle', BASE / (name + '.json'), '--max-ticks', ticks, '--no-record', '--out', dest])
        call(name + '-verify', ['verify-cycle', dest])
        audits[name] = period_audit(read(dest))
        print('循环复跑完成', name, audits[name]['status'], flush=True)
    call('K6-domain', ['check', BASE / '双成品满仓起动试作.json', '--cycle-domain'])
    run = call('K6-finite-run', ['run', BASE / '双成品满仓起动试作.json', '--ticks', 512, '--no-output'])
    audits['K6有限运行'] = run
    save('cycle-manual-audit.json', audits)


def tamper():
    source = OUT / 'reference-input.json'
    source.write_bytes((BASE / '桥接器双通路.json').read_bytes())
    cert_path = OUT / 'reference-cycle.json'
    call('reference-generate', ['cycle', source, '--max-ticks', 120, '--out', cert_path])
    cert = read(cert_path)
    call('reference-control', ['verify-cycle', cert_path])
    cases = []
    for label, path in [('record', Path(cert['run_record_ref']['path'])), ('input', source)]:
        original = path.read_bytes()
        index = original.index(b'\n')
        changed = original[:index] + b' ' + original[index + 1:]
        assert len(changed) == len(original) and sum(a != b for a, b in zip(original, changed)) == 1
        assert json.loads(changed) == json.loads(original)
        path.write_bytes(changed)
        p = call('tamper-' + label + '-one-byte', ['verify-cycle', cert_path], expected=2)
        cases.append(dict(case=label, changed_byte=index, parsed_json_equal=True, result=p))
        if label == 'input':
            # 单独放行来源清单，仍保留引用的旧摘要，确认引用自身也检查字节。
            isolated = copy.deepcopy(cert)
            for row in isolated['fingerprints']:
                if Path(row['path']) == path:
                    row['sha256'] = hashlib.sha256(changed).hexdigest()
            save('input-reference-isolated.json', isolated)
            result = call('tamper-input-reference-isolated', ['verify-cycle', OUT / 'input-reference-isolated.json'], expected=2)
            assert any('artifact_ref.sha256' in item for item in result['open_items'])
            cases.append(dict(case='input_reference_hash_isolated', result=result))
        path.write_bytes(original)
        call('tamper-' + label + '-restored', ['verify-cycle', cert_path])
    # 修改记录语义并重封引用摘要，确认验收不止依赖字节校验。
    path = Path(cert['run_record_ref']['path'])
    original = path.read_bytes()
    record = read(path)
    record['trace']['ticks'][0]['summary']['review_injected'] = True
    save(path.name, record)
    changed = copy.deepcopy(cert)
    changed['run_record_ref']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    save('reference-resealed.json', changed)
    cases.append(dict(case='semantic_record_resealed', result=call('tamper-record-resealed', ['verify-cycle', OUT / 'reference-resealed.json'], expected=2)))
    path.write_bytes(original)
    for label, field, value in [('missing_record', 'path', str(OUT / 'does-not-exist.json')),
                                ('wrong_format', 'format', 'kernel-output-v3/checkpoint_delta'),
                                ('wrong_producer', 'producer', {**cert['run_record_ref']['producer'], 'kind': 'manual_expected'})]:
        bad = copy.deepcopy(cert)
        bad['run_record_ref'][field] = value
        save('reference-' + label + '.json', bad)
        cases.append(dict(case=label, result=call('tamper-' + label, ['verify-cycle', OUT / ('reference-' + label + '.json')], expected=2)))
    # 相对路径统一以证书位置解释；工作目录故意改为target。
    relative = copy.deepcopy(cert)
    for field in ('replay_input_ref', 'run_record_ref'):
        relative[field]['path'] = os.path.relpath(relative[field]['path'], OUT)
        relative[field]['producer']['path'] = os.path.relpath(relative[field]['producer']['path'], OUT)
    for row in relative['fingerprints']:
        row['path'] = os.path.relpath(row['path'], OUT)
    relative['cycle']['normalization']['definition']['path'] = os.path.relpath(relative['cycle']['normalization']['definition']['path'], OUT)
    save('relative-cycle.json', relative)
    call('relative-different-cwd', ['verify-cycle', OUT / 'relative-cycle.json'], cwd=ROOT / 'target')
    save('reference-tamper-results.json', cases)


if __name__ == '__main__':
    dict(benchmark=benchmark, cycles=cycles, tamper=tamper)[sys.argv[1]]()
