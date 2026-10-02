# -*- coding: utf-8 -*-
"""第四张全厂候选的模块模板（局部坐标）与逐模板自检。

局部坐标 (u,v)：u 沿边界，v 离开边界。下带模块 x=x0+u, y=v；左带模块 x=v, y=y0+u。
方向 Side：0=E 1=N 2=W 3=S（与 full-factory-static-v1 相同，指存货边外法向 Din）。
本文件只描述机器、取货口、供电桩和模板内已经定死的进路；运行 python3 模板.py 做局部检查。
"""
import json, sys

E, N, W, S = 0, 1, 2, 3
DV = {E: (1, 0), N: (0, 1), W: (-1, 0), S: (0, -1)}


def size(kind, din):
    if kind == '小':
        return 3, 3
    if kind == '中':
        return 5, 5
    if kind == '大':
        return (6, 4) if din in (N, S) else (4, 6)
    raise ValueError(kind)


def mach(mid, model, kind, u, v, din, recipe):
    w, h = size(kind, din)
    return dict(id=mid, model=model, kind=kind, x0=u, y0=v, w=w, h=h, Din=din, recipe=recipe)


def port_cells(m):
    """返回 [(内侧格, 外侧格, 'in'/'out')]。"""
    x0, y0, w, h, d = m['x0'], m['y0'], m['w'], m['h'], m['Din']
    out = []
    for side, kind in ((d, 'in'), ((d + 2) % 4, 'out')):
        if side == E:
            cells = [(x0 + w - 1, y0 + i) for i in range(h)]
        elif side == W:
            cells = [(x0, y0 + i) for i in range(h)]
        elif side == N:
            cells = [(x0 + i, y0 + h - 1) for i in range(w)]
        else:
            cells = [(x0 + i, y0) for i in range(w)]
        dx, dy = DV[side]
        for (cx, cy) in cells:
            out.append(((cx, cy), (cx + dx, cy + dy), kind))
    return out


# ---------------------------------------------------------------------------
# 模板 DL：双车道（4 蓝铁矿＋2 源矿），砂叶粉碎机在中缝里同供两台研磨机和一台源石研磨机
# 宽 18（6 个取货口），深 19（v=0..18）。
# ---------------------------------------------------------------------------

def tpl_DL(tag, Bi_A, Bi_B, Oi, Sk, Ri_A, Ri_B, ore_ids, ref_ids, kf_ids, ko_ids):
    """ore_ids: 6 个取货口（铁,铁,源,源,铁,铁）；ref_ids: 4 台矿石精炼炉；kf_ids: 4 台蓝铁块粉碎机；ko_ids: 2 台源矿粉碎机"""
    M = []
    P = []  # 仓库取货口（局部 u 起点）
    items = ['蓝铁矿', '蓝铁矿', '源矿', '源矿', '蓝铁矿', '蓝铁矿']
    for k in range(6):
        P.append(dict(id=ore_ids[k], u=3 * k, item=items[k]))
    first = [ref_ids[0], ref_ids[1], ko_ids[0], ko_ids[1], ref_ids[2], ref_ids[3]]
    for k in range(6):
        if k in (2, 3):
            M.append(mach(first[k], '粉碎机', '小', 3 * k, 2, S, '粉碎-源矿'))
        else:
            M.append(mach(first[k], '精炼炉', '小', 3 * k, 2, S, '精炼-蓝铁矿'))
    for j, k in enumerate((0, 1, 4, 5)):
        M.append(mach(kf_ids[j], '粉碎机', '小', 3 * k, 6, S, '粉碎-蓝铁块'))
    M.append(mach(Bi_A, '研磨机', '大', 0, 10, S, '研磨-致密蓝铁'))
    M.append(mach(Bi_B, '研磨机', '大', 12, 10, S, '研磨-致密蓝铁'))
    M.append(mach(Sk, '粉碎机', '小', 8, 10, N, '粉碎-砂叶'))
    M.append(mach(Oi, '研磨机', '大', 6, 15, S, '研磨-致密源石'))
    M.append(mach(Ri_A, '精炼炉', '小', 0, 15, S, '精炼-致密蓝铁'))
    M.append(mach(Ri_B, '精炼炉', '小', 15, 15, S, '精炼-致密蓝铁'))
    stalls = [(7, 5), (9, 5), (3, 16)]
    R = {}  # 进路：名字 -> (源, 汇, 格列表, 物品)
    for k in range(6):
        R[f'feed{k}'] = (ore_ids[k], first[k], [(3 * k + 1, 1)], items[k])
    R['rf_kf_a'] = (ref_ids[0], kf_ids[0], [(1, 5)], '蓝铁块')
    R['rf_kf_b'] = (ref_ids[1], kf_ids[1], [(4, 5)], '蓝铁块')
    R['rf_kf_c'] = (ref_ids[2], kf_ids[2], [(13, 5)], '蓝铁块')
    R['rf_kf_d'] = (ref_ids[3], kf_ids[3], [(16, 5)], '蓝铁块')
    R['kf_a_B'] = (kf_ids[0], Bi_A, [(1, 9)], '蓝铁粉末')
    R['kf_b_B'] = (kf_ids[1], Bi_A, [(4, 9)], '蓝铁粉末')
    R['kf_c_B'] = (kf_ids[2], Bi_B, [(13, 9)], '蓝铁粉末')
    R['kf_d_B'] = (kf_ids[3], Bi_B, [(16, 9)], '蓝铁粉末')
    R['ko_a_O'] = (ko_ids[0], Oi, [(6, v) for v in range(5, 15)], '源石粉末')
    R['ko_b_O'] = (ko_ids[1], Oi, [(11, v) for v in range(5, 15)], '源石粉末')
    R['S_BA'] = (Sk, Bi_A, [(8, 9), (7, 9), (6, 9), (5, 9)], '砂叶粉末')
    R['S_BB'] = (Sk, Bi_B, [(10, 9), (11, 9), (12, 9)], '砂叶粉末')
    R['S_O'] = (Sk, Oi, [(9, 9), (9, 8), (8, 8), (7, 8), (7, 9)] + [(7, v) for v in range(10, 15)], '砂叶粉末')
    R['BA_R'] = (Bi_A, Ri_A, [(1, 14)], '致密蓝铁粉末')
    R['BB_R'] = (Bi_B, Ri_B, [(16, 14)], '致密蓝铁粉末')
    # 砂叶进 S：由东侧走廊 (12..14, 15..18) 下来，模板内只定最后 4 格
    R['SB_S*'] = (None, Sk, [(12, 15), (12, 14), (11, 14), (10, 14), (10, 13)], '砂叶')
    return dict(name=tag, W=18, H=19, machines=M, outlets=P, stalls=stalls, routes=R,
                exits={'Oi出': [(u, 19) for u in range(6, 12)], 'Ri_A出': [(u, 18) for u in range(0, 3)],
                       'Ri_B出': [(u, 18) for u in range(15, 18)], '西走廊': [(u, v) for u in (3, 4, 5) for v in range(15, 19)],
                       '东走廊': [(u, v) for u in (12, 13, 14) for v in range(15, 19)]})


