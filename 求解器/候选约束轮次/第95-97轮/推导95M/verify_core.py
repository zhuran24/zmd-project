"""本席核算：重建次序、首段带容量、换料余量、调试数量。

这里只核对有限组合、局部容量和算术，不认证全厂可摆放或达标。
两种带模型分别用进入步号、反向数组剩余步数；均不调用 sim2。
"""
from fractions import Fraction as F
from itertools import permutations, product
from pathlib import Path
import json

OUT = Path(__file__).resolve().parent


def rebuild_a(nhigh, nlow):
    names = ['M'] + [f'H{i}' for i in range(nhigh)] + [f'L{i}' for i in range(nlow)]
    found = set()
    witnesses = {}
    for order in permutations(names):
        birth = {x:i for i,x in enumerate(order)}
        high = min(max(birth['M'], birth[f'H{i}']) for i in range(nhigh))
        low = min(max(birth['M'], birth[f'L{i}']) for i in range(nlow))
        result = (high > low) - (high < low)
        found.add(result)
        witnesses.setdefault(result, list(order))
    return sorted(found), witnesses


def rebuild_b(nhigh, nlow):
    # Build the source first and either entire grade next. Detect channel
    # creation by adding occupied endpoints, rather than max(birth).
    names = ['M'] + [f'H{i}' for i in range(nhigh)] + [f'L{i}' for i in range(nlow)]
    found = set()
    for order in permutations(names):
        ready = set(); created = {}
        for t,u in enumerate(order):
            ready.add(u)
            if 'M' in ready:
                for v in ready - {'M'}:
                    created.setdefault(v, t)
        ht = min(t for v,t in created.items() if v[0] == 'H')
        lt = min(t for v,t in created.items() if v[0] == 'L')
        found.add((ht > lt) - (ht < lt))
    return sorted(found)


def capacity_a(n, accept_mod):
    belt = [None] * n; splitter = None; seen = {}; out = occ = 0
    def move(t):
        for j in range(n-2,-1,-1):
            if belt[j] is not None and t-belt[j] >= 8 and belt[j+1] is None:
                belt[j+1], belt[j] = t, None
    for t in range(100000):
        state = (t % accept_mod, None if splitter is None else min(8,t-splitter),
                 tuple(None if v is None else min(8,t-v) for v in belt))
        if state in seen:
            p,q,h = seen[state]
            return [t-p, out-q, occ-h]
        seen[state] = t,out,occ
        move(t)
        if splitter is not None and t-splitter >= 8 and belt[0] is None:
            belt[0],splitter = t,None
        if belt[-1] is not None and t-belt[-1] >= 8 and (accept_mod == 1 or t % accept_mod != 0):
            belt[-1] = None; out += 1
        move(t)
        if splitter is None:
            splitter = t
        occ += sum(x is not None for x in belt)
    raise AssertionError('cycle not found')


def capacity_b(n, accept_mod):
    # Cell 0 is the exit; countdown zero means mature at the beginning
    # of the step. No absolute item timestamps are used.
    road = [-1] * n; source = -1; seen = {}; out = occ = 0; t=0
    def advance():
        for j in range(n-1):
            if road[j] == -1 and road[j+1] == 0:
                road[j], road[j+1] = 8, -1
    while t < 100000:
        key = (t % accept_mod, source, tuple(road))
        if key in seen:
            oldt,oldo,oldh = seen[key]
            return [t-oldt,out-oldo,occ-oldh]
        seen[key] = (t,out,occ)
        advance()
        if source == 0 and road[-1] == -1:
            road[-1] = 8; source = -1
        if road[0] == 0 and (accept_mod == 1 or t % accept_mod):
            road[0] = -1; out += 1
        advance()
        if source == -1:
            source = 8
        occ += n - road.count(-1)
        road = [v-1 if v>0 else v for v in road]
        if source>0: source -= 1
        t += 1
    raise AssertionError('cycle not found')


