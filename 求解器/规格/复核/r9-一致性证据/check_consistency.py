"""第9轮一致性复核：独立字段清单、配置及原始证据核对；只写本证据目录。"""
from pathlib import Path
from copy import deepcopy
from itertools import combinations
import ast
import hashlib
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
SPEC = HERE.parents[1]
ROOT = SPEC.parents[1]
KERNEL = ROOT / '求解器/crates/kernel/src'
AJV = '/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
checks = []


def read(path):
    return Path(path).read_text()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def check(condition, label):
    assert condition, label
    checks.append(label)


# 清单按输入正文§6独立填写；不从Rust代码或旧自查结果生成期望。
state_fields = {
    'Content': 'item quantity entered_at',
    'Inventory': 'slot contents',
    'WarehouseSlot': 'slot item quantity empty_identity',
    'Warehouse': 'slots unlisted',
    'Cooldown': 'slot remaining',
    'Progress': 'unit phase recipe candidate_recipes locked_recipe remaining cooldowns',
    'Level': 'id members next_channel',
    'Side': 'unit side graded current_level levels',
    'PollMemory': 'schema sides',
    'Gate': 'unit total_received window_received window_started_at blocked_reasons',
    'Logistics': 'active_channels blocked_channels poll_memory gate_counters connection_order',
    'Environment': 'time stage online withdrawal_memory',
    'Arbitration': 'level_order warehouse_empty_slot_order',
    'ParameterValue': 'axis value lifetime',
    'SemanticContext': 'arbitration parameter_values judgment_context pending_events tick_context',
    'State': 'layout_snapshot settings_anchor warehouse inventory progress logistics environment semantic_context',
    'Pending': 'event operation target trigger predecessors status',
}
model = read(KERNEL / 'model.rs')
actual_fields = {}
for name, fields in state_fields.items():
    body = re.search(r'pub struct ' + name + r' \{(.*?)\n\}', model, re.S)[1]
    actual_fields[name] = re.findall(r'pub (\w+):', body)
    check(set(actual_fields[name]) == set(fields.split()), '输入字段全集与Rust类型一致：' + name)
expected_components = [
    'state.warehouse', 'state.inventory', 'state.progress', 'memory',
    'state.logistics.active_channels', 'state.logistics.blocked_channels',
    'state.logistics.gate_counters', 'state.logistics.connection_order',
    'state.semantic_context.arbitration', 'pending', 'usage',
]
closure = read(KERNEL / 'transition.rs').split('fn closure_key')[1].split('.map_err')[0]
actual_components = re.findall(r'&self\.([a-z_.]+)', closure)
check(actual_components == expected_components, 'closure_key全部元组项及顺序恰为规格11项')
dump('状态字段与闭包键.json', {'expected_types': {k:v.split() for k,v in state_fields.items()},
     'actual_types': actual_fields, 'field_count': sum(len(v) for v in actual_fields.values()),
     'closure_components': actual_components,
     'scope': '类型级字段全集核对；Decision.value的嵌套语法另按正文逐项人工核对'})

