#!/usr/bin/env python3
"""第三轮运行输入的装配与有界检查接口；不作全称认证。"""
import copy
import hashlib
import json
from pathlib import Path
import check_examples as checker

BASE = Path(__file__).resolve().parent
PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
SUPPORTED_PROFILE_SHA256 = '1e5b86f7c5324ae726a6b14a8338e34c41d68a99febd5348698e8ea3ef82643a'


def quantity(value, category='候选'):
    return {'value': str(value), 'category': category}


def time_value(value):
    return {'kind': 'rational', 'value': quantity(value)}


def decision(value, basis, status='specified'):
    return {'status': status, 'value': value, 'basis': [basis]}


def axis_values(data):
    return {name: value for group in ('fixed', 'offline_mutable', 'fixedness_unproven') for name, value in data['parameters'][group].items()}


def templates(data):
    # 模板顺序是显式实验输入，不由实例字符串默定。
    channels = data['layout']['physical_channels']
    source_order = ['ore_source', 'feed_belt', 'crusher', 'belt_a0', 'belt_a1', 'belt_a2', 'belt_b0', 'belt_b1', 'belt_b2', 'belt_b3']
    moves = [{'operation': 'move', 'target': c['id']} for u in source_order for c in channels if c['source_port'].split(':')[0] == u]
    manufactures = [{'operation': 'manufacture', 'target': u['id']} for u in data['layout']['units'] if u['kind'] in ('粉碎机', '研磨机')]
    return moves + manufactures


def profile_values(data, catalog):
    profile = checker.load_json(BASE.parents[1]/'规格/内核配置-v1.json')
    values = {name: copy.deepcopy(row['value']) for name,row in profile['axes'].items() if row['disposition'] != '由输入全称量化'}
    supplied = {
        'judgment.order': {'schema':'event-order-v1','scope':'global','template_order':templates(data),'repeat_embedding':'scan_round_then_template','instant_overrides':[]},
        'damping.branch': {'schema':'damping-branch-v1','fixedness':'fixed_for_run','choices':[],'evaluations':[],'on_missing':'unresolved'},
        'connection.build_order': 'construction.selected_order',
        'connection.order': 'timeline_connection_history',
        'connection.tie': {'kind':'explicit_order','channels':[c['id'] for c in data['layout']['physical_channels']]},
        'connection.belt_shape': {'kind':'layout_build_history','values':[{'unit':u['id'],'build_event':next(m['event'] for m in data['construction']['moments'] if m['unit']==u['id']),'shape':{0:'straight',1:'turn_left',2:'turn_right'}[u['port_layout']]} for u in data['layout']['units'] if u['kind']=='传送带']},
        'transfer.phase': {'kind':'explicit_residuals','values':[]},
        'manufacturing.recipe_selection': {'kind':'explicit_order','recipes':[r['id'] for r in catalog['recipes']]},
        'manufacturing.input_slot_selection': {'kind':'explicit_order','slots':[f"{u['id']}:input:{i}" for u in data['layout']['units'] if u['kind'] in ('粉碎机','研磨机') for i in range(1 if u['kind']=='粉碎机' else 2)]},
        'initialization.warehouse_anchor': {'kind':'input_anchor','event':'build_0','side':'after'},
        'initialization.other_inventory': {'kind':'synthetic_seed','path':'initial_state.nonwarehouse','inventory_assumption':'empty_on_build'},
        'initialization.switches': {'kind':'input_settings','path':'settings','initial_values':'explicit_at_build'},
        'initialization.build_timing': {'kind':'input_history','path':'timeline'},
        'initialization.debug_end': {'kind':'input_witness','event':'debug_end','not_a_timing_strategy':True},
        'warehouse.external_supply': {'kind':'explicit_ore_history','events':[],'through':time_value(3),'basis':'初始80000足够本次4件出库；区间外补给历史不在本次回放范围'},
    }
    checker.require(set(supplied)=={a for a,r in profile['axes'].items() if r['disposition']=='由输入全称量化'},'配置输入接口集合变化，须显式迁移')
    values.update(supplied)
    checker.require(set(values)==set(checker.axis_registry()),'配置与输入字段不一致')
    return values


