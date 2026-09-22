#!/usr/bin/env python3
"""Deterministic embedding of the supplied local pilot, not a layout search."""
import hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('/home/zhuran24/zmd-research-fresh')
OUT = ROOT/'求解器/会议成果/任务书7执行'
EV = OUT/'证据/密排'
def write(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')
source_paths = [ROOT/x for x in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt',
 '求解器/会议成果/任务书7草案.md','求解器/会议成果/主会话三审-0920.md','求解器/会议成果/会议2成果修订-v46.md',
 '求解器/规格/推导/三种相位不改产量-v2.md']]
source_paths += [OUT/x for x in ['植物运行试点.md','送料与接口.json','调试与释放.md','调试后状态.json',
 '相位离线与认证范围.md','仓库接收与循环对应.md','复核/否证-任务4.md','复核/否证-任务5.md','复核/否证-任务6.md',
 '证据/植物运行/局部结构.json','证据/植物运行/否证逐项处理.json']]
sources=[]
for p in source_paths:
    raw=p.read_bytes(); text=raw.decode(); parsed=None
    if p.suffix=='.json': parsed=json.loads(text)
    sources.append(dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),lines=len(text.splitlines()),
                        mtime_ns=p.stat().st_mtime_ns,role='input_read_only',json_parsed=parsed is not None))
write(EV/'输入指纹.json',sources)
feed=json.loads((OUT/'送料与接口.json').read_text())
B=next(x for x in feed['candidates'] if x['id']=='B219')
units=[]; routes=[]; ports=[]; endpoints=[]
D={'N':(0,1),'E':(1,0),'S':(0,-1),'W':(-1,0)}
OP={'N':'S','S':'N','E':'W','W':'E'}
def direction(a,b):
    return next(k for k,v in D.items() if (b[0]-a[0],b[1]-a[1])==v)
def port(u,cell,side,role,slot):
    p=dict(id=f"{u}:{side}:{cell[0]}:{cell[1]}",unit=u,cell=list(cell),side=side,role=role,slot=slot)
    ports.append(p); return p['id']
def unit(uid,kind,x,y,w,h,inp=None,out=None,group='',**kw):
    a=dict(id=uid,kind=kind,xy=[x,y],size=[w,h],orientation=dict(input=inp,output=out),group=group,**kw)
    units.append(a)
    for side,role in [(inp,'in'),(out,'out')]:
        if side is None: continue
        cells=([(xx,y if side=='S' else y+h-1) for xx in range(x,x+w)] if side in ['N','S'] else
               [(x if side=='W' else x+w-1,yy) for yy in range(y,y+h)])
        for cell in cells: port(uid,cell,side,role,role)
    return a
def route(uid,src,dst,cells,item,rate=None,external=False):
    routes.append(dict(id=uid,source_cell=list(src),target_cell=list(dst),cells=[list(c) for c in cells],item=item,
      planned_rate=rate,actual_rate=None,external_sink=external,transport_slots=len(cells)))

for dx,species,P,H,G in [(0,'荞花','M174','M201','M057'),(20,'砂叶','M195','M212','M068')]:
    unit(P,'种植机',8+dx,8,5,5,'S','N',species,recipe=f'1{species}种子→1{species}',manufacture_on=True)
    unit(H,'采种机',8+dx,14,5,5,'S','N',species,recipe=f'1{species}→2{species}种子',manufacture_on=True)
    unit(G,'粉碎机',14+dx,14,3,3,'W','E',species,recipe=f'1{species}→{2 if dx==0 else 3}{species}粉末',manufacture_on=True)
    for n,x,y in [('a',4+dx,10),('b',17+dx,18)]: unit(f'POWER_{species}_{n}','供电桩',x,y,2,2,group=species)
    route(f'{species}_PH',(9+dx,12),(9+dx,14),[(9+dx,13)],species,'1/2')
    route(f'{species}_PG',(12+dx,12),(14+dx,14),[(12+dx,13),(13+dx,13),(13+dx,14)],species,'1/2')
    seed=[(8+dx,19),(7+dx,19)]+[(7+dx,y) for y in range(18,6,-1)]+[(8+dx,7)]
    route(f'{species}_HP',(8+dx,18),(8+dx,8),seed,species+'种子','1')
    for j in range(1 if dx==0 else 3):
        route(f'{species}_粉末{j+1}',(16+dx,14+j),(18+dx,14+j),[(17+dx,14+j)],species+'粉末','1' if dx==0 else '1/2',True)
        endpoints.append(dict(id=f'{species}_粉末{j+1}',cell=[17+dx,14+j],side='E',role='out',
            external_required_service='每件进入边界带后恰1 tick离开；每口可持续1件/tick',external_realized=False))

