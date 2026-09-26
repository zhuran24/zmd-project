"""核对修订交付物的覆盖、引用与只读文件指纹；不证明语义完备。"""
import hashlib
import json
import re
from pathlib import Path

spec_dir = Path(__file__).resolve().parent
root = spec_dir.parent.parent
coverage = (spec_dir / '规则覆盖表.md').read_text()
semantics = (spec_dir / '运行语义.md').read_text()
choices = (spec_dir / '选择点清单.md').read_text()
records = (spec_dir / '修订记录.md').read_text()
results = []


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    results.append(label)


# 逐行比较原文，防止只计数而漏掉或错配行号。
sections = coverage.split('## ')
for section_index, filename, count in [(1, '《明日方舟：终末地》游戏规则.txt', 114), (2, '求解任务.txt', 16)]:
    rows = [line.split('|')[1:-1] for line in sections[section_index].splitlines() if re.match(r'^\| \d+ \|', line)]
    source = (root / filename).read_text().splitlines()
    check(len(rows) == len(source) == count, f'{filename}：{count} 行覆盖')
    for index, (row, line) in enumerate(zip(rows, source), 1):
        assert int(row[0]) == index
        assert row[1].strip() == (line.strip() or '（空行）'), (filename, index)
        assert row[2].strip() and row[3].strip()
    results.append(f'{filename}：逐行原文、序号及去向一致')

constraint_lines = (root / '求解约束.txt').read_text().splitlines()
expected = [(i, line.split('：', 1)[0]) for i, line in enumerate(constraint_lines, 1) if '：' in line and not line.startswith(' ') and not line.endswith('：')]
rows = [line.split('|')[1:-1] for line in sections[3].splitlines() if re.match(r'^\| \d+ \|', line)]
check(len(expected) == len(rows) == 77, '正式约束 77 条覆盖')
for index, (row, (source_line, name)) in enumerate(zip(rows, expected), 1):
    assert int(row[0]) == index and int(row[1]) == source_line
    assert row[2].strip() == '约束·' + name
results.append('正式约束：条款名与源行一致')

fingerprints = json.loads((spec_dir.parent / '内核维护/2026-09-26-第84-85轮三审同步/只读文件指纹.json').read_text())
# 正式源与候选为只读；K线活动源码只记录当前字节，不冻结旧轮实现。
protected_names = {'《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt'}
protected_fingerprints = {path: digest for path, digest in fingerprints.items() if Path(path).parent == root and Path(path).name in protected_names}
check(len(protected_fingerprints) == 4 and all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in protected_fingerprints.items()), '三份正式文件与候选约束4份只读指纹未变')
shared_dependency_fingerprints = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in fingerprints if path not in protected_fingerprints}
shared_dependency_changes = [path for path, digest in shared_dependency_fingerprints.items() if digest != fingerprints[path]]
for filename in ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']:
    assert hashlib.sha256((root / filename).read_bytes()).hexdigest() in semantics
results.append('运行语义中的正式源快照一致')
expected_ids = {f'S-r1-L{seat}-{item:02d}' for seat, items in [(1, [2,3,4,5,7,8]), (2, [1,2,3,5,6]), (3, [2,3,6,7,9,10])] for item in items}
record_ids = re.findall(r'^\| (S-r1-L\d-\d+) \|', records, re.M)
check(set(record_ids) == expected_ids and len(record_ids) == 17, '17 条发现逐条登记且无重复')
expected_revision_ids = {f'S-r2-L{seat}-{item:02d}' for seat, items in [(1, [1,2,3,4]), (2, [1,3]), (3, [1,2,3,5])] for item in items}
revision_ids = re.findall(r'^\| (S-r2-L\d-\d+) \|', records, re.M)
check(set(revision_ids) == expected_revision_ids and len(revision_ids) == 10, '第2轮 10 条发现逐条登记且无重复')
# 仅复核条件算术，不能把数字检查当作运行语义证明。
from fractions import Fraction
from math import ceil
input_rates = [Fraction(value) for value in ['68','51','94.5','11','6','32','16','15','11']]
areas = [9,9,24,9,9,25,25,24,24]
check(sum(input_rates) == Fraction('304.5') and sum(ceil(rate)*area for rate, area in zip(input_rates, areas)) == 5328 > 4900, 'H 下制造输入及占地条件算术通过')
check(46 + 1 == 47 < 52 and 6 > 1, 'H 下核心六口及出库条件算术通过')
choice_ids = set(re.findall(r'^## (T\d+)\.', choices, re.M))
check(choice_ids == {f'T{i}' for i in range(1, 18) if i != 13}, 'T1–T12、T14–T17 存在且无已删除T13')
for filename in ['运行语义.md', '选择点清单.md', '四件前置义务对照.md', '规则覆盖表.md', '选择点参数轴.md', '受限模型声明.md']:
    content = (spec_dir / filename).read_text()
    assert set(re.findall(r'\bT\d+\b', content)) <= choice_ids
    for target in re.findall(r'\]\(([^)]+\.md)\)', content):
        assert (spec_dir / target).exists(), target
    assert not re.search(r'\|\n\n\|', content), filename
