"""工程席独立CLI差分：显式改模板全序后重新派生，逐字段比缓存与直算。"""
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess

OUT = Path(__file__).resolve().parent / 'cache-cli'
ROOT = OUT.parents[4]
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def invoke(args):
    result = subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True, timeout=120)
    assert 'panicked' not in result.stderr, result.stderr
    return result


def main():
    OUT.mkdir(exist_ok=True)
    rng = random.Random(20260920)
    reports = []
    names = ['混做粉碎机两下游', '分流器三路轮询', '桥接器双通路', '传输拒收与暂停核验', '研磨混做核验',
             '阻尼切支恢复核验', '阻尼连续带核验', '生产循环环带', '轮询均分核验']
    for index, name in enumerate(names):
        source = ROOT / '数据/样例' / (name + '.json')
        original = json.loads(source.read_text())
        for variant in range(3):
            data = copy.deepcopy(original)
            for ref in [data['catalog'], data['parameters']['axis_registry']]:
                ref['path'] = str((source.parent / ref['path']).resolve())
            if variant:
                rng.shuffle(data['parameters']['fixed']['judgment.order']['value']['template_order'])
            if variant == 2:
                data['initial_state']['nonwarehouse']['value']['inventory'].reverse()
                data['layout']['units'].reverse()
                data['layout']['physical_channels'].reverse()
            path = OUT / f'case-{index}-{variant}-input.json'
            save(path, data)
            seeded = invoke(['seed', path, '--out', path])
            row = dict(name=name, variant=variant, input=str(path), seed_exit=seeded.returncode)
            if seeded.returncode:
                row['seed_result'] = json.loads(path.read_text())
                reports.append(row)
                continue
            first = OUT / f'case-{index}-{variant}-cached.json'
            second = OUT / f'case-{index}-{variant}-direct.json'
            a = invoke(['run', path, '--ticks', 8, '--out', first])
            b = invoke(['run', path, '--ticks', 8, '--no-cache', '--out', second])
            x, y = json.loads(first.read_text()), json.loads(second.read_text())
            row.update(exit_codes=[a.returncode, b.returncode], status=x['status'], all_fields_equal=x == y,
                       cached_sha256=hashlib.sha256(first.read_bytes()).hexdigest(),
                       direct_sha256=hashlib.sha256(second.read_bytes()).hexdigest())
            assert a.returncode == b.returncode and x == y, row
            reports.append(row)
    save(OUT / 'results.json', {'status': 'pass', 'random_seed': 20260920, 'cases': reports})
    print(json.dumps({'status': 'pass', 'cases': len(reports), 'loaded': sum('all_fields_equal' in r for r in reports)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
