#!/usr/bin/env python3
"""第3轮公开CLI回归：错误须有JSON结果，检查点不修补，资源未决不降格。"""
from evidence_paths import instance_dir
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = None
BIN = Path(os.environ.get('KERNEL_BIN', ROOT / 'target/release/kernel'))
CFG = ROOT / '规格/内核配置-v1.json'
REPORTS = []


def read(path):
    return json.loads(path.read_text())


def save(name, data):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return path


def source(name):
    path = ROOT / '数据/样例' / (name + '.json')
    data = read(path)
    for ref in [data['catalog'], data['parameters']['axis_registry']]:
        ref['path'] = str((path.parent / ref['path']).resolve())
    return data


def invoke(name, mode, path, expected, ticks=2):
    out = OUT / (name + '-result.json')
    out.unlink(missing_ok=True)
    command = [str(BIN), mode, str(path), '--config', str(CFG), '--out', str(out)]
    if mode in ('run', 'cycle'):
        command += ['--ticks', str(ticks)]
    process = subprocess.run(command, capture_output=True, text=True, timeout=90)
    assert out.exists(), (name, process.returncode, process.stdout, process.stderr)
    result = read(out)
    status = result.get('status', result.get('schema'))
    report = dict(case=name, command=command, exit_code=process.returncode, status=status,
                  output=str(out), open_items=result.get('open_items', []),
                  stop=result.get('stop'), stdout=process.stdout, stderr=process.stderr)
    REPORTS.append(report)
    assert process.returncode == (0 if expected in ('completed', 'kernel-input-v3', 'input_checked') else 2), report
    assert status == expected, report
    assert 'panicked' not in process.stderr, report
    return result


def reject_all(name, raw, status='invalid_input'):
    path = save(name + '-input', raw)
    for mode in ['run', 'seed', 'cycle']:
        expected = 'stopped' if mode == 'cycle' and status in ('unsupported', 'unresolved') else status
        result = invoke(name + '-' + mode, mode, path, expected)
        if expected == 'stopped':
            assert result['stop']['kind'] == status


