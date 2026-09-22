#!/usr/bin/env python3
"""只读正式条文与原始候选 B，以有理数独立复算；不读取被审目录或报告。"""
from collections import Counter, defaultdict
import ast
import csv
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
SNAP = OUT / '输入快照'
RAW = SNAP / '原始候选B'
errors = []
checks = []


def check(label, actual, expected):
    row = {'项目': label, '实算': actual, '对照': expected, '一致': actual == expected}
    checks.append(row)
    if not row['一致']:
        errors.append(row)


def encode(value):
    if isinstance(value, F):
        return str(value)
    raise TypeError(type(value).__name__)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, default=encode, ensure_ascii=False, indent=2) + '\n')


def table(name, rows):
    with (OUT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, default=encode, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def amounts(text):
    result = {}
    for term in re.split(r'[＋+]', text.strip()):
        match = re.fullmatch(r'\s*(\d+)\s+(.+?)\s*', term)
        assert match, term
        result[match[2]] = F(match[1])
    return result


lines = (SNAP / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
recipes = {}
owner = None
for lineno, line in enumerate(lines, 1):
    if lineno < 80:
        continue
    if line.strip().endswith(('机', '炉')):
        owner = line.strip()
    match = re.fullmatch(r'(.+) → (.+)，(\d+) tick', line.strip())
    if match:
        recipes[lineno] = {'机型': owner, '投入': amounts(match[1]), '产出': amounts(match[2]), '耗时': F(match[3]), '规则行': lineno}
assert len(recipes) == 18

# 名称别名只指向条文行；投入、产出、耗时均从条文现文解析。
aliases = dict(zip(
    ['粉碎-源矿', '粉碎-蓝铁块', '粉碎-荞花', '粉碎-砂叶', '精炼-蓝铁矿', '精炼-致密蓝铁',
     '研磨-致密蓝铁', '研磨-致密源石', '研磨-细磨荞花', '塑形-钢质瓶', '配件-钢制零件',
     '种植-荞花', '种植-砂叶', '采种-荞花', '采种-砂叶', '封装-电池', '灌装-胶囊'],
    [81, 82, 83, 84, 87, 88, 92, 93, 94, 97, 100, 103, 104, 107, 108, 111, 114]))
sizes = {}
for lineno, owners in [(44, ['粉碎机', '精炼炉', '配件机', '塑形机']), (50, ['采种机', '种植机']), (54, ['研磨机', '封装机', '灌装机'])]:
    match = re.search(r'大小(\d+)x(\d+)', lines[lineno - 1])
    width, height = map(int, match.groups())
    for kind in owners:
        sizes[kind] = {'宽': width, '高': height, '面积': width * height, '存口': width, '取口': width, '规则行': lineno}
machines = list(csv.DictReader((RAW / 'machines.csv').open()))
channels = list(csv.DictReader((RAW / 'channels.csv').open()))
window = int(re.search(r'批次每(\d+)tick', next(k for k in machines[0] if k.startswith('批次每')))[1])
assert window == int(re.search(r'件每(\d+)tick', next(k for k in channels[0] if k.startswith('件每')))[1])
model = {row['机器id']: {'原行': n + 2, '配方': row['配方'], '规则': recipes[aliases[row['配方']]], '批次率': F(row[f'批次每{window}tick']) / window} for n, row in enumerate(machines)}
assert len(model) == len(machines)

# 从目标两产率和配方网络解物料守恒方程，不使用约束内已算流量当输入。
task = (SNAP / '求解任务.txt').read_text()
target_match = re.search(r'（([\d.]+) 个/tick 与 ([\d.]+) 个/tick）', task)
targets = dict(zip(['高容谷地电池', '精选荞愈胶囊'], map(F, target_match.groups())))
active = sorted({aliases[row['配方']] for row in machines})
items = sorted({item for line in active for side in ('投入', '产出') for item in recipes[line][side]})
internal = [item for item in items if item not in ('蓝铁矿', '源矿')]
matrix = [[recipes[line]['产出'].get(item, F(0)) - recipes[line]['投入'].get(item, F(0)) for line in active] + [targets.get(item, F(0))] for item in internal]
rank = 0
pivots = []
for col in range(len(active)):
    pivot = next((r for r in range(rank, len(matrix)) if matrix[r][col]), None)
    if pivot is None:
        continue
    matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
    factor = matrix[rank][col]
    matrix[rank] = [v / factor for v in matrix[rank]]
    for row in range(len(matrix)):
        if row != rank:
            factor = matrix[row][col]
            matrix[row] = [a - factor * b for a, b in zip(matrix[row], matrix[rank])]
    pivots.append(col)
    rank += 1
assert rank == len(active)
rates = {active[col]: matrix[row][-1] for row, col in enumerate(pivots)}
assert all(r >= 0 for r in rates.values())
save('正式配方独立解析.json', {'全部配方': recipes, '尺寸与端口': sizes, '别名': aliases})
save('目标反推.json', {'目标': targets, '说明': '限定原始候选采用的17条配方；未用的蓝铁粉末精炼回块配方仍列入正式解析，但本候选批次率为0。', '秩': rank, '逐配方批次率': rates})

incoming = defaultdict(list)
outgoing = defaultdict(list)
channel_rows = []
flow = defaultdict(F)
for lineno, raw in enumerate(channels, 2):
    source, target, item = raw['源机器id'], raw['目标机器id'], raw['物品']
    rate = F(raw[f'件每{window}tick']) / window
    row = {'通道': raw['通道id'], '原始行': lineno, '源': source, '目标': target, '物品': item, '计划每tick': rate}
    channel_rows.append(row)
    incoming[target].append(row)
    outgoing[source].append(row)
    flow[item] += rate
    check(f'{row["通道"]}端口速率', 0 < rate <= 1, True)
    check(f'{row["通道"]}满速标注', raw['是否满速'], '是' if rate == 1 else '否')
    for endpoint, prefix, side in [(source, '源', '产出'), (target, '目标', '投入')]:
        if endpoint in model:
            unit = model[endpoint]
            check(f'{row["通道"]}{prefix}配方', raw[prefix + '配方'], unit['配方'])
            check(f'{row["通道"]}{prefix}物品', item in unit['规则'][side], True)
        else:
            check(f'{row["通道"]}{prefix}外部端点', endpoint, '仓库出矿口' if prefix == '源' else '协议核心')


def summarize(rows):
    result = defaultdict(F)
    for row in rows:
        result[row['物品']] += row['计划每tick']
    return dict(result)


machine_rows = []
multi_rows = []
fanout_rows = []
counts = Counter()
degrees = defaultdict(lambda: [0, 0])
recipe_actual = defaultdict(F)
for raw in machines:
    mid = raw['机器id']
    unit = model[mid]
    recipe, rate = unit['规则'], unit['批次率']
    size = sizes[recipe['机型']]
    ins, outs = incoming[mid], outgoing[mid]
    expected_in = {item: n * rate for item, n in recipe['投入'].items()}
    expected_out = {item: n * rate for item, n in recipe['产出'].items()}
    check(f'{mid}投入守恒', summarize(ins), expected_in)
    check(f'{mid}产出守恒', summarize(outs), expected_out)
    check(f'{mid}制造占时', 0 < rate * recipe['耗时'] <= 1, True)
    check(f'{mid}存口容量', len(ins) <= size['存口'], True)
    check(f'{mid}取口容量', len(outs) <= size['取口'], True)
    check(f'{mid}原始尺寸', raw['机型'], f'{size["宽"]}x{size["高"]}')
    check(f'{mid}原始存通道数', int(raw['存货通道数']), len(ins))
    check(f'{mid}原始取通道数', int(raw['取货通道数']), len(outs))
    for key, rows in [('存货通道速率', ins), ('取货通道速率', outs)]:
        parsed = [part.rsplit(':', 1) for part in raw[key].split(';')]
        check(f'{mid}{key}逐条多重集', sorted((item, F(q) / window) for item, q in parsed), sorted((row['物品'], row['计划每tick']) for row in rows))
    counts[recipe['机型']] += 1
    degrees[recipe['机型']][0] += len(ins)
    degrees[recipe['机型']][1] += len(outs)
    recipe_actual[recipe['规则行']] += rate
    row = {'机器': mid, '原始行': unit['原行'], '机型': recipe['机型'], '配方': unit['配方'], '规则行': recipe['规则行'], '计划批次每tick': rate, '制造占时': rate * recipe['耗时'], '面积': size['面积'], '存通道数': len(ins), '取通道数': len(outs), '投入每tick': expected_in, '产出每tick': expected_out, '各存口速率': [x['计划每tick'] for x in ins], '各取口速率': [x['计划每tick'] for x in outs]}
    machine_rows.append(row)
    if len(recipe['投入']) > 1:
        multi_rows.append({'机器': mid, '配方': unit['配方'], '计划批次每tick': rate, '每批用量': recipe['投入'], '计划平均进料每tick': expected_in, '各存口': ins, '源机器集合': sorted({x['源'] for x in ins}), '逐tick实际构成': '待验', '多料同步': '待验', '同源运行标记': '待验'})
    if len(outs) > 1:
        port_rates = [x['计划每tick'] for x in outs]
        check(f'{mid}计划均分', len(set(port_rates)), 1)
        quantity = sum(recipe['产出'].values())
        interval = 1 / rate
        cls = '满速扇出定则型' if all(x == 1 for x in port_rates) else '轮询均分型' if interval == 1 and 2 * quantity <= len(outs) else '两者都不落'
        fanout_rows.append({'机器': mid, '配方': unit['配方'], '物品': next(iter(recipe['产出'])), 'k': len(outs), '每批件数': quantity, '每端口计划每tick': port_rates[0], '计划平均批间隔': interval, '计划分类': cls, '认证状态': '待验'})

for line, actual in recipe_actual.items():
    check(f'规则L{line}批次率与目标反推', actual, rates[line])
material_rows = []
for item in items:
    production = sum(rates[line] * recipes[line]['产出'].get(item, F(0)) for line in active)
    consumption = sum(rates[line] * recipes[line]['投入'].get(item, F(0)) for line in active)
    warehouse_out = summarize(outgoing['仓库出矿口']).get(item, F(0))
    warehouse_in = summarize(incoming['协议核心']).get(item, F(0))
    check(f'{item}全局守恒', production + warehouse_out, consumption + warehouse_in)
    check(f'{item}通道合计', flow[item], consumption + warehouse_in)
    material_rows.append({'物品': item, '制造产出': production, '制造消耗': consumption, '出库': warehouse_out, '入库': warehouse_in, '全部通道件每tick': flow[item]})

# 原始脚本仅用 AST 读取其配方常量，避免执行它造成原文件覆盖。
tree = ast.parse((RAW / 'design.py').read_text())
design_recipes = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'RECIPE' for t in node.targets))
for name, (_, ins, outs, duration) in design_recipes.items():
    formal = recipes[aliases[name]]
    for label, actual, expected in [('投入', ins, formal['投入']), ('产出', outs, formal['产出']), ('耗时', duration, formal['耗时'])]:
        check(f'design.py {name}{label}', actual, expected)
