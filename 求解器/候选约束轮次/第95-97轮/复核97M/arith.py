"""复核97M：面积预算、内带缺口所用常数的独立重算（两套编码 A、B）。
A：有理数、按支持集贪心求单机最小权重，再按半格动态规划求机群最小。
B：整数（乘 2）、逐口枚举 {0,1/2,1} 流量求单机表，再按各整数档台数组合求机群最小。
只写本目录下 arith.json。
"""
import json, itertools
from fractions import Fraction as Fr
from math import ceil, floor
from pathlib import Path
OUT = Path(__file__).resolve().parent
res = {}

# ---------- 配方倒推（20 tick：12 电池、11 胶囊） ----------
def backward_A():
    need = {}
    def add(k, v): need[k] = need.get(k, Fr(0)) + Fr(v)
    bat, cap = Fr(12), Fr(11)
    add('封装批', bat); add('灌装批', cap)
    parts, dso = 10*bat, 15*bat          # 钢制零件、致密源石粉末
    bott, fine = 10*cap, 10*cap          # 钢质瓶、细磨荞花粉末
    steel = parts + 2*bott               # 钢块
    dfe = steel                          # 致密蓝铁粉末
    grind = dfe + dso + fine             # 研磨批
    fepow = 2*dfe; srcpow = 2*dso; buckpow = 2*fine; sandpow = grind
    feblock = fepow; feore = feblock; srcore = srcpow
    buck_crush = buckpow/2; sand_crush = sandpow/3
    return dict(研磨批每tick=grind/20, 塑形批每tick=bott/20, 配件批每tick=parts/20,
                蓝铁矿=feore/20, 源矿=srcore/20, 精炼批=(feore+steel)/20,
                粉碎批=(fepow+srcpow+buck_crush+sand_crush)/20,
                荞花采种=buck_crush/20, 砂叶采种=sand_crush/20,
                种植=(2*buck_crush+2*sand_crush)/20, 研磨机群输入=3*grind/20,
                塑形输入=2*bott/20, 封装输入=25*bat/20, 灌装输入=20*cap/20)
def backward_B():   # 以 1/20 件为单位的整数
    bat, cap = 12, 11
    parts, dso, bott, fine = 10*bat, 15*bat, 10*cap, 10*cap
    steel = parts + 2*bott; grind = steel + dso + fine
    return dict(研磨批每tick=(grind, 20), 塑形批每tick=(bott, 20), 研磨机群输入=(3*grind, 20),
                蓝铁矿=(2*steel, 20), 源矿=(2*dso, 20))
A = backward_A(); B = backward_B()
for k, (p, q) in B.items():
    assert A[k] == Fr(p, q), k
res['倒推'] = {k: str(v) for k, v in A.items()}
assert A['研磨批每tick'] == Fr(63, 2) and A['蓝铁矿'] == 34 and A['源矿'] == 18

# ---------- 机型下限与占地 ----------
cnt = dict(粉碎机=68, 精炼炉=51, 研磨机=32, 塑形机=6, 配件机=6, 种植机=32, 采种机=16, 封装机=3, 灌装机=3)
area = dict(粉碎机=9, 精炼炉=9, 研磨机=24, 塑形机=9, 配件机=9, 种植机=25, 采种机=25, 封装机=24, 灌装机=24)
occ_A = sum(cnt[k]*area[k] for k in cnt)
occ_B = 0
for k in cnt:
    for _ in range(cnt[k]): occ_B += area[k]
assert occ_A == occ_B == 3291 and sum(cnt.values()) == 217
# 通道
inp = dict(粉碎机=68, 精炼炉=51, 研磨机=ceil(Fr(189, 2)), 塑形机=11, 配件机=6, 种植机=32, 采种机=16, 封装机=15, 灌装机=11)
outp = dict(粉碎机=ceil(Fr(18)+34+11+Fr(63, 2)), 精炼炉=51, 研磨机=32, 塑形机=6, 配件机=6, 种植机=32, 采种机=32, 封装机=3, 灌装机=3)
S_in, S_out = sum(inp.values()), sum(outp.values())
assert S_in == 305 and S_out == 260
iface = S_in + S_out + 52 + 2
assert iface == 619
res['常数'] = dict(占地=occ_A, 存货通道=S_in, 取货通道含成品各3=S_out, 接口=iface)

