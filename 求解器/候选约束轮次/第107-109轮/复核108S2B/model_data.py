"""本席独立按快照配方及候选接线文字录入。没有导入推导席程序。"""
from collections import Counter, defaultdict

# key: (机型, 输入, 产物, 每批产量, 制造步数)
RECIPES = {
    'ore_blue': ('精炼炉', {'蓝铁矿': 1}, '蓝铁块', 1, 8),
    'blue_powder': ('粉碎机', {'蓝铁块': 1}, '蓝铁粉末', 1, 8),
    'origin_powder': ('粉碎机', {'源矿': 1}, '源石粉末', 1, 8),
    'B': ('研磨机', {'蓝铁粉末': 2, '砂叶粉末': 1}, '致密蓝铁粉末', 1, 8),
    'O': ('研磨机', {'源石粉末': 2, '砂叶粉末': 1}, '致密源石粉末', 1, 8),
    'Q': ('研磨机', {'荞花粉末': 2, '砂叶粉末': 1}, '细磨荞花粉末', 1, 8),
    'R': ('精炼炉', {'致密蓝铁粉末': 1}, '钢块', 1, 8),
    'P': ('配件机', {'钢块': 1}, '钢制零件', 1, 8),
    'H': ('塑形机', {'钢块': 2}, '钢质瓶', 1, 8),
    'E': ('封装机', {'钢制零件': 10, '致密源石粉末': 15}, '高容谷地电池', 1, 40),
    'F': ('灌装机', {'钢质瓶': 10, '细磨荞花粉末': 10}, '精选荞愈胶囊', 1, 40),
}
for prefix, plant in [('S', '砂叶'), ('J', '荞花')]:
    RECIPES[prefix+'C'] = ('采种机', {plant: 1}, plant+'种子', 2, 8)
    RECIPES[prefix+'A'] = ('种植机', {plant+'种子': 1}, plant, 1, 8)
    RECIPES[prefix+'B'] = RECIPES[prefix+'A']
    RECIPES[prefix+'K'] = ('粉碎机', {plant: 1}, plant+'粉末', 3 if prefix=='S' else 2, 8)

S_GROUPS = [('B1','B2','O1'), ('O2','O3'), ('B3','B4','O4'), ('O5','O6'),
            ('B5','B6','O7'), ('O8','O9'), ('B7','B8','B9'), ('B10','Q1','Q2'),
            ('B11','B12','B13'), ('B14','Q3','Q4'), ('B15','B16','Q5'), ('B17',), ('Q6',)]

def build():
    nodes, routes = {}, []
    def node(name, recipe):
        assert name not in nodes
        nodes[name] = RECIPES[recipe]
    def edge(a, b, item):
        routes.append((a,b,item))
    for i in range(1,35):
        node(f'I{i}', 'ore_blue'); node(f'D{i}', 'blue_powder')
        edge(f'Wb{i}', f'I{i}', '蓝铁矿')
        edge(f'I{i}', f'D{i}', '蓝铁块')
        edge(f'D{i}', f'B{(i+1)//2}', '蓝铁粉末')
    for i in range(1,19):
        node(f'X{i}', 'origin_powder')
        edge('核心' if i<=6 else f'Wo{i}', f'X{i}', '源矿')
        edge(f'X{i}', f'O{(i+1)//2}', '源石粉末')
    for i in range(1,18):
        node(f'B{i}','B'); node(f'R{i}','R')
        edge(f'B{i}', f'R{i}', '致密蓝铁粉末')
        dest=f'P{i}' if i<=6 else f'H{(i-7)//2+1}' if i<=16 else 'H6'
        edge(f'R{i}', dest, '钢块')
    for i in range(1,10):
        node(f'O{i}', 'O'); edge(f'O{i}', f'E{(i-1)//3+1}', '致密源石粉末')
    for i in range(1,7):
        node(f'P{i}', 'P'); node(f'H{i}', 'H'); node(f'Q{i}', 'Q')
        edge(f'P{i}', f'E{(i-1)//2+1}', '钢制零件')
        final=1 if i<=2 else 2 if i<=4 else i-2
        edge(f'H{i}', f'F{final}', '钢质瓶')
        edge(f'Q{i}', f'F{final}', '细磨荞花粉末')
    for prefix,count in [('S',13),('J',6)]:
        plant='砂叶' if prefix=='S' else '荞花'
        for i in range(1,count+1):
            for letter in 'CABK': node(f'{prefix}{letter}{i}', prefix+letter)
            edge(f'{prefix}C{i}', f'{prefix}A{i}', plant+'种子')
            edge(f'{prefix}C{i}', f'{prefix}B{i}', plant+'种子')
            edge(f'{prefix}A{i}', f'{prefix}C{i}', plant)
            edge(f'{prefix}B{i}', f'{prefix}K{i}', plant)
            targets=S_GROUPS[i-1] if prefix=='S' else (f'Q{i}',)*(2 if i<=5 else 1)
            for target in targets: edge(f'{prefix}K{i}', target, plant+'粉末')
    for prefix,count in [('E',3),('F',4)]:
        for i in range(1,count+1):
            node(f'{prefix}{i}',prefix)
            edge(f'{prefix}{i}', '核心', RECIPES[prefix][2])
    incoming=defaultdict(list); outgoing=defaultdict(list)
    for j,(a,b,item) in enumerate(routes):
        incoming[b].append(j); outgoing[a].append(j)
        assert a not in nodes or nodes[a][2]==item
        assert b not in nodes or item in nodes[b][1]
    for name,rec in nodes.items():
        assert set(rec[1])=={routes[j][2] for j in incoming[name]}
        assert len(outgoing[name]) <= (6 if rec[0] in ('研磨机','封装机','灌装机') else 5 if rec[0] in ('采种机','种植机') else 3)
    return nodes,routes,incoming,outgoing
