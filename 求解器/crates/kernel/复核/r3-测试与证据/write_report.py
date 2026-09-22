"""汇集已经完成的复核证据；不运行、修改或替换被审实现。"""
from pathlib import Path
import json
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器');OUT=Path(__file__).resolve().parent;REPORT=OUT.parent/'复核-r3-测试与证据.md'
findings=[
{'id':'KR-r3-L2-01','where':str(ROOT/'crates/kernel/src/seed.rs')+':13–32；'+str(ROOT/'规格/内核输入.md')+' §6.4',
 'claim':'seed在识别after_closure之前无条件重写parameter_values，因而把缺失或冲突参数的检查点修补成可接受输入，未按最终规格保留并校验原参数。',
 'evidence':'内核输入§6.4要求after_closure保留游标、参数、账和事件，缺失或冲突即拒收；对内核的修改请求KQ-07重申该要求。seed.rs:19–30先补齐99轴并从顶层参数覆盖全部当前值，derive_context:58的after_closure早退发生在覆盖之后。独立seed_probe.py从桥接器t=5真实检查点构造参数表清空、表内transfer.phase冲突、仅修改顶层初始相位三例：原样run均退出2/invalid_input，seed均退出0且改写semantic_context；合法对照完整状态保持相等。证据：'+str(OUT/'seed-probe-results.json')+'；完整论证：'+str(REPORT)+' §2.1。',
 'severity':'重要'},
{'id':'KR-r3-L2-02','where':str(ROOT/'crates/kernel/src/interfaces.rs')+':119–158；'+str(ROOT/'crates/kernel/src/tests_round5.rs')+':146–172',
 'claim':'after_closure绕过transfer.phase.remaining的独立类型和值域校验，非法相位参数可进入completed记录及通过verify-cycle的生产周期结果。',
 'evidence':'规则“传输”规定5 tick冷却；内核输入§1.1/§5要求Time与支持域检查，现行配置transfer.phase明确本版整数剩余0…5。interfaces.rs:152–155仅在非after_closure时把该值与当前冷却比较，未单独解码或检查其范围。phase_probe.py同步修改顶层参数和检查点parameter_values以排除参数不一致因素，-1、6、1/2、字符串not-a-Time均run退出0/completed；以四格环的真实循环起点和not-a-Time初相位执行cycle，得到P=20的counterexample，verify-cycle仍退出0、cycle_replayed=true。合法初始相位与当前冷却不同的检查点应继续支持，但这不免除初相位本身的校验。证据：'+str(OUT/'phase-probe-results.json')+'、'+str(OUT/'phase-malformed-cycle-check.json')+'；完整论证：'+str(REPORT)+' §2.2。',
 'severity':'阻断'},
{'id':'KR-r3-L2-03','where':str(ROOT/'crates/kernel/src/output.rs')+':265–267；'+str(ROOT/'crates/kernel/tests/audit_round5.py')+':140–146',
 'claim':'覆盖报告把已定向桥上的成功搬运当作connection.bridge_first_contact实际执行证据，聚合审计继承该误标而漏列先接定向的运行覆盖缺口。',
 'evidence':'内核输出§1明确区分exercised实际执行和input_checked仅输入/结构检查，第五轮K6要求逐轴真实执行或逐条说明做不到。output.rs只要任一成功move涉及桥便将先接轴标exercised。桥接器双通路记录从t=0到29，输入两轴早已resolved，四个接通事件发生在-5、-4、-3、-2；所引第一证据J|0|0|0仅是south_box向bridge搬运，不含先接或定向后效。桥两通路各8件及两成品各8件无线入库确实成立，但只能证明运行通路。audit_round5按报告标签直接汇总，未独立核该轴事件。证据：'+str(OUT/'coverage-raw-samples.json')+'；完整论证：'+str(REPORT)+' §2.3。',
 'severity':'重要'}]
