#!/usr/bin/env python3
"""有限合成轨迹的独立重算；只支持已声明的 0–3 tick 子集。"""
import copy
import hashlib
import json
from pathlib import Path
import check_examples as checker
from runtime_example import axis_values, decision, quantity, time_value

BASE=Path(__file__).resolve().parent
INPUT=BASE/'混做粉碎机两下游.json'
GOLDEN=BASE/'混做粉碎机两下游-黄金轨迹.json'
OUTPUT=BASE/'混做粉碎机两下游-运行记录.json'


def run(data):
    checker.check(data,INPUT)
    catalog=checker.load_json(BASE.parent/'正式静态目录.json')
    kinds,units,ports,channels,buffers,_=checker.geometry(data,catalog)
    state=copy.deepcopy(data['initial_state']['nonwarehouse']['value'])
    inv={r['slot']:r['contents'] for r in state['inventory']}
    progress={r['unit']:r for r in state['progress']}
    warehouse={r['slot']:r for r in state['warehouse']['slots']}
    assignments={r['port']:r['slot'] for r in data['settings']['warehouse_assignments']}
    channel_map={c['id']:c for c in channels}; buffer_map={c['id']:c for c in buffers}
    params=axis_values(data); order=params['judgment.order']['value']['template_order']
    sides={(s['unit'],s['side']):s for s in state['logistics']['poll_memory']['value']['sides']}
    recipes={r['id']:r for r in catalog['recipes']}
    due={}; ticks=[]; batches=0
    require=checker.require
    require(params['polling.both_failure']['value']=='advance_authorized','双端失败模型不符')

    def select_source(port):
        uid=ports[port]['unit']; kind=kinds[units[uid]['kind']]
        if kind['family']=='transport': return f'{uid}:transport:0'
        if units[uid]['kind'] in ('协议核心','仓库取货口'):return assignments[port]
        return f'{uid}:output:0'

    def content(slot):
        if slot in warehouse:
            r=warehouse[slot]
            return [] if checker.quantity(r['quantity'])==0 else [{'item':r['item'],'quantity':r['quantity'],'entered_at':None}]
        return inv[slot]

    def select_target(port,item):
        uid=ports[port]['unit']; kind=kinds[units[uid]['kind']]
        if kind['family']=='transport':return f'{uid}:transport:0',1
        require(kind['family']=='manufacturing','unsupported: 本重算不含入库或箱体')
        slots=[x for x in params['manufacturing.input_slot_selection']['value']['slots'] if x.startswith(uid+':')]
        same=[x for x in slots if inv[x] and inv[x][0]['item']==item]
        empty=[x for x in slots if not inv[x]]
        return ((same+empty)[0],50) if same or empty else (None,50)

    def physical(c,t,usage):
        src=select_source(c['source_port']); contents=content(src)
        if not contents:return None,'source_empty'
        item=contents[0]['item']; dst,cap=select_target(c['target_port'],item)
        if dst is None:return None,'target_kind'
        dc=inv[dst]
        if dc and (dc[0]['item']!=item or sum(checker.quantity(x['quantity']) for x in dc)>=cap):return None,'target_capacity'
        if kinds[units[ports[c['source_port']]['unit']]['kind']]['family']=='transport':
            at=checker.quantity(contents[0]['entered_at']['value'],integer=False)
            if t-at<1:return None,'residence'
        if usage.get(c['source_port'],0) or usage.get(c['target_port'],0):return None,'port_budget'
        return (src,dst,item),'ready'

    def refresh(t,usage):
        for s in sides.values():
            if not s['levels']:s['current_level']=None;continue
            require(len(s['levels'])==1,'unsupported: 有界重算只支持单级')
            level=s['levels'][0]
            s['current_level']=level['id'] if not s['graded'] or any(physical(channel_map[c],t,usage)[0] is not None for c in level['members']) else None

    def grant(s,cid,t,usage):
        if s['current_level'] is None:return False
        l=s['levels'][0];m=l['members'];start=m.index(l['next_channel'])
        candidates=m[start:]+m[:start]
        authorized=next((c for c in candidates if physical(channel_map[c],t,usage)[0] is not None),None) if s['graded'] else l['next_channel']
        return authorized==cid

    def advance(s,cid):
        l=s['levels'][0]; m=l['members'];l['next_channel']=m[(m.index(cid)+1)%len(m)]

    def remove(slot,count):
        if slot in warehouse:
            r=warehouse[slot];r['quantity']=quantity(checker.quantity(r['quantity'])-count,'算术推论');return
        r=inv[slot][0]; n=checker.quantity(r['quantity'])-count
        if n:r['quantity']=quantity(n,'算术推论')
        else:inv[slot].clear()

    def put(slot,item,count,t):
        if inv[slot]:
            require(inv[slot][0]['item']==item,'单格混种')
            inv[slot][0]['quantity']=quantity(checker.quantity(inv[slot][0]['quantity'])+count,'算术推论')
        else:inv[slot].append({'item':item,'quantity':quantity(count,'算术推论'),'entered_at':time_value(t)})

    def summary(t):
        cursor=sides['crusher','output']['levels'][0]['next_channel']
        return {'tick':str(t),'warehouse_ore':str(checker.quantity(next(x['quantity'] for x in warehouse.values() if x['item']=='源矿'))),
                'nonempty':{k:[{'item':r['item'],'quantity':r['quantity']['value'],'entered_at':r['entered_at']['value']['value']} for r in v] for k,v in inv.items() if v},
                'crusher_phase':progress['crusher']['phase'],'crusher_remaining':progress['crusher']['remaining']['value']['value'] if progress['crusher']['remaining'] else None,
                'crusher_next_output':cursor,'completed_batches':str(batches)}

    for t in range(4):
        records=[];usage={}; movements=[];passages=[]
        state['environment']['time']=time_value(t)
        for uid,deadline in list(due.items()):
            p=progress[uid];p['remaining']=time_value(deadline-t)
            if deadline==t:
                recipe=recipes[p['recipe']]; inv[f'{uid}:buffer:0'].clear()
                for item,q in recipe['outputs'].items():put(f'{uid}:buffer:0',item,checker.quantity(q),t)
                p['phase']='completed'; p['remaining']=time_value(0);due.pop(uid);batches+=1
                records.append({'event':f'C|{t}|{uid}','operation':'manufacture_complete','target':uid,'outcome':'success','basis':['规则 L35','运行语义 §4.1','受限模型声明 time.manufacture_events']})
        seen=set(); rounds=0
        while True:
            refresh(t,usage)
            key=json.dumps([state['inventory'],state['progress'],state['logistics']['poll_memory'],usage],sort_keys=True,ensure_ascii=False)
            if key in seen:break
            seen.add(key);changed=False
            for i,template in enumerate(order):
                event=f'J|{t}|{rounds}|{i}';operation=template['operation']; target=template['target']
                outcome='guard_false'; detail='';basis=[]
                if operation=='move':
                    c=channel_map[target]; refresh(t,usage)
                    a=sides[ports[c['source_port']]['unit'],'output'];b=sides[ports[c['target_port']]['unit'],'input']
                    ga,gb=grant(a,target,t,usage),grant(b,target,t,usage)
                    route,reason=physical(c,t,usage)
                    if not (ga or gb):outcome='no_request';detail='neither_authorized'
                    elif route and ga and gb:
                        src,dst,item=route;remove(src,1);put(dst,item,1,t)
                        usage[c['source_port']]=usage[c['target_port']]=1
                        movements.append({'event':event,'channel':target,'item':item,'quantity':quantity(1,'算术推论')});outcome='success';changed=True
                    else:outcome='failure';detail=reason if not route else 'dual_permission'
                    if ga:advance(a,target)
                    if gb:advance(b,target)
                    basis=['规则 L13、L15–17、L23–25、L29–32','约束端口速率','受限模型声明 polling.both_failure','内核输入 §5.2、§6.3']
                elif operation=='manufacture':
                    uid=target;p=progress[uid];out_slot=f'{uid}:output:0';buf_slot=f'{uid}:buffer:0'
                    if p['phase']=='completed':
                        rows=inv[buf_slot]
                        if rows and (not inv[out_slot] or inv[out_slot][0]['item']==rows[0]['item']) and sum(checker.quantity(r['quantity']) for r in inv[out_slot]+rows)<=50:
                            for r in copy.deepcopy(rows):put(out_slot,r['item'],checker.quantity(r['quantity']),t)
                            rows.clear();p.update(phase='idle',recipe=None,locked_recipe=None,candidate_recipes=[],remaining=None);outcome='success';changed=True
                            passages.append({'event':event,'batch':f'{uid}|{t}|output','channel':f'BC|{buf_slot}|{out_slot}'})
                    if p['phase']=='idle':
                        slots=[x for x in inv if x.startswith(uid+':input:')]
                        available={r['item']:(x,checker.quantity(r['quantity'])) for x in slots for r in inv[x]}
                        match=[r for r in catalog['recipes'] if r['kind']==units[uid]['kind'] and all(item in available and available[item][1]>=checker.quantity(q) for item,q in r['inputs'].items())]
                        if match:
                            recipe=min(match,key=lambda r:params['manufacturing.recipe_selection']['value']['recipes'].index(r['id']))
                            for item,q in recipe['inputs'].items():
                                src=available[item][0];n=checker.quantity(q);remove(src,n);put(buf_slot,item,n,t)
                                passages.append({'event':event,'batch':f'{uid}|{t}|input','channel':f'BC|{src}|{buf_slot}'})
                            duration=checker.quantity(recipe['duration']);p.update(phase='working',recipe=recipe['id'],locked_recipe=recipe['id'],candidate_recipes=[recipe['id']],remaining=time_value(duration));due[uid]=t+duration;outcome='success';changed=True
                    basis=['规则 L18、L35','受限转移定义 §4.2','受限模型声明 manufacture_subactions、atomic_batch、same_instant']
                records.append({'event':event,'operation':operation,'target':target,'outcome':outcome,'detail':detail,'basis':basis})
            rounds+=1
            if changed:seen.clear()
            require(rounds<100,'inconclusive: 资源上限，不得强行推进时刻')
        refresh(t,usage)
        state['semantic_context']['judgment_context']=decision({'instant':time_value(t),'phase':'after_closure','order_scope':'global','round':rounds,'next_template':0,'ordered_events':[],'next_event':None},'完整扫描边界重复，保留轮询状态')
        state['semantic_context']['pending_events']=decision([{'event':f'C|{deadline}|{uid}','operation':'manufacture_complete','target':uid,'trigger':{'kind':'at_time','value':time_value(deadline)},'predecessors':[],'status':'waiting'} for uid,deadline in due.items()],'制造耗时生成的非判定到期事件')
        state['semantic_context']['tick_context']=decision({'window_start':time_value(t),'window_end':time_value(t+1),'movements':movements,'port_usage':[{'port':p,'quantity':quantity(n,'算术推论')} for p,n in sorted(usage.items())],'internal_passages':passages},'本时刻实际成功记录')
        ticks.append({'time':time_value(t),'events':records,'state':copy.deepcopy(state),'summary':summary(t),'closure':{'kind':'no_success_state_repeat','scan_rounds':rounds,'basis':['受限模型声明 time.instant_end','内核输入 §5.2']}})
    return ticks


