#!/usr/bin/env python3
"""第三轮运行输入的装配与有界检查接口；不作全称认证。"""
import copy
import hashlib
import json
from pathlib import Path
import check_examples as checker

BASE = Path(__file__).resolve().parent
PROFILE_PATH = BASE / 'kernel_profile_v1参数赋值.json'
SUPPORTED_PROFILE_SHA256 = '57bba234a6cae9daf65f2039532e855ef183e2b7a991837e99d89e8f311eb048'


def is_splitter(data):
    return data['scenario']['name'] == '分流器三路轮询'


def input_path(data):
    checker.require(data['scenario']['name'] in ('分流器三路轮询', '混做粉碎机两下游'), 'unsupported: 未支持的运行场景')
    return BASE / (data['scenario']['name'] + '.json')


def projection_path(data):
    return BASE / '分流器三路轮询-参数赋值.json' if is_splitter(data) else PROFILE_PATH


def tick_count(data):
    return 12 if is_splitter(data) else 4


def feed_units(data):
    return ['feed_splitter','probe_left','probe_bottom'] if is_splitter(data) else ['feed_belt']


def build_time(data,index,count):
    return 0 if index>=count-len(feed_units(data)) else index-count+len(feed_units(data))


def quantity(value, category='候选'):
    return {'value': str(value), 'category': category}


def time_value(value):
    return {'kind': 'rational', 'value': quantity(value)}


def decision(value, basis, status='specified'):
    return {'status': status, 'value': value, 'basis': [basis]}


def same_json(left, right):
    return json.dumps(left,sort_keys=True,ensure_ascii=False)==json.dumps(right,sort_keys=True,ensure_ascii=False)


def axis_values(data):
    return {name: value for group in ('fixed', 'offline_mutable', 'fixedness_unproven') for name, value in data['parameters'][group].items()}


def templates(data):
    # 模板顺序是显式实验输入，不由实例字符串默定。
    channels = data['layout']['physical_channels']
    source_order = ['ore_source', 'feed_belt', 'crusher', 'belt_a0', 'belt_a1', 'belt_a2', 'belt_b0', 'belt_b1', 'belt_b2', 'belt_b3']
    if is_splitter(data):
        source_order = ['ore_source', 'feed_splitter', 'south_box', 'splitter', 'probe_left_source', 'probe_bottom_source', 'probe_left', 'probe_bottom', 'probe_merger', 'probe_gate_a', 'probe_gate_b', 'north_box', 'east_box', 'west_box', 'probe_box']
    moves = [{'operation': 'move', 'target': c['id']} for u in source_order for c in channels if c['source_port'].split(':')[0] == u]
    if is_splitter(data):
        # 同刻两个探针分流器都先访问准入口，再访问汇流器。
        moves.sort(key=lambda t:(source_order.index(t['target'].split('|')[1].split(':')[0]), 'probe_gate' not in t['target']))
    manufactures = [{'operation': 'manufacture', 'target': u['id']} for u in data['layout']['units'] if u['kind'] in ('粉碎机', '研磨机')]
    return moves + manufactures + [{'operation':'transfer','target':u['id']} for u in data['layout']['units'] if u['kind']=='协议储存箱']


def reference_branches(data):
    # 有限参考只覆盖此显式参数点，未声称枚举了分支族。
    import itertools
    rows=[]
    for unit in data['layout']['units']:
        if unit['kind']!='分流器':continue
        edges=sorted(c['id'] for c in data['layout']['physical_channels'] if c['source_port'].split(':')[0]==unit['id'])
        for n in range(1,len(edges)+1):
            for subset in itertools.combinations(edges,n):
                rows.append(dict(fork_unit=unit['id'],available_channels=list(subset),outgoing_channel=subset[0]))
    return rows


