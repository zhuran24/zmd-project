"""包三数据重锁及覆盖表暂存；原样核对77条正式约束。"""
import importlib.util,json,re
from pathlib import Path
from guard import OUT,ROOT,REPO,digest,save
S=OUT/'package3-staging'
def put(p,t):
 q=S/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(t.strip()+'\n')
cat=json.loads((ROOT/'数据/正式静态目录.json').read_text())
p=ROOT/'内核维护/2026-09-26-第88-89轮三审同步/work.py'
spec=importlib.util.spec_from_file_location('old_work_readonly',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
for rel,fn in [('规格/规则覆盖表.md',m.rebuild_semantics_table),('数据/规则覆盖表.md',m.rebuild_contract_table)]:
 t=(ROOT/rel).read_text(); assert fn(t,cat)==t,rel
save('package3-constraints-before.json',{'spec_rebuild_unchanged':True,'data_rebuild_unchanged':True,'count':77})
# 对齐约束登记仍引用的§4.2轮询及§4.3速率，保持其77行原字节。
p=S/'规格/运行语义.md';sem=p.read_text()
start=sem.index('## 4. 一步内');end=sem.index('## 5. 起动')
blocks={int(n):body.strip() for n,body in re.findall(r'^### 4\.(\d+) (.*?)(?=^### 4\.|\Z)',sem[start:end],re.M|re.S)}
mapping={1:'4.1',2:'3.2',3:'3.3',4:'3.4',5:'4.4',6:'4.5',7:'4.2',8:'4.6',9:'4.7',10:'4.8',11:'4.9',12:'4.10',13:'4.11',14:'4.12',15:'4.3'}
def refs(t):return re.sub(r'§4\.(\d+)',lambda x:'§'+mapping[int(x[1])],t)
old=(ROOT/'规格/运行语义.md').read_text()
h=old.split('### 4.3 一个 tick 内可以有多少次移动',1)[1].split('“同一时刻”是一组时间标签',1)[0]
h=h[h.index('设 H 为'):].strip()
h=h.replace('规则 29','规则 32').replace('同侧统一单件','每tick同侧统一单件')
blocks[15]='运输速率与条件必要性\n\n'+blocks[15].split('\n',1)[1].strip()+'\n\n'+h+'\n\n回路存量的观察取每步判定完成后的边界；每tick条件量按8步换算。'
blocks[7]+='\n\n正式轮询均分须同时核同级k条、每件可走任一条、首格独占且收后恰1 tick腾空、恰隔1 tick成组、全空首格及相邻组件数和≤k等全部前件；不得以平均间隔替代实际组间隔。分流器直连汇流器且另一支有量时，约束·密集结点要求核先后影响，不能无条件按端口数均分。'
pre=refs(sem[:start]);post=refs(sem[end:])
pre+='\n'+ '\n\n'.join('### '+mapping[i]+' '+refs(blocks[i]) for i in [2,3,4])+'\n\n'
body='## 4. 一步内的运行语义\n\n'+'\n\n'.join('### '+mapping[i]+' '+refs(blocks[i]) for i in [1,7,15,5,6,8,9,10,11,12,13,14])+'\n\n'
put('规格/运行语义.md',pre+body+post)
# 规则逐行去向全部重建，包括标题及空行。
rule=(REPO/'《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
task=(REPO/'求解任务.txt').read_text().splitlines()
assert len(rule)==115 and len(task)==15
mapped={4:('§4.1、§4.3','1 tick=8步，率按tick计'),5:('§2.2','空间及合法占格'),8:('§1、§2.2','70×70基地及几何'),9:('§3.1、§5','建造接通历史，运行中建成停止'),10:('§3.1、§5','重建重新接通，后效未覆盖'),11:('§2.2、§5','朝向及调试权限'),12:('§2.2','正式端口及相遇谓词'),13:('§2.1、§2.2','单格单种、同单位同种单格及例外'),14:('§2.1、§5','仓库身份、容量、环境及周期'),15:('§2.2、§4.6','对应存取格与选货'),16:('§2.2、§3.1','几何形成通道，接通历史'),17:('§2.2、§4.8','制造普通格与容量'),18:('§4.8','开工时一次收用量，完成批可出即整批出'),19:('§2.2','供电由几何导出'),20:('§4.1、§4.8、§4.9','制造/传输停用时进度保留'),21:('§2.1、§5','开关是设定，动态操作另核'),22:('§5、§4.10','设定权限及动态后效停止域'),23:('§4.3、§4.7','运输每格至少8步'),24:('§4.7、§4.12','带内即时前挪、禁止回到刚离开的单位'),25:('§4.1','结束制造→判定→开始制造，玩家在步间'),26:('§4.4、§4.6','每主体每步一次，至多外送一件'),27:('§3.4','层数、最早外送接通序及非运输次序'),28:('§3.3','下游层数与显式选支/环锚点'),29:('§3.2','首尾最长带链、特别单位、桥分轴'),30:('§3.1','通道形成即接通，蓝图中由建成历史派生'),31:('§4.5','非分流器上游被最早成员带动判定'),32:('§4.2','成功后续轮及recency，初次第二条'),33:('§4.6','非运输输出分级，级层数最大/序位最早'),36:('§4.1、§4.8','步末开工、8d步后完成'),37:('§4.9','判定内尽量传输、40步冷却、相对送货显式输入'),42:('§2.2、§5','核心端口指派、仓库容量与身份'),64:('§3.2、§4.12','独立桥轴、来路及双向通道'),65:('§4.10','阻断时不收货，图不变，40步窗口'),73:('§2.2、§4.9','箱编号选格、容量和无线传输'),74:('§2.2、§5','仓库取货口指派及左/下边界'),77:('§2.2','中心12×12与正面积相交')}
def loc(n,line):
 if n in mapped:return mapped[n]
 if not line.strip():return ('§1','空行，保持逐行来源位置')
 if n>=79:return ('§2.3','配方原文或其机型/分节标题')
 return ('§2.2、§3.2','单位类型、端口、格或分类标题')
rs=['| 行 | 原文（据：该行命名条文） | 去向 | 用途或不涉及原因 |','|---:|---|---|---|']
for n,l in enumerate(rule,1):
 d,b=loc(n,l);rs.append(f'| {n} | {l.strip() or "（空行）"} | {d} | {b} |')
ts=['| 行 | 原文 | 去向 | 用途或不涉及原因 |','|---:|---|---|---|']
for n,l in enumerate(task,1):
 d='§1' if n<=5 else '§2.1、§5' if n in [6,7] else '§3.1、§5' if n==14 else '§2.2、§5' if n==15 else '§5'
 ts.append(f'| {n} | {l.strip() or "（空行）"} | {d} | '+('标题/空行保持定位' if not l.strip() or n in [1,4] else '任务条件；运行支持与未完成证明分开登记')+' |')
base=(ROOT/'规格/规则覆盖表.md').read_text();cons=base.split('## 3. 正式约束条目登记',1)[1].split('\n## 4.',1)[0]
put('规格/规则覆盖表.md','''# 规则覆盖表

日期：2026-09-30。状态：现行规则 115 行、任务 15 行，正式约束 77 条。原文列逐行对应正式源；去向指[运行语义](运行语义.md)的现行章节，不以行数覆盖替代运行认证。静态目录判据另见[数据覆盖表](../数据/规则覆盖表.md)。

## 1. 游戏规则逐行

'''+ '\n'.join(rs)+'\n\n## 2. 求解任务逐行\n\n'+'\n'.join(ts)+'\n\n## 3. 正式约束条目登记'+cons+'''

## 4. 约束登记引用说明

第3节77行按本轮要求原样保留，条款序号、源行和条款名逐项回源不变；其中沿用的“规则L63”是旧行号，现行桥接器为L64。§4.2仍承接轮询及密集结点，§4.3保留每tick速率与假设H的条件论证；H不等于现行每步一次判定，不能把两者混用。T1等已解决编号只作追溯，当前轴以配置v2为准。

## 5. 现行接口与核验范围

输入v4的布局/时间线/设定/参数/状态见[内核输入](内核输入.md)§2—6；步记录v5、周期证书v4及核验见[内核输出](内核输出.md)。完整窗口、成功轮询、箱相位和生产键均在步边界核对，不沿用旧微事件字段。

逐行原文、章节存在性、目录/参数SHA、77条约束与历史保护的本轮检查见[维护记录](../内核维护/2026-09-30-步进规则同步/记录.md)。证明义务见[受限模型声明](受限模型声明.md)；旧复核与旧规格自查只按历史时点使用。
''')
base=(ROOT/'数据/规则覆盖表.md').read_text();oldrows={int(r[0]):r for l in base.split('## 《明日方舟：终末地》游戏规则.txt',1)[1].split('## 求解任务.txt',1)[0].splitlines() if re.match(r'^\| \d+ \|',l) for r in [[x.strip() for x in l.split('|')[1:-1]]]}
rd=['| 源行 | 原文 | 目录／检查落点与边界 |','|---|---|---|']
notes={18:'units.inventory；开工时整批进缓存、产物整批出；静态不验运行后态',25:'timing.steps_per_tick；每1/8 tick一步；动态阶段由内核核验',26:'每主体每步一次；静态不检动态判定次数',27:'层数及接通序先后；动态由graph/step核验',28:'层数选支及环上锚点；静态不求动态调度',29:'元件含桥独立轴及最长带链；内核graph派生',30:'通道形成时刻；静态契约不回放建造',31:'非分流器上游成组收货；静态不检',32:'成功后轮询及非运输recency；静态不检',33:'按层数及接通序取货分级；静态不检',36:'recipes.duration及单位需电功能；配方tick装载乘8，动态制造由内核核验',37:'协议储存箱.transfer；每次尝试后冷却40步、相对送货为显式输入；当前契约拒绝带箱模型',65:'物品准入口.settings；阻断时不收货；动态限额与40步窗口由内核核验'}
for n,l in enumerate(rule,1):
 oi=n if n<=24 else n-1
 note=notes.get(n)
 if note is None:
  note=oldrows[oi][2].split('完整转录；',1)[1]
 rd.append(f'| {n} | {l.strip() or "（空行）"} | `sources[0].lines[{n-1}]` 完整转录；{note} |')
td=['| 源行 | 原文 | 目录／检查落点与边界 |','|---|---|---|']
for n,l in enumerate(task,1):td.append(f'| {n} | {l.strip() or "（空行）"} | `sources[1].lines[{n-1}]` 完整转录；'+('仓库取货口只能在左/下边界，实体布局另核' if n==15 else 'task条件及规格承接；静态报告不证明全部可达循环')+' |')
cons=base.split('## 正式约束',1)[1].split('\n## 结构化目录门禁',1)[0]
put('数据/规则覆盖表.md','''# 契约线规则覆盖表

日期：2026-09-30。状态：现行规则 115 行、任务 15 行与77条正式约束逐行/逐项登记。目录转录、静态必要条件和动态内核核验分别记录；本静态校验器通过不表示全称达标。

规范语义入口见[运行语义](../规格/运行语义.md)，逐行去向见[规格覆盖表](../规格/规则覆盖表.md)。

## 《明日方舟：终末地》游戏规则.txt

'''+ '\n'.join(rd)+'\n\n## 求解任务.txt\n\n'+'\n'.join(td)+'\n\n## 正式约束'+cons+'''

## 结构化目录门禁

formal_catalog.py核三份全文/SHA与结构化投影；formal_units.py回源重建单位预期。规则L42、L45—58、L60—77对应单位，L17—22、L36—37对应格/制造/传输，L25给timing.steps_per_tick，L23给residence_ticks，L82—115给18条配方。准入口L65明确阻断时不收货。77条正式约束原文、据行、32项常量、19项物料流量继续逐项回源。

候选B静态报告、完整安全集、来源重锁与全量历史保护见[维护记录](../内核维护/2026-09-30-步进规则同步/记录.md)。目录版本为static-catalog-v3、2026-09-30-r30-step，历史运行结论不随目录更新自动生效。
''')
for rel,fn in [('规格/规则覆盖表.md',m.rebuild_semantics_table),('数据/规则覆盖表.md',m.rebuild_contract_table)]:
 t=(S/rel).read_text();assert fn(t,cat)==t,rel
# 16项来源，仅刷新授权的四项，其余严格核当前字节。
sources=json.loads((ROOT/'数据/候选B/来源清单.json').read_text());changed=[]
allowed={REPO/'《明日方舟：终末地》游戏规则.txt',REPO/'求解任务.txt',REPO/'候选约束.txt',ROOT/'数据/正式静态目录.json'}
for row in sources:
 p=Path(row['path']);h=digest(p)
 if p in allowed:
  changed.append({'path':str(p),'before':row['sha256'],'after':h});row['sha256']=h
 else: assert row['sha256']==h,p
assert len(sources)==16
put('数据/候选B/来源清单.json',json.dumps(sources,ensure_ascii=False,indent=2));save('package3-candidate-lock.json',changed)
p='规格/check_revision.py';t=(ROOT/p).read_text();old='内核维护/2026-09-26-第88-89轮三审同步/只读文件指纹.json';assert t.count(old)==1
put(p,t.replace(old,'内核维护/2026-09-30-步进规则同步/只读文件指纹.json'))
# 只增加任务明确要求的只读旧自查白名单。
p='内核维护/2026-09-30-步进规则同步/guard.py';t=(ROOT/p).read_text();needle="['python3', '数据/工具/test_formal_catalog.py']]";assert t.count(needle)==1
put(p,t.replace(needle,"['python3', '数据/工具/test_formal_catalog.py'], ['python3', '规格/check_revision.py']]"))
p='内核维护/2026-09-30-步进规则同步/work.py';t=(ROOT/p).read_text();t=t.replace("if __name__ == '__main__':",'''def audit():
    import importlib.util
    spec = importlib.util.spec_from_file_location('package3_audit', OUT / 'package3-audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.audit()

if __name__ == '__main__':''');put(p,t)
# 代码现实：correspondence的现行字段名，不以设计泛称替代。
for p in ['规格/受限转移定义.md','规格/内核输出.md']:
 t=(S/p).read_text().replace('reverse_lift','reverse_reconstruction').replace('universal_coverage','all_reachable_cycles')
 put(p,t)
for rel in ['规格/修订记录.md','crates/kernel/修订记录.md']:
 t=(ROOT/rel).read_text()
 link='../内核维护/2026-09-30-步进规则同步/记录.md' if rel.startswith('规格/') else '../../内核维护/2026-09-30-步进规则同步/记录.md'
 if rel.startswith('规格/'):
  t=t.replace('史料：截至2026-09-20的六轮任务执行记录，含第一轮三次修订、第4、5轮落地及第6、7、8轮修订；文中旧版本与旧验证数保留其时点。当前定义以运行语义、选择点清单、义务对照及内核输出等对应规格为准。','史料：截至2026-09-30，按轮次追加；旧版本与旧验证数保留其时点。当前规格清单以运行语义§1为准，清单外材料不作为现行转移定义。')
 else:
  t=t.replace('\n\n','\n\n史料：截至2026-09-30，按轮次保留旧版本记录；现行入口见 README 与运行语义的文件清单。\n\n',1)
 t+='\n\n## r30：整数步规则同步（2026-09-30）\n\n'
 t+=f'目录为 `static-catalog-v3`、`2026-09-30-r30-step`，SHA-256 `{digest(ROOT/"数据/正式静态目录.json")}`。配置为内核配置-v2.json / kernel_profile_v2，66轴，SHA-256 `{digest(ROOT/"规格/内核配置-v2.json")}`。输入kernel-input-v4，运行记录kernel-output-v5，周期证书kernel-cycle-v4，生产键phase-cycle-key-v2，规范cycle-normalization-v3。\n\n'
 for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']:t+=f'- `{n}`：`{digest(REPO/n)}`。\n'
 t+='\n每1/8 tick一步；元件层数和接通先后、非分流器收货组、成功轮询与非运输recency、步末开工、40步箱冷却和窗口。删除旧扫描/双端授权/阻尼及任意判定次序输入，准入口只拒收。包一实现核心，包二实现记录/周期/独立账审及样例迁移，包三重锁候选B并同步现行规格和逐行覆盖。\n\n'
 t+='现行样例在数据/样例/步进及fixtures/step，旧样例/工具/记录/证书/配置v1保留原字节并由历史清单分类。周期仍是diagnostic_cycle，初态可达、反向完整周期、全称覆盖和独立终审不由本次规格同步代替。完整命令、结果、哈希保护与旧自查失败位置见[本轮记录]('+link+')。\n'
 put(rel,t)
print('staged coverage/locks/revisions/guard dispatch')
