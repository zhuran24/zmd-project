#!/usr/bin/env python3
"""Finite overapproximation, with two separately implemented transitions.

The output stock is represented modulo k. When the residue is nonzero,
there must be an item, so an empty head must be served. At residue zero,
either no batch is available, or one or more full batches are available.
This includes arbitrary arrival times, arbitrary backlog, arbitrary route
priorities, and arbitrary record resets, and is larger than the real model.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import time


def graph_a(k, single_items=False):
    # State before the source judgment: (stock residue, availability timers).
    starts = [(r, (0,) * k) for r in range(k)]
    todo, seen, graph = deque(starts), set(starts), {}
    while todo:
        state = todo.popleft()
        residue, timers = state
        empty = [i for i in range(k) if timers[i] == 0]
        decisions = empty[:]
        if residue == 0 or not empty or single_items:
            decisions.append(-1)
        edges = []
        for route in decisions:
            after = [max(0, t - 1) for t in timers]
            r = residue
            if route >= 0:
                after[route] = 7
                r = (r - 1) % k
            nxt = (r, tuple(after))
            edges.append((nxt, route))
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
        graph[state] = tuple(edges)
    return starts, graph


def history_key(state, k):
    residue, history = state
    timers = [0] * k
    for age, route in enumerate(history):
        if route >= 0:
            assert timers[route] == 0
            timers[route] = 7 - age
    return residue, tuple(timers)


def graph_b(k, single_items=False):
    # State records the last 7 judgments, latest first; -1 is no shipment.
    starts = [(r, (-1,) * 7) for r in range(k)]
    todo, seen, graph = deque(starts), set(starts), {}
    while todo:
        state = todo.popleft()
        remaining, history = state
        available = set(range(k)).difference(history)
        labels = sorted(available)
        if not available or remaining == 0 or single_items:
            labels += [-1]
        edges = []
        for selected in labels:
            if selected < 0:
                tail = remaining
            else:
                tail = k - 1 if remaining == 0 else remaining - 1
            nxt = (tail, (selected,) + history[:6])
            edges.append((nxt, selected))
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
        graph[state] = tuple(edges)
    return starts, graph


def graph_digest(graph):
    sha = hashlib.sha256()
    for state in sorted(graph):
        row = (state, sorted(graph[state]))
        sha.update((repr(row) + "\n").encode())
    return sha.hexdigest()


def prefix_extrema(starts, graph, cap=3):
    # A: track actual prefix count difference and both prefix extrema.
    starts = [(s, 0, 0, 0) for s in starts]
    todo, seen = deque(starts), set(starts)
    maximum = 0
    while todo:
        s, d, low, high = todo.popleft()
        for nxt, route in graph[s]:
            delta = (route == 0) - (route == 1)
            value = d + delta
            lower, upper = min(low, value), max(high, value)
            maximum = max(maximum, upper - lower)
            if maximum >= cap:
                return {"maximum": maximum, "states": len(seen),
                        "complete": False, "stopped_at_counterexample": True}
            state = (nxt, value, lower, upper)
            if state not in seen:
                seen.add(state)
                todo.append(state)
    return {"maximum": maximum, "states": len(seen), "complete": True}


def best_interval(starts, graph, sign, cap=3):
    # B: longest weighted suffix, allowed to start anew at every vertex.
    # Queue relaxation, not cumulative-prefix/min/max state enumeration.
    best = {s: 0 for s in graph}
    todo, queued = deque(graph), set(graph)
    relaxations = 0
    while todo:
        s = todo.popleft()
        queued.remove(s)
        for nxt, route in graph[s]:
            w = sign * ((route == 0) - (route == 1))
            candidate = max(0, best[s] + w)
            if candidate > best[nxt]:
                best[nxt] = candidate
                relaxations += 1
                if candidate >= cap:
                    return {"maximum": candidate, "complete": False,
                            "relaxations": relaxations}
                if nxt not in queued:
                    queued.add(nxt)
                    todo.append(nxt)
    return {"maximum": max(best.values()), "complete": True,
            "relaxations": relaxations}


def run(k, single_items=False):
    began = time.monotonic()
    sa, ga = graph_a(k, single_items)
    sb, gb = graph_b(k, single_items)
    # Comparing every reachable transition detects off-by-one cooldown errors.
    normalized = {history_key(s, k): tuple((history_key(n, k), c)
                                         for n, c in edges)
                  for s, edges in gb.items()}
    assert len(normalized) == len(gb)
    assert set(ga) == set(normalized)
    for s in ga:
        assert sorted(ga[s]) == sorted(normalized[s]), s
    a = prefix_extrema(sa, ga)
    bp = best_interval(sb, gb, 1)
    bm = best_interval(sb, gb, -1)
    assert a["maximum"] == max(bp["maximum"], bm["maximum"])
    if not single_items:
        assert a["complete"] and bp["complete"] and bm["complete"]
        assert a["maximum"] <= 2
    else:
        assert a["maximum"] >= 3
    return {"k": k, "single_item_negative_control": single_items,
            "base_states_a": len(ga), "base_states_b": len(gb),
            "base_edges": sum(map(len, ga.values())),
            "base_graph_sha256": graph_digest(ga),
            "transition_mismatches": 0, "prefix_extrema_a": a,
            "interval_relaxation_b_positive": bp,
            "interval_relaxation_b_negative": bm,
            "seconds": round(time.monotonic() - began, 3)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--max-k", type=int, default=4)
    args = p.parse_args()
    result = {"rows": []}
    target = Path(__file__).with_name("graphs.json")
    for k in range(2, args.max_k + 1):
        row = run(k)
        result["rows"].append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    result["negative_control"] = run(2, True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["negative_control"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
