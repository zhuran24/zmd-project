#!/usr/bin/env python3
"""从候选原表转换，所有写入限定在求解器内；不执行原脚本。"""
import ast
import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from formal_catalog import verify

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
OUT = ROOT / '数据/候选B'

def quantity(value, category='候选'):
    assert not isinstance(value, float), '不允许二进制浮点中转'
    return {'value': str(Fraction(value)), 'category': category}

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

# 正式配方由规则原文解析；候选的缩写只用于标识符映射。
recipe_names = ['粉碎-源矿','粉碎-蓝铁块','粉碎-荞花','粉碎-砂叶','精炼-蓝铁矿','精炼-致密蓝铁','精炼-蓝铁粉末','研磨-致密蓝铁','研磨-致密源石','研磨-细磨荞花','塑形-钢质瓶','配件-钢制零件','种植-荞花','种植-砂叶','采种-荞花','采种-砂叶','封装-电池','灌装-胶囊']
recipes = []
kind = None
for line in (REPO / '《明日方舟：终末地》游戏规则.txt').read_text().split('配方\n\n', 1)[1].splitlines():
    if not line.strip():
        continue
    if '→' not in line:
        kind = line.strip()
        continue
    left, right = line.split(' → ')
    output, duration = right.split('，')
    def terms(text):
        return {term.split(' ',1)[1]: quantity(term.split(' ',1)[0], '条文直引') for term in text.split(' ＋ ')}
    recipes.append({'id':recipe_names[len(recipes)],'kind':kind,'inputs':terms(left),'outputs':terms(output),'duration':quantity(duration.split()[0], '条文直引')})
catalog = json.loads((ROOT/'数据/正式静态目录.json').read_text())
verify(catalog)
assert recipes == catalog['recipes'], '正式配方变动，须先审查并修订单位目录'
units = {u['id']:u for u in catalog['units']}
recipe_map = {r['id']:r for r in catalog['recipes']}

# 对照 design.py 的配方常量，不执行会覆盖源 CSV 的脚本。
tree = ast.parse((SOURCE/'design.py').read_text())
source_recipes = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RECIPE' for t in n.targets))
for key, (_, inputs, outputs, duration) in source_recipes.items():
    r = recipe_map[key]
    assert inputs == {k:int(v['value']) for k,v in r['inputs'].items()}
    assert outputs == {k:int(v['value']) for k,v in r['outputs'].items()}
    assert str(duration) == r['duration']['value']
