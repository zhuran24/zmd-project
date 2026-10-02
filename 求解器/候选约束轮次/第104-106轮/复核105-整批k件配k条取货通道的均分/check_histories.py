#!/usr/bin/env python3
"""Two independent step models of rule 32, record retention and clearing."""
from collections import deque
import itertools
import json
from pathlib import Path
import random


class Timestamps:
    """A: actual last-success times and head release times."""
    def __init__(self, k, stock, initial_order, never_count):
        self.k, self.stock = k, stock
        self.connection = list(initial_order)
        self.releases = [None] * k
        self.last = [None] * k
        for rank, head in enumerate(initial_order[never_count:]):
            self.last[head] = rank - k - 20

    def step(self, t, cmd):
        if cmd["offline"]:
            self.connection = list(cmd["connection"])
            if cmd["clear"]:
                self.last = [None] * self.k
        self.stock += cmd["add"]
        assert 0 <= self.stock <= 50
        for head in range(self.k):
            if self.releases[head] is not None and self.releases[head] <= t:
                self.releases[head] = None
        chosen = None
        if self.stock:
            for group in cmd["groups"]:
                def key(head):
                    v = self.last[head]
                    return ((0, self.connection.index(head)) if v is None
                            else (1, v))
                for head in sorted(group, key=key):
                    if self.releases[head] is None:
                        chosen = head
                        break
                if chosen is not None:
                    break
        if chosen is not None:
            self.stock -= 1
            self.releases[chosen] = t + 8
            self.last[chosen] = t
        return chosen

    def canonical(self, t):
        known = tuple(sorted((i for i in range(self.k) if self.last[i] is not None),
                             key=self.last.__getitem__))
        ages = tuple(0 if r is None else r - t for r in self.releases)
        return self.stock, ages, tuple(self.connection), known


class Queues:
    """B: resident item ages, and a queue of previously successful channels."""
    def __init__(self, k, stock, initial_order, never_count):
        self.k, self.stock = k, stock
        self.connection = list(initial_order)
        self.ages = [None] * k
        self.history = deque(initial_order[never_count:])

    def step(self, t, cmd):
        for i, age in enumerate(self.ages):
            if age is not None:
                self.ages[i] = age + 1
                if self.ages[i] == 8:
                    self.ages[i] = None
        if cmd["offline"]:
            self.connection = list(cmd["connection"])
            if cmd["clear"]:
                self.history.clear()
        for _ in range(cmd["add"]):
            self.stock += 1
        assert 0 <= self.stock <= 50
        route = None
        if self.stock:
            unknown = [j for j in self.connection if j not in self.history]
            scan = unknown + list(self.history)
            for group in cmd["groups"]:
                eligible = [j for j in scan if j in group and self.ages[j] is None]
                if eligible:
                    route = eligible[0]
                    break
        if route is not None:
            self.stock -= 1
            self.ages[route] = 0
            if route in self.history:
                self.history.remove(route)
            self.history.append(route)
        return route

    def canonical(self, t):
        return (self.stock, tuple(0 if age is None else 8 - age for age in self.ages),
                tuple(self.connection), tuple(self.history))


def prefix_span(word, k):
    """A: largest difference of two values of each prefix count difference."""
    counts, lower, upper = [0] * k, {}, {}
    pairs = list(itertools.combinations(range(k), 2))
    for pair in pairs:
        lower[pair] = upper[pair] = 0
    for route in word:
        counts[route] += 1
        for a, b in pairs:
            d = counts[a] - counts[b]
            lower[a, b] = min(lower[a, b], d)
            upper[a, b] = max(upper[a, b], d)
    return max((upper[p] - lower[p] for p in pairs), default=0)


def direct_intervals(word, k):
    """B: count every contiguous successful subword explicitly."""
    largest = 0
    for left in range(len(word)):
        counts = [0] * k
        for right in range(left, len(word)):
            counts[word[right]] += 1
            largest = max(largest, max(counts) - min(counts))
    return largest


def rotation(word, k):
    # Every subword of length <= k contains no repeated route.
    return all(len(set(word[start:start + k])) == len(word[start:start + k])
               for start in range(len(word)))


def trial(k, mode, rng, steps):
    stock = rng.randrange(51)
    order = list(range(k))
    rng.shuffle(order)
    never_count = rng.randrange(k + 1)
    a, b = Timestamps(k, stock, order, never_count), Queues(k, stock, order, never_count)
    word, segment, max_segment = [], [], 0
    groups = [list(range(k))]
    mismatches = 0
    for t in range(steps):
        offline = rng.random() < 0.28
        clear = offline and mode != "retained" and rng.random() < 0.6
        if offline:
            if mode != "merger_priorities":
                assert rotation(segment, k), (k, mode, segment)
                max_segment = max(max_segment, prefix_span(segment, k))
            segment = []
            rng.shuffle(order)
            if mode == "merger_priorities":
                # Each designated merger gets its own level; others share one.
                mergers = {j for j in range(k) if rng.random() < 0.5}
                groups = [[j] for j in sorted(mergers)]
                rest = [j for j in range(k) if j not in mergers]
                if rest:
                    groups.append(rest)
                rng.shuffle(groups)
        # More permissive than recipes: any number of complete batches per step.
        capacity = (50 - a.stock) // k
        add = k * rng.randrange(min(capacity, 3) + 1) if rng.random() < 0.18 else 0
        cmd = {"offline": offline, "clear": clear, "connection": order[:],
               "groups": [g[:] for g in groups], "add": add}
        ra, rb = a.step(t, cmd), b.step(t, cmd)
        assert ra == rb and a.canonical(t) == b.canonical(t), (k, mode, t, cmd)
        if ra is not None:
            word.append(ra)
            segment.append(ra)
    if mode != "merger_priorities":
        assert rotation(segment, k)
        max_segment = max(max_segment, prefix_span(segment, k))
    e_a, e_b = prefix_span(word, k), direct_intervals(word, k)
    assert e_a == e_b and e_a <= 2, (k, mode, word)
    if mode == "retained":
        assert rotation(word, k) and e_a <= 1
    return {"max_interval_difference": e_a,
            "max_no_offline_segment_difference": max_segment,
            "successful_items": len(word), "state_mismatches": mismatches}


def main():
    seed = 10520261002
    rng = random.Random(seed)
    rows = []
    repetitions, steps = 200, 192
    for mode in ("retained", "mixed_clearing", "merger_priorities"):
        for k in range(2, 7):
            results = [trial(k, mode, rng, steps) for _ in range(repetitions)]
            row = {"mode": mode, "k": k, "runs": repetitions, "steps_per_run": steps,
                   "max_interval_difference": max(r["max_interval_difference"] for r in results),
                   "max_no_offline_segment_difference": (
                       None if mode == "merger_priorities" else
                       max(r["max_no_offline_segment_difference"] for r in results)),
                   "successful_items": sum(r["successful_items"] for r in results),
                   "state_mismatches": sum(r["state_mismatches"] for r in results)}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    result = {"seed": seed, "rows": rows,
              "note": "Random trials supplement, and do not replace, the all-layout proof and finite graph enumeration."}
    Path(__file__).with_name("histories.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
