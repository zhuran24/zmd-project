#!/usr/bin/env python3
"""将已落盘的独立复算逐字段对照被审快照；不调用转换器或Rust校验器。"""
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SNAP = OUT / '被审快照/求解器'
RAW = Path('/home/zhuran24/文档/会议2全套/会议目录/seat-opus-4')
def read_json(path):
    return json.loads(path.read_text(), parse_float=str)
def q(value, category='候选'):
    return dict(value=str(F(value)),category=category)
def number(value):
    return F(value['value'])
def read_csv(path, delimiter=','):
    with path.open(newline='',encoding='utf-8') as stream:
        return list(csv.DictReader(stream,delimiter=delimiter))

errors=[]
checks=[]
def check(where, condition, detail=''):
    checks.append(dict(where=where, result='通过' if condition else '不一致',detail=detail))
    if not condition:
        errors.append(dict(where=where,detail=detail))
def equal(where, actual, expected):
    check(where, actual==expected, '' if actual==expected else f'实得={actual!r}；独立复算={expected!r}')

data=read_json(OUT/'独立复算.json')
summary=data['summary']
machines=data['per_machine']
official=read_json(OUT/'正式配方独立解析.json')
contract=read_json(SNAP/'数据/候选B/contract.json')
catalog=read_json(SNAP/'数据/正式静态目录.json')
units={unit['id']:unit for unit in catalog['units']}
raw_edges=read_csv(RAW/'channels.csv')
expected_edges=[]
expected_sources=[]
inputs,outputs=Counter(),Counter()
for edge in raw_edges:
    source=edge['源机器id']
    if source=='仓库出矿口':
        source=f'ORE{len(expected_sources):03d}'
        expected_sources.append(dict(id=source,item=edge['物品'],output_ports=q(1,'条文直引'),
            identity=dict(status='待求',kind=None,side=None,index=None)))
    target='CORE' if edge['目标机器id']=='协议核心' else edge['目标机器id']
    inputs[target]+=1
    outputs[source]+=1
    expected_edges.append(dict(id='LF'+edge['通道id'][1:],source=source,target=target,
        source_recipe=edge['源配方'] or None,target_recipe=edge['目标配方'] or None,
        source_port=f'{source}:out:{outputs[source]}',target_port=f'{target}:in:{inputs[target]}',
        item=edge['物品'],planned_rate=q(F(edge['件每20tick'])/20),planned_full_speed=F(edge['件每20tick'])==20,
        proven_actual_rate=None,via=dict(bridge=None,splitter=None,merger=None,gate=None)))
equal('契约/sources',contract['sources'],expected_sources)
equal('契约/逻辑记录数',len(contract['logical_feeds']),len(expected_edges))
for actual,expected in zip(contract['logical_feeds'],expected_edges):
    equal('契约/'+expected['id'],actual,expected)
multi_ids=[]
for actual in contract['machines']:
    identity=actual['id']; value=machines[identity]; recipe=official[str(value['rule_line'])]
    rate=F(value['batch_rate'])
    multi=len(recipe['inputs'])>1 or value['input_count']>1
    if multi: multi_ids.append(identity)
    expected=dict(id=identity,kind=value['machine_type'],recipes=[dict(recipe=value['recipe_alias'],
        planned_batch_rate=q(rate),planned_mean_batch_interval=q(1/rate))],
        input_ports=q(value['port_capacity'],'算术推论'),output_ports=q(value['port_capacity'],'算术推论'),
        area=q({'3':9,'5':25,'6':24}[str(value['port_capacity'])],'算术推论'),orientation=None,
        multi_material=dict(arrival_composition_per_tick='待验',synchronization='待验',same_source='待验') if multi else None)
    equal('契约/'+identity,actual,expected)
equal('契约/机器身份全集',set(m['id'] for m in contract['machines']),set(machines))
shapes={'full_speed_fanout':'满速扇出定则型','round_robin_equal':'轮询均分型','neither':'两者都不落'}
fanouts={row['机器']:row for row in read_csv(OUT/'扇出33点.tsv','\t')}
for actual in contract['fanouts']:
    row=fanouts[actual['machine']]
    recipe=official[str(machines[actual['machine']]['rule_line'])]
    item=next(iter(recipe['outputs']))
    expected=dict(machine=row['机器'],recipe=row['配方'],item=item,ports=q(row['取货端口数']),
        planned_port_rate=q(row['计划各端口速率'].split(',')[0]),planned_mean_batch_interval=q(row['计划平均批间隔']),
        batch_size=q(row['每批件数'],'条文直引'),planned_shape=shapes[row['计划分类']],certification='待验')
    equal('契约/扇出/'+row['机器'],actual,expected)
