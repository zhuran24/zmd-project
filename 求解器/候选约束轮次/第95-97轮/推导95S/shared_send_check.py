#!/usr/bin/env python3
"""Two encodings of an always-stocked shared sender and disjoint forward paths.

The sink calendars are service models for testing a lemma, not game units or
counterexamples to the 221-machine plant. All output is local to this folder.
"""
import hashlib
import itertools
import json
import random
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent


class ArrayEngine:
    def __init__(self, initial, order):
        self.cells = [[None if a is None else -a for a in row] for row in initial]
        self.last = [-1] * len(initial)
        self.rank = list(order)
        self.sent = [[] for _ in initial]
        self.delivered = [[] for _ in initial]
        self.time = 0

    def step(self, accepts):
        now = self.time
        for i, row in enumerate(self.cells):
            if accepts[i] and row[-1] is not None and now - row[-1] >= 8:
                row[-1] = None
                self.delivered[i].append(now)
            for j in range(len(row) - 2, -1, -1):
                if row[j] is not None and now - row[j] >= 8 and row[j + 1] is None:
                    row[j + 1], row[j] = now, None
        eligible = [i for i, row in enumerate(self.cells) if row[0] is None]
        served = None
        if eligible:
            served = min(eligible, key=lambda i: (self.last[i], self.rank[i]))
            self.cells[served][0] = now
            self.last[served] = now
            self.sent[served].append(now)
        self.time += 1
        return served


class Token:
    def __init__(self, age):
        self.age = age


class ObjectEngine:
    def __init__(self, initial, order):
        self.paths = [[None if a is None else Token(a) for a in row] for row in initial]
        # Ordered oldest-success queue is independent of absolute timestamps.
        self.queue = sorted(range(len(order)), key=lambda j: order[j])
        self.sent = [[] for _ in initial]
        self.delivered = [[] for _ in initial]
        self.time = 0

    def step(self, accepts):
        for i, row in enumerate(self.paths):
            if row[-1] is not None and row[-1].age >= 8 and accepts[i]:
                row[-1] = None
                self.delivered[i].append(self.time)
            j = len(row) - 2
            while j >= 0:
                cargo = row[j]
                if cargo is not None and cargo.age >= 8 and row[j + 1] is None:
                    row[j + 1] = cargo
                    cargo.age = 0
                    row[j] = None
                j -= 1
        selected = next((j for j in self.queue if self.paths[j][0] is None), None)
        if selected is not None:
            self.paths[selected][0] = Token(0)
            self.queue.remove(selected)
            self.queue.append(selected)
            self.sent[selected].append(self.time)
        for row in self.paths:
            for cargo in row:
                if cargo is not None:
                    cargo.age = min(8, cargo.age + 1)
        self.time += 1
        return selected


def compare(a, b):
    assert a.sent == b.sent and a.delivered == b.delivered
    assert a.time == b.time
    ages_a = [[None if x is None else min(8, a.time - x) for x in row] for row in a.cells]
    ages_b = [[None if x is None else x.age for x in row] for row in b.paths]
    assert ages_a == ages_b


def probe(initial, order, steps, calendar=None, keep=False, resets=None):
    a, b = ArrayEngine(initial, order), ObjectEngine(initial, order)
    trace = []
    for now in range(steps):
        if resets and now in resets:
            rank = resets[now]
            a.last = [-1] * len(initial)
            a.rank = list(rank)
            b.queue = sorted(range(len(initial)), key=lambda j: rank[j])
        accepts = [True] * len(initial) if calendar is None else calendar(now)
        chosen_a, chosen_b = a.step(accepts), b.step(accepts)
        assert chosen_a == chosen_b
        compare(a, b)
        if keep:
            trace.append(dict(step=now, accepts=accepts, served=chosen_a,
                              head_ages=[None if row[0] is None else min(8, a.time - row[0]) for row in a.cells]))
    if calendar is None:
        for sequence in a.sent:
            tail = [x for x in sequence if x >= 16]
            assert len(tail) >= (steps - 24) // 8
            assert all(v - u == 8 for u, v in zip(tail, tail[1:])), sequence
        for row, sequence in zip(initial, a.delivered):
            tail = [x for x in sequence if x >= 16 + 8 * len(row)]
            assert all(v - u == 8 for u, v in zip(tail, tail[1:])), sequence
    return a, trace


