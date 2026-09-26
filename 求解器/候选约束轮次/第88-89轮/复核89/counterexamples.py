#!/usr/bin/env python3
"""第 89 轮复核的局部反例，逐判定复算（整数 tick、固定判定次序；第 13 项本身限定整数 tick 同相位）。
A  第 13 项：源头是会做两种 1tick 配方的粉碎机，取货格里是它的另一种产物，专线头是只放行原料 i 的准入口 → X 永远空手。
B  第 13 项：起点是「设为蓝铁矿」的仓库取货口，专线给要源矿的粉碎机，头上是只放行源矿的准入口 → X 永远空手。
C  第 13 项：源头精炼炉另一条出口是每 5 tick 限 1 件的准入口；每个时刻判定做完后它都处在断开状态，
   「此刻的取货通道」只有 1 条 ≤ 每批件数 1，X 却每 5 tick 空手 1 次。
E  第 13 项：源头粉碎机交替做砂叶、荞花（都是 1tick），两条出口（≤ 荞花一批 2 件），砂叶粉末专线头是只放行砂叶粉末的准入口，
   另一条出口是普通传送带；源头每刻不空手，X（研磨机，蓝铁粉末两路纯料）仍周期性空手。
D  第 10 项：按「单元」只取拓扑的读法，C 的存货格里留 1 件源矿（误料），Φ0 ≥ S+1/2，循环态中 C、B、K 都空手。
输出 JSON。"""
import sys, json
sys.path.insert(0, __import__('os').path.dirname(__file__))
import evsim
from evsim import World, Cell, Line, Sink, Source, Gate, make_machine


def cells(n, name, gate_first=None):
    cs = [Cell('%s%d' % (name, i)) for i in range(n)]
    if gate_first is not None:
        cs[0].gate = gate_first
    return cs


def run_fixed(w, T, check):
    w.random_order = False
    w.t = 0
    w.closure()
    check(w)
    w.post.append(check)
    w.run_until(T)


def case_A():
    evsim.CAP = 50
    w = World(1)
    Y = w.add_machine(make_machine('Y', '粉碎机'))
    X = w.add_machine(make_machine('X', '精炼炉'))
    # Y 的进料：一条蓝铁块专线（无限源）；调试结束时 Y 取货格里留着 1 件源石粉末（它自己的产物之一）
    w.add_line(Line(Source('蓝铁块'), cells(2, 'F'), Y, 'F'))
    Y.out = ['源石粉末', 1]
    Y.cache = [[r for r in Y.recipes if r.out == '蓝铁粉末'][0], 0]    # 做好的一批蓝铁粉末
    # Y -> X：专线，头一格是只放行蓝铁粉末、不设上限的物品准入口，其后两格传送带
    w.add_line(Line(Y, cells(3, 'L', Gate(fil='蓝铁粉末')), X, 'L'))
    w.add_line(Line(X, cells(1, 'XO'), Sink(name='XS'), 'XO'))
    log = dict(x_empty=0, y_empty=0, closures=0, y_channels_connected_max=0)
    def chk(wd):
        log['closures'] += 1
        log['x_empty'] += X.cache is None
        log['y_empty'] += Y.cache is None
        g = wd.lines[1].cells[0].gate
        conn = int(Y.out is None or g.ok(Y.out[0], wd.t, wd.Q))
        log['y_channels_connected_max'] = max(log['y_channels_connected_max'], conn)
    run_fixed(w, 60, chk)
    log['final'] = dict(Y_out=Y.out, Y_cache_done=Y.cache is not None, X_grid=X.grid, X_cache=X.cache is not None)
    return log


def case_B():
    evsim.CAP = 50
    w = World(1)
    X = w.add_machine(make_machine('X', '粉碎机'))
    w.add_line(Line(Source('蓝铁矿'), cells(3, 'L', Gate(fil='源矿')), X, 'L'))
    w.add_line(Line(X, cells(1, 'XO'), Sink(name='XS'), 'XO'))
    log = dict(x_empty=0, closures=0)
    def chk(wd):
        log['closures'] += 1
        log['x_empty'] += X.cache is None
    run_fixed(w, 40, chk)
    return log


