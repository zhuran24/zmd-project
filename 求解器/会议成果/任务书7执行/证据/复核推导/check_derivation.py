#!/usr/bin/env python3
"""复核推导的有限算术检查；不实现游戏调度，不产生整厂运行证书。"""
import json
from fractions import Fraction as Q
from pathlib import Path

HERE = Path(__file__).resolve().parent

dead = []
states = 0
transitions = 0
for a in range(51):
    for b in range(51):
        z = a - 2*b
        can_start = a >= 2 and b >= 1
        if can_start:
            assert (a-2)-2*(b-1) == z
            transitions += 1
        if a < 50:
            assert (a+1)-2*b == z+1
            transitions += 1
        if b < 50:
            assert a-2*(b+1) == z-2
            transitions += 1
        for head in ('A', 'B'):
            states += 1
            head_full = a == 50 if head == 'A' else b == 50
            if head_full and not can_start:
                dead.append({'a': a, 'b': b, 'head': head, 'Z': z})
                assert not -99 < z < 50
assert dead == [
    {'a': 0, 'b': 50, 'head': 'B', 'Z': -100},
    {'a': 1, 'b': 50, 'head': 'B', 'Z': -99},
    {'a': 50, 'b': 0, 'head': 'A', 'Z': 50},
]

rotations = {}
for word in ('AAB', 'ABA', 'BAA'):
    prefix = [0]
    for letter in word:
        prefix.append(prefix[-1]+(1 if letter == 'A' else -2))
    assert prefix[-1] == 0  # 整轮净零将有限前缀界推广到所有轮次。
    assert all(-99 < -50+d < 50 for d in prefix)
    rotations[word] = {'prefix': prefix, 'range': [min(prefix), max(prefix)]}
full_safe_D = [d for d in range(-200, 201) if -99 < -50+d < 50]
assert full_safe_D == list(range(-48, 100))

# 边界上也有可持续接收的字序：只核收件/扣料账，排货与时间由正文前提提供。
a, b = 50, 0
boundary_path = [[a,b]]
for letter in 'BAA':
    if letter == 'B':
        b += 1
        a -= 2
        b -= 1
    else:
        a += 1
    assert 0 <= a <= 50 and 0 <= b <= 50
    boundary_path.append([a,b])
assert (a,b) == (50,0)

battery, capsule = Q(3,5), Q(11,20)
parts = 10*battery
dense_source = 15*battery
bottles = fine_flower = 10*capsule
steel = parts + 2*bottles
blue_dust = 2*steel
source_dust = 2*dense_source
flower_dust = 2*fine_flower
sand_dust = steel + dense_source + fine_flower
flower_crush, sand_crush = flower_dust/2, sand_dust/3
base_crush = source_dust + blue_dust + flower_crush + sand_crush
base_refine = blue_dust + steel
assert (base_crush,base_refine) == (68,51)
assert 50*battery+40*capsule == 52
capacity_cases = []
for nc,nr in ((68,51),(68,52),(69,51),(69,52)):
    r_bound = min(Q(nc)-base_crush,Q(nr)-base_refine)
    capacity_cases.append({'crushers': nc, 'refiners': nr, 'r_upper_bound': str(r_bound)})
assert [c['r_upper_bound'] for c in capacity_cases] == ['0','0','0','1']

result = {
    'status': 'pass',
    'scope': '局部库存算术、归纳基和必要产能；无游戏调度、无参数扫描、无整厂证书',
    'inventory_and_head_cases': states,
    'invariant_transitions_checked': transitions,
    'deadlock_count_states': dead,
    'rotations': rotations,
    'full_input_Z0': -50,
    'full_input_safe_integer_D': [full_safe_D[0],full_safe_D[-1]],
    'safe_boundary_BAA_count_path': boundary_path,
    'net_rates': {key:str(value) for key,value in {
        'battery':battery, 'capsule':capsule,'parts':parts,'dense_source':dense_source,
        'bottles':bottles,'fine_flower':fine_flower,'steel':steel,
        'blue_dust':blue_dust,'source_dust':source_dust,
        'flower_dust':flower_dust,'sand_dust':sand_dust,
        'flower_crush':flower_crush,'sand_crush':sand_crush,
        'base_crush':base_crush,'base_refine':base_refine,
    }.items()},
    'capacity_cases':capacity_cases,
    'kernel': {'compiled':False, 'loaded':False, 'stepped':False},
}
(HERE/'核算结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
