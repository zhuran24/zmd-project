#!/usr/bin/env python3
"""第四轮独立数值复算：只读正式源及候选原始表，不导入被审代码。"""
import ast
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
RAW = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
RULE = ROOT / '《明日方舟：终末地》游戏规则.txt'
TASK = ROOT / '求解任务.txt'
LIMIT = ROOT / '求解约束.txt'

def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))

def save_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                     default=lambda value: str(value)) + '\n')

def save_tsv(name, rows):
    with (OUT / name).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)

def material(text):
    return {name: int(count) for count, name in
            re.findall(r'(\d+)\s+([^＋]+?)(?=\s*＋|$)', text.strip())}

def evaluate(node):
    # 只解释设计声明里的常量、容器、加乘，不执行原脚本的写文件语句。
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [evaluate(value) for value in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Dict):
        return {evaluate(key): evaluate(value) for key, value in zip(node.keys, node.values)}
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
        left, right = evaluate(node.left), evaluate(node.right)
        return left + right if isinstance(node.op, ast.Add) else left * right
    raise ValueError(ast.dump(node))

def main():
    lines = RULE.read_text().splitlines()
    recipes = {}
    machine_type = None
    for line_number, line in enumerate(lines, 1):
        if line_number < 80:
            continue
        if line.strip().endswith(('机', '炉')):
            machine_type = line.strip()
        match = re.fullmatch(r'(.+) → (.+)，(\d+) tick', line.strip())
        if match:
            recipes[line_number] = dict(machine_type=machine_type,
                inputs=material(match[1]), outputs=material(match[2]),
                ticks=int(match[3]), rule_line=line_number)
    # 原始表的配方简称只作为索引；所有用量和制造时长从正式规则解析。
    aliases = dict(zip(
        ['粉碎-源矿','粉碎-蓝铁块','粉碎-荞花','粉碎-砂叶','精炼-蓝铁矿',
         '精炼-致密蓝铁','研磨-致密蓝铁','研磨-致密源石','研磨-细磨荞花',
         '塑形-钢质瓶','配件-钢制零件','种植-荞花','种植-砂叶',
         '采种-荞花','采种-砂叶','封装-电池','灌装-胶囊'],
        [81,82,83,84,87,88,92,93,94,97,100,103,104,107,108,111,114]))
    sizes = {}
    for number, types in [(44, ['粉碎机','精炼炉','配件机','塑形机']),
                          (50, ['采种机','种植机']), (54, ['研磨机','封装机','灌装机'])]:
        width, height = map(int, re.search(r'大小(\d+)x(\d+)', lines[number-1]).groups())
        for unit in types:
            sizes[unit] = (width, height, max(width, height))
    machines = read_csv(RAW / 'machines.csv')
    edges = read_csv(RAW / 'channels.csv')
    raw_fanout = json.loads((RAW / 'fanout.json').read_text(), parse_float=str)
    declared = {}
    for node in ast.parse((RAW / 'design.py').read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ['P','RECIPE','DESIGN','ORE']:
                    declared[target.id] = evaluate(node.value)
    window = declared['P']
    errors = []
    def check(condition, description):
        if not condition:
            errors.append(description)
    check(len(recipes) == 18, '正式配方解析不是18条')
    for alias, line_number in aliases.items():
        original = declared['RECIPE'][alias]
        official = recipes[line_number]
        check((original[1], original[2], original[3]) ==
              (official['inputs'], official['outputs'], official['ticks']),
              f'design.py配方与正式源不一致：{alias}')
    design_rows = [(alias, batches, ports) for alias, specs in declared['DESIGN']
                   for batches, ports in specs]
    check(len(design_rows) == len(machines), 'DESIGN与机器表条数不一致')
    by_id = {row['机器id']: row for row in machines}
    check(len(by_id) == len(machines), '机器id重复')
    check(len({edge['通道id'] for edge in edges}) == len(edges), '通道id重复')
    incoming, outgoing = defaultdict(list), defaultdict(list)
    edge_table = []
    ore = Counter()
    delivered = Counter()
    for edge in edges:
        source, target, item = edge['源机器id'], edge['目标机器id'], edge['物品']
        rate = F(edge['件每20tick']) / window
        check(0 < rate <= 1, f'{edge["通道id"]}计划端口速率超界')
        check(edge['是否满速'] == ('是' if rate == 1 else '否'), f'{edge["通道id"]}满速标记不符')
        outgoing[source].append((item, rate, target, edge['通道id']))
        incoming[target].append((item, rate, source, edge['通道id']))
        if source == '仓库出矿口':
            ore[item] += rate
            check(item in ['源矿','蓝铁矿'], f'{edge["通道id"]}取非矿')
        else:
            check(source in by_id, f'{edge["通道id"]}源机器不存在')
            check(edge['源配方'] == by_id[source]['配方'], f'{edge["通道id"]}源配方错误')
            check(edge['源机型'] == by_id[source]['机型'], f'{edge["通道id"]}源尺寸错误')
        if target == '协议核心':
            delivered[item] += rate
        else:
            check(target in by_id, f'{edge["通道id"]}目标机器不存在')
            check(edge['目标配方'] == by_id[target]['配方'], f'{edge["通道id"]}目标配方错误')
            check(edge['目标机型'] == by_id[target]['机型'], f'{edge["通道id"]}目标尺寸错误')
        edge_table.append({'原始通道': edge['通道id'], '源': source, '目标': target, '物品': item, '计划件每tick': str(rate), '源配方': edge['源配方'], '目标配方': edge['目标配方']})
    def totals(entries):
        result = Counter()
        for item, rate, *_ in entries:
            result[item] += rate
        return result
    def compact(entries):
        return '; '.join(f'{identity}:{item}={rate}({peer})' for item,rate,peer,identity in entries)
    def parse_ports(text):
        return Counter((item, F(rate)/window) for item,rate in
                       (part.split(':') for part in text.split(';')))
    production, consumption = Counter(), Counter()
    type_counts, type_area, type_inputs, type_outputs = Counter(), Counter(), Counter(), Counter()
    recipe_batches = Counter()
    machine_table, multi_table, fanout_table = [], [], []
    per_machine = {}
    for index, row in enumerate(machines):
        identity, alias = row['机器id'], row['配方']
        recipe = recipes[aliases[alias]]
        unit = recipe['machine_type']
        batch_rate = F(row['批次每20tick']) / window
        input_expected = {item: count * batch_rate for item, count in recipe['inputs'].items()}
        output_expected = {item: count * batch_rate for item, count in recipe['outputs'].items()}
        actual_in, actual_out = totals(incoming[identity]), totals(outgoing[identity])
        input_count, output_count = len(incoming[identity]), len(outgoing[identity])
        width, height, port_capacity = sizes[unit]
        check(row['机型'] == f'{width}x{height}', f'{identity}尺寸与规则不符')
        check(batch_rate * recipe['ticks'] <= 1, f'{identity}制造负载超界')
        check(dict(actual_in) == input_expected, f'{identity}进料不守恒')
        check(dict(actual_out) == output_expected, f'{identity}产出不守恒')
        check(input_count <= port_capacity and output_count <= port_capacity, f'{identity}端口数超界')
        check((input_count, output_count) == (int(row['存货通道数']), int(row['取货通道数'])), f'{identity}原表端口件数不符')
        check(parse_ports(row['存货通道速率']) == Counter((i,r) for i,r,*_ in incoming[identity]), f'{identity}原表进料速率列表不符')
        check(parse_ports(row['取货通道速率']) == Counter((i,r) for i,r,*_ in outgoing[identity]), f'{identity}原表出料速率列表不符')
        check(design_rows[index] == (alias,int(row['批次每20tick']),output_count), f'{identity}DESIGN声明不符')
        type_counts[unit] += 1
        type_area[unit] += width * height
        type_inputs[unit] += input_count
        type_outputs[unit] += output_count
        recipe_batches[alias] += batch_rate
        production.update(output_expected)
        consumption.update(input_expected)
        per_machine[identity] = dict(machine_type=unit, recipe_alias=alias, rule_line=recipe['rule_line'],
            batch_rate=batch_rate, input_rates=dict(actual_in), output_rates=dict(actual_out),
            input_count=input_count, output_count=output_count, port_capacity=port_capacity,
            input_edges=incoming[identity], output_edges=outgoing[identity],
            normalized_input={item: actual_in[item]/count for item,count in recipe['inputs'].items()})
        machine_table.append({'机器': identity, '机型': unit, '配方': alias, '计划批每tick': str(batch_rate), '计划负载': str(batch_rate * recipe['ticks']), '端口上限': port_capacity, '存货端口数': input_count, '取货端口数': output_count, '进料各端口': compact(incoming[identity]), '出料各端口': compact(outgoing[identity]), '逐机逐物品守恒': '通过' if dict(actual_in) == input_expected and dict(actual_out) == output_expected else '失败'})
        if len(recipe['inputs']) > 1:
            multi_table.append({'机器': identity, '配方': alias, '计划批每tick': str(batch_rate), '配方用量': json.dumps(recipe['inputs'], ensure_ascii=False), '计划进料件每tick': json.dumps({key: str(value) for key, value in actual_in.items()}, ensure_ascii=False), '归一化批每tick': json.dumps({item: str(actual_in[item] / count) for item, count in recipe['inputs'].items()}, ensure_ascii=False), '进料各端口': compact(incoming[identity]), '每tick实际到达构成': '待验', '多料同步': '待验', '同源标记': '待验'})
        if output_count > 1:
            rates = [rate for _,rate,*_ in outgoing[identity]]
            quantity = sum(recipe['outputs'].values())
            interval = 1 / batch_rate
            category = 'full_speed_fanout' if all(rate==1 for rate in rates) else (
                'round_robin_equal' if interval==1 and 2*quantity<=output_count else 'neither')
            raw_row = next(entry for entry in raw_fanout if entry['机器']==identity)
            old_category = {'full_speed_fanout':'A 满速','round_robin_equal':'B 原文前提内','neither':'C 需推广版'}[category]
            check(raw_row['类别'] == old_category and row['扇出类别'] == old_category, f'{identity}扇出类别不一致')
            check(raw_row['k'] == output_count and F(str(raw_row['批间隔tick'])) == interval
                  and raw_row['每批件数'] == quantity and all(F(raw_row['每端口速率'])/window==rate for rate in rates), f'{identity}扇出数值不一致')
            fanout_table.append({'机器': identity, '配方': alias, '取货端口数': output_count, '每批件数': quantity, '计划平均批间隔': str(interval), '计划各端口速率': ','.join(map(str, rates)), '计划分类': category, '认证状态': '待验'})
    items = sorted(set(production) | set(consumption) | set(ore) | set(delivered))
    material_table = []
    for item in items:
        residual = production[item] + ore[item] - consumption[item] - delivered[item]
        check(residual == 0, f'{item}全局守恒不成立')
        material_table.append({'物品': item, '制造产出': str(production[item]), '仓库供给': str(ore[item]), '制造消耗': str(consumption[item]), '成品入库': str(delivered[item]), '残差': str(residual)})
    flow_line = LIMIT.read_text().splitlines()[43].split('至少需',1)[1]
    flow_matches = re.findall(r'([^、，：（） ]+) (\d+(?:\.\d+)?)', flow_line)
    formal_flow = {name:F(value) for name,value in flow_matches if name in items}
    check(len(formal_flow)==19, '物料流量未解析出19种物品')
    for item,value in formal_flow.items():
        check(production[item]+ore[item] == value, f'{item}与正式物料流量不符')
    check(sum(formal_flow.values()) == F('305.65'), '正式物料流量合计不符')
    check(dict(ore)==declared['ORE'], '原设计矿流声明不符')
    check(delivered['高容谷地电池']==F(3,5) and delivered['精选荞愈胶囊']==F(11,20), '成品目标不符')
    plant_cycles = {}
    for plant in ['荞花','砂叶']:
        plant_cycles[plant] = dict(seed_batches=recipe_batches['采种-'+plant],
            plant_batches=recipe_batches['种植-'+plant], crush_batches=recipe_batches['粉碎-'+plant], warehouse_flow=0)
        check(recipe_batches['采种-'+plant] == recipe_batches['粉碎-'+plant], f'{plant}回路守恒失败')
        check(recipe_batches['种植-'+plant] == 2*recipe_batches['采种-'+plant], f'{plant}种子自给失败')
    # 在候选使用的配方集合中，只用正式配方与目标另解一遍十九元有理线性方程。
    # 蓝铁粉末再精炼的正式配方不在该候选中；此处不把候选子集当规则全集。
    goal_rates = re.search(r'（([\d.]+) 个/tick 与 ([\d.]+) 个/tick）', TASK.read_text()).groups()
    targets = dict(zip(['高容谷地电池','精选荞愈胶囊'],map(F,goal_rates)))
    variables = list(aliases) + ['外部源矿','外部蓝铁矿']
    matrix = []
    for item in items:
        coefficients = [F(recipes[aliases[alias]]['outputs'].get(item,0) - recipes[aliases[alias]]['inputs'].get(item,0)) for alias in aliases]
        matrix.append(coefficients + [F(item=='源矿'),F(item=='蓝铁矿'),targets.get(item,F(0))])
    for column in range(len(variables)):
        pivot = next(row for row in range(column,len(matrix)) if matrix[row][column])
        matrix[column],matrix[pivot] = matrix[pivot],matrix[column]
        divisor = matrix[column][column]
        matrix[column] = [value/divisor for value in matrix[column]]
        for row in range(len(matrix)):
            if row != column:
                coefficient = matrix[row][column]
                matrix[row] = [value-coefficient*other for value,other in zip(matrix[row],matrix[column])]
    solved = {name:matrix[index][-1] for index,name in enumerate(variables)}
    for alias in aliases:
        check(solved[alias]==recipe_batches[alias],f'目标反推批次率不符：{alias}')
    check(solved['外部源矿']==ore['源矿'] and solved['外部蓝铁矿']==ore['蓝铁矿'],'目标反推矿耗不符')
    save_json('目标反推.json',dict(targets=targets,recipe_support=list(aliases),rates=solved))
    # 单件矿耗沿正式配方链反向展开，所有系数均来自本次解析的规则正文。
    def per_output(line_number,input_item):
        recipe=recipes[line_number]
        return F(recipe['inputs'][input_item],sum(recipe['outputs'].values()))
    iron_per_steel=per_output(88,'致密蓝铁粉末')*per_output(92,'蓝铁粉末')*per_output(82,'蓝铁块')*per_output(87,'蓝铁矿')
    battery_ore = per_output(111,'钢制零件') * per_output(100,'钢块') * iron_per_steel
    battery_source = per_output(111,'致密源石粉末') * per_output(93,'源石粉末') * per_output(81,'源矿')
    capsule_ore = per_output(114,'钢质瓶') * per_output(97,'钢块') * iron_per_steel
    check((battery_ore,battery_source,capsule_ore)==(20,30,40), '单位矿耗异常')
    summary = dict(machine_count=len(machines),machine_area=sum(type_area.values()),
        logical_feeds=len(edges),manufacturing_source_ports=sum(type_outputs.values()),
        manufacturing_target_ports=sum(type_inputs.values()),ore_ports=len(outgoing['仓库出矿口']),
        core_input_ports=len(incoming['协议核心']),S=sum(type_outputs.values())+len(outgoing['仓库出矿口']),
        R=sum(type_inputs.values())+len(incoming['协议核心']),type_counts=type_counts,type_area=type_area,
        type_inputs=type_inputs,type_outputs=type_outputs,
        grinding_at_least_three=sum(value['input_count']>=3 for value in per_machine.values() if value['machine_type']=='研磨机'),
        shaping_at_least_two=sum(value['input_count']>=2 for value in per_machine.values() if value['machine_type']=='塑形机'),
        packaging_inputs=[value['input_count'] for value in per_machine.values() if value['machine_type']=='封装机'],
        filling_inputs=[value['input_count'] for value in per_machine.values() if value['machine_type']=='灌装机'],
        multi_input_machines=len(multi_table),fanout_counts=dict(Counter(row['计划分类'] for row in fanout_table)),
        material_flow_total=sum(production.values())+sum(ore.values()),ore_rates=ore,product_rates=delivered,
        plant_cycles=plant_cycles,unit_ore=dict(battery_blue=battery_ore,battery_source=battery_source,capsule_blue=capsule_ore),
        source_convergence=dict(K=len(incoming['协议核心']),B=0,C=0,weighted=len(incoming['协议核心'])),
        errors=errors)
    files = [RULE,TASK,LIMIT]+[RAW/name for name in ['design.py','machines.csv','channels.csv','fanout.json','scc.py']]
    save_json('独立输入指纹.json', {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in files})
    save_json('正式配方独立解析.json',recipes)
    save_json('独立复算.json',dict(summary=summary,per_machine=per_machine,recipe_batches=recipe_batches))
    save_tsv('逐机端口速率.tsv',machine_table)
    save_tsv('逐通道速率.tsv',edge_table)
    save_tsv('多料机38台.tsv',multi_table)
    save_tsv('扇出33点.tsv',fanout_table)
    save_tsv('物品守恒19种.tsv',material_table)
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
    if errors:
        raise SystemExit(1)

if __name__=='__main__':
    main()
