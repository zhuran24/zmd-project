"""第 87 轮复核：记账与见证（本席自写，只读快照）。

A 配方与机型下限：从快照游戏规则解析 18 个配方，按目标产率解收支（蓝铁粉末回炼 r=0），得九机型最少台数。
B 研磨机进入「两种主料占格」的全部转移：逐状态、逐事件（进一件 / 开一批）枚举，核「只能一步由一主料一空格进入」。
C 第 0 项（丙）读法：「全部首件收不下」若只看现有首件，给出一台之后照样开批的研磨机状态。
D 第 2、3 项：固定双料配方、两格只有两种原料、各料专线首件只有本料时，枚举全部库存，核不存在存货首件死锁。
E 第 1 项（丁）读法：精炼炉两条取货通道分别接放行钢块的准入口与每 5 tick 限 1 件的蓝铁块准入口；
  后者限额用尽断开通道时，现有通道全都拒收蓝铁块，但此后照样每 5 tick 开一批。
F 第 12 项：纯料专线含每 5 tick 限 1 件的准入口（第 84 轮反例的独立复算）：源头每刻不空手，X 每 5 刻空手 4 刻。
G 第 10 项：K 唯一出口首格是汇流器，另一存货通道直接接分流器、接通更早（存货优先级高），K 每刻 0 件。
用法：python3 -B witnesses.py > witnesses.json
"""
import json
import math
import re
from fractions import Fraction as Fr
from pathlib import Path

SNAP = Path(__file__).resolve().parent.parent / '前提快照' / '《明日方舟：终末地》游戏规则.txt'


def parse_recipes():
    txt = SNAP.read_text(encoding='utf-8')
    body = txt.split('\n配方\n', 1)[1]
    machines = ['粉碎机', '精炼炉', '研磨机', '塑形机', '配件机', '种植机', '采种机', '封装机', '灌装机']
    rec = []
    cur = None
    for line in body.splitlines():
        s = line.strip()
        if s in machines:
            cur = s
            continue
        mm = re.match(r'(.+?)\s*→\s*(\d+)\s*(\S+?)，\s*(\d+)\s*tick', s)
        if mm and cur:
            ins = []
            for part in re.split(r'＋|\+', mm.group(1)):
                a = re.match(r'\s*(\d+)\s*(\S+)\s*', part)
                ins.append((a.group(2), int(a.group(1))))
            rec.append({'m': cur, 'in': ins, 'out': (mm.group(3), int(mm.group(2))), 'd': int(mm.group(4))})
    return rec


def solve_bounds(rec):
    items = sorted({i for r in rec for i, _ in r['in']} | {r['out'][0] for r in rec})
    ores = {'源矿', '蓝铁矿'}
    target = {'高容谷地电池': Fr(3, 5), '精选荞愈胶囊': Fr(11, 20)}
    n = len(rec)
    rows, rhs = [], []
    for it in items:
        if it in ores:
            continue
        row = [Fr(0)] * n
        for j, r in enumerate(rec):
            if r['out'][0] == it:
                row[j] += r['out'][1]
            for i2, a in r['in']:
                if i2 == it:
                    row[j] -= a
        rows.append(row)
        rhs.append(target.get(it, Fr(0)))
    # r=0：蓝铁粉末→蓝铁块 的批率为 0
    jr = [j for j, r in enumerate(rec) if r['m'] == '精炼炉' and r['in'][0][0] == '蓝铁粉末'][0]
    row = [Fr(0)] * n
    row[jr] = Fr(1)
    rows.append(row)
    rhs.append(Fr(0))
    # 高斯消元（行数可能多于列数，检查相容）
    A = [rows[i] + [rhs[i]] for i in range(len(rows))]
    piv_r = 0
    where = [-1] * n
    for c in range(n):
        p = None
        for r in range(piv_r, len(A)):
            if A[r][c] != 0:
                p = r
                break
        if p is None:
            continue
        A[piv_r], A[p] = A[p], A[piv_r]
        pv = A[piv_r][c]
        A[piv_r] = [x / pv for x in A[piv_r]]
        for r in range(len(A)):
            if r != piv_r and A[r][c] != 0:
                f = A[r][c]
                A[r] = [x - f * y for x, y in zip(A[r], A[piv_r])]
        where[c] = piv_r
        piv_r += 1
    assert all(w >= 0 for w in where), '解不唯一'
    for r in range(piv_r, len(A)):
        assert A[r][-1] == 0, '不相容'
    x = [A[where[c]][-1] for c in range(n)]
    load = {}
    for j, r in enumerate(rec):
        load[r['m']] = load.get(r['m'], Fr(0)) + x[j] * r['d']
    order = ['粉碎机', '精炼炉', '研磨机', '塑形机', '配件机', '种植机', '采种机', '封装机', '灌装机']
    return {'recipes': len(rec), 'items': len(items),
            'machine_load': {m: str(load[m]) for m in order},
            'min_count': {m: math.ceil(load[m]) for m in order}}


