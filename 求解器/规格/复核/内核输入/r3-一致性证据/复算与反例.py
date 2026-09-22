#!/usr/bin/env python3
"""一致性席独立几何、有限轨迹核验与校验器反例；仅在本目录写证据。"""
import copy
import hashlib
import io
import json
import re
import runpy
import sys
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
EXAMPLES = ROOT / '求解器/数据/样例'
SPEC = ROOT / '求解器/规格'
sys.dont_write_bytecode = True
sys.path.insert(0, str(EXAMPLES))


def load(path):
    # 原始JSON重复键也拒绝。
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, key
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def number(value):
    return Fraction(value['value'])


def plain(value):
    # 数字证据类别不同不构成物理状态差异，比较时只去这一层。
    if isinstance(value, dict):
        if set(value) == {'value', 'category'}:
            return str(number(value))
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def geometry(data, catalog):
    """用边界线段中点和整矩形占格独立算几何，不调用被审旋转/几何函数。"""
    kinds = {u['id']: u for u in catalog['units']}
    cells, ports, details = {}, {}, []
    for unit in data['layout']['units']:
        uid, kind = unit['id'], kinds[unit['kind']]
        width, height = (int(number(kind['dimensions'][k])) for k in ('width', 'height'))
        ox, oy = map(number, unit['origin'])
        turns = {'r0': 0, 'r90': 1, 'r180': 2, 'r270': 3}[unit['rotation']]
        rw, rh = (height, width) if turns % 2 else (width, height)
        occupied = {(int(ox + x), int(oy + y)) for x in range(rw) for y in range(rh)}
        assert all(0 <= x < 70 and 0 <= y < 70 for x, y in occupied)
        assert not occupied.intersection(cells)
        cells.update({cell: uid for cell in occupied})
        if unit['occupied_cells'] is not None:
            assert occupied == {tuple(map(number, row)) for row in unit['occupied_cells']}
        def transform(x, y):
            points = [(x, y), (height-y, x), (width-x, height-y), (y, width-x)]
            a, b = points[turns]
            return ox+a, oy+b
        if unit['kind'] == '桥接器':
            edges = []
            for axis, pair in [('vertical', ('south', 'north')), ('horizontal', ('west', 'east'))]:
                status = unit['bridge_axes'][axis]
                assert status['status'] == 'resolved'
                for side in pair:
                    edges.append({'side': side, 'positions': [{'value': '0'}], 'axis': axis,
                                  'role': 'input' if side == status['input_side'] else 'output'})
        else:
            edges = kind['ports']['layouts'][unit['port_layout']]
        for edge in edges:
            side = edge['side']
            for pos in edge['positions']:
                p = number(pos)
                x, y, nx, ny = {
                    'south': (p+Fraction(1,2), 0, 0, -1),
                    'north': (p+Fraction(1,2), height, 0, 1),
                    'west': (0, p+Fraction(1,2), -1, 0),
                    'east': (width, p+Fraction(1,2), 1, 0),
                }[side]
                mx, my = transform(x, y)
                ex, ey = transform(x+nx, y+ny)
                pid = f'{uid}:{side}:{p}'
                ports[pid] = {'midpoint': (mx, my), 'normal': (ex-mx, ey-my), 'role': edge['role'],
                              'axis': edge['axis'], 'unit': uid, 'family': kind['family']}
        details.append({'unit': uid, 'kind': unit['kind'], 'cells': sorted(occupied)})
    channels = []
    for source, a in ports.items():
        for target, b in ports.items():
            if a['role'] == 'output' and b['role'] == 'input' and a['midpoint'] == b['midpoint']:
                if a['normal'] == tuple(-n for n in b['normal']) and 'transport' in (a['family'], b['family']):
                    channels.append({'id': f'PC|{source}|{target}', 'source_port': source, 'target_port': target})
    buffers = []
    for unit in data['layout']['units']:
        kind = kinds[unit['kind']]
        if kind['family'] != 'manufacturing':
            continue
        uid = unit['id']
        for row in kind['inventory']:
            if row['role'] not in ('input', 'output'):
                continue
            for index in range(int(number(row['count']))):
                slot, buffer = f"{uid}:{row['role']}:{index}", f'{uid}:buffer:0'
                a, b = (slot, buffer) if row['role'] == 'input' else (buffer, slot)
                buffers.append({'id': f'BC|{a}|{b}', 'source_slot': a, 'target_slot': b})
    for field, values in [('physical_channels', channels), ('buffer_channels', buffers)]:
        assert sorted(data['layout'][field], key=lambda x:x['id']) == sorted(values, key=lambda x:x['id'])
    powered = {}
    for unit in data['layout']['units']:
        if not kinds[unit['kind']]['power_required']:
            continue
        occupied = next(d['cells'] for d in details if d['unit'] == unit['id'])
        powered[unit['id']] = []
        for pole in data['layout']['units']:
            if pole['kind'] != '供电桩':
                continue
            px, py = map(number, pole['origin'])
            if any(px-5 <= x < px+7 and py-5 <= y < py+7 for x, y in occupied):
                powered[unit['id']].append(pole['id'])
    result = {'units': len(details), 'occupied_cells': len(cells), 'physical_channels': channels,
              'buffer_channels': buffers, 'power_positive_area': powered, 'per_unit': details}
    return result, ports