results.append('六正文选择点编号、文件链接与表格连续性通过')
for phrase in ['同一机器同侧的多条通道则可以承担多件/tick', '匹配一批配方用量、上一批', '每对存取方向由先接端决定', '运行中制造/传输冷却进度推进，停用保留', '同侧总共一件的排除只写在相应满载机器条件下', '当前未证合法也未证排除', '既非已排除项，也非已准许项', '满足两端适用轮询及优先级', '桥接器另一对端口仍独立']:
    assert all(phrase not in (spec_dir / name).read_text() for name in ['运行语义.md', '选择点清单.md', '四件前置义务对照.md', '规则覆盖表.md', '选择点参数轴.md', '受限模型声明.md']), phrase
results.append('已定位旧断言无正文残留（仅字符串检查）')
# 目标小节内容检查覆盖已定位的陈旧指针；不宣称通用语义蕴含检查。
def section_map(content):
    headings = list(re.finditer(r'^#{2,3} (\d+(?:\.\d+)*)\.? ', content, re.M))
    return {match.group(1): content[match.end():headings[index+1].start() if index+1 < len(headings) else len(content)] for index, match in enumerate(headings)}

semantic_sections = section_map(semantics)
for row in coverage.splitlines():
    if re.match(r'^\| \d+ \|', row):
        destination = row.split('|')[-2] if '约束·' in row.split('|')[3] else row.split('|')[3]
        for number in re.findall(r'§(\d+(?:\.\d+)*)', destination):
            assert number in semantic_sections, (number, row)
results.append('覆盖表所有显式目标小节均存在（不证明条款已落地）')


def validate_feed_destination(table):
    row = next(line for line in table.splitlines() if '| 约束·研磨进料 |' in line)
    destination = re.search(r'§(\d+(?:\.\d+)*)', row).group(1)
    body = semantic_sections[destination]
    assert '约束·研磨进料' in body
    for phrase in ['研磨机恰 32 台', '至少 31 台', '至少 3 条存货通道', '采种机恰 16 台', '每台至少 2 条取货通道', '塑形机恰 6 台', '至少 5 台', '至少 2 条存货通道']:
        assert phrase in body, phrase

validate_feed_destination(coverage)
results.append('研磨进料去向节包含条款名及三个条件结论')
feed_row = next(line for line in coverage.splitlines() if '| 约束·研磨进料 |' in line)
mutated_coverage = coverage.replace(feed_row, re.sub(r'§6', '§4.3', feed_row))
try:
    validate_feed_destination(mutated_coverage)
except AssertionError:
    results.append('负例通过：研磨进料去向退回旧§4.3会被拒绝（内存变异，无文件改写）')
else:
    raise AssertionError('陈旧指针未被拒绝')