# ---------------------------------------------------------------------------
# 模板 SrcDL：源矿双车道（4 源矿＋中缝 2 蓝铁矿），砂叶粉碎机在中缝里同供两台源石研磨机
# 宽 18，深 10（v=0..9）；中缝两台矿石精炼炉的蓝铁块从中缝两列向上送出。
# ---------------------------------------------------------------------------

def tpl_SrcDL(tag, O_a, O_b, Sk, ore_ids, ko_ids, ref_ids):
    M = []
    P = []
    items = ['源矿', '源矿', '蓝铁矿', '蓝铁矿', '源矿', '源矿']
    for k in range(6):
        P.append(dict(id=ore_ids[k], u=3 * k, item=items[k]))
    first = [ko_ids[0], ko_ids[1], ref_ids[0], ref_ids[1], ko_ids[2], ko_ids[3]]
    for k in range(6):
        if k in (2, 3):
            M.append(mach(first[k], '精炼炉', '小', 3 * k, 2, S, '精炼-蓝铁矿'))
        else:
            M.append(mach(first[k], '粉碎机', '小', 3 * k, 2, S, '粉碎-源矿'))
    M.append(mach(O_a, '研磨机', '大', 0, 6, S, '研磨-致密源石'))
    M.append(mach(O_b, '研磨机', '大', 12, 6, S, '研磨-致密源石'))
    M.append(mach(Sk, '粉碎机', '小', 7, 6, N, '粉碎-砂叶'))
    stalls = [(9, 9)]
    R = {}
    for k in range(6):
        R[f'feed{k}'] = (ore_ids[k], first[k], [(3 * k + 1, 1)], items[k])
    R['ko1'] = (ko_ids[0], O_a, [(1, 5)], '源石粉末')
    R['ko2'] = (ko_ids[1], O_a, [(4, 5)], '源石粉末')
    R['ko3'] = (ko_ids[2], O_b, [(13, 5)], '源石粉末')
    R['ko4'] = (ko_ids[3], O_b, [(16, 5)], '源石粉末')
    R['S_Oa'] = (Sk, O_a, [(7, 5), (6, 5), (5, 5)], '砂叶粉末')
    R['S_Ob'] = (Sk, O_b, [(9, 5), (10, 5), (11, 5), (12, 5)], '砂叶粉末')
    R['rf1_up*'] = (ref_ids[0], None, [(6, v) for v in range(5, 11)], '蓝铁块')
    R['rf2_up*'] = (ref_ids[1], None, [(11, v) for v in range(5, 11)], '蓝铁块')
    R['SB_S*'] = (None, Sk, [(8, 11), (8, 10), (8, 9)], '砂叶')
    return dict(name=tag, W=18, H=10, machines=M, outlets=P, stalls=stalls, routes=R,
                exits={'O_a出': [(u, 10) for u in range(0, 6)], 'O_b出': [(u, 10) for u in range(12, 18)]})


