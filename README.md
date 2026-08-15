# 《明日方舟：终末地》70×70 基地 certified-exact 最大空矩形求解器

> **本文件是当前状态报告，不是历史 handoff 档案。**
> 核验基线：**2026-08-09**，`HEAD=52d5295`。结论来自 14 路独立精读（约 31 万字）+ 4 路双模型对照核验，
> 承重项均回到源码字节、JSON 字面值、内核日志独立复验。第九节标注了哪些是证实的、哪些是快照说法、哪些未证实。
>
> 权威顺序不变：`PROJECT_LOCK.md` > `data/proof_obligations/` 与 `data/review_gates/` 的机器状态 > 本文件 > 其余文档。
> 本文件与 lock 或 gate JSON 冲突时，**以 lock 和 gate JSON 为准**。

---

## 一、这个项目真正硬核的地方不是求解器

表面任务：在 70×70 单基地（唯一 active = `valley4_protocol_core`）里放下 266 个 mandatory 设施实例，
求最大空矩形，目标 `max_lex(area, min_side)`——先最大化面积，再最大化最短边。

但项目 80% 的工程量不在求解，而在**证明纪律**：如何保证一个声称 `CERTIFIED` 的结果确实被证明过。
为此建立的机制包括 96 条 Accepted Invariants、84 个编号契约族（`F-CAM-PR1-*`、`F-BIND-R*`、`F-GM-*`、
`F-PRE-R*`…）、producer/supervisor/publisher 三方分权、5 件字节级冻结工件、124 个 V99 源码 SHA pin、
67 个 proof-bearing sink pin、20 道 preflight gate。

一句刻在 `PROJECT_LOCK.md` 和 `CLAUDE.md` 里的话概括了全部气质：**绝不能从绿灯推导关门**。
测试全过、checker PASS、`supervisor_seal()` 方法存在——都只说明登记结构没漂移，不构成 soundness 证明，
不构成 owner 关门动作。

与此配套的一条边界必须写在最显眼处：**P1.2 的 clean-review 计数是
`owner-maintained outside the repo`**（gate 字段 `owner_clean_count_status = "maintained_outside_repo"`、
`repo_derives_clean_count_from_receipts = false`）。仓库里的 receipt 是 `informational_record_only`，
`can_open_p1_3b: false`——**不要试图从 receipt、测试绿灯、checker PASS 或内部 seal 推导关门进度**，
唯一入口权威是 owner 的显式 `owner_manual_decision`。

## 二、目标的精确边界

- **`min_side >= 6` 是候选 admissibility 规则，不是目标 tie-break**；权威在
  `rules/canonical_rules.json::globals.empty_rectangle.min_side_admissibility`，不是源码常量。
- **空矩形语义**（owner 2026-08-05 裁决，已写进 canonical `emptiness = "no_occupant_of_any_kind"`）：
  矩形内不得有任何占用物——设施本体、供电桩、传送带、跨接件都不行。route-cell 严格空地被挂进谓词 5。
- **exact 模式没有「50 供电桩 + 10 协议箱」硬 cap**，该数字已于 2026-06-04 降级为 exploratory 示意。
- 其余 6 个 IndustrialPlanner 基地是 `future_scope`（2026-04-14 收窄），结论不得外推。

---

## 三、推进过程编年史

### 3.1 起点：至迟 2026-03-16，真实开工日未证实

`CHANGELOG.md:184` 最早日期块（2026-03-16）写的是 "Built out the current exact-safe local-capacity path,
frontier guidance, and routing-core shrink work **that made the certified path viable at scale**"——
它描述的已是一条相当成熟的路径，说明 CP-SAT 骨架和 certified/exploratory 分流在此之前就存在。

`specs/04` 里有个 `§4.8 DEPRECATED (2026-03-12)` 标签，但它是后来回溯写入的单一来源，不足以把起点提前。
**项目真实创建日期在本仓库内无法证实**——git 历史已于 2026-08-09 空白重建，只剩 3 个提交。

**同样未证实的还有第一次技术选型的理由**：为什么一开始选 OR-Tools CP-SAT 而不是 Gurobi/SCIP/其他，
全仓找不到任何文档记载。（有记载的是**第二次**选型，见 §3.3）

### 3.2 2026-03～04：基础设施与交付面成型

3 月中下旬密集建设：coordinate master 稳定化、campaign persistence/resume、几何 power coverage、
local-capacity oracle、并行 scheduler、canonical preprocess、interchange/adapters、Endfield 生态摄取、
frontier probe。4 月转向交付面：release builder、viewer/frontdoor、checked artifact inventory。
**2026-04-14 active scope 收窄为单一基地**——这条边界至今有效。