expected_third_ids = {f'S-r3-L{seat}-{item:02d}' for seat, items in [(1, [1,2,3,4]), (2, [1,2]), (3, [1,2,3])] for item in items}
third_ids = re.findall(r'^\| (S-r3-L\d-\d+) \|', records, re.M)
check(set(third_ids) == expected_third_ids and len(third_ids) == 9, '第3轮 9 条发现逐条登记且无重复')
choice_sections = {match.group(1): match.group(2) for match in re.finditer(r'^## (T\d+)\.[^\n]*\n(.*?)(?=^## |\Z)', choices, re.M | re.S)}
check('操作精度' in choice_sections['T12'] and '周期末' in choice_sections['T12'], 'T12包含成品拿取操作精度及周期末限制')
check('接通早的级别高' in semantic_sections['3.1'] and '接通早的级别高' in semantic_sections['4.2'], '存货级序方向在派生量及调度两处明写')
check('分流器、汇流器' in semantic_sections['2.2'] and '特别运输单位' in choice_sections['T4'], '特别运输分类和元件计数落点存在')
check('**已排除**' in choice_sections['T14'] and '按轴另分' in choice_sections['T14'], 'T14按轴调度已列排除')
check(all(term in choice_sections['T7'] for term in ['甲读法', '乙读法', '每格合计', '每种分别计数', '逐格求值', '并集求值']), 'T7混装、容量、谓词论域分别登记')
check('设 J' in semantic_sections['2.3'] and '达标循环不相容' in semantic_sections['2.3'], 'J的条件排除有正文落点')
for phrase in ['桥接器按单位或按轴待', '桥接器按单位或按轴存货分级', '桥接器辖域待', '在待定辖域内', '两轴合并或分开', '桥接器调度辖域（T14）', '桥接器辖域（T14）', '普通存货格混装、失败', '存货格“不限制物品种类”不取消单格单种规则', '运输格各上限 1、箱格']:
    assert all(phrase not in (spec_dir / name).read_text() for name in ['运行语义.md', '选择点清单.md', '四件前置义务对照.md', '规则覆盖表.md', '选择点参数轴.md', '受限模型声明.md']), phrase
results.append('第3轮已定位旧辖域断言无正文残留（字符串检查）')
# 本轮参数轴、目录引用、取值辖域及保护范围核验。
axes = (spec_dir / '选择点参数轴.md').read_text()
profile = (spec_dir / '受限模型声明.md').read_text()
active_names = ['运行语义.md', '选择点清单.md', '四件前置义务对照.md', '规则覆盖表.md', '选择点参数轴.md', '受限模型声明.md']
active = {name: (spec_dir / name).read_text() for name in active_names}
axis_rows = re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \| (.*?) \| (.*?) \| (.*?) \|$', axes, re.M)
axis_ids = [row[0] for row in axis_rows]
check(len(axis_ids) == len(set(axis_ids)) and len(axis_ids) >= 70, '具名参数轴无重复且均带生命周期、状态与据')
for field, identifiers, lifetime, body in axis_rows:
    assert set(re.findall(r'\bT\d+\b', identifiers)) <= choice_ids
    assert lifetime and '据：' in body and any(value in body for value in ['known', 'open', 'obligation'])
profile_fields = set(re.findall(r'`([a-z_]+\.[a-z_]+)(?:=[a-z_]+)?`', profile))
check(profile_fields <= set(axis_ids), '受限模型全部具名字段均在参数轴表中')
independent = (spec_dir / '复核/选择点独立清单-r3.md').read_text()
independent_ids = re.findall(r'^### ([A-K]\d+)\s', independent, re.M)
mapped_ids = re.findall(r'^\| ([A-K]\d+) \|', axes, re.M)
check(len(independent_ids) == 55 and len(mapped_ids) == 55 and set(mapped_ids) == set(independent_ids), '独立清单实际55项逐条映射，无遗漏或重复')


def validate_active_scope(documents):
    for name, body in documents.items():
        assert not re.search(r'\bT13\b', body), name
        for phrase in ['判定次序整场固定；', '判定整场固定、', '制造端口可访问哪些格待 T7', '按箱/按格冷却与判定粒度', '逐 tick 式存在计数域措辞冲突', 'unresolved_semantics']:
            assert phrase not in body, (name, phrase)
    assert 'per_instant' in documents['运行语义.md'] and 'per_instant' in documents['选择点清单.md']
    for value in ['exclude_first', 'second_cursor', 'start_on_second', 'skip', 'empty_turn']:
        assert value in documents['选择点清单.md']
    for value in ['positive_area', 'closed_touch', 'same_instant', 'next_instant']:
        assert value in documents['选择点清单.md']
    for field in ['manufacturing.port_slot_relation', 'transfer.judgment', 'transfer.cooldown_scope', 'bridge.capacity', 'bridge.scheduling_scope']:
        assert field in documents['选择点参数轴.md']


