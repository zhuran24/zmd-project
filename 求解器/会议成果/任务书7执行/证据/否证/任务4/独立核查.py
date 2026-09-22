#!/usr/bin/env python3
"""独立数据、几何及局部算术检查；只写本脚本目录，不运行被审写入脚本。"""
from pathlib import Path
from fractions import Fraction as Q
from collections import Counter, defaultdict
import ast, contextlib, hashlib, io, json, runpy

E = Path(__file__).resolve().parent
O = E.parents[2]
ROOT = O.parents[2]
A = O/'证据/植物运行'
def read(p): return json.loads(p.read_text())
def save(name, obj): (E/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')
def meta(p):
    b=p.read_bytes()
    return dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),lines=len(b.splitlines()),mtime_ns=p.stat().st_mtime_ns)
paths=[O/'植物运行试点.md',O/'送料与接口.json']+[A/n for n in (
    '候选A原脚本重放.log','局部时间表核对.json','局部结构.json','提取与算术.py','来源增量.json',
    '来源增量核查.py','核验.log','核验.py','核验结果.json','版本失配.log','算术与图核验.json',
    '读者自审.md','输入当前指纹.json','输入指纹.json','逐机逐口清单.md','交付清单.json')]
deps=read(A/'输入当前指纹.json')
allpaths=list(dict.fromkeys(paths+[Path(x['path']) for x in deps]))
current=[meta(p) for p in allpaths]
start=E/'被审指纹.json'
if start.exists():
    assert read(start)==current,'被审或来源文件在本席核查期间变化，须重新复核'
else: save(start.name,current)
result={'scope':'读当前全部被审文件；原始A只读重放；精确分数配平；实际几何；条件局部算术。无内核轨迹或全厂认证。'}
manifest=read(A/'交付清单.json')
for x in manifest['files']:
    m=meta(Path(x['path']))
    assert (m['sha256'],m['bytes'])==(x['sha256'],x['bytes'])
for x in deps:
    assert meta(Path(x['path']))==x
result['locked_review_files']=len(paths)
result['manifest_entries_matching']=len(manifest['files'])
result['current_dependencies_matching']=len(deps)

# 用逆向增量原文重算哈希，仅提取两个字面量，不执行原脚本。
constants={}
for n in ast.parse((A/'来源增量核查.py').read_text()).body:
    if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('task_old13','task_old29'):
        constants[n.targets[0].id]=ast.literal_eval(n.value)
old={x['path']:x for x in read(A/'输入指纹.json')}
changes=read(A/'来源增量.json')
for c in changes:
    p=Path(c['path']);b=p.read_bytes()
    if p.name.startswith('《'):
        s=b.decode().splitlines(keepends=True)
        s[35]=s[35].replace('，即使那个物品格中没有物品也一样','')
    elif p.name=='任务书7草案.md':
        s=b.decode().splitlines(keepends=True)
        s[12]=constants['task_old13']+'\n';s[28]=constants['task_old29']+'\n'
        s[66]=s[66].replace('规则 `d150b86b398f`（09-21 上午恢复第 36 行后的现行值；任务 1 首次重锁时是 31ced2a24fef，主会话已同步）','规则 `31ced2a24fef`')
    else: s=b.decode().splitlines(keepends=True)[:53]
    assert hashlib.sha256(''.join(s).encode()).hexdigest()==old[str(p)]['sha256']==c['old_sha256']
result['source_reverse_increments']=3

