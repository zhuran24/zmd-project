#!/usr/bin/env python3
"""Expand polyline solver coordinates into explicit units and physical channels."""
import argparse,json
from pathlib import Path
from collections import defaultdict
from static_check import BASE,digest,body,rectangle_rows,portjson,audit,read
D=((1,0),(0,1),(-1,0),(0,-1))
def direction(a,b):return D.index((b[0]-a[0],b[1]-a[1]))
def grid_as_paths(raw):
    """Decompose a grid-model incumbent; discard only separate unused cycles."""
    ts={(t['x'],t['y']):t for t in raw['transport']};paths=[];used=set();W=raw['W']
    for label,e in enumerate(raw['routes'],1):
        start,ins=divmod(e['start_index'],4);end,outs=divmod(e['end_index'],4);first=(start%W,start//W);last=(end%W,end//W);at=first;enter=ins;cells=[]
        while True:
            if at in cells or at not in ts:raise ValueError('逐格解没有有限的完整进路')
            t=ts[at];axis=enter%2 if t['type']=='bridge' else -1;tag=t['H'] if axis in (-1,0) else t['V']
            if tag!=label:raise ValueError('标签不连续')
            options=[s for s in t['out'] if t['type']=='belt' or s%2==axis]
            if len(options)!=1:raise ValueError('出口不唯一')
            leave=options[0];cells.append(at);used.add((at,axis))
            if at==last and leave==outs:break
            dx,dy=D[leave];at=(at[0]+dx,at[1]+dy);enter=(leave+2)%4
        paths.append({**{k:e[k] for k in ('id','source','target','item','rate')},'start':[*first,ins],'end':[*last,outs],'cells':[list(c) for c in cells]})
    return {**raw,'paths':paths,'grid_transport_slots_discarded':sum(2 if t['type']=='bridge' else 1 for t in ts.values())-len(used)}
def make(raw,contract,diagnostic=False):
    if 'paths' not in raw and raw.get('schema')=='joint-cp-run-v1':raw=grid_as_paths(raw)
    if raw['status'] not in ('FEASIBLE','OPTIMAL') or 'paths' not in raw:raise ValueError('没有坐标与完整路径')
    spec={u['id']:u for u in contract['machines']};outlets={u['id']:u for u in contract['warehouse_outlets']};poses=raw['placements'];lay=dict(W=raw['W'],H=raw['H'],machines=[],warehouse_outlets=[],core=None,power_poles=[],storage_boxes=[],transport=[],vin=[],vout=[])
    for uid,p in poses.items():
        u={k:p[k] for k in ('x0','y0','x1','y1')};u['id']=uid
        if p['kind']=='machine':
            sp=spec[uid];u.update(model=sp['model'],kind=sp['kind'],Din=p['Din'],recipe_ids=[sp['recipe_id']],settings={'manufacture_on':True});lay['machines'].append(u)
        elif p['kind']=='outlet':u.update(Dout=p['Din'],item=outlets[uid]['item']);lay['warehouse_outlets'].append(u)
        elif p['kind']=='core':
            u.update(Din=p['Din'],output_items=[dict(side=s,offset=z,item='源矿') for s in ((p['Din']+1)%4,(p['Din']+3)%4) for z in (1,4,7)]);lay['core']=u
        else:u['orientation']=0;lay['power_poles'].append(u)
    usage=defaultdict(list);route_specs=[]
    for i,path in enumerate(raw['paths']):
        cells=list(map(tuple,path['cells']));seq=[]
        for j,c in enumerate(cells):
            si=path['start'][2] if j==0 else direction(c,cells[j-1]);so=path['end'][2] if j==len(cells)-1 else direction(c,cells[j+1]);usage[c].append((i,si,so));seq.append((c,si,so))
        route_specs.append(seq)
    tids={c:f'T{c[0]}_{c[1]}' for c in usage};bridges=set()
    for (x,y),us in sorted(usage.items()):
        u=dict(id=tids[x,y],x=x,y=y)
        if len(us)==1:
            _,si,so=us[0]
            if si==so:raise ValueError('折返带')
            u.update(type='belt',in_side=si,out_side=so)
        elif len(us)==2:
            if us[0][0]==us[1][0] or any((si+2)%4!=so for _,si,so in us) or us[0][1]%2==us[1][1]%2:raise ValueError('非法交叉')
            u.update(type='bridge',H_in=next(si for _,si,so in us if si%2==0),V_in=next(si for _,si,so in us if si%2==1));bridges.add(u['id'])
        else:raise ValueError('格子超用')
        lay['transport'].append(u)
    def terminal(uid,pt):
        x,y,transportside=pt;side=(transportside+2)%4;p=poses[uid];off=y-p['y0'] if side%2==0 else x-p['x0'];return uid,side,off
    channels=[];feeds=[]
    for path,seq in zip(raw['paths'],route_specs):
        source=terminal(path['source'],path['start']);dest=terminal(path['target'],path['end']);edges=[];prev=source
        for c,si,so in seq:
            target=(tids[c],si,0);edges.append((prev,target));prev=(tids[c],so,0)
        edges.append((prev,dest));ids=[]
        for a,b in edges:
            cid=f'PC{len(channels):05}';ids.append(cid);channels.append(dict(id=cid,**{'from':portjson(a),'to':portjson(b)},allowed_items=[path['item']]))
        feeds.append(dict(id=path['id'],**{'from':portjson(source),'to':portjson(dest)},item=path['item'],rate=path['rate'],path=ids))
    reverse=[]
    for e in list(channels):
        if e['from']['unit'] in bridges and e['to']['unit'] in bridges:
            cid=f'PC{len(channels):05}';channels.append(dict(id=cid,**{'from':e['to'],'to':e['from']},allowed_items=e['allowed_items']));reverse.append(cid)
    occ={(u['x'],u['y']) for u in lay['transport']}
    for g in ('machines','warehouse_outlets','power_poles'):
        for u in lay[g]:occ.update(body(u))
    if lay['core']:occ.update(body(lay['core']))
    rr=rectangle_rows(occ,lay['W'],lay['H']);rr={k:rr[k] for k in ('x0','y0','x1','y1')} if rr else None
    schema='full-factory-static-s2-bridges-v2' if reverse or diagnostic else 'full-factory-static-v1'
    data=dict(schema=schema,candidate_id='s2-third-A',source_fingerprints={k:digest(BASE/'依据快照'/n) for k,n in [('rules','《明日方舟：终末地》游戏规则.txt'),('task','求解任务.txt'),('constraints','求解约束.txt')]},targets={'高容谷地电池':'3/5','精选荞愈胶囊':'11/20'},layout=lay,empty_rectangle=rr,design={'class':'s2_isolated_paths' if reverse or diagnostic else 'p2p','physical_channels':channels,'logical_feeds':feeds,'restrictions':[]},flow_witness=None)
    if schema.endswith('v2'):
        data['temporary_rules_sha256']=digest(BASE/'依据快照/临时规则.md');data['design']['bridge_reverse_channels']=reverse
    else:data['provenance']=[{'path':'求解器/候选约束轮次/第107-109轮/临时规则.md','sha256':digest(BASE/'依据快照/临时规则.md')}]
    if diagnostic:data['diagnostic_only']=True
    return data

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--out',required=True);ap.add_argument('--local',action='store_true');ap.add_argument('--partial',action='store_true');a=ap.parse_args();raw=read(a.input);c=read(BASE/'逻辑接法.json')
    if a.local:
        keep=set(raw['placements']);c['machines']=[u for u in c['machines'] if u['id'] in keep];c['warehouse_outlets']=[];c['logical_feeds']=[e for e in c['logical_feeds'] if e['source'] in keep and e['target'] in keep]
    data=make(raw,c,a.local or a.partial);out=Path(a.out).resolve()
    if not out.is_relative_to(BASE):raise ValueError('输出越界')
    out.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n');result=audit(data,c,not a.local);result['candidate_sha256']=digest(out);out.with_suffix('.check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['static_pass','local_checks_pass','statistics']},ensure_ascii=False))
