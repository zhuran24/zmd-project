#!/usr/bin/env python3
"""按推导98S2第2节独立编码230台机器、325条进路；只写本交付目录。"""
import hashlib
import json
import os
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[3]
SOURCE = ROOT / '求解器/候选约束轮次/第98-100轮'


def write(name, value):
    p = BASE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def make_contract():
    machines, outlets, feeds = [], [], []
    kinds = {'粉碎机':'小', '精炼炉':'小', '配件机':'小', '塑形机':'小',
             '种植机':'中', '采种机':'中', '研磨机':'大', '封装机':'大', '灌装机':'大'}

    def m(uid, name, model, recipe, inputs, outputs, rate='1', time=1):
        machines.append(dict(id=uid, name=name, model=model, kind=kinds[model],
                             recipe_id=recipe, inputs=inputs, outputs=outputs,
                             batch_rate=str(Fraction(rate)), duration=time))

    def f(a, b, item, rate='1'):
        feeds.append(dict(id=f'LF{len(feeds):03}', source=a, target=b,
                          item=item, rate=str(Fraction(rate))))

    for i in range(1, 35):
        w, r, k = f'WFE{i}', f'RF{i}', f'KF{i}'
        outlets.append(dict(id=w, name=f'第{i}条蓝铁矿的仓库取货口', item='蓝铁矿'))
        m(r, f'第{i}台蓝铁矿精炼炉', '精炼炉', '精炼-蓝铁矿', {'蓝铁矿':1}, {'蓝铁块':1})
        m(k, f'第{i}台蓝铁块粉碎机', '粉碎机', '粉碎-蓝铁块', {'蓝铁块':1}, {'蓝铁粉末':1})
        f(w, r, '蓝铁矿'); f(r, k, '蓝铁块')
    for i in range(1, 19):
        k = f'KO{i}'
        if i <= 6:
            w = 'CORE'
        else:
            w = f'WO{i}'
            outlets.append(dict(id=w, name=f'第{i}条源矿的仓库取货口', item='源矿'))
        m(k, f'第{i}台源矿粉碎机', '粉碎机', '粉碎-源矿', {'源矿':1}, {'源石粉末':1})
        f(w, k, '源矿')
    for i in range(1, 18):
        m(f'B{i}', f'B{i} 蓝铁粉末研磨机', '研磨机', '研磨-致密蓝铁',
          {'蓝铁粉末':2, '砂叶粉末':1}, {'致密蓝铁粉末':1})
        f(f'KF{2*i-1}', f'B{i}', '蓝铁粉末'); f(f'KF{2*i}', f'B{i}', '蓝铁粉末')
    for i in range(1, 10):
        m(f'O{i}', f'O{i} 源石粉末研磨机', '研磨机', '研磨-致密源石',
          {'源石粉末':2, '砂叶粉末':1}, {'致密源石粉末':1})
        f(f'KO{2*i-1}', f'O{i}', '源石粉末'); f(f'KO{2*i}', f'O{i}', '源石粉末')
    for i in range(1, 7):
        m(f'Q{i}', f'Q{i} 荞花粉末研磨机', '研磨机', '研磨-细磨荞花',
          {'荞花粉末':2, '砂叶粉末':1}, {'细磨荞花粉末':1}, '1/2' if i == 6 else '1')

    sand_groups = [['B1','B2','O1'], ['O2','O3'], ['B3','B4','O4'], ['O5','O6'],
                   ['B5','B6','O7'], ['O8','O9'], ['B7','B8','B9'], ['B10','Q1','Q2'],
                   ['B11','B12','B13'], ['B14','Q3','Q4'], ['B15','B16','Q5'], ['B17'], ['Q6']]
    for plant, count, prefix, outputs in [('砂叶',13,'S',3), ('荞花',6,'Q',2)]:
        for i in range(1, count+1):
            c, a, b = f'{prefix}C{i}', f'{prefix}A{i}', f'{prefix}B{i}'
            k = f'S{i}' if plant == '砂叶' else f'QK{i}'
            if plant == '砂叶':
                demand = sum((Fraction(1,2) if t=='Q6' else Fraction(1)) for t in sand_groups[i-1])
                rate = demand / 3
            else:
                rate = Fraction(1,2) if i == 6 else Fraction(1)
            seed, powder = plant+'种子', plant+'粉末'
            m(c, f'第{i}台{plant}采种机', '采种机', '采种-'+plant, {plant:1}, {seed:2}, rate)
            m(a, f'第{i}台{plant}回路种植机', '种植机', '种植-'+plant, {seed:1}, {plant:1}, rate)
            m(b, f'第{i}台{plant}供粉碎机的种植机', '种植机', '种植-'+plant, {seed:1}, {plant:1}, rate)
            m(k, f'第{i}台{plant}粉碎机', '粉碎机', '粉碎-'+plant, {plant:1}, {powder:outputs}, rate)
            f(c,a,seed,rate); f(c,b,seed,rate); f(a,c,plant,rate); f(b,k,plant,rate)
    for i, group in enumerate(sand_groups, 1):
        for t in group:
            f(f'S{i}', t, '砂叶粉末', '1/2' if t == 'Q6' else '1')
    for i in range(1,7):
        f(f'QK{i}', f'Q{i}', '荞花粉末')
        if i < 6: f(f'QK{i}', f'Q{i}', '荞花粉末')
    for i in range(1,18):
        m(f'R{i}', f'R{i} 致密蓝铁粉末精炼炉', '精炼炉', '精炼-致密蓝铁', {'致密蓝铁粉末':1}, {'钢块':1})
        f(f'B{i}', f'R{i}', '致密蓝铁粉末')
    for i in range(1,7):
        m(f'P{i}', f'P{i} 配件机', '配件机', '配件-钢制零件', {'钢块':1}, {'钢制零件':1})
        m(f'H{i}', f'H{i} 塑形机', '塑形机', '塑形-钢质瓶', {'钢块':2}, {'钢质瓶':1}, '1/2' if i==6 else '1')
        f(f'R{i}', f'P{i}', '钢块')
    for i in range(1,6):
        f(f'R{2*i+5}', f'H{i}', '钢块'); f(f'R{2*i+6}', f'H{i}', '钢块')
    f('R17','H6','钢块')
    for i in range(1,4):
        m(f'E{i}', f'E{i} 封装机', '封装机', '封装-电池',
          {'钢制零件':10,'致密源石粉末':15}, {'高容谷地电池':1}, '1/5', 5)
        for j in [2*i-1, 2*i]: f(f'P{j}', f'E{i}', '钢制零件')
        for j in [3*i-2, 3*i-1, 3*i]: f(f'O{j}', f'E{i}', '致密源石粉末')
        f(f'E{i}','CORE','高容谷地电池','1/5')
    for i, rate in enumerate(['1/5','1/5','1/10','1/20'],1):
        m(f'F{i}', f'F{i} 灌装机', '灌装机', '灌装-胶囊',
          {'钢质瓶':10,'细磨荞花粉末':10}, {'精选荞愈胶囊':1}, rate, 5)
        indices = [2*i-1,2*i] if i<3 else [i+2]
        for j in indices:
            f(f'H{j}',f'F{i}','钢质瓶','1/2' if j==6 else '1')
            f(f'Q{j}',f'F{i}','细磨荞花粉末','1/2' if j==6 else '1')
        f(f'F{i}','CORE','精选荞愈胶囊',rate)
    return dict(schema='s2-logical-contract-v1', basis='推导98S2.md §2',
                machines=machines, warehouse_outlets=outlets,
                core=dict(id='CORE', output_item='源矿', output_count=6),
                logical_feeds=feeds, equal_length=[['H6','F4'],['Q6','F4']],
                boundary_sides=['左','下'], route_type='互不共格且至少一格的纯有向传送带',
                forbidden_units=['桥接器','物品准入口','分流器','汇流器','协议储存箱'])


