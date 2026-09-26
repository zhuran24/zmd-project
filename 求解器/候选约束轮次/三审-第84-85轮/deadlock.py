#!/usr/bin/env python3
"""三审自写：存货首件死锁的穷举与分类核对，研磨机进入永久停机的转移计数。

编码甲：从正式游戏规则解析配方，存货格状态用「种类→件数」集合表示。
编码乙：配方手抄，存货格按有序两格逐件试放。
两套独立写出，结果逐项比对；再用条文的文字分类（一）（二）与误料一类逐组核对。
只用 Python 标准库，单核。
"""
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CAP = 50
W = '误料'

# ---------- 编码甲：从规则文件解析 ----------

def parse_recipes():
    text = (REPO / '《明日方舟：终末地》游戏规则.txt').read_text()
    body = text.split('\n配方\n', 1)[1]
    machine, recipes = None, {}
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if '→' not in line:
            machine = line
            recipes[machine] = []
            continue
        left, right = line.split('→')
        need = {}
        for term in left.strip().split('＋'):
            n, item = term.strip().split(' ', 1)
            need[item.strip()] = int(n)
        recipes[machine].append(need)
    return recipes


RECIPES_A = parse_recipes()
GRIDS = {m: (2 if m in ('研磨机', '封装机', '灌装机') else 1) for m in RECIPES_A}


def materials(recipes):
    return sorted({i for r in recipes for i in r})


def states_A(machine, types):
    """全部存货格状态：frozenset((种类, 件数))，同种只占一格，格数不超过本机格数。"""
    n = GRIDS[machine]
    out = [frozenset()]
    for k in range(1, n + 1):
        for combo in itertools.combinations(types, k):
            for counts in itertools.product(range(1, CAP + 1), repeat=k):
                out.append(frozenset(zip(combo, counts)))
    return out


def can_batch_A(machine, st):
    have = dict(st)
    return any(all(have.get(i, 0) >= n for i, n in r.items()) for r in RECIPES_A[machine])


def accepts_A(machine, st, item):
    have = dict(st)
    if item in have:
        return have[item] < CAP
    return len(st) < GRIDS[machine]


def two_main(st):
    mains = {'蓝铁粉末', '源石粉末', '荞花粉末'}
    return len([t for t, _ in st if t in mains]) >= 2


# ---------- 编码乙：手抄配方，有序格逐件试放 ----------

RECIPES_B = {
    '粉碎机': [{'源矿': 1}, {'蓝铁块': 1}, {'荞花': 1}, {'砂叶': 1}],
    '精炼炉': [{'蓝铁矿': 1}, {'致密蓝铁粉末': 1}, {'蓝铁粉末': 1}],
    '研磨机': [{'蓝铁粉末': 2, '砂叶粉末': 1}, {'源石粉末': 2, '砂叶粉末': 1}, {'荞花粉末': 2, '砂叶粉末': 1}],
    '塑形机': [{'钢块': 2}],
    '配件机': [{'钢块': 1}],
    '种植机': [{'荞花种子': 1}, {'砂叶种子': 1}],
    '采种机': [{'荞花': 1}, {'砂叶': 1}],
    '封装机': [{'钢制零件': 10, '致密源石粉末': 15}],
    '灌装机': [{'钢质瓶': 10, '细磨荞花粉末': 10}],
}
NGRID_B = {'研磨机': 2, '封装机': 2, '灌装机': 2}


def try_place_B(grids, item):
    """grids: list of [type or None, count]; 返回能否收下（不改动）。"""
    for t, c in grids:
        if t == item:
            return c < CAP
    return any(t is None for t, c in grids)


def batch_B(machine, grids):
    for r in RECIPES_B[machine]:
        ok = True
        for item, n in r.items():
            got = sum(c for t, c in grids if t == item)
            if got < n:
                ok = False
        if ok:
            return True
    return False


def states_B(machine, types):
    n = NGRID_B.get(machine, 1)
    cells = [(None, 0)] + [(t, c) for t in types for c in range(1, CAP + 1)]
    seen = set()
    for combo in itertools.product(cells, repeat=n):
        ts = [t for t, _ in combo if t is not None]
        if len(ts) != len(set(ts)):
            continue
        key = tuple(sorted((t, c) for t, c in combo if t is not None))
        if key in seen:
            continue
        seen.add(key)
        yield [list(x) for x in combo]


# ---------- 死锁组合计数 ----------

def dead_combos_A(machine, allow_W_first, allow_W_grid=False):
    mats = materials(RECIPES_A[machine])
    grid_types = mats + ([W] if allow_W_grid else [])
    first_types = mats + ([W] if allow_W_first else [])
    out = []
    for st in states_A(machine, grid_types):
        if machine == '研磨机' and two_main(st):
            continue
        if can_batch_A(machine, st):
            continue
        rej = [x for x in first_types if not accepts_A(machine, st, x)]
        for k in range(1, len(rej) + 1):
            for sub in itertools.combinations(rej, k):
                out.append((st, frozenset(sub)))
    return out


