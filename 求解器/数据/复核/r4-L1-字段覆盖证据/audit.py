#!/usr/bin/env python3
"""复核静态字段与来源；结果只写入本复核证据目录。"""
import ast
import copy
import csv
import hashlib
import importlib.util
import json
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE / 'snapshot'
DATA = REPO / '求解器/数据'
SOURCE = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
catalog = json.loads((DATA / '正式静态目录.json').read_text())
contract = json.loads((DATA / '候选B/contract.json').read_text())
results = {}


def value(q):
    return Fraction(q['value'])


def record(name, condition):
    assert condition, name
    results[name] = True


# 直接比较正式全文，并独立逐行解析约束分节和据。
for source in catalog['sources']:
    content = (REPO / source['path']).read_bytes()
    record('来源/' + source['path'],
           hashlib.sha256(content).hexdigest() == source['sha256']
           and content.decode().splitlines() == source['lines'])
rules = (REPO / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
constraint_lines = (REPO / '求解约束.txt').read_text().splitlines()
parsed, section = [], None
for line_number, line in enumerate(constraint_lines, 1):
    if not line.strip() or '：' not in line:
        continue
    if line.startswith('    据：'):
        parsed[-1].update(basis=line.strip().split('：', 1)[1], basis_line=str(line_number))
    elif line.endswith('：'):
        section = line[:-1]
    else:
        name, text = line.split('：', 1)
        parsed.append(dict(name=name, text=text, section=section,
                           source_line=str(line_number),
                           obligation='目标须对其每种取值都达成' if section.startswith('不得依赖') else None))
record('约束完整上下文', parsed == catalog['constraints'])

# 从配方原文独立重建语义内容；工程 id 另行检查唯一。
expected_recipes, kind = [], None
for line in rules[79:]:
    if not line.strip():
        continue
    if '→' not in line:
        kind = line.strip()
        continue
    left, right = line.split(' → ')
    outputs, duration = right.split('，')
    def terms(text):
        return {item: int(count) for count, item in re.findall(r'(\d+) ([^＋]+?)(?= ＋ |$)', text)}
    expected_recipes.append((kind, terms(left), terms(outputs), int(duration.split()[0])))
actual_recipes = [(r['kind'], {k:int(value(v)) for k,v in r['inputs'].items()},
                   {k:int(value(v)) for k,v in r['outputs'].items()}, int(value(r['duration'])))
                  for r in catalog['recipes']]
record('全部配方机型用量产量耗时', actual_recipes == expected_recipes)
record('配方身份唯一', len({r['id'] for r in catalog['recipes']}) == 18)

# 对照规则 L41、44、50、54、59–76；未知桥容量不取默认。
units = {u['id']:u for u in catalog['units']}
groups = [('粉碎机 精炼炉 塑形机 配件机',3,3,3,3,1),
          ('种植机 采种机',5,5,5,5,1), ('研磨机 封装机 灌装机',6,4,6,6,2)]
expected_units = {}
for names,w,h,ins,outs,input_slots in groups:
    for name in names.split():
        expected_units[name]=(w,h,ins,outs,True,[('input',input_slots,50),('output',1,50),('buffer',1,None)])
expected_units.update({
    '协议核心':(9,9,14,6,False,[('warehouse',None,80000)]),
    '传送带':(1,1,1,1,False,[('transport',1,1)]),
    '桥接器':(1,1,2,2,False,[('vertical',1,None),('horizontal',1,None)]),
    '物品准入口':(1,1,1,1,False,[('transport',1,1)]),
    '分流器':(1,1,1,3,False,[('transport',1,1)]),
    '汇流器':(1,1,3,1,False,[('transport',1,1)]),
    '协议储存箱':(3,3,3,3,True,[('storage',6,50)]),
    '仓库取货口':(3,1,0,1,False,[]), '供电桩':(2,2,0,0,False,[])})
record('单位类目', set(units) == set(expected_units) and len(catalog['units']) == 18)
for name,(w,h,ins,outs,powered,slots) in expected_units.items():
    u=units[name]
    numbers=[value(u['dimensions']['width']),value(u['dimensions']['height']),
             value(u['area']),value(u['ports']['input_count']),value(u['ports']['output_count'])]
    record('单位数值/'+name, numbers == [w,h,w*h,ins,outs] and u['power_required'] == powered)
    actual_slots=[(s['role'],None if s['count'] is None else value(s['count']),
                   None if s['capacity'] is None else value(s['capacity'])) for s in u['inventory']]
    record('物品格/'+name, actual_slots == slots)
record('供电覆盖数值', all(value(units['供电桩']['coverage'][key]) == 12 for key in ['width','height']))
record('准入口数值', [(value(units['物品准入口']['settings'][k]['min']), value(units['物品准入口']['settings'][k]['max']))
                     for k in ['total_limit','window_limit']] == [(1,5000),(1,5)]
       and value(units['物品准入口']['settings']['window_ticks']) == 5)
record('箱体冷却', value(units['协议储存箱']['transfer']['cooldown_ticks']) == 5)
bounds = {row['name']:row['text'] for row in parsed}
for name,u in units.items():
    if u['family'] != 'manufacturing':
        continue
    low = int(re.search(re.escape(name)+r' ≥(\d+)', bounds['机型下限']).group(1))
    inc = int(re.search(re.escape(name)+r' (\d+)', bounds['通道下限'].split('；')[0]).group(1))
    out = int(re.search(re.escape(name)+r' (\d+)', bounds['通道下限'].split('；')[1]).group(1))
    record('正式下限/'+name, [value(u['static_lower_bounds'][k]) for k in ['machines','input_channels','output_channels']] == [low,inc,out])

# 每行 CSV 与契约对应，不运行会覆盖会议资产的原生成器。
machine_rows=list(csv.DictReader((SOURCE/'machines.csv').open()))
feed_rows=list(csv.DictReader((SOURCE/'channels.csv').open()))
recipe_map={r['id']:r for r in catalog['recipes']}
machine_map={m['id']:m for m in contract['machines']}
feed_map={e['id']:e for e in contract['logical_feeds']}
incoming, outgoing = {}, {}
for machine in contract['machines']:
    incoming[machine['id']]={e['target_port'] for e in contract['logical_feeds'] if e['target']==machine['id']}
    outgoing[machine['id']]={e['source_port'] for e in contract['logical_feeds'] if e['source']==machine['id']}
for row in machine_rows:
    m=machine_map[row['机器id']]
    record('源机器/'+m['id'], len(m['recipes']) == 1 and m['recipes'][0]['recipe'] == row['配方']
           and value(m['recipes'][0]['planned_batch_rate']) == Fraction(row['批次每20tick'])/20
           and value(m['recipes'][0]['planned_mean_batch_interval']) == 20/Fraction(row['批次每20tick'])
           and len(incoming[m['id']])==int(row['存货通道数']) and len(outgoing[m['id']])==int(row['取货通道数']))
ore_index=0
for row in feed_rows:
    e=feed_map['LF'+row['通道id'][1:]]
    expected_source=row['源机器id']
    if expected_source=='仓库出矿口':
        expected_source=f'ORE{ore_index:03d}'; ore_index+=1
    record('源送料/'+e['id'], e['source']==expected_source and e['target']==('CORE' if row['目标机器id']=='协议核心' else row['目标机器id'])
           and e['source_recipe']==(row['源配方'] or None) and e['target_recipe']==(row['目标配方'] or None)
           and e['item']==row['物品'] and value(e['planned_rate'])==Fraction(row['件每20tick'])/20
           and e['planned_full_speed']==(row['是否满速']=='是') and e['proven_actual_rate'] is None
           and e['via']==dict(bridge=None,splitter=None,merger=None,gate=None))
required_multi={m['id'] for m in contract['machines'] if len(m['recipes'])>1 or len(incoming[m['id']])>1
                or any(len(recipe_map[p['recipe']]['inputs'])>1 for p in m['recipes'])}
record('到达义务字段覆盖', {m['id'] for m in contract['machines'] if m['multi_material'] is not None}==required_multi
       and all(set(m['multi_material'].values())=={'待验'} for m in contract['machines'] if m['multi_material']))
record('来源身份字段', len(contract['sources'])==52 and all(s['identity']==dict(status='待求',kind=None,side=None,index=None) for s in contract['sources']))
record('来源取值域', [value(contract['source_domain'][k]) for k in ['left','bottom','core']]==[23,23,6] and contract['source_domain']['all_different'])
record('扇出完整性', {f['machine'] for f in contract['fanouts']}=={m for m,v in outgoing.items() if len(v)>1}
       and len(contract['fanouts'])==33 and all(f['certification']=='待验' for f in contract['fanouts']))

missing=[]
def scan(node,path=''):
    if isinstance(node,dict):
        if 'value' in node and set(node)!={'value','category'}: missing.append(path)
        for k,v in node.items(): scan(v,path+'/'+k)
    elif isinstance(node,list):
        for i,v in enumerate(node): scan(v,path+'/'+str(i))
    elif isinstance(node,(float,int)) and not isinstance(node,bool): missing.append(path)
scan(catalog,'catalog');scan(contract,'contract')
record('无未分类结构化数值', not missing)

# 完整源转录的行号入口及报告对正式条目的覆盖。
coverage=(DATA/'规则覆盖表.md').read_text()
sections=re.split(r'^## ',coverage,flags=re.M)
for name,count in [('《明日方舟：终末地》游戏规则.txt',114),('求解任务.txt',15)]:
    block=next(s for s in sections if s.startswith(name))
    rows=[line.split('|')[1:3] for line in block.splitlines() if re.match(r'^\| \d+ \|',line)]
    originals=(REPO/name).read_text().splitlines()
    record('覆盖表/'+name, len(rows)==count and all(int(n.strip())==i and text.strip()==(originals[i-1].strip() or '（空行）') for i,(n,text) in enumerate(rows,1)))
report=(DATA/'候选B/校验报告.md').read_text()
record('报告正式条目覆盖', all('| 正式条目/'+r['name']+' |' in report for r in parsed))
record('CLI逐字节复现', (HERE/'原版-CLI报告.md').read_bytes()==(DATA/'候选B/校验报告.md').read_bytes())
counts=Counter(m['kind'] for m in contract['machines'])
summary=dict(machine_count=len(contract['machines']),machine_kinds=dict(counts),
             area=str(sum(value(m['area']) for m in contract['machines'])),
             logical_feeds=len(contract['logical_feeds']),
             s=len({(e['source'],e['source_port']) for e in contract['logical_feeds']}),
             r=len({(e['target'],e['target_port']) for e in contract['logical_feeds']}),
             multi_material=len(required_multi),full_speed=sum(e['planned_full_speed'] for e in contract['logical_feeds']),
             fanout_shapes=dict(Counter(f['planned_shape'] for f in contract['fanouts'])))
(HERE/'独立核对结果.json').write_text(json.dumps(dict(summary=summary,checks=results),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(passed=len(results),summary=summary),ensure_ascii=False,indent=2))
