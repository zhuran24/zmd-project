"""判定序的有限表及全时域周期编码；不改变受限运行配置。"""
import copy
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
    checker.require(value['kind'] == 'rational', 'unsupported: 周期求值需要已解释的有理时刻')
    return checker.quantity(value['value'], integer=False)


def order_at(value, instant):
    """周期槽覆盖全部有理时刻；不存在表耗尽或默认排序回退。"""
    version = value.get('schema')
    if version == 'event-order-v1':
        checker.fields(value, 'schema scope template_order repeat_embedding instant_overrides', 'EventOrder')
        schedules = value['instant_overrides']
    else:
        checker.require(version == 'event-order-v2', 'unsupported: 判定序版本')
        checker.fields(value, 'schema scope template_order repeat_embedding schedule', 'EventOrder')
        schedules = []
    checker.require(value['repeat_embedding'] == 'scan_round_then_template', 'unsupported: 判定重复嵌入')
    keys = template_keys(value['template_order'])
    checker.require(value['scope'] in ('global', 'per_instant'), '判定序辖域非法')
    if value['scope'] == 'global':
        checker.require(schedules == [] and (version == 'event-order-v1' or value['schedule'] is None), 'global 不接受时变表')
        return copy.deepcopy(value['template_order'])
    if version == 'event-order-v2':
        schedule = value['schedule']
        checker.require(isinstance(schedule, dict), '缺少判定序 schedule')
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
