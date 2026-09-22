#!/usr/bin/env python3
"""第四轮反例回归：排序函数、格身份和全记录事件身份。"""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
EXAMPLES = BASE.parents[1] / '数据/样例'
sys.path.insert(0, str(EXAMPLES))
import check_examples as checker
from check_golden_trace import INPUT, OUTPUT, run
from runtime_example import time_value
from runtime_record import validate_event_identity, validate_record, validate_state
from event_order import order_at, event_key


def replace_string(value, old, new):
    if isinstance(value, dict):
        return {k: replace_string(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_string(v, old, new) for v in value]
    return new if value == old else value


def main():
    results = []
    def accept(name, condition):
        checker.require(condition, name)
        results.append({'name': name, 'status': '通过'})
    def reject(name, action, reason):
        try:
            action()
        except checker.CheckError as error:
            checker.require(reason in str(error), name+': 拒收位置不符 '+str(error))
            results.append({'name': name, 'status': '正确拒绝', 'reason': str(error)})
        else:
            raise checker.CheckError(name+': 错误放行')

    first = [{'operation': 'transfer', 'target': 'box_a'}, {'operation': 'transfer', 'target': 'box_b'}]
    second = first[::-1]
    slot = {'op': 'floor_slot', 'origin': time_value(0), 'width': time_value(5)}
    schedule = {'schema': 'event-order-v3', 'scope': 'per_instant', 'template_order': first,
                'repeat_embedding': 'scan_round_then_template',
                'schedule': {'kind': 'expression', 'language': 'order-expr-v1', 'expression': {
                    'op': 'if', 'condition': {'op': 'is_power_of_two', 'arg': slot},
                    'then': {'op': 'permutation', 'order': second},
                    'otherwise': {'op': 'permutation', 'order': first}}}}
    (BASE/'二的幂次到期排序.json').write_text(json.dumps(schedule, ensure_ascii=False, indent=2)+'\n')
    # 独立期望用迭代倍增集合，不复用被测位运算。
    powers = set(); value = 1
    while value <= 1024:
        powers.add(value); value *= 2
    for index in range(-20, 1025):
        expected = second if index in powers else first
        checker.require(order_at(schedule, time_value(5*index)) == expected, '逐到期排序错误')
    accept('负序号至1024逐到期独立倍增期望', True)
    for exponent in (128, 1024, 4096):
        value = 2 ** exponent
        for delta in (-1, 0, 1):
            expected = second if delta == 0 else first
            instant = time_value(5*(value+delta))
            checker.require(order_at(schedule, instant) == expected, '远时刻排序错误')
            checker.require(event_key(schedule, instant, 10**6, expected[1]) == (10**6, 1), '新判定嵌入错误')
    accept('2的128/1024/4096次幂及相邻到期与新判定嵌入', True)
    boundary = [('-1/10', first), ('0', first), ('49/10', first), ('5', second),
                ('149/10', second), ('15', first), ('199/10', first), ('20', second)]
    accept('非整数槽边界和负时间向下取整', all(order_at(schedule, time_value(t)) == order for t, order in boundary))
    readback = checker.load_json(BASE/'二的幂次到期排序.json')
    accept('全时域表达式文件往返和同刻重复稳定', all(order_at(readback, time_value(40)) == second for _ in range(8)))
    mutations = [
        ('未选分支漏模板', lambda d: d['schedule']['expression']['otherwise']['order'].pop(), '模板集合'),
        ('未选分支重复模板', lambda d: d['schedule']['expression']['otherwise']['order'].append(first[0]), '模板重复'),
        ('缺else', lambda d: d['schedule']['expression'].pop('otherwise'), '字段缺失'),
        ('条件类型错', lambda d: d['schedule']['expression'].update(condition={'op': 'integer', 'value': '1'}), '类型不符'),
        ('零槽宽', lambda d: d['schedule']['expression']['condition']['arg'].update(width=time_value(0)), '槽宽'),
        ('负槽宽', lambda d: d['schedule']['expression']['condition']['arg'].update(width=time_value(-5)), '槽宽'),
        ('未知版本', lambda d: d['schedule'].update(language='unregistered'), '语言版本'),
        ('旧schema不能偷带表达式', lambda d: d.update(schema='event-order-v2'), '需要 event-order-v3'),
        ('隐藏状态自由变量', lambda d: d['schedule']['expression']['condition'].update(arg={'op': 'inventory'}), '未实现'),
        ('零除数', lambda d: d['schedule']['expression']['condition'].update(arg={'op':'modulo','arg':slot,'divisor':{'op':'integer','value':'0'}}), '正整数常量'),
        ('布尔整数', lambda d: d['schedule']['expression']['condition'].update(arg={'op':'integer','value':True}), '整数常量'),
    ]
    for name, mutate, reason in mutations:
        bad = copy.deepcopy(schedule); mutate(bad)
        reject('函数排序/'+name, lambda: order_at(bad, time_value(5)), reason)
    reject('函数排序/符号时间不近似', lambda: order_at(schedule, {'kind':'symbol','value':'phase_a'}), '有理时刻')
    # 组合算术及逻辑也是可输入语言，不只支持专用二次幂判定。
    integer = lambda n: {'op':'integer','value':str(n)}
    compound = copy.deepcopy(schedule)
    compound['schedule']['expression']['condition'] = {'op':'all','args':[
        {'op':'not','arg':{'op':'less_than','left':slot,'right':integer(0)}},
        {'op':'any','args':[{'op':'equal','left':{'op':'modulo','arg':{'op':'subtract','left':{'op':'multiply','left':{'op':'add','left':slot,'right':integer(1)},'right':integer(3)},'right':integer(3)},'divisor':integer(2)},'right':integer(1)}]}]}
    accept('通用整数运算与逻辑组合', all(order_at(compound,time_value(5*n)) == (second if n>=0 and n%2 else first) for n in range(-3,10)))

    data = checker.load_json(INPUT)
    seed = data['initial_state']['nonwarehouse']['value']
    # 全文槽位辖域：输入、输出、缓存、每个运输格及未来单位槽位。
    slots = [r['slot'] for r in seed['inventory']] + ['future_unit:input:0']
    for sid in slots:
        bad = replace_string(data, 'warehouse_0', sid)
        reject('仓库碰撞/'+sid, lambda: checker.check(bad, INPUT), '单位槽位命名域')
    for name in ('桥接器双通路.json', '分流器三路轮询.json'):
        bad = replace_string(checker.load_json(EXAMPLES/name), 'warehouse_0', 'future_unit:buffer:0')
        reject('静态仓库命名域/'+name, lambda: checker.check(bad, EXAMPLES/name), '单位槽位命名域')
    renamed = replace_string(data, 'warehouse_0', 'ore_inventory_safe')
    checker.check(renamed, INPUT)
    original_ticks = run(data); renamed_ticks = run(renamed)
    accept('不冲突仓库更名不改库存收支', [t['summary'] for t in original_ticks] == [t['summary'] for t in renamed_ticks])
    accept('四次出库恰扣四件且制造存货清空', renamed_ticks[-1]['summary']['warehouse_ore']=='79996' and
           all(not next(r['contents'] for r in t['state']['inventory'] if r['slot']=='crusher:input:0') for t in renamed_ticks))
    bad_state = copy.deepcopy(original_ticks[-1]['state'])
    bad_state['warehouse']['slots'][0]['slot'] = 'crusher:input:0'
    reject('输出状态命名域', lambda: validate_state(data,bad_state), '单位槽位命名域')
    duplicate = copy.deepcopy(original_ticks[-1]['state'])
    duplicate['warehouse']['slots'].append(copy.deepcopy(duplicate['warehouse']['slots'][0]))
    reject('输出仓库重复标签', lambda: validate_state(data,duplicate), 'id 重复')

    for identifier in ('J|0|0|0', 'C|2|crusher'):
        bad = replace_string(data, 'build_13', identifier)
        reject('输入历史占运行ID/'+identifier, lambda: checker.check(bad,INPUT), '运行事件保留前缀')
        # 单独核生成守卫，避免装载拦截掩盖第二道防线失效。
        with patch.object(checker, 'check', return_value=None):
            reject('生成器全局注册/'+identifier, lambda: run(bad), '全局注册冲突')
    accept('正常pending跨状态引用及一次消费', validate_event_identity(data['timeline'],seed,original_ticks))
    bad_history = copy.deepcopy(data['timeline'])
    bad_history['events'][0]['id'] = original_ticks[0]['events'][0]['event']
    reject('事件验收/历史与新事件碰撞', lambda: validate_event_identity(bad_history,seed,original_ticks), '运行事件保留前缀')
    repeated = copy.deepcopy(original_ticks)
    repeated[1]['events'][0]['event'] = repeated[0]['events'][0]['event']
    reject('事件验收/跨tick重复', lambda: validate_event_identity(data['timeline'],seed,repeated), '跨时刻运行事件重复')
    pending_conflict = copy.deepcopy(original_ticks)
    pending_conflict[1]['state']['semantic_context']['pending_events']['value'][0]['event'] = 'build_13'
    reject('事件验收/pending碰历史', lambda: validate_event_identity(data['timeline'],seed,pending_conflict), '输入历史身份冲突')
    pending_done = copy.deepcopy(original_ticks)
    pending_done[2]['state']['semantic_context']['pending_events']['value'][0]['event'] = 'C|2|crusher'
    reject('事件验收/已办又待办', lambda: validate_event_identity(data['timeline'],seed,pending_done), '已执行事件又列为待事件')
    pending_changed = copy.deepcopy(original_ticks)
    pending_changed[2]['events'][0]['target'] = 'grinder_a'
    reject('事件验收/完成改目标', lambda: validate_event_identity(data['timeline'],seed,pending_changed), '操作/目标冲突')
    output = checker.load_json(OUTPUT)
    bad_output = copy.deepcopy(output)
    bad_output['trace']['ticks'][1]['events'][0]['event'] = 'J|0|0|0'
    reject('完整验收/跨tick重复', lambda: validate_record(bad_output,data,original_ticks), '跨时刻运行事件重复')
    bad_output = copy.deepcopy(output)
    bad_output['trace']['ticks'][0]['events'][0]['event'] = 'build_13'
    reject('完整验收/建造冒充移动', lambda: validate_record(bad_output,data,original_ticks), '输入历史身份冲突')
    report = {'status':'通过','tests':results,'count':len(results),
              'finding_ids':['K3-r4-L1-01','K3-r4-L3-01','K3-r4-L3-02'],
              'scope':'函数全域定义性见处理报告；选点回归不当作穷尽证明。命名与事件反例在输入和独立记录层均核验。'}
    (BASE/'修订回归结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','count':len(results)},ensure_ascii=False))


if __name__ == '__main__':
    main()