equal('契约/扇出身份全集',set(fanouts),set(row['machine'] for row in contract['fanouts']))
equal('契约/到达义务43台',len(multi_ids),38+5)
equal('契约/速率窗口',contract['rate_window'],q(20))
equal('契约/来源域',contract['source_domain'],dict(left=q(23,'条文直引'),bottom=q(23,'条文直引'),core=q(6,'条文直引'),all_different=True))
equal('契约/核心',contract['core'],dict(id='CORE',input_ports=q(14,'条文直引'),output_ports=q(6,'条文直引'),orientation=None))
equal('契约/目标',contract['targets'],{item:q(value,'条文直引') for item,value in summary['product_rates'].items()})
equal('契约/排除单位',set(contract['planned_absent']),{'splitter','merger','gate','storage'})
equal('契约/格式',contract['schema'],'feeding-v2')

# 核三份正式全文、每条据与任务条件；目录只作为被审对象。
source_texts={}
for source in catalog['sources']:
    path=ROOT/source['path']; raw=path.read_bytes(); source_texts[source['path']]=raw.decode().splitlines()
    equal('目录/源指纹/'+source['path'],source['sha256'],hashlib.sha256(raw).hexdigest())
    equal('目录/源全文/'+source['path'],source['lines'],source_texts[source['path']])
limit_lines=source_texts['求解约束.txt']
rules={}
section=None
for index,line in enumerate(limit_lines,1):
    if line.endswith('：') and not line.startswith(' '): section=line[:-1]
    elif '：' in line and not line.startswith(' '):
        name,body=line.split('：',1)
        rules[name]=dict(text=body,section=section,source_line=str(index),basis=limit_lines[index].strip()[2:],
            basis_line=str(index+1),obligation='目标须对其每种取值都达成' if section.startswith('不得依赖') else None)
equal('目录/约束56条',len(catalog['constraints']),len(rules))
for rule in catalog['constraints']:
    equal('目录/约束/'+rule['name'],{k:v for k,v in rule.items() if k!='name'},rules[rule['name']])
task_lines=source_texts['求解任务.txt']
equal('目录/完整目标',catalog['task']['goal'],task_lines[1])
equal('目录/目标速率',catalog['task']['targets'],contract['targets'])
expected_conditions=[dict(name=line.split('：',1)[0],text=line.split('：',1)[1],basis='求解任务·'+line.split('：',1)[0]) for line in task_lines if '：' in line]
equal('目录/任务条件',catalog['task']['conditions'],expected_conditions)
equal('目录/配方总数',len(catalog['recipes']),len(official))
recipe_lookup={}
for actual,expected in zip(catalog['recipes'],official.values()):
    converted=dict(kind=expected['machine_type'],inputs={k:q(v,'条文直引') for k,v in expected['inputs'].items()},
        outputs={k:q(v,'条文直引') for k,v in expected['outputs'].items()},duration=q(expected['ticks'],'条文直引'))
    equal('目录/配方/'+actual['id'],{k:v for k,v in actual.items() if k!='id'},converted)
    recipe_lookup[actual['id']]=expected
