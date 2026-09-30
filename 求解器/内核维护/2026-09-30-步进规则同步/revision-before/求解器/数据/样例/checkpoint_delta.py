"""逐时刻检查点和对象成员替换增量；只改变记录编码，不改变状态语义。"""
import copy
import json
from check_examples import require, fields


def same(left, right):
    return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)


def state_delta(before, after, path=()):
    """对象同键时递归，数组及其它值整体替换；键按UTF-8序规范输出。"""
    if same(before, after):
        return []
    if isinstance(before, dict) and isinstance(after, dict) and set(before) == set(after):
        return [op for key in sorted(before, key=lambda x: x.encode('utf-8'))
                for op in state_delta(before[key], after[key], path + (key,))]
    require(bool(path), '增量不能替换根状态')
    return [{'op': 'replace', 'path': list(path), 'value': copy.deepcopy(after)}]


def apply_delta(before, delta):
    require(isinstance(delta, list), 'delta须为数组')
    after = copy.deepcopy(before)
    paths = []
    for op in delta:
        fields(op, 'op path value', 'delta.operation')
        require(op['op'] == 'replace', '未知增量操作')
        path = op['path']
        require(isinstance(path, list) and path and all(isinstance(x, str) and x for x in path), '增量路径非法')
        for old in paths:
            require(path[:len(old)] != old and old[:len(path)] != path, '增量路径重复或前缀冲突')
        paths.append(path)
        target = after
        for key in path[:-1]:
            require(isinstance(target, dict) and key in target, '增量路径不存在或穿越数组')
            target = target[key]
        require(isinstance(target, dict) and path[-1] in target, '增量路径不存在或穿越数组')
        require(not same(target[path[-1]], op['value']), '增量含无效替换')
        target[path[-1]] = copy.deepcopy(op['value'])
    require(same(delta, state_delta(before, after)), '增量不是规范最小对象替换序列')
    return after


def encode_trace(trace, interval):
    require(trace['format'] == 'full_state_each_instant', '编码需要完整轨迹')
    require(type(interval) is int and interval >= 1, '检查点间隔须为正整数')
    encoded = copy.deepcopy(trace)
    encoded.update(format='checkpoint_delta', checkpoint_interval=interval, delta_encoding='object_replace_v1')
    previous = trace['start_state']
    for index, tick in enumerate(encoded['ticks']):
        state = tick['state']
        if index % interval:
            tick['delta'] = state_delta(previous, state)
            del tick['state']
        previous = state
    return encoded


def decode_trace(trace):
    if trace['format'] == 'full_state_each_instant':
        fields(trace, 'start_state ticks end_time format', 'full_trace')
        for tick in trace['ticks']:
            fields(tick, 'time events state summary closure warehouse_ledger', 'full_tick')
        return copy.deepcopy(trace)
    fields(trace, 'start_state ticks end_time format checkpoint_interval delta_encoding', 'delta_trace')
    require(trace['format'] == 'checkpoint_delta' and trace['delta_encoding'] == 'object_replace_v1', '不支持的轨迹编码')
    interval = trace['checkpoint_interval']
    require(type(interval) is int and interval >= 1, '检查点间隔须为正整数')
    require(bool(trace['ticks']), '有限完成轨迹不能为空')
    decoded = copy.deepcopy(trace)
    previous = trace['start_state']
    for index, tick in enumerate(decoded['ticks']):
        fields(tick, 'time events summary closure warehouse_ledger ' + ('state' if index % interval == 0 else 'delta'), 'checkpoint_tick')
        if index % interval:
            tick['state'] = apply_delta(previous, tick.pop('delta'))
        previous = tick['state']
    decoded['format'] = 'full_state_each_instant'
    del decoded['checkpoint_interval'], decoded['delta_encoding']
    return decoded
