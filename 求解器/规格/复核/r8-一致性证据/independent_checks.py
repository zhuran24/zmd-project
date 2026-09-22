"""第八轮一致性独立核对：字段集合、局部键、分支表及两处文档冲突。"""
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import subprocess

output_dir = Path(__file__).resolve().parent
spec_dir = output_dir.parent.parent
root = spec_dir.parent.parent
schema = json.loads((spec_dir / '内核输出.schema.json').read_text())
defs = schema['$defs']
results = []

def check(value, name):
    assert value, name
    results.append(name)

def save(name, value):
    (output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

# 根据正文独立抄录字段集，不从生成脚本的定义反推期望。
expected = {
    'WarehouseLedger': 'core_inbound wireless_inbound port_outbound external_supply player_withdrawal representative_adjustment totals',
    'CoreInbound': 'event channel port item quantity',
    'WirelessInbound': 'event unit item quantity',
    'PortOutbound': 'event channel port slot item quantity',
    'ExternalSupply': 'event mode item quantity',
    'PlayerWithdrawal': 'event slot item quantity',
    'RepresentativeAdjustment': 'item quantity reason',
    'WarehouseTotal': 'item core_inbound wireless_inbound port_outbound external_supply player_withdrawal representative_adjustment actual_inbound',
    'CycleResult': 'schema result_id status level execution_mode port_meeting seed parameter_point reading support_domain replay_input run_record cycle stop budget open_items',
    'Cycle': 'period start_time end_time start_state end_state start_key end_key normalization ledger totals rates acceptance lift',
    'CycleRate': 'item inbound period average target comparison',
    'CycleKey': 'schema domain state product_acceptance',
    'Acceptance': 'time products',
    'StateSeed': 'layout_snapshot settings_anchor warehouse inventory progress logistics environment semantic_context',
    'RunRecord': 'schema run_id profile_id producer status fingerprints parameter_assignment input_history uncovered_axes trace validation_scope open_items execution_mode port_meeting',
}
for name, fields in expected.items():
    field_set = set(fields.split())
    check(set(defs[name]['properties']) == field_set, name + '属性恰集')
    check(set(defs[name]['required']) == field_set, name + '必填恰集')
    check(defs[name]['additionalProperties'] is False, name + '封闭顶层')
for name in ['Tick', 'DeltaTick']:
    check(defs[name]['properties']['warehouse_ledger'] == {'$ref': '#/$defs/WarehouseLedger'}, name + '共用同一台账定义')
    check('warehouse_ledger' in defs[name]['required'], name + '台账必填')
check(defs['FullTrace']['properties']['ticks']['items'] == {'$ref': '#/$defs/Tick'}, '全状态记录没有旧内联Tick')
check(defs['CheckpointTrace']['properties']['ticks']['items']['oneOf'] == [{'$ref': '#/$defs/Tick'}, {'$ref': '#/$defs/DeltaTick'}], '增量记录共用Tick/DeltaTick')
check('gate_identity_maintenance' in defs['Event']['properties']['operation']['enum'], 'I事件类型登记')
config = json.loads((spec_dir / '内核配置-v1.json').read_text())
input_axes = {name for name, entry in config['axes'].items() if entry['disposition'] == '由输入全称量化'}
point = defs['CycleResult']['properties']['parameter_point']['anyOf'][0]
check(len(input_axes) == 15 and set(point['properties']['input_axes']['required']) == input_axes, '15输入轴证书恰集')
for axis in ['warehouse.external_supply', 'warehouse.periodic_lift', 'damping.branch']:
    entry = config['axes'][axis]
    line = next(line for line in (spec_dir / '受限模型声明.md').read_text().splitlines() if line.startswith('| `' + axis + '` |'))
    check('`' + json.dumps(entry['value'], ensure_ascii=False, separators=(',', ':')) + '`' in line, axis + '声明配置取值一致')
save('三轴登记.json', {axis: config['axes'][axis] for axis in ['warehouse.external_supply', 'warehouse.periodic_lift', 'damping.branch']})

# 引用实际closure_key完整元组，而非只查名称是否出现。
source = (root / '求解器/crates/kernel/src/transition.rs').read_text()
block = source.split('fn closure_key(&self)')[1].split('.map_err')[0]
components = re.findall(r'&self\.([\w.]+),', block)
expected_components = ['state.warehouse', 'state.inventory', 'state.progress', 'memory', 'state.logistics.active_channels', 'state.logistics.blocked_channels', 'state.logistics.gate_counters', 'state.logistics.connection_order', 'state.semantic_context.arbitration', 'pending', 'usage']
check(components == expected_components, 'closure_key完整11项及顺序一致')
save('闭包字段.json', components)

module_path = spec_dir / '第五轮规格修订/cycle_key_reference.py'
module_spec = importlib.util.spec_from_file_location('cycle_reference_r8', module_path)
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)
record = json.loads((root / '求解器/数据/样例/混做粉碎机两下游-运行记录-kernel.json').read_text())
state = deepcopy(record['trace']['ticks'][-1]['state'])
state['environment']['stage'] = 'zero_intervention'
state['semantic_context']['judgment_context']['value']['next_event'] = None
state['semantic_context']['arbitration']['warehouse_empty_slot_order'] = []
key = module.key_bytes(module.cycle_key(state))