（本段全部是 CHANGELOG 的历史快照说法，写于 2026-08-02，不是同期机器日志。）

### 3.3 2026-05：范式大屠杀 —— 项目最惨烈也最有价值的一个月

这个月的主题是**系统性证伪**。`docs/research/` 最早一批日期目录出现在 05-16，随后 27 条技术路线（lever）
被逐条判死。几条代表性死因，每条死法都不一样：

| 路线 | 实测数据 | 死因性质 |
|---|---|---|
| v8 anchor slicing | build wall −92% 真实，但单 anchor 仍 307.76s UNKNOWN（5.5M branches） | **算法错估**：只量了 build 时间，没量 solve 质量 |
| v10 witness preflight | 算法本身 sound，但社区蓝图实缺 41 个 mandatory 设施，compatible anchor 数 = **0** | **前提错估** |
| L14 weighted occupancy | interior anchor 场景 LP 松弛 = 1.000 exact | **数学能力上限**，不是可修的 bug |
| Path 15 PGW-UB | blocked_owner 276-327（target ≤120），top5_blocker_coverage 0.044-0.053（target ≥0.55，**差 10 倍**） | routing residual 全域均匀分布，LNS 邻域修复从根上不成立 |
| Path 16 GOC-C2 | 30 分钟无输出，**RSS 25GB**（target 12GB），变量 ~1.5M（原估 180K，失真 8 倍） | 数学 sound 但与生产资源约束不兼容 |
| Path 17 augmented master | 约束 2.68M（cap 650K），RSS 32.3GB，600s UNKNOWN；根因精确到 280,444 pose × 8.4 ports = 2.36M 条 OnlyEnforceIf | 真实 10-commodity 场景需 ~24M 约束，不可能 |
| B1 pose-bool master | Phase 0 实测 53s OPTIMAL（vs coordinate-based 30 分钟 UNKNOWN，快 34 倍），但 routing precheck `front_blocked`，~500-610 端口系统性阻塞 | master 不知端口方向，Phase 6.2 四种 form 全死 |
| PCR-CUT | Phase 0-4 GO，Phase 5 **0/8 CERTIFIED、7/8 UNPROVEN** | necessary but insufficient |

一手实测数字见 `paths/15_positive_global_witness/phase0_verdict.md`、
`paths/16_global_optional_owner_core/phase0_verdict.md`、`paths/17_candidate_d_commodity_flow/phase3_verdict.md`。

**2026-05-21：第二次技术选型。** 用户 ad-hoc 问 GPT，三份独立回复形成共同 thesis（内部代号
"GPT v13 cut language thesis"），核心论点是**「换 cut 语言不是换 solver」**——明确排除了换用
Choco/Gecode/Z3/clingo/Gurobi/SCIP、把全量 routing 塞进 master、从零写通用 solver 这三类方案。
自建对象是专用 cut/proof 工具链（PoseStore/SearchState/OracleRunner/CutFactory/ProofLog），CP-SAT 本身保留。
考据见 `docs/research/history_toolchain_origin_20260709/`。

值得注意的是 owner 拍板的形式：考古文档明确写「文件中未见一句『用户说自建工具链』的直引」，
可见的拍板是 **phase-gate 式的**——Phase 0 close 后决定是否进入 Phase 1 编码。

**2026-05-22：B Design v2 Phase 0 close**，冻结 cut object、group-orbit、9 族 lifecycle、state schema，
PoC 14/14。`src/cuts/` 的前身当日落地（90/90 test pass）。

### 3.4 2026-06：审查链，以及「评审基础设施本身有 bug」

这个月是 F2-F9 各族的多轮外部交叉审查（Gemini 1-5 轮、GPT Pro 审计）。编号体系在这里成型——
**v2→v22 是评审包序号，v28/v30/v31/v37/v46/v99 是评审事件锚点**，两者不是同一条轴，也不构成连续日历。

- **06-04（v28）**：外审触发两项长期修正——F9 tight-K quarantine；specs 里 `I_opt=60`/总集 326
  从 exact 固定枚举**降级为 exploratory 示意**。
- **06-07（v31）postmortem 判 `NOT CLEAN`**：v29-v31 的 sibling bypass 被汇总为 proof-obligation 问题。
- **06-08（v46）**：评审协议开始明确区分**算法 soundness finding** 与 **review-infrastructure finding**
  ——即「评审工具自己的 bug」被单列一类。