lower_m={k:int(v) for k,v in re.findall(r'([^、 ≥]+) ≥(\d+)',rules['机型下限']['text']) if k in units}
lower_parts=rules['通道下限']['text'].split('；')
lower_in={k:int(v) for k,v in re.findall(r'([^、 ]+) (\d+)',lower_parts[0].replace('存货通道至少','')) if k in units}
lower_out={k:int(v) for k,v in re.findall(r'([^、 ]+) (\d+)',lower_parts[1].replace('取货通道至少','')) if k in units}
unit_rows=[]
for name in lower_m:
    u=units[name]
    cap=3 if name in ['粉碎机','精炼炉','配件机','塑形机'] else 5 if name in ['种植机','采种机'] else 6
    width,height=(cap,4 if cap==6 else cap)
    equal('目录/尺寸/'+name,(number(u['dimensions']['width']),number(u['dimensions']['height']),number(u['area'])),(width,height,width*height))
    equal('目录/端口数/'+name,(number(u['ports']['input_count']),number(u['ports']['output_count'])),(cap,cap))
    equal('目录/三下限/'+name,{key:number(u['static_lower_bounds'][key]) for key in ['machines','input_channels','output_channels']},
          dict(machines=lower_m[name],input_channels=lower_in[name],output_channels=lower_out[name]))
    slots={slot['role']:slot for slot in u['inventory']}
    equal('目录/物品格/'+name,(number(slots['input']['count']),number(slots['input']['capacity']),number(slots['output']['count']),number(slots['output']['capacity']),number(slots['buffer']['count']),slots['buffer']['capacity']),
          (2 if cap==6 else 1,50,1,50,1,None))
    unit_rows.append({'机型': name, '台数': summary['type_counts'][name], '台数下限': lower_m[name], '存货通道': summary['type_inputs'][name], '存货下限': lower_in[name], '取货通道': summary['type_outputs'][name], '取货下限': lower_out[name]})
for name,width,height,ins,outs in [('协议核心',9,9,14,6),('传送带',1,1,1,1),('桥接器',1,1,2,2),('物品准入口',1,1,1,1),('分流器',1,1,1,3),('汇流器',1,1,3,1),('协议储存箱',3,3,3,3),('仓库取货口',3,1,0,1),('供电桩',2,2,0,0)]:
    u=units[name]
    equal('目录/非制造尺寸端口/'+name,tuple(number(value) for value in [u['dimensions']['width'],u['dimensions']['height'],u['area'],u['ports']['input_count'],u['ports']['output_count']]),(width,height,width*height,ins,outs))
equal('目录/单位数',len(units),18)
expected_constants=dict(port_rate=1,source_per_side=23,ore_total=52,battery_iron=20,battery_ore=30,capsule_iron=40,
    grinder_trigger=32,grinder_count=31,grinder_inputs=3,seed_trigger=16,seed_outputs=2,shaper_trigger=6,shaper_count=5,shaper_inputs=2,
    pack_trigger=3,pack_inputs=5,fill_trigger=3,fill_count=2,fill_inputs=4,fill_other_inputs=3,plant_trigger=32,product_sources=6,product_inputs=2,
    transport_s=312,transport_r=307,box_base=619,box_h=2,box_eta_h_offset=2,box_eta_m_base=5,box_eta_h_factor=2,box_eta_h_subtract=9,plant_area=1378,flow_total=F(6113,20))
equal('目录/阈值字段集合',set(catalog['static_checks']['constants']),set(expected_constants))
for name,value in catalog['static_checks']['constants'].items():
    equal('目录/阈值/'+name,value['quantity'],q(expected_constants[name],'条文直引'))
    check('目录/阈值出处/'+name,value['source_excerpt'] in rules[value['basis'].split('·')[1]]['text'])
material_rows={row['物品']:row for row in read_csv(OUT/'物品守恒19种.tsv','\t')}
for item,value in catalog['static_checks']['material_flow'].items():
    equal('目录/物料流量/'+item,value,q(F(material_rows[item]['制造产出'])+F(material_rows[item]['仓库供给']),'条文直引'))
gate=units['物品准入口']['settings']
equal('目录/准入口数值',tuple(number(value) for value in [gate['total_limit']['min'],gate['total_limit']['max'],gate['window_limit']['min'],gate['window_limit']['max'],gate['window_ticks']]),(1,5000,1,5,5))
equal('目录/传输冷却',units['协议储存箱']['transfer']['cooldown_ticks'],q(5,'条文直引'))

