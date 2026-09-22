"""复核轴表、交付指纹及制造出缓存守卫；只向标准输出打印证据。"""
import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


review_dir = Path(__file__).resolve().parent
spec_dir = review_dir.parent
repo = spec_dir.parent.parent
validation = spec_dir / '第三轮任务验证'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


manifest = read_json(validation / '交付文件清单.json')
published = read_json(validation / '交付指纹.json')
files = {name: digest(Path(name)) for name in manifest}
assert len(manifest) == len(files) == 25
assert all(files[name] == expected for name, expected in published.items())
protected = read_json(validation / '开工只读指纹.json')
protected_changed = [name for name, expected in protected.items() if digest(Path(name)) != expected]
assert not protected_changed

# 将全部 JSON 解析，不以显示少量文件头代替清单和配置核对。
json_shapes = {}
for name in manifest:
    path = Path(name)
    if path.suffix == '.json':
        value = read_json(path)
        json_shapes[name] = {'type': type(value).__name__, 'entries': len(value)}

axis_text = (spec_dir / '选择点参数轴.md').read_text()
profile_text = (spec_dir / '受限模型声明.md').read_text()
axis_rows = re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \| (.*?) \| (.*?) \| (.*?) \|$', axis_text, re.M)
profile_rows = [line.split('|')[1:-1] for line in profile_text.splitlines() if re.match(r'^\| `[a-z_]+\.[a-z_]+` \|', line)]
profile_map = {row[0].strip().strip('`'): row for row in profile_rows}
registry = read_json(spec_dir / '内核配置-v1.json')
axis_names = [row[0] for row in axis_rows]
assert len(axis_names) == len(set(axis_names)) == 96
assert set(axis_names) == set(profile_map) == set(registry['axes'])
assert len(profile_rows) == 96
for field, choice, lifetime, body in axis_rows:
    row = profile_map[field]
    entry = registry['axes'][field]
    assert len(row) == 6 and all(cell.strip() for cell in row)
    assert row[1].strip() == entry['disposition']
    assert json.dumps(entry['value'], ensure_ascii=False, separators=(',', ':')) in row[2]
    assert choice == entry['choice'] and lifetime == entry['lifetime']
    assert entry['basis'] and entry['coverage_loss'] and entry['extension_gate']
    assert '据：' in body and '据：' in row[3]

critic = (review_dir / '完整性批评-2.md').read_text()
missing_section = critic.split('## 附录：', 1)[1]
previous_missing = set(re.findall(r'`([a-z_]+\.[a-z_]+)`', missing_section.split('\n\n其中', 1)[0]))
assert len(previous_missing) == 43 and previous_missing <= set(profile_map)
new_axes = {'polling.split_merge_scope', 'polling.split_merge_singleton', 'polling.both_failure', 'connection.belt_shape', 'initialization.belt_shape_lifecycle'}
assert len(set(axis_names) - new_axes) == 91

findings = read_json(validation / '任务发现输入.json')['aFindings']
dispositions = read_json(validation / '发现处置.json')
assert len(findings) == len(dispositions) == 28
assert {entry['id'] for entry in findings} == {entry['id'] for entry in dispositions}
records = (spec_dir / '修订记录.md').read_text()
assert set(re.findall(r'^\| (S2-r[45]-L\d-\d+) \|', records, re.M)) == {entry['id'] for entry in findings}

# 这是规则13的独立不变量：排除缓存后，一个物种至多占一个普通格。
def unique_ordinary_slots(state):
    occupied = [state[role]['item'] for role in ['input', 'output'] if state[role]['count']]
    return len(occupied) == len(set(occupied))


state = {
    'time': 0,
    'input': {'item': None, 'count': 0},
    'output': {'item': None, 'count': 0},
    'buffer': {'item': '源矿', 'count': 1},
    'phase': 'working',
    'remaining': 1,
    'belt': {'item': '源石粉末', 'count': 1, 'entered_at': 0},
    'port_used': False,
}
trace = []


def record(action):
    trace.append({'action': action, 'state': copy.deepcopy(state), 'rule13_holds': unique_ordinary_slots(state)})


record('t=0的合成段起点；普通格空，缓存一批在制原料')
state.update(time=1, remaining=0, phase='completed')
state['buffer'] = {'item': '源石粉末', 'count': 1}
record('受限转移§2.1：工作量耗足，先完成并将产物放在缓存')
assert state['time'] - state['belt']['entered_at'] >= 1
assert not state['port_used'] and state['input']['count'] == 0
state['input'] = {'item': state['belt']['item'], 'count': 1}
state['belt']['count'] = 0
state['belt']['item'] = None
state['port_used'] = True
record('move排在manufacture之前：从唯一存货通道接收已滞留一tick的物品')
assert unique_ordinary_slots(state)
safe_before_output = copy.deepcopy(state)

# 逐字落实§4.2第1步所列的条件，核其是否足够保持正式不变量。
listed_guard = (state['phase'] == 'completed'
                and (state['output']['count'] == 0 or state['output']['item'] == state['buffer']['item'])
                and state['output']['count'] + state['buffer']['count'] <= 50)
assert listed_guard
state['output'] = copy.deepcopy(state['buffer'])
state['buffer'] = {'item': None, 'count': 0}
state['phase'] = 'idle'
record('按§4.2第1步已列条件出缓存：产生两个普通格同种物品')
assert not unique_ordinary_slots(state)
assert safe_before_output['buffer']['count'] == 1

source_names = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
result = {
    'scope': '机械登记、当前字节核验与局部转移反例；不是完整内核、蓝图可达性或达标反例',
    'sources': {name: digest(repo / name) for name in source_names},
    'reviewed_files': files,
    'published_fingerprints_matched': len(published),
    'json_shapes': json_shapes,
    'protected_count': len(protected),
    'protected_changed': protected_changed,
    'axes': {
        'count': len(axis_names),
        'original_part_count': len(set(axis_names) - new_axes),
        'new_names': sorted(new_axes),
        'previous_43_missing_now_registered': sorted(previous_missing),
        'disposition_counts': dict(Counter(entry['disposition'] for entry in registry['axes'].values())),
        'group_counts': dict(Counter(name.split('.')[0] for name in axis_names)),
        'per_axis': [dict(field=field, **registry['axes'][field]) for field in axis_names],
    },
    'previous_findings_registered': sorted(entry['id'] for entry in findings),
    'counterexample': {
        'finding_id': 'S3-r6-L2-01',
        'rule13': (repo / source_names[0]).read_text().splitlines()[12],
        'trace': trace,
        'listed_output_guard': listed_guard,
        'violates_same_item_across_ordinary_slots': True,
        'required_safe_state': safe_before_output,
        'explanation': '缓存例外允许收货后的状态；出缓存目的格不属于例外，须保留整批并等待，而非提交非法状态或拒绝合法前态。',
    },
}
print(json.dumps(result, ensure_ascii=False, indent=2))