schema_path = SPEC / '内核输出.schema.json'
schema = json.loads(read(schema_path))
defs = schema['$defs']
# 由输出正文逐个对象填写期望字段，逐项核required和未知字段拒收。
contracts = {
    'RunRecord': 'schema run_id execution_mode port_meeting profile_id producer status fingerprints parameter_assignment input_history uncovered_axes trace validation_scope open_items',
    'Tick': 'time events state summary closure warehouse_ledger',
    'DeltaTick': 'time events summary closure delta warehouse_ledger',
    'FullTrace': 'start_state ticks end_time format',
    'CheckpointTrace': 'start_state ticks end_time format checkpoint_interval delta_encoding',
    'DeltaOperation': 'op path value',
    'CoreInbound': 'event channel port item quantity',
    'WirelessInbound': 'event unit item quantity',
    'PortOutbound': 'event channel port slot item quantity',
    'ExternalSupply': 'event mode item quantity',
    'PlayerWithdrawal': 'event slot item quantity',
    'RepresentativeAdjustment': 'item quantity reason',
    'WarehouseTotal': 'item core_inbound wireless_inbound port_outbound external_supply player_withdrawal representative_adjustment actual_inbound',
    'WarehouseLedger': 'core_inbound wireless_inbound port_outbound external_supply player_withdrawal representative_adjustment totals',
    'CycleResult': 'schema result_id status level execution_mode port_meeting seed parameter_point reading support_domain replay_input run_record cycle stop budget open_items',
    'Cycle': 'period start_time end_time start_state end_state start_key end_key normalization ledger totals rates acceptance lift',
    'CycleKey': 'schema domain state product_acceptance',
    'CycleRate': 'item inbound period average target comparison',
    'Acceptance': 'time products',
    'ProofSource': 'path sha256',
    'StateSeed': state_fields['State'],
    'Parameters': 'axis_registry profile_id fixed offline_mutable fixedness_unproven',
    'Quantity': 'value category',
    'Time': 'kind value',
    'Decision': 'status value basis',
}
objects = {name: defs[name] for name in contracts}
objects.update({
    'RunRecord.producer': defs['RunRecord']['properties']['producer'],
    'RunRecord.fingerprints[]': defs['RunRecord']['properties']['fingerprints']['items'],
    'RunRecord.input_history': defs['RunRecord']['properties']['input_history']['anyOf'][0],
    'RunRecord.uncovered_axes[]': defs['RunRecord']['properties']['uncovered_axes']['items'],
    'RunRecord.validation_scope': defs['RunRecord']['properties']['validation_scope']['anyOf'][0],
    'CycleResult.seed': defs['CycleResult']['properties']['seed']['anyOf'][0],
    'CycleResult.parameter_point': defs['CycleResult']['properties']['parameter_point']['anyOf'][0],
    'CycleResult.reading': defs['CycleResult']['properties']['reading'],
    'CycleResult.support_domain': defs['CycleResult']['properties']['support_domain'],
    'CycleResult.budget': defs['CycleResult']['properties']['budget'],
    'CycleResult.stop': defs['CycleResult']['properties']['stop']['anyOf'][0],
    'Cycle.normalization': defs['Cycle']['properties']['normalization'],
    'Cycle.ledger[]': defs['Cycle']['properties']['ledger']['items'],
    'Cycle.lift': defs['Cycle']['properties']['lift']['anyOf'][0],
    'Acceptance.products[]': defs['Acceptance']['properties']['products']['items'],
})
contracts.update({
    'RunRecord.producer': 'kind path claim',
    'RunRecord.fingerprints[]': 'role path sha256',
    'RunRecord.input_history': 'timeline construction debug_operations environment reachability',
    'RunRecord.uncovered_axes[]': 'axis reason disposition coverage_status evidence other_values',
    'RunRecord.validation_scope': 'kind from through golden_match initial_history manufacturing_cycles_completed universal_parameters all_reachable_cycles target_certified',
    'CycleResult.seed': 'state reachability source_event',
    'CycleResult.parameter_point': 'assignment input_axes',
    'CycleResult.reading': 'port_meeting warehouse_acceptance acceptance_quantifier cycle_interpretation remaining_assumptions',
    'CycleResult.support_domain': 'name checks uncovered',
    'CycleResult.budget': 'max_ticks max_sweeps completed_ticks',
    'CycleResult.stop': 'kind axis event time reason partial_events',
    'Cycle.normalization': 'schema definition basis domain_checks',
    'Cycle.ledger[]': 'time warehouse_ledger',
    'Cycle.lift': 'status family proof family_checks',
    'Acceptance.products[]': 'item capacity_available physical_path_exists selected_acceptance',
})
for name, fields in contracts.items():
    obj = objects[name]
    check(set(obj['properties']) == set(obj['required']) == set(fields.split())
          and obj.get('additionalProperties') is False, '输出封闭对象字段及必填全集：' + name)
check(set(defs['Event']['properties']) == set('event operation target outcome detail basis'.split())
      and set(defs['Event']['required']) == set('event operation target outcome basis'.split()),
      'Event仅detail可省，与正文一致')
check(defs['FullTrace']['properties']['ticks']['items'] == {'$ref':'#/$defs/Tick'}
      and defs['CheckpointTrace']['properties']['ticks']['items']['oneOf'] == [
          {'$ref':'#/$defs/Tick'}, {'$ref':'#/$defs/DeltaTick'}], '两种trace共享必填台账的Tick定义')
dump('输出字段清单.json', {name: {'expected': fields.split(), 'schema': objects[name]}
                            for name, fields in contracts.items()})

# 生成器仅在内存执行：删除其唯一落盘语句与打印；不重写被复核schema。
build_path = SPEC / '第五轮规格修订/build_schema.py'
tree = ast.parse(read(build_path))
assert isinstance(tree.body[-2], ast.Expr) and isinstance(tree.body[-2].value, ast.Call)
assert isinstance(tree.body[-2].value.func, ast.Attribute) and tree.body[-2].value.func.attr == 'write_text'
assert isinstance(tree.body[-1], ast.Expr) and tree.body[-1].value.func.id == 'print'
tree.body = tree.body[:-2]
namespace = {'__file__': str(build_path), '__name__': '__review__'}
exec(compile(tree, str(build_path), 'exec'), namespace)
rebuilt = (json.dumps(namespace['schema'], ensure_ascii=False, indent=2) + '\n').encode()
check(rebuilt == schema_path.read_bytes(), 'schema内存重建与现行字节一致且未写原文件')

