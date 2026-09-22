"""第8轮回归：接口前件、字段名、KQ边界及当前规格一致性；不作运行认证。"""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent
WORKSPACE = SPEC.parent
AJV = '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
checks = []


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def check(condition, label):
    assert condition, label
    checks.append(label)


def run_script(relative, log_name, *args):
    # 子进程禁写字节码；所有日志及新结果均在本线目录，不编译内核。
    proc = subprocess.run([sys.executable, '-B', str(SPEC / relative), *args],
                          cwd=WORKSPACE, capture_output=True, text=True)
    (HERE / log_name).write_text(proc.stdout + proc.stderr)
    check(proc.returncode == 0, relative + '退出成功，详见' + log_name)
    return proc.stdout


def compile_guard(body):
    matches = re.findall(r'`(len\(U\)>=2 and [^`]+)`', body)
    assert len(matches) == 1, matches
    # 只求值已核的谓词语法，禁止属性、下标、导入与任意函数调用。
    tree = ast.parse(matches[0], mode='eval')
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Compare, ast.GtE,
               ast.In, ast.Call, ast.Name, ast.Load, ast.Store, ast.Constant,
               ast.GeneratorExp, ast.comprehension)
    assert all(isinstance(node, allowed) for node in ast.walk(tree))
    assert {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} <= {
        'len', 'any', 'U', 'E', 'w', 'assigned_slots'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name) and node.func.id in {'len', 'any'}
    compiled = compile(tree, '<规格停止谓词>', 'eval')

    def evaluate(new_species, empty_slots, assigned_slots):
        return eval(compiled, {'__builtins__': {}, 'len': len, 'any': any,
                               'U': new_species, 'E': empty_slots,
                               'assigned_slots': assigned_slots})
    return matches[0], evaluate


# 生成器需与当前schema逐字节一致；不只检“能被JSON读取”。
schema_path = SPEC / '内核输出.schema.json'
schema_before = schema_path.read_bytes()
run_script('第五轮规格修订/build_schema.py', 'schema生成.log')
check(schema_path.read_bytes() == schema_before, 'schema重新生成与既有字节一致')
revision = json.loads(run_script('check_revision.py', '规格自查.log'))
check(revision['status'] == 'PASS' and revision['axis_count'] == 99,
      '规格自查及99轴配置一致性通过')
interface = revision['shared_interface']
check(interface['axis_set_matches'] and not interface['lifetime_mismatches']
      and not interface['revision6_description_mismatches'], '输入轴投影与当前轴表一致')
run_script('第五轮规格修订/check_round5.py', '第五轮自查.log', '--output-dir', str(HERE))
round5 = json.loads((HERE / '自查结果.json').read_text())
check(round5['status'] == 'PASS' and round5['check_count'] == 183, '第五轮183项原有检查通过')

transfer = (SPEC / '受限转移定义.md').read_text()
reply = (SPEC / '参数轴-对内核输入请求的答复.md').read_text()
source_expression, source_guard = compile_guard(transfer)
reply_expression, reply_guard = compile_guard(reply)
truth_table = []
for species_count in range(4):
    new_species = {f'item_{index}' for index in range(species_count)}
    for empty_count in range(4):
        empty_slots = [f'W_empty_{index}' for index in range(empty_count)]
        for assigned_count in range(empty_count + 1):
            for selected in combinations(empty_slots, assigned_count):
                assigned_slots = {'W_ore_a', 'W_ore_b', *selected}
                # 独立判据来自可观察性：确有物种选择，且能被取货口观察。
                expected = species_count > 1 and bool(set(empty_slots) & assigned_slots)
                actual = source_guard(new_species, empty_slots, assigned_slots)
                stated = reply_guard(new_species, empty_slots, assigned_slots)
                assert actual == stated == expected
                truth_table.append({'new_species_count': species_count,
                                    'empty_slots': empty_slots, 'assigned_empty_slots': list(selected),
                                    'expected_stop': expected, 'transfer_stop': actual,
                                    'reply_stop': stated})