def decide(value):
    return {'status': 'specified', 'value': value, 'basis': ['仅字段编码试样，不是可达证书']}

def time(value):
    return {'kind': 'rational', 'value': {'value': str(Fraction(value)), 'category': '候选'}}

def test_mutation(name, edit, same):
    changed = deepcopy(state)
    edit(changed)
    check((module.key_bytes(module.cycle_key(changed)) == key) == same, name)

test_mutation('纯依据变化不改键', lambda s: s['semantic_context']['judgment_context'].update(basis=['不同审计文案']), True)
test_mutation('已完成扫描轮变化不改键', lambda s: s['semantic_context']['judgment_context']['value'].update(round=9999, next_template=0, ordered_events=[]), True)
test_mutation('省略的已成功账不改键', lambda s: s['semantic_context']['tick_context']['value'].update(movements=[], internal_passages=[]), True)
test_mutation('布局锚点变化必须异键', lambda s: s.update(layout_snapshot='changed_anchor'), False)
test_mutation('设置锚点变化必须异键', lambda s: s['settings_anchor'].update(event='changed_anchor'), False)
test_mutation('植物仓库历史身份不得删除', lambda s: s['warehouse']['slots'].append({'slot': 'other_history', 'item': None, 'quantity': {'value': '0', 'category': '候选'}, 'empty_identity': decide('钢块')}), False)
# 单独构造门/待事件字段试样，只检编码，不声称它们属于该记录布局。
t = module.number(state['environment']['time'])
gated = deepcopy(state)
gated['logistics']['gate_counters'] = [{'unit': 'gate_fixture', 'total_received': {'value':'2','category':'候选'}, 'window_received':{'value':'1','category':'候选'}, 'window_started_at':time(t-2), 'blocked_reasons':['window_exhausted','identity_mismatch']}]
gated['semantic_context']['pending_events'] = decide([{'event':f'W|{t+3}|gate_fixture','operation':'gate_window_expiry','target':'gate_fixture','trigger':{'kind':'at_time','value':time(t+3)},'predecessors':[],'status':'waiting'}])
gated_key = module.cycle_key(gated)
check(gated_key['state']['logistics']['gate_counters'][0]['window_started_at'] == {'elapsed': {'value': '2'}}, '窗口起点归一为精确elapsed')
check(gated_key['state']['semantic_context']['pending_events']['value'][0]['event'] == ['gate_window_expiry','gate_fixture','3'], '待事件身份按类型目标剩余时长归一')
changed = deepcopy(gated)
changed['logistics']['gate_counters'][0]['blocked_reasons'].reverse()
check(module.key_bytes(module.cycle_key(changed)) == module.key_bytes(gated_key), '门原因集合逆序不改键')
changed['logistics']['gate_counters'][0]['total_received']['value'] = '3'
check(module.key_bytes(module.cycle_key(changed)) != module.key_bytes(gated_key), '累计计数精确保留')

