# 批E(RFC-003)实施规格:semantic dedup + JSONL ledger + epoch 记账

> **状态:侦察齐备、拍板成文(2026-07-12 晚立项)**。随批双审把关后实现。
> 三路侦察全部回报:scout-e-ledger ✅ / scout-e-dedup ✅ / scout-e-host ✅(宿主 harness 并入本批侦察面,解「批C 宿主环」)。

- 立项依据:`02_rfc_adoption_assessment.md` §RFC-003 采纳序 ①semantic fingerprint 严格相等去重
  (指纹禁含时间戳/iteration)②JSONL append-only 最小 ledger(APPLIED 记录+restart 全链
  replay,「不能直接相信上次 APPLIED」照单全收);③selector 打分/六维 watcher/family
  dominance 后置不做。验收含 rollback 演练 + batch0/C1 基线 cut off/on A/B(02:56-58,
  与 M5/1F smoke 共用基线合并排期)。
- B6 线位置:本批是 flip 前置(lock:492),且是批C(PIC-4)的实测对象——ledger+dedup 不先落,
  批C 测到的池行为是将被本批改写的旧行为。

## §0 侦察颠覆的一个前提(本批中心拍板的地基)

RFC-003 §1 的问题陈述假设「常驻 cut 池 + 已 APPLIED cut 跨 epoch 漂移失效」。侦察坐实:
该场景在当前架构里已被**结构性消灭**——

- typed cut **100% 随进程死**:CompiledCut/ConstraintPlan 无任何序列化(grep 空);生产 attach
  路径(`_maybe_attach_framework_cuts`,benders_loop.py:8119)每次 fresh 生成→validate→
  compile→apply,不经 CutStore/serialize/replay。
- CutStore 纯内存且**生产零调用**(store.py:71-77 docstring 明写 disk persist 是 P1.21 defer;
  CutStore/replay_cut/regression_sweep 只在测试出现)。
- master **per-rect 新建**(run_benders_for_ghost_rect 内),「每次 master build=天然 epoch」
  (02_rfc 判定)在源码上仍准确。
- **V82 条款已是「不信任上次 APPLIED」的既有实现**(benders_loop.py:8862-8867):certified 下
  持久 exact_safe_cuts 被强制丢弃重生成("performance hints, not proof objects");checkpoint
  resume 侧 `_sanitize_resume_state_for_untrusted_candidate_evidence`(exact_campaign.py:2160)
  把候选强 status 清为 UNKNOWN 且 `exact_safe_cuts=[]`。

即:RFC §7「restart 时读 ledger proof envelope 全链 replay」要防的那个「信任旧 APPLIED」漏洞,
今天靠**根本不持久化、全部重生成**防得更彻底。

**dedup 侧侦察(scout-e-dedup)再坐实两件事**:

- **指纹已在阶段B 顺带造好且 RFC §5 逐字段合规**:F1/F6/F7 各有 `*_semantic_fingerprint_v1`
  (region_capacity_typed.py:348-377 / shape_packing_hall_typed.py:372-402 /
  power_hitting_set_typed.py:298-328),投影同构(compiler_version/family/model_scope/
  operation/parameters/parameter_schema/schema_version/snapshot artifact identities/
  source_digest),**不含时间戳/iteration/oracle 名/审计计数**;挂 ConstraintPlan
  (typed_platform.py:529-580)。批E ① 的「造键」已完成,剩「接线」。
- **单 epoch 内重复真实存在且无任何既有去重**:attach 链(编排循环 benders_loop.py:8308-8341
  /typed_apply/master `_lower_*`)全程无 fingerprint 去重;预算(:8193/:8309)计「已 attach
  约束数」,重复照吃。最干净的重复源是 F1:ghost-agnostic+生成不吃 solution+指纹输入帧内
  全冻结→同一条约束在一个 rect 的 ≤30 轮 benders 里可被重复编译重复 Add ≤30 次(I-8 场景
  实锤,发生在**单 epoch 内**而非跨 epoch);F6 anchor 稳定时同理;F7 吃 incumbent 随轮变;
  F5 shadow-only 不占预算。cut_id 夹带墙钟时间戳/iteration(region_capacity_oracle.py:205 等)
  但均不进指纹。
- **主会话复核**:两个 `master.build()` 调用点(benders_loop.py:8752/8798)是互斥分支且都在
  controller 创建(:9133)之前各执行一次——**controller 生存期内 master 不 rebuild**,
  controller 级 pool=per master build=per epoch 今天严格重合(D-2 锚点依据)。

**宿主侦察(scout-e-host)解开「批C 环」并重划 PIC-4/5 可验层级**:

- **直建 harness 已存在并 prod-scale 跑过**:`docs/research/p1_3_m5_convergence_20260708/
  m5_cell_runner.py:117-203`——净室构造(建 session/master 前 pop env)→构造后设
  `EXACT_CUT_FRAMEWORK_ATTACH=1`→`controller.run_with_status()` 走完整 `_maybe_attach`
  编排。守卫是**纯入口门**(全仓 4 处、全 keyed `solve_mode=="certified_exact"`:
  ExactSearchSession.create benders_loop.py:2246-2248 / create_exact_search_session
  :2326-2339 / run_benders_for_ghost_rect :8524-8555 / run_outer_search
  outer_search.py:1770);attach 机制自身只读 env 不查 mode(:7912-7922)。
  「入口守卫 vs controller 层放行」边界已被现有红测钉死(test_ghost_anchor_filter.py:
  241-277 / test_orbit_homogeneity_gate.py:119 / test_cut_framework_attach_wiring.py:
  274-292)。**环解开,不动 lock、不动 sealed 文件**。
- **PIC-4 层级重解释**:框架 cut ghost-bound/per-master,结构上不跨 solve 迁移(跨 solve
  持久的是 whole-layout nogood=另一机制 preloaded_exact_safe_cuts);anchor 切换退役
  发生在**单 controller 多迭代之间**(resolver conditioned 在 u_var 上,lifecycle.py:
  1657/1686/1797-1806,换 anchor 后 `OnlyEnforceIf(u_var)` 恒假即物理失活)。「跨 solve
  cut 池演化」对框架族主要是 within-solve 池+预算行为——单 controller harness 即可复刻。
