# 存货首件死锁：按现行规则第 18 行（存货物品格上限 50、不限种类、同种只占一格）与第 97–105 行配方，
# 枚举每种机型存货物品格的全部内容（含一种代表误料 W）与首件种类的非空集合，
# 找出「凑不齐任何一批、且每个首件都收不下」的状态，再和条文的分类逐一比对。
from itertools import combinations, product

R = {
 '粉碎机': [{'源矿':1}, {'蓝铁块':1}, {'荞花':1}, {'砂叶':1}],
 '精炼炉': [{'蓝铁矿':1}, {'致密蓝铁粉末':1}, {'蓝铁粉末':1}],
 '配件机': [{'钢块':1}],
 '塑形机': [{'钢块':2}],
 '种植机': [{'荞花种子':1}, {'砂叶种子':1}],
 '采种机': [{'荞花':1}, {'砂叶':1}],
 '研磨机': [{'蓝铁粉末':2,'砂叶粉末':1}, {'源石粉末':2,'砂叶粉末':1}, {'荞花粉末':2,'砂叶粉末':1}],
 '封装机': [{'钢制零件':10,'致密源石粉末':15}],
 '灌装机': [{'钢质瓶':10,'细磨荞花粉末':10}],
}
NG = {k: (2 if k in ('研磨机','封装机','灌装机') else 1) for k in R}
MAIN = {'蓝铁粉末','源石粉末','荞花粉末'}

def legit(m):
    s = set()
    for r in R[m]: s |= set(r)
    return sorted(s)

def can_batch(m, st):
    return any(all(st.get(k,0) >= v for k, v in r.items()) for r in R[m])

def accept(m, st, x):
    if x in st: return st[x] < 50
    return len(st) < NG[m]

def states(m):
    kinds = legit(m) + ['W']
    yield {}
    for a in kinds:
        for n in range(1, 51): yield {a: n}
    if NG[m] == 2:
        for a, b in combinations(kinds, 2):
            for n, k in product(range(1, 51), repeat=2): yield {a: n, b: k}

def clause_predicts(m, st, firsts):
    """条文分类：返回 True 表示条文把它列为死锁（只在条文覆盖的前提内判）。"""
    wrong_store = 'W' in st
    wrong_first = 'W' in firsts
    two_main = m == '研磨机' and len(set(st) & MAIN) == 2
    if wrong_store or two_main:
        return None                      # 条文分类不覆盖
    if NG[m] == 1:
        if not wrong_first: return False  # 小、中无此状态
        # 首件有误料：塑形机格里只有 1 件钢块、首件都是误料
        return m == '塑形机' and st == {'钢块': 1} and firsts == {'W'}
    # 大制造单位
    if len(st) == 1:
        (a, n), = st.items()
        return (not wrong_first) and n == 50 and firsts == {a}    # （一）
    if len(st) == 2:
        if can_batch(m, st): return False
        # （二）里收不下的种类：格里满 50 的那种；研磨机另有另外两种主料
        bad = {k for k, v in st.items() if v == 50}
        if m == '研磨机': bad |= (MAIN - set(st))
        # 条文（二）的括号：研磨机主料只剩 1 件，封装 零件<10 或 粉<15，灌装 瓶<10 或 粉<10
        if m == '研磨机': cond = any(st.get(k) == 1 for k in MAIN)
        elif m == '封装机': cond = st.get('钢制零件',0) < 10 or st.get('致密源石粉末',0) < 15
        else: cond = st.get('钢质瓶',0) < 10 or st.get('细磨荞花粉末',0) < 10
        assert cond, (m, st)
        allowed = bad | ({'W'} if wrong_first or True else set())
        if not wrong_first:
            return firsts <= bad and len(firsts) > 0
        return firsts <= (bad | {'W'})
    return False

summary = {}
for m in R:
    kinds = legit(m) + ['W']
    n_dead_legit = n_dead_any = 0
    mism = 0
    for st in states(m):
        if can_batch(m, st): continue
        for r in range(1, len(kinds) + 1):
            for fs in combinations(kinds, r):
                fs = set(fs)
                dead = all(not accept(m, st, x) for x in fs)
                pred = clause_predicts(m, st, fs)
                if pred is None: continue
                if dead != pred:
                    mism += 1
                    if mism <= 3: print('不符', m, st, fs, dead, pred)
                if dead:
                    n_dead_any += 1
                    if 'W' not in fs: n_dead_legit += 1
    summary[m] = (n_dead_legit, n_dead_any, mism)
for m, v in summary.items():
    print(f'{m}: 只含合法首件的死锁 {v[0]} 组，含误料首件在内共 {v[1]} 组，与条文分类不符 {v[2]} 处')
