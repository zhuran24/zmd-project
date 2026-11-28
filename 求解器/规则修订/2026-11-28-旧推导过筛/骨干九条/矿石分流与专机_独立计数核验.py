from fractions import Fraction as F
from itertools import product

steel_blue = 2
battery_blue, battery_source = 10 * steel_blue, 15 * 2
capsule_blue = 10 * 2 * steel_blue
blue = F(18, 30) * battery_blue + F(33, 60) * capsule_blue
source = F(18, 30) * battery_source
print(battery_blue, battery_source, capsule_blue, blue, source, 2 * (70 // 3) + 6)

def totals(states):
    # Double the sum. Zero and full rates fix it, partial rates give an
    # open interval with even endpoints. All nonempty intersections of
    # such intervals and singleton totals contain an integer.
    full, partial = states.count(2), states.count(1)
    if not partial:
        return {2 * full}
    return set(range(2 * full + 1, 2 * (full + partial)))

for name, ins, outs in [('straight', 1, 1), ('merger', 3, 1), ('splitter', 1, 3), ('box', 3, 3)]:
    rows = []
    for left in product(range(3), repeat=ins):
        for right in product(range(3), repeat=outs):
            if not (totals(left) & totals(right) - {0}):
                continue
            rows.append((outs-right.count(0) - (ins-left.count(0)), left.count(2)-right.count(2), right.count(1)-left.count(1)))
    print(name, tuple(map(max, zip(*rows))))