validate_active_scope(active)
results.append('主席已定项与四处旧断言、三漏项的现行辖域检查通过')
mutated_active = dict(active)
mutated_active['选择点清单.md'] += '\n## T13. 旧冲突\n'
try:
    validate_active_scope(mutated_active)
except AssertionError:
    results.append('负例通过：恢复T13旧选择点会被拒绝（内存变异）')
else:
    raise AssertionError('未拒绝恢复的旧选择点')

catalog = json.loads((root / '求解器/数据/正式静态目录.json').read_text())
unit_ids = {unit['id'] for unit in catalog['units']}
recipe_ids = {recipe['id'] for recipe in catalog['recipes']}
recipe_rows = re.findall(r'^\| `([^`]+)` \| `([^`]+)` \| (.*?) \| (\d+) \|$', semantic_sections['2.3'], re.M)
check(len(unit_ids) == 18 and len(recipe_ids) == 18 and len(recipe_rows) == 18, '共享目录18单位与18配方及规格18配方行数一致')
recipe_map = {recipe['id']: recipe for recipe in catalog['recipes']}
for identifier, unit_id, formula, duration in recipe_rows:
    recipe = recipe_map[identifier]
    assert unit_id in unit_ids and unit_id == recipe['kind']
    format_items = lambda items: '＋'.join(value['value'] + ' ' + item for item, value in items.items())
    assert formula == format_items(recipe['inputs']) + ' → ' + format_items(recipe['outputs'])
    assert duration == recipe['duration']['value']
check({row[0] for row in recipe_rows} == recipe_ids, '全部配方id、机型、用量、产量及耗时逐项与目录一致')
check(all(identifier in semantic_sections['2.2'] for identifier in unit_ids), '全部单位id均有运行语义状态入口')
check(hashlib.sha256((root / '求解器/数据/正式静态目录.json').read_bytes()).hexdigest() in records, '当前目录字节已登记于本轮修订记录并逐项核验')
# 正面积/闭边格集合为条件解释的算术，不是供电规则唯一性的证明。
for center_x, center_y in [(1, 1), (35, 35), (69, 69)]:
    for x in range(70):
        for y in range(70):
            positive_intersection = min(x + 1, center_x + 6) > max(x, center_x - 6) and min(y + 1, center_y + 6) > max(y, center_y - 6)
            positive_formula = center_x - 6 <= x < center_x + 6 and center_y - 6 <= y < center_y + 6
            closed_intersection = min(x + 1, center_x + 6) >= max(x, center_x - 6) and min(y + 1, center_y + 6) >= max(y, center_y - 6)
            closed_formula = center_x - 7 <= x <= center_x + 6 and center_y - 7 <= y <= center_y + 6
            assert positive_intersection == positive_formula
            assert closed_intersection == closed_formula
results.append('T15两种格集合公式与方块相交条件在中央及边界桩位置一致（条件算术）')
for name, body in active.items():
    for target in re.findall(r'\]\(([^)]+)\)', body):
        assert (spec_dir / target.split('#')[0]).exists(), (name, target)
results.append('六正文所有本地文件链接存在')
# 第三轮新增门禁：先核原始发现集合，再核正文落点和当前配置。
validation_dir = spec_dir / '第三轮任务验证'
finding_input = json.loads((validation_dir / '任务发现输入.json').read_text())
expected_new_ids = {item['id'] for item in finding_input['aFindings']}
new_ids = re.findall(r'^\| (S2-r[45]-L\d-\d+) \|', records, re.M)
check(len(new_ids) == len(expected_new_ids) == 28 and set(new_ids) == expected_new_ids, '第4/5轮28条发现逐项登记且无重复，含两条阻断级')
dispositions = json.loads((validation_dir / '发现处置.json').read_text())
check({item['id'] for item in dispositions} == expected_new_ids and all(item['change'] and item['locations'] and item['basis'] for item in dispositions), '28条发现均有改动、落点及据')
start_specs = json.loads((validation_dir / '开工规格指纹.json').read_text())
check(all(hashlib.sha256((spec_dir / name).read_bytes()).hexdigest() != start_specs[str(spec_dir / name)] for name in active_names), '六正文均已实际修改，不是只增加修订记录')