def canonical(old):
    if old.startswith('协议核心'): return 'CORE'
    prefixes = [('矿精炼','RF'), ('铁粉碎','KF'), ('源粉碎','KO'), ('铁研磨','B'), ('源研磨','O'),
                ('荞研磨','Q'), ('砂叶采种','SC'), ('砂叶种植A','SA'), ('砂叶种植B','SB'),
                ('砂叶粉碎','S'), ('荞花采种','QC'), ('荞花种植A','QA'), ('荞花种植B','QB'),
                ('荞花粉碎','QK'), ('钢精炼','R'), ('配件','P'), ('塑形','H'), ('封装','E'), ('灌装','F')]
    for a,b in prefixes:
        if old.startswith(a): return b+str(int(old[len(a):])+1)
    if old.startswith('仓库取货口'):
        i=int(old.removeprefix('仓库取货口'))
        return f'WFE{i+1}' if i<34 else f'WO{i-33}'
    raise ValueError(old)


def main():
    paths = {
        '规则.txt': SOURCE/'前提快照/《明日方舟：终末地》游戏规则.txt',
        '任务.txt': SOURCE/'前提快照/求解任务.txt',
        '约束.txt': SOURCE/'前提快照/求解约束.txt',
        '推导98S2.md': SOURCE/'推导98S2.md',
        '既有逻辑图.json': SOURCE/'推导98S2/graph_98040.json',
        '既有逻辑图生成器.py': SOURCE/'推导98S2/factory_check.py',
        '全厂静态格式.md': ROOT/'求解器/构造/第一张全厂候选/格式.md',
    }
    records=[]
    for name,p in paths.items():
        target=BASE/'依据快照'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(p.read_bytes())
        records.append(dict(source=str(p),copy=str(target.relative_to(BASE)),sha256=sha(target)))
    write('证据/输入指纹.json',records)
    contract=make_contract()
    write('逻辑接法.json',contract)
    old=json.loads((BASE/'依据快照/既有逻辑图.json').read_text())
    expected=Counter((canonical(r['from']),canonical(r['to']),r['item']) for r in old['routes'])
    actual=Counter((r['source'],r['target'],r['item']) for r in contract['logical_feeds'])
    counts=dict(Counter(m['model'] for m in contract['machines']))
    balances=[]
    for m in contract['machines']:
        for way,key in [('input','inputs'),('output','outputs')]:
            endpoint='target' if way=='input' else 'source'
            got=defaultdict(Fraction)
            for e in contract['logical_feeds']:
                if e[endpoint]==m['id']: got[e['item']]+=Fraction(e['rate'])
            want={item:qty*Fraction(m['batch_rate']) for item,qty in m[key].items()}
            if dict(got)!=want: balances.append(dict(machine=m['id'],way=way,got=str(got),want=str(want)))
    result=dict(machine_count=len(contract['machines']),machine_counts=counts,
                route_count=len(contract['logical_feeds']),warehouse_outlet_count=len(contract['warehouse_outlets']),
                machine_area=sum({'小':9,'中':25,'大':24}[m['kind']] for m in contract['machines']),
                full_multiset_matches_existing_graph=actual==expected,
                missing=list((expected-actual).elements()),extra=list((actual-expected).elements()),
                exact_material_balance_errors=balances,
                scope='独立转写第2节并逐条比对现有325路；没有坐标，不是布局')
    write('证据/接法逐条对照.json',result)
    assert len(contract['machines'])==230 and len(contract['logical_feeds'])==325
    assert len(contract['warehouse_outlets'])==46 and counts==old['machines']
    assert actual==expected and not balances
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()
