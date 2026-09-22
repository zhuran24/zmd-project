"""有限运行记录的来源闭合、逐轴覆盖及完整重算关联校验。"""
import hashlib
import json
from pathlib import Path
import check_examples as checker
from runtime_example import PROFILE_PATH, axis_values, quantity, time_value, validate_profile, validate_decision_tree

BASE = Path(__file__).resolve().parent
SPEC = BASE.parents[1] / '规格'


def same(left, right):
    # JSON 类型也必须相同，不能让 Python 的 True == 1 掩盖非法参数。
    return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)


def fingerprints():
    paths = [('input', BASE/'混做粉碎机两下游.json'), ('catalog', BASE.parent/'正式静态目录.json'),
             ('axis_registry', checker.AXIS_PATH), ('profile', SPEC/'受限模型声明.md'),
             ('profile', SPEC/'内核配置-v1.json'), ('parameter_projection', PROFILE_PATH),
             ('golden', BASE/'混做粉碎机两下游-黄金轨迹.json'), ('golden', BASE/'混做粉碎机两下游-黄金轨迹.md'),
             ('semantics', SPEC/'受限转移定义.md'), ('semantics', SPEC/'运行语义.md'),
             ('semantics', SPEC/'内核输入.md'), ('semantics', SPEC/'内核输出.md'),
             ('schema', SPEC/'内核输出.schema.json')]
    paths += [('checker', BASE/name) for name in
              ('check_golden_trace.py', 'runtime_example.py', 'check_examples.py', 'runtime_record.py', 'event_order.py', 'test_runtime_input.py')]
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
            status='not_exercised'; evidence=['布局无协议储存箱，0–3 tick 无传输、冷却或相位事件。']
        elif name.startswith('damping.'):
            status='not_exercised'; evidence=['参考执行只处理单级通道，没有调用阻尼求值器；有传送带不等于已验证元件计数。']
        elif name=='polling.level_tie':
            status='not_exercised'; evidence=['每侧至多一个级，无多级同键平局，没有运行级仲裁。']
        elif name.startswith('bridge.') or name.startswith('connection.bridge'):
            status='not_exercised'; evidence=['本运行输入无桥接器；另两个结构样例的结果不并入本次运行覆盖。']
        elif name.startswith('gate.'):
            status='not_exercised'; evidence=['本运行输入无物品准入口，无身份阻断、累计或窗口事件。']
        elif name.startswith('polling.split_merge'):
            status='not_exercised'; evidence=['本运行输入无分流器/汇流器，无第二条起轮及单成员级特例。']
        if disposition=='超出覆盖即停':
            status='stop_not_triggered'
            evidence += ['所填 stop 是遇到对应机制即停止的工程处置；本轨迹未触及，不证明后效。']
        if name=='warehouse.periodic_lift':
            status='proof_pending'; evidence=['只核有限前缀，完整仓库周期提升没有证明；请求提升即停止。']
        rows.append({'axis':name,'reason':row['coverage_loss'],'disposition':disposition,
                     'coverage_status':status,'evidence':evidence,
                     'other_values':'已定域无其它值；未运行结构仍未验证' if disposition=='已定' else '本次未覆盖其它值及其联合组合'})
    return rows


def build_record(data, ticks, golden):
    checker.require([t['summary'] for t in ticks]==golden['ticks'], '黄金轨迹与有限重算不同')
    profile=validate_profile(data, checker.load_json(PROFILE_PATH))
    batches=sum(e['operation']=='manufacture_complete' for t in ticks for e in t['events'])
    return {'schema':'kernel-output-v2','run_id':'mixed_crusher_prefix_0_3','profile_id':data['parameters']['profile_id'],
            'producer':{'kind':'bounded_reference_checker','path':str(BASE/'check_golden_trace.py'),
                        'claim':'有限重算，与手工黄金摘要比较；不是 Rust 内核结果'},
            'status':'completed','fingerprints':fingerprints(),'parameter_assignment':data['parameters'],
            'input_history':{**{k:data[k] for k in ('timeline','construction','debug_operations','environment')},
                             'reachability':data['initial_state']['reachability']},
            'uncovered_axes':coverage(data,ticks,profile),
            'trace':{'start_state':data['initial_state']['nonwarehouse']['value'],'ticks':ticks,
                     'end_time':ticks[-1]['time'],'format':'full_state_each_instant'},
            'validation_scope':{'kind':'finite_trace','from':ticks[0]['time'],'through':ticks[-1]['time'],
                 'golden_match':True,'initial_history':'conditional_witness','universal_parameters':False,
                 'all_reachable_cycles':False,'target_certified':False,
                 'manufacturing_cycles_completed':quantity(batches,'算术推论')},
            'open_items':['未覆盖实际混做与下游生产','未覆盖离线、其它初态与判定顺序',
                          '有限重算不替代全部可达循环和完整目标认证']}


def validate_state(data, state):
    validate_decision_tree(state)
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
        checker.require(len(row['contents'])<=1,'普通物品格混种')
        for content in row['contents']:
            key=(uid,content['item'])
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


def validate_record(output, data, recomputed=None):
    """在确定性子集内逐字段比对交付记录，不重写被验证文件。"""
    from check_golden_trace import run, GOLDEN, INPUT
    # 数据参数必须来自实际被指纹绑定的输入文件。
    checker.require(same(data,checker.load_json(INPUT)),'验收输入与指纹目标文件不符')
    checker.check(data,INPUT)
    actual=run(data) if recomputed is None else recomputed
    expected=build_record(data,actual,checker.load_json(GOLDEN))
    checker.require(output.get('status')=='completed','unsupported: 此验收器只核成功有限记录')
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
