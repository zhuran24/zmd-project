#!/usr/bin/env python3
"""正式来源的完整转录与数值投影；只读核验，不自动批准规则改动。"""
import hashlib
import json
import re
import argparse
import sys
from fractions import Fraction
from pathlib import Path
from formal_units import unit_projection

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
SOURCE_NAMES = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']


def quantity(value, category='条文直引'):
    return {'value': str(Fraction(value)), 'category': category}


def source_snapshot(repo=REPO):
    return [{'path': name, 'sha256': hashlib.sha256((repo/name).read_bytes()).hexdigest(),
             'lines': (repo/name).read_text().splitlines()} for name in SOURCE_NAMES]


def parse_constraints(text):
    section, rows = None, []
    for number, line in enumerate(text.splitlines(), 1):
        if line.endswith('：') and not line.startswith(' '):
            section = line[:-1]
        elif line.startswith('    据：'):
            assert rows and 'basis' not in rows[-1]
            rows[-1]['basis'] = line.strip()[2:]
            rows[-1]['basis_line'] = str(number)
        elif line and not line.startswith(' ') and '：' in line:
            name, body = line.split('：', 1)
            rows.append({'name': name, 'text': body, 'section': section,
                         'source_line': str(number),
                         'obligation': '目标须对其每种取值都达成' if section.startswith('不得依赖的量') else None})
    assert len(rows) == 77 and all(r.get('basis') for r in rows)
    return rows


def formal_projection(snapshot):
    texts = {s['path']: '\n'.join(s['lines']) for s in snapshot}
    rules = parse_constraints(texts['求解约束.txt'])
    by_name = {r['name']: r['text'] for r in rules}
    constants = {}

    def extract(key, name, pattern, group=1):
        match = re.search(pattern, by_name[name])
        assert match, (key, name, pattern)
        constants[key] = {'quantity': quantity(match.group(group)), 'basis': '求解约束·'+name,
                          'source_excerpt': match.group(0)}

    specs = [
        ('port_rate','端口速率',r'至多通过 (\d+) 个'),
        ('source_per_side','出库上限',r'每边至多 (\d+) 个'),
        ('ore_total','矿石需求',r'合计 (\d+) 个'),
        ('battery_iron','单位矿耗',r'耗 (\d+) 蓝铁矿'),
        ('battery_ore','单位矿耗',r'、(\d+) 源矿'),
        ('capsule_iron','单位矿耗',r'胶囊耗 (\d+) 蓝铁矿'),
        ('grinder_trigger','研磨进料',r'研磨机恰 (\d+) 台'),
        ('grinder_count','研磨进料',r'时至少 (\d+) 台'),
        ('grinder_inputs','研磨进料',r'各有 至少 (\d+) 条'),
        ('seed_trigger','研磨进料',r'采种机恰 (\d+) 台'),
        ('seed_outputs','研磨进料',r'每台至少 (\d+) 条取货'),
        ('shaper_trigger','研磨进料',r'塑形机恰 (\d+) 台'),
        ('shaper_count','研磨进料',r'塑形机恰 \d+ 台时至少 (\d+) 台'),
        ('shaper_inputs','研磨进料',r'塑形机.*各有 至少 (\d+) 条'),
        ('pack_trigger','封装进料',r'封装机恰 (\d+) 台'),
        ('pack_inputs','封装进料',r'每台至少 (\d+) 条'),
        ('fill_trigger','封装进料',r'灌装机恰 (\d+) 台'),
        ('fill_count','封装进料',r'灌装机恰 \d+ 台时至少 (\d+) 台'),
        ('fill_inputs','封装进料',r'灌装机.*各有 至少 (\d+) 条'),
        ('fill_other_inputs','封装进料',r'第 \d+ 台恰 (\d+) 条'),
        ('product_sources','成品汇入',r'至少有 (\d+) 个来源'),
        ('product_inputs','通道下限',r'成品入库至少 (\d+) 条'),
        ('transport_s','运输端口收支',r'S ≥(\d+)'),
        ('transport_r','运输端口收支',r'R ≥(\d+)'),
        ('box_base','箱体接口',r'S\+R ≥(\d+)\+η'),
        ('box_h','箱体接口',r'H=max\((\d+),B1\)'),
        ('box_eta_h_offset','箱体接口',r'max\(H−(\d+),'),
        ('box_eta_m_base','箱体接口',r', (\d+)−2M'),
        ('box_eta_h_factor','箱体接口',r', (\d+)H−9−2D'),
        ('box_eta_h_subtract','箱体接口',r', 2H−(\d+)−2D'),
        ('plant_area','回路转弯',r'合计至少 (\d+) 格'),
        ('flow_total','物料流量',r'合计 ([\d.]+) 件'),
    ]
    for args in specs:
        extract(*args)
    # 去掉分用途括号，主项每物品只取一次；十进制直接转有理数。
    flow_body = re.sub(r'（[^）]*）', '', by_name['物料流量']).split('，合计')[0].removeprefix('循环态中每 tick 至少需')
    flow = {item: quantity(value) for item, value in re.findall(r'([^、 ]+) ([\d.]+)', flow_body)}
    assert len(flow) == 19
    task_lines = texts['求解任务.txt'].splitlines()
    goal = task_lines[1]
    rates = re.search(r'（([\d.]+) 个/tick 与 ([\d.]+) 个/tick）', goal).groups()
    task = {'goal': goal, 'conditions': [], 'targets': dict(zip(['高容谷地电池','精选荞愈胶囊'], map(quantity, rates))),
            'basis': '求解任务·目标；求解约束·周期倍数'}
    for line in task_lines:
        if '：' in line:
            name, text = line.split('：', 1)
            task['conditions'].append({'name':name, 'text':text, 'basis':'求解任务·'+name})
    assert len(task['conditions']) == 11
    return {'constraints': rules, 'task': task, 'static_checks': {'constants': constants, 'material_flow': flow}}


