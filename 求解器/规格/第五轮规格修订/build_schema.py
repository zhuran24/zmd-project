"""由只读v2格式基线生成第五轮记录/循环结果schema；不触碰数据与实现。"""
import json,copy
from pathlib import Path
here=Path(__file__).resolve().parent; spec=here.parent
base=json.loads((here/'运行记录v2基线.schema.json').read_text())
def obj(props,required=None):return dict(type='object',properties=props,required=list(props) if required is None else required,additionalProperties=False)
def arr(item,**kw):return dict(type='array',items=item,**kw)
def ref(n):return {'$ref':'#/$defs/'+n}
def null_or(s):return {'anyOf':[s,{'type':'null'}]}
s={'type':'string','minLength':1}; ni={'type':'integer','minimum':0}; pi={'type':'integer','minimum':1}; boolean={'type':'boolean'}; nullable={'type':['string','null']}
d=base.pop('$defs');base.pop('$id');base.pop('$schema')
d['Event']['properties']['operation']['enum'].append('gate_identity_maintenance')
q=ref('Quantity'); time=ref('Time')
d['CoreInbound']=obj(dict(event=s,channel=s,port=s,item=s,quantity=q))
d['WirelessInbound']=obj(dict(event=s,unit=s,item=s,quantity=q))
d['PortOutbound']=obj(dict(event=s,channel=s,port=s,slot=s,item=s,quantity=q))
d['ExternalSupply']=obj(dict(event=s,mode={'enum':['sufficient','explicit_ore_history']},item={'enum':['源矿','蓝铁矿']},quantity=q))
d['PlayerWithdrawal']=obj(dict(event=s,slot=s,item={'enum':['高容谷地电池','精选荞愈胶囊']},quantity=q))
d['RepresentativeAdjustment']=obj(dict(item={'enum':['高容谷地电池','精选荞愈胶囊']},quantity=q,reason={'const':'production_representative'}))
total_keys=['core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment','actual_inbound']
d['WarehouseTotal']=obj({'item':s,**{k:q for k in total_keys}})
d['WarehouseLedger']=obj({k:arr(ref(n)) for k,n in [('core_inbound','CoreInbound'),('wireless_inbound','WirelessInbound'),('port_outbound','PortOutbound'),('external_supply','ExternalSupply'),('player_withdrawal','PlayerWithdrawal'),('representative_adjustment','RepresentativeAdjustment'),('totals','WarehouseTotal')]})
for n in ['Tick','DeltaTick']:
 d[n]['properties']['warehouse_ledger']=ref('WarehouseLedger');d[n]['required'].append('warehouse_ledger')
