#!/usr/bin/env python3
"""第八轮第1否证席：独立复算局部停止谓词与实际输出 schema。"""

import copy
import datetime
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
EVIDENCE = Path(__file__).resolve().parent
WORKSPACE = EVIDENCE.parents[2]
REPOSITORY = WORKSPACE.parent
TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
AJV = Path('/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js')
PRODUCTS = ['高容谷地电池', '精选荞愈胶囊']


def save(name, value):
    path = EVIDENCE / name
    assert path.parent == EVIDENCE
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def fingerprint(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def source_paths():
    names = ['参数轴-对内核输入请求的答复.md', '受限转移定义.md', '内核输入.md',
             '内核输出.md', '内核输出.schema.json', '修订记录.md', '受限模型声明.md',
             '选择点参数轴.md', '内核输入-对参数轴的修改请求.md']
    paths = [WORKSPACE / '规格' / name for name in names]
    paths += [REPOSITORY / name for name in ['《明日方舟：终末地》游戏规则.txt',
                                           '求解任务.txt', '求解约束.txt', '候选约束.txt']]
    paths += [TASKS / name for name in ['任务书5.md', '任务书.md', '任务书2.md', '任务书3.md', '任务书4.md']]
    paths += [WORKSPACE / '规格/复核' / name for name in [
        '复核-r8-可导出性.md', '复核-r8-一致性.md',
        'r8-一致性证据/停止条件反例.json', 'r8-一致性证据/字段名反例.json',
        'r8-一致性证据/independent_checks.py']]
    return paths


def source_excerpt(path, first, last):
    lines = path.read_text().splitlines()
    return {'path': str(path), 'first_line': first, 'last_line': last,
            'lines': [{'line': index, 'text': lines[index - 1]} for index in range(first, last + 1)]}


def local_transaction():
    # 这是由转移原文独立写出的局部事务，不调用复核席脚本或 Rust 内核。
    initial_items = ['源矿', '蓝铁矿', '荞花', '砂叶', '荞花种子', '砂叶种子']
    rows = [{'slot': 'W_initial_' + str(index), 'item': item, 'quantity': 80000,
             'empty_identity': None} for index, item in enumerate(initial_items)]
    rows += [{'slot': 'E0', 'item': None, 'quantity': 0, 'empty_identity': None}]
    before = {'warehouse': rows, 'order': ['E0'], 'box': {item: 1 for item in PRODUCTS},
              'assigned_slots': ['W_initial_0', 'W_initial_1'], 'powered': True,
              'transfer_enabled': True, 'cooldown': 0}
    assert all(0 <= row['quantity'] <= 80000 for row in rows)
    assert all(0 < quantity <= 50 for quantity in before['box'].values())
    identities = {row['item'] or row['empty_identity']: row['slot'] for row in rows
                  if row['item'] is not None or row['empty_identity'] is not None}
    empty = [row['slot'] for row in rows if row['item'] is None
             and row['quantity'] == 0 and row['empty_identity'] is None]
    unknown = set(before['box']) - set(identities)
    assert set(empty) == set(before['order'])
    reply_stop = len(unknown) >= 2 and bool(empty)
    transition_stop = len(unknown) >= 2 and bool(set(empty) & set(before['assigned_slots']))
    assert reply_stop is True and transition_stop is False
    after = copy.deepcopy(before)
    plan = []
    used = set()
    for index, item in enumerate(sorted(unknown, key=lambda value: value.encode('utf-8'))):
        slot = before['order'][index] if index < len(before['order']) else 'W_new_' + item.encode('utf-8').hex()
        existing = next((row for row in after['warehouse'] if row['slot'] == slot), None)
        if existing is None:
            existing = {'slot': slot, 'item': None, 'quantity': 0, 'empty_identity': None}
            after['warehouse'].append(existing)
        assert existing['item'] is None
        amount = before['box'][item]
        assert existing['quantity'] + amount <= 80000
        existing.update(item=item, quantity=existing['quantity'] + amount)
        plan.append({'item': item, 'slot': slot, 'quantity': amount})
        used.add(slot)
    after['order'] = [slot for slot in before['order'] if slot not in used]
    after['box'] = {}
    after['cooldown'] = 5
    assert after['order'] == []
    assert {entry['quantity'] for entry in plan} == {1}
    assert after['warehouse'][:6] == before['warehouse'][:6]
    assert after['assigned_slots'] == before['assigned_slots']
    assert len({row['item'] for row in after['warehouse']}) == len(after['warehouse'])
    return {'scope': '有限具体执行的局部事务推演；不是完整 StateSeed、可达性证明或生产周期证书',
            'before': before, 'U': sorted(unknown), 'E': empty,
            'reply_stop': reply_stop, 'transition_stop': transition_stop,
            'plan': plan, 'after': after}


def guard_matrix():
    results = []
    for count in range(3):
        for empty_count in range(3):
            empty = [f'E{index}' for index in range(empty_count)]
            for mask in itertools.product([False, True], repeat=empty_count):
                assigned = [slot for slot, selected in zip(empty, mask) if selected]
                reply_stop = count >= 2 and bool(empty)
                transition_stop = count >= 2 and bool(set(empty) & set(assigned))
                results.append({'new_species_count': count, 'empty': empty, 'assigned_empty': assigned,
                                'reply_stop': reply_stop, 'transition_stop': transition_stop})
    mismatches = [row for row in results if row['reply_stop'] != row['transition_stop']]
    assert len(results) == 21 and len(mismatches) == 2
    assert all(not row['assigned_empty'] and row['empty'] for row in mismatches)
    return {'scope': '仅枚举两个停止谓词的有限布尔分界，不穷尽游戏状态',
            'cases': results, 'case_count': len(results), 'mismatches': mismatches}


def schema_probe(schema):
    # 使用自建结构试样，避免把改写旧运行记录当作完成迁移或重跑。
    record = {'schema': 'kernel-output-v3', 'run_id': 'r8-seat1-structure-probe',
              'profile_id': 'kernel_profile_v1', 'producer': {'kind': 'manual_expected',
              'path': str(Path(__file__).resolve()), 'claim': '仅输出字段结构试样，不是游戏运行证据'},
              'status': 'invalid_input', 'fingerprints': [], 'parameter_assignment': None,
              'input_history': None, 'uncovered_axes': [], 'trace': None,
              'validation_scope': {'kind': 'finite_trace',
                  'from': {'kind': 'rational', 'value': {'value': '0', 'category': '候选'}},
                  'through': {'kind': 'rational', 'value': {'value': '0', 'category': '候选'}}, 'golden_match': False,
                  'initial_history': 'conditional_witness', 'universal_parameters': False,
                  'all_reachable_cycles': False, 'target_certified': False,
                  'manufacturing_cycles_completed': {'value': '0', 'category': '候选'}},
              'open_items': ['结构试样：输入尚未装载，未产生轨迹'],
              'execution_mode': 'finite_concrete', 'port_meeting': 'shared_edge_opposite'}
    renamed = copy.deepcopy(record)
    renamed['verification_scope'] = renamed.pop('validation_scope')
    extra = copy.deepcopy(record)
    extra['verification_scope'] = copy.deepcopy(extra['validation_scope'])
    # 根 schema 原样编译；另编译同一 $defs/RunRecord，定位根 oneOf 内的具体错误。
    payload = {'root': schema, 'record_schema': {'$schema': schema['$schema'],
               '$defs': schema['$defs'], '$ref': '#/$defs/RunRecord'},
               'records': [record, renamed, extra]}
    code = """const fs=require('fs');
const Ajv=require(process.argv[1]);
const data=JSON.parse(fs.readFileSync(0,'utf8'));
const result={};
for(const key of ['root','record_schema']) {
  const check=new Ajv({strict:false,allErrors:true}).compile(data[key]);
  result[key]=data.records.map(value=>{const valid=check(value);return {valid,errors:check.errors};});
}
process.stdout.write(JSON.stringify(result));
"""
    completed = subprocess.run(['node', '-e', code, str(AJV)], input=json.dumps(payload),
                               text=True, capture_output=True, check=True)
    result = json.loads(completed.stdout)
    save('schema-试样.json', {'scope': '仅结构试样，不满足运行记录全部语义验收义务',
                          'original': record, 'renamed': renamed, 'extra_alias': extra})
    save('schema-结果.json', {'ajv': str(AJV), 'result': result, 'stderr': completed.stderr})
    for key in ['root', 'record_schema']:
        assert result[key][0]['valid'], result[key][0]
        assert not result[key][1]['valid'] and not result[key][2]['valid']
    errors = result['record_schema'][1]['errors']
    assert len(errors) == 2
    assert any(error['keyword'] == 'required' and error['params']['missingProperty'] == 'validation_scope' for error in errors)
    assert any(error['keyword'] == 'additionalProperties' and error['params']['additionalProperty'] == 'verification_scope' for error in errors)
    return {'original_valid': True, 'renamed_valid': False, 'extra_alias_valid': False,
            'run_record_rename_errors': errors}


def main():
    paths = source_paths()
    before = [fingerprint(path) for path in paths]
    save('读取指纹.json', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'files': before})
    spec = WORKSPACE / '规格'
    extracts = [source_excerpt(spec / '参数轴-对内核输入请求的答复.md', 1, 24),
                source_excerpt(spec / '受限转移定义.md', 85, 96),
                source_excerpt(spec / '受限转移定义.md', 132, 136),
                source_excerpt(spec / '修订记录.md', 223, 234),
                source_excerpt(spec / '内核输出.md', 5, 23),
                source_excerpt(spec / '内核输出.md', 63, 65)]
    save('原文摘录.json', extracts)
    reply = (spec / '参数轴-对内核输入请求的答复.md').read_text().splitlines()
    assert '本文件描述当前规格' in reply[2]
    assert '转移细节以' in reply[4]
    assert 'verification_scope' in reply[21]
    assert '整箱至少两种无非空/历史目标物种且有无身份空格时' in reply[23]
    assert '指派' not in reply[23]
    transaction = local_transaction()
    save('停止条件-独立事务.json', transaction)
    matrix = guard_matrix()
    save('停止条件-谓词对照.json', matrix)
    schema = json.loads((spec / '内核输出.schema.json').read_text())
    definition = schema['$defs']['RunRecord']
    assert 'validation_scope' in definition['properties'] and 'validation_scope' in definition['required']
    assert 'verification_scope' not in definition['properties']
    assert definition['additionalProperties'] is False
    schema_result = schema_probe(schema)
    after = [fingerprint(path) for path in paths]
    unchanged = before == after
    save('读取后核对.json', {'unchanged': unchanged, 'file_count': len(paths), 'files': after})
    assert unchanged
    summary = {'status': 'PASS', 'meaning': '本席局部检查的断言通过；不是被审规格无缺陷',
               'local_transaction': {'reply_stop': transaction['reply_stop'], 'transition_stop': transaction['transition_stop']},
               'guard_cases': matrix['case_count'], 'guard_mismatches': len(matrix['mismatches']),
               'schema_probe': schema_result, 'source_files_unchanged': len(paths)}
    save('复算摘要.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
