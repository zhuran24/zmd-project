#!/usr/bin/env python3
"""22c 正反对照的独立接续版；全部输入、运行输出及日志仅写本目录。"""
from pathlib import Path
import hashlib
import json
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
OUT = BASE / 'final'
OUT.mkdir()
source = ROOT / '数据/样例/任务7内核/无线多格全收.json'
binary = ROOT / 'target/release/kernel'
config = ROOT / '规格/内核配置-v1.json'

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

document = json.loads(source.read_text())
for ref in [document['catalog'], document['parameters']['axis_registry']]:
    ref['path'] = str((source.parent / ref['path']).resolve())
save(OUT / 'positive-input.json', document)
rows = []
for name, arguments, status in [
    ('kernel-seed', ['seed', str(OUT / 'positive-input.json'), '--out', str(OUT / 'seed-output.json')], None),
    ('kernel-check', ['check', str(OUT / 'seed-output.json')], 'input_checked'),
    ('kernel-run', ['run', str(OUT / 'seed-output.json'), '--ticks', '6', '--out', str(OUT / 'positive-run.json')], 'completed'),
    ('kernel-verify-record', ['verify-record', str(OUT / 'positive-run.json')], 'input_checked'),
]:
    argv = [str(binary), *arguments, '--config', str(config)]
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    (OUT / (name + '.log')).write_text(result.stdout + result.stderr)
    response = json.loads(result.stdout)
    row = {'name': name, 'argv': argv, 'exit_code': result.returncode, 'status': response.get('status')}
    rows.append(row)
    save(OUT / 'commands.json', rows)
    assert result.returncode == 0 and response.get('status') == status, row
assert json.loads((OUT / 'seed-output.json').read_text())['schema'] == 'kernel-input-v3'
assert json.loads((OUT / 'positive-run.json').read_text())['status'] == 'completed'

document['catalog']['sha256'] = '6e609fbab15104489f7e00a03c64b3f89cd77668de26789622d78be27a0ee3ff'
save(OUT / 'stale-catalog-input.json', document)
argv = [str(binary), 'seed', str(OUT / 'stale-catalog-input.json'), '--config', str(config)]
result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
(OUT / 'stale-catalog.log').write_text(result.stdout + result.stderr)
response = json.loads(result.stdout)
reason = next((item for item in response.get('open_items', [])
               if str(ROOT / '数据/正式静态目录.json') in item and '源文件指纹不符' in item), None)
row = {'name': 'stale-catalog-negative', 'argv': argv, 'exit_code': result.returncode,
       'status': response.get('status'), 'reason': reason, 'expected': 'invalid_input: 源文件指纹不符'}
rows.append(row)
save(OUT / 'commands.json', rows)
assert result.returncode != 0 and response['status'] == 'invalid_input' and reason, row
save(OUT / 'positive-validation.json', {
    'status': 'pass', 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
    'commands': rows, 'scope': '6 tick 有限运行及完整记录复验；不认证达标循环或全参数',
})
print(json.dumps(rows, ensure_ascii=False, indent=2))
