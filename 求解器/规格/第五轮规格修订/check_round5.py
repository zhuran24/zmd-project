"""第五轮规格自查：结构/字段/负例/条件算术；不冒充Rust实现或普遍证明。"""
from pathlib import Path
from copy import deepcopy
from fractions import Fraction
from itertools import permutations
import argparse,hashlib,json,re,subprocess,sys
# 借用系统已有AJV2020，只读加载；不安装依赖或创建缓存。
AJV_PATH='/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js'
class Draft202012Validator:
    def __init__(self,schema):self.schema=schema
    @staticmethod
    def _call(payload):
        script="const fs=require('fs');const Ajv=require(process.argv[1]);const a=new Ajv({strict:false,allErrors:true});const p=JSON.parse(fs.readFileSync(0,'utf8'));let ok;if(p.meta){ok=a.validateSchema(p.schema);console.log(JSON.stringify(ok?[]:a.errors));}else{const v=a.compile(p.schema);ok=v(p.value);console.log(JSON.stringify(ok?[]:v.errors));}"
        r=subprocess.run(['node','-e',script,AJV_PATH],input=json.dumps(payload),text=True,capture_output=True,check=True)
        return json.loads(r.stdout)
    @classmethod
    def check_schema(cls,schema):assert not cls._call({'schema':schema,'meta':True})
    def iter_errors(self,value):return self._call({'schema':self.schema,'value':value})
    def validate(self,value):
        errors=self.iter_errors(value)
        assert not errors,errors[:3]

from cycle_key_reference import cycle_key,key_bytes,number,PRODUCTS
def time(value):return {"kind":"rational","value":{"value":str(Fraction(value)),"category":"候选"}}
here=Path(__file__).resolve().parent;spec=here.parent;root=spec.parent.parent
parser=argparse.ArgumentParser(description='第五轮规格结构自查，输出限本线目录')
parser.add_argument('--output-dir',type=Path,default=here)
args=parser.parse_args();output_dir=args.output_dir.resolve()
assert output_dir.is_relative_to(spec) and not output_dir.is_relative_to(spec/'复核/约减'), '输出须在规格线写权内'
output_dir.mkdir(parents=True,exist_ok=True)
results=[]
def check(value,label):
    assert value,label
    results.append(label)