config = json.loads(read(SPEC / '内核配置-v1.json'))
axis_rows = {row[0]: row for row in re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \| (.*?) \| (.*?) \| (.*?) \|$', read(SPEC / '选择点参数轴.md'), re.M)}
input_rows = {row[0]: row for row in re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \| `([^`]+)`；([^|]+) \| ([^\n]+) \|$', read(SPEC / '内核输入.md'), re.M)}
check(set(axis_rows) == set(input_rows) == set(config['axes']) and len(axis_rows) == 99, '99轴三处全集一致')
for axis, row in axis_rows.items():
    check(row[2].strip() == input_rows[axis][2].strip() and row[3] in input_rows[axis][3],
          '输入轴说明逐项覆盖登记表：' + axis)
point_axes = objects['CycleResult.parameter_point']['properties']['input_axes']
check(set(point_axes['properties']) == set(point_axes['required']) == {
    k for k,v in config['axes'].items() if v['disposition']=='由输入全称量化'}, '证书恰15输入轴与配置一致')

# 每个分叉三条几何可能出支：共7个非空集、24张局部完整选择表。
channels = ('PC_a', 'PC_b', 'PC_c')
subsets = [c for n in range(1,4) for c in combinations(channels,n)]
count = 1
for subset in subsets:
    count *= len(subset)
check(len(subsets) == 7 and count == 24, 'v2三出支7个非空子集与24张确定表的条件算术')
branch = {s:s[-1] for s in subsets}
sequence = [channels, ('PC_a','PC_b'), ('PC_b',), channels]
answers = [branch[s] for s in sequence]
check(answers == ['PC_c','PC_b','PC_b','PC_c'], 'v2切支与恢复仅由当前集合查询，固定支失活不单独停止')
dump('分支局部复算.json', {'subsets': subsets, 'table_count':count,
    'sequence':sequence, 'answers':answers,
    'scope':'输入§5.3与转移§3.4的表查询条件例；非完整布局或Rust执行证据'})

# 一次批调用覆盖所有基本台账对象的字段删改负例。
def sample(part):
    if '$ref' in part:
        return sample(defs[part['$ref'].split('/')[-1]])
    if 'const' in part:
        return part['const']
    if 'enum' in part:
        return part['enum'][0]
    if 'anyOf' in part:
        return sample(part['anyOf'][0])
    kind = part.get('type')
    if isinstance(kind, list):
        kind = next((v for v in kind if v != 'null'), 'null')
    if kind == 'object':
        return {k:sample(part['properties'][k]) for k in part.get('required', [])}
    if kind == 'array':
        return [sample(part['items']) for _ in range(part.get('minItems',0))]
    if kind == 'boolean':
        return False
    if kind == 'integer':
        return part.get('minimum', 0)
    if kind == 'string':
        return '0' if 'pattern' in part else 'fixture'
    return None
cases = []
for name in ['CoreInbound','WirelessInbound','PortOutbound','ExternalSupply','PlayerWithdrawal',
             'RepresentativeAdjustment','WarehouseTotal','WarehouseLedger','CycleRate','Acceptance']:
    value = sample(defs[name])
    cases.append({'label':name+'结构正例', 'definition':name, 'value':value, 'expected':True})
    for field in defs[name]['required']:
        bad = deepcopy(value)
        del bad[field]
        cases.append({'label':name+'缺字段 '+field, 'definition':name, 'value':bad, 'expected':False})
    bad = deepcopy(value)
    bad['unknown_field'] = 'fixture'
    cases.append({'label':name+'未知字段', 'definition':name, 'value':bad, 'expected':False})
record = {
 'schema':'kernel-output-v3','run_id':'review_fixture','execution_mode':'finite_concrete',
 'port_meeting':'shared_edge_opposite','profile_id':'kernel_profile_v1',
 'producer':{'kind':'manual_expected','path':str(HERE / 'check_consistency.py'),'claim':'仅结构试样'},
 'status':'invalid_input','fingerprints':[],'parameter_assignment':None,'input_history':None,
 'uncovered_axes':[],'trace':None,'validation_scope':None,'open_items':['结构试样，无实际运行'],
}
cases.append({'label':'RunRecord结构正例','definition':'RunRecord','value':record,'expected':True})
bad=deepcopy(record);bad['verification_scope']=bad.pop('validation_scope')
cases.append({'label':'验证范围旧字段拒收','definition':'RunRecord','value':bad,'expected':False})
js = """const fs=require('fs'); const Ajv=require(process.argv[1]);
const p=JSON.parse(fs.readFileSync(0,'utf8'));const a=new Ajv({strict:false,allErrors:true});
if(!a.validateSchema(p.schema))throw Error(JSON.stringify(a.errors));
const validators={}; const results=p.cases.map(c=>{let v=validators[c.definition];
if(!v)v=validators[c.definition]=a.compile({$schema:p.schema.$schema,$defs:p.schema.$defs,$ref:'#/$defs/'+c.definition});
return {label:c.label,expected:c.expected,actual:v(c.value),errors:v.errors};});
console.log(JSON.stringify(results));"""
proc=subprocess.run(['node','-e',js,AJV],input=json.dumps({'schema':schema,'cases':cases}),
                    capture_output=True,text=True,check=True)
results=json.loads(proc.stdout)
check(all(row['actual']==row['expected'] for row in results), 'AJV批量字段删改正负例全部符合预期')
dump('schema正负例.json', {'count':len(cases),'cases':results,
     'scope':'局部形状核验，不核数量合法性、跨字段守恒或独立运行'})

# 对现行两段谓词及r8全部60行做独立真值复算。
transfer_text = read(SPEC / '受限转移定义.md')
reply_text = read(SPEC / '参数轴-对内核输入请求的答复.md')
expressions = []
for body in [transfer_text, reply_text]:
    matches = re.findall(r'`(len\(U\)>=2 and [^`]+)`', body)
    check(matches == ['len(U)>=2 and any(w in assigned_slots for w in E)'], '现行竞争停止谓词的指派前件完整')
    expressions.append(matches[0])
previous_guard = json.loads(read(SPEC / '第五轮规格修订-r8/停止条件复算.json'))
truth_rows = []
for row in previous_guard['truth_table']:
    expected = row['new_species_count'] >= 2 and bool(set(row['empty_slots']) & set(row['assigned_empty_slots']))
    check(expected == row['expected_stop'] == row['transfer_stop'] == row['reply_stop'],
          'r8停止真值逐行复核：' + str(len(truth_rows)))
    truth_rows.append({'new_species_count':row['new_species_count'], 'empty_slots':row['empty_slots'],
                       'assigned_empty_slots':row['assigned_empty_slots'], 'stop':expected})
check(len(truth_rows) == 60, 'r8停止前件共60组，含未指派继续分支')
dump('停止前件独立复算.json', {'expressions':expressions, 'cases':truth_rows})

# 对上一席清单逐字节核验；活动K线来源差异独立登记，不倒改旧证据。
previous = json.loads(read(SPEC / '第五轮规格修订-r8/交付清单.json'))
manifest_rows = [{'path':p,'recorded':h,'current':digest(p),'matches':h==digest(p)}
                 for p,h in previous['sha256'].items()]
check(all(row['matches'] for row in manifest_rows), 'r8交付清单35项哈希仍匹配')
old_sources=json.loads(read(SPEC / '第五轮规格修订-r8/本轮自查结果.json'))['sources']
source_rows=[{'path':p,'recorded':h,'current':digest(p),'matches':h==digest(p)} for p,h in old_sources.items()]
dump('r8来源复核.json', {'manifest':manifest_rows,'observed_sources':source_rows,
     'scope':'历史证据与当前字节核对；并行K线变化不是S线写入'})
protected = [ROOT / p for p in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']]
source_paths = protected + list(SPEC.glob('*.md')) + [schema_path,SPEC/'内核配置-v1.json',SPEC/'check_revision.py',
    build_path,SPEC/'第五轮规格修订/check_round5.py',SPEC/'第五轮规格修订/cycle_key_reference.py',
    SPEC/'第五轮规格修订-r8/check_round8.py'] + list(KERNEL.glob('*.rs'))
dump('本席读取指纹.json',{str(p):digest(p) for p in source_paths})
check(all(p.suffix in ['.py','.md','.log','.json'] for p in HERE.iterdir()), '本目录产物类型符合证据纪律')
dump('一致性自查.json', {'status':'PASS','checks':checks,'count':len(checks),
    'schema_cases':len(cases),'schema_sha256':digest(schema_path),'findings':[],
    'scope':'一致性复核，未运行K线测试，未认证完整目标'})
print(json.dumps({'status':'PASS','checks':len(checks),'schema_cases':len(cases)},ensure_ascii=False))
