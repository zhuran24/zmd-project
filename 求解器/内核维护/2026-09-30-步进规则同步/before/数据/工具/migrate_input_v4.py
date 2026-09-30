#!/usr/bin/env python3
"""v3 -> v4 条件种子迁移。标准输出；不改历史输入、不继承旧轮询记忆。"""
import argparse,copy,json
from pathlib import Path
from fractions import Fraction
from collections import Counter
from step_inputs import ROOT,q,t,decision,ref,generate,axis as set_axis
from step_graph import build,defaults,poll_state,axis

def migrate(raw,source_base,destination_base):
    if raw['schema']!='kernel-input-v3':raise ValueError('只接受 kernel-input-v3')
    old=raw['initial_state']['nonwarehouse']['value']
    if any(p['phase']=='intake' for p in old['progress']):raise ValueError('intake 阶段不能迁移')
    def times(v):
        if isinstance(v,dict):
            if set(v)=={'kind','value'} and v['kind']=='rational':
                n=Fraction(v['value']['value'])*8
                if n.denominator!=1:raise ValueError('时刻不在 1/8 tick 格点')
                return t(int(n))
            return {k:times(x) for k,x in v.items()}
        if isinstance(v,list):return [times(x) for x in v]
        return v
    out=times(copy.deepcopy(raw));out['schema']='kernel-input-v4'
    out['catalog']=ref(ROOT/'数据/正式静态目录.json',destination_base)
    cfg=json.loads((ROOT/'规格/内核配置-v2.json').read_text())
    params={'axis_registry':ref(ROOT/'规格/内核配置-v2.json',destination_base),'profile_id':cfg['profile_id'],'fixed':{},'offline_mutable':{},'fixedness_unproven':{}}
    for name,row in cfg['axes'].items():
        value=row['value']
        if row['disposition']=='由输入全称量化':
            try:value=axis(out,name)
            except ValueError:pass
        params['fixed' if row['lifetime'].startswith('F') else 'offline_mutable' if row['lifetime']=='O' else 'fixedness_unproven'][name]=decision(value)
    # Use the serialized enum spelling in the registry (not a translated guess).
    for name,row in cfg['axes'].items():
        if isinstance(row['value'],str) and row['value'].startswith('interface:'):
            try:set_axis({'parameters':params},name,axis(out,name))
            except ValueError:pass
    for name in ('connection.build_order','connection.order','connection.tie','connection.belt_shape','transfer.phase','manufacturing.recipe_selection','manufacturing.input_slot_selection','initialization.warehouse_anchor','initialization.other_inventory','initialization.switches','initialization.build_timing','initialization.debug_end','warehouse.external_supply'):
        set_axis({'parameters':params},name,axis(out,name))
    out['parameters']=params
    state=out['initial_state']['nonwarehouse']['value']
    phase=old['semantic_context']['judgment_context']['value']['phase']
    if phase not in ('before_boundary','after_closure'):raise ValueError('只迁移完整边界种子')
    if phase=='after_closure':state['environment']['time']=t(int(state['environment']['time']['value']['value'])+8)
    byid={u['id']:u for u in out['layout']['units']}
    if out['layout']['physical_channels'] is None:
        description={'units':[{'id':u['id'],'kind':u['kind'],'x':int(u['origin'][0]['value']),'y':int(u['origin'][1]['value']),'rotation':int(u['rotation'][1:]),'port_layout':u['port_layout'] or 0} for u in byid.values()]}
        made=generate(description,destination_base);out['layout']['physical_channels']=made['layout']['physical_channels']
    g=build(out,destination_base)
    for inv in state['inventory']:
        u=inv['slot'].split(':')[0];transport=g['kinds'][byid[u]['kind']]['family']=='transport'
        if not transport:
            counts=Counter()
            for c in inv['contents']:counts[c['item']]+=int(c['quantity']['value'])
            inv['contents']=[{'item':k,'quantity':q(v),'entered_at':None} for k,v in sorted(counts.items()) if v]
    for p in state['progress']:
        p['cooldown']=p['cooldowns'][0]['remaining'] if p['cooldowns'] else None
        for key in ('candidate_recipes','locked_recipe','cooldowns'):del p[key]
    for gate in state['logistics']['gate_counters']:gate.pop('blocked_reasons',None)
    state['logistics']={'poll_state':poll_state(g),'gate_counters':state['logistics']['gate_counters']}
    now=int(state['environment']['time']['value']['value'])
    for gate in state['logistics']['gate_counters']:
        if gate['window_started_at'] and int(gate['window_started_at']['value']['value'])+40<=now:gate.update(window_started_at=None,window_received=q(0))
    state['semantic_context']={'warehouse_empty_slot_order':state['semantic_context']['arbitration']['warehouse_empty_slot_order']}
    set_axis(out,'step.order',defaults(g));set_axis(out,'transfer.timing',{'schema':'transfer-timing-v1','values':[{'unit':p['unit'],'timing':'before_send'} for p in state['progress'] if p['cooldown'] is not None]})
    # Initial residuals belong to this migrated seed; the old state cannot encode later v4 polling.
    set_axis(out,'transfer.phase',{'kind':'explicit_residuals','values':[{'unit':p['unit'],'slot':None,'remaining':p['cooldown']} for p in state['progress'] if p['cooldown'] is not None]})
    doc=out['initial_state']['reachability']['value'].get('document')
    if doc:out['initial_state']['reachability']['value']['document']=str((Path(source_base)/doc).resolve())
    out['scenario']['migration']={'source_schema':'kernel-input-v3','note':'不继承旧轮询记忆；默认选支和传输次序仅为一个代表值，不宣称全称。','old_anchor':phase}
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    print(json.dumps(migrate(json.loads(a.input.read_text()),a.input.parent,a.base),ensure_ascii=False,indent=2))
