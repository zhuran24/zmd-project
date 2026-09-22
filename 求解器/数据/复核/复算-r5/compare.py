#!/usr/bin/env python3
"""独立结果封存后，逐项比较被审契约、目录与 Markdown 校验报告。"""
from collections import Counter, defaultdict
from fractions import Fraction as F
import csv
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
SNAP = OUT / '输入快照'
DATA = SNAP / '求解器/数据'
independent = json.loads((OUT / '独立复算.json').read_text())
formal = json.loads((OUT / '正式配方独立解析.json').read_text())
contract = json.loads((DATA / '候选B/contract.json').read_text())
catalog = json.loads((DATA / '正式静态目录.json').read_text())
report_text = (DATA / '候选B/校验报告.md').read_text()
checks, errors = [], []


def check(label, actual, expected):
    row = {'项目': label, '被审': actual, '独立期望': expected, '一致': actual == expected}
    checks.append(row)
    if not row['一致']:
        errors.append(row)


def q(value):
    return F(value['value'])


def quantity(label, value, expected, category):
    check(label + '/值', q(value), F(expected))
    check(label + '/类别', value['category'], category)


rows = {}
sections = Counter()
section = None
for lineno, line in enumerate(report_text.splitlines(), 1):
    if line.startswith('## '):
        section = line.split('（')[0][3:]
    if line.startswith('| ') and not line.startswith('| 检查项'):
        fields = line.strip('|').split('|')
        if len(fields) == 2:
            name, detail = map(str.strip, fields)
            check('报告唯一条目/' + name, name not in rows, True)
            rows[name] = {'行号': lineno, '正文': detail, '分组': section}
            sections[section] += 1
check('报告分组实际行数', dict(sections), {'能检且通过': 4925, '不能静态检': 59})


def number_row(name, pattern, expected):
    check('报告存在/' + name, name in rows, True)
    if name not in rows:
        return
    match = re.search(pattern, rows[name]['正文'])
    check('报告格式/' + name, match is not None, True)
    if match:
        check('报告数值/' + name, [F(x) for x in match.groups()], [F(x) for x in expected])


recipes = {r['id']: r for r in catalog['recipes']}
aliases = {**formal['别名'], '精炼-蓝铁粉末': 89}
check('目录配方全集', set(recipes), set(aliases))
for rid, line in aliases.items():
    source = formal['全部配方'][str(line)]
    rec = recipes[rid]
    check(rid + '/机型', rec['kind'], source['机型'])
    for side, key in [('inputs', '投入'), ('outputs', '产出')]:
        check(rid + '/' + side + '/物品集合', set(rec[side]), set(source[key]))
        for item, expected in source[key].items():
            quantity(rid + '/' + side + '/' + item, rec[side][item], expected, '条文直引')
    quantity(rid + '/耗时', rec['duration'], source['耗时'], '条文直引')
unit_map = {u['id']: u for u in catalog['units']}
for kind, expected in formal['尺寸与端口'].items():
    unit = unit_map[kind]
    for key, zh in [('width', '宽'), ('height', '高')]:
        quantity(kind + '/' + key, unit['dimensions'][key], expected[zh], '条文直引')
    quantity(kind + '/面积', unit['area'], expected['面积'], '算术推论')
    for key, zh in [('input_count', '存口'), ('output_count', '取口')]:
        quantity(kind + '/' + key, unit['ports'][key], expected[zh], '算术推论')
for key in ['width', 'height']:
    quantity('供电覆盖/' + key, unit_map['供电桩']['coverage'][key], 12, '条文直引')
for key, expected in [('input_count', 14), ('output_count', 6)]:
    quantity('协议核心/' + key, unit_map['协议核心']['ports'][key], expected, '条文直引')

