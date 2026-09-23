#!/usr/bin/env python3
"""第64轮独立复算。只读正式文件和第63轮 JSON；只向本目录写结果。

python audit.py         从正式配方重建模型，重新求解并生成分数证书
python audit.py --exact  不导入 scipy，不调用求解器，重建并检查两组证书
未读取、导入或执行第63轮的任何 Python 脚本。
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction as F
import hashlib
from itertools import product
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = HERE.parent / 'B-切线容量'
FORMAL = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
KINDS = ['粉碎机', '精炼炉', '配件机', '塑形机', '种植机', '采种机']
SATURATED = [k for k in KINDS if k != '塑形机']
MINERALS = {'蓝铁矿', '源矿', '蓝铁块', '蓝铁粉末', '源石粉末'}
COUNTS = {'粉碎机': 68, '精炼炉': 51, '研磨机': 32, '塑形机': 6,
          '配件机': 6, '种植机': 32, '采种机': 16, '封装机': 3, '灌装机': 3}


def dump(name, data):
    def encode(obj):
        if isinstance(obj, F):
            return str(obj)
        raise TypeError(type(obj))
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                       default=encode) + '\n')


def hashes():
    return {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in FORMAL}


def recipes_from_rules():
    recipes = []
    kind = None
    text = (ROOT / FORMAL[0]).read_text().split('\n配方\n', 1)[1]
    for line in text.splitlines():
        line = line.strip()
        if line in COUNTS:
            kind = line
        elif '→' in line:
            m = re.fullmatch(r'(.+) → (.+)，(\d+) tick', line)
            assert m, line
            def side(s):
                out = {}
                for term in re.split(r'\s*[＋+]\s*', s):
                    count, item = term.split(' ', 1)
                    out[item] = int(count)
                return out
            recipes.append({'kind': kind, 'inputs': side(m[1]),
                            'outputs': side(m[2]), 'ticks': int(m[3])})
    assert len(recipes) == 18
    return recipes


def exact_unique_solution(matrix, rhs):
    a = [[F(v) for v in row] + [F(b)] for row, b in zip(matrix, rhs)]
    n = len(matrix[0])
    pivot = 0
    columns = []
    for j in range(n):
        found = next((i for i in range(pivot, len(a)) if a[i][j]), None)
        if found is None:
            continue
        a[pivot], a[found] = a[found], a[pivot]
        d = a[pivot][j]
        a[pivot] = [v/d for v in a[pivot]]
        for i in range(len(a)):
            if i != pivot and a[i][j]:
                d = a[i][j]
                a[i] = [v-d*w for v,w in zip(a[i], a[pivot])]
        columns.append(j)
        pivot += 1
    assert len(columns) == n
    assert all(any(row[:-1]) or row[-1] == 0 for row in a)
    result = [F(0)] * n
    for i,j in enumerate(columns):
        result[j] = a[i][-1]
    return result


def global_rates(recipes):
    # 成品恰产率取自正式周期倍数；回炼为0由51台精炼炉饱和推出。
    items = sorted({s for r in recipes for field in ['inputs','outputs'] for s in r[field]})
    assert len(items) == 19
    matrix, rhs = [], []
    for item in items:
        matrix.append([r['outputs'].get(item,0)-r['inputs'].get(item,0) for r in recipes]
                      + [int(item == '蓝铁矿'), int(item == '源矿')])
        rhs.append({'高容谷地电池': F(3,5), '精选荞愈胶囊': F(11,20)}.get(item, F(0)))
    recycle = next(j for j,r in enumerate(recipes)
                   if r['kind'] == '精炼炉' and '蓝铁粉末' in r['inputs'])
    row = [0]*20
    row[recycle] = 1
    matrix.append(row)
    rhs.append(0)
    rates = exact_unique_solution(matrix,rhs)
    assert rates[-2:] == [34,18]
    load = {k: sum(rates[j]*r['ticks'] for j,r in enumerate(recipes) if r['kind']==k)
            for k in COUNTS}
    assert all(0 <= load[k] <= COUNTS[k] for k in COUNTS)
    assert all(load[k] == COUNTS[k] for k in SATURATED + ['封装机'])
    minima = {k: max(F(0), load[k]-(COUNTS[k]-1)) /
              next(r['ticks'] for r in recipes if r['kind']==k) for k in COUNTS}
    return items, rates[:18], load, minima


def branches():
    # 用剩余宽度逐层递归生成，不把215写成枚举边界。
    widths = [3,3,3,3,5,5]
    def walk(prefix, remaining):
        i = len(prefix)
        if i == len(widths):
            yield prefix
        else:
            for n in range(remaining // widths[i] + 1):
                yield from walk(prefix + [n], remaining - n*widths[i])
    return list(walk([],15))


def build_model(recipes, items, rates, counts):
    size = 18 + 1 + len(items)
    def row_for(kind):
        return [F(int(r['kind']==kind)) for r in recipes] + [F(0)]*(size-18)
    grinder = row_for('研磨机')
    mineral_grinder = [F(int(r['kind']=='研磨机' and bool(MINERALS & r['inputs'].keys())))
                       for r in recipes] + [F(0)]*(size-18)
    shaper = row_for('塑形机')
    A = [grinder, [-v for v in grinder], [-v for v in mineral_grinder],
         shaper, [-v for v in shaper]]
    b = [F(1),F(-1,2),F(-1,2),F(counts[3]), -max(F(0),F(counts[3])-F(1,2))]
    # v = S*r + z*e_蓝铁矿 + (7-z)*e_源矿。
    for i,item in enumerate(items):
        v = [F(r['outputs'].get(item,0)-r['inputs'].get(item,0)) for r in recipes]
        v += [F(int(item=='蓝铁矿')-int(item=='源矿'))] + [F(0)]*len(items)
        offset = F(7 if item=='源矿' else 0)
        for sign in [1,-1]:
            row = [sign*q for q in v]
            row[19+i] = -1
            A.append(row)
            b.append(-sign*offset)
    E = [row_for(k) for k in SATURATED]
    d = [F(counts[KINDS.index(k)]) for k in SATURATED]
    upper = [rate if r['kind'] not in ['封装机','灌装机'] else F(0)
             for rate,r in zip(rates,recipes)] + [F(7)] + [None]*len(items)
    c = [F(0)]*19 + [F(1)]*len(items)
    return A,b,E,d,upper,c


def dot(a,b):
    return sum((x*y for x,y in zip(a,b)), F(0))


def check_certificate(model, certificate):
    A,b,E,d,u,c = model
    def vec(key):
        return [F(x) for x in certificate[key]]
    x,y,e,lo,hi = [vec(key) for key in ['primal','y','e','lower','upper']]
    assert len(x)==len(lo)==len(hi)==len(c)
    assert len(y)==len(A) and len(e)==len(E)
    assert all(v>=0 for v in x)
    assert all(bound is None or v<=bound for v,bound in zip(x,u))
    assert all(dot(row,x)<=rhs for row,rhs in zip(A,b))
    assert all(dot(row,x)==rhs for row,rhs in zip(E,d))
    assert all(v<=0 for v in y) and all(v>=0 for v in lo) and all(v<=0 for v in hi)
    assert all(bound is not None or mult==0 for bound,mult in zip(u,hi))
    for j in range(len(c)):
        assert c[j] == sum((A[i][j]*y[i] for i in range(len(A))),F(0)) + \
                       sum((E[i][j]*e[i] for i in range(len(E))),F(0)) + lo[j]+hi[j]
    lower = dot(b,y)+dot(d,e)+sum((v*bound for v,bound in zip(hi,u) if bound is not None),F(0))
    objective = dot(c,x)
    assert lower == objective == F(certificate['bound'])
    assert lower >= F(19,3)
    return lower


def verify_set(data, recipes, items, rates):
    expected = {tuple(n) for n in branches()}
    seen = set()
    bounds = []
    for cert in data:
        counts = tuple(cert['counts'])
        assert counts in expected and counts not in seen
        seen.add(counts)
        bounds.append(check_certificate(build_model(recipes,items,rates,counts), cert))
    assert seen == expected
    assert min(bounds) == F(19,3)
    return {'branches': len(seen), 'minimum': min(bounds), 'maximum': max(bounds),
            'bound_distribution': dict(sorted(Counter(str(v) for v in bounds).items())),
            'all_exact': True}


def solve_new(recipes,items,rates):
    from scipy.optimize import linprog
    certificates=[]
    for counts in branches():
        A,b,E,d,u,c=build_model(recipes,items,rates,counts)
        def floating(rows):
            return [[float(v) for v in row] for row in rows]
        res=linprog([float(v) for v in c], A_ub=floating(A),b_ub=list(map(float,b)),
                    A_eq=floating(E),b_eq=list(map(float,d)),
                    bounds=[(0,None if v is None else float(v)) for v in u],method='highs')
        assert res.success, (counts,res.message)
        def rational(xs):
            return [F(float(v)).limit_denominator(1000000) for v in xs]
        primal=rational(res.x)
        cert={'counts':counts,'primal':primal,'y':rational(res.ineqlin.marginals),
              'e':rational(res.eqlin.marginals),'lower':rational(res.lower.marginals),
              'upper':rational(res.upper.marginals),'bound':dot(c,primal)}
        check_certificate((A,b,E,d,u,c),cert)
        certificates.append(cert)
    return certificates


def edge_pattern(g):
    # 直接铺3格取货口；唯一空格g不铺。
    occupied=set()
    centers=[]
    x=0
    while x<70:
        if x==g:
            x+=1
        else:
            block={x,x+1,x+2}
            assert g not in block and max(block)<70
            occupied |= block
            centers.append(x+1)
            x+=3
    assert len(occupied)==69 and len(centers)==23
    return centers


def geometry(minima):
    patterns=[(left,bottom) for left,bottom in product(range(0,70,3), repeat=2)
              if left==0 or bottom==0]
    assert len(patterns)==47
    records=[]
    for b in [6,7,9,17]:
        for left,g in patterns:
            centers=edge_pattern(g)
            sources=[x for x in centers if x>=49]
            assert len(sources)==7
            # 完整大制造单位，包含端口朝向；只用必要条件筛选。
            candidates=[]
            for w,h in [(6,4),(4,6)]:
                for x in range(49,71-w):
                    for y in range(1,b-h+1):
                        if y==1 and any(x<=s<x+w for s in sources):
                            continue
                        for input_side in (['下','上'] if w==6 else ['左','右']):
                            if w==6:
                                # y=0为空格也不能在循环态转运；y=b为空矩形。
                                available=(y-1>=1 and y+h<b)
                            else:
                                # x=48主区运输格可用；基地以外不可用。
                                available=(x-1>=0 and x+w<70)
                            if available:
                                candidates.append({'x':x,'y':y,'w':w,'h':h,'input':input_side})
            if b==6:
                assert not candidates
            viable=[]
            if b==7:
                for q in candidates:
                    assert q['y']==2 and q['w']==6 and q['h']==4
                    m=sum(q['x']<=s<q['x']+6 for s in sources)
                    assert m in [1,2]
                    for kind in ['研磨机','封装机','灌装机']:
                        input_count={'研磨机':3,'封装机':25,'灌装机':20}[kind]
                        rate=minima[kind]*(input_count if q['input']=='下' else 1)
                        if m+rate<=2:
                            assert m==1 and q['input']=='上'
                            viable.append({**q,'kind':kind,'m':m})
                starts=sorted({q['x'] for q in viable})
                assert all(abs(a-z)<6 for a,z in product(starts,repeat=2))
                for x in starts:
                    # 穷尽所有可能碰第1行的3x3机身，必与唯一研磨机重叠。
                    for sx in range(49,68):
                        if not any(sx<=s<sx+3 for s in sources):
                            assert max(sx,x)<min(sx+3,x+6)
                records.append({'b':b,'left_gap':left,'bottom_gap':g,'raw_ports':sources,
                                'large_singleton_candidates':len(candidates),'grinder_starts':starts})
            else:
                records.append({'b':b,'left_gap':left,'bottom_gap':g,'raw_ports':sources,
                                'large_singleton_candidates':len(candidates)})
    possible=[r for r in records if r['b']==7 and r['grinder_starts']]
    assert len(possible)==6 and sum(len(r['grinder_starts']) for r in possible)==10
    return {'pattern_count':len(patterns),'cases':records,'b7_shapes':possible,
            'note':'单体必要域，不是可行布局；b9、17不使用一格走廊进一步筛选。'}


def scope_checks():
    # 几何定义检验：b=9孔为[49,69]x[9,61]，桩在[48,49]x[64,65]。
    hole={(x,y) for x in range(49,70) for y in range(9,62)}
    pole={(x,y) for x in [48,49] for y in [64,65]}
    assert not (hole & pole)
    assert {x for x,y in pole}=={48,49}
    assert not any(1<=y<=8 for x,y in pole)
    return {'b':9,'pole_lower_left':[48,64],'pole_size':[2,2],
            'literal_D_contribution':2,'lower_strip_D_contribution':0,
            'intersects_hole':False,'is_full_layout_counterexample':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exact',action='store_true')
    args=parser.parse_args()
    before=hashes()
    recipes=recipes_from_rules()
    items,rates,load,minima=global_rates(recipes)
    data=json.loads((OLD/'b7_rational_certificates.json').read_text())
    old_check=verify_set(data,recipes,items,rates)
    if args.exact:
        own=json.loads((HERE/'new_certificates.json').read_text())
        result={'formal_sha256':before,'old_certificates':old_check,
                'new_certificates':verify_set(own,recipes,items,rates),'solver_called':False}
        assert before==hashes()
        dump('exact_verification.json',result)
        print(json.dumps(result,ensure_ascii=False,default=str))
        return
    own=solve_new(recipes,items,rates)
    dump('new_certificates.json',own)
    accounting=[]
    for r,rate in zip(recipes,rates):
        ki=sum(v for s,v in r['inputs'].items() if s in MINERALS)
        ko=sum(v for s,v in r['outputs'].items() if s in MINERALS)
        accounting.append({**r,'global_rate':rate,'K_in':ki,'K_out':ko,
                           'K_net_reduction':ki-ko,'K_input_per_tick_cap':F(ki,r['ticks'])})
    dump('recipes.json',{'recipes':accounting,'global_load':load,'per_machine_min_batches':minima})
    geom=geometry(minima)
    dump('geometry.json',geom)
    scope=scope_checks()
    dump('scope_check.json',scope)
    best=min(own,key=lambda q:q['bound'])
    bm=build_model(recipes,items,rates,best['counts'])
    dump('model.json',{'items':items,'kinds':KINDS,'recipe_order':recipes,
                       'variable_order':'18 recipe rates, blue ore rate, 19 absolute net flows',
                       'best_counts':best['counts'],'A':bm[0],'b':bm[1],'E':bm[2],
                       'd':bm[3],'upper':bm[4],'objective':bm[5]})
    # 整数尺寸面积阶梯独立计算。
    areas=sorted({w*h for w in range(6,69) for h in range(w,69) if w*h<=1113},reverse=True)
    assert areas[:2]==[1113,1110]
    result={'formal_sha256':before,'recipes':len(recipes),'items':len(items),
            'patterns':geom['pattern_count'],'geometry_cases':len(geom['cases']),
            'b7_patterns':len(geom['b7_shapes']),
            'b7_grinder_start_combinations':sum(len(r['grinder_starts']) for r in geom['b7_shapes']),
            'integer_branches':len(branches()),'old_certificates':old_check,
            'new_certificates':verify_set(own,recipes,items,rates),
            'best_counts':dict(zip(KINDS,best['counts'])),
            'cut_capacity_b6':5,'mineral_deficit_b6':2,
            'cut_capacity_b7':6,'deficit_b7':F(1,3),'area_levels':areas[:2],
            'scope_correction':scope}
    assert before==hashes()
    dump('results.json',result)
    print(json.dumps(result,ensure_ascii=False,default=str))


if __name__=='__main__':
    main()
