#!/usr/bin/env python3
"""第81轮B 编码B：按报告里写成文字的判别式逐条实现（配方手抄，不解析规则文件），
再与编码A的显式搜索结果逐项比对。

报告条文的判别式：
  内部死态（任何到件都救不回）：某格有误料；或研磨机两格分别是蓝铁粉末、源石粉末、荞花粉末中的两种。
  进入内部死态的唯一一步：一种物品进了空格，而另一格已是误料或另一种主料（研磨机），或进来的是误料。
  首件死锁（本身不是内部死态，开不了批，首件种类集合 H 全被拒）：只可能在大制造单位，
    (i) 只有一格有货且满 50，H 只含这一种；
    (ii) 两格都有货、凑不齐一批（研磨机：主料恰 1 件；封装机、灌装机：有一种少于一批用量），
         H 中每一种要么是格里满 50 的那种，要么是格里没有的种类。
"""
import itertools, json, hashlib, os
from pathlib import Path

os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
HERE = Path(__file__).resolve().parent
CAP = 50
WRONG = '误料'
R = {
    '粉碎机': (1, [{'源矿': 1}, {'蓝铁块': 1}, {'荞花': 1}, {'砂叶': 1}]),
    '精炼炉': (1, [{'蓝铁矿': 1}, {'致密蓝铁粉末': 1}, {'蓝铁粉末': 1}]),
    '研磨机': (2, [{'蓝铁粉末': 2, '砂叶粉末': 1}, {'源石粉末': 2, '砂叶粉末': 1}, {'荞花粉末': 2, '砂叶粉末': 1}]),
    '塑形机': (1, [{'钢块': 2}]),
    '配件机': (1, [{'钢块': 1}]),
    '种植机': (1, [{'荞花种子': 1}, {'砂叶种子': 1}]),
    '采种机': (1, [{'荞花': 1}, {'砂叶': 1}]),
    '封装机': (2, [{'钢制零件': 10, '致密源石粉末': 15}]),
    '灌装机': (2, [{'钢质瓶': 10, '细磨荞花粉末': 10}]),
}
PRINC = {'蓝铁粉末', '源石粉末', '荞花粉末'}


def enc(d, nslots):
    items = sorted(d.items())
    parts = [f'{k}:{c}' for k, c in items] + ['空'] * (nslots - len(items))
    return '|'.join(parts)


def states(kinds, nslots):
    yield {}
    for k in kinds:
        for c in range(1, CAP + 1):
            yield {k: c}
    if nslots == 2:
        for k1, k2 in itertools.combinations(kinds, 2):
            for c1 in range(1, CAP + 1):
                for c2 in range(1, CAP + 1):
                    yield {k1: c1, k2: c2}


def internal_dead(mach, d):
    if WRONG in d:
        return True
    if mach == '研磨机' and len(set(d) & PRINC) == 2:
        return True
    return False


def batch_ok(recipes, d):
    return any(all(d.get(k, 0) >= a for k, a in r.items()) for r in recipes)


def head_dead_claim(mach, nslots, recipes, d, H):
    """报告判别式；只对非内部死态、不含误料的状态调用。"""
    if nslots == 1:
        return False
    if batch_ok(recipes, d):
        return False
    if len(d) == 1:
        (k, c), = d.items()
        return c == CAP and set(H) <= {k}
    if len(d) == 2:
        # 两格都有货且凑不齐一批
        full = {k for k, c in d.items() if c == CAP}
        absent_ok = set(H) - set(d)
        return all((h in full) or (h not in d) for h in H)
    return False  # 两格全空：什么都收


out = {}
A = json.loads((HERE / 'dead_states_A.json').read_text())
allok = True
for mach, (nslots, recipes) in R.items():
    kinds = sorted({k for r in recipes for k in r}) + [WRONG]
    real = [k for k in kinds if k != WRONG]
    dead = []
    head = []
    head_alive = []
    entry = set()
    for d in states(kinds, nslots):
        e = enc(d, nslots)
        idead = internal_dead(mach, d)
        if idead:
            dead.append(e)
        # 进入内部死态的一步（报告判别式）：只由一次进空格造成
        if not idead and len(d) < nslots:
            for k in kinds:
                if k in d:
                    continue
                nd = dict(d); nd[k] = 1
                if internal_dead(mach, nd):
                    entry.add((e, k))
        if WRONG in d:
            continue
        for r in range(1, len(real) + 1):
            for H in itertools.combinations(real, r):
                if idead:
                    # 内部死态：按定义取被拒集合（两格都有货，拒收＝满 50 或格里没有）
                    if all((d.get(h, 0) == CAP) or (h not in d and len(d) == nslots) for h in H):
                        head.append(e + '#' + ','.join(H))
                elif head_dead_claim(mach, nslots, recipes, d, H):
                    head.append(e + '#' + ','.join(H))
                    head_alive.append(e + '#' + ','.join(H))
    dead.sort(); head.sort(); head_alive.sort()
    a = A[mach]
    def norm(x):
        st, _, H = x.partition('#')
        return (tuple(sorted(st.split('|'))), H)
    same_dead = sorted(map(norm, dead)) == sorted(map(norm, a['dead_list']))
    same_head = sorted(map(norm, head)) == sorted(map(norm, a['head_dead_list']))
    # 编码A的进入转移另算（A 包含开批，B 按条文只有进空格）
    rec = dict(slots=nslots, dead=len(dead), dead_match_A=same_dead,
               head_dead=len(head), head_dead_match_A=same_head,
               head_dead_not_internal=len(head_alive),
               head_dead_not_internal_list=head_alive if len(head_alive) <= 600 else head_alive[:600],
               dead_entry_steps=len(entry), dead_entry_count_A=a['dead_entry_transitions'],
               dead_entry_match_A=(len(entry) == a['dead_entry_transitions']))
    allok &= same_dead and same_head and rec['dead_entry_match_A']
    out[mach] = rec
    print(mach, 'dead', len(dead), same_dead, 'head', len(head), same_head, 'head_not_internal', len(head_alive), 'entry', len(entry), a['dead_entry_transitions'])
out['all_match'] = allok
(HERE / 'dead_states_B.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
print('ALL MATCH' if allok else 'MISMATCH')
