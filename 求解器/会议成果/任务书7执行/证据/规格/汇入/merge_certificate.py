from pathlib import Path
import json, copy, hashlib
R=Path('/home/zhuran24/zmd-research-fresh'); S=R/'求解器/规格'
p=S/'内核输出.schema.json'; schema=json.loads(p.read_text())
assert schema['$id']=='urn:zmd:kernel-output-v3'
def obj(props,required=None):
 return {'type':'object','properties':props,'required':list(props) if required is None else required,'additionalProperties':False}
def arr(item,minimum=0): return {'type':'array','items':item,'minItems':minimum}
def ref(name): return {'$ref':'#/$defs/'+name}
def const(x): return {'const':x}
string={'type':'string','minLength':1}
strings=arr(string)
boolean={'type':'boolean'}

# 旧版本不在新schema验收域；实现迁移由任务8完成。
def migrate(x):
 if isinstance(x,str):
  return x.replace('kernel-output-v3','kernel-output-v4').replace('kernel-cycle-v2','kernel-cycle-v3').replace('production-cycle-key-v1','phase-cycle-key-v1').replace('production_v1','phase_production_v1').replace('cycle-normalization-v1','cycle-normalization-v2').replace('observable_base_with_withdrawal','concrete_base_with_withdrawal').replace('full_base','concrete_full_cycle')
 if isinstance(x,list): return [migrate(v) for v in x]
 if isinstance(x,dict): return {k:migrate(v) for k,v in x.items()}
 return x
schema=migrate(schema); D=schema['$defs']
schema['$id']='urn:zmd:kernel-output-v4'
D['CycleKey']['properties']['product_acceptance']['items']['properties']['state']=const('receivable_at_all_checks')
D['CycleKey']['description']='phase-cycle-key-v1按受限转移§6.2逐字段规范；结构校验之外必须核未来读取前件、真实耗时与后继保持。完整StateSeed用于恢复。'
D['EvidenceScope']=obj({
 'kind':{'enum':['direct_invariant','conditional_local_proof','production_cycle','concrete_full_cycle','diagnostic','unresolved']},
 'support_domain':arr(string,1),
 'fixed_parameter_lifecycle':string,
 'context_bindings':arr(ref('ProofSource')),
 'initial_state_coverage':obj({'description':string,'exact_reachable_set_enumerated':boolean}),
 'direction':{'enum':['conditional_witness','sufficient','counterexample','diagnostic','unresolved']},
 'review_status':{'enum':['author_checked','pending','independently_reviewed']},
 'proof_sources':arr(ref('ProofSource')),
})
D['ProofCheck']=obj({'condition':string,'status':{'enum':['pass','unresolved','not_claimed']},'evidence':arr(string,1)})
def obligation(conditions):
 checks=arr(ref('ProofCheck'),len(conditions)); checks['maxItems']=len(conditions)
 checks['prefixItems']=[{'allOf':[ref('ProofCheck'),{'properties':{'condition':const(c)}}]} for c in conditions]
 result=obj({'status':{'enum':['proved','unresolved','not_claimed']},'proof_sources':arr(ref('ProofSource')),'checks':checks})
 result['allOf']=[{'if':{'properties':{'status':const('proved')},'required':['status']},'then':{'properties':{'proof_sources':{'minItems':1},'checks':{'items':{'properties':{'status':const('pass')}}}}}}]
 return result