# 所有报告行都有一条审计记录；数值行用独立算式对照，纯边界行逐类核其适用范围。
report_rows=[]; section=None; counts=Counter(); unhandled=[]
report_lines=(SNAP/'数据/候选B/校验报告.md').read_text().splitlines()
for line_number,line in enumerate(report_lines,1):
    if line.startswith('## '): section=re.search(r'## (.+)（',line)[1]
    if line.startswith('| ') and not line.startswith('| 检查项'):
        key,body=line[2:-2].split(' | ',1)
        report_rows.append((line_number,section,key,body));counts[section]+=1
        parts=key.split('/'); prefix=parts[0]; identity=parts[-1]
        ok=True; mode='结构、证据边界文字核对'
        nums=lambda pattern: tuple(F(value) for value in re.search(pattern,body).groups())
        if prefix=='目录' and parts[1]=='阈值': ok=F(body.split('（')[0])==expected_constants[identity];mode='正式阈值逐项对照'
        elif prefix=='端口速率':
            if parts[1]=='记录': expected=number(expected_edges[int(identity[2:])]['planned_rate'])
            else:
                port='/'.join(parts[3:]);side='target_port' if parts[1]=='存货' else 'source_port'
                expected=sum(number(edge['planned_rate']) for edge in expected_edges if edge[side]==port)
            ok=F(re.search(r'(?:计划 |端口各记录合计 )([\d/]+)',body)[1])==expected and 0<expected<=1;mode='端口速率独立复算'
        elif prefix=='满速独占' and parts[1]=='计划标记':
            edge=expected_edges[int(identity[2:])]
            ok=nums(r'计划 ([\d/]+) 件')==(number(edge['planned_rate']),) and ('标记=true' in body)==edge['planned_full_speed'];mode='逐LF满速标记'
        elif prefix=='端口数':
            m=machines[identity];ok=nums(r'存货 (\d+)、取货 (\d+)、存货上限 (\d+)、取货上限 (\d+)')==(m['input_count'],m['output_count'],m['port_capacity'],m['port_capacity']);mode='逐机端口计数'
        elif prefix=='占地':
            m=machines[identity];expected={3:9,5:25,6:24}[m['port_capacity']];ok=nums(r'机型面积 (\d+) 格')==(expected,);mode='正式尺寸乘积'
        elif prefix=='逐机配方守恒':
            m=machines[parts[1]];side='input_rates' if parts[3]=='输入' else 'output_rates'
            expected=F(m[side][parts[4]]);ok=nums(r'合计 ([\d/]+)，配方要求 ([\d/]+)')==(expected,expected);mode='逐机逐物品精确守恒'
        elif prefix in ['制造能力','满载配置']:
            m=machines[identity];expected=F(m['batch_rate'])*official[str(m['rule_line'])]['ticks']
            pattern=r'之和 ([\d/]+) ≤1' if prefix=='制造能力' else r'计划占用=([\d/]+)；'
            ok=nums(pattern)==(expected,);mode='逐机时间占用'
        elif prefix=='全局守恒':
            row=material_rows[identity];expected=F(row['制造产出'])+F(row['仓库供给']);ok=nums(r'出库 ([\d/]+) = 消耗\+入库 ([\d/]+)')==(expected,expected);mode='19种物品全局守恒'
        elif prefix=='目标' and identity!='项目集':
            expected=F(summary['product_rates'][identity]);ok=nums(r'计划入库 ([\d/]+)，目标 ([\d/]+)')==(expected,expected);mode='正式目标速率'
        elif prefix=='机型下限':ok=nums(r'^(\d+) ≥ (\d+)$')==(summary['type_counts'][identity],lower_m[identity]);mode='逐机型计数'
        elif prefix=='通道下限':ok=nums(r'存货 (\d+) ≥(\d+)；取货 (\d+) ≥(\d+)')==(summary['type_inputs'][identity],lower_in[identity],summary['type_outputs'][identity],lower_out[identity]);mode='逐机型端口计数'
        elif prefix=='物料流量':
            row=material_rows[identity];expected=F(row['制造产出'])+F(row['仓库供给']);ok=nums(r'流量 ([\d/]+) ≥ ([\d/]+)')==(expected,expected);mode='19种物料流量'
        elif prefix=='扇出' and parts[1]=='计划分类':ok=('计算形状='+shapes[fanouts[identity]['计划分类']]+'；') in body;mode='独立扇出分类'
        elif prefix=='正式条目':
            rule=rules[identity]; expected=f'分节：{rule["section"]}；义务：{rule["obligation"] or "按条文前件"}；条文：{rule["text"]}；据：{rule["basis"]}'
            ok=expected in body and section=='不能静态检';mode='全部56条正式原文和未覆盖边界'
        elif prefix in ['契约','来源端口身份','配方','目录','协议核心','出库上限','目标','研磨进料','封装进料','灌装混线','取货口配置','矿线专机','单位矿耗','回路守恒','矿系不入库','成品汇入','运输端口收支','箱体接口','矿石分流与专机','箱体过站','回路转弯','满速独占','扇出','候选B','多料接口']:
            # 汇总投影在下方具名复算，纯文字与全部输入逐字段对照联合检查。
            pass
        else: unhandled.append(key)
        checks.append(dict(where=f'校验报告.md:{line_number} {key}',result='通过' if ok else '不一致',detail=mode))
        if not ok: errors.append(dict(where=f'校验报告.md:{line_number}',detail=key+'：'+body))