def profile_values(data, catalog):
    profile = checker.load_json(BASE.parents[1]/'规格/内核配置-v1.json')
    values = {name: copy.deepcopy(row['value']) for name,row in profile['axes'].items() if row['disposition'] != '由输入全称量化'}
    supplied = {
        'judgment.order': {'schema':'event-order-v1','scope':'global','template_order':templates(data),'repeat_embedding':'scan_round_then_template','instant_overrides':[]},
        'damping.branch': {'schema':'damping-branch-v2','fixedness':'by_available_set','choices':reference_branches(data),'evaluations':[],'on_missing':'unresolved'},
        'connection.build_order': 'construction.selected_order',
        'connection.order': 'timeline_connection_history',
        'connection.tie': {'kind':'explicit_order','channels':[c['id'] for c in data['layout']['physical_channels']]},
        'connection.belt_shape': {'kind':'layout_build_history','values':[{'unit':u['id'],'build_event':next(m['event'] for m in data['construction']['moments'] if m['unit']==u['id']),'shape':{0:'straight',1:'turn_left',2:'turn_right'}[u['port_layout']]} for u in data['layout']['units'] if u['kind']=='传送带']},
        'transfer.phase': {'kind':'explicit_residuals','values':[{'unit':u['id'],'slot':None,'remaining':time_value(0)} for u in data['layout']['units'] if u['kind']=='协议储存箱']},
        'manufacturing.recipe_selection': {'kind':'explicit_order','recipes':[r['id'] for r in catalog['recipes']]},
        'manufacturing.input_slot_selection': {'kind':'explicit_order','slots':[f"{u['id']}:input:{i}" for u in data['layout']['units'] if u['kind'] in ('粉碎机','研磨机') for i in range(1 if u['kind']=='粉碎机' else 2)]},
        'initialization.warehouse_anchor': {'kind':'input_anchor','event':'build_0','side':'after'},
        'initialization.other_inventory': {'kind':'synthetic_seed','path':'initial_state.nonwarehouse','inventory_assumption':'empty_on_build'},
        'initialization.switches': {'kind':'input_settings','path':'settings','initial_values':'explicit_at_build'},
        'initialization.build_timing': {'kind':'input_history','path':'timeline'},
        'initialization.debug_end': {'kind':'input_witness','event':'debug_end','not_a_timing_strategy':True},
        'warehouse.external_supply': {'kind':'explicit_ore_history','events':[],'through':time_value(tick_count(data)-1)},
    }
    checker.require(set(supplied)=={a for a,r in profile['axes'].items() if r['disposition']=='由输入全称量化'},'配置输入接口集合变化，须显式迁移')
    values.update(supplied)
    checker.require(set(values)==set(checker.axis_registry()),'配置与输入字段不一致')
    return values


