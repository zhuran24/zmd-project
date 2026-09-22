#!/usr/bin/env python3
"""Read-only audit of submitted inputs; writes only this seat's evidence directory."""
import ast
import contextlib
import hashlib
import io
import itertools
import json
import traceback
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
AUTHOR = BASE / '证据/密排'
J = json.loads((BASE / '密排布局.json').read_text())
UNITS = {u['id']: u for u in J['units']}
assert len(UNITS) == len(J['units'])
DIR = dict(N=(0, 1), E=(1, 0), S=(0, -1), W=(-1, 0))
OPP = dict(N='S', S='N', E='W', W='E')
TR = {'传送带', '桥接器', '物品准入口', '分流器', '汇流器'}
SMALL = {'粉碎机', '精炼炉', '配件机', '塑形机'}
MEDIUM = {'种植机', '采种机'}
LARGE = {'研磨机', '封装机', '灌装机'}
SIZES = {**{k: (3, 3) for k in SMALL}, **{k: (5, 5) for k in MEDIUM},
         **{k: (6, 4) for k in LARGE}, **{k: (1, 1) for k in TR},
         '供电桩': (2, 2), '协议储存箱': (3, 3), '协议核心': (9, 9), '仓库取货口': (3, 1)}
checks = []
def check(name, condition, details=None):
    checks.append(dict(name=name, passed=bool(condition), details=details))
    if not condition:
        raise AssertionError((name, details))