def dump(name,value): (output_dir/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
schema=json.loads((spec/'内核输出.schema.json').read_text());Draft202012Validator.check_schema(schema)
check(True,'Draft 2020-12 schema元验证')
def validator(name):return Draft202012Validator({'$schema':schema['$schema'],'$defs':schema['$defs'],'$ref':'#/$defs/'+name})
def rejects(name,value):return bool(list(validator(name).iter_errors(value)))
config=json.loads((spec/'内核配置-v1.json').read_text())
axes=config['axes'];check(len(axes)==99,'99轴未增删')
from collections import Counter
check(Counter(e['disposition'] for e in axes.values())=={'本版选值':55,'超出覆盖即停':18,'由输入全称量化':15,'已定':11},'55/18/15/11处置计数保持')
check(set(schema['$defs']['CycleResult']['properties']['parameter_point']['anyOf'][0]['properties']['input_axes']['required'])=={k for k,v in axes.items() if v['disposition']=='由输入全称量化'},'证书input_axes恰15个输入轴')
for name in ['Tick','DeltaTick']:
 check('warehouse_ledger' in schema['$defs'][name]['required'],name+'逐刻台账必填')
# 使用旧记录的真实字段仅构造结构/映射试样，不宣称它已迁移或重跑。
old=json.loads((root/'求解器/数据/样例/混做粉碎机两下游-运行记录-kernel.json').read_text())
state=deepcopy(old['trace']['ticks'][-1]['state']);state['environment']['stage']='zero_intervention'
state['semantic_context']['judgment_context']['value']['next_event']=None
state['semantic_context']['arbitration']['warehouse_empty_slot_order']=[]
key=cycle_key(state);validator('CycleKey').validate(key)
check(True,'规范键结构通过；字段映射试样非执行证书')
# 按字段表只平移动态时间；固定建造/参数历史不动。
shifted=deepcopy(state);delta=31;t=number(state['environment']['time'])
shifted['environment']['time']=time(t+delta)
for slot in shifted['inventory']:
 for content in slot['contents']:
  if content['entered_at'] is not None:content['entered_at']=time(number(content['entered_at'])+delta)
for gate in shifted['logistics']['gate_counters']:
 if gate['window_started_at'] is not None:gate['window_started_at']=time(number(gate['window_started_at'])+delta)
sc=shifted['semantic_context'];sc['judgment_context']['value']['instant']=time(t+delta)
for k in ['window_start','window_end']:sc['tick_context']['value'][k]=time(number(sc['tick_context']['value'][k])+delta)
for p in sc['pending_events']['value']:
 p['trigger']['value']=time(number(p['trigger']['value'])+delta)
 parts=p['event'].split('|');parts[1]=str(int(parts[1])+delta);p['event']='|'.join(parts)
check(key_bytes(key)==key_bytes(cycle_key(shifted)),'平移动态绝对时刻31tick后键相同')
changed=deepcopy(state);changed['inventory'].reverse();changed['progress'].reverse();changed['warehouse']['slots'].reverse()
check(key_bytes(key)==key_bytes(cycle_key(changed)),'无序记录数组逆序后键相同')
changed=deepcopy(state)
for row in changed['warehouse']['slots']:
 if row['item'] in ['源矿','蓝铁矿']:row['quantity']['value']='1'
check(key_bytes(key)==key_bytes(cycle_key(changed)),'两矿正代表量改变后键相同')
changed=deepcopy(state);changed['warehouse']['slots'].append({'slot':'product_fixture','item':PRODUCTS[0],'quantity':{'value':'79999','category':'候选'},'empty_identity':{'status':'not_applicable','value':None,'basis':['结构试样']}})
check(key_bytes(key)==key_bytes(cycle_key(changed)),'成品数量及无出口标签移出键')
changed=deepcopy(state);row=next(r for r in changed['warehouse']['slots'] if r['item']=='荞花');row['quantity']['value']=str(number(row['quantity'])-1)
check(key_bytes(key)!=key_bytes(cycle_key(changed)),'植物仓库存量不得误删')
changed=deepcopy(state);active=[x for x in changed['inventory'] if x['contents']];check(bool(active),'试样有非仓库货物')
active[0]['contents'][0]['quantity']['value']=str(number(active[0]['contents'][0]['quantity'])+1)
check(key_bytes(key)!=key_bytes(cycle_key(changed)),'非仓库件数改变键必须改变')
changed=deepcopy(state);changed['semantic_context']['arbitration']['warehouse_empty_slot_order']=['observable_empty']
try:cycle_key(changed)
except AssertionError:check(True,'非空O拒绝规范，不能静默删去')
else:raise AssertionError('非空O漏拒')
# 全部字段必须有表项，不以行数代替；按当前Rust模型字段自动核名。
model=(root/'求解器/crates/kernel/src/model.rs').read_text();section=(spec/'受限转移定义.md').read_text().split('### 6.2')[1].split('### 6.3')[0]
state_types=['Content','Inventory','WarehouseSlot','Warehouse','Cooldown','Progress','Level','Side','PollMemory','Gate','Logistics','Environment','Arbitration','ParameterValue','SemanticContext','State','Pending']
fields={}
for kind in state_types:
 body=re.search(r'pub struct '+kind+r' \{(.*?)\n\}',model,re.S)[1];fields[kind]=re.findall(r'pub (\w+):',body)
 for field in fields[kind]:check(field in section,f'字段落点 {kind}.{field}')
dump('StateSeed字段清点.json',fields)
closure=(root/'求解器/crates/kernel/src/transition.rs').read_text().split('fn closure_key')[1].split('.map_err')[0]
components=['warehouse','inventory','progress','memory','active_channels','blocked_channels','gate_counters','connection_order','arbitration','pending','usage']
check(all(re.search(r'&self\.(?:state\.(?:logistics\.|semantic_context\.)?)?'+x+r'\b',closure) for x in components),'私有closure_key实际11项逐名对照')
# 容量反例与取空身份后效的最小条件算术，不伪造完整可达布局。
capacity=80000
case={'warehouse_before':79999,'whole_box':2,'actual_accepts':79999+2<=capacity,'representative_accepts':0+2<=capacity,'actual_warehouse_after':79999,'family_under_capacity_holds':79999<capacity}
check(not case['actual_accepts'] and case['representative_accepts'] and case['family_under_capacity_holds'],'F未满仍允许整箱拒收，级二容量反例成立')
check((79999+1<=capacity)!=(80000+1<=capacity),'矿量不只经非空使用：回矿容量反例')
dump('提升容量卡点.json',case)
# 同级U、独占首格、每组1、下tick先腾空；按§3.2–3.3逐模板授权。
polling=[]
for order in permutations(range(3)):
 cursor=0;successes=[];counts=[0]*3
 for tick in range(12):
  stock=1;occupied=[False]*3;used=[0]*3;seen=set();tick_success=[]
  for sweep in range(20):
   boundary=(stock,tuple(occupied),tuple(used),cursor)
   if boundary in seen:break
   seen.add(boundary)
   for c in order:
    physical=[bool(stock and not occupied[i] and not used[i]) for i in range(3)]
    grant=next((i for j in range(3) if physical[i:=(cursor+j)%3]),None)
    source=(grant==c);target=physical[c]
    if source and target:stock-=1;occupied[c]=True;used[c]=1;tick_success.append(c);counts[c]+=1
    if source:cursor=(c+1)%3
  else:raise AssertionError('闭包未结束')
  check(len(tick_success)==1,'同级场景每tick恰一件 '+str(order)+'/'+str(tick))
  successes+=tick_success
 check(successes==[i%3 for i in range(12)] and max(counts)-min(counts)<=1,'同级场景6种模板序循环成功 '+str(order))
 polling.append({'template_order':order,'successes':successes,'counts':counts})
dump('轮询均分局部推演.json',polling)
# Schema正负例只验证结构：必填台账、不同停止结果与15轴。
q=lambda n:{'value':str(n),'category':'候选'}
ledger={k:[] for k in ['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment','totals']}
for item in PRODUCTS:ledger['totals'].append({'item':item,**{k:q(0) for k in ['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment','actual_inbound']}})
tick=deepcopy(old['trace']['ticks'][-1]);tick['warehouse_ledger']=ledger
validator('Tick').validate(tick)
for field in ['wireless_inbound','port_outbound','external_supply','representative_adjustment']:
 bad=deepcopy(tick);del bad['warehouse_ledger'][field];check(rejects('Tick',bad),'schema拒绝漏台账 '+field)
for name in ['Tick','DeltaTick']:
 bad=deepcopy(tick)
 if name=='DeltaTick':del bad['state'];bad['delta']=[]
 del bad['warehouse_ledger'];check(rejects(name,bad),name+'不能漏仓库账')
run=deepcopy(old);run['schema']='kernel-output-v3';run['execution_mode']='production_abstraction';run['port_meeting']='shared_edge_opposite'
for row in run['trace']['ticks']:row['warehouse_ledger']=deepcopy(ledger)
validator('RunRecord').validate(run)
point={'assignment':run['parameter_assignment'],'input_axes':{k:{'status':'specified','value':{'fixture':True},'basis':['仅schema结构试样']} for k,v in axes.items() if v['disposition']=='由输入全称量化'}}
cycle={'period':q(1),'start_time':time(t),'end_time':time(t+1),'start_state':state,'end_state':shifted,'start_key':key,'end_key':key,'normalization':{'schema':'cycle-normalization-v1','definition':{'path':'受限转移定义.md','sha256':'0'*64},'basis':['结构试样非证书'],'domain_checks':['D.1','D.2','D.3','D.4','D.5']},'ledger':[{'time':time(t+1),'warehouse_ledger':ledger}],'totals':ledger['totals'],'rates':[{'item':item,'inbound':q(0),'period':q(1),'average':q(0),'target':q(target),'comparison':'lt'} for item,target in zip(PRODUCTS,['3/5','11/20'])],'acceptance':[{'time':time(t+1),'products':[{'item':i,'capacity_available':True,'physical_path_exists':True,'selected_acceptance':True} for i in PRODUCTS]}],'lift':None}
result={'schema':'kernel-cycle-v1','result_id':'schema_only_fixture','status':'cycle_found','level':'production_part','execution_mode':'production_abstraction','port_meeting':'shared_edge_opposite','seed':{'state':state,'reachability':{'status':'unresolved','value':None,'basis':['仅结构测试']},'source_event':'fixture'},'parameter_point':point,'reading':{'port_meeting':'shared_edge_opposite','warehouse_acceptance':'capacity_and_path','acceptance_quantifier':'per_instant','cycle_interpretation':'production_projection','remaining_assumptions':['仅结构测试，不是实跑证书']},'support_domain':{'name':'production_v1','checks':[],'uncovered':['语义关联未核']} ,'replay_input':{'schema':'kernel-input-v3',**{k:{} for k in ['layout','settings','parameters','initial_state','timeline','environment']}},'run_record':run,'cycle':cycle,'stop':None,'budget':{'max_ticks':5,'max_sweeps':100,'completed_ticks':1},'open_items':['结构试样不落盘为证书']}
validator('CycleResult').validate(result);check(True,'cycle_found结构正例通过，未冒充语义通过')
for mutation,label in [('port_meeting','缺相遇读法'),('cycle','成功无cycle')]:
 bad=deepcopy(result);del bad[mutation];check(rejects('CycleResult',bad),'schema拒绝'+label)
bad=deepcopy(result);del bad['parameter_point']['input_axes']['damping.branch'];check(rejects('CycleResult',bad),'schema拒绝15轴缺一')
bad=deepcopy(result);bad['level']='full_base';check(rejects('CycleResult',bad),'schema拒绝full_base无提升对象')
for status,kind in [('inconclusive','resource'),('stopped','unresolved'),('counterexample','low_rate')]:
 trial=deepcopy(result);trial['status']=status;trial['stop']={'kind':kind,'axis':'fixture','event':None,'time':time(t),'reason':'结构测试','partial_events':[]}
 if status!='counterexample':trial['cycle']=None
 validator('CycleResult').validate(trial);check(True,status+'结构正例')
 bad=deepcopy(trial);bad['stop']=None;check(rejects('CycleResult',bad),status+'必须附停止原因')
# 保留正式与源码的原字节；不修改K/R线文件。
fingerprints=json.loads((here/'开工只读指纹.json').read_text())
protected_names={'《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt'}
protected={p:h for p,h in fingerprints.items() if Path(p).parent==root and Path(p).name in protected_names}
check(len(protected)==4 and all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in protected.items()),'三份正式文件及候选约束4份指纹未变')
shared={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in fingerprints if p not in protected}
dump('活动内核来源.json',{'current':shared,'changed_since_round5_start':[p for p,h in shared.items() if h!=fingerprints[p]],'scope':'K线活动源码只读观测；不以旧轮次字节限制本轮实现'})
# 新证据目录只允许脚本、日志、json、md。
check(all(p.is_file() and p.suffix in ['.py','.log','.json','.md'] for p in output_dir.iterdir()),'本证据目录无编译/缓存/仓库快照')
report={'status':'PASS','scope':'规格结构、逐字段定位、规范键正反例、条件局部推演及容量算术；非Rust回归/独立证书核验/一般规则证明','checks':results,'check_count':len(results),'open_items':['K线迁移和端到端场景未在本席执行','级二F容量条件不足','普遍相容性和所有种子/参数/读法覆盖未完成']}
dump('自查结果.json',report);print(json.dumps({'status':'PASS','check_count':len(results)},ensure_ascii=False))
