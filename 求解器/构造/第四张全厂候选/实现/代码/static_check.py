#!/usr/bin/env python3
"""Independent grid/port audit, including actual bidirectional bridge ports.

Only this program's full-mode all-pass result is static_pass. Solver status and
local diagnostic examples cannot set that flag. It never certifies dynamics.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import argparse,json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction as Q
BASE=Path(__file__).resolve().parents[1]
D=((1,0),(0,1),(-1,0),(0,-1))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    def unique(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('重复JSON键 '+k)
            d[k]=v
        return d
    return json.loads(Path(p).read_text(),object_pairs_hook=unique)
def portref(d):return d['unit'],d['side'],d['offset']
def portjson(p):return dict(zip(('unit','side','offset'),p))
def body(u):return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
def sidecell(u,s,o):return [(u['x1'],u['y0']+o),(u['x0']+o,u['y1']),(u['x0'],u['y0']+o),(u['x0']+o,u['y0'])][s]

def rectangle_rows(occ,W=70,H=70,minimum=6):
    score=(0,0);result=None
    for a in range(H):
        bad=[False]*W
        for b in range(a,H):
            for x in range(W):bad[x]|=(x,b) in occ
            hh=b-a+1
            if hh<minimum:continue
            start=0
            for end in range(W+1):
                if end==W or bad[end]:
                    ww=end-start;ss=(ww*hh,min(ww,hh))
                    if ww>=minimum and ss>score:score=ss;result=dict(x0=start,y0=a,x1=end-1,y1=b,area=ss[0],short_side=ss[1])
                    start=end+1
    return result

def rectangle_columns_bitsets(occ,W=70,H=70,minimum=6):
    masks=[sum(1<<y for y in range(H) if (x,y) not in occ) for x in range(W)];score=(0,0);answer=None
    for left in range(W):
        free=(1<<H)-1
        for right in range(left,W):
            free &= masks[right];width=right-left+1
            if width<minimum:continue
            y=0
            while y<H:
                if not(free>>y)&1:y+=1;continue
                start=y
                while y<H and (free>>y)&1:y+=1
                height=y-start
                if height>=minimum and (width*height,min(width,height))>score:
                    score=(width*height,min(width,height));answer=dict(x0=left,x1=right,y0=start,y1=y-1,area=score[0],short_side=score[1])
    return answer

def expected_edges():
    """Second transcription of S2 section 2, independent of the stored contract."""
    edges=[]
    def add(a,b,i,n=1):edges.extend([(a,b,i)]*n)
    for n in range(1,35):add(f'WFE{n}',f'RF{n}','蓝铁矿');add(f'RF{n}',f'KF{n}','蓝铁块');add(f'KF{n}',f'B{(n+1)//2}','蓝铁粉末')
    for n in range(1,19):add('CORE' if n<=6 else f'WO{n}',f'KO{n}','源矿');add(f'KO{n}',f'O{(n+1)//2}','源石粉末')
    for typ,count,plant in [('S',13,'砂叶'),('Q',6,'荞花')]:
        for n in range(1,count+1):
            add(f'{typ}C{n}',f'{typ}A{n}',plant+'种子');add(f'{typ}C{n}',f'{typ}B{n}',plant+'种子');add(f'{typ}A{n}',f'{typ}C{n}',plant);add(f'{typ}B{n}',f'S{n}' if typ=='S' else f'QK{n}',plant)
    table=['B1 B2 O1','O2 O3','B3 B4 O4','O5 O6','B5 B6 O7','O8 O9','B7 B8 B9','B10 Q1 Q2','B11 B12 B13','B14 Q3 Q4','B15 B16 Q5','B17','Q6']
    for n,row in enumerate(table,1):
        for dest in row.split():add(f'S{n}',dest,'砂叶粉末')
    for n in range(1,7):add(f'QK{n}',f'Q{n}','荞花粉末',1 if n==6 else 2)
    for n in range(1,18):
        add(f'B{n}',f'R{n}','致密蓝铁粉末');add(f'R{n}',f'P{n}' if n<=6 else f'H{min(6,(n-5)//2)}','钢块')
    for n in range(1,4):
        for j in [2*n-1,2*n]:add(f'P{j}',f'E{n}','钢制零件')
        for j in [3*n-2,3*n-1,3*n]:add(f'O{j}',f'E{n}','致密源石粉末')
        add(f'E{n}','CORE','高容谷地电池')
    for n,indices in [(1,[1,2]),(2,[3,4]),(3,[5]),(4,[6])]:
        for j in indices:add(f'H{j}',f'F{n}','钢质瓶');add(f'Q{j}',f'F{n}','细磨荞花粉末')
        add(f'F{n}','CORE','精选荞愈胶囊')
    return Counter(edges)

def audit(data,contract=None,full=True):
    contract=contract or read(BASE/'逻辑接法.json');spec={u['id']:u for u in contract['machines']};outlets={u['id']:u for u in contract['warehouse_outlets']};l=data['layout'];W,H=l['W'],l['H'];checks={};errors=[]
    def test(k,ok,detail=None):
        v=checks.setdefault(k,dict(status='PASS',instances=0,failures=[]));v['instances']+=1
        if not ok:v['status']='FAIL';v['failures'].append(detail);errors.append(k)
    test('schema',data.get('schema') in ('full-factory-static-v1','full-factory-static-s2-bridges-v2'),data.get('schema'))
    if full:
        test('complete_artifact',not data.get('diagnostic_only',False))
        test('base_size',W==H==70,(W,H));test('snapshots',data.get('source_fingerprints')=={k:digest(BASE/'依据快照'/n) for k,n in [('rules','《明日方舟：终末地》游戏规则.txt'),('task','求解任务.txt'),('constraints','求解约束.txt')]})
        test('temporary_rules',data.get('temporary_rules_sha256')==digest(BASE/'依据快照/临时规则.md') if data['schema'].endswith('v2') else any(p.get('sha256')==digest(BASE/'依据快照/临时规则.md') for p in data.get('provenance',[])))
        test('s2_transcription',expected_edges()==Counter((e['source'],e['target'],e['item']) for e in contract['logical_feeds']))
        test('manufacturing_inventory',Counter(u['id'] for u in l['machines'])==Counter(spec.keys()))
        test('warehouse_inventory',Counter(u['id'] for u in l['warehouse_outlets'])==Counter(outlets.keys()))
        test('no_virtual_interfaces',l.get('vin')==l.get('vout')==[])
        test('allowed_units',l.get('storage_boxes')==[])
    units={};kind={};occ={};ports={};lookup={};trans={u['id']:u for u in l['transport']}
    def insert(u,k):
        uid=u['id'];test('unique_ids',uid not in units,uid);units[uid]=u;kind[uid]=k
        cs=[(u['x'],u['y'])] if k in ('belt','bridge') else body(u)
        for c in cs:
            test('bounds',all(type(v)==int for v in c) and 0<=c[0]<W and 0<=c[1]<H,(uid,c));test('overlap',c not in occ,(uid,c,occ.get(c)));occ[c]=uid
    def addport(u,s,off,mode):
        c=(u['x'],u['y']) if u['id'] in trans else sidecell(u,s,off);p=(u['id'],s,off);ports[p]=(c,mode);lookup[(c,s)]=(p,mode)
    def edge(u,s,mode,offsets=None):
        for off in (range(u['y1']-u['y0']+1 if s%2==0 else u['x1']-u['x0']+1) if offsets is None else offsets):addport(u,s,off,mode)
    for u in l['machines']:
        insert(u,'machine');d=u['Din'];sp=spec.get(u['id']);dims=(3,3) if u['kind']=='小' else (5,5) if u['kind']=='中' else ((4,6) if d%2==0 else (6,4))
        test('machine_dimensions',(u['x1']-u['x0']+1,u['y1']-u['y0']+1)==dims,(u['id'],dims));test('machine_contract',sp is not None and u['model']==sp['model'] and u['kind']==sp['kind'] and u['recipe_ids']==[sp['recipe_id']] and u['settings']=={'manufacture_on':True},u['id']);edge(u,d,1);edge(u,(d+2)%4,2)
    for u in l.get('warehouse_outlets',[]):
        insert(u,'outlet');d=u['Dout'];test('outlet_boundary',((d==0 and u['x0']==u['x1']==0 and u['y1']==u['y0']+2) or (d==1 and u['y0']==u['y1']==0 and u['x1']==u['x0']+2)),u['id']);test('outlet_item',u['id'] in outlets and u['item']==outlets[u['id']]['item'],u['id']);edge(u,d,2,[1])
    core=l.get('core')
    if core:
        insert(core,'core');test('core',core['id']=='CORE' and core['x1']==core['x0']+8 and core['y1']==core['y0']+8);d=core['Din']
        for s in (d,(d+2)%4):edge(core,s,1,range(1,8))
        for s in ((d+1)%4,(d+3)%4):edge(core,s,2,[1,4,7])
        test('core_six_sources',Counter((q['side'],q['offset'],q['item']) for q in core['output_items'])==Counter((s,z,'源矿') for s in ((d+1)%4,(d+3)%4) for z in (1,4,7)))
    elif full:test('core',False,'缺少协议核心')
    for u in l.get('power_poles',[]):
        insert(u,'pole');test('pole_dimensions',u['x1']==u['x0']+1 and u['y1']==u['y0']+1,u['id'])
    for u in l['transport']:
        test('allowed_units',u['type'] in ('belt','bridge'),u['id'])
        if u['type'] not in ('belt','bridge'):continue
        insert(u,u['type'])
        if u['type']=='belt':
            test('belt_ports',u['in_side'] in range(4) and u['out_side'] in range(4) and u['in_side']!=u['out_side'],u['id']);addport(u,u['in_side'],0,1);addport(u,u['out_side'],0,2)
        else:
            for s in range(4):addport(u,s,0,3)
    if full:
        for u in l['machines']:
            cov=[p['id'] for p in l['power_poles'] if u['x1']>=p['x0']-5 and u['x0']<=p['x0']+6 and u['y1']>=p['y0']-5 and u['y0']<=p['y0']+6]
            test('power',bool(cov),u['id'])
    actual=set()
    for p,(c,mode) in ports.items():
        if not mode&2:continue
        dx,dy=D[p[1]];other=lookup.get(((c[0]+dx,c[1]+dy),(p[1]+2)%4))
        if other and other[1]&1 and (p[0] in trans or other[0][0] in trans):actual.add((p,other[0]))
    claimed=data.get('design',{}).get('physical_channels',[]);decl=[(portref(e['from']),portref(e['to'])) for e in claimed]
    test('unique_channel_ids',len({e['id'] for e in claimed})==len(claimed))
    test('all_automatic_channels',set(decl)==actual and len(decl)==len(actual),{'unlisted':list(actual-set(decl))[:20],'absent':list(set(decl)-actual)[:20]})
    outgoing=defaultdict(list)
    for e in actual:outgoing[e[0]].append(e)
    paths=[];used=Counter();slot_use={};reverse=set()
    for first in sorted(e for e in actual if e[0][0] not in trans):
        ed=first;walk=[];es=[];seen=set();terminal=None
        for _ in range(W*H+1):
            es.append(ed);uid=ed[1][0]
            if uid not in trans:terminal=ed[1];break
            t=trans[uid];axis=ed[1][1]%2 if t['type']=='bridge' else -1;slot=(uid,axis)
            if slot in seen:break
            seen.add(slot);walk.append(uid);side=(ed[1][1]+2)%4 if t['type']=='bridge' else t['out_side'];cand=outgoing[(uid,side,0)]
            if len(cand)!=1:break
            ed=cand[0]
        valid=terminal is not None and bool(walk) and len(set(walk))==len(walk)
        test('directed_routes',valid,{'from':first[0],'to':terminal,'length':len(walk)})
        if not valid:continue
        uid=first[0][0]
        item=outlets[uid]['item'] if uid in outlets else '源矿' if uid=='CORE' else next(iter(spec[uid]['outputs']))
        rr=dict(source=uid,target=terminal[0],item=item,from_port=first[0],to_port=terminal,cells=[(trans[z]['x'],trans[z]['y']) for z in walk],units=walk,edges=es)
        pi=len(paths);paths.append(rr);used.update(es)
        for slot in seen:test('slot_exclusivity',slot not in slot_use,slot);slot_use[slot]=pi
    expected=Counter((e['source'],e['target'],e['item']) for e in contract['logical_feeds']);observed=Counter((p['source'],p['target'],p['item']) for p in paths)
    test('s2_routes',expected==observed,{'missing':list((expected-observed).elements()),'extra':list((observed-expected).elements())})
    for a,b in actual:
        if a[0] in trans and b[0] in trans and trans[a[0]]['type']==trans[b[0]]['type']=='bridge' and (b,a) in used:reverse.add((a,b))
    test('no_extra_channels',set(used)|reverse==actual and all(n==1 for n in used.values()),{'uncovered':list(actual-set(used)-reverse)[:20]})
    declared_by_edge={pair:e for pair,e in zip(decl,claimed)};by_ports={(p['from_port'],p['to_port']):p for p in paths};expected_id={e['id']:e for e in contract['logical_feeds']};logical=data.get('design',{}).get('logical_feeds',[])
    test('logical_feed_ids',len({e['id'] for e in logical})==len(logical))
    covered_routes=[]
    for e in logical:
        key=(portref(e['from']),portref(e['to']));route=by_ports.get(key);want=expected_id.get(e['id'])
        ok=route is not None and want is not None
        if ok:
            ok=(route['source'],route['target'],route['item'],e['rate'])==(want['source'],want['target'],want['item'],want['rate']) and e['item']==route['item'] and e['path']==[declared_by_edge[q]['id'] for q in route['edges'] if q in declared_by_edge]
            covered_routes.append(key)
        test('logical_feed_claims',ok,e['id'])
    test('logical_feed_coverage',Counter(covered_routes)==Counter(by_ports.keys()))
    for route in paths:
        for edge in route['edges']:
            test('channel_item_labels',edge in declared_by_edge and declared_by_edge[edge]['allowed_items']==[route['item']],edge)
            if edge[::-1] in reverse:test('channel_item_labels',edge[::-1] in declared_by_edge and declared_by_edge[edge[::-1]]['allowed_items']==[route['item']],edge[::-1])
    if data['schema'].endswith('v2'):
        test('declared_bridge_reverse_channels',set(data['design'].get('bridge_reverse_channels',[]))=={declared_by_edge[e]['id'] for e in reverse if e in declared_by_edge})
    bridgeinfo=[];adjacent=[]
    for uid,t in trans.items():
        if t['type']=='belt':test('no_unused_transport',(uid,-1) in slot_use,uid);continue
        axes=[]
        for ax,key in [(0,'H_in'),(1,'V_in')]:
            pi=slot_use.get((uid,ax));incident=[e for e in actual if (e[0][0]==uid and e[0][1]%2==ax) or (e[1][0]==uid and e[1][1]%2==ax)]
            test('bridge_axis_coverage',pi is not None or not incident,(uid,key))
            if pi is not None:
                incoming=[e for e in paths[pi]['edges'] if e[1][0]==uid];test('bridge_direction',len(incoming)==1 and t.get(key)==incoming[0][1][1],(uid,key));p=paths[pi];axes.append(dict(axis=key,route=[p['source'],p['target'],p['item']]))
            else:test('bridge_direction',t.get(key) is None,(uid,key))
        test('bridge_distinct_routes',len({slot_use.get((uid,ax)) for ax in (0,1)}-{None})==len(axes),uid)
        test('no_unused_transport',bool(axes),uid)
        bridgeinfo.append(dict(id=uid,x=t['x'],y=t['y'],axes=axes))
        for dx,dy in ((1,0),(0,1)):
            other=occ.get((t['x']+dx,t['y']+dy))
            if other in trans and trans[other]['type']=='bridge':adjacent.append([uid,other])
    if data['schema']=='full-factory-static-v1':test('v1_no_adjacent_bridges',not adjacent,adjacent[:20])
    eq=[]
    for pair in contract.get('equal_length',[]):eq.append([len(p['cells']) for p in paths if [p['source'],p['target']]==pair])
    if full:test('H6_Q6_equal_length',len(eq)==2 and len(eq[0])==len(eq[1])==1 and eq[0]==eq[1],eq)
    # Exact design flow, recomputed only when all expected routes exist.
    if expected==observed and full:
        rates=defaultdict(list)
        for e in contract['logical_feeds']:rates[e['source'],e['target'],e['item']].append(Q(e['rate']))
        ingress=defaultdict(lambda:defaultdict(Q));egress=defaultdict(lambda:defaultdict(Q))
        for p in paths:
            q=rates[p['source'],p['target'],p['item']].pop();ingress[p['target']][p['item']]+=q;egress[p['source']][p['item']]+=q;test('route_capacity',0<q<=1,p['source'])
        for uid,sp in spec.items():
            r=Q(sp['batch_rate']);test('exact_balance',dict(ingress[uid])=={k:r*v for k,v in sp['inputs'].items()} and dict(egress[uid])=={k:r*v for k,v in sp['outputs'].items()},uid);test('manufacturing_rate',r*sp['duration']<=1,uid)
        if full:test('products',dict(ingress['CORE'])=={'高容谷地电池':Q(3,5),'精选荞愈胶囊':Q(11,20)})
    elif full:checks['exact_balance']={'status':'NOT_RUN_MISSING_ROUTES'}
    r1=rectangle_rows(occ,W,H);r2=rectangle_columns_bitsets(occ,W,H);test('independent_rectangle',(None if r1 is None else (r1['area'],r1['short_side']))==(None if r2 is None else (r2['area'],r2['short_side'])))
    if full:
        rr=data.get('empty_rectangle');clean=bool(rr) and all((x,y) not in occ for x in range(rr['x0'],rr['x1']+1) for y in range(rr['y0'],rr['y1']+1));score=((rr['x1']-rr['x0']+1)*(rr['y1']-rr['y0']+1),min(rr['x1']-rr['x0']+1,rr['y1']-rr['y0']+1)) if rr else None
        test('maximum_empty_rectangle',clean and r1 is not None and score==(r1['area'],r1['short_side']) and score[1]>=6,{'claimed':rr,'computed':r1})
    return dict(static_pass=full and not errors and all(c['status']=='PASS' for c in checks.values()),local_checks_pass=not errors,full_mode=full,runtime_certified=False,checks=checks,statistics=dict(machines=len(l['machines']),routes=len(paths),physical_channels=len(actual),transport_units=len(trans),transport_slots=sum(len(p['cells']) for p in paths),bridges=len(bridgeinfo),adjacent_bridge_pairs=len(adjacent),reverse_bridge_channels=len(reverse),occupied_cells=len(occ)),maximum_empty_rectangle=r1,independent_maximum=r2,bridges=bridgeinfo,adjacent_bridges=adjacent,route_lengths=[dict(source=p['source'],target=p['target'],item=p['item'],length=len(p['cells'])) for p in paths])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('candidate',nargs='?');ap.add_argument('--out',default=str(BASE/'证据/静态检查结果.json'));a=ap.parse_args()
    if not a.candidate:result=dict(static_pass=False,runtime_certified=False,status='NOT_RUN_NO_LAYOUT',checks={k:{'status':'NOT_RUN_NO_LAYOUT'} for k in ['bounds','overlap','all_automatic_channels','s2_routes','power','H6_Q6_equal_length','maximum_empty_rectangle','exact_balance']})
    else:
        try:result=audit(read(a.candidate));result['candidate_sha256']=digest(a.candidate)
        except Exception as e:result=dict(static_pass=False,runtime_certified=False,status='REJECTED',error=repr(e))
    out=Path(a.out).resolve()
    if not out.is_relative_to(BASE):raise ValueError('输出越界')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result.get(k) for k in ['static_pass','status','statistics']},ensure_ascii=False));raise SystemExit(0 if result['static_pass'] else 1)
