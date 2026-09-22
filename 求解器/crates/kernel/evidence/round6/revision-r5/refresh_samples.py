"""从原输入重跑当前样例；验证后原子替换，仅指纹变更不允许沿用旧结论。"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
E = Path(__file__).resolve().parent
ROOT = E.parents[4]
BASE = ROOT / '数据/样例'
BIN = ROOT / 'target/release/kernel'
CFG = ROOT / '规格/内核配置-v1.json'
sys.path.insert(0, str(BASE))
from runtime_record import build_record, validate_record
from check_golden_trace import run as reference_run


def read(path): return json.loads(path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def run(*args):
    result = subprocess.run([str(BIN), *map(str, args), '--config', str(CFG)], capture_output=True, text=True)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return json.loads(result.stdout)


rows = []
stage = E / 'regenerated'
stage.mkdir(exist_ok=True)
for path in sorted(BASE.glob('*.json')):
    previous = read(path)
    if not isinstance(previous, dict) or previous.get('schema') not in ('kernel-output-v3', 'kernel-cycle-v2'): continue
    old_hash = digest(path)
    temporary = stage / path.name
    if previous['schema'] == 'kernel-cycle-v2':
        assert previous['record_mode'] == 'none'
        source = path.parent / previous['replay_input_ref']['path']
        budget = previous['budget']
        run('cycle', source, '--max-ticks', budget['max_ticks'], '--max-sweeps', budget['max_sweeps'], '--no-record', '--out', temporary)
        verified = run('verify-cycle', temporary)
        current = read(temporary)
        # 所有语义结论和完整恢复状态均不允许靠刷新来源悄悄改变。
        for key in ('status', 'level', 'cycle', 'last_state', 'budget', 'domain_report', 'stop'):
            assert current[key] == previous[key], (path, key)
    else:
        source = next(path.parent / r['path'] for r in previous['fingerprints'] if r['role'] == 'input')
        if previous['producer']['kind'] == 'kernel':
            assert previous['status'] == 'completed' and previous['execution_mode'] == 'finite_concrete'
            run('run', source, '--ticks', len(previous['trace']['ticks']), '--format', previous['trace']['format'],
                '--checkpoint-interval', previous['trace'].get('checkpoint_interval', 10), '--out', temporary)
            verified = run('verify-record', temporary)
            current = read(temporary)
        else:
            raw = read(source)
            ticks = reference_run(raw)
            current = build_record(raw, ticks, read(BASE / '混做粉碎机两下游-黄金轨迹.json') if source.stem == '混做粉碎机两下游' else None)
            validate_record(current, raw, ticks)
            save(temporary, current)
            verified = {'independent_reference': True}
        a, b = dict(previous), dict(current)
        a.pop('fingerprints'); b.pop('fingerprints')
        assert a == b, (path, '非指纹字段变化')
    temporary.replace(path)
    rows.append(dict(path=str(path), before_sha256=old_hash, after_sha256=digest(path),
        verification=verified, semantic_content_unchanged=True))
    print('已重跑并核验', path.name, flush=True)
    save(E / 'sample-regeneration.json', dict(status='running', files=rows))
save(E / 'sample-regeneration.json', dict(status='pass', files=rows, records=sum('运行记录' in r['path'] for r in rows),
    cycles=sum('周期证书' in r['path'] for r in rows), scope='保持输入、预算、完整轨迹/周期及结论；按当前实现从源重跑，非刷新旧哈希'))