def write(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

# Endpoints are exact lattice edge segments. Matching never uses declared routes.
occ = {}
ports = []
for uid, u in UNITS.items():
    x, y = u['xy']; w, h = u['size']; kind = u['kind']
    check('size:' + uid, (w, h) in {SIZES[kind], tuple(reversed(SIZES[kind]))})
    for xx in range(x, x+w):
        for yy in range(y, y+h):
            assert 0 <= xx < 70 and 0 <= yy < 70
            assert (xx, yy) not in occ
            occ[xx, yy] = uid
    if kind == '供电桩':
        continue
    roles = {}
    if kind == '桥接器':
        assert len(u['axes']) == 2
        for a in u['axes']:
            assert OPP[a['input']] == a['output']
            assert a['axis'] == ('horizontal' if a['input'] in 'EW' else 'vertical')
            for s, r in [(a['input'], 'in'), (a['output'], 'out')]:
                assert s not in roles
                roles[s] = (r, a['axis'], None)
        assert set(roles) == set(DIR)
    elif kind == '协议核心':
        # This submitted core is N/S input, E/W output; verify against all saved ports below.
        roles = {s: ('in', 'warehouse', range(1, 8)) for s in 'NS'}
        roles.update({s: ('out', '蓝铁矿', [1, 4, 7]) for s in 'EW'})
    elif kind == '仓库取货口':
        assert (w == 1 and x == 0) or (h == 1 and y == 0)
        roles['E' if w == 1 else 'N'] = ('out', u['warehouse_item'], [1])
    else:
        a, b = u['orientation']['input'], u['orientation']['output']
        assert a in DIR and b in DIR and a != b
        if kind != '传送带':
            assert OPP[a] == b
        if kind in LARGE:
            assert (a in 'NS' and w == 6) or (a in 'EW' and h == 6)
        assert kind not in {'分流器', '汇流器', '物品准入口'}  # absent in this submitted candidate
        roles = {a: ('in', 'in', None), b: ('out', 'out', None)}
    for side, (role, slot, selected) in roles.items():
        span = w if side in 'NS' else h
        for t in (range(span) if selected is None else selected):
            xx, yy = (x+t, y if side == 'S' else y+h-1) if side in 'NS' else (x if side == 'W' else x+w-1, y+t)
            ends = {'S': ((xx, yy), (xx+1, yy)), 'N': ((xx, yy+1), (xx+1, yy+1)),
                    'W': ((xx, yy), (xx, yy+1)), 'E': ((xx+1, yy), (xx+1, yy+1))}[side]
            ports.append(dict(id=f'{uid}:{side}:{xx}:{yy}', unit=uid, cell=[xx, yy],
                              side=side, role=role, slot=slot, segment=ends))
check('all_saved_ports', sorted([{k:v for k,v in p.items() if k != 'segment'} for p in ports],key=lambda p:p['id'])
      == sorted(J['ports'],key=lambda p:p['id']))
by_edge = defaultdict(list)
by_id = {p['id']:p for p in ports}
for p in ports: by_edge[p['segment']].append(p)
channels = []
for edge, ps in by_edge.items():
    assert len(ps) <= 2
    if len(ps) != 2: continue
    a, b = ps
    if a['role'] == b['role']: continue
    if a['role'] == 'in': a,b=b,a
    if not (UNITS[a['unit']]['kind'] in TR or UNITS[b['unit']]['kind'] in TR): continue
    assert OPP[a['side']] == b['side']
    channels.append(dict(source=a['id'],target=b['id'],source_unit=a['unit'],target_unit=b['unit'],
                         source_slot=a['slot'],target_slot=b['slot']))
check('all_saved_automatic_channels', sorted(channels,key=lambda c:(c['source'],c['target'])) ==
      sorted(json.loads((AUTHOR/'自动通道.json').read_text()),key=lambda c:(c['source'],c['target'])))
actual = {(c['source'],c['target']) for c in channels}
expected = set(); used_slots = {}; routes=[]
for r in J['routes']:
    cells = [r['source_cell']] + r['cells'] + [r['target_cell']]
    ids = []; slots=[]; components=0; previous=None
    for i, cell in enumerate(r['cells'], 1):
        xy=tuple(cell); uid=occ[xy]; u=UNITS[uid]; kind=u['kind']; ids.append(uid)
        assert kind in TR
        a=tuple(cells[i-1][j]-cell[j] for j in (0,1)); b=tuple(cells[i+1][j]-cell[j] for j in (0,1))
        s=next(k for k,v in DIR.items() if v==a); t=next(k for k,v in DIR.items() if v==b)
        p=by_id[f'{uid}:{s}:{cell[0]}:{cell[1]}'];q=by_id[f'{uid}:{t}:{cell[0]}:{cell[1]}']
        assert p['role']=='in' and q['role']=='out'
        slot=p['slot'] if kind=='桥接器' else 'only'
        if kind=='桥接器': assert q['slot']==slot
        key=(uid,slot); assert key not in used_slots
        used_slots[key]=r['id'];slots.append([uid,slot])
        components += int(kind!='传送带' or previous!='传送带');previous=kind
    for i in range(len(cells)-1):
        if i == len(cells)-2 and r['external_sink']:
            assert tuple(cells[i+1]) not in occ
            continue
        a,b=cells[i:i+2]; ua,ub=occ[tuple(a)],occ[tuple(b)]
        side=next(s for s,d in DIR.items() if d==(b[0]-a[0],b[1]-a[1]))
        expected.add((f'{ua}:{side}:{a[0]}:{a[1]}',f'{ub}:{OPP[side]}:{b[0]}:{b[1]}'))
    check('route_metadata:'+r['id'], ids==r['transport_unit_ids'] and len(ids)==r['transport_slots']==r['physical_cells']==r['minimum_delay_ticks']
          and components==r['components']==r['internal_damping_prefix'] and r['damping']==(None if r['external_sink'] else components))
    routes.append(dict(id=r['id'],slots=slots,length=len(ids),components=components,
                       single_slot_capacity='1',planned_rate=r['planned_rate'],guaranteed_production=r['actual_rate']))
check('full_graph_equals_all_routes',actual==expected,dict(extra=list(actual-expected),missing=list(expected-actual)))
check('all_transport_slots_in_one_route',len(used_slots)==sum(2 if u['kind']=='桥接器' else int(u['kind'] in TR) for u in UNITS.values()))
bridges=[]
for uid,u in UNITS.items():
    if u['kind']!='桥接器':continue
    x,y=u['xy']; neighbors={}
    for side,(dx,dy) in DIR.items():
        v=UNITS[occ[x+dx,y+dy]]; assert v['kind']=='传送带'
        q=by_id[f"{v['id']}:{OPP[side]}:{x+dx}:{y+dy}"]
        neighbors[side]=q['role']
    orders=[]
    for perm in itertools.permutations(DIR):
        inferred={}
        for side in perm:
            axis='horizontal' if side in 'EW' else 'vertical'
            if axis in inferred:continue
            inp=side if neighbors[side]=='out' else OPP[side]
            inferred[axis]=(inp,OPP[inp])
        assert all(inferred[a['axis']]==(a['input'],a['output']) for a in u['axes'])
        orders.append(list(perm))
    bridges.append(dict(id=uid,verified_orders=orders,inferred_axes=inferred))
power={}
for uid,u in UNITS.items():
    if u['kind'] not in SMALL|MEDIUM|LARGE|{'协议储存箱'}:continue
    x,y=u['xy'];w,h=u['size']; covers=[]
    for pid,p in UNITS.items():
        if p['kind']!='供电桩':continue
        a,b=p['xy']
        # Count covered occupied unit cells, independently of author rectangle overlap code.
        count=sum(a-5<=xx<a+7 and b-5<=yy<b+7 for xx in range(x,x+w) for yy in range(y,y+h))
        if count:covers.append(dict(pole=pid,covered_cells=count))
    assert covers;power[uid]=covers
check('saved_power', {u:[p['pole'] for p in ps] for u,ps in power.items()} ==json.loads((AUTHOR/'桥与供电.json').read_text())['power'])

register=J['planned_factory_machine_register']; plans=[]; counts=Counter(m['kind'] for m in register)
for m in register:
    cap=F(1,5) if m['kind'] in {'封装机','灌装机'} else F(1)
    need=sum((F(r['expected_batches_per_tick']) for r in m['recipes']), F(0))
    assert F(m['capacity_batches_per_tick'])==cap and F(m['planned_batches_per_tick'])==need
    assert F(m['planned_spare_capacity'])==cap-need>=0
    assert m['actual_guaranteed_rate'] is None
    assert m['xy']==UNITS.get(m['id'],{}).get('xy')
    plans.append(dict(id=m['id'],demand=str(need),capacity=str(cap),slack=str(cap-need)))
minimum=dict(粉碎机=68,精炼炉=51,研磨机=32,塑形机=6,配件机=6,种植机=32,采种机=16,封装机=3,灌装机=3)
area=sum(n*SIZES[k][0]*SIZES[k][1] for k,n in counts.items())
assert area==3325 and area-sum(n*SIZES[k][0]*SIZES[k][1] for k,n in minimum.items())==34
feed=json.loads((BASE/'送料与接口.json').read_text());B=next(c for c in feed['candidates'] if c['id']=='B219')
original={f['id']:f for f in B['feeds']}
for e in J['logical_edge_register']:
    assert all(e[k]==original[e['id']][k] for k in ['source','target','source_port','target_port','item','expected_rate_per_tick'])
    assert e['actual_guaranteed_rate'] is None
    rs=[r for r in J['routes'] if e['id'] in r['logical_feed_ids']]
    assert [r['id'] for r in rs]==e['physical_route_ids']
    status='changed_terminal_to_wireless_box' if any(r['id'].endswith('_成品') for r in rs) else 'source_stub_only' if any(r['external_sink'] for r in rs) else 'fully_embedded' if rs else 'unrouted'
    assert status==e['geometry_status']
counts_edges=Counter(e['geometry_status'] for e in J['logical_edge_register'])

product=[]
for r in routes:
    if not r['id'].endswith('_成品'):continue
    n=r['length']
    product.append(dict(route=r['id'],all_segments=[dict(slot=s,capacity='1') for s in r['slots']],
                        planned_rate=r['planned_rate'],completion_rate_upper='1/5',burst_closed_interval='1+floor(s/5)',
                        output_queue_upper=2,to_box_upper=n+1,to_warehouse_upper=n+6,
                        inflight_empty_start_upper=1+(n+1)//5,physical_inflight_upper=n))
stats=dict(units=len(UNITS),kinds=Counter(u['kind'] for u in UNITS.values()),occupied_cells=len(occ),ports=len(ports),channels=len(channels),
           routes=len(routes),transport_cells=sum(u['kind'] in TR for u in UNITS.values()),transport_slots=len(used_slots),
           product_slots=sum(r['length'] for r in routes if r['id'].endswith('_成品')),
           plant_slots={s:sum(r['length'] for r in routes if r['id'].startswith(s)) for s in ['荞花','砂叶']},
           ore_stubs=Counter(r['item'] for r in J['routes'] if r['external_sink'] and r['item'] in ['蓝铁矿','源矿']),
           planned_machine_count=len(register),planned_machine_area=area,planned_machine_counts=counts,edge_statuses=counts_edges)
check('reported_totals', (stats['units'],stats['occupied_cells'],stats['ports'],stats['channels'],stats['routes'],stats['transport_cells'],stats['transport_slots'])==(235,697,542,182,68,166,170),stats)

# Capture author script writes in memory. The original files are never executed with writable output paths.
class CaptureWrites(ast.NodeTransformer):
    def visit_Call(self,node):
        self.generic_visit(node)
        if isinstance(node.func,ast.Attribute) and node.func.attr=='write_text':
            return ast.copy_location(ast.Call(func=ast.Name(id='_capture_write',ctx=ast.Load()),args=[node.func.value]+node.args,keywords=node.keywords),node)
        return node
replays=[]
for name in ['生成.py','核验.py']:
    path=AUTHOR/name; tree=ast.parse(path.read_text()); captured={}; output=io.StringIO(); errors=None
    def capture(path,txt,**kwargs):
        captured[str(path.resolve())]=txt
        return len(txt)
    scope={'__file__':str(path.resolve()),'__name__':'__main__','_capture_write':capture}
    tree=ast.fix_missing_locations(CaptureWrites().visit(tree))
    try:
        with contextlib.redirect_stdout(output):exec(compile(tree,str(path),'exec'),scope)
        code=0
    except Exception:
        code=1;errors=traceback.format_exc()
    comparisons=[]
    for dest,txt in captured.items():
        comparisons.append(dict(path=dest,byte_equal=Path(dest).read_text()==txt,
                                semantic_equal=(json.loads(Path(dest).read_text())==json.loads(txt)) if dest.endswith('.json') else Path(dest).read_text()==txt))
    replays.append(dict(script=str(path.resolve()),execution='AST write_text captured in memory; input reads unchanged',exit_code=code,
                        stdout=output.getvalue(),stderr=errors,outputs=comparisons))
    check('read_only_replay:'+name,code==0 and all(c['semantic_equal'] for c in comparisons),comparisons)

manifests=[]
for name in ['交付清单.json','输入指纹.json']:
    m=json.loads((AUTHOR/name).read_text()); rows=m['files'] if isinstance(m,dict) else m
    for row in rows:
        p=Path(row['path']);raw=p.read_bytes()
        manifests.append(dict(manifest=name,path=str(p),sha256_matches=hashlib.sha256(raw).hexdigest()==row['sha256'],
                              mtime_matches=p.stat().st_mtime_ns==row['mtime_ns'] if 'mtime_ns' in row else None))
check('all_author_manifest_hashes',all(m['sha256_matches'] for m in manifests))
write('逐格独立核验.json',dict(status='pass',scope='independent static geometry, arithmetic, read-only author reproduction',metrics=stats,
                               checks=checks,channels=channels,routes=routes,bridges=bridges,power=power,
                               planned_capacity=plans,product_segments=product,manifests=manifests))
write('作者脚本只读复算.json',replays)
print(json.dumps(dict(status='pass',metrics=stats,read_only_replay_status=[dict(script=x['script'],exit_code=x['exit_code']) for x in replays]),ensure_ascii=False))
