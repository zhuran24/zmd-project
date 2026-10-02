#!/usr/bin/env python3
"""把已经静态重建核对的布局转换成搜索器的机位和路径初值。"""
import json,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];data=json.loads(Path(sys.argv[1]).read_text());l=data['layout'];c=json.loads((B/'逻辑接法.json').read_text());idx={e['id']:i for i,e in enumerate(c['logical_feeds'])};units={}
for group,t in [('machines',None),('core',3),('warehouse_outlets',4),('power_poles',5)]:
    for u in ([l[group]] if group=='core' else l[group]):
        typ={'小':0,'中':1,'大':2}[u['kind']] if t is None else t
        units[u['id']]=dict(id=u['id'],type=typ,x=u['x0'],y=u['y0'],w=u['x1']-u['x0']+1,h=u['y1']-u['y0']+1,d=u.get('Din',u.get('Dout',0)))
order=[m['id'] for m in c['machines']]+['CORE']+[u['id'] for u in c['warehouse_outlets']]+[u['id'] for u in l['power_poles']]
trans={u['id']:u for u in l['transport']};channels={p['id']:p for p in data['design']['physical_channels']};paths=[]
for feed in data['design']['logical_feeds']:
    pcs=[channels[k] for k in feed['path']];cells=[]
    for a,z in zip(pcs,pcs[1:]):
        assert a['to']['unit']==z['from']['unit'];u=trans[a['to']['unit']]
        cells.append([u['x'],u['y'],a['to']['side'],z['from']['side']])
    paths.append(dict(r=idx[feed['id']],source=[*cells[0][:2],feed['from']['side'],feed['from']['offset']],target=[*cells[-1][:2],feed['to']['side'],feed['to']['offset']],cells=cells))
poles=l['power_poles'];unpowered=[u['id'] for u in l['machines'] if not any(u['x1']>=p['x0']-5 and u['x0']<=p['x0']+6 and u['y1']>=p['y0']-5 and u['y0']<=p['y0']+6 for p in poles)]
raw=dict(units=[units[u] for u in order],paths=paths,overlap=0,power_distance=0 if not unpowered else len(unpowered),source_layout=str(Path(sys.argv[1]).resolve()))
Path(sys.argv[2]).write_text(json.dumps(raw,ensure_ascii=False,indent=1));print(len(paths),unpowered)
