import json,collections,hashlib
from pathlib import Path
from 目录与流量 import *
base=BASE;c=load(base/'候选.json');a=load(base/'检查/甲.json');b=load(base/'检查/乙.json');s=load(base/'实验/导出摘要.json');hall=load(base/'检查/矿源割证书.json');reg=load(base/'检查/回归.json');ca=load(base/'检查/甲-重建通道.json');cb=load(base/'检查/乙-重建通道.json')
assert ca==cb
assert a['candidate_sha256']==b['candidate_sha256']==sha(base/'候选.json')
assert not a['geometry_errors'] and not a['structural_errors'] and not b['errors']
assert len(a['formal_constraints'])==len(b['formal_constraints'])==72
l=c['layout'];r=c['empty_rectangle'];w=r['x1']-r['x0']+1;h=r['y1']-r['y0']+1
full_lp=dict(candidate_sha256=sha(base/'候选.json'),graph_agreement=True,channel_count=len(ca),A_solver='SciPy/HiGHS，实体通道×物品变量，桥H/V分开',A_result=a['lp'],B_solver='OR-Tools/GLOP，独立从p2p路径消元建模，按物品逐机配方守恒',B_result=b['lp'],positive_delta='基本可行性已失败，不报告最优delta=0',product_inlet_bounds={'高容谷地电池':'1/5','精选荞愈胶囊':'0'},product_bound_reason='仅M213的封装-电池输出一条路径到CORE；单机5tick配方的批率至多1/5；无胶囊入CORE路径，无储存箱无线弧。',full_static_pass=False)
(base/'检查/连续LP汇总.json').write_text(json.dumps(full_lp,ensure_ascii=False,indent=2))
missing=[z['port'] for z in b['lp']['empty_source_equalities']]
# Formal constraints table is an implementation coverage ledger, not 71 successful checks.
lines=['# 72条正式约束检查覆盖台账','','日期：2026-09-22。状态：静态拒绝；两份检查器的完整静态覆盖尚未完成。',f'候选 SHA-256：`{sha(base/"候选.json")}`。','',
'“平均流前置检查失败”表示本候选已经没有达标连续流，不表示该条独立运行命题被反驳。“未实现”属于本工作流内未完成事项，不能当作运行范围外。两份程序共享规范数据和语法解析；占格、端口、桥、通道、矩形、供电、路径和LP建模分开实现。','',
'|序号|条名|甲|乙|前件与证据／剩余义务|','|---:|---|---|---|---|']
for i,(x,y) in enumerate(zip(a['formal_constraints'],b['formal_constraints']),1):
 assert x['name']==y['name']
 detail=x['premise']+'；'+x['remaining'];lines.append(f'|{i}|{x["name"]}|{x["status"]}|{y["status"]}|{detail}|')
(base/'检查/72条覆盖台账.md').write_text('\n'.join(lines)+'\n')
# Human-readable physical occupancy, all settings remain solely authoritative in candidate.json.
grid=[['.']*70 for _ in range(70)];symbols={'粉碎机':'c','精炼炉':'r','研磨机':'g','塑形机':'m','配件机':'a','种植机':'p','采种机':'s','封装机':'b','灌装机':'f'}
for cat in ['machines','warehouse_outlets','core','power_poles']:
 for u in [l[cat]] if cat=='core' else l[cat]:
  ch=symbols[u['model']] if cat=='machines' else {'warehouse_outlets':'O','core':'C','power_poles':'P'}[cat]
  for y in range(u['y0'],u['y1']+1):
   for x in range(u['x0'],u['x1']+1):grid[y][x]=ch
for t in l['transport']:grid[t['y']][t['x']]='#' if t['type']=='bridge' else '>^<v'[t['out_side']]
for y in range(r['y0'],r['y1']+1):
 for x in range(r['x0'],r['x1']+1):assert grid[y][x]=='.';grid[y][x]='_'
