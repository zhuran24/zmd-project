#!/usr/bin/env python3
"""第81轮B：成品拒收后哪些配方必在有限时间内停下（配方图上的推算，两套写法互核）。

写法A（从规则快照解析配方）：把拒收的成品集合 R 视为“进不去仓库”。迭代：
  一个配方“已停”，当它的某种产物满足：该产物不能入库（成品在 R 中，或按前提非成品不入库），
  且该产物作为原料的全部配方都已停（成品不作任何配方原料）；
  另把“只由已停配方消耗、且只由这些配方及仓库取货口产生”的原料，其来源（取货口）也记为停。
  植物回路单独处理：某种植物的粉碎已停时，采种（种子+植株总数+1/批）也停，随后种植停。
写法B：手写各情形的停下清单，逐项比对。
"""
import json, os, re
from pathlib import Path
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
HERE = Path(__file__).resolve().parent
RULE = (HERE.parent / '前提快照' / '《明日方舟：终末地》游戏规则.txt').read_text()
lines = RULE.splitlines()
i0 = lines.index('配方')
recs = []
mach = None
for s in lines[i0 + 1:]:
    s = s.strip()
    if not s:
        continue
    if '→' not in s:
        mach = s; continue
    lhs, rhs = s.split('→')
    ins = {}
    for part in lhs.split('＋'):
        n, it = part.strip().split(' ', 1); ins[it.strip()] = int(n)
    q, it = rhs.split('，')[0].strip().split(' ', 1)
    recs.append(dict(m=mach, ins=ins, out=it.strip(), n=int(q)))
PRODUCTS = {'高容谷地电池', '精选荞愈胶囊'}
ORES = {'源矿', '蓝铁矿'}
PLANTS = {'荞花': '荞花种子', '砂叶': '砂叶种子'}


def rid(r):
    return f"{r['m']}:{'+'.join(r['ins'])}→{r['out']}"


def stopped_set(refused):
    stopped = set()
    changed = True
    while changed:
        changed = False
        for r in recs:
            k = rid(r)
            if k in stopped:
                continue
            o = r['out']
            if o in PRODUCTS:
                ok = o in refused
            else:
                # 非成品按前提不入库；它的所有下游配方都停了才算
                users = [rid(x) for x in recs if o in x['ins']]
                ok = all(u in stopped for u in users)
                # 植物回路：采种产种子、种植产植株，互为下游；用计数论证：
                # 该种植物的粉碎配方已停时，采种与种植都停
                if r['m'] in ('采种机', '种植机'):
                    plant = o if o in PLANTS else [p for p, s in PLANTS.items() if s == o][0]
                    crush = [rid(x) for x in recs if x['m'] == '粉碎机' and plant in x['ins']]
                    ok = all(c in stopped for c in crush)
            if ok:
                stopped.add(k); changed = True
    # 物品族计数：取非成品集合 F，使每个未停且吃 F 中物品的配方都只产 F 中物品且件数不减；
    # 则矿石 o∈F 的取货每次使 F 在仓库外的件数 +1，永不减少、又有容量上限，只能有限次；
    # 取货停后 o 只剩有限件，吃 o 的配方也只能有限次。
    ore_stop = set()
    while True:
        items = {x for r in recs for x in list(r['ins']) + [r['out']]} - PRODUCTS
        F = set(items)
        ch = True
        while ch:
            ch = False
            for r in recs:
                if rid(r) in stopped:
                    continue
                fin = [x for x in r['ins'] if x in F]
                if not fin:
                    continue
                ok = (r['out'] in F) and r['n'] >= sum(r['ins'][x] for x in fin) and len(fin) == len(r['ins'])
                if not ok:
                    for x in fin:
                        F.discard(x)
                    ch = True
        new_ore = {o for o in ORES if o in F} - ore_stop
        if not new_ore:
            break
        ore_stop |= new_ore
        for r in recs:
            if any(o in r['ins'] for o in new_ore):
                stopped.add(rid(r))
        # 再跑一遍前面的停下推理
        changed = True
        while changed:
            changed = False
            for r in recs:
                k = rid(r)
                if k in stopped or r['out'] in PRODUCTS:
                    continue
                o = r['out']
                users = [rid(x) for x in recs if o in x['ins']]
                if all(u in stopped for u in users):
                    stopped.add(k); changed = True
    ore_stop |= {o for o in ORES if all(rid(x) in stopped for x in recs if o in x['ins'])}
    return sorted(stopped), sorted(ore_stop)

res = {}
for name, R in [('电池拒收', {'高容谷地电池'}), ('胶囊拒收', {'精选荞愈胶囊'}), ('两种都拒收', PRODUCTS)]:
    st, ore = stopped_set(R)
    running = sorted(rid(r) for r in recs if rid(r) not in st)
    res[name] = dict(stopped=st, still_may_run=running, ore_pickups_stopped=ore)
    print(name, '停下', len(st), '可能还跑', running, '停的矿口', ore)

# 写法B：手写
B = {
 '电池拒收': dict(may_run={'粉碎机:蓝铁块→蓝铁粉末','粉碎机:荞花→荞花粉末','粉碎机:砂叶→砂叶粉末','精炼炉:蓝铁矿→蓝铁块','精炼炉:致密蓝铁粉末→钢块','精炼炉:蓝铁粉末→蓝铁块','研磨机:蓝铁粉末+砂叶粉末→致密蓝铁粉末','研磨机:荞花粉末+砂叶粉末→细磨荞花粉末','塑形机:钢块→钢质瓶','种植机:荞花种子→荞花','种植机:砂叶种子→砂叶','采种机:荞花→荞花种子','采种机:砂叶→砂叶种子','灌装机:钢质瓶+细磨荞花粉末→精选荞愈胶囊'}, ore={'源矿'}),
 '胶囊拒收': dict(may_run={'粉碎机:源矿→源石粉末','粉碎机:蓝铁块→蓝铁粉末','粉碎机:砂叶→砂叶粉末','精炼炉:蓝铁矿→蓝铁块','精炼炉:致密蓝铁粉末→钢块','精炼炉:蓝铁粉末→蓝铁块','研磨机:蓝铁粉末+砂叶粉末→致密蓝铁粉末','研磨机:源石粉末+砂叶粉末→致密源石粉末','配件机:钢块→钢制零件','种植机:砂叶种子→砂叶','采种机:砂叶→砂叶种子','封装机:钢制零件+致密源石粉末→高容谷地电池'}, ore=set()),
 '两种都拒收': dict(may_run={'粉碎机:蓝铁块→蓝铁粉末','精炼炉:蓝铁粉末→蓝铁块'}, ore={'源矿','蓝铁矿'}),
}
allok = True
for k in B:
    a = set(res[k]['still_may_run']); b = B[k]['may_run']
    ok = (a == b) and set(res[k]['ore_pickups_stopped']) == B[k]['ore']
    allok &= ok
    res[k]['match_B'] = ok
    if not ok:
        print(k, 'A-B', a - b, 'B-A', b - a, res[k]['ore_pickups_stopped'])
res['all_match'] = allok
(HERE / 'freeze_scope.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
print('ALL MATCH' if allok else 'MISMATCH')