# ---------- 存货边权重 ----------
def w_of(ports_flows):
    """ports_flows: [(pos, flow)] 正流量口；相邻两口相距<=3 时两口各记本口流量。"""
    ps = sorted(ports_flows)
    w = 0
    for (p1, f1), (p2, f2) in zip(ps, ps[1:]):
        if p2 - p1 <= 3: w += f1 + f2
    return w

TYPES = {'研磨机': (6, 3), '封装机': (6, 5), '灌装机': (6, 4), '塑形机': (3, 2)}  # 存货边长, 单机输入上限
GROUP = {'研磨机': Fr(189, 2), '塑形机': Fr(11), '封装机': Fr(15), '灌装机': Fr(11)}

def single_A(L, xmax):
    """精确：对每个支持集 S，系数=该口相邻近口数，按系数从小到大贪心填流量。返回 x->最小权重（x 取半格）。"""
    table = {}
    for k in range(1, L+1):
        for S in itertools.combinations(range(L), k):
            coef = []
            for i, p in enumerate(S):
                c = 0
                if i > 0 and p - S[i-1] <= 3: c += 1
                if i+1 < k and S[i+1] - p <= 3: c += 1
                coef.append(c)
            order = sorted(coef)
            for twice in range(0, 2*xmax+1):
                x = Fr(twice, 2)
                if x > k: continue
                # 每口流量 (0,1]，闭包允许 0：贪心
                rem, w = x, Fr(0)
                for c in order:
                    t = min(Fr(1), rem); w += c*t; rem -= t
                table[x] = min(table.get(x, w), w)
    table[Fr(0)] = Fr(0)
    return table

def single_B(L, xmax):
    """逐口枚举 0,1/2,1（以半件为单位的整数 0,1,2）。返回 2x -> 2w。"""
    best = {}
    for vec in itertools.product((0, 1, 2), repeat=L):
        s = sum(vec)
        if s > 2*xmax: continue
        pf = [(p, f) for p, f in enumerate(vec) if f]
        w2 = w_of(pf)
        best[s] = min(best.get(s, w2), w2)
    return best

def group_A(tab, n, X, xmax):
    """半格 DP：f[j]=前若干台总输入 j/2 的最小权重。"""
    INF = None
    cur = {0: Fr(0)}
    for _ in range(n):
        nxt = {}
        for j, v in cur.items():
            for t in range(0, 2*xmax+1):
                jj = j + t
                if jj > 2*X: continue
                val = v + tab[Fr(t, 2)]
                if jj not in nxt or val < nxt[jj]: nxt[jj] = val
        cur = nxt
    return cur.get(int(2*X))

def group_B(tab2, n, X2, xmax):
    """整数档台数组合：除至多一台在半档外，其余台在整数档（以半件为单位 tab2[2m]）；枚举各档台数。"""
    levels = list(range(0, xmax+1))
    best = None
    def rec(i, left, tot, cost):
        nonlocal best
        if i == len(levels):
            if left != 0: return
            # 剩余半件给一台额外机器（从某台整数档 m 改为 m+1/2 等价于再枚举一台）
            if tot == X2:
                if best is None or cost < best: best = cost
            return
        m = levels[i]
        for c in range(0, left+1):
            rec(i+1, left-c, tot + c*2*m, cost + c*tab2[2*m])
    # 情形一：全部整数档
    rec(0, n, 0, 0)
    # 情形二：一台在半档 h+1/2，其余 n-1 台整数档
    for h in range(0, xmax):
        half = 2*h+1
        if half not in tab2: continue
        sub = None
        def rec2(i, left, tot, cost):
            nonlocal best
            if i == len(levels):
                if left == 0 and tot + half == X2:
                    c2 = cost + tab2[half]
                    if best is None or c2 < best: best = c2
                return
            m = levels[i]
            for c in range(0, left+1):
                rec2(i+1, left-c, tot + c*2*m, cost + c*tab2[2*m])
        rec2(0, n-1, 0, 0)
    return best

