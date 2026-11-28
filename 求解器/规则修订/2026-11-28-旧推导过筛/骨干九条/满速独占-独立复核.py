from fractions import Fraction as F

battery, capsule = F(18, 30), F(33, 60)
steel = 10 * battery + 20 * capsule
dense_ore = 15 * battery
fine_flower = 10 * capsule
ground_sand = (steel + dense_ore + fine_flower) / 3
blue, ore = 2 * steel, 2 * dense_ore
assert (blue, ore, 2 * (70 // 3) + 6) == (34, 18, 52)
# 回炼每多一批，额外粉碎、精炼各一批
base = (blue + ore + fine_flower + ground_sand, blue + steel,
        10 * battery, 2 * (fine_flower + ground_sand))
assert base == (68, 51, 6, 32)
print("矿石", blue, ore, "机器批率常数项", *base)

def first_refusal(start, k, reset_after_four=False):
    slots = []
    for i in range(100):
        s = start + 8 * i
        if reset_after_four and i and i % 4 == 0:
            slots = []
            # 在紧邻本次收货前重建，本步为新段的第 1 步
            last_reset = s
        age = s - last_reset + 1 if reset_after_four and i >= 4 else s
        segment = 1 + age // 4
        slots = [before for before in slots if segment - before < 10]
        if len(slots) >= k:
            return i + 1
        slots.append(segment)
    return None

for k in range(6):
    results = {first_refusal(start, k) for start in range(1, 9)}
    assert results == ({k + 1} if k < 5 else {None})
    print("k", k, "各相位首拒件序号", results)
assert first_refusal(1, 4, True) is None
