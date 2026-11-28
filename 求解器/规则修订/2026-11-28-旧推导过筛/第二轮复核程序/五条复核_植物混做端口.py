#!/usr/bin/env python3
"""第二轮独立复核：植物再生来路、混做清空、混做连续批次出货、植物沿途存量、运输端口收支 的数字。
配方从现行规则正文解析。用法: python3 本文件 <游戏规则.txt>"""
import re, sys
from fractions import Fraction as F
from math import ceil
text = open(sys.argv[1], encoding="utf-8").read()
sec = text.split("\n配方\n", 1)[1]
rec = []
for line in sec.strip().splitlines():
    line = line.strip()
    if "：" not in line: continue
    mach, body = line.split("：", 1)
    for part in body.split("；"):
        m = re.match(r"(.+?)\s*→\s*(\d+)\s*(\S+?)，\s*(\d+)\s*tick", part.strip())
        ins = {}
        for t in m.group(1).split("＋"):
            mm = re.match(r"\s*(\d+)\s*(\S+)\s*", t); ins[mm.group(2)] = int(mm.group(1))
        rec.append((mach, ins, m.group(3), int(m.group(2)), int(m.group(4))))
assert len(rec) == 18
# 需求倒推（r=0：不把蓝铁粉末炼回蓝铁块）
need = {"高容谷地电池": F(3,5), "精选荞愈胶囊": F(11,20)}
batch = {}  # (mach,out) -> 批/tick
def prod(item, q):
    rs = [r for r in rec if r[2] == item and not (r[0]=="精炼炉" and "蓝铁粉末" in r[1])]
    assert len(rs) == 1, item
    mach, ins, out, n, d = rs[0]
    b = F(q, n); batch[(mach,out)] = batch.get((mach,out),0)+b
    for i,a in ins.items():
        if i in ("源矿","蓝铁矿"): need[i]=need.get(i,0)+a*b; continue
        if i.endswith("种子"):  # 种子由采种回路自给，单独处理
            continue
        prod(i, a*b)
for k in list(need): prod(k, need[k]) if k in ("高容谷地电池","精选荞愈胶囊") else None
# 植物回路：粉碎用量 f，采种 a=f（非成品零入库），种植 z=2a
for p in ("荞花","砂叶"):
    f = batch.pop(("种植机",p))  # prod() 把粉碎所需植株记在种植机名下，先取出
    a = f; z = 2*a
    batch[("采种机",p+"种子")] = a; batch[("种植机",p)] = z
    print(f"{p}: 粉碎 f={f} 采种 a={a} 种植 z={z}; 沿途存量下界(每件至少过1个运输格): 种子 z+Q_s>= {z+z}, 植株 a+f+Q_p>= {a+f+z}")
# 逐机型进、出件率
inr, outr = {}, {}
for (mach,out), b in batch.items():
    r = [x for x in rec if x[0]==mach and x[2]==out][0]
    inr[mach] = inr.get(mach,0) + b*sum(r[1].values())
    outr[mach] = outr.get(mach,0) + b*r[3]
order = ["粉碎机","精炼炉","研磨机","塑形机","配件机","种植机","采种机","封装机","灌装机"]
sin = [ceil(inr[m]) for m in order]; sout = [ceil(outr[m]) for m in order]
print("存货通道下限", dict(zip(order,sin)), "合计", sum(sin))
print("取货通道下限", dict(zip(order,sout)), "合计", sum(sout))
cap5 = F(1,5)  # 5 tick 配方每台至多 1/5 批/tick
n_feng = ceil(F(3,5)/cap5); n_guan = ceil(F(11,20)/cap5)
ore_ports = 2*(70//3) + 6
S = sum(sout) - 2 + n_feng + n_guan + ore_ports
R = sum(sin) + ceil(F(3,5)+F(11,20))
print(f"封装机>={n_feng} 灌装机>={n_guan} 矿口={ore_ports} => S>={S}, R>={R}")
# 混做：每 tick 一批 = 每 8 步一批；同一运输格相邻两次接收至少隔 8 步
def max_recv(window_steps, gap=8):
    # 窗口内可用步 1..window_steps，贪心从第 1 步起每 gap 步一件
    return len(range(1, window_steps+1, gap))
print("混做连续批次: m, 砂叶需求3m, 现行两口容量, 旧式两口容量 2(m+1)")
for m in range(1,5):
    print(" ", m, 3*m, 2*max_recv(8*m), 2*(m+1))
for kx,ky,name in [(3,2,"砂叶-荞花"),(3,1,"砂叶-单件"),(2,1,"荞花-单件"),(2,2,"采种机")]:
    print(f"严格交替 {name}: 条文下界 ceil((kx+ky)/2)={ceil(F(kx+ky,2))}, 现行窗口实得下界 max(kx,ky)={max(kx,ky)}")
# 采种机分去两台种植机
for a in (F(1,2), F(51,100), F(1)):
    print(f"采种机批率 a={a}: 种子 {2*a}/tick, 单台种植机至多 1/tick => 至少 {ceil(2*a)} 台种植机")
# 桥接器一条轴：两端非桥单位朝向该轴的那段边只能是 存/取/无 之一
ends = ["存","取","无"]
both = [(L,Rr) for L in ends for Rr in ends if (L=="取" and Rr=="存") and (Rr=="取" and L=="存")]
print("桥轴两方向同时有正流的端点组合数:", len(both))
