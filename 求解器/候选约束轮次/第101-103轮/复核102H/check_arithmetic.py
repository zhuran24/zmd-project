"""Independent finite lemmas. Standard library; writes only beside this file."""
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, product
from math import gcd, lcm
from pathlib import Path
import json

OUT = Path(__file__).resolve().parent

def release_checks():
    # Encoding A: all non-idling schedules, represented by a bit mask.
    # Encoding B: independently sort release dates and recur on finish times.
    cases = states = 0
    latest = 0
    by_k = {}
    for k in range(1, 7):
        count = 0
        for occupied in range(k):
            for positive in combinations(range(1, 8), occupied):
                rel = (0,) * (k - occupied) + positive
                @lru_cache(None)
                def search(t, mask):
                    if mask == (1 << k) - 1:
                        return (t - 1, t - 1)
                    ready = [j for j in range(k) if not mask >> j & 1 and rel[j] <= t]
                    if not ready:
                        return search(t + 1, mask)
                    ends = [search(t + 1, mask | 1 << j) for j in ready]
                    return min(x[0] for x in ends), max(x[1] for x in ends)
                got = search(0, 0)
                prev = -1
                for r in sorted(rel):
                    prev = max(r, prev + 1)
                expression = max(r + k - i - 1 for i, r in enumerate(sorted(rel)))
                assert got == (prev, prev) and prev == expression <= 7
                states += search.cache_info().currsize
                latest = max(latest, prev)
                count += 1
        by_k[k] = count
        cases += count
    return dict(patterns=cases, schedule_states=states, latest_offset=latest, by_k=by_k)

def modular_checks():
    checked = 0
    for length in range(1, 11):
        for k in range(1, 7):
            for word in product(range(2), repeat=length):
                h = gcd(length, k)
                formula = [[Fraction(h * sum(word[i] == a for i in range(j % h, length, h)), length * k)
                            for a in range(2)] for j in range(k)]
                observed = [[0, 0] for _ in range(k)]
                period = lcm(length, k)
                for event in range(period):
                    observed[event % k][word[event % length]] += 1
                observed = [[Fraction(v, period) for v in row] for row in observed]
                assert formula == observed
                checked += 1
    return dict(binary_words_and_channel_counts=checked, max_word_length=10)

def window_checks():
    # Maximum-weight separated subset, independent of the residue calculation.
    @lru_cache(None)
    def select(steps_left, cooldown):
        if not steps_left:
            return 0
        skip = select(steps_left - 1, max(0, cooldown - 1))
        return skip if cooldown else max(skip, 1 + select(steps_left - 1, 7))
    max_single = select(40, 0)
    phase_max = 0
    for residues in product(range(8), repeat=3):
        count = sum(sum(t % 8 == r for t in range(1, 41)) for r in residues)
        phase_max = max(phase_max, count)
        assert count == 3 * max_single == 15
    for t in range(1, 161):
        assert select(t, 0) == (t + 7) // 8
    return dict(three_port_phases=8**3, single_port_40_steps=max_single,
                three_port_40_steps=phase_max)

def cumulative_checks():
    checked = 0
    for h2 in [300, 352, 354, 388]:
        for x2 in range(0, 801):
            y = x2
            for m in range(31):
                y = min(y - 1, h2)
                closed = min(x2 - (m + 1), h2 - m)
                assert y == closed
                checked += 1
    # Components, in half-item integer units; a separate rational computation.
    low = 2 * (49 + 50 + 49 + 1 + 1)
    normal = sum([50, 50, 50, 1, 1]) + Fraction(49, 2) - Fraction(1, 2)
    capacity = Fraction(3 * 50 + 2) + Fraction(50, 2)
    assert low // 2 == 150 and normal == 176 and capacity == 177
    assert sum([98, 100, 98, 2, 2]) == 300
    assert sum([100, 100, 100, 2, 2, 49, -1]) == 352
    assert sum([100, 100, 100, 2, 2, 50]) == 354
    budgets = sum([50] * 52) + sum([53] * 18) + sum([153] * 9) + sum([100] * 3) + 9800
    direct = 52*50 + 18*(50+3) + 9*(100+50+3) + 3*100 + 2*70*70
    assert budgets == direct == 15031
    return dict(cumulative_cases=checked, H_preparation=150, H_normal=176, max_phi_offset=177,
                powder_minima=[50-k for k in [2,3]], startup_threshold=(200-5)//2,
                old_startup_stock_upper=direct, remaining=80000-direct,
                startup_supply_need=550+9800)

def finite_stock_checks():
    # For 400 discrete steps, count all possible 8-step phases of starts.
    starts = [len(range(p, 400, 8)) for p in range(8)]
    assert max(starts) == 50
    waits = []
    for n in range(1, 4):
        longest = 0
        for orders in product(list(__import__('itertools').permutations(range(n))), repeat=n):
            occupied = set()
            for t, order in enumerate(orders):
                target = next(j for j in order if j not in occupied)
                occupied.add(target)
                if target == 0:
                    longest = max(longest, t)
                    break
            assert 0 in occupied
        assert longest == n-1
        waits.append(longest)
    return dict(max_starts_in_400_steps=max(starts), C21_min_output=[50-3*k for k in [1,2,3]],
                K_max_wait_steps=waits)

def main():
    result = dict(release=release_checks(), modular=modular_checks(), window=window_checks(),
                  cumulative=cumulative_checks(), finite_stock=finite_stock_checks())
    (OUT / 'arithmetic.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