raw_fanout = json.loads((RAW / 'fanout.json').read_text(), parse_float=str)
check('原始扇出节点集合', sorted(x['机器'] for x in raw_fanout), sorted(x['机器'] for x in fanout_rows))
by_fanout = {x['机器']: x for x in fanout_rows}
class_labels = {'满速扇出定则型': 'A 满速', '轮询均分型': 'B 原文前提内', '两者都不落': 'C 需推广版'}
for old in raw_fanout:
    row = by_fanout[old['机器']]
    for key in ['配方', '物品', 'k', '每批件数']:
        check(f'fanout {row["机器"]} {key}', old[key], row[key])
    check(f'fanout {row["机器"]}速率', F(old['每端口速率']) / window, row['每端口计划每tick'])
    check(f'fanout {row["机器"]}平均间隔', F(str(old['批间隔tick'])), row['计划平均批间隔'])
    check(f'fanout {row["机器"]}形状分类', old['类别'], class_labels[row['计划分类']])

grinders = [r for r in machine_rows if r['机型'] == '研磨机']
shapers = [r for r in machine_rows if r['机型'] == '塑形机']
packers = [r for r in machine_rows if r['机型'] == '封装机']
fillers = [r for r in machine_rows if r['机型'] == '灌装机']
summary = {'机器数': len(machines), '机器面积': sum(r['面积'] for r in machine_rows), '计划逻辑通道数': len(channels), '机型台数': dict(counts), '分型机器存取通道': dict(degrees), '制造机存通道': sum(r['存通道数'] for r in machine_rows), '制造机取通道': sum(r['取通道数'] for r in machine_rows), '矿石来源数': len(outgoing['仓库出矿口']), '矿石来源件每tick': summarize(outgoing['仓库出矿口']), '成品入核心通道': len(incoming['协议核心']), 'S': sum(r['取通道数'] for r in machine_rows) + len(outgoing['仓库出矿口']), 'R': sum(r['存通道数'] for r in machine_rows) + len(incoming['协议核心']), '研磨至少3存口台数': sum(r['存通道数'] >= 3 for r in grinders), '塑形至少2存口台数': sum(r['存通道数'] >= 2 for r in shapers), '封装各存口数': [r['存通道数'] for r in packers], '灌装各存口数': [r['存通道数'] for r in fillers], 'K+3B+2C': len(incoming['协议核心']), '扇出分类': dict(Counter(r['计划分类'] for r in fanout_rows)), '多料机数': len(multi_rows), '物料总流量': sum(flow.values()), '成品产率': summarize(incoming['协议核心']), '说明': 'S/R仅为每条原始逻辑送料记录两端各占独立实体通道且无箱路径拆段的计划计数，未证几何或运行。'}
expected = {'机器数': 219, '机器面积': 3325, '计划逻辑通道数': 315, '制造机存通道': 309, '制造机取通道': 263, '矿石来源数': 52, '成品入核心通道': 6, 'S': 315, 'R': 315, '研磨至少3存口台数': 31, '塑形至少2存口台数': 5, '封装各存口数': [5, 5, 5], '灌装各存口数': [4, 4, 4], 'K+3B+2C': 6, '扇出分类': {'满速扇出定则型': 30, '轮询均分型': 2, '两者都不落': 1}, '多料机数': 38, '物料总流量': F('305.65')}
for key, value in expected.items():
    check('任务件数:' + key, summary[key], value)

