#!/usr/bin/env python3
"""契约交付核对；只读输入，结果写入求解器内。"""
import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
from formal_catalog import verify

root = Path(__file__).resolve().parents[2]
data = root / '数据'
import argparse
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir', type=Path, default=data/'修订验证/r4')
args = parser.parse_args()
output_dir = args.output_dir.resolve()
assert any(output_dir.is_relative_to(base) for base in [data/'修订验证', root/'内核维护']), '自查输出限于数据/修订验证或内核维护'
output_dir.mkdir(parents=True, exist_ok=True)
# 报告自引用先建进行中标记，全部断言通过后再写成功结果。
(output_dir/'自查结果.json').write_text(json.dumps({'status':'进行中'},ensure_ascii=False)+'\n')
contract = json.loads((data/'候选B/contract.json').read_text())
catalog = json.loads((data/'正式静态目录.json').read_text())
verify(catalog)
feeds = contract['logical_feeds']
machines = contract['machines']
assert contract['schema'] == 'feeding-v2' and 'channels' not in contract
assert len(catalog['units']) == 18 and len(catalog['recipes']) == 18
assert len(catalog['constraints']) == 72
assert len({u['id'] for u in catalog['units']}) == 18
assert all(set(e['via']) == {'bridge','splitter','merger','gate'} for e in feeds)
assert all(e['proven_actual_rate'] is None and e['id'].startswith('LF') for e in feeds)
source_dir = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
rows = list(csv.DictReader((source_dir/'channels.csv').open()))
assert len(rows) == len(feeds)
for original, feed in zip(rows, feeds):
    assert feed['id'] == 'LF' + original['通道id'][1:]
    assert F(feed['planned_rate']['value']) == F(original['件每20tick']) / 20
    assert feed['planned_full_speed'] == (original['是否满速']=='是') == (F(feed['planned_rate']['value'])==1)
    assert feed['item'] == original['物品']
    assert feed['source_recipe'] == (original['源配方'] or None)
    assert feed['target_recipe'] == (original['目标配方'] or None)
    if original['源机器id'] != '仓库出矿口':
        assert feed['source'] == original['源机器id']
    else:
        assert feed['source'].startswith('ORE')
    assert feed['target'] == ('CORE' if original['目标机器id']=='协议核心' else original['目标机器id'])

def degree(mid, side):
    return len({e[side+'_port'] for e in feeds if e[side] == mid})
def degrees(kind):
    return [degree(m['id'],'target') for m in machines if m['kind']==kind]
metrics = {'machines':len(machines),'area':str(sum(F(m['area']['value']) for m in machines)),
    'logical_feeds':len(feeds),'S':len({(e['source'],e['source_port']) for e in feeds}),
    'R':len({(e['target'],e['target_port']) for e in feeds}),
    'grinders_with_three_inputs':sum(n>=3 for n in degrees('研磨机')),
    'shapers_with_two_inputs':sum(n>=2 for n in degrees('塑形机')),
    'packaging_inputs':degrees('封装机'),'filling_inputs':degrees('灌装机'),
    'K_plus_3B_plus_2C':degree('CORE','target'),
    'fanout_shapes':dict(Counter(f['planned_shape'] for f in contract['fanouts'])),
    'multi_material':sum(m['multi_material'] is not None for m in machines)}
assert metrics == {'machines':219,'area':'3325','logical_feeds':315,'S':315,'R':315,
    'grinders_with_three_inputs':31,'shapers_with_two_inputs':5,
    'packaging_inputs':[5,5,5],'filling_inputs':[4,4,4],'K_plus_3B_plus_2C':6,
    'fanout_shapes':{'满速扇出定则型':30,'轮询均分型':2,'两者都不落':1},'multi_material':43}
for path, expected in json.loads((output_dir/'只读文件指纹.json').read_text()).items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
for record in json.loads((data/'候选B/来源清单.json').read_text()):
    assert hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() == record['sha256'], record['path']
for doc in [data/'送料契约.md',data/'候选B/转换说明.md',data/'规则覆盖表.md',data/'修订记录.md',data/'候选B/验证记录.md']:
    import re
    for target in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
        assert (doc.parent/target.split('#')[0]).resolve().exists(), (doc,target)
# 两份覆盖表均逐行回源核对；A线其它自查由独立入口验证。
import re
coverage_checks = {}
for label, path in [('contract', data/'规则覆盖表.md'), ('semantics',root/'规格/规则覆盖表.md')]:
    sections = path.read_text().split('## ')
    for i, source in enumerate(catalog['sources'][:2],1):
        rows = [line.split('|')[1:-1] for line in sections[i].splitlines() if re.match(r'^\| \d+ \|',line)]
        assert len(rows)==len(source['lines'])
        for n,(row,line) in enumerate(zip(rows,source['lines']),1):
            assert int(row[0])==n and row[1].strip()==(line.strip() or '（空行）')
            assert row[2].strip()
        coverage_checks[label+'/'+source['path']] = len(rows)
    if label == 'contract':
        rows = [line.split('|')[1:-1] for line in sections[3].splitlines() if '`constraints[' in line]
        assert len(rows) == len(catalog['constraints'])
        for index, (row, rule) in enumerate(zip(rows, catalog['constraints'])):
            assert row[0].strip() == rule['name']
            assert row[1].strip() == rule['section']+'；'+(rule['obligation'] or '按条文前件')
            assert f'`constraints[{index}]`' in row[2]
            assert '据行 '+rule['basis_line']+' 完整转录' in row[2]
report = (data/'候选B/校验报告.md').read_text()
assert '能检且不通过（0 项' in report
assert '315+E≥315' in report and '非矿石 248' in report
for rule in catalog['constraints']:
    assert '正式条目/'+rule['name'] in report
    assert rule['basis'] in report and rule['section'] in report
axes = (root/'规格/选择点参数轴.md').read_text()
contract_text = (data/'送料契约.md').read_text()
interface = contract_text.split('## 待验字段与选择点接口')[1]
for field in re.findall(r'[a-z_]+\.[a-z_]+',interface):
    if field.split('.')[0] in ['time','judgment','polling','connection','manufacturing','offline']:
        assert '`'+field+'`' in axes, field
samples=json.loads((output_dir/'样例检查.json').read_text())
assert samples['status']=='通过' and len(samples['results'])==3
assert all(n['status']=='正确拒绝' for n in samples['negative_tests'])
result = {'status':'通过','scope':'目录完整回源、两份规则覆盖表逐行原文、契约格式、原CSV逐记录同值、候选件数、来源指纹、待验轴引用、文档链接及样例；非运行认证',
    'metrics':metrics,'planned_full_speed':sum(e['planned_full_speed'] for e in feeds),
    'coverage_rows':coverage_checks,'constraint_rows':len(catalog['constraints']),
    'read_only_sources_unchanged':True}
(output_dir/'自查结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