def make_poll_memory(data, catalog):
    kinds, units, ports, channels, _, _ = checker.geometry(data, catalog)
    order = {u:i for i,u in enumerate(data['construction']['selected_order'])}
    sides=[]
    for uid, unit in units.items():
        if unit['kind']=='供电桩': continue
        for side,key in [('input','target_port'),('output','source_port')]:
            members=[c['id'] for c in channels if ports[c[key]]['unit']==uid]
            members.sort(key=lambda cid:max(order[x.split(':')[0]] for x in cid.split('|')[1:]))
            graded=side=='input' or kinds[unit['kind']]['family']!='transport'
            lid=f"L|{uid}|{side}|{'other' if graded else 'ungraded'}"
            current=lid if members and (not graded or (uid=='feed_belt' and side=='input') or (uid=='ore_source' and side=='output')) else None
            sides.append({'unit':uid,'side':side,'graded':graded,'current_level':current,'levels':[{'id':lid,'members':members,'next_channel':members[0]}] if members else []})
    return {'schema':'poll-memory-v1','sides':sides}


def upgrade(data, catalog):
    """将指定合成结构升级；不从未知初态自动推可达性。"""
    data['schema']='kernel-input-v3'; data['purpose']='synthetic_execution'
    data['parameters']['profile_id']='kernel_profile_v1'
    # 所有输出带先建，供料带最后；之前没有任何仓库出库路径。
    order=data['construction']['selected_order']; order.remove('feed_belt'); order.append('feed_belt')
    by_unit={u['id']:u for u in data['layout']['units']}
    n=len(order)
    data['construction']['moments']=[{'event':f'build_{i}','unit':u,'placement':{k:by_unit[u][k] for k in ('kind','origin','rotation','port_layout','occupied_cells')}} for i,u in enumerate(order)]
    data['timeline']['events']=[{'id':f'build_{i}','kind':'build','time':time_value(i-n+1)} for i,u in enumerate(order)]+[{'id':e,'kind':e,'time':time_value(0)} for e in ('blueprint_complete','debug_end')]
    data['timeline']['relations']=[{'before':f'build_{i}','after':f'build_{i+1}','relation':'strict','basis':['候选实际历史，非玩家定时策略']} for i in range(n-1)]
    data['timeline']['relations'] += [{'before':f'build_{n-1}','after':'blueprint_complete','relation':'occurs_before','basis':['全部建成']},{'before':'blueprint_complete','after':'debug_end','relation':'occurs_before','basis':['无调试动作的有限历史'] }]
    data['timeline']['connection_events']=[]
    rank={u:i for i,u in enumerate(order)}
    for i,c in enumerate(data['layout']['physical_channels']):
        a,b=[c[k].split(':')[0] for k in ('source_port','target_port')]; later=max(rank[a],rank[b]); eid=f'connect_{i}'
        data['timeline']['events'].append({'id':eid,'kind':'connection_open','time':time_value(later-n+1)})
        data['timeline']['connection_events'].append({'event':eid,'channel':c['id'],'action':'open','cause':f'build_{later}','geometry_snapshot':data['layout']['id'],'construction_basis':decision({'source_build':f'build_{rank[a]}','target_build':f'build_{rank[b]}','later_build':f'build_{later}'},'规则 L28')})
        data['timeline']['relations'].append({'before':eid,'after':'blueprint_complete','relation':'occurs_before','basis':['建成后通道形成，运行扫描前完成']})
    data['layout']['post_debug']=decision(data['layout']['id'],'同几何、无调试动作的具体历史')
    values=profile_values(data,catalog)
    registry=checker.axis_registry()
    data['parameters'].update(fixed={},offline_mutable={},fixedness_unproven={})
    for name,row in registry.items():
        group='fixed' if name=='judgment.order' else row['group']
        data['parameters'][group][name]=decision(values[name], '受限模型声明；内核输入 §5.2–5.4；'+row['description'], 'derived' if name in ('connection.build_order','connection.order') else 'specified')
    data['initial_state']['anchor']=decision({'event':'build_0','side':'after'},'本例选核心建成锚点；不是蓝图默认')
    inventory=[];progress=[]
    kinds={k['id']:k for k in catalog['units']}
    for u in data['layout']['units']:
        kind=kinds[u['kind']]
        for row in kind['inventory']:
            if row['role']=='warehouse': continue
            for i in range(checker.quantity(row['count'])): inventory.append({'slot':f"{u['id']}:{row['role']}:{i}",'contents':[]})
        if kind['family']=='manufacturing': progress.append({'unit':u['id'],'phase':'idle','recipe':None,'candidate_recipes':[],'locked_recipe':None,'remaining':None,'cooldowns':[]})
    seed={'layout_snapshot':data['layout']['id'],'settings_anchor':data['settings']['anchor'], 'warehouse':copy.deepcopy(data['initial_state']['warehouse']), 'inventory':inventory,'progress':progress,
          'logistics':{'active_channels':[c['id'] for c in data['layout']['physical_channels']],'blocked_channels':[], 'poll_memory':decision(make_poll_memory(data,catalog),'规则 L29–32；内核输入 §6.3'),'gate_counters':[],'connection_order':decision('timeline_connection_history','规则接通；未发生离线','derived')},
          'environment':{'time':time_value(0),'stage':'zero_intervention','online':True,'withdrawal_memory':decision({'once_fired':[],'pending_rules':[]},'无拿取事件')},
          'semantic_context':{'arbitration':{'level_order':[l['id'] for side in make_poll_memory(data,catalog)['sides'] for l in side['levels']],'warehouse_empty_slot_order':[]},'parameter_values':[{'axis':a,'value':d,'lifetime':'F' if g=='fixed' else 'O' if g=='offline_mutable' else 'U'} for g in ('fixed','offline_mutable','fixedness_unproven') for a,d in data['parameters'][g].items()],
             'judgment_context':decision({'instant':time_value(0),'phase':'before_boundary','order_scope':'global','round':0,'next_template':0,'ordered_events':[],'next_event':None},'新时刻扫描前；无先前判定'),
             'pending_events':decision([],'所有单位初始空，无在制到期事件'),
             'tick_context':decision({'window_start':time_value(0),'window_end':time_value(1),'movements':[],'port_usage':[],'internal_passages':[]},'供料带此刻建成，尚未执行任何判定')}}
    data['initial_state']['nonwarehouse']=decision(seed,'候选合成状态：空库存来自 empty_on_build；历史推演见黄金轨迹 §2')
    data['initial_state']['reachability']=decision({'kind':'conditional_history','document':'混做粉碎机两下游-黄金轨迹.md','scope':'本输入历史及初值读法；不覆盖全部建造或调试时刻'},'黄金轨迹 §2；任务操作精度')
    data['environment']['offline']['event_domain']=decision({'kind':'selected_history','events':[]},'本次无离线见证，不排除其它历史')
    data['environment']['product_withdrawal']['policy']=decision({'schema':'withdrawal-policy-v1','rules':[],'selection':decision({'kind':'listed_order','rule_order':[]},'空规则集合'),'timing_family':{'kind':'imprecise','after':[],'before':[],'response':decision(None,'本有限实验不请求响应界','unresolved'),'interleaving':decision([],'无事件')},'admissibility':decision({'kind':'no_actions'},'未请求任何玩家动作')},'有限轨迹中无成品可拿取')
    return data


