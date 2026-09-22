"""工程席公开CLI回归；只生成复核目录内的输入、结果和日志。"""
import copy
import json
import subprocess
from pathlib import Path

ROOT = Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT = ROOT / 'crates/kernel/复核/r3-工程证据'
BIN = ROOT / 'target/release/kernel'
CONFIG = ROOT / '规格/内核配置-v1.json'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def materialize(name, data, source):
    data = copy.deepcopy(data)
    for ref in (data['catalog'], data['parameters']['axis_registry']):
        ref['path'] = str((source.parent / ref['path']).resolve())
    path = OUT / (name + '.json')
    write(path, data)
    return path


def invoke(name, mode, path, options=()):
    result_path = OUT / (name + '-result.json')
    result_path.unlink(missing_ok=True)
    cmd = [str(BIN), mode, str(path), '--config', str(CONFIG), *options]
    if '--no-output' not in options:
        cmd += ['--out', str(result_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    value = None
    if result_path.exists():
        value = json.loads(result_path.read_text())
    elif result.stdout.strip():
        try:
            value = json.loads(result.stdout)
        except ValueError:
            pass
    row = dict(case=name, command=cmd, exit_code=result.returncode,
               stdout=result.stdout, stderr=result.stderr,
               result_path=str(result_path) if result_path.exists() else None,
               status=value.get('status') if value else None,
               stop=value.get('stop') if value else None,
               statistics=value.get('statistics') if value else None)
    return row


def main():
    source = ROOT / '数据/样例/混做粉碎机两下游.json'
    raw = json.loads(source.read_text())
    reports = []
    for name, kind in [('valid-control', 'valid'), ('invalid-slot-label', 'slot'),
                       ('invalid-unit-label', 'unit'), ('invalid-seed-shape', 'seed')]:
        data = copy.deepcopy(raw)
        if kind == 'slot':
            data['initial_state']['nonwarehouse']['value']['inventory'][0]['slot'] = 'bad'
        elif kind == 'unit':
            data['initial_state']['nonwarehouse']['value']['inventory'][0]['slot'] = 'bad:input:0'
        elif kind == 'seed':
            data['initial_state']['nonwarehouse']['value'] = True
        path = materialize(name, data, source)
        reports.append(invoke(name, 'seed' if kind == 'seed' else 'run', path,
                              [] if kind == 'seed' else ['--ticks', '1']))
    ring = ROOT / '数据/样例/生产循环环带.json'
    raw = json.loads(ring.read_text())
    for row in raw['initial_state']['nonwarehouse']['value']['inventory']:
        if row['contents'] and ':transport:' in row['slot']:
            row['contents'][0]['entered_at']['value']['value'] = str(-(2**63))
            break
    path = materialize('load-age-overflow', raw, ring)
    for mode in ['run', 'cycle']:
        reports.append(invoke(mode + '-load-age-overflow', mode, path, ['--ticks', '2']))
    for mode in ['run', 'cycle']:
        reports.append(invoke(mode + '-one-sweep', mode, ring,
                              ['--ticks', '2', '--max-sweeps', '1'] +
                              (['--no-output'] if mode == 'run' else [])))
        reports.append(invoke(mode + '-adequate-sweeps', mode, ring,
                              ['--ticks', '2', '--max-sweeps', '1000'] +
                              (['--no-output'] if mode == 'run' else [])))
    reports.append(invoke('relocated-input', 'seed', source))
    # 入口生成的文件再由公开run装载，确认不依赖旧输入目录。
    reports.append(invoke('relocated-run', 'run', OUT / 'relocated-input-result.json',
                          ['--ticks', '4', '--no-output']))
    write(OUT / 'CLI探针汇总.json', reports)
    print(json.dumps([{k: row[k] for k in ['case', 'exit_code', 'status', 'statistics']}
                      for row in reports], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
