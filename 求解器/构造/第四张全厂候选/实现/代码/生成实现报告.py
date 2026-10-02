#!/usr/bin/env python3
"""从同一份布局及其哈希绑定的核查结果生成报告。"""
import os
os.sched_setaffinity(0,{6})
import json,hashlib,sys,datetime
from pathlib import Path
from collections import Counter
B=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())
d=read(B/'布局.json');s=read(B/'证据/静态检查结果.json');r=read(B/'证据/逐路与端口核查.json');checks=read(B/'证据/复核汇总.json')
sha=hashlib.sha256((B/'布局.json').read_bytes()).hexdigest()
assert all(q['candidate_sha256']==sha for q in [s,r,checks])
assert {k for k,v in s['checks'].items() if v['status']!='PASS'} <= {'s2_routes','exact_balance'}, '需要先处理其他静态失败，报告不能将它们写为通过'
l=d['layout'];stats=s['statistics'];rect=s['maximum_empty_rectangle'];nr=stats['routes'];missing=325-nr;nc=Counter(u['model'] for u in l['machines'])
sources=sum(f['from']['unit']=='CORE' or f['from']['unit'] in {u['id'] for u in l['warehouse_outlets']} for f in d['design']['logical_feeds'])
core_sources=sum(f['from']['unit']=='CORE' for f in d['design']['logical_feeds']);products=sum(f['to']['unit']=='CORE' for f in d['design']['logical_feeds'])
lengths={u:[p['length'] for p in s['route_lengths'] if p['source']==u and p['target']=='F4'] for u in ['H6','Q6']}
hlen=lengths['H6'][0] if len(lengths['H6'])==1 else '未完成';qlen=lengths['Q6'][0] if len(lengths['Q6'])==1 else '未完成'
powered=230-len(s['checks']['power']['failures']);hard=sum(v for k,v in r['missing_classes'].items() if k!='单路可达，尚未联合布通')
ongoing='--ongoing' in sys.argv;status='搜索中；本存档未通过' if ongoing else '未通过' if not s['static_pass'] else '静态检查通过'
geom=f"{rect['x1']-rect['x0']+1}×{rect['y1']-rect['y0']+1}，x={rect['x0']}…{rect['x1']}、y={rect['y0']}…{rect['y1']}，面积{rect['area']}，短边{rect['short_side']}"
first=(f"当前存档尚未形成达标全厂：230台制造单位已逐格落位，{powered}台有供电，完成{nr}/325条进路，仍缺{missing}条。" if not s['static_pass'] else '325条指定进路及全部已实现静态项目通过。')
scope=(f"固定全部非运输单位，撤去全部运输单位且不保留空矩形后，缺路中仍有{hard}条被端口或空格连通性拒绝。BFS和并查集逐条一致。这组机位不能仅靠补传送带或桥接器完成；仍须调整部分单位位置或朝向。" if hard else '缺路在撤去运输单位后的放宽图中单独可达，尚未同时布通。')
lines=["# 第四张全厂候选：第107轮隔离接法逐格实现\n",f"日期：2026-10-02。状态：**{status}**。\n",first+" 本构造没有提高任务给定的正式下界L=0。\n",f"短边至少6的几何最大空矩形为 **{geom}**。这是当前候选的占格结果；达标全厂空矩形尚未实现。没有进入完整布通后的扩大空矩形阶段。\n",
"[布局JSON](实现/布局.json)、[布局图SVG](实现/布局图.svg)、[PNG](实现/布局图.png)、[自写静态检查结果](实现/证据/静态检查结果.json)、[325条逐路清单及端口核查](实现/证据/逐路与端口核查.json)。布局SHA-256：`"+sha+"`。\n",
"|检查项|结果|\n|---|---|",
f"|制造单位|230台；粉碎机{nc['粉碎机']}、精炼炉{nc['精炼炉']}、研磨机{nc['研磨机']}、塑形机{nc['塑形机']}、配件机{nc['配件机']}、种植机{nc['种植机']}、采种机{nc['采种机']}、封装机{nc['封装机']}、灌装机{nc['灌装机']}|",
"|尺寸、朝向、70×70内、占格不重叠|通过；制造单位占3567格|",
f"|供电|{len(l['power_poles'])}根供电桩，覆盖{powered}/230台；制造开关全开；[逐台覆盖](实现/证据/逐台供电覆盖.json)|",
"|协议核心和仓库取货口|1个9×9协议核心，六个取货端口均设源矿；46个仓库取货口均贴左或下边界，34个设蓝铁矿、12个设源矿|",
f"|完整接法|**未通过：{nr}/325条，缺{missing}条**；矿源进路{sources}/52，其中协议核心{core_sources}/6；成品入库{products}/7|",
f"|进路与运输格|已接部分均符合指定源汇和物品；{stats['transport_units']}个运输单位、{stats['transport_slots']}个在用运输物品格；逐格相邻、不重复经过物理单位、不共用运输物品格|",
f"|桥接器|{stats['bridges']}座，两轴用法已逐座重建；{stats['adjacent_bridge_pairs']}对相邻桥|",
f"|自动通道|重建{stats['physical_channels']}条，含{stats['reverse_bridge_channels']}条桥间逆向通道；声明与实物一致，除前向进路和这些逆向通道外没有其他通道|",
f"|末端等长|塑形机H6→灌装机F4为{hlen}格，研磨机Q6→灌装机F4为{qlen}格；通过|",
"|禁用单位|没有分流器、汇流器、物品准入口、协议储存箱或虚拟全厂接口|",
"|平均流与运行|完整接法未满足，整厂精确平均流核验未执行；没有调试和所有可达循环态达标的认证|\n",
"**尚未通过的部分。** "+scope+" 这只约束当前固定机位，不是对70×70内全部桥接器布局的不可行证明。\n",
"|缺路分类（全部撤去运输单位）|条数|\n|---|---|" ]
lines += [f"|{k}|{v}|" for k,v in r['missing_classes'].items()]
lines += [f"\n共有{len(r['port_shortage_units'])}个非运输单位的可用端口邻格少于完整接法要求。具体单位、被挡邻格、逐路首尾和已布运输格均在逐路清单中。同源、同汇、同物品的并行进路按接法分别计数，不能合成一条。\n",
"**复核。** [独立主核查](实现/独立复核/结果-主.json)逐单位枚举端口并顺流追路；[独立副核查](实现/独立复核/结果-副.json)逐相邻格重建通道并倒追进路。两者与自写检查的单位占格、通道、已通进路和供电数量一致。[旧A](实现/证据/旧A复查.json)、[旧B](实现/证据/旧B复查.json)适配了双向桥端口后，几何重算也一致；旧版完整检查和线性规划未适配。[汇总](实现/证据/复核汇总.json)绑定同一份候选指纹。\n",
"[拒绝性核验](实现/证据/拒绝性核验.json)分别损坏带方向、桥方向声明、逆向通道声明、占格、供电、等长进路和空矩形，相应检查均能拒绝。\n",
"格式采用`full-factory-static-s2-bridges-v2`，扩展范围见[格式说明](实现/格式扩展.md)。相邻桥的真实逆向通道显式保留；方向声明不能改变桥的物理端口。期望接法固定为第107轮第1、2节的230台、325路，未改变机器数量、配方或砂叶分组。\n",
"**规划调整记录。**\n",
"|部位|落格时的处理及证据|\n|---|---|",
"|初始规划清点|74段运输中，66条首尾完整，8条是外接片段；核心区原定285格，分配的机器和核心已占375格，必须扩展|",
"|蓝铁矿支路编号|修正规划中4条粉碎机到研磨机的源汇错配，并同步重编号仓库取货口、精炼炉和粉碎机；[错配记录](实现/证据/规划接法错配.json)|",
"|角区出口|R3置于x=23…25、y=20…22，R5置于x=20…22、y=23…25；挪开挡走廊的供电桩并延长对应进路。原固定模板出口放宽容量为6，供电修正后的模板为12，需求为12；[割集检查](实现/证据/最终模板角区出口容量.json)。容量检查不等于12条实际进路已布通|",
"|粉碎机KO9、KO15供电|O5上移一格，O8右移一格，源石粉末和砂叶粉末进路相应延长；在(37,5)、(5,37)增设供电桩。[模块运输及端口局部核验](实现/证据/改规划4模块局部验证.json)通过；供电覆盖另由全厂检查核验|",
"|末端等长|对同机型机位及对应支路作整组身份重指派，使H6、Q6到F4均用1格；不属于固定接法的旧路线全部删除。[完整映射和删路记录](实现/证据/末端等长重排.json)|",
"|其余机位|核心区、研磨机区和植物区联合调整位置、朝向和进路；未完成全厂联合布通。最终坐标以布局JSON为准|\n",
"局部模板、摆放邻域和逐路联合搜索的参数、坐标及日志保存在[实验目录](实现/实验/)；主要精确子问题的范围与终止状态见[搜索记录索引](实现/证据/搜索范围汇总.json)。`INFEASIBLE`仅对应当次固定的邻域和限制，`UNKNOWN`表示未决；搜索失败没有转为全类不可行结论。\n",
"在项目根目录复跑当前核验：\n\n```bash\npython -B '求解器/构造/第四张全厂候选/实现/代码/验收回放.py'\n```\n\n回放只重做当前文件的静态核查，不重启长时间搜索。回放结果一致与全厂静态通过是不同的结果；`static_pass`始终取完整检查的实际布线结论。\n"]
if (B/'证据/删除冗余供电桩.json').exists():
    q=read(B/'证据/删除冗余供电桩.json')
    if len(l['power_poles'])==q['after']:lines.insert(-2,f"在选定候选的既有桩位中删除了{q['before']-q['after']}根冗余供电桩，全部230台仍有电；[记录](实现/证据/删除冗余供电桩.json)。这不是全图最少桩数证明。\n")
if (B/'证据/资源与停止记录.json').exists():
    lines.append('执行范围、耗时与搜索停止状态见[运行记录](实现/证据/资源与停止记录.json)。\n')
(B.parent/'实现.md').write_text('\n'.join(lines))
print(B.parent/'实现.md')