def dead_combos_B(machine, allow_W_first):
    mats = sorted({i for r in RECIPES_B[machine] for i in r})
    first_types = mats + ([W] if allow_W_first else [])
    mains = {'蓝铁粉末', '源石粉末', '荞花粉末'}
    out = []
    for grids in states_B(machine, mats):
        if machine == '研磨机' and len([t for t, _ in grids if t in mains]) >= 2:
            continue
        if batch_B(machine, grids):
            continue
        rej = [x for x in first_types if not try_place_B(grids, x)]
        st = frozenset((t, c) for t, c in grids if t is not None)
        for k in range(1, len(rej) + 1):
            for sub in itertools.combinations(rej, k):
                out.append((st, frozenset(sub)))
    return out


# ---------- 条文分类（按将写入正式文件的文字独立实现） ----------

def text_class(machine, st, first):
    """返回 '一'、'二'、'误料' 或 None（条文不认为是死锁）。只用条文文字给的判别。"""
    have = dict(st)
    large = machine in ('研磨机', '封装机', '灌装机')
    if not large:
        # 小、中制造单位：只有塑形机格里 1 件钢块、首件都是误料一例
        if machine == '塑形机' and have == {'钢块': 1} and first == frozenset([W]):
            return '误料'
        return None
    mats = materials(RECIPES_A[machine])
    if len(have) == 1:
        (t, c), = have.items()
        if c == CAP and first == frozenset([t]):
            return '一'
        return None
    if len(have) == 2:
        if machine == '研磨机':
            main = [t for t in have if t != '砂叶粉末'][0]
            short = have[main] == 1
        elif machine == '封装机':
            short = have['钢制零件'] < 10 or have['致密源石粉末'] < 15
        else:
            short = have['钢质瓶'] < 10 or have['细磨荞花粉末'] < 10
        if not short:
            return None

        def rejected_kind(x):
            if x in have:
                return have[x] == CAP
            return x in mats  # 格里没有的本机原料（只有研磨机会出现：另两种主料）
        if W in first:
            if all(x == W or rejected_kind(x) for x in first):
                return '误料'
            return None
        if all(rejected_kind(x) for x in first):
            return '二'
    return None


# ---------- 研磨机进入永久停机（甲、乙）的全部转移 ----------

def grinder_transitions():
    m = '研磨机'
    types = materials(RECIPES_A[m]) + [W]
    mains = {'蓝铁粉末', '源石粉末', '荞花粉末'}

    def permanent(st):
        return any(t == W for t, _ in st) or two_main(st)
    into_two, into_W, by_batch, total = 0, 0, 0, 0
    kinds = set()
    for st in states_A(m, types):
        if permanent(st):
            continue
        have = dict(st)
        # 到件
        for x in types:
            if not accepts_A(m, st, x):
                continue
            nh = dict(have)
            nh[x] = nh.get(x, 0) + 1
            nst = frozenset(nh.items())
            if permanent(nst):
                total += 1
                if x == W:
                    into_W += 1
                else:
                    into_two += 1
                    # 核对是「主料进空格、另一格是另一种主料」
                    other = [t for t in have if t != x]
                    assert x in mains and x not in have and len(have) == 1 and other[0] in mains
                    kinds.add('主料进空格')
        # 开批
        for r in RECIPES_A[m]:
            if all(have.get(i, 0) >= n for i, n in r.items()):
                nh = {i: have[i] - r.get(i, 0) for i in have}
                nst = frozenset((i, c) for i, c in nh.items() if c > 0)
                if permanent(nst):
                    by_batch += 1
    return {'进入永久停机的转移': total, '两种主料': into_two, '误料进格': into_W,
            '由开批造成': by_batch, '两种主料的进入方式': sorted(kinds)}


def main():
    res = {'配方来源': '正式游戏规则解析（编码甲）与手抄（编码乙）', '机型': {}}
    for m in RECIPES_A:
        assert sorted(RECIPES_A[m], key=lambda r: sorted(r.items())) == sorted(RECIPES_B[m], key=lambda r: sorted(r.items())), m
        row = {}
        for allow in (False, True):
            a = dead_combos_A(m, allow)
            b = dead_combos_B(m, allow)
            assert set(a) == set(b) and len(a) == len(set(a)), (m, allow)
            key = '首件可含误料' if allow else '首件无误料'
            row[key] = len(a)
            # 条文分类逐组核对：死锁组合 == 条文判为死锁的组合
            mats = materials(RECIPES_A[m])
            grid_types = mats
            first_types = mats + ([W] if allow else [])
            classified = set()
            for st in states_A(m, grid_types):
                if m == '研磨机' and two_main(st):
                    continue
                for k in range(1, len(first_types) + 1):
                    for sub in itertools.combinations(first_types, k):
                        c = text_class(m, st, frozenset(sub))
                        if c is not None:
                            classified.add((st, frozenset(sub)))
            row[key + '·与条文分类一致'] = classified == set(a)
            if allow:
                cls = {}
                for st, sub in a:
                    c = text_class(m, st, sub)
                    cls[c] = cls.get(c, 0) + 1
                row['分类计数'] = cls
        res['机型'][m] = row
    res['研磨机转移'] = grinder_transitions()
    out = HERE / 'out' / 'deadlock.json'
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