def earliest_a(channels):
    # Enumerate the first two receipts after the former batch at step 0.
    return min(max(8,t2) for t1 in range(1,18) for t2 in range(t1,19)
               for c1 in range(channels) for c2 in range(channels)
               if (t1 != t2 or c1 != c2) and (c1 != c2 or t2-t1 >= 8))


def earliest_b(channels):
    # Set of receipt counts and cooldown vectors; a new item cannot enter
    # the storage before step 1, because manufacture starts last.
    states = {(0, (0,)*channels)}
    for t in range(1,24):
        nxt=set()
        for have, old in states:
            ages = tuple(max(0,v-1) for v in old)
            for bits in product((0,1),repeat=channels):
                if any(take and ages[j] for j,take in enumerate(bits)): continue
                count = min(2, have+sum(bits))
                after = tuple(8 if bits[j] else ages[j] for j in range(channels))
                if count == 2 and t >= 8: return t
                nxt.add((count,after))
        states = nxt
    raise AssertionError('no two receipts')


def main():
    rebuild=[]
    for h,l in ((1,1),(2,1),(1,3),(3,2)):
        a,w = rebuild_a(h,l); b = rebuild_b(h,l)
        assert a == b and -1 in a and 1 in a
        rebuild.append({'high_channels':h,'low_channels':l,'signs':a,'low_first_witness':w[1]})
    capacities=[]
    for n in (1,2,3,4,6,16,32,64):
        for mod in (1,3,11):
            a=capacity_a(n,mod); b=capacity_b(n,mod)
            assert a == b,(n,mod,a,b)
            p,q,h=a
            assert 8*n*q <= h <= n*p-q
            if mod == 1: assert F(8*q,p) == F(8*n,8*n+1)
            capacities.append({'n':n,'accept_mod':mod,'period_steps':p,'out':q,'occupied_cell_steps':h,'rate':str(F(8*q,p))})
    receipt=[]
    for c in (1,2):
        a,b=earliest_a(c),earliest_b(c)
        assert a==b
        receipt.append({'channels':c,'earliest_next_batch':a})
    limits=[]
    for n in (32,33,34):
        fa = max(a for a in range(n+1) if F(n)-F(a,9)>=F(63,2))
        ib = max(a for a in range(n+1) if 18*n-2*a>=567)
        assert fa==ib
        w1=8*(F(n)-F(63,2)); w2=(160*n-8*630)//20
        assert w1==w2
        limits.append({'N':n,'a_upper':fa,'W_per_tick_upper':str(w1)})
    # Threshold by rational subtraction and by doubled integer inequality.
    la = int(F(100)-F(5,2))
    lb = max(l for l in range(4901) if 2*l+5<=200)
    assert la==lb==97
    demand_a={'荞花':6*50,'荞花种子':6*50,'砂叶':11*50,'砂叶种子':11*50}
    demand_b={x:sum(50 for _ in range(6 if x.startswith('荞花') else 11)) for x in demand_a}
    assert demand_a==demand_b
    pollution_a=52*50+18*(50+3)+9*(100+50+3)+3*100+2*70*70
    pollution_b=sum([50]*52+[53]*18+[153]*9+[100]*3+[2]*4900)
    assert pollution_a==pollution_b==15031
    startup={'threshold':la,'seed_and_plant_demand':demand_a,'pre_setting_withdrawal_upper':pollution_a,
             'remaining_lower':80000-pollution_a,'all_long_routes_demand_upper':550+2*70*70,
             'phi_at_end':{'L_le_97':'100','L_gt_97':'100+L'}}
    # These are bound values, never claimed to be realizable populations.
    result={'rebuild':rebuild,'capacity':capacities,'switch_receipts':receipt,
            'grinder_limits':limits,'startup':startup,
            'all_checks_pass':True,'simulation_role':'局部边界容量及实施核对，不是全厂证书'}
    (OUT/'core_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'rebuild_cases':len(rebuild),'capacity_cases':len(capacities),'switch_receipts':receipt,'startup_threshold':la,'all_checks_pass':True},ensure_ascii=False))


if __name__=='__main__': main()
