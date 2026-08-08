# 27 — 现状仪表盘

> **本页为无时态文档**：全篇现在时、就地更新，不做增量追加。历史考古走 `git log` / `git blame` 与台账 `docs/项目说明/00_master_roadmap.md` §0a。
> **更新责任**：凡改动本页所记状态的批，必须同批更新对应行（比照 reseal pathspec 全集纪律）。
> **本页零权威**：每行只给坐标与指针。与「权威所在」列的文件冲突时，一律以那个文件为准，并回来修这里。
> 所有路径相对仓库根 `/home/zhuran24/zmd-pj`。带【待核】的断言未经本页作者亲手验证。

---

## 0. 权威分层（先认这张表，再看下面任何一行）

| 层 | 权威物 | 管什么 |
|---|---|---|
| 1 | `PROJECT_LOCK.md` | release 边界、`F-*`/`PCR-*`/`CUT-*` fail-closed 条款 |
| 1' | `docs/项目说明/01_overview.md` §1.1 / §1.2 | **6 谓词外延与 `CERTIFIED` 命题本身**——`PROJECT_LOCK.md` §1A 开篇自认从属于 `01_overview` 的谓词外延，冲突时以它为准 |
| 2 | `rules/canonical_rules.json` | 游戏语义裁决条款、admissibility、`semantics.axiom_kernel`（冻结件） |
| 3 | `data/review_gates/phase_1_2_spike_close.json` | 阶段手动门开关（owner-only） |
| 4 | `docs/项目说明/06_current_status.md` | 当前实现状态 |
| 5 | `docs/项目说明/00_master_roadmap.md` | 总图 / 排期 / owner 拍板台账 |
| — | 本页 | 只总结、只指路 |

---

## 1. 阶段与门

| 项 | 现状 | 权威所在 |
|---|---|---|
| P1.2 spike close 手动门 | `closed_manual_owner_decision`；关门是 owner 真实手动输入，不是任何绿灯推导出来的 | `data/review_gates/phase_1_2_spike_close.json`（唯一权威。决定 id、时间、supersede 关系、`informational_history` 全在文件里，本页刻意不复刻） |
| 当前阶段 | P1.3 production master integration（机器兼容 id `p1_3b`），`next_phase_entry.allowed=true` | 同上 `next_phase_entry` |
| clean-review 计数 | 保存在**仓库外**，仓库刻意不推导；审查收据只是 `informational_record_only`，不能换 clean 学分、不能开阶段门 | 同上 `manual_review_standard` / `receipt_policy` |
| release 边界 | fail-closed 条款集不变 | `PROJECT_LOCK.md` |
| 认证发布链形状 | 跑 `main.py` 只能到 `CANDIDATE_PROPOSED`；durable `CERTIFIED` 唯一 mint 点是 `ExactCampaign.supervisor_seal()`，生产入口是独立命令 `scripts/run_supervisor_seal.py`（从已提交 proposal marker 驱动）；唯一公开发布器是 `publish_verified_certified_delivery_surface()` | `CLAUDE.md` 大图 §3；`scripts/run_supervisor_seal.py` |
| 认证证的是什么 | 6 个 gating 谓词 + `max_lex(area, min_side)` lex 最优；吞吐 / 带宽 / 离散容量流明确 OUT-OF-SCOPE | 谓词外延见 `docs/项目说明/01_overview.md` §1.1 / §1.2；scope 排除见 `PROJECT_LOCK.md` §1A B 块（B-1/B-3/B-4） |

⚠ 仓内三处对 P1.2 关门的记述停在**上一次**关门，与 gate JSON 现值不一致 —— 见 §9 欠账 A1。**判断阶段状态只读 gate JSON。**

---

## 2. cut 框架 family 现状