MAINS = ['蓝铁粉末', '源石粉末', '荞花粉末']
SAND = '砂叶粉末'
GRIND = [(mn, 2, SAND, 1) for mn in MAINS]


def grinder_transitions():
    """状态：两格，各为 None 或 (物品, 件数)，同种物品只占一格。事件：来一件合法物品（四种之一）或开一批。"""
    goods = MAINS + [SAND]
    slot_states = [None] + [(g, c) for g in goods for c in range(1, 51)]
    states = set()
    for a in slot_states:
        for b in slot_states:
            if a and b and a[0] == b[0]:
                continue
            states.add(tuple(sorted([a, b], key=lambda z: (z is None, z))))

    def is_yi(s):
        ms = [z[0] for z in s if z and z[0] in MAINS]
        return len(set(ms)) == 2

    enter_yi = []
    for s in states:
        if is_yi(s):
            continue
        # 来一件
        for g in goods:
            sl = list(s)
            idx = [i for i, z in enumerate(sl) if z and z[0] == g]
            if idx:
                i = idx[0]
                if sl[i][1] >= 50:
                    continue
                sl[i] = (g, sl[i][1] + 1)
            else:
                e = [i for i, z in enumerate(sl) if z is None]
                if not e:
                    continue
                sl[e[0]] = (g, 1)
            ns = tuple(sorted(sl, key=lambda z: (z is None, z)))
            if is_yi(ns):
                enter_yi.append(('in', s, g))
        # 开一批（任一可开的配方）
        cnt = {z[0]: z[1] for z in s if z}
        for mn, a, sd, b in GRIND:
            if cnt.get(mn, 0) >= a and cnt.get(sd, 0) >= b:
                sl = []
                for z in s:
                    if z is None:
                        sl.append(None)
                        continue
                    c = z[1] - (a if z[0] == mn else b if z[0] == sd else 0)
                    sl.append((z[0], c) if c > 0 else None)
                ns = tuple(sorted(sl, key=lambda z: (z is None, z)))
                if is_yi(ns):
                    enter_yi.append(('start', s, mn))
    one_step = all(kind == 'in' and sum(1 for z in s if z is None) == 1 and
                   any(z and z[0] in MAINS for z in s) and g in MAINS for kind, s, g in enter_yi)
    return {'grinder_states': len(states), 'transitions_into_yi': len(enter_yi),
            'all_are_main_into_empty_beside_other_main': one_step,
            'by_start': sum(1 for e in enter_yi if e[0] == 'start')}


def can_start(cnt):
    return any(cnt.get(mn, 0) >= a and cnt.get(sd, 0) >= b for mn, a, sd, b in GRIND)


def receivable(slots, g):
    for z in slots:
        if z and z[0] == g:
            return z[1] < 50
    return any(z is None for z in slots)


def bing_reading():
    slots = [('蓝铁粉末', 1), (SAND, 50)]
    heads = [None, SAND]  # 蓝铁粉末路首格此刻空（货在路上），砂叶粉末路首件收不下
    cnt = {z[0]: z[1] for z in slots}
    literal = (not can_start(cnt)) and all(not receivable(slots, h) for h in heads if h is not None)
    strict = (not can_start(cnt)) and all(h is not None and not receivable(slots, h) for h in heads)
    # 之后蓝铁粉末到首格
    ok_in = receivable(slots, '蓝铁粉末')
    cnt2 = dict(cnt)
    cnt2['蓝铁粉末'] += 1
    return {'state': '研磨机两格：蓝铁粉末 1、砂叶粉末 50；蓝铁粉末路首格空、砂叶粉末路首件为砂叶粉末',
            'literal_all_present_heads_unreceivable': literal,
            'strict_every_channel_has_unreceivable_head': strict,
            'iron_powder_arrives_receivable': ok_in, 'can_start_after': can_start(cnt2)}