# ---------------------------------------------------------------------------
# 模板 PP：两个采种单元一对（借第三张 B 的 12×16 双单元骨架），两侧 3 宽的粉碎机列
# 局部 x 0..14（含东侧粉碎机列 12..14；西侧粉碎机 K1 放在 -3..-1，与左邻模块的东列共用）
# ---------------------------------------------------------------------------

def tpl_PP(tag, u1, u2, plant):
    """u1/u2: dict(C=, A=, B=, K=)；plant: '砂叶' 或 '荞花'。K1 在西侧共用列 (-3..-1, 8..10)，K2 在东列 (12..14, 5..7)。"""
    seed = plant + '种子'
    M = [mach(u1['B'], '种植机', '中', 0, 10, N, f'种植-{plant}'),
         mach(u1['A'], '种植机', '中', 6, 6, W, f'种植-{plant}'),
         mach(u1['C'], '采种机', '中', 6, 11, E, f'采种-{plant}'),
         mach(u2['C'], '采种机', '中', 1, 0, W, f'采种-{plant}'),
         mach(u2['A'], '种植机', '中', 1, 5, E, f'种植-{plant}'),
         mach(u2['B'], '种植机', '中', 7, 1, S, f'种植-{plant}'),
         mach(u1['K'], '粉碎机', '小', -3, 8, E, f'粉碎-{plant}'),
         mach(u2['K'], '粉碎机', '小', 12, 5, W, f'粉碎-{plant}')]
    R = {
        'C1_B1': (u1['C'], u1['B'], [(5, 15), (4, 15)], seed),
        'C1_A1': (u1['C'], u1['A'], [(5, 11), (5, 10)], seed),
        'A1_C1': (u1['A'], u1['C'], [(11, 10), (11, 11)], plant),
        'B1_K1': (u1['B'], u1['K'], [(0, 9)], plant),
        'C2_B2': (u2['C'], u2['B'], [(6, 0), (7, 0)], seed),
        'C2_A2': (u2['C'], u2['A'], [(6, 4), (6, 5)], seed),
        'A2_C2': (u2['A'], u2['C'], [(0, 5), (0, 4)], plant),
        'B2_K2': (u2['B'], u2['K'], [(11, 6)], plant),
    }
    return dict(name=tag, W=15, H=16, machines=M, outlets=[], stalls=[], routes=R,
                exits={'K1出(西)': [(-4, v) for v in range(8, 11)], 'K2出(东)': [(15, v) for v in range(5, 8)]})


# ---------------------------------------------------------------------------
# 局部检查：重叠、进路逐格相邻、端口相接、运输格互斥（桥＝两路直穿且垂直）、桥邻格无多余端口
# ---------------------------------------------------------------------------