# 仅求值字面量、列表重复与连接；不运行原脚本的文件写入。
def literal_expression(node):
    if isinstance(node, ast.BinOp):
        left, right = literal_expression(node.left), literal_expression(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Mult):
            return left * right
        raise ValueError('不支持的设计表达式')
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [literal_expression(x) for x in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    return ast.literal_eval(node)
source_design = next(literal_expression(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DESIGN' for t in n.targets))
rows = list(csv.DictReader((SOURCE/'machines.csv').open()))
edges = list(csv.DictReader((SOURCE/'channels.csv').open()))
design_rows = [(recipe, batches, ports) for recipe, group in source_design for batches, ports in group]
assert len(rows) == len(design_rows)
for index, (row, (recipe, batches, ports)) in enumerate(zip(rows, design_rows)):
    assert row['机器id'] == f'M{index:03d}'
    assert (row['配方'], int(row['批次每20tick']), int(row['取货通道数'])) == (recipe, batches, ports)
fanout_rows = json.loads((SOURCE/'fanout.json').read_text(), parse_float=str)
machines = []
for row in rows:
    rid = row['配方']
    unit = units[recipe_map[rid]['kind']]
    input_cap = unit['ports']['input_count']
    output_cap = unit['ports']['output_count']
    area = int(unit['area']['value'])
    assert row['机型'] == unit['dimensions']['width']['value'] + 'x' + unit['dimensions']['height']['value']
    multi = len(recipe_map[rid]['inputs']) > 1 or int(row['存货通道数']) > 1
    machines.append({'id':row['机器id'],'kind':recipe_map[rid]['kind'],
        'recipes':[{'recipe':rid,'planned_batch_rate':quantity(Fraction(row['批次每20tick'])/20),'planned_mean_batch_interval':quantity(Fraction(20,int(row['批次每20tick'])))}],
        'input_ports':input_cap,'output_ports':output_cap,'area':quantity(area,'算术推论'),
        'orientation':None,'multi_material':{'arrival_composition_per_tick':'待验','synchronization':'待验','same_source':'待验'} if multi else None})
machine_rows = {row['机器id']:row for row in rows}
for row in edges:
    assert row['是否满速'] == ('是' if Fraction(row['件每20tick']) == 20 else '否')
    for side in ['源', '目标']:
        mid = row[side+'机器id']
        if mid in machine_rows:
            assert row[side+'配方'] == machine_rows[mid]['配方']
            assert row[side+'机型'] == machine_rows[mid]['机型']
        else:
            assert row[side+'配方'] == '' and row[side+'机型'] == ''
logical_feeds = []
sources = []
input_count = Counter()
output_count = Counter()
for row in edges:
    source = row['源机器id']
    if source == '仓库出矿口':
        source = f'ORE{len(sources):03d}'
        sources.append({'id':source,'item':row['物品'],'identity':{'status':'待求','kind':None,'side':None,'index':None},'output_ports':quantity(1,'条文直引')})
    target = 'CORE' if row['目标机器id']=='协议核心' else row['目标机器id']
    input_count[target] += 1
    output_count[source] += 1
    logical_feeds.append({'id':'LF'+row['通道id'][1:],'source':source,'source_recipe':row['源配方'] or None,'source_port':f'{source}:out:{output_count[source]}',
        'target':target,'target_recipe':row['目标配方'] or None,'target_port':f'{target}:in:{input_count[target]}',
        'item':row['物品'],'planned_rate':quantity(Fraction(row['件每20tick'])/20),'planned_full_speed':row['是否满速']=='是','proven_actual_rate':None,
        'via':{'bridge':None,'splitter':None,'merger':None,'gate':None}})
# 原表的逐机端口件数、速率列表与通道逐项比对，保留平行边。
for row in rows:
    for side, field, count_field in [('target','存货通道速率','存货通道数'),('source','取货通道速率','取货通道数')]:
        selected = [c for c in logical_feeds if c[side]==row['机器id']]
        assert len(selected)==int(row[count_field])
        actual = Counter((c['item'], Fraction(c['planned_rate']['value'])*20) for c in selected)
        original = Counter((v.split(':')[0],Fraction(v.split(':')[1])) for v in row[field].split(';'))
        assert actual==original, (row['机器id'],field)
fanouts = []
for row in fanout_rows:
    interval = Fraction(20, int(machine_rows[row['机器']]['批次每20tick']))
    assert Fraction(row['批间隔tick']) == interval, '源表平均间隔与整数批数不一致，不能静默保留舍入值'
    fanouts.append({'machine':row['机器'],'recipe':row['配方'],'item':row['物品'],'ports':quantity(row['k']),
        'planned_port_rate':quantity(Fraction(row['每端口速率'],20)),
        'planned_mean_batch_interval':quantity(interval),
        'batch_size':quantity(row['每批件数'],'条文直引'),
        'planned_shape':{'A 满速':'满速扇出定则型','B 原文前提内':'轮询均分型','C 需推广版':'两者都不落'}[row['类别']],
        'certification':'待验'})
contract = {'schema':'feeding-v2','candidate':'候选B','rate_window':quantity(20),
    'model':'专用逻辑送料记录，无分流汇流储存箱准入口；运输实现待求',
    'planned_absent':['splitter','merger','gate','storage'],
    'machines':machines,'sources':sources,'logical_feeds':logical_feeds,'fanouts':fanouts,
    'source_domain':{'left':catalog['static_checks']['constants']['source_per_side']['quantity'],'bottom':catalog['static_checks']['constants']['source_per_side']['quantity'],'core':units['协议核心']['ports']['output_count'],'all_different':True},
    'core':{'id':'CORE','input_ports':units['协议核心']['ports']['input_count'],'output_ports':units['协议核心']['ports']['output_count'],'orientation':None},
    'targets':catalog['task']['targets']}
write_json(OUT/'contract.json', contract)
paths = [REPO/n for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']]
paths += [SOURCE/n for n in ['design.py','channels.csv','machines.csv','fanout.json','scc.py']]
paths += [SOURCE.parent/'纪要.md',SOURCE.parent/'seat-opus-1/共识草案-v45-5c9e556a.md', SOURCE.parent/'seat-opus-3.md']
paths += [Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')/n for n in ['任务书.md','任务书2.md','gptpro_评审摘录.md']]
paths += [ROOT/'数据/正式静态目录.json']
write_json(OUT/'来源清单.json', [{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths])
print('转换完成；逐机端口和物品速率与源 CSV 一致；正式配方与 design.py 一致。')
