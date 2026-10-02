#!/usr/bin/env python3
"""Execute full-stock debugging using only stock/output additions and switches.
No insertion into any transport slot and no manual cache mutation after setup.
"""
import json
import random
from collections import Counter
from pathlib import Path
from bridge_factory import BridgeFactory, PRODUCTS
from engine_b import EngineB

HERE = Path(__file__).resolve().parent


class SwitchReference(EngineB):
    def step_with_switches(self, switches):
        now = self.time
        for i,recipe in enumerate(self.recipes):
            if recipe is None: continue
            if not switches[i] and self.due[i] is not None: self.due[i] += 1
            if switches[i] and self.due[i] is not None and self.due[i] <= now:
                self.due[i] = None; self.complete[i] = True; self.batches[i] += 1
            self.release_batch(i)
        for target,routes in enumerate(self.incoming):
            if not routes: continue
            start = 0 if self.cursor[target] is None else (routes.index(self.cursor[target])+1)%len(routes)
            for r in routes[start:]+routes[:start]:
                _,_,item = self.paths[r]
                if self.cargo[r][-1] != 8: continue
                accept = self.open if self.recipes[target] is None else self.stock[target].get(item,0)<50
                if accept:
                    if self.recipes[target] is None: self.shipped[item] += 1
                    else: self.stock[target][item] = self.stock[target].get(item,0)+1
                    self.cargo[r][-1] = None; self.cursor[target] = r; self.received[r] += 1
        for cells in self.cargo:
            for j in range(len(cells)-2,-1,-1):
                if cells[j] == 8 and cells[j+1] is None: cells[j] = None; cells[j+1] = 0
        for source,routes in enumerate(self.outgoing):
            if self.recipes[source] is not None and not self.out[source]: continue
            free = [r for r in routes if self.cargo[r][0] is None]
            if free:
                r = min(free,key=lambda r:(self.last[r],self.rank[r]))
                self.cargo[r][0] = 0; self.last[r] = now; self.sent[r] += 1
                if self.recipes[source] is not None:
                    self.out[source] -= 1; self.release_batch(source)
        for i,recipe in enumerate(self.recipes):
            if recipe is None or not switches[i] or self.due[i] is not None or self.complete[i]: continue
            ingredients,_,_,duration = recipe
            if all(self.stock[i].get(k,0)>=q for k,q in ingredients.items()):
                for k,q in ingredients.items(): self.stock[i][k] -= q
                self.due[i] = now+duration
        for cells in self.cargo:
            for j,age in enumerate(cells):
                if age is not None: cells[j] = min(8,age+1)
        self.time += 1


def run(seed,maxlen,mode):
    rng = random.Random(seed)
    f = BridgeFactory(seed,maxlen,mode)
    final = {u for u in f.ms if u.typ in ('封装机','灌装机')}
    # A clean, correctly typed but incomplete post-cleanup state. All transport
    # is emptied, so later previous-unit records must be created by transfers.
    for r in f.rs:
        r.cells = [None]*len(r.cells); f.prev[r.index] = [None]*len(r.cells)
    for u in f.ms:
        f.enabled[u] = False
        u.stock = Counter({k:rng.randrange(51) for k in u.recipe[0]})
        u.out = 0 if u in final else rng.randrange(51)
        state = 0 if u in final else rng.randrange(3)
        u.done = state == 1; u.remaining = rng.randrange(1,9) if state == 2 else 0
    b = SwitchReference(f)
    additions = Counter(); waits=[]; checked=0; reorders=0
    def step(n):
        nonlocal checked,reorders
        waits.append(n)
        for _ in range(n):
            if f.t%13==0:
                reset = (f.t//13)%2 == 0
                f.rebuild(reset=reset); b.copy_order(f,reset); reorders += 1
            switches=[f.enabled.get(u,False) for u in b.units]
            f.step(); b.step_with_switches(switches); b.compare(f)
            assert f.received == b.received
            for r in f.rs:
                for j,c in enumerate(r.cells):
                    if c is not None: assert f.prev[r.index][j] == f.upstream_unit(r.index,j)
            checked += 1
    def top_up():
        for u in f.ms:
            i=b.index[u]
            for item in u.recipe[0]:
                additions[item] += 50-u.stock[item]
                u.stock[item] = b.stock[i][item] = 50
            if u not in final:
                additions[u.recipe[1]] += 50-u.out
                u.out = b.out[i] = 50
    def all_roads_full():
        return all(all(c is not None for c in r.cells) for r in f.rs if r.target is not f.sink)
    rounds=0; filling_rounds=0
    while True:
        rounds += 1
        assert rounds < 100
        for u in f.ms: f.enabled[u]=False
        top_up()
        while not all_roads_full():
            step(rng.randrange(9,8*maxlen+40))
            top_up(); filling_rounds+=1
            assert filling_rounds < 1000
        top_up()
        if all(u.done for u in f.ms if u not in final): break
        for u in f.ms: f.enabled[u] = u not in final
        step(rng.randrange(16,70))
    step(rng.randrange(16,50))
    for u in f.ms:
        assert all(u.stock[k] == 50 for k in u.recipe[0])
        assert (u.out,u.done,u.remaining) == ((0,False,0) if u in final else (50,True,0))
    for r in f.rs:
        assert all(c is None for c in r.cells) if r.target is f.sink else all(c is not None and f.t-c>=8 for c in r.cells)
    prepared_at=f.t
    quota=json.loads((HERE/'startup_budget.json').read_text())['feedstock_quota_by_item']
    assert all(v<=quota[k] for k,v in additions.items())
    for u in f.ms: f.enabled[u]=True
    # The certificate here is preparation plus continued exact paired steps;
    # the autonomous cycle certificates are in bridge_factory.py outputs.
    for _ in range(2000):
        f.step(); b.step_with_switches([True]*len(b.units)); b.compare(f); f.audit(); checked+=1
    return dict(seed=seed,maxlen=maxlen,mode=mode,preparation_rounds=rounds,filling_rounds=filling_rounds,
                prepared_at=prepared_at,steps_compared=checked,rebuilds=reorders,
                manual_transport_insertions=0,manual_cache_changes_after_initialization=0,
                prepared_state_verified=True,provenance_verified=True,kit_bound_pass=True,
                additions=dict(additions),waits_in_steps=waits)


if __name__=='__main__':
    results=[run(107101,4,'mixed'),run(107102,12,'all_bridge'),run(107103,24,'mixed')]
    (HERE/'startup_bridge_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(results,ensure_ascii=False))