def pure_feed_enum():
    recipes = [('研磨机', mn, 2, SAND, 1) for mn in MAINS] + [
        ('封装机', '钢制零件', 10, '致密源石粉末', 15), ('灌装机', '钢质瓶', 10, '细磨荞花粉末', 10)]
    viol = 0
    checked = 0
    for mach, A, a, B, b in recipes:
        for xa in range(51):
            for xb in range(51):
                slots = [(A, xa) if xa else None, (B, xb) if xb else None]
                if xa >= a and xb >= b:
                    continue  # 够一批，不可能是死锁
                # 专线首件只能是本料；死锁要求每条通道首件都在且收不下；额外通道首件也只能是 A 或 B
                ha = not receivable(slots, A)
                hb = not receivable(slots, B)
                checked += 1
                if ha and hb:
                    viol += 1
    return {'states_checked': checked, 'deadlock_found': viol}


class Gate:
    def __init__(self, allow, cap5=None):
        self.allow, self.cap5 = allow, cap5
        self.item = None  # (物品, 进格时刻)
        self.ws, self.cnt = None, 0

    def blocked_for(self, g, t):
        if self.allow is not None and g != self.allow:
            return True
        if self.cap5 is not None and self.ws is not None and t < self.ws + 5 and self.cnt >= self.cap5:
            return True
        return False

    def can_recv(self, g, t):
        return self.item is None and not self.blocked_for(g, t)

    def recv(self, g, t):
        if self.ws is None or t >= self.ws + 5:
            self.ws, self.cnt = t, 1
        else:
            self.cnt += 1
        self.item = (g, t)


def ding_reading():
    """精炼炉 R：蓝铁矿→蓝铁块，存货来自仓库取货口（每 tick 至多 1 件，始终有货）。
    取货通道 1 接准入口 G1（放行钢块）；取货通道 2 接准入口 G2（放行蓝铁块、每 5 tick 限 1 件），其后一格传送带进不堵的下游。"""
    R = {'st': 0, 'cache': None, 'pk': 0}
    ore_cell = None  # 仓库取货口后的一格传送带（进格时刻）
    G1, G2 = Gate('钢块'), Gate('蓝铁块', 1)
    belt = None
    rows = []
    batches = 0
    for t in range(0, 200):
        changed = True
        while changed:
            changed = False
            # 仓库取货口向首格供矿（始终有货）
            if ore_cell is None:
                ore_cell = t
                changed = True
            if ore_cell is not None and ore_cell + 1 <= t and R['st'] < 50:
                R['st'] += 1
                ore_cell = None
                changed = True
            c = R['cache']
            if c and c[0] == 'run' and c[1] + 1 <= t:
                R['cache'] = ('done',)
                changed = True
            if R['cache'] == ('done',) and R['pk'] + 1 <= 50:
                R['pk'] += 1
                R['cache'] = None
                changed = True
            if R['cache'] is None and R['st'] >= 1:
                R['st'] -= 1
                R['cache'] = ('run', t)
                batches += 1
                changed = True
            if R['pk'] > 0 and G1.can_recv('蓝铁块', t):
                R['pk'] -= 1
                G1.recv('蓝铁块', t)
                changed = True
            if R['pk'] > 0 and G2.can_recv('蓝铁块', t):
                R['pk'] -= 1
                G2.recv('蓝铁块', t)
                changed = True
            if G2.item and G2.item[1] + 1 <= t and belt is None:
                belt = t
                G2.item = None
                changed = True
            if belt is not None and belt + 1 <= t:
                belt = None  # 下游始终收
                changed = True
        connected = [ch for ch, g in (('G1', G1), ('G2', G2)) if not g.blocked_for('蓝铁块', t)]
        literal_ding = R['pk'] > 0 and all(False for _ in connected)  # 现有（接通的）通道全都拒收蓝铁块
        rows.append({'t': t, 'pk': R['pk'], 'G2_blocked': G2.blocked_for('蓝铁块', t), 'literal_ding': literal_ding,
                     'batches_so_far': batches})
    first = next(r for r in rows if r['literal_ding'])
    return {'first_literal_ding_tick': first['t'], 'batches_at_that_tick': first['batches_so_far'],
            'pickup_at_t199': rows[-1]['pk'],
            'literal_ding_ticks_in_150_199': sum(1 for r in rows[150:] if r['literal_ding']),
            'batches_in_150_199': rows[-1]['batches_so_far'] - rows[149]['batches_so_far']}