def recipe_projection(rule_text):
    # id 是既有接口编码；配方归属、物品、批量和耗时全部从正式原文读取。
    recipe_ids = ['粉碎-源矿','粉碎-蓝铁块','粉碎-荞花','粉碎-砂叶','精炼-蓝铁矿',
                  '精炼-致密蓝铁','精炼-蓝铁粉末','研磨-致密蓝铁','研磨-致密源石',
                  '研磨-细磨荞花','塑形-钢质瓶','配件-钢制零件','种植-荞花','种植-砂叶',
                  '采种-荞花','采种-砂叶','封装-电池','灌装-胶囊']
    recipes, kind = [], None

    def terms(text):
        result = {}
        for term in text.split(' ＋ '):
            value, item = term.split(' ', 1)
            if item in result:
                raise AssertionError(f'正式配方重复物品：{item}')
            result[item] = quantity(value)
        return result

    for line in rule_text.split('配方\n\n', 1)[1].splitlines():
        if not line.strip():
            continue
        if '→' not in line:
            kind = line.strip()
            continue
        left, right = line.split(' → ')
        output, duration = right.split('，')
        if not re.fullmatch(r'\d+ tick', duration) or len(recipes) >= len(recipe_ids):
            raise AssertionError('正式配方格式或数量变化，须审查编码')
        recipes.append({'id': recipe_ids[len(recipes)], 'kind': kind, 'inputs': terms(left),
                        'outputs': terms(output), 'duration': quantity(duration.split()[0])})
    if len(recipes) != len(recipe_ids):
        raise AssertionError('正式配方缺项，须审查编码')
    return recipes


def compare(actual, expected, path):
    """逐字段严格比较，包含类别、键集合、列表长度、null 与类型；报告首个差异。"""
    if type(actual) is not type(expected):
        raise AssertionError(f'{path} 类型不一致：{actual!r} / {expected!r}')
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise AssertionError(f'{path} 字段不一致：缺 {expected.keys()-actual.keys()}，多 {actual.keys()-expected.keys()}')
        for key in expected:
            compare(actual[key], expected[key], f'{path}.{key}')
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f'{path} 长度不一致：{len(actual)} / {len(expected)}')
        for index, (value, reference) in enumerate(zip(actual, expected)):
            compare(value, reference, f'{path}[{index}]')
    elif actual != expected:
        raise AssertionError(f'{path} 与正式来源投影不一致：{actual!r} / {expected!r}')


def indexed(rows, path):
    result = {}
    for row in rows:
        key = row['id']
        if key in result:
            raise AssertionError(f'{path} 重复 id：{key}')
        result[key] = row
    return result


def verify(catalog, repo=REPO):
    current = source_snapshot(repo)
    compare(catalog['sources'], current, 'sources')
    projection = formal_projection(current)
    for key, expected in projection.items():
        compare(catalog[key], expected, key)
    rule_text = '\n'.join(current[0]['lines'])
    compare(indexed(catalog['recipes'], 'recipes'), indexed(recipe_projection(rule_text), 'recipes'), 'recipes')
    compare(indexed(catalog['units'], 'units'), unit_projection(rule_text, projection['constraints'], quantity), 'units')
    compare(catalog['schema'], 'static-catalog-v2', 'schema')
    compare(catalog['source_root'], '../..', 'source_root')
    return current


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', default=str(ROOT/'数据/正式静态目录.json'), help='待核目录路径；- 表示标准输入')
    args = parser.parse_args()
    try:
        document = sys.stdin.read() if args.catalog == '-' else Path(args.catalog).read_text()
        verify(json.loads(document))
    except (AssertionError, KeyError, ValueError, TypeError) as error:
        print(f'目录回源失败：{error}', file=sys.stderr)
        sys.exit(1)
    print('三份正式来源指纹与全文、77 条约束上下文、任务与阈值、18 条配方、18 类单位全部字段及数字类别一致。')