art=['# 候选占格图','','日期：2026-09-22。状态：静态拒绝布局的显示副本。',f'候选 SHA-256：`{sha(base/"候选.json")}`。','','x从左到右为0…69；y从上到下为69…0。`_`为声明矩形，`.`为其余空格。`O`仓库口、`C`核心、`P`供电桩、`#`桥、箭头为传送带出向。机型字母：'+str(symbols)+'。全部朝向、配方及设定以候选.json为准。','','```text']
for y in reversed(range(70)):art.append(f'{y:02} '+''.join(grid[y]))
art+=['```',''];(base/'布局图.md').write_text('\n'.join(art))
counts=collections.Counter(m['model'] for m in l['machines']);nomen='、'.join(f'{k}{v}' for k,v in counts.items());missdesc='、'.join(f'{p[0]}(side={p[1]},offset={p[2]})' for p in missing)
report=f'''# 第一张全厂静态候选：拒绝报告

日期：2026-09-22。状态：未达成全静态可行目标；保留一张严格字段格式的全厂摆放及95条完整路径，作为有精确拒绝证据的布局尝试。已认证布局的 L 不更新，U 不降低。

## 1. 可交接结论

`候选.json` 包含219台制造单位、真实左/下边界各23个仓库口、一个协议核心、25个供电桩、317个运输单位（305条带、12座桥），无虚拟接口、分流器、汇流器、准入口或储存箱。全体制造开关开启，219台均有供电。它不是通过冻结共识静态闸门的全厂可行候选。

两份新检查器从实体独立重建出相同的424条结构通道和95条非运输端口到非运输端口路径；几何、桥方向、无相邻桥、通道声明集合、单物品种类传播及最大空矩形一致。联合连续LP及独立路径消元LP均不可行。315条搜索送料中220条未完成，不能把已完成路径集合当作全厂送料兑现。

最大合格空矩形为左下格 **({r['x0']},{r['y0']})**，右上格 **({r['x1']},{r['y1']})**，宽 **{w}**、高 **{h}**、面积 **{w*h}**、短边 **{min(w,h)}**。两份程序分别穷举水平条带、垂直条带，按面积及短边重算得到该最优值。短边≥6；该值仅属于被拒绝布局，不是 L。

候选 SHA-256：`{sha(base/'候选.json')}`。

## 2. 摆放、指派和限制

唯一正式依据为根目录三份正式文件，指纹写在JSON内并由程序与当前字节、支持版本同时核对。正式约束按“据”行计数为72。任务启动时为71条；本轮期间正式文件被外部工作更新，mtime为2026-09-22 18:46:08 -0400，旧指纹cf44821f…、当前指纹a67c18de…。本任务未改正式文件。新增“1113 位置”对本布局面积48的前件不成立；非成品入库相关修订已经核读，LP的非成品零入库条件保持适用。当前文件全文快照见检查/正式文件版本快照.json。格式.md保持原样，字段契约未变，检查器显式登记支持当前指纹。表示和P/N类取自会议3冻结稿及格式.md。现存seat-codex-3.md是终稿，没有第六节；登记使用冻结稿§1.3和格式.md§8.3明确的来源、覆盖损失、撤去义务、失败范围四项，没有虚构旧章节。

机器配置为：{nomen}。数量与逐ID配方沿用候选B，机器实体位置不沿用任何虚拟砖。机型身份在同尺寸占格间按送料距离、空隙连通分量及矿源匹配重指派；同物品同搜索速率的送料目标也允许重指派。因此不声称保持B的315条端点指派。

边界排布固定为：左侧x=0，从y=1起每3格一个口；下侧y=0，从x=1起每3格一个口，角格(0,0)为空。52个ORE身份完整绑定到46个仓库口和核心6个真实输出端口；合计18个源矿、34个蓝铁矿。

协议核心占x=34…42、y=24…32，Din=0（左右存货、上下取货），六个输出均设蓝铁矿。24个初始桩在x、y各取8、22、36、50、64的网格交点上，去掉(64,64)；导出时补桩(62,62)，其实体为(62…63,62…63)。实际供电重新按12×12范围与机器占格交集核验。

CP-SAT的格级摆放只保证占格、端口邻格及所登记形状限制；其满足性结果“OPTIMAL”没有面积最优含义。真实布线由本轮A*点对点布线器完成，逐路径拆除后重布，交叉仅允许两条直线构成桥；候选只收完整路径。旧会议文件只读，副本置于代码/会议副本；代码、实验和结果均在本生成目录内。未运行git、cargo test或内核。CP-SAT每次配置5或6个worker，LP为单线程。早期曾在6-worker搜索仍运行时执行一次短时单线程LP，合计配置可能达到7，未严格保持全时段合计≤6；后续采用5-worker搜索加单线程检查或顺序执行，交付时无本任务遗留求解器进程。

登记共{len(c['design']['restrictions'])}项：P1–P6、N1/N2/N3a/N3b/N4a/N4b/N5a/N5b，以及`fixed-b-counts`、`all-single-recipe`、`fixed-border`、`fixed-placement`、`search-feed-reassignment`。这些是待核受限类与搜索域登记，不是自动满足的声明。单机单配方是独立限制；不能由P2推出。生成器使用B的精确速率类别引导匹配，最终JSON省略logical_feeds，LP可自行选择连续流和批率，没有把20tick网格或搜索标签当成全域流量条件。

## 3. 两份新检查器与LP

|检查|甲|乙|
|---|---|---|
|当前文件字段、正式指纹|通过已实现的p2p解析|通过同一规范解析入口|
|尺寸、边界、非重叠|零错误|零错误|
|供电|219/219，25桩|219/219，25桩|
|桥轴按邻端推导、无相邻桥|零错误|零错误|
|当且仅当通道集合|424条，声明逐端点相等|424条，与甲相同|
|完整路径、误料与设计外原料|95条，零错误|95条，零错误|
|最大空矩形|8×6=48，短边6|8×6=48，短边6|
|分物品连续LP|HiGHS INFEASIBLE|独立GLOP INFEASIBLE|
|全部静态条件|未通过|未通过|

甲以“格、边”端口字典扫描；乙以相邻格对查询单位边界。桥的方向都先从非桥邻端推导，不相信H_in/V_in声明。两份程序分别实现占格、端口、桥、通道、矩形、供电、路径检查。甲LP以物理边×物品建模；乙从自己重建的p2p路径消去运输守恒后建连续LP，两个程序没有共用通道重建函数或LP建模函数。它们共享配方目录、严格JSON及语法入口，因此不是两份完全无共享代码的格式验证器。

有限变异回归共{len(reg['cases'])}项，均验证两份检查器能拒绝：未知字段、错误指纹、遗漏通道声明、实体重叠、带子改向、桥方向翻转、假物品标签。此回归不证明两份程序已完整实现全部正式规则。

## 4. 不通过的精确原因与覆盖域

### 4.1 真实矿口断路

52个物理输出端口中只有16个具有完整路径，以下36个无完整路径：

{missdesc}

规则和格式要求每个真实矿口为1件/tick；对应LP方程的所有流变量均缺失，形成36行精确矛盾`0=1`。一个这样的方程就足以否定该固定图上的目标平均流。两份LP分别重建并报告同一组36个断口。这不是浮点容差、超时或“delta很小”的推断。基本LP已不可行，不报告最优delta=0，也没有正流见证。

### 4.2 成品入口不足

只有M213的一条高容谷地电池路径进入CORE，没有胶囊路径，没有箱体无线入库。因此，即使免费补足各制造原料，仓库电池速率仍至多1/5，小于3/5；胶囊为0，小于11/20。实测运行未做，也不把这个上界当成实测产率。

全部结构通道中S=95、R=95、E=234；正流支撑数不超过结构数，已经低于正式S≥312、R≥307。无箱无汇流时，成品汇入所需K≥6，本图只有K=1。逐机型通道下限的不足记录在甲.json相应条目。

### 4.3 固定摆放的更强拒绝证书

[矿源割证书](检查/矿源割证书.json)独立重算矿口到首个小型制造单位的可达二分图，并用整数增广路求匹配与Hall集。甚至允许所有空格（包括留白）作不计容量的无向道路、允许任意重指派小机型，最大匹配仍只有20。证书的一个源集含46个矿口，其全部可达小机邻域仅14个位置，缺额32。

源必须各输出1件/tick，首个消耗原矿的小机至多1批/tick，故该Hall缺额拒绝这一固定摆放的全厂p2p供矿。证书基于初始24桩摆放，放宽移除了导出时新增的P024；增加该障碍不可能修复缺额，所以证书仍适用于最终实体布局。它不拒绝改变机器位置/朝向、边带位置等其他布局，也不降低U。

失败记录固定候选SHA、检查器SHA、正式指纹、实体与设计物品；连续流与批率仍开放。所查量词是“该固定静态布局是否存在达标平均流”。初态、调试和合法先后未作为排除依据。

## 5. 搜索覆盖与结果

|实验|固定条件|结果与范围|
|---|---|---|
|植物单砖10×10、10×11、11×11|2种植、1采种、1粉碎，无外部植物源，3个粉末输出|各为INFEASIBLE，只排除所列封闭砖模型|
|逐ID矩形摆放|219台、24桩、核心和6×6留白，送料距离目标|180秒UNKNOWN|
|匿名矩形摆放|同尺寸位置排序消对称，固定桩和核心|150秒UNKNOWN|
|离散端口邻格摆放|219台、24桩、右上6×6留白|164.6秒找到满足性解，后被矿源割否定|
|全进出料边留空＋贯通十字走廊|固定24桩、219台和留白|300.3秒UNKNOWN|
|匿名三尺寸＋42个非角区边界矿口直供|全端口边留空，固定桩与留白|300.2秒UNKNOWN|

最后两次UNKNOWN没有可导出布局，也不是不可行证明。早期较多路径的版本未通过最终结构互核，其中102条版本含相邻桥；修复后的一份99条版本仍被检查器抓到路径重建错误。最终95条版本经过重建互核，没有保留这些错误。早期实验文件不是可交付布局；最终唯一输入为候选.json。最终生成脚本为固定矿线指派.py（seed=5）加导出候选.py。

## 6. 本工作流内未完成与范围外

本工作流内尚未完成：找到全厂达标布线；让两份连续LP通过；完成两份检查器对72条正式约束的全部静态投影。甲至少尚未实现角区、核心离带、核心取货边朝带、运输降幅、面积预算、侧旁供电、矩形离带、矿石走廊、内带缺口的完整细项；供电单桩细分上限、运输下限的细分条件等也没有完整编码。植物再生路径、任意分区收支及其他正流支撑细项在平均流失败后未完成。乙的逐条覆盖更少。完整状态见[72条覆盖台账](检查/72条覆盖台账.md)。这些缺项本属于静态范围，不能解释成不需要做。

明确在本次范围外：植物第一批种子/植株取得；蓝图及调试办法；调试后允许初态和库存；制造缓存与每格50件的逐事件界；轮询服务、取货阻尼与运行死锁证明；接通先后、分叉分支、传输相位、固定判定先后的全部允许取值；离线接续状态；全部相关可达循环态均达标；内核运行。静态JSON没有这些时间状态或调试证据，本次也未运行内核。即使将来静态通过，也不能自动完成这些义务或更新L。

## 7. 文件与复核

主文件为[候选.json](候选.json)、本报告、[布局图](布局图.md)。检查原始结果为[甲.json](检查/甲.json)、[乙.json](检查/乙.json)、[连续LP汇总](检查/连续LP汇总.json)、[矿源割证书](检查/矿源割证书.json)、[回归](检查/回归.json)。全部新文件及绝对路径见[文件清单](文件清单.md)，版本字节见[交付哈希](交付哈希.json)。复核命令见[静态复核命令](静态复核命令.md)。

后续构造需改变被Hall证书否定的摆放，并在摆放阶段保留真实52矿口的首个加工能力与跨区容量；给当前固定摆放继续换路由次序不能完成目标。
'''
(base/'报告.md').write_text(report)
cmd=f'''# 静态复核命令

日期：2026-09-22。状态：可复核拒绝结果；不涉及内核和游戏运行。

工作目录为 `{ROOT}`。下列命令顺序执行；BLAS与LP单线程，CP-SAT实验最多6个worker。没有git或cargo命令。

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python 求解器/构造/第一张全厂候选/生成/代码/检查器甲.py 求解器/构造/第一张全厂候选/生成/候选.json 求解器/构造/第一张全厂候选/生成/检查/甲.json
python 求解器/构造/第一张全厂候选/生成/代码/检查器乙.py 求解器/构造/第一张全厂候选/生成/候选.json 求解器/构造/第一张全厂候选/生成/检查/乙.json
python 求解器/构造/第一张全厂候选/生成/代码/检查器回归.py
python 求解器/构造/第一张全厂候选/生成/代码/矿源割证书.py 求解器/构造/第一张全厂候选/生成/实验/离散摆放-首版.json
```

预期：两份几何/通道重建均为424条、95条路径、48格矩形，结构错误为空；两份LP不可行且36个矿口方程为0=1；矿源Hall证书46对14、缺额32。候选不通过全静态检查。

从保存的确定性路由数据重新导出：

```bash
python 求解器/构造/第一张全厂候选/生成/代码/导出候选.py 求解器/构造/第一张全厂候选/生成/实验/布线-5.json
```

`实验/匿名直供摆放.json`和`实验/贯通摆放.json`是UNKNOWN记录，没有布局，不得送入布线器或转换为空布局。
'''
(base/'静态复核命令.md').write_text(cmd)
# List every produced file. Manifest self digest is intentionally excluded to avoid recursion.
listpath=base/'文件清单.md';hashpath=base/'交付哈希.json'
paths=sorted(set(list(base.rglob('*'))+[listpath,hashpath]))
pathlines=['# 新文件及目录清单','','日期：2026-09-22。状态：本轮静态拒绝交付文件。','',f'所有新文件都位于 `{base}`；格式.md和会议归档未改。','', '## 目录','']
for p in paths:
 if p.is_dir():pathlines.append(f'- `{p}`')
pathlines+=['','## 文件','']
for p in paths:
 if not p.is_dir():pathlines.append(f'- `{p}`')
listpath.write_text('\n'.join(pathlines)+'\n')
manifest=dict(candidate_sha256=sha(base/'候选.json'),files=[dict(path=str(p.resolve()),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(base.rglob('*')) if p.is_file() and p!=hashpath],self_hash_omitted=True,official_files={k:dict(path=str(ROOT/v),sha256=sha(ROOT/v)) for k,v in FILES.items()},reader_review='日期状态、静态拒绝边界、数值、真实引用和路径已自审；未把未实现静态项归入运行范围外。')
hashpath.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('report',base/'报告.md','files',len(manifest['files']))
