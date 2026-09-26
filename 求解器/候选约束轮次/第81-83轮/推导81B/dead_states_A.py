#!/usr/bin/env python3
"""第81轮B 编码A：从前提快照解析配方，对九种制造单位的存货格做显式状态搜索。

状态只含存货格（每格：空，或一种物品及件数1..50）；到件与开批两种转移：
  到件 k：有放 k 且未满 50 的格就放进去；否则若没有格放着 k 且有空格，占一个空格；否则拒收。
  开批：存货格内容满足某配方用量就可开批（取货侧假定总能腾空，这是对“活”最宽的假定）。
活态：存在一串到件使之后能开批。死态＝非活态（任何到件序列都开不了批）。
首件死锁：给定存货通道首件的种类集合 H（首件单位只有一个出口，被拒就永远停在那里），
  当前开不了批且 H 中每一种都被拒收。
配方解析与 81A 独立写；件数上限、格数取自规则文字。
"""
import itertools, json, hashlib, os, re
from pathlib import Path

os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
HERE = Path(__file__).resolve().parent
SNAP = HERE.parent / '前提快照'
RULE = (SNAP / '《明日方舟：终末地》游戏规则.txt').read_text()
CAP = 50
WRONG = '误料'


def parse():
    # 机型所属大小类
    cls = {}
    cur = None
    for line in RULE.splitlines():
        s = line.strip()
        m = re.match(r'(小|中|大)制造单位：.*?(\d) 个存货物品格', s)
        if m:
            cur = int(m.group(2))
            continue
        if s.endswith('单位：') or s.endswith('单位') or s.startswith('运输单位') or s.startswith('仓储') or s.startswith('供电') or s == '':
            if not m:
                cur = None if (s.startswith('运输') or s.startswith('仓储') or s.startswith('供电')) else cur
            continue
        if cur is not None and re.fullmatch(r'[一-鿿]+', s):
            cls[s] = cur
    # 配方
    rec = {}
    lines = RULE.splitlines()
    i0 = lines.index('配方')
    mach = None
    for s in lines[i0 + 1:]:
        s = s.strip()
        if not s:
            continue
        if '→' not in s:
            mach = s
            rec.setdefault(mach, [])
            continue
        lhs = s.split('→')[0]
        ins = {}
        for part in lhs.split('＋'):
            n, item = part.strip().split(' ', 1)
            ins[item.strip()] = int(n)
        rec[mach].append(ins)
    return cls, rec


CLS, REC = parse()
assert set(CLS) == set(REC), (CLS, REC.keys())


def arrive(state, k, nslots):
    slots = list(state)
    for i, sl in enumerate(slots):
        if sl is not None and sl[0] == k:
            if sl[1] < CAP:
                slots[i] = (k, sl[1] + 1)
                return canon(slots)
            return None
    for i, sl in enumerate(slots):
        if sl is None:
            slots[i] = (k, 1)
            return canon(slots)
    return None


def canon(slots):
    return tuple(sorted(slots, key=lambda x: ('~',) if x is None else x))


def can_batch(state, recipes):
    have = {sl[0]: sl[1] for sl in state if sl is not None}
    return any(all(have.get(k, 0) >= a for k, a in r.items()) for r in recipes)


def all_states(kinds, nslots):
    opts = [None] + [(k, c) for k in kinds for c in range(1, CAP + 1)]
    out = set()
    for combo in itertools.product(opts, repeat=nslots):
        ks = [x[0] for x in combo if x is not None]
        if len(ks) != len(set(ks)):
            continue  # 同一单位同种物品只放一个格
        out.add(canon(list(combo)))
    return out


def enc(state):
    return '|'.join('空' if s is None else f'{s[0]}:{s[1]}' for s in state)


result = {}
for mach, recipes in REC.items():
    nslots = CLS[mach]
    kinds = sorted({k for r in recipes for k in r}) + [WRONG]
    S = all_states(kinds, nslots)
    # 活态：反向不动点
    alive = {s for s in S if can_batch(s, recipes)}
    succ = {s: [t for k in kinds for t in [arrive(s, k, nslots)] if t is not None] for s in S}
    changed = True
    while changed:
        changed = False
        for s in S:
            if s not in alive and any(t in alive for t in succ[s]):
                alive.add(s)
                changed = True
    dead = S - alive
    # 死态分类
    principals = sorted({k for r in recipes for k in r})
    def kinds_of(s):
        return sorted(x[0] for x in s if x is not None)
    dead_kind_sets = sorted({'+'.join(kinds_of(s)) for s in dead})
    # 进入死态的转移（从活态出发）
    entries = set()
    for s in alive:
        for k in kinds:
            t = arrive(s, k, nslots)
            if t is not None and t in dead:
                entries.add((enc(s), k))
        # 开批只减少件数，也检查
        have = {sl[0]: sl[1] for sl in s if sl is not None}
        for r in recipes:
            if all(have.get(k, 0) >= a for k, a in r.items()):
                slots = []
                for sl in s:
                    if sl is None:
                        slots.append(None)
                    else:
                        c = sl[1] - r.get(sl[0], 0)
                        slots.append((sl[0], c) if c > 0 else None)
                t = canon(slots)
                if t in dead:
                    entries.add((enc(s), '开批'))
    # 首件死锁（不含误料的状态，H 不含误料）
    real = [k for k in kinds if k != WRONG]
    head_dead = []
    for s in S:
        if any(x is not None and x[0] == WRONG for x in s):
            continue
        if can_batch(s, recipes):
            continue
        refused = {k for k in real if arrive(s, k, nslots) is None}
        for r in range(1, len(real) + 1):
            for H in itertools.combinations(real, r):
                if set(H) <= refused:
                    head_dead.append(enc(s) + '#' + ','.join(H))
    head_dead.sort()
    # 活态中首件死锁（排除内部死态）
    entry_kinds = sorted({e[1] for e in entries})
    result[mach] = dict(
        slots=nslots, kinds=kinds, recipes=recipes, states=len(S), alive=len(alive), dead=len(dead),
        dead_kind_sets=dead_kind_sets,
        dead_entry_transitions=len(entries), dead_entry_by=entry_kinds,
        dead_sha256=hashlib.sha256('\n'.join(sorted(enc(s) for s in dead)).encode()).hexdigest(),
        head_dead_count=len(head_dead),
        head_dead_sha256=hashlib.sha256('\n'.join(head_dead).encode()).hexdigest(),
        head_dead_list=head_dead if len(head_dead) < 200000 else None,
        dead_list=sorted(enc(s) for s in dead),
    )
    print(mach, nslots, 'states', len(S), 'dead', len(dead), 'kinds', dead_kind_sets[:8], 'entries', len(entries), entry_kinds, 'head_dead', len(head_dead))

(HERE / 'dead_states_A.json').write_text(json.dumps(result, ensure_ascii=False))
print('written')