FORWARD=['production_representation','warehouse_label_noninterference','candidate_and_actual_acceptance','successor_time_delivery_preservation']
REVERSE=['reachable_start','fixed_parameters','positive_real_duration','repeated_production','periodic_withdrawal_program','withdrawal_prefix_legality','product_balance','ore_and_other_warehouse_restoration','labels_and_all_effective_state_restoration','operation_precision']
UNIVERSAL=['all_initial_states','all_fixed_parameters','legal_offline_and_recovery','all_real_cycle_projections','all_positive_duration_cycles']
D['CycleCorrespondence']=obj({'forward_projection':obligation(FORWARD),'reverse_reconstruction':obligation(REVERSE),'all_reachable_cycles':obligation(UNIVERSAL)})
D['ReceptionScope']=obj({
 'checks':const('all_candidate_and_actual_checks'),
 'interval':string,
 'state_coverage':string,
 'recovery_state_coverage':string,
 'status':{'enum':['proved','unresolved']},
 'proof_sources':arr(ref('ProofSource')),
})
D['ReceptionScope']['allOf']=[{'if':{'properties':{'status':const('proved')}},'then':{'properties':{'proof_sources':{'minItems':1}}}}]
cycle=D['Cycle']; cycle['properties'].pop('lift'); cycle['required'].remove('lift')
cycle['properties']['correspondence']=ref('CycleCorrespondence'); cycle['required'].append('correspondence')
cycle['properties']['reception_scope']=ref('ReceptionScope'); cycle['required'].append('reception_scope')
cycle['properties']['normalization']['properties']['mapping_proof']=ref('ProofSource')
cycle['properties']['normalization']['required'].append('mapping_proof')
cycle['description']='周期用真实正时长；ledger覆盖实际推进段，零时失败环另核。全部数量、时差、端点和入库账由语义校验复算。'

run=D['RunRecord']
run['properties']['evidence_scope']=ref('EvidenceScope'); run['required'].append('evidence_scope')
run['allOf']=[{'properties':{'evidence_scope':{'properties':{'kind':const('diagnostic'),'direction':const('diagnostic')}}}}]
cr=D['CycleResult']
cr['properties']['evidence_scope']=ref('EvidenceScope'); cr['required'].append('evidence_scope')
cr['properties']['environment_assumption']=const('仓库收得下成品。'); cr['required'].append('environment_assumption')
cr['properties']['status']['enum'].append('diagnostic_cycle')
# 成功、低产诊断共用完整周期材料；停止外壳保持原约束。
for branch in cr['allOf']:
 test=branch.get('if',{}).get('properties',{})
 if test.get('status')=={'enum':['cycle_found','counterexample']}:
  test['status']['enum'].append('diagnostic_cycle')
 if test.get('level')=={'const':'concrete_full_cycle'}:
  branch['then']['properties']['cycle']['properties'].pop('lift',None)
  branch['then']['properties']['cycle']['properties']['correspondence']={'properties':{'reverse_reconstruction':{'properties':{'status':const('proved')}}}}
def cond(test,then): cr['allOf'].append({'if':{'properties':test,'required':list(test)},'then':{'properties':then}})
cond({'level':const('production_part')},{'reading':{'properties':{'cycle_interpretation':const('production_projection')}}})
cond({'level':const('concrete_full_cycle')},{'execution_mode':const('finite_concrete'),'reading':{'properties':{'cycle_interpretation':const('concrete_base_with_withdrawal')}}})
cond({'status':const('cycle_found'),'level':const('production_part')},{'evidence_scope':{'properties':{'kind':const('production_cycle'),'direction':const('conditional_witness')}}})
cond({'status':const('cycle_found'),'level':const('concrete_full_cycle')},{'evidence_scope':{'properties':{'kind':const('concrete_full_cycle'),'direction':const('conditional_witness')}}})
cond({'status':const('counterexample')},{'level':const('concrete_full_cycle'),'evidence_scope':{'properties':{'kind':const('concrete_full_cycle'),'direction':const('counterexample')}},'cycle':{'properties':{'correspondence':{'properties':{'reverse_reconstruction':{'properties':{'status':const('proved')}}}}}}})
cond({'status':const('diagnostic_cycle')},{'level':const('production_part'),'stop':{'type':'null'},'evidence_scope':{'properties':{'kind':const('diagnostic'),'direction':const('diagnostic')}}})
cond({'status':{'enum':['stopped','inconclusive','invalid_input']}},{'evidence_scope':{'properties':{'kind':{'enum':['diagnostic','unresolved']},'direction':{'enum':['diagnostic','unresolved']}}}})
cond({'status':{'enum':['cycle_found','counterexample']}},{'cycle':{'properties':{'reception_scope':{'properties':{'status':const('proved')}}}}})

