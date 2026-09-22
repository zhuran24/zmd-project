#!/usr/bin/env python3
"""核对被审证据链、有限轨迹计数和只读指纹，不重判运行语义。"""
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
SNAP = OUT / '输入快照'
DATA = SNAP / '求解器/数据'
R4 = DATA / '修订验证/r4'
manifest = json.loads((OUT / '输入指纹.json').read_text())['文件']
snapshot_by_original = {row['原路径']: OUT / row['快照'] for row in manifest}
checks, errors = [], []


def check(label, actual, expected):
    row = {'项目': label, '实际': actual, '期望': expected, '一致': actual == expected}
    checks.append(row)
    if not row['一致']:
        errors.append(row)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stored(path):
    return snapshot_by_original.get(path, Path(path))


for row in manifest:
    check('本轮输入未变/' + row['原路径'], digest(Path(row['原路径'])), row['sha256'])
    check('快照未变/' + row['快照'], digest(OUT / row['快照']), row['sha256'])
for record in json.loads((DATA / '候选B/交付哈希.json').read_text()):
    check('r4交付哈希/' + record['path'], digest(stored(record['path'])), record['sha256'])
for record in json.loads((DATA / '候选B/来源清单.json').read_text()):
    check('候选来源清单/' + record['path'], digest(stored(record['path'])), record['sha256'])
for name in ['只读文件指纹.json', '修订前产物指纹.json', '验证依赖指纹.json']:
    document = json.loads((R4 / name).read_text())
    if name == '修订前产物指纹.json':
        # 此表是历史起点，不要求它与修订后的产物相同；逐条对照修订记录的 before。
        before = document
        continue
    values = document.get('fingerprints', document)
    for path, expected in values.items():
        if isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected):
            check('r4证据指纹/' + name + '/' + path, digest(stored(path)), expected)
self_audit = json.loads((R4 / '交付自审.json').read_text())
for row in self_audit['owned_changes']:
    check('修订收尾/' + row['path'], digest(stored(row['path'])), row['after'])
    if row['before'] is not None:
        check('修订起点/' + row['path'], before.get(row['path']), row['before'])
conversion = json.loads((R4 / '转换复现.json').read_text())
check('历史转换前后', conversion['before'], conversion['after'])
for path, expected in conversion['after'].items():
    check('转换收尾/' + path, digest(stored(path)), expected)
gate_results = json.loads((R4 / '隔离门禁结果.json').read_text())['results']
for row in gate_results:
    rejected = row['expected'] == '拒绝'
    check(row['case'] + '/direct', row['direct_exit_code'], 1 if rejected else 0)
    check(row['case'] + '/cargo', row['cargo_exit_code'], 101 if rejected else 0)
    text = (R4 / row['log']).read_text()
    check(row['case'] + '/错误诊断', not rejected or row['diagnostic'] in text, True)
    check(row['case'] + '/cargo测试状态', 'test catalog_is_checked_against_live_formal_sources ... ' + ('FAILED' if rejected else 'ok') in text, True)

samples = json.loads((R4 / '样例检查.json').read_text())
runtime = json.loads((R4 / '运行输入回归结果.json').read_text())
trace = json.loads((R4 / '黄金轨迹运行记录.json').read_text())
original_trace = json.loads((DATA / '样例/混做粉碎机两下游-运行记录.json').read_text())
original_runtime = json.loads((SNAP / '求解器/规格/内核输入修订验证-r3/运行回归结果.json').read_text())
check('保存的两份轨迹相同', trace, original_trace)
check('保存的两份输入回归相同', runtime, original_runtime)
check('样例数', len(samples['results']), 3)
check('样例负例数', len(samples['negative_tests']), 19)
check('样例表达回归数', len(samples['representation_tests']), 8)
check('样例负例全部拒绝', all(row['status'] == '正确拒绝' for row in samples['negative_tests']), True)
check('输入回归数', len(runtime['tests']), 17)
check('输入回归轴数', runtime['axis_count'], 96)
events = []
for tick in trace['trace']['ticks']:
    events.append({'时刻': tick['time']['value']['value'], '事件数': len(tick['events']), '完成制造': [e for e in tick['events'] if e['operation'] == 'manufacture_complete'], '开始制造': [e for e in tick['events'] if e['operation'] == 'manufacture' and e['outcome'] == 'success']})
check('轨迹时刻', [e['时刻'] for e in events], ['0', '1', '2', '3'])
check('轨迹事件计数', [e['事件数'] for e in events], [28, 42, 43, 43])
check('制造完成次数', sum(len(e['完成制造']) for e in events), 2)
for flag in ['universal_parameters', 'all_reachable_cycles', 'target_certified']:
    check('有限轨迹未冒充全称/' + flag, trace['validation_scope'][flag], False)
dependency_state = {'说明': '仅检查所附日志、快照与事件计数一致性；本席没有以这段样例轨迹替代候选B的运行证明，也没有重判每条状态转移。', '样例数': 3, '负例数': 19, '表达回归数': 8, '输入回归数': 17, '轴数': 96, '轨迹事件': events}
result = {'状态': '通过' if not errors else '存在差异', '检查项数': len(checks), '差异': errors, '并行依赖': dependency_state, '逐项': checks}
(OUT / '证据链与只读复验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'状态': result['状态'], '检查项数': len(checks), '差异': errors}, ensure_ascii=False, indent=2))
assert not errors, errors[:3]