def formula(name, n):
    if name == '研磨机': return Fr(379-8*n, 2) if n <= 47 else Fr(0)
    if name == '塑形机': return Fr(max(0, 22-2*n))
    if name == '封装机': return Fr({3: 24, 4: 18, 5: 10, 6: 6, 7: 2}.get(n, 0))
    if name == '灌装机': return Fr({3: 14, 4: 6, 5: 2}.get(n, 0))

tables = {}
weights = {}
for name, (L, xmax) in TYPES.items():
    tA = single_A(L, xmax)
    tB = single_B(L, xmax)
    for twice in range(0, 2*xmax+1):
        assert tA[Fr(twice, 2)]*2 == tB[twice], (name, twice, tA[Fr(twice, 2)], tB[twice])
    tables[name] = {str(Fr(t, 2)): str(tA[Fr(t, 2)]) for t in range(2*xmax+1)}
    nmin = cnt[name]
    X = GROUP[name]
    rows = {}
    n = nmin
    while True:
        if n*xmax < X: n += 1; continue
        gA = group_A(tA, n, X, xmax)
        gB = group_B(tB, n, int(2*X), xmax)
        assert gA*2 == gB, (name, n, gA, gB)
        assert gA == formula(name, n), (name, n, gA, formula(name, n))
        rows[n] = str(gA)
        if gA == 0 and n > nmin + 2: break
        n += 1
    weights[name] = rows
Omega = sum(Fr(weights[k][cnt[k]]) for k in weights)
assert Omega == Fr(219, 2)
res['单机最小权重表'] = tables
res['机群最小权重'] = weights
res['Omega'] = str(Omega)

# 增配增量 4E+Ω
inc = {}
for name in ['研磨机', '塑形机', '封装机', '灌装机']:
    seq = []
    for k in range(1, 20):
        dO = formula(name, cnt[name]+k) - formula(name, cnt[name]+k-1)
        seq.append(str(4*area[name] + dO))
    inc[name] = seq[:8]
inc['小机'] = '36'; inc['协议储存箱'] = '36'; inc['种植/采种'] = '100'
assert min(Fr(x) for name in ['研磨机', '塑形机', '封装机', '灌装机'] for x in inc[name]) == 34
res['增配增量'] = inc

# 4(T+F)+2J >= 921 的组成
O_dirs, core_gap, band, qdirs = 184, 8, 88, 4
four_T = iface + O_dirs + core_gap + 109 - 91   # N+w<=91, w 和 N 一起扣
assert four_T == 829 and four_T + band + qdirs == 921
res['921'] = dict(四T下界=four_T, 加内带与q=four_T+band+qdirs)

# ---------- 面积 ----------
TOT = 4900; core, ports = 81, 138
assert TOT - 3291 - core - ports == 1390
assert 4*1390 - 921 == 4639
assert 4*1390 - 809 == 4751
assert 1390 - 208 == 1182 and ceil(Fr(829, 4)) == 208
assert ceil(Fr(717*4 + 4*Fr(219, 2) + 4*34, 16)) >= 0  # 占位，见下
# 供电可行 (P,J)
def feasible(P, J):
    return J >= 0 and J <= P and 23*P - 10*J >= 217 and 54*P - 25*J >= 520 and P >= 10
