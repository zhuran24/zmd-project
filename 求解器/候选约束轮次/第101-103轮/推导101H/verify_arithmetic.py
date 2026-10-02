"""Independent arithmetic and exhaustive small scheduling lemmas."""
from pathlib import Path
from fractions import Fraction
from functools import lru_cache
import itertools
import json

OUT = Path(__file__).resolve().parent


def main():
    # Formula versus explicit weighted extreme-state enumeration.
    maximum_formula = 3*50+2+Fraction(50, 2)
    maximum_enumeration = max(Fraction(sum(raw)+ca+cc)+Fraction(out, 2)
                              for raw in itertools.product((0, 49, 50), repeat=3)
                              for ca, cc in itertools.product((0, 1), repeat=2)
                              for out in range(51))
    lower150 = sum((49, 50, 49, 1, 1))
    lower150_alternative = sum([50]*3)-2+len(["A cache", "C cache"])
    lower176 = Fraction(3*50+2)+Fraction(49, 2)-Fraction(1, 2)
    lower176_alternative = maximum_enumeration-1
    assert maximum_formula == maximum_enumeration == 177
    assert lower150 == lower150_alternative == 150
    assert lower176 == lower176_alternative == 176
    compositions = 0
    for threshold in (304, 356, 676):
        for initial in range(0, threshold+11):
            for resets in range(21):
                value = initial
                for _ in range(resets+1):
                    value = min(value-1, threshold)
                closed = min(initial-(resets+1), threshold-resets)
                assert value == closed
                compositions += 1
    # At the start of a nonempty k-item block, previously occupied heads become
    # ready at distinct positive integer offsets in 1..7. Empty heads have 0.
    # Every work-conserving choice is explored; no polling algorithm is assumed.
    cases = branches = worst_finish = 0
    for k in range(1, 7):
        for zeros in range(1, k+1):
            for positive in itertools.combinations(range(1, 8), k-zeros):
                release = (0,)*zeros+positive
                @lru_cache(None)
                def finish(time, mask):
                    nonlocal branches
                    branches += 1
                    if mask == 0:
                        return time-1
                    available = [p for p in range(k) if mask >> p & 1 and release[p] <= time]
                    if not available:
                        return finish(time+1, mask)
                    return max(finish(time+1, mask ^ (1 << p)) for p in available)
                by_choices = finish(0, (1 << k)-1)
                by_counting = max(r+k-i-1 for i, r in enumerate(sorted(release)))
                assert by_choices == by_counting <= 7
                worst_finish = max(worst_finish, by_choices)
                cases += 1
    result = dict(constants=dict(maximum_loop_offset=int(maximum_formula),
                                 arbitrary_start_offset=lower150, normal_start_offset=int(lower176),
                                 K_output_floor={str(k): 50-k for k in (2, 3)},
                                 three_outlet_wait_steps=3-1, cooldown_steps=5*8),
                  iterated_epoch_bounds=compositions, readiness_patterns=cases,
                  scheduling_states=branches, latest_last_send_offset=worst_finish,
                  methods=["weighted state enumeration versus component sum",
                           "iterated min map versus closed expression",
                           "all work-conserving choices versus sorted-release counting"])
    (OUT/"arithmetic.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
