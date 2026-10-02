#!/usr/bin/env python3
"""Direct step model: last-success sorting; no import of sim2."""
import hashlib
import itertools
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def run(k, groups, phases, delays, mode):
    order = tuple(range(k)) if mode == 'rotor' else tuple(reversed(range(k)))
    last = {ch: rank - k for rank, ch in enumerate(order)}
    release = [-99] * k
    cursor = 0
    pending = 0
    sent = []
    arrivals = {8 * n + delays[n]: count for n, count in enumerate(groups)}
    for step in range(8 * len(groups) + 8):
        pending += arrivals.get(step, 0)
        if not pending:
            continue
        choice = (sorted(range(k), key=lambda ch: last[ch]) if mode == 'lru'
                  else [(cursor + offset) % k for offset in range(k)])
        for ch in choice:
            # A phase bit means a cell frees after the source's judgement.
            if release[ch] < step or (release[ch] == step and not phases[ch]):
                sent.append((step, ch))
                pending -= 1
                release[ch] = step + 8
                last[ch] = step
                cursor = (ch + 1) % k
                break
    assert pending == 0
    expected = [order[n % k] for n in range(sum(groups))]
    assert [ch for _, ch in sent] == expected, (k, groups, phases, delays, mode, sent)
    return sent


def main():
    digest = hashlib.sha256()
    cases = {str(k): 0 for k in range(1, 7)}
    for k in range(1, 7):
        for groups in itertools.product(range(k + 1), repeat=4):
            if any(a + b > k for a, b in zip(groups, groups[1:])):
                continue
            for phases in itertools.product((0, 1), repeat=k):
                for delays in itertools.product((0, 1), repeat=4):
                    for mode in ('rotor', 'lru'):
                        sent = run(k, groups, phases, delays, mode)
                        row = [k, groups, phases, delays, mode, sent]
                        digest.update((json.dumps(row, separators=(',', ':')) + '\n').encode())
                        cases[str(k)] += 1
    result = {'model': 'direct step / absolute releases / sorted success ages',
              'cases_by_k': cases, 'cases_total': sum(cases.values()),
              'canonical_sha256': digest.hexdigest(), 'violations': 0,
              'scope': 'all four-group words, k=1..6, all per-channel release phases and all group delays 0/1 step; rotor natural order and LRU reversed order'}
    (OUT / 'polling_verify_a.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
