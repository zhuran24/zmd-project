"""Dual checks of X after its dedicated input chains have become full.

Each input terminal refills in the same step when it sends; this is the chain
lemma's consequent, not an assumption about an uncertified whole factory.
"""
import itertools
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent


class AbsoluteX:
    def __init__(self, p):
        self.p = p
        self.stock = p['initial_stock'][:]
        self.output = p['initial_output']
        self.batch = None if p['initial_batch'] is None else -1+p['initial_batch']
        self.inputs = [-1+r for r in p['input_waits']]
        self.heads = [None if r is None else -1-r for r in p['head_ages']]
        self.last = [-100+j for j in range(p['n'])]

    def release(self, t):
        if self.batch is not None and self.batch <= t and self.output+self.p['q'] <= 50:
            self.output += self.p['q']
            self.batch = None

    def step(self, t, ordered, accept):
        self.release(t)
        for i in ordered:
            kind = self.p['kinds'][i]
            if self.inputs[i] <= t and self.stock[kind] < 50:
                self.stock[kind] += 1
                self.inputs[i] = t+8
        cleared = []
        for j, entered in enumerate(self.heads):
            if entered is not None and t-entered >= 8 and accept[j]:
                self.heads[j] = None
                cleared.append(j)
        for j in sorted(range(self.p['n']), key=lambda j: self.last[j]):
            if self.output and self.heads[j] is None:
                self.output -= 1
                self.heads[j] = t
                self.last[j] = t
                self.release(t)
                break
        if self.batch is None and all(s >= c for s, c in zip(self.stock, self.p['cost'])):
            self.stock = [s-c for s, c in zip(self.stock, self.p['cost'])]
            self.batch = t+self.p['duration']
        return cleared

    def state(self, t):
        return (tuple(self.stock), self.output,
                None if self.batch is None else max(0, self.batch-t),
                tuple(max(0, v-t) for v in self.inputs),
                tuple(None if v is None else min(8, t-v) for v in self.heads),
                tuple(sorted(range(self.p['n']), key=lambda j: self.last[j])))


class CountdownX:
    def __init__(self, p):
        self.p = p
        self.inventories = p['initial_stock'][:]+[p['initial_output']]
        self.progress = -1 if p['initial_batch'] is None else p['initial_batch']
        self.timers = p['input_waits'][:]
        self.outlets = [-1 if age is None else 8-age for age in p['head_ages']]
        self.priority = list(range(p['n']))

    def unpack(self):
        if self.progress == 0 and self.inventories[-1] <= 50-self.p['q']:
            self.progress = -1
            self.inventories[-1] += self.p['q']

    def step(self, t, ordered, accept):
        if self.progress > 0:
            self.progress -= 1
        self.unpack()
        self.timers = [max(0, v-1) for v in self.timers]
        for port in ordered:
            slot = self.p['kinds'][port]
            if self.timers[port] == 0 and self.inventories[slot] != 50:
                self.inventories[slot] += 1
                self.timers[port] = 8
        cleared = []
        for j in range(len(self.outlets)):
            if self.outlets[j] > 0:
                self.outlets[j] -= 1
            if self.outlets[j] == 0 and accept[j]:
                self.outlets[j] = -1
                cleared.append(j)
        selected = next((j for j in self.priority if self.outlets[j] == -1), None)
        if self.inventories[-1] > 0 and selected is not None:
            self.inventories[-1] -= 1
            self.outlets[selected] = 8
            self.priority.remove(selected)
            self.priority.append(selected)
            self.unpack()
        if self.progress < 0:
            enough = all(self.inventories[j] >= required for j, required in enumerate(self.p['cost']))
            if enough:
                for j, required in enumerate(self.p['cost']):
                    self.inventories[j] -= required
                self.progress = self.p['duration']
        return cleared

    def state(self, t):
        return (tuple(self.inventories[:-1]), self.inventories[-1],
                None if self.progress < 0 else self.progress,
                tuple(self.timers), tuple(None if v < 0 else 8-v for v in self.outlets),
                tuple(self.priority))


def inspect_case(p, limit=150000):
    a, b = AbsoluteX(p), CountdownX(p)
    seen, empty_cache, failed_refill = {}, [], []
    for t in range(limit):
        # Every type has its own slot. Vary the receiving order, including ties.
        ordered = list(range(len(p['kinds'])))
        shift = t % len(ordered)
        ordered = ordered[shift:]+ordered[:shift]
        accept = [((t+j*3) % p['period'] < p['open_steps']) for j in range(p['n'])]
        ca, cb = a.step(t, ordered, accept), b.step(t, ordered, accept)
        assert ca == cb and a.state(t) == b.state(t), (p, t, a.state(t), b.state(t))
        empty_cache.append(a.batch is None)
        failed_refill.append(bool(p['n'] == 1 and p['duration'] == 8 and ca and a.heads[0] is None))
        state = (a.state(t), t % p['period'], t % len(ordered))
        if state in seen:
            s = seen[state]
            return dict(first=s, second=t, compared_steps=t+1,
                        empty_cache_in_cycle=sum(empty_cache[s+1:t+1]),
                        refill_failures_in_cycle=sum(failed_refill[s+1:t+1]))
        seen[state] = t
    raise AssertionError(('cycle not found in test budget', p))


def run():
    rng = random.Random(962)
    recipes = [(8, [1], 1), (8, [1], 2), (8, [1], 3), (8, [2], 1),
               (8, [2, 1], 1), (40, [10, 15], 1), (40, [10, 10], 1)]
    count, comparisons, max_first = 0, 0, 0
    for duration, cost, q in recipes:
        for run in range(80):
            c = [(x*8+duration-1)//duration for x in cost]
            for j in range(len(c)):
                if sum(c) < 6 and rng.random() < .5:
                    c[j] += 1
            kinds = [i for i, amount in enumerate(c) for _ in range(amount)]
            n = rng.randrange(4)
            period = rng.choice([8, 17, 40, 97])
            p = dict(duration=duration, cost=cost, q=q, n=n, kinds=kinds,
                     initial_stock=[rng.randrange(51) for _ in cost], initial_output=rng.randrange(51),
                     initial_batch=rng.choice([None, 0, 1, duration]),
                     input_waits=[rng.randrange(9) for _ in kinds],
                     head_ages=[rng.choice([None, 0, 1, 8]) for _ in range(n)],
                     period=period, open_steps=rng.choice([0, 1, period//2, period]))
            result = inspect_case(p)
            assert result['empty_cache_in_cycle'] == result['refill_failures_in_cycle'] == 0, (p, result)
            count += 1
            comparisons += result['compared_steps']
            max_first = max(max_first, result['first'])
    # With 2 required per batch but only one route, d*c<a. This negative control
    # must actually display empty caches in a recurrent state.
    p = dict(duration=8, cost=[2], q=1, n=1, kinds=[0], initial_stock=[0],
             initial_output=0, initial_batch=None, input_waits=[0], head_ages=[None],
             period=8, open_steps=8)
    negative = inspect_case(p)
    assert negative['empty_cache_in_cycle'] > 0
    output = dict(scope='X after input chains are full; same-step terminal refill proved separately',
                  cases=count, compared_steps=comparisons, largest_first_repeated_state=max_first,
                  violations=0, insufficient_input_negative_control=negative)
    (HERE/'dedicated_results.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