- **06-16**：certified source digest 扩展，旧 checkpoint 因 source-tree 摘要变化整体失效。
- **06-17（V99）**：close-kernel sealing 落地。文档明写它**不是 theorem、也不会自动关闭 P1.2**，
  当时 P1.2 仍 blocked。
- **06-21**：owner 澄清 `machine_min_clearance_cells` —— 它管的是 active port/front 格必须可放带，
  **不要求机身之间留空隙，贴身合法**。
- **06-26**：PR1 producer/supervisor/publisher 三分权成型。

`P1_2_TECHNICAL_CLOSE_PACKET/` 记录了一个极具代表性的洞：M8 negative control 发现，
**删掉 `_check_close_kernel_contract(manifest)` 这一调用后，gate 和测试仍然全绿**——checker 当时不检查
自己有没有被调用。最终加了 "checker self-binding guard" 才修复。这是「checker 自证不闭合」的教科书案例。

### 3.5 2026-07 上旬：P1.2 首次关闭、Stage B 落地

- **07-04**：独立 supervisor seal 入口 `scripts/run_supervisor_seal.py` 落地。
- **07-07**：**owner 首次执行 `owner_manual_decision`——P1.2 CLOSED、P1.3 entry allowed**。
  同批裁定 power coverage 语义为「塔覆盖矩形与受电 footprint 至少一格相交」（不是包含）。
- **07-08**：F8 因**游戏规则前提为假**整族退役（`validator_version="retired-false-premise"`）；
  `EXACT_CUT_FRAMEWORK_ATTACH` 被归类为 certified unsafe。
- **07-09**：C1 master 完成 `OPTIMAL @ 541.3s`——**这是 master 解，不是六谓词终端 CERTIFIED**。
- **07-10**：attach power-on 对照实验，10K cut、total wall +6.9%，限定口径判 GO（文档明确仅 synthetic/one-rect）。
- **07-11/12**：Stage B v3 定稿，B0→B5b 落地：F1/F6/F7 走 typed lowering 全链，F5 独立 verifier 但
  shadow-only。**B6 owner promotion 未做**——该状态保持至今。

### 3.6 2026-07 中下旬：front offset 事故 —— 全项目最重要的一次翻车

**07-18，P0 事故定谳**：stored port 坐标**本身**就是带子/front 格，而旧代码又做了一次 `+dir` 去查体外
第二格。后果是双向的——**既产生假 INFEASIBLE，也产生假放行**。

修复规模：扫描 599,384 条 port 记录；候选池 66,405 → 补回 2,064 个墙距合法 pose → 68,469 →
批3+5 中间池 81,797 → owner 第四笔「未激活口可朝外/被堵」域修正后，形成**现行 82,829 pose**
（`54,467,709` 字节，`f05b1291…d280d3`）。

这次事故的余波是：**07-18 之前所有涉及 front 语义的运行数值全部作废**，包括此前「全部杠杆穷尽、
遇到结构墙」的总判断被撤回。

同期另一条线在建**研究上界账本**：

| 日期 | 上界 | 授权源 |
|---|---|---|
| 07-20 | `(1326,34)` → 同日收紧 `(1190,34)`，给出 `P≥9` | cleanroom R1/R3 判决 |
| 07-23 | **`U=(1188,22)`**、`L=absent` | proof-bearing PB/RoundingSat/VeriPB 链 |
| 07-27 | **`U=(1188,18)`**、`L=absent`，`production_certified=false` | SMM4 fresh-authority root + detached receipt + immutable closeout |

- **07-28/29**：W0 D6 v1 root closure 缺陷被发现，v2/v3 协议修复后两个 closed-root 得到
  replay-accepted INFEASIBLE。效力**仅关闭 exact local antecedent**，不改 U/L、不改 cut、不改 production authority。
- **07-30**：AB16 多轮 admission/路径/资源协议失败关闭，organic arms 仍 **0/16**。

### 3.7 2026-08：严格语义、P1.2 重开重关、reseal、git 重建