def validate_decision_tree(value, name='root'):
    """所有嵌套 Decision 先核封套；可运行状态另核所需已解状态。"""
    if isinstance(value, dict):
        if 'status' in value and ('value' in value or 'basis' in value) and '.bridge_axes.' not in name:
            try:checker.decision(value, nullable=name.endswith('.empty_identity'))
            except checker.CheckError as error:raise checker.CheckError('Decision '+name+': '+str(error)) from error
        for key, child in value.items():
            validate_decision_tree(child, name+'.'+key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            validate_decision_tree(child, name+f'[{index}]')


def empty_slot_ids(warehouse):
    result=[]
    for row in warehouse['slots']:
        if row['item'] is None:
            checker.decision(row['empty_identity'], {'specified'}, nullable=True)
            if row['empty_identity']['value'] is None:
                result.append(row['slot'])
    return result


def make_poll_memory(data, catalog, seed=None, only_units=None):
    """从实际库存、格选择、滞留及端口预算派生参考子集的当前可动级。"""
    kinds, units, ports, channels, _, _ = checker.geometry(data, catalog)
    order = {u:i for i,u in enumerate(data['construction']['selected_order'])}
    params=axis_values(data)
    ties=params['connection.tie']['value']['channels']
    warehouse={r['slot']:r for r in (seed['warehouse'] if seed else data['initial_state']['warehouse'])['slots']}
    inv={r['slot']:r['contents'] for r in seed['inventory']} if seed else {}
    checker.validate_slot_identity(seed['warehouse'] if seed else data['initial_state']['warehouse'], inv)
    assignments={r['port']:r['slot'] for r in data['settings']['warehouse_assignments']}
    usage={r['port']:checker.quantity(r['quantity']) for r in seed['semantic_context']['tick_context']['value']['port_usage']} if seed else {}
    time=checker.quantity(seed['environment']['time']['value'],integer=False) if seed else 0

    def physical(channel):
        source,target=channel['source_port'],channel['target_port']
        if usage.get(source,0) or usage.get(target,0):return False
        uid=ports[source]['unit'];kind=units[uid]['kind'];family=kinds[kind]['family']
        if kind in ('协议核心','仓库取货口'):
            row=warehouse[assignments[source]]
            if row['item'] is None or checker.quantity(row['quantity'])==0:return False
            item=row['item']
        else:
            slot=next((s for s in inv if s.startswith(uid+':storage:') and inv[s]), None) if kind=='协议储存箱' else f"{uid}:{ports[source]['axis'] if kind=='桥接器' else 'transport' if family=='transport' else 'output'}:0"
            rows=inv.get(slot,[])
            if not rows:return False
            row=rows[0];item=row['item']
            if row.get('last_unit') == ports[target]['unit']:return False
            if checker.quantity(row['quantity'])<=0:return False
            if family=='transport':
                checker.require(row['entered_at'] is not None,'运输物品缺入格时刻')
                if time-checker.quantity(row['entered_at']['value'],integer=False)<1:return False
        uid=ports[target]['unit'];family=kinds[units[uid]['kind']]['family']
        if family=='transport':slots=[f"{uid}:{ports[target]['axis'] or 'transport'}:0"];capacity=1
        elif units[uid]['kind']=='协议储存箱':
            slots=[s for s in inv if s.startswith(uid+':storage:')];capacity=50
            return any(not inv[s] or (inv[s][0]['item']==item and checker.quantity(inv[s][0]['quantity'])<capacity) for s in slots)
        else:
            checker.require(family=='manufacturing','unsupported: 初态检查不含PC入库')
            if any(r['item']==item for r in inv.get(f'{uid}:output:0',[])):return False
            slots=[x for x in params['manufacturing.input_slot_selection']['value']['slots'] if x.startswith(uid+':')];capacity=50
        same=[x for x in slots if inv.get(x) and inv[x][0]['item']==item]
        available=same or [x for x in slots if not inv.get(x)]
        return bool(available) and sum(checker.quantity(r['quantity']) for r in inv.get(available[0],[]))<capacity

    from polling_reference import build_sides, refresh_sides
    cmap={c['id']:c for c in channels}
    memory=build_sides(data,kinds,units,ports,channels)
    if only_units is not None:
        memory['sides']=[s for s in memory['sides'] if s['unit'] in only_units]
    arbitration=seed['semantic_context']['arbitration']['level_order'] if seed else [l['id'] for s in memory['sides'] for l in s['levels']]
    refresh_sides(data,memory['sides'],lambda cid:physical(cmap[cid]),arbitration)
    return memory


def upgrade(data, catalog):
    """将指定合成结构升级；不从未知初态自动推可达性。"""
    data['schema']='kernel-input-v3'; data['purpose']='synthetic_execution'
    data['parameters']['profile_id']='kernel_profile_v1'
    # 入口运输单位最后建成；之前没有任何仓库出库路径。
    order=data['construction']['selected_order']
    for uid in feed_units(data):order.remove(uid)
    order.extend(feed_units(data))
    by_unit={u['id']:u for u in data['layout']['units']}
    n=len(order)
    data['construction']['moments']=[{'event':f'build_{i}','unit':u,'placement':{k:by_unit[u][k] for k in ('kind','origin','rotation','port_layout','occupied_cells')}} for i,u in enumerate(order)]
    data['timeline']['events']=[{'id':f'build_{i}','kind':'build','time':time_value(build_time(data,i,n))} for i,u in enumerate(order)]+[{'id':e,'kind':e,'time':time_value(0)} for e in ('blueprint_complete','debug_end')]
    data['timeline']['relations']=[{'before':f'build_{i}','after':f'build_{i+1}','relation':'occurs_before' if build_time(data,i,n)==build_time(data,i+1,n) else 'strict','basis':['候选实际历史，非玩家定时策略']} for i in range(n-1)]
    data['timeline']['relations'] += [{'before':f'build_{n-1}','after':'blueprint_complete','relation':'occurs_before','basis':['全部建成']},{'before':'blueprint_complete','after':'debug_end','relation':'occurs_before','basis':['无调试动作的有限历史'] }]
    data['timeline']['connection_events']=[]
    rank={u:i for i,u in enumerate(order)}
    for i,c in enumerate(data['layout']['physical_channels']):
        a,b=[c[k].split(':')[0] for k in ('source_port','target_port')]; later=max(rank[a],rank[b]); eid=f'connect_{i}'
        data['timeline']['events'].append({'id':eid,'kind':'connection_open','time':time_value(build_time(data,later,n))})
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
        if kind['family']=='manufacturing' or u['kind']=='协议储存箱': progress.append({'unit':u['id'],'phase':'idle','recipe':None,'candidate_recipes':[],'locked_recipe':None,'remaining':None,'cooldowns':[{'slot':None,'remaining':time_value(0)}] if u['kind']=='协议储存箱' else []})
    seed={'layout_snapshot':data['layout']['id'],'settings_anchor':data['settings']['anchor'], 'warehouse':copy.deepcopy(data['initial_state']['warehouse']), 'inventory':inventory,'progress':progress,
          'logistics':{'active_channels':[c['id'] for c in data['layout']['physical_channels']],'blocked_channels':[], 'poll_memory':decision(make_poll_memory(data,catalog),'规则 L29–32；内核输入 §6.3'),'gate_counters':[{'unit':u['id'],'total_received':quantity(0),'window_received':quantity(0),'window_started_at':None,'blocked_reasons':[]} for u in data['layout']['units'] if u['kind']=='物品准入口'],'connection_order':decision('timeline_connection_history','规则接通；未发生离线','derived')},
          'environment':{'time':time_value(0),'stage':'zero_intervention','online':True,'withdrawal_memory':decision({'once_fired':[],'pending_rules':[]},'无拿取事件')},
          'semantic_context':{'arbitration':{'level_order':[l['id'] for side in make_poll_memory(data,catalog)['sides'] for l in side['levels']],'warehouse_empty_slot_order':[]},'parameter_values':[{'axis':a,'value':d,'lifetime':'F' if g=='fixed' else 'O' if g=='offline_mutable' else 'U'} for g in ('fixed','offline_mutable','fixedness_unproven') for a,d in data['parameters'][g].items()],
             'judgment_context':decision({'instant':time_value(0),'phase':'before_boundary','order_scope':'global','round':0,'next_template':0,'ordered_events':[],'next_event':None},'新时刻扫描前；无先前判定'),
             'pending_events':decision([],'所有单位初始空，无在制到期事件'),
             'tick_context':decision({'window_start':time_value(0),'window_end':time_value(1),'movements':[],'port_usage':[],'internal_passages':[]},'供料带此刻建成，尚未执行任何判定')}}
    data['initial_state']['nonwarehouse']=decision(seed,'候选合成状态：空库存来自 empty_on_build；历史推演见黄金轨迹 §2')
    data['initial_state']['reachability']=decision({'kind':'conditional_history','document':'分流器三路轮询-运行说明.md' if is_splitter(data) else '混做粉碎机两下游-黄金轨迹.md','scope':'本输入历史及初值读法；不覆盖全部建造或调试时刻'},'黄金轨迹 §2；任务操作精度')
    data['environment']['offline']['event_domain']=decision({'kind':'selected_history','events':[]},'本次无离线见证，不排除其它历史')
    data['environment']['product_withdrawal']['policy']=decision({'schema':'withdrawal-policy-v1','rules':[],'selection':decision({'kind':'listed_order','rule_order':[]},'空规则集合'),'timing_family':{'kind':'imprecise','after':[],'before':[],'response':decision(None,'本有限实验不请求响应界','unresolved'),'interleaving':decision([],'无事件')},'admissibility':decision({'kind':'no_actions'},'未请求任何玩家动作')},'有限轨迹中无成品可拿取')
    return data


def profile_projection(data):
    specification=BASE.parents[1]/'规格/受限模型声明.md'
    configuration=specification.with_name('内核配置-v1.json')
    registry=checker.load_json(configuration)
    source=lambda path:{'path':str(Path('../../规格')/path.name),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return {'schema':'profile-assignment-v2','profile_id':'kernel_profile_v1',
            'profile_source':source(specification),'configuration_source':source(configuration),
            'axis_source':source(checker.AXIS_PATH),
            'axes':[{'axis':name,'decision':d,'disposition':registry['axes'][name]['disposition'],
                     'coverage_loss':registry['axes'][name]['coverage_loss']} for name,d in axis_values(data).items()]}


def write_profile(data):
    projection_path(data).write_text(json.dumps(profile_projection(data),ensure_ascii=False,indent=2)+'\n')


def validate_profile(data, profile):
    # 不刷新声明中的旧哈希：先完整核来源链、每项决定及覆盖说明。
    checker.require(same_json(profile,profile_projection(data)),'参数投影来源/逐轴值/处置/覆盖损失不符，须重新核验后迁移')
    return profile


def validate_runtime(data, catalog, ports, channels, buffers):
    require=checker.require; fields=checker.fields
    require(hashlib.sha256((BASE.parents[1]/'规格/内核配置-v1.json').read_bytes()).hexdigest()==SUPPORTED_PROFILE_SHA256,'unsupported: 受限配置字节已改变，须核对解释并迁移实现')
    validate_decision_tree(data)
    values=axis_values(data); expected=profile_values(data,catalog)
    require(set(values)==set(expected),'运行参数不完整')
    for name,d in values.items():
        require(same_json(d['value'],expected[name]),f'unsupported: 未实现的运行轴值: {name}')
    order=values['judgment.order']['value']
    all_templates=[(t['operation'],t['target']) for t in templates(data)]
    require(sorted((t['operation'],t['target']) for t in order['template_order'])==sorted(all_templates),'排序模板遗漏/重复')
    branch=values['damping.branch']['value']
    require(branch['choices']==reference_branches(data), 'unsupported: 参考仅覆盖明确首支优先的局部表；本样例不请求多级阻尼')
    if is_splitter(data):
        require(data['settings']['gates']==[{'unit':uid,'item':'源矿','total_limit':None,'window_limit':quantity(1)} for uid in ('probe_gate_a','probe_gate_b')], 'unsupported: 门控参考只覆盖源矿/窗口1/无累计限制')
        warehouse_items={r['slot']:r['item'] for r in data['initial_state']['warehouse']['slots']}
        require(all(warehouse_items[a['slot']]=='源矿' for a in data['settings']['warehouse_assignments'] if a['port'].startswith(('probe_left_source:','probe_bottom_source:'))), 'unsupported: 参考未执行身份不符的维护分支')
    seed=data['initial_state']['nonwarehouse']['value']
    fields(seed,'layout_snapshot settings_anchor warehouse inventory progress logistics environment semantic_context','StateSeed')
    checker.validate_slot_identity(seed['warehouse'], [r['slot'] for r in seed['inventory']])
    require(seed['layout_snapshot']==data['layout']['id'] and seed['settings_anchor']==data['settings']['anchor'],'状态锚点不一致')
    require(seed['warehouse']==data['initial_state']['warehouse'],'unsupported: 初始仓库变化未经本检查器回放')
    expected_slots=[]; manufacturing=[]
    kinds={r['id']:r for r in catalog['units']}
    for u in data['layout']['units']:
        k=kinds[u['kind']]
        require(u['kind'] in ('协议核心','粉碎机','研磨机','传送带','供电桩','仓库取货口','分流器','协议储存箱','汇流器','物品准入口'),'unsupported: 运行例包含未支持机型')
        if k['family']=='manufacturing' or u['kind']=='协议储存箱': manufacturing.append(u['id'])
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
        require(r=={'unit':r['unit'],'phase':'idle','recipe':None,'candidate_recipes':[],'locked_recipe':None,'remaining':None,'cooldowns':[{'slot':None,'remaining':time_value(0)}] if next(u['kind'] for u in data['layout']['units'] if u['id']==r['unit'])=='协议储存箱' else []},'unsupported: 本运行检查子集只接 idle 起点')
    log=seed['logistics'];fields(log,'active_channels blocked_channels poll_memory gate_counters connection_order','logistics')
    checker.decision(seed['semantic_context']['tick_context'], {'specified'})
    require(seed['semantic_context']['tick_context']['value']=={'window_start':time_value(0),'window_end':time_value(1),'movements':[],'port_usage':[],'internal_passages':[]},'起点端口额度/内部穿越不符')
    require(sorted(log['active_channels'])==sorted(c['id'] for c in channels) and log['blocked_channels']==[] and log['gate_counters']==[{'unit':u['id'],'total_received':quantity(0),'window_received':quantity(0),'window_started_at':None,'blocked_reasons':[]} for u in data['layout']['units'] if u['kind']=='物品准入口'],'运行通道/准入口状态不符')
    checker.decision(log['poll_memory'],{'specified'})
    require(same_json(log['poll_memory']['value'],make_poll_memory(data,catalog,seed)),'轮询记忆成员/侧/级/位置或当前级不符')
    checker.decision(log['connection_order'], {'derived'})
    require(log['connection_order']['status']=='derived' and log['connection_order']['value']=='timeline_connection_history','接通运行状态未绑定历史')
    env=seed['environment']; fields(env,'time stage online withdrawal_memory','state.environment')
    require(env['time']==time_value(0) and env['stage']=='zero_intervention' and env['online'] is True,'unsupported: 运行起点不在本子集')
    checker.decision(env['withdrawal_memory'], {'specified'})
    require(env['withdrawal_memory']['value']=={'once_fired':[],'pending_rules':[]},'运行拿取记忆不符')
    sem=seed['semantic_context']; fields(sem,'arbitration parameter_values judgment_context pending_events tick_context','semantic_context')
    exp=[{'axis':a,'value':d,'lifetime':'F' if g=='fixed' else 'O' if g=='offline_mutable' else 'U'} for g in ('fixed','offline_mutable','fixedness_unproven') for a,d in data['parameters'][g].items()]
    fields(sem['arbitration'],'level_order warehouse_empty_slot_order','arbitration')
    level_ids=[l['id'] for side in make_poll_memory(data,catalog,seed)['sides'] for l in side['levels']]
    for key,expected_ids in [('level_order',level_ids),('warehouse_empty_slot_order',empty_slot_ids(seed['warehouse']))]:
        rows=sem['arbitration'][key]
        require(isinstance(rows,list) and len(rows)==len(set(rows)) and set(rows)==set(expected_ids),'级仲裁/空格选择状态不完整')
    for key in ('judgment_context','pending_events','tick_context'):
        checker.decision(sem[key], {'specified'})
    require(same_json(sorted(sem['parameter_values'],key=lambda row:row['axis']),sorted(exp,key=lambda row:row['axis'])),'当前轴值/生命周期与参数输入不一致')
    require(same_json(sem['judgment_context']['value'],{'instant':time_value(0),'phase':'before_boundary','order_scope':'global','round':0,'next_template':0,'ordered_events':[],'next_event':None}),'起点排序上下文不完整')
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
    require([m['unit'] for m in moments[-len(feed_units(data)):]]==feed_units(data),'供料带必须为该历史最后建成者')
    for i,m in enumerate(moments):require(event_map[m['event']]['time']==time_value(build_time(data,i,n)),'unsupported: 建造时刻不在已推演历史')
    for eid in ('blueprint_complete','debug_end'): require(event_map[eid]['time']==time_value(0),'运行边界不符')
    # 只计算正面积覆盖，额外触边供电不抵达标义务。
    powered={}
    for u in data['layout']['units']:
        if u['id'] not in manufacturing:continue
        w,h=[checker.quantity(kinds[u['kind']]['dimensions'][k]) for k in ('width','height')]
        if u['rotation'] in ('r90','r270'):w,h=h,w
        x,y=map(checker.quantity,u['origin'])
        powered[u['id']]=any(max(x,checker.quantity(p['origin'][0])-5)<min(x+w,checker.quantity(p['origin'][0])+7) and max(y,checker.quantity(p['origin'][1])-5)<min(y+h,checker.quantity(p['origin'][1])+7) for p in data['layout']['units'] if p['kind']=='供电桩')
    require(all(powered[uid] for uid in powered if next(u['kind'] for u in data['layout']['units'] if u['id']==uid)!='协议储存箱'),'运行制造单位未获 positive_area 供电')
    require(all(x['enabled'] == (x['function']=='manufacture') for x in data['settings']['switches']),'unsupported: 本轨迹制造须开、箱体传输须关')
    return powered