- **批C 三卡点(排期依据,非本批范围)**:①组织性触发未验——spike 只灌 direct step_8,
  当前表示+可解配方下 binding-INFEASIBLE 是否真发生从未复现(历史 cuts_6x6.json 证明旧
  表示下发生过 5 次);批C 第一验=6×6 可解配方 attach-on 单点,看
  coordinate_framework_cut_count>0。②算力:每 solve ~500-650s/尖峰 ~60G/一次只能一个,
  完整 A/B 矩阵需 owner 算力窗口。③生产 campaign 多 rect 编排层恰是守卫层,attach-on
  走不了——批C 用 harness 自建多 rect 外循环复刻;真生产编排层诚实标记为 flip 后烧机验
  (已列入 #9 promotion 包第⑤项)。

## §1 中心拍板(草案,待三路侦察齐后定稿、随批双审)

**D-1 ledger 承担面:方案 (b) 重生成为主,ledger=审计+去重+epoch 记账,不承担 envelope replay。**

- (a) RFC §7 字面:ledger 携 proof envelope,restart 后 deserialize→cut_to_envelope_v1→
  validate_and_compile(fresh snapshot)→resolver(fresh master)→step_8 全链重走。
- (b) V82 哲学:restart 后一切 cut 由 generator 从当前 state 确定性重生成(与今天行为相同);
  ledger 不作为任何 cut 的来源,只作为 append-only 审计事实(GENERATED/REJECTED/VALIDATED/
  SHADOW/APPLIED+receipt/POISONED)、per-epoch dedup 记账与 rollback 演练证据。
- 倾向 (b) 理由:①(a) 新开一条「磁盘→master」注入通道,纵深上是新攻击面,而其全部收益只是
  省 oracle 重生成的 warm-start(价值未证,PIC-4 可实测);②(b) 与 V82/resume-sanitize 既有
  纪律同构,「不能直接相信上次 APPLIED」被更强形式满足(根本不消费);③typed 链的 snapshot-
  native 复验使 (a) 可以做 sound,但 sound≠值得——重生成本身就是最强的 re-qualification。
- **对 02_rfc 采纳判定的偏差登记**:采纳序②字面含「restart 全链 replay」。本批把它重解释为
  「restart 后资格全链重取得(经由重生成)」,并保留 ledger 格式向前兼容(事件携 payload_digest
  与 plan digest,若未来实测证明 warm-start 有价值,(a) 可在不改 ledger 格式的前提下另批叠加)。
  此偏差随批双审把关,并在 owner 面前明示。

**D-2 dedup 作用域 = per master build(=per epoch),进程内存,不跨进程/不跨 rect。**

- 「重复」只在同一个 master 的约束集合内有意义;跨 epoch 用 ledger 事实去重会把「新 master
  还没有这条约束」误判为重复→少 attach(方向 safe:under-cut 只损性能不损 soundness,
  但语义就是错的)。ghost-bound cut 的 fingerprint 已含 ghost 身份→跨 rect 天然不同指纹。
- 命中处置:不重注,ledger 记 REJECTED(reason=semantic_duplicate)/hit++(RFC §5);
  绝不 raise、绝不影响首次 attach。
- **落点(侦察候选 A,拍板采纳)**:编排层——`_maybe_attach_framework_cuts` 的
  `isinstance(result, CompiledCut)` 分支内、step_7/step_8 之前,键=`result.plan.
  semantic_fingerprint`(RFC §7 伪码明写的键);pool=controller 实例上的 `set[str]`
  (attach 跨 ≤30 次调用累积,不能做调用局部量)。不碰 master(重 TCB,B 候选否)、
  不碰 registry/resolver(无状态性不破坏,C 候选否)。锚点安全性见 §0 主会话复核
  (controller 生存期内 master 不 rebuild);实现随附「一 controller 一 master build」
  不变量注释+防回退断言。
- 碰撞方向分析(fail-closed 论证,双审把关点):严格相等 SHA-256 下指纹命中 ⟺ canonical
  projection 逐字节相同 ⟺ 同一条 lowered 约束(投影已捕获区分同族两条不同约束的全部
  语义量:F1 capacity+group_cell_weights+domain_fingerprint;F7 blocked_cells_digest+
  group_id+pose_id+ghost_rect_digest;plugin compile 为确定性纯投影)。故严格相等去重
  不可能误杀语义新 cut。另一重保险:即便误杀,方向也是 under-cut(master 少一条剪枝
  约束=松弛),FP=0 exactness 不受威胁,只损性能。

**D-3 epoch 粒度 = per master build(per run_benders_for_ghost_rect),epoch_id=RFC §2 四 digest
+ rect/master 身份。** CP-SAT 约束不可删,rebuild=重建 master——今天 per-rect 重建即天然
epoch 边界,与 02_rfc 判定一致。

**D-4 poison 语义映射 = fail-closed abort。** RFC §3 的 POISONED epoch「保留诊断、禁发布」
在本项目映射为:APPLY 后任何完整性失败(α-1 内容绑定、resolver 复验、typed_apply 失败)
已经/继续是异常中止该 rect solve(既有 fail-closed 哲学),ledger 补记 POISONED 事件作审计。
不新开「带毒继续跑」路径。

**D-5 ledger 位置=data/cuts/(gitignored),scope key=(campaign_instance_id, epoch_id, seq)。**
文件 `cut_ledger_<campaign_instance_id>.jsonl`;harness/非 campaign 进程用显式 run_tag 代
campaign id。选 data/cuts/ 而非 data/checkpoints/:①.gitignore 预留语义(CutStore
disk-persist,P1.21 defer)与 ledger 同源;②不与 checkpoint 轮换/清理生命周期耦合;
③data/checkpoints/benders_cuts.jsonl 是 CutManager legacy 通道的 reserved 槽位,不占用
不混写。禁区不碰(data/solutions/ 等 proof 输出;tracked 路径违 reseal 铁律)。

**D-6 崩溃整性=单调 seq + prev_event_hash 链 + 逐事件整行 write+flush;APPLIED/POISONED
与正常关闭时 fsync;reader 全程 fail-closed。** 截断尾行(不完整 JSON/链断/seq 跳变)整行
拒收且其后不再消费(RFC §8「只消费完整事件」的工程化);PREPARED 绝不当 APPLIED(§9 门 4)。
(b) 下 ledger 是审计通道非 proof 通道,故高频 GENERATED/REJECTED 不逐事件 fsync(逐事件
flush+hash 链已够审计档,放宽点仅此一处);但 rollback 演练(§9 门 7)消费 ledger 当证据,
链与 seq 的 fail-closed 不放宽。先例:atomic_write_json(exact_campaign.py:1619,
tmp+fsync+replace)、CutManager append(cut_manager.py:569-570)。

**D-7 事件词表**:RFC §2 八词表基础上,F5(结构上永不 apply)记 VALIDATED+SHADOW 变体、
legacy 四族在 registry 边界拒绝记 REJECTED(stage=registry)——确保「无 APPLIED 事件的家族」
在 ledger 上可辨认,rollback 演练(§9 门 7)才有干净证据。

**D-8 F5 不进本批 dedup。** ShadowValidated 无 plan/semantic_fingerprint,唯一内容地址
proof_digest 含 core_minimization 审计统计(pattern_nogood_oracle.py:312-324)——用它去重
违 RFC §5 禁含项;且 F5 不 apply 不占预算,I-8 动机对 F5 不成立。若 F5 转正批需要 dedup,
届时先造不含审计计数的语义投影(登记进批D 规格 §5 清单的关联项)。

**D-9 cut_id 不动(批E)。** F1 cut_id 的墙钟时间戳不进指纹、去重后不再是预算污染源;
ledger 事件以 (seq, cut_id, semantic_fingerprint, payload_digest) 联合定位,审计可复现性
由 fingerprint 承担((b) 下 ledger 不作注入源,cut_id 非确定性只是审计瑕疵)。cut_id
确定性化(如嵌 fingerprint 前缀)列为可选后续,留给下一个碰 oracle 文件的批顺带——
region_capacity_oracle.py 等是 sealed 面,单独为此开 reseal 轮不值。

**D-10 去重记账双写。** 本批 ①② 同批落地:命中 semantic_duplicate 时 ledger 记
REJECTED(semantic_duplicate) 事件,同时进 `stats["cut_framework_attach_last"]` 新增
semantic_duplicate 计数字段(既有 telemetry 形态,benders_loop.py:8346-8354)。

**D-11 宿主=m5_cell_runner 基座扩展(直建 harness 路线坐实,批C 复用,依据见 §0 宿主
侦察段)。** harness 扩展放批C/批E 共用的 docs/research/ 实验目录(非 src 非 sealed):
换已证可解配方(fixed+p3+s3,m5_ab_param_bisect_20260711)、接 ledger/dedup telemetry
断言、调高 max_iterations 备 anchor 退役观测。「净室构造→构造后设 env→run_with_status」
是 sanctioned 形态(现有三处红测钉着入口/controller 边界),批E 不新增守卫豁免、不动 lock。

## §2 范围(待侦察齐后定稿)

1. semantic fingerprint 严格相等 dedup(落点待 scout-e-dedup:候选=validate_and_compile 后、
   selector/预算扣减前,RFC §7 形态)。
2. CutLedger(JSONL append-only)+ ModelEpoch 记账,接进 `_maybe_attach_framework_cuts`
   编排(certified 下该路径本就禁用,不碰 certified 行为;harness/PIC-4 消费)。
3. RFC §9 七门测试映射(见 §4)。
4. **宿主 harness(并入本批,D-11)**:以 m5_cell_runner.py 为基座扩展。批E 交付 harness
   扩展本体+fixture 级触发验证(既有 stage_b fixture 通路,cuts 真流经 dedup/ledger);
   prod-scale 单点触发验证(批C 卡点①)与完整 A/B 矩阵(卡点②)归批C,owner 排算力窗口。

## §3 不做面

- selector 打分/六维 watcher/family dominance(RFC 自排后置;§6 指标只留 ledger 字段占位)。
- envelope replay 注入通道(D-1 (b);格式向前兼容留门)。
- CutStore/replay.py 双表接通生产(RFC §10 明说不应作生产正确性依赖;ledger 独立实现)。
- F5 转正面一切;certified 行为一切(attach 仍 unsafe-map 禁用)。

## §4 测试义务(RFC §9 七门在 (b) 语义下的映射,草案)

| RFC §9 门 | (b) 语义下的形态 |
|---|---|
| 1 APPLIED→QUARANTINE 禁 publish | poison=fail-closed abort+ledger POISONED 事件(D-4);红测:apply 后注入完整性失败→solve 中止且事件落账 |
| 2 ghost condition 错位 fail-closed | 已有 resolver/§2.6 三重绑定红测,补 ledger 侧事件断言 |
| 3 同语义不同 cut_id 只 attach 一次 | dedup 正例红测:F1 同 controller 两轮 attach(iter 0/1,cut_id 含不同时间戳/iteration)→第二轮 REJECTED(semantic_duplicate)+hit++,master 约束计数不变;负例:真语义新 cut(改 capacity/region)不被误杀 |
| 4 crash 截断不把 PREPARED 当 APPLIED | reader fail-closed 截断测试(坏尾行拒绝;(b) 下 reader 只服务审计/演练,不服务注入) |
| 5 restart 全链 replay | 重解释:restart 后 cut 全部经重生成重新取得资格(既有行为)+ledger 新 campaign_instance 事实连续性测试 |
| 6 batch0/C1 cut off/on A/B | 拆两层:批E=fixture 级 off/on 等价断言+harness 扩展就绪;prod-scale 单点触发验证与完整 A/B 矩阵归批C(卡点①②)——不得把 fixture 绿当 prod 层已验(PIC-5 同款纪律) |
| 7 rollback 演练 | 关 family 后新 epoch 重生成天然排除该族;ledger 证据断言「新 epoch 零该族 APPLIED」 |

## §5 reseal 面(预估,待范围定稿)

- 碰 benders_loop.py(编排接 ledger/dedup)=v99 floor+JSON sink 双钉+checker 自钉连锁。
- 新文件(ledger 模块)是否入 floor/sink:按「是否 TCB」判——(b) 下 ledger 不在 proof 通道,
  倾向 mypy target+测试钉、不入 close-kernel(随双审把关)。
- typed_platform/lifecycle 若因 dedup 落点被碰→相应 reseal。

## §6 双审与落地记录(待填)