d=read(O/'送料与接口.json')
# 配方独立抄自 R81—114，不导入被审提取函数。
recipes={
 '粉碎-源矿':({'源矿':1},{'源石粉末':1}), '粉碎-蓝铁块':({'蓝铁块':1},{'蓝铁粉末':1}),
 '粉碎-荞花':({'荞花':1},{'荞花粉末':2}), '粉碎-砂叶':({'砂叶':1},{'砂叶粉末':3}),
 '精炼-蓝铁矿':({'蓝铁矿':1},{'蓝铁块':1}), '精炼-致密蓝铁':({'致密蓝铁粉末':1},{'钢块':1}),
 '研磨-致密蓝铁':({'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1}),
 '研磨-致密源石':({'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1}),
 '研磨-细磨荞花':({'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1}),
 '塑形-钢质瓶':({'钢块':2},{'钢质瓶':1}), '配件-钢制零件':({'钢块':1},{'钢制零件':1}),
 '种植-荞花':({'荞花种子':1},{'荞花':1}), '种植-砂叶':({'砂叶种子':1},{'砂叶':1}),
 '采种-荞花':({'荞花':1},{'荞花种子':2}), '采种-砂叶':({'砂叶':1},{'砂叶种子':2}),
 '封装-电池':({'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1}),
 '灌装-胶囊':({'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1})}
kind_area={'粉碎机':9,'精炼炉':9,'配件机':9,'塑形机':9,'种植机':25,'采种机':25,'研磨机':24,'封装机':24,'灌装机':24}
def cycle_components(fs,s):
    edges=[(f['source'],f['target']) for f in fs if f['item'] in (s,s+'种子')]
    nodes=set(sum(([x,y] for x,y in edges),[]))
    # 全部节点可达集合求交，算法与被审 Tarjan 实现独立。
    reach={}
    for n in nodes:
        seen={n};todo=[n]
        while todo:
            v=todo.pop()
            for x,y in edges:
                if x==v and y not in seen: seen.add(y);todo.append(y)
        reach[n]=seen
    cs={tuple(sorted(v for v in nodes if v in reach[u] and u in reach[v])) for u in nodes}
    return [dict(machines=list(c), incoming=[f['id'] for f in fs if f['item'] in (s,s+'种子') and f['target'] in c and f['source'] not in c],outgoing=[f['id'] for f in fs if f['item'] in (s,s+'种子') and f['source'] in c and f['target'] not in c]) for c in sorted(cs) if len(c)>1]

result['candidates']={}
for c in d['candidates']:
    byid={m['id']:m for m in c['machines']};ins=defaultdict(Counter);outs=defaultdict(Counter);deg=Counter()
    fs=c['feeds'];seenports=set()
    for f in fs:
        r=Q(f['expected_rate_per_tick']);assert 0<r<=1
        for side,key in (('in','target'),('out','source')):
            obj=f[key];port=f[key+'_port']
            assert (side,port) not in seenports
            seenports.add((side,port));deg[obj,side]+=1
        ins[f['target']][f['item']]+=r;outs[f['source']][f['item']]+=r
        assert f['proven_actual_rate_per_tick'] is None and f['transport_cells'] is None
    for m in byid.values():
        expin=Counter();expout=Counter()
        for r in m['recipes']:
            a,b=recipes[r['name']];v=Q(r['expected_batches_per_tick'])
            expin.update({k:n*v for k,n in a.items()});expout.update({k:n*v for k,n in b.items()})
            assert r['proven_actual_batches_per_tick'] is None
        assert ins[m['id']]==expin,(c['id'],m['id'],'in')
        assert outs[m['id']]==expout,(c['id'],m['id'],'out')
        ports={9:3,25:5,24:6}[kind_area[m['kind']]]
        assert all(deg[m['id'],side]<=ports for side in ('in','out'))
    cycles={s:cycle_components(fs,s) for s in ('荞花','砂叶')}
    expected=read(A/'算术与图核验.json')['raw_graph_cycle_components_'+c['id'][0]]
    assert all(sorted(cycles[s],key=lambda z:z['machines'])==sorted(expected[s],key=lambda z:z['machines']) for s in cycles)
    assert all(not comp['incoming'] for cs in cycles.values() for comp in cs)
    roots=sum(map(len,cycles.values()))
    selected=[f for f in fs if f['item'] in ('荞花','荞花种子','砂叶','砂叶种子')]
    powders=[f for f in fs if f['item'] in ('荞花粉末','砂叶粉末')]
    assert len(selected)==66
    result['candidates'][c['id']]=dict(machines=len(byid),feeds=len(fs),raw_feeds=len(selected),powder_feeds=len(powders),area=sum(kind_area[m['kind']] for m in byid.values()),roots=roots,cycles=cycles,machine_kind_counts=dict(Counter(m['kind'] for m in byid.values())),recipe_balances='全部逐机逐物品以精确分数相等')
    # 所有逐机逐口 Markdown 行必须真实出现。
    table=(A/'逐机逐口清单.md').read_text()
    for f in selected+powders:
        row=f"| {f['id']} | {f['source_port']} → {f['target_port']} | {f['item']} | {f['expected_rate_per_tick']} |"
        assert row in table

# A 只读原脚本已逐行检查；只把重放标准输出写入本席目录。
cap=io.StringIO()
with contextlib.redirect_stdout(cap): orig=runpy.run_path(d['candidates'][0]['source'])
assert cap.getvalue()==(A/'候选A原脚本重放.log').read_text()
(E/'候选A独立重放.log').write_text(cap.getvalue())
for f,(item,s,t,n) in zip(d['candidates'][0]['feeds'],orig['edges']):
    assert f['item']==item and Q(f['expected_rate_per_tick'])==Q(n,20)
    assert f['target']==('A_CORE' if t=='核心' else f'A_M{t.gid:03}')
    if s is not None: assert f['source']==f'A_M{s.gid:03}'
contract=read(Path(d['candidates'][1]['source']))
for f,g in zip(d['candidates'][1]['feeds'],contract['logical_feeds']):
    assert all(f[k]==g[k] for k in ('id','source','target','source_port','target_port','item'))
    assert Q(f['expected_rate_per_tick'])==Q(g['planned_rate']['value'])
result['source_records_match']=True

# 已保存几何反向重建所有共边端口，无正向路径生成器复用。
dirs={'N':(0,1),'S':(0,-1),'E':(1,0),'W':(-1,0)}
rev={'N':'S','S':'N','E':'W','W':'E'}
result['geometry']={}
for s,g in read(A/'局部结构.json').items():
    occ={};ports={}
    for m in g['machines']+g['power']:
        for x in range(m['x'],m['x']+m['w']):
            for y in range(m['y'],m['y']+m['h']):
                assert 0<=x<70 and 0<=y<70 and (x,y) not in occ
                occ[x,y]=m['id']
                for mode in ('input','output'):
                    if mode not in m: continue
                    dr=m[mode]
                    boundary={'N':y==m['y']+m['h']-1,'S':y==m['y'],'E':x==m['x']+m['w']-1,'W':x==m['x']}[dr]
                    if boundary: ports[x,y,dr]=(m['id'],mode)
    for b in g['belts']:
        x,y=b['x'],b['y'];assert (x,y) not in occ
        occ[x,y]=b['id']
        for mode in ('input','output'): ports[x,y,b[mode]]=(b['id'],mode)
    links=[]
    for (x,y,dr),(who,mode) in ports.items():
        dx,dy=dirs[dr];other=ports.get((x+dx,y+dy,rev[dr]))
        if mode=='output' and other and other[1]=='input':links.append([who,other[0]])
    assert sorted(links)==sorted(g['internal_channels'])
    for m in g['machines']:
        hits=[]
        for p in g['power']:
            if any(p['x']-5<=x<p['x']+7 and p['y']-5<=y<p['y']+7 for (x,y),who in occ.items() if who==m['id']):hits.append(p['id'])
        assert hits==g['power_coverage'][m['id']]
    result['geometry'][s]=dict(transport_slots=len(g['belts']),channels=len(links),paths=dict(Counter(b['path'] for b in g['belts'])),unexpected_channels=0)

# 独立闭式到达计数，逐行比对保存时间表。只检查所指定时间表，非模拟器。
traces=read(A/'局部时间表核对.json');schedule=[]
for tr in traces:
    q=tr['initial_seeds'];first=tr['first_h'];b=2 if tr['plant']=='荞花' else 3
    h0=1 if first else 2;g0=2 if first else 1
    for row in tr['rows']:
        t=row['t'];H=max(0,(t-(h0+4))//2+1);G=max(0,(t-(g0+4))//2+1)
        first_return=h0+21
        returned=max(0,t-first_return+1)
        pin=q-(t+1)+returned
        assert row['P']==t and row['H']==H and row['G']==G
        assert row['N']==q+H-G and row['inputs']=={'P':pin,'H':0,'G':0}
        if b==3: powder=3*G
        else: powder=sum(min(2,max(0,t-u+1)) for u in range(g0+4,t+1,2))
        assert row['powder']==powder
    schedule.append(dict(plant=tr['plant'],q=q,first_h=first,first_return=h0+21,checked_rows=len(tr['rows'])))
result['saved_schedule_checks']=schedule

# 逐事件 K 恒等式以及所需容量公式。
events={'plant_complete':(0,0,0,0,0),'harvest_complete':(1,-1,0,0,0),'crush_complete':(-1,0,-1,0,0),
        'assign_h':(0,1,0,1,0),'assign_g':(0,0,1,0,1)}
assert all(n+h-g==ah-ag for n,h,g,ah,ag in events.values())
result['capacities']={}
for s,p,h,g,b in [('荞花',11,6,6,2),('砂叶',21,11,11,3)]:
    vals=dict(ordinary_all_materials=100*(p+h+g),normal_cache=p+2*h+b*g,N_normal=100*(p+h)+50*g+p+2*h+g)
    inv=d['inventory'][s]
    assert vals['N_normal']==inv['seed_plus_plant_with_normal_cache']
    assert vals['ordinary_all_materials']==inv['ordinary_all_materials']
    result['capacities'][s]=vals
assert 4800+64+51*16==5680 and 250+4+23==277

# 反例：仅普通输入格放种子，已严格超过被审“普通种子”物理上界。
# 所有制造开关关闭，所有缓存/取货格/带空，R17、T12允许逐格放料。
witness=[]
for s,p,h,g,claimed in [('荞花',11,6,6,850),('砂叶',21,11,11,1600)]:
    actual=50*(p+h+g);assert actual>claimed
    witness.append(dict(species=s,planters=p,harvesters=h,crushers=g,input_each={'item':s+'种子','count':50},all_switches='off',all_caches='empty',all_output_slots='empty',all_transport_slots='empty',ordinary_seed_count=actual,claimed_bound=claimed,excess=actual-claimed,legality=['R17','R21','T6','T12','T13'],consequence='开关保持关闭时状态固定；普通输入容量无配方身份限制。此例攻击物理容量标签，未攻击正确原料的运行充分族。'))
save('普通种子容量反例.json',witness)
result['ordinary_seed_capacity_counterexample']=witness
units=[dict(id='CORE',kind='协议核心',x=0,y=0,w=9,h=9)]
medium=[];small=[]
for s,p,h,g in [('荞花',11,6,6),('砂叶',21,11,11)]:
    for kind,n in [('种植机',p),('采种机',h)]:
        for i in range(n): medium.append((s,kind,i))
    for i in range(g): small.append((s,'粉碎机',i))
for j,(s,kind,i) in enumerate(medium+small):
    if j<len(medium): x,y,w=10+5*(j%12),5*(j//12),5
    else: x,y,w=10+3*(j-len(medium)),25,3
    units.append(dict(id=f'{s}-{kind}-{i}',kind=kind,x=x,y=y,w=w,h=w,input='S',output='N',switch='off',input_inventory={s+'种子':50},output_inventory={},cache={}))
occupied=set()
for u in units:
    for x in range(u['x'],u['x']+u['w']):
        for y in range(u['y'],u['y']+u['h']):
            assert 0<=x<70 and 0<=y<70 and (x,y) not in occupied
            occupied.add((x,y))
save('容量反例合法摆放.json',dict(scope='66台植物机器及核心的容量见证；全关机无运输单位，R16不形成机器直连；非目标达标布局',units=units,seed_totals={'荞花种子':1150,'砂叶种子':2150},normal_caches_empty=True,occupied_cells=len(occupied)))
result['status']='PASS'
save('独立核查结果.json',result)
assert [meta(p) for p in allpaths]==current,'检查期间输入改变'
print('PASS: 18份被审文件、17条清单指纹、19份来源及3项逆增量核对。')
print('PASS: 438台机器、629条边逐机精确配平；A/B分别17/4个循环根；几何24/26格、27/29通道。')
print('PASS: 8份保存时间表各28行闭式核对；正常缓存、K及容量算术核对。')
print('COUNTEREXAMPLE: 普通输入格允许任意种类，荞花种子1150>850、砂叶种子2150>1600。')
print('SCOPE: 正常配方槽位容量与实际物理容量须分开；局部时间表无全参数认证含义。')
