"""独立小算例核对规格中的边界与后效；不是布局执行器或认证器。"""
import itertools
import json
from dataclasses import dataclass

results = []


def check(condition, name):
    assert condition, name
    results.append(name)


# 列举两端授权的四种组合，避免把无授权、失败、成功混为一类。
def attempt(source_authorized, target_authorized, physical):
    authorized = (source_authorized, target_authorized)
    judged = any(authorized)
    success = all(authorized) and physical
    return judged, success, authorized if judged else (False, False)


for source, target, physical in itertools.product([False, True], repeat=3):
    judged, success, advance = attempt(source, target, physical)
    assert judged == (source or target)
    assert success == (source and target and physical)
    assert advance == (source, target)
check(True, '双端授权×物理守卫的8种组合：无侧不判，失配推进授权侧，成功两侧前移')
check(attempt(True, False, True) == (True, False, (True, False)), '失配回归：拒绝旧双端死等和无权侧前移')


def initial_cursor(members, special):
    if not members:
        return None
    return members[1] if special and len(members) >= 2 else members[0]


check(initial_cursor(['a'], True) == 'a' and initial_cursor(['b', 'c'], True) == 'c', '汇流器每级起轮：单成员为自身，多成员取级内第二条')
check(initial_cursor(['a', 'b', 'c'], True) == 'b', '全侧第二条与逐级第二条不同，回归例能区分范围')


# 不同级有明确严格优先关系，授权不读对端指针。
def highest(levels, physical):
    return next((i for i, level in enumerate(levels) if any(physical[c] for c in level)), None)


check(highest([['a'], ['b', 'c']], {'a': True, 'b': True, 'c': True}) == 0, '高级物理可动时，不能因对端未授权而降到低级')
check(highest([['a'], ['b', 'c']], {'a': False, 'b': True, 'c': False}) == 1, '高级全部物理不可动才选低级')


def box_source(slots):
    return next((index for index, amount in enumerate(slots) if amount > 0), None)


check(box_source([2, 1, 0]) == 0, '箱体只取最小编号非空格；第一格货物被拒收不改选第二格')


def expire(reasons, start, count, now):
    reasons = set(reasons)
    if start is not None and now - start >= 5:
        reasons.discard('window_exhausted')
        return reasons, None, 0
    return reasons, start, count


check(expire({'window_exhausted'}, 0, 1, 4) == ({'window_exhausted'}, 0, 1), '窗口满5前不提前恢复')
check(expire({'window_exhausted'}, 0, 1, 5) == (set(), None, 0), '窗口在首件后第5 tick解除原因且下一件再起窗')
check(expire({'window_exhausted', 'identity_mismatch'}, 0, 1, 5)[0] == {'identity_mismatch'}, '窗口恢复不抹掉身份锁存')
check(expire({'window_exhausted', 'total_exhausted'}, 0, 1, 5)[0] == {'total_exhausted'}, '窗口恢复不清累计原因')


# 纯失败的有限轮询环必须比较指针；只比库存会提前截断。
position = 0
seen = {position}
visits = 0
while True:
    position = (position + 1) % 3
    visits += 1
    if position in seen:
        break
    seen.add(position)
check(visits == 3 and position == 0, '库存一直不变的3位置失败环：首次完整状态重复在3次后')


# 用独立方块相交式核供电构造，不用轴表的格公式。
def intersect(machine, pole, closed):
    x, y = machine
    a, b = pole
    delta_x = min(x + 3, a + 7) - max(x, a - 5)
    delta_y = min(y + 3, b + 7) - max(y, b - 5)
    return delta_x >= 0 and delta_y >= 0 if closed else delta_x > 0 and delta_y > 0


def pole_overlap(machine, pole):
    x, y = machine
    a, b = pole
    return min(x + 3, a + 2) > max(x, a) and min(y + 3, b + 2) > max(y, b)


for closed, offsets, expected in [(False, [-7, -4, -1, 2, 5], 24), (True, [-8, -5, -2, 1, 4, 7], 32)]:
    pole = (30, 30)
    machines = [(30 + x, 30 + y) for x, y in itertools.product(offsets, repeat=2) if not pole_overlap((30 + x, 30 + y), pole)]
    assert len(machines) == expected and all(intersect(m, pole, closed) for m in machines)
    for first, second in itertools.combinations(machines, 2):
        assert abs(first[0] - second[0]) >= 3 or abs(first[1] - second[1]) >= 3
    check(True, f'供电{expected}台整齐构造逐台相交/互斥核对；只证构造不证达标或一般上界')


# 源矿→带→粉碎机→带→箱的手算流水；单通道端点无轮询争用。
@dataclass
class Pipeline:
    belt_in: int | None = None
    belt_out: int | None = None
    input_count: int = 0
    output_count: int = 0
    phase: str = 'idle'
    remaining: int = 0
    box: int = 0
    supplied: int = 0
    started: int = 0
    completed: int = 0


def instant(state, now):
    if state.phase == 'working':
        state.remaining -= 1
        if state.remaining == 0:
            state.phase = 'completed'
            state.completed += 1
    used = set()
    seen = set()
    while True:
        key = (state.belt_in, state.belt_out, state.input_count, state.output_count, state.phase, state.remaining, state.box, tuple(sorted(used)))
        if key in seen:
            return
        seen.add(key)
        if state.belt_in is None and 'source' not in used:
            state.belt_in = now
            state.supplied += 1
            used.add('source')
        if state.belt_in is not None and now - state.belt_in >= 1 and 'intake' not in used:
            state.belt_in = None
            state.input_count += 1
            used.add('intake')
        if state.phase == 'completed' and state.output_count < 50:
            state.output_count += 1
            state.phase = 'idle'
        if state.phase == 'idle' and state.input_count:
            state.input_count -= 1
            state.phase = 'working'
            state.remaining = 1
            state.started += 1
        if state.output_count and state.belt_out is None and 'outlet' not in used:
            state.output_count -= 1
            state.belt_out = now
            used.add('outlet')
        if state.belt_out is not None and now - state.belt_out >= 1 and 'sink' not in used:
            state.belt_out = None
            state.box += 1
            used.add('sink')


state = Pipeline()
trace = []
for now in range(7):
    instant(state, now)
    row = {'tick': now, 'supplied': state.supplied, 'started': state.started, 'completed': state.completed, 'box': state.box}
    trace.append(row)
    assert state.supplied == now + 1
    assert state.started == now
    assert state.completed == max(now - 1, 0)
    assert state.box == max(now - 2, 0)
    # 该1→1配方下，包含在制的完整物料账必须守恒。
    physical_count = int(state.belt_in is not None) + int(state.belt_out is not None) + state.input_count + state.output_count + int(state.phase in ['working', 'completed']) + state.box
    assert physical_count == state.supplied
check(True, '7个观察边界流水：完成先于闭包、内部立即开工、两段运输各足1 tick、逐tick物料守恒')
check(trace[2]['completed'] == 1 and trace[2]['box'] == 0 and trace[3]['box'] == 1, '制造完成与运输零停留错误可由t2/t3边界区分')
print(json.dumps({'status': 'PASS', 'scope': '规格算例、条件几何与调度后效回归；非完整执行器、非C线黄金轨迹认证', 'checks': results, 'pipeline_trace': trace}, ensure_ascii=False, indent=2))