for dx,kind,product,start in [(0,'封装机','高容谷地电池',213),(34,'灌装机','精选荞愈胶囊',216)]:
    group='电池输出' if dx==0 else '胶囊输出'
    for i,x in enumerate([6,13,20]):
        u=f'M{start+i}'
        unit(u,kind,x+dx,34,6,4,'S','N',group,manufacture_on=True,
             recipe='10钢制零件+15致密源石粉末→1高容谷地电池' if dx==0 else '10钢质瓶+10细磨荞花粉末→1精选荞愈胶囊')
        for xx in range(x+dx,x+dx+6):
            endpoints.append(dict(id=f'{u}_原料口{xx-x-dx+1}',unit=u,cell=[xx,34],side='S',role='in',
             external_required_service='逐物种到达前缀及≤50库存；各口分工须由M7重新分配',external_realized=False))
    box='BOX_B' if dx==0 else 'BOX_C'
    unit(box,'协议储存箱',15+dx,44,3,3,'S','N',group,transmission_on=True,initial_contents='empty',
         initial_cooldown='arbitrary in [0,5]',warehouse_precondition='仓库收得下成品',external_output=False)
    for i,x in enumerate([11,27]):unit(f'POWER_{group}_{i}','供电桩',x+dx,39,2,2,group=group)
    cells1=[(7,y) for y in range(38,42)]+[(x,41) for x in range(8,17)]+[(16,42),(16,43)]
    cells2=[(18,y) for y in range(38,43)]+[(17,42),(17,43)]
    cells3=[(25,y) for y in range(38,41)]+[(x,40) for x in range(24,14,-1)]+[(15,y) for y in range(41,44)]
    for i,(cells,sx,tx) in enumerate([(cells1,7,16),(cells2,18,17),(cells3,25,15)]):
        route(f'M{start+i}_成品',(sx+dx,37),(tx+dx,44),[(x+dx,y) for x,y in cells],product,
              '3/20' if start+i==218 else '1/5')

# Required core and ore edge geometry are instantiated; all 52 ore continuations remain open.
core=unit('CORE','协议核心',49,8,9,9,group='整厂边界')
for side in ['N','S']:
    for k in range(1,8):port('CORE',(49+k,16 if side=='N' else 8),side,'in','warehouse')
for side in ['W','E']:
    for k in [1,4,7]:
        src=(49 if side=='W' else 57,8+k);port('CORE',src,side,'out','蓝铁矿')
        x=48 if side=='W' else 58; dst=(x-1 if side=='W' else x+1,8+k)
        route(f'CORE_{side}_{k}',src,dst,[(x,8+k)],'蓝铁矿','1',True)
for i in range(23):
    y=1+3*i; uid=f'ORE_W_{i:02d}'
    unit(uid,'仓库取货口',0,y,1,3,group='整厂边界',warehouse_item='蓝铁矿')
    port(uid,(0,y+1),'E','out','蓝铁矿')
    dst=(1,y+2) if i==0 else (2,y+1)
    route(uid+'_边界',(0,y+1),dst,[(1,y+1)],'蓝铁矿','1',True)
    x=1+3*i;uid=f'ORE_S_{i:02d}';item='蓝铁矿' if i<5 else '源矿'
    unit(uid,'仓库取货口',x,0,3,1,group='整厂边界',warehouse_item=item)
    port(uid,(x+1,0),'N','out',item)
    dst=(x+2,1) if i==0 else (x+1,2)
    route(uid+'_边界',(x+1,0),dst,[(x+1,1)],item,'1',True)

# Create every actual belt/bridge from oriented path crossings.
cell_uses=defaultdict(list)
for r in routes:
    path=[r['source_cell']]+r['cells']+[r['target_cell']]
    for i,cell in enumerate(r['cells'],1):
        inp=direction(cell,path[i-1]);out=direction(cell,path[i+1])
        cell_uses[tuple(cell)].append((r['id'],inp,out,r['item']))
for cell,uses in sorted(cell_uses.items()):
    uid=f'T_{cell[0]}_{cell[1]}'
    if len(uses)==1:
        rid,inp,out,item=uses[0]
        unit(uid,'传送带',*cell,1,1,inp,out,group='运输',routes=[rid],item=item)
    else:
        assert len(uses)==2 and all(OP[a]==b for _,a,b,_ in uses)
        assert len({v for _,a,b,_ in uses for v in [a,b]})==4
        unit(uid,'桥接器',*cell,1,1,group='运输',routes=[x[0] for x in uses],axes=[])
        for rid,inp,out,item in uses:
            axis='horizontal' if inp in ['W','E'] else 'vertical'
            units[-1]['axes'].append(dict(axis=axis,input=inp,output=out,item=item,route=rid,slot_capacity=1))
            port(uid,cell,inp,'in',axis);port(uid,cell,out,'out',axis)
