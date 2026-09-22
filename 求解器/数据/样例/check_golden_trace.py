#!/usr/bin/env python3
"""有限合成轨迹的独立重算；只支持显式声明的两个有限场景子集。"""
import copy
import hashlib
import json
from pathlib import Path
import check_examples as checker
from runtime_example import axis_values, decision, quantity, time_value, input_path, is_splitter, tick_count

BASE=Path(__file__).resolve().parent
INPUT=BASE/'混做粉碎机两下游.json'
GOLDEN=BASE/'混做粉碎机两下游-黄金轨迹.json'
OUTPUT=BASE/'混做粉碎机两下游-运行记录.json'


def run(data, checkpoints=None):
    checker.check(data,input_path(data))
    checker.require(not checkpoints or not is_splitter(data),'unsupported: 箱体中途续跑需扩展continuation投影')
    catalog=checker.load_json(BASE.parent/'正式静态目录.json')
    kinds,units,ports,channels,buffers,_=checker.geometry(data,catalog)
    state=copy.deepcopy(data['initial_state']['nonwarehouse']['value'])
    state['inventory'].sort(key=lambda r:r['slot'])
    inv={r['slot']:r['contents'] for r in state['inventory']}
    progress={r['unit']:r for r in state['progress']}
    warehouse={r['slot']:r for r in state['warehouse']['slots']}
    checker.validate_slot_identity(state['warehouse'], inv)
    allocated={row['id'] for row in data['timeline']['events']}
    executed=set()

    def allocate_event(identifier):
        checker.require(identifier not in allocated, '新运行事件与全局注册冲突: '+identifier)
        allocated.add(identifier)
        return identifier

    def execute_event(identifier):
        checker.require(identifier in allocated and identifier not in executed,
                        '运行事件未注册或重复执行: '+identifier)
        executed.add(identifier)
        return identifier
    assignments={r['port']:r['slot'] for r in data['settings']['warehouse_assignments']}
    channel_map={c['id']:c for c in channels}; buffer_map={c['id']:c for c in buffers}
    params=axis_values(data); order=params['judgment.order']['value']['template_order']
    sides={(s['unit'],s['side']):s for s in state['logistics']['poll_memory']['value']['sides']}
    recipes={r['id']:r for r in catalog['recipes']}
    due={}; gate_due={}; ticks=[]; batches=0
    gates={r['unit']:r for r in state['logistics']['gate_counters']}
    gate_settings={r['unit']:r for r in data['settings']['gates']}
    active=set(state['logistics']['active_channels'])
    tie_sides=[]
    require=checker.require
    require(params['polling.both_failure']['value']=='advance_authorized','双端失败模型不符')

    def select_source(port):
        uid=ports[port]['unit']; kind=kinds[units[uid]['kind']]
        if kind['family']=='transport': return f'{uid}:transport:0'
        if units[uid]['kind'] in ('协议核心','仓库取货口'):return assignments[port]
        if units[uid]['kind']=='协议储存箱':
            return next((s for s in inv if s.startswith(uid+':storage:') and inv[s]), f'{uid}:storage:0')
        return f'{uid}:output:0'

    def content(slot):
        if slot in warehouse:
            r=warehouse[slot]
            return [] if checker.quantity(r['quantity'])==0 else [{'item':r['item'],'quantity':r['quantity'],'entered_at':None}]
        return inv[slot]

    def select_target(port,item):
        uid=ports[port]['unit']; kind=kinds[units[uid]['kind']]
        if kind['family']=='transport':return f'{uid}:transport:0',1
        if units[uid]['kind']=='协议储存箱':
            slots=sorted((s for s in inv if s.startswith(uid+':storage:')), key=lambda s:int(s.rsplit(':',1)[1]))
            return next(((s,50) for s in slots if not inv[s] or (inv[s][0]['item']==item and sum(checker.quantity(r['quantity']) for r in inv[s])<50)), (None,50))
        require(kind['family']=='manufacturing','unsupported: 本重算不含入库或箱体')
        if any(r['item']==item for r in inv[f'{uid}:output:0']):return None,50
        slots=[x for x in params['manufacturing.input_slot_selection']['value']['slots'] if x.startswith(uid+':')]
        same=[x for x in slots if inv[x] and inv[x][0]['item']==item]
        empty=[x for x in slots if not inv[x]]
        return ((same+empty)[0],50) if same or empty else (None,50)

    def physical(c,t,usage):
        if c['id'] not in active:return None,'disconnected'
        src=select_source(c['source_port']); contents=content(src)
        if not contents:return None,'source_empty'
        item=contents[0]['item']; target_uid=ports[c['target_port']]['unit']
        if target_uid in gates:
            setting=gate_settings[target_uid]; counter=gates[target_uid]
            if setting['item'] is not None and item!=setting['item']:return None,'identity_mismatch'
            if counter['blocked_reasons']:return None,'gate_blocked'
        dst,cap=select_target(c['target_port'],item)
        if dst is None:return None,'target_kind'
        dc=inv[dst]
        if dc and (dc[0]['item']!=item or sum(checker.quantity(x['quantity']) for x in dc)>=cap):return None,'target_capacity'
        if kinds[units[ports[c['source_port']]['unit']]['kind']]['family']=='transport':
            at=checker.quantity(contents[0]['entered_at']['value'],integer=False)
            if t-at<1:return None,'residence'
        if usage.get(c['source_port'],0) or usage.get(c['target_port'],0):return None,'port_budget'
        return (src,dst,item),'ready'

    def refresh(t,usage):
        nonlocal tie_sides
        from polling_reference import refresh_sides
        tie_sides=refresh_sides(data,list(sides.values()),lambda cid:physical(channel_map[cid],t,usage)[0] is not None,state['semantic_context']['arbitration']['level_order'])

    def rebuild_graph(t,usage):
        nonlocal active,sides
        from polling_reference import build_sides
        # 一次事务在全部原因提交后映射完整旧环到最终图，不能逐边重置。
        blocked={c['id'] for c in channels if ports[c['target_port']]['unit'] in gates and gates[ports[c['target_port']]['unit']]['blocked_reasons']}
        active=set(channel_map)-blocked
        state['logistics']['active_channels']=[c['id'] for c in channels if c['id'] in active]
        state['logistics']['blocked_channels']=[c['id'] for c in channels if c['id'] in blocked]
        memory=build_sides(data,kinds,units,ports,[c for c in channels if c['id'] in active],state['logistics']['poll_memory']['value'])
        state['logistics']['poll_memory']['value']=memory
        sides={(s['unit'],s['side']):s for s in memory['sides']}
        refresh(t,usage)

    def pending_events():
        return [{'event':f'C|{deadline}|{uid}','operation':'manufacture_complete','target':uid,'trigger':{'kind':'at_time','value':time_value(deadline)},'predecessors':[],'status':'waiting'} for uid,deadline in due.items()] + [
            {'event':f'W|{deadline}|{uid}','operation':'gate_window_expiry','target':uid,'trigger':{'kind':'at_time','value':time_value(deadline)},'predecessors':[],'status':'waiting'} for uid,deadline in gate_due.items()]

    def grant(s,cid,t,usage):
        if s['current_level'] is None:return False
        l=next(l for l in s['levels'] if l['id']==s['current_level']);m=l['members'];start=m.index(l['next_channel'])
        candidates=m[start:]+m[:start]
        authorized=next((c for c in candidates if physical(channel_map[c],t,usage)[0] is not None),None) if s['graded'] else l['next_channel']
        return authorized==cid

    def advance(s,cid):
        l=next(l for l in s['levels'] if cid in l['members']); m=l['members'];l['next_channel']=m[(m.index(cid)+1)%len(m)]

    def remove(slot,count):
        if slot in warehouse:
            r=warehouse[slot];r['quantity']=quantity(checker.quantity(r['quantity'])-count,'算术推论');return
        # 输入§6、转移§4.2：同种各入格时刻分别存账，整批扣料跨记录合计。
        require(sum(checker.quantity(r['quantity']) for r in inv[slot])>=count,'源库存不足')
        while count:
            r=inv[slot][0];n=checker.quantity(r['quantity']);taken=min(n,count)
            if taken==n:inv[slot].pop(0)
            else:r['quantity']=quantity(n-taken,'算术推论')
            count-=taken

    def put(slot,item,count,t):
        require(':buffer:' in slot or all(r['item']==item for r in inv[slot]),'单格混种')
        cohort=next((r for r in inv[slot] if r['item']==item and r['entered_at'] is not None and checker.quantity(r['entered_at']['value'],integer=False)==t),None)
        if cohort:cohort['quantity']=quantity(checker.quantity(cohort['quantity'])+count,'算术推论')
        else:
            inv[slot].append({'item':item,'quantity':quantity(count,'算术推论'),'entered_at':time_value(t)})
            inv[slot].sort(key=lambda r:r['item'])

    def summary(t):
        if is_splitter(data):
            return {'tick':str(t),'warehouse_ore':str(checker.quantity(next(x['quantity'] for x in warehouse.values() if x['item']=='源矿'))),
                    'nonempty':{k:[{'item':r['item'],'quantity':r['quantity']['value'],'entered_at':r['entered_at']['value']['value']} for r in v] for k,v in inv.items() if v},
                    'splitter_next_output':sides['splitter','output']['levels'][0]['next_channel'],
                    'delivered_to_boxes':{uid:str(sum(checker.quantity(r['quantity']) for s,contents in inv.items() if s.startswith(uid+':') for r in contents)) for uid in ('north_box','east_box','west_box')}}
        cursor=sides['crusher','output']['levels'][0]['next_channel']
        return {'tick':str(t),'warehouse_ore':str(checker.quantity(next(x['quantity'] for x in warehouse.values() if x['item']=='源矿'))),
                'nonempty':{k:[{'item':r['item'],'quantity':r['quantity']['value'],'entered_at':r['entered_at']['value']['value']} for r in v] for k,v in inv.items() if v},
                'crusher_phase':progress['crusher']['phase'],'crusher_remaining':progress['crusher']['remaining']['value']['value'] if progress['crusher']['remaining'] else None,
                'crusher_next_output':cursor,'completed_batches':str(batches)}

    for t in range(tick_count(data)):
        records=[];usage={}; movements=[];passages=[]
        state['environment']['time']=time_value(t)
        for uid,deadline in list(due.items()):
            p=progress[uid];p['remaining']=time_value(deadline-t)
            if deadline==t:
                recipe=recipes[p['recipe']]; inv[f'{uid}:buffer:0'].clear()
                for item,q in recipe['outputs'].items():put(f'{uid}:buffer:0',item,checker.quantity(q),t)
                p['phase']='completed'; p['remaining']=time_value(0);due.pop(uid);batches+=1
                records.append({'event':execute_event(f'C|{t}|{uid}'),'operation':'manufacture_complete','target':uid,'outcome':'success','basis':['规则 L35','运行语义 §4.1','受限模型声明 time.manufacture_events']})
        expired=sorted(uid for uid,deadline in gate_due.items() if deadline==t)
        if expired:
            for uid in expired:
                g=gates[uid]
                g['window_received']=quantity(0,'算术推论');g['window_started_at']=None
                g['blocked_reasons']=[r for r in g['blocked_reasons'] if r!='window_exhausted']
                del gate_due[uid]
            rebuild_graph(t,usage)
            for uid in expired:
                records.append({'event':execute_event(f'W|{t}|{uid}'),'operation':'gate_window_expiry','target':uid,'outcome':'success','detail':'atomic_batch:'+','.join(expired),'basis':['规则 L64','受限转移定义 §2.1、§3.4','gate.concurrent_expiry=atomic_batch']})
        seen=set(); rounds=0
        while True:
            refresh(t,usage)
            key=json.dumps(([state['warehouse'],state['inventory'],state['progress'],state['logistics'],state['semantic_context']['arbitration'],usage] if is_splitter(data) else [state['inventory'],state['progress'],state['logistics']['poll_memory'],usage]),sort_keys=True,ensure_ascii=False)
            if key in seen:break
            seen.add(key);changed=False
            for i,template in enumerate(order):
                event=execute_event(allocate_event(f'J|{t}|{rounds}|{i}'));operation=template['operation']; target=template['target']
                outcome='guard_false'; detail='';basis=[]
                if operation=='move':
                    c=channel_map[target]; refresh(t,usage)
                    a=sides[ports[c['source_port']]['unit'],'output'];b=sides[ports[c['target_port']]['unit'],'input']
                    ga,gb=(grant(a,target,t,usage),grant(b,target,t,usage)) if target in active else (False,False)
                    route,reason=physical(c,t,usage)
                    if not (ga or gb):outcome='no_request';detail='neither_authorized'
                    elif route and ga and gb:
                        src,dst,item=route;remove(src,1);put(dst,item,1,t)
                        usage[c['source_port']]=usage[c['target_port']]=1
                        movements.append({'event':event,'channel':target,'item':item,'quantity':quantity(1,'算术推论')});outcome='success';changed=True
                    else:outcome='failure';detail=reason if not route else 'dual_permission'
                    if ga:advance(a,target)
                    if gb:advance(b,target)
                    observed_ties=list(tie_sides)
                    target_uid=ports[c['target_port']]['unit']
                    if outcome=='success' and target_uid in gates:
                        g=gates[target_uid]; setting=gate_settings[target_uid]
                        g['total_received']=quantity(checker.quantity(g['total_received'])+1,'算术推论')
                        g['window_received']=quantity(checker.quantity(g['window_received'])+1,'算术推论')
                        if g['window_started_at'] is None:
                            g['window_started_at']=time_value(t);gate_due[target_uid]=t+5
                            allocate_event(f'W|{t+5}|{target_uid}')
                        for field,reason in [('total_limit','total_exhausted'),('window_limit','window_exhausted')]:
                            count=g['total_received' if field=='total_limit' else 'window_received']
                            if setting[field] is not None and checker.quantity(count)>=checker.quantity(setting[field]):
                                if reason not in g['blocked_reasons']:g['blocked_reasons'].append(reason)
                        rebuild_graph(t,usage)
                    basis=['规则 L13、L15–17、L23–25、L29–32','约束端口速率','受限模型声明 polling.both_failure','内核输入 §5.2、§6.3']
                    if observed_ties:basis.append('polling.level_tie=fixed_arbitration:'+','.join(observed_ties))
                elif operation=='manufacture':
                    uid=target;p=progress[uid];out_slot=f'{uid}:output:0';buf_slot=f'{uid}:buffer:0'
                    if p['phase']=='completed':
                        rows=inv[buf_slot]
                        input_conflict=any(r['item']==o['item'] for slot,contents in inv.items() if slot.startswith(uid+':input:') for r in contents for o in rows)
                        if rows and not input_conflict and (not inv[out_slot] or inv[out_slot][0]['item']==rows[0]['item']) and sum(checker.quantity(r['quantity']) for r in inv[out_slot]+rows)<=50:
                            for r in copy.deepcopy(rows):put(out_slot,r['item'],checker.quantity(r['quantity']),t)
                            rows.clear();p.update(phase='idle',recipe=None,locked_recipe=None,candidate_recipes=[],remaining=None);outcome='success';changed=True
                            passages.append({'event':event,'batch':f'{uid}|{t}|output','channel':f'BC|{buf_slot}|{out_slot}'})
                    if p['phase']=='idle':
                        slots=[x for x in inv if x.startswith(uid+':input:')]
                        available={}
                        for x in slots:
                            for r in inv[x]:
                                available[r['item']]=(x,available.get(r['item'],(x,0))[1]+checker.quantity(r['quantity']))
                        match=[r for r in catalog['recipes'] if r['kind']==units[uid]['kind'] and all(item in available and available[item][1]>=checker.quantity(q) for item,q in r['inputs'].items())]
                        if match:
                            recipe=min(match,key=lambda r:params['manufacturing.recipe_selection']['value']['recipes'].index(r['id']))
                            for item,q in recipe['inputs'].items():
                                src=available[item][0];n=checker.quantity(q);remove(src,n);put(buf_slot,item,n,t)
                                passages.append({'event':event,'batch':f'{uid}|{t}|input','channel':f'BC|{src}|{buf_slot}'})
                            duration=checker.quantity(recipe['duration'])
                            allocate_event(f'C|{t+duration}|{uid}')
                            p.update(phase='working',recipe=recipe['id'],locked_recipe=recipe['id'],candidate_recipes=[recipe['id']],remaining=time_value(duration));due[uid]=t+duration;outcome='success';changed=True
                    basis=['规则 L18、L35','受限转移定义 §4.2','受限模型声明 manufacture_subactions、atomic_batch、same_instant']
                elif operation=='transfer':
                    # 此参考子集只接受传输开关关闭；不伪造无线入库或冷却执行证据。
                    require(not next(s['enabled'] for s in data['settings']['switches'] if s['unit']==target and s['function']=='transfer'), 'unsupported: 参考子集未实现无线传输')
                    detail='function_disabled';basis=['规则 L20–21、L36','受限转移定义 §4.3']
                records.append({'event':event,'operation':operation,'target':target,'outcome':outcome,'detail':detail,'basis':basis})
                if checkpoints is not None and event in checkpoints:
                    # 原子判定后捕获；刷新派生级，不再执行边界或下一模板。
                    refresh(t,usage)
                    saved=copy.deepcopy(state)
                    saved['semantic_context']['judgment_context']=decision({
                        'instant':time_value(t),'phase':'in_closure','order_scope':'global','round':rounds,
                        'next_template':i+1,'ordered_events':[f'J|{t}|{rounds}|{j}' for j in range(i+1)],
                        'next_event':f'J|{t}|{rounds}|{i+1}' if i+1<len(order) else None,
                        'continuation':{'schema':'closure-continuation-v1',
                            'boundary_done':['manufacture_completions','external_history','window_maintenance'],
                            'boundary_events':[r['event'] for r in records if r['operation']=='manufacture_complete'],
                            'seen_boundaries':[json.loads(k) for k in sorted(seen)],'round_changed':changed,
                            'instant_events':copy.deepcopy(records),'completed_batches':quantity(batches,'算术推论')}
                    },'规则 L25；边界已办、原子判定后、下一模板前的完整恢复位置')
                    saved['semantic_context']['pending_events']=decision([
                        {'event':f'C|{deadline}|{uid}','operation':'manufacture_complete','target':uid,
                         'trigger':{'kind':'at_time','value':time_value(deadline)},'predecessors':[],'status':'waiting'}
                        for uid,deadline in due.items()],'仍未到期的制造完成事件')
                    saved['semantic_context']['tick_context']=decision({
                        'window_start':time_value(t),'window_end':time_value(t+1),
                        'movements':copy.deepcopy(movements),
                        'port_usage':[{'port':p,'quantity':quantity(n,'算术推论')} for p,n in sorted(usage.items())],
                        'internal_passages':copy.deepcopy(passages)},'保留本窗口已消耗额度与已完成内部穿越')
                    checkpoints[event]=saved

            rounds+=1
            if changed:seen.clear()
            require(rounds<100,'inconclusive: 资源上限，不得强行推进时刻')
        refresh(t,usage)
        state['semantic_context']['judgment_context']=decision({'instant':time_value(t),'phase':'after_closure','order_scope':'global','round':rounds,'next_template':0,'ordered_events':[],'next_event':None},'完整扫描边界重复，保留轮询状态')
        state['semantic_context']['pending_events']=decision(pending_events(),'制造完成及准入口窗口的非判定到期事件' if gates else '制造耗时生成的非判定到期事件')
        state['semantic_context']['tick_context']=decision({'window_start':time_value(t),'window_end':time_value(t+1),'movements':movements,'port_usage':[{'port':p,'quantity':quantity(n,'算术推论')} for p,n in sorted(usage.items())],'internal_passages':passages},'本时刻实际成功记录')
        from ledger_reference import warehouse_ledger
        ledger=warehouse_ledger(data,records,state)
        ticks.append({'warehouse_ledger':ledger,'time':time_value(t),'events':records,'state':copy.deepcopy(state),'summary':summary(t),'closure':{'kind':'no_success_state_repeat','scan_rounds':rounds,'basis':['受限模型声明 time.instant_end','内核输入 §5.2']}})
    return ticks


def main():
    from runtime_record import build_record, validate_record
    data=checker.load_json(INPUT); ticks=run(data); golden=checker.load_json(GOLDEN)
    output=build_record(data,ticks,golden)
    validate_record(output,data,ticks)
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'通过','golden_match':True,'ticks':len(ticks),
        'complete_cycles':output['validation_scope']['manufacturing_cycles_completed']['value'],
        'events':[len(t['events']) for t in ticks],'output':str(OUTPUT)},ensure_ascii=False))


if __name__=='__main__':main()