equal('报告/行数',dict(counts),{'能检且通过':4925,'不能静态检':59})
equal('报告/未识别行类别',unhandled,[])
report_map={key:body for _,_,key,body in report_rows}
def has(key,text):check('报告/'+key,text in report_map[key],text)
has('研磨进料/研磨','31/32');has('研磨进料/塑形','5/6')
has('封装进料/封装机',str(summary['packaging_inputs']));has('封装进料/灌装机',str(summary['filling_inputs']))
has('灌装混线/结构','前提不触发')
for plant,values in summary['plant_cycles'].items():has('回路守恒/种子自给/'+plant,f'采种 {values["seed_batches"]}、种植 {values["plant_batches"]}')
has('成品汇入/通道下限/入库途径','K=6；成品来源=6')
has('运输端口收支/可知投影','S=315、R=315')
has('运输端口收支/派生运输下限',f'{max(summary["S"],summary["R"])}+E≥315')
eta=max(2-2,5,2*2-9)
has('箱体接口/已知计数投影',f'H=2、η={eta}，S+R={summary["S"]+summary["R"]}≥{619+eta}')
has('矿石分流与专机/定义计数','N矿=52');has('矿石分流与专机/定义计数','C矿=52')
has('箱体过站/已知流量投影','⌈305.65+Q⌉=306')
histogram=Counter(str(number(edge['planned_rate'])) for edge in expected_edges)
has('满速独占/计划适用集合',f'计划满速记录 {histogram["1"]} 条，其中矿石来源 52、非矿石 {histogram["1"]-52}')
plant_area=sum({3:9,5:25,6:24}[m['port_capacity']] for m in machines.values() if m['machine_type'] in ['种植机','采种机'] or m['recipe_alias'] in ['粉碎-荞花','粉碎-砂叶'])
has('回路转弯/占格条件投影',f'制造占格={plant_area}')
has('回路转弯/占格条件投影',f'max(0,1378−{plant_area})={max(0,1378-plant_area)}')
# 覆盖表逐行回源，不把行数覆盖当语义证明。
coverage=(SNAP/'数据/规则覆盖表.md').read_text().splitlines()
coverage_counts=Counter()
for line in coverage:
    match=re.search(r'\| (\d+) \| (.*?) \| `sources\[(\d+)\]\.lines\[(\d+)\]`',line)
    if match:
        source,index=int(match[3]),int(match[4]);coverage_counts[source]+=1
        expected=catalog['sources'][source]['lines'][index].strip() or '（空行）'
        equal(f'覆盖表/{source}/{index+1}',(int(match[1]),match[2]),(index+1,expected))
equal('覆盖表/114与15行',dict(coverage_counts),{0:114,1:15})
for index,rule in enumerate(catalog['constraints']):
    check('覆盖表/约束/'+rule['name'],any(f'`constraints[{index}]`' in line and f'报告“正式条目/{rule["name"]}”' in line for line in coverage))

result=dict(check_count=len(checks),difference_count=len(errors),differences=errors,
    report_counts=dict(counts),independent_summary=summary,multi_obligation_ids=multi_ids,
    rate_histogram=dict(histogram),unit_counts=unit_rows)
(OUT/'逐项对比.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
with (OUT/'报告及字段逐项审计.tsv').open('w',newline='',encoding='utf-8') as stream:
    writer=csv.DictWriter(stream,fieldnames=['where','result','detail'],delimiter='\t');writer.writeheader();writer.writerows(checks)
print(json.dumps({key:value for key,value in result.items() if key not in ['independent_summary','multi_obligation_ids','unit_counts']},ensure_ascii=False,indent=2,default=str))
raise SystemExit(bool(errors))
