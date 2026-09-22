#!/usr/bin/env python3
"""运行输入、关键拒收边界和输出 schema 的无依赖回归。"""
import copy
import hashlib
import json
import re
from pathlib import Path
import check_examples as checker
from runtime_example import axis_values, decision, quantity
from check_golden_trace import run, INPUT, GOLDEN, OUTPUT

BASE=Path(__file__).resolve().parent


def validate_schema(value,schema,root,path='$'):
    """仅实现本交付 schema 实际使用的关键词；未知验证关键词即拒绝。"""
    supported={'$ref','$schema','$id','$defs','type','properties','required','additionalProperties','items','minItems','minLength','pattern','minimum','enum','const','anyOf','if','then','else'}
    checker.require(not (set(schema)-supported),'schema 出现未实现关键词')
    if 'if' in schema:
        try:validate_schema(value,schema['if'],root,path)
        except checker.CheckError:branch=schema.get('else',{})
        else:branch=schema.get('then',{})
        validate_schema(value,branch,root,path)
    if '$ref' in schema:
        target=root
        for part in schema['$ref'][2:].split('/'):target=target[part]
        validate_schema(value,target,root,path);return
    if 'anyOf' in schema:
        for branch in schema['anyOf']:
            try:validate_schema(value,branch,root,path);return
            except checker.CheckError:pass
        raise checker.CheckError(path+': anyOf 不匹配')
    if 'const' in schema:checker.require(type(value) is type(schema['const']) and value==schema['const'],path+': const不符')
    if 'enum' in schema:checker.require(value in schema['enum'],path+': enum不符')
    if 'type' in schema:
        types=schema['type'] if isinstance(schema['type'],list) else [schema['type']]
        actual='null' if value is None else 'boolean' if type(value)is bool else 'integer' if type(value)is int else 'string' if isinstance(value,str) else 'array' if isinstance(value,list) else 'object' if isinstance(value,dict) else 'unsupported'
        checker.require(actual in types,path+': 类型不符')
    if isinstance(value,dict):
        props=schema.get('properties',{});extra=set(value)-set(props)
        checker.require(set(schema.get('required',[]))<=set(value),path+': 必填字段缺失')
        if schema.get('additionalProperties') is False:checker.require(not extra,path+': 未知字段')
        for key,val in value.items():
            if key in props:validate_schema(val,props[key],root,path+'.'+key)
            elif isinstance(schema.get('additionalProperties'),dict):validate_schema(val,schema['additionalProperties'],root,path+'.'+key)
    elif isinstance(value,list):
        checker.require(len(value)>=schema.get('minItems',0),path+': 数组过短')
        for i,val in enumerate(value):validate_schema(val,schema.get('items',{}),root,f'{path}[{i}]')
    elif isinstance(value,str):
        checker.require(len(value)>=schema.get('minLength',0),path+': 字符串过短')
        if 'pattern' in schema:checker.require(re.search(schema['pattern'],value) is not None,path+': 格式不符')
    elif type(value)is int:
        if 'minimum' in schema:checker.require(value>=schema['minimum'],path+': 小于下界')


