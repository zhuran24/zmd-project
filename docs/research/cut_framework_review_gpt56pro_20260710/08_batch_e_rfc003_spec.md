# 批E(RFC-003)实施规格:semantic dedup + JSONL ledger + epoch 记账

> **状态:rev2(2026-07-12 晚)——规格双审(opus 设计位 AGREE_WITH_AMENDMENTS 4M+6L /
> codex 第二视角 BLOCK→修订条件全采纳)后的修订版**。§6 记录两审裁决与逐条处置。
> **D-1 是对 02 采纳判定的实质 waiver,须 owner 显式批准后方可实现**(codex BLOCK 条件之一)。
> 三路侦察:scout-e-ledger ✅ / scout-e-dedup ✅ / scout-e-host ✅(宿主并入,解「批C 宿主环」)。

- 立项依据:`02_rfc_adoption_assessment.md` §RFC-003 采纳序 ①semantic fingerprint 严格相等去重
  (指纹禁含时间戳/iteration)②JSONL append-only 最小 ledger;③selector/watcher/dominance
  后置不做。验收含 rollback 演练 + batch0/C1 基线 cut off/on A/B(02:56-58)。
- B6 线位置:本批是 flip 前置(lock:492),且是批C(PIC-4)的实测对象。

## §0 侦察坐实的地基事实

RFC-003 §1 的问题陈述假设「常驻 cut 池 + 已 APPLIED cut 跨 epoch 漂移失效」。侦察坐实:
该场景在当前架构里已被**结构性消灭**——

- typed cut **100% 随进程死**:CompiledCut/ConstraintPlan 无任何序列化(grep 空);生产 attach
  路径(`_maybe_attach_framework_cuts`,benders_loop.py:8119)每次 fresh 生成→validate→
  compile→apply,不经 CutStore/serialize/replay。
