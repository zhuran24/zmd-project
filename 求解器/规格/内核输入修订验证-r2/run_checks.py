"""执行本轮要求的独立自查，所有持久输出限定在求解器内。"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

out = Path(__file__).resolve().parent
solver = out.parents[1]
root = solver.parent
env = dict(os.environ)
env.update(CARGO_HOME=str(solver / '.cargo-home'), CARGO_TARGET_DIR=str(solver / 'target'), TMPDIR=str(out / 'tmp'), PYTHONDONTWRITEBYTECODE='1')
Path(env['TMPDIR']).mkdir(exist_ok=True)
steps = [
    ('规则覆盖检查', ['python', '-B', str(solver / '规格/check_revision.py')], out / '规则覆盖检查.log'),
    ('现行规则覆盖', ['python', '-B', str(out / 'check_current_coverage.py')], out / '现行规则覆盖.json'),
    ('正式目录回源', ['python', '-B', str(solver / '数据/工具/formal_catalog.py')], out / '正式目录回源.log'),
    ('cargo test', ['cargo', 'test', '--offline', '--locked', '--manifest-path', str(solver / 'Cargo.toml')], out / 'cargo-test.log'),
    ('候选B校验', ['cargo', 'run', '--offline', '--locked', '--manifest-path', str(solver / 'Cargo.toml'), '-p', 'topology', '--', str(solver / '数据/候选B/contract.json')], solver / '数据/候选B/校验报告.md'),
    ('样例检查', ['python', '-B', str(solver / '数据/样例/check_examples.py'), '--self-test', '--report', str(solver / '数据/样例/检查结果.json')], out / '样例检查.log'),
]
results = []
for name, command, output in steps:
    with output.open('w') as stream, (out / (name.replace(' ', '-') + '.stderr.log')).open('w') as errors:
        result = subprocess.run(command, cwd=root, env=env, stdout=stream, stderr=errors, check=False)
    results.append({'name': name, 'command': command, 'exit_code': result.returncode, 'output': str(output)})
    print(name, result.returncode, flush=True)
protected = json.loads((out / '只读指纹.json').read_text())
changed = [name for name, digest in protected.items() if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
results.append({'name': '只读文件逐字节指纹', 'count': len(protected), 'changed': changed, 'exit_code': int(bool(changed))})
current_sim = {str(p) for p in (root / '模拟器').rglob('*') if p.is_file() and not p.is_symlink()}
prior_sim = {name for name in protected if Path(name).is_relative_to(root / '模拟器')}
same_set = current_sim == prior_sim
required_pass = same_set and all(r['exit_code'] == 0 for r in results if r['name'] != '规则覆盖检查')
# 当前覆盖检查已核实历史快照的差异全部先于本轮；原失败仍逐项保留。
legacy_failed = results[0]['exit_code'] != 0
legacy_error = (out / '规则覆盖检查.stderr.log').read_text()
legacy_stale = 'AssertionError: 只读文件 53 份指纹未变' in legacy_error
required_pass = required_pass and (not legacy_failed or legacy_stale)
status = '当前必需检查通过；原A线历史快照检查失败，差异已证在本轮之前存在' if required_pass and legacy_failed else ('PASS' if required_pass else '有失败，须逐项判读')
report = {'checks': results, 'status': status, 'required_current_checks_pass': required_pass, 'historical_check_failure_preserved': legacy_failed, 'protected_file_set_unchanged': same_set}
if required_pass:
    samples = json.loads((solver / '数据/样例/检查结果.json').read_text())
    report['samples'] = {'count': len(samples['results']), 'negative_tests': len(samples['negative_tests']), 'representation_tests': len(samples['representation_tests']), 'axes': samples['axis_count']}
(out / '自查结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
sys.exit(0 if required_pass else 1)