def write_profile(data):
    profile=Path(__file__).resolve().parents[2]/'规格/受限模型声明.md'
    registry=checker.load_json(profile.with_name('内核配置-v1.json'))
    value={'schema':'profile-assignment-v1','profile_id':'kernel_profile_v1','profile_source':{'path':'../../规格/受限模型声明.md','sha256':hashlib.sha256(profile.read_bytes()).hexdigest()},'axes':[]}
    for name,d in axis_values(data).items():
        v=d['value']; stop=isinstance(v,dict) and v.get('policy')=='stop'
        value['axes'].append({'axis':name,'decision':d,'disposition':registry['axes'][name]['disposition'],'coverage_loss':registry['axes'][name]['coverage_loss']})
    PROFILE_PATH.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def validate_runtime(data, catalog, ports, channels, buffers):
    require=checker.require; fields=checker.fields
    require(hashlib.sha256((BASE.parents[1]/'规格/内核配置-v1.json').read_bytes()).hexdigest()==SUPPORTED_PROFILE_SHA256,'unsupported: 受限配置字节已改变，须核对解释并迁移实现')
    values=axis_values(data); expected=profile_values(data,catalog)
    require(set(values)==set(expected),'运行参数不完整')
    for name,d in values.items():
        require(d['value']==expected[name],f'unsupported: 未实现的运行轴值: {name}')
    order=values['judgment.order']['value']
    all_templates=[('move',c['id']) for c in channels]+[('manufacture',u['id']) for u in data['layout']['units'] if u['kind'] in ('粉碎机','研磨机')]
    require(sorted((t['operation'],t['target']) for t in order['template_order'])==sorted(all_templates),'排序模板遗漏/重复')
    branch=values['damping.branch']['value']
    require(branch['choices']==[] and all(u['kind']!='分流器' for u in data['layout']['units']),'unsupported: 运行检查子集无阻尼分叉')
    seed=data['initial_state']['nonwarehouse']['value']
    fields(seed,'layout_snapshot settings_anchor warehouse inventory progress logistics environment semantic_context','StateSeed')
    require(seed['layout_snapshot']==data['layout']['id'] and seed['settings_anchor']==data['settings']['anchor'],'状态锚点不一致')
    require(seed['warehouse']==data['initial_state']['warehouse'],'unsupported: 初始仓库变化未经本检查器回放')
    expected_slots=[]; manufacturing=[]
    kinds={r['id']:r for r in catalog['units']}
    for u in data['layout']['units']:
        k=kinds[u['kind']]
        require(u['kind'] in ('协议核心','粉碎机','研磨机','传送带','供电桩','仓库取货口'),'unsupported: 运行例包含未支持机型')
        if k['family']=='manufacturing': manufacturing.append(u['id'])
        for row in k['inventory']:
            if row['role']=='warehouse':continue
            expected_slots += [f"{u['id']}:{row['role']}:{i}" for i in range(checker.quantity(row['count']))]
    require(sorted(r['slot'] for r in seed['inventory'])==sorted(expected_slots),'StateSeed 物品格缺失/重复')
    for r in seed['inventory']:
        fields(r,'slot contents','inventory')
        require(r['contents']==[],'unsupported: 本运行检查子集只接全空非仓库起点')
    require(sorted(r['unit'] for r in seed['progress'])==sorted(manufacturing),'StateSeed 进度缺失/重复')
    for r in seed['progress']:
        fields(r,'unit phase recipe candidate_recipes locked_recipe remaining cooldowns','progress')
        require(r=={'unit':r['unit'],'phase':'idle','recipe':None,'candidate_recipes':[],'locked_recipe':None,'remaining':None,'cooldowns':[]},'unsupported: 本运行检查子集只接 idle 起点')
    log=seed['logistics'];fields(log,'active_channels blocked_channels poll_memory gate_counters connection_order','logistics')
    require(sorted(log['active_channels'])==sorted(c['id'] for c in channels) and log['blocked_channels']==[] and log['gate_counters']==[],'运行通道/准入口状态不符')
    checker.decision(log['poll_memory'],{'specified'})
    require(log['poll_memory']['value']==make_poll_memory(data,catalog),'轮询记忆成员/侧/级/位置或当前级不符')
    require(log['connection_order']['status']=='derived' and log['connection_order']['value']=='timeline_connection_history','接通运行状态未绑定历史')
    env=seed['environment']; fields(env,'time stage online withdrawal_memory','state.environment')
    require(env['time']==time_value(0) and env['stage']=='zero_intervention' and env['online'] is True,'unsupported: 运行起点不在本子集')
    require(env['withdrawal_memory']['value']=={'once_fired':[],'pending_rules':[]},'运行拿取记忆不符')
    sem=seed['semantic_context']; fields(sem,'arbitration parameter_values judgment_context pending_events tick_context','semantic_context')
    exp=[{'axis':a,'value':d,'lifetime':'F' if g=='fixed' else 'O' if g=='offline_mutable' else 'U'} for g in ('fixed','offline_mutable','fixedness_unproven') for a,d in data['parameters'][g].items()]
    require(sem['arbitration']=={'level_order':[l['id'] for side in make_poll_memory(data,catalog)['sides'] for l in side['levels']], 'warehouse_empty_slot_order':[]},'级仲裁/空格选择状态不完整')
    require(sem['parameter_values']==exp,'当前轴值/生命周期与参数输入不一致')
    require(sem['judgment_context']['value']=={'instant':time_value(0),'phase':'before_boundary','order_scope':'global','round':0,'next_template':0,'ordered_events':[],'next_event':None},'起点排序上下文不完整')
    require(sem['pending_events']['status']=='specified' and sem['pending_events']['value']==[],'起点待事件不符')
    require(sem['tick_context']['value']=={'window_start':time_value(0),'window_end':time_value(1),'movements':[],'port_usage':[],'internal_passages':[]},'起点端口额度/内部穿越不符')
    require(data['initial_state']['anchor']['value']=={'event':'build_0','side':'after'},'仓库初始锚点不符')
    require(data['initial_state']['reachability']['value']['kind']=='conditional_history','可达性不得冒充全称证明')
    require(data['environment']['offline']['event_domain']['value']=={'kind':'selected_history','events':[]},'离线历史域不在本子集')
    policy=data['environment']['product_withdrawal']['policy']['value']
    require(policy['schema']=='withdrawal-policy-v1' and policy['rules']==[],'unsupported: 运行例不执行拿取策略')
    # 核实际建造时刻和供料首次连通；不能把调试中已运行的设备重置为空。
    event_map={e['id']:e for e in data['timeline']['events']}
    moments=data['construction']['moments']; n=len(moments)
    require(moments[-1]['unit']=='feed_belt','供料带必须为该历史最后建成者')
    for i,m in enumerate(moments):require(event_map[m['event']]['time']==time_value(i-n+1),'unsupported: 建造时刻不在已推演历史')
    for eid in ('blueprint_complete','debug_end'): require(event_map[eid]['time']==time_value(0),'运行边界不符')
    # 只计算正面积覆盖，额外触边供电不抵达标义务。
    powered={}
    for u in data['layout']['units']:
        if u['id'] not in manufacturing:continue
        w,h=[checker.quantity(kinds[u['kind']]['dimensions'][k]) for k in ('width','height')]
        if u['rotation'] in ('r90','r270'):w,h=h,w
        x,y=map(checker.quantity,u['origin'])
        powered[u['id']]=any(max(x,checker.quantity(p['origin'][0])-5)<min(x+w,checker.quantity(p['origin'][0])+7) and max(y,checker.quantity(p['origin'][1])-5)<min(y+h,checker.quantity(p['origin'][1])+7) for p in data['layout']['units'] if p['kind']=='供电桩')
    require(all(powered.values()),'运行制造单位未获 positive_area 供电')
    require(all(x['enabled'] for x in data['settings']['switches']),'unsupported: 本轨迹需要显式开启制造')
    return powered