machines = {m['id']: m for m in contract['machines']}
feeds = {f['id']: f for f in contract['logical_feeds']}
sources = {s['id']: s for s in contract['sources']}
check('契约机器身份全集', set(machines), {m['机器'] for m in independent['机器']})
check('契约送料身份全集', set(feeds), {'LF' + e['通道'][1:] for e in independent['通道']})
input_ports, output_ports = Counter(), Counter()
source_number = 0
mapped_edges = []
for edge in independent['通道']:
    fid = 'LF' + edge['通道'][1:]
    feed = feeds[fid]
    source, target = edge['源'], edge['目标']
    if source == '仓库出矿口':
        source = f'ORE{source_number:03d}'
        source_number += 1
        variable = sources[source]
        check(source + '/物品', variable['item'], edge['物品'])
        check(source + '/待求', variable['identity'], {'status': '待求', 'kind': None, 'side': None, 'index': None})
        quantity(source + '/端口', variable['output_ports'], 1, '条文直引')
    if target == '协议核心':
        target = 'CORE'
    input_ports[target] += 1
    output_ports[source] += 1
    expected = {'source': source, 'target': target, 'item': edge['物品'], 'source_port': f'{source}:out:{output_ports[source]}', 'target_port': f'{target}:in:{input_ports[target]}', 'proven_actual_rate': None, 'planned_full_speed': F(edge['计划每tick']) == 1, 'via': dict.fromkeys(['bridge', 'splitter', 'merger', 'gate'])}
    for side in ['source', 'target']:
        endpoint = expected[side]
        expected[side + '_recipe'] = next((m['配方'] for m in independent['机器'] if m['机器'] == endpoint), None)
    for key, value in expected.items():
        check(fid + '/' + key, feed[key], value)
    quantity(fid + '/计划速率', feed['planned_rate'], edge['计划每tick'], '候选')
    number_row('端口速率/记录/' + fid, r'计划 (\S+) 件/tick', [edge['计划每tick']])
    number_row('满速独占/计划标记/' + fid, r'计划 (\S+) 件/tick', [edge['计划每tick']])
    check('报告满速标记/' + fid, '满速标记=true' in rows['满速独占/计划标记/' + fid]['正文'], expected['planned_full_speed'])
    for side, label in [('source', '取货'), ('target', '存货')]:
        number_row(f'端口速率/{label}/{expected[side]}/{expected[side + "_port"]}', r'端口各记录合计 (\S+) 件/tick', [edge['计划每tick']])
    mapped_edges.append(expected)
check('矿口全集', set(sources), {f'ORE{i:03d}' for i in range(source_number)})
arrivals = []
for machine in independent['机器']:
    mid, rid = machine['机器'], machine['配方']
    m = machines[mid]
    size = formal['尺寸与端口'][machine['机型']]
    check(mid + '/机型', m['kind'], machine['机型'])
    check(mid + '/配方列表', [r['recipe'] for r in m['recipes']], [rid])
    for key, value in [('planned_batch_rate', machine['计划批次每tick']), ('planned_mean_batch_interval', 1 / F(machine['计划批次每tick']))]:
        quantity(mid + '/' + key, m['recipes'][0][key], value, '候选')
    for key, expected in [('input_ports', size['存口']), ('output_ports', size['取口']), ('area', machine['面积'])]:
        quantity(mid + '/' + key, m[key], expected, '算术推论')
    multi = len(machine['投入每tick']) > 1 or machine['存通道数'] > 1
    expected_multi = {'arrival_composition_per_tick': '待验', 'synchronization': '待验', 'same_source': '待验'} if multi else None
    check(mid + '/三栏', m['multi_material'], expected_multi)
    if multi:
        arrivals.append(mid)
    number_row('端口数/' + mid, r'存货 (\d+)、取货 (\d+)、存货上限 (\d+)、取货上限 (\d+)', [machine['存通道数'], machine['取通道数'], size['存口'], size['取口']])
    number_row('占地/' + mid, r'机型面积 (\d+) 格', [machine['面积']])
    number_row('制造能力/' + mid, r'各配方批次率×耗时之和 (\S+) ≤1', [machine['制造占时']])
    for key, label in [('投入每tick', '输入'), ('产出每tick', '输出')]:
        for item, rate in machine[key].items():
            number_row(f'逐机配方守恒/{mid}/{rid}/{label}/{item}', r'计划通道合计 (\S+)，配方要求 (\S+) 件/tick', [rate, rate])

