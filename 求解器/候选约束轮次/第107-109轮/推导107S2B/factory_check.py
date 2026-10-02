#!/usr/bin/env python3
"""226-machine isolated slow branches; abstract directed belt model only."""
import argparse
import hashlib
import json
import pickle
import random
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
from engine_a import Factory, M, R
from engine_b import EngineB

HERE = Path(__file__).resolve().parent
PRODUCTS = ('高容谷地电池', '精选荞愈胶囊')


class Layout(Factory):
    def __init__(self, seed, maxlen, initial='empty', core_mix=False, separate=False, layer=False):
        self.rng = random.Random(seed)
        self.ms, self.sources, self.rs, self.units = [], [], [], []
        self.t, self.open = 0, True
        self.delivered = Counter()
        self.sink, self.core = M('协议核心收货'), M('协议核心取货')
        self.sources.append(self.core)
        self.types = Counter()

        def m(name, typ, ingredients, product, qty=1, duration=8):
            u = M(name, (ingredients, product, qty, duration))
            u.typ = typ
            self.ms.append(u)
            self.types[typ] += 1
            return u

        def r(a, b, item):
            v = R(a, b, item, self.rng.randint(1, maxlen), len(self.rs))
            self.rs.append(v)
            a.routes.append(v)
            a.sent[v.index] = -1
            a.order[v.index] = v.index
            b.accept_order[v.index] = v.index
            return v

        # A core shared by six ore streams of one packaging module, or a mixed
        # stress case. It always remains one nontransport sending unit.
        core_indices = set(range(34, 40)) if not core_mix else {0, 12, 32, 34, 40, 50}
        def ore(i):
            if i in core_indices:
                return self.core
            u = M('仓库取货口' + str(i))
            self.sources.append(u)
            return u

        fe = [m('矿精炼'+str(i), '精炼炉', {'蓝铁矿':1}, '蓝铁块') for i in range(34)]
        fc = [m('铁粉碎'+str(i), '粉碎机', {'蓝铁块':1}, '蓝铁粉末') for i in range(34)]
        oc = [m('源粉碎'+str(i), '粉碎机', {'源矿':1}, '源石粉末') for i in range(18)]
        for i in range(34):
            r(ore(i), fe[i], '蓝铁矿')
            r(fe[i], fc[i], '蓝铁块')
        for i in range(18):
            r(ore(34+i), oc[i], '源矿')
        gf = [m('铁研磨'+str(i), '研磨机', {'蓝铁粉末':2,'砂叶粉末':1}, '致密蓝铁粉末') for i in range(17)]
        go = [m('源研磨'+str(i), '研磨机', {'源石粉末':2,'砂叶粉末':1}, '致密源石粉末') for i in range(9)]
        gq = [m('荞研磨'+str(i), '研磨机', {'荞花粉末':2,'砂叶粉末':1}, '细磨荞花粉末') for i in range(6)]
        for i, u in enumerate(gf):
            r(fc[2*i], u, '蓝铁粉末'); r(fc[2*i+1], u, '蓝铁粉末')
        for i, u in enumerate(go):
            r(oc[2*i], u, '源石粉末'); r(oc[2*i+1], u, '源石粉末')
        ks, kq = [], []
        for plant, n, k in [('砂叶', 16 if layer else (13 if separate else 12), 3), ('荞花', 6, 2)]:
            for i in range(n):
                sd, pw = plant+'种子', plant+'粉末'
                c = m(plant+'采种'+str(i), '采种机', {plant:1}, sd, 2)
                a = m(plant+'种植A'+str(i), '种植机', {sd:1}, plant)
                b = m(plant+'种植B'+str(i), '种植机', {sd:1}, plant)
                k0 = m(plant+'粉碎'+str(i), '粉碎机', {plant:1}, pw, k)
                ca = r(c,a,sd); r(c,b,sd); ac = r(a,c,plant); r(b,k0,plant)
                self.units.append((c,a,b,k0,ca,ac))
                (ks if plant == '砂叶' else kq).append(k0)
        if layer:
            groups = []
            for i in range(3):
                groups += [gf[2*i:2*i+2], go[3*i:3*i+3]]
            for i in range(2):
                blue=gf[6+4*i:10+4*i]
                groups += [blue[:3],blue[3:],gq[2*i:2*i+2]]
            groups += [gf[14:16],[gq[4]],[gf[16]],[gq[5]]]
            assert len(groups)==16
            for source, group in zip(ks,groups):
                for target in group: r(source,target,'砂叶粉末')
        elif not separate:
            fast = gf + go + gq[:5]
            # Fixed assignment, all shared sand groups contain only full-rate
            # target branches. A slow branch never shares its K with a fast one.
            for i, target in enumerate(fast):
                r(ks[i//3], target, '砂叶粉末')
            r(ks[11], gq[5], '砂叶粉末')
        else:
            # Stronger isolation by final machine (230 machines).
            groups = []
            for i in range(3):
                v = gf[2*i:2*i+2] + go[3*i:3*i+3]
                groups += [v[:3], v[3:]]
            for i in range(2):
                v = gf[6+4*i:10+4*i] + gq[2*i:2*i+2]
                groups += [v[:3], v[3:]]
            groups += [gf[14:16]+[gq[4]], [gf[16]], [gq[5]]]
            assert len(groups) == 13
            for source, group in zip(ks, groups):
                for target in group:
                    r(source, target, '砂叶粉末')
        for i, (source, target) in enumerate(zip(kq, gq)):
            r(source, target, '荞花粉末')
            if i < 5:
                r(source, target, '荞花粉末')
        st = [m('钢精炼'+str(i), '精炼炉', {'致密蓝铁粉末':1}, '钢块') for i in range(17)]
        pc = [m('配件'+str(i), '配件机', {'钢块':1}, '钢制零件') for i in range(6)]
        sh = [m('塑形'+str(i), '塑形机', {'钢块':2}, '钢质瓶') for i in range(6)]
        for u, v in zip(gf, st): r(u,v,'致密蓝铁粉末')
        for i in range(6): r(st[i], pc[i], '钢块')
        for i in range(5):
            r(st[6+2*i], sh[i], '钢块'); r(st[7+2*i], sh[i], '钢块')
        r(st[16], sh[5], '钢块')
        packs = [m('封装'+str(i), '封装机', {'钢制零件':10,'致密源石粉末':15}, PRODUCTS[0], 1, 40) for i in range(3)]
        fills = [m('灌装'+str(i), '灌装机', {'钢质瓶':10,'细磨荞花粉末':10}, PRODUCTS[1], 1, 40) for i in range(4)]
        for i in range(3):
            for j in range(2): r(pc[2*i+j], packs[i], '钢制零件')
            for j in range(3): r(go[3*i+j], packs[i], '致密源石粉末')
            r(packs[i], self.sink, PRODUCTS[0])
        for i in range(2):
            for j in range(2):
                r(sh[2*i+j], fills[i], '钢质瓶')
                r(gq[2*i+j], fills[i], '细磨荞花粉末')
        for i in range(2):
            r(sh[4+i], fills[2+i], '钢质瓶')
            r(gq[4+i], fills[2+i], '细磨荞花粉末')
        for u in fills: r(u, self.sink, PRODUCTS[1])
        if layer or separate:
            pair=[v for v in self.rs if v.target is fills[3]]
            assert len(pair)==2
            pair[1].cells=[None]*len(pair[0].cells)
            if maxlen==1:
                # Meet the independent scalar lower bound of eight additional
                # boundary ore cells. This still is not a geometric embedding.
                for v in [v for v in self.rs if v.source in self.sources and v.source is not self.core][:8]:
                    v.cells.append(None)
        self.fills, self.sh = fills, sh
        self.ore_routes = [v for v in self.rs if v.source in self.sources]
        self.incoming = {u:[] for u in self.ms+[self.sink]}
        for v in self.rs: self.incoming[v.target].append(v)
        self.received = [0]*len(self.rs)
        self.refusals = [0]*len(self.rs)
        self.fast_shared = [v for v in self.rs if len(v.source.routes)>1 and
                            (v.source is self.core or (v.source.typ == '粉碎机'))]
        self.plant_machines = {u for unit in self.units for u in unit[:4]}
        for u in self.ms:
            if initial in ('dense','prepared'):
                u.stock.update({k:50 for k in u.recipe[0]})
                u.out, u.done = 50, True
            elif initial == 'random':
                u.stock.update({k:self.rng.randrange(51) for k in u.recipe[0]})
                u.out = self.rng.randrange(51)
                if self.rng.random()<.7:
                    u.remaining = self.rng.randrange(1,u.recipe[3]+1)
        if initial != 'empty':
            for v in self.rs:
                v.cells = [-self.rng.randrange(9) if initial == 'dense' or self.rng.random()<.7 else None for _ in v.cells]
        # This is the proven dense source hypothesis, not the lower Phi startup.
        for u in self.plant_machines:
            u.stock = Counter({k:50 for k in u.recipe[0]})
            u.out, u.done, u.remaining = 50, True, 0
        for v in self.rs:
            if v.source in self.plant_machines and v.target in self.plant_machines:
                v.cells = [-self.rng.randrange(9) for _ in v.cells]
        if initial == 'prepared':
            for u in packs+fills:
                u.out,u.done,u.remaining=0,False,0
            for v in self.rs:
                v.cells=([None] if v.target is self.sink else [-8])*len(v.cells)
        rebuild(self, self.rng, blueprint=True)


def rebuild(f, rng, blueprint=False, reset=True):
    physical = f.ms + f.sources
    keys = [('m',i) for i in range(len(physical))]
    cells = [('c',r.index,j) for r in f.rs for j in range(len(r.cells))]
    if blueprint:
        rng.shuffle(keys); rng.shuffle(cells); keys += cells
    else:
        keys += cells; rng.shuffle(keys)
    rank = {key:i for i,key in enumerate(keys)}
    ids = {u:i for i,u in enumerate(physical)}
    ids[f.sink] = ids[f.core]
    for r in f.rs:
        r.source.order[r.index] = max(rank[('m',ids[r.source])],rank[('c',r.index,0)])
        r.target.accept_order[r.index] = max(rank[('m',ids[r.target])],rank[('c',r.index,len(r.cells)-1)])
    if reset:
        for u in physical:
            u.sent = {r.index:-1 for r in u.routes}
    for u, routes in f.incoming.items():
        routes.sort(key=lambda r:(u.accept_order[r.index],r.index))
        if reset: u.cursor = None


def state_b(b):
    # Complete autonomous state of B; absolute due times and send times are
    # reduced to remaining durations and relative success order respectively.
    return (tuple(tuple(sorted(s.items())) for s in b.stock), tuple(b.out),
            tuple(None if d is None else d-b.time for d in b.due),
            tuple(b.complete), tuple(tuple(x) for x in b.cargo), tuple(b.cursor),
            tuple(tuple(sorted(rs,key=lambda r:(b.last[r],b.rank[r]))) for rs in b.outgoing))


def graph(f):
    return {'machines':dict(f.types),'machine_count':len(f.ms),'route_count':len(f.rs),
            'sources':len(f.sources),'core_outlets':len(f.core.routes),
            'routes':[{'id':r.index,'from':r.source.name,'to':r.target.name,'item':r.kind,'length':len(r.cells)} for r in f.rs]}


def run(args):
    f = Layout(args.seed,args.maxlen,args.initial,args.core_mix,args.separate,args.layer)
    b = EngineB(f)
    rng = random.Random(args.seed+1000000)
    graph_data = graph(f)
    (HERE/f'graph_{args.seed}.json').write_text(json.dumps(graph_data,ensure_ascii=False,indent=2)+'\n')
    first = [None]*len(f.rs)
    last = [None]*len(f.rs)
    lowest = {u.name:{k:u.stock[k] for k in u.recipe[0]} for u in f.ms}
    resets = []
    invariant_violations=[]
    recent_begins=[]
    fast_units=[u for u in f.ms if u not in f.plant_machines and u.typ not in ('封装机','灌装机') and u.name not in ('塑形5','荞研磨5')]
    shared_groups={r.source:sorted({v.target for v in r.source.routes},key=lambda u:u.name) for r in f.fast_shared}

    def step():
        old = f.refusals[:]
        f.step(); b.step(); b.compare(f)
        assert b.received == f.received
        for i,(x,y) in enumerate(zip(old,f.refusals)):
            if x!=y:
                if first[i] is None: first[i]=f.t-1
                last[i]=f.t-1
        for u in f.ms:
            for k in u.recipe[0]:
                lowest[u.name][k] = min(lowest[u.name][k],u.stock[k])
        began_now={u:u.remaining==u.recipe[3] for u in f.ms}
        recent_begins.append(began_now)
        if len(recent_begins)>3: recent_begins.pop(0)
        if (args.layer or args.separate) and args.initial=='prepared' and len(invariant_violations)<20:
            for u in fast_units:
                if u.out!=50 or not(u.done or u.remaining) or any(u.stock[k]<50-q for k,q in u.recipe[0].items()):
                    invariant_violations.append({'t':f.t,'machine':u.name,'stock':dict(u.stock),'output':u.out,'remaining':u.remaining,'done':u.done})
                    break
            for source,targets in shared_groups.items():
                offsets=[2 if u.name.startswith('铁研磨') else 0 for u in targets]
                span=max(offsets)-min(offsets)
                if len(recent_begins)<=span: continue
                began=[recent_begins[-1-(max(offsets)-d)][u] for u,d in zip(targets,offsets)]
                if any(began) and not all(began):
                    invariant_violations.append({'t':f.t,'source':source.name,'common_calendar_failed':[u.name for u,b0 in zip(targets,began) if b0]})
                    break

    # All-product stop, then product-selective stops. Long intervals are also
    # exercised to approach saturated downstream buffers.
    events = {101,300,1000,1650,2000,2800,3199,5100,9999,14999,19999}
    for t in range(args.burn):
        accept = {PRODUCTS[0]:True, PRODUCTS[1]:True}
        if 200<=t<2900 or 11000<=t<14500:
            accept = {p:False for p in PRODUCTS}
        if 4000<=t<8000: accept[PRODUCTS[0]]=False
        if 8100<=t<10500: accept[PRODUCTS[1]]=False
        f.open=accept; b.open=accept
        if t in events or (args.frequent and 15000<=t<args.burn and t%7==0):
            clear=args.history=='clear' or (args.history=='alternate' and len(resets)%2==0)
            rebuild(f,rng,reset=clear); b.copy_order(f,reset=clear); resets.append(t)
        step()
    f.open=b.open=True
    seen={}
    result = None
    for _ in range(args.limit):
        step()
        if f.t%8: continue
        key=hashlib.sha256(pickle.dumps(f.state(),protocol=4)).digest()
        if key in seen:
            period=f.t-seen[key]
            start=f.t
            state0,state_b0=f.state(),state_b(b)
            d0=Counter(f.delivered); o0=[r.count for r in f.ore_routes]
            ref0=f.refusals[:]
            for _ in range(period): step()
            exact_a=state0==f.state(); exact_b=state_b0==state_b(b)
            assert exact_a and exact_b, 'hash candidate did not close'
            delta={p:f.delivered[p]-d0[p] for p in PRODUCTS}
            ore=[r.count-n for r,n in zip(f.ore_routes,o0)]
            rejects=[n-old for n,old in zip(f.refusals,ref0)]
            result={'status':'closed_cycle','cycle_start':start,'period_steps':period,
                    'direct_state_equality_a':exact_a,'direct_state_equality_b':exact_b,
                    'delivery':delta,'ore_counts':ore,
                    'all_52_full':all(8*n==period for n in ore),
                    'product_rates_pass':40*delta[PRODUCTS[0]]==3*period and 160*delta[PRODUCTS[1]]==11*period,
                    'critical_shared_refusals':sum(rejects[r.index] for r in f.fast_shared),
                    'critical_shared_routes':len(f.fast_shared),
                    'all_refusals':sum(rejects),'cycle_refusals':[{'id':r.index,'from':r.source.name,'to':r.target.name,'refusals':rejects[r.index]} for r in f.rs if rejects[r.index]],
                    'state_a':state0,'state_b':state_b0}
            break
        seen[key]=f.t
    if result is None: result={'status':'inconclusive_no_cycle_within_limit'}
    result.update({'parameters':vars(args),'machines':dict(f.types),'machine_count':len(f.ms),
                   'route_count':len(f.rs),'transport_cells':sum(len(r.cells) for r in f.rs),
                   'cross_checked_steps':f.t,'offline_events':resets,
                   'critical_shared_last_refusal':max((last[r.index] or -1 for r in f.fast_shared),default=-1),
                   'minimum_stocks':lowest,'graph_path':f'graph_{args.seed}.json'})
    result['full_service_invariant_violations']=invariant_violations
    (HERE/f'cycle_{args.seed}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('state_a','state_b','minimum_stocks','cycle_refusals','offline_events')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--seed',type=int,default=98020)
    p.add_argument('--maxlen',type=int,default=4)
    p.add_argument('--initial',choices=['empty','dense','random','prepared'],default='empty')
    p.add_argument('--burn',type=int,default=20000)
    p.add_argument('--limit',type=int,default=90000)
    p.add_argument('--core-mix',action='store_true')
    p.add_argument('--separate',action='store_true')
    p.add_argument('--layer',action='store_true')
    p.add_argument('--frequent',action='store_true')
    p.add_argument('--history',choices=['clear','keep','alternate'],default='clear')
    run(p.parse_args())
