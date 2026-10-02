#!/usr/bin/env python3
"""复核100S2 引擎乙：用项目独立模拟器 sim2（只读导入，不改源文件）跑同一张图，
与引擎甲逐步比对完整状态。

sim2 的两处已知错误（同种唯一、按元件判断不移回）在本图不触发：每格只放本线物品，
全部移动都沿纯带向前。sim2 的收货按现行第31行（最先判定的上游带动），本图每个
机器的元件上游都只有层数1的纯带、互相不经别的单位相连，这一差别只改判定先后、不改结果；
比对就是这句话的程序核验。
"""
import sys
sys.path.insert(0, '/home/zhuran24/zmd-research-fresh/求解器/规则修订/2026-09-30-迟滞/sim2')
import simulator as S  # noqa: E402
from net import BAT, CAP  # noqa: E402


class CoreSink(S.Sink):
    def __init__(self, fa):
        super().__init__('核心收')
        self.fa = fa
        self.count = {BAT: 0, CAP: 0}

        self.cap_left = {BAT: None, CAP: None}

    def can_accept(self, item, w):
        if not self.fa.accept[item.kind]:
            return False
        left = self.cap_left[item.kind]
        return left is None or left > 0

    def receive(self, item, w):
        self.count[item.kind] += 1
        if self.cap_left[item.kind] is not None:
            self.cap_left[item.kind] -= 1


def build_from(fa):
    """按引擎甲实例 fa 的图、路长与接通先后搭 sim2 世界。fa 必须处于初始状态。"""
    nodes, lookup = [], {}
    for m in fa.mach.values():
        rec = S.Recipe(m.name, tuple(m.inputs.items()), m.product, m.qty, m.dur)
        sm = S.Machine(m.name, auxiliary=(m.ncells == 2), recipes=[rec])
        sm.slots = [[S.Item(k, -100) for _ in range(n)] if k else [] for k, n in m.cells]
        while len(sm.slots) < m.ncells:
            sm.slots.append([])
        sm.output = [S.Item(m.product, -100) for _ in range(m.take)]
        if m.cache is not None:
            assert m.cache[0] == 'done'
            sm.cache = [S.Item(m.product, -100) for _ in range(m.cache[1])]
        nodes.append(sm)
        lookup[m.name] = sm
    sources = []
    for s in fa.src.values():
        ss = S.Source(s.name, kinds=(s.kind,))
        nodes.append(ss)
        lookup[s.name] = ss
        sources.append(ss)
    sink = CoreSink(fa)
    nodes.append(sink)
    belts = {}
    for b in fa.belts:
        sb = S.Belt(f'带{b.idx}', b.tiles)
        if b.dst != '核心':
            sb.fill(b.kind, entered=-8)
        nodes.append(sb)
        belts[b.idx] = sb
        src = lookup[b.src]
        dst = sink if b.dst == '核心' else lookup[b.dst]
        src.connect(sb, connected=rank_of(fa, b, 'in'))
        sb.connect(dst, connected=rank_of(fa, b, 'out'))
    return nodes, sources, lookup, belts, sink


def rank_of(fa, b, side):
    keys = sorted([(x.conn_in, 'in', x.idx) for x in fa.belts] + [(x.conn_out, 'out', x.idx) for x in fa.belts])
    if not hasattr(fa, '_rank'):
        fa._rank = {(s, i): r for r, (_, s, i) in enumerate(keys)}
    return fa._rank[(side, b.idx)]


def make_world(fa):
    nodes, sources, lookup, belts, sink = build_from(fa)
    comps = [belts[b.idx].name for b in fa.elem_order]
    nts = [u.name for u in fa.nt_order if u.name in lookup and not isinstance(lookup[u.name], S.Source)]
    sched = dict(choices={}, order=comps + nts)
    w = S.World(nodes, sources=sources, schedule=sched)
    return w, lookup, belts, sink


def reconnect(fa, w, lookup, belts, keep):
    """引擎甲已做 offline() 之后，把新的接通先后搬进 sim2 世界。"""
    if hasattr(fa, '_rank'):
        del fa._rank
    for b in fa.belts:
        sb = belts[b.idx]
        c_in = sb.input_channels[0]
        c_out = sb.output_channels[0]
        c_in.connected = rank_of(fa, b, 'in')
        c_out.connected = rank_of(fa, b, 'out')
    comps = [belts[b.idx] for b in fa.elem_order]
    nts = [lookup[u.name] for u in fa.nt_order if u.name in lookup and not isinstance(lookup[u.name], S.Source)]
    rest = [u for u in w.order if u not in comps and u not in nts]
    w.order = comps + nts + rest
    for u in w.nodes:
        if not keep:
            for c in u.output_channels:
                u.last_output[c] = -1
            u.input_cursor = 0
            u.output_cursor = 0
    if keep:
        # 收货轮询起点：按引擎甲记住的「上次成功的那条」换算成新排序下的下标
        for m in fa.mach.values():
            sm = lookup[m.name]
            arr = sorted(sm.input_channels, key=lambda c: c.connected)
            if m.cursor is None:
                sm.input_cursor = 0
            else:
                tgt = belts[m.cursor.idx]
                k = [c.src for c in arr].index(tgt)
                sm.input_cursor = (k + 1) % len(arr)


def sim2_state(fa, w, lookup, belts):
    t = w.t
    out = []
    for m in fa.mach.values():
        sm = lookup[m.name]
        cells = []
        for s in sm.slots:
            cells.append((s[0].kind if s else None, len(s)))
        if sm.running is not None:
            cs = 1000 + sm.remaining - 1
        elif sm.cache:
            cs = -len(sm.cache)
        else:
            cs = 0
        out.append((tuple(cells), len(sm.output), cs))
    for b in fa.belts:
        sb = belts[b.idx]
        out.append(tuple(-1 if e is None else min(8, t - e.entered) for e in sb.cells))
    return tuple(out)


def a_state(fa):
    t = fa.t
    out = []
    for m in fa.mach.values():
        cells = tuple((c[0] if c[1] > 0 else None, c[1]) for c in m.cells)
        c = m.cache
        cs = 0 if c is None else (1000 + c[1] - t if c[0] == 'run' else -c[1])
        out.append((cells, m.take, cs))
    for b in fa.belts:
        out.append(tuple(-1 if e is None else min(8, t - e) for e in b.cells))
    return tuple(out)
