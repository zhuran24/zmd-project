#!/usr/bin/env python3
"""Physical bridge-axis step engine versus independent age-array route engine.

Topology is an abstract port graph, never a 70 x 70 geometric certificate.
The reference modules are frozen copies of 98S2. This file does not call
Factory.step: it dispatches actual belt components and both bridge axes.
"""
import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from factory_check import Layout, graph
from engine_b import EngineB

HERE = Path(__file__).resolve().parent
PRODUCTS = ('高容谷地电池', '精选荞愈胶囊')


class BridgeFactory(Layout):
    def __init__(self, seed=107001, maxlen=5, mode='mixed'):
        super().__init__(seed, maxlen, initial='prepared', separate=True)
        self.seed, self.mode = seed, mode
        self.rng = random.Random(seed + 17000)
        self.enabled = {u: True for u in self.ms}
        self.prev, self.phys, self.kinds, self.components = [], [], [], []
        self.element_of = {}
        self.forward, self.backward, self.inputs = {}, {}, defaultdict(list)
        self.recv_cursor, self.send_cursor, self.channel_last = {}, {}, {}
        self.mphys = {u: 'M:' + u.name for u in self.ms + self.sources}
        self.mphys[self.sink] = self.mphys[self.core]
        buckets = [[], []]
        for r in self.rs:
            if mode == 'all_bridge':
                types = ['B'] * len(r.cells)
            elif mode == 'belt':
                types = ['L'] * len(r.cells)
            else:
                types = ['B' if self.rng.random() < .65 else 'L' for _ in r.cells]
            self.kinds.append(types)
            axis = self.rng.randrange(2)
            physical = []
            for j, typ in enumerate(types):
                if typ == 'B':
                    if j == 0 or types[j-1] != 'B':
                        axis = self.rng.randrange(2)
                    buckets[axis].append((r.index, j))
                    physical.append(None)
                else:
                    physical.append(f'L:{r.index}:{j}')
            self.phys.append(physical)
        self.rng.shuffle(buckets[0]); self.rng.shuffle(buckets[1])
        self.bridge_axes = {}
        bnum = 0
        while buckets[0] or buckets[1]:
            axis = 0 if buckets[0] else 1
            a = buckets[axis].pop()
            matches = [j for j,b in enumerate(buckets[1-axis]) if b[0] != a[0]]
            occurrences = [(axis, a)]
            if matches:
                occurrences.append((1-axis, buckets[1-axis].pop(matches[-1])))
            name = f'B:{bnum}'; bnum += 1
            self.bridge_axes[name] = occurrences
            for _, (ri, j) in occurrences:
                self.phys[ri][j] = name
        for r in self.rs:
            assert len(set(self.phys[r.index])) == len(r.cells)
            origins = []
            for j,c in enumerate(r.cells):
                origins.append(None if c is None else self.upstream_unit(r.index, j))
            self.prev.append(origins)
            j = 0
            while j < len(r.cells):
                end = j
                if self.kinds[r.index][j] == 'L':
                    while end+1 < len(r.cells) and self.kinds[r.index][end+1] == 'L':
                        end += 1
                e = len(self.components)
                self.components.append((r.index, j, end))
                for k in range(j, end+1): self.element_of[r.index,k] = e
                j = end+1
        self.route_elements = [[] for _ in self.rs]
        for e,(ri,a,b) in enumerate(self.components):
            self.route_elements[ri].append(e)
            r = self.rs[ri]
            receiver = ('m', r.target) if b+1 == len(r.cells) else ('e', self.element_of[ri,b+1])
            self.forward[e] = receiver
            self.inputs[receiver].append(e)
            if self.kinds[ri][a] == 'B' and a > 0 and self.kinds[ri][a-1] == 'B':
                receiver_back = ('e', self.element_of[ri,a-1])
                self.backward[e] = receiver_back
                self.inputs[receiver_back].append(e)
        # Enumerate every non-returning continuation. A backwards bridge branch
        # ends only by revisiting a component, and is NOT a layer-1 terminal.
        def depths(e, seen):
            ans = set()
            for typ,d in [self.forward[e]] + ([self.backward[e]] if e in self.backward else []):
                if typ == 'm': ans.add(1)
                elif d not in seen:
                    ans.update(x+1 for x in depths(d, seen | {d}))
            return ans
        self.layers = []
        for e in range(len(self.components)):
            choices = depths(e, {e})
            assert len(choices) == 1, ('undefined_or_multiple_layers', e, choices)
            self.layers.append(next(iter(choices)))
        for es in self.route_elements:
            assert [self.layers[e] for e in es] == list(range(len(es),0,-1))
        self.reverse_block_checks = 0
        self.trigger_count = 0
        self.cross_axis_early_pulls = 0
        self.rebuild(blueprint=True, reset=True)

    def upstream_unit(self, ri, j):
        return self.mphys[self.rs[ri].source] if j == 0 else self.phys[ri][j-1]

    def downstream_unit(self, ri, j):
        r = self.rs[ri]
        return self.mphys[r.target] if j+1 == len(r.cells) else self.phys[ri][j+1]

    def channel_endpoints(self, e, receiver):
        ri,a,b = self.components[e]
        if receiver == self.forward[e]:
            return self.phys[ri][b], self.downstream_unit(ri,b)
        return self.phys[ri][a], self.phys[ri][a-1]

    def rebuild(self, blueprint=False, reset=True):
        nonbelts = list(set(self.mphys.values()) | set(self.bridge_axes))
        belts = [p for ps,ks in zip(self.phys,self.kinds) for p,k in zip(ps,ks) if k == 'L']
        nonbelts.sort(); belts.sort()
        self.rng.shuffle(nonbelts); self.rng.shuffle(belts)
        order = nonbelts + belts
        if not blueprint: self.rng.shuffle(order)
        rank = {p:i for i,p in enumerate(order)}
        channels = {}
        for e in range(len(self.components)):
            for receiver in [self.forward[e]] + ([self.backward[e]] if e in self.backward else []):
                a,b = self.channel_endpoints(e,receiver)
                channels['e',e,receiver] = max(rank[a],rank[b])
        for r in self.rs:
            channels['s',r.index] = max(rank[self.mphys[r.source]],rank[self.phys[r.index][0]])
        # Equal-time channels are randomly ordered, rather than ordered by ID.
        ties = list(channels); self.rng.shuffle(ties)
        tie = {key:i for i,key in enumerate(ties)}
        self.crank = {key:(time,tie[key]) for key,time in channels.items()}
        for r in self.rs:
            r.source.order[r.index] = self.crank['s',r.index]
            e = self.route_elements[r.index][-1]
            r.target.accept_order[r.index] = self.crank['e',e,('m',r.target)]
        for u, rs in self.incoming.items():
            rs.sort(key=lambda r:u.accept_order[r.index])
            if reset: u.cursor = None
        for receiver, es in self.inputs.items():
            es.sort(key=lambda e:self.crank['e',e,receiver])
        def earliest(e):
            dests = [self.forward[e]] + ([self.backward[e]] if e in self.backward else [])
            return min(self.crank['e',e,d] for d in dests)
        self.schedule = sorted(range(len(self.components)), key=lambda e:(self.layers[e],earliest(e)))
        self.sender_order = sorted(self.sources+self.ms,
                                   key=lambda u:min(u.order.values()) if u.order else (10**9,0))
        if reset:
            for u in self.sources+self.ms: u.sent = {r.index:-1 for r in u.routes}
            self.recv_cursor.clear(); self.send_cursor.clear(); self.channel_last.clear()

    def ready(self, e):
        ri,a,b = self.components[e]
        r = self.rs[ri]
        return r.cells[b] is not None and self.t-r.cells[b] >= 8

    def selected_receiver(self, e):
        if not self.ready(e): return None
        ri,a,b = self.components[e]
        origin = self.prev[ri][b]
        assert origin != self.downstream_unit(ri,b), ('forbidden_forward_origin', self.t,ri,b)
        if e in self.backward:
            self.reverse_block_checks += 1
            # This is a comparison of PHYSICAL units, not of component IDs.
            assert origin == self.phys[ri][a-1], ('reverse_possible',self.t,ri,a,origin)
        return self.forward[e]

    def judge_raw(self, e):
        if e in self.judged: return
        self.judged.add(e)
        ri,a,b = self.components[e]; r = self.rs[ri]
        receiver = self.selected_receiver(e)
        if receiver is not None:
            typ,target = receiver
            if typ == 'm':
                if target is self.sink:
                    ok = self.open if isinstance(self.open,bool) else self.open[r.kind]
                    if ok: self.delivered[r.kind] += 1
                else:
                    # All live items are recipe-compatible and uniquely named.
                    assert r.kind in target.recipe[0]
                    ok = target.stock[r.kind] < 50
                    if ok: target.stock[r.kind] += 1
                if ok:
                    r.cells[b] = None; self.prev[ri][b] = None
                    target.cursor = ri; self.received[ri] += 1
                else: self.refusals[ri] += 1
            else:
                rj,start,end = self.components[target]
                assert rj == ri and start == b+1
                ok = r.cells[start] is None
                if ok:
                    r.cells[start] = self.t; self.prev[ri][start] = self.phys[ri][b]
                    r.cells[b] = None; self.prev[ri][b] = None
            if ok:
                self.recv_cursor[receiver] = e
                self.send_cursor[e] = receiver
                self.channel_last[e,receiver] = self.t
        # A continuous belt is one component; its cells move downstream first.
        for j in range(b-1,a-1,-1):
            if r.cells[j] is not None and self.t-r.cells[j] >= 8 and r.cells[j+1] is None:
                assert self.prev[ri][j] != self.phys[ri][j+1]
                r.cells[j+1] = self.t; self.prev[ri][j+1] = self.phys[ri][j]
                r.cells[j] = None; self.prev[ri][j] = None

    def step(self):
        for u in self.ms:
            if self.enabled[u] and u.remaining:
                u.remaining -= 1
                if not u.remaining: u.done = True; u.batches += 1
            u.flush()
        self.judged = set()
        for e in self.schedule:
            if e in self.judged: continue
            receiver = self.selected_receiver(e)
            if receiver is None:
                self.judge_raw(e); continue
            self.trigger_count += 1
            es = self.inputs[receiver]
            cursor = self.recv_cursor.get(receiver)
            start = 0 if cursor is None else (es.index(cursor)+1)%len(es)
            for x in es[start:]+es[:start]:
                if x not in self.judged:
                    assert x == e or self.layers[x] == self.layers[e], ('early_pull',e,x)
                    self.judge_raw(x)
        assert len(self.judged) == len(self.components)
        for u in self.sender_order:
            if u.recipe and not u.out: continue
            for r in sorted(u.routes,key=lambda r:(u.sent[r.index],u.order[r.index])):
                if r.cells[0] is None:
                    r.cells[0] = self.t; self.prev[r.index][0] = self.mphys[u]
                    r.count += 1; u.count += 1; u.sent[r.index] = self.t
                    if u.recipe: u.out -= 1; u.flush()
                    break
        for u in self.ms:
            if (self.enabled[u] and not u.done and not u.remaining
                    and all(u.stock[k] >= v for k,v in u.recipe[0].items())):
                for k,v in u.recipe[0].items(): u.stock[k] -= v
                u.remaining = u.recipe[3]
        self.t += 1

    def audit(self):
        plants = self.plant_machines
        for u in self.ms:
            assert all(0 <= u.stock[k] <= 50 for k in u.recipe[0]) and 0 <= u.out <= 50
            fast = u not in plants and u.typ not in ('封装机','灌装机') and u.name not in ('塑形5','荞研磨5')
            if fast:
                assert u.out == 50 and (u.done or u.remaining), ('contract_output',self.t,u.name)
                assert all(u.stock[k] >= 50-v for k,v in u.recipe[0].items()), ('contract_input',self.t,u.name)
        for c,a,b,k,ca,ac in self.units:
            assert all(u.done or u.remaining for u in (c,a,b,k))
            assert min(b.stock.values()) >= 49 and min(k.stock.values()) >= 49
            assert b.out >= 49 and k.out >= 50-k.recipe[2]
        for r in self.rs:
            for j,cargo in enumerate(r.cells):
                assert (cargo is None) == (self.prev[r.index][j] is None)
                if cargo is not None:
                    assert self.prev[r.index][j] == self.upstream_unit(r.index,j)
        h = self.sh[5]
        q = next(u for u in self.ms if u.name == '荞研磨5')
        assert (h.stock['钢块'],h.out,h.remaining,h.done) == (q.stock['荞花粉末'],q.out,q.remaining,q.done)
        slow = self.fills[3]
        assert slow.stock['钢质瓶'] == slow.stock['细磨荞花粉末']

    def full_state(self):
        # Channel last-success magnitude is irrelevant; receiver/source order
        # and capped cargo ages are the complete future-relevant histories.
        cursors = tuple(self.send_cursor.get(e) for e in range(len(self.components)))
        normalized = tuple((x[0],self.mphys[x[1]]) if x and x[0]=='m' else x for x in cursors)
        rec = tuple(self.recv_cursor.get(('e',e)) for e in range(len(self.components)))
        return self.state(), tuple(tuple(x) for x in self.prev), normalized, rec

    def evidence_graph(self):
        g = graph(self)
        g.update(is_layout=False, bridges=len(self.bridge_axes),
                 double_axis_bridges=sum(len(v)==2 for v in self.bridge_axes.values()),
                 components=len(self.components), transport_slots=sum(len(r.cells) for r in self.rs),
                 adjacent_bridge_pairs=sum(sum(a==b=='B' for a,b in zip(ts,ts[1:])) for ts in self.kinds),
                 maximum_bridge_run=max((len(s) for ts in self.kinds for s in ''.join(ts).split('L')),default=0),
                 different_F4_segmentation=(self.kinds[self.incoming[self.fills[3]][0].index] != self.kinds[self.incoming[self.fills[3]][1].index]))
        for r in g['routes']:
            ri = r['id']; r['types'] = self.kinds[ri]; r['physical_units'] = self.phys[ri]
            r['component_layers'] = [self.layers[e] for e in self.route_elements[ri]]
        return g


