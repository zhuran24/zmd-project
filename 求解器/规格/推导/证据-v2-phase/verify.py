"""复算已读复核的全部算术，并核对本版矿含量账。不是整厂认证器。

只在本脚本所在目录写 JSON/LOG；不运行 kernel，不修改输入，不复制快照。
首次执行创建 replay-1、replay-2；再次执行检查已有结果，不覆盖复核证据。
"""
from pathlib import Path
from fractions import Fraction as F
import contextlib
import hashlib
import io
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DER = ROOT / '求解器/规格/推导'
DIALOGUE = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/786b1aaa-8792-43fd-afbc-2a7361543a07/scratchpad/总结/对话-0920-精简.md')
DIALOGUE_READ_SHA = 'ef0dc268fd3c06eaa1ea95fcda41022b2d51cf113ac30a34a4f715f6556efc8a'
MAIN_DIALOGUE = DIALOGUE.with_name('对话-0920-主线.md')
EXPECTED = {
    '《明日方舟：终末地》游戏规则.txt': 'abc7a5867f6477eedb619c63a21c4a77144c57ad4567fdcfb696b3049d66a670',
    '求解任务.txt': '1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac',
    '求解约束.txt': 'f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6',
    '候选约束.txt': 'a0ac3f9c82f371132b7de29fe47e4c6c587904680bc2786523de0c825fd5efd9',
}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

inputs = [ROOT / s for s in EXPECTED]
inputs += [DER / '三种相位不改产量.md', DER / '总纲-流量存量相位.md']
dialogue_record = {'path': str(DIALOGUE), 'sha256_at_initial_full_read': DIALOGUE_READ_SHA,
                  'lines_at_initial_full_read': 756, 'available_now': DIALOGUE.is_file(),
                  'quoted_owner_records': 'owner-quotes.md'}
if DIALOGUE.is_file():
    assert sha(DIALOGUE) == DIALOGUE_READ_SHA
    inputs.append(DIALOGUE)
else:
    # 精简稿在初读后已不在原路径。明记缺失，保留先前工具实读的哈希与引文。
    assert (HERE / 'owner-quotes.md').is_file()
    assert MAIN_DIALOGUE.is_file()
    inputs.append(MAIN_DIALOGUE)
inputs += [DER / '复核' / s for s in ['独立推导-相位-opus.md', '否证-相位-1.md', '否证-相位-2.md']]
inputs += [DER / '回路总数决定论.md']
for label in [1, 2]:
    inputs += sorted((DER / '复核' / f'否证-相位-{label}-证据').iterdir())
assert all(p.is_file() for p in inputs)
before = {str(p): sha(p) for p in inputs}
for name, expected in EXPECTED.items():
    assert before[str(ROOT / name)] == expected, name
write_json('sources.json', {'files': before, 'snapshot_copied': False,
                           'dialogue_initial_full_read': dialogue_record,
                           'opus_phase_separate_evidence_directory': None})

replays = []
for label, filename, products in [
    (1, 'check_traces.py', ['inputs.json', 'continuous_filler.json', 'three_fillers.json',
                          'gate_sliding_window.json', 'gate_intermittent.json',
                          'serial_gates.json', 'parts_backlog.json', 'checks.json', 'checks.log']),
    (2, '逐tick核算.py', ['输入与结果.json', '核算.log']),
]:
    source_dir = DER / '复核' / f'否证-相位-{label}-证据'
    script = source_dir / filename
    dest = HERE / f'replay-{label}'
    if not dest.exists():
        dest.mkdir()
        code = script.read_text()
        assert code.count('HERE = Path(__file__).resolve().parent') == 1
        assert code.count('ROOT = HERE.parents[4]') == 1
        code = code.replace('HERE = Path(__file__).resolve().parent', f'HERE = Path({str(dest)!r})')
        code = code.replace('ROOT = HERE.parents[4]', f'ROOT = Path({str(ROOT)!r})')
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            exec(compile(code, str(script), 'exec'), {'__file__': str(script), '__name__': '__main__'})
        (dest / 'execution.log').write_text(capture.getvalue())
    compared = []
    for name in products:
        assert (dest / name).read_bytes() == (source_dir / name).read_bytes(), (label, name)
        compared.append(name)
    replays.append({'seat': label, 'exact_original_script_with_only_output_and_root_paths_rebound': True,
                    'byte_identical_results': compared})

