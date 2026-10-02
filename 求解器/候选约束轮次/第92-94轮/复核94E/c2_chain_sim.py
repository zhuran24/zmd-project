#!/usr/bin/env python3
"""复核94E 编码二：按快照规则逐步运行「源→分流器 X→活支（带/准入口串）→汇；X→断头支」的确定性模拟。

自写，不导入 sim2 或推导席脚本。规则落实：
- 第 25—27 行：每步先结束到时的制造（此处无制造），再按层数从小到大判定元件，同层按送货通道最早接通的先（对同层元件全排列枚举），
  然后判定非运输单位（源头往 X 送一件；汇不送货）。
- 第 26 行：每个元件、非运输单位每步只判定一次，一次至多送出一件。
- 第 23 行：运输物品格里停留至少 8 步才能离格；带内各格各自计滞留，带内前挪随时进行（每次判定后、每步开头都从后往前级联）。
- 第 28 行：元件送往的单位里若有还往下送货的元件，层数=其中一个的层数+1，否则 1；X 有两支可数时两种取法都枚举。
- 第 31 行：每个单位只有一个元件上游（链状），一起判定不改变次序；X 是分流器不参加。
- 第 32 行：分流器按接通先后轮询，第一次从第二条接通的通道开始，此后从上次成功的下一条开始；两种接通先后都枚举。
- 第 65 行：准入口未设任何限制，相当于 1 格元件。
输出：循环态里 X 每 tick 平均送往活支的件数（精确分数），以及各元件层数。
"""
import itertools, json
from fractions import Fraction

E = None  # 空格


class Elem:
    def __init__(self, name, ncell):
        self.name = name
        self.cells = [E] * ncell  # 每格存进格步号
        self.down = None  # 下游单位（Elem 或 'SINK' 或 None）

    def has_out(self):
        return self.down is not None


def build(n, live_tail, dead):
    """live_tail: 首段带之后的元件格数列表（准入口=1，带=格数，带与准入口交替）；dead: 断头支各元件格数。"""
    B = Elem('B', n)
    live = [B]
    for j, c in enumerate(live_tail):
        live.append(Elem(f'L{j+2}', c))
    for a, b in zip(live, live[1:]):
        a.down = b
    live[-1].down = 'SINK'
    D = [Elem(f'D{j+1}', c) for j, c in enumerate(dead)]
    for a, b in zip(D, D[1:]):
        a.down = b
    D[-1].down = None  # 断头
    X = Elem('X', 1)
    return X, live, D


def layers(X, live, D, x_choice):
    lay = {}
    def lay_of(e):
        if e.name in lay:
            return lay[e.name]
        d = e.down
        if isinstance(d, Elem) and d.has_out():
            v = lay_of(d) + 1
        else:
            v = 1
        lay[e.name] = v
        return v
    for e in live + D:
        lay_of(e)
    opts = {}
    if live[0].has_out():
        opts['live'] = lay['B'] + 1
    if D[0].has_out():
        opts['dead'] = lay[D[0].name] + 1
    if not opts:
        lay['X'] = 1
    else:
        lay['X'] = opts[x_choice] if x_choice in opts else None
    return lay, opts


