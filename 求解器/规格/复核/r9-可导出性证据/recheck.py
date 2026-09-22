"""只读复核当前规格；将原自查的全部输出重定向到本席证据目录。"""
from pathlib import Path
from contextlib import redirect_stdout
from itertools import combinations, permutations
from fractions import Fraction
import ast
import hashlib
import io
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent.parent
ROOT = SPEC.parent.parent
SOURCE = SPEC / '第五轮规格修订-r8/check_round8.py'
OUTPUT = HERE / '重跑'
OUTPUT.mkdir(exist_ok=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    assert path.resolve().is_relative_to(HERE)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


# 不保存文件副本，锁定正文、原证据、正式源和候选的当前字节。
protected = [p for p in SPEC.iterdir() if p.is_file()]
protected += [p for folder in ['第五轮规格修订', '第五轮规格修订-r8']
              for p in (SPEC / folder).iterdir() if p.is_file()]
protected += [ROOT / name for name in ['《明日方舟：终末地》游戏规则.txt',
                                      '求解任务.txt', '求解约束.txt', '候选约束.txt']]
before = {str(path): digest(path) for path in protected}
dump(HERE / '复核前指纹.json', before)
namespace = {'__file__': str(SOURCE), '__name__': '__main__'}


def run_script(relative, log_name, *args):
    if relative == '第五轮规格修订/build_schema.py':
        # 仅替换已审生成器的输出目标；读取的基线、配置和生成逻辑原样。
        builder = SPEC / relative
        source = builder.read_text()
        old = "(spec/'内核输出.schema.json').write_text"
        assert source.count(old) == 1
        output_schema = OUTPUT / '重建schema.json'
        captured = io.StringIO()
        with redirect_stdout(captured):
            exec(compile(source.replace(old, 'output_schema.write_text'), str(builder), 'exec'),
                 {'__file__': str(builder), 'output_schema': output_schema})
        assert output_schema.read_bytes() == (SPEC / '内核输出.schema.json').read_bytes()
        stdout, stderr, returncode = captured.getvalue(), '', 0
    else:
        proc = subprocess.run([sys.executable, '-B', str(SPEC / relative), *args],
                              cwd=SPEC.parent, capture_output=True, text=True)
        stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
    (OUTPUT / log_name).write_text(stdout + stderr)
    namespace['check'](returncode == 0, relative + '退出成功，详见' + log_name)
    return stdout


# 原22项断言不变，只替换HERE/SPEC和有写操作的执行包装；原文件不改写。
tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
nodes = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == 'run_script':
        continue
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in ['HERE', 'SPEC']:
            path = OUTPUT if target.id == 'HERE' else SPEC
            node.value = ast.Call(func=ast.Name(id='Path', ctx=ast.Load()),
                                  args=[ast.Constant(str(path))], keywords=[])
    nodes.append(node)
tree.body = nodes
ast.fix_missing_locations(tree)
namespace['run_script'] = run_script
captured = io.StringIO()
with redirect_stdout(captured):
    exec(compile(tree, str(SOURCE), 'exec'), namespace)
(HERE / '原自查重跑.log').write_text(captured.getvalue())

# 独立枚举更宽的U/E/指派域；不复用原自查的60行期望数据。
expression, guard = namespace['compile_guard']((SPEC / '受限转移定义.md').read_text())
guard_cases = 0
for count in range(7):
    for empty_count in range(7):
        empty = [f'W_{i}' for i in range(empty_count)]
        for mask in range(1 << empty_count):
            assigned = {empty[i] for i in range(empty_count) if (mask >> i) & 1}
            actual = guard(set(range(count)), empty, assigned | {'W_ore'})
            assert actual == (count >= 2 and bool(assigned))
            guard_cases += 1

# 取空再入的局部表示与容量对照；这是条件算术，不称真实布局轨迹。
products = ['高容谷地电池', '精选荞愈胶囊']
label_cases = []
for item in products:
    for amount in [1, 2, 79999]:
        identity = item
        empty_order = []
        slot = 'product_history'
        after_take = {'slot': slot, 'item': None, 'quantity': 0,
                      'empty_identity': identity}
        after_return = {'slot': slot, 'item': item, 'quantity': amount,
                        'empty_identity': None}
        assert after_take['slot'] == after_return['slot'] and empty_order == []
        label_cases.append({'item': item, 'quantity': amount, 'same_slot': True, 'order': []})
capacity_cases = []
for quantity in [0, 79998, 79999, 80000]:
    for amount in [1, 2, 300]:
        capacity_cases.append({'before': quantity, 'batch': amount,
                               'one_item_available': quantity < 80000,
                               'batch_available': quantity + amount <= 80000,
                               'representative_available': amount < 80000})
assert any(r['one_item_available'] and not r['batch_available'] for r in capacity_cases)

# 完整读取并验证交付清单、日志及JSON；活动K线漂移只列观察，不当作S线改动。
manifest = json.loads((SPEC / '第五轮规格修订-r8/交付清单.json').read_text())
manifest_drift = []
for name, value in manifest['sha256'].items():
    path = Path(name)
    if not path.is_absolute():
        path = SPEC / path
    if not path.exists() or digest(path) != value:
        manifest_drift.append(str(path))
artifact_inventory = []
for path in sorted((SPEC / '第五轮规格修订-r8').iterdir()):
    data = path.read_text()
    parsed = json.loads(data) if path.suffix == '.json' else None
    artifact_inventory.append({'path': str(path), 'sha256': digest(path),
                               'lines': len(data.splitlines()),
                               'json_type': type(parsed).__name__ if parsed is not None else None})
after = {str(path): digest(path) for path in protected}
unchanged = before == after
assert unchanged
result = {'status': 'PASS', 'original_round8_checks': len(namespace['checks']),
          'original_round5_checks': namespace['round5']['check_count'],
          'extended_guard_cases': guard_cases, 'guard_expression': expression,
          'label_cases': label_cases, 'capacity_cases': capacity_cases,
          'original_artifacts': artifact_inventory, 'manifest_drift': manifest_drift,
          'protected_unchanged': unchanged,
          'rerun_method': '原r8 AST仅替换输出目录和执行包装；schema生成只改输出目标并与原字节比较；其余断言原样',
          'scope': '静态结构、原自查、局部守卫和容量算术；非K线运行或全称证明'}
dump(HERE / '复算结果.json', result)
print(json.dumps({k: result[k] for k in ['status', 'original_round8_checks',
                                       'original_round5_checks', 'extended_guard_cases',
                                       'manifest_drift', 'protected_unchanged']}, ensure_ascii=False))
