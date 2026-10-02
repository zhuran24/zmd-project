#!/usr/bin/env python3
"""Two independent counts for every indicator word position, plus LRU trace."""
from fractions import Fraction
from math import gcd
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def direct_pairs(length, channels):
    counts = [[0] * length for _ in range(channels)]
    state = (0, 0)
    period = 0
    while True:
        position, ch = state
        counts[ch][position] += 1
        period += 1
        state = ((position + 1) % length, (ch + 1) % channels)
        if state == (0, 0):
            return period, counts


def modular_pairs(length, channels):
    # This implementation uses only gcd, with no traversal of the joint orbit.
    h = gcd(length, channels)
    period = length * channels // h
    counts = [[int(position % h == ch % h) for position in range(length)]
              for ch in range(channels)]
    return period, counts


def main():
    instances = scalar_checks = 0
    for length in range(1, 61):
        for k in range(1, 7):
            period_a, counts_a = direct_pairs(length, k)
            period_b, counts_b = modular_pairs(length, k)
            assert (period_a, counts_a) == (period_b, counts_b)
            for ch in range(k):
                for position in range(length):
                    assert Fraction(counts_a[ch][position], period_a) == Fraction(
                        gcd(length, k) * counts_b[ch][position], length * k)
                    scalar_checks += 1
            instances += 1

    # Actual connection order is A,B,C, while attainable success ages are A,C,B.
    ages = {'A': -30, 'B': -10, 'C': -20}
    free_at = dict.fromkeys(ages, -99)
    direct = []
    for step in range(0, 120, 8):
        candidates = sorted(ages, key=ages.__getitem__)
        ch = next(c for c in candidates if free_at[c] <= step)
        direct.append({'step': step, 'channel': ch})
        ages[ch], free_at[ch] = step, step + 8
    queue = ['A', 'C', 'B']
    independent = []
    for step in range(0, 120, 8):
        ch = queue.pop(0)
        queue.append(ch)
        independent.append({'step': step, 'channel': ch})
    assert direct == independent
    actual = ''.join(event['channel'] for event in direct)
    assert actual[:3] not in ('ABC', 'BCA', 'CAB')
    result = {
        'formula_instances': instances, 'scalar_equalities_checked': scalar_checks,
        'range': {'L': [1, 60], 'k': [1, 6]}, 'violations': 0,
        'counterexample': {'connection_order': 'ABC', 'initial_success_age_order': 'ACB',
                          'initial_all_first_cells_empty': True,
                          'group_sizes': [1] * 15, 'adjacent_group_sum': 2,
                          'k': 3, 'two_independent_implementations_agree': True,
                          'trace': direct, 'success_word': actual,
                          'qualification': 'local temporal counterexample to connection-order wording, not a certified successful base layout'}}
    (OUT / 'polling_formula_verify.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: val for key, val in result.items() if key != 'counterexample'}))


if __name__ == '__main__':
    main()