def run_case(seed,maxlen,mode,history,frequent=False):
    f = BridgeFactory(seed,maxlen,mode)
    b = EngineB(f)
    g = f.evidence_graph()
    (HERE/f'graph_{seed}.json').write_text(json.dumps(g,ensure_ascii=False,indent=2)+'\n')
    reorders = 0
    checks = 0
    def one():
        nonlocal checks
        b.open = f.open
        f.step(); b.step(); b.compare(f)
        assert b.received == f.received
        f.audit(); checks += 1
    # Two product kinds are independently stopped, with outages long enough
    # to fill finished-product stocks and halt production.
    for t in range(15000):
        f.open = {PRODUCTS[0]:not(800<=t<7200), PRODUCTS[1]:not(4200<=t<13500)}
        if t in (1,17,799,803,7199,10013,13499,14999) or (frequent and t%7 == 0):
            reset = history == 'clear' or (history == 'mixed' and t%2 == 0)
            f.rebuild(reset=reset); b.copy_order(f,reset); reorders += 1
        one()
    f.open = True
    seen = {}
    for t in range(60000):
        one()
        if f.t%8: continue
        state = f.full_state()
        key = hashlib.sha256(repr(state).encode()).hexdigest()
        if key in seen:
            old = seen[key]
            assert state == old['state']
            period = f.t-old['time']
            delivery = {k:f.delivered[k]-old['delivery'].get(k,0) for k in PRODUCTS}
            ore = [r.count-x for r,x in zip(f.ore_routes,old['ore'])]
            rejects = {r.index:f.refusals[r.index]-old['refusals'][r.index] for r in f.fast_shared}
            assert delivery[PRODUCTS[0]]*40 == 3*period
            assert delivery[PRODUCTS[1]]*160 == 11*period
            assert all(x*8 == period for x in ore)
            assert all(x == 0 for x in rejects.values())
            # A full direct tuple equality after one extra period, without a
            # hash lookup, verifies closure of both engines independently.
            before = f.full_state()
            b_before = (tuple(tuple(sorted(s.items())) for s in b.stock),tuple(b.out),
                        tuple(None if d is None else d-b.time for d in b.due),tuple(b.complete),
                        tuple(tuple(x) for x in b.cargo),tuple(b.cursor),
                        tuple(tuple(sorted(rs,key=lambda r:(b.last[r],b.rank[r]))) for rs in b.outgoing))
            for _ in range(period): one()
            b_after = (tuple(tuple(sorted(s.items())) for s in b.stock),tuple(b.out),
                       tuple(None if d is None else d-b.time for d in b.due),tuple(b.complete),
                       tuple(tuple(x) for x in b.cargo),tuple(b.cursor),
                       tuple(tuple(sorted(rs,key=lambda r:(b.last[r],b.rank[r]))) for rs in b.outgoing))
            assert f.full_state() == before and b_before == b_after
            result = dict(seed=seed,maxlen=maxlen,mode=mode,history=history,frequent=frequent,
                          steps_compared=checks,rebuilds=reorders,cycle_start=old['time'],period_steps=period,
                          delivery=delivery,ore_counts=ore,shared_route_count=len(rejects),shared_refusals=rejects,
                          reverse_block_checks=f.reverse_block_checks,receive_group_triggers=f.trigger_count,
                          invariant_violations=0,step_differences=0,closure_direct_equal=True,
                          topology={k:g[k] for k in ('bridges','double_axis_bridges','components','transport_slots','adjacent_bridge_pairs','maximum_bridge_run','different_F4_segmentation')})
            (HERE/f'cycle_{seed}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps(result,ensure_ascii=False),flush=True)
            return result
        seen[key] = dict(state=state,time=f.t,delivery=dict(f.delivered),ore=[r.count for r in f.ore_routes],refusals=f.refusals[:])
    raise RuntimeError('inconclusive: no cycle within the declared step limit')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--seed',type=int,default=107001)
    p.add_argument('--maxlen',type=int,default=5)
    p.add_argument('--mode',choices=['mixed','all_bridge','belt'],default='mixed')
    p.add_argument('--history',choices=['keep','clear','mixed'],default='keep')
    p.add_argument('--frequent',action='store_true')
    args = p.parse_args()
    run_case(args.seed,args.maxlen,args.mode,args.history,args.frequent)