# v2中定义存在内联Tick；统一替换，防止全状态和增量两条路径漏台账。
d['FullTrace']['properties']['ticks']=arr(ref('Tick'))
d['CheckpointTrace']['properties']['ticks']=arr({'oneOf':[ref('Tick'),ref('DeltaTick')]})
base['properties']['schema']={'const':'kernel-output-v3'}
meeting={'enum':['shared_edge_opposite','closed_segment_touch']}
base['properties']['execution_mode']={'enum':['finite_concrete','production_abstraction']}
base['properties']['port_meeting']=meeting
base['required'] += ['execution_mode','port_meeting']
base['properties']['trace']={'anyOf':[{'type':'null'},ref('FullTrace'),ref('CheckpointTrace')]}
base['then']['properties']['trace']={'oneOf':[ref('FullTrace'),ref('CheckpointTrace')]}
d['RunRecord']=base
config=json.loads((spec/'内核配置-v1.json').read_text())
input_axes=[k for k,v in config['axes'].items() if v['disposition']=='由输入全称量化'];assert len(input_axes)==15
point=obj(dict(assignment=ref('Parameters'),input_axes=obj({k:ref('Decision') for k in input_axes})))
check=obj(dict(condition=s,status={'enum':['pass','fail','unresolved']},evidence=arr(s,minItems=1)))
d['ProofSource']=obj(dict(path=s,sha256=ref('Hash')))
d['CycleKey']=obj(dict(schema={'const':'production-cycle-key-v1'},domain={'const':'production_v1'},state=obj({k:{'type':'object'} for k in ['settings_anchor','warehouse','logistics','environment','semantic_context']}|{'layout_snapshot':s,'inventory':arr({'type':'object'}),'progress':arr({'type':'object'})}),product_acceptance=arr(obj(dict(item={'enum':['高容谷地电池','精选荞愈胶囊']},state={'const':'under_capacity'})),minItems=2,maxItems=2)))
d['CycleRate']=obj(dict(item={'enum':['高容谷地电池','精选荞愈胶囊']},inbound=q,period=q,average=q,target=q,comparison={'enum':['lt','eq','gt']}))
d['Acceptance']=obj(dict(time=time,products=arr(obj(dict(item={'enum':['高容谷地电池','精选荞愈胶囊']},capacity_available=boolean,physical_path_exists=boolean,selected_acceptance=boolean)),minItems=2,maxItems=2)))
d['Cycle']=obj(dict(period=q,start_time=time,end_time=time,start_state=ref('StateSeed'),end_state=ref('StateSeed'),start_key=ref('CycleKey'),end_key=ref('CycleKey'),normalization=obj(dict(schema={'const':'cycle-normalization-v1'},definition=ref('ProofSource'),basis=arr(s,minItems=1),domain_checks=arr(s,minItems=5))),ledger=arr(obj(dict(time=time,warehouse_ledger=ref('WarehouseLedger'))),minItems=1),totals=arr(ref('WarehouseTotal'),minItems=2),rates=arr(ref('CycleRate'),minItems=2,maxItems=2),acceptance=arr(ref('Acceptance'),minItems=1),lift=null_or(obj(dict(status={'enum':['proved','blocked']},family=ref('ProofSource'),proof=ref('ProofSource'),family_checks=arr(check))))))
stop=obj(dict(kind={'enum':['invalid_input','unsupported','unresolved','resource','low_rate']},axis=nullable,event=nullable,time=null_or(time),reason=s,partial_events=arr(ref('Event'))))
cycle_result=obj(dict(schema={'const':'kernel-cycle-v1'},result_id=s,status={'enum':['cycle_found','counterexample','stopped','inconclusive','invalid_input']},level={'enum':['production_part','full_base',None]},execution_mode={'enum':['finite_concrete','production_abstraction']},port_meeting=meeting,seed=null_or(obj(dict(state=ref('StateSeed'),reachability=ref('Decision'),source_event=s))),parameter_point=null_or(point),reading=obj(dict(port_meeting=meeting,warehouse_acceptance=s,acceptance_quantifier=s,cycle_interpretation={'enum':['production_projection','observable_base_with_withdrawal']},remaining_assumptions=arr(s))),support_domain=obj(dict(name=s,checks=arr(check),uncovered=arr(s))),replay_input=null_or({'type':'object','properties':{'schema':{'const':'kernel-input-v3'}},'required':['schema','layout','settings','parameters','initial_state','timeline','environment']}),run_record=null_or(ref('RunRecord')),cycle=null_or(ref('Cycle')),stop=null_or(stop),budget=obj(dict(max_ticks=pi,max_sweeps=pi,completed_ticks=ni)),open_items=arr(s)))
cycle_result['allOf']=[
 {'if':{'properties':{'status':{'enum':['cycle_found','counterexample']}}},'then':{'properties':{'cycle':ref('Cycle'),'seed':{'type':'object'},'parameter_point':point,'run_record':ref('RunRecord'),'replay_input':{'type':'object'},'level':{'enum':['production_part','full_base']}}}},
 {'if':{'properties':{'status':{'const':'cycle_found'}}},'then':{'properties':{'stop':{'type':'null'}}}},
 {'if':{'properties':{'status':{'const':'counterexample'}}},'then':{'properties':{'stop':{'allOf':[stop,{'properties':{'kind':{'const':'low_rate'}}}]}}}},
 {'if':{'properties':{'status':{'enum':['stopped','inconclusive','invalid_input']}}},'then':{'properties':{'cycle':{'type':'null'},'stop':stop}}},
 {'if':{'properties':{'status':{'const':'inconclusive'}}},'then':{'properties':{'stop':{'properties':{'kind':{'const':'resource'}}},'seed':{'type':'object'},'parameter_point':point,'replay_input':{'type':'object'},'run_record':ref('RunRecord')}}},
 {'if':{'properties':{'level':{'const':'production_part'}}},'then':{'properties':{'execution_mode':{'const':'production_abstraction'}}}},
 {'if':{'properties':{'level':{'const':'full_base'},'status':{'enum':['cycle_found','counterexample']}}},'then':{'properties':{'cycle':{'properties':{'lift':{'type':'object','properties':{'status':{'const':'proved'}}}}}}}}
]
d['CycleResult']=cycle_result
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:zmd:kernel-output-v3','oneOf':[ref('RunRecord'),ref('CycleResult')],'$defs':d}
(spec/'内核输出.schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'definitions':len(d),'input_axes':len(input_axes),'schemas':['kernel-output-v3','kernel-cycle-v1']},ensure_ascii=False))
