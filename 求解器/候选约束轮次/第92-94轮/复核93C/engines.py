"""Two independently encoded, deliberately restricted rule interpreters.

No import of sim2 or the derivation seat's programs.  All machines in these
fixtures consume one item and produce q items in 8 steps, with one correct
input species and a different output species.  Routes are disjoint directed
belts or chains of unrestricted admission gates.  This is not a general game
simulator: mergers, splitters, bridges and arbitrary recipes are excluded.

Engine A uses absolute event deadlines and per-route success timestamps.
Engine B uses a flat countdown array and rotating service queues.  Their
transition implementations do not call each other.
"""
from copy import deepcopy


class DeadlineEngine:
    def __init__(self, spec):
        self.t = 0
        self.cap = spec.get('cap', 50)
        self.nodes = deepcopy(spec['nodes'])
        self.routes = deepcopy(spec['routes'])
        self.order = spec.get('order', list(self.nodes))[:]
        self.sink_limit = spec.get('sink_limit', None)
        self.sent = []
        self.received = []
        self.starts = {n: [] for n in self.nodes}
        self.sink_count = 0
        self.in_cursor = {n: 0 for n in self.nodes}
        for n, a in self.nodes.items():
            work = a.pop('work')
            a['due'] = work-1 if work > 0 else None
            a['held'] = work == 0
        for i,r in enumerate(self.routes):
            r['cells'] = [None if x < 0 else x-1 for x in r['cells']]
            r['last'] = None
            r['rank'] = r.get('rank',i)
        self.outgoing = {n: [i for i,r in enumerate(self.routes) if r['src']==n]
                         for n in self.nodes}
        self.incoming = {n: [i for i,r in enumerate(self.routes) if r['dst']==n]
                         for n in self.nodes}

    def flush(self, n):
        a = self.nodes[n]
        if a['held'] and a['out']+a['q'] <= self.cap:
            a['out'] += a['q']
            a['held'] = False

    def relax(self, r):
        if r.get('mode', 'belt') != 'belt':
            return
        c = r['cells']
        for j in range(len(c)-2, -1, -1):
            if c[j] is not None and c[j] <= self.t and c[j+1] is None:
                c[j], c[j+1] = None, self.t+8

    def step(self, sink_budget=None):
        sent_begin, received_begin = len(self.sent), len(self.received)
        self.step_min_output = {n:a['out'] for n,a in self.nodes.items()}
        # Completion and eager moves internal to a continuous belt.
        for n,a in self.nodes.items():
            if a['due'] is not None and a['due'] <= self.t:
                a['due'], a['held'] = None, True
            self.flush(n)
        for r in self.routes:
            self.relax(r)
        budget = self.sink_limit if sink_budget is None else sink_budget
        used = 0
        # Each terminal component is layer 1. The destination receives its
        # non-splitter component upstreams together, in cyclic input order.
        groups = list(self.nodes) + [None]
        for dst in groups:
            incoming = ([i for i,r in enumerate(self.routes) if r['dst'] is None]
                        if dst is None else self.incoming[dst])
            if not incoming:
                continue
            p = 0 if dst is None else self.in_cursor[dst]
            candidates = incoming[p:] + incoming[:p]
            for i in candidates:
                r = self.routes[i]
                z = r['cells'][-1]
                can = (budget is None or used < budget) if dst is None else self.nodes[dst]['in'] < self.cap
                if z is not None and z <= self.t and can:
                    r['cells'][-1] = None
                    if dst is None:
                        used += 1
                        self.sink_count += 1
                    else:
                        self.nodes[dst]['in'] += 1
                        self.in_cursor[dst] = (incoming.index(i)+1) % len(incoming)
                    self.received.append((self.t, i))
                    self.relax(r)
        # Gates have their own judgements, in downstream-to-upstream layers.
        for depth in range(1, max(map(lambda r:len(r['cells']), self.routes), default=0)):
            for r in self.routes:
                if r.get('mode', 'belt') != 'gates':
                    continue
                c = r['cells']
                j = len(c)-1-depth
                if j >= 0 and c[j] is not None and c[j] <= self.t and c[j+1] is None:
                    c[j], c[j+1] = None, self.t+8
        for n in self.order:
            if n not in self.nodes:
                continue
            a = self.nodes[n]
            if not a['out']:
                continue
            candidates = sorted(self.outgoing[n], key=lambda i:
                                (-10**9 if self.routes[i]['last'] is None else self.routes[i]['last'], self.routes[i]['rank']))
            for i in candidates:
                r = self.routes[i]
                if r['cells'][0] is None:
                    a['out'] -= 1
                    self.step_min_output[n] = min(self.step_min_output[n],a['out'])
                    r['cells'][0] = self.t+8
                    r['last'] = self.t
                    self.sent.append((self.t,n,i))
                    self.flush(n)
                    break
        for n,a in self.nodes.items():
            if a['due'] is None and not a['held'] and a['in'] > 0:
                a['in'] -= 1
                a['due'] = self.t+8
                self.starts[n].append(self.t)
        self.t += 1
        self.recent_sent = self.sent[sent_begin:]
        self.recent_received = self.received[received_begin:]

    def state(self):
        end = self.t-1
        return {
            'nodes': {n:(a['in'], a['out'], 0 if a['held'] else -1 if a['due'] is None else a['due']-end)
                      for n,a in self.nodes.items()},
            'routes': [tuple(-1 if z is None else max(0,z-end) for z in r['cells']) for r in self.routes],
            'out_orders': {n:tuple(sorted(o,key=lambda i:(-10**9 if self.routes[i]['last'] is None else self.routes[i]['last'],self.routes[i]['rank'])))
                           for n,o in self.outgoing.items()},
            'in_cursors': self.in_cursor.copy(),
            'sink': self.sink_count,
        }


