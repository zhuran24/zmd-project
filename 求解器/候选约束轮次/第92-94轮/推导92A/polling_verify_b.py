#!/usr/bin/env python3
"""Independent event model: queue order and countdown occupancy."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def words(length, alphabet):
    if length == 0:
        yield ()
    else:
        for x in alphabet:
            for suffix in words(length - 1, alphabet):
                yield (x,) + suffix


def batches(k, prefix=()):
    if len(prefix) == 4:
        yield prefix
        return
    maximum = k if not prefix else k - prefix[-1]
    for size in range(maximum + 1):
        yield from batches(k, prefix + (size,))


def run(k, groups, phases, delays, mode):
    original = list(range(k)) if mode == 'rotor' else list(range(k - 1, -1, -1))
    queue = original[:]
    countdown = [0] * k
    waiting = []
    for group_index, size in enumerate(groups):
        waiting += [(8 * group_index + delays[group_index], group_index)] * size
    sent = []
    for step in range(8 * len(groups) + 8):
        if waiting and waiting[0][0] <= step:
            ch = next((candidate for candidate in queue
                       if countdown[candidate] == 0), None)
            if ch is not None:
                waiting.pop(0)
                sent.append((step, ch))
                # Countdown is reduced after the source's judgement.
                countdown[ch] = 8 + phases[ch]
                if mode == 'lru':
                    queue.remove(ch)
                    queue.append(ch)
                else:
                    after = (ch + 1) % k
                    queue = list(range(after, k)) + list(range(after))
        countdown = [max(0, age - 1) for age in countdown]
    assert not waiting
    for number, (_, ch) in enumerate(sent):
        assert ch == original[number % k]
    return sent


def main():
    digest = hashlib.sha256()
    counts = {}
    for k in range(1, 7):
        count = 0
        for groups in batches(k):
            for phases in words(k, (0, 1)):
                for delays in words(4, (0, 1)):
                    for mode in ('rotor', 'lru'):
                        sent = run(k, groups, phases, delays, mode)
                        row = [k, groups, phases, delays, mode, sent]
                        digest.update((json.dumps(row, separators=(',', ':')) + '\n').encode())
                        count += 1
        counts[str(k)] = count
    result = {'model': 'event queue / countdown cells / move-success-to-back',
              'cases_by_k': counts, 'cases_total': sum(counts.values()),
              'canonical_sha256': digest.hexdigest(), 'violations': 0}
    (OUT / 'polling_verify_b.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