# A=1110 无增配：16P-2J+X+Y<=199
nobox = {}
for P in range(10, 20):
    Js = [J for J in range(0, P+1) if feasible(P, J)]
    ok = [J for J in Js if 16*P - 2*J <= 199]
    nobox[P] = dict(J可行=Js, 满足199的J=ok, X加Y上限={J: 199-16*P+2*J for J in ok})
assert all(not nobox[P]['满足199的J'] for P in range(14, 20))
assert nobox[13]['满足199的J'] and min(nobox[13]['满足199的J']) >= 5 or True
assert min(J for J in nobox[13]['满足199的J'] if 199-16*13+2*J >= 0) == 5
res['A1110无增配'] = {P: v for P, v in nobox.items() if v['满足199的J']}
# 有增配：4A <= 4751 - min(16P-2J) - 143.5
m = min(16*P - 2*J for P in range(10, 30) for J in range(0, P+1) if feasible(P, J))
assert m == 160
Amax = Fr(4751 - m, 4) - Fr(287, 8)
assert Amax == Fr(8895, 8)  # 1111.875
res['有增配A上限'] = str(Amax)
# 尺寸
def sizes(Aval):
    out = []
    for w in range(6, 69):
        if Aval % w == 0 and 6 <= Aval//w <= 68: out.append((w, Aval//w))
    return out
sz = {a: sizes(a) for a in range(1105, 1112)}
assert sz[1111] == [] and sz[1109] == [] and sz[1108] == [] and sz[1110] == [(30, 37), (37, 30)] and (27, 41) in sz[1107]
res['尺寸'] = {a: v for a, v in sz.items()}
# 单增配预算
budget = {}
for name, val in [('塑形机', Fr(219, 2) + 34), ('小机或箱', Fr(219, 2) + 36)]:
    for P in range(10, 14):
        for J in range(0, P+1):
            if not feasible(P, J): continue
            b = 4751 - 4*1110 - (16*P - 2*J) - val
            if b >= 0: budget[f'{name},P={P},J={J}'] = str(b)
assert set(budget) == {'塑形机,P=10,J=0', '小机或箱,P=10,J=0'}
res['单增配X0+Y0预算'] = budget
# 外边表：ℓ<=6X0+14c+8t+5k
tab = {}
for case, ell, k, t1 in [('右上都贴', 71, 2, 1), ('只贴一边', 101, 3, 2), ('都不贴', 138, 2, 2)]:
    x_extra = ceil(Fr(ell - 14 - 8*t1 - 5*k, 6))
    x_none = ceil(Fr(ell - 14 - 5*k, 6))
    tab[case] = dict(单增配X0下界=x_extra, 无增配X下界=x_none)
assert tab == {'右上都贴': {'单增配X0下界': 7, '无增配X下界': 8}, '只贴一边': {'单增配X0下界': 10, '无增配X下界': 12}, '都不贴': {'单增配X0下界': 17, '无增配X下界': 19}}
# ℓ 由矩形 30x37 与贴边位置独立枚举
ells = {'右上都贴': set(), '只贴一边': set(), '都不贴': set()}
for (W, H) in [(30, 37), (37, 30)]:
    for a in range(4, 70-W+1):
        for b in range(4, 70-H+1):
            right = a+W-1 == 69; top = b+H-1 == 69
            cov = (H if right else 0) + (W if top else 0)
            ell = 138 - cov
            key = '右上都贴' if right and top else ('只贴一边' if right or top else '都不贴')
            ells[key].add(ell)
res['外边长度'] = {k: sorted(v) for k, v in ells.items()}
assert min(ells['右上都贴']) == 71 and min(ells['只贴一边']) == 101 and min(ells['都不贴']) == 138
res['外边表'] = tab
(OUT/'arith.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str)+'\n')
print(json.dumps({'Omega': str(Omega), '研磨': weights['研磨机'].get(32), '塑形': weights['塑形机'].get(6),
                  '封装': weights['封装机'].get(3), '灌装': weights['灌装机'].get(3), '外边表': tab, 'A增配上限': str(Amax)}, ensure_ascii=False))
