"""判定序的有限表、周期及全时域纯函数表达式；不改变受限运行配置。"""
import copy
import re
from fractions import Fraction
import check_examples as checker


def template_keys(rows):
    checker.require(isinstance(rows, list) and rows, '排序模板为空')
    keys = []
    for row in rows:
        checker.fields(row, 'operation target', '排序模板')
        checker.require(row['operation'] in ('move', 'manufacture', 'transfer', 'internal_move')
                        and isinstance(row['target'], str) and row['target'], '排序模板非法')
        keys.append((row['operation'], row['target']))
    checker.require(len(keys) == len(set(keys)), '排序模板重复')
    return set(keys)


def rational_time(value):
    checker.fields(value, 'kind value', '排序时刻')
    checker.require(value['kind'] == 'rational', 'unsupported: 排序求值需要已解释的有理时刻')
    return checker.quantity(value['value'], integer=False)


def validate_expression(node, expected, keys, depth=0):
    """遍历所有分支核类型和全域定义性，不因本次没选中而放过坏分支。"""
    checker.require(depth <= 64, 'unsupported: 排序表达式超过实现深度64')
    checker.require(isinstance(node, dict), '排序表达式节点不是对象')
    op = node.get('op')
    def child(value, kind):
        validate_expression(value, kind, keys, depth + 1)
    if op == 'integer':
        checker.fields(node, 'op value', '整数常量')
        checker.require(isinstance(node['value'], str) and re.fullmatch(r'0|-?[1-9][0-9]*', node['value']), '整数常量非法')
        kind = 'integer'
    elif op == 'floor_slot':
        checker.fields(node, 'op origin width', '时刻槽号')
        rational_time(node['origin'])
        checker.require(rational_time(node['width']) > 0, '表达式槽宽必须为正')
        kind = 'integer'
    elif op in ('add', 'subtract', 'multiply'):
        checker.fields(node, 'op left right', '整数运算')
        child(node['left'], 'integer'); child(node['right'], 'integer')
        kind = 'integer'
    elif op == 'modulo':
        checker.fields(node, 'op arg divisor', '整数取模')
        child(node['arg'], 'integer'); child(node['divisor'], 'integer')
        checker.require(node['divisor']['op'] == 'integer' and int(node['divisor']['value']) > 0, '取模除数须为正整数常量')
        kind = 'integer'
    elif op in ('equal', 'less_than'):
        checker.fields(node, 'op left right', '整数比较')
        child(node['left'], 'integer'); child(node['right'], 'integer')
        kind = 'boolean'
    elif op == 'is_power_of_two':
        checker.fields(node, 'op arg', '正的2的幂谓词')
        child(node['arg'], 'integer'); kind = 'boolean'
    elif op in ('all', 'any'):
        checker.fields(node, 'op args', '逻辑运算')
        checker.require(isinstance(node['args'], list), '逻辑参数须为数组')
        for arg in node['args']: child(arg, 'boolean')
        kind = 'boolean'
    elif op == 'not':
        checker.fields(node, 'op arg', '逻辑非')
        child(node['arg'], 'boolean'); kind = 'boolean'
    elif op == 'permutation':
        checker.fields(node, 'op order', '排序叶节点')
        checker.require(template_keys(node['order']) == keys, '表达式排序模板集合变化')
        kind = 'order'
    elif op == 'if':
        checker.fields(node, 'op condition then otherwise', '排序条件分支')
        child(node['condition'], 'boolean')
        child(node['then'], 'order'); child(node['otherwise'], 'order')
        kind = 'order'
    else:
        raise checker.CheckError('unsupported: 未实现排序表达式运算 '+str(op))
    checker.require(kind == expected, '排序表达式类型不符')


