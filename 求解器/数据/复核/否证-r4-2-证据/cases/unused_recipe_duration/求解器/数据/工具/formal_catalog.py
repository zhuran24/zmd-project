#!/usr/bin/env python3
"""正式来源的完整转录与数值投影；只读核验，不自动批准规则改动。"""
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path

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
    assert len(rows) == 56 and all(r.get('basis') for r in rows)
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
        ('plant_trigger','矿系不入库',r'种植机恰 (\d+) 台'),
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
    assert len(task['conditions']) == 10
    return {'constraints': rules, 'task': task, 'static_checks': {'constants': constants, 'material_flow': flow}}


def verify(catalog, repo=REPO):
    current = source_snapshot(repo)
    assert catalog['sources'] == current, '正式文件字节或完整转录变化，须先审查目录'
    for key, expected in formal_projection(current).items():
        assert catalog[key] == expected, f'目录 {key} 与正式来源不一致'
    units = {u['id']: u for u in catalog['units']}
    rule_text = '\n'.join(current[0]['lines'])
    gate_text = re.search(r'^    物品准入口：(.*)$', rule_text, re.M).group(1)
    low, high, window_low, window_high = re.search(r'累计收下上限（(\d+)-(\d+)）和每 \d+ tick 的收下上限（(\d+)-(\d+)）', gate_text).groups()
    gate = units['物品准入口']['settings']
    for field, minimum, maximum in [('total_limit', low, high), ('window_limit', window_low, window_high)]:
        assert gate[field]['min'] == quantity(minimum) and gate[field]['max'] == quantity(maximum)
        assert gate[field]['requires'] == 'allowed_item' and gate[field]['optional'] is True
    assert gate['window_ticks'] == quantity(re.search(r'每 (\d+) tick', gate_text).group(1))
    assert gate['window_start'] == '收下第一件起算；走完后由下一件重新起算'
    cooldown = re.search(r'^传输：.*，(\d+) tick 冷却$', rule_text, re.M).group(1)
    assert units['协议储存箱']['transfer']['cooldown_ticks'] == quantity(cooldown)
    assert units['协议储存箱']['transfer']['judgment_scope'] == 'unit'
    assert units['协议储存箱']['transfer']['cooldown_scope'] == 'unresolved'
    for u in units.values():
        policy = u['inventory_rules']
        assert policy['same_item_across_slots'] == ('exempt' if u['id'] == '协议储存箱' else 'at_most_one_slot')
        assert policy['excluded_roles'] == ['buffer']
        if u['family'] == 'manufacturing' or u['id'] in ['协议储存箱', '桥接器']:
            assert all(u['ports'][f]['category'] == '算术推论' for f in ['input_count','output_count'])
    return current


if __name__ == '__main__':
    verify(json.loads((ROOT/'数据/正式静态目录.json').read_text()))
    print('三份正式来源的指纹、完整行文本、分节、据、任务与结构化阈值均一致。')
