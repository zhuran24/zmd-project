#!/usr/bin/env python3
"""整理本轮已完成检查的证据索引、逐项结论及发现。"""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
K=ROOT/'crates/kernel'
def read(name):return json.loads((OUT/name).read_text())
findings=[
 dict(id='KR-r4-L2-1',where=f'{K}/src/output.rs:273-275；{K}/src/polling.rs:124-127；{K}/tests/audit_round5.py:164-174',
      claim='当前path_runs未执行几何邻接轴，却把连续带路径标为damping.belt_adjacency已执行，导致K6覆盖审计漏报一项缺口。',
      evidence='最终选择点参数轴.md:40限定该轴仅用于geometric_components，受限模型声明.md:40明确path_runs不调用此值；polling.rs只在belt&&previous_belt时写belt_adjacency标记，output.rs据标记报exercised。新跑阻尼连续带核验3刻的J|0|0|0及公开verify-record复现该误报；证据为复核/r4-测试与证据/dormant-axis-evidence.json。',
      severity='重要'),
 dict(id='KR-r4-L2-2',where=f'{K}/src/cycle.rs:675-692；{ROOT}/规格/内核输出.schema.json:2527-2633；{K}/tests/audit_revision_r3.py:23-39',
      claim='KQ-09仍未收口：cycle装载资源不足返回的真实inconclusive空上下文不符合现行交付schema。',
      evidence='内核输出.md §5.1允许装载前失败run_record为空，受限转移定义§1要求资源不足为inconclusive；CycleResult/allOf/4却强制seed、parameter_point、replay_input及run_record非空。独立重跑age-overflow-cycle得到exit=2、resource.integer、completed_ticks=0及空上下文，AJV2020再次拒收；58份结果中57通过、此1份失败，见复核/r4-测试与证据/independent-schema.json。该项为既有未决复现，需S线修schema，不能改错资源分类或伪造状态。',
      severity='重要')]
notes='完整报告：'+str(K/'复核/复核-r4-测试与证据.md')+'。Cargo原生120项通过、1个写死旧证据目录的Rust集成测试改以同等4次CLI调用及全部断言在复核目录通过；Clippy通过。3次release基准两档均达标，26份运行/10份循环审计通过，新搜索并回放20/190 tick周期，手推20 tick全状态及200事件相符；补矿30 tick差分、D.2四组容量对照和31条覆盖轴原始事件抽查完成。保留2项重要发现；现有验收通过不代表错误覆盖标签已正确。'
(OUT/'结果.json').write_text(json.dumps(dict(findings=findings,notes=notes),ensure_ascii=False,indent=2)+'\n')
bench=read('benchmark.json')['cases']
benchmark_table='\n'.join('| '+r['name']+' | '+str(r['units'])+'/'+str(r['pc'])+' | '+', '.join(f"{x['ms_per_tick']:.6f}" for x in r['runs'])+' | '+f"{r['median_ms']:.6f}"+' | '+('三次均达标' if r['all_within_target'] else '附加对照，无本轮达标主张')+' |'for r in bench)
period=read('manual-period-check.json')
period_table='\n'.join(f"| {r['tick']} | {r['move'].split('|')[1].split(':')[0]}→{r['move'].split('|')[2].split(':')[0]} | {r['occupied'].split(':')[0]} | {r['cooldown']} | {'尝试成功，空箱' if r['empty_transfer'] else '冷却未到'} | {r['representative_adjustment']} |"for r in period['table'])
reasons={
 'transfer.judgment':'north/east箱各按全箱尝试；无逐格判定冒名',
 'transfer.cooldown_scope':'单箱单冷却；实际尝试后5→4→3→2→1→5',
 'transfer.phase':'初始0实际触发；正冷却场景另核，非法历史相位有负例',
 'transfer.pause':'east_box停用且正冷却保持；没有恢复事件',
 'transfer.failure_cooldown':'south_box容量拒收后冷却=5，空箱尝试也起冷却',
 'transfer.partial_acceptance':'t=0整箱容量拒收，电池与砂叶均不入库',
 'transfer.resume_event':'未执行；固定开关/供电域的已披露缺口',
 'bridge.inventory_scope':'两轴各8件进出，物种与轴对应无互换',
 'bridge.scheduling_scope':'同一桥存取侧共享环和授权，实际跨两轴服务',
 'bridge.capacity':'双轴独立容量1；同种双轴拒收另有原生测试',
 'connection.bridge_first_contact':'仅历史输入检查；未执行建造或定向',
 'warehouse.delivery_count':'两成品实际无线入库各8；空箱不计产量',
 'warehouse.empty_slot_identity':'首次入库新建成品格、绑定身份；匿名/历史格另有单元正反例',
 'warehouse.external_supply':'成功出矿事务同事件补回；30刻独立差分各30件',
 'damping.branch':'源取货侧有多个级；实际查可用出支集，门切支/恢复后重查',
 'damping.belt_component_rule':'多级排序实际沿两条相继带计单个path_runs元件',
 'damping.belt_adjacency':'不接受exercised：路径带串不是几何邻接判据，见发现1',
 'manufacturing.port_slot_relation':'矿粉/砂叶粉末从存货口进入input格',
 'manufacturing.input_mixing':'同一研磨机先后两配方，单格不并存异种',
 'manufacturing.input_capacity_scope':'实际入料核普通存货格容量；满容量边界另有单元测试',
 'manufacturing.input_slot_selection':'已有物种回现格，新物种选择明确输入格',
 'manufacturing.empty_slot_identity':'第一批归集清空输入格后第二物种可进入',
 'manufacturing.recipe_match_scope':'两个输入格合并匹配2矿粉+1砂叶粉末',
 'manufacturing.recipe_completeness':'t=2实际凑足整批后归集',
 'manufacturing.recipe_quantity_match':'按每配方所需数量归集，剩余库存不凭空抹除',
 'manufacturing.recipe_extra_items':'匹配器检查该输入并集；不声称已区分全部额外物种读法',
 'manufacturing.recipe_selection':'按显式配方序选择；本例单次只有一个可匹配配方',
 'manufacturing.recipe_lock_time':'J|2|0|6锁配方并开始工作',
 'manufacturing.input_collection':'同一事件两条BC入缓存，2+1原料完整入批',
 'manufacturing.buffer_power_gate':'BC搬运与制造子动作实际执行；停电分支另有单元回归',
 'manufacturing.output_blocked':'C|3|grinder完成后J|3|0|6执行整批出缓存守卫；阻塞保批负例另有原生测试'}
