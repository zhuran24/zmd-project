"""Two independently represented step models of the outlet interface.

This is a local interface check, not a certificate for a 70 x 70 factory.
Batch tests allow more arrival schedules than actual recipes. They check the
stronger scheduling lemma used in the report. No external module is imported.
"""
from pathlib import Path
from fractions import Fraction
from math import gcd, lcm
import hashlib
import itertools
import json
import random

OUT = Path(__file__).resolve().parent


def timestamps(c):
    k = c["k"]
    stock = c.get("stock", 0)
    physical = [None] * k
    history = list(c.get("history", [None] * k))
    order = list(range(k))
    pointer = c.get("pointer")
    trace = []
    sent = []
    for t in range(c["steps"]):
        if t in c["offline"]:
            order = c["offline"][t][:]
            if c["mode"] == "clear":
                history = [None] * k
                pointer = None
        for j in range(k):
            if physical[j] is not None and t >= physical[j] + 8 and not c["late"][j]:
                physical[j] = None
        added = c["arrivals"].get(t, 0)
        if not c.get("arrive_late", False) and stock + added <= 50:
            stock += added
        if c["kind"] == "machine":
            candidates = sorted(range(k), key=lambda j: (
                history[j] is not None,
                history[j] if history[j] is not None else order.index(j)))
        else:
            first = (order.index(pointer) + 1) % k if pointer is not None else 1 % k
            candidates = order[first:] + order[:first]
        selected = None
        if stock:
            for j in candidates:
                if physical[j] is None:
                    selected = j
                    stock -= 1
                    physical[j] = t
                    history[j] = t
                    pointer = j
                    sent.append((t, j))
                    break
        for j in range(k):
            if physical[j] is not None and t >= physical[j] + 8:
                physical[j] = None
        if c.get("arrive_late", False) and stock + added <= 50:
            stock += added
        if c["kind"] == "machine":
            recency = sorted(range(k), key=lambda j: (
                history[j] is not None,
                history[j] if history[j] is not None else order.index(j)))
        else:
            first = (order.index(pointer) + 1) % k if pointer is not None else 1 % k
            recency = order[first:] + order[:first]
        trace.append([t, stock, [None if p is None else 8-(t-p) for p in physical],
                      recency, selected])
    return trace, sent


def counters(c):
    count = c.get("stock", 0)
    timers = [-1] * c["k"]
    fresh = {j for j, h in enumerate(c.get("history", [None] * c["k"])) if h is None}
    queue = sorted((j for j in range(c["k"]) if j not in fresh),
                   key=lambda j: c["history"][j])
    connections = list(range(c["k"]))
    last_port = c.get("pointer")
    snapshots, successes = [], []
    for step in range(c["steps"]):
        if step in c["offline"]:
            connections = list(c["offline"][step])
            if c["mode"] == "clear":
                fresh, queue = set(range(c["k"])), []
                last_port = None
        for port in range(c["k"]):
            if timers[port] > 0:
                timers[port] -= 1
            if timers[port] == 0 and not c["late"][port]:
                timers[port] = -1
        delivery = c["arrivals"].get(step, 0)
        if not c.get("arrive_late", False):
            if delivery <= 50-count:
                count += delivery
        if c["kind"] == "machine":
            scan = [j for j in connections if j in fresh] + queue[:]
        else:
            scan = connections[:]
            if last_port is None:
                scan = scan[1:] + scan[:1]
            else:
                while scan[0] != last_port:
                    scan.append(scan.pop(0))
                scan.append(scan.pop(0))
        chosen = next((j for j in scan if timers[j] < 0), None) if count > 0 else None
        if chosen is not None:
            count -= 1
            timers[chosen] = 8
            fresh.discard(chosen)
            if chosen in queue:
                queue.remove(chosen)
            queue.append(chosen)
            last_port = chosen
            successes.append((step, chosen))
        timers = [-1 if value == 0 else value for value in timers]
        if c.get("arrive_late", False) and delivery <= 50-count:
            count += delivery
        if c["kind"] == "machine":
            scan = [j for j in connections if j in fresh] + queue[:]
        else:
            scan = connections[:]
            if last_port is None:
                scan = scan[1:] + scan[:1]
            else:
                while scan[0] != last_port:
                    scan.append(scan.pop(0))
                scan.append(scan.pop(0))
        snapshots.append([step, count, [None if v < 0 else v for v in timers], scan, chosen])
    return snapshots, successes


def all_interval_gap(word, k):
    """max(prefix difference) - min(prefix difference), all pairs."""
    counts = [0] * k
    minima = {(i, j): 0 for i in range(k) for j in range(i)}
    maxima = dict(minima)
    for port in word:
        counts[port] += 1
        for i, j in minima:
            d = counts[i] - counts[j]
            minima[i, j] = min(minima[i, j], d)
            maxima[i, j] = max(maxima[i, j], d)
    return max((maxima[key]-minima[key] for key in minima), default=0)


def direct_interval_gap(word, k):
    maximum = 0
    for start in range(len(word)):
        cnt = [0] * k
        for p in word[start:]:
            cnt[p] += 1
            maximum = max(maximum, max(cnt)-min(cnt))
    return maximum


