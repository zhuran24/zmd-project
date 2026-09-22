#!/usr/bin/env python3
"""独立复跑第四轮两条发现；原件只读，全部副本和输出位于本目录。"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAPSHOT = HERE / 'snapshot'
FORMAL = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
FILES = FORMAL + [
    '候选约束.txt', '求解器/Cargo.toml', '求解器/Cargo.lock',
    '求解器/crates/topology/Cargo.toml',
    '求解器/crates/topology/src/lib.rs', '求解器/crates/topology/src/main.rs',
    '求解器/crates/topology/tests/validation.rs',
    '求解器/数据/工具/formal_catalog.py', '求解器/数据/工具/convert_candidate_b.py',
    '求解器/数据/工具/test_formal_catalog.py', '求解器/数据/正式静态目录.json',
    '求解器/数据/送料契约.md', '求解器/数据/修订记录.md', '求解器/数据/规则覆盖表.md',
    '求解器/数据/候选B/contract.json', '求解器/数据/候选B/校验报告.md',
    '求解器/数据/复核/复核-r4-字段覆盖.md', '求解器/数据/复核/复核-r4-校验器正确性.md',
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(command, cwd, env, prefix):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, check=False)
    (HERE / (prefix + '.stdout')).write_bytes(result.stdout)
    (HERE / (prefix + '.stderr')).write_bytes(result.stderr)
    return result


def differences(left, right, path=''):
    if type(left) is not type(right):
        return [{'path': path, 'before': left, 'after': right}]
    if isinstance(left, dict):
        assert left.keys() == right.keys()
        return [d for k in left for d in differences(left[k], right[k], path + '/' + k)]
    if isinstance(left, list):
        assert len(left) == len(right)
        return [d for i, (a, b) in enumerate(zip(left, right)) for d in differences(a, b, path + '/' + str(i))]
    return [] if left == right else [{'path': path, 'before': left, 'after': right}]


assert not SNAPSHOT.exists(), '保留既有证据；重跑时使用新的证据目录'
before = {name: digest(REPO / name) for name in FILES}
save('原件开工指纹.json', before)
for name in FILES:
    destination = SNAPSHOT / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / name, destination)
assert all(digest(SNAPSHOT / name) == value for name, value in before.items())
shutil.copytree(REPO / '求解器/.cargo-home', HERE / 'cargo-home')
env = os.environ.copy()
env.update(CARGO_HOME=str(HERE / 'cargo-home'), CARGO_TARGET_DIR=str(HERE / 'target'),
           TMPDIR=str(HERE), PYTHONDONTWRITEBYTECODE='1', RUSTUP_AUTO_INSTALL='0')
catalog_path = Path('求解器/数据/正式静态目录.json')
original = json.loads((SNAPSHOT / catalog_path).read_text())
spec = importlib.util.spec_from_file_location('formal_catalog', SNAPSHOT / '求解器/数据/工具/formal_catalog.py')
module = importlib.util.module_from_spec(spec)
sys.modules['formal_catalog'] = module
spec.loader.exec_module(module)

# 独立从正式配方节逐行解析，避免把现有目录正确性当作前提。
parsed = []
machine = None
for line in (SNAPSHOT / FORMAL[0]).read_text().split('\n配方\n', 1)[1].splitlines():
    if not line.strip():
        continue
    if '→' not in line:
        machine = line.strip()
        continue
    match = re.fullmatch(r'(.+) → (.+)，(\d+) tick', line)
    assert match, line
    def terms(value):
        return {item: {'value': amount, 'category': '条文直引'}
                for amount, item in (term.split(' ', 1) for term in value.split(' ＋ '))}
    parsed.append({'kind': machine, 'inputs': terms(match[1]), 'outputs': terms(match[2]),
                   'duration': {'value': match[3], 'category': '条文直引'}})
assert parsed == [{k: v for k, v in row.items() if k != 'id'} for row in original['recipes']]
save('原配方独立回源.json', {'recipe_count': len(parsed), 'all_equal': True, 'parsed': parsed})

# 仅执行转换器截至配方比较的原始语法树节点，不运行写候选文件的后半段。
converter = SNAPSHOT / '求解器/数据/工具/convert_candidate_b.py'
tree = ast.parse(converter.read_text())
prefix_tree = ast.Module(body=[node for node in tree.body if node.end_lineno <= 41], type_ignores=[])
prefix_code = compile(prefix_tree, str(converter), 'exec')

cases = ['baseline', 'unused_recipe_duration', 'power_coverage', 'core_port_category',
         'used_recipe_duration', 'cooldown_control']
results = []
for case in cases:
    changed = copy.deepcopy(original)
    units = {u['id']: u for u in changed['units']}
    recipes = {r['id']: r for r in changed['recipes']}
    if case == 'unused_recipe_duration':
        recipes['精炼-蓝铁粉末']['duration']['value'] = '2'
    elif case == 'power_coverage':
        units['供电桩']['coverage']['width']['value'] = '13'
    elif case == 'core_port_category':
        units['协议核心']['ports']['input_count']['category'] = '候选'
    elif case == 'used_recipe_duration':
        recipes['研磨-致密蓝铁']['duration']['value'] = '1/2'
    elif case == 'cooldown_control':
        units['协议储存箱']['transfer']['cooldown_ticks']['value'] = '4'
    delta = differences(original, changed)
    assert len(delta) == (0 if case == 'baseline' else 1)
    row = {'case': case, 'differences': delta, 'source_snapshots_unchanged': changed['sources'] == original['sources']}
    try:
        module.verify(changed, SNAPSHOT)
        row['verify'] = 'accepted'
    except AssertionError as error:
        row['verify'] = 'rejected'
        row['verify_error'] = str(error)
    save(case + '-catalog.json', changed)
    if case != 'cooldown_control':
        case_root = HERE / 'cases' / case
        shutil.copytree(SNAPSHOT, case_root)
        (case_root / catalog_path).write_text(json.dumps(changed, ensure_ascii=False, indent=2) + '\n')
        assert all(digest(case_root / name) == before[name] for name in FILES if name != str(catalog_path))
        try:
            exec(prefix_code, {'__file__': str(case_root / '求解器/数据/工具/convert_candidate_b.py'), '__name__': '__probe__'})
            row['converter_recipe_prefix'] = 'accepted'
        except AssertionError as error:
            row['converter_recipe_prefix'] = 'rejected'
            row['converter_recipe_error'] = str(error)
        workspace = case_root / '求解器'
        test = run(['cargo', 'test', '--offline', '--locked'], workspace, env, case + '-cargo-test')
        row['cargo_exit_code'] = test.returncode
        row['cargo_summaries'] = [line for line in test.stdout.decode().splitlines() if line.startswith('test result:')]
        row['topology_recompiled'] = 'Compiling topology' in test.stderr.decode()
        cli = run(['cargo', 'run', '--offline', '--locked', '--quiet', '-p', 'topology', '--',
                   str(workspace / '数据/候选B/contract.json')], workspace, env, case + '-cli')
        row['cli_exit_code'] = cli.returncode
        output = cli.stdout.decode()
        row['cli_counts'] = dict(re.findall(r'- (能检且通过|能检且不通过|不能静态检)：(\d+)', output))
        row['m120_report'] = [line for line in output.splitlines() if '| 制造能力/M120 |' in line]
        row['cli_equal_original_report'] = cli.stdout == (SNAPSHOT / '求解器/数据/候选B/校验报告.md').read_bytes()
    results.append(row)
    save('复跑结果.json', results)
    print(json.dumps(row, ensure_ascii=False), flush=True)

after = {name: digest(REPO / name) for name in FILES}
save('原件收尾核验.json', {'all_unchanged': before == after, 'before': before, 'after': after})
assert before == after, '原件发生并发变化，须复核差异后再交付'
