"""包三接口与选择点文档暂存稿。"""
exec(compile((__import__('pathlib').Path(__file__).parent/'package3-docs.py').read_text(), 'package3-docs.py', 'exec'))
resolved={1:('整数步与阶段','规则 L25 每 1/8 tick 一步，结束制造→判定→开始制造；L23、L24 规定运输停满 8 步及即时前挪。'),2:('判定先后','规则 L26—L31 给每主体每步一次、层数/接通序及非分流器上游一起判定；不再输入任意判定排列。'),3:('收货与轮询','规则 L31—L33 给收货组、成功后续轮及非运输送货的成功先后记忆；普通循环侧初次起点仍按配置的本版选值。'),4:('元件与层数','规则 L28—L29 规定首尾连续带为元件、桥分轴及下游层数；不确定选支和环上层数由 step.order 输入。'),8:('准入口阻断','规则 L65 明定阻断时不收货，通道与层数不变；首件起 40 步窗口，累计与窗口分别计数。'),14:('桥接器独立轴','规则 L29、L64 规定每对边一个元件、两轴互不相干；L13、L24、L60 规定容量例外、来路及每格上限1。'),16:('非运输停留','规则 L24—L26 的持续移动与每主体判定规定何时可外送，不另给非运输格加停留；缓存整批可容即进输出。'),17:('缓存阶段边界','规则 L18、L25、L36 规定步初结束、整批能出即出、步末开工并一次收料；不得推迟已能进行的内部出缓存。')}
remaining={
5:('蓝图接通、平局与几何','''蓝图逐个建成，非传送带先于带；初次接通时刻取两端较晚建成时刻（规则 L9、L30）。时刻以步表示，同一步接通的全序用 connection.tie 显式给。接通次序及其关联仍需覆盖，不能只取一份生成器代表。

桥四边始终双向，接通不定型；相邻桥形成两个相反方向 PC，物品 last_unit 阻止直接退回（L24、L64）。本版相遇为共边全长重合且法向相反、存取互补、至少一端运输（L12、L16）；角点不成通道。建造中运行及重建后效见 T11。'''),
6:('箱传输、相位与部分剩余','''规则 L26、L37、L73：箱在自己的判定中按仓库余量尽量传输；before_send/after_send 每箱显式输入（transfer.timing）。每次尝试包括空箱、全拒收都起箱级40步冷却，初相位为0…40，供电且开启时逐步减1，本版停用冻结。

端口收发取最小编号可用/非空格；无线同种跨编号格的部分残留分配不由此自动确定。可唯一确定的全收、全拒收、单格部分收可执行，歧义跨格残留 unsupported。多个新物种竞争可观察无身份仓格也须完整后态。

箱只收成品、无取货外送、有电、开传输、仓库全收时，才可用约束·传输箱不满；初始堵塞到该域的过渡及全部初相位另证。'''),
7:('制造匹配、选格与身份','''规则 L18、L25、L36 已定步末一次整批收料并开工，上一批全进取货格才允许下一批。这里保留“符合配方”的论域、数量、物种及选格解释，不能把已定整体收料重新拆成部分归集或停用预收。

甲读法为普通存货格单种但不预绑定物种；乙读法允许混装，仍须证明与 L13、L17 的相容性。每格合计容量与每种分别计数、逐格求值与全部输入格并集求值是不同问题。本版 single_kind、per_slot_total、input_union、full_batch、at_least、allow；exact 与 forbid 等其他值的覆盖损失见配置表。at_least 允许2源矿匹配用1源矿的配方，exact 不允许；额外物种是否忽略与数量轴独立。

端口到格已定 distributed：外部存货只入存货格，外部取货只出取货格。全单位普通格同种单格，缓存例外；出缓存须整批且不能与其他普通格同种并占。箱按编号收发，不能任意选格。

manufacturing.recipe_selection 与 input_slot_selection 给完整显式顺序。普通格清空本版释放身份，仓格另按 T12 保留历史身份。配方至多一个的证明只在单种＋全物种＋并集的前件下成立；组合 J 的条件排除见运行语义 §2.3。错料永久滞留还需无匹配配方、无合法出口与无移除动作，不能只由端口映射推得。'''),
9:('准入口改设定与计数寿命','''规则 L22、L65 区分可变阈值 C 与已经收到的累计 n。同一准入口只改累计阈值仍保留 n；C>n 解除这一阻断条件，C≤n 仍阻断。首件窗口为40步，正常到期只清窗口计数与起点，不清累计。只解除一项不能跳过身份、容量、其余限额及滞留守卫。

调试可取消限额、清理、手工放料，但实际设置限额仍须先设身份、累计1…5000、窗口1…5；操作精度不得变成指定某一步。改身份、拆建、设限前收件和窗口承接须给具体后果；本版累计按 since_build，动态编辑触发 gate.counter_edit/cancel_limit 停止，不能以生成另一个静态种子宣称已回放该程序。'''),
10:('离线接续与实际时间','''任务 L14 允许任意两通道的接通先后在离线后改变，因而层数选支、同层先后和轮询可能改变。实际库存、运输年龄、制造剩余、箱冷却、准入口累计/窗口与来路都必须承接；哪些量由一次纯重排保持、哪些随实际离线时长推进，须分别证明。

合法重排域、共享建成时刻的并列关联及轮询记忆接续尚待覆盖；step.order 生命周期为 O，并不允许运行中直接替换它。当前遇离线即 unsupported。扩大排列域所得成功只在证明包含真实域后有充分性，坏路径须另核合法性与可达性。'''),
11:('调试权限、起动与后置状态','''任务 L12 允许调试期拆建、增建、旋转、清理、手工放料和改设定；L13 禁止依赖精确 tick 或精确计时，换成整数步不能放宽它。L8—9 限制零干预后的操作。程序需记录物品收支、几何/设定/进度后效及所有结束状态；本版动作回放未覆盖。

默认起法是先关机填满带和存货格，再使上游各完成一批、末级最后开。关闭时既不开工也不进缓存；完成批一旦放得下取货格就立即出去，不能任意指定“停在缓存”。因此旧起法中的缓存停留必须给实际阻塞条件；旧关闭预收阶段不能沿用。本版条件种子不是该起法的可达证明。

蓝图按 L9 逐个建成，L30 定接通，L10 定重建重新接通；任何新布局都须重新核占格、供电、通道、桥轴与建造史。仅旋转保持带形，拆建可重选带形。规则未给拆除后的自动返仓/销毁/保留结果，依赖这些后效的程序须另证。任务初始六种满仓与调试后仓存分开记账。'''),
12:('仓库环境、收支与周期对应','''仓库收得下成品。

该前提覆盖整个证书区间的所有候选与实际接收检查，单点未满不足以替代它。最终全矿指派下，生产投影仍须核成品格标签、空格次序及引用非干扰；本版 D.3 要求当前无身份空格序为空、成品格无取货指派、规范新格不冲突。见受限转移 §6。

真实仓库逐种 ΔW=I−O−P；成品最终 O=0，完整周期还须 ΔW=0。生产代表清零只记 representative_adjustment，不是玩家拿取。玩家操作精度、段内接收容量、外部补矿及拿取过程复原须另证，不能设计在精确周期末自动拿取来冒充完整周期。

生产周期到完整基地周期的反向复原、全部起点/参数/可达循环覆盖、接收中断与恢复状态集合分别登记，单次 diagnostic_cycle 不替代这些义务。'''),
15:('供电覆盖的格集合','''2×2 桩左下角 (a,b)，中心 c=(a+1,b+1)，供电区域为以中心为原点的12×12正方形。只须单位一部分落入，不能要求整个单位被覆盖。

positive_area 给格集合 { (i,j): c_x−6≤i<c_x+6, c_y−6≤j<c_y+6 }∩基地格；closed_touch 给 { (i,j): c_x−7≤i≤c_x+6, c_y−7≤j≤c_y+6 }∩基地格。后者外接格数可14×14，区域仍是12×12；该差别是接触判据，不是扩大供电距离。

两种解释的合法范围须合读来源；达标供电义务按最严 positive_area 核验，不以闭边多覆盖满足必要条件。当前内核采用 positive_area。不能任意偏移中心或无限扩供，目录未定标记不自动填默认。几何核对见受限模型 §3。''')}
parts=['# 选择点清单',header,'## 1. 读法与工程覆盖','正式来源及现行文件清单见[运行语义](运行语义.md) §1。已解决项保留编号便于追溯；输入残余不确定性、本版选值及停止域见[选择点参数轴](选择点参数轴.md)与[受限模型声明](受限模型声明.md)。允许域须联合满足三份正式文件；列出的待审方向不等于已获准，配置通过也不证明全称覆盖。']
for i in range(1,18):
 if i==13:continue
 if i in resolved:
  title,body=resolved[i];body='**由 2026-09-30 规则解决。** '+body
 else:title,body=remaining[i]
 parts.extend([f'## T{i}. {title}',body])