| 日期 | 事件 |
|---|---|
| 08-01 | 自治期 66 个历史提交经审计合并，另一个未过门禁的大提交被精确 revert |
| 08-02 | AB16 减法/返工批完成；**CHANGELOG 在此停更** |
| 08-03 | AB16 campaign 收官：21 attempts、16 credible，**16/16 全部 `BUDGET_CENSORED_UNKNOWN` + `ORGANIC_NONACTIVATION`，G/C/A = 0/0/0**；同日发现 W0 的 45 项测试因错误外部路径与 phantom hash **实际被 skip** |
| 08-04 | W0 fix-and-rerun 收官为 `BUDGET_CENSORED`；strict supply 2,544 对 demand 3,325 |
| 08-05 | **M5 现行池复验**：一次约 9 分钟 OOM；另一次 master 有 incumbent，但 binding↔routing 枚举 **≥33h** 后由 owner 停机，**认证级存在性回到 OPEN** |
| 08-05 | **owner 空矩形语义裁决**（采甲案）；strict-ghost 修复批落地；**旧 P1.2 close 因语义/source hash 改变而重开** |
| 08-06 | 三轮复审 + seal batch 后，**owner 以 `owner-p1-2-reclose-20260806` 重新关闭 P1.2**，supersede 07-07 那次 |
| 08-06 | band22 R2 RAB 阶梯跑完：rung1 `INTAKE_ACCEPTED`、rung2 `MASTER_FEASIBLE`、rung3 约 20,400s 后 `UNKNOWN_CENSORED` |
| 08-07 | canonical axiom kernel 进入 freeze ritual，初次 gate 红、r2 绿 |
| 08-08 | canonical reseal 完成，`c3fc3a34…542c0` |
| 08-09 | **git 仓库空白重建**，只剩 3 个提交；原 820 commit + 5 worktree 分支备份在 `/home/zhuran24/zmd-pj-cc-backup-20260809/` |

**P1.2 的完整身份必须写成三段**：07-07 首次 close → 08-05 因严格空地语义与 source 变更而重开 →
08-06 superseding re-close。任何只说其中一段的表述都是错的。

---

## 四、架构与证明纪律（已核验属实）

### 4.1 三方分权在代码里是结构性拒绝，不是注释约定

```
main.py → run_solve() → src/search/outer_search.py
  PRODUCER   outer_search.py:1973 唯一成功返回 = CANDIDATE_PROPOSED
             exact_campaign.py:3528 无条件 raise RuntimeError
             ("CERTIFIED campaign stop must be minted by supervisor_seal")
  SUPERVISOR scripts/run_supervisor_seal.py:131 是唯一 production caller
             从磁盘读提案，写前写后各验一次
  PUBLISHER  publish_verified_certified_delivery_surface() 单事务派生三件交付物
```

`main.py:328` 那个 `if status == "CERTIFIED"` 分支是**死代码**——`run_outer_search` 永不返回该值。

### 4.2 flow 的诊断锁在代码里可验

`if flow_status ==` 在 `benders_loop.py` 只有两处（`:5468`/`:5472`），**都在 `_run_exploratory` 内**；
`_run_certified_exact` 里只做 `diagnostic_flow_status = flow_status`，此后该变量只进 telemetry，
**从不进 `if`**。契约测试 monkeypatch flow→INFEASIBLE 后仍断言 CERTIFIED。

### 4.3 cut framework 当前状态（读 `src/cuts/typed_platform.py` registry 字面值）

| 族 | stage | execution_path | 状态 |
|---|---|---|---|
| F1 region_capacity | COMPILABLE | TYPED | typed lowering 全链 |
| F6 shape_packing_hall | COMPILABLE | TYPED | 全链（requires_ghost_bound） |
| F7 power_hitting_set | COMPILABLE | TYPED | 全链（requires_ghost_bound） |
| F5 pattern_nogood | VALIDATED | TYPED | **shadow-only**，`compiler_version=None` |
| F2/F3/F4/F9 | VALIDATED | LEGACY_DIAGNOSTIC | registry 边界即拒 |
| F8 power_grid_reach | **RETIRED** | — | `retired-false-premise` |

`EXACT_CUT_FRAMEWORK_ATTACH` 未设置时取空串，落在 FALSE 集合 → **默认 OFF**；且被登记进
`_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES`，certified 下即使显式打开也 fail-closed。
**B6 owner promotion 未做。**

### 4.4 pin 闭包在 HEAD 上完全自洽

- 5 件冻结工件 **5/5 齐全、5/5 SHA256 匹配**（含 `candidate_placements.json` 的 `54,467,709` 字节；
  实测 `pose_id` 计数 **82,829**，与 lock 记录精确吻合）
- 67 个 proof-bearing sink pin：**零 drift、零 missing**
- 124 个 V99 源码 pin：**124/124 相同**
- 6 个核心权威文件 `git show HEAD:` 与磁盘**逐字节一致**

