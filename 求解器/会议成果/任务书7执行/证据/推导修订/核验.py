#!/usr/bin/env python3
"""任务3修订交付检查：文本、版本及必要算术；不执行游戏转移。"""
from pathlib import Path
from hashlib import sha256
from fractions import Fraction as F
import json
import re

BASE = Path('/home/zhuran24/zmd-research-fresh')
EVIDENCE = Path(__file__).resolve().parent
REPORT = BASE / '求解器/会议成果/任务书7执行/推导复核范围.md'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def reverse_diff(new, patch):
    """在内存中逆转差异，以验证原指纹；不写修订前正文副本。"""
    lines, changes = new.splitlines(True), patch.splitlines(True)
    out, cursor, index = [], 0, 0
    while index < len(changes):
        m = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', changes[index])
        if not m:
            index += 1
            continue
        start_new, count_new = int(m[3]), int(m[4] or '1')
        start = start_new - 1 if count_new else start_new
        assert start >= cursor
        out.extend(lines[cursor:start])
        old_part, new_part = [], []
        index += 1
        while index < len(changes) and not changes[index].startswith('@@'):
            item = changes[index]
            if item.startswith((' ', '+')):
                new_part.append(item[1:])
            if item.startswith((' ', '-')):
                old_part.append(item[1:])
            index += 1
        assert len(new_part) == count_new
        assert lines[start:start + len(new_part)] == new_part
        out.extend(old_part)
        cursor = start + len(new_part)
    out.extend(lines[cursor:])
    return ''.join(out)


