from itertools import product

def one_port(width):
    # 最后一步不送，或最后一步送且此前七步不送。
    best = [0]
    for n in range(1, width + 1):
        best.append(max(best[n - 1], 1 + best[max(0, n - 8)]))
    return best[-1]

period = 5 * 8
limit = 3 * one_port(period)
print(period, one_port(period), one_port(period + 1), limit)
max_slots = 0
for sequence in product((1, 2), repeat=limit):
    slots = [[] for _ in range(5)]
    for kind in sequence:
        slot = next(s for s in slots if not s or (s[0] == kind and len(s) < 50))
        slot.append(kind)
        max_slots = max(max_slots, sum(bool(s) for s in slots))
print(2**limit, max_slots)
