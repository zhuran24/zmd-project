#!/usr/bin/env python3
"""简要布局生成 kernel-input-v4。标准输出 JSON；落盘须经本轮 work.py 守卫。

描述：units=[{id,kind,x,y,rotation=0,port_layout=0}]；可给 step_order、
transfer_timing、build_order、warehouse_items（端口到物种）。生成的空库存种子为条件输入。
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def q(n): return {'value': str(n), 'category':'候选'}
def t(n): return {'kind':'step','value':q(n)}
def decision(v): return {'status':'specified','value':v,'basis':['步进规则同步：显式有限构型，未声明全称或可达性']}
def axis(raw, name, value):
    for g in ['fixed','offline_mutable','fixedness_unproven']:
        if name in raw['parameters'][g]: raw['parameters'][g][name]=decision(value); return
    raise KeyError(name)
def ref(path, base):
    import os
    return {'path':os.path.relpath(path,base),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
def rotate(x,y,w,h,r):
    return [(x,y),(h-1-y,x),(w-1-x,h-1-y),(y,w-1-x)][r]

def generate(description=None, base=None):
    d=description or {}; base=Path(base or ROOT)
    catalog=json.loads((ROOT/'数据/正式静态目录.json').read_text()); kinds={r['id']:r for r in catalog['units']}
    config=json.loads((ROOT/'规格/内核配置-v2.json').read_text())
    specs=d.get('units',[{'id':'core','kind':'协议核心','x':50,'y':50}])
    if not any(u['kind']=='协议核心' for u in specs): specs=[{'id':'core','kind':'协议核心','x':50,'y':50},*specs]
    units=[{'id':u['id'],'kind':u['kind'],'origin':[q(u['x']),q(u['y'])],'rotation':f"r{u.get('rotation',0)}",'port_layout':None if u['kind']=='桥接器' else u.get('port_layout',0),'bridge_axes':None,'occupied_cells':None} for u in specs]
    by_id={u['id']:u for u in units}; ports={};inventory=[];progress=[];switches=[];gates=[];shapes=[];buffers=[]
    order=d.get('build_order',sorted(by_id,key=lambda u:(by_id[u]['kind']=='传送带',u)))
    build={u:'build_'+str(i) for i,u in enumerate(order)}
    seed_time=d.get('time',0)
    for u in units:
        uid=u['id'];k=kinds[u['kind']];r=int(u['rotation'][1:])//90;w=int(k['dimensions']['width']['value']);h=int(k['dimensions']['height']['value']);ox,oy=[int(v['value']) for v in u['origin']]
        edges=k['ports']['layouts'][u['port_layout'] or 0]
        for edge in edges:
            for pos in edge['positions']:
                p=int(pos['value']);s=edge['side'];x,y,dx,dy={'south':(p,0,0,-1),'north':(p,h-1,0,1),'west':(0,p,-1,0),'east':(w-1,p,1,0)}[s]
                x,y=rotate(x,y,w,h,r)
                for _ in range(r):dx,dy=-dy,dx
                ports[f'{uid}:{s}:{p}']={'unit':uid,'role':edge['role'],'axis':edge.get('axis'),'cell':(ox+x,oy+y),'normal':(dx,dy)}
        for sk in k['inventory']:
            if sk['role']=='warehouse':continue
            for i in range(int(sk['count']['value'])):
                slot=f"{uid}:{sk['role']}:{i}";inventory.append({'slot':slot,'contents':[]})
                if k['family']=='manufacturing' and sk['role'] in ['input','output']:
                    a,b=(slot,f'{uid}:buffer:0') if sk['role']=='input' else (f'{uid}:buffer:0',slot)
                    buffers.append({'id':f'BC|{a}|{b}','source_slot':a,'target_slot':b})
        if k['powered_functions']:
            progress.append({'unit':uid,'phase':'idle','recipe':None,'remaining':None,'cooldown':t(0) if u['kind']=='协议储存箱' else None})
        switches.extend({'unit':uid,'function':f,'enabled':True} for f in k['powered_functions'])
        if u['kind']=='物品准入口':gates.append({'unit':uid,'item':None,'total_limit':None,'window_limit':None})
        if u['kind']=='传送带':
            sides=['south','east','north','west'];a=next(sides.index(e['side']) for e in edges if e['role']=='input');b=next(sides.index(e['side']) for e in edges if e['role']=='output')
            shapes.append({'unit':uid,'build_event':build[uid],'shape':{1:'turn_left',2:'straight',3:'turn_right'}[(b-a)%4]})
    faces={(p['cell'],p['normal']):pid for pid,p in ports.items()};channels=[]
    for pid,p in sorted(ports.items()):
        if p['role'] not in ['output','bidirectional']:continue
        x,y=p['cell'];dx,dy=p['normal'];other=faces.get(((x+dx,y+dy),(-dx,-dy)))
        if other and ports[other]['role'] in ['input','bidirectional'] and any(kinds[by_id[v]['kind']]['family']=='transport' for v in [p['unit'],ports[other]['unit']]):channels.append({'id':f'PC|{pid}|{other}','source_port':pid,'target_port':other})
    times={u:seed_time-len(order)+i-1 for i,u in enumerate(order)}
    events=[{'id':build[u],'kind':'build','time':t(times[u])} for u in order]+[{'id':'complete','kind':'blueprint_complete','time':t(seed_time)},{'id':'debug_end','kind':'debug_end','time':t(seed_time)}]
    connections=[]
    for i,c in enumerate(channels):
        a,b=[ports[c[k]]['unit'] for k in ['source_port','target_port']];later=max([a,b],key=order.index);eid=f'connection_{i}'
        events.append({'id':eid,'kind':'connection_open','time':t(times[later])})
        connections.append({'event':eid,'channel':c['id'],'action':'open','cause':build[later],'geometry_snapshot':'built_layout','construction_basis':decision({'source_build':build[a],'target_build':build[b],'later_build':build[later]})})
    wh={'slots':[{'slot':f'warehouse_{i}','item':item,'quantity':q(80000),'empty_identity':{'status':'not_applicable','value':None,'basis':['非空物种由 item 承载']}} for i,item in enumerate(['源矿','蓝铁矿','荞花','砂叶','荞花种子','砂叶种子'])],'unlisted':'empty'}
    wh_slots={r['item']:r['slot'] for r in wh['slots']}
    assignments=[{'port':pid,'slot':wh_slots[d.get('warehouse_items',{}).get(pid,'源矿')]} for pid,p in ports.items() if p['role']=='output' and by_id[p['unit']]['kind'] in ['协议核心','仓库取货口']]
    anchor={'event':'complete','side':'after'}
    raw={'schema':'kernel-input-v4','purpose':'synthetic_execution','catalog':ref(ROOT/'数据/正式静态目录.json',base),'timeline':{'events':events,'relations':[],'connection_events':connections},'layout':{'base':{'width':q(70),'height':q(70)},'id':'built_layout','anchor':anchor,'units':units,'physical_channels':channels,'buffer_channels':buffers,'snapshots':[],'post_debug':decision('built_layout')},'construction':{'mode':'blueprint_once','order_domain':'all_rule_consistent_orders','selected_order':order,'moments':[{'event':build[u],'unit':u,'placement':{k:by_id[u][k] for k in ['kind','origin','rotation','port_layout','occupied_cells']}} for u in order],'complete_event':'complete'},'settings':{'anchor':anchor,'switches':switches,'gates':gates,'warehouse_assignments':assignments},'parameters':{'axis_registry':ref(ROOT/'规格/内核配置-v2.json',base),'profile_id':config['profile_id'],'fixed':{},'offline_mutable':{},'fixedness_unproven':{}},'initial_state':{'anchor':decision(anchor),'warehouse':wh,'nonwarehouse':decision({}),'reachability':decision({'kind':'conditional_history','scope':'条件种子，不是起动证明'})},'debug_operations':[],'environment':{'ore_supply':'task_continuous_sufficient','offline':{'event_domain':decision({'kind':'selected_history','events':[]}),'selected_events':[]},'product_withdrawal':{'policy':decision({'schema':'withdrawal-policy-v1','rules':[],'admissibility':decision({'kind':'no_actions'})}),'selected_events':[]},'debug_end_event':'debug_end','zero_intervention_after_debug':True},'contract_binding':None,'scenario':{}}
    for a,r in config['axes'].items():raw['parameters']['fixed' if r['lifetime'].startswith('F') else 'offline_mutable' if r['lifetime']=='O' else 'fixedness_unproven'][a]=decision(r['value'])
    # 元件身份与默认数层见设计 §1.2、§9.4。此库只生成代表值。
    belts={u for u in by_id if by_id[u]['kind']=='传送带'};nxt={};prev={}
    for c in channels:
        a,b=[ports[c[k]]['unit'] for k in ['source_port','target_port']]
        if a in belts and b in belts:nxt[a]=b;prev[b]=a
    comps={};owner={};seen=set()
    for start in sorted(belts-set(prev))+sorted(belts):
        if start in seen:continue
        cells=[];u=start
        while u not in seen:
            seen.add(u);cells.append(u)
            if u not in nxt:break
            u=nxt[u]
        ring=u==start and cells[-1] in nxt;cid=f'C|ring|{start}' if ring else f'C|{cells[-1]}'
        comps[cid]={'kind':'传送带','inputs':[],'outputs':[]}
        for u in cells:owner[(u,None)]=cid
    for u in by_id:
        if kinds[by_id[u]['kind']]['family']=='transport' and u not in belts:
            for a in ['horizontal','vertical'] if by_id[u]['kind']=='桥接器' else [None]:
                cid=f'C|{u}'+(f'|{a}' if a else '')
                if cid in comps:raise ValueError('元件身份重复: '+cid)
                owner[(u,a)]=cid;comps[cid]={'kind':by_id[u]['kind'],'inputs':[],'outputs':[]}
    nt={u:{'inputs':[],'outputs':[]} for u in by_id if kinds[by_id[u]['kind']]['family'] not in ['transport','power']};allnodes={**comps,**nt};ends={}
    rank={c['id']:i for i,c in enumerate(sorted(channels,key=lambda c:(max(times[ports[c[k]]['unit']] for k in ['source_port','target_port']),c['id'])))}
    for c in sorted(channels,key=lambda c:rank[c['id']]):
        a,b=[owner.get((ports[c[k]]['unit'],ports[c[k]]['axis']),ports[c[k]]['unit']) for k in ['source_port','target_port']]
        if a==b and a in comps and comps[a]['kind']=='传送带':continue
        allnodes[a]['outputs'].append(c['id']);allnodes[b]['inputs'].append(c['id']);ends[c['id']]=(a,b)
    candidates={c:sorted({ends[ch][1] for ch in v['outputs'] if ends[ch][1] in comps and comps[ends[ch][1]]['outputs']}) for c,v in comps.items()}
    dist={c:1 if not ds else float('inf') for c,ds in candidates.items()}
    for _ in comps:
        for c,ds in candidates.items():
            if ds:dist[c]=min(dist[c],min(dist[d]+1 for d in ds))
    edges={c:min(ds,key=lambda d:(dist[d],d)) for c,ds in candidates.items() if ds};cycles=[];done=set()
    for c in comps:
        path=[];u=c
        while u not in done and u not in path and u in edges:path.append(u);u=edges[u]
        if u in path:cycles.append(min(path[path.index(u):]))
        done.update(path)
    step_order={'schema':'step-order-v1','layer_choices':[{'component':c,'downstream':edges[c]} for c,ds in sorted(candidates.items()) if len(ds)>1],'cycle_layers':[{'component':c,'layer':q(1)} for c in sorted(cycles)],'nontransport_order':sorted(nt,key=lambda u:(rank[nt[u]['outputs'][0]] if nt[u]['outputs'] else float('inf'),u))}
    transfer=[{'unit':p['unit'],'timing':'before_send'} for p in progress if p['cooldown'] is not None]
    values={'connection.build_order':'construction.selected_order','connection.order':'timeline_connection_history','connection.tie':{'kind':'explicit_order','channels':[c['id'] for c in channels]},'connection.belt_shape':{'kind':'layout_build_history','values':shapes},'step.order':d.get('step_order',step_order),'transfer.timing':{'schema':'transfer-timing-v1','values':d.get('transfer_timing',transfer)},'transfer.phase':{'kind':'explicit_residuals','values':[{'unit':p['unit'],'slot':None,'remaining':p['cooldown']} for p in progress if p['cooldown'] is not None]},'manufacturing.recipe_selection':{'kind':'explicit_order','recipes':sorted(r['id'] for r in catalog['recipes'])},'manufacturing.input_slot_selection':{'kind':'explicit_order','slots':sorted(r['slot'] for r in inventory if ':input:' in r['slot'])},'initialization.warehouse_anchor':{'kind':'input_anchor',**anchor},'initialization.other_inventory':{'kind':'synthetic_seed','path':'initial_state.nonwarehouse'},'initialization.switches':{'kind':'input_settings','path':'settings'},'initialization.build_timing':{'kind':'input_history','path':'timeline'},'initialization.debug_end':{'kind':'input_witness','event':'debug_end','not_a_timing_strategy':True},'warehouse.external_supply':{'kind':'sufficient'}}
    for a,v in values.items():axis(raw,a,v)
    cursors=[{'side':f'{c}:{side[:-1] if side=="inputs" else "output"}','last_success':None} for c,node in allnodes.items() for side in ['inputs','outputs'] if len(node[side])>1 and (c in comps or side=='inputs')]
    state={'layout_snapshot':'built_layout','settings_anchor':anchor,'warehouse':copy.deepcopy(wh),'inventory':sorted(inventory,key=lambda r:r['slot']),'progress':sorted(progress,key=lambda r:r['unit']),'logistics':{'poll_state':{'schema':'poll-state-v1','cursors':sorted(cursors,key=lambda r:r['side']),'recency':[{'unit':u,'order':[]} for u in sorted(nt) if len(nt[u]['outputs'])>1]},'gate_counters':[{'unit':g['unit'],'total_received':q(0),'window_received':q(0),'window_started_at':None} for g in gates]},'environment':{'time':t(seed_time),'stage':'zero_intervention','online':True,'withdrawal_memory':decision({'once_fired':[],'pending_rules':[]})},'semantic_context':{'warehouse_empty_slot_order':[]}}
    raw['initial_state']['nonwarehouse']=decision(state)
    return raw

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('description',nargs='?');p.add_argument('--base',default=str(ROOT));args=p.parse_args()
    print(json.dumps(generate(json.loads(Path(args.description).read_text()) if args.description else None,args.base),ensure_ascii=False,indent=2))
