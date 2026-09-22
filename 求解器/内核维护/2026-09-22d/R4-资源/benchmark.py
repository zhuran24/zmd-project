#!/usr/bin/env python3
"""Sequential release resource measurements; all output remains beside this file.

GNU time is selected from time-tool.json or --time-bin. No tests are invoked.
Run: python benchmark.py --suite main
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def measure(name, sample, ticks, mode='none', repeat=1, interval=32):
    prefix = OUT / name
    input_path = ROOT / '数据/样例' / (sample + '.json')
    artifact = prefix.with_suffix('.artifact.json')
    argv = [str(BIN), 'cycle' if mode == 'cycle' else 'run', str(input_path),
            '--config', str(CFG), '--max-ticks' if mode == 'cycle' else '--ticks', str(ticks),
            '--max-sweeps', '100000']
    if mode == 'none':
        argv += ['--no-output']
    elif mode == 'cycle':
        argv += ['--no-record', '--search-checkpoint-interval', str(interval), '--out', str(artifact)]
    else:
        argv += ['--format', mode, '--checkpoint-interval', str(interval), '--out', str(artifact)]
    command = [ARGS.time_bin, '-v', '-o', str(prefix.with_suffix('.time.log')), *argv]
    row = {'name': name, 'sample': sample, 'mode': mode, 'requested_ticks': ticks,
           'repeat': repeat, 'interval': interval, 'argv': command, 'cwd': str(ROOT),
           'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'binary_sha256_before': sha(BIN), 'input_sha256': sha(input_path),
           'config_sha256': sha(CFG), 'cpu_affinity': sorted(os.sched_getaffinity(0))}
    write(prefix.with_suffix('.command.json'), row)
    prefix.with_suffix('.command.log').write_text(shlex.join(command) + '\n')
    started = time.perf_counter()
    max_threads = 0
    with prefix.with_suffix('.stdout.log').open('wb') as stdout, prefix.with_suffix('.stderr.log').open('wb') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=ENV, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            # GNU time directly launches one single-threaded kernel child.
            try:
                children = Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
                for pid in children:
                    status = Path(f'/proc/{pid}/status').read_text()
                    max_threads = max(max_threads, int(re.search(r'^Threads:\s+(\d+)', status, re.M)[1]))
            except (FileNotFoundError, ProcessLookupError):
                pass
            if time.perf_counter() - started > 600:
                process.kill()
                for pid in children:
                    try:
                        os.kill(int(pid), 9)
                    except ProcessLookupError:
                        pass
                row['timeout'] = True
                break
            time.sleep(.05)
        row['returncode'] = process.wait()
    row['driver_wall_seconds'] = time.perf_counter() - started
    row['sampled_max_kernel_threads'] = max_threads or None
    row['binary_sha256_after'] = sha(BIN)
    timing = prefix.with_suffix('.time.log').read_text()
    for key, pattern in {
        'user_seconds': r'User time \(seconds\): ([\d.]+)',
        'system_seconds': r'System time \(seconds\): ([\d.]+)',
        'peak_rss_kib': r'Maximum resident set size \(kbytes\): (\d+)',
        'major_page_faults': r'Major .* page faults: (\d+)',
        'minor_page_faults': r'Minor .* page faults: (\d+)',
        'swaps': r'Swaps: (\d+)',
    }.items():
        match = re.search(pattern, timing)
        row[key] = float(match[1]) if match else None
    wall = re.search(r'Elapsed \(wall clock\) time .*: (\d+:\d[^\n]*)', timing)
    if wall:
        value = 0.0
        for part in wall[1].split(':'):
            value = value * 60 + float(part)
        row['wall_seconds'] = value
    data = json.loads((artifact if artifact.exists() else prefix.with_suffix('.stdout.log')).read_text())
    row['status'] = data.get('status')
    if mode == 'none':
        row['completed_ticks'] = data.get('completed_ticks', ticks if row['status'] == 'completed' else None)
        row['elapsed_ns'] = data.get('elapsed_ns')
        row['final_inventory'] = data.get('final_inventory')
    elif mode == 'cycle':
        row['completed_ticks'] = data.get('budget', {}).get('completed_ticks')
        row['cycle_period'] = (data.get('cycle') or {}).get('period')
        row['record_mode'] = data.get('record_mode')
    else:
        rows = (data.get('trace') or {}).get('ticks', [])
        row['completed_ticks'] = len(rows)
        row['recorded_events'] = sum(len(t.get('events', [])) for t in rows)
        row['scan_rounds'] = sum(t['closure']['scan_rounds'] for t in rows)
    if artifact.exists():
        row['artifact_bytes'] = artifact.stat().st_size
        row['artifact_sha256'] = sha(artifact)
    row['stop'] = data.get('stop')
    write(prefix.with_suffix('.result.json'), row)
    print(json.dumps({k: row.get(k) for k in ['name', 'status', 'completed_ticks', 'wall_seconds', 'elapsed_ns', 'peak_rss_kib', 'artifact_bytes']}, ensure_ascii=False), flush=True)
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suite', choices=['main', 'output', 'cycle', 'extended'], default='main')
    parser.add_argument('--time-bin', default=json.loads((OUT / 'time-tool.json').read_text())['executable'])
    ARGS = parser.parse_args()
    ENV = {**os.environ, 'LC_ALL': 'C', 'LANG': 'C', 'CARGO_TARGET_DIR': str(ROOT / 'target'),
           'CARGO_BUILD_JOBS': '1', 'RAYON_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
           'OPENBLAS_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:6])
    results = []
    if ARGS.suite == 'main':
        write(OUT / 'environment.json', {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'platform': platform.platform(), 'cpu_model': next(l.strip() for l in Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),
              'meminfo': Path('/proc/meminfo').read_text(), 'loadavg': Path('/proc/loadavg').read_text(),
              'rustc': subprocess.check_output(['rustc', '--version', '--verbose'], text=True),
              'cargo': subprocess.check_output(['cargo', '--version'], text=True),
              'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, env=ENV).strip(),
              'binary_sha256': sha(BIN), 'binary_mtime_ns': BIN.stat().st_mtime_ns,
              'build_command': 'CARGO_TARGET_DIR=' + str(ROOT / 'target') + ' CARGO_BUILD_JOBS=1 RAYON_NUM_THREADS=1 cargo build --release --locked -p kernel --bin kernel -j 1',
              'environment_overrides': {k: ENV[k] for k in ['LC_ALL','CARGO_TARGET_DIR','CARGO_BUILD_JOBS','RAYON_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']}})
        for repeat in range(1, 4):
            for ticks in [1000, 10000, 100000]:
                results.append(measure(f'ring-none-{ticks}-r{repeat}', '生产循环环带', ticks, repeat=repeat))
        for ticks in [1000, 10000, 100000]:
            results.append(measure(f'splitter-none-{ticks}', '分流器三路轮询', ticks))
    elif ARGS.suite == 'output':
        for mode, short in [('full_state_each_instant', 'full'), ('checkpoint_delta', 'delta')]:
            results.append(measure(f'ring-{short}-1000', '生产循环环带', 1000, mode, interval=32))
    elif ARGS.suite == 'cycle':
        for interval in [1, 32, 128]:
            results.append(measure(f'ring-cycle-100000-k{interval}', '生产循环环带', 100000, 'cycle', interval=interval))
    else:
        for ticks in [1000, 10000, 100000]:
            results.append(measure(f'dense-none-{ticks}', '密集制造闭环序2核验', ticks))
        for interval in [1, 32, 128]:
            results.append(measure(f'dense-cycle-1000-k{interval}', '密集制造闭环序2核验', 1000, 'cycle', interval=interval))
    write(OUT / (ARGS.suite + '-results.json'), results)
