#!/usr/bin/env python3
# 矿石走廊 独立复算：a=4（走廊为第1..3列）时 m<=6、H<=21
# 记号：左下角格 (0,0)；左带仓库取货口在第0列；空矩形左列 a=4，行 b..b+H-1
from collections import deque
from itertools import product

N = 70
# ---------- 1. 配方对五物集合 M 的净变化 ----------
M = {"源矿","蓝铁矿","蓝铁块","蓝铁粉末","源石粉末"}
recipes = [  # (机器, 输入dict, 输出dict)
 ("粉碎机",{"源矿":1},{"源石粉末":1}),("粉碎机",{"蓝铁块":1},{"蓝铁粉末":1}),
 ("粉碎机",{"荞花":1},{"荞花粉末":2}),("粉碎机",{"砂叶":1},{"砂叶粉末":3}),
 ("精炼炉",{"蓝铁矿":1},{"蓝铁块":1}),("精炼炉",{"致密蓝铁粉末":1},{"钢块":1}),("精炼炉",{"蓝铁粉末":1},{"蓝铁块":1}),
 ("研磨机",{"蓝铁粉末":2,"砂叶粉末":1},{"致密蓝铁粉末":1}),("研磨机",{"源石粉末":2,"砂叶粉末":1},{"致密源石粉末":1}),
 ("研磨机",{"荞花粉末":2,"砂叶粉末":1},{"细磨荞花粉末":1}),
 ("塑形机",{"钢块":2},{"钢质瓶":1}),("配件机",{"钢块":1},{"钢制零件":1}),
 ("种植机",{"荞花种子":1},{"荞花":1}),("种植机",{"砂叶种子":1},{"砂叶":1}),
 ("采种机",{"荞花":1},{"荞花种子":2}),("采种机",{"砂叶":1},{"砂叶种子":2}),
 ("封装机",{"钢制零件":10,"致密源石粉末":15},{"高容谷地电池":1}),
 ("灌装机",{"钢质瓶":10,"细磨荞花粉末":10},{"精选荞愈胶囊":1}),
]
assert len(recipes)==18
size = {"粉碎机":(3,3),"精炼炉":(3,3),"配件机":(3,3),"塑形机":(3,3),
        "采种机":(5,5),"种植机":(5,5),"研磨机":(6,4),"封装机":(6,4),"灌装机":(6,4)}
other_units = {"协议储存箱":(3,3),"协议核心":(9,9),"供电桩(无端口)":(2,2),"仓库取货口(须贴左/下边界)":(3,1)}
print("== 1. 配方对 M={源矿,蓝铁矿,蓝铁块,蓝铁粉末,源石粉末} 的每批净变化 ==")
bad = []
for mach,i,o in recipes:
    net = sum(v for k,v in o.items() if k in M) - sum(v for k,v in i.items() if k in M)
    fits = min(size[mach]) <= 3
    if net != 0: print(f"  {mach}: {i}->{o}  净 {net:+d}  机身最窄 {min(size[mach])}  能整台放进/跨入3列: {fits}")
    if net < 0 and fits: bad.append((mach,i,o))
print("  其余配方 M 净变化均为 0")
print("  能放进3列且净消耗 M 的配方：", bad if bad else "无")
print("  最窄边<=3 的有端口单位：", [k for k,v in size.items() if min(v)<=3]+[k for k,v in other_units.items() if min(v)<=3])

# ---------- 2. 边带：左带端口行 ----------
def port_rows(d):
    k = d//3
    rows = [3*j+1 for j in range(k)]
    y = d+2
    while y <= 68: rows.append(y); y += 3
    assert len(rows)==23, (d,len(rows))
    return rows
D = list(range(0,70,3))
assert len(D)==24

# ---------- 3. 走廊内整台 3x3 的可放位置 ----------
print("\n== 3. 第1..3列中避开端口对接格 (1,p) 的整台 3x3 位置（行 y..y+2，y>=2） ==")
gap_ok = True
for d in D:
    P = set(port_rows(d))
    pos = [y for y in range(2,68) if not ({y,y+1,y+2} & P)]
    # 不重叠的最多台数
    cnt, last = 0, -10
    for y in pos:
        if y >= last+3: cnt += 1; last = y
    if cnt > 1 or (pos and not all(d-1 <= y <= d-1 for y in pos)):
        gap_ok = False
        print("  d=",d,"位置",pos)
print("  每种边带至多 1 台，且只能在空格两侧端口之间（行 d-1..d+1）：", gap_ok)

# ---------- 4. 割容量：最大流（松弛：格点容量不限，每条有向边容量1） ----------
def maxflow(H, srcs, top_open):
    # 节点: 走廊格 (x,y) x=1..3, y=0..H-1 ; S, T
    idx = {}
    for x in range(1,4):
        for y in range(H): idx[(x,y)] = len(idx)
    S = len(idx); T = S+1; n = T+1
    cap = [dict() for _ in range(n)]
    def add(u,v,c):
        cap[u][v] = cap[u].get(v,0)+c; cap[v].setdefault(u,0)
    for (x,y),u in idx.items():
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            q=(x+dx,y+dy)
            if q in idx: add(u,idx[q],1)
        if y==0: add(u,T,1)               # 下端割边（向外）
        if y==H-1 and top_open: add(u,T,1) # 上端割边
    for y in srcs: add(S, idx[(1,y)], 1)
    flow=0
    while True:
        par={S:None}; dq=deque([S])
        while dq and T not in par:
            u=dq.popleft()
            for v,c in cap[u].items():
                if c>0 and v not in par: par[v]=u; dq.append(v)
        if T not in par: return flow
        v=T
        while par[v] is not None:
            u=par[v]; cap[u][v]-=1; cap[v][u]+=1; v=u
        flow+=1

print("\n== 4. 逐边带、逐跨度：m、端数 e、最大流，求 H 上界 ==")
best = (0,None); best_m6 = (0,None); viol = []
mf_checked = 0
for d in D:
    P = port_rows(d)
    for b in range(2,70):
        for H in range(1,70-b+1):
            top = b+H-1
            m = sum(1 for p in P if b<=p<=top)
            e = 1 if top==69 else 2
            if m <= 6 and H > best_m6[0]: best_m6 = (H,(d,b,top,m,e))
            feas = m <= 3*e
            if H<=30 and (d%9==0) :
                f = maxflow(H,[p-b for p in P if b<=p<=top], top!=69)
                mf_checked += 1
                if f != min(m,3*e): viol.append((d,b,H,m,e,f))
            if feas and H > best[0]: best = (H,(d,b,top,m,e))
print("  最大流抽查跨度数：", mf_checked, " 与 min(m,3e) 不符：", viol[:5] if viol else "无")
print("  只用 m<=6 时最大 H =", best_m6[0], " 例 (d,b,顶行,m,e) =", best_m6[1])
print("  用 m<=3e（贴上边界 e=1）时最大 H =", best[0], " 例 =", best[1])
# 21 的实现例：含空格处间距4的窗口
ex=[]
for d in D:
    P=port_rows(d)
    for b in range(2,70):
        top=b+20
        if top>69: continue
        m=sum(1 for p in P if b<=p<=top)
        if m==6 and top!=69: ex.append((d,b,top)); break
print("  H=21、m=6 的窗口个数（每种边带取一例）：", len(ex), ex[:4])
# H=22 一律 m>=7（不贴上边界）或贴上边界时 m>=4
h22 = all((sum(1 for p in port_rows(d) if b<=p<=b+21) > (3 if b+21==69 else 6)) for d in D for b in range(2,70-21))
print("  H=22 的所有窗口都违反 m<=3e：", h22)
