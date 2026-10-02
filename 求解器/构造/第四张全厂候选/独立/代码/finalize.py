#!/usr/bin/env python3
import json,csv,hashlib,datetime,re
from pathlib import Path
from collections import Counter,defaultdict
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[3];parent=BASE.parent;ck=json.loads((BASE/'静态检查结果.json').read_text());st=ck['stats'];extra=json.loads((BASE/'结果/补充统计.json').read_text());select=json.loads((BASE/'结果/交付候选选择.json').read_text());layout=json.loads((BASE/'布局.json').read_text())
now=datetime.datetime.now(datetime.timezone.utc);started=datetime.datetime.fromisoformat('2026-10-02T16:27:18+00:00');elapsed=(now-started).total_seconds()
sourcechecks=[]
for z in json.loads((BASE/'依据/指纹.json').read_text()):
 p=Path(z['path']);h=hashlib.sha256(p.read_bytes()).hexdigest();sourcechecks.append({'path':str(p),'recorded_sha256':z['sha256'],'current_sha256':h,'unchanged':h==z['sha256']})
(BASE/'结果/输入未改动核验.json').write_text(json.dumps({'all_unchanged':all(z['unchanged'] for z in sourcechecks),'files':sourcechecks},ensure_ascii=False,indent=2)+'\n')
rows=[];modelresults=[]
for p in (BASE/'迭代').rglob('*.json'):
 try:d=json.loads(p.read_text())
 except (json.JSONDecodeError,UnicodeDecodeError):continue
 if isinstance(d,dict) and 'units' in d and 'paths' in d:
  rows.append({'file':str(p.relative_to(BASE)),'seed':d.get('seed',''),'elapsed':d.get('elapsed',''),'overlap':d.get('overlap',''),'completed_route_records':sum(bool(x.get('cells')) for x in d['paths']),'port_deficit':d.get('deficit',d.get('port_pack',{}).get('port_slack','')),'power_distance':d.get('power_distance',''),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 if isinstance(d,dict) and 'status' in d and 'wall_seconds' in d and ('result' in p.name or p.name.endswith('.cp.json')):modelresults.append({'file':str(p.relative_to(BASE)),**{k:d.get(k) for k in ['status','wall_seconds','radius','solutions','workers','route'] if k in d}})
with (BASE/'迭代索引.tsv').open('w') as f:
 keys=['file','seed','elapsed','overlap','completed_route_records','port_deficit','power_distance','sha256'];w=csv.DictWriter(f,fieldnames=keys,delimiter='\t');w.writeheader();w.writerows(sorted(rows,key=lambda z:z['file']))
(BASE/'结果/整数模型结果索引.json').write_text(json.dumps(modelresults,ensure_ascii=False,indent=2)+'\n')
byrun=defaultdict(list)
for z in rows:
 name=Path(z['file']).name
 run=re.split(r'-(?:legal|iteration|initial|best|maxroutes|final|start|solution)',name)[0]
 byrun[run].append(z)
summary={'raw_state_files':len(rows),'integer_model_records':len(modelresults),'status_counts':dict(Counter(z['status'] for z in modelresults)),'selected_raw_state':select['raw_source'],'note':'状态索引中的进路数为搜索记录数，不能代替实体静态核查。全局机位指派的端口分配数不计为进路。'}
(BASE/'结果/迭代汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
state={'status':'已结束；未找到达标全厂','started_utc':started.isoformat(),'finished_utc':now.isoformat(),'elapsed_seconds':elapsed,'deadline_utc':'2026-10-02T20:27:18Z','within_four_hours':elapsed<=14400,'max_cpu_cores':6,'cpu_affinity_union':[0,1,2,3,4,5],'static_pass':ck['static_pass'],'completed_routes':st['completed_routes'],'total_routes':325,'layout_sha256':ck['layout_sha256'],'git_used':False,'kernel_cargo_tests_run':False,'write_root':str(parent)}
(BASE/'执行状态.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
n=st['completed_routes'];miss=st['missing_routes'];blocked=st['fixed_geometry_obstructed'];r=st['empty_rectangle']['rectangle'];w=r['x1']-r['x0']+1;h=r['y1']-r['y0']+1
report=f'''# 第107轮桥接器接法：独立构造结果

日期：2026-10-02。状态：**本轮未找到达标全厂，`static_pass=false`。** 主候选接通{n}/325条进路，缺{miss}条；230台制造单位均有供电。正式下界L仍为0。本结果没有证明该接法在所有70×70布局中不可实现。

主候选为[布局.json](独立/布局.json)，SHA-256为`{ck['layout_sha256']}`。它的几何最大空矩形是 **{w}×{h}，左下角({r['x0']},{r['y0']})，面积{w*h}**；这块空地属于未达标候选，不能计为下界。

![未达标主候选的实际单位和进路](独立/布局图.png)

## 交付文件

- [布局JSON](独立/布局.json)、[布局图SVG](独立/布局图.svg)、[布局图PNG](独立/布局图.png)。
- [自写静态检查程序](独立/代码/check_static.py)、[静态检查结果](独立/静态检查结果.json)。检查结果以实体坐标、端口和自动通道重建，不把声明的进路当成已接通事实。
- [230台逐台核查表](独立/逐台核查.tsv)、[325路逐路核查表](独立/逐路核查.tsv)，包括全部缺路。
- [独立几何数字复算](独立/结果/独立几何数字复算.json)、[9类错误的拒绝性检验](独立/结果/检查器拒绝性检验.json)。
- [迭代索引](独立/迭代索引.tsv)、[原始状态和日志](独立/迭代/)、[整数模型结果索引](独立/结果/整数模型结果索引.json)、[执行状态](独立/执行状态.json)。
- [格式及恢复说明](独立/格式说明.md)、[本次接法](独立/逻辑接法.json)、[规则依据快照](独立/依据/)。

## 主候选核验

|项目|核验结果|
|---|---|
|70×70内、单位尺寸、旋转、占格互斥|通过|
|制造单位|粉碎机71、精炼炉51、研磨机32、塑形机6、配件机6、种植机38、采种机19、封装机3、灌装机4；共230台，机身3567格|
|配方及制造开关|230台与第107轮逐台接法一致，制造开关全开|
|协议核心|一个9×9核心，六个取货端口均设源矿；设定合法不代表六路都接通|
|仓库取货口|46个，左、下各23个；34个设蓝铁矿、12个设源矿|
|供电|25个2×2供电桩，230台制造单位全部覆盖|
|已建运输单位|{st['transport_units']-st['bridges']}格传送带、{st['bridges']}座桥接器，共{st['transport_units']}个实体，占用{st['transport_cells_used']}个运输物品格|
|自动通道|{st['automatic_channels']}条，其中前向{st['automatic_channels']-st['bridge_reverse_channels']}条、相邻桥逆向{st['bridge_reverse_channels']}条；声明与重建一致，无额外通道|
|已接进路|{n}条，均属于指定接法；逐格连续、至少一格、不重复物理单位、不共用运输物品格|
|桥接器|双轴分属不同进路；{len(extra['adjacent_bridge_pairs'])}对相邻桥，最长同轴直串{extra['longest_collinear_bridge_chain']}座；逆向通道完整列出|
|禁用单位|没有分流器、汇流器、物品准入口、协议储存箱或虚拟接口|
|完整接法|失败：缺{miss}条；矿石进路接通{st['ore_routes']}/52，成品入库接通{st['product_routes']}/7|
|H6→F4与Q6→F4等长|失败：塑形机H6→灌装机F4缺失；研磨机Q6→灌装机F4为1格|
|全厂平均物料收支和交付目标|失败；缺路的实际图不满足规定的全厂流量|
|几何最大空矩形|{w}×{h}，({r['x0']},{r['y0']})；二维前缀和枚举4601025个候选矩形，确认位置唯一|

当前唯一成品入库路是灌装机F4→协议核心，运输物品格数14。三台封装机都没有入库进路，不能持续向仓库交付高容谷地电池。没有执行或宣称完成全厂调试、动态运行、全部可达循环态认证。

## 具体阻塞与结论范围

**{blocked}条缺路被固定机位阻断。** 撤去全部运输单位，固定制造单位、协议核心、仓库取货口和供电桩，允许所有剩余格任意转弯、交叉，连原空矩形也允许经过，仍找不到相接的首末运输格连通块。余下{miss-blocked}条缺路只记为未接通，没有证明它们可以同时布出。逐路清单见静态结果和逐路核查表。

**这组机位还违反运输格数的必要条件。** 对325条进路，各取首末运输格横向距离加纵向距离再加1的最小值，相加为{st['transport_length_lower_bound']}。这一步忽略障碍、端口争用和进路冲突，只会低估运输物品格需求。非运输占格为3886；保留至少6×6空地后，至多剩978个运输实体位置，即使每一格都使用双轴桥，也至多提供{st['transport_slot_upper_bound']}个物品格。`{st['transport_length_lower_bound']}>{st['transport_slot_upper_bound']}`，所以保持逐台坐标与朝向，仅拆换运输单位不能补成完整接法。

这些是对主候选的拒绝证据，不是第107轮接法全类无解的证明。833是该接法的面积预算上界，不是可实现值；主候选不达标，因此不计算“833减去36”作为最优性差距。

## 实际搜索与存档

先按七台成品机的上游分组粗摆；反复执行拥塞加权寻路、拆线重布、机身移动与旋转、同尺寸交换及成组推移。随后保留不受影响的线路，只拆除被移动机身影响或与缺路争用的线路；增加矿石链、采种单元等区块的身份重分配。仓库取货口的设定和位置映射始终维持34条蓝铁矿、12条源矿，协议核心六路仍为源矿。

摆放调整同时使用单路可达性、端口缺口、实际已接进路数和运输格数需求。另实际运行了局部整数重摆、为缺路预留运输格、固定机位的全局端口指派、全厂端口修复，以及小制造单位的重新装填。整数模型的`FEASIBLE`只表示其记录的子问题可行；端口指派不是实体进路。`UNKNOWN`不表示不可行，局部`INFEASIBLE`只覆盖该次固定的范围。

运行中保存了{len(rows)}份含完整机位和路径列表的搜索状态；索引逐份记录路径、阶段数据及SHA-256。外层摆放与布线轮次通常每30—40秒保存快照，整数子问题的输入、结果和找到的坐标也分别保存。内层单次扰动不是独立交付布局。未接通全部325路，因而没有进入扩大预留空矩形的阶段。

在项目根目录执行下列命令可重算主候选检查，不启动长时间搜索：

```bash
bash '求解器/构造/第四张全厂候选/独立/复核.sh'
```

复核程序正常结束只表示记录重新算完；布局是否通过必须读取`static_pass`，当前为false。原检查器A/B未作本次全厂认证。自写检查器覆盖上述几何、端口、通道、配方、供电、固定接法、等长和有理数收支；不把这些静态检查说成已经执行动态调试。

本次墙钟约{int(elapsed//3600)}小时{int(elapsed%3600//60)}分，计算进程亲和性限定在CPU 0—5，单次整数求解至多4个工作线程，并与其他计算共享这6个核。输入文件字节核验见[输入未改动核验](独立/结果/输入未改动核验.json)。
'''
(parent/'独立.md').write_text(report)
with (BASE/'迭代记录.md').open('a') as f:
 f.write(f'\n- 交付时：主候选经实体检查为{n}/325路，230台全部供电，最大空矩形{w}×{h}；未达标。静态证据确认固定机位下{blocked}条不可达，运输格数下界{st["transport_length_lower_bound"]}超过上限{st["transport_slot_upper_bound"]}。\n- 全厂全端口硬修、允许移动供电桩、匿名重摆小制造单位等有时限子问题均未提供完整全厂证书，具体状态保存在整数模型结果索引；全局机位端口指派经实际重布仅接通162条，未替换主候选。\n- 运行归档完成于{now.isoformat()}，含完整机位和路径列表的状态{len(rows)}份。\n')
print(json.dumps({'elapsed_seconds':elapsed,'state_files':len(rows),'models':len(modelresults),'report':str(parent/'独立.md'),'stats':st},ensure_ascii=False))
