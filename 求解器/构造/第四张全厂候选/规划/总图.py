# -*- coding: utf-8 -*-
"""第四张全厂候选的总体平面规划：取货口全排、四个已定模板模块按世界坐标展开、其余区块给区块矩形与机器清单，
输出 粗坐标.json、区块总图（字符图）和面积/容量账。只用标准库。"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from 模板 import tpl_DL, tpl_SrcDL, tpl_PP, check_template, port_cells, E, N, W, S

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- 取货口：下边 x=1..69、左边 y=1..69 各 23 个，(0,0) 是唯一空的边界格 ----------------
bottom_items = {}
left_items = {}
# 下边：k=0..5 角区(蓝铁矿)；k=6..11 DL-X；k=12..17 SrcDL-4；k=18..22 下端区(蓝铁矿)
for k in range(23):
    if 6 <= k <= 11:
        bottom_items[k] = ['蓝铁矿', '蓝铁矿', '源矿', '源矿', '蓝铁矿', '蓝铁矿'][k - 6]
    elif 12 <= k <= 17:
        bottom_items[k] = ['源矿', '源矿', '蓝铁矿', '蓝铁矿', '源矿', '源矿'][k - 12]
    else:
        bottom_items[k] = '蓝铁矿'
for k in range(23):
    if 6 <= k <= 11:
        left_items[k] = ['蓝铁矿', '蓝铁矿', '源矿', '源矿', '蓝铁矿', '蓝铁矿'][k - 6]
    elif 12 <= k <= 17:
        left_items[k] = ['源矿', '源矿', '蓝铁矿', '蓝铁矿', '源矿', '源矿'][k - 12]
    else:
        left_items[k] = '蓝铁矿'

DIN_T = {S: W, N: E, E: N, W: S}  # 下带模板转到左带（x=v, y=u）


def place(T, axis, o):
    """把模板放到世界坐标：axis='B' 下带 (x=o+u, y=v)；'L' 左带 (x=v, y=o+u)。"""
    out = dict(machines=[], stalls=[], routes={}, name=T['name'])
    for m in T['machines']:
        if axis == 'B':
            out['machines'].append(dict(m, x0=o + m['x0'], y0=m['y0']))
        else:
            out['machines'].append(dict(m, x0=m['y0'], y0=o + m['x0'], w=m['h'], h=m['w'], Din=DIN_T[m['Din']]))
    for (a, b) in T['stalls']:
        out['stalls'].append((o + a, b) if axis == 'B' else (b, o + a))
    for rn, (src, dst, cells, item) in T['routes'].items():
        cc = [(o + u, v) if axis == 'B' else (v, o + u) for (u, v) in cells]
        out['routes'][T['name'] + ':' + rn] = (src, dst, cc, item)
    return out


mods = []
# 编号沿用 S2 逻辑接法（第三张 A 的转写）：KF(2i-1),KF(2i)->Bi；KO(2i-1),KO(2i)->Oi；WFEj 供 RFj，WOj 供 KOj
mods.append(('B', 19, tpl_DL('DL-X', 'B3', 'B4', 'O4', 'S3', 'R3', 'R4',
                             ['WFE5', 'WFE6', 'WO7', 'WO8', 'WFE7', 'WFE8'], ['RF5', 'RF6', 'RF7', 'RF8'],
                             ['KF5', 'KF6', 'KF7', 'KF8'], ['KO7', 'KO8'])))
mods.append(('B', 37, tpl_SrcDL('SrcDL-4', 'O5', 'O6', 'S4', ['WO9', 'WO10', 'WFE9', 'WFE10', 'WO11', 'WO12'],
                                ['KO9', 'KO10', 'KO11', 'KO12'], ['RF9', 'RF10'])))
mods.append(('L', 19, tpl_DL('DL-Y', 'B5', 'B6', 'O7', 'S5', 'R5', 'R6',
                             ['WFE11', 'WFE12', 'WO13', 'WO14', 'WFE13', 'WFE14'], ['RF11', 'RF12', 'RF13', 'RF14'],
                             ['KF11', 'KF12', 'KF13', 'KF14'], ['KO13', 'KO14'])))
mods.append(('L', 37, tpl_SrcDL('SrcDL-6', 'O8', 'O9', 'S6', ['WO15', 'WO16', 'WFE15', 'WFE16', 'WO17', 'WO18'],
                                ['KO15', 'KO16', 'KO17', 'KO18'], ['RF15', 'RF16'])))

placed = [place(T, ax, o) for (ax, o, T) in mods]

# ---------------- 其余区块：矩形、内容与朝向原则（实现席在区块内定格） ----------------
# 每个区块：名字、矩形 (x0,y0,x1,y1)、机器清单、内部排法
blocks = [
    dict(name='角区', rect=(1, 1, 18, 18),
         content='下边 k=0..5（x=1..18）与左边 k=0..5（y=1..18）共 12 个蓝铁矿取货口 → RF1..RF4、RF17..RF24 等 12 台矿石精炼炉 + 12 台蓝铁块粉碎机；只做到蓝铁粉末，12 条蓝铁粉末经出口走廊送 B1、B2、B9、B10、B13、B14',
         machines=[]),
    dict(name='下端区', rect=(55, 0, 69, 13),
         content='下边 k=18..22 五个蓝铁矿口 → 5 精炼炉(y=2..4) + 5 粉碎机(y=6..8) + B15(55..60,10..13)、B16(64..69,10..13)，中缝 x=61..63 走 S11 两路砂叶粉末下行及第 5 台粉碎机产物上行',
         machines=[]),
    dict(name='左上端区', rect=(0, 55, 13, 69),
         content='左边 k=18..22 五个蓝铁矿口，左带转置的下端区：B11、B12 + 1 台单出粉碎机；中缝 y=61..63',
         machines=[]),
]


def world_grid():
    g = [['.' for _ in range(70)] for _ in range(70)]
    return g


def main():
    occ = {}
    errs = []
    units = []
    # 取货口
    outlets = []
    for k in range(23):
        outlets.append(dict(id=f'OUTB{k:02d}', side='下', x0=3 * k + 1, y0=0, x1=3 * k + 3, y1=0, Dout=1,
                            port_outer=(3 * k + 2, 1), item=bottom_items[k]))
        outlets.append(dict(id=f'OUTL{k:02d}', side='左', x0=0, y0=3 * k + 1, x1=0, y1=3 * k + 3, Dout=0,
                            port_outer=(1, 3 * k + 2), item=left_items[k]))
    for o in outlets:
        for x in range(o['x0'], o['x1'] + 1):
            for y in range(o['y0'], o['y1'] + 1):
                occ[(x, y)] = o['id']
    # 模块机器
    allm = []
    allst = []
    allr = {}
    for P in placed:
        for m in P['machines']:
            for i in range(m['w']):
                for j in range(m['h']):
                    c = (m['x0'] + i, m['y0'] + j)
                    if not (0 <= c[0] < 70 and 0 <= c[1] < 70):
                        errs.append(f"{m['id']} 出界 {c}")
                    if c in occ:
                        errs.append(f"重叠 {m['id']} vs {occ[c]} @ {c}")
                    occ[c] = m['id']
            allm.append(dict(m, module=P['name']))
        for (a, b) in P['stalls']:
            for i in range(2):
                for j in range(2):
                    c = (a + i, b + j)
                    if c in occ:
                        errs.append(f"桩重叠 {c} vs {occ[c]}")
                    occ[c] = 'PWR'
            allst.append(dict(x0=a, y0=b, module=P['name']))
        allr.update(P['routes'])
    for rn, (src, dst, cells, item) in allr.items():
        for c in cells:
            if c in occ:
                errs.append(f"进路 {rn} 压单位 {occ[c]} @ {c}")
    return occ, errs, outlets, allm, allst, allr


if __name__ == '__main__':
    occ, errs, outlets, allm, allst, allr = main()
    print('errors', len(errs), errs[:10])
    print('machines placed', len(allm), 'cells', sum(m['w'] * m['h'] for m in allm), 'stalls', len(allst), 'routes', len(allr))
