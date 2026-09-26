#!/usr/bin/env python3
"""三审第 88—89 轮修正版自写的逐事件模拟器（只用标准库）。

按正式规则建模，时间取整数，单位 1/Q tick，不同单位的事件可以落在不同的余数（相位）上：
- 运输物品格上限 1，物品进格后至少停 Q 个单位（滞留 1 tick）才能走；移动零时。
- 同一时刻的判定逐个做，做到没有可动为止（闭合）；对手模式下每一步从能动的判定里随机挑，
  这包含全部判定先后、轮询与接通先后（离线改接通先后只改这些先后）；确定模式下按固定次序，
  制造单位的几条取货通道按轮询指针轮流尝试。
- 制造单位：存货物品格（小、中 1 格，大 2 格，同种只占一格，上限 50），缓存格一次一批，
  存货够一批且缓存格空就当刻开批，d tick 后做完，取货物品格放得下（同种、合计不超 50）就整批进格；
  取货物品格经各条取货通道逐件出货。
- 矿石来源（仓库取货口、协议核心取货端口）：首运输物品格空着就补一件矿石。
- 汇（协议核心的存货端口或一般的收货端）：开着就收，停收时拒收。

只模拟专用进路：每个运输物品格只从前一格（或起点）收货、只往后一格（或终点）送货。
"""
import heapq
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RULES = REPO / '《明日方舟：终末地》游戏规则.txt'


def parse_recipes():
    """从正式游戏规则现读配方：{机型: [(输入{物品:件数}, 产物, 件数, 时长)]}。"""
    text = RULES.read_text().split('\n配方\n', 1)[1]
    out = {}
    cur = None
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            continue
        if '→' not in s:
            cur = s
            out[cur] = []
            continue
        lhs, rhs = s.split('→')
        rhs, dur = rhs.split('，')
        ins = {}
        for part in re.split('＋', lhs):
            m = re.match(r'\s*(\d+)\s*(\S+)\s*', part)
            ins[m.group(2)] = int(m.group(1))
        m = re.match(r'\s*(\d+)\s*(\S+)\s*', rhs)
        d = int(re.match(r'\s*(\d+)', dur).group(1))
        out[cur].append((ins, m.group(2), int(m.group(1)), d))
    assert sorted(out) == sorted(NSTORE_KEYS) and sum(len(v) for v in out.values()) == 18, out
    return out


NSTORE_KEYS = ['粉碎机', '精炼炉', '配件机', '塑形机', '采种机', '种植机', '研磨机', '封装机', '灌装机']
RECIPES = None
NSTORE = {'粉碎机': 1, '精炼炉': 1, '配件机': 1, '塑形机': 1, '采种机': 1, '种植机': 1,
          '研磨机': 2, '封装机': 2, '灌装机': 2}
RECIPES = parse_recipes()


