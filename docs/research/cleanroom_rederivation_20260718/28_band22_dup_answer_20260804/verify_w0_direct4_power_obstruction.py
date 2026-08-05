#!/usr/bin/env python3
"""Arithmetic verifier for the direct adjacent-4-band power obstruction.

Scope:
  * 14 manufacturing bands with heights 6x3, 4x4, 4x5;
  * a 9x9 core occupying two adjacent 4-high bands;
  * one full-height riser/slit column per band;
  * hole Model A or Model B in one 5-high band;
  * all corridor rows reserved for transport;
  * every 2x2 power-pole body wholly inside manufacturing-band free cells.

This script checks the q/r arithmetic and the only global-equality escape case.
It does not invoke a solver.
"""
from itertools import product
from math import ceil

K = {3: 5, 5: 4, 6: 3}

# Horizontal-union lemma M_w(f) <= K_w floor(f/2).
for w in (3, 5, 6):
    for f in range(2, 69):
        M = (f + 8) // w + 2
        assert M <= K[w] * (f // 2), (w, f, M, K[w] * (f // 2))


def q(width: int, machine_width: int, m: int) -> int:
    return (width - machine_width * m) // 2


def r(m: int, machine_width: int) -> int:
    return ceil(m / K[machine_width])


def deficit_states(base, deficit, machine_width):
    out = []
    for dec in product(range(deficit + 1), repeat=len(base)):
        if sum(dec) != deficit:
            continue
        ms = [m - d for (_, m), d in zip(base, dec)]
        if min(ms) < 0:
            continue
        qs = [q(w, machine_width, m) for (w, _), m in zip(base, ms)]
        rs = [r(m, machine_width) for m in ms]
        out.append({"Q": sum(qs), "R": sum(rs), "dec": dec, "m": ms, "q": qs, "r": rs})
    return out


# Four 4-high bands: two normal width67 and two core-cut width58.
base4 = [(67, 11), (67, 11), (58, 9), (58, 9)]
states4 = deficit_states(base4, 2, 6)
assert {s["Q"] for s in states4} == {10}
assert min(s["R"] for s in states4) == 13
for s in states4:
    if s["R"] == 13:
        assert sorted(s["q"]) == [0, 2, 2, 6]

# Six exact 3-high bands.
Q3, R3 = 0, 6 * ceil(22 / K[3])
assert R3 == 30

# Model A cases.
A_endpoint = deficit_states([(67, 13), (67, 13), (67, 13), (62, 12)], 2, 5)
A_internal_good = deficit_states([(67, 13), (67, 13), (67, 13), (61, 12)], 2, 5)
A_internal_bad = deficit_states([(67, 13), (67, 13), (67, 13), (61, 11)], 1, 5)
assert {s["Q"] for s in A_endpoint} == {8, 9}
assert max(s["Q"] for s in A_internal_good) == 8
assert max(s["Q"] for s in A_internal_bad) == 8

# Model B cases. At a=1 the hole+riser union removes 5 working columns, width63.
# For 2<=a<=64 it removes 6 working columns, width62. Good capacity is12;
# bad internal residue has capacity11.
B_a1_good = deficit_states([(67, 13), (67, 13), (67, 13), (63, 12)], 2, 5)
B_other_good = deficit_states([(67, 13), (67, 13), (67, 13), (62, 12)], 2, 5)
B_internal_bad = deficit_states([(67, 13), (67, 13), (67, 13), (62, 11)], 1, 5)
assert sorted({(s["Q"], s["R"]) for s in B_a1_good}) == [(8, 13), (9, 14), (9, 15)]
assert sorted({(s["Q"], s["R"]) for s in B_other_good}) == [(8, 13), (8, 14), (9, 14), (9, 15)]
assert sorted({(s["Q"], s["R"]) for s in B_internal_bad}) == [(8, 14), (9, 15)]


def check_family(name, states5):
    equality_cases = 0
    for s4 in states4:
        for s5 in states5:
            Q = Q3 + s4["Q"] + s5["Q"]
            R = R3 + s4["R"] + s5["R"]
            assert R >= 3 * Q, (name, s4, s5, Q, R)
            if R == 3 * Q:
                equality_cases += 1
                # Equality in the summed neighborhood bound forces both boundary
                # bands to have q=0. There is exactly one non-3-high q=0 band.
                # A boundary 3-high band would require its sole neighbor q=5,
                # but no q=5 occurs. Hence two boundaries cannot be filled.
                non3_q = s4["q"] + s5["q"]
                assert non3_q.count(0) == 1, (name, non3_q)
                assert 5 not in non3_q, (name, non3_q)
    return equality_cases


eq_A_endpoint = check_family("Model A endpoint", A_endpoint)
eq_A_good = check_family("Model A internal good", A_internal_good)
eq_A_bad = check_family("Model A internal bad", A_internal_bad)
eq_B_a1 = check_family("Model B a=1 good", B_a1_good)
eq_B_good = check_family("Model B other good", B_other_good)
eq_B_bad = check_family("Model B internal bad", B_internal_bad)

assert eq_A_good == eq_A_bad == eq_B_bad == 0
assert eq_A_endpoint > 0 and eq_B_a1 > 0 and eq_B_good > 0

print("ASSUMPTIONS: adjacent 4+4 core; one riser/slit per band; corridor rows reserved; poles wholly inside manufacturing bands")
print("LEMMA_CHECKED: M_w(f) <= K_w floor(f/2), w in {3,5,6}, f=2..68")
print("4_BAND_STATES:", len(states4), "Q4", sorted({s['Q'] for s in states4}), "min_R4", min(s['R'] for s in states4))
print("MODEL_A: endpoint/internal-good/internal-bad checked")
print("MODEL_B: a=1 good width63; other good width62; bad width62 checked")
print("EQUALITY_CASES:", {"A_endpoint": eq_A_endpoint, "B_a1": eq_B_a1, "B_other_good": eq_B_good})
print("EQUALITY_ESCAPE_REJECTED: two boundary q=0 positions are needed, but only one non-3 band has q=0 and no q=5 can support a boundary 3-band")
print("RESULT: every Model A and Model B hole position/residue is impossible under the stated scope")