# 字段可编码并非证明完成；证据类别支持直接条件证明，避免强制走执行器。
D['ProofCertificate']=obj({
 'schema':const('kernel-proof-v1'),'result_id':string,
 'environment_assumption':const('仓库收得下成品。'),
 'evidence_scope':ref('EvidenceScope'),
 'fingerprints':copy.deepcopy(cr['properties']['fingerprints']),
 'statement':string,
 'proof_status':{'enum':['proved','conditional','unresolved']},
 'obligations':arr(ref('ProofCheck'),1),
 'all_reachable_cycles':obligation(UNIVERSAL),
 'open_items':strings,
})
D['ProofCertificate']['allOf']=[
 {'properties':{'evidence_scope':{'properties':{'kind':{'enum':['direct_invariant','conditional_local_proof','diagnostic','unresolved']},'direction':{'enum':['sufficient','diagnostic','unresolved']}}}}},
 {'if':{'properties':{'proof_status':const('proved')}},'then':{'properties':{'evidence_scope':{'properties':{'proof_sources':{'minItems':1}}},'obligations':{'items':{'properties':{'status':const('pass')}}}}}},
]
schema['oneOf'].append(ref('ProofCertificate'))
# 两成品必须各出现一次，禁止重复电池两次通过形状校验。
for path in [('CycleKey','product_acceptance'),('Cycle','rates')]:
 a=D[path[0]]['properties'][path[1]]
 a['allOf']=[{'contains':{'properties':{'item':const(item)},'required':['item']},'minContains':1,'maxContains':1} for item in ['高容谷地电池','精选荞愈胶囊']]
D['Acceptance']['properties']['products']['allOf']=copy.deepcopy(D['Cycle']['properties']['rates']['allOf'])
# 取值和生命周期属于轴表全义务，schema至少拒绝两项已定机制的旧位置/值。
for axis_name, value in [('judgment.order_scope','fixed_run_order'),('transfer.failure_cooldown','every_attempt')]:
 params=D['Parameters']['properties']
 params['fixed'].setdefault('properties',{})[axis_name]={'allOf':[ref('Decision'),{'properties':{'value':const(value)}}]}
 params['fixed'].setdefault('required',[]).append(axis_name)
 for group in ['offline_mutable','fixedness_unproven']:
  params[group].setdefault('properties',{})[axis_name]=False
D['Parameters']['properties']['fixed'].setdefault('required',[]).append('judgment.order')
for group in ['offline_mutable','fixedness_unproven']:
 D['Parameters']['properties'][group].setdefault('properties',{})['judgment.order']=False
p.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')