def main():
    global OUT
    assert hashlib.sha256((ROOT / 'crates/kernel/复核/r3-规格保真-证据/gate-expired-after-closure-input.json').read_bytes()).hexdigest() == 'e3179739624643208053567874190b2dbc3e8a387b394e6105cc861cf62f5e19', 'required historical fixture mismatch: gate-expired-after-closure-input.json'
    assert hashlib.sha256((ROOT / 'crates/kernel/复核/r3-规格保真-证据/tiny-expired-cycle.json').read_bytes()).hexdigest() == '5d7fb60fd4ba78be19d47b39b9e728c98fe4c0f0ff68ec99158ba229f94e711d', 'required historical fixture mismatch: tiny-expired-cycle.json'
    OUT = instance_dir('revision_r3_cli')
    OUT.mkdir(parents=True, exist_ok=True)
    original = source('桥接器双通路')
    record = invoke('bridge-control', 'run', save('bridge-input', original), 'completed', ticks=7)
    checkpoint = copy.deepcopy(original)
    checkpoint['initial_state']['nonwarehouse']['value'] = copy.deepcopy(record['trace']['ticks'][5]['state'])
    path = save('checkpoint-control', checkpoint)
    derived = invoke('checkpoint-seed', 'seed', path, 'kernel-input-v3')
    assert derived['initial_state']['nonwarehouse'] == checkpoint['initial_state']['nonwarehouse']
    direct = invoke('checkpoint-run', 'run', path, 'completed', ticks=1)
    resumed = invoke('checkpoint-derived-run', 'run', OUT / 'checkpoint-seed-result.json', 'completed', ticks=1)
    for field in ['time', 'state', 'events', 'warehouse_ledger', 'closure']:
        assert direct['trace']['ticks'][0][field] == resumed['trace']['ticks'][0][field] == record['trace']['ticks'][6][field]
    for case in ['missing', 'conflict', 'top_only', 'lifetime']:
        raw = copy.deepcopy(checkpoint)
        rows = raw['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']
        if case == 'missing':
            rows.clear()
        elif case == 'conflict':
            next(r for r in rows if r['axis'] == 'transfer.phase')['value']['value']['values'][0]['remaining']['value']['value'] = '4'
        elif case == 'top_only':
            raw['parameters']['fixedness_unproven']['transfer.phase']['value']['values'][0]['remaining']['value']['value'] = '4'
        else:
            rows[0]['lifetime'] = 'wrong'
        reject_all('parameter-' + case, raw)
    for value, status in [('-1', 'invalid_input'), ('6', 'invalid_input'), ('1/2', 'unsupported'), ('not-a-Time', 'invalid_input')]:
        raw = copy.deepcopy(checkpoint)
        phase = raw['parameters']['fixedness_unproven']['transfer.phase']['value']
        if value == 'not-a-Time':
            phase['values'][0]['remaining'] = value
        else:
            phase['values'][0]['remaining']['value']['value'] = value
        next(r for r in raw['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values'] if r['axis'] == 'transfer.phase')['value']['value'] = copy.deepcopy(phase)
        reject_all('phase-' + value.replace('/', '_'), raw, status)
    crusher = source('混做粉碎机两下游')
    for case in ['slot_short', 'slot_unknown', 'boolean_seed', 'boolean_context', 'missing_inventory', 'unknown_progress']:
        raw = copy.deepcopy(crusher)
        seed = raw['initial_state']['nonwarehouse']['value']
        if case.startswith('slot_'):
            seed['inventory'][0]['slot'] = 'bad' if case == 'slot_short' else 'bad:input:0'
        elif case == 'boolean_seed':
            raw['initial_state']['nonwarehouse']['value'] = True
        elif case == 'boolean_context':
            seed['semantic_context'] = True
        elif case == 'missing_inventory':
            seed['inventory'] = []
        else:
            seed['progress'][0]['unit'] = 'unknown'
        reject_all(case, raw)
    for item, label in [('源矿', 'origin'), ('蓝铁矿', 'iron')]:
        raw = source('生产循环环带')
        row = next(r for r in raw['initial_state']['nonwarehouse']['value']['warehouse']['slots'] if r['item'] == item)
        row.update(item=None, quantity={'value': '0', 'category': '候选'},
                   empty_identity={'status': 'specified', 'value': item, 'basis': ['历史空矿格回归']})
        reject_all('zero-ore-' + label, raw)
    raw = source('生产循环环带')
    row = next(r for r in raw['initial_state']['nonwarehouse']['value']['inventory'] if r['contents'] and ':transport:' in r['slot'])
    row['contents'][0]['entered_at']['value']['value'] = str(-(2**63))
    path = save('age-overflow-input', raw)
    run = invoke('age-overflow-run', 'run', path, 'inconclusive')
    cycle = invoke('age-overflow-cycle', 'cycle', path, 'inconclusive')
    assert run['trace'] is None and cycle['cycle'] is None and cycle['run_record_ref'] is None
    assert cycle['stop']['kind'] == 'resource' and cycle['stop']['axis'] == 'resource.integer'
    expired = ROOT / 'crates/kernel/复核/r3-规格保真-证据/gate-expired-after-closure-input.json'
    reject_all('expired-after-closure', read(expired))
    # 原复核的小门证书只在循环起点之前有延迟W事件；必须先由独立身份检查拒收。
    legacy = ROOT / 'crates/kernel/复核/r3-规格保真-证据/tiny-expired-cycle.json'
    bad = invoke('legacy-late-window-cycle', 'verify-cycle', legacy, 'invalid_input')
    # 第六轮拒收旧内嵌式版本；下方仍独立核其待事件时序错误。
    assert any('字段须恰为' in s or '版本不符' in s for s in bad['open_items']), bad
    embedded = save('legacy-late-window-record', read(legacy)['run_record'])
    invoke('legacy-late-window-record', 'verify-record', embedded, 'invalid_input')
    result = dict(status='pass',binary=str(BIN),binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),
                  cases=REPORTS,checkpoint_state_preserved=True,checkpoint_resume_fields_equal=True)
    save('results', result)
    print(json.dumps(dict(status='pass', cases=len(REPORTS), result=str(OUT / 'results.json')), ensure_ascii=False))


if __name__ == '__main__':
    main()