profile_registry = json.loads((spec_dir / '内核配置-v1.json').read_text())
profile_rows = [line.split('|')[1:-1] for line in profile.splitlines() if re.match(r'^\| `[a-z_]+\.[a-z_]+` \|', line)]
profile_row_map = {row[0].strip().strip('`'): row for row in profile_rows}
allowed_dispositions = {'本版选值', '已定', '由输入全称量化', '超出覆盖即停'}
check(len(axis_ids) == 99 and set(profile_row_map) == set(axis_ids) == set(profile_registry['axes']) and len(profile_rows) == 99, '原91轴加5轴及第6轮3轴共99项，与受限模型逐轴表和JSON集合全等')
for field, row in profile_row_map.items():
    entry = profile_registry['axes'][field]
    assert len(row) == 6 and row[1].strip() in allowed_dispositions
    assert row[1].strip() == entry['disposition'] and all(cell.strip() for cell in row)
    assert '据：' in row[3] and entry['basis'] and entry['coverage_loss'] and entry['extension_gate']
    encoded = json.dumps(entry['value'], ensure_ascii=False, separators=(',', ':'))
    assert '`' + encoded + '`' in row[2] and entry['meaning'] in row[2], field
    assert row[4].strip() == entry['coverage_loss'] and row[5].strip() == entry['extension_gate'], field
    assert entry['basis'] in row[3], field
    if entry['disposition'] == '已定':
        assert next(item[3] for item in axis_rows if item[0] == field).startswith('known：'), field
check(profile_registry['axis_count'] == len(axis_ids), '99轴处置类别、实际编码、据、覆盖损失及补齐节点逐项一致')

# 整表缺项负例在内存内实施，不能通过仅检查已写字段掩盖漏轴。
def validate_profile_fields(field_set):
    assert field_set == set(axis_ids)
for missing_field in ['time.instant_order', 'time.manufacture_events', 'polling.level_tie', 'connection.port_meeting']:
    try:
        validate_profile_fields(set(profile_row_map) - {missing_field})
    except AssertionError:
        results.append('负例通过：漏必选轴' + missing_field + '会被拒绝')
    else:
        raise AssertionError('漏轴负例未被拒绝')

transfer = (spec_dir / '受限转移定义.md').read_text()
for phrase in ['completion_before_closure', 'advance_authorized', 'A(c)', '首次重复', '不读取任何轮询指针', '不跳到后格', '无侧授权', 'unsupported']:
    # 文义检查仍只声明定位检查；离散算法另用回归算例核。
    if phrase == '无侧授权':
        assert 'A为空' in transfer
    else:
        assert phrase in transfer, phrase
check('closed_touch下多覆盖的机器不算数' in profile and '不额外加positive_area前件' in semantics, '最严供电义务与四条必要条件的辖域落地')
check('单位占格互不相交' in semantics and '约束·不得依赖的量' in semantic_sections['1'], '占格互斥具有最严可建造的正文依据')
check('item=null' in choice_sections['T12'] and 'empty_identity' in choice_sections['T12'], '空仓库格指派要求empty_identity且沿用原轴')
for term in ['polling.split_merge_scope', 'polling.split_merge_singleton', 'polling.both_failure', 'connection.belt_shape', 'initialization.belt_shape_lifecycle']:
    assert term in axes and term in choices and term in profile
results.append('五个新增轴在登记、清单、配置三处都有落点')
for forbidden in ['箱体逐次取编号最小合法格已定', '断边时允许检查物理相邻源的候选来件', 'open：内部通道不入分级、不入端口轮询；是否入通道分级另审', '现在只有带守卫的部分转移关系，没有唯一后继函数', '内核落地前补齐请求如何成为判定', '内核编码前须由后续复核/实现规格收口']:
    assert all(forbidden not in body for body in list(active.values()) + [transfer]), forbidden