def evaluate_expression(node, instant):
    """只读取给定时刻及已校验常量，不访问运行状态或执行外部代码。"""
    op = node['op']
    evaluate = lambda value: evaluate_expression(value, instant)
    if op == 'integer': return int(node['value'])
    if op == 'floor_slot': return (instant - rational_time(node['origin'])) // rational_time(node['width'])
    if op == 'add': return evaluate(node['left']) + evaluate(node['right'])
    if op == 'subtract': return evaluate(node['left']) - evaluate(node['right'])
    if op == 'multiply': return evaluate(node['left']) * evaluate(node['right'])
    if op == 'modulo': return evaluate(node['arg']) % evaluate(node['divisor'])
    if op == 'equal': return evaluate(node['left']) == evaluate(node['right'])
    if op == 'less_than': return evaluate(node['left']) < evaluate(node['right'])
    if op == 'is_power_of_two':
        value = evaluate(node['arg'])
        return value > 0 and value & (value - 1) == 0
    if op == 'all': return all(evaluate(arg) for arg in node['args'])
    if op == 'any': return any(evaluate(arg) for arg in node['args'])
    if op == 'not': return not evaluate(node['arg'])
    if op == 'permutation': return copy.deepcopy(node['order'])
    if op == 'if': return evaluate(node['then'] if evaluate(node['condition']) else node['otherwise'])
    raise checker.CheckError('unsupported: 未实现排序表达式运算')


def order_at(value, instant):
    """周期槽与纯函数覆盖各自完整有理时域；有限表不作默认回退。"""
    version = value.get('schema')
    if version == 'event-order-v1':
        checker.fields(value, 'schema scope template_order repeat_embedding instant_overrides', 'EventOrder')
        schedules = value['instant_overrides']
    else:
        checker.require(version in ('event-order-v2', 'event-order-v3'), 'unsupported: 判定序版本')
        checker.fields(value, 'schema scope template_order repeat_embedding schedule', 'EventOrder')
        schedules = []
    checker.require(value['repeat_embedding'] == 'scan_round_then_template', 'unsupported: 判定重复嵌入')
    keys = template_keys(value['template_order'])
    checker.require(value['scope'] in ('global', 'per_instant'), '判定序辖域非法')
    if value['scope'] == 'global':
        checker.require(schedules == [] and (version == 'event-order-v1' or value['schedule'] is None), 'global 不接受时变表')
        return copy.deepcopy(value['template_order'])
    if version in ('event-order-v2', 'event-order-v3'):
        schedule = value['schedule']
        checker.require(isinstance(schedule, dict), '缺少判定序 schedule')
        if schedule.get('kind') == 'expression':
            checker.require(version == 'event-order-v3', 'unsupported: 表达式需要 event-order-v3')
            checker.fields(schedule, 'kind language expression', '函数排序')
            checker.require(schedule['language'] == 'order-expr-v1', 'unsupported: 排序表达式语言版本')
            validate_expression(schedule['expression'], 'order', keys)
            return evaluate_expression(schedule['expression'], rational_time(instant))
        if schedule.get('kind') == 'periodic':
            checker.fields(schedule, 'kind origin slot_width orders', '周期排序')
            origin = rational_time(schedule['origin'])
            width = rational_time(schedule['slot_width'])
            orders = schedule['orders']
            checker.require(width > 0 and isinstance(orders, list) and orders, '周期槽宽/周期列表非法')
            for rows in orders:
                checker.require(template_keys(rows) == keys, '周期排序模板集合变化')
            index = int((rational_time(instant) - origin) // width) % len(orders)
            return copy.deepcopy(orders[index])
        checker.fields(schedule, 'kind entries', '有限时刻排序')
        checker.require(schedule['kind'] == 'finite_table', 'unsupported: 未实现排序函数编码')
        schedules = schedule['entries']
    checker.require(isinstance(schedules, list), '时刻表不是数组')
    seen = set()
    found = None
    t = rational_time(instant)
    for row in schedules:
        checker.fields(row, 'instant template_order', '时刻排序')
        key = rational_time(row['instant'])
        checker.require(key not in seen, '同刻排序重复')
        seen.add(key)
        checker.require(template_keys(row['template_order']) == keys, '时刻排序模板集合变化')
        if key == t:
            found = row['template_order']
    checker.require(found is not None, 'unsupported: 有限排序表未覆盖本时刻')
    return copy.deepcopy(found)


def event_key(value, instant, sweep, template):
    checker.require(type(sweep) is int and sweep >= 0, '扫描轮号非法')
    rows = order_at(value, instant)
    checker.require(template in rows, '新判定引用未知模板')
    return sweep, rows.index(template)