| family | 状态 |
|---|---|
| F1 / F6 / F7 | **typed**（COMPILABLE）。唯一写 master 通路 = typed registry → resolver（`ModelScopeBinding` 唯一构造链）→ `step_8_apply_to_master` → `typed_apply` |
| F5 | **shadow-only**（`compiler=None`），只产 `ShadowValidated`，结构上不可能改 master；真 adapter 因 frozen tuple/list 形态差异在独立 verifier 前 fail-closed，真路径由哨兵测试钉死 |
| F2 / F3 / F4 / F9 | **LEGACY_DIAGNOSTIC**，在 typed 单入口的 registry 边界即拒绝（不是 step_8 `NotImplementedError` fallback——那机制早已退役） |
| F8 | retired |
| attach 开关 | `EXACT_CUT_FRAMEWORK_ATTACH` 在 certified unsafe-map 内、default-off；certified 路径双重禁用 |
| 剩余开放项 | **B6 owner 手动门** + **`PROJECT_LOCK.md` 列举的生产层前置**（PIC-4/PIC-5 的 production-campaign 层等；**清单不止这两项，且以 `PROJECT_LOCK.md:700` 那条 bullet 为准**，本页刻意不复刻——复刻就是第二真相源。口径分歧见 §8 #9 行）+ F5 转正批（F5 修复不是 flip 的前置） |

权威：`PROJECT_LOCK.md` + `CLAUDE.md` 大图 §2；卡层当前态 `cc_memory_vnext/cards/cut-framework-stage-b-current-20260712.md`。

**B6 的前置数据要连着前提读**：cap 口径下 binding 恒 `ALT_CAP→UNKNOWN`，`binding_infeasible` 结构上到不了，所以有机激活恒为零；**零激活 ≠ cut 无用**，它是口径的结构后果。出处：文件记忆卡 `cut-trigger-never-organic-mechanism`。

---

## 3. 钳口（研究双账）

| 边 | 值 | 引用时必须带的前提 |
|---|---|---|
| 上界 U | `(1188, 18)`，**conditional** | 授权源只有 SMM4 最终 detached receipt 与 immutable closeout（两者 `upper_bound_update_authorized=true`）；内部 formal receipt 即使 `VERIFIED`/UNSAT 也**不是**账本授权源。它只更新 research upper ledger，**不建立** `(1188,18)` attainability、全局最优、整例不可行、任何下界、production `CERTIFIED` |
| 下界 L | **absent** | W2b 没有通过其 HEAD/input-pinned 验收链的 content-addressed layout；**band22 三见证（R1/R2/R3）真死**——其路网依赖「分流器筛货 / 机器挑货」假语义，在门口混流的修正语义下三份独立设计全绕不开门口混流（终裁原话，见下方权威行），④路登记线已关闭 |

- 权威：`docs/项目说明/06_current_status.md`「当前结论摘要」首两条；U 的条件文本在 `docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md`，本页不复刻。band22 终态见 `.artifacts/band22_registration_20260805/coupling_verdict_20260806/REVERDICT_A_REVISED_20260806.md`。
- **真墙 = binding↔routing 枚举循环**（不是 master 求不动）。出处：文件记忆卡 `first-certified-reduces-to-4-small-instances`。
- 双钳不受 front 排他终裁影响：逐证书作用域盘点确认在案证书（PB-03 VeriPB、(1190,34)+P≥9、SMM4 A004、W0 各条）**全部不依赖 routing 模型约束**。出处：`.artifacts/band22_registration_20260805/coupling_verdict_20260806/CERT_SCOPE_AUDIT.md`。

**另一本账，别和上表混**：P2.0（带吞吐）语义下的 research upper ledger 为 **A ≤ 1167 无条件 / A ≤ 1015 单层【条件·待 OB6】**，`P_min = 9`。它是 `OPT_P2.0` 的界，**推不出六谓词最优值的任何变化**（报告自身记录了这条过推被驳回）。权威：`docs/research/p2_0_area_bound_20260806/AREA_BOUND_THEOREM_REPORT.md`。

---

## 4. 供电可行布局存在性与资源条款

| 项 | 现状 |
|---|---|
| 供电可行布局存在性 | **OPEN**。现行池 + front 修正语义下：master 在预算内找到可行候选布局，但 binding↔routing 无帽枚举 **≥33h 无终态**，owner 判「有限时间内跑不通」停机，枚举 `censored@33h`。**master 可行 ≠ 认证级存在**（binding/routing 门未过） |
| 旧「已关闭」结论 | 那次 `OPTIMAL@649.1s` 跑于 **front 错位语义 + 旧候选池**，引用必须带「front 修正前口径」条件 |
| 生产内存条款（1F） | **62G 修订条款对现行池失效**：原公式在 42G/20G cgroup 下 9min OOM（池扩约 18% 后内存包络越界）。条款需随池版本重标定 —— 欠账 A4 |
| 长跑铁律（不变） | prod-scale master solve **一次只跑一个**（本机 47.7GB，双并发必 OOM）；内存采样 ≤1s 间隔并读 `VmHWM`/`VmSwap`（30s 采样会把 60G 尖峰看成「温和」） |