def quota_line_witness():
    """Y：精炼炉 蓝铁粉末→蓝铁块；X：粉碎机 蓝铁块→蓝铁粉末。Y 唯一取货通道 → 准入口 G（蓝铁块、每 5 tick 限 1）→ X 存货格；
    X 唯一取货通道 → 15 格传送带 → Y 存货格。起态：Y 存货 50、取货 50、缓存做好的一块；X 全空；路全空。"""
    Y = {'st': 50, 'cache': ('done',), 'pk': 50}
    X = {'st': 0, 'cache': None, 'pk': 0}
    G = Gate('蓝铁块', 1)
    belt = [None] * 15
    seen = {}
    log = []
    for t in range(0, 400):
        changed = True
        while changed:
            changed = False
            for M in (Y, X):
                c = M['cache']
                if c and c[0] == 'run' and c[1] + 1 <= t:
                    M['cache'] = ('done',)
                    changed = True
                if M['cache'] == ('done',) and M['pk'] + 1 <= 50:
                    M['pk'] += 1
                    M['cache'] = None
                    changed = True
                if M['cache'] is None and M['st'] >= 1:
                    M['st'] -= 1
                    M['cache'] = ('run', t)
                    changed = True
            if Y['pk'] > 0 and G.can_recv('蓝铁块', t):
                Y['pk'] -= 1
                G.recv('蓝铁块', t)
                changed = True
            if G.item and G.item[1] + 1 <= t and X['st'] < 50:
                X['st'] += 1
                G.item = None
                changed = True
            if belt[-1] is not None and belt[-1] + 1 <= t and Y['st'] < 50:
                Y['st'] += 1
                belt[-1] = None
                changed = True
            for j in range(13, -1, -1):
                if belt[j] is not None and belt[j] + 1 <= t and belt[j + 1] is None:
                    belt[j + 1] = t
                    belt[j] = None
                    changed = True
            if belt[0] is None and X['pk'] > 0:
                belt[0] = t
                X['pk'] -= 1
                changed = True
        def rel(c):
            return None if c is None else ('d' if c[0] == 'done' else t - c[1])
        key = (Y['st'], rel(Y['cache']), Y['pk'], X['st'], rel(X['cache']), X['pk'],
               None if G.item is None else min(t - G.item[1], 1),
               None if G.ws is None or t >= G.ws + 5 else (t - G.ws, G.cnt),
               tuple(None if b is None else min(t - b, 1) for b in belt))
        log.append({'t': t, 'Y_idle': Y['cache'] is None, 'X_idle': X['cache'] is None})
        if key in seen:
            t1 = seen[key]
            cyc = log[t1 + 1:t + 1]
            return {'cycle_from': t1, 'cycle_to': t, 'period': t - t1,
                    'Y_idle_ticks_in_cycle': sum(r['Y_idle'] for r in cyc),
                    'X_idle_ticks_in_cycle': sum(r['X_idle'] for r in cyc)}
        seen[key] = t
    return {'cycle': None}


