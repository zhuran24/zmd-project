#!/usr/bin/env python3
"""第五轮字段覆盖独立核对；只在本复核证据目录写入。"""
import ast
import contextlib
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

OUT = Path(__file__).resolve().parent
SOLVER = OUT.parents[2]
REPO = SOLVER.parent
DATA = SOLVER / '数据'
SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    catalog = read(DATA / '正式静态目录.json')
    contract = read(DATA / '候选B/contract.json')
    units = {u['id']: u for u in catalog['units']}
    recipes = {r['id']: r for r in catalog['recipes']}
    machines = contract['machines']
    feeds = contract['logical_feeds']
    rules = (REPO / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
    results = {}

    # 独立从正式配方段读机型及等式；不调用生产回源投影。
    expected = []
    kind = None
    for line in rules[79:]:
        if not line.strip():
            continue
        if '→' not in line:
            kind = line.strip()
            continue
        left, right, duration = re.fullmatch(r'(.*?) → (.*?)，(\d+) tick', line).groups()
        terms = lambda text: {item: int(value) for value, item in re.findall(r'(\d+) ([^＋]+?)(?: ＋ |$)', text)}
        expected.append((kind, terms(left), terms(right), int(duration)))
    actual = [(r['kind'], {k: int(v['value']) for k, v in r['inputs'].items()},
               {k: int(v['value']) for k, v in r['outputs'].items()}, int(r['duration']['value']))
              for r in recipes.values()]
    assert sorted(expected, key=str) == sorted(actual, key=str)
    assert len(actual) == len(recipes) == 18
    results['recipe_equations'] = actual

    # 此表由规则 L41、L44、L50、L54、L59–76 单独列出。
    sizes = {**{n: (3, 3, 3, 3) for n in ['粉碎机', '精炼炉', '配件机', '塑形机']},
             **{n: (5, 5, 5, 5) for n in ['采种机', '种植机']},
             **{n: (6, 4, 6, 6) for n in ['研磨机', '封装机', '灌装机']},
             '协议核心': (9, 9, 14, 6), '传送带': (1, 1, 1, 1),
             '桥接器': (1, 1, 2, 2), '物品准入口': (1, 1, 1, 1),
             '分流器': (1, 1, 1, 3), '汇流器': (1, 1, 3, 1),
             '协议储存箱': (3, 3, 3, 3), '仓库取货口': (3, 1, 0, 1), '供电桩': (2, 2, 0, 0)}
    assert set(units) == set(sizes)
    for name, (width, height, inputs, outputs) in sizes.items():
        u = units[name]
        assert (int(u['dimensions']['width']['value']), int(u['dimensions']['height']['value']),
                int(u['ports']['input_count']['value']), int(u['ports']['output_count']['value'])) == (width, height, inputs, outputs)
        assert u['area'] == {'value': str(width * height), 'category': '算术推论'}
        assert u['power_required'] == (u['family'] == 'manufacturing' or name == '协议储存箱')
        for layout in u['ports']['layouts']:
            endpoints = [(e['side'], int(p['value']), e['role'], e['axis']) for e in layout for p in e['positions']]
            assert len({(s, p) for s, p, _, _ in endpoints}) == inputs + outputs
            assert Counter(role for _, _, role, _ in endpoints) == Counter({'input': inputs, 'output': outputs})
            assert all(0 <= p < (width if s in ['north', 'south'] else height) for s, p, _, _ in endpoints)
    results['unit_dimensions_and_ports'] = sizes

    # 用独立分组核角色、空值语义和设定域。
    for u in units.values():
        if u['family'] == 'manufacturing':
            slots = {s['role']: s for s in u['inventory']}
            assert slots['input']['count']['value'] == ('2' if u['dimensions']['width']['value'] == '6' else '1')
            assert slots['output']['count']['value'] == '1'
            assert all(slots[r]['capacity']['value'] == '50' for r in ['input', 'output'])
            assert slots['buffer']['capacity'] is None and slots['buffer']['capacity_status'] == 'unlimited'
            assert slots['buffer']['item_policy'] == 'unlimited_kinds'
        assert u['inventory_rules']['same_item_across_slots'] == ('exempt' if u['id'] == '协议储存箱' else 'at_most_one_slot')
    assert units['协议核心']['inventory'][0]['count'] is None
    assert units['协议核心']['inventory'][0]['capacity']['value'] == '80000'
    assert len(units['桥接器']['inventory']) == 2
    assert all(s['capacity'] is None and s['capacity_status'] == 'unresolved' for s in units['桥接器']['inventory'])
    assert units['桥接器']['port_assignment'] == 'first_connected_peer'
    gate = units['物品准入口']['settings']
    assert [gate['total_limit'][k]['value'] for k in ['min', 'max']] == ['1', '5000']
    assert [gate['window_limit'][k]['value'] for k in ['min', 'max']] == ['1', '5']
    assert gate['window_ticks']['value'] == '5'
    assert units['协议储存箱']['inventory'][0]['count']['value'] == '6'
    assert units['协议储存箱']['inventory'][0]['capacity']['value'] == '50'
    assert units['协议储存箱']['transfer']['cooldown_ticks']['value'] == '5'
    assert units['协议储存箱']['transfer']['judgment_scope'] == 'unit'
    assert units['协议储存箱']['transfer']['cooldown_scope'] == 'unresolved'
    assert all(units['供电桩']['coverage'][k]['value'] == '12' for k in ['width', 'height'])
    results['inventory_and_settings'] = '通过'

    # 按字段路径遍历，拒绝未分类的物理数值；布尔值不是数字。
    categories = Counter()
    def walk(value, path):
        if isinstance(value, dict):
            if 'value' in value and 'category' in value:
                assert set(value) == {'value', 'category'}, path
                F(value['value'])
                assert value['category'] in ['条文直引', '算术推论', '候选', '启发式', '实测'], path
                categories[value['category']] += 1
            else:
                for k, v in value.items(): walk(v, path + '/' + k)
        elif isinstance(value, list):
            for i, v in enumerate(value): walk(v, path + '/' + str(i))
        else:
            assert not isinstance(value, (int, float)) or isinstance(value, bool), path
    walk(contract, 'contract')
    walk(catalog['units'], 'units')
    walk(catalog['recipes'], 'recipes')
    results['quantity_categories'] = dict(categories)

    def ports(mid, side):
        return {e[side + '_port'] for e in feeds if e[side] == mid}
    def degrees(kind):
        return [len(ports(m['id'], 'target')) for m in machines if m['kind'] == kind]
    counts = Counter(m['kind'] for m in machines)
    metrics = {'machines': len(machines), 'area': str(sum(F(m['area']['value']) for m in machines)),
               'feeds': len(feeds), 'S': len({(e['source'], e['source_port']) for e in feeds}),
               'R': len({(e['target'], e['target_port']) for e in feeds}), 'counts': dict(counts),
               'grinding_degrees': dict(Counter(degrees('研磨机'))), 'shaping_degrees': dict(Counter(degrees('塑形机'))),
               'packaging_degrees': degrees('封装机'), 'filling_degrees': degrees('灌装机'),
               'K': len(ports(contract['core']['id'], 'target')), 'sources': len(contract['sources']),
               'ore_items': dict(Counter(s['item'] for s in contract['sources'])),
               'fanout_shapes': dict(Counter(f['planned_shape'] for f in contract['fanouts'])),
               'arrival_obligations': sum(m['multi_material'] is not None for m in machines),
               'full_speed_records': sum(e['planned_full_speed'] for e in feeds)}
    assert [metrics[k] for k in ['machines','area','feeds','S','R','K','sources','arrival_obligations','full_speed_records']] == [219,'3325',315,315,315,6,52,43,300]
    assert metrics['fanout_shapes'] == {'满速扇出定则型':30,'轮询均分型':2,'两者都不落':1}
    for m in machines:
        assert set(m) == {'id','kind','recipes','input_ports','output_ports','area','orientation','multi_material'}
        assert m['orientation'] is None
        required = len(m['recipes']) > 1 or len(ports(m['id'],'target')) > 1 or any(len(recipes[p['recipe']]['inputs']) > 1 for p in m['recipes'])
        assert (m['multi_material'] is not None) == required
        if required: assert m['multi_material'] == dict.fromkeys(['arrival_composition_per_tick','synchronization','same_source'],'待验')
        for p in m['recipes']: assert F(p['planned_batch_rate']['value']) * F(p['planned_mean_batch_interval']['value']) == 1
    for e, row in zip(feeds, csv.DictReader((SOURCE/'channels.csv').open())):
        assert e['id'] == 'LF' + row['通道id'][1:]
        assert e['item'] == row['物品'] and F(e['planned_rate']['value']) == F(row['件每20tick']) / 20
        assert e['proven_actual_rate'] is None
        assert e['planned_full_speed'] == (F(e['planned_rate']['value']) == 1)
        assert e['via'] == dict.fromkeys(['bridge','splitter','merger','gate'])
    assert len({s['id'] for s in contract['sources']}) == 52
    assert all(s['identity'] == {'status':'待求','kind':None,'side':None,'index':None} for s in contract['sources'])
    assert all(f['certification'] == '待验' for f in contract['fanouts'])
    assert contract['rate_window'] == {'value':'20','category':'候选'}
    results['candidate_metrics'] = metrics

    # 逐条核来源全文、正式约束上下文及覆盖表行；不以行数代替条款内容。
    for source in catalog['sources']:
        assert source['sha256'] == digest(REPO/source['path'])
        assert source['lines'] == (REPO/source['path']).read_text().splitlines()
    coverage = (DATA/'规则覆盖表.md').read_text().split('## ')
    for i, source in enumerate(catalog['sources'][:2],1):
        rows=[line.split('|')[1:-1] for line in coverage[i].splitlines() if re.match(r'^\| \d+ \|',line)]
        assert len(rows)==len(source['lines'])
        assert all(int(row[0])==n and row[1].strip()==(text.strip() or '（空行）') and row[2].strip() for n,(row,text) in enumerate(zip(rows,source['lines']),1))
    constraint_lines=(REPO/'求解约束.txt').read_text().splitlines()
    for rule in catalog['constraints']:
        assert constraint_lines[int(rule['source_line'])-1] == rule['name']+'：'+rule['text']
        assert constraint_lines[int(rule['basis_line'])-1] == '    据：'+rule['basis']
    assert len(catalog['constraints'])==56
    assert all(r['obligation']=='目标须对其每种取值都达成' for r in catalog['constraints'][:4])
    results['normative_coverage'] = {'rule_lines':114,'task_lines':15,'constraints':56}

    # 输出重定向只改变写入路径；转换算法逐字保留。
    code=(DATA/'工具/convert_candidate_b.py').read_text()
    tree=ast.parse(code)
    relocated=OUT/'conversion'
    relocated.mkdir(exist_ok=True)
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ROOT' for t in node.targets):
            node.value=ast.Call(func=ast.Name(id='Path',ctx=ast.Load()),args=[ast.Constant(str(SOLVER))],keywords=[])
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='OUT' for t in node.targets):
            node.value=ast.Call(func=ast.Name(id='Path',ctx=ast.Load()),args=[ast.Constant(str(relocated))],keywords=[])
    sys.path.insert(0,str(DATA/'工具'))
    with contextlib.redirect_stdout(io.StringIO()) as log:
        exec(compile(ast.fix_missing_locations(tree),str(DATA/'工具/convert_candidate_b.py'),'exec'),{'__file__':str(DATA/'工具/convert_candidate_b.py'),'__name__':'__main__'})
    (OUT/'转换.log').write_text(log.getvalue())
    assert all((relocated/n).read_bytes()==(DATA/'候选B'/n).read_bytes() for n in ['contract.json','来源清单.json'])
    results['conversion_byte_equal']=['contract.json','来源清单.json']
    binary=OUT/'isolated/求解器/target/debug/topology'
    cli=subprocess.run([str(binary),str(DATA/'候选B/contract.json')],capture_output=True)
    (OUT/'校验报告.md').write_bytes(cli.stdout)
    assert cli.returncode==0 and cli.stdout==(DATA/'候选B/校验报告.md').read_bytes()
    results['cli_report_byte_equal']=True
    results['status']='通过'
    save('独立字段核对.json',results)
    print(json.dumps({'status':'通过','metrics':metrics,'output':str(OUT/'独立字段核对.json')},ensure_ascii=False))


if __name__ == '__main__':
    main()