def validate_branch_table(value,channels,units,query,fork,evaluation_id=None):
    """核具体分支选择，不把有限调用表提升为整场固定性证明。"""
    checker.fields(value,'schema fixedness choices evaluations on_missing','DampingBranch')
    checker.require(value['schema']=='damping-branch-v1' and value['on_missing']=='unresolved','分支版本/缺省不符')
    if value['fixedness']=='fixed_for_run':
        checker.require(value['evaluations']==[],'固定分支不能混入跨次表');rows=value['choices']
    elif value['fixedness']=='per_evaluation':
        checker.require(value['choices']==[],'逐次分支不能混固定表')
        ids=[e['evaluation_id'] for e in value['evaluations']]
        checker.require(len(ids)==len(set(ids)),'调用 id 重复')
        checker.require(evaluation_id in ids,'unresolved: 缺少本次求值')
        rows=next(e['choices'] for e in value['evaluations'] if e['evaluation_id']==evaluation_id)
    else:raise checker.CheckError('分支固定性非法')
    cmap={c['id']:c for c in channels};umap={u['id']:u for u in units};seen=set();mapping={}
    for row in rows:
        checker.fields(row,'channel fork_unit outgoing_channel','branch_choice')
        key=(row['channel'],row['fork_unit']);checker.require(key not in seen,'分支键重复');seen.add(key)
        checker.require(row['channel'] in cmap and row['outgoing_channel'] in cmap,'分支引用非当前边')
        checker.require(umap.get(row['fork_unit'],{}).get('kind')=='分流器','分叉点不是分流器')
        checker.require(cmap[row['outgoing_channel']]['source_port'].split(':')[0]==row['fork_unit'],'所选边不是该点出支')
        # 先核查询沿有向边可到该分叉；到达后实际所选路径仍由调用者逐步核。
        start=cmap[row['channel']]['target_port'].split(':')[0];todo=[start];visited=set()
        while todo:
            u=todo.pop()
            if u in visited:continue
            visited.add(u)
            if umap[u]['kind'] not in ('分流器','汇流器','传送带','物品准入口'):continue
            todo.extend(c['target_port'].split(':')[0] for c in channels if c['source_port'].split(':')[0]==u)
        checker.require(row['fork_unit'] in visited,'分叉不在查询可达路中')
        mapping[key]=row['outgoing_channel']
    checker.require((query,fork) in mapping,'unresolved: 缺少分支键')
    return mapping[query,fork]


