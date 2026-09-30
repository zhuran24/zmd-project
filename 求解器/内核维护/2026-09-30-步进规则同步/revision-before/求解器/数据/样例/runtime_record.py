"""有限运行记录的来源闭合、逐轴覆盖及完整重算关联校验。"""
import copy
import hashlib
import json
from pathlib import Path
import check_examples as checker
from runtime_example import PROFILE_PATH, axis_values, quantity, time_value, validate_profile, validate_decision_tree, input_path, projection_path, is_splitter, tick_count

BASE = Path(__file__).resolve().parent
SPEC = BASE.parents[1] / '规格'


def same(left, right):
    # JSON 类型也必须相同，不能让 Python 的 True == 1 掩盖非法参数。
    return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)


def fingerprints(data):
    paths = [('input', input_path(data)), ('catalog', BASE.parent/'正式静态目录.json'),
             ('axis_registry', checker.AXIS_PATH), ('profile', SPEC/'受限模型声明.md'),
             ('profile', SPEC/'内核配置-v1.json'), ('parameter_projection', projection_path(data)),
             ('golden', BASE/'混做粉碎机两下游-黄金轨迹.json'), ('golden', BASE/'混做粉碎机两下游-黄金轨迹.md'),
             ('semantics', SPEC/'受限转移定义.md'), ('semantics', SPEC/'运行语义.md'),
             ('semantics', SPEC/'内核输入.md'), ('semantics', SPEC/'内核输出.md'),
             ('schema', SPEC/'内核输出.schema.json')]
    if is_splitter(data):
        paths = [(role, path) for role, path in paths if role!='golden']
        paths.append(('semantics', BASE/'分流器三路轮询-运行说明.md'))
    paths += [('checker', BASE/name) for name in
              ('check_golden_trace.py', 'runtime_example.py', 'check_examples.py', 'runtime_record.py', 'event_order.py', 'test_runtime_input.py', 'checkpoint_delta.py', 'check_port_meeting.py', 'check_splitter_trace.py', 'test_round4.py', 'polling_reference.py', 'ledger_reference.py')]
    paths += [('formal_source', checker.ROOT/name) for name in checker.SOURCE_HASHES]
    return [{'role': role, 'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for role, path in paths]


def coverage(data, ticks, profile):
    events = [event for tick in ticks for event in tick['events']]
    moves = [e['event'] for e in events if e['operation']=='move' and e['outcome']=='success']
    manufactures = [e['event'] for e in events if e['operation']=='manufacture' and e['outcome']=='success']
    completes = [e['event'] for e in events if e['operation']=='manufacture_complete']
    failures = [e['event'] for e in events if e['operation']=='move' and e['outcome']=='failure']
    exercised = {}
    for name in ('time.domain','time.instant_order','time.retry_schedule','time.instant_end','time.boundary',
                 'judgment.order_scope','judgment.order','polling.dual_permission','polling.memory_scope',
                 'polling.eligibility_stage','residence.nontransport'):
        exercised[name] = moves
    for name in ('judgment.buffer_event_class','manufacturing.port_slot_relation','manufacturing.input_mixing',
                 'manufacturing.input_capacity_scope','manufacturing.recipe_match_scope',
                 'manufacturing.recipe_completeness','manufacturing.recipe_lock_time',
                 'manufacturing.input_collection','cascade.buffer'):
        exercised[name] = manufactures
    exercised['time.manufacture_events'] = completes
    exercised['polling.both_failure'] = failures
    exercised['polling.ungraded_blocked'] = failures
    exercised['polling.membership_change'] = [e['event'] for e in events if e['operation']=='gate_window_expiry']
    checked = {'connection.build_order','connection.order','connection.tie','connection.port_meeting',
               'connection.belt_shape','polling.initial_cursor','polling.direct_peer',
               'initialization.warehouse_anchor','initialization.other_inventory','initialization.switches',
               'initialization.build_timing','initialization.debug_end','warehouse.capacity','power.cell_rule'}
    rows=[]
    for row in profile['axes']:
        name=row['axis']; disposition=row['disposition']
        status='not_exercised'
        evidence=['本次未记录此机制的运行验证；赋值和静态相容检查不等于行为已验证。']
        if name in exercised and exercised[name]:
            status='exercised'; evidence=exercised[name]
        elif name in checked:
            status='input_checked'; evidence=['输入、目录和条件历史的装载检查；不代表遍历全部取值或历史。']
        if name.startswith('transfer.'):
            status='not_exercised'; evidence=['没有成功传输：粉碎机布局无箱；分流器布局箱体传输显式关闭，仅检查模板守卫，不验证冷却/相位后效。']
        elif name.startswith('damping.'):
            status='not_exercised'; evidence=['参考执行只处理单级通道，没有调用阻尼求值器；有传送带不等于已验证元件计数。']
        elif name=='polling.level_tie':
            evidence=[e['event'] for e in events if any(b.startswith('polling.level_tie=fixed_arbitration:') for b in e['basis'])]
            status='exercised' if evidence else 'not_exercised'
            if not evidence:evidence=['本次没有实际多可动级同键平局']
        elif name.startswith('bridge.') or name.startswith('connection.bridge'):
            status='not_exercised'; evidence=['本运行输入无桥接器；其它样例的结果不并入本次运行覆盖。']
        elif name.startswith('gate.'):
            evidence=[e['event'] for e in events if e['operation']=='gate_window_expiry'] if name in ('gate.concurrent_expiry','gate.window_clock','gate.window_recovery','gate.reconnect_record') else []
            status='exercised' if evidence else 'not_exercised'
            if not evidence:evidence=['本次未记录此门控机制的运行证据，不能用存在准入口代替触发。']
        elif name.startswith('polling.split_merge'):
            if is_splitter(data):
                uid='probe_merger' if name=='polling.split_merge_scope' else 'feed_splitter' if name=='polling.split_merge_singleton' else 'splitter'
                evidence=[e['event'] for e in events if e['operation']=='move' and e['outcome'] in ('success','failure') and ((uid=='probe_merger' and e['target'].split('|')[2].startswith('probe_merger:')) or e['target'].startswith('PC|'+uid+':'))]
                status='exercised' if evidence else 'not_exercised'
                if name=='polling.split_merge_scope':
                    evidence+=['两个直连分流器使汇流器存货侧形成两个单成员级，各级sole_member独立起轮；跨级仲裁不取代级内指针。']
            else:
                status='not_exercised'; evidence=['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
        if name=='connection.port_meeting':
            from check_port_meeting import compare_meeting
            comparison=compare_meeting(data,checker.load_json(BASE.parent/'正式静态目录.json'))
            status='input_checked';evidence=[comparison['status'], '额外角接对数='+str(len(comparison['corner_pairs']))+'；本记录仅执行shared_edge_opposite']
        if disposition=='超出覆盖即停':
            status='stop_not_triggered'
            evidence += ['所填 stop 是遇到对应机制即停止的工程处置；本轨迹未触及，不证明后效。']
        if name=='warehouse.periodic_lift':
            status='proof_pending'; evidence=['只核有限前缀，完整仓库周期提升没有证明；请求提升即停止。']
        rows.append({'axis':name,'reason':row['coverage_loss'],'disposition':disposition,
                     'coverage_status':status,'evidence':evidence,
                     'other_values':'已定域无其它值；未运行结构仍未验证' if disposition=='已定' else '本次未覆盖其它值及其联合组合'})
    return rows


def build_record(data, ticks, golden=None):
    validate_event_identity(data['timeline'], data['initial_state']['nonwarehouse']['value'], ticks)
    if golden is not None:
        checker.require([t['summary'] for t in ticks]==golden['ticks'], '黄金轨迹与有限重算不同')
    profile=validate_profile(data, checker.load_json(projection_path(data)))
    batches=sum(e['operation']=='manufacture_complete' for t in ticks for e in t['events'])
    return {'schema':'kernel-output-v4',
            'evidence_scope':{'kind':'diagnostic','direction':'diagnostic',
                'support_domain':['两个显式有限参考场景；逐事件重算，不覆盖桥或完整工厂'],
                'fixed_parameter_lifecycle':'按当前配置的固定参数与输入组，有限前缀内无离线或玩家动作',
                'context_bindings':[{'path':r['path'],'sha256':r['sha256']} for r in fingerprints(data)],
                'initial_state_coverage':{'description':'一个显式种子的有限前缀','exact_reachable_set_enumerated':False},
                'review_status':'author_checked','proof_sources':[]},'execution_mode':'finite_concrete','port_meeting':'shared_edge_opposite','run_id':'splitter_prefix_0_11' if is_splitter(data) else 'mixed_crusher_prefix_0_3','profile_id':data['parameters']['profile_id'],
            'producer':{'kind':'bounded_reference_checker','path':str(BASE/('check_splitter_trace.py' if is_splitter(data) else 'check_golden_trace.py')),
                        'claim':'有限重算；有黄金时另作手工摘要比较；不是 Rust 内核结果'},
            'status':'completed','fingerprints':fingerprints(data),'parameter_assignment':data['parameters'],
            'input_history':{**{k:data[k] for k in ('timeline','construction','debug_operations','environment')},
                             'reachability':data['initial_state']['reachability']},
            'uncovered_axes':coverage(data,ticks,profile),
            'trace':{'start_state':data['initial_state']['nonwarehouse']['value'],'ticks':ticks,
                     'end_time':ticks[-1]['time'],'format':'full_state_each_instant'},
            'validation_scope':{'kind':'finite_trace','from':ticks[0]['time'],'through':ticks[-1]['time'],
                 'golden_match':golden is not None,'initial_history':'conditional_witness','universal_parameters':False,
                 'all_reachable_cycles':False,'target_certified':False,
                 'manufacturing_cycles_completed':quantity(batches,'算术推论')},
            'open_items':(['无线传输关闭，未验证transfer.*运行后效','窗口恢复与级仲裁只有本输入有限轨迹证据，未覆盖其它次序及联合组合'] if is_splitter(data) else ['未覆盖实际混做与下游生产']) + ['端口相遇两读法PC集合仍不同，详见第四轮前置-疑问记录.md','未覆盖离线、其它初态与判定顺序',
                          '有限重算不替代全部可达循环和完整目标认证']}


def validate_state(data, state):
    validate_decision_tree(state)
    checker.validate_slot_identity(state['warehouse'], [r['slot'] for r in state['inventory']])
    catalog=checker.load_json(BASE.parent/'正式静态目录.json')
    kinds,units,ports,channels,buffers,_=checker.geometry(data,catalog)
    expected={}
    for uid,u in units.items():
        for row in kinds[u['kind']]['inventory']:
            if row['role']=='warehouse':continue
            for i in range(checker.quantity(row['count'])):
                expected[f"{uid}:{row['role']}:{i}"]=row['capacity']
    checker.require(len(state['inventory'])==len(expected) and {r['slot'] for r in state['inventory']}==set(expected),'状态物品格集合不符')
    for row in state['inventory']:
        count=sum(checker.quantity(r['quantity']) for r in row['contents'])
        checker.require(all(checker.quantity(r['quantity'])>0 for r in row['contents']),'状态库存数量非法')
        cap=expected[row['slot']]
        if cap is not None:
            checker.require(count<=checker.quantity(cap),'状态物品格超容量: '+row['slot'])
    occupied={}
    for row in state['inventory']:
        uid,role,_=row['slot'].split(':')
        if role=='buffer':continue
        items={content['item'] for content in row['contents']}
        checker.require(len(items)<=1,'普通物品格混种')
        if kinds[units[uid]['kind']]['inventory_rules']['same_item_across_slots']=='exempt':continue
        for item in items:
            key=(uid,item)
            checker.require(key not in occupied,'同单位同种物品跨普通格重复')
            occupied[key]=row['slot']
    for row in state['warehouse']['slots']:
        n=checker.quantity(row['quantity'])
        checker.require(0<=n<=80000 and (row['item'] is None)==(n==0),'状态仓库容量/物种不符')
    tc=state['semantic_context']['tick_context']['value']; cmap={r['id']:r for r in channels};usage={}
    for move in tc['movements']:
        checker.require(move['channel'] in cmap and checker.quantity(move['quantity'])==1,'成功移动记录非法')
        for key in ('source_port','target_port'):
            port=cmap[move['channel']][key];usage[port]=usage.get(port,0)+1
    rows=tc['port_usage']
    checker.require(len(rows)==len({r['port'] for r in rows}) and all(n<=1 for n in usage.values()),'端口预算重复或超额')
    checker.require({r['port']:checker.quantity(r['quantity']) for r in rows}==usage,'端口账与成功事件不符')


def validate_event_identity(timeline, start_state, ticks):
    """全记录唯一域：历史、待事件登记和跨时刻执行分开核对。"""
    history = checker.validate_timeline(timeline)
    executed = set()
    registered = {}
    previous_pending = set()

    def check_pending(state):
        nonlocal previous_pending
        current = set()
        for row in state['semantic_context']['pending_events']['value']:
            checker.fields(row, 'event operation target trigger predecessors status', 'pending_event')
            eid = row['event']
            checker.require(isinstance(eid, str) and eid and eid not in current, '待事件 id 重复或非法')
            checker.require(eid not in executed, '已执行事件又列为待事件: '+eid)
            checker.require(eid not in history or history[eid]['kind'] == 'runtime', '待事件与输入历史身份冲突: '+eid)
            descriptor = {key:row[key] for key in ('operation', 'target', 'trigger', 'predecessors')}
            if eid in registered:
                checker.require(same(registered[eid], descriptor), '待事件身份被改用: '+eid)
            registered[eid] = descriptor
            current.add(eid)
        checker.require(previous_pending - executed <= current, '待事件未经执行而丢失')
        previous_pending = current

    check_pending(start_state)
    for tick in ticks:
        for row in tick['events']:
            eid = row['event']
            checker.require(isinstance(eid, str) and eid and eid not in executed, '跨时刻运行事件重复: '+str(eid))
            checker.require(eid not in history or (history[eid]['kind'] == 'runtime' and eid in registered),
                            '运行事件与输入历史身份冲突: '+eid)
            if eid in registered:
                pending = registered[eid]
                checker.require(row['operation'] == pending['operation'] and row['target'] == pending['target'],
                                '已登记事件的操作/目标冲突: '+eid)
                checker.require(pending['trigger']['kind'] == 'at_time' and same(pending['trigger']['value'], tick['time']),
                                'unsupported: 待事件触发时刻不符或触发类型未实现')
            executed.add(eid)
        check_pending(tick['state'])
    return True


def validate_record(output, data, recomputed=None):
    """在确定性子集内逐字段比对交付记录，不重写被验证文件。"""
    from check_golden_trace import run, GOLDEN, INPUT
    # 数据参数必须来自实际被指纹绑定的输入文件。
    checker.require(same(data,checker.load_json(input_path(data))),'验收输入与指纹目标文件不符')
    checker.check(data,input_path(data))
    actual=run(data) if recomputed is None else recomputed
    expected=build_record(data,actual,None if is_splitter(data) else checker.load_json(GOLDEN))
    from test_runtime_input import validate_schema
    from checkpoint_delta import decode_trace, encode_trace
    schema=checker.load_json(SPEC/'内核输出.schema.json')
    validate_schema(output,schema,schema)
    output=copy.deepcopy(output)
    encoded=copy.deepcopy(output['trace'])
    output['trace']=decode_trace(encoded)
    if encoded['format']=='checkpoint_delta':
        checker.require(same(encoded,encode_trace(output['trace'],encoded['checkpoint_interval'])),'压缩轨迹不规范')
    checker.require(output.get('status')=='completed','unsupported: 此验收器只核成功有限记录')
    validate_event_identity(output['input_history']['timeline'], output['trace']['start_state'], output['trace']['ticks'])
    validate_state(data,output['trace']['start_state'])
    for tick in output['trace']['ticks']:
        validate_state(data,tick['state'])
        ids=[e['event'] for e in tick['events']]
        checker.require(len(ids)==len(set(ids)),'运行事件重复')
        for move in tick['state']['semantic_context']['tick_context']['value']['movements']:
            matches=[e for e in tick['events'] if e['event']==move['event']]
            checker.require(len(matches)==1 and matches[0]['operation']=='move' and matches[0]['outcome']=='success'
                            and matches[0]['target']==move['channel'],'成功移动缺对应事件')
    for key in expected:
        checker.require(same(output.get(key),expected[key]),'交付记录与输入/完整重算不符: '+key)
    checker.require(set(output)==set(expected),'交付记录未知字段')
    return True


def validate_checkpoint(data, state, event):
    """核保存/读回的闭包内部种子；不声称已实现任意种子的直接续跑。"""
    from check_golden_trace import run
    captured={event:None};run(data,captured)
    checker.require(captured[event] is not None,'检查点事件不存在')
    validate_state(data,state)
    checker.require(same(state,captured[event]),'闭包中途种子与已重算断点不符')
    return True
