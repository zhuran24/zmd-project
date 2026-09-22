#!/usr/bin/env python3
"""Aggregate raw results and verify pre-existing tracked bytes without Git writes."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess

out = Path(__file__).resolve().parent
root = out.parents[2]
repo = root.parent


def write(name, data):
    (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


results = []
for suite in ['main', 'output', 'cycle', 'extended']:
    results += json.loads((out / (suite + '-results.json')).read_text())
ring = []
for ticks in [1000, 10000, 100000]:
    rows = [r for r in results if r['name'].startswith(f'ring-none-{ticks}-')]
    ring.append({'ticks': ticks, 'repeats': len(rows),
                 'median_wall_seconds': statistics.median(r['wall_seconds'] for r in rows),
                 'median_elapsed_seconds': statistics.median(int(r['elapsed_ns']) / 1e9 for r in rows),
                 'median_peak_rss_kib': statistics.median(r['peak_rss_kib'] for r in rows),
                 'min_peak_rss_kib': min(r['peak_rss_kib'] for r in rows),
                 'max_peak_rss_kib': max(r['peak_rss_kib'] for r in rows)})
probe = []
for line in (out / 'probe.stdout.log').read_text().splitlines():
    row = json.loads(line)
    status = row.pop('proc_status')
    for name in ['VmRSS', 'VmHWM', 'Threads']:
        row[name] = int(re.search(r'^' + name + r':\s+(\d+)', status, re.M)[1])
    probe.append(row)
summary = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'ring_medians': ring, 'results': results, 'probe': probe,
           'ring_rss_slope_kib_per_tick_10k_100k': (ring[2]['median_peak_rss_kib'] - ring[1]['median_peak_rss_kib']) / 90000,
           'binary_hashes': sorted(set(r['binary_sha256_before'] for r in results) | set(r['binary_sha256_after'] for r in results)),
           'sampled_max_kernel_threads': max(r['sampled_max_kernel_threads'] or 0 for r in results),
           'all_major_faults': sum(r['major_page_faults'] for r in results),
           'all_swaps': sum(r['swaps'] for r in results)}
write('summary.json', summary)
before = json.loads((out / 'tracked-before.json').read_text())
changed = []
for rel, old in before.items():
    path = repo / rel
    actual = {'sha256': digest(path), 'size': path.stat().st_size} if path.is_file() else None
    if actual != old:
        changed.append({'path': rel, 'before': old, 'after': actual})
write('integrity.json', {'checked_tracked_files': len(before), 'changed': changed,
                        'release_kernel_sha256': digest(root / 'target/release/kernel'),
                        'expected_release_kernel_sha256': summary['binary_hashes']})
git_status = subprocess.check_output(['git', 'status', '--porcelain=v1', '-uall'], cwd=repo,
                                    env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
(out / 'git-after.log').write_bytes(git_status)
print(json.dumps({'ring_medians': ring, 'changed_tracked_files': len(changed),
                  'measurements': len(results), 'sampled_max_kernel_threads': summary['sampled_max_kernel_threads']}, ensure_ascii=False, indent=2))
