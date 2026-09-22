"""按当前正式原文检查两份覆盖表及内核输入接口，不刷新历史指纹。"""
import hashlib
import json
import re
from pathlib import Path

out = Path(__file__).resolve().parent
solver = out.parents[1]
root = solver.parent
checks = []
for path in (solver / '规格/规则覆盖表.md', solver / '数据/规则覆盖表.md'):
    sections = path.read_text().split('## ')
    for section_index, filename, expected_count in ((1, '《明日方舟：终末地》游戏规则.txt', 114), (2, '求解任务.txt', 15)):
        rows = [line.split('|')[1:-1] for line in sections[section_index].splitlines() if re.match(r'^\| \d+ \|', line)]
        source = (root / filename).read_text().splitlines()
        assert len(rows) == len(source) == expected_count
        for index, (row, line) in enumerate(zip(rows, source), 1):
            assert int(row[0]) == index and row[1].strip() == (line.strip() or '（空行）')
            assert row[2].strip()
            if len(row) > 3:
                assert row[3].strip()
        checks.append({'table': str(path), 'source': filename, 'lines': len(rows), 'status': '逐行原文、序号与非空去向通过'})
    if path.parent.name == '规格':
        rows = [line.split('|')[1:-1] for line in sections[3].splitlines() if re.match(r'^\| \d+ \|', line)]
        source = [(i, line.split('：', 1)[0]) for i, line in enumerate((root / '求解约束.txt').read_text().splitlines(), 1) if '：' in line and not line.startswith(' ') and not line.endswith('：')]
        assert len(rows) == len(source) == 56
        for index, (row, (line, name)) in enumerate(zip(rows, source), 1):
            assert int(row[0]) == index and int(row[1]) == line and row[2].strip() == '约束·' + name
        checks.append({'table': str(path), 'source': '求解约束.txt', 'clauses': 56, 'status': '条款名和源行通过'})

record = (solver / '规格/内核输入-修订记录.md').read_text()
r2 = {'K-r2-L1-' + str(n) for n in (2, 3, 4)} | {'K-r2-L2-' + str(n).zfill(2) for n in range(1, 6)} | {'K-r2-L3-' + str(n).zfill(2) for n in (1, 2, 3, 4, 6, 7, 8, 9)}
r1 = {'K-r1-L1-' + str(n) for n in (1, 2, 3)} | {'K-r1-L2-' + str(n) for n in (1, 2, 3, 4)} | {'K-r1-L3-' + str(n).zfill(2) for n in range(1, 7)}
for expected, version in ((r2, 2), (r1, 1)):
    actual = re.findall(r'^\| (K-r' + str(version) + r'-L\d-\d+) \|', record, re.M)
    assert len(actual) == len(set(actual)) and set(actual) == expected
    checks.append({'round': version, 'findings': len(actual), 'status': '逐条处理或映射齐全'})

specification = solver / '规格/内核输入.md'
body = specification.read_text()
headings = set(re.findall(r'^#{2,3} (\d+(?:\.\d+)*)\.', body, re.M))
# 二级标题和三级标题的末尾格式不同，分别提取。
headings |= set(re.findall(r'^#{2,3} (\d+(?:\.\d+)*) ', body, re.M))
assert {'1', '1.1', '1.2', '2', '2.1', '2.2', '2.3', '3', '3.1', '3.2', '3.3', '4', '5', '5.1', '6', '6.1', '6.2', '7', '8', '9'} <= headings
for phrase in ('settings={switches,gates,warehouse_slots', '前序操作 id', 'construction_then_offline_events', '本表共有 87 个字段', 'product_withdrawal 为 Decision', '桥接器要在每个规范轴上找最早'):
    assert phrase not in body, phrase
for path in (specification, solver / '规格/内核输入-修订记录.md', solver / '规格/规则覆盖表.md', solver / '规格/选择点参数轴.md', solver / '规格/选择点清单.md'):
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        assert (path.parent / target.split('#')[0]).exists(), (path, target)
checks.append({'status': '现行接口的旧句、章节及本地链接检查通过'})
# 判别旧A线失败的时间归属，不能把本轮之前的契约修订算成保护失败。
old = json.loads((solver / '规格/第二轮任务修订前只读指纹.json').read_text())
before = json.loads((out / '修订前产物指纹.json').read_text())
stale = [name for name, digest in old.items() if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
assert all(before.get(name) != old[name] for name in stale)
checks.append({'historical_snapshot_differences': stale, 'status': '全部差异在本轮开工前已存在；旧快照与脚本未修改'})
print(json.dumps({'status': 'PASS', 'scope': '当前规则覆盖、16条本轮处理、13条前轮映射及接口引用；非语义完备证明', 'checks': checks}, ensure_ascii=False, indent=2))
