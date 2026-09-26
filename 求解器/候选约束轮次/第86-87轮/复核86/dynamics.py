"""Independent pure-line event model for review 86 (integer sub-ticks).
q sub-ticks = one tick. No imports of historical review code.
Simulation is corroboration, not a proof over arbitrary real phases.
"""
from collections import Counter
import random


class Net:
    def __init__(self, q=1, capacity=50):
        self.q, self.capacity, self.t = q, capacity, 0
        self.m = {}
        self.lines = []
        self.order = None
        self.delivered = Counter()
        self.starts = Counter()
        self.shipped = Counter()
        self.sink_open = lambda name, t: True

    def machine(self, name, inputs, product, batch=1, duration=1):
        self.m[name] = dict(inputs=inputs, product=product, batch=batch,
                            duration=duration*self.q, stock={i:0 for i in inputs},
                            output=0, cache=None, ports=[], pointer=0)

    def link(self, source, target, item, length=1, quota=None):
        assert length >= 1
        idx = len(self.lines)
        self.lines.append(dict(source=source,target=target,item=item,
                               cells=[None]*length,quota=quota,window=None,used=0))
        if source in self.m:
            self.m[source]['ports'].append(idx)
        return idx

    def admit(self, line):
        if line['cells'][0] is not None:
            return False
        return (line['quota'] is None or line['window'] is None or
                self.t-line['window'] >= 5*self.q or line['used'] < line['quota'])

    def receive_first(self, idx):
        line = self.lines[idx]
        line['cells'][0] = self.t+self.q
        if line['quota'] is not None:
            if line['window'] is None or self.t-line['window'] >= 5*self.q:
                line['window'], line['used'] = self.t, 0
            line['used'] += 1
        self.shipped[idx] += 1

    def act(self, action):
        kind, idx = action
        if kind == 'machine':
            m = self.m[idx]
            changed = False
            if m['cache'] is not None and m['cache'] <= self.t and m['output']+m['batch'] <= self.capacity:
                m['output'] += m['batch']
                m['cache'] = None
                changed = True
            if m['cache'] is None and all(m['stock'][i] >= n for i,n in m['inputs'].items()):
                for i,n in m['inputs'].items():
                    m['stock'][i] -= n
                m['cache'] = self.t+m['duration']
                self.starts[idx] += 1
                changed = True
            return changed
        if kind == 'output':
            m = self.m[idx]
            if not m['ports']:
                return False
            changed = False
            for _ in range(len(m['ports'])):
                p = m['ports'][m['pointer']]
                m['pointer'] = (m['pointer']+1)%len(m['ports'])
                if m['output'] and self.admit(self.lines[p]):
                    m['output'] -= 1
                    self.receive_first(p)
                    changed = True
            return changed
        line = self.lines[idx]
        if kind == 'supply':
            if self.admit(line):
                self.receive_first(idx)
                return True
            return False
        if kind == 'line':
            cells = line['cells']
            changed = False
            if cells[-1] is not None and cells[-1] <= self.t:
                dest = line['target']
                ok = False
                if dest in self.m:
                    inv = self.m[dest]['stock']
                    if inv[line['item']] < self.capacity:
                        inv[line['item']] += 1
                        ok = True
                elif self.sink_open(dest, self.t):
                    self.delivered[line['item']] += 1
                    ok = True
                if ok:
                    cells[-1] = None
                    changed = True
            for j in range(len(cells)-2, -1, -1):
                if cells[j] is not None and cells[j] <= self.t and cells[j+1] is None:
                    cells[j] = None
                    cells[j+1] = self.t+self.q
                    changed = True
            return changed
        raise ValueError(action)

    def actions(self):
        out = [(kind,k) for k in self.m for kind in ('machine','output')]
        for i,line in enumerate(self.lines):
            out.append(('line',i))
            if line['source'] not in self.m:
                out.append(('supply',i))
        return out

    def close(self, rng=None):
        if self.order is None:
            self.order = self.actions()
        if rng is not None:
            rng.shuffle(self.order)
        rounds = 0
        while True:
            changed = False
            for action in self.order:
                changed |= self.act(action)
            rounds += 1
            if not changed:
                break
            assert rounds < 10000

    def key(self, external_period=1):
        machines = tuple((tuple(m['stock'].values()),m['output'],
                          -1 if m['cache'] is None else max(0,m['cache']-self.t),m['pointer'])
                         for m in self.m.values())
        lines = tuple((tuple(-1 if c is None else max(0,c-self.t) for c in line['cells']),
                       0 if line['window'] is None or self.t-line['window'] >= 5*self.q else 5*self.q-(self.t-line['window']),
                       0 if line['window'] is None or self.t-line['window'] >= 5*self.q else line['used'])
                      for line in self.lines)
        return self.t%external_period,machines,lines


def plant(q=1, lengths=(1,1,1,1), k=2, capacity=50):
    n = Net(q,capacity)
    n.machine('C', {'plant':1}, 'seed', 2)
    n.machine('A', {'seed':1}, 'plant')
    n.machine('B', {'seed':1}, 'plant')
    n.machine('K', {'plant':1}, 'powder', k)
    for source,target,item,length in zip(['C','A','C','B'],['A','C','B','K'],
                                       ['seed','plant','seed','plant'],lengths):
        n.link(source,target,item,length)
    for i in range(k):
        n.link('K','sink'+str(i),'powder',1)
    return n


def phi2(n):
    a,c = n.m['A'],n.m['C']
    return 2*(sum(x is not None for j in (0,1) for x in n.lines[j]['cells'])+
              a['stock']['seed']+(a['cache'] is not None)+a['output']+
              c['stock']['plant']+(c['cache'] is not None))+c['output']


def randomize(n, rng, mode):
    for m in n.m.values():
        for i in m['stock']:
            m['stock'][i] = rng.randrange(n.capacity+1) if mode == 'dense' else rng.randrange(4)
        m['output'] = rng.randrange(n.capacity+1) if mode == 'dense' else rng.randrange(4)
        m['cache'] = None if rng.random()<0.4 else rng.randrange(m['duration']+1)
    for line in n.lines:
        for j in range(len(line['cells'])):
            line['cells'][j] = rng.randrange(n.q+1) if rng.random()<0.6 else None
    n.close(rng)