权威：`cc_memory_vnext/cards/p1-3-batch1-m5-current-20260805.md`（单层现态卡）；跑批记录在 `.artifacts/m5_revalidation_20260803/` 下（NOTES.md 全程记录；`.artifacts/` 是未跟踪的只读历史证据根，lightweight checkout 里可能不在）。

---

## 5. 冻结工件与 freeze-ritual

- **清单与 pin 的运行时权威**：`scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS` / `EXTERNAL_FROZEN_ARTIFACTS`；runtime 侧另有 `src/search/certified_artifact_contract.py` 的源码常量。判据以这两处为准。
- **识别用短标签**（只为一眼认出"是不是同一代"，**不是校验值**；全值、字节数与拒绝判据以上两处为准）：`canonical_rules.json` = `c3fc3a34…` / `preprocess_plan.json` = `5c669c4f…` / `mandatory_exact_instances.json` = `545b98c2…` / `generic_io_requirements.json` = `ad5125b5…` / `candidate_placements.json` = `f05b1291…`。前四个是仓内跟踪件，本页作者已逐个 `sha256` 核过与 `preflight_gate.py` 常量一致；第五个是外部大工件，lightweight checkout 允许缺失，短标签抄自 `EXTERNAL_FROZEN_ARTIFACTS`。
- `candidate_placements.json` 缺失时 certified 跑之前必须恢复并验字节（`scripts/check_external_artifacts.py` / `scripts/restore_external_artifacts.py`）。缺它还会让部分测试在 fixture 阶段硬失败而非 skip。
- 改任一冻结件 = **freeze-ritual**（更新 pin → 重生成依赖产物 → 重跑 gate）；改 close-kernel sealed 文件还要走完整 reseal 连锁，**checker 自钉最后**。`PROJECT_LOCK.md` 自身另有 6+1 处 pin 继承链（3 测试 + 3 个 D6 研究脚本 + antecedent 重算），出处：文件记忆卡 `project-lock-sha-succession-chain`。操作步骤见 `docs/项目说明/28_pitfalls_and_sop.md` SOP-1 / SOP-2。
- superseded 的历史 hash 链必须被 `artifact_hash_mismatch` **拒绝**，绝不"好心"更新 expected hash。清单在 `CLAUDE.md` 冻结件节。

---

## 6. 规则语义现状（一行指路）

- 游戏规则的现行理解归 `docs/项目说明/26_rules_handbook.md`；条款权威是 `rules/canonical_rules.json`，卡与研究文书只是推导史。
- 公理系已入 canonical：`semantics.axiom_kernel`（`axioms` 11 条 + `scope_premises` + `ruling_level_inputs` + `model_stricter_faces` + `model_stricter_faces_usage_rule` + `model_stricter_faces_completeness`）。
- **完整性欠账的唯一登记处 = `semantics.axiom_kernel.model_stricter_faces`**：登记"模型比裁决语义严"的各面，按一等审计面对待。理由是双向保真公理——对全局最优证书而言，过严就是假证书，而过严限制**永不自曝报警**。在册面会随放开批变动，**读原键、不读任何转述**。同键旁的 `_usage_rule` 规定在册面**只能描述当前受限模型、不得当游戏语义前提**（依赖它的 current-model theorem 必须点名依赖），`_completeness` 规定本台账必须穷尽、**不在册 ≠ 等价**。
- 箱的 fill-first 明文与单槽容量参数**已入 canonical**（`protocol_storage_box_wireless.slot_count_clause.cache_parameters`）；箱的 class 措辞改判也已落地，但**落法是实例级 discharge 注**（写在 `mixed_commodity_flow.terminal_clause`，只对冻结的 266 实例集成立），**类级规则未动**。准入口豁免同批降格为条件式 authority ＋ `model_stricter_faces` 第 (6) 项。细节读 `26_rules_handbook.md` §4 / §4.1 / §11。