def main():
    data=checker.load_json(INPUT);results=[]
    def reject(name,mutate,expected):
        d=copy.deepcopy(data);mutate(d)
        try:checker.check(d,INPUT)
        except checker.CheckError as error:
            checker.require(expected in str(error),name+': 错误位置不符 '+str(error));results.append({'name':name,'status':'正确拒绝'})
        else:raise checker.CheckError(name+': 被错误放行')
    checker.check(data,INPUT)
    reject('漏一项运行轴',lambda d:d['parameters']['fixedness_unproven'].pop('time.domain'),'fixedness_unproven')
    reject('未定义判定模板',lambda d:d['parameters']['fixed']['judgment.order']['value']['template_order'].pop(),'judgment.order')
    reject('新生成判定使用未支持排序规则',lambda d:d['parameters']['fixed']['judgment.order']['value'].update(repeat_embedding='unknown'),'judgment.order')
    reject('完整StateSeed漏格',lambda d:d['initial_state']['nonwarehouse']['value']['inventory'].pop(),'物品格缺失')
    reject('轮询游标指向其它级',lambda d:d['initial_state']['nonwarehouse']['value']['logistics']['poll_memory']['value']['sides'][0].update(current_level='invented'),'轮询记忆')
    reject('当前参数与输入不同',lambda d:d['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values'].pop(),'当前轴值')
    reject('起点偷清已有端口消耗',lambda d:d['initial_state']['nonwarehouse']['value']['semantic_context']['tick_context']['value']['port_usage'].append({'port':'ore_source:north:1','quantity':quantity(1)}),'起点端口额度')
    reject('无供电仍声称可制造',lambda d:(next(u for u in d['layout']['units'] if u['kind']=='供电桩')['origin'][0].update(value='60'),next(m for m in d['construction']['moments'] if m['unit']=='power')['placement']['origin'][0].update(value='60')),'未获 positive_area')
    def empty_assignment(d,resolve):
        slot={'slot':'empty_test','item':None,'quantity':quantity(0),'empty_identity':decision(None,'无保留身份','specified' if resolve else 'unresolved')}
        d['initial_state']['warehouse']['slots'].append(slot)
        d['settings']['warehouse_assignments'][0]['slot']='empty_test'
    static=checker.load_json(BASE/'桥接器双通路.json')
    for resolve in (False,True):
        d=copy.deepcopy(static);empty_assignment(d,resolve)
        try:checker.check(d,BASE/'桥接器双通路.json')
        except checker.CheckError as e:
            checker.require(not resolve and 'empty_identity' in str(e),'空格指派诊断不符')
        else:checker.require(resolve,'未解决空格身份被放行')
    results.append({'name':'空格指派拒绝未解、接受显式无历史身份','status':'通过'})
    split=checker.load_json(BASE/'分流器三路轮询.json');channels=split['layout']['physical_channels'];units=split['layout']['units']
    query=next(c['id'] for c in channels if c['target_port'].startswith('splitter:'));outs=[c['id'] for c in channels if c['source_port'].startswith('splitter:')]
    rows=lambda out:[{'channel':query,'fork_unit':'splitter','outgoing_channel':out}]
    fixed={'schema':'damping-branch-v1','fixedness':'fixed_for_run','choices':rows(outs[0]),'evaluations':[],'on_missing':'unresolved'}
    checker.require(all(validate_branch_table(fixed,channels,units,query,'splitter',eid)==outs[0] for eid in ('a','b')),'跨次固定分支变化')
    varying={'schema':'damping-branch-v1','fixedness':'per_evaluation','choices':[],'evaluations':[{'evaluation_id':eid,'anchor':{'event':'debug_end','side':'after'},'choices':rows(out)} for eid,out in zip(('a','b'),outs)],'on_missing':'unresolved'}
    checker.require(validate_branch_table(varying,channels,units,query,'splitter','a')!=validate_branch_table(varying,channels,units,query,'splitter','b'),'逐次分支未独立编码')
    for name,bad,eid in [('缺调用',varying,'missing'),('非分支边',{**fixed,'choices':rows(query)},None),('重复分支键',{**fixed,'choices':rows(outs[0])+rows(outs[1])},None)]:
        try:validate_branch_table(bad,channels,units,query,'splitter',eid)
        except checker.CheckError:results.append({'name':name,'status':'正确拒绝'})
        else:raise checker.CheckError(name+' 被放行')
    results.append({'name':'非空分支表固定/逐次两种编码','status':'通过'})
    actual=run(data);golden=checker.load_json(GOLDEN)
    checker.require([t['summary'] for t in actual]==golden['ticks'],'黄金摘要不符')
    changed=copy.deepcopy(golden['ticks']);changed[2]['completed_batches']='2'
    checker.require([t['summary'] for t in actual]!=changed,'错误黄金值未检出')
    schema=checker.load_json(BASE.parents[1]/'规格/内核输出.schema.json');output=checker.load_json(OUTPUT)
    validate_schema(output,schema,schema)
    for name,mutate in [('输出漏逐轴赋值',lambda d:d.pop('parameter_assignment')),('输出冒称全称认证',lambda d:d['validation_scope'].update(target_certified=True)),('输出状态漏轮询记忆',lambda d:d['trace']['ticks'][0]['state']['logistics'].pop('poll_memory'))]:
        bad=copy.deepcopy(output);mutate(bad)
        try:validate_schema(bad,schema,schema)
        except checker.CheckError:results.append({'name':name,'status':'正确拒绝'})
        else:raise checker.CheckError(name+' 被放行')
    invalid=copy.deepcopy(output);invalid.update(status='invalid_input',parameter_assignment=None,input_history=None,trace=None,validation_scope=None,open_items=['装载时缺状态种子，无实际转移'])
    validate_schema(invalid,schema,schema)
    invalid['status']='completed'
    try:validate_schema(invalid,schema,schema)
    except checker.CheckError:results.append({'name':'装载失败可无种子，成功记录不可缺种子','status':'通过'})
    else:raise checker.CheckError('空种子被当完整执行结果')
    for row in output['fingerprints']:
        p=Path(row['path']);checker.require(hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],'输出指纹失效 '+str(p))
    profile=checker.load_json(BASE.parents[1]/'规格/内核配置-v1.json')
    for axis,row in profile['axes'].items():
        if row['disposition']!='由输入全称量化':checker.require(axis_values(data)[axis]['value']==row['value'],'profile逐值不一致 '+axis)
    report={'status':'通过','axis_count':len(axis_values(data)),'golden_match':True,'schema_validation':'本地严格验证本schema全部已用关键词，非通用JSON Schema工具','tests':results,'finite_trace_events':[len(t['events']) for t in actual],'bounds':'仅0–3 tick；无全称或完整目标认证'}
    target=BASE.parents[1]/'规格/内核输入修订验证-r3/运行回归结果.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','tests':len(results),'axis_count':len(axis_values(data)),'output':str(target)},ensure_ascii=False))


if __name__=='__main__':main()