def run(n, live_tail, dead, x_choice, tie_perm_index, conn_live_first, maxsteps=200000):
    X, live, D = build(n, live_tail, dead)
    lay, opts = layers(X, live, D, x_choice)
    if lay['X'] is None:
        return None
    elems = [X] + live + D
    groups = {}
    for e in elems:
        groups.setdefault(lay[e.name], []).append(e)
    # 同层全排列，取第 tie_perm_index 组合
    perms = [list(itertools.permutations(groups[l])) for l in sorted(groups)]
    combos = list(itertools.product(*perms))
    if tie_perm_index >= len(combos):
        return 'skip'
    order = [e for grp in combos[tie_perm_index] for e in grp]
    chans = [live[0], D[0]] if conn_live_first else [D[0], live[0]]
    rr = [1]  # 第一次从第二条接通的开始
    t = 0
    sent_live = []

    def settle():
        for e in live + D:
            c = e.cells
            for i in range(len(c) - 2, -1, -1):
                if c[i] is not E and c[i + 1] is E and t - c[i] >= 8:
                    c[i + 1] = t; c[i] = E

    def accept(u):
        return u.cells[0] is E

    def judge(e):
        c = e.cells
        if c[-1] is E or t - c[-1] < 8:
            return 0
        if e is X:
            k = len(chans)
            for j in range(k):
                i = (rr[0] + j) % k
                tgt = chans[i]
                if accept(tgt):
                    tgt.cells[0] = t; c[-1] = E; rr[0] = (i + 1) % k
                    return 1 if tgt is live[0] else 0
            return 0
        d = e.down
        if d == 'SINK':
            c[-1] = E; return 0
        if d is None:
            return 0
        if accept(d):
            d.cells[0] = t; c[-1] = E
        return 0

    seen = {}
    while t < maxsteps:
        key = (tuple(tuple(E if v is E else min(t - v, 8) for v in e.cells) for e in elems), rr[0])
        if key in seen:
            t0 = seen[key]
            cyc = sent_live[t0:]
            return dict(rate=Fraction(8 * sum(cyc), len(cyc)), cycle_steps=len(cyc), layers=lay, x_opts=opts,
                        order=[e.name for e in order])
        seen[key] = t
        settle()
        s = 0
        for e in order:
            s += judge(e)
            settle()
        # 非运输单位：源头往 X 送一件
        if X.cells[0] is E:
            X.cells[0] = t
        settle()
        sent_live.append(s)
        t += 1
    raise RuntimeError('no cycle')


def main():
    rows = []
    for n in (1, 2, 3):
        for m in (2, 3, 4):
            # 活支：B(n) 之后交替 准入口(1)、带(1)…，共 m 个元件
            tail = [1 if j % 2 == 0 else 1 for j in range(m - 1)]
            for k in (1, 2, 3, 4, 5):
                for dead_kind in ('gates', 'belt_first'):
                    dead = [1] * k if dead_kind == 'gates' else ([2] + [1] * (k - 1))
                    for choice in ('live', 'dead'):
                        for conn in (True, False):
                            idx = 0
                            while True:
                                r = run(n, tail, dead, choice, idx, conn)
                                if r == 'skip':
                                    break
                                if r is None:
                                    break
                                lay = r['layers']
                                xo = r['order'].index('X'); bo = r['order'].index('B')
                                x_first = xo < bo
                                pred = Fraction(8 * n, 8 * n + 1) if x_first else Fraction(1)
                                rows.append(dict(n=n, m=m, k=k, dead_kind=dead_kind, x_choice=choice, conn_live_first=conn,
                                                 perm=idx, layer_X=lay['X'], layer_B=lay['B'], x_before_B=x_first,
                                                 rate=str(r['rate']), predicted=str(pred), match=(r['rate'] == pred)))
                                idx += 1
    # 汇总：候选二的判断
    bad = [r for r in rows if not r['match']]
    summary = {}
    for r in rows:
        key = (r['m'], r['k'], r['x_choice'])
        s = summary.setdefault(str(key), set())
        s.add(r['rate'])
    out = dict(cases=len(rows), mismatches=len(bad), mismatch_rows=bad[:20],
               summary={k: sorted(v) for k, v in summary.items()}, rows=rows)
    json.dump(out, open(__file__.replace('.py', '.json'), 'w'), ensure_ascii=False, indent=1)
    print('cases', len(rows), 'mismatches', len(bad))
    for k, v in sorted(out['summary'].items()):
        print(k, v)
    # 候选二的条文核对：按断支数层（choice=dead）且 k>=2 时，k<m 必降速；k=m 时存在 X 先判的次序且降速；k>m 不降速
    chk = []
    for r in rows:
        if r['x_choice'] != 'dead' or r['k'] < 2:
            continue
        slow = r['rate'] != '1'
        if r['k'] < r['m']:
            chk.append(('k<m', slow))
        elif r['k'] == r['m']:
            chk.append(('k=m', slow == r['x_before_B']))
        else:
            chk.append(('k>m', not slow))
    print('candidate2 checks', {c: (sum(1 for a, b in chk if a == c and b), sum(1 for a, b in chk if a == c)) for c in ('k<m', 'k=m', 'k>m')})


if __name__ == '__main__':
    main()
