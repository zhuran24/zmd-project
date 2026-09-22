#!/usr/bin/env python3
"""契约线第四轮第一否证席：只在本目录创建隔离副本与验证证据。"""
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
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WORK = HERE / 'isolated'
SNAPSHOT = HERE / 'snapshot'
TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
SOURCES = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
FILES = SOURCES + [
    '求解器/Cargo.toml', '求解器/Cargo.lock',
    '求解器/crates/topology/Cargo.toml',
    '求解器/crates/topology/src/lib.rs',
    '求解器/crates/topology/src/main.rs',
    '求解器/crates/topology/tests/validation.rs',
    '求解器/数据/工具/formal_catalog.py',
    '求解器/数据/工具/convert_candidate_b.py',
    '求解器/数据/工具/test_formal_catalog.py',
    '求解器/数据/正式静态目录.json',
    '求解器/数据/送料契约.md',
    '求解器/数据/候选B/contract.json',
    '求解器/数据/候选B/校验报告.md',
    '求解器/数据/修订记录.md',
    '求解器/数据/复核/复核-r4-字段覆盖.md',
    '求解器/数据/复核/复核-r4-校验器正确性.md',
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(command, name):
    result = subprocess.run(command, cwd=WORK/'求解器', env=ENV,
                            capture_output=True, check=False)
    (HERE/(name+'.stdout')).write_bytes(result.stdout)
    (HERE/(name+'.stderr')).write_bytes(result.stderr)
    return result


def differences(left, right, path=''):
    if isinstance(left, dict):
        assert left.keys() == right.keys()
        return sum((differences(left[key], right[key], path+'/'+key) for key in left), [])
    if isinstance(left, list):
        assert len(left) == len(right)
        return sum((differences(a, b, path+'/'+str(i)) for i, (a, b) in enumerate(zip(left, right))), [])
    return [] if left == right else [{'path': path, 'before': left, 'after': right}]


# 复制只读输入；拒绝覆盖前次运行的证据。
assert not WORK.exists() and not SNAPSHOT.exists(), '证据目录已使用，不能覆盖'
protected = {str(REPO/name): digest(REPO/name) for name in FILES+['候选约束.txt']}
protected.update({str(TASKS/name): digest(TASKS/name) for name in ['任务书3.md', '任务书.md', '任务书2.md']})
write_json(HERE/'输入指纹.json', protected)
for name in FILES:
    target = SNAPSHOT/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO/name, target)
