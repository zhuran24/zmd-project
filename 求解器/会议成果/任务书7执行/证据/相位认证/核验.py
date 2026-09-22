#!/usr/bin/env python3
"""任务6作者自核。只在本席证据目录写JSON；不调用任何被审脚本或游戏内核。"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import ast, hashlib, json, re

E = Path(__file__).resolve().parent
B = E.parent.parent
ROOT = B.parent.parent.parent

def read(p):
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name, value):
    assert Path(name).name == name and name.endswith('.json')
    (E/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

checks=[]
def ok(name, detail):
    checks.append({'name':name,'result':'PASS','detail':detail})

manifest=read(E/'输入指纹.json')['files']
read_audit=[]
for row in manifest:
    p=Path(row['path']); raw=p.read_bytes(); txt=raw.decode('utf-8')
    assert sha(p)==row['sha256'], str(p)
    assert p.stat().st_mtime_ns==row['mtime_ns'], str(p)
    assert len(raw)==row['bytes'] and len(txt.splitlines())==row['lines']
    info={'path':str(p),'sha256':sha(p),'bytes_read':len(raw),'full_utf8_read':True}
    if p.suffix=='.json':
        obj=json.loads(txt)
        def count(v):
            if isinstance(v,dict): return 1+sum(count(z) for z in v.values())
            if isinstance(v,list): return 1+sum(count(z) for z in v)
            return 1
        info['json_nodes_visited']=count(obj)
    if p.suffix=='.py':
        tree=ast.parse(txt); info['ast_nodes_visited']=sum(1 for _ in ast.walk(tree))
        info['executed']=False
    read_audit.append(info)
assert len(manifest)==93
ok('输入原始字节与mtime保持',len(manifest))
write('读取核查.json',{'files':read_audit,'scope':'全部列入输入逐字节读取；JSON遍历、Python静态解析；正文引用另作语义核查'})

sealed=0
for group in ['植物运行','调试释放']:
    m=read(B/'证据'/group/'交付清单.json')
    for row in m['files']:
        p=Path(row['path']); assert sha(p)==row['sha256'],str(p)
        sealed+=1
ok('任务4修订后及任务5交付清单',sealed)
review5=read(B/'证据/否证/任务5/审查输入指纹.json')
review_bound=0
for row in review5['files']:
    p=Path(row['path'])
    assert sha(p)==row['sha256'],str(p)
    review_bound+=1
find5=read(B/'证据/否证/任务5/结构化结果.json')['findings']
assert Counter(x['verdict'] for x in find5)=={'否证不成立':20,'无法判定':4}
ok('任务5已交独立否证绑定',{'files':review_bound,'verdicts':dict(Counter(x['verdict'] for x in find5))})

plant=read(B/'送料与接口.json')
assert plant['schema']=='plant-pilot-v2'
assert sum(len(c['machines']) for c in plant['candidates'])==438
assert sum(len(c['feeds']) for c in plant['candidates'])==629
for c in plant['candidates']:
    assert all(x['coordinates'] is None for x in c['machines'])
    assert all(x['proven_actual_rate_per_tick'] is None for x in c['feeds'])
assert plant['inventory']['荞花']['ordinary_seeds']==1150
assert plant['inventory']['砂叶']['ordinary_seeds']==2150
assert plant['inventory']['荞花']['ordinary_seeds_normal_recipe_slots']==850
assert plant['inventory']['砂叶']['ordinary_seeds_normal_recipe_slots']==1600
ok('候选接口范围',{'machines':438,'feeds':629,'coordinates':'尚未提供','actual_rates':'均未认证'})

# 独立从所有边界端口生成局部通道，不从internal_channels推邻接。
geom=read(B/'证据/植物运行/局部结构.json')
delta={'N':(0,1),'S':(0,-1),'E':(1,0),'W':(-1,0)}
opp={'N':'S','S':'N','E':'W','W':'E'}
def edge_cells(u,d):
    x,y,w,h=u['x'],u['y'],u.get('w',1),u.get('h',1)
    if d=='N': return [(a,y+h-1) for a in range(x,x+w)]
    if d=='S': return [(a,y) for a in range(x,x+w)]
    if d=='E': return [(x+w-1,a) for a in range(y,y+h)]
    return [(x,a) for a in range(y,y+h)]
geometry_results=[]
for species,g in geom.items():
    units=g['machines']+g['belts']; all_units=units+g['power']
    occupied={}
    for u in all_units:
        for x in range(u['x'],u['x']+u.get('w',1)):
            for y in range(u['y'],u['y']+u.get('h',1)):
                assert 0<=x<70 and 0<=y<70 and (x,y) not in occupied
                occupied[x,y]=u['id']
    inputs={}
    for u in units:
        for x,y in edge_cells(u,u['input']): inputs[x,y,u['input']]=u['id']
    channels=[]; types={u['id']:u.get('kind','传送带') for u in units}
    for u in units:
        d=u['output']; dx,dy=delta[d]
        for x,y in edge_cells(u,d):
            v=inputs.get((x+dx,y+dy,opp[d]))
            if v is not None:
                assert types[u['id']]=='传送带' or types[v]=='传送带'
                channels.append((u['id'],v))
    assert sorted(channels)==sorted(map(tuple,g['internal_channels']))
    machine_checks=[]
    for u in g['machines']:
        peers=[v for a,v in channels if a==u['id']]
        assert all(types[v]=='传送带' for v in peers)
        machine_checks.append({'unit':u['id'],'kind':u['kind'],'all_output_peers':peers,'output_levels':1,'PA-01':True})
    assert not any(t in ['分流器','汇流器','协议储存箱'] for t in types.values())
    geometry_results.append({'species':species,'transport_slots':len(g['belts']),'actual_channels_checked':len(channels),'machines':machine_checks,'PA-02':True,'PA-03':'无箱','scope':g['coordinates_scope']})
write('设计律核查.json',{'local_instances':geometry_results,'full_AB_realization':'未提供实际几何，保持待核','direction':'局部结构定理前件检查'})
ok('两份局部全部共边通道及三规矩',geometry_results)

# 配方精确算术：从R解析18条配方，复算PA-11的消元，不假定目标率。
lines=(ROOT/'《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
recipes=[]
current_kind=None
for lineno,line in enumerate(lines,1):
    if line.strip() in ['粉碎机','精炼炉','研磨机','塑形机','配件机','种植机','采种机','封装机','灌装机']:
        current_kind=line.strip()
    match=re.fullmatch(r'(.*?) → (.*?)，(\d+) tick',line.strip())
    if match:
        def side(s):
            return {item:int(q) for q,item in re.findall(r'(\d+) ([^＋]+?)(?= ＋|$)',s)}
        recipes.append({'line':lineno,'kind':current_kind,'input':side(match[1]),'output':side(match[2]),'duration':int(match[3])})
assert len(recipes)==18
b=F(3,5); g=F(32)-F(16); c=(g-F(25,3)*b)/20
assert c==F(11,20)
assert F(30)*b+60*c==51
assert 18+34+F(11,2)+F(21,2)==68
assert 50*b+40*c==52
# 该表仅检验零泄漏配方稳态账中的系数。
for bb,cc,rr in [(F(3,5),F(11,20),F(0)),(F(1,2),F(2,5),F(1,7)),(F(0),F(0),F(3))]:
    raw_iron=20*bb+40*cc; steel=10*bb+20*cc
    seed_powder_need=25*bb+30*cc
    flower_crush=10*cc; sand_crush=seed_powder_need/3
    assert flower_crush+sand_crush==F(25,3)*bb+20*cc
    assert raw_iron+steel+rr==30*bb+60*cc+rr
# 另一路从正式配方的全内部物种平衡矩阵求解，不使用上述手写系数。
all_items=set().union(*(set(r['input'])|set(r['output']) for r in recipes))
internal=sorted(all_items-{'蓝铁矿','源矿','高容谷地电池','精选荞愈胶囊'})
rows=[]
for item in internal:
    rows.append([F(r['output'].get(item,0)-r['input'].get(item,0)) for r in recipes]+[F(0)])
minima={'粉碎机':68,'精炼炉':51,'配件机':6,'种植机':32,'采种机':16,'封装机':3}
for kind,n in minima.items():
    rows.append([F(r['duration'] if r['kind']==kind else 0) for r in recipes]+[F(n)])
def solve_unique(matrix,n):
    a=[r[:] for r in matrix]; pivot_row=0; pivots=[]
    for col in range(n):
        q=next((q for q in range(pivot_row,len(a)) if a[q][col]),None)
        if q is None:continue
        a[pivot_row],a[q]=a[q],a[pivot_row]
        scale=a[pivot_row][col];a[pivot_row]=[v/scale for v in a[pivot_row]]
        for j in range(len(a)):
            if j!=pivot_row and a[j][col]:
                scale=a[j][col];a[j]=[x-scale*y for x,y in zip(a[j],a[pivot_row])]
        pivots.append(col);pivot_row+=1
    assert not any(all(v==0 for v in row[:n]) and row[n]!=0 for row in a)
    assert len(pivots)==n
    x=[F(0)]*n
    for j,col in enumerate(pivots): x[col]=a[j][n]
    assert all(sum(row[i]*x[i] for i in range(n))==row[n] for row in matrix)
    return x
rates=solve_unique(rows,len(recipes))
by_line={r['line']:rate for r,rate in zip(recipes,rates)}
assert by_line[111]==F(3,5) and by_line[114]==F(11,20) and by_line[89]==0
assert all(rate>=0 for rate in rates)
# 219候选窄式：只施加精炼51、封装3与R89=0，配方全平衡仍给相同率。
rows219=rows[:len(internal)]
for kind,n in [('精炼炉',51),('封装机',3)]:
    rows219.append([F(r['duration'] if r['kind']==kind else 0) for r in recipes]+[F(n)])
rows219.append([F(r['line']==89) for r in recipes]+[F(0)])
rates219=solve_unique(rows219,len(recipes))
assert rates219==rates
ok('正式配方全内部物种矩阵独立消元',{'recipes':len(recipes),'internal_items':len(internal),'rank':len(rates),'D_rows':len(rows),'219_rows':len(rows219),'rates_by_rule_line':{str(k):str(v) for k,v in by_line.items()}})
ok('18条正式配方与连续制造反向收支',{'battery':str(b),'plant_crush':str(g),'capsule':str(c),'r_bound_at_minima':'0'})

# 单门样本是PA-07前件中的工作过程，不是全厂模拟器。
def saturate(k,t0,history,n=30):
    history=list(map(F,history)); t0=F(t0)
    if history:
        assert history[0]==0 and all(v<5 for v in history)
        assert len(history)<=k and all(b-a>=1 for a,b in zip(history,history[1:]))
        assert history[-1]<=t0
        start=F(0); used=len(history); last=history[-1]
    else: start=None; used=0; last=t0-1
    out=[]
    while len(out)<n:
        t=max(t0,last+1)
        if start is not None and t>=start+5: start=None; used=0
        if start is not None and used>=k:
            t=max(t,start+5); start=None; used=0
        if start is None: start=t; used=0
        used+=1; assert used<=k
        out.append(t); last=t
    return out
sample_rows=[]
for k in range(1,5):
    histories=[[],[F(0)]]
    if k>=2: histories += [[F(0),F(4)],[F(0),F(4,3)]]
    if k>=3: histories += [[F(0),F(1),F(7,2)]]
    if k>=4: histories += [[F(0),F(1),F(2),F(13,3)]]
    for h in histories:
        for delay in [F(0),F(1,3),F(2)]:
            t0=(h[-1] if h else F(0))+delay
            a=saturate(k,t0,h)
            for j,t in enumerate(a): assert t<=t0+6+5*(j//k)+(j%k)
            for T in range(0,31):
                count=sum(t<=t0+T for t in a)
                lower=k*(max(T-6,0)//5)
                # a只有30项；T<=30时需求上界<=20项。
                assert count>=lower
            sample_rows.append({'k':k,'t0':str(t0),'old_accepts':list(map(str,h)),'new_accepts':list(map(str,a[:12])),'bound_checked_items':len(a)})
# k=5的不额外阻断：第五件可在窗内，第六件最早last+1>=5。
for gaps in [[F(1)]*4,[F(7,6)]*4,[F(1),F(1),F(1),F(3,2)]]:
    t=[F(0)]
    for d in gaps:t.append(t[-1]+d)
    assert t[-1]<5 and t[-1]+1>=5
# 原有不滑动窗口例。
a=[0,4,5,6]; assert len([t for t in a if 0<=t<5])==2
assert len([t for t in a if 5<=t<10])==2
assert len([t for t in a if 4<=t<9])==3
write('窗口与算术.json',{'recipes':recipes,'reverse_balance':{'b':str(b),'g':str(g),'c':str(c),'refining_formula':'30*b+60*c+r','plant_formula':'25*b/3+20*c'},'gate_samples':sample_rows,'sample_scope':'单门合法旧窗口、单一持续备货、恰1tick排空；只查界的算术','k5_global_graph_elimination_proved':False})
ok('k<5单门界样本',{'cases':len(sample_rows),'item_bounds':sum(x['bound_checked_items'] for x in sample_rows)})

# 状态删除的守卫/更新恒等式查错。
for age in [F(0),F(1,3),F(1),F(5),F(1000)]:
    r=max(F(0),1-age)
    assert (age>=1)==(r==0)
    for dt in [F(0),F(1,7),F(1),F(8)]:
        assert max(F(0),1-age-dt)==max(F(0),r-dt)
for C in [1,2,5,5000]:
    for n in [0,1,C-1,C,C+1,C+100]:
        assert (n<C)==(min(n,C)<C)
        if n<C: assert min(n+1,C)==min(min(n,C)+1,C)
# 5tick相位差，仅连续机器样本；不替代供料证明。
for phase in [F(0),F(1,3),F(9,2)]:
    for t in [F(0),F(1),F(5),F(101,3)]:
        cnt=lambda p: sum(F(0)<p+5*j<=t for j in range(-2,10))
        assert abs(cnt(phase)-cnt(F(0)))<=1
ok('成熟年龄、累计饱和及连续5tick相位算术','exact Fraction checks')

# 直接链工作表反例检查：一次正向扫描漏掉能同刻移动的旧件。
initial=[1,1,0] # 1为本刻前已成熟，2为本刻新到（不能再前移）
def sweep(s):
    s=list(s); changes=0
    for i in range(len(s)-1):
        if s[i]==1 and s[i+1]==0: s[i]=0;s[i+1]=2;changes+=1
    return s,changes
one,_=sweep(initial); assert one==[1,0,2]
closed=list(initial); passes=0
while True:
    closed,n=sweep(closed);passes+=1
    if n==0:break
assert closed==[0,2,2] and passes==3
ok('直接链必须重新尝试旧货',{'single_sweep':one,'closure':closed,'passes':passes,'scope':'三个带格的物料闭包，不含双端争用'})

# 固定参数与逐步换参的证据方向逻辑例。
f={0:{'x':('y',0),'y':('y',1)},1:{'x':('x',1),'y':('x',0)}}
assert f[0]['x']==('y',0) and f[1]['y']==('x',0)
assert all(not (f[p]['x']==('y',0) and f[p]['y']==('x',0)) for p in f)
ok('逐步换固定参数的坏环不能直接还原','抽象两状态逻辑例；不是游戏反例')

state=read(E/'状态与参数.json')
assert state['status']=='partial' and state['full_layout_certified'] is False
assert len(state['claims'])==12 and len(state['open_items'])==9
assert state['for_owner']==[] and state['certificate_instantiated'] is False
assert state['rule_sha256']==sha(ROOT/'《明日方舟：终末地》游戏规则.txt')
links=[]
for name in ['相位离线与认证范围.md','规格修改稿-任务6.md']:
    p=B/name
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        if '://' not in target and not target.startswith('#'):
            q=(p.parent/target.split('#')[0]).resolve()
            # 核验结果与日志由当前命令最终创建。
            if q not in [E/'核验结果.json',E/'核验.log']:
                assert q.exists(),str(q)
            links.append(str(q))
ok('交付状态与引用',{'links':len(links),'claims':12,'open_items':9})

result={'status':'PASS','exit_status':0,'command':'python -B '+str(E/'核验.py'),'checks':checks,'input_files_unchanged':len(manifest),'upstream_sealed_files_checked':sealed,'task5_review_files_matched':review_bound,'scope':'作者条件证明查错；未运行游戏内核，未全参数扫描，非独立复核或整厂认证','L':0,'U':1113}
write('核验结果.json',result)
print(json.dumps({'status':'PASS','checks':len(checks),'input_files_unchanged':len(manifest),'upstream_sealed_files_checked':sealed,'gate_cases':len(sample_rows),'L':0,'U':1113},ensure_ascii=False))