def case_C():
    evsim.CAP = 50
    w = World(1)
    Y = w.add_machine(make_machine('Y', '精炼炉'))
    X = w.add_machine(make_machine('X', '粉碎机'))
    w.add_line(Line(Source('蓝铁矿'), cells(2, 'F'), Y, 'F'))
    # 次序：先列 G 那条（固定判定次序里 G 先试），再列 Y->X 专线
    G = Gate(fil='蓝铁块', k5=1)
    lg = w.add_line(Line(Y, [Cell('G', G), Cell('G1')], Sink(name='GS'), 'G'))
    lx = w.add_line(Line(Y, cells(3, 'L'), X, 'L'))
    w.add_line(Line(X, cells(1, 'XO'), Sink(name='XS'), 'XO'))
    # 起态：路满、Y 存货 50、取货 0、缓存一批刚开工（整数相位）
    Y.grid[0] = ['蓝铁矿', 50]
    for c in w.lines[0].cells:
        c.kind, c.entry = '蓝铁矿', 0
    for c in lx.cells:
        c.kind, c.entry = '蓝铁块', 0
    X.grid[0] = ['蓝铁块', 1]
    trace = []
    def chk(wd):
        conn = 1 + int(G.ok('蓝铁块', wd.t, wd.Q))           # 此刻接通的取货通道条数
        trace.append((wd.t, X.cache is not None, Y.cache is not None, conn, X.stock('蓝铁块')))
    run_fixed(w, 200, chk)
    # 取第 100—199 tick
    tail = [r for r in trace if 100 <= r[0] < 200]
    return dict(ticks=len(tail), x_empty=sum(1 for r in tail if not r[1]), y_empty=sum(1 for r in tail if not r[2]),
                max_connected_channels=max(r[3] for r in tail),
                sample=[r for r in trace if 150 <= r[0] < 161])


def case_D():
    evsim.CAP = 50
    w = World(1)
    C = w.add_machine(make_machine('C', '采种机'))
    A = w.add_machine(make_machine('A', '种植机'))
    B = w.add_machine(make_machine('B', '种植机'))
    K = w.add_machine(make_machine('K', '粉碎机'))
    L1, L2, L3, L4 = 3, 3, 2, 2
    CA = w.add_line(Line(C, cells(L1, 'CA'), A, 'CA'))
    CB = w.add_line(Line(C, cells(L3, 'CB'), B, 'CB'))
    AC = w.add_line(Line(A, cells(L2, 'AC'), C, 'AC'))
    BK = w.add_line(Line(B, cells(L4, 'BK'), K, 'BK'))
    KX = [w.add_line(Line(K, cells(1, 'KX%d' % j), Sink(name='KS'), 'KX')) for j in range(2)]
    for c in CA.cells:
        c.kind, c.entry = '荞花种子', 0
    for c in AC.cells:
        c.kind, c.entry = '荞花', 0
    A.grid[0] = ['荞花种子', 20]
    C.grid[0] = ['源矿', 1]           # 调试遗留：采种机任何配方都不用的误料
    S = L1 + L2 + 2
    phi = L1 + 20 + L2                 # CA + A 存货 + AC（其余为 0）
    log = dict(S=S, phi0=phi, threshold=S + 0.5)
    emp = dict(C=0, B=0, K=0, closures=0)
    def chk(wd):
        if wd.t >= 100:
            emp['closures'] += 1
            for nm, m in (('C', C), ('B', B), ('K', K)):
                emp[nm] += m.cache is None
    run_fixed(w, 140, chk)
    log['empty_after_t100'] = emp
    log['C_grid'] = C.grid
    return log


class AltSource(Source):
    """按固定次序交替给出物品的来源（代替一个把两条纯料带交替并成一条的汇流器，只用于构造源头的进料）。"""
    def __init__(self, kinds):
        self.name = 'alt'
        self._kinds, self._i = kinds, 0

    @property
    def kind(self):
        return self._kinds[self._i % len(self._kinds)]


def case_E():
    evsim.CAP = 50
    w = World(1)
    Y = w.add_machine(make_machine('Y', '粉碎机'))
    X = w.add_machine(make_machine('X', '研磨机'))
    alt = AltSource(['砂叶', '荞花'])
    fl = w.add_line(Line(alt, cells(2, 'F'), Y, 'F'))
    def adv(wd, a):
        if a is not None and a[0] == 0 and wd.lines[a[1]] is fl:
            alt._i += 1
    w.observers.append(adv)
    lq = w.add_line(Line(Y, cells(2, 'Q'), Sink(name='QS'), 'Q'))       # 另一条出口：普通传送带，什么都收
    ls = w.add_line(Line(Y, cells(3, 'S', Gate(fil='砂叶粉末')), X, 'S'))
    for j in range(2):
        w.add_line(Line(Source('蓝铁粉末'), cells(2, 'B'), X, 'B'))
    w.add_line(Line(X, cells(1, 'XO'), Sink(name='XS'), 'XO'))
    trace = []
    def chk(wd):
        trace.append((wd.t, X.cache is not None, Y.cache is not None, None if Y.out is None else tuple(Y.out)))
    run_fixed(w, 300, chk)
    tail = [r for r in trace if 200 <= r[0] < 300]
    return dict(ticks=len(tail), x_empty=sum(1 for r in tail if not r[1]), y_empty=sum(1 for r in tail if not r[2]),
                x_sand_received_per_tick=ls.delivered / 300, sample=[r for r in trace if 200 <= r[0] < 212])


if __name__ == '__main__':
    print(json.dumps(dict(A=case_A(), B=case_B(), C=case_C(), D=case_D(), E=case_E()), ensure_ascii=False, indent=1, default=str))
