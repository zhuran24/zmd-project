import json
from pathlib import Path
v=Path(__file__).resolve().parent
cases=[]
def add(name,units,inventory,ticks=12,**expect):
    cases.append(dict(name=name,units=units,inventory=inventory,ticks=ticks,expect=expect))
def b(i,x,y,r='r0'):return [i,'桥接器',x,y,r]
def t(i,x,y,r='r0'):return [i,'传送带',x,y,r]
add('straight', [b('b',20,20),t('in',20,19),t('out',20,21)], [['in:transport:0','源矿',1,None]],out={'out:transport:0':1},channels=2)
add('two-inward', [b('b',20,20),t('south',20,19),t('north',20,21,'r180')], [['south:transport:0','源矿',1,None],['north:transport:0','蓝铁矿',1,None]],trapped=True,channels=2)
for n in [2,3]:
    for direction in ['east','west','north','south']:
        horizontal=direction in ['east','west'];sign=1 if direction in ['east','north'] else -1
        rot={'east':'r270','west':'r90','north':'r0','south':'r180'}[direction]
        def xy(k): return (20+sign*k,20) if horizontal else (20,20+sign*k)
        units=[b(f'b{i}',*xy(i),'r90' if i%2 else 'r0') for i in range(n)]
        units += [t(f'feed{i}',*xy(-1-i),rot) for i in range(5)]
        units += [t(f'exit{i}',*xy(n+i),rot) for i in range(6)]
        inv=[[f'feed{i}:transport:0',item,1,None] for i,item in [(0,'源矿'),(2,'蓝铁矿'),(4,'砂叶')]]
        add(f'chain-{n}-{direction}-gaps',units,inv,24,chain=n,direction=direction,channels=(n-1)*2+10+1)
for rotation in ['r0','r90','r180','r270']:
    add(f'empty-adjacent-{rotation}',[b('a',20,20),b('b',21,20,rotation)],[],6,empty=True,channels=2)
base=[b('b',20,20),t('west',19,20,'r270'),t('east',21,20,'r270')]
add('axis-belt-control',base,[['west:transport:0','蓝铁矿',1,None]],out={'east:transport:0':1},channels=2)
add('axis-splitter-busy',base+[['split','分流器',20,19,'r0'],t('north',20,21)], [['west:transport:0','蓝铁矿',1,None],['split:transport:0','源矿',1,None]],out={'east:transport:0':1,'north:transport:0':1},axis_independent=True,channels=4)
add('axis-splitter-blocked',base+[['split','分流器',20,19,'r0']], [['west:transport:0','蓝铁矿',1,None],['split:transport:0','源矿',1,None]],out={'east:transport:0':1,'b:vertical:0':1},axis_independent=True,channels=3)
add('same-item-two-axes',[b('b',20,20),t('south',20,19),t('west',19,20,'r270')],[['south:transport:0','源矿',1,None],['west:transport:0','源矿',1,None]],out={'b:vertical:0':1,'b:horizontal:0':1},same_item=True,channels=2)
(v/'cases.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
print(f'{len(cases)} independent layouts')