# 用正向/反向两次遍历独立计算 SCC；不借用旧 scc.py 的算法与注释。
graph, reverse = defaultdict(set), defaultdict(set)
nodes = set()
for row in channel_rows:
    graph[row['源']].add(row['目标'])
    reverse[row['目标']].add(row['源'])
    nodes.update([row['源'], row['目标']])
visited, order = set(), []
def visit(node):
    if node in visited:
        return
    visited.add(node)
    for child in sorted(graph[node]):
        visit(child)
    order.append(node)
for node in sorted(nodes):
    visit(node)
visited = set()
components = []
for node in reversed(order):
    if node in visited:
        continue
    stack, comp = [node], []
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        comp.append(current)
        stack.extend(reverse[current] - visited)
    components.append(sorted(comp))
save('原始流图计数.json', {'节点': len(nodes), '合并平行边': sum(len(v) for v in graph.values()), 'SCC数': len(components), '非平凡SCC': sorted(c for c in components if len(c) > 1), '说明': '聚合全部仓库矿口的原始机器图；只是连通性计数，不缩小活性论证范围。'})
for name, rows in [('逐机端口与守恒.tsv', machine_rows), ('逐通道速率.tsv', channel_rows), ('多料机38台.tsv', multi_rows), ('扇出33点.tsv', fanout_rows), ('物料守恒.tsv', material_rows)]:
    table(name, rows)
save('独立复算.json', {'阶段': '尚未读取被审契约和校验报告', '摘要': summary, '机器': machine_rows, '通道': channel_rows, '多料机': multi_rows, '扇出': fanout_rows, '物料': material_rows, '对照项数': len(checks), '错误': errors})
save('独立检查明细.json', checks)
print(json.dumps({'摘要': summary, '对照项数': len(checks), '错误数': len(errors)}, default=encode, ensure_ascii=False, indent=2))
assert not errors, errors[:3]