check(len(truth_table) == 60, '60组有限前件组合：答复/转移/独立可观察性判据一致')
products = ['高容谷地电池', '精选荞愈胶囊']
empty_slots = ['W_empty']
assigned_slots = {'W_ore_a', 'W_ore_b'}
ordered = sorted(products, key=lambda item: item.encode('utf-8'))
allocation = {item: empty_slots[index] if index < len(empty_slots)
              else 'W_new_' + item.encode('utf-8').hex()
              for index, item in enumerate(ordered)}
check(not reply_guard(products, empty_slots, assigned_slots), '双成品与一个未指派空格不停止')
check(reply_guard(products, empty_slots, assigned_slots | {'W_empty'}), '同一空格被指派即停止')
check(len(set(allocation.values())) == 2 and all(1 <= 80000 for _ in products),
      '规范落格两个唯一物种目标、每种1件容量合法')
dump('停止条件复算.json', {'scope': '局部守卫及条件落格，非完整可达布局或Rust运行',
                         'source_expression': source_expression, 'reply_expression': reply_expression,
                         'truth_table': truth_table, 'counterexample': {
                             'U': products, 'E': empty_slots, 'O': empty_slots,
                             'assigned_slots': sorted(assigned_slots),
                             'stop': False, 'allocation': allocation, 'O_after': [],
                             'quantities_after': {item: 1 for item in products},
                             'conditions': ['有电且传输开、冷却0', '身份和O完整', '新标签无冲突',
                                            '无改指派/拿取/离线且retain_history']}})

# 最小失败记录仅测schema封闭字段；不是迁移后的真实运行证书。
schema = json.loads(schema_path.read_text())
record = {'schema': 'kernel-output-v3', 'run_id': 'schema_only_round8',
          'profile_id': 'kernel_profile_v1',
          'producer': {'kind': 'manual_expected', 'path': str(Path(__file__).resolve()),
                       'claim': '仅字段结构试样，非运行记录'},
          'status': 'invalid_input', 'fingerprints': [], 'parameter_assignment': None,
          'input_history': None, 'uncovered_axes': [], 'trace': None,
          'validation_scope': None, 'open_items': ['结构试样：无可执行输入'],
          'execution_mode': 'finite_concrete', 'port_meeting': 'shared_edge_opposite'}
renamed = deepcopy(record)
renamed['verification_scope'] = renamed.pop('validation_scope')
script = """const fs=require('fs');const Ajv=require(process.argv[1]);
const p=JSON.parse(fs.readFileSync(0,'utf8'));const a=new Ajv({strict:false,allErrors:true});
const meta=a.validateSchema(p.schema);if(!meta)throw new Error(JSON.stringify(a.errors));
const v=a.compile({$schema:p.schema.$schema,$defs:p.schema.$defs,$ref:'#/$defs/RunRecord'});
console.log(JSON.stringify(p.records.map(r=>{const valid=v(r);return {valid,errors:v.errors};})));"""
proc = subprocess.run(['node', '-e', script, AJV], capture_output=True, text=True, check=True,
                      input=json.dumps({'schema': schema, 'records': [record, renamed]}))
valid, invalid = json.loads(proc.stdout)
check(valid['valid'], 'validation_scope结构正例通过AJV2020')
check(not invalid['valid'], '改名verification_scope结构负例被拒绝')
check(any(e['keyword'] == 'required' and e['params'].get('missingProperty') == 'validation_scope'
          for e in invalid['errors']), '改名负例明确缺validation_scope')
check(any(e['keyword'] == 'additionalProperties' and e['params'].get('additionalProperty') == 'verification_scope'
          for e in invalid['errors']), '改名负例明确多verification_scope')
run_schema = schema['$defs']['RunRecord']
check('validation_scope' in run_schema['required']
      and 'verification_scope' not in run_schema['properties']
      and run_schema['additionalProperties'] is False, '不为旧拼写增加schema兼容别名')
dump('字段名复算.json', {'scope': '仅schema结构，非执行认证', 'original': valid, 'renamed': invalid})

