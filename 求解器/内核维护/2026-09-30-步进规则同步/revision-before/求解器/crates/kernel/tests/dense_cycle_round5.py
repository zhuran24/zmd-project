"""密集结点闭环：所有分支经箱/运输回到两独立供料箱，核真实循环内竞争量。"""
import copy,json,subprocess,sys
from pathlib import Path
import round5_scenarios as s
from generate_examples import unit
from migrate_round5 import save,migrate
from runtime_example import quantity as q,time_value as t
ROOT=s.ROOT;BASE=s.OUT;BIN=s.BIN;CFG=s.CONFIG
# 已有限运行的分叉相遇几何作起点，重新由目录导出所有边和历史。
d=json.loads((BASE/'密集结点核验.json').read_text())
units=[]
for u in d['layout']['units']:
    uid=u['id']
    if uid=='core' or uid in ('source_d','source_e','fd1','fd2','fd3','fd4','fd5','fe1','fe2','fe3','fe4','fe5'):continue
    units.append(copy.deepcopy(u))
units += [unit('supply_d','协议储存箱',9,3),unit('supply_e','协议储存箱',21,3),unit('return_fork','分流器',20,7,'r180'),unit('return_merge','汇流器',20,9,'r180')]
cells={(int(u['origin'][0]['value']),int(u['origin'][1]['value'])):u for u in units if u['kind'] in ('传送带','分流器','汇流器')}
# 路径只列运输格，端点单位由已有端口接通；交叉点由桥显式双轴定向。
paths=[
 [(x,7)for x in range(19,11,-1)]+[(12,y)for y in range(6,1,-1)]+[(11,2)],
 [(20,y)for y in range(6,1,-1)]+[(21,2),(22,2)],
 [(7,15)]+[(x,15)for x in range(6,1,-1)]+[(2,y)for y in range(14,0,-1)]+[(x,1)for x in range(3,9)]+[(8,2),(9,2)],
 [(5,y)for y in range(9,-1,-1)]+[(x,0)for x in range(6,11)]+[(10,1),(10,2)],
 [(20,8)],
 [(x,11)for x in range(16,22)]+[(21,10),(21,9)]
]
ends=[((20,7),(11,3)),((20,7),(22,3)),((7,14),(9,3)),((6,9),(10,3)),((20,9),(20,7)),((15,11),(20,9))]
axis={};sides={(0,-1):'south',(1,0):'east',(0,1):'north',(-1,0):'west'}
for path,(start,end) in zip(paths,ends):
    for a,b,c in zip([start]+path,path,path[1:]+[end]):
        incoming=sides[(a[0]-b[0],a[1]-b[1])];outgoing=sides[(c[0]-b[0],c[1]-b[1])]
        axis.setdefault(b,[]).append((incoming,outgoing))
for cell,roles in axis.items():
    if cell in cells:
        old=cells[cell]
        if old['id'].startswith('fe'):
            units.remove(old);roles.append(('south','north'))
        else:raise ValueError(('碰撞',cell,old['id']))
    x,y=cell;uid=f'r{x}_{y}'
    if len(roles)==2:
        u=unit(uid,'桥接器',x,y)
        for incoming,outgoing in roles:
            key='vertical'if incoming in ('south','north')else'horizontal'
            u['bridge_axes'][key]['input_side']=incoming
        units.append(u)
    else:
        incoming,outgoing=roles[0];seq=['south','east','north','west'];i=seq.index(incoming);j=seq.index(outgoing);rotation=['r0','r90','r180','r270'][i];delta=(j-i)%4
        units.append(unit(uid,'传送带',x,y,rotation,{1:1,2:0,3:2}[delta]))
# 早先两段新增返回线的互相交叉也在axis中合为双轴桥。
d=s.b.generate('密集结点闭环核验',units)
for uid in ['supply_d','supply_e','sink_dn','sink_dw','sink_e','sink_m']:
    s.put(d,uid+':storage:0','高容谷地电池',50)
    next(r for r in d['initial_state']['nonwarehouse']['value']['inventory']if r['slot']==uid+':storage:0')['contents'][0]['entered_at']=None
# 供料箱后五格由调试条件库存占位，防止无限积在未使用空格；slot0不断流是待核前件。
for uid in ['supply_d','supply_e']:
    for index in range(1,6):
        s.put(d,f'{uid}:storage:{index}','砂叶',1)
        next(r for r in d['initial_state']['nonwarehouse']['value']['inventory']if r['slot']==f'{uid}:storage:{index}')['contents'][0]['entered_at']=None
# 先接顺序保留，扫描模板用几何uid逆序只是明确候选点，不作语义默认。
s.finish(d,'密集结点闭环核验',240,True)