# 矿含量为（蓝铁矿，源矿）；在制的一批沿用投入的同一矿含量。
weights = {
    '源矿': (0, 1), '源石粉末': (0, 1), '致密源石粉末': (0, 2),
    '蓝铁矿': (1, 0), '蓝铁块': (1, 0), '蓝铁粉末': (1, 0),
    '致密蓝铁粉末': (2, 0), '钢块': (2, 0), '钢制零件': (2, 0), '钢质瓶': (4, 0),
    '荞花': (0, 0), '砂叶': (0, 0), '荞花种子': (0, 0), '砂叶种子': (0, 0),
    '荞花粉末': (0, 0), '砂叶粉末': (0, 0), '细磨荞花粉末': (0, 0),
    '高容谷地电池': (20, 30), '精选荞愈胶囊': (40, 0),
}
recipes = [
    (81, {'源矿': 1}, {'源石粉末': 1}), (82, {'蓝铁块': 1}, {'蓝铁粉末': 1}),
    (83, {'荞花': 1}, {'荞花粉末': 2}), (84, {'砂叶': 1}, {'砂叶粉末': 3}),
    (87, {'蓝铁矿': 1}, {'蓝铁块': 1}), (88, {'致密蓝铁粉末': 1}, {'钢块': 1}),
    (89, {'蓝铁粉末': 1}, {'蓝铁块': 1}),
    (92, {'蓝铁粉末': 2, '砂叶粉末': 1}, {'致密蓝铁粉末': 1}),
    (93, {'源石粉末': 2, '砂叶粉末': 1}, {'致密源石粉末': 1}),
    (94, {'荞花粉末': 2, '砂叶粉末': 1}, {'细磨荞花粉末': 1}),
    (97, {'钢块': 2}, {'钢质瓶': 1}), (100, {'钢块': 1}, {'钢制零件': 1}),
    (103, {'荞花种子': 1}, {'荞花': 1}), (104, {'砂叶种子': 1}, {'砂叶': 1}),
    (107, {'荞花': 1}, {'荞花种子': 2}), (108, {'砂叶': 1}, {'砂叶种子': 2}),
    (111, {'钢制零件': 10, '致密源石粉末': 15}, {'高容谷地电池': 1}),
    (114, {'钢质瓶': 10, '细磨荞花粉末': 10}, {'精选荞愈胶囊': 1}),
]
rule_lines = (ROOT / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
for line, left, right in recipes:
    for side, text in [(left, rule_lines[line-1].split('→')[0]), (right, rule_lines[line-1].split('→')[1])]:
        assert all(f'{n} {s}' in text for s, n in side.items())
    totals = [tuple(sum(n * weights[s][i] for s, n in side.items()) for i in [0, 1]) for side in [left, right]]
    assert totals[0] == totals[1], line
assert max(sum(w) for w in weights.values()) == 50
assert 50 * F(3, 5) + 40 * F(11, 20) == 52
assert F(3, 5) * 20 == 12 and F(11, 20) * 20 == 11
# 产率同时达标时：50(b-3/5)+40(c-11/20) <= 0；两项非负，只能都为0。
# 蓝铁块→粉末→块，两种配方各加r批不改物料净收支；不能推出总过货量唯一。
cycle_balance = {}
for line, left, right in recipes:
    if line in [82, 89]:
        for s, n in left.items(): cycle_balance[s] = cycle_balance.get(s, 0) - n
        for s, n in right.items(): cycle_balance[s] = cycle_balance.get(s, 0) + n
assert all(v == 0 for v in cycle_balance.values())
assert {str(p): sha(p) for p in inputs if p.is_file()} == before
write_json('checks.json', {
    'replays': replays, 'recipe_conservation_checked': len(recipes),
    'max_item_total_ore_weight': 50, 'target_ore_per_tick': '52',
    'battery_capsule_per_20_ticks': [12, 11],
    'blue_block_powder_extra_cycle_net_balance': cycle_balance,
    'input_hashes_unchanged': True, 'kernel_run': False,
    'whole_layout_certified': False, 'v2_independent_review_completed': False,
})
(HERE / 'verify.log').write_text('PASS: 两席原脚本复算结果逐字节相同；18条配方矿含量守恒；目标恰用52；额外蓝铁块/粉末循环净收支为零；所有输入哈希未变。\n未运行kernel，未认证整厂，未进行第二版独立复核。\n')
print((HERE / 'verify.log').read_text())
