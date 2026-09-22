#!/usr/bin/env python3
"""工程复核：独立入口负例、原记录再读和有限性能实测；写入仅限本目录。"""
import copy
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BIN = OUT / 'target/release/kernel'
CONFIG = ROOT / '规格/内核配置-v1.json'
SAMPLES = ROOT / '数据/样例'
sys.path.insert(0, str(SAMPLES))
from test_runtime_input import validate_schema


def save(name, value):
    """证据文件使用真实换行和 UTF-8。"""
    path = OUT / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def load(name):
    """拷贝样例并改为绝对引用，不改任何源样例。"""
    data = json.loads((SAMPLES / (name + '.json')).read_text())
    for ref in [data['catalog'], data['parameters']['axis_registry']]:
        ref['path'] = str((SAMPLES / ref['path']).resolve())
    return data


def run_case(name, data, ticks=2):
    """真实 CLI 返回码、stderr、输出记录一起保存。"""
    source = save(name + '-input.json', data)
    record = OUT / (name + '-record.json')
    args = [str(BIN), 'run', str(source), '--config', str(CONFIG), '--ticks', str(ticks), '--out', str(record)]
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    result = {'case': name, 'command': args, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr, 'record_exists': record.exists()}
    if record.exists():
        value = json.loads(record.read_text())
        result['status'] = value['status']
        result['open_items'] = value['open_items']
        schema = json.loads((ROOT / '规格/内核输出.schema.json').read_text())
        try:
            validate_schema(value, schema, schema)
            result['schema'] = 'accepted'
        except Exception as e:
            result['schema'] = 'rejected'
            result['schema_error'] = str(e)
        if value['trace']:
            result['gate_states'] = value['trace']['ticks'][-1]['state']['logistics']['gate_counters']
    return result


def main():
    """入口校验、来源清单、覆盖摘要与实测分开取证。"""
    cases = []
    data = load('混做粉碎机两下游')
    data['initial_state']['nonwarehouse']['value']['semantic_context']['judgment_context']['value'] = {'phase': 'before_boundary'}
    cases.append(run_case('missing-judgment-context', data))
    data = load('混做粉碎机两下游')
    data['layout']['snapshots'] = [False]
    cases.append(run_case('snapshot-bool', data))
    data = load('分流器三路轮询')
    data['settings']['gates'][0]['item'] = 7
    cases.append(run_case('gate-numeric-item', data))
    data = load('混做粉碎机两下游')
    data['initial_state']['warehouse']['slots'][1]['slot'] = data['initial_state']['warehouse']['slots'][0]['slot']
    cases.append(run_case('initial-duplicate-slot', data))
    save('input-probes.json', cases)

    spec = importlib.util.spec_from_file_location('review_verify_outputs', ROOT / 'crates/kernel/tests/verify_outputs.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = []
    for name in ['混做粉碎机两下游', '分流器三路轮询']:
        original = json.loads((SAMPLES / (name + '.json')).read_text())
        expected = module.run(original)
        for suffix in ['运行记录-kernel', '运行记录-checkpoint_delta-kernel']:
            path = SAMPLES / (name + '-' + suffix + '.json')
            checks.append({'case': str(path), 'result': module.verify(path, original, expected)})
        full = json.loads((SAMPLES / (name + '-运行记录-kernel.json')).read_text())
        for mutation in ['missing-fingerprints', 'false-validation-count']:
            altered = copy.deepcopy(full)
            if mutation == 'missing-fingerprints':
                altered['fingerprints'] = []
            else:
                altered['validation_scope']['manufacturing_cycles_completed']['value'] = '999'
            path = save(name + '-' + mutation + '.json', altered)
            try:
                result = module.verify(path, original, expected)
                checks.append({'case': name + ':' + mutation, 'accepted': True, 'result': result})
            except Exception as e:
                checks.append({'case': name + ':' + mutation, 'accepted': False, 'error': str(e)})
    save('record-verifier-probes.json', checks)

    args = [str(BIN), 'run', str(ROOT / 'crates/kernel/tests/fixtures/benchmark_1000.json'), '--config', str(CONFIG), '--ticks', '1000', '--no-output']
    start = time.perf_counter_ns()
    p = subprocess.run(args, capture_output=True, text=True, timeout=60)
    duration = time.perf_counter_ns() - start
    save('benchmark.json', {'classification': '实测', 'command': args, 'returncode': p.returncode, 'process_elapsed_ns': duration, 'result': json.loads(p.stdout), 'stderr': p.stderr, 'platform': platform.platform(), 'rustc': subprocess.check_output(['rustc', '--version'], text=True).strip(), 'binary_sha256': hashlib.sha256(BIN.read_bytes()).hexdigest(), 'input_sha256': hashlib.sha256(Path(args[2]).read_bytes()).hexdigest(), 'scope': '单次 release 1000 时刻，输出关闭，编译不计；后段阻塞，不是满载基准'})
    print(json.dumps({'input_cases': cases, 'verifier_mutations': [x for x in checks if 'accepted' in x], 'benchmark_process_ns': duration}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