results.append('第4/5轮及完整性批评定位的旧正文断言无残留')
for number, required in [(14, ['T11/T12', '§5', '§6']), (41, ['T1/T11/T12', '80000', '格指派']), (16, ['T5', '共边'])]:
    line = next(line for line in sections[1].splitlines() if line.startswith('| ' + str(number) + ' |'))
    assert all(term in line for term in required), line
results.append('仓库/核心/相遇覆盖入口的辖域回归通过')
for g in range(7):
    assert ceil((g + 7) / 3) == [3,3,3,4,4,4,5][g]
    assert ceil((g + 8) / 3) == [3,3,4,4,4,5,5][g]
results.append('两种供电侧旁一维列数及跃变位置复算通过；非达标构造证明')

# 第6轮逐项登记与守卫定位，数值转移另由局部回归核。
revision6_dir = spec_dir / '第6轮修订验证'
revision6_rows = json.loads((revision6_dir / '发现处置.json').read_text())
revision6_ids = {'S3-r6-L1-01', 'S3-r6-L2-01', 'S3-r6-L3-01', 'S3-r6-L3-02', 'S3-r6-L3-03'}
check({row['id'] for row in revision6_rows} == revision6_ids and len(revision6_rows) == 5, '第6轮五项发现有逐条处置')
check(set(re.findall(r'^\| (S3-r6-L\d-\d+) \|', records, re.M)) == revision6_ids, '修订记录追加第6轮五项且无遗漏')
for field in ['gate.concurrent_expiry', 'manufacturing.recipe_quantity_match', 'manufacturing.recipe_extra_items']:
    assert field in axes and field in choices and field in profile
check(all(term in transfer for term in ['同一快照', '一次重算', '保持completed', '全部存货格', 'competing_new_species', 'len(U)>=2 and any(w in assigned_slots for w in E)', 'recipe_quantity_match=at_least', 'recipe_extra_items=allow']), '第6轮边界、库存、仓库停止及配方两轴在可执行条款定位')
for identifier in ['S2-r4-L1-03', 'S2-r5-L1-04']:
    row = next(row for row in dispositions if row['id'] == identifier)
    assert '原发现已明确反对' in row['change'] and '不采发现中直接排除' not in row['change']
    line = next(line for line in records.splitlines() if line.startswith('| ' + identifier + ' |'))
    assert '原发现已明确反对' in line and '不采发现中直接排除' not in line
check(True, '两条旧覆盖发现归因在历史行及JSON均已纠正')
check(all(value in axes and value in choices for value in ['event-order-v2', 'event-order-v3', 'order-expr-v1']) and 'continuation' in semantics, '内核输入请求第6/7节在共享正文并入')

# 第7轮既核处置同步也拒绝已定位的旧唯一性断言，回归值另由本轮脚本核。
revision7_rows = json.loads((spec_dir / '第7轮修订验证/发现处置.json').read_text())
revision7_ids = {'S3-r7-L3-1', 'S3-r7-L3-2'}
check(len(revision7_rows) == 2 and {row['id'] for row in revision7_rows} == revision7_ids
      and set(re.findall(r'^\| (S3-r7-L\d-\d+) \|', records, re.M)) == revision7_ids,
      '第7轮两条发现与修订记录均有逐项落点及据')
meeting_row = next(row for row in axis_rows if row[0] == 'connection.port_meeting')
check(meeting_row[2] == 'U' and meeting_row[3].startswith('open：')
      and profile_registry['axes']['connection.port_meeting']['disposition'] == '本版选值'
      and profile_registry['axes']['connection.port_meeting']['lifetime'] == 'U',
      '端口相遇从已定/F改为open/U及显式工程选值')
for phrase in ['**相遇判据已定**', '两端口要相遇只能重合', '共边相向相遇已定', '角触/隔格/同类端口', '按共享选择点 T5 已定']:
    assert all(phrase not in body for body in list(active.values()) + [(spec_dir/'内核输入.md').read_text(), (spec_dir/'参数轴-对内核输入请求的答复.md').read_text()]), phrase
check('closed_segment_touch' in choice_sections['T5'] and '未获全规则许可' in choice_sections['T5'],
      '角点相遇有显式待审谓词及覆盖损失，未当成已获准')
