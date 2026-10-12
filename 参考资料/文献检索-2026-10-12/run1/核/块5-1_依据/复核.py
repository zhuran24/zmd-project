"""只复核本席保存的单桩模式和集中桩位例；不写项目仓库。"""
from pathlib import Path
from collections import Counter
import json

ROOT = Path(__file__).resolve().parent


def body(z):
    x, y, w, h = z['r']
    return {(i, j) for i in range(x, x + w) for j in range(y, y + h)}


def check_mode(name, counts):
    d = json.loads((ROOT / name).read_text())
    zs = d['chosen']
    assert Counter(z['kind'] for z in zs) == Counter(dict(zip('sml', counts)))
    pole = {(5, 5), (5, 6), (6, 5), (6, 6)}
    occupied = set(pole)
    coverage = {(i, j) for i in range(12) for j in range(12)}
    assert len(zs) <= 23
    for z in zs:
        _, _, width, height = z['r']
        assert (width, height, z['axis']) in {
            's': {(3, 3, 0), (3, 3, 1)},
            'm': {(5, 5, 0), (5, 5, 1)},
            'l': {(6, 4, 1), (4, 6, 0)},
        }[z['kind']]
        b = body(z)
        assert b & coverage
        assert not b & occupied
        occupied |= b
    for z in zs:
        x, y, w, h = z['r']
        sides = (
            [[(x - 1, j) for j in range(y, y + h)],
             [(x + w, j) for j in range(y, y + h)]]
            if z['axis'] == 0 else
            [[(i, y - 1) for i in range(x, x + w)],
             [(i, y + h) for i in range(x, x + w)]]
        )
        assert all(any(c not in occupied for c in side) for side in sides)
    return counts


a = check_mode('mode_13_5_4.json', (13, 5, 4))
check_mode('mode_14_5_3.json', (14, 5, 3))
b = check_mode('mode_14_3_2.json', (14, 3, 2))
assert tuple(9 * x + y for x, y in zip(a, b)) == (131, 48, 38)

d = json.loads((ROOT / '反例检查.json').read_text())
occupied = set()
for z in d['fixed_poles'] + d['candidate_units']:
    cells = body(z)
    assert all(0 <= x < 70 and 0 <= y < 70 for x, y in cells)
    assert not occupied & cells
    occupied |= cells
coverage = set()
for p in d['fixed_poles']:
    x, y, _, _ = p['r']
    coverage |= {(i, j) for i in range(x - 5, x + 7)
                 for j in range(y - 5, y + 7)}
assert coverage == {(i, j) for i in range(15, 35) for j in range(55, 69)}
assert 30 * 20 == d['body_containment_area'] == 600
assert 131 * 9 + 48 * 25 + 38 * 24 == d['required_machine_area'] == 3291
print('PASS: 三个局部模式、完整配置 IP 的整数解、集中桩位例的占格及面积矛盾')