shutil.copytree(SNAPSHOT, WORK)
shutil.copytree(REPO/'求解器/数据/复核/r4-校验器证据/cargo-home', HERE/'cargo-home')
(HERE/'tmp').mkdir()
ENV = os.environ.copy()
ENV.update(CARGO_HOME=str(HERE/'cargo-home'), CARGO_TARGET_DIR=str(HERE/'target'),
           CARGO_INCREMENTAL='0', TMPDIR=str(HERE/'tmp'), PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode = True
tool_dir = WORK/'求解器/数据/工具'
sys.path.insert(0, str(tool_dir))
spec = importlib.util.spec_from_file_location('formal_catalog', tool_dir/'formal_catalog.py')
module = importlib.util.module_from_spec(spec)
sys.modules['formal_catalog'] = module
spec.loader.exec_module(module)
catalog_path = WORK/'求解器/数据/正式静态目录.json'
original_bytes = catalog_path.read_bytes()
catalog = json.loads(original_bytes)
contract = json.loads((WORK/'求解器/数据/候选B/contract.json').read_text())

# 从正式配方正文重建数值，不用被审程序生成预期值。
rules = (WORK/SOURCES[0]).read_text().splitlines()
expected = []
kind = None
for line in rules[79:]:
    if not line.strip():
        continue
    if '→' not in line:
        kind = line.strip()
        continue
    left, right = line.split(' → ')
    output, duration = right.split('，')
    def terms(text):
        return {item: Fraction(count) for count, item in (part.split(' ', 1) for part in text.split(' ＋ '))}
    expected.append((kind, terms(left), terms(output), Fraction(duration.split()[0])))
actual = [(r['kind'], {k: Fraction(v['value']) for k, v in r['inputs'].items()},
           {k: Fraction(v['value']) for k, v in r['outputs'].items()}, Fraction(r['duration']['value']))
          for r in catalog['recipes']]
assert actual == expected and len(expected) == 18
units = {u['id']: u for u in catalog['units']}
assert units['供电桩']['coverage']['width'] == {'value': '12', 'category': '条文直引'}
assert units['供电桩']['coverage']['height'] == {'value': '12', 'category': '条文直引'}
assert units['协议核心']['ports']['input_count'] == {'value': '14', 'category': '条文直引'}
assert not any(p['recipe'] == '精炼-蓝铁粉末' for m in contract['machines'] for p in m['recipes'])

# 仅执行原转换器至完整配方比较的原始语法树；不进入候选写出部分。
converter = tool_dir/'convert_candidate_b.py'
tree = ast.parse(converter.read_text(), filename=str(converter))
prefix = ast.Module(body=[node for node in tree.body if node.lineno <= 41], type_ignores=[])
assert isinstance(prefix.body[-1], ast.Assert) and prefix.body[-1].lineno == 41
converter_guard = compile(prefix, str(converter), 'exec')
cases = ['baseline', 'unused_recipe_duration', 'power_coverage', 'core_port_category', 'used_recipe_duration']
results = []
started = datetime.now(timezone.utc).isoformat()
try:
    for name in cases:
        changed = copy.deepcopy(catalog)
        changed_units = {u['id']: u for u in changed['units']}
        if name == 'unused_recipe_duration':
            next(r for r in changed['recipes'] if r['id'] == '精炼-蓝铁粉末')['duration']['value'] = '2'
        elif name == 'power_coverage':
            changed_units['供电桩']['coverage']['width']['value'] = '13'
        elif name == 'core_port_category':
            changed_units['协议核心']['ports']['input_count']['category'] = '候选'
        elif name == 'used_recipe_duration':
            next(r for r in changed['recipes'] if r['id'] == '研磨-致密蓝铁')['duration']['value'] = '1/2'
        delta = differences(catalog, changed)
        assert len(delta) == (0 if name == 'baseline' else 1)
        assert changed['sources'] == catalog['sources']
        catalog_path.write_text(json.dumps(changed, ensure_ascii=False, indent=2)+'\n')
        shutil.copyfile(catalog_path, HERE/(name+'.catalog.json'))
        row = {'case': name, 'differences': delta, 'catalog_sha256': digest(catalog_path)}
        checked = run(['python', str(tool_dir/'formal_catalog.py')], name+'-verify')
        row['verify_exit_code'] = checked.returncode
        try:
            exec(converter_guard, {'__file__': str(converter), '__name__': 'converter_guard_probe'})
            row['converter_recipe_guard'] = 'accepted'
        except AssertionError as error:
            row['converter_recipe_guard'] = 'rejected: '+str(error)
        # 每种目录重新编译 topology，排除 include_str 编译缓存的影响。
        cleaned = run(['cargo', 'clean', '-p', 'topology', '--offline', '--locked'], name+'-clean')
        assert cleaned.returncode == 0
        tested = run(['cargo', 'test', '--offline', '--locked'], name+'-cargo-test')
        row['cargo_test_exit_code'] = tested.returncode
        row['cargo_test_summaries'] = [line for line in tested.stdout.decode().splitlines() if line.startswith('test result:')]
        cli = run(['cargo', 'run', '--offline', '--locked', '-p', 'topology', '--',
                   str(WORK/'求解器/数据/候选B/contract.json')], name+'-cli')
        row['cli_exit_code'] = cli.returncode
        report = cli.stdout.decode()
        row['cli_counts'] = dict(re.findall(r'^## (能检且通过|能检且不通过|不能静态检)（(\d+) 项', report, re.M))
        assert len(row['cli_counts']) == 3
        row['m120_load'] = next(line for line in report.splitlines() if '| 制造能力/M120 |' in line)
        row['original_report_equal'] = cli.stdout == (SNAPSHOT/'求解器/数据/候选B/校验报告.md').read_bytes()
        results.append(row)
        write_json(HERE/'运行结果.json', results)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    # 已有守卫的反例用于确认拒绝路径确实执行。
    control = copy.deepcopy(catalog)
    control['static_checks']['constants']['transport_s']['quantity']['value'] = '1'
    try:
        module.verify(control)
        control_result = 'accepted'
    except AssertionError as error:
        control_result = 'rejected: '+str(error)
    write_json(HERE/'回源对照.json', {'mutation': differences(catalog, control), 'result': control_result})
finally:
    catalog_path.write_bytes(original_bytes)
    after = {path: digest(Path(path)) for path in protected}
    write_json(HERE/'保护核验.json', {'unchanged': protected == after,
                                  'changes': {p: {'before': protected[p], 'after': after[p]} for p in protected if protected[p] != after[p]}})
    write_json(HERE/'运行元数据.json', {'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
                                    'recipe_values_match_formal_source': len(expected),
                                    'command_scope': '原转换器仅执行至第41行断言；cargo测试和CLI完整运行',
                                    'rust_version': subprocess.check_output(['rustc', '--version'], env=ENV).decode().strip(),
                                    'cargo_version': subprocess.check_output(['cargo', '--version'], env=ENV).decode().strip()})