check(all(term in transfer for term in ['O(S)', 'E(S)', '稳定子序', '清空时item=null', 'JSON重载'])
      and '第一仍为空' not in transfer,
      '仓库当前候选序、成功提交、历史身份和重载辖域在转移中明写')

# 第8轮接口前件及拼写定位；反例和schema改名拒收另由check_round8运行。
reply = (spec_dir / '参数轴-对内核输入请求的答复.md').read_text()
check('len(U)>=2 and any(w in assigned_slots for w in E)' in reply
      and 'finite_concrete' in reply and 'D.3' in reply,
      '第8轮接口完整停止前件及普通运行/生产抽象分域')
check('verification_scope' not in reply and '`validation_scope`' in reply,
      '第8轮答复验证范围字段与封闭输出同名')
line36 = next(line for line in coverage.splitlines() if line.startswith('| 36 |'))
check('至少一格被取货端口指派' in line36 and '全未指派' in line36,
      '第8轮规则L36覆盖说明同时保留停止与继续分支')
revision8_ids = {'S5-r8-L1-01', 'S5-r8-L2-01', 'S5-r8-L2-02'}
check(set(re.findall(r'^\| (S5-r8-L\d-\d+) \|', records, re.M)) == revision8_ids,
      '第8轮三条发现分别登记')
check('### 6.4 种子派生与检查点恢复' in (spec_dir/'内核输入.md').read_text()
      and all(term in transfer for term in ['KQ-08', '容量读取前', '级排序或授权前', '零回矿账']),
      'KQ-07种子来源与KQ-08容量前准入具有明确落点')

# C线并行文件不设只读门禁；单独报告当前接口是否追上共享轴。
input_body = (spec_dir / '内核输入.md').read_text()
input_axis_rows = re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \| `([^`]+)`；([^|]+) \| ([^\n]+) \|$', input_body, re.M)
input_axis_map = {row[0]: row for row in input_axis_rows}
expected_life = {row[0]: row[2].strip() for row in axis_rows}
interface_status = {
    'axis_set_matches': set(input_axis_map) == set(axis_ids),
    'missing_in_input': sorted(set(axis_ids) - set(input_axis_map)),
    'extra_in_input': sorted(set(input_axis_map) - set(axis_ids)),
    'lifetime_mismatches': [field for field in axis_ids if field in input_axis_map and input_axis_map[field][2].strip() != expected_life[field]],
    'schemas_present': {name: name in input_body for name in ['event-order-v1', 'event-order-v2', 'event-order-v3', 'order-expr-v1', 'damping-branch-v2', 'poll-memory-v1']},
    'revision6_description_mismatches': [field for field in ['time.instant_order', 'polling.membership_change', 'manufacturing.recipe_completeness', 'manufacturing.output_blocked', 'warehouse.empty_slot_identity', 'connection.port_meeting'] if field not in input_axis_map or next(row[3] for row in axis_rows if row[0] == field) not in input_axis_map[field][3]],
    'note': '共享文件为运行时观测，不冻结为A线只读；样例及黄金轨迹由C线另验'
}
request = spec_dir / '内核输入-对参数轴的修改请求.md'
request_hash = hashlib.sha256(request.read_bytes()).hexdigest() if request.exists() else None
result = {'status': 'PASS', 'scope': '规格线文档覆盖、99轴、当前目录、定位回归、条件算术与本轮只读指纹；非全规则或运行认证', 'axis_count': len(axis_ids), 'independent_item_count': len(independent_ids), 'finding_count': len(new_ids), 'revision6_finding_count': 5, 'revision7_finding_count': 2, 'catalog_sha256': hashlib.sha256((root / '求解器/数据/正式静态目录.json').read_bytes()).hexdigest(), 'axis_registry_sha256': hashlib.sha256((spec_dir / '选择点参数轴.md').read_bytes()).hexdigest(), 'request_sha256': request_hash, 'shared_interface': interface_status, 'shared_dependency_fingerprints': shared_dependency_fingerprints, 'shared_dependency_changes_since_round5_start': shared_dependency_changes, 'checks': results}
print(json.dumps(result, ensure_ascii=False, indent=2))
