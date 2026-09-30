"""从 v4 物理通道独立求元件、接通序位、默认先后及轮询侧；不调用 Rust。"""
from pathlib import Path
import json
from step_inputs import q, rotate

def axis(raw,name):
    for g in ('fixed','offline_mutable','fixedness_unproven'):
        if name in raw['parameters'][g]:return raw['parameters'][g][name]['value']
    raise ValueError('missing axis '+name)

def build(raw, base):
    catalog=json.loads((Path(base)/raw['catalog']['path']).resolve().read_text())
    kinds={u['id']:u for u in catalog['units']};units={u['id']:u for u in raw['layout']['units']}
    ports={};cells={};powered=set()
    for uid,u in units.items():
        k=kinds[u['kind']];w,h=(int(k['dimensions'][z]['value']) for z in ('width','height'));r=int(u['rotation'][1:])//90;ox,oy=(int(v['value']) for v in u['origin'])
        cells[uid]={(ox+rotate(x,y,w,h,r)[0],oy+rotate(x,y,w,h,r)[1]) for x in range(w) for y in range(h)}
        for edge in k['ports']['layouts'][u['port_layout'] or 0]:
            for pos in edge['positions']:
                ports[f"{uid}:{edge['side']}:{pos['value']}"]={'unit':uid,'axis':edge.get('axis'),'role':edge['role']}
    for uid,u in units.items():
        if u['kind'] not in ('供电桩','协议核心'):continue
        # Formal grid power coverage: catalog field is inspected by the caller too.
        k=kinds[u['kind']];coverage=k.get('coverage')
        if coverage:
            width=int(coverage['width']['value']);height=int(coverage['height']['value'])
            minx=min(x for x,y in cells[uid]);maxx=max(x for x,y in cells[uid]);miny=min(y for x,y in cells[uid]);maxy=max(y for x,y in cells[uid])
            x0=(minx+maxx+1-width)//2;y0=(miny+maxy+1-height)//2
            for peer,occupied in cells.items():
                if any(x0<=x<x0+width and y0<=y<y0+height for x,y in occupied):powered.add(peer)
    channels={c['id']:c for c in raw['layout']['physical_channels']}
    events={e['id']:int(e['time']['value']['value']) for e in raw['timeline']['events']}
    times={c['channel']:events[c['event']] for c in raw['timeline']['connection_events']}
    tie={c:i for i,c in enumerate(axis(raw,'connection.tie')['channels'])}
    rank={c:i for i,c in enumerate(sorted(channels,key=lambda c:(times[c],tie[c])))}
    belts={uid for uid,u in units.items() if u['kind']=='传送带'};nxt={};prev={}
    for c in channels.values():
        a,b=(ports[c[z]]['unit'] for z in ('source_port','target_port'))
        if a in belts and b in belts:nxt[a]=b;prev[b]=a
    owner={};nodes={};seen=set()
    for first in sorted(belts-set(prev))+sorted(belts):
        if first in seen:continue
        line=[];u=first
        while u not in seen:
            line.append(u);seen.add(u)
            if u not in nxt:break
            u=nxt[u]
        ring=u==first and line[-1] in nxt;name='C|ring|'+min(line) if ring else 'C|'+line[-1]
        nodes[name]={'kind':'BeltRing' if ring else 'BeltChain','unit':None,'cells':[b+':transport:0' for b in line],'inputs':[],'outputs':[]}
        for b in line:owner[b,None]=name
    for uid,u in units.items():
        if uid in belts or kinds[u['kind']]['family']=='power':continue
        if kinds[u['kind']]['family']=='transport':
            for a in ('horizontal','vertical') if u['kind']=='桥接器' else (None,):
                name='C|'+uid+('|' +a if a else '');owner[uid,a]=name
                nodes[name]={'kind':u['kind'],'unit':uid,'cells':[f'{uid}:{a or "transport"}:0'],'inputs':[],'outputs':[]}
        else:nodes[uid]={'kind':u['kind'],'unit':uid,'cells':[],'inputs':[],'outputs':[]}
    ends={}
    for cid in sorted(channels,key=rank.get):
        c=channels[cid];ps=[ports[c[z]] for z in ('source_port','target_port')];a,b=[owner.get((p['unit'],p['axis']),p['unit']) for p in ps]
        if a==b and nodes[a]['kind'].startswith('Belt'):continue
        ends[cid]=(a,b);nodes[a]['outputs'].append(cid);nodes[b]['inputs'].append(cid)
    candidates={c:sorted({ends[ch][1] for ch in n['outputs'] if ends[ch][1].startswith('C|') and nodes[ends[ch][1]]['outputs']}) for c,n in nodes.items() if c.startswith('C|')}
    return dict(catalog=catalog,kinds=kinds,units=units,ports=ports,channels=channels,nodes=nodes,ends=ends,rank=rank,candidates=candidates,powered=powered)

def defaults(g):
    cs=g['candidates'];distance={c:1 if not ds else float('inf') for c,ds in cs.items()}
    for _ in cs:
        for c,ds in cs.items():
            if ds:distance[c]=min(distance[c],min(distance[d]+1 for d in ds))
    edges={c:min(ds,key=lambda d:(distance[d],d)) for c,ds in cs.items() if ds}
    done=set();cycles=[]
    for c in sorted(cs):
        u=c;path=[]
        while u in edges and u not in path and u not in done:path.append(u);u=edges[u]
        if u in path:cycles.append(min(path[path.index(u):]))
        done.update(path)
    nt=[u for u in g['nodes'] if not u.startswith('C|')]
    return {'schema':'step-order-v1','layer_choices':[{'component':c,'downstream':edges[c]} for c in sorted(cs) if len(cs[c])>1], 'cycle_layers':[{'component':c,'layer':q(1)} for c in sorted(cycles)], 'nontransport_order':sorted(nt,key=lambda u:(min((g['rank'][c] for c in g['nodes'][u]['outputs']),default=float('inf')),u))}

def poll_state(g):
    return {'schema':'poll-state-v1','cursors':sorted([{'side':u+':'+side,'last_success':None} for u,n in g['nodes'].items() for side in ('input','output') if len(n[side+'s'])>1 and (u.startswith('C|') or side=='input')],key=lambda c:c['side']), 'recency':[{'unit':u,'order':[]} for u,n in sorted(g['nodes'].items()) if not u.startswith('C|') and len(n['outputs'])>1]}
