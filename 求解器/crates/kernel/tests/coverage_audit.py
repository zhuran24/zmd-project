"""内核输出§1、§3：从已独立重算的事件及状态提取逐轴证据，不读取报告来决定期望。"""
import json
from collections import defaultdict
import check_examples as checker
from runtime_example import input_path, validate_runtime


def expected_coverage(data, ticks, root):
    """本版输出报告的逐轴五态编码；适用域由参考执行器先验证，不能冒充通用机制认证。"""
    config = checker.load_json(root / '规格/内核配置-v1.json')
    source = input_path(data)
    catalog = checker.load_json(source.parent / data['catalog']['path'])
    kinds, units, ports, channels, buffers, _ = checker.geometry(data, catalog)
    powered = validate_runtime(data, catalog, ports, channels, buffers)
    channels = {c['id']: c for c in channels}
    events = [e for tick in ticks for e in tick['events']]
    ids = lambda op, outcomes=None: [e['event'] for e in events if e['operation'] == op
                                    and (outcomes is None or e['outcome'] in outcomes)]
    moves = ids('move', ['success'])
    failures = ids('move', ['failure'])
    complete = ids('manufacture_complete')
    transfer = ids('transfer', ['success', 'failure'])
    expiry = ids('gate_window_expiry')
    tie = [e['event'] for e in events if any(b.startswith('polling.level_tie=') for b in e['basis'])]
    split_merge = [e['event'] for e in events if e['operation'] == 'move'
                   and e['outcome'] in ('success', 'failure')
                   and (units[ports[channels[e['target']]['source_port']]['unit']]['kind'] == '分流器'
                        or units[ports[channels[e['target']]['target_port']]['unit']]['kind'] == '汇流器')]
    phases = {p['unit']: p['phase'] for p in data['initial_state']['nonwarehouse']['value']['progress']}
    switches = {(s['unit'], s['function']): s['enabled'] for s in data['settings']['switches']}
    manufacturing = defaultdict(list)
    for tick in ticks:
        passages = tick['state']['semantic_context']['tick_context']['value']['internal_passages']
        for event in tick['events']:
            uid, eid = event['target'], event['event']
            if event['operation'] == 'manufacture_complete':
                phases[uid] = 'completed'
            if event['operation'] != 'manufacture':
                continue
            axes = []
            output = any(p['event'] == eid and p['channel'].startswith(f'BC|{uid}:buffer:') for p in passages)
            intake = any(p['event'] == eid and p['channel'].startswith(f'BC|{uid}:input:') for p in passages)
            if phases[uid] == 'completed':
                axes.append('manufacturing.output_blocked')
            if output:
                phases[uid] = 'idle'
            if intake:
                axes += ['manufacturing.' + name for name in
                         ('recipe_match_scope', 'recipe_completeness', 'recipe_quantity_match',
                          'recipe_extra_items', 'recipe_selection', 'recipe_lock_time', 'input_collection')]
                phases[uid] = 'intake'
            if output or intake:
                axes += ['manufacturing.buffer_power_gate', 'judgment.buffer_event_class', 'cascade.buffer']
            if phases[uid] == 'intake' and powered.get(uid) and switches.get((uid, 'manufacture')):
                phases[uid] = 'working'
            for axis in axes:
                manufacturing[axis].append(eid)

    acceptance = []
    capacity = int(next(r for r in kinds['协议核心']['inventory'] if r['role'] == 'warehouse')['capacity']['value'])
    boxes = sorted(uid for uid, unit in units.items() if unit['kind'] == '协议储存箱'
                   and powered.get(uid) and switches.get((uid, 'transfer')))
    for tick in ticks:
        inbound = sorted(c for c in tick['state']['logistics']['active_channels']
                         if ports[channels[c]['target_port']]['family'] == 'core')
        path = bool(inbound or boxes)
        products = []
        for item in ('高容谷地电池', '精选荞愈胶囊'):
            stored = sum(int(r['quantity']['value']) for r in tick['state']['warehouse']['slots'] if r['item'] == item)
            free = capacity - stored
            products.append({'item': item, 'free_capacity': {'value': str(free), 'category': '算术推论'},
                             'capacity_available': free > 0, 'physical_path_exists': path,
                             'capacity_and_path': free > 0 and path})
        observation = {'time': tick['time'], 'phase': 'after_closure', 'products': products,
                       'core_input_channels': inbound, 'enabled_transfer_units': boxes,
                       'path_scope': '入库途径仅指当前现存核心存货PC或有电且开关开的箱体传输接口；不承诺成品已到达、端口本刻余量、冷却就绪或全程送料可达。',
                       'both_products_capacity_and_path': all(p['capacity_and_path'] for p in products)}
        acceptance.append(json.dumps(observation, ensure_ascii=False, sort_keys=True, separators=(',', ':')))

    checked = {'connection.build_order', 'connection.order', 'connection.tie', 'connection.port_meeting',
               'connection.belt_shape', 'initialization.warehouse_anchor', 'initialization.other_inventory',
               'initialization.switches', 'initialization.build_timing', 'initialization.debug_end',
               'warehouse.capacity', 'power.cell_rule', 'polling.initial_cursor', 'polling.direct_peer'}
    result = {}
    for name, conf in config['axes'].items():
        status, evidence = 'not_exercised', ['本次未记录该机制实际后效；参数赋值不等于覆盖。']
        if moves and (name.startswith('time.') or name in {'judgment.order', 'judgment.order_scope',
                     'polling.dual_permission', 'polling.memory_scope', 'polling.eligibility_stage'}):
            status, evidence = 'exercised', moves
        if name == 'time.manufacture_events':
            status, evidence = ('exercised', complete) if complete else ('not_exercised', ['本次没有制造完成'])
        if name in manufacturing:
            status, evidence = 'exercised', manufacturing[name]
        if name in checked:
            status, evidence = 'input_checked', ['本次输入/目录/种子检查；单一历史不证明全称可达性。']
        if name == 'connection.bridge_first_contact' and any(u['kind'] == '桥接器' for u in units.values()):
            status, evidence = 'input_checked', ['仅校验输入中已解桥方向及先接历史；运行段不执行建造/先接定向，后续搬运不构成定向事件。']
        if name in ('polling.both_failure', 'polling.ungraded_blocked') and failures:
            status, evidence = 'exercised', failures
        if name == 'polling.level_tie' and tie:
            status, evidence = 'exercised', tie
        if name.startswith('transfer.') and transfer and name not in ('transfer.pause','transfer.resume_event'):
            status, evidence = 'exercised', transfer
        if name in ('gate.concurrent_expiry', 'gate.window_clock', 'gate.window_recovery',
                    'gate.reconnect_record', 'polling.membership_change') and expiry:
            status, evidence = 'exercised', expiry
        if name.startswith('polling.split_merge') and split_merge:
            status, evidence = 'exercised', split_merge
        if name in ('manufacturing.input_mixing','manufacturing.input_capacity_scope','manufacturing.port_slot_relation','manufacturing.input_slot_selection','manufacturing.empty_slot_identity'):
            inbound=[e['event'] for e in events if e['operation']=='move' and e['outcome']=='success' and kinds[units[ports[channels[e['target']]['target_port']]['unit']]['kind']]['family']=='manufacturing']
            if inbound:status,evidence='exercised',inbound
        if name=='damping.belt_adjacency':
            status,evidence='not_exercised',['本版path_runs只计路径连续带串，不调用geometric_components的几何邻接轴。']
        if name=='transfer.resume_event':
            status,evidence='not_exercised',['运行段开关/供电固定，暂停后重新启用需未支持的调试或离线后效；未以普通冷却到期冒领。']
        if conf['disposition'] == '超出覆盖即停':
            status, evidence = 'stop_not_triggered', ['所请求的有限前缀未触及停止域，不证明该域后效。']
        if name == 'warehouse.periodic_lift':
            status, evidence = 'proof_pending', ['完整基地周期提升未证明，请求提升立即停止。']
        if name in ('warehouse.acceptance', 'warehouse.acceptance_quantifier') and acceptance:
            status, evidence = 'exercised', acceptance
        result[name] = {'axis': name, 'reason': conf['coverage_loss'], 'disposition': conf['disposition'],
                        'coverage_status': status, 'evidence': evidence,
                        'other_values': '已定域无其它值；未执行结构仍未验证' if conf['disposition'] == '已定'
                        else '其它值及其联合组合未覆盖'}
    return result