class CountdownEngine:
    def __init__(self, spec):
        self.time = 0
        self.capacity = spec.get('cap', 50)
        self.names = list(spec['nodes'])
        ix = {n:i for i,n in enumerate(self.names)}
        self.inputs = [spec['nodes'][n]['in'] for n in self.names]
        self.outputs = [spec['nodes'][n]['out'] for n in self.names]
        self.work = [spec['nodes'][n]['work'] for n in self.names]
        self.quantities = [spec['nodes'][n]['q'] for n in self.names]
        self.drain = spec.get('sink_limit', None)
        self.flat = []
        self.paths = []
        self.from_node, self.to_node, self.belts = [], [], []
        for r in spec['routes']:
            p = list(range(len(self.flat),len(self.flat)+len(r['cells'])))
            self.paths.append(p)
            self.flat.extend(r['cells'])
            self.from_node.append(ix[r['src']])
            self.to_node.append(-1 if r['dst'] is None else ix[r['dst']])
            self.belts.append(r.get('mode','belt') == 'belt')
        self.service = [[j for j,x in enumerate(self.from_node) if x == i] for i in range(len(self.names))]
        ranks = [r.get('rank',j) for j,r in enumerate(spec['routes'])]
        for queue in self.service:
            queue.sort(key=lambda j:ranks[j])
        self.in_paths = [[j for j,x in enumerate(self.to_node) if x == i] for i in range(len(self.names))]
        self.pointer = [0] * len(self.names)
        self.sequence = [ix[n] for n in spec.get('order',self.names) if n in ix]
        self.batches = [[] for _ in self.names]
        self.dispatches, self.arrivals = [], []
        self.drained = 0

    def unload(self, v):
        if self.work[v] == 0 and self.outputs[v] <= self.capacity-self.quantities[v]:
            self.outputs[v] += self.quantities[v]
            self.work[v] = -1

    def compact(self, path):
        for a,b in reversed(list(zip(path[:-1],path[1:]))):
            if self.flat[a] == 0 and self.flat[b] == -1:
                self.flat[a] = -1
                self.flat[b] = 8

    def step(self, sink_budget=None):
        self.minimum_during_step = list(self.outputs)
        self.flat = [max(0,x-1) if x >= 0 else -1 for x in self.flat]
        for v in range(len(self.names)):
            if self.work[v] > 0:
                self.work[v] -= 1
            self.unload(v)
        for p,belt in zip(self.paths,self.belts):
            if belt:
                self.compact(p)
        left = self.drain if sink_budget is None else sink_budget
        for v in range(len(self.names)+1):
            incoming = self.in_paths[v] if v<len(self.names) else [j for j,x in enumerate(self.to_node) if x == -1]
            begin = self.pointer[v] if v<len(self.names) else 0
            for offset in range(len(incoming)):
                position = (begin+offset)%len(incoming)
                j = incoming[position]
                endcell = self.paths[j][-1]
                ok = (left is None or left>0) if v == len(self.names) else self.inputs[v] != self.capacity
                if ok and self.flat[endcell] == 0:
                    self.flat[endcell] = -1
                    if v == len(self.names):
                        self.drained += 1
                        if left is not None:
                            left -= 1
                    else:
                        self.inputs[v] += 1
                        self.pointer[v] = (position+1)%len(incoming)
                    self.arrivals.append((self.time,j))
                    if self.belts[j]:
                        self.compact(self.paths[j])
        # Each route is disjoint; processing its remaining gates in reverse
        # order commutes with gates on other routes, including unequal layers.
        for p,belt in zip(self.paths,self.belts):
            if not belt:
                self.compact(p)
        for v in self.sequence:
            if self.outputs[v] <= 0:
                continue
            for pos,j in enumerate(self.service[v]):
                first = self.paths[j][0]
                if self.flat[first] == -1:
                    self.outputs[v] -= 1
                    self.minimum_during_step[v] = min(self.minimum_during_step[v],self.outputs[v])
                    self.flat[first] = 8
                    self.service[v].append(self.service[v].pop(pos))
                    self.dispatches.append((self.time,self.names[v],j))
                    self.unload(v)
                    break
        for v in range(len(self.names)):
            if self.work[v] == -1 and self.inputs[v]>0:
                self.inputs[v] -= 1
                self.work[v] = 8
                self.batches[v].append(self.time)
        self.time += 1

    def state(self):
        return {'nodes':{n:(self.inputs[i],self.outputs[i],self.work[i]) for i,n in enumerate(self.names)},
                'routes':[tuple(self.flat[x] for x in p) for p in self.paths],
                'out_orders':{n:tuple(self.service[i]) for i,n in enumerate(self.names)},
                'in_cursors':{n:self.pointer[i] for i,n in enumerate(self.names)},
                'sink':self.drained}


