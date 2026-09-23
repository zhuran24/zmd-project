"""Independent small-layout oracle: no imports from the solver or synchronizer."""
import collections,copy,json
from pathlib import Path
v=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text())
def number(q):return int(q['value'])
def canonical(inventory):
    return {r['slot']:[{'item':c['item'],'n':number(c['quantity']),'entered':number(c['entered_at']['value']) if c['entered_at'] else None,'last':c.get('last_unit')} for c in r['contents']] for r in inventory}
def totals(inv):
    result=collections.Counter()
    for rows in inv.values():
        for c in rows:result[c['item']]+=c['n']
    return result
def independent_ports(units):
    # Local coordinates and counterclockwise quarter-turns as defined by the input convention.
    ports={}
    for name,kind,x,y,rot in units:
        turn={'r0':0,'r90':1,'r180':2,'r270':3}[rot]
        for side,(dx,dy) in {'south':(0,-1),'north':(0,1),'west':(-1,0),'east':(1,0)}.items():
            if kind=='桥接器':role='both'
            elif kind=='传送带':
                if side not in ['south','north']:continue
                role='input' if side=='south' else 'output'
            elif kind=='分流器':role='input' if side=='south' else 'output'
            else:raise AssertionError(kind)
            for _ in range(turn):dx,dy=-dy,dx
            ports[f'{name}:{side}:0']={'unit':name,'kind':kind,'pos':(x,y),'normal':(dx,dy),'role':role,'axis':('vertical' if side in ['north','south'] else 'horizontal') if kind=='桥接器' else None}
    return ports
def check(case):
    d=v/'cases'/case['name'];seed=load(d/'seed.json');record=load(d/'record.json')
    ports=independent_ports(case['units'])
    expected_channels={f'PC|{a}|{b}' for a,p in ports.items() for b,q in ports.items() if p['role']!='input' and q['role']!='output' and (p['pos'][0]+p['normal'][0],p['pos'][1]+p['normal'][1])==q['pos'] and p['normal']==tuple(-n for n in q['normal'])}
    actual_channels={c['id'] for c in seed['layout']['physical_channels']}
    assert actual_channels==expected_channels,(actual_channels^expected_channels)
    assert len(actual_channels)==case['expect']['channels']
    def slot(port):
        p=ports[port];return p['unit']+':'+(p['axis'] or 'transport')+':0'
    state=canonical(seed['initial_state']['nonwarehouse']['value']['inventory'])
    start=totals(state);successful=[];guards=[];tick_summaries=[]
    ticks=record['trace']['ticks']
    assert len(ticks)==case['ticks']
    for tick in ticks:
        time=number(tick['state']['environment']['time']['value'])
        used=collections.Counter()
        for e in tick['events']:
            if e['operation']!='move':continue
            _,a,b=e['target'].split('|');src,dst=slot(a),slot(b)
            if e.get('detail')=='immediate_return':
                assert state[src] and state[src][0]['last']==ports[b]['unit']
                guards.append({'tick':time,'channel':e['target'],'destination_empty':not state[dst]})
            if e['outcome']!='success':continue
            assert len(state[src])==1 and state[src][0]['n']==1 and not state[dst]
            item=state[src][0]
            assert item['last']!=ports[b]['unit'],'immediate return succeeded'
            assert time-item['entered']>=1,'transport cooldown violated'
            used[a]+=1;used[b]+=1
            assert used[a]<=1 and used[b]<=1,'physical port used twice'
            state[src]=[]
            state[dst]=[dict(item=item['item'],n=1,entered=time,last=ports[a]['unit'] if ports[b]['kind']=='桥接器' else None)]
            successful.append({'tick':time,'item':item['item'],'from':ports[a]['unit'],'to':ports[b]['unit'],'channel':e['target']})
            if case['expect'].get('chain'):
                direction=case['expect']['direction'];dim=0 if direction in ['east','west'] else 1;sign=1 if direction in ['east','north'] else -1
                assert (ports[b]['pos'][dim]-ports[a]['pos'][dim])*sign==1,'item moved backwards'
        actual=canonical(tick['state']['inventory'])
        assert state==actual,{'tick':time,'simulated':state,'actual':actual}
        assert totals(state)==start
        for values in state.values():assert sum(c['n'] for c in values)<=1
        tick_summaries.append({'tick':time,'inventory':{k:c for k,c in state.items() if c}})
        sides=tick['state']['logistics']['poll_memory']['value']['sides']
        for name,kind,*_ in case['units']:
            if kind!='桥接器':continue
            local=[x for x in sides if x['unit']==name]
            assert {(x['axis'],x['side']) for x in local}=={(a,d) for a in ['vertical','horizontal'] for d in ['input','output']}
            for side in local:
                for level in side['levels']:
                    for channel in level['members']:
                        _,a,b=channel.split('|');p=ports[b if side['side']=='input' else a]
                        assert p['unit']==name and p['axis']==side['axis'],'polling scope crossed an axis'
    e=case['expect']
    for slotname,n in e.get('out',{}).items():assert sum(c['n'] for c in state[slotname])==n,(slotname,state)
    if e.get('trapped'):
        assert len(successful)==1 and len(state['b:vertical:0'])==1
        assert len(state['north:transport:0'])+len(state['south:transport:0'])==1
        assert all(c.split('|')[2].startswith('b:') for c in actual_channels)
    if e.get('empty'):assert not successful and not start
    if e.get('same_item'):
        assert state['b:vertical:0'][0]['item']==state['b:horizontal:0'][0]['item']=='源矿'
    if e.get('chain'):
        assert sum(c['n'] for key,rows in state.items() if key.startswith('exit') for c in rows)==3
        assert guards and any(g['destination_empty'] for g in guards),'gap never exercised the return guard'
        for item in start:
            assert sum(m['item']==item and m['from'].startswith('b') and m['to'].startswith('b') for m in successful)==e['chain']-1
    if e.get('axis_independent'):
        control=load(v/'cases/axis-belt-control/record.json')['trace']['ticks']
        for a,b in zip(ticks,control):
            def project(t):
                state=t['state'];return {'inventory':[x for x in state['inventory'] if x['slot'] in ['west:transport:0','b:horizontal:0','east:transport:0']],
                    'polling':[x for x in state['logistics']['poll_memory']['value']['sides'] if x['unit']=='b' and x['axis']=='horizontal']}
            assert project(a)==project(b),'other axis changes belt-axis inventory/polling'
    result={'name':case['name'],'pass':True,'ticks':len(ticks),'channels':len(actual_channels),'successful_moves':len(successful),'return_guard_failures':len(guards),'return_guard_with_empty_destination':sum(g['destination_empty'] for g in guards),'final_inventory':tick_summaries[-1]['inventory']}
    (d/'observations.json').write_text(json.dumps({'result':result,'moves':successful,'return_guards':guards,'states':tick_summaries},ensure_ascii=False,indent=2)+'\n')
    return result
results=[]
for case in load(v/'cases.json'):
    try:results.append(check(case))
    except Exception as e:results.append({'name':case['name'],'pass':False,'error':repr(e)})
(v/'case-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
for result in results:print(json.dumps(result,ensure_ascii=False))
raise SystemExit(any(not r['pass'] for r in results))
