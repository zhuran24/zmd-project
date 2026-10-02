# -*- coding: utf-8 -*-
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import 总图 as G
os.chdir(os.path.dirname(os.path.abspath(__file__)))
occ, errs, outlets, allm, allst, allr = G.main()
assert not errs, errs
placed_ids = {m['id'] for m in allm}
lg = json.load(open('逻辑接法-借自第三张A.json'))
allids = [m['id'] for m in lg['machines']]
rest = [i for i in allids if i not in placed_ids]
# 区块分配（粗）：区块矩形与成员；坐标为区块内建议起点，实现席在区块内定格
blk = {
 '角区(1..18,1..18)': [f'RF{i}' for i in (1,2,3,4,17,18,21,22,25,26,27,28)] + [f'KF{i}' for i in (1,2,3,4,17,18,21,22,25,26,27,28)],
 '下端区(55..69,0..13)': [f'RF{i}' for i in (29,30,31,32,33)] + [f'KF{i}' for i in (29,30,31,32,33)] + ['B15','B16'],
 '左上端区(0..13,55..69)': [f'RF{i}' for i in (19,20,23,24,34)] + [f'KF{i}' for i in (19,20,23,24,34)] + ['B10','B12'],
 'SrcDL上方(37..54,10..18)': ['KF9','KF10','B1','B2','R1','R2','P1','P2','P3','P4'],
 'SrcDL右方(10..18,37..54)': ['KF15','KF16','B8','B11','R11','R12','P5','P6'],
 '核心区(40..54,19..37)': ['KO1','KO2','KO3','KO4','KO5','KO6','O1','O2','O3','E1','E2','E3','F1','F2','F3','F4'],
 '研磨列(19..36,19..36)': ['B7','B9','B13','B14','B17','R7','R8','R9','R10','R13','R14','R15','R16','R17','H1','H2','H3','H4','H5','H6'],
}
assigned = [i for v in blk.values() for i in v]
plants = [i for i in rest if i[:2] in ('SC','SA','SB','QC','QA','QB','QK') or (i.startswith('S') and i[1:].isdigit())]
blk['植物带(19..69,38..69 及 55..69,19..37)'] = plants + ['Q1','Q2','Q3','Q4','Q5','Q6']
assigned = [i for v in blk.values() for i in v]
missing = [i for i in rest if i not in assigned]
dup = [i for i in assigned if assigned.count(i) > 1]
print('rest', len(rest), 'assigned', len(assigned), 'missing', missing, 'dup', sorted(set(dup)))
out = dict(schema='第四张全厂候选-规划粗坐标-v1', 坐标约定='左下角(0,0)，x 向右 y 向上；Din 为存货边外法向 0E 1N 2W 3S；大制造单位 Din∈{1,3} 宽6高4，Din∈{0,2} 宽4高6',
  定格精度={'模板模块': '逐格定死（DL-X、SrcDL-4、DL-Y、SrcDL-6），已过局部检查', '区块': '只定区块矩形与成员，区块内由实现席定格'},
  warehouse_outlets=[dict(id=o['id'], x0=o['x0'], y0=o['y0'], x1=o['x1'], y1=o['y1'], Dout=o['Dout'], item=o['item'], 取货端口外侧格=o['port_outer']) for o in outlets],
  core=dict(区块='核心区(40..54,19..37)', 建议左下角=[43,26], 存货边Din=0, 取货端口='上下两边 offset 1/4/7 共 6 口全设源矿，各正对一台源矿粉碎机（KO1..KO3 在上、KO4..KO6 在下）'),
  machines=[dict(id=m['id'], model=m['model'], recipe=m['recipe'], x0=m['x0'], y0=m['y0'], x1=m['x0']+m['w']-1, y1=m['y0']+m['h']-1, Din=m['Din'], 模块=m['module'], 精度='定格') for m in allm],
  blocks={k: v for k, v in blk.items()},
  power_stalls=[dict(x0=s['x0'], y0=s['y0'], x1=s['x0']+1, y1=s['y0']+1, 模块=s['module']) for s in allst],
  routes_fixed=[dict(name=k, source=v[0], target=v[1], item=v[3], cells=v[2]) for k, v in allr.items()],
)
json.dump(out, open('粗坐标.json','w'), ensure_ascii=False, indent=1)
# 字符图
g = [['.']*70 for _ in range(70)]
for (x,y),u in occ.items():
    ch = '#'
    if u.startswith('OUT'): ch = 'W'
    elif u == 'PWR': ch = 'P'
    g[y][x] = ch
for k,(s,d,cells,it) in allr.items():
    for (x,y) in cells:
        g[y][x] = '+' if g[y][x] in '-|+' else '-'
# 区块框
import re
for name in blk:
    m = re.search(r'\((\d+)\.\.(\d+),(\d+)\.\.(\d+)', name)
    if not m: continue
    x0,x1,y0,y1 = map(int, m.groups())
    for x in range(x0, x1+1):
        for y in range(y0, y1+1):
            if g[y][x] == '.': g[y][x] = {'角':'c','下':'d','左':'u','S':'s','核':'k','研':'g','植':'p'}[name[0]] if name[0]!='S' else ('s' if '上方' in name else 'r')
lines = [''.join(g[y]) + f' {y:2d}' for y in range(69,-1,-1)]
open('区块总图.txt','w').write('\n'.join(lines) + '\n' + ''.join(str(x//10) for x in range(70)) + '\n' + ''.join(str(x%10) for x in range(70)) + '\n')
print('\n'.join(lines[-25:]))
