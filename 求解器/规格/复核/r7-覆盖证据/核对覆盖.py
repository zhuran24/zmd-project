"""第7轮覆盖席独立核对；只写本复核证据目录，不改被审产物。"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re

ROOT = Path('/home/zhuran24/zmd-research-fresh')
BASE = Path(__file__).resolve().parent
SPEC = ROOT / '求解器/规格'
TASK = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def axis_rows(path):
    rows = []
    for line in path.read_text().splitlines():
        if re.match(r'^\| `[a-z_]+\.[a-z_]+` \|', line):
            rows.append([part.strip() for part in line.split('|')[1:-1]])
    names = [row[0].strip('`') for row in rows]
    assert len(names) == len(set(names))
    return dict(zip(names, rows))


def main():
    report = {'scope': '逐行文本、登记集合、指纹及现有证据范围；语义逐条判断另见复核报告'}
    coverage = (SPEC / '规则覆盖表.md').read_text()
    sections = re.split(r'^## ', coverage, flags=re.M)
    source_rows = {}
    for index, name, count in [(1, '《明日方舟：终末地》游戏规则.txt', 114), (2, '求解任务.txt', 15)]:
        lines = (ROOT / name).read_text().splitlines()
        rows = [[part.strip() for part in line.split('|')[1:-1]]
                for line in sections[index].splitlines() if re.match(r'^\| \d+ \|', line)]
        assert len(rows) == len(lines) == count
        result = []
        for number, (line, row) in enumerate(zip(lines, rows), 1):
            assert int(row[0]) == number
            assert row[1] == (line.strip() or '（空行）')
            assert row[2] and row[3]
            result.append({'line': number, 'source': line, 'destination': row[2], 'coverage_note': row[3]})
        source_rows[name] = result
    report['line_counts'] = {name: len(rows) for name, rows in source_rows.items()}
    (BASE / '逐行入口.json').write_text(json.dumps(source_rows, ensure_ascii=False, indent=2) + '\n')

    # 从正式配方行独立取机型、公式、时长，再与规格配方表比较。
    machine_names = {'粉碎机', '精炼炉', '研磨机', '塑形机', '配件机', '种植机', '采种机', '封装机', '灌装机'}
    official_recipes = []
    current_machine = None
    for line in (ROOT / '《明日方舟：终末地》游戏规则.txt').read_text().splitlines()[78:]:
        if line.strip() in machine_names:
            current_machine = line.strip()
        match = re.fullmatch(r'(.+)，(\d+) tick', line.strip())
        if match:
            official_recipes.append((current_machine, re.sub(r'\s+', '', match[1]), int(match[2])))
    text = (SPEC / '运行语义.md').read_text()
    projected_recipes = [(kind, re.sub(r'\s+', '', formula), int(duration))
                         for _, kind, formula, duration in re.findall(r'^\| `([^`]+)` \| `([^`]+)` \| (.*?) \| (\d+) \|$', text, re.M)]
    assert Counter(official_recipes) == Counter(projected_recipes)
    report['recipes_from_formal_source'] = len(official_recipes)

    official_constraints = [(number, line.split('：', 1)[0])
                            for number, line in enumerate((ROOT / '求解约束.txt').read_text().splitlines(), 1)
                            if '：' in line and not line.startswith(' ') and not line.endswith('：')]
    constraint_rows = [[part.strip() for part in line.split('|')[1:-1]]
                       for line in sections[3].splitlines() if re.match(r'^\| \d+ \|', line)]
    assert len(official_constraints) == len(constraint_rows) == 56
    for index, ((number, name), row) in enumerate(zip(official_constraints, constraint_rows), 1):
        assert row[:3] == [str(index), str(number), '约束·' + name]
    report['formal_constraint_count'] = 56

    axes = axis_rows(SPEC / '选择点参数轴.md')
    profile = axis_rows(SPEC / '受限模型声明.md')
    inputs = axis_rows(SPEC / '内核输入.md')
    config = load(SPEC / '内核配置-v1.json')
    assert set(axes) == set(profile) == set(inputs) == set(config['axes'])
    assert len(axes) == config['axis_count'] == 99
    for field, row in axes.items():
        assert row[3] in inputs[field][2]
        entry = config['axes'][field]
        assert profile[field][1] == entry['disposition']
        assert json.dumps(entry['value'], ensure_ascii=False, separators=(',', ':')) in profile[field][2]
        assert profile[field][4] == entry['coverage_loss']
        assert profile[field][5] == entry['extension_gate']
    report['axis_count'] = 99
    report['axis_dispositions'] = dict(Counter(row[1] for row in profile.values()))
    report['all_input_descriptions_match_axis_table'] = True
    critic = (SPEC / '复核/完整性批评-2.md').read_text().split('## 附录：')[1]
    missing_axes = set(re.findall(r'`([a-z_]+\.[a-z_]+)`', critic))
    assert len(missing_axes) == 43 and missing_axes <= set(profile)
    report['previously_missing_axes_now_registered'] = sorted(missing_axes)

    state = load(TASK / 'round3_state.json')
    findings = state['aFindings']
    dispositions = load(SPEC / '第三轮任务验证/发现处置.json')
    assert len(findings) == len(dispositions) == 28
    assert {row['id'] for row in findings} == {row['id'] for row in dispositions}
    saved_findings = load(SPEC / '第三轮任务验证/任务发现输入.json')['aFindings']
    assert {row['id']: row for row in findings} == {row['id']: row for row in saved_findings}
    record_ids = re.findall(r'^\| (S2-r[45]-L\d-\d+) \|', (SPEC / '修订记录.md').read_text(), re.M)
    assert Counter(record_ids) == Counter(row['id'] for row in findings)
    report['old_findings_count'] = 28
    report['critic_missing_count'] = len(state['critic']['missing'])
    (BASE / '原始欠账与完整性批评.json').write_text(json.dumps({'aFindings': findings, 'critic_missing': state['critic']['missing']}, ensure_ascii=False, indent=2) + '\n')
    for name in ['任务书3.md', '任务书.md', '任务书2.md']:
        (BASE / name).write_bytes((TASK / name).read_bytes())

    # 指纹清单完整读取；只输出数量和差异，避免打印数万路径。
    revision = SPEC / '第6轮修订验证'
    for name in ['交付指纹.json', '开工只读指纹.json']:
        fingerprints = load(revision / name)
        changed = [path for path, value in fingerprints.items() if not Path(path).is_file() or digest(Path(path)) != value]
        report[name] = {'count': len(fingerprints), 'changed': changed}
        assert not changed
    product_start = load(revision / '开工产物指纹.json')
    report['start_product_fingerprint_count'] = len(product_start)
    assert all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) for value in product_start.values())
    report['delivery_list_count'] = len(load(revision / '交付文件清单.json'))
    assert all(Path(path).is_file() for path in load(revision / '交付文件清单.json'))
    snapshot = load(BASE / '开工指纹.json')
    changes = [entry['path'] for entry in snapshot['files'] if digest(ROOT / entry['path']) != entry['sha256']]
    assert not changes
    report['reviewed_snapshot_count'] = len(snapshot['files'])
    report['changes_since_review_start'] = changes

    checks = {}
    for name in ['规格自查', '原转移回归', '本轮局部回归', '当前样例黄金只读核验']:
        result = load(BASE / (name + '.json'))
        assert result['status'] == 'PASS'
        checks[name] = {'status': result['status'], 'checks': len(result.get('checks', []))}
    report['rerun'] = checks
    current_record = load(ROOT / '求解器/数据/样例/混做粉碎机两下游-运行记录.json')
    report['runtime_record_scope'] = current_record['validation_scope']
    report['runtime_axis_coverage'] = dict(Counter(row['coverage_status'] for row in current_record['uncovered_axes']))
    assert len(current_record['uncovered_axes']) == 99
    assert not any(current_record['validation_scope'][key] for key in ['universal_parameters', 'all_reachable_cycles', 'target_certified'])
    report['runtime_ticks'] = [row['time'] for row in current_record['trace']['ticks']]
    report['cargo_log_results'] = re.findall(r'^test result:.*$', (revision / 'cargo-test.log').read_text(), re.M)
    candidate_report = (revision / '候选B校验报告.md').read_text()
    report['candidate_report_sections'] = re.findall(r'^## .*$', candidate_report, re.M)
    report['status'] = 'PASS'
    (BASE / '独立核对结果.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'axis_count': 99, 'old_findings': 28, 'source_lines': report['line_counts'], 'output': str(BASE / '独立核对结果.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