parts.extend(['## 2. 证明义务边界','缓存与普通库存的可达界、起动、参数族覆盖和完整周期复原不能用指定上界或单个种子代替证明。正式“轮询均分”的全部前件必须逐项满足，不能以平均组间隔代替真实恰隔1 tick；会议中的宽松候选不作为内核来源。现行单步内核不增加玩家精确操作能力。'])
put('规格/选择点清单.md','\n\n'.join(parts))
put('规格/受限转移定义.md',f'''# 受限转移定义

{header}

## 1. 输入、支持域和返回值

输入为[内核输入](内核输入.md)的 kernel-input-v4、配置 v2 与 static-catalog-v3。装载固定布局、设定、完整建造接通史、参数点及步边界状态，求出元件、层数、顺序及收货组。规则语义详见[运行语义](运行语义.md) §4。所有运行时刻均为整数步，1 tick=8步。

step(S) 成功给下一步边界及 StepReport；非法输入 invalid_input，未定层数 unresolved，未实现事件 unsupported，资源/整数域不足 inconclusive。错误后引擎封存，不能继续将部分修改当合法后继；记录只保留已完整完成的步。

## 2. 一步转移与事件

### 2.1 阶段顺序

令 s=environment.time，执行顺序固定如下：

1. 检查时刻s的外部停止，生产模式先作成品代表调整，显式补矿事件入库；启用箱冷却减1且下限0。
2. 启用且 working 的机器剩余减1，至0时原料换成产物、phase=completed；所有已完成批都尝试整批进取货格。
3. 每段带由头向尾检查，物品停满8步且前格空则挪一格，重新记录入格时刻。
4. 遍历装载后的主体次序；分流器自己送，其余元件触发收货组，非运输单位按级送；已被带动判定的元件跳过。
5. 按机器id依次开工：供电且开关开、idle、输入匹配，扣一次完整用量到缓存，working，剩余8d。
6. 窗口若 w+40≤s+1 则清窗口起点和计数；time=s+1，返回事件与本步台账。

第s步末开工在第s+8d步初完成；第s步传输后冷却40，在第s+40步可再传。停用时制造剩余和箱冷却冻结，准入口窗口按步时钟运行。缓存可出即出不等单位判定，开始新批只在步末。

### 2.2 主体、层数与顺序

分流、汇流、准入口各一个元件，桥每轴一个，首尾连接的最长带链一个；带环单列。身份为 C\\|单位、C\\|桥\\|轴、C\\|头带、C\\|ring\\|最小id（竖线是身份分隔符）。下游自身有送货通道才参加层数候选；无候选为1，有一个为其层数+1，多个用 layer_choices。选支函数图的环至少有一个显式正整数 cycle_layers 锚点；缺项 unresolved，非法项 invalid_input。

元件按（层数、最早外送通道接通序位）排序，无外送者在层1末按身份排；其后是全部非运输单位，有外送者的相对先后必须等于最早送货序位，无外送者可在非运输全序内显式安放。供电桩不判定。图固定且不因准入口拒收改变。

### 2.3 事件及守恒

只记有后效的 supply、complete、flush、judge、start；传输尝试即使0件也记。事件为 `{{event,phase,subject,moves,detail}}`，身份 E\\|s\\|i，i从0连续递增，moves为channel/item列表。收货组 detail.members 记本次联动成员，传输 detail.transfer 记 sent/retained。带内移动由完整状态可见，不另记外送事件。

仓库六流：external_supply、core_inbound、wireless_inbound、port_outbound、player_withdrawal、representative_adjustment。逐物种核 ΔW=前三项−中间两出项+代表调整；流条目的事件引用必须存在。交付只计核心及无线实际入库。

## 3. 判定、收货与轮询

### 3.1 一次判定

每元件和非运输单位每步最多外送一件。运输头件须停满8步；带链仅头格外送，带环没有外部出口。分流器按送货轮询依次尝试，首个成功即止。

某非分流器元件轮到时，以它为起点寻找共同收货方及其全部非分流器上游；新成员触发其余收货方，广度优先直到成员集不再增长。成员立即标记本步已判定；收货方按发现序、各自收货轮询依次试来自成员的通道，容量允许即收。每成员成功后本步不能再送；失败成员也不再判定。分流器既不被拉入组，也不参与组成员的同步争用。

桥每轴独立收货方；双出口桥轴的传递联动按 L31 本版读法，范围与审查限制见[受限模型声明](受限模型声明.md) §4。

### 3.2 轮询状态

循环侧存 last_success，成功后从下一通道开始；普通侧初次取第一条，分流送货侧、汇流收货侧初次从第二条开始，不足两条取唯一通道。非运输送货侧先按级别，再按 recency 最早成功优先，未成功的按接通序排最前。只有成功改变状态，失败不动；成功同时更新发送侧和接收侧，分流器单独送入也更新收货侧。

非运输输出分级：直接接汇流器的每条一级，其余合一级；级层数=max成员所通元件层数，级接通序=min成员序位；按两者升序。低级只在高级全部不能送时尝试。非运输 recency 成功通道移尾，保持语义顺序。

### 3.3 移动提交与即时前挪

先核源货、滞留/来路、目的格物种容量及准入口资格，再提交去源、入目标、两端轮询、准入口计数和台账。运输入格时刻=s，非运输格时刻=null。桥格记源单位 last_unit，送往该单位的回头通道被跳过。提交后对源/目标带段头向尾前挪；从机器取货格取走一件后立即再试整批出缓存。

每次带内挪动后新格时刻=s，故同一件不能在同一步连穿多格；前一格腾空可使后续不同物品在同一步依次跟上。无需端口预算，速率由8步滞留及运输单格容量推出。

## 4. 库存、制造、传输与准入口

### 4.1 库存选择与仓库

运输格容量1；普通格单种，同单位同种单格，缓存/箱/桥按例外处理。箱端口收货取最小编号可放格，取货取最小编号非空格，不能因这一格受阻转取后格。制造输入按显式格序；仓库端口读取各自指派格。

仓库已有物种回到对应格；空格历史身份 retain_history，同种不得另占一格。无身份空格按 warehouse_empty_slot_order；成功分配后稳定删项，失败不改序。未列仓格用规范 W_new_物种UTF8十六进制标签；多物种竞争可观察空格且没有确定顺序时停止，不能任意以字典序替代游戏规则。所有 put 在修改前核守卫，失败不部分写入。

sufficient 模式出矿原子回补，explicit_ore_history 在第s步首注入覆盖期内的登记事件，只允许原矿，容量仍核；最后一件矿不得取空。生产模式另受 §6 的 D.2 回矿限制。

### 4.2 制造

制造取 idle/working/completed 三阶段；working 缓存恰一批原料、剩余1…8d，completed 恰一批产物且 remaining=null，idle 空缓存。完成、整批出缓存、开工的触发点见 §2.1。输出放得下要求同种或空、总量≤50且其他普通格无同种物品。缓存放不下输出就保留整批，不拆批；上一批全进取货格即可再开工，不必等它离开单位。

关闭机器不收新用量到缓存、在制剩余冻结；输入配方的论域及匹配轴按 T7 与配置 v2。每台配方与选格全序显式给出，不能把未实现读法默认为同一后继。

### 4.3 箱体传输

有电且开传输、冷却到0时，在箱判定内按 transfer.timing 与端口外送安排先后。无线按各物种仓库可接受余量尽量收，可接受另一物种不因一物种拒收而放弃。跨格部分残留若不唯一则 unsupported；全收/全拒收及可唯一确定的部分接收保存每个编号格的后态。每次尝试即使空箱、0件也冷却40步。普通送货至多一件，无线整箱另计。

### 4.4 物品准入口

来件不符指定物种、累计已达上限、当前窗口已达上限时不收；通道不改变。成功收货累计+1、窗口+1，未开窗口从s起算；w…w+39可属于同一窗口。边界到期清窗口，累计保留。本版 since_build；动态改设定/取消限额/重建的后效触及停止域。

## 5. 步边界、终止与恢复

所有状态都是步边界。每步遍历有限主体，每收货组最多收入有限元件、有限通道；每个主体至多判一次，每次前挪扫描有限带段。因此该输入上的一步有限，不需要扫描轮数预算。纯带环按稳定格序实施可用位置前挪，成熟物品和腾空传播仍遵守入格时刻；满环不凭空挪动。

时刻s的离线、拿取、调试、拆建，以及种子之后的建成在第s步开始前停止。种子之前的历史由当前完整状态承接，不自动重新执行。周期或有限执行预算以完整步数计，超限只报 inconclusive；错误封存不能恢复为假成功。

seed 仅规范排序、补缺失轮询侧为空、清到期窗口后严格装载，不推导可达性。checkpoint 先核原记录/证书，再把末边界作为新种子，固定参数保持原样；初始 transfer.phase 仅在原锚点核等，恢复状态按自身冷却核合法。

## 6. 生产周期接口与正式循环对应

### 6.1 D.1—D.5 准入域

普通模式 finite_concrete 保留真实仓库。production_abstraction 的保守域逐条核：

1. 固定布局/设定/step.order、在线、zero_intervention、sufficient，无未来历史或待执行玩家策略；拿取记忆为空。
2. 两矿各有唯一正库存、出矿原子回补。回矿候选在仓库矿容量被读取之前停止：静态/周期核查扫描当前核心上游源候选及有资格箱，运行 accept/transfer 也执行 D.2 守卫。域要求覆盖整个周期，不能以没有成功回矿代替没有被抽象矿容量的读取。
3. 所有核心及仓库取货口只指派原矿；无端口指派成品现存/历史身份格；当前匿名空格序 O=[]；规范新格标签与物种相容。非成品的数量、身份及标签全部保留，不做植物库存抽象。
4. step.order 完整装载，全部层数与先后已算出，所有状态/接口合法；这不证明种子可达。
5. 每步每成品入量有结构界 B=核心几何存货通道数+300×有电且开传输箱数<80000。每PC每步至多1、每箱每步至多一次全箱300；这是代表容量的安全界，不是实际吞吐预测。

生产转移 G 在每步开始把成品数量代表取0，已有成品格保留历史身份，再执行一步。调整另记 representative_adjustment；D.5 保证本步内所有成品接收检查有余量。这不是游戏拿取动作或成品自动消失规则。真实环境前提是“仓库收得下成品”。

### 6.2 phase-cycle-key-v2

域名 phase_production_v2，规范版本 cycle-normalization-v3。键绑定完整固定上下文；只在步边界比较。Quantity 值约分且不比类别，Decision 保留status/value、不比basis；集合按身份规范化，语义顺序（recency、通道序及参数顺序）保留。

| 状态字段 | 键处理 |
|---|---|
| layout_snapshot、settings_anchor | 保留并绑定完整固定输入 |
| warehouse | 成品现存/历史身份格移出；两矿数量取 sufficient；其余字段完整保留，格按名排序 |
| inventory | 保留格、物种、数量、桥last_unit；运输 entered_at 换 max(0,entered_at+8−time)，成熟为0；非运输无时间并按物种合并 |
| progress | 单位、阶段、配方、剩余、箱冷却均保留相对量 |
| poll_state | last_success 及 recency 原语义顺序全部保留 |
| gate_counters | 有累计上限时 min(n,C)，无上限时null；窗口idle或active/received/remaining=w+40−time |
| environment | 去掉time，保留stage、online及空拿取记忆 |
| semantic_context | O 必须为空才准入，不能将非空序先删后比较 |

事件序号、日志、交付累计账不是物理键。实际完整状态保存原时刻、累计和证据；不得用规范键替代 checkpoint。读取点逐项见[周期键读取审计](../crates/kernel/周期键读取审计.md)。

### 6.3 后继、耗时及入库保持

条件论证要求固定相同图、设定和参数且 D 在整个区间成立。运输未来只读剩余滞留、制造和冷却只读剩余步；窗口只读剩余及次数，固定阈值只读是否达限；轮询记忆按成功次序且不读绝对时刻。D.2/D.3 排除被抽象库存及标签对未来读取的影响，成品接收前提给相同接收结果。

在这些前件及每个选择器后效一致下，可逐阶段对应供给、完成、前挪、判定、开工和收尾，得到相同下一键、一步耗时及实际入库。涉及双出口桥轴读法、真实输入域或更广仓库表示时须另核对应；实现自重放不能替代这项全域独立证明。

### 6.4 搜索、率与证据级别

搜索逐步查重，摘要仅作候选索引，命中必须恢复完整状态并比完整键，哈希碰撞不算周期。发现周期从其起点独立重跑 P 次 step，核完整终态、台账、D 前件和率；预算为 max_steps/completed_steps，资源耗尽保留 inconclusive。

P 以步计，period_ticks=P/8（有理数约分）；实际交付 I 的率为8I/P件/tick。对目标 n/d 用8Id与Pn精确比较。只有核心和无线实际入库计交付，矿回补、代表调整、玩家拿取均不计。

kernel-cycle-v4 目前给 diagnostic_cycle，保存计算出的 lt/eq/gt，不因低率直接声称真实反例。全部起点、合法参数、离线接续和全部可达循环另证；找到一个周期不证明全局最终收敛，也不证明周期集合有限。

### 6.5 真实仓库与完整周期

接收环境覆盖所有候选及实际成品入库检查；真实两成品满足 ΔW_i=I_i−O_i−P_i，全矿指派下 O_i=0。成品数量只影响接收，D.3 的身份及标签前件保证合法拿取不影响生产读取；固定相同参数与真实后效可逐事件对应生产轨迹及入库率。

完整真实循环投影到已证明保持的生产状态时仍以同一时长重复。反向须给正时长 Q：生产、段内拿取相对次序/数量、实际矿库存、其他库存、标签以及所有未来相关字段均复原，逐种拿取与入库配平且全过程满足容量；玩家操作还须符合任务操作精度。端点净变为0不足以证明后续段内过程重复。

接收中断后保留真实物品、轮询、制造和冷却；释放后进入安全集合及两成品异步/反复恢复均须另证。证书 correspondence 的 forward_projection、reverse_lift、universal_coverage 分别列依据和待证项，不能相互代替。
''')
put('规格/内核输入.md',f'''# 内核输入

{header}

## 1. 版本与基础类型

只接受 kernel-input-v4。静态目录 schema 为 static-catalog-v3，参数注册表 schema 为 kernel-profile-registry-v2、profile_id=kernel_profile_v2；目录与注册表均用 path/sha256 锁原字节，相对路径基于输入文件目录。目录还回源核三份正式全文；注册表必须与编译进内核的配置字节一致。

Quantity 为 `{{"value":"整数或有理数字符串","category":"候选/条文直引/算术推论等出处标签"}}`；运行所需整数量严格解析。Time 为 `{{"kind":"step","value":{{"value":"8","category":"候选"}}}}`，时刻及剩余量只取整数步。Decision 为 `{{"status":"specified","value":具体值,"basis":[依据]}}`；unknown/unresolved 不被悄悄填默认，not_applicable 须有可核的不适用范围。

## 2. 顶层与布局

| 字段 | 含义 |
|---|---|
| schema、purpose | kernel-input-v4 与输入用途声明 |
| catalog | static-catalog-v3 路径/SHA |
| timeline | 全局事件、先后关系、接通事件 |
| layout | 单位id、机型、origin、rotation、port_layout、占格及物理通道快照 |
| construction | blueprint_once、建造域、selected_order、moments、complete_event |
| settings | 需电开关、仓库格指派、准入口身份和限额 |
| parameters | JSON轴注册表、profile_id及F/O/U三组Decision |
| initial_state | 任务仓库锚点/满仓快照、完整执行种子、reachability条件依据 |
| debug_operations、environment | 动作与离线/拿取/矿供给历史；触及本版停止域即停 |
| contract_binding | 静态送料契约绑定；非空完整绑定尚未执行 |
| scenario | 自由场景说明，差分步数及现象断言可放此处 |

单位id只含字母数字下划线，核心唯一、基地70×70、占格合法；坐标/端口由目录几何派生。实体通道身份 PC\\|源端口\\|目标端口，内部缓存通道与实体通道分开。layout.physical_channels 可为 null 后由内核求出；显式给出时必须与几何全集一致，新步进样例全部给出完整表。

## 3. 时间线与建造

事件包含 id、kind、time；id唯一且不得用保留前缀 E\\|，这是运行事件域。kind 包含 build、debug_operation、offline、blueprint_complete、debug_end、unit_removed、unit_rebuilt、connection_open、connection_close、withdraw_product、runtime。表示这些类型不等于已经实现回放；runtime 只给显式矿供给。

relations 合并各类次序来源并检查无环及时间相容。construction.moments 的 placement 和首次建成布局相符，selected_order 不重不漏，非带先于带；connection_events 核时刻为两端较晚建成时刻。相同时刻的通道序用 connection.tie。种子已承接不晚于自身的建成与接通；未来建成在执行触及时停止。

## 4. 设定、仓格身份与环境

开关只用于正式需电功能；供电从几何导出。协议核心各取货端口、仓库取货口指派仓格，空格必须有已解 empty_identity；格物种来自状态，不是自由设定。准入口先设物种才可限额，累计1…5000、窗口1…5，窗口时长40步不是上限数值。

任务初始仓库六类满仓与实际种子仓库分开存；reachability 明示条件历史或证据引用，不声称装载即证明可达。环境含 debug_end_event、zero_intervention_after_debug、offline、product_withdrawal；后两者的实际事件以及调试动作须引用正确类型的全局事件，不能伪装runtime绕过停止。

## 5. 66轴与显式顺序接口

轴集合必须恰等配置v2，按生命周期F/O/U分别放 fixed、offline_mutable、fixedness_unproven；本版定值严格核等，输入接口值逐项核结构，停止轴只能用stop策略。当前值及损失见[受限模型声明](受限模型声明.md) §2。缺具体参数不能靠程序默认运行。

### 5.1 接通序与层数输入

connection.order=timeline_connection_history，connection.tie.value 为 kind=explicit_order 和所有通道的 channels 全排列。装载按（建成接通步、tie序位）求唯一序位。

step.order 在 offline_mutable 中，其 Decision.value 为：

```json
{{"schema":"step-order-v1","layer_choices":[{{"component":"C|x1","downstream":"C|s3"}}],"cycle_layers":[],"nontransport_order":["source","crusher","core"]}}
```

每个有至少两个合格下游的元件恰一条选支，桥轴同样适用；有零/一个候选不可多给。选定边构成环时每环至少一个正整数锚点（layer用Quantity），只能给环上元件；锚点停止递归，其余从下游加1。未给必要选支/环锚点 unresolved，错误位置或候选 invalid_input。

nontransport_order 恰含全部非运输单位且不含供电桩；有外送通道者的相对次序须按最早送货通道序。无外送者位置显式给；开传输箱的该位置可能可观察。无外送元件统一在层1末按身份排。

### 5.2 箱传输

transfer.timing 在 fixedness_unproven 中，value 为 `{{"schema":"transfer-timing-v1","values":[{{"unit":"box_1","timing":"before_send"}}]}}`，每箱恰一条、值为 before_send/after_send。

transfer.phase 为 kind=explicit_residuals、values逐箱记录unit、slot=null、remaining=Time(0…40)。它是初相位：仅当种子还在 initial_state.anchor 的原时刻才要求与种子冷却相等；checkpoint 保持原初相位，后继种子单独核自身冷却，不改固定参数。

### 5.3 其余输入接口

制造配方和输入选格用 kind=explicit_order 的 recipes/slots 全排列；传送带形状按每个建造生命段显式给，旋转不改变相对形状。初始锚点、库存、开关、建造时刻、调试后条件及引用必须与顶层实际对象对应。

warehouse.external_supply 为 ore-supply-v2。sufficient 出矿立即原子回补；explicit_ore_history 明列 event/time/item/quantity，并在 timeline 登记同id同time的runtime事件，仅两矿且容量合规。through 以步计，执行不能超覆盖；取走最后一件矿被拒。该接口不能表达任意非矿外部补给。

## 6. 完整状态v2与种子

状态v2是当前 State 结构的版本称呼，没有额外schema字段。字段为 layout_snapshot、settings_anchor、warehouse、inventory、progress、logistics、environment、semantic_context，逐项见[运行语义](运行语义.md) §2.1；输入位置为 initial_state.nonwarehouse.value。

运输格entered_at必须非空且≤time，玩家边界放入可等于time、time+8才可外送；非运输entered_at必须null，同物种只一行。last_unit只许桥轴格并给合法来路。库存按格容量与全单位同种单格守卫；制造阶段只idle/working/completed且缓存/剩余一致，箱只有cooldown。

poll-state-v1.cursors 恰含多通道循环侧：C\\|身份:input/output以及非运输单位:input；每行last_success为本侧通道或null。recency恰含多出口非运输单位，order是不重复的已成功通道子序列，未列者表示从未成功。单通道侧不存游标，多通道侧不能缺漏；seed工具可补合法缺失的空记忆后严格装载。

准入口每个一个计数行；窗口未开为null/0，已开满足w≤time<w+40且计数合法。累计可大于后来调低的上限，阻断不使这个种子非法；是否能通过玩家程序到达另证。semantic_context仅含当前无身份仓格顺序。状态处于在线zero_intervention；动态外部动作仍受停止边界约束。

## 7. 生成、核验与迁移

完整实例见[base fixture](../crates/kernel/tests/fixtures/step/base.json)与[步进样例](../数据/样例/步进/README.md)。step_inputs.py/step_samples.py 给显式代表输入；默认最小层候选、环最小身份锚点1、before_send均只是代表，不证明全称。

seed做状态规范化和完整装载，check做完整装载而不运行；checkpoint先核记录或证书再恢复末步边界。契约非空绑定/完整可达性证据的执行仍属未覆盖域，不能由格式接受提升认证。

历史输入v2/v3被拒；迁移工具只读旧文件另写v4，tick时刻乘8，不继承旧轮询记忆。旧扫描后锚点t映射8(t+1)，旧步前锚点t映射8t；旧intake阶段拒绝迁移。历史样例、工具、记录与证书保持原字节，索引见[历史说明](../数据/样例/历史说明.md)。
''')
put('规格/内核输出.md',f'''# 内核输出

{header}

## 1. 版本、来源与证据范围

运行记录 kernel-output-v5；周期证书 kernel-cycle-v4；结构定义见[内核输出.schema.json](内核输出.schema.json)。输入为v4、目录v3、配置v2；每份产物绑定原输入、配置、正式来源、目录、生成与核验源码的原字节SHA。相对引用按产物所在目录解析，producer与format也须核对。结构通过不等于重跑通过，更不等于游戏全称认证。

运行/周期产物均保留 evidence_scope、执行域和未覆盖项。支持域是固定布局、设定、step-order-v1与整数步的有限执行；actual_inbound 是实际核心加无线入库，不计代表调整、补矿或玩家拿取。时间字段均用步，目标率用件/tick。

## 2. 运行记录与事件

顶层为 schema、evidence_scope、execution_mode、port_meeting、run_id、profile_id、producer、status、fingerprints、parameter_assignment、input_history、uncovered_axes、trace、validation_scope、open_items。run_id=kernel:输入名:起始步:请求步数；执行模式 finite_concrete 或 production_abstraction。

trace 含 start_state、steps、end_step、format；每行一步，含 step、events、state（或delta）、warehouse_ledger。step=s的行保存执行后的time=s+1状态；end_step是最后成功边界，from/through同为边界步号。manufacturing_cycles_completed只数complete事件。

事件字段 event/phase/subject/moves/detail；event=E\\|步\\|序号，序号从0连续，phase为supply/complete/flush/judge/start。只记实际后效及箱传输尝试，0件传输仍记；带内前挪由状态核对。detail.members保存收货组，detail.transfer保存sent/retained。台账六流及守恒见[受限转移定义](受限转移定义.md) §2.3；所有事件引用须存在。

full_state_each_step 每步保存完整状态；checkpoint_delta 使用 object_replace_v1，checkpoint_interval以步行计，索引i满足i%K=0保存全状态，其余保存相对上一行的对象替换增量。解码后必须与全状态逐字段相同；不能只核最终数量。

## 3. 内容核验与轴覆盖

verify-record 核来源、输入及参数、完整起态、连续步、事件身份、逐物种台账，再从原输入重跑比较全状态/事件/流。独立 audit_step.py 从移动、补给、传输及代表调整重算仓库六流，核箱格后态/冷却与身份；测试通过stdin传内存记录，不落仓库证据。

66轴逐项记录disposition、coverage_status、evidence、损失及其他值。实际后效为exercised，只装载为input_checked，没用为not_exercised，停止域未触及为stop_not_triggered，完整周期提升为proof_pending。有移动可触发time/component/step，轮询需多通道侧，箱需传输尝试，制造需start/complete/flush，桥/门需相应移动，仓库按流。一次exercised不代表该轴全部值覆盖。

validation_scope 固定 universal_parameters=false、all_reachable_cycles=false、target_certified=false。只有现行版本交新入口核验；旧记录只列historical_records，见[测试历史说明](../crates/kernel/tests/历史说明.md)。

## 4. 停止与恢复

invalid_input、unresolved、unsupported、inconclusive保持不同原因；装载失败可trace=null且无完整状态，不能伪造合法轨迹。运行中失败仅记录成功步前缀，失败引擎封存；completed才是请求区间完成。

seed输出规范化v4输入；checkpoint先核v5记录或v4证书再取末边界，缺原输入/完整状态的诊断外壳拒绝恢复。固定参数保留，不把恢复时的剩余冷却写回初相位。检查点合法也不证明可达。

## 5. kernel-cycle-v4 周期证书

### 5.1 字段与搜索

保留 result_id/status/level、seed、parameter_point、reading、support_domain、domain_report、fingerprints、record_mode、replay_input_ref、run_record_ref、last_state、cycle、stop、budget、open_items、evidence_scope、environment_assumption。budget 为 max_steps/completed_steps；record_mode 为none或referenced，有引用时原输入/记录都核path、sha256、producer、format。

搜索按步取phase-cycle-key-v2，摘要命中后比完整键，再从周期起点独立重跑。cycle保留起末步与完整起末态、键/摘要、normalization、逐步ledger、totals、rates、acceptance、reception_scope、correspondence。normalization.schema=cycle-normalization-v3，绑定受限转移定义的原字节；D.1—D.5与每项保持前件见转移§6。

### 5.2 周期与率

period=P为步数，period_ticks=P/8约分；入库I的average=8I/P件/tick，与3/5和11/20用交叉乘法比lt/eq/gt。无周期或资源耗尽为inconclusive，不等于无解。当前找到的生产循环为diagnostic_cycle，不能因平均率通过提升正式cycle_found或全称认证。

correspondence分别登记forward_projection、reverse_lift、universal_coverage；商状态保持、真实仓库/拿取/矿过程复原、全部种子参数和离线史覆盖的证据不能混用。真实接收前提为仓库收得下成品，代表调整与真实拿取分开。

### 5.3 独立核验

verify-cycle 从原输入重跑到发现前缀，核证书的周期起末、连续事件、D动态前件、账和率；再从完整周期起点重跑P步，比较完整末态。record_mode=none仍执行上述重跑；referenced还核相应v5记录。篡改周期账、引用、producer、状态或预算不能仅因schema合法而通过。

## 6. 命令行接口

参数为实际步数：run --steps N，cycle --max-steps N；run可用--no-output，默认记录格式full_state_each_step，可选--format checkpoint_delta及--checkpoint-interval K。cycle可用--no-record及--search-checkpoint-interval K；引用记录模式由--out同时派生记录文件。

check完整装载，check --cycle-domain给D域静态报告；request报告指定轴处置；seed规范化，checkpoint恢复；verify-record、verify-cycle、verify-batch核产物。批量入口verify_all.py只验当前版本并按版本列历史。run写记录须--out；停止一般退出2，cycle的诊断周期或预算未决可正常交付但须读status，不能只看进程退出码。

历史--ticks、--max-ticks、--max-sweeps、--no-cache已删除。维护轮次的许可命令以[任务书](../内核维护/2026-09-30-步进规则同步/任务书.md)为准，接口存在不构成该轮写证据的授权。
''')
put('crates/kernel/README.md','''# 整数步运行内核

日期：2026-09-30。版本：r30；1步=1/8 tick。内核执行固定输入的有限轨迹、诊断生产周期和独立重放；不证明种子可达、全称达标或最优布局。

现行入口为[运行语义](../../规格/运行语义.md)、[受限转移定义](../../规格/受限转移定义.md)、[输入](../../规格/内核输入.md)与[输出](../../规格/内核输出.md)。输入kernel-input-v4、目录static-catalog-v3、配置kernel_profile_v2（66轴）、运行记录kernel-output-v5、周期证书kernel-cycle-v4、生产键phase-cycle-key-v2。

每步结束到时制造，按元件层数和接通序逐个判定，再开始制造。非分流器上游随收货组一起判定；带内成熟件即时前挪，轮询只在成功时更新。准入口拒收不改变通道。层数不确定选支/环上锚点及箱无线相对送货次序显式输入。

从求解器目录构建使用共享target、默认profile：

```bash
CARGO_TARGET_DIR="$PWD/target" cargo build --workspace -j 4
```

命令接口：check、run --steps N、cycle --max-steps N、request、seed、checkpoint、verify-record、verify-cycle、verify-batch。run可关闭记录，cycle可无引用记录但仍独立重放；完整开关见输出§6。旧输入不兼容，迁移另写新文件，见[步进样例](../../数据/样例/步进/README.md)与[历史清单](tests/历史说明.md)。

测试包括kernel库、reference的九例4000步sim2差分及Python独立账审；topology库/validation及两包doc测试另属安全集。2026-09-30维护只允许[任务书](../../内核维护/2026-09-30-步进规则同步/任务书.md)列出的安全命令，每条必须经过[run.sh](../../内核维护/2026-09-30-步进规则同步/run.sh)前后历史哈希守卫；不执行workspace测试或批量写记录入口。验证结果、限制和日志见[维护记录](../../内核维护/2026-09-30-步进规则同步/记录.md)。

周期边界与读取点见[周期键读取审计](周期键读取审计.md)。unsupported/unresolved/inconclusive均不表示游戏无解；diagnostic_cycle不等于完整基地周期或全称认证。
''')
print('staged choices/transition/input/output/readme')