by_fanout = {x['machine']: x for x in contract['fanouts']}
check('扇出身份集合', set(by_fanout), {x['机器'] for x in independent['扇出']})
for row in independent['扇出']:
    fan = by_fanout[row['机器']]
    for key, cn in [('recipe', '配方'), ('item', '物品'), ('planned_shape', '计划分类'), ('certification', '认证状态')]:
        check(row['机器'] + '/扇出/' + key, fan[key], row[cn])
    for key, cn, category in [('ports', 'k', '候选'), ('planned_port_rate', '每端口计划每tick', '候选'), ('planned_mean_batch_interval', '计划平均批间隔', '候选'), ('batch_size', '每批件数', '条文直引')]:
        quantity(row['机器'] + '/扇出/' + key, fan[key], row[cn], category)
    check('报告扇出/' + row['机器'], re.search(r'计算形状=([^；]+)', rows['扇出/计划分类/' + row['机器']]['正文'])[1], row['计划分类'])
for row in independent['物料']:
    total = row['全部通道件每tick']
    number_row('全局守恒/' + row['物品'], r'产出\+出库 (\S+) = 消耗\+入库 (\S+) 件/tick', [total, total])
    number_row('物料流量/' + row['物品'], r'首次来源流量 (\S+) ≥ (\S+) 件/tick', [total, total])
for item, rate in independent['摘要']['成品产率'].items():
    quantity('契约目标/' + item, contract['targets'][item], rate, '条文直引')
    number_row('目标/' + item, r'计划入库 (\S+)，目标 (\S+) 件/tick', [rate, rate])

# 机型与通道下限直接从正式约束解析；不取目录阈值为期望。
constraint_text = (SNAP / '求解约束.txt').read_text()
constraint_lines = constraint_text.splitlines()
bodies = {line.split('：', 1)[0]: line.split('：', 1)[1] for line in constraint_lines if '：' in line and not line.startswith(' ')}
lower = {kind: int(n) for kind, n in re.findall(r'(\S+) ≥(\d+)', bodies['机型下限'].split('，合计')[0].replace('、', ' '))}
channel_parts = bodies['通道下限'].split('；')
for kind, count in independent['摘要']['机型台数'].items():
    ins, outs = independent['摘要']['分型机器存取通道'][kind]
    in_min, out_min = [int(re.search(re.escape(kind) + r' (\d+)', part)[1]) for part in channel_parts[:2]]
    number_row('机型下限/' + kind, r'(\d+) ≥ (\d+)', [count, lower[kind]])
    number_row('通道下限/' + kind, r'存货 (\d+) ≥(\d+)；取货 (\d+) ≥(\d+)', [ins, in_min, outs, out_min])
    for key, expected in [('machines', lower[kind]), ('input_channels', in_min), ('output_channels', out_min)]:
        quantity(kind + '/正式下限/' + key, unit_map[kind]['static_lower_bounds'][key], expected, '条文直引')
