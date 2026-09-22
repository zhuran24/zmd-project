"""生产键的规范编码参考；仅验证局部编码，调用方仍须核转移§6.1全部D条件。"""
from copy import deepcopy
from fractions import Fraction
import json

PRODUCTS=('高容谷地电池','精选荞愈胶囊')
ORES=('源矿','蓝铁矿')
def number(value):
    if isinstance(value,dict) and value.get('kind')=='rational':value=value['value']
    if isinstance(value,dict):value=value['value']
    return Fraction(value)
def quantity(value):return {'value':str(Fraction(value))}
def time(value):return {'kind':'rational','value':quantity(value)}
def canonical(value):
    # 类别与依据已由输入验收，不参与物理控制；语义有序数组维持原序。
    if isinstance(value,list):return [canonical(x) for x in value]
    if not isinstance(value,dict):return value
    if set(value)=={'value','category'}:return quantity(number(value))
    return {k:canonical(v) for k,v in value.items() if not(k=='basis' and 'status' in value)}
def cycle_key(state):
    source=deepcopy(state); t=number(source['environment']['time'])
    sc=source['semantic_context']; jc=sc['judgment_context']['value'];tc=sc['tick_context']['value']
    assert jc['phase']=='after_closure' and jc['order_scope']=='global'
    assert jc['next_event'] is None and 'continuation' not in jc
    assert sc['arbitration']['warehouse_empty_slot_order']==[]
    assert source['environment']['online'] and source['environment']['stage']=='zero_intervention'
    source['warehouse']['slots']=[r for r in source['warehouse']['slots'] if (r['item'] or r['empty_identity']['value']) not in PRODUCTS]
    for row in source['warehouse']['slots']:
        if row['item'] in ORES:
            assert 0<number(row['quantity'])<=80000
            row['quantity']={'value':'sufficient'}
    source['warehouse']['slots'].sort(key=lambda r:r['slot'])
    for row in source['inventory']:
        for item in row['contents']:
            if item['entered_at'] is not None:item['entered_at']={'age':quantity(t-number(item['entered_at']))}
        row['contents'].sort(key=lambda x:(x['item'],json.dumps(x['entered_at'],sort_keys=True)))
    source['inventory'].sort(key=lambda r:r['slot'])
    for row in source['progress']:
        row['candidate_recipes']=sorted(row['candidate_recipes'])
        row['cooldowns'].sort(key=lambda r:(r['slot'] is not None,r['slot'] or ''))
    source['progress'].sort(key=lambda r:r['unit'])
    lg=source['logistics']
    for k in ['active_channels','blocked_channels']:lg[k]=sorted(lg[k])
    pm=lg['poll_memory']['value'];pm['sides'].sort(key=lambda r:(r['unit'],r['side']))
    for row in pm['sides']:row['levels'].sort(key=lambda r:r['id'])
    for row in lg['gate_counters']:
        row['blocked_reasons']=sorted(row['blocked_reasons'])
        if row['window_started_at'] is not None:row['window_started_at']={'elapsed':quantity(t-number(row['window_started_at']))}
    lg['gate_counters'].sort(key=lambda r:r['unit'])
    source['environment']['time']=time(0)
    sc['parameter_values'].sort(key=lambda r:r['axis'])
    sc['judgment_context']['value']={'instant':time(0),'phase':'after_closure','order_scope':'global'}
    for row in sc['pending_events']['value']:
        assert row['operation'] in ['manufacture_complete','gate_window_expiry']
        assert row['trigger']['kind']=='at_time' and row['predecessors']==[] and row['status']=='waiting'
        remaining=number(row['trigger']['value'])-t
        row['event']=[row['operation'],row['target'],str(remaining)]
        row['trigger']['value']=time(remaining)
    sc['pending_events']['value'].sort(key=lambda r:(r['operation'],r['target'],str(number(r['trigger']['value']))))
    tc['window_start']=time(number(tc['window_start'])-t);tc['window_end']=time(number(tc['window_end'])-t)
    assert number(tc['window_start'])==0 and number(tc['window_end'])==1
    tc['port_usage']=[r for r in tc['port_usage'] if number(r['quantity'])!=0]
    tc['port_usage'].sort(key=lambda r:r['port']);del tc['movements'];del tc['internal_passages']
    return dict(schema='production-cycle-key-v1',domain='production_v1',state=canonical(source),product_acceptance=[{'item':p,'state':'under_capacity'} for p in PRODUCTS])
def key_bytes(key):return json.dumps(key,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
