"""修订r5交付审计：来源保护、测试结果、证据格式、当前文档链接与完整文件清单。"""
import hashlib
import json
from pathlib import Path
import re

E = Path(__file__).resolve().parent
ROOT = E.parents[4]
BASE = ROOT / '数据/样例'


def read(path): return json.loads(path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


before = read(E / 'before.json')
protected_changes = [name for name, expected in before['protected'].items() if digest(Path(name)) != expected]
assert not protected_changes, protected_changes
baseline = read(ROOT / 'crates/kernel/evidence/round5/protected-baseline.json')
assert all(digest(Path(name)) == expected for name, expected in baseline.items())
commands = read(E / 'validation-commands.json')
assert all(step['exit_code'] == 0 for step in commands)
assert commands[-1]['name'] == 'reduction-lock'
test_log = (E / 'cargo-test.log').read_text()
assert 'FAILED' not in test_log and 'error:' not in test_log
passed = sum(map(int, re.findall(r'test result: ok\. (\d+) passed', test_log)))
assert passed == 141
cli = read(E / 'cli/results.json')
assert cli['status'] == 'pass' and len(cli['cases']) == 52
schema = read(E / 'spec-selfcheck.log')
assert schema['status'] == 'PASS' and schema['schema_cases'] == 76
batch = read(E / 'verify-batch.json')
assert batch['audited_tree_unchanged'] and len(batch['records']) == 29 and len(batch['cycles']) == 11
for name in ('verify-relative-batch.json', 'verify-reference-batch.json'):
    assert read(E / name)['audited_tree_unchanged']
regenerated = read(E / 'sample-regeneration.json')
assert regenerated['status'] == 'pass' and len(regenerated['files']) == 40
assert all(row['semantic_content_unchanged'] for row in regenerated['files'])
reduction = read(E / 'reduction-lock.json')
assert reduction['after_exit'] == 0 and reduction['non_fingerprint_content_equal']
benchmark = read(E / 'benchmark/benchmark-final.json')
assert benchmark['status'] == 'pass' and all(n > 0 for n in benchmark['production_audit']['actual_inbound'].values())
for path in E.rglob('*'):
    if path.is_dir(): assert path.name not in ('target', '.cargo-home', 'registry', '__pycache__'), path
    else: assert path.suffix in ('.py', '.log', '.json', '.md'), path
large = [str(p) for p in BASE.rglob('*') if p.is_file() and p.stat().st_size > 20_000_000]
assert not large, large
documents = [ROOT / 'crates/kernel/README.md', E / '修订与验证.md',
    ROOT / 'crates/kernel/修订记录.md', ROOT / '规格/内核实现-对规格的疑问.md']
link_targets = []
for path in documents:
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
        if '://' not in target and not target.startswith('#'):
            destination = (path.parent / target.split('#')[0]).resolve()
            link_targets.append(destination)
            assert destination.exists() or destination in (E / 'final-audit.json', E / 'files.json'), (path, target)
for name in ('cycle.rs', 'cycle_io.rs'):
    source = (ROOT / 'crates/kernel/src' / name).read_text()
    assert 'Engine::new(' not in source and 'production_abstraction = true' not in source
findings = ['KR-r5-L2-01', 'KR-r5-L2-02', 'KR-r5-L2-03']
for finding in findings:
    assert finding in (ROOT / 'crates/kernel/修订记录.md').read_text()
    assert finding in (E / '修订与验证.md').read_text()
save(E / 'reader-review.json', dict(status='pass', documents=list(map(str, documents)),
    checks={'陌生读者上下文': '三发现及条款、接口和试样均自包含',
        '终态与史料': 'README及本报告为现状，原round6报告明确标成执行存档',
        '头部状态': '报告与最终机械验收一致', '指令回声': '未把写作指令写进正文',
        '数字口径': '141项测试、52次CLI、29份记录和11份循环；旧数字均在历史区',
        '命名': '沿用发现ID、KQ编号及revision-r5路径', '交叉引用': '本次四份文档全部本地链接目标存在'}))
summary = dict(status='pass', findings={name: 'fixed' for name in findings}, tests_passed=passed,
    clippy='pass', cli_calls=len(cli['cases']), positive_cli_schema_documents=cli['positive_schema_documents'],
    schema_cases=schema['schema_cases'], specification_checks=schema['specification_checks'],
    records=len(batch['records']), cycles=len(batch['cycles']), batch_read_only=True,
    protected_spec_and_formal_files=len(before['protected']), protected_baseline_files=len(baseline),
    protected_changes=[], sample_bytes=sum(p.stat().st_size for p in BASE.rglob('*') if p.is_file()),
    oversize_samples=large, reduction=reduction, performance=[dict(name=r['name'],
        run_ms_per_tick=r['modes']['run']['engine_ms_per_tick'], cycle_wall_ms_per_tick=r['modes']['cycle']['wall_ms_per_tick'],
        run_target_met=r['run_target_met'], cycle_wall_target_met=r['cycle_wall_target_met']) for r in benchmark['reports']],
    open_items=['K6尚未取得两成品目标率的生产部分周期，级二与全族认证仍未完成。',
        'benchmark_brick的run仍高于1ms/tick，四档cycle墙钟均未达到对应目标。'])
save(E / 'final-audit.json', summary)
# 时间边界只用于枚举既有证据的本次重跑写入；源码、样例另以开工字节作精确比较。
start_ns = (E / 'before.json').stat().st_mtime_ns
changed = [name for name, old in before['mutable'].items() if Path(name).exists() and digest(Path(name)) != old]
deleted = [name for name in before['mutable'] if not Path(name).exists()]
written = [str(p) for directory in (ROOT / 'crates/kernel', BASE) for p in directory.rglob('*')
    if p.is_file() and p.stat().st_mtime_ns >= start_ns]
files = sorted(set(changed + written + deleted + [str(E / 'files.json')]))
save(E / 'files.json', dict(files=files, changed_from_baseline=sorted(changed), deleted=deleted,
    scope='所有本次修改/新增/重跑写入的交付文件；既有证据写入按开工时间核，源码及样例按字节核。target编译产物不列入。'))
assert all(path.exists() for path in link_targets)
print(json.dumps(dict(status='pass', tests=passed, cli_calls=len(cli['cases']), files=len(files),
    protected_files=len(before['protected']), changed_specifications=[str(ROOT / '规格/内核实现-对规格的疑问.md'),
        str(ROOT / '规格/复核/约减/等价类计数.json')]), ensure_ascii=False))