---

## 7. 在飞与外部等待（本页最易过期的一节）

> 这一节的权威是台账 §0a 的**末尾若干行**；本页只留坐标，读之前先扫台账末尾。

- **U-01 + 混吃汇流区批**：在 worktree `mixflow-surgery` 验收成立，**未 reseal、未接线**，按纪律留接入批。工件 `.artifacts/mixflow_u01_20260807/`、`.artifacts/mixflow_demix_ban_20260807/`。
- **mixflow 外审判决 = BLOCK**：阻断点是 de-mix 解的游戏动力学纳伪（含 4 格反例），编码层清白；解除条件六条。判决存 `.artifacts/mixflow_review_pack_20260806/verdict_20260807/`。
- **GPT Pro 审查包**：`.artifacts/gpt_pro_review_batch_20260807/`（codex 额度见底后审查改攒批走 GPT Pro）。
- **规则系统重设计线**：`docs/research/rule_system_redesign_20260807/`，方法学已翻转为第一性推导版。

---

## 8. owner-only 闸（各带默认建议）

> **在案待决的完整清单在台账 §4 表（表头自记哪些待决、哪些已决）＋ §0a 末尾几行。本页不复刻条数**——条数会变，抄下来就是第二真相源。

| 闸 | 现状 | 默认建议 | 出处 |
|---|---|---|---|
| 阶段手动门（P1.2 close / P1.3 entry） | 已关 / 已开 | 无需动作；任何绿灯都不得改写为关门动作 | `data/review_gates/phase_1_2_spike_close.json` |
| B6 cut promotion 手动门 | **未授权** | **维持不动**：前置数据 = 无有机暴露证据（零激活是 cap 口径的结构后果）；换实验设计拿到激活证据再议 | 台账 §0a「owner 五项拍板」行；卡 `cut-trigger-never-organic-mechanism` |
| canonical 条款修正（任何一笔） | 上一笔挂账已由 08-08 批结清（§6 末行）；新的待写内容按老规矩继续挂 | **攒批合批**走完整 freeze-ritual，不零敲碎打 | 台账 §4 #12 与其后挂账行 |
| PIC-4/PIC-5 证据口径（#9） | 待表态：管理口径认为只剩 B6，`PROJECT_LOCK.md` 口径仍把它列为 B6 硬前置，而仓库无「prod 形态修复后 APPLIED>0 且走完失活 / 回滚」的归档证据 | 二选一，本页不替 owner 选：正式接受 harness 层证据，或 B6 前补做一发 prod 注入演习归档 | 台账 §4 #9 |
| front-clear lift 默认值翻转（#10） | 维持 default-OFF | **维持 OFF**：语义三面实证正确、OFF 零回归，但 ON 解不动锚点 | 台账 §4 #10 |
| 研究线调参演习 go/no-go（#11） | 待拍板 | 决定研究线火力投放，需 owner 定；本机内存余量存疑是硬约束（见 §4） | 台账 §4 #11 |
| 游戏语义定谳 | 常设入口 | 对账先跑模拟器（第一参照），**分歧才升级为 owner 游戏实测定谳**；owner-only 闸是"账算齐了再上桌"，不是停止推导的借口 | 卡 `canonical-audit-simulator-first`、`classification-labels-hide-parameters` |

---

## 9. 已知登记漂移与机制欠账（订正不在本页职权内）