---

## 五、当前现状：基础设施齐备，但一次都没跑通过

### 5.1 从未产出过任何 CERTIFIED（双模型独立核验一致）

- `data/blueprints/` **整个目录不存在**；`final_solution.json`、`optimal_blueprint.json` 全仓零命中
- `data/checkpoints/` 只有 0 字节的 `benders_cuts.jsonl` 和一份 telemetry，**`exact_campaign_state.json` 不存在**
- `run_supervisor_seal.py` 的前置条件检查在当前树上**必然失败**——它至今**从未有过合法输入**。
  不是「没人跑」，是结构上无输入
- 唯一 campaign 遗留物是 2026-07-10 的墓碑：`final_status="UNKNOWN"`、
  `reason="campaign_time_budget_exhausted"`、**`best_certified_result: null`**，且跑在两代之前的工件
  `a914ba63…` 上。那次实际只打了 `70x19`/`19x70` 两个形状，**3/3 全部 master INFEASIBLE**

### 5.2 核心数字：「面积求到多大」这个问题当前没有答案

| 量 | 值 |
|---|---|
| **下界 L（六谓词）** | **absent** —— 没有任何被账本接受的可行布局 |
| **上界 U（六谓词）** | **`(1188, 18)`**，conditional research upper ledger |
| **gap** | **无法计算**（L 缺席，且目标是 lex tuple 不是标量） |

`(1188,18)` 是 lex 分数不是布局实例；若真达到，整数宽高只能是 `18×66` 或 `66×18`，
但**没有证明这两个方向可行**。

唯一试图立下界的实物是 band22 见证线：目标 `w=7,h=6,area=42,min_side=6`。结果是
`layout_structure_check.ok=true`、master `OPTIMAL`（1.137s、6104 fixed literals），但
`binding_status=ALT_CAP_REACHED`、`routing_status=PRECHECK_FRONT_BLOCKED`，**终态 `UNKNOWN_CENSORED`**。
它不是 incumbent，**不得进入 L**。

**真墙是 binding↔routing 无帽枚举**：M5 复验 CPU `1d 8h 46min`、内存峰值 29.4G、全程停在 iteration 1，
≥33h censored；band22 rung-3 在 20,400s 处 censored。M5 的三条入账结论：① 62G 修订条款对现行池不再成立；
② master 层供电可行候选布局**存在**；③ **认证枚举墙从 7 月的 649s 深化到 ≥33h，存在性问题回到 OPEN**。

### 5.3 门禁：最后一次落盘绿灯是 08-08，当前 HEAD 未证实

- 最近落盘的标准 `--full`：`.artifacts/memsys_meeting_20260808/preflight_b3_rerun.log`，**08-08 04:11**，
  `21 passed`、`7265 passed/125 skipped`、exit=0
- 最近落盘的标准 `--slow-tests`：`.artifacts/canonical_reseal_20260808/slow_lane.log`，
  `33 passed/7358 deselected`，exit=0
- **2026-08-09 HEAD 的门禁结果只有 commit message 自述**（`20 passed`、`7306 passed`），
  **无归档日志、无 slow lane 记录**

按项目自己的纪律（改 `preflight_gate.py` 这类 V99 钉死面后必须另跑 `--slow-tests`），这条只能记作**未封印**。

一个易被忽略的限定：08-07 那次双绿的 `[memory]` lane 真跑了 265 个 `cc_memory/` 测试，而该目录**现已整体
移除**（`MEMORY_TEST_DIRS = ()`）——**它测的检查面和今天的不是同一套**。

---

## 六、当前活跃工作线

| 工作线 | 是什么 | 状态 |
|---|---|---|
| **band22** | 唯一试图立下界的见证线，7×6 严格空矩形 | rung3 `UNKNOWN_CENSORED`；且跑在已被 08-07 reseal 超越的旧 canonical 上 |
| **AB16** | 16 条 non-certified cut arm 的可信度实验 | 08-03 按 owner 停止令收官，**organic arms 0/16**，全部 authority false |
| **W0-D6** | power cycle domino 局部反证协议 | 修复后两个 closed-root replay-accepted；仅关 exact local antecedent |
| **mixflow** | demix ban / u01 | 相关提交在 git 重建中，原库备份在归档里 |
| **M5** | 现行池认证级存在性复验 | ≥33h censored，**存在性 OPEN** |
| **P2.0** | 第七谓词（吞吐守恒）另一本账：`A≤1167`、`L_route≥305` | **明令不得与六谓词 `U=(1188,18)` 混写** |
| **certside** | P3.0c 轴 B，独立 OPB→RoundingSat→VeriPB→**CakePB** 四层异构复验链 | **roadmap 说「待开工」是过时的**——实际 07-18 已达 30/30 结构验收全绿；纯 diagnostic，不进 TCB |