- CutStore 纯内存且**生产零调用**(store.py:71-77 docstring 明写 disk persist 是 P1.21 defer)。
- master **per-controller 恰好构建一次**:8752 显式 build / 8798 显式 build / 8756
  `from_exact_core` 内部构建(master_model.py:2996-3018,`_built=True`)三路互斥,均在
  controller 构造(:9133)之前完成——**controller 生存期内 master 不 rebuild**(rev2 订正:
  初版只列两个显式点,漏 from_exact_core 内建路,不变量结论不变;双审 F7/codex#3 同点)。
- **V82 条款已是「不信任上次 APPLIED」的既有实现**(benders_loop.py:8862-8867):certified 下
  持久 exact_safe_cuts 强制丢弃重生成;resume 侧 `_sanitize_resume_state_for_untrusted_
  candidate_evidence`(exact_campaign.py:2160)把候选强 status 清 UNKNOWN 且 exact_safe_cuts=[]。

**dedup 侧**:

- **指纹已在阶段B 造好且 RFC §5 禁含项合规**:F1/F6/F7 各有 `*_semantic_fingerprint_v1`
  (region_capacity_typed.py:348-377 / shape_packing_hall_typed.py:372-402 /
  power_hitting_set_typed.py:298-328),挂 ConstraintPlan(typed_platform.py:529-580)。
- **指纹语义=lowered-constraint 等价,不是完整 proof 身份**(rev2 明确,codex#4):
  typed_apply 的 lowering 是 (operation, parameters, condition_lits, blocked_cells) 的纯函数
  且这些全被指纹吃进;但 proof 级字段(如 F1 RegionCapacityBody.region_cells,
  region_capacity_typed.py:72-79)不进指纹——两个不同 region witness 若导出同 capacity/
  weights/scope,指纹相同、lowered 方程也相同,**去重仍安全**(跳过的是物理上完全相同的
  约束)。「指纹命中⟺同一条 lowered 约束」在 **SHA-256 抗碰撞假设下**成立(非无条件数学
  等价);碰撞方向仍只是 under-cut。
- **单 epoch 内重复真实存在且无既有去重**:F1 ghost-agnostic+生成不吃 solution→同一条约束
  一个 rect 的 ≤30 轮里可被重复 Add ≤30 次(I-8 场景实锤);预算(:8193/:8309)计约束数,
  重复照吃。F7 吃 incumbent(target_poses,:8241-8248)随轮变;F5 shadow-only 不占预算。

**宿主侧(解「批C 环」并重划 PIC-4/5 可验层级)**:

- **直建 harness 已存在并 prod-scale 跑过**:`docs/research/p1_3_m5_convergence_20260708/
  m5_cell_runner.py:117-203`——净室构造(建 session/master 前 pop env)→构造后设
  `EXACT_CUT_FRAMEWORK_ATTACH=1`→`controller.run_with_status()` 走完整编排。守卫是
  **纯入口门**(4 处:benders_loop.py:2246-2248/:2326-2339/:8524-8555,outer_search.py:1770);
  attach 机制只读 env 不查 mode(:7912-7922)。「入口守卫 vs controller 层放行」边界已被
  现有红测钉死(test_ghost_anchor_filter.py:241-277 / test_orbit_homogeneity_gate.py:119 /
  test_cut_framework_attach_wiring.py:274-292)。**环解开,不动 lock、不动 sealed 守卫**。
- **PIC-4 层级重解释**:框架 cut ghost-bound/per-master,不跨 solve 迁移(跨 solve 持久的是
  whole-layout nogood=另一机制);anchor 切换退役发生在**单 controller 多迭代之间**
  (lifecycle.py:1657/1686/1797-1806,`OnlyEnforceIf(u_var)` 恒假即物理失活)。
- **批C 三卡点(排期依据)**:①组织性触发未验——当前表示+可解配方下 binding-INFEASIBLE
  从未复现(历史 cuts_6x6.json 证明旧表示下发生过 5 次);批C 第一验=6×6 可解配方 attach-on
  单点看 coordinate_framework_cut_count>0。②算力:每 solve ~500-650s/尖峰 ~60G/一次一个,
  A/B 矩阵需 owner 算力窗口。③生产 campaign 多 rect 编排层恰是守卫层——harness 自建外循环
  复刻,真生产编排 flip 后烧机验(#9 promotion 包⑤)。

## §1 拍板(rev2,双审修订已合入)

**D-1 ledger 承担面:fresh-model regeneration + non-consumption isolation——对 02 采纳判定的
实质 waiver,须 owner 批准。**

- 机制:restart 后一切 cut 由 generator 从当前 state 重新生成并完整走 typed 链(与现行
  V82/resume-sanitize 行为同构);**ledger 数据绝不影响 generator/selector/apply(非消费
  隔离,结构性不变量)**;ledger=审计事实+per-epoch 去重记账+rollback 演练证据。
- soundness(双审均确认):restart 必建新 master、旧 pool/constraint/receipt 零继承、新 cut
  全链资格——未重生成的 cut 只是 under-cut,不 over-prune;比 (a)(envelope replay)少一条
  磁盘→master 注入通道。
- **诚实边界(rev2,codex#1/#2 采纳)**:
  - **不声称 RFC §7 restart-replay 门被满足**——该门以 §4 门 5 的**替代门**重定义并明示替代。
  - **重生成不是确定性的**:F7 由 incumbent 驱动,restart 后不同 seed/workers/hint 的
    incumbent 可不含原 pose→F7(P) 不再生成;cut 集/搜索轨迹/branches/wall 不可跨 restart
    复现;固定预算下可能重访已排除 incumbent。这是 (b) 的真实代价,按「性能/可复现性代价、
    非 soundness 代价」登记。
  - **(a) 独有且 (b) 真丢的东西**:①warm-start;②跨 restart 审计连续性(补救=GENESIS 事件
    记 predecessor 血缘,见 D-5);③proof preimage 不可从 digest 重建——「格式向前兼容」
    仅指事件字段可扩展,**不承诺凭现有字段可重建 (a)**;若未来实测证明 warm-start 有价值,
    须另加 content-addressed envelope 存储(仍禁注入)另批评审。
- **owner 批准点**:02 采纳判定(双审定稿)字面为「APPLIED 记录+restart 全链 replay 照单
  全收」;本批改裁为上述 waiver。批准前不实现。

**D-2 dedup:编排层严格相等去重;pool=「已成功 APPLIED 指纹集」,挂 controller 实例,
绑定 build generation。**

- CHECK 位置:`_maybe_attach_framework_cuts` 的 `isinstance(result, CompiledCut)` 分支、
  step_7 之前;键=`result.plan.semantic_fingerprint`。
- **INSERT 时机(rev2,codex#3/opus F4 收敛采纳):仅在 step_8 成功返回之后**。顺序:
  `fp in pool→跳过记 duplicate; step_7; resolver; step_8; pool.add(fp)`。防「首个同指纹
  cut 被 step_7 attach_timing 拒绝(benders_loop.py:8322-8324 真实非 attach 路径)或 step_8
  异常后,指纹残留 pool 永久误杀后续」。
- pool=controller **实例**属性(非类级可变默认,防跨 rect 泄漏);随 controller 构造捕获
  master build 身份(epoch_instance_id,见 D-3),attach 入口断言 generation 未变——防未来
  同对象原位 rebuild 后旧 pool 误杀(今天不可达,断言是防回退钉)。
- 命中处置:不重注、ledger 记 REJECTED(semantic_duplicate)+hit++、telemetry 计数;绝不
  raise、绝不影响首次 attach。误杀方向兜底:under-cut 只损性能,FP=0 不受威胁(benders
  的完备性由 whole-layout nogood+子问题闸独立保证,framework cut 是可选强化)。
- **ghost 唯一性哨兵(rev2,codex#4)**:`_locate_master_ghost_rect`(lifecycle.py:1302-1322)
  首匹配即返、不拒多匹配;生产 builder 每坐标恰一变量(exact_coordinate_master.py:4124-4139)。
  本批加**测试侧哨兵**:对生产构建 master 断言 ghost rect digest 全局唯一;resolver 侧
  多匹配拒绝(碰 sealed lifecycle.py)登记为后续加固项,不入本批。

**D-3 epoch:双标识。** `epoch_instance_id`=每次 master build 唯一(进程内单调+进程身份,
用于 pool 绑定与 ledger 事件);`epoch_semantic_digest`=RFC §2 四元组(source_digest/
artifact_set_digest/master_schema_version/enabled_family_manifest_digest,后者来源见 D-13)
+rect 身份——可跨进程比对。今天 per-rect 重建=天然 epoch 边界(02_rfc 判定,源码坐实)。

**D-4 poison 语义映射=fail-closed abort。** RFC §3 的 POISONED「保留诊断、禁发布」映射为:
**apply 链路上任一闸失败即 fail-closed 异常中止该 rect solve**(α-1 绑定/resolver 复验在
apply 前、typed_apply 失败在 apply 中——rev2 措辞订正,opus F8),ledger 补记 POISONED
作审计;单 epoch 内输入全冻结(snapshot 单次构建 :8233、artifacts hash-frozen)→自然漂移
mid-epoch 不可能;ghost 切换经 OnlyEnforceIf 物理失活非 poison;跨 epoch=fresh 重生成;
RFC 第 5 类「replay 不一致」在 (b) 下 N/A。不新开「带毒继续跑」路径。**ledger 自身写失败
(write/flush/fsync 异常)同样 poison+abort**(codex#5):审计通道断了就不该继续产可信结论。

**D-5 ledger 落盘协议:per-writer segment + GENESIS 血缘链,绝不原地续写。**(rev2 重写,
codex#7 主发现+opus F1 合并采纳)

- 位置 `data/cuts/`(gitignored;不与 checkpoint 轮换耦合;不占用 legacy 通道 reserved 的
  data/checkpoints/benders_cuts.jsonl)。禁区不碰(data/solutions/ 等;tracked 路径违 reseal)。
- **单写者=单 segment 文件**:`data/cuts/<campaign_instance_id 或 run_tag>/segment_<writer_id>_
  <segment_seq>.jsonl`,O_CREAT|O_EXCL 创建;**任何进程绝不 append 已存在文件**——restart/
  轮换一律开新 segment。多进程 worker(exact_parallel_scheduler.py:266-309,campaign=None
  直调)天然各持 writer_id 各写各段,无共享 seq/锁问题。
- **GENESIS 事件**(每 segment 首行):writer 身份(pid/host/run_tag)、campaign_instance_id、
  predecessor 血缘(前一 segment 路径+tail hash;跨 restart 时 predecessor_campaign_instance_id;
  若前段尾部损坏则记损坏偏移+forensic 保留声明)、恢复原因、solver/ortools 版本、seed/workers、
  env manifest 摘要(codex#2 要求的可复现性上下文)。
- seq 单调+prev_event_hash 链均 **per-segment**;审计视图由 reader 沿 GENESIS 血缘拼接。
- 事件通用字段:seq/event/cut_id/semantic_fingerprint/plan digest/payload_digest/
  epoch_instance_id/epoch_semantic_digest/reason_code/时间戳;APPLIED 另携 receipt(D-12)、
  trigger(binding_infeasible|routing_exhausted)、incumbent digest(F7 类 solution 驱动族)、
  ghost anchor。

**D-6 崩溃整性:两故障模型分开说,前缀单调不变量显式化。**(rev2 重写,codex#5+opus F2)

- **进程崩(主模型)**:逐事件整行 write+flush→数据在内核 page cache,进程死不丢;截断只
  发生在 flush 边界后的最后一行。
- **断电(次模型)**:flush 不落盘。加固:①segment 创建后对父目录 fsync(先例
  fsync_directory,exact_campaign.py:1605-1610;**CutManager append 不是 durability 先例**,
  cut_manager.py:569-570 无 flush/fsync——rev2 订正引用);②APPLIED/POISONED 逐事件 fsync,
  且 **fsync 成功是 solve 继续的前置**(失败→D-4 poison+abort);③EPOCH_CLOSED/SEGMENT_SEAL
  终止事件+fsync,区分「正常完整关闭」与「中途崩」;④GENERATED/REJECTED 只 flush,显式
  标注为**断电下 best-effort telemetry,不得用于完备性或否定性证明**(「零 APPLIED」类
  否定断言只能依据 sealed segment)。
- **前缀单调不变量(显式)**:单 segment 单顺序 append 流,fsync 任一事件连带落盘其全部
  前缀;reader 首个 gap(半行/链断/seq 跳变)处截断,之前=干净前缀。未来任何「分流写」
  设计变更都会破坏此不变量,须重审 D-6。
- **reader 三态**:complete(见 SEAL)/truncated(干净前缀+截断点)/corrupt(链断),
  绝不把 truncated/corrupt 当 complete 消费;门 7 的否定性断言仅接受 complete。
  PREPARED 绝不当 APPLIED(§4 门 4)。

**D-7 事件词表**:RFC §2 八词表 + GENESIS/SEGMENT_SEAL/EPOCH_CLOSED/POISONED;F5 记
VALIDATED+SHADOW 变体、legacy 四族 registry 边界拒绝记 REJECTED(stage=registry)——
「无 APPLIED 家族」在 ledger 上可辨认,rollback 演练才有干净证据。

**D-8 F5 不进本批 dedup。** ShadowValidated 无 plan/fingerprint,proof_digest 含
core_minimization 审计计数(pattern_nogood_oracle.py:312-324)违 RFC §5 禁含项;F5 不
apply 不占预算,I-8 动机不成立。F5 语义投影留 F5 转正批。

**D-9 cut_id 不动(批E)。** 墙钟时间戳不进指纹;ledger 事件以 (seq, cut_id,
semantic_fingerprint, payload_digest) 联合定位。确定性化列可选后续(碰 oracle 的批顺带)。

**D-10 去重记账双写。** semantic_duplicate 命中→ledger REJECTED 事件+
`stats["cut_framework_attach_last"]` 新增计数字段(benders_loop.py:8346-8354 形态)。

**D-11 宿主=m5_cell_runner 基座扩展。** harness driver 放 docs/research/ 实验目录
(非 src 非 sealed,CI 不覆盖是接受的——**可测正确性全部落 src fixture 测试,driver 只是
prod-scale 手动跑批壳**,rev2 明确,opus F10);换已证可解配方(fixed+p3+s3)、接 ledger/
dedup telemetry 断言、调高 max_iterations 备 anchor 退役观测。harness 会话写的 ledger
在 gitignored data/cuts/,**非 proof 面、不入证据链**。不新增守卫豁免、不动 lock。

**D-12 APPLIED receipt=编排层 receipt v1(rev2 新增,codex#5)。** 现状:step_8 返回 None
(lifecycle.py:1741-1746)、typed_apply 返回 bool——「master attach receipt」无既有产生点。
本批拍板:**编排层构造 receipt**,字段=plan digest+family+operation+binding 身份(rect
digest/u_var 标识,resolver binding 对象已持有)+apply 前后 coordinate_framework_cut_count
差+apply 返回 True 断言。**诚实标注:它证明「编排层观察到 apply 调用成功+计数推进+绑定
身份」,不是 master 内部约束体 attestation**(后者需改 sealed typed_apply/lifecycle 返回
receipt 对象=另批加固项,登记不做)。(b) 下 ledger 是审计通道,编排层 receipt 与用途匹配;
若未来 ledger 承担任何注入/证据职能,receipt 必须先升级为 master 内部 attestation。

**D-13 family-enable 最小机制(rev2 新增,opus F3)。** 现状:generators 硬调
(benders_loop.py:8236/8245/8254),无 family 开关→门 7「关 family」字面不可测、
enabled_family_manifest_digest 无真来源。拍板:**参数级**(非 env,避开 EXACT_* allowlist/
lock/tests 三同步)——controller 构造参数 `enabled_cut_families`(默认=现行四族全开,生产
行为零变),`_maybe_attach_framework_cuts` 按它跳过对应 generator;epoch_semantic_digest 的
manifest 分量=实际启用集的规范化 digest。harness/fixture 用它做门 7。默认全开+零 env=
certified 行为零改变。

## §2 范围

1. semantic fingerprint 严格相等 dedup(D-2,含 generation 绑定断言+ghost 唯一性测试哨兵)。
2. CutLedger(JSONL segment 协议 D-5/D-6/D-7)+ ModelEpoch 双标识(D-3)+ 编排层接线
   (certified 下路径本就禁用,不碰 certified 行为)。
3. 编排层 receipt v1(D-12)。
4. family-enable 参数(D-13,默认全开零变更)。
5. 宿主 harness 扩展(D-11):fixture 级触发验证落 src 测试;prod-scale 单点与 A/B 归批C。
6. RFC §9 七门在 (b) 语义下的测试映射(§4)。

## §3 不做面

- selector 打分/六维 watcher/family dominance(RFC 自排后置)。
- envelope replay 注入通道与 content-addressed envelope 存储(D-1;后者若未来要 (a) 另批)。
- CutStore/replay.py 双表接通生产;**RFC §4 CutRecordView/消除 is_quarantined 双状态源**
  (rev2 显式,opus F9)——typed cut 已 frozen、ledger 审计-only,该项属 legacy CutStore
  清理,后置。
- resolver 多匹配拒绝(碰 sealed lifecycle.py,D-2 哨兵覆盖当前风险,登记后续加固)。
- master 内部 receipt attestation(D-12 登记)。
- F5 转正面一切;certified 行为一切(attach 仍 unsafe-map 禁用,unchanged)。

## §4 测试义务(RFC §9 七门在 (b) 语义下的映射,rev2 按双审重写)

| RFC §9 门 | 本批形态 | 诚实标注 |
|---|---|---|
| 1 APPLIED→QUARANTINE 禁 publish | 注入式哨兵(批D reachability-sentinel 口径,opus F5):APPLIED 后注入完整性失败→①异常传播中止 solve;②上层即便捕获异常也无可发布结论(断言无 CERTIFIED/candidate 材料产生);③fresh master 上该约束不存在(fresh 重建断言);④ledger POISONED 事件落账 | 冻结 epoch 下自然路径不可达,测的是 fail-closed 完整性,非自然 QUARANTINE |
| 2 ghost condition 错位 fail-closed | 从 `_maybe_attach_framework_cuts` 集成路径驱动(codex 要求,非旁挂单测):错位绑定→CutRejection 分桶+**零 APPLIED 事件**+master 零写 | 复用既有 resolver 红测面,新增 ledger 侧断言 |
| 3 同语义只 attach 一次 | 参数化覆盖 F1/F6/F7:同 controller 两轮同语义(不同 cut_id/iteration)→第二轮 REJECTED(semantic_duplicate)+hit+++master 约束计数不变;**负例=改 capacity/weights/ghost scope**(不得用「只改 region」——proof 级差异不改 lowered 方程,指纹本就该相同,codex#4);**污染负例:首个 cut 被 attach_timing 拒→指纹不入 pool→后续同指纹仍可 attach**;**generation 负例:新 controller/master 不消费旧 pool** | 指纹=lowered-constraint 等价,非 proof 身份 |
| 4 crash 截断不把 PREPARED 当 APPLIED | reader 三态测试:截断/链断/半行→truncated/corrupt,拒绝消费;audit view 重建正确;rollback consumer 对非 complete segment 拒绝否定性结论 | (b) 下无 PREPARED→master 消费者,parser 面为主 |
| 5 restart 全链资格 | **替代门(非 RFC replay 门,显式声明)**:双进程 kill/resume 测试——fresh master/pool 零继承;**预置恶意/伪造 ledger 于 data/cuts/ →对新进程 cut 生成/attach/master 零影响(非消费隔离的结构断言)**;新 APPLIED 全部出自本进程 typed 链;GENESIS predecessor 血缘正确 | RFC 字面 replay 已被 D-1 waiver;此门测的是 (b) 的核心不变量 |
| 6 batch0/C1 cut off/on A/B | 拆两层:批E=fixture 级 off/on 等价断言且**硬断言 generated>0 && applied>0**(防双零空过,codex);harness 扩展就绪。**RFC 门 6 本批不记 PASS,状态=OPEN→批C**(卡点①②) | 不得把 fixture 绿当 prod 层已验(PIC-5 同款纪律) |
| 7 rollback 演练 | 用 D-13:同 state 先跑全开 epoch(阳性:该族 APPLIED>0)→新 controller 关目标族→①fresh master 无该族约束;②**complete** sealed segment 上零该族 APPLIED;③epoch_semantic_digest 的 manifest 分量变化可见;覆盖 compiler 版本回滚变体(fingerprint 的 compiler_version 分量变→旧指纹自然不命中) | 否定性断言仅接受 complete segment(D-6 三态) |

全量:cuts 回归+fast lane+慢 lane(pytest-forked);新 ledger/dedup 测试进 cuts 目录。

## §5 reseal 面(定论式,rev2)

- **碰 benders_loop.py**(dedup pool+ledger 接线+D-13 参数+receipt 构造,全在编排层)=
  v99 floor+JSON sink 双钉+checker 自钉连锁(语义投影剥 source_sha256,纯 sha 钉不触发
  投影常量)。
- **新 ledger 模块(src/cuts/ledger.py 拟)**:audit 通道非 proof 通道→**不入 close-kernel
  floor/sink**;进 mypy strict targets+测试钉。若双审(实现轮)另裁,从其裁。
- **typed_platform.py / lifecycle.py / typed_apply.py:零改动**(receipt 走编排层 D-12,
  ghost 唯一性走测试哨兵 D-2)。
- 测试文件非 sealed。

## §6 规格双审记录(2026-07-12)

- **opus 设计位:AGREE_WITH_AMENDMENTS(0 BLOCK/0 HIGH/4 MEDIUM/6 LOW)**。核心确认:
  D-1 (b)≥(a) soundness、D-2 双重健全(指纹 biconditional 单 epoch 成立+误杀 under-cut
  兜底)、D-4 poison 全覆盖、D-11 不弱化威胁模型、§5「typed_platform/lifecycle 不必碰」
  坐实。10 条修订:F1 跨 restart 审计连续性丢失补认+predecessor 血缘(→D-1/D-5);
  F2 两故障模型+前缀单调不变量(→D-6);F3 family 开关不存在(→D-13);F4 pool INSERT
  时机(→D-2);F5 门1 哨兵口径标注、F6 门5 弱于 RFC 字面标注(→§4);F7 build 点枚举
  订正(→§0);F8 D-4 措辞(→D-4);F9 RFC§4 表态(→§3);F10 harness/src 切分+ledger
  非 proof 面声明(→D-11)。**全数采纳。**
- **codex 第二视角:BLOCK→修订条件全采纳,rev2 后待复核降档**。七组发现:#1 D-1 须按
  实质 waiver 走 owner 批准、更名 fresh-model regeneration/non-consumption isolation、
  不声称 replay 门满足(→D-1,owner 批准点已立);#2「确定性重生成」被 F7 incumbent 反例
  证伪+ledger 补可复现性上下文字段+「格式向前兼容」措辞订正(→D-1/D-5);#3 pool=
  APPLIED-only 集+generation 绑定+from_exact_core 路径订正(→D-2/§0);#4 指纹=lowered
  等价非 proof 身份+F1 region 反例+门3 负例修正+ghost 唯一性哨兵+SHA 措辞(→§0/D-2/§4);
  #5 D-6 断电模型五项加固+CutManager 非先例订正+**receipt 缺口**(→D-6/D-12);#6 七门
  空验证重写(→§4);#7 **单写者/segment 续写协议缺失**(主发现,→D-5 重写)。
  主会话抽查其四条承重断言(step_7 拒绝分支/step_8 返回 None/resolver 首匹配/worker
  campaign=None)全部属实。
- 两审收敛点:pool INSERT 时机、from_exact_core 路径、D-1 治理框架——独立复现,置信度高。

## §7 实现与落地记录(待批准后填)

- 前置:owner 批准 D-1 waiver。
- 实现顺序拟:ledger 模块(纯新文件+自测)→ benders_loop 编排接线(dedup+ledger+D-13+
  receipt,一次 reseal)→ §4 七门测试 → harness 扩展 → 慢 lane+全量 → 实现轮双审
  (设计位 opus+攻击位 opus;codex 复核规格降档)→ reseal 收口。
