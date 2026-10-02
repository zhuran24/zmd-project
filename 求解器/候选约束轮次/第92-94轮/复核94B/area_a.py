#!/usr/bin/env python3
"""复核94B 面积算术编码甲：按条文逐项用有理数算式推，不做穷举。"""
import json, sys
from fractions import Fraction as Fr
from math import ceil, floor

out = {}
# 机型下限台数与占地（快照规则第 44-58 行的尺寸；求解约束「机型下限」的台数）
cnt = dict(粉碎机=68, 精炼炉=51, 研磨机=32, 塑形机=6, 配件机=6, 种植机=32, 采种机=16, 封装机=3, 灌装机=3)
size = dict(粉碎机=9, 精炼炉=9, 配件机=9, 塑形机=9, 种植机=25, 采种机=25, 研磨机=24, 封装机=24, 灌装机=24)
mach = sum(cnt[k] * size[k] for k in cnt)
out["机身占地"] = mach
core, ports = 81, 46 * 3
out["T+F+E+A+4P"] = 4900 - mach - core - ports  # 1390

# 921 的组成：619 接口 + 184 矿石格方向 + 8 核心切向 + 109 权重 − 91(N+w 上界) + 88 内带 + 4 q
store = 68 + 51 + 95 + 11 + 6 + 32 + 16 + 15 + 11
pick = 95 + 51 + 32 + 6 + 6 + 32 + 32 + 1 + 1
iface = store + (pick + 4) + 52 + 2
out["存货通道"] = store
out["取货通道"] = pick
out["接口"] = iface
c921 = iface + 184 + 8 + 109 - 91 + 88 + 4
out["921"] = c921
out["4T>=(无箱,不含内带)"] = iface + 184 + 8 + 109 - 91
out["T>=无箱"] = ceil(Fr(iface + 184 + 8 + 109 - 91, 4))
K = out["T+F+E+A+4P"]
# 4(T+F)+2P>=921, T+F = K - A - 4P - E  =>  4A+16P+4E-2P <= 4K-921
out["4A+14P<="] = 4 * K - c921
out["4A+16P-2J+X+Y<="] = 4 * K - c921
# A+4P<=K-208
out["A+4P<="] = K - 208
# A=1110 的桩数与 J
A = 1110
rhs = 4 * K - c921 - 4 * A  # 16P-2J+X+Y<=rhs
out["16P-2J+X+Y<=(A=1110)"] = rhs
pj = {}
for P in range(10, 20):
    Jmax = min(P, floor(Fr(23 * P - 217, 10)), floor(Fr(54 * P - 520, 25)))
    # 需要 2J >= 16P - rhs + (X+Y)，X+Y>=0
    Jneed = ceil(Fr(16 * P - rhs, 2))
    pj[P] = dict(Jmax=Jmax, Jneed_if_XY0=max(Jneed, 0), feasible=max(Jneed, 0) <= Jmax,
                 XY_max_formula=f"X+Y<=2J+{rhs - 16 * P}")
out["P,J(A=1110)"] = pj
# 也核不含周边项的 4A+14P<=4639 在 A=1110 给出的 P 上界
out["P<=(4A+14P)"] = floor(Fr(4 * K - c921 - 4 * A, 14))
# 矩形离带：a=2 时 H<=9、W<=68；a=3 时 H<=15、W<=67；对 b 同理
out["a=2最大面积"] = 9 * 68
out["a=3最大面积"] = 15 * 67
# 合法尺寸：短边>=6、两边<=66（面积>1005 时）
legal = {}
for area in range(1100, 1114):
    fs = [(w, area // w) for w in range(6, 67) if area % w == 0 and 6 <= area // w <= 66 and w <= area // w]
    legal[area] = fs
out["1100-1113合法尺寸"] = legal
# 方向预算 Ω 在最低配置
f研 = Fr(379 - 8 * 32, 2); f塑 = max(0, 22 - 2 * 6); f封 = 24; f灌 = 14
out["Ω最低"] = str(f研 + f塑 + f封 + f灌)
# A=1110 时的增配排除（方向预算：4A+16P-2J+4E+Ω+X0+Y0<=4751）
lim = 4751 - 4 * A
inc = {"塑形机": 34, "粉碎机/精炼炉/配件机/协议储存箱": 36}
res = {}
for P in range(10, 14):
    Jmax = min(P, floor(Fr(23 * P - 217, 10)), floor(Fr(54 * P - 520, 25)))
    Jmin = 0
    best = lim - 16 * P + 2 * Jmax  # 4E+Ω+X0+Y0 的允许上界（J 取最大）
    res[P] = {k: str(best - (f研 + f塑 + f封 + f灌) - v) for k, v in inc.items()}
out["A=1110单增配后X0+Y0上界(按P)"] = res
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "area_a.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