def replay(data, catalog, ports, output):
    """独立重放全部扫描，检查完整库存、进度、轮询、端口预算和事件后效。"""
    units = {u['id']:u for u in data['layout']['units']}
    kinds = {u['id']:u for u in catalog['units']}
    seed = data['initial_state']['nonwarehouse']['value']
    stocks = {r['slot']: [] for r in seed['inventory']}
    wh = {r['slot']: [r['item'], int(number(r['quantity']))] for r in seed['warehouse']['slots']}
    assigns = {r['port']: r['slot'] for r in data['settings']['warehouse_assignments']}
    params = {k:v['value'] for group in ('fixed','offline_mutable','fixedness_unproven') for k,v in data['parameters'][group].items()}
    templates = params['judgment.order']['template_order']
    channels = {c['id']:c for c in data['layout']['physical_channels']}
    sides = {(s['unit'],s['side']): copy.deepcopy(s) for s in seed['logistics']['poll_memory']['value']['sides']}
    progress = {p['unit']:copy.deepcopy(p) for p in seed['progress']}
    deadlines, results, completed = {}, [], 0
    recipe_by_id = {r['id']:r for r in catalog['recipes']}
    def content(slot):
        return [[wh[slot][0],wh[slot][1],None]] if slot in wh and wh[slot][1] else stocks.get(slot,[])
    def remove(slot,count):
        if slot in wh:
            wh[slot][1] -= count
        else:
            stocks[slot][0][1] -= count
            if stocks[slot][0][1] == 0: stocks[slot] = []
    def add(slot,item,count,t):
        if stocks[slot]:
            assert stocks[slot][0][0] == item
            stocks[slot][0][1] += count
        else: stocks[slot] = [[item,count,t]]
    def route(cid,t,usage):
        c = channels[cid]; a,b = c['source_port'],c['target_port']
        su,tu = ports[a]['unit'],ports[b]['unit']
        sf,tf = ports[a]['family'],ports[b]['family']
        src = assigns[a] if a in assigns else f"{su}:{'transport' if sf=='transport' else 'output'}:0"
        if not content(src): return None
        item,count,entered = content(src)[0]
        if tf == 'transport': dst,cap=f'{tu}:transport:0',1
        else:
            candidates = [s for s in params['manufacturing.input_slot_selection']['slots'] if s.startswith(tu+':')]
            same = [s for s in candidates if stocks[s] and stocks[s][0][0] == item]
            empty = [s for s in candidates if not stocks[s]]
            if not same and not empty: return None
            dst,cap=(same+empty)[0],50
        if stocks[dst] and (stocks[dst][0][0] != item or stocks[dst][0][1] >= cap): return None
        if sf == 'transport' and t-entered < 1: return None
        if a in usage or b in usage: return None
        return src,dst,item
    def refresh(t,usage):
        for side in sides.values():
            levels = side['levels']
            if not levels: side['current_level']=None
            else:
                assert len(levels)==1
                movable=any(route(c,t,usage) for c in levels[0]['members'])
                side['current_level']=levels[0]['id'] if movable or not side['graded'] else None
    def auth(side,cid,t,usage):
        if side['current_level'] is None: return False
        level=side['levels'][0]; members=level['members']; start=members.index(level['next_channel'])
        if not side['graded']: return members[start]==cid
        found=next((members[(start+i)%len(members)] for i in range(len(members)) if route(members[(start+i)%len(members)],t,usage)),None)
        return found==cid
    def advance(side,cid):
        level=side['levels'][0]; members=level['members']
        level['next_channel']=members[(members.index(cid)+1)%len(members)]
    for t in range(4):
        usage=set(); events=[]; moves=[]; passages=[]
        for uid in list(deadlines):
            p=progress[uid]; p['remaining']={'kind':'rational','value':{'value':str(deadlines[uid]-t),'category':'候选'}}
            if deadlines[uid]==t:
                r=recipe_by_id[p['recipe']]; stocks[f'{uid}:buffer:0']=[]
                for item,q in r['outputs'].items(): add(f'{uid}:buffer:0',item,int(number(q)),t)
                p['phase']='completed'; del deadlines[uid]; completed+=1
                events.append((f'C|{t}|{uid}','manufacture_complete',uid,'success'))
        refresh(t,usage)
        def state_key(): return json.dumps([stocks,wh,progress,list(sides.values()),sorted(usage)],ensure_ascii=False,sort_keys=True)
        seen={state_key()}; sweep=0
        while True:
            for index,template in enumerate(templates):
                event=f'J|{t}|{sweep}|{index}'; op,target=template['operation'],template['target']; outcome='guard_false'
                if op=='move':
                    refresh(t,usage); c=channels[target]
                    a=sides[ports[c['source_port']]['unit'],'output']; b=sides[ports[c['target_port']]['unit'],'input']
                    ga,gb=auth(a,target,t,usage),auth(b,target,t,usage); r=route(target,t,usage)
                    if not ga and not gb: outcome='no_request'
                    elif r and ga and gb:
                        src,dst,item=r; remove(src,1);add(dst,item,1,t); usage.update((c['source_port'],c['target_port']))
                        moves.append((event,target,item,1));outcome='success'
                    else:outcome='failure'
                    if ga:advance(a,target)
                    if gb:advance(b,target)
                elif op=='manufacture':
                    uid=target;p=progress[uid];buf=f'{uid}:buffer:0';out=f'{uid}:output:0'
                    if p['phase']=='completed':
                        item,count,_=stocks[buf][0]
                        if not stocks[out] or stocks[out][0][0]==item and stocks[out][0][1]+count<=50:
                            add(out,item,count,t);stocks[buf]=[]
                            p.update(phase='idle',recipe=None,locked_recipe=None,candidate_recipes=[],remaining=None)
                            passages.append((event,f'BC|{buf}|{out}'));outcome='success'
                    if p['phase']=='idle':
                        inputs={r[0]:(slot,r[1]) for slot,rows in stocks.items() if slot.startswith(uid+':input:') for r in rows}
                        for rid in params['manufacturing.recipe_selection']['recipes']:
                            recipe=recipe_by_id[rid]
                            if recipe['kind']!=units[uid]['kind'] or not all(item in inputs and inputs[item][1]>=number(q) for item,q in recipe['inputs'].items()):continue
                            for item,q in recipe['inputs'].items():
                                src=inputs[item][0];count=int(number(q));remove(src,count);add(buf,item,count,t);passages.append((event,f'BC|{src}|{buf}'))
                            duration=int(number(recipe['duration']));deadlines[uid]=t+duration
                            p.update(phase='working',recipe=rid,locked_recipe=rid,candidate_recipes=[rid],remaining={'kind':'rational','value':{'value':str(duration),'category':'候选'}})
                            outcome='success';break
                events.append((event,op,target,outcome))
            sweep+=1;refresh(t,usage);key=state_key()
            if key in seen:break
            seen.add(key);assert sweep<20
        tick=output['trace']['ticks'][t]; observed=tick['state']
        assert [(e['event'],e['operation'],e['target'],e['outcome']) for e in tick['events']]==events
        assert sweep==tick['closure']['scan_rounds']
        for row in observed['inventory']:
            values=[[r['item'],int(number(r['quantity'])),int(number(r['entered_at']['value']))] for r in row['contents']]
            assert values==stocks[row['slot']], (t,row['slot'])
        assert plain(observed['progress'])==plain(list(progress.values()))
        assert observed['logistics']['poll_memory']['value']['sides']==list(sides.values())
        for row in observed['warehouse']['slots']:assert [row['item'],int(number(row['quantity']))]==wh[row['slot']]
        context=observed['semantic_context']['tick_context']['value']
        assert [(m['event'],m['channel'],m['item'],int(number(m['quantity']))) for m in context['movements']]==moves
        assert {r['port'] for r in context['port_usage']}==usage and all(number(r['quantity'])==1 for r in context['port_usage'])
        assert [(r['event'],r['channel']) for r in context['internal_passages']]==passages
        assert tick['summary']['completed_batches']==str(completed)
        results.append({'tick':t,'records':len(events),'scan_rounds':sweep,'completed_batches':completed,'full_state_projection_match':True})
    return results


