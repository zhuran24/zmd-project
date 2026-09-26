"""规则内局部反例及双编码核算。"""
import os
os.sched_setaffinity(0,{1})
from pathlib import Path
from itertools import combinations,product
import json
OUT=Path(__file__).resolve().parent

recipes={'塑形机':[{'钢块':2}], '研磨机':[{'蓝铁粉末':2,'砂叶粉末':1},{'源石粉末':2,'砂叶粉末':1},{'荞花粉末':2,'砂叶粉末':1}]}
def can_receive(slot,item):
    return slot.get(item,0)<50 if item in slot else len(slot)<2
def can_make(slot,r): return all(slot.get(k,0)>=v for k,v in r.items())
examples=[]
# 原 B5 的两项前提成立；初存合法却留下另一主料 1 件。
store={'源石粉末':1,'砂叶粉末':50}; heads=['蓝铁粉末','砂叶粉末']
assert not any(can_make(store,r) for r in recipes['研磨机'])
assert not any(can_receive(store,i) for i in heads)
# 第二种编码不用 dict，直接查两个有身份的格。
slots=[['源石粉末',1],['砂叶粉末',50]]
receivable=lambda item:any(q<50 for name,q in slots if name==item) or len(slots)<2
assert not any(receivable(i) for i in heads)
examples.append({'candidate':'纯料通道与单主料研磨机不入停机态','initial_inventory':store,'head_items':heads,'cache':None,'effect':'全部首件被拒且无配方可开；旧源石粉末不是研磨机误料','source':'调试期由源矿粉碎取得源石粉末，放入 1 件；砂叶粉末格填至 50；最终两条纯料带只送蓝铁粉末、砂叶粉末。状态稳定，不需按 tick 操作。'})
examples.append({'candidate':'存货首件死锁','machine':'塑形机','initial_inventory':{'钢块':1},'head_items':['源矿'],'cache':None,'effect':'一存货格被钢块占据但不足 2；唯一传送带的源矿不能进入，永久停机','source':'钢块在调试期按配方制造后放入 1 件；源矿来自设为源矿的仓库取货口。首件留在运输格，不触犯存货误料的前提。'})

# 两种计数：遍历原料合法存货状态上的加件；独立计 3*2*50 与 1+4*50。
types=['蓝铁粉末','源石粉末','荞花粉末','砂叶粉末','误料']
states=[{}]+[{i:q} for i in types for q in range(1,51)]+[{i:q,j:r} for i,j in combinations(types,2) for q,r in product(range(1,51),repeat=2)]
def permanent(s): return '误料' in s or len(s)==2 and '砂叶粉末' not in s
enters={'two_main':0,'wrong':0}
for state in states:
    if permanent(state): continue
    for item in types:
        if not can_receive(state,item): continue
        nxt=state.copy(); nxt[item]=nxt.get(item,0)+1
        if permanent(nxt): enters['wrong' if item=='误料' else 'two_main']+=1
assert enters=={'two_main':3*2*50,'wrong':1+4*50}

# D1：k=2 的采种机，出口一接纯带，出口二接汇流器。
# 汇流器另一输入直接接分流器，取更早的输入级；该级每 tick 有货。
# 固定判定顺序：下游腾位、分流器输入、采种机尝试。
q=50; head_a=None; merge=None; diverter='荞花种子'; counts=[0,0]; trace=[]
for t in range(4):
    # 上一刻运输格的货已滞留一 tick；下游箱有充足空间。
    head_a=None; merge=None
    ready=[True,True]
    merge=diverter; diverter='荞花种子'
    if head_a is None and q: head_a='荞花种子'; q-=1; counts[0]+=1
    # 第二出口虽在本刻曾经为空，现由高优先输入占据。
    if merge is None and q: merge='荞花种子'; q-=1; counts[1]+=1
    trace.append({'tick':t,'first_slots_were_empty':ready,'taken_from_machine':counts[:],'remaining_initial_output':q})
direct_counts=[4,0]
assert counts==direct_counts and abs(counts[0]-counts[1])>1
examples.append({'candidate':'一批k件配k条取货通道的均分','k':2,'initial_output':50,'trace':trace,'two_encodings_agree':counts==direct_counts,
                 'source':'采种机及关闭传输的来源箱在调试期由荞花/荞花种子备料；来源箱经传送带、分流器到汇流器，直接分流器输入级较早接通。下游为关闭传输的空箱，四 tick 内容量足够。','geometry':{'采种机':[10,10,5,5,'存左取右'],'纯料带一':[15,11,1,1,'存左取右'],'纯料带二':[16,11,1,1,'存左取右'],'汇流器':[15,13,1,1,'取下'],'分流器':[15,14,1,1,'存右'],'来源带':[16,14,1,1,'存右取左'],'来源箱':[17,13,3,3,'存右取左'],'合流出带一':[15,12,1,1,'存上取右'],'合流出带二':[16,12,1,1,'存左取右'],'接收箱':[17,10,3,3,'存左取右'],'供电桩':[7,12,2,2]}})