excerpts=read('coverage-event-excerpts.json')
coverage_table=[]
for axis,row in excerpts.items():
 if row.get('record'):
  name=Path(row['record']).name.replace('-运行记录-v3-kernel.json','')
  event=row['first_event']['event']['event']
  source=f"{name}，`{event}`"
 else:source='未执行，已登记原因'
 source=source.replace('|', r'\|')
 reason=reasons[axis].replace('|', r'\|')
 coverage_table.append(f"| `{axis}` | {source} | {reason} |")
coverage_table='\n'.join(coverage_table)
report=f'''# 内核第4轮复核：测试与证据

日期：2026-09-20。状态：复核完成；2项重要发现，未发现本轮证据足以成立的新增“实现会做错”阻断项。发现1是新的覆盖误报，发现2是已登记KQ-09的独立复现。有限执行测试通过不能把这两项标成已关闭。

## 1. 判据、对象与证据定位

本报告按第五轮任务书及前四轮任务书执行；保留任务书3 §0和任务书5 §0的辖域与证据纪律。正式判断源是仓库根三份正式文件，当前规格负责具体受限接口；候选约束、面积必要条件、第三方模拟器均未作为判据。主席已定的分级、after_closure从t+1续跑、局部分支表及相遇读法范围没有重议。

正式依据主要为规则L13/L17/L18（容量、批次）、L20/L23–32（暂停、滞留、判定、轮询与阻尼）、L35/L36（制造和传输）、L41/L63/L64/L72（仓库、桥、门和箱），任务L2/L6–9/L12/L14，以及正式约束“端口速率、入库途径、轮询均分、密集结点”。目标仍量化所有相应可达循环及允许取值；本报告没有据有限样本改变全题结论。

被审74份指定文件的当前字节、行数与JSON状态索引见[被审文件清单](r4-测试与证据/被审文件清单.json)。另查了`tests_round5.rs`、`reference.rs`、`polling.rs`、`ledger.rs`、`warehouse.rs`、独立密集审计和最终规格键参考。源码/规格/旧证据未改；本席只在本复核目录写脚本、日志、JSON、Markdown，编译使用共享`求解器/target`。未建工作树、未复制整仓或依赖缓存、未操作模拟器、未commit/push。

证据入口为[recheck.py](r4-测试与证据/recheck.py)、[probes.py](r4-测试与证据/probes.py)、[manual_period.py](r4-测试与证据/manual_period.py)。它们分别执行原验收与公开CLI、独立边界探针、手工递推。报告的机器摘要是[结果.json](r4-测试与证据/结果.json)。

## 2. 发现及完整论证

### KR-r4-L2-1：未调用的几何邻接轴被报为已执行

**严重性：重要。** 位置：`src/polling.rs:124–127`、`src/output.rs:273–275`、`tests/audit_round5.py:164–174`，并影响`evidence/round5/audit-results.json`的覆盖集合与“仅两项未覆盖”结论。

最终`规格/选择点参数轴.md:40`写明该轴“只在 geometric_components 解释中使用”；`规格/受限模型声明.md:40`进一步写“本版path_runs不调用此值，显式保存以便迁移”。这是两条正交轴：沿通道路径的极大带串由`damping.belt_component_rule=path_runs`确定；哪些格在几何上邻接才属于`damping.belt_adjacency`。正式规则L26/L27要求“连续传送带”与阻尼，但没有让这两个登记的受限读法合并为一项；按任务书纪律也不能借未定自由创造等价关系。

实际`Engine::damping`只在当前/上一运输单位均为带时写`belt_adjacency:{{origin}}`，随后依`!belt || !previous_belt`计元件。这个分支没有读取`DampingBeltAdjacency`，也没有计算几何相邻连通块。源码中的该枚举仅在配置解析/名字映射出现。共边成PC来自`connection.port_meeting`，不等于运行过几何邻接轴。

独立公开CLI复现：`probes.py coverage`对“阻尼连续带核验”新跑3刻，[新记录](r4-测试与证据/dormant-axis-record.json)中该轴为`exercised`，首证据`J|0|0|0`为`PC|source:north:0|merger:south:0`的一次`dual_permission`失败，其basis含对另一条源出边路径记的`belt_adjacency:`标记。[公开verify-record结果](r4-测试与证据/dormant-axis-verified.json)仍为`input_checked`。这不是伪造或篡改记录，而是当前生成器与同实现重跑一致接受错误覆盖语义。原18刻记录也相同；原始轴行、事件和参数见[直接证据](r4-测试与证据/dormant-axis-evidence.json)。

聚合审计只把各记录已报的`exercised`并入集合，再检查缺失名单是否包含在两项已知原因内；它没有独立证明这条轴被调用。已有“全部审计通过”因此不能否证本发现。最小处置是把该轴保留为未执行/仅输入检查并登记当前模式不调用的理由，同时修正聚合缺口与文档；若以后要获得运行证据，须有获准且真正执行几何连通块读法的路径。本报告不要求为了满足覆盖数字而改变受限语义。其余`damping.branch`及`belt_component_rule`的实际调用不受本发现否定。

### KR-r4-L2-2：资源未决空外壳仍违反现行schema（既有KQ-09）

**严重性：重要。** 位置：`src/cycle.rs:675–692`；`规格/内核输出.schema.json:2527–2633`；`tests/audit_revision_r3.py:23–39`。

受限转移§1区分`inconclusive(resource)`与非法输入、未支持、低产反例；输出§5.1允许装载前失败时`run_record=null`。当前内核在年龄计算超出i64运行域时正确保留资源分类和真实空上下文。将其改为游戏反例、非法输入或填一个未成功构造的种子都会抹掉证据边界，不是修复方案。

然而schema的`CycleResult/allOf/4`在`status=inconclusive`时无条件要求`seed`、`parameter_point`、`replay_input`为object，`run_record`满足非空RunRecord。将环带非空运输格`entered_at`改为−9223372036854775808后，本席原生CLI回归独立得到exit=2、`inconclusive`、`stop.kind=resource`、`axis=resource.integer`、`completed_ticks=0`及上述四个null。使用独立的AJV2020实现（不是仓库手写schema验证器）复核58个非seed结果，**57通过、1失败**；错误具体指向这四个空字段及allOf/4。详见[独立schema结果](r4-测试与证据/independent-schema.json)与[原始失败对象](r4-测试与证据/revision_r3_cli/age-overflow-cycle-result.json)。

K线README、修订报告及KQ-09已如实披露，没有把该例记为schema通过；本发现不重复指控其误报。问题在于下游若严格按现行唯一schema消费，仍无法接受该合法技术未决结果，接口尚未收口。按写权应由S线把非空要求限定到已有合法上下文的分支，并保留装载资源失败时`cycle=null`、`completed_ticks=0`、`stop.kind=resource`的约束；运行中未决不能借此删除已完成前缀。本席未改schema或内核。

## 3. 独立执行结果与测试口径

| 检查 | 本席结果 | 证据与范围 |
|---|---|---|
| cargo test --locked --offline | 原生120项通过，0失败；1项过滤 | [日志](r4-测试与证据/cargo-test.log)：83内核库、3参考、3 CLI/Python、31 topology。过滤的唯一Rust CLI测试写死旧round5证据目录，会违反复核写权 |
| 被过滤的round5 CLI集成测试 | 相同4次公开CLI调用与全部断言通过 | [等价重跑](r4-测试与证据/redirected-rust-cli.json)：导出种子、迁移后续跑、扫描资源未决统计、非法cycle外壳。只改文件位置。不能把该项写成原生cargo第121项通过 |
| 3个Python CLI集成 | 原断言不变，输出目录重定向 | [包装脚本](r4-测试与证据/bin/python.py)只替换3个脚本的固定证据目录。第3轮59次调用按预期返回；结果保存在`revision_r3_cli/results.json` |
| Clippy全工作区/all-targets/-D warnings | 通过 | [日志](r4-测试与证据/clippy.log)，源码未改，因此复用共享构建缓存 |
| release构建 | 通过 | [日志](r4-测试与证据/release-build.log)，二进制SHA-256见benchmark.json |
| 双样例双编码独立参考 | 4份通过 | [verify-outputs](r4-测试与证据/record-validation.json)，黄金、Python现场重算、完整tick、增量解码和来源闭包 |
| 原扩展记录和循环验收 | 26份运行、10份循环结果通过原验收 | [审计](r4-测试与证据/audit-results.json)、[日志](r4-测试与证据/coverage-audit.log)。其覆盖标签有发现1，不把脚本PASS提升为该标签正确 |
| 新循环搜索与起点回放 | 环带P=20、密集制造序0 P=190，均通过 | [新结果汇总](r4-测试与证据/fresh-cycles.json)；后者a=72、b=262。均为条件低产counterexample，不是全题无解 |
| 手工环带周期 | 20刻、200事件，五字段完整相等 | [手推结果](r4-测试与证据/manual-period-check.json)，下面§5展开 |
| 两补矿模式额外差分 | 30刻通过 | [差分](r4-测试与证据/supply-differential.json)：两模式各出矿30；sufficient补30，explicit补0且库存减少30 |
| 容量读取前停止 | PC/全箱 × 79999/80000四组通过 | [D.2对照](r4-测试与证据/d2-capacity-before-stop.json)：普通运行入矿分别1/0；cycle均D.2停止且0完成刻 |
| 额外独立schema | 57通过、1失败 | 失败即KQ-09，不并入通过总数 |

测试复现：工作目录为`求解器/`，`python -B crates/kernel/复核/r4-测试与证据/run_cargo.py`运行同一原生测试范围。然后分别执行`recheck.py cli`、`recheck.py reference`、`recheck.py audit`、`recheck.py cycle`、`recheck.py benchmark`，以及`probes.py d2`、`probes.py schema`、`probes.py coverage`、`probes.py supply`和`manual_period.py`。所有脚本均在`crates/kernel/复核/r4-测试与证据/`。原`cleanup`、`final_audit`、`finalize`、`scope`含删除或回写被审材料的操作，只读审查，不直接运行其修改入口。

### 黄金、差分、确定性与守恒有没有放宽

`tests/reference.rs:14–38`递归比较对象键全集、数组长度/顺序及标量类型和值；粉碎机4刻summary与固定黄金逐字段比较，两个样例整tick与落盘v3参考比较，`live_python_differential`还现场执行独立Python并先与参考文件比、再与Rust比。没有只比较摘要或删事件。与第3轮开工基线核对，`reference.rs`、两份黄金及两份历史v2运行记录共5份保持原字节，见[黄金指纹](r4-测试与证据/golden-unchanged.json)。这证明本次及第3轮对应基线的保留，不冒充对所有更早历史的完整审计。v3台账升级由现场Python差分核验，未用修改黄金掩盖行为差异。

`tests.rs:132–154`对两个样例各4刻比较两次序列化字节，并反转units/PC/BC输入数组后比较完整tick；`tests_round5.rs:233–245`另反转inventory。输入中的真实语义顺序没有被排序掉。缓存差分实际比较默认关闭缓存与显式打开缓存，两旧样例、7个扩展样例及3档合成大布局均保留整tick相等断言。

种子往返比较两个旧样例完整tick；第3轮真实桥t=5检查点经seed保持完整nonwarehouse对象，续跑t=6的time/state/events/ledger/closure与长轨迹相等。缺参数、重复参数、表内冲突、仅顶层改相位、错误生命周期均拒收；历史初相位在before_boundary/after_closure均核整数0…5，合法历史相位无需等于当前冷却。到期门窗口负例覆盖deadline<t、=t、>t；before_boundary恰到期正例实际执行对应W事件。既有KQ-02/06旧停止预期改成t+1续跑/切支成功，依据主席已定和最终规格，不是放宽同一契约的断言。

守恒测试从80000仓库与完整制造原料/成品变换核总量；新增仓库账逐物种核`ΔW=实际入库+补矿−出库−外取−代表调整`。扩展Python审计还从实际成功移动、箱库存和传输事件重建明细，核按口出入与无线整箱账，不只相信totals。额外30刻两模式差分比较inventory/progress/logistics/environment、全部事件/时间/闭包及实际出入明细；独立以仓库前后数量核每刻守恒。参数模式、补给账和矿库存是预期差异，不删其它动态字段掩盖差异。原last-ore回归另验证sufficient库存为1也不会假断供。

## 4. 性能复测

同一当前release二进制、同一已锁定输入，每档3次，每次12 tick，输出关闭；ms/tick取内核elapsed_ns/12，含推进不含解析/构造/序列化。三次原始值均保留，未挑最好的一次。没有重生成或覆盖被审benchmark。当前两档结果如下；负载并非隔离CPU，不能据此声称任何机器或任意布局均达标。

| 输入 | 单位/PC | 三次ms/tick | 中位数 | 判读 |
|---|---:|---|---:|---|
{benchmark_table}

砖档目标≤1，B档目标≤20；两档每次均满足。额外81单位/100PC的纵向送料对照超过1，原报告也已披露，不能替换57单位的指定砖档数字。B档含219台制造单位、315逻辑段展开630PC，共535单位；制造关闭、有限预装货，仅测合成物流。证据是[benchmark.json](r4-测试与证据/benchmark.json)，其输入/二进制指纹与旧基准吻合。本复核不把合成性能当候选B几何可行或满载生产证明。

## 5. 从循环起点手工推一个周期

对象为本席新生成的[环带循环](r4-测试与证据/生产循环环带-fresh-cycle.json)。起点t=0、after_closure：一件电池在b，entered_at=0；a/c/d空；box六格全空、传输冷却5；t=0前缀已经把箱内5胶囊存入仓库。固定模板依次a→b、b→c、c→d、d→a、box传输。各存取侧只有一个环成员，故不存在选择另一分支的自由度。

独立推导：规则L23使每刻开始时那一件电池刚好可出；目标空，单边双授权且预算空，成功移到下一格。进入后年龄0，不能在同刻再出，正式端口速率也保持；源空的其它判定失败。源未分级单成员环即使失败前移也回自身，输入最高可动级在终态全部为空。第一轮有一次物流改变，第二轮只失败/冷却访问且调度状态相同，恰两轮闭包。依据规则L36和本版every_attempt，空箱在t=5、10、15、20尝试并起5 tick冷却，其余时刻减1。

代表化仅在t=1把前缀存入的5胶囊归零并保留身份；它不是玩家动作或实际交付。两矿/四种植物仓库格、所有参数、图、建造常量、仲裁、空格序保持；无制造、门和pending事件。每刻tick_context只含本次一条移动与两个端口各1额度，窗口为[t,t+1)，judgment为after_closure/round=2。由此可逐字段构造完整状态，而不是只猜电池位置。

| t | 唯一成功移动 | 闭包电池位置 | 冷却 | 箱体 | 代表扣胶囊 |
|---:|---|---|---:|---|---:|
{period_table}

电池位置周期4，空箱冷却周期5，故联合周期为lcm(4,5)=20。t=20电池在b且相对年龄0、冷却5；图/游标/级/额度与t=0同形。完整状态中的绝对时间和成功事件id不同，成品仓库5/0也不同；按最终§6.2只对允许字段规范化后键相等。非抽象库存没有丢弃，未把私有closure_key替换成生产键。

[manual_period.py](r4-测试与证据/manual_period.py)从起点复制静态字段，按上述递推生成全部20刻，**不调用Rust转移、Python执行参考或现有轨迹来生成期望后态**；逐字段比较time/state/events/warehouse_ledger/closure，包含全部200条事件、完整状态、数值category和basis文案，差异数0。期望全文在[manual-expected.json](r4-测试与证据/manual-expected.json)。循环内两成品实际入库均0，故精确率0<3/5、0<11/20；t=0旧入库不在(a,b]，不可把5/20算作周期产量。summary的全前缀累计口径由整份verify-cycle重算核验，不在独立P步动态字段中偷换累计起点。

另一个新搜出的密集制造序0周期P=190已由verify-cycle从a=72重跑190步，显示手工小例之外的完整恢复流程也通过；它不是本节手工证明的一部分。4份密集条件周期、2份预算未决保持分开。

## 6. 新覆盖轴逐项核原始事件

本席对原审计要求的31轴逐项保存所报状态、记录SHA-256及首条原始事件，并核所有声称事件ID都能在该记录中定位，见[31轴摘录](r4-测试与证据/coverage-event-excerpts.json)。下表中事件ID按原文保留；“已执行”只表示对应代码路径在这些条件下实际发生，不代表替代读法被区分或一般约束被证明。

| 轴 | 抽查原始记录与事件 | 核到的内容与限制 |
|---|---|---|
{coverage_table}

桥双通路的30刻中，south→vertical→north与west→horizontal→east四条PC各成功8次，箱无线交付两成品各8；普通桥双轴单元测试还核t=0各轴存1、下游为空，t=1分别到达正确下游且总量守恒，同种同时占两轴负例被拒。故“桥真的跑起来”有实际证据。先接历史在种子前，不能把搬运算作定向；该项input_checked修复成立。

研磨例在t=3和t=5发生两次真实制造完成，分别处理蓝铁粉末/源石粉末加砂叶粉末，产出两种致密粉末各1并实际无线入库。recipe_intents或文件名没有被当作混做证据。拒收/暂停例t=0全箱warehouse_capacity失败、无线账空，east_box正冷却在停用段保持；没有恢复转移，故resume缺口不能关闭。

门切支例记录两次W到期恢复，图和分支表按当前可用出支集合变化；多级取货侧确实请求阻尼，连续带也实际进入path_runs计数。唯独几何邻接轴没有被调用，修正后K6要求中至少三项仍无运行覆盖：先接、恢复、几何邻接。前两项已诚实披露，本报告不把合理登记的支持域缺口重复制造成新实现错误。

轮询均分6局部序每份都有31组单件供货，A/B/C为11/10/10；30件已见恰1 tick释放，末刻新收件的未来未观察，未声称31件都已释放。记录还核下一组前释放、同级三通道和真实矿料/精炼前件。密集制造4份周期核竞争来源正量、D总量正、M恰1 tick释放与空旁路服务，比例0/1；序2/5在1000刻内未决。这些有限或条件证据保留范围，不替代全部模板全序、全部种子或一般动态约束的证明。

## 7. 第3轮修复回归与证据维护

第3轮L1-01/L2-01检查点参数、L1-02窗口、L1-03周期完整前缀、L1-04两矿、L2-02相位、L3-01畸形输入，均保留正反例并在本次原生测试/公开CLI中通过。L2-03桥先接标签已改input_checked，缺口说明真实；本次发现的是另一条邻接轴误报。L3-02资源分类正确，但schema兼容仍为发现2。L3-03清理清单中的15个ELF/ar文件和193个快照文件逐路径确认不存在；4组小探针迁到legacy_probes，README明确依赖当前实现，未把重新构建它们称为旧实现复现。

原`audit_revision_r3.py`对KQ-09专门记录gap，并没有静默吞成pass；`finalize_revision_r3.py`读该gap写未决。原`final_audit_round5.py`与`scope_revision_r3.py`会回写报告、基准/清单，且后者含清理检查，故本席使用只读指纹与独立输出替代执行这些修改入口。它们在覆盖聚合上继承发现1，在KQ-09上保留了正确披露。

本席开工保护清单含658份当前源码/规格/数据/旧证据与根目录正式/候选文件（排除共享构建/依赖缓存及各席复核树），收尾逐字节均未变；与原修订席2362份保护对象是不同统计范围，不混称2362为本席新验数。正式3文件与候选文件单独包含在658份内。当前报告及本目录未复制任何target、registry、.cargo-home、整仓快照或二进制。

完整检查记录与最终指纹见[收尾自审](r4-测试与证据/交付自审.json)。结论适用于所锁定当前字节；若内核、规格或样例随后变化，需要针对新字节复核。
'''
(K/'复核/复核-r4-测试与证据.md').write_text(report)
print('report',len(report),'characters; findings',len(findings))

if __name__=='__main__':pass