for name, pattern, expected in [
    ('研磨进料/研磨', r'至少 (\d+) 输入的研磨机 (\d+)/(\d+)', [3, 31, 32]),
    ('研磨进料/塑形', r'至少 (\d+) 输入的塑形机 (\d+)/(\d+)', [2, 5, 6]),
    ('运输端口收支/可知投影', r'S=(\d+)、R=(\d+)', [315, 315]),
    ('箱体接口/已知计数投影', r'H=(\d+)、η=(\d+)，S\+R=(\d+)≥(\d+)', [2, 5, 630, 624]),
    ('满速独占/计划适用集合', r'计划满速记录 (\d+) 条，其中矿石来源 (\d+)、非矿石 (\d+)', [300, 52, 248]),
    ('矿石分流与专机/定义计数', r'N矿=(\d+)；.*C矿=(\d+)', [52, 52]),
    ('成品汇入/通道下限/入库途径', r'K=(\d+)；成品来源=(\d+)', [6, 6]),
    ('单位矿耗/矿石需求', r'蓝铁矿=(\d+)、源矿=(\d+)', [34, 18]),
    ('回路守恒/种子自给/荞花', r'采种 (\S+)、种植 (\S+) 批/tick', [F('11/2'), 11]),
    ('回路守恒/种子自给/砂叶', r'采种 (\S+)、种植 (\S+) 批/tick', [F('21/2'), 21]),
]:
    number_row(name, pattern, expected)
for name in ['运输端口收支/派生运输下限', '回路转弯/占格条件投影', '多料接口/全称目标']:
    check('未定保持未认证/' + name, rows[name]['分组'], '不能静态检')
for index, line in enumerate(constraint_lines):
    if not line or line.startswith(' ') or '：' not in line or line.endswith('：'):
        continue
    name, text = line.split('：', 1)
    key = '正式条目/' + name
    check('正式约束保持待认证/' + name, rows[key]['分组'], '不能静态检')
    check('正式约束全文/' + name, '条文：' + text + '；据：' + constraint_lines[index + 1].strip()[2:] in rows[key]['正文'], True)
coverage = (DATA / '规则覆盖表.md').read_text().split('## ')
for index, name in enumerate(['《明日方舟：终末地》游戏规则.txt', '求解任务.txt'], 1):
    actual = [line.split('|')[1:-1] for line in coverage[index].splitlines() if re.match(r'^\| \d+ \|', line)]
    expected = (SNAP / name).read_text().splitlines()
    check('覆盖行数/' + name, len(actual), len(expected))
    for number, (record, text) in enumerate(zip(actual, expected), 1):
        check(f'覆盖原文/{name}:{number}', record[1].strip(), text.strip() or '（空行）')

full = [edge for edge in independent['通道'] if F(edge['计划每tick']) == 1]
plant_area = sum(row['面积'] for row in independent['机器'] if row['机型'] in ['种植机', '采种机'] or row['配方'] in ['粉碎-荞花', '粉碎-砂叶'])
supplement = {'到达义务机器': arrivals, '登记数': len(arrivals), '多物品之外的机器': sorted(set(arrivals) - {row['机器'] for row in independent['多料机']}), '计划满速数': len(full), '非矿石计划满速数': sum(edge['源'] != '仓库出矿口' for edge in full), '植物相关制造面积': plant_area, '无箱H': 2, '无箱eta': max(2 - 2, 5, 2 * 2 - 9), '无箱接口下限': 619 + max(0, 5, -5), 'T加b接口下界': '315+E，E≥0', 'T加b流量下界': 306}
number_row('回路转弯/占格条件投影', r'相关制造占格=(\d+)', [plant_area])
check('到达义务总数', len(arrivals), 43)
check('非矿石计划满速数', supplement['非矿石计划满速数'], 248)
result = {'独立结果sha256': hashlib.sha256((OUT / '独立复算.json').read_bytes()).hexdigest(), '检查项数': len(checks), '差异数': len(errors), '差异': errors, '补充计数': supplement, '报告实际分组数': dict(sections), '逐项': checks}
(OUT / '逐项对比.json').write_text(json.dumps(result, default=lambda x: sorted(x) if isinstance(x, set) else str(x), ensure_ascii=False, indent=2) + '\n')
(OUT / '报告条目索引.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != '逐项'}, ensure_ascii=False, indent=2))
assert not errors, errors[:3]