def check_template(T, verbose=True):
    occ = {}
    errs = []
    for m in T['machines']:
        for i in range(m['w']):
            for j in range(m['h']):
                c = (m['x0'] + i, m['y0'] + j)
                if c in occ:
                    errs.append(f"重叠 {m['id']} 与 {occ[c]} @ {c}")
                occ[c] = m['id']
    for p in T['outlets']:
        for i in range(3):
            c = (p['u'] + i, 0)
            if c in occ:
                errs.append(f"取货口重叠 {c}")
            occ[c] = p['id']
    for (a, b) in T['stalls']:
        for i in range(2):
            for j in range(2):
                c = (a + i, b + j)
                if c in occ:
                    errs.append(f"供电桩重叠 {c} 与 {occ[c]}")
                occ[c] = 'PWR'
    byid = {m['id']: m for m in T['machines']}
    portmap = {}  # 外侧格 -> [(机器, in/out, 内侧格)]
    for m in T['machines']:
        for inner, outer, kind in port_cells(m):
            portmap.setdefault(outer, []).append((m['id'], kind, inner))
    for p in T['outlets']:
        inner = (p['u'] + 1, 0)
        portmap.setdefault((p['u'] + 1, 1), []).append((p['id'], 'out', inner))
    use = {}  # 格 -> [(进路, 轴/类型)]
    for rn, (src, dst, cells, item) in T['routes'].items():
        for c in cells:
            if c in occ:
                errs.append(f"进路 {rn} 压在单位 {occ[c]} 上 @ {c}")
        for a, b in zip(cells, cells[1:]):
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                errs.append(f"进路 {rn} 不连续 {a}->{b}")
        # 起点：第一格须正对源的取货端口
        if src is not None:
            ok = any(mid == src and kind == 'out' for (mid, kind, inner) in portmap.get(cells[0], []))
            if not ok:
                errs.append(f"进路 {rn} 首格 {cells[0]} 不正对 {src} 的取货端口")
        if dst is not None:
            ok = any(mid == dst and kind == 'in' for (mid, kind, inner) in portmap.get(cells[-1], []))
            if not ok:
                errs.append(f"进路 {rn} 末格 {cells[-1]} 不正对 {dst} 的存货端口")
        for idx, c in enumerate(cells):
            prev = cells[idx - 1] if idx > 0 else None
            nxt = cells[idx + 1] if idx + 1 < len(cells) else None
            use.setdefault(c, []).append((rn, idx, prev, nxt))
    bridges = []
    for c, lst in use.items():
        if len(lst) == 1:
            continue
        if len(lst) > 2:
            errs.append(f"格 {c} 被 {len(lst)} 路共用")
            continue
        axes = []
        for (rn, idx, prev, nxt) in lst:
            cells = T['routes'][rn][2]
            # 进入方向与离开方向须同轴直穿；首/末格方向由端口决定
            dirs = set()
            if prev is not None:
                dirs.add('H' if prev[1] == c[1] else 'V')
            else:
                # 首格：与源端口相对
                srcp = [inner for (mid, kind, inner) in portmap.get(c, []) if mid == T['routes'][rn][0] and kind == 'out']
                if srcp:
                    dirs.add('H' if srcp[0][1] == c[1] else 'V')
            if nxt is not None:
                dirs.add('H' if nxt[1] == c[1] else 'V')
            else:
                dstp = [inner for (mid, kind, inner) in portmap.get(c, []) if mid == T['routes'][rn][1] and kind == 'in']
                if dstp:
                    dirs.add('H' if dstp[0][1] == c[1] else 'V')
            if len(dirs) != 1:
                errs.append(f"格 {c} 共用但进路 {rn} 在此转弯")
            axes.append(dirs.pop() if dirs else '?')
        if sorted(axes) != ['H', 'V']:
            errs.append(f"格 {c} 两路不垂直：{axes}")
        bridges.append(c)
        # 桥邻格的端口：每个正对桥的机器端口，必须是该轴进路的源或汇
        for side, (dx, dy) in DV.items():
            nb = (c[0] + dx, c[1] + dy)
            ax = 'H' if side in (E, W) else 'V'
            for (mid, kind, inner) in portmap.get(c, []):
                if inner == nb:
                    rn_ax = [lst[i][0] for i in range(2) if axes[i] == ax]
                    rr = T['routes'][rn_ax[0]]
                    if not ((kind == 'out' and rr[0] == mid and rr[2][0] == c) or (kind == 'in' and rr[1] == mid and rr[2][-1] == c)):
                        errs.append(f"桥 {c} 的 {ax} 轴正对 {mid} 的端口，但不是该轴进路的端点")
    ncell = sum(len(r[2]) for r in T['routes'].values())
    phys = len(use)
    mcell = sum(m['w'] * m['h'] for m in T['machines'])
    res = dict(name=T['name'], ok=not errs, errors=errs, machines=len(T['machines']), machine_cells=mcell,
               route_count=len(T['routes']), item_cells=ncell, physical_transport=phys, bridges=sorted(bridges),
               stalls=len(T['stalls']), box=f"{T['W']}x{T['H']}")
    if verbose:
        print(json.dumps(res, ensure_ascii=False))
    return res


def demo_templates():
    dl = tpl_DL('DL-X', 'B3', 'B4', 'O4', 'S3', 'R3', 'R4', ['WFE5', 'WFE6', 'WO7', 'WO8', 'WFE7', 'WFE8'],
                ['RF5', 'RF6', 'RF7', 'RF8'], ['KF5', 'KF6', 'KF7', 'KF8'], ['KO7', 'KO8'])
    src = tpl_SrcDL('SrcDL-4', 'O5', 'O6', 'S4', ['WO9', 'WO10', 'WFE19', 'WFE20', 'WO11', 'WO12'],
                    ['KO9', 'KO10', 'KO11', 'KO12'], ['RF19', 'RF20'])
    pp = tpl_PP('PP', dict(C='SC1', A='SA1', B='SB1', K='S1'), dict(C='SC2', A='SA2', B='SB2', K='S2'), '砂叶')
    return [dl, src, pp]


if __name__ == '__main__':
    out = [check_template(T) for T in demo_templates()]
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else '/dev/null', 'w'), ensure_ascii=False, indent=1)
    sys.exit(0 if all(r['ok'] for r in out) else 1)
