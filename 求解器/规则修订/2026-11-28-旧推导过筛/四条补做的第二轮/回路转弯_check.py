#!/usr/bin/env python3
"""独立复核「回路转弯」的数值与几何下界（只读，不改仓库）。"""
from fractions import Fraction as F
from itertools import product
import heapq

print("== 1. 物料流量（由配方与目标产率复算） ==")
bat, cap = F(3,5), F(11,20)            # 电池 0.6/tick，胶囊 0.55/tick
parts, bottles = 10*bat, 10*cap        # 钢制零件 6，钢质瓶 5.5
steel = parts + 2*bottles              # 钢块 17
dense_fe = steel                       # 致密蓝铁粉末 17
dense_src = 15*bat                     # 致密源石粉末 9
fine_q = 10*cap                        # 细磨荞花粉末 5.5
sand_powder = dense_fe + dense_src + fine_q   # 砂叶粉末 31.5
q_powder = 2*fine_q                    # 荞花粉末 11
q_crush = q_powder/2                   # 荞花粉碎 5.5 株
s_crush = sand_powder/3                # 砂叶粉碎 10.5 株
# 仓库不供种子/植株（取货口配置）且无入库：采种=粉碎，种植=2×采种
q_seed, s_seed = q_crush, s_crush
q_plant, s_plant = 2*q_seed, 2*s_seed
seed_out = 2*(q_seed+s_seed)           # 采种机输出种子
plant_out = q_plant + s_plant          # 种植机输出植株
crush_plant = q_crush + s_crush
print(f"钢块={steel} 砂叶粉末={sand_powder} 荞花粉碎={q_crush} 砂叶粉碎={s_crush}")
print(f"采种批 {q_seed}+{s_seed}={q_seed+s_seed}, 种植批 {q_plant}+{s_plant}={plant_out}")
print(f"种子输出 {seed_out}/tick, 植株输出 {plant_out}/tick, 粉碎植株 {crush_plant} 批/tick")
assert (seed_out, plant_out, crush_plant) == (32, 32, 16)

print("\n== 2. 少于 4 次转弯的闭合方向序列 ==")
# 方向 0=E 1=N 2=W 3=S；任何单位内部都不能掉头（传送带进出不同边、分流/汇流器唯一口对其余三边、
# 桥接器/准入口/方形单位直行），压缩后的循环方向串相邻两项差 ±1 (mod 4)。
for k in range(0,4):
    sets=set()
    if k==0:
        sets={frozenset([d]) for d in range(4)}
    else:
        for w in product(range(4),repeat=k):
            ok=all((w[(i+1)%k]-w[i])%4 in (1,3) for i in range(k))
            if ok: sets.add(frozenset(w))
    adj = all(len(s)==1 or (len(s)==2 and (max(s)-min(s))%4 in (1,3)) for s in sets)
    print(f"k={k}: 可行压缩串的方向集合 {sorted(map(sorted,sets))}  全在两相邻方向内={adj}")
    assert adj

print("\n== 3. 势 φ=d1+d2 的最小增量（端口中点坐标） ==")
def unit_increments(q, turn_ok):
    """q×q 单位，入方向 E（从西边入），出口在东边（直行）或北/南边（转弯，仅1×1运输单位）。
    返回在每个相邻方向对 {E,N},{E,S} 势下的最小增量。"""
    res={}
    for d2 in (1,3):                     # 势方向 E+N 或 E+S
        sgn = 1 if d2==1 else -1
        best=None
        for yi in range(q):              # 入口端口所在格
            pin=(0.0, yi+0.5)
            outs=[(float(q), yo+0.5, 0) for yo in range(q)]   # 东边直行
            if turn_ok:
                outs.append((0.5, 1.0, 1))   # 1×1 左转向北
                outs.append((0.5, 0.0, 3))   # 1×1 右转向南
            for x,y,dout in outs:
                if dout not in (0,d2): continue   # 只允许势的两个方向
                inc=(x-pin[0]) + sgn*(y-pin[1])
                best=inc if best is None else min(best,inc)
        res[d2]=best
    return res
r1=unit_increments(1,True); r3=unit_increments(3,False); r5=unit_increments(5,False)
print("1×1 运输单位:",r1," 3×3 储存箱:",r3," 5×5 种植/采种机:",r5)
assert min(r1.values())>=1 and min(r3.values())>=1 and min(r5.values())>=1
# 从北向入的情形由对称性相同；转弯 N->E 的增量同为 1
print("故 <4 次转弯时势每过一单位至少 +1，回路不能闭合")

print("\n== 4. 松弛网格上的最少转弯闭合回路（不计重叠，只作合理性检查） ==")
D=[(2,0),(0,2),(-2,0),(0,-2)]        # 坐标乘 2，端口中点为整数
def moves(pos,d):
    x,y=pos; dx,dy=D[d]; px,py=-dy//2,dx//2  # 左法向(单位)
    # 1×1 运输单位：直行或左右转
    yield (x+dx,y+dy),d,0
    for nd in ((d+1)%4,(d+3)%4):
        ndx,ndy=D[nd]; yield (x+dx//2+ndx//2, y+dy//2+ndy//2),nd,1
    for q in (3,5):
        for lat in range(-(q-1),q):
            yield (x+q*dx+lat*2*px, y+q*dy+lat*2*py),d,0
B=40
start=((0,0),0)
dist={start:0}; pq=[(0,start)]; best=None
while pq:
    c,(p,d)=heapq.heappop(pq)
    if c>dist.get((p,d),99): continue
    for np_,nd,t in moves(p,d):
        if abs(np_[0])>B or abs(np_[1])>B: continue
        st=(np_,nd); nc=c+t
        if st==start:                       # 闭合回到起点端口且同向
            best=nc if best is None else min(best,nc); continue
        if nc<dist.get(st,99):
            dist[st]=nc; heapq.heappush(pq,(nc,st))
print("回到起始端口且同向的最少转弯数 =",best)
assert best==4

print("\n== 5. 桥接器同轴两向不能同时有周期正流量 ==")
# 链端外邻非桥单位的那段边只能是 无端口/存货端口/取货端口 之一
types=["none","storage","pickup"]
ok=True
for X,Y in product(types,repeat=2):
    east = (X=="pickup" and Y=="storage")   # 向东：X 供入 B1，Bk 交给 Y
    west = (Y=="pickup" and X=="storage")
    if east and west: ok=False
print("所有链端组合下两向都正：", not ok, "→ 每轴至多 1 件/tick，每桥至多 2 件/tick")
assert ok
# 单格：每件停满 8 步才能移出，同步可补进下一件 → N 步内至多 N/8 次收货
for N in (160,320,480):
    t=0;cnt=0
    while t<N: cnt+=1; t+=8
    assert cnt==N//8
print("单格每 tick 至多收 1 件：核对通过")

print("\n== 6. 整数下界 ==")
best=min((T,b) for T in range(0,200) for b in range(0,T+1) if T-b>=4 and T+b>=64)
print("min T植 s.t. T−b≥4, T+b≥64:",best)
alt=min((T,b) for T in range(0,200) for b in range(0,T+1) if T-b>=4 and T+3*b>=64)
print("若只按桥 4 格计容量 (T+3b≥64) 只得:",alt)
assert best==(34,30)
plant_m, seed_m = int(plant_out), int(q_seed+s_seed)   # 每台每 tick ≤1 批
crush_m = int(crush_plant)
area = (plant_m+seed_m)*25 + crush_m*9 + best[0]
print(f"占格 ({plant_m}+{seed_m})×25 + {crush_m}×9 + {best[0]} = {area}")
assert area==1378
print("\n全部核对通过")