for r in routes:
    kinds=[next(u['kind'] for u in units if u['id']==f'T_{x}_{y}') for x,y in r['cells']]
    components=0;prev=None
    for k in kinds:
        if k=='桥接器' or prev!='传送带':components+=1
        prev=k
    r['components']=components
    r['damping']=None if r['external_sink'] else components
    r['internal_damping_prefix']=components
    r['minimum_delay_ticks']=len(kinds)
    r['service_capacity_given_receiving_boundary']='1 item/tick'
    r['physical_cells']=len(kinds)
    r['transport_unit_ids']=[f'T_{x}_{y}' for x,y in r['cells']]
    if r['external_sink'] and ('CORE_' in r['id'] or 'ORE_' in r['id']):
        cell=r['cells'][-1];side=direction(cell,r['target_cell'])
        endpoints.append(dict(id=r['id'],cell=cell,side=side,role='out',external_realized=False,
                              external_required_service='原矿续路每tick 1；实际接入尚缺'))

register=[];byid={u['id']:u for u in units}
occupied={}
for u in units:
    x,y=u['xy'];w,h=u['size']
    for xx in range(x,x+w):
        for yy in range(y,y+h):occupied[xx,yy]=u['id']
for r in routes:
    r['source_unit']=occupied[tuple(r['source_cell'])]
    r['source_port']=next(p['id'] for p in ports if p['unit']==r['source_unit'] and p['cell']==r['source_cell'] and p['side']==direction(r['source_cell'],r['cells'][0]))
    r['target_unit']=None if r['external_sink'] else occupied[tuple(r['target_cell'])]
    r['target_port']=None if r['external_sink'] else next(p['id'] for p in ports if p['unit']==r['target_unit'] and p['cell']==r['target_cell'] and p['side']==direction(r['target_cell'],r['cells'][-1]))
    possible=[f for f in B['feeds'] if f['source']==r['source_unit'] and f['item']==r['item']]
    if r['item'].endswith('粉末') and r['external_sink']:
        i=int(r['id'][-1])-1;possible=possible[i:i+1]
    elif not r['external_sink'] and not r['id'].endswith('_成品'):
        possible=[f for f in possible if f['target']==r['target_unit']]
    r['logical_feed_ids']=[f['id'] for f in possible]
for ep in endpoints:
    if ep.get('unit','').startswith('M') and ep['role']=='in':
        u=byid[ep['unit']];n=ep['cell'][0]-u['xy'][0]+1
        ep['logical_port']=f"{ep['unit']}:in:{n}"
        fs=[f for f in B['feeds'] if f['target_port']==ep['logical_port']]
        ep['planned_inputs']=[{k:f[k] for k in ['id','source','source_port','item','expected_rate_per_tick']} for f in fs]
        ep['actual_guaranteed_arrivals']=None
        ep['external_required_service']='兑现planned_inputs逐物种前缀，输入格≤50且开工前足量；未分配口保持空接'
edge_register=[]
for f in B['feeds']:
    rs=[r for r in routes if f['id'] in r['logical_feed_ids']]
    status=('changed_terminal_to_wireless_box' if any(r['id'].endswith('_成品') for r in rs) else
            'source_stub_only' if any(r['external_sink'] for r in rs) else 'fully_embedded' if rs else 'unrouted')
    edge_register.append({k:f[k] for k in ['id','source','target','source_port','target_port','item','expected_rate_per_tick']})
    edge_register[-1].update(geometry_status=status,physical_route_ids=[r['id'] for r in rs],actual_guaranteed_rate=None)
for m in B['machines']:
    n=dict(id=m['id'],kind=m['kind'],recipes=m['recipes'],xy=byid.get(m['id'],{}).get('xy'),
      placement_status='placed' if m['id'] in byid else 'unplaced',
      nominal_surplus_designation=m['id'] in ['M068','M212'],actual_guaranteed_rate=None)
    cap='1/5' if m['kind'] in ['封装机','灌装机'] else '1'
    from fractions import Fraction
    demand=sum(Fraction(r['expected_batches_per_tick']) for r in m['recipes'])
    n.update(capacity_batches_per_tick=cap,planned_batches_per_tick=str(demand),planned_spare_capacity=str(Fraction(cap)-demand))
    register.append(n)