# v2定义域的局部核算：三个出支7个非空子集，24张总选择表。
channels = ('a','b','c')
subsets = [s for n in range(1,4) for s in combinations(channels,n)]
policies = [dict(zip(subsets, choices)) for choices in product(*subsets)]
check(len(subsets) == 7 and len(policies) == 24, '三出支局部总表共有24种选择')
policy = {s:s[0] for s in subsets}
path = [channels, ('b','c'), ('c',), channels]
check([policy[s] for s in path] == ['a','b','c','a'], '切支和恢复按同集合恢复同选')
save('分支表局部核对.json', {'非空子集':subsets,'局部总表数':len(policies),'切换集合':path,'选择':[policy[s] for s in path],'说明':'只核输入§5.3与转移§3.4函数定义相同，不是内核端到端测试'})

# 发现1：当前答复保留旧停止前件；与主席已定条件及转移逐项比较。
new_items = ['高容谷地电池','精选荞愈胶囊']
empty_slots = ['W_empty']
assigned_slots = ['W_ore_a','W_ore_b']
old_stop = len(new_items) >= 2 and bool(empty_slots)
current_stop = len(new_items) >= 2 and any(s in assigned_slots for s in empty_slots)
plan = {}
for index,item in enumerate(sorted(new_items, key=lambda s:s.encode('utf-8'))):
    plan[item] = empty_slots[index] if index < len(empty_slots) else 'W_new_' + item.encode('utf-8').hex()
check(old_stop and not current_stop, '旧当前答复会额外停止无指派空格案例')
save('停止条件反例.json', {'scope':'有限具体运行的局部传输守卫，不是级一D域/可达循环证书','box_items':{item:1 for item in new_items},'U':new_items,'E':empty_slots,'O':empty_slots,'assigned_slots':assigned_slots,'答复第24行停止':old_stop,'现行转移第90行停止':current_stop,'现行规范落格':plan,'容量检查':'各物种入1件，不超过80000；假定有电开关开冷却0且标签无冲突','basis':['规则L13/L36/L41/L73','任务书4§3.3','受限转移定义§4.3']})

# 发现2：按错误字段名交付会由当前封闭schema拒收；以结构试样作单变量变异。
q = lambda n: {'value':str(n),'category':'候选'}
ledger = {k:[] for k in ['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment','totals']}
for item in module.PRODUCTS:
    ledger['totals'].append({'item':item, **{k:q(0) for k in ['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment','actual_inbound']}})
run = deepcopy(record)
run.update(schema='kernel-output-v3', execution_mode='finite_concrete', port_meeting='shared_edge_opposite')
for tick in run['trace']['ticks']:
    tick['warehouse_ledger'] = deepcopy(ledger)
bad = deepcopy(run)
bad['verification_scope'] = bad.pop('validation_scope')
node_script = "const fs=require('fs');const Ajv=require(process.argv[1]);const p=JSON.parse(fs.readFileSync(0,'utf8'));const v=new Ajv({strict:false,allErrors:true}).compile(p.schema);console.log(JSON.stringify(p.values.map(x=>({valid:v(x),errors:v.errors}))));"
payload = {'schema':{'$schema':schema['$schema'],'$defs':defs,'$ref':'#/$defs/RunRecord'},'values':[run,bad]}
result = subprocess.run(['node','-e',node_script,'/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'],input=json.dumps(payload),text=True,capture_output=True,check=True)
validation = json.loads(result.stdout)
check(validation[0]['valid'] and not validation[1]['valid'], 'validation_scope改名verification_scope被拒收')
save('字段名反例.json', {'scope':'仅schema结构试样，未声称迁移或轨迹合法','原字段':validation[0],'改名后':validation[1]})
save('独立核对结果.json', {'checks':results,'check_count':len(results),'status':'PASS','note':'两条冲突反例已成立；其余通过项只作所列有限一致性证据'})
print(json.dumps({'status':'PASS','check_count':len(results)},ensure_ascii=False))