def main():
    count = 0
    compared = 0
    maximum_last_non8 = -1
    summaries = []
    for n in (1, 2, 3):
        cases = 0
        # Empty plus residence ages 0..8, independently per first cell.
        for ages in itertools.product([None] + list(range(9)), repeat=n):
            for order in itertools.permutations(range(n)):
                a, _ = probe([[x] for x in ages], order, 64)
                for seq in a.sent:
                    maximum_last_non8 = max([maximum_last_non8] + [v for u, v in zip(seq, seq[1:]) if v - u != 8])
                cases += 1
                compared += 64
        summaries.append(dict(outlets=n, cases=cases, method='all one-cell states and initial orders'))
        count += cases
    # Every initial order of the six core outlets in a mature full-path case.
    for order in itertools.permutations(range(6)):
        probe([[8]] * 6, order, 96)
        count += 1
        compared += 96
    summaries.append(dict(outlets=6, cases=720, method='all orders of six simultaneously vacated heads'))
    rng = random.Random(95095)
    reset_count = 0
    for i in range(600):
        n = 1 + i % 6
        lengths = [rng.randint(1, 16) for _ in range(n)]
        initial = [[None if rng.randrange(4) == 0 else rng.randrange(9) for _ in range(length)] for length in lengths]
        order = list(range(n))
        rng.shuffle(order)
        resets = {}
        for t in range(256):
            if rng.randrange(4) == 0:
                rank = list(range(n))
                rng.shuffle(rank)
                resets[t] = rank
        reset_count += len(resets)
        probe(initial, order, 256, resets=resets)
        count += 1
        compared += 256
    summaries.append(dict(outlets='1..6', cases=600, method='seeded arbitrary occupancy, ages and path lengths 1..16'))

    negative = []
    for n in (2, 3, 6):
        # Target outlet 0 is always accepted. Other tails accept together once
        # per (8+n-1) steps. Their early success order leaves target last.
        period = 8 + n - 1
        initial = [[0] for _ in range(n)]
        initial[0] = [None]
        def calendar(t, p=period, m=n):
            return [True] + [(t - 8) % p == 0] * (m - 1)
        order = [n - 1] + list(range(n - 1))
        a, trace = probe(initial, order, period * 100 + 16, calendar, keep=True)
        seq = a.sent[0]
        suffix = [t for t in seq if t >= period * 20]
        assert all(v - u == period for u, v in zip(suffix, suffix[1:])), (n, suffix)
        # Independent numeric rate is total tail deliveries in a period-aligned
        # window, not the sender gap used in the previous assertion.
        start = period * 20 + 16
        end = start + period * 60
        count_delivered = sum(start <= t < end for t in a.delivered[0])
        rate_from_window = Fraction(count_delivered * 8, end - start)
        rate_from_gap = Fraction(8, period)
        assert rate_from_window == rate_from_gap
        negative.append(dict(outlets=n, service_period_steps=period,
                             target_rate=str(rate_from_window), measured_deliveries=count_delivered,
                             window=[start, end], first_target_sends=seq[:12],
                             trace=trace[:4 * period]))
        compared += period * 100 + 16
    data = dict(status='passed', positive_cases=count, positive_groups=summaries,
                compared_steps=compared, history_resets=reset_count,
                last_non8_interval_end=maximum_last_non8,
                negative_controls=negative,
                boundary='External acceptance calendars test a service lemma; none is a factory counterexample.')
    (HERE / 'shared_send_results.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in data.items() if k != 'negative_controls'}, ensure_ascii=False))
    print(json.dumps([dict(outlets=x['outlets'], target_rate=x['target_rate']) for x in negative], ensure_ascii=False))


if __name__ == '__main__':
    main()