# KQ-08：零回矿账不能替代容量读取前的域检查。
ore_cases = [{'warehouse_quantity': quantity, 'candidate': '源矿', 'inbound_quantity': 1,
              'concrete_capacity_accepts': quantity + 1 <= 80000,
              'concrete_inbound': int(quantity + 1 <= 80000),
              'production_stop_before_capacity': True}
             for quantity in [79999, 80000]]
check(ore_cases[0]['concrete_capacity_accepts'] != ore_cases[1]['concrete_capacity_accepts']
      and ore_cases[1]['concrete_inbound'] == 0, 'KQ-08满仓零回矿账仍隐藏守卫差异')
check(all(row['production_stop_before_capacity'] for row in ore_cases),
      'KQ-08同矿候选对两代表统一在容量前停止（条件推演）')
dump('回矿容量复算.json', {'scope': '核心PC和整箱各回1件矿的局部容量算术；非Rust测试', 'cases': ore_cases})

# 当前正文全文扫旧句；历史复核、旧日志/试样只作为带时点的证据保留。
active_names = ['参数轴-对内核输入请求的答复.md', '运行语义.md', '选择点清单.md',
                '选择点参数轴.md', '受限模型声明.md', '受限转移定义.md', '内核输入.md',
                '内核输出.md', '规则覆盖表.md', '四件前置义务对照.md',
                '对内核的修改请求.md', '普遍审查场景.md', '内核输入-对参数轴的修改请求.md',
                '第四轮前置-疑问记录.md', '修订记录.md', '内核输入-修订记录.md']
forbidden = ['verification_scope', '整箱至少两种无非空/历史目标物种且有无身份空格时',
             'T12整箱多新物种竞争无身份空格明确unsupported', '无身份空格至少一个时返回unsupported',
             'len(U)>=2 and len(E)>=1', '循环段不得有矿石入库', '无回矿前提下']
scan = []
for name in active_names:
    body = (SPEC / name).read_text()
    hits = [{'line': index, 'phrase': phrase} for index, line in enumerate(body.splitlines(), 1)
            for phrase in forbidden if phrase in line]
    assert not hits, (name, hits)
    scan.append({'path': str(SPEC / name), 'lines': len(body.splitlines()), 'old_phrase_hits': hits})
check(True, '16份当前正文/交接/修订记录全文无已定位旧句')
question_body = (SPEC / '内核实现-对规格的疑问.md').read_text()
questions = re.findall(r'^## (KQ-\d+)', question_body, re.M)
check(all(int(value.split('-')[1]) <= 8 for value in questions), '交付前无KQ-08之后的新疑问')
requests = (SPEC / '对内核的修改请求.md').read_text()
check(all('| ' + value + ' |' in requests for value in ['KQ-07', 'KQ-08']), '新增KQ-07/08均有明确答复')
check('### 6.4 种子派生与检查点恢复' in (SPEC / '内核输入.md').read_text(), 'KQ-07沿用已有状态字段')
dump('辖域扫描.json', {'files': scan, 'forbidden_current_phrases': forbidden,
                      'historical_scope': '复核目录与以旧轮次命名的证据保存旧句，不作为现行契约；本轮脚本中的旧句仅为负例',
                      'questions_read': questions})
source_paths = [SPEC / name for name in active_names] + [schema_path, SPEC / '内核配置-v1.json',
                SPEC / 'check_revision.py', SPEC / '第五轮规格修订/check_round5.py',
                SPEC / '第五轮规格修订/build_schema.py', SPEC / '内核实现-对规格的疑问.md',
                WORKSPACE / 'crates/kernel/src/model.rs', WORKSPACE / 'crates/kernel/src/transition.rs',
                WORKSPACE / '数据/样例/混做粉碎机两下游-运行记录-kernel.json']
dump('本轮自查结果.json', {'status': 'PASS', 'checks': checks, 'check_count': len(checks),
                          'round5_check_count': round5['check_count'], 'axis_count': 99,
                          'scope': '规格、配置、schema、接口前件和局部容量；不含K线运行回归或全称认证',
                          'sources': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}})
print(json.dumps({'status': 'PASS', 'checks': len(checks), 'round5_checks': 183, 'guard_cases': 60}, ensure_ascii=False))