def main():
    rng = random.Random(101)
    digest = hashlib.sha256()
    batch_cases = group_cases = state_pairs = 0
    largest_batch_gap = 0
    for k in range(2, 7):
        for mode in ("retain", "clear"):
            for repeat in range(60):
                c = dict(k=k, steps=600, stock=rng.randrange(51), kind="machine",
                         mode=mode, late=[0]*k, offline={}, arrivals={})
                for t in range(1, c["steps"]):
                    if rng.randrange(4) == 0:
                        order = list(range(k))
                        rng.shuffle(order)
                        c["offline"][t] = order
                for t in range(rng.randrange(8), c["steps"], 8):
                    if rng.randrange(3):
                        c["arrivals"][t] = k
                a, events = timestamps(c)
                b, other = counters(c)
                assert a == b and events == other
                word = [j for _, j in events]
                gap = all_interval_gap(word, k)
                assert gap <= 2, (c, events, gap)
                largest_batch_gap = max(largest_batch_gap, gap)
                cuts = [0]+sorted(c["offline"])+[c["steps"]]
                for lo, hi in zip(cuts, cuts[1:]):
                    local = [j for t, j in events if lo <= t < hi]
                    assert all_interval_gap(local, k) <= 1
                if mode == "retain":
                    assert gap <= 1
                # A residue prefix followed by complete blocks of k.
                residue = c["stock"] % k
                assert len(set(word[:residue])) == len(word[:residue])
                for p in range(residue, len(word), k):
                    assert len(set(word[p:p+k])) == len(word[p:p+k])
                digest.update(json.dumps(a, separators=(",", ":")).encode())
                batch_cases += 1
                state_pairs += len(a)
    for k in range(1, 7):
        for kind in ("machine", "transport"):
            for _ in range(100):
                groups = [rng.randrange(k+1)]
                for _ in range(24):
                    groups.append(rng.randrange(k-groups[-1]+1))
                c = dict(k=k, kind=kind, mode="retain", stock=0, steps=220,
                         arrivals={8*i: g for i, g in enumerate(groups)}, offline={},
                         late=[rng.randrange(2) for _ in range(k)],
                         arrive_late=bool(rng.randrange(2)))
                a, events = timestamps(c)
                b, other = counters(c)
                assert a == b and events == other
                word = [j for _, j in events]
                assert all_interval_gap(word, k) <= 1
                assert direct_interval_gap(word, k) == all_interval_gap(word, k)
                if len(word) >= k:
                    assert len(set(word[:k])) == k
                    assert all(p == word[i % k] for i, p in enumerate(word))
                digest.update(json.dumps(a, separators=(",", ":")).encode())
                group_cases += 1
                state_pairs += len(a)
    witnesses = {}
    for mode in ("retain", "clear"):
        c = dict(k=3, kind="machine", stock=0, steps=90, mode=mode,
                 late=[0]*3, offline={30: [2, 1, 0]}, arrivals={0: 3, 40: 3})
        a, sent = timestamps(c)
        b, other = counters(c)
        assert a == b and sent == other
        witnesses["batch_"+mode] = dict(config=c, trace=a, events=sent,
             window_2_41=[sum(2 <= t < 41 and p == j for t, p in sent) for j in range(3)])
        c = dict(k=3, kind="machine", stock=0, steps=160, mode=mode,
                 late=[0]*3, offline={t: [0, 1, 2] for t in range(8, 160, 8)},
                 arrivals={t: 1 for t in range(0, 160, 8)})
        a, sent = timestamps(c)
        b, other = counters(c)
        assert a == b and sent == other
        witnesses["group_"+mode] = dict(config=c, trace=a, events=sent,
             counts=[sum(p == j for _, p in sent) for j in range(3)])
        c = dict(c, kind="transport")
        a, sent = timestamps(c)
        b, other = counters(c)
        assert a == b and sent == other
        witnesses["splitter_"+mode] = dict(config=c, trace=a, events=sent,
             counts=[sum(p == j for _, p in sent) for j in range(3)])
    assert witnesses["batch_clear"]["window_2_41"] == [0, 0, 2]
    assert witnesses["group_clear"]["counts"] == [20, 0, 0]
    assert witnesses["splitter_clear"]["counts"] == [0, 20, 0]
    assert direct_interval_gap([j for t, j in witnesses["batch_clear"]["events"]], 3) == 2
    crt_cases = 0
    for k in range(1, 7):
        for length in range(1, 31):
            word = [rng.randrange(3) for _ in range(length)]
            joint = lcm(k, length)
            h = gcd(k, length)
            # Number-theoretic encoding, independent of the explicit dispatch.
            predicted = [[Fraction(h * sum(word[i] == x for i in range(j % h, length, h)),
                                   length*k) for x in range(3)] for j in range(k)]
            counted = [[0]*3 for _ in range(k)]
            for n in range(joint):
                counted[n % k][word[n % length]] += 1
            observed = [[Fraction(v, joint) for v in row] for row in counted]
            assert predicted == observed
            crt_cases += 1
    result = dict(batch_cases=batch_cases, group_cases=group_cases,
                  paired_step_states=state_pairs, largest_batch_all_interval_gap=largest_batch_gap,
                  crt_cases=crt_cases, normalized_state_sha256=digest.hexdigest(),
                  witnesses=witnesses,
                  scope="Local outlet interfaces; random batch schedules are a relaxation, not factory feasibility.")
    (OUT/"polling_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({key: val for key, val in result.items() if key != "witnesses"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