def main():
    import check_examples as checker
    import check_golden_trace as reference
    import test_runtime_input as regressions
    catalog=load(EXAMPLES.parent/'正式静态目录.json')
    examples=[load(EXAMPLES/n) for n in checker.NAMES]
    geometry_results={}
    for name,data in zip(checker.NAMES,examples):
        result,ports=geometry(data,catalog);geometry_results[name]=result
    save('独立几何.json',geometry_results)
    data=examples[2]; output=load(reference.OUTPUT)
    save('被核运行记录.json',output)
    replay_result=replay(data,catalog,geometry(data,catalog)[1],output)
    save('独立轨迹核对.json',replay_result)
    # 原有入口只把写入重定向到复核证据目录，不碰交付文件。
    captures={}
    def intercept_write(path,text,*args,**kwargs):
        captures[str(path.resolve())]=text
        return len(text)
    log=io.StringIO()
    with patch.object(Path,'write_text',intercept_write),redirect_stdout(log):
        runpy.run_path(str(EXAMPLES/'generate_examples.py'),run_name='__main__')
        reference.main()
        regressions.main()
        runpy.run_path(str(SPEC/'内核输入修订验证-r3/build_output_schema.py'),run_name='__main__')
    (HERE/'原检查入口.log').write_text(log.getvalue())
    regenerated=[]
    for path,text in captures.items():
        same=json.loads(text)==load(path)
        regenerated.append({'path':path,'semantic_json_equal':same})
    base_checks=[checker.check(x,EXAMPLES/n) for x,n in zip(examples,checker.NAMES)]
    negatives=checker.negative_tests(examples);representations=checker.representation_tests(examples)
    save('原程序重跑.json',{'regenerated':regenerated,'examples':base_checks,'negative_tests':negatives,'representation_tests':representations})
    mutations={
        '判定上下文标为未解':lambda s:s['semantic_context']['judgment_context'].update(status='unresolved'),
        '端口预算上下文标为未解':lambda s:s['semantic_context']['tick_context'].update(status='unresolved'),
        '拿取记忆状态非法':lambda s:s['environment']['withdrawal_memory'].update(status='unknown'),
        '端口预算缺依据':lambda s:s['semantic_context']['tick_context'].pop('basis'),
        '接通历史缺依据':lambda s:s['logistics']['connection_order'].pop('basis'),
    }
    results=[]
    for name,mutate in mutations.items():
        bad=copy.deepcopy(data);mutate(bad['initial_state']['nonwarehouse']['value'])
        status=checker.check(bad,reference.INPUT)['status']; ticks=reference.run(bad)
        results.append({'case':name,'status':status,'runtime_ticks':len(ticks)})
        if name=='判定上下文标为未解':save('反例-未解判定上下文.json',bad)
    empty={'slot':'empty_extra','item':None,'quantity':{'value':'0','category':'候选'},'empty_identity':{'status':'specified','value':None,'basis':['候选：尚未使用的仓库空格']}}
    bad=copy.deepcopy(data);bad['initial_state']['warehouse']['slots'].append(empty)
    bad['initial_state']['nonwarehouse']['value']['warehouse']=copy.deepcopy(bad['initial_state']['warehouse'])
    next(a for a in bad['settings']['warehouse_assignments'] if a['port'].startswith('ore_source:'))['slot']='empty_extra'
    status=checker.check(bad,reference.INPUT)['status'];actual=reference.run(bad)
    save('反例-空仓库源与错误派生状态.json',bad)
    results.append({'case':'空仓库源仍有current_level且空格仲裁表为空','status':status,'completed_batches':[t['summary']['completed_batches'] for t in actual]})
    corrected=copy.deepcopy(bad)
    state=corrected['initial_state']['nonwarehouse']['value']
    for side in state['logistics']['poll_memory']['value']['sides']:
        if (side['unit'],side['side']) in {('ore_source','output'),('feed_belt','input')}:
            side['current_level']=None
    state['semantic_context']['arbitration']['warehouse_empty_slot_order']=['empty_extra']
    try:
        checker.check(corrected,reference.INPUT)
        correction_result={'status':'接受'}
    except checker.CheckError as error:
        correction_result={'status':'拒绝','reason':str(error)}
    save('正确空源派生状态被拒绝.json',correction_result)
    bad_output=copy.deepcopy(output)
    # 原记录第一个格是粉碎机存货格，上限50；999件和摘要12345均与重算矛盾。
    bad_output['trace']['ticks'][2]['state']['inventory'][0]['contents']=[{'item':'源矿','quantity':{'value':'999','category':'算术推论'},'entered_at':{'kind':'rational','value':{'value':'2','category':'候选'}}}]
    bad_output['trace']['ticks'][2]['summary']['warehouse_ore']='12345'
    save('反例-错误运行记录.json',bad_output)
    original_load=checker.load_json
    def altered_read(path):
        return bad_output if Path(path).resolve()==reference.OUTPUT.resolve() else original_load(path)
    log=io.StringIO()
    with patch.object(checker,'load_json',altered_read),patch.object(Path,'write_text',intercept_write),redirect_stdout(log):
        regressions.main()
    (HERE/'错误运行记录仍通过.log').write_text(log.getvalue())
    results.append({'case':'999件超容量库存和不一致摘要','regression_status':'通过','tests':17})
    save('反例检查结果.json',results)
    print(json.dumps({'geometry':{n:{k:v for k,v in r.items() if k in ('units','occupied_cells')} for n,r in geometry_results.items()},'independent_trace':replay_result,'counterexamples':results},ensure_ascii=False))


if __name__=='__main__':
    main()
