"""工程复核入口：原脚本仅重定向输出，所有结果保存在本席目录。"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
TESTS = ROOT / 'crates/kernel/tests'
sys.path.insert(0, str(TESTS))
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'


def save(name, data):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def cli():
    module = importlib.import_module('revision_r3_cli')
    module.OUT = OUT / 'cli'
    module.BIN = BIN
    module.main()
    schema = importlib.import_module('audit_revision_r3')
    schema.OUT = OUT
    schema.main()


def references():
    module = importlib.import_module('verify_outputs')
    reports = []
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        data = module.checker.load_json(ROOT / f'数据/样例/{name}.json')
        expected = module.run(data)
        for suffix in ('运行记录-v3-kernel', '运行记录-checkpoint_delta-v3-kernel'):
            reports.append(module.verify(ROOT / f'数据/样例/{name}-{suffix}.json', data, expected))
    save('reference-results.json', {'status': 'pass', 'records': reports})
    print('四份参考记录通过', flush=True)


def audit():
    module = importlib.import_module('audit_round5')
    dense = importlib.import_module('audit_dense_round5')
    def redirected(path, data):
        save('audit/' + path.name, data)
    module.write = redirected
    dense.E = OUT / 'audit'
    dense.E.mkdir(exist_ok=True)
    module.main()


def benchmark():
    old = json.loads((ROOT / 'crates/kernel/evidence/benchmark.json').read_text())
    reports = []
    for row in old['reports']:
        source = Path(row['command'][2])
        current = hashlib.sha256(source.read_bytes()).hexdigest()
        measurements = []
        for _ in range(5):
            process = subprocess.run(row['command'], capture_output=True, text=True, timeout=120)
            result = json.loads(process.stdout)
            assert process.returncode == 0 and result['status'] == 'completed', (process.returncode, result)
            measurements.append(dict(ms_per_tick=int(result['elapsed_ns']) / 1e6 / row['ticks'], result=result))
        median = statistics.median(r['ms_per_tick'] for r in measurements)
        reports.append(dict(name=row['name'], command=row['command'], input_sha256=current,
                            input_matches_old=current == row['input_sha256'], old_ms=row['ms_per_tick'],
                            median_ms=median, target_ms=row['target_ms'], target_met=median <= row['target_ms'],
                            measurements=measurements))
        print(row['name'], median, flush=True)
    save('benchmark-replay.json', dict(binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),
                                     old_binary_sha256=old['binary_sha256'], reports=reports))


def generate():
    module = importlib.import_module('benchmark_round5')
    fixtures = OUT / 'generated'
    fixtures.mkdir(exist_ok=True)
    module.b.OUT = fixtures
    reports = []
    for name, machines, logical, columns in [('benchmark_brick_60', 0, 0, 0), ('benchmark_brick', 30, 50, 6), ('benchmark_candidate_b', 219, 315, 17)]:
        path, shape = module.generate_dense_brick() if not machines else module.generate(name, machines, logical, columns)
        process = subprocess.run([str(BIN), 'seed', str(path), '--config', str(CFG), '--out', str(path)], capture_output=True, text=True)
        assert process.returncode == 0, process.stderr
        original = ROOT / 'crates/kernel/tests/fixtures' / path.name
        reports.append(dict(name=name, shape=shape, input_equal=json.loads(path.read_text()) == json.loads(original.read_text()),
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    save('benchmark-generator.json', {'reports': reports})
    print(json.dumps(reports, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    {'cli': cli, 'references': references, 'audit': audit, 'benchmark': benchmark, 'generate': generate}[sys.argv[1]]()
