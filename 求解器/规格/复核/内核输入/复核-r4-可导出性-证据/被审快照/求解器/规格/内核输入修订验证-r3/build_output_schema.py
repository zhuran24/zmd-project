"""生成运行记录 schema；数据语义交由专门校验器复核。"""
import json
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'内核输出.schema.json'
def obj(properties,required=None):return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}
def array(value):return {'type':'array','items':value}
def ref(name):return {'$ref':'#/$defs/'+name}
string={'type':'string','minLength':1}; nullable={'type':['string','null']}; integer={'type':'integer','minimum':0}
q=obj({'value':{'type':'string','pattern':r'^-?\d+(?:/[1-9]\d*)?$'},'category':{'enum':['条文直引','算术推论','候选','启发式','实测']}})
dec=obj({'status':{'enum':['specified','derived','unresolved','not_applicable']},'value':{},'basis':{'type':'array','minItems':1,'items':string}})
time=obj({'kind':{'const':'rational'},'value':ref('Quantity')})
content=obj({'item':string,'quantity':ref('Quantity'),'entered_at':{'anyOf':[ref('Time'),{'type':'null'}]}})
warehouse=obj({'slots':array(obj({'slot':string,'item':nullable,'quantity':ref('Quantity'),'empty_identity':ref('Decision')})),'unlisted':{'const':'empty'}})
progress=obj({'unit':string,'phase':{'enum':['idle','intake','working','completed']},'recipe':nullable,'candidate_recipes':array(string),'locked_recipe':nullable,'remaining':{'anyOf':[ref('Time'),{'type':'null'}]},'cooldowns':array(obj({'slot':nullable,'remaining':ref('Time')}))})
state=obj({'layout_snapshot':string,'settings_anchor':obj({'event':string,'side':{'enum':['before','after']}}),'warehouse':ref('Warehouse'),'inventory':array(obj({'slot':string,'contents':array(ref('Content'))})),'progress':array(ref('Progress')),
'logistics':obj({'active_channels':array(string),'blocked_channels':array(string),'poll_memory':ref('Decision'),'gate_counters':array(obj({'unit':string,'blocked_reasons':array({'enum':['identity_mismatch','total_exhausted','window_exhausted']}),'total_received':ref('Quantity'),'window_received':ref('Quantity'),'window_started_at':{'anyOf':[ref('Time'),{'type':'null'}]}})),'connection_order':ref('Decision')}),
'environment':obj({'time':ref('Time'),'stage':{'enum':['building','debug','zero_intervention']},'online':{'type':'boolean'},'withdrawal_memory':ref('Decision')}),
'semantic_context':obj({'arbitration':obj({'level_order':array(string),'warehouse_empty_slot_order':array(string)}),'parameter_values':array(obj({'axis':string,'value':ref('Decision'),'lifetime':{'enum':['F','O','U']}})),'judgment_context':ref('Decision'),'pending_events':ref('Decision'),'tick_context':ref('Decision')})})
parameters=obj({'axis_registry':obj({'path':string,'sha256':ref('Hash')}),'profile_id':string,**{k:{'type':'object','additionalProperties':ref('Decision')} for k in ('fixed','offline_mutable','fixedness_unproven')}})
event=obj({'event':string,'operation':{'enum':['move','internal_move','manufacture','transfer','manufacture_complete','time_advance','ore_supply','offline','player_action']},'target':string,'outcome':{'enum':['success','failure','guard_false','no_request']},'detail':{'type':'string'},'basis':{'type':'array','minItems':1,'items':string}},['event','operation','target','outcome','basis'])
tick=obj({'time':ref('Time'),'events':array(ref('Event')),'state':ref('StateSeed'),'summary':{'type':'object'},'closure':obj({'kind':{'const':'no_success_state_repeat'},'scan_rounds':integer,'basis':array(string)})})
schema=obj({'schema':{'const':'kernel-output-v2'},'run_id':string,'profile_id':string,'producer':obj({'kind':{'enum':['kernel','bounded_reference_checker','manual_expected']},'path':string,'claim':string}),'status':{'enum':['completed','invalid_input','unsupported','unresolved','inconclusive']},'fingerprints':array(obj({'role':{'enum':['input','catalog','axis_registry','profile','parameter_projection','formal_source','golden','checker','semantics','schema']},'path':string,'sha256':ref('Hash')})),
'parameter_assignment':ref('Parameters'),'input_history':obj({'timeline':{'type':'object'},'construction':{'type':'object'},'debug_operations':array({'type':'object'}),'environment':{'type':'object'},'reachability':ref('Decision')}),'uncovered_axes':array(obj({'axis':string,'reason':string,'disposition':string,'coverage_status':{'enum':['exercised','input_checked','not_exercised','stop_not_triggered','proof_pending']},'evidence':{'type':'array','minItems':1,'items':string},'other_values':string})),
 'trace':obj({'start_state':ref('StateSeed'),'ticks':array(ref('Tick')),'end_time':ref('Time'),'format':{'const':'full_state_each_instant'}}),
'validation_scope':obj({'kind':{'const':'finite_trace'},'from':ref('Time'),'through':ref('Time'),'golden_match':{'type':'boolean'},'initial_history':{'const':'conditional_witness'},'universal_parameters':{'const':False},'all_reachable_cycles':{'const':False},'target_certified':{'const':False},'manufacturing_cycles_completed':ref('Quantity')}),'open_items':array(string)})
# 装载前失败不能伪造完整种子；成功记录则必须保留全部可复验字段。
complete_properties={key:schema['properties'][key] for key in ('parameter_assignment','input_history','trace','validation_scope')}
for key,value in complete_properties.items():schema['properties'][key]={'anyOf':[value,{'type':'null'}]}
schema['if']={'properties':{'status':{'const':'completed'}}}
schema['then']={'properties':complete_properties}
schema.update({'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:zmd:kernel-output-v2','$defs':{'Quantity':q,'Decision':dec,'Time':time,'Hash':{'type':'string','pattern':'^[0-9a-f]{64}$'},'Warehouse':warehouse,'Content':content,'Progress':progress,'StateSeed':state,'Parameters':parameters,'Event':event,'Tick':tick}})
out.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')