def plant_spec(lengths=(1,1,1,1), k=2, nodes=None, mode='belt'):
    if nodes is None:
        nodes = {n:dict(q=q, **{'in':0,'out':0,'work':-1}) for n,q in [('C',2),('A',1),('B',1),('K',k)]}
    links = [('C','A'),('C','B'),('A','C'),('B','K')]
    routes = [dict(src=a,dst=b,cells=[-1]*lengths[i],mode=mode) for i,(a,b) in enumerate(links)]
    routes += [dict(src='K',dst=None,cells=[-1],mode=mode) for _ in range(k)]
    return dict(nodes=nodes, routes=routes)


def twice_phi(state):
    n = state['nodes']
    count = sum(x>=0 for i in [0,2] for x in state['routes'][i])
    count += n['A'][0]+n['A'][1]+n['C'][0]+(n['A'][2]>=0)+(n['C'][2]>=0)
    return 2*count+n['C'][1]


def independent_weight(state):
    # Count with half units through an inventory table, rather than the
    # doubled linear form used in twice_phi.
    table = [sum(z != -1 for z in state['routes'][0]), state['nodes']['A'][0],
             int(state['nodes']['A'][2] != -1), state['nodes']['A'][1],
             sum(z != -1 for z in state['routes'][2]), state['nodes']['C'][0],
             int(state['nodes']['C'][2] != -1), state['nodes']['C'][1]/2]
    return sum(table)