s=(S/'内核输出.md').read_text()
rh=hashlib.sha256((R/'《明日方舟：终末地》游戏规则.txt').read_bytes()).hexdigest()
s=s.replace('31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff',rh).replace('31ced2a24fef',rh[:12])
s=s.replace('状态：任务书7任务1规则回填；已定规则与工程支持范围分开登记，完整语义与全称认证仍待后续推导、实现和复核。','状态：任务书7任务2、6证书契约已汇入，schema升版；Rust生成与语义验收由任务8实现，新增条件证明待独立复核。')
start=s.index('当前schema仍为'); end=s.index('## 1.',start)
s=s[:start]+'''当前契约为运行记录`kernel-output-v4`、循环结果`kernel-cycle-v3`和直接证明`kernel-proof-v1`，结构定义见[内核输出.schema.json](内核输出.schema.json)。旧记录保持历史版本，重核来源、转移、参数和证据范围后才生成新证书。结构通过与实际回放/证明复核分别验收。

'''+s[end:]
s=s.replace('kernel-output-v3','kernel-output-v4').replace('kernel-cycle-v2','kernel-cycle-v3')
s=s.replace('| schema、run_id | kernel-output-v4、唯一运行标识。 |','| schema、run_id | kernel-output-v4、唯一运行标识。 |\n| evidence_scope | §5.1公共证据范围；运行记录kind=diagnostic、direction=diagnostic，有限轨迹按实际范围报告。 |')
s=s.replace('当前普通运行未实现，数组必须[]，不能以此写入抽象代表化。','普通执行器未实现该动作时返回unsupported；抽象执行无拿取事件时数组为[]。具体完整周期按真实拿取填账，数学代表调整单列。')
s=s.replace('空箱/拒收无入库明细。','空箱/拒收无入库明细，transfer事件仍记录本次尝试和冷却重起5 tick。')
s=s.replace('史料接口：身份维护事件', '身份维护事件')
begin=s.index('身份维护事件`operation=gate_identity_maintenance`')
end=s.index('\n\n',begin)
s=s[:begin]+'''身份维护事件`operation=gate_identity_maintenance`的detail保存`{gates,removed_channels,restored_channels,reason_changes}`；reason_changes逐门给before/after原因集合。恢复判断读取原几何对接候选，前后图及指针完整后态从事件与StateSeed交叉核。event沿用全局唯一身份，属于非判定维护，不计通道成功额度。字符串detail须可解析成上述封闭对象；schema只验证封套，内容由语义验收核。旧仅有removed_channels的记录按其旧模型保留。（规则L16、L22、L64；受限转移§2.2、§3.4。）'''+s[end:]
begin=s.index('## 4.')
s=s[:begin]+'''## 4. 版本与引用边界

schema根oneOf区分RunRecord、CycleResult和ProofCertificate。当前版本分别为kernel-output-v4、kernel-cycle-v3、kernel-proof-v1；生产键为phase-cycle-key-v1、归一化为cycle-normalization-v2。新字段、状态含义及参数生命周期共同升版，旧输出须重核后重生。StateSeed完整原状态仍用于恢复，规范键用于判等。

引用对象`{path,sha256,producer,format}`四项必填，sha256为原始字节64位小写摘要，path相对证书目录或为绝对路径。先核摘要再解析，嵌套引用相对所属文件目录解析；producer身份与被引对象及实际工具相符。run_record_ref.format为kernel-output-v4/full_state_each_instant或kernel-output-v4/checkpoint_delta，replay_input_ref.format为kernel-input-v3。

record_mode=referenced时保存独立运行记录；none时从引用输入独立重建前缀及周期。两模式均锁全部依赖、起点、固定参数和预算。无周期的已装载结果保留last_state；装载前失败的replay_input_ref/seed/parameter_point/last_state可空，completed_ticks=0，并保存实际停止原因。指纹不符须重新验收。

## 5. 循环、真实反例及直接证明

### 5.1 公共证据范围

每条证据用evidence_scope保存kind、support_domain、fixed_parameter_lifecycle、context_bindings、initial_state_coverage、direction、review_status及proof_sources。kind取direct_invariant、conditional_local_proof、production_cycle、concrete_full_cycle、diagnostic、unresolved；direction取conditional_witness、sufficient、counterexample、diagnostic、unresolved。支持域写具体结构、状态、接收区间与未覆盖后态；固定判定规则贯穿所有时刻，其它参数按实际生命周期记录。initial_state_coverage含description及exact_reachable_set_enumerated，可靠包络未枚举精确可达集合时填false。review_status为author_checked、pending或independently_reviewed，证据引用用带完整指纹的ProofSource。

循环与涉及目标交付的直接证明均必填environment_assumption，固定为：

仓库收得下成品。

实际接收域reception_scope另列checks=all_candidate_and_actual_checks、interval、state_coverage、recovery_state_coverage、status和proof_sources；覆盖物理候选、最高可移动级、授权、核心与无线实际接收的全部检查。端点容量布尔量只作观察。通路、供电、开关和冷却是生产系统字段。任务L2、L9以及受限转移§6.5给此范围；实际环境义务不换算为固定拿取量或间隔。

当前99轴处置为22项已定、44项本版选值、18项工程停止、15项输入量化；逐名集合从被锁定轴表重建。判定作用域fixed_run_order和排序均在fixed，零传输冷却为every_attempt/F。15个输入轴为judgment.order、damping.branch、connection.build_order、connection.order、connection.tie、connection.belt_shape、transfer.phase、manufacturing.recipe_selection、manufacturing.input_slot_selection、initialization.warehouse_anchor、initialization.other_inventory、initialization.switches、initialization.build_timing、initialization.debug_end、warehouse.external_supply。

### 5.2 CycleResult与D域

顶层必填schema、result_id、status、level、execution_mode、port_meeting、seed、parameter_point、reading、support_domain、domain_report、fingerprints、record_mode、replay_input_ref、run_record_ref、last_state、cycle、stop、budget、open_items、evidence_scope、environment_assumption。未知键拒收。seed保存reachability及source_event；parameter_point保留完整assignment与15输入轴的实际值；指纹包括实际读取输入、目录、三份正式源、轴表、配置、语义、schema、实现及所有引用依赖。

status=cycle_found表示指定起点/参数的已核达标周期，kind随level取production_cycle或concrete_full_cycle，direction=conditional_witness；全族结论单列。低产生产循环缺真实反向对应时status=diagnostic_cycle、kind/direction=diagnostic、level=production_part。counterexample要求合法可达的完整低产周期，level/kind=concrete_full_cycle、direction=counterexample、stop.kind=low_rate，至少一个实际率低于目标且反向复原全部通过。

level只取production_part、concrete_full_cycle或null。生产部分execution_mode=production_abstraction、support_domain.name=phase_production_v1、reading.cycle_interpretation=production_projection；完整周期execution_mode=finite_concrete、解释为concrete_base_with_withdrawal。每种成品分别记ΔW=I−O−P；全矿指派给O=0；仓库确实复原时才令ΔW=0。实际入库I只来自核心与无线实际送出，代表调整单列。

domain_report仍按D.1—D.5恰五项保存condition/status/scope/locations/evidence，status=pass/fail/unresolved，scope=static/executed_prefix/cycle/not_checked。not_checked为unresolved。周期材料五项均pass/cycle；具体完整周期的D.1、D.5按保留真实外部过程和真实容量的模式核，代表化特有部分写明不采用的原因。D.2任何候选容量读点在读取前检查，D.3标签非干扰及D.4有效字段全程核，D.5只限定代表编码的工程容量安全。静态检查仅报告其实际范围，后续动态读点另验。

stopped对应unsupported/unresolved；inconclusive对应resource；invalid_input对应invalid_input。这三种cycle/level为null，保留已装载末态或装载前失败外壳。零传输冷却和判定固定性已有规则值，停止只报告尚缺实现/推导的具体后效。stop.partial_events只作未完成段审计。

### 5.3 cycle字段、键和对应义务

cycle必填period、start_time、end_time、start_state、end_state、start_key、end_key、normalization、ledger、totals、rates、acceptance、reception_scope、correspondence。period为真实正时长，两端完整状态和规范键均保存。normalization含schema=cycle-normalization-v2、definition、basis、domain_checks及mapping_proof，后者锁定所用逐字段映射、未来读取和后继/耗时保持证明。当前phase_production_v1仍只接已核整数D域；连续时域的通用字段可表示精确有理时长，实际执行支持另核。

ledger记录(a,b]内各实际推进段的warehouse_ledger，整数P tick执行恰P项；起点旧事件不重计。rates恰含电池和胶囊各一次，inbound取actual_inbound合计，average=inbound/period，目标为3/5与11/20，comparison精确取lt/eq/gt。acceptance保存观测，完整区间接收由reception_scope证明。

correspondence将以下三组义务分别保存status、proof_sources、checks。status取proved/unresolved/not_claimed；proved须有指纹证明且所有固定次序检查pass。结构校验约束列表齐全，语义验收逐项验证材料。

| 组 | 固定检查项，按列出次序 |
|---|---|
| forward_projection | production_representation；warehouse_label_noninterference；candidate_and_actual_acceptance；successor_time_delivery_preservation |
| reverse_reconstruction | reachable_start；fixed_parameters；positive_real_duration；repeated_production；periodic_withdrawal_program；withdrawal_prefix_legality；product_balance；ore_and_other_warehouse_restoration；labels_and_all_effective_state_restoration；operation_precision |
| all_reachable_cycles | all_initial_states；all_fixed_parameters；legal_offline_and_recovery；all_real_cycle_projections；all_positive_duration_cycles |

生产周期默认只承诺生产见证；完整周期及真实低产反例须reverse_reconstruction=proved，核真实拿取相对时点/件数/同刻顺序的重复、逐前缀合法、仓库和全部有效状态复原及操作精度。全称结论须all_reachable_cycles=proved，并把全部正式循环投影到已检对象。单份生产周期不自动取得该结论（任务2§6.5.5；任务6 SP-11）。

### 5.4 直接证明与连续制造

ProofCertificate使用kernel-proof-v1，保存result_id、environment_assumption、evidence_scope、fingerprints、statement、proof_status、obligations、all_reachable_cycles、open_items。proof_status=proved/conditional/unresolved。直接共同状态证明给集合S、初始化包含、正常/离线/恢复保持、每个成品有限值V_i及d_i−ρ_iΔt≥V_i(s')−V_i(s)，沿真实周期求和即得目标。有限图路线覆盖全部可达正时长循环并保持计量时间，零时失败环另核。证明实例与范围见受限转移§6.4。

continuous_required_types逐机型按约束L50和实际台数生成，只含恰下限六类。真实周期逐台核工作时间/批次，过渡暂停单列，研磨/塑形/灌装按实际率与服务核。用此项替代目标比较时，须附运行语义§7所列PA-11完整D域及反向收支，或另一份明确充分证明。条件局部证明和pending复核状态继续保留实际范围。

### 5.5 独立语义验收

1. 按相对目录解析引用，先核原始字节指纹，再核format、producer及全部依赖。重建99轴恰集及生命周期；同一运行、端点和回放中固定排序不得改变。旧版本重核后生成新记录。
2. referenced模式验收完整或checkpoint_delta记录；none模式从引用种子重建前缀。核起点真实到达、实际时长/工作量、门恢复、部分入库、每次尝试冷却和所有守恒账。中途continuation及额度按完整状态恢复。
3. 按所用域重算D项及规范键的未来读取前件。hash相等只找候选，重放后比较完整键内容；碰撞保留其它候选位置。成熟年龄/累计删除不带来实数有限化结论。
4. 整数D域从start_state恰P次step_tick重放(a,b]；其它已证时间域按真实间隔重放。端点完整状态、逐次事件、入库账、接收响应及实际率均独立复算。失败环真实唤醒出口的未决保持相应证据范围。
5. 具体完整周期核reverse_reconstruction全部项目；counterexample还核至少一率低于目标。全称证明核所有初态/参数/合法接续/投影及全部可达循环。资源耗尽、实现停止、装载失败和探索坏环保留各自诊断身份。

任务8定向验收：空箱/全拒收均5 tick；部分可收与两成品一满一可收；同种多格余件及接收原子账；成品取空再入库的标签；固定判定不可改写；门恢复和完整级/环重算；成熟旧货重试；失败环出口；新键端点、真实周期长和真实/代表收支分账。本规格汇入仅完成契约，实际内核运行结果由任务8提交。
'''
(S/'内核输出.md').write_text(s)
print('schema kernel-output-v4 / kernel-cycle-v3 / kernel-proof-v1; certificate contract merged')