def main():
    (EVIDENCE / '核验结果.json').write_text('{"status":"running"}\n')
    inputs = json.loads((EVIDENCE / '输入指纹.json').read_text())
    verdicts = json.loads((EVIDENCE / '裁定处理.json').read_text())
    report = REPORT.read_text()
    readonly = []
    for item in inputs['readonly']:
        path = Path(item['path'])
        actual = digest(path)
        assert actual == item['sha256'], ('只读输入发生变化', str(path), actual)
        readonly.append({'path': str(path), 'sha256': actual, 'unchanged': True})

    diffs = dict(re.findall(r'## ([^\n]+)\n\n```diff\n(.*?)```\n',
                            (EVIDENCE / '修订差异.md').read_text(), re.S))
    assert len(diffs) == 3
    current, originals, outputs = {}, {}, []
    for item in inputs['manuscripts_before']:
        path = Path(item['path'])
        content = path.read_text()
        original = reverse_diff(content, diffs[path.name])
        assert sha256(original.encode()).hexdigest() == item['sha256']
        assert len(original.splitlines()) == item['lines']
        actual = digest(path)
        assert item['sha256'] in report and actual in report
        current[path.name] = content
        originals[path.name] = original
        outputs.append({'path': str(path), 'sha256': actual,
                        'lines': len(content.splitlines()), 'before': item['sha256']})

    expected_ids = ({'L-E01', 'L-E02', 'P-E01', 'P-U05', 'G-U01', 'G-U02'}
                    | {f'L-N{i:02}' for i in range(1, 9)}
                    | {f'L-U{i}' for i in range(1, 9)}
                    | {f'P-N{i:02}' for i in range(1, 6)}
                    | {f'G-N{i:02}' for i in range(1, 22)})
    ids = [row['id'] for row in verdicts['rows']]
    assert len(ids) == len(set(ids)) == 48
    assert set(ids) == expected_ids
    assert all(f'| {i} |' in report for i in expected_ids)
    assert verdicts['disagreements'] == []

    loop = current['回路总数决定论-v2.md']
    phase = current['三种相位不改产量-v2.md']
    outline = current['总纲-流量存量相位.md']
    assert phase.splitlines()[2] == inputs['preserved_phase_line3']
    assert inputs['preserved_phase_item7'] in phase.splitlines()
    phase_old_hashes = json.loads((BASE / '求解器/规格/推导/证据-v2-phase-否证/input_hashes.json').read_text())
    phase_path = str(BASE / '求解器/规格/推导/三种相位不改产量-v2.md')
    old_phase_hash = phase_old_hashes[phase_path]
    assert old_phase_hash == '51327afa43a98af4a002f1e98f25561159a3855fe8240c77863dc4ab66324753'
    assert old_phase_hash in inputs['preserved_phase_line3']
    assert old_phase_hash in inputs['preserved_phase_item7']
    assert old_phase_hash in (BASE / '求解器/会议成果/会议2成果修订-v46.md').read_text()
    assert '包括整批传输可接收' not in loop
    assert '主会话三审 L23 应按下表替换' not in loop
    boundary = next(line for line in loop.splitlines() if line.startswith('| 成品边界与目标 |'))
    assert boundary.count('|') == 4
    assert '仓库收得下成品' in boundary and '能送多少送多少' in boundary
    assert '31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff' in loop
    assert '31ced2a24fef' in next(line for line in phase.splitlines() if line.startswith('| 规则 |'))
    assert '本次修订文字待独立复核' in loop
    assert '新文字待独立复核' in phase
    assert '本次重写文字待独立复核' in outline
    assert '## §8 任务3修订记录' in loop
    assert '## §7 任务3修订记录' in phase
    assert '## 7. 任务3修订记录' in outline
    assert '所选认证路线的完整转移、时间表示及循环对应' in phase
    assert '全部执行最终必进循环' in phase and '实际使用' in phase
    assert '粉碎恰68台或精炼恰51台' in outline
    assert '68+r' in outline and '51+r' in outline and 'A=1113' in outline
    assert 'G-U01：全送料表及逐机分担唯一性，缺推导' in outline
    assert 'G-U02：植物充分存量集合，缺推导' in outline
    assert '库存删减交任务6' in outline and '相位和状态判等的删减交任务6' in outline

    # 正式行号与关键引文直接在现行文件中核对。
    rules = (BASE / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
    task = (BASE / '求解任务.txt').read_text().splitlines()
    constraints = (BASE / '求解约束.txt').read_text().splitlines()
    for line, quote in [(36, '能送多少送多少，5 tick 冷却'), (82, '1 蓝铁块 → 1 蓝铁粉末'),
                        (89, '1 蓝铁粉末 → 1 蓝铁块'), (18, '上一批已全部进入取货物品格')]:
        assert quote in rules[line - 1]
    assert '粉碎机、精炼炉、配件机、种植机、采种机、封装机' in constraints[49]
    assert '故 A=1113 时九机型恰为下限' in constraints[112]
    assert '基地的状态以固定周期重复' in task[9]

    # 只核本次重述的算术与同义改写，历史轨迹及局部枚举未重放。
    battery, capsule = F(3, 5), F(11, 20)
    parts, bottles = 10 * battery, 10 * capsule
    steel = parts + 2 * bottles
    dense_source, fine_buckwheat = 15 * battery, 10 * capsule
    blue_powder, source_powder, buckwheat_powder = 2 * steel, 2 * dense_source, 2 * fine_buckwheat
    sand_powder = steel + dense_source + fine_buckwheat
    crushing_base = source_powder + blue_powder + buckwheat_powder / 2 + sand_powder / 3
    refining_base = blue_powder + steel
    assert 50 * battery + 40 * capsule == 52
    assert crushing_base == 68 and refining_base == 51
    assert [2 * 16 + 48 * m for m in (0, 1, 16)] == [32, 80, 800]
    safe_d = [d for d in range(-200, 201) if -99 < -50 + d < 50]
    assert safe_d == list(range(-48, 100))
    rotations = {}
    for word in ('AAB', 'ABA', 'BAA'):
        d, prefix = 0, [0]
        for letter in word:
            d += 1 if letter == 'A' else -2
            prefix.append(d)
        assert d == 0 and all(-99 < -50 + q < 50 for q in prefix)
        rotations[word] = [min(prefix), max(prefix)]

    # 核新加和改动行中的文件链接；保留旧链接的问题单列，不混称全量已修。
    links_checked, inherited_missing = [], []
    docs = [(Path(item['path']), current[Path(item['path']).name], originals[Path(item['path']).name])
            for item in inputs['manuscripts_before']]
    docs.append((REPORT, report, ''))
    for path, content, old in docs:
        old_links = set(re.findall(r'\]\(([^)]+)\)', old))
        for target in set(re.findall(r'\]\(([^)]+)\)', content)):
            if target.startswith(('https:', 'http:', '#')):
                continue
            resolved = (path.parent / target.split('#')[0]).resolve()
            if not resolved.exists():
                if target in old_links:
                    inherited_missing.append({'file': str(path), 'target': target})
                else:
                    raise AssertionError(('新增链接缺失', str(path), target))
            else:
                links_checked.append({'file': str(path), 'target': target})

    result = {'status': 'passed', 'verification_kind': '修订席自核，非独立复核或运行认证',
              'readonly': readonly, 'manuscripts': outputs, 'verdict_ids': sorted(ids),
              'phase_line3_and_item7_byte_equal': True,
              'phase_old_review_input_sha256': old_phase_hash,
              'reverse_diff_restores_before_hashes': True,
              'arithmetic': {'crushing_base': str(crushing_base), 'refining_base': str(refining_base),
                             'safe_integer_D': [min(safe_d), max(safe_d)], 'rotations': rotations},
              'links_checked': len(links_checked), 'inherited_missing_links': inherited_missing,
              'kernel_compiled': False, 'kernel_loaded': False, 'kernel_steps': 0,
              'remaining_proof_gaps_closed': [], 'L': 0, 'U': 1113}
    (EVIDENCE / '核验结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'PASS：{len(readonly)}份只读输入指纹保持；三份正文差异逆算恢复原指纹。')
    print('PASS：48个裁定编号完整且唯一；汇总中的新旧正文指纹与磁盘一致。')
    print('PASS：相位第3行及§4第7项逐字保留，旧审指纹与输入JSON、v46一致。')
    print('PASS：当前来源、接收边界、历史三审引用、默认起法及认证路线文字核对通过。')
    print('PASS：矿预算52、粉碎68+r、精炼51+r、首次清出32/80/800、D界及三轮相算术通过。')
    print(f'PASS：{len(links_checked)}个文件链接目标存在；继承的失效旧链接{len(inherited_missing)}个。')
    print('范围：未编译/装载/步进内核；旧算例未重放；U1—U7及其他证明缺口保持；新文字待独立复核。')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        (EVIDENCE / '核验结果.json').write_text(json.dumps(
            {'status': 'failed', 'error': repr(error)}, ensure_ascii=False, indent=2) + '\n')
        raise