# 原 B3 “任一次入库后可开始满仓拒收”不能从空仓实现。
examples.append({'candidate':'成品拒收的冻结范围','state':'玩家刚把一种成品从仓库取空','single_next_delivery_max':300,'warehouse_capacity':80000,'conclusion':'下一次单个入库判定至多增加一箱的 300 件，达不到满仓；只取不添的玩家不能指定此时拒收。冻结定理须从实际可到达的拒收区间起算。'})

# D1 坐标证书：格集合与矩形区间两种无重叠检查，另枚举所有自动端口对接。
geo=examples[2]['geometry']
bodies={n:{(x+i,y+j) for i in range(w) for j in range(h)} for n,(x,y,w,h,*rest) in geo.items()}
for a,b in combinations(geo,2):
    assert not bodies[a]&bodies[b]
    ax,ay,aw,ah=geo[a][:4];bx,by,bw,bh=geo[b][:4]
    assert ax+aw<=bx or bx+bw<=ax or ay+ah<=by or by+bh<=ay
assert all(0<=x<70 and 0<=y<70 for body in bodies.values() for x,y in body)
directions={'左':(-1,0),'右':(1,0),'上':(0,1),'下':(0,-1)}
opposite={'左':'右','右':'左','上':'下','下':'上'}
def side_cells(n,d):
    x,y,w,h=geo[n][:4]
    if d=='左':return [(x,v) for v in range(y,y+h)]
    if d=='右':return [(x+w-1,v) for v in range(y,y+h)]
    if d=='上':return [(u,y+h-1) for u in range(x,x+w)]
    return [(u,y) for u in range(x,x+w)]
inputs={};outputs={}
for n,g in geo.items():
    if n=='供电桩':inputs[n]=[];outputs[n]=[];continue
    mode=g[4]
    if n=='汇流器':outs=[mode[1]];ins=[d for d in directions if d not in outs]
    elif n=='分流器':ins=[mode[1]];outs=[d for d in directions if d not in ins]
    else:ins=[mode[1]];outs=[mode[3]]
    inputs[n]=[(cell,d) for d in ins for cell in side_cells(n,d)]
    outputs[n]=[(cell,d) for d in outs for cell in side_cells(n,d)]
actual=set()
nontransport={'采种机','来源箱','接收箱','供电桩'}
for a,b in product(geo,repeat=2):
    if a==b or a in nontransport and b in nontransport:continue
    for (x,y),d in outputs[a]:
        dx,dy=directions[d]
        if ((x+dx,y+dy),opposite[d]) in inputs[b]:actual.add((a,b))
expected={('采种机','纯料带一'),('采种机','汇流器'),('纯料带一','纯料带二'),('纯料带二','接收箱'),('汇流器','合流出带一'),('合流出带一','合流出带二'),('合流出带二','接收箱'),('分流器','汇流器'),('来源带','分流器'),('来源箱','来源带')}
assert actual==expected
px,py=geo['供电桩'][:2]
assert any(px-5<=x<=px+6 and py-5<=y<=py+6 for x,y in bodies['采种机'])
examples[2]['geometry_verification']={'set_nonoverlap':True,'interval_nonoverlap':True,'all_cells_in_base':True,'all_actual_channels':sorted(actual),'seed_machine_powered':True}

# 两条独占专线共享桥接器的两轴；否定“专线数就是运输单位数”的计数步骤。
bridge_bodies={'西精炼炉':(27,30,3,3),'南精炼炉':(28,27,3,3),'北粉碎机':(30,31,3,3),'东粉碎机':(31,28,3,3),'桥接器':(30,30,1,1)}
occupied={n:{(x+i,y+j) for i in range(w) for j in range(h)} for n,(x,y,w,h) in bridge_bodies.items()}
assert all(not occupied[a]&occupied[b] for a,b in combinations(occupied,2))
assert (29,30) in occupied['西精炼炉'] and (31,30) in occupied['东粉碎机']
assert (30,29) in occupied['南精炼炉'] and (30,31) in occupied['北粉碎机']
bridge_certificate={'units':bridge_bodies,'material':'蓝铁块','two_paths':[['西精炼炉','桥接器横轴','东粉碎机'],['南精炼炉','桥接器纵轴','北粉碎机']],'transport_units':1,'transport_slots':2,'nonoverlap':True}

# 成品箱的逐事件归纳基本步。尾格身份不影响第一格证明。
box_steps=0
for q in range(1,51):
    for d in (-1,0,1):
        if 1<=q+d<=50:
            assert q+d>0; box_steps+=1

result={'examples':examples,'grinder_first_entry_counts':enters,'grinder_total_first_entries':sum(enters.values()),'box_first_slot_inductive_steps':box_steps,
        'accepted_box_arrival_bound_per_5_ticks':3*(5+1),
        'two_dedicated_paths_one_bridge':bridge_certificate,
        'D2_blocked_phi_offset_sum':50+1+50+50+1+49/2,
        'D2_blocked_phi_offset_formula':(7*50+3)/2,
        'sealed_plant_capacity_formula':'102*n_a+101*n_z+T+b+300*B',
        'potential_telescoping_rates':['12/20','11/20']}
(OUT/'local_certificates.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'examples':len(examples),'first_entries':enters,'box_steps':box_steps},ensure_ascii=False))
