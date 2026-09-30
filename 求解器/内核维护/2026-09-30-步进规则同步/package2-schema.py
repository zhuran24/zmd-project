from pathlib import Path
import json,copy
O=Path(__file__).resolve().parent;R=O.parents[1];S=O/'package2-stage'
x=json.loads((R/'规格/内核输出.schema.json').read_text())
def transform(v):
    if isinstance(v,dict):return {k:transform(value) for k,value in v.items()}
    if isinstance(v,list):return [transform(value) for value in v]
    if isinstance(v,str):
        for a,b in [('kernel-output-v4','kernel-output-v5'),('kernel-cycle-v3','kernel-cycle-v4'),('kernel-input-v3','kernel-input-v4'),('kernel_profile_v1','kernel_profile_v2'),('phase-cycle-key-v1','phase-cycle-key-v2'),('phase_production_v1','phase_production_v2'),('cycle-normalization-v2','cycle-normalization-v3'),('full_state_each_instant','full_state_each_step')]:v=v.replace(a,b)
    return v
x=transform(x);d=x['$defs'];ref=lambda n:{'$ref':'#/$defs/'+n};arr=lambda v:{'type':'array','items':v};null={'type':'null'};text={'type':'string','minLength':1};integer={'type':'integer'}
def obj(p,required=None):return {'type':'object','properties':p,'required':list(p) if required is None else required,'additionalProperties':False}
def nullable(v):return {'anyOf':[v,null]}
def rename(o,old,new):
    o['properties'][new]=o['properties'].pop(old);o['required']=[new if k==old else k for k in o['required']]
def remove(o,key):o['properties'].pop(key,None);o['required']=[k for k in o['required'] if k!=key]
d['Time']['properties']['kind']={'const':'step'}
d['Progress']=obj(dict(unit=text,phase={'enum':['idle','working','completed']},recipe=nullable(text),remaining=nullable(ref('Time')),cooldown=nullable(ref('Time'))))
d['PollState']=obj({'schema':{'const':'poll-state-v1'},'cursors':arr(obj(dict(side=text,last_success=nullable(text)))),'recency':arr(obj(dict(unit=text,order=arr(text))))})
d['GateCounter']=obj(dict(unit=text,total_received=ref('Quantity'),window_received=ref('Quantity'),window_started_at=nullable(ref('Time'))))
s=d['StateSeed']['properties'];s['logistics']=obj(dict(poll_state=ref('PollState'),gate_counters=arr(ref('GateCounter'))));s['semantic_context']=obj(dict(warehouse_empty_slot_order=arr(text)))
d['Event']=obj(dict(event={'type':'string','pattern':r'^E\|-?[0-9]+\|[0-9]+$'},phase={'enum':['supply','complete','flush','judge','start']},subject=text,moves=arr(obj(dict(channel=text,item=text))),detail={'type':['object','null']}))
d['Step']=obj(dict(step=integer,events=arr(ref('Event')),state=ref('StateSeed'),warehouse_ledger=ref('WarehouseLedger')))
d['DeltaStep']=obj(dict(step=integer,events=arr(ref('Event')),delta=arr(ref('DeltaOperation')),warehouse_ledger=ref('WarehouseLedger')))
d.pop('Tick');d.pop('DeltaTick')
d['FullTrace']=obj(dict(start_state=ref('StateSeed'),steps=arr(ref('Step')),end_step=integer,format={'const':'full_state_each_step'}))
d['CheckpointTrace']=obj(dict(start_state=ref('StateSeed'),steps=arr({'oneOf':[ref('Step'),ref('DeltaStep')]}),end_step=integer,format={'const':'checkpoint_delta'},checkpoint_interval={'type':'integer','minimum':1},delta_encoding={'const':'object_replace_v1'}))
rename(d['CoreInbound'],'port','unit');remove(d['PortOutbound'],'slot')
record=d['RunRecord'];record.pop('allOf',None)
for v in [record['properties']['validation_scope']['anyOf'][0],record['then']['properties']['validation_scope']]:remove(v,'golden_match')
record['properties']['profile_id']={'const':'kernel_profile_v2'}
# Preserve diagnostic evidence framing shared by ordinary and cycle records.
record['allOf']=[{'properties':{'evidence_scope':{'properties':{'kind':{'enum':['finite_trace','diagnostic']},'direction':{'const':'diagnostic'}}}}}]
ev=d['EvidenceScope']['properties']['kind']
if 'finite_trace' not in ev.get('enum',[]):ev['enum'].append('finite_trace')
cy=d['Cycle'];cy['properties']['period_ticks']=ref('Quantity');cy['required'].append('period_ticks')
rename(cy['properties']['ledger']['items'],'time','step');cy['properties']['ledger']['items']['properties']['step']=integer
budget=d['CycleResult']['properties']['budget'];rename(budget,'max_ticks','max_steps');rename(budget,'completed_ticks','completed_steps');remove(budget,'max_sweeps')
key=d['CycleKey']['properties']['state'];key['properties']['environment']={'type':'object','not':{'required':['time']}}
key['properties']['logistics']=obj({'poll_state':ref('PollState'),'gate_counters':arr(obj(dict(unit=text,total_received=nullable(obj({'value':text})),window_received=obj({'value':text}),window_started_at=ref('GateWindowProjection'))))})
key['properties']['semantic_context']=obj(dict(warehouse_empty_slot_order={'type':'array','maxItems':0}))
key['properties']['inventory']['items']['properties']['contents']['items']['properties']['entered_at']=nullable(ref('MaturityResidual'))
d['MaturityResidual']['properties']['residual']['properties']['value']={'type':'string','pattern':r'^[0-8]$'}
# Current active schema supports records and certificates; old direct-proof material is historical.
x['oneOf']=[ref('RunRecord'),ref('CycleResult')];d.pop('ProofCertificate')
path=S/'规格/内核输出.schema.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