def merger_witness():
    """K：荞花粉碎机，取货格 50 件荞花粉末、缓存里做好的一批（放不进）——每刻不空手。
    K 唯一取货通道 → 汇流器 M；M 另一存货通道直接接分流器 D（自成一级，接通早，存货优先级高）。
    D 每刻都有满 1 tick 的货（上游恒满）；M 取货端口 → 一格传送带 → 不堵的下游。"""
    K = {'pk': 50, 'cache': ('done',)}
    M = None  # (来源, 进格时刻)
    D = -1  # D 里货的进格时刻
    belt = None
    rows = []
    for t in range(0, 30):
        m_empty_seen = M is None
        k_sent = 0
        changed = True
        while changed:
            changed = False
            if belt is not None and belt + 1 <= t:
                belt = None
                changed = True
            if M is not None and M[1] + 1 <= t and belt is None:
                belt = t
                M = None
                m_empty_seen = True
                changed = True
            if M is None:
                cand = []
                if D is not None and D + 1 <= t:
                    cand.append(('D', 0))  # 级别 0（高）
                if K['pk'] > 0:
                    cand.append(('K', 1))
                if cand:
                    top = min(c[1] for c in cand)
                    src = [c[0] for c in cand if c[1] == top][0]
                    M = (src, t)
                    if src == 'D':
                        D = None
                    else:
                        K['pk'] -= 1
                        k_sent += 1
                    changed = True
            if D is None:
                D = t  # 上游恒满，同刻补入
                changed = True
            if K['cache'] == ('done',) and K['pk'] + 2 <= 50:
                K['pk'] += 2
                K['cache'] = ('run', t)  # 取货格腾空才会走到这里（本例不会）
                changed = True
        rows.append({'t': t, 'M_ready': m_empty_seen, 'K_sent': k_sent, 'K_cache_nonempty': K['cache'] is not None})
    tail = rows[5:]
    return {'ticks': len(tail), 'M_ready_every_tick': all(r['M_ready'] for r in tail),
            'K_sent_total': sum(r['K_sent'] for r in tail),
            'K_never_idle': all(r['K_cache_nonempty'] for r in tail),
            'claimed_min_per_tick': 'min(1,2)=1'}


def skeleton_counts():
    """第 13 项骨架的台数与满载流量（逐台建图后按每刻至多一批、收支相等求上限）。"""
    from fractions import Fraction as Q
    m = {}
    def add(t, n):
        m[t] = m.get(t, 0) + n
    add('精炼炉', 34); add('粉碎机', 34)          # 蓝铁矿 → 蓝铁块 → 蓝铁粉末
    add('粉碎机', 18)                              # 源矿 → 源石粉末
    add('研磨机', 17 + 9)                          # 致密蓝铁、致密源石
    add('采种机', 11 + 6); add('种植机', 2 * (11 + 6)); add('粉碎机', 11 + 6)  # 植物单元
    add('研磨机', 6)                               # 细磨荞花
    add('精炼炉', 17)                              # 制钢
    add('配件机', 6); add('塑形机', 6); add('封装机', 3); add('灌装机', 3)
    sand_channels_max = 11 * 3
    sand_need = Q(17) + 9 + 4 + 2 * Q(3, 4)       # 32 台研磨机的砂叶粉末（第三台灌装机的两台荞花研磨机各 3/4）
    steel = 6 + 10 + 1
    bottles = 5 * 1 + Q(1, 2)                      # 5 台双路塑形机各 1/tick，单路 1/2
    capsule = 2 * Q(1, 5) + Q(3, 2) / 10           # 前两台 1/5，第三台瓶 3/2 每 10 瓶一粒
    battery = 3 * Q(1, 5)
    iron_ore = 17 * 2                              # 17 台致密蓝铁研磨机各 2 件蓝铁粉末/tick
    source_ore = 9 * 2
    return {'counts': m, 'total': sum(m.values()), 'sand_channels_max': sand_channels_max, 'sand_channels_used': 32,
            'sand_need_per_tick': str(sand_need), 'steel_refineries': steel, 'bottles_per_tick': str(bottles),
            'capsule_per_tick': str(capsule), 'battery_per_tick': str(battery),
            'iron_ore_per_tick': iron_ore, 'source_ore_per_tick': source_ore}


def main():
    rec = parse_recipes()
    out = {'A_bounds': solve_bounds(rec), 'B_grinder_yi': grinder_transitions(), 'C_bing_reading': bing_reading(),
           'D_pure_feed': pure_feed_enum(), 'E_ding_reading': ding_reading(), 'F_quota_line': quota_line_witness(),
           'G_merger': merger_witness(), 'H_skeleton': skeleton_counts()}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