def main():
    data=checker.load_json(INPUT); ticks=run(data); golden=checker.load_json(GOLDEN)
    actual=[t['summary'] for t in ticks]
    checker.require(actual==golden['ticks'],'黄金轨迹与有限重算不同')
    profile=checker.load_json(BASE/'kernel_profile_v1参数赋值.json')
    catalog=BASE.parent/'正式静态目录.json';reg=checker.AXIS_PATH; semantics=BASE.parents[1]/'规格/受限模型声明.md'
    fingerprints=[{'role':role,'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for role,p in [('input',INPUT),('catalog',catalog),('axis_registry',reg),('profile',semantics),('golden',GOLDEN),('checker',Path(__file__)),('checker',BASE/'runtime_example.py'),('profile',BASE.parents[1]/'规格/内核配置-v1.json'),('semantics',BASE.parents[1]/'规格/受限转移定义.md'),('semantics',BASE.parents[1]/'规格/内核输入.md'),('schema',BASE.parents[1]/'规格/内核输出.schema.json')]]+[{'role':'formal_source','path':str((checker.ROOT/n).resolve()),'sha256':h} for n,h in checker.SOURCE_HASHES.items()]
    output={'schema':'kernel-output-v1','run_id':'mixed_crusher_prefix_0_3','profile_id':'kernel_profile_v1','producer':{'kind':'bounded_reference_checker','path':str(Path(__file__).resolve()),'claim':'有限重算，与手工黄金摘要比较；不是 Rust 内核结果'},'status':'completed','fingerprints':fingerprints,
            'parameter_assignment':data['parameters'],'input_history':{'timeline':data['timeline'],'construction':data['construction'],'debug_operations':data['debug_operations'],'environment':data['environment'],'reachability':data['initial_state']['reachability']},
            'uncovered_axes':[{'axis':r['axis'],'reason':r['coverage_loss'],'disposition':r['disposition']} for r in profile['axes'] if r['disposition']!='已定'],
            'trace':{'start_state':data['initial_state']['nonwarehouse']['value'],'ticks':ticks,'end_time':time_value(3),'format':'full_state_each_instant'},
            'validation_scope':{'kind':'finite_trace','from':time_value(0),'through':time_value(3),'golden_match':True,'initial_history':'conditional_witness','universal_parameters':False,'all_reachable_cycles':False,'target_certified':False,'manufacturing_cycles_completed':quantity(2,'算术推论')},
            'open_items':['未覆盖实际混做与下游生产','未覆盖离线、其它初态与判定顺序','有限重算不替代全部可达循环和完整目标认证']}
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','golden_match':True,'ticks':4,'complete_cycles':2,'events':[len(t['events']) for t in ticks],'output':str(OUTPUT)},ensure_ascii=False))


if __name__=='__main__':main()
