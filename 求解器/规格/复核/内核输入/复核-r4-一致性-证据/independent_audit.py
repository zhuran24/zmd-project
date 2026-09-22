"""一致性复核：独立几何、逐轴对照和有限轨迹重算；输出只写本目录。"""
import copy
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
SNAP = BASE / '被审快照'
EXAMPLES = SNAP / '求解器/数据/样例'


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, (path, key)
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def write(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def number(value):
    return Fraction(value['value'])


def instant(value):
    assert value['kind'] == 'rational'
    return number(value['value'])


def axes(data):
    return {a: d for g in ('fixed', 'offline_mutable', 'fixedness_unproven')
            for a, d in data['parameters'][g].items()}


def geometry(data, catalog):
    """用连续矩形及端口线段中点旋转求相遇，不调用被审程序。"""
    kinds = {k['id']: k for k in catalog['units']}
    occupied, ports, units, bcs = {}, {}, {}, []
    for u in data['layout']['units']:
        uid = u['id']; k = kinds[u['kind']]; units[uid] = u
        w, h = [int(number(k['dimensions'][d])) for d in ('width', 'height')]
        ox, oy = map(number, u['origin'])
        turn = ('r0', 'r90', 'r180', 'r270').index(u['rotation'])
        def transform(x, y):
            return ((x, y), (h-y, x), (w-x, h-y), (y, w-x))[turn]
        cells = []
        for x in range(w):
            for y in range(h):
                rx, ry = transform(Fraction(x)+Fraction(1, 2), Fraction(y)+Fraction(1, 2))
                cell = (int(ox+rx), int(oy+ry))
                assert cell not in occupied and all(0 <= z < 70 for z in cell)
                occupied[cell] = uid; cells.append(cell)
        if u['occupied_cells'] is not None:
            assert sorted(cells) == sorted(tuple(map(int, map(number, c))) for c in u['occupied_cells'])
        if u['kind'] == '桥接器':
            edges = {e['side']: e for variant in k['ports']['layouts'] for e in variant}.values()
        else:
            edges = k['ports']['layouts'][u['port_layout']]
        for edge in edges:
            side = edge['side']; role = edge['role']
            if u['kind'] == '桥接器':
                a = u['bridge_axes'][edge['axis']]
                assert a['status'] == 'resolved'
                role = 'input' if side == a['input_side'] else 'output'
            for pos in edge['positions']:
                p = int(number(pos)); half = Fraction(1, 2)
                midpoint = {'south': (p+half, 0), 'north': (p+half, h),
                            'west': (0, p+half), 'east': (w, p+half)}[side]
                dx, dy = {'south': (0,-1), 'north': (0,1), 'west': (-1,0), 'east': (1,0)}[side]
                normal = ((dx,dy), (-dy,dx), (-dx,-dy), (dy,-dx))[turn]
                rx, ry = transform(*midpoint)
                ports[f'{uid}:{side}:{p}'] = {'unit': uid, 'role': role, 'axis': edge['axis'],
                                             'point': (ox+rx, oy+ry), 'normal': normal, 'family': k['family']}
        if k['family'] == 'manufacturing':
            for row in k['inventory']:
                if row['role'] in ('input','output'):
                    for index in range(int(number(row['count']))):
                        ordinary = f"{uid}:{row['role']}:{index}"; buffer = f'{uid}:buffer:0'
                        a,b = (ordinary,buffer) if row['role']=='input' else (buffer,ordinary)
                        bcs.append({'id':f'BC|{a}|{b}', 'source_slot':a, 'target_slot':b})
    pcs = []
    for a, p in ports.items():
        if p['role'] != 'output': continue
        for b, q in ports.items():
            if q['role'] != 'input' or p['unit'] == q['unit']: continue
            if p['point'] == q['point'] and p['normal'] == tuple(-z for z in q['normal']) and 'transport' in (p['family'],q['family']):
                pcs.append({'id':f'PC|{a}|{b}', 'source_port':a, 'target_port':b})
    assert sorted(pcs,key=lambda c:c['id']) == sorted(data['layout']['physical_channels'],key=lambda c:c['id'])
    assert sorted(bcs,key=lambda c:c['id']) == sorted(data['layout']['buffer_channels'],key=lambda c:c['id'])
    by_id = {c['id']:c for c in pcs}
    for route in data['scenario']['expected_paths']:
        selected = [by_id[c] for c in route['physical_channels']]
        for left,right in zip(selected, selected[1:]):
            p,q = ports[left['target_port']], ports[right['source_port']]
            assert p['unit'] == q['unit'] and p['family'] == 'transport'
            if units[p['unit']]['kind'] == '桥接器': assert p['axis'] == q['axis']
    power = {}
    for uid,u in units.items():
        if not kinds[u['kind']]['power_required']: continue
        cells = [c for c,v in occupied.items() if v==uid]
        power[uid] = [p['id'] for p in units.values() if p['kind']=='供电桩'
                      and any(number(p['origin'][0])-5 <= x < number(p['origin'][0])+7
                              and number(p['origin'][1])-5 <= y < number(p['origin'][1])+7 for x,y in cells)]
    return units, ports, pcs, {'units':len(units),'occupied_cells':len(occupied),'physical_channels':pcs,'buffer_channels':bcs,'positive_area_power':power,
                              'ports':{pid:{**p,'point':[str(z) for z in p['point']]} for pid,p in ports.items()}}


def replay(data, catalog, record, units, ports, pcs):
    """从输入自身建立物理状态，自行生成扫描和后效；不调用被审运行函数。"""
    seed = data['initial_state']['nonwarehouse']['value']
    inv = {r['slot']: [] for r in seed['inventory']}
    warehouse = {r['slot']:[r['item'],int(number(r['quantity']))] for r in seed['warehouse']['slots']}
    assignments = {r['port']:r['slot'] for r in data['settings']['warehouse_assignments']}
    kinds = {r['id']:r for r in catalog['units']}
    recipes = {r['id']:r for r in catalog['recipes']}
    prog = {u:None for u in units if kinds[units[u]['kind']]['family']=='manufacturing'}
    params = axes(data); order = params['judgment.order']['value']['template_order']
    tie = params['connection.tie']['value']['channels']
    build = {m['unit']:instant(next(e for e in data['timeline']['events'] if e['id']==m['event'])['time']) for m in data['construction']['moments']}
    channels = {c['id']:c for c in pcs}; rings = {}; cursor = {}
    for uid,u in units.items():
        if u['kind']=='供电桩': continue
        for side,field in (('input','target_port'),('output','source_port')):
            members = [c['id'] for c in pcs if ports[c[field]]['unit']==uid]
            members.sort(key=lambda c:(max(build[p.split(':')[0]] for p in c.split('|')[1:]),tie.index(c)))
            rings[uid,side] = members; cursor[uid,side] = 0
    def slot_for(port):
        uid = ports[port]['unit']
        if port in assignments: return assignments[port]
        return f"{uid}:{'transport' if ports[port]['family']=='transport' else 'output'}:0"
    def source(slot):
        if slot in warehouse:
            item,n = warehouse[slot]; return [] if n==0 else [(item,n,None)]
        return inv[slot]
    def route(cid,t,used):
        c=channels[cid]; a,b=c['source_port'],c['target_port']; src=slot_for(a); contents=source(src)
        if not contents:return None,'source_empty'
        item,n,age=contents[0]; uid=ports[b]['unit']
        if ports[b]['family']=='transport': dst=f'{uid}:transport:0'; cap=1
        else:
            assert ports[b]['family']=='manufacturing'
            choices=params['manufacturing.input_slot_selection']['value']['slots']
            slots=[s for s in choices if s.startswith(uid+':')]
            if any(x[0]==item for x in inv[f'{uid}:output:0']): return None,'target_kind'
            same=[s for s in slots if inv[s] and inv[s][0][0]==item]
            empty=[s for s in slots if not inv[s]]
            if not same and not empty:return None,'target_kind'
            dst=(same+empty)[0];cap=50
        if inv[dst] and (inv[dst][0][0]!=item or sum(x[1] for x in inv[dst])>=cap):return None,'target_capacity'
        if ports[a]['family']=='transport' and t-age<1:return None,'residence'
        if used.get(a,0) or used.get(b,0):return None,'port_budget'
        return (src,dst,item),'ready'
    def authorized(key,t,used):
        members=rings[key]
        if not members:return None
        graded=key[1]=='input' or kinds[units[key[0]]['kind']]['family']!='transport'
        if not graded:return members[cursor[key]]
        return next((members[(cursor[key]+i)%len(members)] for i in range(len(members))
                     if route(members[(cursor[key]+i)%len(members)],t,used)[0]),None)
    def decrement(slot,n):
        if slot in warehouse:warehouse[slot][1]-=n;return
        item,q,at=inv[slot][0];inv[slot]=[(item,q-n,at)] if q>n else []
    def increment(slot,item,n,t):
        if inv[slot]:
            a,q,at=inv[slot][0]; assert a==item; inv[slot]=[(a,q+n,at)]
        else:inv[slot]=[(item,n,Fraction(t))]
    def poll(t,used):
        rows=[]
        for key,members in rings.items():
            uid,side=key; graded=side=='input' or kinds[units[uid]['kind']]['family']!='transport'
            lid=f"L|{uid}|{side}|{'other' if graded else 'ungraded'}"
            current=lid if members and (not graded or any(route(c,t,used)[0] for c in members)) else None
            rows.append({'unit':uid,'side':side,'graded':graded,'current_level':current,
                         'levels':[{'id':lid,'members':members,'next_channel':members[cursor[key]]}] if members else []})
        return {'schema':'poll-memory-v1','sides':rows}
    assert poll(0,{})==seed['logistics']['poll_memory']['value']
    results=[]; total_batches=0
    for t in range(4):
        events=[];used={};moves=[]; passages=[]
        for uid in [x['target'] for x in order if x['operation']=='manufacture']:
            job=prog[uid]
            if job and job['phase']=='working' and job['due']==t:
                inv[f'{uid}:buffer:0']=[(i,int(number(q)),Fraction(t)) for i,q in recipes[job['recipe']]['outputs'].items()]
                job['phase']='completed'; total_batches+=1
                events.append((f'C|{t}|{uid}','manufacture_complete',uid,'success',None))
        seen=set(); sweep=0
        while True:
            state_key=repr((inv,warehouse,prog,poll(t,used),sorted(used.items())))
            if state_key in seen:break
            seen.add(state_key)
            for index,template in enumerate(order):
                eid=f'J|{t}|{sweep}|{index}'; op=template['operation']; target=template['target']; outcome='guard_false'; detail=''
                if op=='move':
                    c=channels[target]; a,b=c['source_port'],c['target_port']
                    keys=[(ports[a]['unit'],'output'),(ports[b]['unit'],'input')]
                    grants=[authorized(k,t,used)==target for k in keys]
                    found,reason=route(target,t,used)
                    if not any(grants):outcome='no_request';detail='neither_authorized'
                    elif all(grants) and found:
                        src,dst,item=found;decrement(src,1);increment(dst,item,1,t);used[a]=used[b]=1;outcome='success'
                        moves.append((eid,target,item,1))
                    else:outcome='failure';detail=reason if found is None else 'dual_permission'
                    for key,grant in zip(keys,grants):
                        if grant:cursor[key]=(rings[key].index(target)+1)%len(rings[key])
                else:
                    assert op=='manufacture';uid=target;job=prog[uid];buffer=f'{uid}:buffer:0';output=f'{uid}:output:0'
                    slots=[s for s in inv if s.startswith(uid+':input:')]
                    if job and job['phase']=='completed':
                        product=inv[buffer]; conflict=any(a[0]==b[0] for s in slots for a in inv[s] for b in product)
                        if product and not conflict and (not inv[output] or inv[output][0][0]==product[0][0]) and sum(x[1] for x in inv[output]+product)<=50:
                            for item,n,at in product:increment(output,item,n,t)
                            inv[buffer]=[];prog[uid]=None;outcome='success'
                            passages.append((eid,f'{uid}|{t}|output',f'BC|{buffer}|{output}'))
                    if prog[uid] is None:
                        available={a[0]:(s,a[1]) for s in slots for a in inv[s]}
                        candidates=[recipes[rid] for rid in params['manufacturing.recipe_selection']['value']['recipes']
                                    if recipes[rid]['kind']==units[uid]['kind'] and all(i in available and available[i][1]>=number(q) for i,q in recipes[rid]['inputs'].items())]
                        if candidates:
                            recipe=candidates[0]
                            for item,q in recipe['inputs'].items():
                                src=available[item][0]; n=int(number(q));decrement(src,n);increment(buffer,item,n,t)
                                passages.append((eid,f'{uid}|{t}|input',f'BC|{src}|{buffer}'))
                            prog[uid]={'recipe':recipe['id'],'phase':'working','due':Fraction(t)+number(recipe['duration'])};outcome='success'
                events.append((eid,op,target,outcome,detail))
            sweep+=1; assert sweep<100
        actual=record['trace']['ticks'][t]; actual_state=actual['state']
        assert events==[(e['event'],e['operation'],e['target'],e['outcome'],e.get('detail')) for e in actual['events']], ('events',t)
        assert sweep==actual['closure']['scan_rounds']
        assert inv=={r['slot']:[(c['item'],int(number(c['quantity'])),instant(c['entered_at']) if c['entered_at'] else None) for c in r['contents']] for r in actual_state['inventory']},('inventory',t)
        assert warehouse=={r['slot']:[r['item'],int(number(r['quantity']))] for r in actual_state['warehouse']['slots']}
        assert poll(t,used)==actual_state['logistics']['poll_memory']['value']
        for p in actual_state['progress']:
            job=prog[p['unit']]
            assert p['phase']==('idle' if job is None else job['phase'])
            assert p['recipe']==(None if job is None else job['recipe'])
            assert p['locked_recipe']==p['recipe'] and p['candidate_recipes']==([] if job is None else [job['recipe']])
            assert p['remaining']==None if job is None else instant(p['remaining'])==job['due']-t
        tc=actual_state['semantic_context']['tick_context']['value']
        assert used=={r['port']:int(number(r['quantity'])) for r in tc['port_usage']}
        assert moves==[(m['event'],m['channel'],m['item'],int(number(m['quantity']))) for m in tc['movements']]
        assert passages==[(p['event'],p['batch'],p['channel']) for p in tc['internal_passages']]
        assert int(actual['summary']['completed_batches'])==total_batches
        results.append({'tick':t,'scan_rounds':sweep,'events':len(events),'completed_batches':total_batches,
                        'successful_moves':[m[0] for m in moves], 'warehouse_ore':warehouse['warehouse_0'][1],
                        'exact_event_inventory_progress_poll_and_port_match':True})
    return results


def main():
    catalog=read(SNAP/'求解器/数据/正式静态目录.json')
    docs={p.name:read(p) for p in EXAMPLES.glob('*.json')}
    shapes=[]; current={}
    for name in ('桥接器双通路.json','分流器三路轮询.json','混做粉碎机两下游.json'):
        data=docs[name]; units,ports,pcs,result=geometry(data,catalog)
        shapes.append({'file':name,**result});current[name]=(units,ports,pcs)
    write('独立几何.json',shapes)
    spec=SNAP/'求解器/规格'; names=lambda p,section:re.findall(r'^\| `([a-z_]+\.[a-z_]+)` \|',p.read_text().split(section)[1].split('## 3.')[0] if section=='## 2.' else p.read_text().split(section)[1].split('### 5.1')[0],re.M)
    registry=names(spec/'选择点参数轴.md','## 2.'); input_names=names(spec/'内核输入.md','## 5. ')
    config=read(spec/'内核配置-v1.json'); data=docs['混做粉碎机两下游.json']; values=axes(data)
    assert len(registry)==len(set(registry))==99 and set(registry)==set(input_names)==set(config['axes'])==set(values)
    projection=docs['kernel_profile_v1参数赋值.json']; by_axis={r['axis']:r for r in projection['axes']}
    axis_result=[]
    for a in registry:
        p=by_axis[a]; c=config['axes'][a]; assert p['decision']==values[a] and p['coverage_loss']==c['coverage_loss'] and p['disposition']==c['disposition']
        if c['disposition']!='由输入全称量化':assert json.dumps(values[a]['value'],sort_keys=True)==json.dumps(c['value'],sort_keys=True)
        axis_result.append({'axis':a,'disposition':c['disposition'],'value':values[a]['value'],'projection_equal':True})
    for key in ('profile_source','configuration_source','axis_source'):
        entry=projection[key];path=(EXAMPLES/entry['path']).resolve()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
    for name in ('桥接器双通路.json','分流器三路轮询.json'):
        assert set(axes(docs[name]))==set(registry)
    write('逐轴对照.json',axis_result)
    # 配方从正式散文独立提取，不从目录反造期望。
    parsed=[];kind=None
    for line in (SNAP/'《明日方舟：终末地》游戏规则.txt').read_text().splitlines()[78:]:
        if not line.strip():continue
        if '→' not in line:kind=line.strip();continue
        m=re.fullmatch(r'(.+) → (.+)，(\d+) tick',line)
        def ingredients(s):return {name:int(q) for q,name in re.findall(r'(\d+) ([^＋]+?)(?= ＋ |$)',s)}
        parsed.append((kind,ingredients(m[1]),ingredients(m[2]),int(m[3])))
    transcribed=[(r['kind'],{i:int(number(q)) for i,q in r['inputs'].items()}, {i:int(number(q)) for i,q in r['outputs'].items()},int(number(r['duration']))) for r in catalog['recipes']]
    assert sorted(parsed,key=repr)==sorted(transcribed,key=repr) and len(parsed)==18
    write('目录配方回源.json',{'recipe_count':18,'all_equal':True,'formal_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SNAP.glob('*.txt')}})
    result=replay(data,catalog,docs['混做粉碎机两下游-运行记录.json'],*current['混做粉碎机两下游.json'])
    write('独立轨迹.json',result)
    print(json.dumps({'几何':[{'file':r['file'],'units':r['units'],'area':r['occupied_cells'],'PC':len(r['physical_channels']),'BC':len(r['buffer_channels'])} for r in shapes], '轴':len(axis_result),'轨迹':result},ensure_ascii=False))


if __name__=='__main__':main()