(OUT/'findings.json').write_text(json.dumps(findings,ensure_ascii=False,indent=2)+'\n')
text='''# 内核第3轮复核：测试与证据

日期：2026-09-20。状态：复核完成；发现3项（阻断1项、重要2项）。现有回归、原证据重验和要求的性能复测通过，但检查点输入校验及一项覆盖标注仍需修订。结论针对当前源码和锁定输入，不认定一般机制、全参数族或任务目标已经获证。

## 1. 依据、对象与来源状态

已读第五轮任务书及第一至第四轮任务书；按第五轮§0、§2–§3和第三轮§0、§2执行。正式游戏口径为仓库根《明日方舟：终末地》游戏规则.txt、求解任务.txt、求解约束.txt。候选约束不作为裁错依据；本报告不使用面积条件选取实现、不重新审议主席已定事项。

接口对照采用当前规格第8轮：受限转移定义§1–§6、内核输入§5–§6.4、内核输出§1–§5、对内核的修改请求KQ-01–08、参数轴答复、配置和普遍审查场景。规格只是已定任务的实现契约，不能自行增加游戏规则。两级周期、sufficient抽象、after_closure起点及局部可用集合分支表都按任务书限定范围审查。

开工对源码、测试、规格、样例和既有证据记录1710份文件的SHA-256及大小；只记录指纹，不复制目录或整仓。172项交付清单在开工时全部吻合。收尾时仅两份历史CLI汇总JSON与开工字节不同，见[来源复核](r3-测试与证据/来源复核.json)：它们在本席cargo结束后再次生成；本席独立输出的inode、时间、随机临时目录和哈希均不同。不能把收尾时的172项称全部相符，也没有依据将外部改写归责本次被审修订。其余170项交付指纹、1708份开工指纹以及12份保护文件保持相符；核心源码和本轮结论所据输入未漂移。

本席cargo原样执行全部测试；用bwrap只读挂载根目录，将测试硬编码的revision-r2和round5输出目录映射到本席复核目录，共享target保持工作区路径。未编辑测试、跳过测试或另建target。复核产物只有脚本、日志、JSON和Markdown；未改正式文件、候选约束、被审源码、样例或模拟器，未commit/push。具体命令见[复跑入口](r3-测试与证据/reproduce_cargo.py)。

## 2. 发现

### 2.1 KR-r3-L2-01：检查点参数在验证前被改写（重要）

`Input::canonicalize_seed`先读顶层参数，随后在seed.rs:13–30无条件重建StateSeed.semantic_context.parameter_values。缺失、重复或不完整的轴集合会被补齐；已有值和生命周期也被顶层参数覆盖。直到之后才调用parse和Engine::new_derived。derive_context在第58行发现after_closure后直接返回，已经不能恢复被覆盖的参数证据。

最终内核输入§6.4明确要求after_closure“保留原已执行游标、参数、台账、活动事件身份与时间锚点”，并要求“缺失或冲突即拒收”；对内核的修改请求KQ-07有同样要求。此义务来自检查点仍属于原参数点、规则的轮询历史及任务判定次序固定性，不能由当前库存倒造历史。before_boundary作为明确的新调度起点允许派生，不能把这个许可挪给历史检查点。

[独立探针](r3-测试与证据/seed_probe.py)直接取桥接器双通路既有记录t=5完整状态，保留真实库存、时间、游标、额度和日程；仅按下表改动参数。每例都分别交给公开run和seed，文件和进程退出码保存在[结果](r3-测试与证据/seed-probe-results.json)。

| 输入 | run | seed | seed后完整状态 |
|---|---|---|---|
| 原样合法检查点 | 0/completed | 0 | 与原检查点相等 |
| parameter_values=[] | 2/invalid_input | 0 | 被补为99轴，不相等 |
| 检查点transfer.phase与顶层冲突 | 2/invalid_input | 0 | 被覆盖，不相等 |
| 仅更改顶层transfer.phase初始值 | 2/invalid_input | 0 | 保留当前物理冷却却覆盖原参数身份，不相等 |

普通run的拒收原因为“当前值/生命周期与参数向量不符”，所以这不是探针输入因其它条件不合法而偶然失败。当前round5_seed_roundtrip只验证两个合法before_boundary样例，round5_seed_tie_changes_rebuild_ring验证另一个新起点，均不能覆盖上述检查点负例。合法after_closure续跑测试通过也不能推出冲突检查点会拒收。

修订应在任何参数同步之前分支检查phase：after_closure走原始完整一致性校验并保留原参数；新调度起点另行派生。需要保留正例，并补缺失、重复、值冲突和生命周期冲突的检查点负例。本项没有否定两份既有合法种子的往返结果。

### 2.2 KR-r3-L2-02：历史传输初相位逃逸类型和值域检查（阻断）

interfaces.rs:119–158验证explicit_residuals的外层、单位和slot，然后只在种子不是after_closure时比较`r.remaining`与当前progress.cooldowns[0].remaining。对after_closure，该值既未解码成Time，也没有单独检查本版整数0…5的域。

允许检查点当前冷却不同于原始transfer.phase是正确的：当前冷却已经经历运行，不能被强迫等于初相位。但初相位仍是证书15个输入轴之一，不能因此接受非法表示。正式规则“传输”规定5 tick冷却；内核输入§1.1规定Time/Quantity语法，§5要求已知不支持值明确停止，当前配置transfer.phase明确本版整数剩余0…5。半tick在一般规则域是否允许不由本报告裁定；这里仅要求本版按声明拒收不支持值，不能当作已支持整数参数点。

[独立探针](r3-测试与证据/phase_probe.py)使用合法after_closure检查点，同时改顶层transfer.phase与检查点同轴镜像，排除了§2.1的参数冲突。`remaining=-1`、`6`、`1/2`以及字面字符串`not-a-Time`全部run退出0并产出completed记录，合法0作对照。原始输入、记录及命令见[相位结果](r3-测试与证据/phase-probe-results.json)。

缺陷还会穿过周期验收：取生产循环环带t=0的真实after_closure起点，唯一异常为同步的`remaining="not-a-Time"`，cycle仍退出0，产生P=20的production_part/counterexample；parameter_point.input_axes.transfer.phase原样保存该字符串；verify-cycle退出0并报告cycle_replayed=true。[完整输入](r3-测试与证据/phase-malformed-cycle-input.json)、[完整结果](r3-测试与证据/phase-malformed-cycle-result.json)、[验收日志](r3-测试与证据/phase-malformed-cycle-check.json)可直接复跑。

这不是对周期数学计算的反例：物理状态中真正使用的冷却仍合法，20刻投影确实重复。问题是输入校验和发证范围错误，验收器把不属于已声明参数域的对象认证为受支持参数点。现有证书篡改测试修改period/key/rates/acceptance/full_base，未覆盖合法物理检查点附非法历史参数的情况；“整份重算相等”复用同一装载器，不能弥补此处语义入口缺失。

修订应在全部phase下独立解析并核transfer.phase.remaining的Time形状、整数域与范围；仅“等于当前冷却”的条件继续对after_closure豁免。以正确历史初相位但不同当前冷却的检查点作为必须继续成功的对照。

### 2.3 KR-r3-L2-03：先接定向的覆盖证据被普通搬运替代（重要）

output.rs:265–267把`connection.bridge_first_contact`与全部bridge.*放在同一条件：只要成功move的任一端属于桥，就置exercised，并引用这些move。audit_round5.py:140–146直接按记录中的标签汇总，未检查先接定向是否真的在所报运行区间发生。

内核输出§1明确区分exercised（实际执行）与input_checked（仅输入/结构检查）；第五轮K6要求新轴有实际执行记录，做不到须逐条解释。正式桥接器条文的先接定向是“端口类型由先接上的那一端所接的单位决定”，已经定向后的搬运不产生这个后效。

[记录原文抽查](r3-测试与证据/coverage-raw-samples.json)显示：桥接器双通路的两轴在输入layout中均resolved；四个接通历史为connect_0=-5、connect_1=-4、connect_3=-3、connect_2=-2；记录范围0…29。该轴的首个证据`J|0|0|0`只是south_box→bridge的成功move，全部32条引用均为桥入/出搬运，没有先接或定向事件。此时历史可以被输入校验，应该据实标input_checked；它不是一次运行中的先接后效证据。

本项不否定桥真的跑起来：两轴各进入8件、离开8件；最终两种成品各8件实际无线入库，库存/台账重验通过。它也不要求用两种读法做区分实验；问题是输入历史核验被当作已执行运行机制，导致K6“仅transfer.resume_event未触发”的覆盖结论过强。应拆开这条轴的证据提取，给历史/方向的结构证据并注明运行覆盖边界；若另有实际先接后效执行器，则由其真实事件取证。先接取向不能借普通物流事件冒领。

## 3. 独立重跑结果

| 检查 | 本席实测结果 | 证据与限制 |
|---|---|---|
| 完整cargo test --locked --offline | 113通过、0失败、0忽略 | [日志](r3-测试与证据/cargo-test.log)；kernel 76单元+3参考+3 CLI，topology 1单元+30集成 |
| Clippy全target、-D warnings | 通过 | [日志](r3-测试与证据/clippy-recheck.log)；[命令](r3-测试与证据/clippy-command.json) |
| release构建 | 通过，共享target | [日志](r3-测试与证据/release-build.log) |
| 两旧样例、完整/增量四份记录 | 独立Python重算严格相等 | [结果](r3-测试与证据/verify-outputs.json)；12份保护文件无变化 |
| 扩展26份运行记录 | schema、指纹、逐笔台账及Rust完整重跑通过 | [审计](r3-测试与证据/audit-results.json)；不把标签复算视为独立覆盖证明 |
| 10份循环结果 | 5份已核条件低产周期、5份inconclusive | 同上；5个周期为20、190、190、105、395；未决不能当成无周期 |
| 新cycle请求 | 环带P=20、制造闭环序3 P=105，均独立重载回放通过 | [命令与结果](r3-测试与证据/cycle-recheck.json)；[日志](r3-测试与证据/cycle-recheck.log) |
| 原生成器重跑 | 3份基准JSON生成并seed后与原fixture逐字段相等 | [结果](r3-测试与证据/generator-results.json) |
| 两档基准，各5进程×12刻 | 57单位/97PC中位0.840087 ms/tick；219制造台/630PC中位17.417978 ms/tick | [完整数据](r3-测试与证据/benchmark-recheck.json)；各自目标1/20均达到 |
| 额外81单位/100PC对照 | 中位2.686693 ms/tick | 与原报告一样不满足1ms；未用该对照代表约60单位目标档 |

性能沿用原脚本的引擎12次推进时间，解析/种子装载和序列化不包含在ms/tick内，进程wall_ns另列。B档219制造台关制造，只测有限预装物料物流和后续阻塞；砖档是运输网络。测量证实所报合成档位，不推为真实候选B的制造满载性能或可行布局。

## 4. 黄金、差分、种子与台账测试有效性

### 4.1 原比较没有为第五轮删减轨迹字段

reference.rs:13–33递归核对象键集合、数组长度/顺序及叶值；每个tick的time、全部events、完整StateSeed、summary、closure和新增warehouse_ledger一起比较。crusher_reference另把前4刻完整summary与固定黄金ticks相等比较。live_python_differential先让现场Python结果等于已落盘v3参考，再逐刻与Rust相等；没有只比较摘要、删事件、排序语义数组或放宽数值类型。

verify_outputs.py的same使用类型严格递归比较，另重建来源清单、元数据、覆盖行和验证范围。旧黄金JSON/Markdown及旧v2记录在12项保护集内；本席重新校验字节无差异。Python参考新增ledger_reference并显式排序无序inventory；没有让参考从Rust输出取答案。旧参考只覆盖两份有限样例，不支持无线与通用桥/阻尼，因此扩展记录的Rust回放必须另辅以事务审计，不能称它们都经过第二套完整执行语义。

第1/2轮CLI负例在本次cargo中原样运行：40项来源/范围变异及64项元数据变异等继续拒收。既有after_closure和切支测试按KQ-02/06改为成功，不是绕过尚未解决的规格。检查点异常仍有§2.1、§2.2缺口。

### 4.2 两补矿模式的独立差分与确定性

[独立脚本](r3-测试与证据/supply_differential.py)对粉碎机和轮询均分两个实际供矿场景分别跑40刻，explicit为足量、无补给事件的有限史，sufficient为原子补回。每种模式使用相同持久输入独立运行两次，输出逐字节相等。

两个模式逐tick比较完整对象，只显式归一规则允许不同的矿数量及数量类别、external_supply轴值、补给明细/总账，以及可读摘要中对应的矿量/补给数；events、其余warehouse、inventory、progress、logistics、其它semantic_context、实际入库和出库账均严格相等。没有泛化删除仓库或整段语义上下文。两场景均实际出矿40件，sufficient补回各40件，每刻逐物种守恒另行核验。[结果](r3-测试与证据/supply-differential-results.json)。

原Rust确定性测试还把单位、PC、BC排列反转后比较轨迹；库存排列规范化另有round5回归。缓存开/关对两旧样例、七个扩展场景以及三档基准严格比较tick对象；读源码确认Engine默认cache=false，另一侧确实显式启用，不是两次同模式的空差分。扩展段含门窗口恢复及箱冷却，基准只比两刻是其明确有限覆盖。

### 4.3 台账分途径与原子性

扩展审计从成功move的真实PC/指派和逐事件箱库存重建core_inbound、port_outbound、wireless_inbound、external_supply；无线成功核全箱每个物种，失败不写任何入库。每刻核

`W_after−W_before=core_inbound+wireless_inbound+external_supply−port_outbound−player_withdrawal−representative_adjustment`。

这比只读台账totals再自加减更强。额外[核心入库探针](r3-测试与证据/core_ledger_probe.py)使合法箱经带向核心真实入库2件，两个事件均标core:south:1，wireless为空；逐笔账、守恒与verify-record通过，[结果](r3-测试与证据/core-ledger-results.json)。桥接器无线两成品各8件是另一途径的正例。整箱容量拒收无无线明细，停用east_box的正冷却3在12个时刻均保留，见原文抽查。

## 5. 手工核一份完整周期

核对象为生产循环环带。固定配置只有a→b→c→d→a四格环、一只有电且开启传输的独立空箱，以及无相连PC的核心；条件种子的可达史未证。证书循环起点为t=0已闭包态：环内一件电池在b，entered_at=0；箱冷却5；仓库已有起动时无线交付的5胶囊；每侧至多一个通道，游标没有选择自由；无pending和门。

从这个起点重新推，不用证书终态倒填轨迹。正式滞留要求每次进运输格后至少1 tick，移动耗时0；因此每个下一整数时刻只可能成功移动一格，新格同刻不能再出。箱每5tick尝试一次，空箱尝试按本版every_attempt重置冷却5。转移§6.1只在每个生产代表边界把仓库成品数量归零，t=1移去5胶囊并保留历史身份，之后无成品再入库；这笔记representative_adjustment，不能算玩家拿取或周期产量。

| t | 末态位置 | 箱剩余冷却 | 本刻空箱尝试 |
|---|---|---|---|
| 1,2,3,4 | c,d,a,b | 4,3,2,1 | 无 |
| 5,6,7,8,9 | c,d,a,b,c | 5,4,3,2,1 | t=5 |
| 10,11,12,13,14 | d,a,b,c,d | 5,4,3,2,1 | t=10 |
| 15,16,17,18,19 | a,b,c,d,a | 5,4,3,2,1 | t=15 |
| 20 | b | 5 | t=20 |

每刻首轮只有当前旧格出边成功，事件索引固定为a出边0/b出边1/c出边2/d出边3；其余有源但年龄0者为residence失败、无源者为source_empty失败。单成员不分级侧失败仍回自身，分级侧在闭包末无physical可动成员。第二轮不再改变状态，完整调度边界重复；恰2轮闭包。成功move身份为`J|t|0|index`，空箱尝试为`J|t|0|4`，其它轮传输为cooldown观测。

独立[手推脚本](r3-测试与证据/manual_cycle.py)仅实现以上四格递推，逐t=1…20构造所有完整StateSeed语义值和全部事件，逐字段对照；只不比较basis/category说明文字，数组和所有物理/调度字段均保留，事件身份/operation/target/outcome/detail全比。台账和两轮闭包也逐刻核。没有调用Rust、既有Python转移器或cycle_key_reference生成期望。[20行结果](r3-测试与证据/manual-cycle-results.json)。

t=20位置、年龄0、冷却5、单环游标、活动图、端口预算图与t=0一致；仓库胶囊5→0是生产键允许删除的区别。环状态最小重复4，冷却最小重复5，故联合P=lcm(4,5)=20。参数、布局、其余仓库和pending不变，时间/进入时刻按§6.2归一；规范完整键的独立参考另由扩展审计逐字段核过。

周期区间是(0,20]，起动时t=0的5胶囊不在其中。周期两成品actual_inbound均0，平均0/20低于3/5及11/20；counterexample只是此条件种子及受限参数点的低产周期，不是一般任务无解，也不是完整基地周期。复核没有把精确代表化解释为玩家操作。

## 6. 新机制覆盖与边界

[抽查脚本](r3-测试与证据/coverage_probe.py)保存各新轴所引首个事件原文、出现次数和关键状态，不只看字符串标签。transfer的实际成功/空箱、容量拒收和暂停，桥两轴真实通量，研磨机两种配方完成，多级非运输取货侧的分支及连续带阻尼都能找到实际证据；研磨两种完成来自前一刻working配方，不把后态已换配方误作完成配方。warehouse.external_supply由40刻真实出矿补回覆盖，core/wireless分账如§4.3。需要纠正的先接覆盖见§2.3。

轮询均分原审计六局部序已重跑，核每组1件、相邻组和2≤3、各首格真实进出相差1tick、下一组前释放、三支成功前缀差≤1；它验证有限接收前缀，末刻未来释放没有被补造。密集制造闭环六序保持非全序字段相同，实际4件矿起动；序0/1的P190直接比1，序3 P105和序4 P395直接比0，竞争来源量与D总量均正，制造完成和M收后1tick释放满足所声明前件。序2/5在1000tick未决；另外3份旧密集探索也未决。4份条件周期的敏感性正证据不等于全局模板全序约减或一般动态约束证明。

transfer.resume_event未实际执行，有明确原因；固定开关/供电段不能生成停用后的重新启用，冷却自然到期不能替代恢复。该已登记未决不重复列为新发现。级二整批容量卡点、非精确拿取族、种子/参数/读法族和R线最终约减同样保留开放，不作为已有实现通过测试即可解决的事项。

## 7. 复现与交付核验

以下入口均将新增输出放在本报告旁的r3-测试与证据目录，编译仍用工作区共享target：

```bash
python -B 求解器/crates/kernel/复核/r3-测试与证据/reproduce_cargo.py test
python -B 求解器/crates/kernel/复核/r3-测试与证据/reproduce_cargo.py clippy
python -B 求解器/crates/kernel/复核/r3-测试与证据/recheck.py audit
python -B 求解器/crates/kernel/复核/r3-测试与证据/recheck.py cycle
python -B 求解器/crates/kernel/复核/r3-测试与证据/recheck.py benchmark
python -B 求解器/crates/kernel/复核/r3-测试与证据/generator_probe.py
python -B 求解器/crates/kernel/复核/r3-测试与证据/seed_probe.py
python -B 求解器/crates/kernel/复核/r3-测试与证据/phase_probe.py
python -B 求解器/crates/kernel/复核/r3-测试与证据/supply_differential.py
python -B 求解器/crates/kernel/复核/r3-测试与证据/core_ledger_probe.py
python -B 求解器/crates/kernel/复核/r3-测试与证据/manual_cycle.py
python -B 求解器/crates/kernel/复核/r3-测试与证据/coverage_probe.py
```

首次cargo原样完整通过后未反复运行；补充探针针对检查点与覆盖的未解问题。原审计/生成器的输出目录在模块入口显式重定向，未运行会直接改写被审文件的finalize/final_audit入口。发现的机器版本为[findings.json](r3-测试与证据/findings.json)。交付前已按未来独立读者检查数字、各自验证范围、路径/节号和当前/历史边界；机械链接/指纹/扩展名检查见[交付核验](r3-测试与证据/交付核验.json)。
'''
REPORT.write_text(text)
print(REPORT)