layout=dict(schema='dense-interface-pilot-v1',date='2026-09-21',status='partial',L=0,U=1113,
 scope='确定性局部落格与六来源成品出路；整厂未完成',full_layout_certified=False,default_start_certified=False,
 coordinates='左下格(0,0)，每格整数坐标；xy为单位左下角，size为占格宽高；N为y增加',
 sources_manifest='证据/密排/输入指纹.json',units=units,ports=ports,routes=routes,external_interfaces=endpoints,
 planned_factory_machine_register=register,logical_edge_register=edge_register,planned_factory_counts=dict(Counter(m['kind'] for m in B['machines'])),
 plan_surplus=dict(粉碎机=1,采种机=1),surplus_note='M068和M212为记账指定的新增台；不表示可直接删除，单机闲置产能另列',
 bridge_build_contract='桥四邻均为定向带，无桥邻桥；蓝图先桥后带，每轴任一端首接都给同一方向',
 plant_start_contract=dict(kind='辅助空线程序',q_range=[19,50],q50_margin=31,
   initial='P输入q种子，其余该回路普通格/缓存/运输为空；H/G先开，P最后开',
   external_powder_service='每个出口带每件恰1tick离开且不共享格',offline_scope='固定接通序内及独立证明保持安全集合的接续；一般任意离线仍开放'),
 product_start_contract='六机输出与成品路径、末端箱清空；正常缓存每机≤1批；六末级任意次序/迟延开启；两箱先开并始终有电',
 for_owner=[],open_items=['整厂余下207台及其逻辑边','植物粉末到M150/M151的实际接收','默认堵满释放与离线共同安全集合','无箱A=1113出货支路','本次新增结论独立复核'])
write(OUT/'密排布局.json',layout)
lines=['# 已放单位与逐格路径清单','',
 '日期：2026-09-21。状态：静态局部组合；完整工厂未认证。由同目录生成.py确定性生成。',
 '', '方向N为y增加，xy为左下格。全部端口含未接通端口在../../密排布局.json的ports逐项列出；自动形成的实际边在自动通道.json。',
 '', '## 全部235个实体单位','', '| ID | 型别 | xy | 宽×高 | 存货→取货 / 桥轴 | 设定 |', '| --- | --- | --- | --- | --- | --- |']
for u in units:
    ori=(str(u['axes']) if u['kind']=='桥接器' else str(u['orientation']))
    setting={k:u[k] for k in ['recipe','manufacture_on','transmission_on','initial_contents','initial_cooldown','warehouse_item'] if k in u}
    lines.append(f"| {u['id']} | {u['kind']} | {u['xy']} | {u['size'][0]}×{u['size'][1]} | {ori} | {setting} |")
lines+=['','## 全部68条已铺路径','', '各序列依输送顺序列出运输格；桥的对应轴由轴方向决定。外部终点是接口位置，没有在该格虚构消费者。',
 '', '| 路径 | 源物理端口 → 终点 | 逐格序列 | 长/元件/完整阻尼 | 逻辑边 |', '| --- | --- | --- | --- | --- |']
for r in routes:
    seq=' → '.join(f'({x},{y})' for x,y in r['cells'])
    lines.append(f"| {r['id']} | {r['source_port']} → {r['target_port'] or '开放边界'+str(r['target_cell'])} | {seq} | {r['transport_slots']}/{r['components']}/{r['damping']} | {','.join(r['logical_feed_ids'])} |")
lines+=['','## 92个外接端口','', '| ID | 坐标/边/角色 | 计划原料或服务 |', '| --- | --- | --- |']
for e in endpoints:lines.append(f"| {e['id']} | {e['cell']}/{e['side']}/{e['role']} | {e.get('planned_inputs',e['external_required_service'])} |")
lines+=['','## 219台逐台产能及计划余量','',
 '理论上限、计划值与差值均按批/tick计。实际保证均待整厂证明；M068、M212的新增台标签只作C46台数账。',
 '', '| ID | 型别 | 理论上限 | 计划批率 | 计划闲余 | 台数增量标签 | 坐标 |', '| --- | --- | --- | --- | --- | --- | --- |']
for r in register:lines.append(f"| {r['id']} | {r['kind']} | {r['capacity_batches_per_tick']} | {r['planned_batches_per_tick']} | {r['planned_spare_capacity']} | {r['nominal_surplus_designation']} | {r['xy']} |")
lines+=['','## 全部逻辑边的实现范围','', str(dict(Counter(e['geometry_status'] for e in edge_register))), '',
 '原315条逻辑边全部保存在密排布局.json的logical_edge_register；每条保留原源、目标、物种、计划速率、几何状态和对应物理路径。']
(EV/'逐单位与路径.md').write_text('\n'.join(lines)+'\n')
write(EV/'工具与输入核查.json',dict(structured_output_tool_available=False,return_format='final JSON + evidence JSON',
   full_read_sources=len(sources),candidate_summary=[dict(id=c['id'],machines=len(c['machines']),feeds=len(c['feeds']),
    all_actual_rates_null=all(x['proven_actual_rate_per_tick'] is None for x in c['feeds'])) for c in feed['candidates']],
   no_kernel_build=True,no_kernel_execution=True))
print(json.dumps(dict(units=len(units),routes=len(routes),ports=len(ports),placed_machines=sum(r['placement_status']=='placed' for r in register),
 kinds=dict(Counter(u['kind'] for u in units))),ensure_ascii=False))