---

## 七、债务与风险（按严重度）

1. **P1.2 re-close 的外审证据不在版本库里**。gate JSON 是 tracked 的，但它引用的
   `.artifacts/ghost_strict_fix_20260805/round3_verdicts_20260806/` 等路径 `git ls-files` 返回 **0**。
   一次干净 clone 拿不到 P1.2 关门的证据。
2. **`CLAUDE.md` 自身是未跟踪文件**，且 mtime 晚于 HEAD。这份自称「OVERRIDE 一切」的最高优先级指令文件，
   正处在它自己 §7 警告的「共享工作区里 untracked 文件会消失」状态。（是刻意还是遗漏——**未证实**）
3. **当前 HEAD 门禁未封印**，尤其 slow soundness lane 是盲区。
4. **文档滞后于机器状态**：`docs/项目说明/06_current_status.md` 仍把当前关门归给 07-07，而 gate JSON
   是 08-06。`PROJECT_LOCK.md` 头部 `Updated: 2026-08-03` 也已过时（正文含 08-05 裁决、08-06 Erratum）。
   `27_status_dashboard.md` 自己挂了这条欠账并写明「判断阶段状态只读 gate JSON」。
5. **退役残留**：`.github/` 已删但 `specs/23`、`code_assets.json` 仍登记不存在的 workflows；
   `devtools/memory_*.py` 默认路径仍指向已移除的仓内 `cc_memory/`。
6. **旧 commit hash 全部失去可验证性**。文档里大量历史 hash 只能作为历史文本标识，不能再 `git show` 复核。

---

## 八、快速上手

```bash
# 解释器：必须用 .venv/bin/python（系统 python 没有 ortools/mypy/ruff）
.venv/bin/python scripts/preflight_gate.py --full        # 唯一权威验收面
.venv/bin/python scripts/preflight_gate.py --slow-tests   # 改认证核心后必跑

.venv/bin/python main.py --mode certified_exact --campaign-hours 8   # 只会停在 CANDIDATE_PROPOSED
.venv/bin/python scripts/run_supervisor_seal.py                       # 唯一 durable CERTIFIED mint 入口

# 恢复外部大工件（轻量副本里可能缺失）
.venv/bin/python scripts/check_external_artifacts.py --require candidate_placements
```

日常约束、坑册与 SOP 见 `CLAUDE.md`；排期与 owner 拍板见 `docs/项目说明/00_master_roadmap.md`；
坐标速查见 `docs/项目说明/27_status_dashboard.md`；名词消歧见 `docs/项目说明/21_glossary.md`。

---

## 九、诚实边界

**已证实**（回到字节/源码/内核日志）：三方分权的结构性拒绝、6 谓词落点、cut registry 全表、
attach 默认值、5 件冻结工件 hash、67+124 个 pin、gate JSON 字面值、`L=absent`/`U=(1188,18)`、
从未产出 CERTIFIED、`.artifacts` 的 tracked/untracked 边界。

**属于快照说法**：2026-03～04 的全部建设记录（出自写到 08-02 的 CHANGELOG）、05 月各 lever 的性能数字
（出自各研究包自述）、08-07/08 的门禁数字（那批日志的检查面已变）。

**未证实**（不得填补）：项目真实开工日；第一次为何选 CP-SAT；v2→v22 各版精确日历；
B Design Phase 0 是 22 轮还是 23 轮；`(1188,18)` 的 attainability；当前 HEAD 门禁实况；
`src/runtime/`、`src/preprocess/`、`src/placement/` 里 13 个文件的具体职责（只做到文件名清单级）；
`CLAUDE.md` 未被 track 是否刻意。

---

**一句话现状**：认证基础设施、冻结输入、分权机制、pin 闭包全部齐备且自洽，P1.2 已由 owner 于
2026-08-06 关闭、P1.3 入口已开；但真实 70×70 求解**从未产出过 durable CERTIFIED**，也**尚无任何
被账本接受的可行空矩形下界**——`L=absent` 一天没变过，真正的墙是 binding↔routing 无帽枚举
（≥33h 无终态）。
