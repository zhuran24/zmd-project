#!/usr/bin/env python3
"""任务4容量修订的定向作者核验；读取原始见证，写本席JSON，不执行游戏内核。"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re

E = Path(__file__).resolve().parent
O = E.parent.parent
ROOT = O.parents[2]


def read(p):
    return json.loads(p.read_text())


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def record(p):
    b = p.read_bytes()
    return dict(path=str(p), sha256=hashlib.sha256(b).hexdigest(), bytes=len(b),
                lines=len(b.splitlines()), mtime_ns=p.stat().st_mtime_ns)


baseline = read(E/'修订前指纹.json')
for item in baseline['read_only_inputs']:
    assert record(Path(item['path'])) == item, item['path']

data = read(O/'送料与接口.json')
arithmetic = read(E/'算术与图核验.json')
dispositions = read(E/'否证逐项处理.json')
assert data['schema'] == 'plant-pilot-v2'

# 对两普通格枚举同一种种子的所有容量内状态；R13要求同种至多占一格。
single_kind_states = [(a, b) for a in range(51) for b in range(51) if not (a and b)]
assert len(single_kind_states) == 101
assert max(a+b for a, b in single_kind_states) == 50
assert (50, 0) in single_kind_states

# 逐格核否证席见证，清点实际机器输入；不执行或重写否证席脚本和文件。
witness_path = O/'证据/否证/任务4/容量反例合法摆放.json'
witness = read(witness_path)
occupied = {}
species_counts = Counter()
machine_kinds = Counter()
for unit in witness['units']:
    for x in range(unit['x'], unit['x']+unit['w']):
        for y in range(unit['y'], unit['y']+unit['h']):
            assert 0 <= x < 70 and 0 <= y < 70
            assert (x, y) not in occupied, (x, y)
            occupied[x, y] = unit['id']
    if unit['kind'] == '协议核心':
        assert (unit['w'], unit['h']) == (9, 9)
        continue
    assert unit['kind'] in {'种植机', '采种机', '粉碎机'}
    assert (unit['w'], unit['h']) == ((3, 3) if unit['kind']=='粉碎机' else (5, 5))
    assert unit['switch'] == 'off' and unit['output_inventory'] == {} and unit['cache'] == {}
    assert len(unit['input_inventory']) == 1
    item, count = next(iter(unit['input_inventory'].items()))
    assert item in {'荞花种子', '砂叶种子'} and count == 50
    species = item[:-2]
    species_counts[species] += count
    machine_kinds[species, unit['kind']] += 1
assert len(witness['units']) == 67
assert species_counts == {'荞花': 1150, '砂叶': 2150}

computed = {}
for species, counts, powder_batch in [('荞花', (11, 6, 6), 2), ('砂叶', (21, 11, 11), 3)]:
    p, h, g = counts
    assert tuple(machine_kinds[species, kind] for kind in ('种植机', '采种机', '粉碎机')) == counts
    # 独立按每台槽位和配方最大阶段累加，避免复制生成器中的聚合算式。
    physical_seed = normal_seed = ordinary_n = cache_n = all_ordinary = all_cache = 0
    for kind, number in zip(('P', 'H', 'G'), counts):
        for _ in range(number):
            physical_seed += 50
            all_ordinary += 100
            normal_slots = {'P': ('seed', 'plant'), 'H': ('plant', 'seed'), 'G': ('plant', 'powder')}[kind]
            normal_seed += 50*normal_slots.count('seed')
            ordinary_n += sum(50 for slot in normal_slots if slot in {'seed', 'plant'})
            cache_n += {'P': 1, 'H': 2, 'G': 1}[kind]
            all_cache += {'P': 1, 'H': 2, 'G': powder_batch}[kind]
    expected = dict(ordinary_seeds=physical_seed, ordinary_seeds_normal_recipe_slots=normal_seed,
                    ordinary_all_materials=all_ordinary, ordinary_plants=50*sum(counts),
                    ordinary_seed_plus_plant=ordinary_n, reachable_normal_cache_all_materials=all_cache,
                    reachable_normal_cache_seed_plus_plant=cache_n,
                    seed_plus_plant_with_normal_cache=ordinary_n+cache_n)
    for key, value in expected.items():
        assert data['inventory'][species][key] == value, (species, key)
    assert physical_seed == species_counts[species]
    computed[species] = expected
assert sum(x['ordinary_seeds'] for x in computed.values()) == 3300
assert sum(x['ordinary_seeds_normal_recipe_slots'] for x in computed.values()) == 2450
assert sum(x['seed_plus_plant_with_normal_cache'] for x in computed.values()) == 5833
assert sum(x['ordinary_all_materials']+x['reachable_normal_cache_all_materials'] for x in computed.values()) == 6711
assert data['inventory'] == arithmetic['capacities_219']
assert data['inventory_definitions'] == arithmetic['inventory_definitions']
assert data['local_geometry']['normal_seed_plus_plant_capacity'] == 100+100+50+1+2+1+23 == 277
assert 'normal_recipe_slots' in data['local_geometry']['capacity_scope']
assert data['other_configurations'][0]['inventory_scope']
assert 32*100+16*100+32+16*2+16*(50+1) == 5680

# 原定理、候选438台/629条记录逐字义保持；只允许本轮明示的范围/登记变化。
changed_old_keys = {'schema', 'inventory', 'local_geometry', 'other_configurations', 'open_items'}
for key, old_digest in baseline['interface_top_level_digests'].items():
    if key not in changed_old_keys:
        assert digest(data[key]) == old_digest, key
for key, old_digest in baseline['arithmetic_top_level_digests'].items():
    if key != 'capacities_219':
        assert digest(arithmetic[key]) == old_digest, key
assert data['default_start_certified'] is False and data['full_layout_certified'] is False
assert data['L'] == 0 and data['U'] == 1113 and data['status'] == 'partial'
for candidate in data['candidates']:
    assert all(feed['proven_actual_rate_per_tick'] is None for feed in candidate['feeds'])
    assert all(recipe['proven_actual_batches_per_tick'] is None for machine in candidate['machines'] for recipe in machine['recipes'])

assert [f['id'] for f in dispositions['findings']] == [f'F{i:02d}' for i in range(1, 19)]
assert Counter(f['verdict'] for f in dispositions['findings']) == {'否证成立': 1, '否证不成立': 14, '无法判定': 3}
assert all(f['agree'] for f in dispositions['findings'])
assert [f['id'] for f in dispositions['findings'] if f['verdict']=='否证成立'] == ['F13']
assert {x['id'] for x in data['open_items']} == {f'PR-{i:02d}' for i in range(1, 8)}
assert all(x['status']=='unproved' and x['missing_category']=='缺构造与推导' for x in data['open_items'])
assert data['for_owner'] == dispositions['for_owner'] == []
assert data['review_status']['report_sha256'] == record(O/'复核/否证-任务4.md')['sha256']

# 未修改的旧证据保持完整字节和mtime，历史失败日志继续作为史料。
old_changed = {'植物运行试点.md', '送料与接口.json', '提取与算术.py', '核验.py',
               '算术与图核验.json', '核验结果.json', '读者自审.md', '交付清单.json'}
preserved = []
for item in baseline['prior_files']:
    p = Path(item['path'])
    if p.name not in old_changed:
        assert record(p) == item, p
        preserved.append(str(p))

# AST编译只在内存检查语法，无pyc文件。
for p in E.glob('*.py'):
    compile(p.read_text(), str(p), 'exec')

md = (O/'植物运行试点.md').read_text()
assert all(f'| F{i:02d} ' in md.split('## 10. 修订记录')[1] for i in range(1, 19))
assert '| 荞花 | 11/6/6 | 2300 | 1150 | 1150 |' in md
assert '| 荞花 | 11/6/6 | 2300 | 850 | 1150 | 35 | 2029 |' in md
missing_links = []
for p in [O/'植物运行试点.md', E/'读者自审.md', E/'逐机逐口清单.md']:
    for target in re.findall(r'\]\(([^)]+)\)', p.read_text()):
        if '://' not in target and not target.startswith('#'):
            resolved = (p.parent/target.split('#')[0]).resolve()
            # 本命令结束时写出的结果本身；其余链接当前均须已存在。
            if resolved != E/'修订核验结果.json' and not resolved.exists():
                missing_links.append(str(resolved))
assert not missing_links, missing_links

result = dict(status='PASS', scope='作者修订定向核验；实际游戏转移及修订后独立重核分别按交付范围保留',
              command='python -B '+str(Path(__file__).resolve()), exit_status=0,
              read_only_inputs_matched=len(baseline['read_only_inputs']),
              protected_sources=[record(ROOT/name) for name in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt']],
              single_kind_ordinary_states_checked=len(single_kind_states),
              witness_units=67, witness_machine_count=66, witness_unexpected_overlap=0,
              capacities=computed, ordinary_seed_physical_total=3300, normal_recipe_seed_total=2450,
              normal_N_total=5833, normal_all_materials_total=6711,
              unchanged_candidates=dict(machines=438, feeds=629), conditional_guarantees_unchanged=True,
              preserved_old_files=preserved, findings=dict(accepted=18, upheld=1, not_upheld=14, undecided=3),
              open_items=7, independent_recheck='pending', links_checked=True, for_owner=[], L=0, U=1113,
              修订记录=[dict(date='2026-09-21', finding='F13/F14', change='逐格重核既有容量见证；分别核普通物理种子与正常配方槽位、缓存和联合N，保持其他候选及定理字段。'),
                        dict(date='2026-09-21', finding='F01/F16—F18', change='核输入指纹、18项处理及7项未证登记；修订后独立复核仍待交。')])
(E/'修订核验结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print('PASS: 24份只读输入（含三份正式文件、候选约束）字节与mtime保持；66机容量见证无重叠。')
print('PASS: 普通种子物理上限1150/2150，正常槽位850/1600；5833/6711/277/5680保留正常域。')
print('PASS: 438台机器、629条边、4项条件定理与旧版数据逐字段一致；18项处理齐全，7项保持未证。')

# 修订记录
# 2026-09-21 新增F13/F14定向作者核验，读取既有否证容量见证、检查所有改动数据和证据范围。
# 输出仅为修订核验结果.json；未触及模拟器，未使用版本控制命令，未调用编译器或游戏内核。