| # | 漂移/欠账 | 现行以谁为准 |
|---|---|---|
| A1 | 三处对 P1.2 关门的记述停在上一次关门：`CLAUDE.md` 大图 §4、`docs/项目说明/06_current_status.md` 头部发布结论行、`docs/项目说明/00_master_roadmap.md` §0 | `data/review_gates/phase_1_2_spike_close.json` |
| A3 | 文件记忆卡 `empty-rectangle-strict-semantics` 内记的 canonical 字节身份停在中间代 | `scripts/preflight_gate.py` `FROZEN_ARTIFACTS` |
| A4 | 1F 生产内存条款（62G）对现行池失效，待随池版本重标定 | §4 本页行 + M5 卡 `cc_memory_vnext/cards/p1-3-batch1-m5-current-20260805.md` |
| A5 | `docs/项目说明/06_current_status.md` 的状态日期早于最近数批（严格空矩形语义落地、canonical 公理 kernel 批、面积上界转正、U-01/mixflow 批） | 比它新的进展在台账 §0a |
| A6 | `PCR patch_routing_core._add_port_adherence` 仍用旧 `port + DIR_DELTA` 偏移（front 事故点名禁止的形态），属 LEGACY_DIAGNOSTIC 面漏网；当前 HEAD 由 closed allowlist 挡住不可达，归 PCR / pose-bool promotion 的**前置硬阻断** | 源码 `src/models/patch_routing_core.py:569` + `PROJECT_LOCK.md` |
| A7 | `PROJECT_LOCK.md` §1A 把谓词外延与 soundness 定义的出处引成 `01_overview` 的「§1.1/§1.3」，但本仓 §1.3 标题是「当前求解与发布链」，命题文本实际在 §1.2 —— 节号指称漂移，条款实质不受影响 | `docs/项目说明/01_overview.md` 实际章节结构 |
| A9 | 无时态手册（26/27/28）的**内容现势性**无机械体检：就地更新只有各页头部「同批更新」纪律在管；两个扫描器只查引用完整性不查内容是否过时；查漏镜头现役范围=记忆层、未覆盖 docs 手册。补法=查漏镜头 docs 适配扩到 26-28（未来剪枝批） | 各页头部纪律 + 台账 P4 行 |
| A10 | 文件记忆层每卡**两块门牌**（MEMORY.md 索引行 + frontmatter description）与正文的语义现势一致性无机械体检——门牌停旧名会让联想链断在门口（卡在库里等于没有）；日期代理分诊 49/79 过标，只能语义判。补法=判官层检查项（预筛+gap-lens 型语义核验）+ 单门牌化提案（description 唯一真相源、索引行编译生成，待 owner 点头） | `.artifacts/prune_v2_20260803/plate_staleness_note_20260808.md` |

---

## 10. 线程分工

- **分工是条件式的，前提 = 确实存在左 / 右双线并行编排**（owner 口径见卡 `branch-resume-topology-wf-inheritance`）。**在该前提下**：主线前沿（W0 / 求解方向线）归左线，欠账 / 基建 / 剪枝类归另一线（不影响左线即可；登记欠账类顺手做没问题）。
- **跨线通信**：CC 2.1.226 起两线可**直接 SendMessage**（`ListAgents` 见对方会话名即可发）。现行口径 = 纯信息交接 / 通报 / 征求意见走直达；**决策与拍板类仍上桌给 owner**；一方权限内被拒的动作不得让另一方代做。
- **当前是否处于该编排、你是哪一线，问 owner 或看台账 §0a——本页不判定。** 不在双线编排下时，上面这条分工不适用，别拿它当「这活不归我」的理由。
- 配套拓扑纪律：`/branch` 会把"主线程"身份连同活 workflow / shell / monitor 一起搬给分支线程，原线程被关；resume 原线程后**别动 `.claude/worktrees/` 下任何目录**，也别用 journal 续跑那个 wf（会造出撞车副本）。
- 出处：文件记忆卡 `branch-resume-topology-wf-inheritance`（owner 口径）。

---

## 11. 去哪儿看

| 想知道 | 去 |
|---|---|
| 当前实现状态全景（本页不取代它） | `docs/项目说明/06_current_status.md` —— 它的状态日期见其头部；**比它新的进展见 `docs/项目说明/00_master_roadmap.md` §0a** |
| 接下来做什么 / 某条线排在哪 / 哪些事等 owner | `docs/项目说明/00_master_roadmap.md`（§0a 里程碑指针表、§4 拍板台账、§0b 科学面归属判据） |
| release 红线 | `PROJECT_LOCK.md` |
| 谓词到底是哪 6 条 | `docs/项目说明/01_overview.md` §1.1 / §1.2 |
| 游戏规则现行理解 | `docs/项目说明/26_rules_handbook.md` ＋ `rules/canonical_rules.json` |
| 机制性坑与操作规程 | `docs/项目说明/28_pitfalls_and_sop.md` |
| 调用链导航 | `NAV_MAP.md`；符号定位先用 CodeGraph（`.codegraph/` 缺了就 `codegraph init .`，约 9s） |
