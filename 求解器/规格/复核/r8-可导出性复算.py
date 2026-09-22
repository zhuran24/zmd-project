"""复核席只读加载原产物；所有新证据仅写本席复核目录。"""
from pathlib import Path
from contextlib import redirect_stdout
from copy import deepcopy
from fractions import Fraction
import ast
import hashlib
import io
import json
import runpy
import sys
import traceback

review = Path(__file__).resolve().parent
spec = review.parent
root = spec.parent.parent
evidence = review / 'r8-可导出性证据'
evidence.mkdir(exist_ok=True)


def guard(event, args):
    # 阻止本进程意外改写被复核文件，也禁止产生字节码缓存。
    if event == 'open' and isinstance(args[0], (str, bytes)):
        mode, flags = args[1], args[2]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or flags & 3 != 0 or flags & 64 != 0
        if writing and not Path(args[0]).resolve().is_relative_to(review):
            raise PermissionError('复核写权之外：' + str(args[0]))


sys.addaudithook(guard)
sys.dont_write_bytecode = True


def save(name, value):
    (evidence / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


targets = ['受限转移定义.md', '受限模型声明.md', '选择点参数轴.md', '内核配置-v1.json',
           '内核输入.md', '内核输出.md', '内核输出.schema.json', '普遍审查场景.md', '对内核的修改请求.md',
           '运行语义.md', '选择点清单.md', '四件前置义务对照.md', '规则覆盖表.md', '第四轮前置-疑问记录.md',
           '参数轴-对内核输入请求的答复.md', '内核输入-对参数轴的修改请求.md', '修订记录.md',
           '内核输入-修订记录.md', 'check_revision.py']
paths = [spec / name for name in targets] + sorted((spec / '第五轮规格修订').iterdir())
paths += [root / name for name in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']]
fingerprints = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
save('读取指纹.json', fingerprints)
for path in paths:
    if path.suffix == '.json':
        json.loads(path.read_text())

log = io.StringIO()
previous = {'__file__': str(spec / 'check_revision.py'), '__name__': '__review__'}
check_failures = []
with redirect_stdout(log):
    try:
        exec(compile((spec / 'check_revision.py').read_text(), previous['__file__'], 'exec'), previous)
    except AssertionError as error:
        check_failures.append({'script': 'check_revision.py', 'error': str(error)})
        traceback.print_exc(file=log)
(evidence / '既有自查复跑.log').write_text(log.getvalue())

# 原自查的四个落盘动作改为写复核目录；其余断言与路径保持原样。
source = spec / '第五轮规格修订/check_round5.py'
tree = ast.parse(source.read_text(), filename=str(source))
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name == 'dump':
        node.body = ast.parse("review_save(name, value)").body
ast.fix_missing_locations(tree)
sys.path.insert(0, str(source.parent))
namespace = {'__file__': str(source), '__name__': '__review__', 'review_save': save}
log = io.StringIO()
with redirect_stdout(log):
    try:
        exec(compile(tree, str(source), 'exec'), namespace)
    except AssertionError as error:
        check_failures.append({'script': 'check_round5.py', 'error': str(error)})
        traceback.print_exc(file=log)
(evidence / '第五轮自查复跑.log').write_text(log.getvalue())

# 在内存中再生成 schema，与交付字节逐一对照，不执行生成器的原落盘语句。
builder = spec / '第五轮规格修订/build_schema.py'
tree = ast.parse(builder.read_text(), filename=str(builder))
tree.body = [node for node in tree.body if not (
    isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'write_text')]
ast.fix_missing_locations(tree)
generated = {'__file__': str(builder), '__name__': '__review__'}
log = io.StringIO()
with redirect_stdout(log):
    exec(compile(tree, str(builder), 'exec'), generated)
assert json.dumps(generated['schema'], ensure_ascii=False, indent=2) + '\n' == (spec / '内核输出.schema.json').read_text()

from cycle_key_reference import cycle_key, key_bytes, PRODUCTS
base = deepcopy(namespace['state'])
changed = deepcopy(base)
changed['warehouse']['slots'].append({
    'slot': 'review_product', 'item': PRODUCTS[0],
    'quantity': {'value': '79999', 'category': '候选'},
    'empty_identity': {'status': 'not_applicable', 'value': None, 'basis': ['复核条件试样']}})
empty = deepcopy(changed)
row = empty['warehouse']['slots'][-1]
row['item'] = None
row['quantity']['value'] = '0'
row['empty_identity'] = {'status': 'specified', 'value': PRODUCTS[0], 'basis': ['清空前物种']}
assert key_bytes(cycle_key(base)) == key_bytes(cycle_key(changed)) == key_bytes(cycle_key(empty))
assert empty['semantic_context']['arbitration']['warehouse_empty_slot_order'] == []

# 四种最低限度的独立算术/谓词核对，不把它们写成完整运行证书。
cases = {
    'product_capacity': {'quantity': 79999, 'incoming': 2,
                         'capacity_one': 79999 < 80000,
                         'concrete_whole_batch': 79999 + 2 <= 80000,
                         'representative_whole_batch': 2 <= 80000},
    'ore_return': {'q79999_accepts_one': 79999 + 1 <= 80000,
                   'q80000_accepts_one': 80000 + 1 <= 80000},
    'unassigned_empty_slot_stop': {'new_species_count': 2, 'anonymous_slots': ['E0'],
                                   'assigned_anonymous_slots': [],
                                   'transfer_4_3_stop': False, 'reply_line24_stop': True},
    'product_emptying': {'key_preserved': True, 'empty_order_unchanged': True,
                         'retained_identity': row['empty_identity']['value']},
    'scope': '局部条件算术、字段映射及停止谓词；不是 Rust 运行或完整可达布局证明'
}
assert Fraction(18, 30) == Fraction(3, 5)
assert Fraction('16.5') / 30 == Fraction(11, 20)
save('独立条件复算.json', cases)
after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
assert after == fingerprints
save('复核结果.json', {
    'status': 'PARTIAL' if check_failures else 'PASS', 'original_script_failures': check_failures,
    'existing_check_count_before_stop': len(previous['results']),
    'round5_check_count': len(namespace['results']), 'schema_byte_reproduction': True,
    'reviewed_files_unchanged': True, 'fingerprinted_files': len(fingerprints),
    'compilation': '未编译', 'scope': '机械自查复现与独立局部核算；不等于完整语义认证'})
original = json.loads((spec / '第五轮规格修订/开工只读指纹.json').read_text())
save('历史只读指纹差异.json', [{'path': p, 'expected': sha, 'actual': hashlib.sha256(Path(p).read_bytes()).hexdigest()}
                              for p, sha in original.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != sha])
print(json.dumps({'status': 'PARTIAL' if check_failures else 'PASS', 'round5_check_count': len(namespace['results']),
                  'evidence': str(evidence)}, ensure_ascii=False))