class Net:
    """一张只含专用进路的网络。实体键：('c', i) 运输物品格、('m', i) 制造单位、('o', i) 矿石来源、('s', i) 汇。"""

    def __init__(self, Q, rng):
        self.Q = Q
        self.rng = rng
        self.cells = []      # [item, tin, nxt, prv]
        self.machs = []      # dict
        self.ores = []       # [item, cell]
        self.sinks = []      # dict(open, feed=[cells], got={})
        self.t = 0
        self.heap = []
        self.work = set()    # 待查的实体
        self.wlist = []      # 对手模式：随机取用的列表；确定模式：最小堆
        self.adv = True      # 对手模式
        self.on_take = None  # 回调：制造单位经取货通道出货 (m, cell)
        self.on_leave = None  # 回调：物品离开运输物品格 (cell)
        self.on_ore = None   # 回调：矿石进首格 (ore)

    # ---------- 建网 ----------
    def cell(self):
        self.cells.append([None, 0, None, None])
        return len(self.cells) - 1

    def mach(self, name, typ, recipe_idx=None):
        rec = RECIPES[typ] if recipe_idx is None else [RECIPES[typ][recipe_idx]]
        self.machs.append(dict(name=name, typ=typ, rec=rec, ns=NSTORE[typ], store={}, cache=None,
                               pk_item=None, pk_n=0, exits=[], inputs=[], ptr=0, powered=True))
        return len(self.machs) - 1

    def ore(self, item):
        self.ores.append([item, None])
        return len(self.ores) - 1

    def sink(self, name):
        self.sinks.append(dict(name=name, open=True, feed=[], got={}))
        return len(self.sinks) - 1

    def line(self, src, dst, n):
        """src: ('m', i) 或 ('o', i)；dst: ('m', i) 或 ('s', i)；n 个运输物品格。返回格号列表（首格在前）。"""
        cs = [self.cell() for _ in range(n)]
        for k, c in enumerate(cs):
            self.cells[c][3] = src if k == 0 else ('c', cs[k - 1])
            self.cells[c][2] = dst if k == n - 1 else ('c', cs[k + 1])
        if src[0] == 'm':
            self.machs[src[1]]['exits'].append(cs[0])
        else:
            self.ores[src[1]][1] = cs[0]
        if dst[0] == 'm':
            self.machs[dst[1]]['inputs'].append(cs[-1])
        else:
            self.sinks[dst[1]]['feed'].append(cs[-1])
        return cs

    # ---------- 规则 ----------
    def accepts(self, m, item):
        st = m['store']
        if item in st:
            return st[item] < 50
        if not any(item in ins for ins, _, _, _ in m['rec']):
            # 误料：规则里存货物品格不限种类，本模拟的专用进路只送本线物品，不会出现
            pass
        return len(st) < m['ns']

    def can_start(self, m):
        if m['cache'] is not None or not m['powered']:
            return None
        for r in m['rec']:
            ins = r[0]
            if all(m['store'].get(k, 0) >= v for k, v in ins.items()):
                return r
        return None

    def wake(self, key):
        if key not in self.work:
            self.work.add(key)
            if self.adv:
                self.wlist.append(key)
            else:
                heapq.heappush(self.wlist, key)

    def set_mode(self, adv):
        self.adv = adv
        keys = list(self.work)
        self.work = set()
        self.wlist = []
        for k in keys:
            self.wake(k)

    def sched(self, when, key):
        heapq.heappush(self.heap, (when, key))

    def put(self, c, item):
        cc = self.cells[c]
        assert cc[0] is None
        cc[0] = item
        cc[1] = self.t
        self.sched(self.t + self.Q, ('c', c))
        self.wake(('c', c))

    def vacate(self, c):
        cc = self.cells[c]
        cc[0] = None
        if self.on_leave:
            self.on_leave(c)
        self.wake(cc[3])

    def act_cell(self, c):
        cc = self.cells[c]
        if cc[0] is None or self.t < cc[1] + self.Q:
            return False
        kind, j = cc[2]
        item = cc[0]
        if kind == 'c':
            if self.cells[j][0] is not None:
                return False
            self.vacate(c)
            self.put(j, item)
            return True
        if kind == 'm':
            m = self.machs[j]
            if not self.accepts(m, item):
                return False
            m['store'][item] = m['store'].get(item, 0) + 1
            self.vacate(c)
            self.wake(('m', j))
            return True
        s = self.sinks[j]
        if not s['open']:
            return False
        s['got'][item] = s['got'].get(item, 0) + 1
        self.vacate(c)
        return True

    def mach_options(self, i):
        m = self.machs[i]
        opts = []
        cache = m['cache']
        if cache is not None and self.t >= cache[2]:
            it, n, _ = cache
            if (m['pk_item'] in (None, it)) and m['pk_n'] + n <= 50:
                opts.append(('xfer',))
        if self.can_start(m):
            opts.append(('start',))
        if m['pk_n'] > 0:
            for k, c in enumerate(m['exits']):
                if self.cells[c][0] is None:
                    opts.append(('exit', k))
        return opts

    def act_mach(self, i):
        m = self.machs[i]
        opts = self.mach_options(i)
        if not opts:
            return False
        if self.adv:
            op = self.rng.choice(opts)
        else:
            op = None
            for o in opts:
                if o[0] in ('xfer', 'start'):
                    op = o
                    break
            if op is None:
                n = len(m['exits'])
                free = {o[1] for o in opts}
                for step in range(n):
                    k = (m['ptr'] + step) % n
                    if k in free:
                        op = ('exit', k)
                        m['ptr'] = (k + 1) % n
                        break
                    # 这条没能取（首格占着），权限传给下一条
                assert op is not None
        if op[0] == 'xfer':
            it, n, _ = m['cache']
            m['cache'] = None
            m['pk_item'] = it
            m['pk_n'] += n
            self.wake(('m', i))
            return True
        if op[0] == 'start':
            ins, out, n, d = self.can_start(m)
            for k, v in ins.items():
                m['store'][k] -= v
                if m['store'][k] == 0:
                    del m['store'][k]
            m['cache'] = (out, n, self.t + d * self.Q)
            self.sched(self.t + d * self.Q, ('m', i))
            for c in m['inputs']:
                self.wake(('c', c))
            self.wake(('m', i))
            return True
        k = op[1]
        c = m['exits'][k]
        m['pk_n'] -= 1
        it = m['pk_item']
        if m['pk_n'] == 0:
            m['pk_item'] = None
        self.put(c, it)
        if self.on_take:
            self.on_take(i, c)
        self.wake(('m', i))
        return True

    def act_ore(self, o):
        item, c = self.ores[o]
        if self.cells[c][0] is not None:
            return False
        self.put(c, item)
        if self.on_ore:
            self.on_ore(o)
        return True

    def act(self, key):
        kind, i = key
        if kind == 'c':
            return self.act_cell(i)
        if kind == 'm':
            return self.act_mach(i)
        if kind == 'o':
            return self.act_ore(i)
        if kind == 's':
            for c in self.sinks[i]['feed']:
                self.wake(('c', c))
            return False
        return False

    def closure(self):
        work, wl, rng = self.work, self.wlist, self.rng
        while wl:
            if self.adv:
                i = rng.randrange(len(wl))
                key = wl[i]
                wl[i] = wl[-1]
                wl.pop()
            else:
                key = heapq.heappop(wl)
            work.discard(key)
            if self.act(key):
                self.wake(key)

    def next_time(self):
        while self.heap:
            return self.heap[0][0]
        return None

    def advance_to(self, t):
        """处理时刻 ≤ t 的全部事件（逐个时刻闭合），停在 t。"""
        while self.heap and self.heap[0][0] <= t:
            tt = self.heap[0][0]
            self.t = tt
            while self.heap and self.heap[0][0] == tt:
                _, key = heapq.heappop(self.heap)
                self.wake(key)
            self.pre_closure()
            self.closure()
            self.post_closure()
        self.t = t

    # 钩子，子类改写
    def pre_closure(self):
        pass

    def post_closure(self):
        pass

    def start(self, t0):
        """把全部实体唤醒，在 t0 做一次闭合。"""
        self.t = t0
        for i in range(len(self.cells)):
            self.wake(('c', i))
        for i in range(len(self.machs)):
            self.wake(('m', i))
            m = self.machs[i]
            if m['cache'] is not None and m['cache'][2] > t0:
                self.sched(m['cache'][2], ('m', i))
        for i in range(len(self.ores)):
            self.wake(('o', i))
        for i, cc in enumerate(self.cells):
            if cc[0] is not None and cc[1] + self.Q > t0:
                self.sched(cc[1] + self.Q, ('c', i))
        self.pre_closure()
        self.closure()
        self.post_closure()

    def set_sink(self, s, is_open):
        self.sinks[s]['open'] = is_open
        if is_open:
            self.wake(('s', s))

    def poke(self):
        """外部改变（收货端开关）发生在当前时刻 self.t：接着在这一时刻做到闭合。"""
        if self.wlist:
            self.pre_closure()
            self.closure()
            self.post_closure()

    def snapshot(self):
        """时刻 self.t 的状态（相对时间）。"""
        Q, t = self.Q, self.t
        cs = tuple((cc[0], min(t - cc[1], Q)) if cc[0] is not None else None for cc in self.cells)
        ms = tuple((tuple(sorted(m['store'].items())),
                    None if m['cache'] is None else (m['cache'][0], max(m['cache'][2] - t, 0)),
                    m['pk_item'], m['pk_n'], m['ptr']) for m in self.machs)
        ss = tuple(s['open'] for s in self.sinks)
        return hash((cs, ms, ss))
