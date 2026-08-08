# 00 — 总路线图（master roadmap）

> **本文档的地位（先读这段）**：全项目工作线的**总图 + 排期快照 + 指针**，
> 2026-07-05 起立此存照。它不复制各阶段计划的细节（细节仍在 08/09/10 与
> docs/research/ 各设计稿），也**不是**状态权威——release 边界以
> `PROJECT_LOCK.md` + gate JSON 为准，当前实现状态以
> [06_current_status](06_current_status.md) 为准。
> [soundness_gap_roadmap](soundness_gap_roadmap.md) 是截止 2026-07-11 的 P1.2
> soundness 历史快照，不是当前 authority；其中 throughput 的 P1.2 scope exclusion
> 不覆盖本文 §1e 的后续 owner 决定。主线执行序以 owner 拍板的排期卡
> （`cc_memory_vnext/cards/p1-2-closeout-then-tcb-backlog-order.md`，
> **以其正文 2026-07-04 晚修正版为准**）为准。本文档过时时，以上述权威为准
> 并回来修这里。
>
> **为什么有这份文档**（2026-07-05 盘点结论）：此前"阶段之间的总图"散在
> 05 号汇总表、排期卡与各研究稿里，没有单一入口；且 2026-07-04/05 两天
> 新增了整条形式化验证线（P3.0 双轴）与吞吐改判（P2.0 必做），旧计划
> 文档没有它们的位置。08/09/10/13 是"史料+现行混排"的 ledger，**保持
> 原样加注、不重写**；总图由本文档承担。

## 0. 一句话现状（2026-07-30；研究证据截止 2026-07-30）

P1.2 认证链 **CLOSED**（2026-07-07 owner `owner_manual_decision`）。P1.3 进行中，
研究双账当前为 `U=(1188,18)`、`L=absent`。strict/SMM3 与前两个 SMM4 root
的失败事实继续保留；第三个 fresh-authority root 的唯一 formal one-shot 已由
最终 detached receipt 与 immutable closeout 授权 research upper recovery。
该结果不建立 `(1188,18)` attainability、global optimality、whole-instance
infeasibility、lower bound 或 production `CERTIFIED`。最近已完成的最小研究实现是
W0 power-cycle domino 的局部 D6 joint completion；closed-root v2 的 seed-narrow 与
28-slot antecedent 均已被异构 replay 接受为 local `INFEASIBLE`。随后唯一放宽
`d6_6b_d9_6g_swap_v1` 单轴 class transfer 也已通过 clean 实施提交、full preflight、两次
相同资源门禁与双异构 replay，终态仍为 exact local D6 `INFEASIBLE`；本轮据此停止。
AB16 强制链已冻结 A031–A038：A033 停在 formal admission；A034 只发布 input
authority 并完成 disposable drill；A035–A037 只发布 input authority；A038 的 pinned
Gate-A full preflight 以 `FAIL_CLOSED` 结束。A038 不得补写、重放或复用，目前没有
fresh successor、Gate-B 新 authority、formal trusted terminal 或 organic arm，仍为
`0/16`。下一 fresh successor 必须绑定 clean 修复提交和新的 stage-specific resource
profile set 后从完整 Gate A 重来；A038 与此前 full 均不构成资格证据。

| 工作线 | 当前终态坐标 | Authority 边界 |
|---|---|---|
| **cut 框架工程线** | Production family 状态不变：F1/F6/F7 为 typed，F5 为 shadow-only，F2/F3/F4/F9 为 `LEGACY_DIAGNOSTIC`，F8 retired；attach 仍 unsafe/default-off，B6 未授权。07-24 rule/cut evolution 只增加 test/offline shadow 维护面。Noncert cuts Gate 1 v4 只建立 `MECHANISM_CREDIBLE`。AB16 A031–A038 均已冻结；A033 完成 Gate-B/package 后只发布 formal admission，A034 停在 Gate-A input authority 与 disposable drill，A035–A037 只发布 input authority，A038 的 full preflight 为 `FAIL_CLOSED`；没有新 Gate-A/Gate-B authority、guardian-ready、attempt consumption、selection、unit、terminal 或 organic arm，仍为 `0/16`。 | Shadow 与 noncert 结果都不授权 production attach、family-global soundness、上下界、witness 或 optimality。 |
| **求解与研究线** | SMM4 fresh-authority 的 `smm4-formal-a004` 已消费且不得重试；最终 detached receipt 与 immutable closeout 均为 `VERIFIED` 并授权 research upper ledger 更新为 `U=(1188,18)`，`L=absent`。内部 formal receipt 即使 `VERIFIED`/UNSAT 仍为 `upper_bound_update_authorized=false`；routing-aware witness/W2b 仍没有被账本接受的 layout。W0 D6 已具备 hash-pinned、no-overwrite、cache-free、逐组件 no-follow 打开、全树目录 FD/signature 终检、固定 artifact label/path 与独立 replay；closed-root v2 的 seed-narrow、28-slot antecedent，以及保持 geometry/pairing/tile split/28 slots/全局 ledger 不变的 v3 `d6_6b_d9_6g_swap_v1`，均为 replay-accepted local `INFEASIBLE`。本轮停在 v3 精确局部结论。`AB16_GATE_B_AND_16_ORGANIC_ARMS` 停在 A038 `FAIL_CLOSED` 后的实现收口；下一 fresh successor 只可在 stage-specific resource admission、独立 worktree 快进与完整 Gate-A 门禁闭合后创建。 | D6 的 `FEASIBLE` 只证明完整一致的局部 antecedent，`INFEASIBLE` 只关闭同一局部 antecedent，`UNKNOWN` 无拒绝语义；D9 在 swap 中只作 ledger 算术补偿、不被求解。W0 v3 与 AB16 transport/resource admission 条款均不扩大 certified/production authority，不改变上下界或 cut。旧 receipt-payload-v1 root 不证明完整 run root 已封存。 |
| **支线** | P3.0 轴 A 已有 68 条定理；轴 B 待开工。P2.0 吞吐认证仍是 owner 判定的必做线；TNS 设计稿完成未排。 | P2.0 不受 P1.2 历史 theorem scope exclusion 覆盖。 |

下表保存 **2026-07-20 的执行快照**，仅用于追溯当时的排期，不覆盖上表终态：

| 工作线 | 当时在哪 | 当时下一步 | 当时等谁 |
|---|---|---|---|
| **cut 框架工程线** | Stage B 工程面全部完成（B0-B5b + 批D F5 独立 verifier + 修复批 α/α2/β + B6 前置工程批 + 批E RFC-003 + prod 形态适配批）。family 现状：F1/F6/F7 = COMPILABLE/TYPED；F5 = shadow-only（compiler=None，真 adapter 修复挂 F5 转正批）；F2/F3/F4/F9 = LEGACY_DIAGNOSTIC；F8 retired。certified 下 attach 保持双重禁用（env unsafe-map） | B6 owner flip → F5 转正批 | **owner**（B6 手动门；PIC-4/5 生产层 APPLIED>0 证据口径见台账 #9） |
| **求解与研究线** | C1 编码 = certified 默认 master 表示（首解之墙 07-09 已破）。全局最优证明已规约为「3 负锚点 + 1 witness = 4 个固定小实例」（07-14 八人会议）。RAB-SEP 通道收编 certified（默认 OFF，`F-BL-R11-01`）；front-clear 必要条件上收 master 编码（`F-GM-FCL-01`，默认 OFF，语义三面实证正确、OFF 路径零回归；presolve off 为 lift-ON 必要操作配方）。6×6 锚点 lift-ON 下 30min 单发 fixed/automatic 均无 incumbent 无 INFEASIBLE。**⚠ 07-18 front 错位 P0 事故：旧实验数字全部在错位语义下跑出，批 4 全量重跑前处于撤回状态**；修复批序列 批1（`060aeb6`）/批2（`bb415f1`）/批3+5（`9c0f724`，封号窗口 codex 代刀，新池 81,797 异构对账全中、五钉一致，合并终态门 07-18 晚两连绿）已落地；批4 部分（`a0f7525`：重建 witness FEASIBLE、"24 杠杆穷尽/结构墙"维持撤回）；**07-19 值夜**：RAB-on SIGSEGV 销项+FCL 生产 lift A/B 齐（on 臂 0 cuts/2.4h，**lift 默认 OFF 维持**，台账 #10 不变；doc `04`）；owner 第 4 笔域缺口（未启用口朝外合法）→ codex `0c8603d` 修复**池 82,829**（core+488/box+544，闭式对账全中）+严格三层规格书 `5a697c8`（validator 不外发防牵引）→ 合并 `b1cf014` 终态门双绿；R1 严格版已交 owner 外发 GPT Pro | 批 4 余量：witness maximize 臂（在跑）+ rounds 1-5 重跑（清单三梯队已立）+ PB 闭环 | 批 4 自主推进；R1 回复到达后按 rubric 判读 |
| **支线** | P3.0 轴 A：68 条定理落 main、两轮外审闭环；轴 B（证书侧 proof logging）待开工；P2.0 吞吐已改判必做、b 段实现规格待批准；TNS 设计稿完成未排 | 按 §2 与台账 | 台账 #4 |

防蓄意内鬼硬化桶（#8 深化/#2/#3/#5-F/#9b/#9c/Option B）延期到发布时点；#9a 为部署时点任务。

### 0a. 里程碑指针表（P1.3 开放以来；叙事细节归各文书与 git，此表只留坐标）

| 日期 | 里程碑 | 详录 |
|---|---|---|
| 07-08 | M1 attach sizing spike GO；M2 语义前置（F7 stencil 统一/F8 整族退役/F3 方向表）；M3 step_8 通电+LBBD 接线；M4 attach 链通电+cut 预算闸（F5 后于 B5a 转 shadow-only，通电终态=F1/F6/F7）；M5 一阶段：prod 规模无首解 | [09号](09_phase_1_3_plan.md)；`p1_3a_attach_sizing_spike_20260708/` |
| 07-09 | M6 八实验定位首解之墙=供电覆盖 witness 编码；C1（杆侧 pose 布尔+cov 通道）当夜破墙——项目史首个完整 master 解 OPTIMAL@541s；GPT Pro 双轨外审零 BLOCK | `p1_3_m6_diagnosis_20260709/07_final_diagnosis.md`；`p1_3_a_batch0_20260709/` |
| 07-10 | 批1（C1 certified 化）1A-1F 全落地；M5 内存归因平反「产品化回归」冤案（真相=C1 出解时刻 ~60G 固有尖峰撞 42G 帽+禁 swap）；attach 通电 spike 判 GO（10K cut +6.9% wall） | `p1_3_batch1_design_20260710/`；`m5_c1_memory_attribution_20260710.md`；`p1_3a_attach_power_on_spike_20260710/` |
| 07-11 | M5 A/B 证伪「默认参数病态」；Stage B 规格 v3 定稿并当夜连落 B0→B5b（typed 单一可信链通电+AST lockdown，F5 apply 物理删除） | `cut_framework_review_gpt56pro_20260710/03_stage_b_implementation_spec.md` |
| 07-12 | 批D（RFC-002 F5 独立 verifier，differential 357）；修复批 α/α2（信任根七门+写入面锁定）；批E（RFC-003 semantic dedup+非消费 ledger+family 开关）；修复批 β（文档层校准） | [06号](06_current_status.md) 07-12 增量段 |
| 07-13 | 批C cap 矩阵完成；owner 四项口径拍板（台账 #7）；F-6 诊断：binding↔routing 无帽枚举循环 | 台账 #7；`batch_ce_attach_host_20260712/` |
| 07-14 | prod 形态适配批（int orientation gap，台账 #8）；八人会议规约「3 负锚点+1 witness」；研究线 round 1-3（两条便宜上界证书判死→front-clear 必要条件翻案） | `cut_framework_review_gpt56pro_20260710/` doc10-14 |
| 07-15 | round 4-5：UBC 证书 sound+紧凑但 CP-SAT 在三真锚点全 UNKNOWN（solver 墙）；owner 立项 Fable 对照实验 | 同上 doc15-16 |
| 07-16 | 对照实验发现树内 RAB-SEP 通道+Opus 五轮三次擦肩（doc17）；RAB-SEP 三段批收口（`815a73e`）；front-clear 上收批：设计四席对抗→实施 reseal（`7b9cbae`）→六级验证阶梯→presolve 病灶破案→探针 3/4（`0873cd1`/`7b88ab8`） | doc17；`rab_sep_promotion_20260716/` doc01-06 |
| 07-17 | 过夜长预算单发在跑（lift ON + presolve off + automatic，无时限）；文档卫生批（本文档重构+名词表+`deliverable-docs` skill） | `rab_sep_promotion_20260716/`；[21号](21_glossary.md) |
| 07-18 | front 错位 P0 事故（口坐标=带子格、机械查体外第 2 格）：普查+批 0 owner 定谳（补域 68,469）+批 1 identity 原子 reseal 落地（`060aeb6`，四门全绿）；owner 全量规则校对：3 笔新实锤（协议箱实体口/中枢 14 进/canonical 语义缺口）+IP/EC 上游对账快照入库；批计划改为 批2→批3+5（合并换钉，含协议箱池重生成）→批4；批2 落地（`bb415f1`）；owner 点火批3+5 并原则性纠正措辞（最优解从未变，旧数字=模型误差品）；**封号窗口（午-晚）codex 于 `~/zmd-pj-codex` 代刀完成批3+5（`9c0f724`，新池 81,797 与主会话独立闭式逐池全中）+批4 部分（`a0f7525`）**；晚间合并快进回主树+池工件 restore+终态门补跑（两连绿 4,561×2+慢 lane 31/31） | `front_offset_incident_20260718/00`-`02`；`rules_audit_20260718/00`-`01` |

| 07-19 | 值夜批：RAB-on SIGSEGV 复现销项（clean 逐字一致；根因=内存超频环境层）+FCL 生产 lift A/B 收齐（on 臂 0 cuts/2.4h→lift 默认 OFF 维持）+owner 第 4 笔域缺口定谳（未启用口朝外/被堵合法）→codex 修复池 82,829+严格三层规格书（validator 不外发）→合并 `b1cf014` 终态门双绿；R1 严格版外发 GPT Pro；rounds 1-5 重跑清单三梯队；stop hook v1.7（23 键泄漏修复）；witness 链独立零违规审计收官（`d8bb218`，两臂零违规+五路突变金丝雀） | `front_offset_incident_20260718/03`-`04`；`cleanroom_rederivation_20260718/strict/` |
| 07-20 | **Rounds 梯队 3 主件收官（RND-06 重验完成）**：codex plan 模式端到端试点成功（owner 教的 plan 问答循环→选1→执行→自提交流程全链走通；机器重启后 owner 亲驱 codex 续完）——round45 bespoke coordinate master 修正语义重建 `9219498`：**10,816 var/16,513 constraint（对比历史 10.7K），六臂（seed 71-73×600s/1200s）全 clean 完成、三锚点全 UNKNOWN=无上界证书**；旧 18-20GiB 内存墙未复现（峰值 1.44GiB）但不得升级为新结论，"结构墙"判词维持撤回；campaign 工件哈希/soundness 抽审/独立 oracle 验收全绿后合并 `74ff084`。附带 `c8fe04e` 严格包确定性账本修复（对已外发 R1 三件套零影响=不必重发，六向哈希比对）。owner 侧：A 社订阅再封→中转链就位；⚠ 中转配额紧→**owner 拍板默认委托路由改 codex 直调（MCP/shell），claude 只管计划诞生+判读验收**。**R1 严格版判读（`7d013c3`）：12/12 满分+十条假设零违背（严格包完备性干净房间级确认）+两项 certified 前置引理异构复算收编——47 边界模式塌缩（每边恰23台/gap≡0 mod3/角互斥）+**全局面积上界 (1326,34)**（P≥2→自由格≤1348→46 接驳格强制→47×1,182 枚举；项目首个 certified 上界；`verify_r1_strict_bounds.py` 复现）。**PB-03 收官=批 4 清单全清**（codex 端到端第二单，`3888407`→合并 `18a6270`，门 19/19）：(1326,34) 带内 22 尺寸的 residual-band OPB（16,749 var）经独立 translation gate（14/14 PASS、最小 |R∪Q|=1,351>1,348）→RoundingSat 25.5MB proof→**VeriPB 3.0.2 VERIFIED UNSATISFIABLE**——项目首份机器可验上界证书；claim=两段式（带外 1,763 尺寸初等排除+带内 VeriPB），研究级非 sealed。干净房间 R3（方法论移植轮）材料备好（`95b4843`）；**R2 判读（`f931d1a`）：五问全中靶心——判据层被独立公式化（owner=max scope 归属公式/P⇒E 投影铁律/六 soundness gates/cut-dependent proof ledger），四条量化断言复算逐字全中、11 假设零违背；六条超出增量入收编候选（归属公式候补 00 号 §0b 待 owner；proof ledger+minimality witness 归 Stage B promotion 前置；两条免费投影转 witness/负锚点线）**。主线回归 4 小实例框架：witness routing-aware 构造器委托已发（codex 端到端第三单，计划已批执行中）。**R3 判读（`cb32e07`）：方法论移植轮直接命中——两个未走过的方向产出更强上界：certified 全局上界收紧至 (1190,34)**（端口膜计数：对侧单向口+外部每格≤4 接驳 ⇒ wh+⌈(580−w−h)/4⌉≤1320）**+杆数下界 P≥9**（供电光环 396 权重证书，840 放置不等式复算零违例）——两证书 `verify_r3_certificates.py` 异构复算全过，(1326,34) 被严格超越（PB-03 证书自身 claim 不受影响）；等式挖矿三强制（ceiling 下恰 9 杆/零箱/矩形不贴边）；方法论批判六条（语义 ledger 三极性/cut 带前件/主动挖对偶/micro-oracle/信任三段/双 ledger）与 R2 归属公式合并候补 00 号 §0b（待 owner）。**(1190,34)+P≥9 对抗复核批已过（`11` 号：codex exec ultra 对抗席 14 攻击面全 CONFIRMED、两证书 SURVIVES）——certified 待遇正式生效**；待办：PB 化评估；光环推广与 frontier 逐维排除入换攻法候选 | `front_offset_incident_20260718/06`-`07`；round45 目录+`.artifacts/.../r45-6120809f5de8b4f5/`；`cleanroom_rederivation_20260718/04`-`06` |
| 07-23 | R4 `a004` 只把 `(1188,22)` 准入为 B1 encoder-design 输入；随后 B1 proof-bearing PB/RoundingSat/VeriPB 链完整关闭 lex-better band，research upper ledger 更新为 `U=(1188,22)`，`L=absent` | `r4_response_review_20260723/`；`b1_r4_1188_22_pb_20260723/` |
| 07-24 | `(1188,18)` sidewise strict 与 SMM3 recovery 均以 `FORMAL_AUTHORITY_INCOMPLETE` 失败关闭，账本不变。Rule/cut evolution 保持 test/offline shadow。Noncert Gate 1 v4 仅建立单个注入 inequality 的 `MECHANISM_CREDIBLE`；AB16 停在 Gate A，未创建 formal campaign 或 organic arm | `b1_sidewise_marked_membrane_strict_20260724/`；`b1_sidewise_marked_membrane_authority_recovery_20260724/`；`23_rule_cut_evolution_protocol.md`；`noncert_cuts_ab_trust_gate1_v4_20260724/`；`noncert_cuts_ab16_20260724/` |
| 07-25 | 合并态 provenance gate 保留 Track B、R4 与 noncert 研究 authority 的原始 HEAD/input/tool 身份；旧 receipt 不因进入后续 HEAD 而成为新生成 authority，研究双账仍为 `U=(1188,22)`、`L=absent` | `src/tests/conftest.py` |
| 07-27 | SMM4 第三个 fresh-authority root 完成唯一 formal one-shot；`smm4-formal-a004` 已消费且不得重试。最终 detached receipt 与 immutable closeout 均为 `VERIFIED`，且只有二者授权 research upper ledger 更新为 `U=(1188,18)`、`L=absent`；`production_certified=false`。下一项强制任务登记为 `AB16_GATE_B_AND_16_ORGANIC_ARMS`，未执行 | [SMM4 fresh-authority recovery](../research/b1_sidewise_marked_membrane_fresh_authority_20260727/README.md) |
| 07-28 | G3 最小公共研究基础层与 W0 D6 层落地后，发现 historical seed-narrow `receipt_payload_v1` root 有两个未登记 `.pyc`；其命名字节图局部 `INFEASIBLE` 保留，但完整 root closure 不成立。G3 v2 以逐组件 no-follow 打开并保留全部目录 FD/signature 至终检，采用排除固定 `receipt.json` 自指的 exact path/type manifest 与 `-I -B` 进程合同；W0 replayer 同步该遍历合同并钉死 artifact label/path，对真正 `receipt_payload_v1` 稳定返回 `ROOT_CLOSURE_CONTRACT_MISSING`，并拒绝整体改名和任何额外节点。截至 07-28 当时，强制 seed-narrow v2 重跑仍等待 Endfield 退出，随后还须通过 full preflight 及资源/竞争 solver/项目锁/clean-HEAD 门禁，才按 FEASIBLE / failure-or-UNKNOWN / replay-accepted INFEASIBLE 自动分支。tracked 状态与 `U=(1188,18)`、`L=absent`、production authority 不变。AB16 未取消，继续后置 | [W0 D6 research gate](../research/w0_power_cycle_domino_d6_20260728/README.md)；[24号治理](24_repository_asset_governance.md) |
| 07-29 | W0 D6 v3 协议与单轴 `d6_6b_d9_6g_swap_v1` 落地于 `db00416d3c68`；full preflight `19 passed`，两次相同资源门禁均通过。新 no-overwrite producer root 返回 `INFEASIBLE`，exact antecedent 为 `dab2a328…a9221`；CPython 3.13.13 与 3.14.6 的两份 root-pinned replay 均 `PASS`、输出逐字节一致（SHA-256 `568b58bb…cc6f24`）。该结果只关闭 exact local D6 swap antecedent；D9 只作未求解的 ledger 算术补偿。本轮停止，不自动进入另一轴、D7 或多轴放宽；tracked `U=(1188,18)`、`L=absent`、cut 与 production/certified authority 均不变 | [W0 D6 research gate](../research/w0_power_cycle_domino_d6_20260728/README.md) |
| 07-30 | AB16 强制链的 A031–A034 均已冻结。A033 通过 fresh Gate A、Gate-B qualification 与 package/campaign 创建，但 formal 阶段只发布 admission；A034 只发布 input authority 并完成 disposable drill，未 finalize Gate A、发布 candidate/preregistration、进入 Gate B 或消费 formal attempt。冻结证据不能恢复被旧 orchestrator 遮蔽的 selected-supervisor stderr；241-byte canonical guardian socket path 暴露 Linux pathname AF_UNIX 阻断，而后续审查又证明 pathname unlink 与未经闭合的 retirement 验证不能授权清理成功。当前修复保留 canonical absolute identity 与 retained-dirfd transport，以 path-preregistration v4、formal context v3/admission v2 登记固定 `.retired` 终端成员；cleanup 只执行 `renameat2(RENAME_NOREPLACE)` 与 parent fsync，authority 链不调用 pathname unlink，并在最终 absolute-parent join 后以 retained absolute-directory-chain 与 retired-inode mutation watches 闭合 topology/parent/leaf 验证窗口。A031–A034 不可修补或重试；此前 full 无资格意义，下一 fresh root 只能是 A035，必须重新绑定提交与完整门禁 | [AB16 current status](../research/noncert_cuts_ab16_20260724/README.md) |
| 07-30 | AB16 后续 A035–A037 均只发布一次 input authority 后冻结；A038 的 pinned Gate-A full preflight 以 `FAIL_CLOSED`/exit `1` 结束，三项 launch authorization 均为 false。A031–A038 与所有历史 roots 保持不可变，fresh successor 尚未创建，organic arms 仍为 `0/16`。下一实现把原跨阶段统一阈值拆为 `FULL_PREFLIGHT`、`GATE_B_QUALIFICATION`、`FORMAL_ORGANIC_ARM` 三个有 basis/predicted peak/safety margin/host reserve/live measurement 的 conservative temporary profile；三锁、same-UID 冲突、单 worker 与 formal `35/39 GiB + 16 GiB swap` cgroup 硬上限保留，且在拿锁后及每个实际重负载 prelaunch 前重新判定。该协议只治理 research admission，不新增 Gate-A/Gate-B/formal authority，也不改变 `U=(1188,18)`、`L=absent`、cut、production/certified 状态 | [AB16 current status](../research/noncert_cuts_ab16_20260724/README.md) |
| 08-01 | owner 回归。codex 自治期未合并段（66 提交）经五维对抗验收全 `PASS_WITH_NOTES`（smm4-authority/ab16-lock/w0-domino/shadow-parity/ab-trust-line；66 提交对 `src/` 非测试文件逐提交零触碰，sealed 面全未动，SMM4 的 24 项输入哈希与 VeriPB 均独立复核通过），合并入主树 `d3f4781`（冲突解法：parity 守卫取超集版并同步 lock pin；README 口径修正为 SMM4 授权后 `U=(1188,18)` conditional；交接书顺延为 25 号）。codex 停机前最后一笔 `62bc65f`（phase 2 预算权威，11 万插入行）未过门禁即提交且丢失 authority 接口、打红 43–64 个测试，已精确 revert（`7b2432c`，父提交时点实测全绿）；合并态 full preflight `19 passed`。验收坐实 ab16 两个 major：38 个 Gate-A root 26.5h 内全部冻死、0/16 organic arm、自治期 81% 插入行零科学产出=自加固循环；解锁链无尝试次数上限。owner 表达方向倾向：**AB16 不封顶、考虑做减法**（"是否应该去掉一些"）——候选=去除自建威胁防御层、保留预注册 16 臂科学本体；减法批范围待 owner 对具体清单拍板后才执行 | 本文档；[验收 workflow 记录见会话]；`docs/项目说明/25_autonomy_campaign_plan_20260720.md` |
| 08-02 | **AB16 减法批 + 返工批验收合并**（owner 已拍板"不封顶、做减法"）：codex 端到端四刀（拆预算权威 phase-1 逐字节逆向/拆防御栈 8.2 万行/one-shot 冻结改可修复重跑/lock §3C 瘦身 1004→700 行 + 44→49 schema 外移为 machine-checked declaration）经三方验收（opus 六维工作流 20 代理 + codex 对照席 ×2 + 主会话独立 preflight ×3 与分歧亲裁）判"刀1 过、刀2/3/4 返工"——坐实 4 blocker（16 臂生产链断头+冻结 manifest 钉死 attempt_dir 结构性不可重试/终名直写无原子发布=新冻死类/科学输入无 campaign 级锚可跨 slot 漂移/retained-FD 防御残留）+5 concern；另 6 条指控经对抗复核驳倒入禁修清单（Gate1/trust §3C 条款删除裁定属 ab16 范畴合规）。返工 6 提交全部落地（生产链+recover-staging/abandon-attempt 原子恢复+预注册钉 campaign 科学锚+普通路径执行+baseline 自举+文档四件套），复验收九项逐证据点核过、独立 preflight `19 passed` 后 ff 合并 `93835fd`（净 −87,127 行）。**ab16 剩余 = 资源标定→真跑 16 臂→预注册口径评估报告，然后按 owner 停止令停下**；R11（flock 随控制进程死亡先于 transient unit 释放+`run_selected_arm` 直调不获锁）为真跑前必修遗留。**新排期候选（owner 08-01 监督线程提出、codex 四层分类答复）：「基础机制→派生定理→人工 cut」批**——派生结论按性质四分（必要投影/带前件条件 cut/充分限制/启发式），五个候选方向（端口 Hall/单格路由方向签名/供电 hitting-set/组件分隔带/孔洞条件 Hall）与 R1 弹药清单及 3 号 GPT 诊断 G1 三路汇流；排 ab16 收尾后 shadow-only 起步。另记环境债：6 个 track-b/R3/R4 测试硬编码 `/home/zhuran24/zmd-pj-codex*` 绝对路径，现靠 host symlink（→wd_external 归档/→主仓）垫绿，耐久修复另立小批 | 本文档；`.artifacts/ab16_slimdown_20260801/`（task_brief/rework_brief/RESULT/三轮 preflight 日志）；[AB16 current status](../research/noncert_cuts_ab16_20260724/README.md) |
| 08-03 | **AB16 十六臂正式实验完成并按 owner 停止令收官**。真跑阶段以「停机→gated 修复批→重试」循环连清七块执行链化石（R14 baseline 导出 pybind→generated protobuf 桥/R15 fixed-replay 从 pose-bool 选择器面改为消费真实 coordinate-master 变量面、293 条 incumbent 独立复核/R16 manager-epoch 重捕获改用 bootstrap 钉死的 attestor_python 独立身份/R17 零 attach-hook 正常终态如实发布+payload 失败输出接进 supervisor 生命周期/R18 systemd unit 回收竞态下以 wait-observer AddRef 保住 identity-bound 终态取证/R19 ALT_CAP_REACHED=200 对称编码为合法内部截断/R20 suite gate 跨 attempt 工具身份按字节内容归并且 provenance 全保留），每批 codex 执行、主会话逐证据点亲手验收（含「修复前必红」在旧树独立复现）+独立 full preflight 后 ff 合并（`d0e6fad`→`9b29da7` 七提交）。campaign root `run-20260802T221714Z-r6` 共 21 attempts=16 credible+5 工程史料（slot1 磨 5 次），**16/16 臂全部 `BUDGET_CENSORED_UNKNOWN`（binding_alt_cap=200 右删失）+ `ORGANIC_NONACTIVATION`（G/C/A=0/0/0）**，det. time 全带 48.2~49.4s、峰值 ~14.7GiB 零 memory event。正式 v2 分类（sha `8745361b…5769`）：region-capacity/power-hitting-set=`INCONSISTENT_FIXED_RUN_OBSERVATIONS`、shape-packing-hall/bundle=`FIXED_CONFIGURATION_NO_EFFECT`——**本实验没有一个 cut 配置展示可归因的有机 runtime 改善，根因是四个 treatment 的 cut 触发点（binding-infeasible/routing-exhausted 分支）在撞 alternatives cap 前从未到达**；结论只覆盖本冻结实例+seed+删失里程碑，不外推 cut 激活时性能、不授权任何 soundness/promotion claim（authority 全 false，U=(1188,18)/L=absent 不变）。**对 B6 的含义：有机激活率为零 → promotion 实测依据缺位，B6 owner 门的前置数据现状如实为「无有机暴露证据」**。新欠账：PROJECT_LOCK 遗留 R11 blocker 过期文案（attempt-0003 EVAL 判定文档漂移非因果）、`host_gate_quarantine/` 两个可逆迁移的 pytest scratch 目录待处置、6 硬编码路径测试耐久修复仍挂账。ab16 线就此停止；后续 = B6 owner 手动门（真人输入）/派生定理四层分类批（shadow-only）/W0 转向复算（先亲手验 3 号 GPT「129/219 绑不上端口」死刑指控）均待 owner 拍板 | 最终 [EVAL](../../.artifacts/ab16_arms_20260802/EVAL.md)（sha `0320a9ac…1784`）；`ARM_CLOSURES_R6.log`（16 行）；`R6_POSTCLOSE_SUITE_GATE_FAILURE_20260803T0753Z.md`；r3/r4/r5 失败 root 与 EVAL_r*_stopped 系列史料；RESULT.md R14-R20 小节 |
| 08-03 | **收官后三件套（同日）**。①**W0 方向证据做满**：19 号=pinned seed 死刑指控独立复算成立且 repo 语义下更强（最弱 1进1出 要求 219 身位仅 91 可活；GPT 类划分 need 向量与冻结 recipes 商品种类语义不符被抓出并修正）；20 号=H20 备胎微型判定器 UNSAT（双 gap 解读 ~0.018s INFEASIBLE，R2 计数矛盾解析验证：22 台仅 2 杆可达、双杆≤10、缺口 12）——两份外脑回复全消化，**唯一在案候选新方向=17 号 front-aware generator**。②**§0b v2.4 管线门序泛化**（owner 认可）：归属判据泛化为通用管线门序设计法，W0 seed 收编为反面校准（与五月 47,666 惨案构成硬合并/硬后置同构对偶），新管线开线须显式过堂。③**R21 卫生批**（codex 五提交，验收合并 `ffcf0ee`）：lock 头部+§3C 过时叙述对齐（§3B/§4–EOF 及其间 137,658 字节逐字节自证不变、pin 同步）；6 硬编码路径测试改 committed locator 解析（4 归档根+9 哈希，symlink 摘除实测 244 passed，16 旧 fixture-skip 退役真跑，全局 skip 207→170）；quarantine 可逆迁出（EISDIR 消失）。**08-02 行挂账三项全清**。遗留 owner 拍板项：B6 手动门（默认建议不动，零有机暴露证据）/W0 开线（17 号方向）/SMM4 授权工件权威存放地/`.artifacts` 治理边界（live checker 如实停在 376 个批前未跟踪 artifact 代码资产，822≠446，codex 未垫绿）/派生定理四层分类批排期 | 本文档 §0b v2.4；19/20 号文书；`.artifacts/h20_row_power_oracle_20260803/`；RESULT.md R21 小节；locator `src/tests/track_b_archive_locators_v1.json`；迁移收据 `/mnt/wd_external/archives/trash/zmd-pj-r21-20260803/` |
| 08-03 | **owner 五项拍板（原话"都按你推荐的来"）+ 执行**：①**B6 手动门不动**（零有机暴露证据，promotion 无实测依据；将来换实验设计拿到激活证据再议）；②**W0 开线走 17 号 front-aware generator**（G1 先行，G1/G2/G3 按 §0b v2.4 过堂，类需求强制 repo 端口语义）；③**派生定理四层分类并入 W0 线**不单开；④**SMM4 授权工件第二副本落 winc**——已执行：13G 镜像至 `/mnt/winc/zmd-archives-mirror/zmd-codex-autonomy-20260801`（排除 codex-sessions/ 16G），locator 9 哈希验真全过，权威副本仍在 wd_external；⑤**`.artifacts` 历史 root 登记为只读历史证据类**（R22 批执行）。同日 main（`b3cefc5`）慢 soundness lane 全绿（33 passed），快慢双 lane 绿标 | 本行；`/mnt/winc/zmd-archives-mirror/`；`.artifacts/ab16_slimdown_20260801/slowlane_20260803.log`；R22 任务书 `.artifacts/ab16_slimdown_20260801/r22_artifacts_governance_brief.md`；W0 开线任务书 `.artifacts/w0_front_aware_20260803/opening_brief.md` |
| 08-03 | **剪枝系统 v2 开线（owner 指令："把剪枝系统做一下，而且不止应用于记忆，项目文档也要剪枝"）+ 两项架构拍板**。设计稿 `.artifacts/prune_v2_20260803/design_v2.md`（继承六月四次会议全部不变量；新增 docs adapter 第五 scanner；Phase B 解锁、C 继续 defer）。**证据基座**：六路使用普查 `usage_census/report.md`（521 行、全数字附复算命令）+ opus 时代对照镜头 `lens5b_opus_era.md`——查明 cc_memory 仅 11 entries 且 07-14 停写、语义栈 752 行读路径零调用、prune scan 959 行建成后 34 天零调用、文件索引层零代码却贡献 73% 记忆消费；八个漏检案例中五个「知识在库里却找不到」，Phase B 证据门正式判过（查漏镜头优先级 1）。**owner 拍板**：①记忆系统**专门为 Fable 设计**（单一消费者，轻重两档作废）；②**cc_memory 冻结为只读档案**（修订 06-30「三层共存」为「两层活跃+一层只读档案」，执行挂 P2 主批）。**P1 已入库**（main `9880054`，独立 full preflight 19 门 6543 passed 全绿）：540 篇文档分类登记 + 引用完整性扫描器（五 flag、脏分支 fail-closed、报告只落 `.prune/`）+ 117 测试实例；经两轮 codex 对抗审查（12 条 CONFIRMED 带 /tmp 复现）后按 **§3d 收敛判据**分诊——功能缺口全修，内鬼类通路按 **07-06 owner 裁决**暂缓并如实登记进模块 docstring + 报告 `threat_model`/`self_check_scope` 字段。**首份真跑报告结论**（`first_scan_findings.md`）：8 候选 + 134 FYI，逐条核后 **living 层真实文档缺陷 = 0**（6 条是交付副本 commit-hash 重建的已知情况、2 条是计划文档的未来对象），**文档腐烂假设在 living 层不成立**，P3 语义镜头优先级进一步下调 |
| 08-03 | **W0 front-aware G1 批全程收官并入 main（merge `9a6018c`+`080ab73`，16+1 commits）**。G1 终态 = **双 INFEASIBLE·合规**（L0 0.201s / L1 并集 0.283s，删除核 21 命名假设族上证极小；L1 核显示失败从台数迁移到 5×5/6×4 类供给）；台数上界 210→244（「每区 9 台」证伪为菜单排序假象）；供给 3,013→3,113 对需求 3,325 缺 212；病灶=生成模型无自由空间连通性（146→50 存活塌缩）。三席审查（codex BLOCK×4 + opus×2 PASS_WITH_NOTES）→ 主会话裁决：**slot 语义胜诉**（19 号第 4 步系我方事实错误，21 号更正文书入库；GPT 九类表经独立推导坐实），其余三阻塞（L2–L4 越界论断/receipt 第五门 fail-open/preflight 收据）全修（修复批 5 commits + 终验收笔 e23f7ac：gate.json 条件式 PASS 作废语义、治理 append-only 例外等）。**L2 方向决策待 owner**（生成器可修 vs 限制档位太紧，证据分不出）：逐族 valid 极限探测在跑（先导：CLEAN 138 破目录 134；strict 读法下供给仅 2,749 ——两种连通性读法分歧成新变量）；两份 GPT Pro 咨询包（L2 裁决包 + 从头征法包）经 5 席验证修订中，包好即交 owner 上传 | 分支 `w0/front-aware-g1-20260803`；`docs/research/w0_front_aware_20260803/`（章程/RESULT/evidence 小收据入库）；21 号更正文书；`.artifacts/w0_front_aware_20260803/`（g1_run 收据、probe_20260803、两咨询包）；治理登记 `data/repository_governance/code_assets.json` |

### 0b. 科学面方法论：知识与计算的归属判据（尺度无关）v2 → v2.7（2026-07-17 三轮推出 v1/v2/v2.1；07-18 两轮补 cut 方法论与四问统一；07-20 干净房间 R2/R3 外部收编；08-03 管线门序泛化；08-03 夜门内归属四则+分层重排；08-04 预设锚点判据）

> **【操作卡·日常入口】适用域=科学/求解/数学面的**任何**「知识×计算」分解边界（v2.6，见文末声明）。本节自 v2.5 起分两层：这张卡是执行入口（按决策时刻排的七问，⓪–⑥），
> 其下正文各版本块是推导依据与判例库，内容互为映射；日常按卡执行，起争议回正文仲裁。**
>
> **押任何结构性预设（ansatz）之前——最先问**
> ⓪ **锚点问（预设锚点判据，v2.7）**：这条预设卡在哪笔**零余量账**上（=问题算术里
> 被迫的结构，所有解本来就得长这样）？来源属哪类——①算术被迫/②对称 WLOG/
> ③求解器方便/④配方类比？③④类必须当场标价：写明扔掉的解空间与撤退线。
> 快诊断：多份独立方案的撞车点≈被迫结构，分歧点≈愿望区=审查火力集中处。
>
> **开线/设计新管线时——**
> ① **切分问**：每条规则切三档——健全影子（不依赖下层决策即可求值的必要条件松弛）/
> 精确本体/启发式残部。上收的只是影子，本体留在下游当复核官。
> ② **住址问（支撑域判据，v2.5）**：每一片的变量管辖范围装得进哪一层？整个装得进
> 子问题的就住进子问题模型（内聚代价是局部的）；「切开省计算」只对跨子问题的规则成立。
> ③ **排序问**：门按**实测**拒绝成本便宜→贵排；知识坐在它能剪掉的昂贵步骤之前，
> 验证坐在它背书的步骤之后。成本拿不准就先花小钱实测，不许拍脑袋。
>
> **把一条规则切出去当过滤器之前——**
> ④ **耦合问（目标耦合测试，v2.5）**：先小钱实测「无此规则的最优解在过滤下的存活率
> 随目标值怎么变」。最优邻域存活塌缩＝规则与目标对抗＝必须内聚或以禁闭子句反馈；
> 耦合弱才允许切开。
> ⑤ **计量问（报警计量完整性，v2.5）**：过滤器的拒绝率是一等报警指标、必须上报；
> 任何 fail-soft 降级（剥落/取子集）仍计入拒绝率，不许把拒绝转译成接受把报警清零。
>
> **读任何可行/不可行结果时——**
> ⑥ **余量问（余量-影子定律，v2.5）**：需求离松弛上限多近？余量 ~2% 量级时一切
> 未建模约束都会咬，影子必须加肥后其两个方向的读数才可信。
>
> **两条不变式**：早期拒绝带证书、早期放行皆暂定、终审归精确本体；新开管线须按
> 本卡过堂并留记录（模板如下，任务书直接抄走填空）：
>
> ```
> 【过堂表】管线:___  日期:___  过堂人:___
> 预设锚点: 预设 | 前提集 | 来源(①被迫/②对称/③方便/④配方) | 依据的零余量账 | ③④类价签(扔掉什么+撤退线)
> 逐规则: 规则名 | 三档切分 | 支撑域→住址 | 若为过滤器: 耦合实测值+拒绝率上报位置 | 证书形态
> 门序: 门 | 拒绝成本(实测/估) | 它剪掉谁 | 判死条件
> 余量核算: 需求 vs 最松上限 = 余量__%；余量<5% 时列出全部未建模约束及其预估代价
> ```


**一条规则的归属不是"上收/下放"一维选择，是切分后各片的四元组位置：**

1. **切分（纵向）**：每条规则先切成至多三档形态——健全影子（可传播的必要
   条件松弛）/ 精确本体 / 启发式残部。上收从来不是搬家：**能上去的只是影
   子，精确本体留在下游当复核官**（fail-closed 双保险是切分的必然结构，
   不是保守偏好）。先例：front-clear = 计数影子进 master + RAB 逐端口判留
   binding + 完整连通判留 routing；F-GM-BS-R2-01 = 超杀残部降级为热启动
   启发式。
2. **住址（聚类轴）**：每片放它能通过**①尺寸紧凑 ②传播力足 ③机器兼容**
   三腿测试的最高上下文。聚类判据=厚薄：共享决策变量、互相剪枝的片必须
   同住一个求解上下文（学习机器才能跨规则冲突分析）；只交换判决的片允许
   分居（薄腰=合法切口）。跨层共享的计算必须 SSOT 化（先例：demand 三
   helper 进 sealed port_binding）。
3. **管线序（顺序轴）**：**知识坐在它能剪掉的昂贵步骤之前，验证坐在它要
   背书的步骤之后**；按实测拒绝成本从便宜到贵排（RAB 0.07s → binding 秒
   级 → routing 分钟级 → master 百秒级）。踏车的顺序论解读=知识坐在了
   昂贵步骤之后。
4. **下游验证人**：每个早期拒绝带证书、每个早期放行是暂定，由该规则的
   精确孪生在最低管辖层终审（I1 复核、terminal validator 即此结构）。

**报警信号（双向对称）**：上收信号=踏车（下层通道反复学同类教训不完）；
下放信号=①白吃饭（高成本×低剪枝命中率，遥测可测）②超杀（比真相强，
高层会冤杀——降级为启发式/诊断，不删除）③越权判断（所需信息在该层不
存在）。三腿可推理程度：健全性=纯证明、尺寸=纯算术、传播力≈七成经验
可预判、机器兼容靠带遥测便宜探针；漏斗纪律=否决便宜（纸面终审）、通过
昂贵（实测只施加漏斗底部幸存者）。**归属是 master 表示法的函数**：换表示
（pose-bool→coordinate）后必须重跑全部归属测试。
**层数与切口自身是被决定项（v2.1 补，同日）**：规则的完整归属方案是一个
**有序划分**（给出分组+顺序后"不与谁同住"自动蕴含），而划分的格数与切口
位置不是继承给定的——当前 precheck→master→RAB 过滤→binding→routing→
终验的格局是历史累积（RAB-SEP 即一次未被命名的加层）。推导：格数=聚合力
（共享变量互相剪枝→同格，传播更强但单格更重）与切分力（拒绝成本梯度→
分格漏斗+每格专用引擎）在**信息依赖 DAG**（规则需要某层决策结果才能求值
→硬顺序）上的均衡。切分的正确切口=沿信息依赖边界下刀：影子=规则中不
需要下层决策即可求值的部分（五月 47,666 约束惨案=违反信息依赖硬合并；
front-clear 计数影子可上收=计数形态消掉了对 binding 选择的依赖）。两格
互不依赖且成本相近时顺序自由、可并行。**对搜索硬度的层数响应**：单格
solve 解不动时先问"这格是否合并过头"——候选=两段式 master（便宜松弛格
先解、解作 hint 喂完整格）。
历史校准：五月 Lazy Power Completion 是一次失败的下放（教训=下放前提是
例外通道扛得动残余）；C1 与 front-clear 是两次成功的切分上收。若 routing
层将来踏车，第一天照此办理（round 1-2 已证其便宜代理不健全，健全性腿是
那里的主战场）。

**cut 方法论与四问统一（v2.2 补，2026-07-18 owner 两轮推出）**：

*cut 是什么*：cut = 住在下层的规则向 master 运送知识的**运输形态**——
上收是整条规则搬家，cut 是分期付款的包裹。九族（F1-F9，2026-05-22 定型）
是从五月失败样本**归纳**出来的，无覆盖性论证（F8 建立在错误游戏规则前提
上还能立项即铁证）；owner 07-18 指控"cut 无方法论"成立，本节即补账。

*打包三问*（给定一次下层拒绝，包裹打法不是选出来的、是问出来的）：
①**责任圈**能收多小——点名越少禁得越多（五月整层 nogood 踏车=没问此问，
266 全点名一包只杀一点）；②死因里有没有可抬的**数量律**——计数型死因
（容量/口数/覆盖）可抬成算术律（F1/F6/F7/F9），身份型死因（具体形状咬合）
抬不动只能原样打包（F5 的正当业务）；③抬出的定律**上层词汇说得出吗**——
说得出发泛化版，说不出退回冲突核降级版（连通性即此类）。cut 类型空间
因此有界可枚举 = 各验证者拒绝路径清单 × 每条的最泛化健全表达；覆盖性
检查 = 有限审计（F5 兜底占比即未覆盖失败流量的在线测量）。

*四问双向统一*（上收判据与下放判据 = 同一套提问的正反两读；owner 由
打包三问取反推出，把 v2 三个下放信号从症状升级为病理）：

| 问 | 通 → | 卡 → |
|---|---|---|
| ①责任圈/激活面宽吗 | 常驻上层有价值 | 激活面极窄 → 下层待命 |
| ②有可抬的数量律吗 | 抬成算术律上楼 | 身份型零散 → 下层+F5 式个案快递（**白吃饭的病理**：命中率低=知识本质泛化不了） |
| ③上层词汇说得出吗 | 直接编码 | 说不出/爆炸 → 下层+冲突核降级快递 |
| ④求值依赖下层决策吗 | 整条上收 | 依赖 → 只能保守猜=**越权→超杀的因果链**（47,666 惨案全链）；或切出不依赖的影子上楼、本体留守（front-clear 模式） |

四问全通→上收；卡在哪问→卡点同时决定住址**和**该规则 cut 的打法——
归属判据与打包判据是同一次提问的两个读数。每族 cut 的终局三选一，九族
历史全部出现过：毕业上收（F3→front-clear）、确认真例外（F5）、前提证伪
退役（F8）。前瞻价值：routing 踏车之日，第一天即枚举其拒绝路径逐条过
三问生成 cut 族，不再归纳两个月。

**干净房间外部收编（v2.3 补，2026-07-20 owner 批准；出处=cleanroom R2/R3
判读 `08`/`10` 号，两轮独立大脑对同一判据体系的重推与批判）**：

1. **权威归属公式（R2）**：`owner(r) = max{owner(v) : v ∈ scope(r)}`——
   规则的**权威** owner 由其语义所需变量的最晚层决定，更早层只能持有
   §0b-1 意义下被证明的投影。这是"精确本体留在下游当复核官"的形式化：
   权威归属（语义必然，公式定死）与表示归属（性能选择，三腿测试定）是
   两个问题，不得混问。
2. **三极性登记（R3，对 v2.2 三档的扩容）**：每条规则登记三极——必要
   投影（上界证明用）/**充分限制**（构造器用：比真规则严、构造出的必
   合法——v2.2 三档没有这一极，witness 构造器的 L1 保守子集即此形态）/
   精确语义（终审 checker 用）。可空但不可混极。
3. **cut 必须带前件（R3）**：每条学习 cut 表示为"前件配置 ⇒ 必要修复
   析取"；裸正极障碍集不得做几何 cut（前件缺失=cut 在前提变动后幽灵
   存活的病根）。
4. **主动挖对偶（R3，对踏车警报的补充而非替代）**：最强 lift 不必等
   踏车报警——解局部松弛的小对偶问题（micro-oracle）主动挖计数不变量，
   经精确枚举验证后全局求和成证书（先例=供电光环 396 权重→P≥9）。
   漏斗序相应修订：micro-oracle 插在前提数据核查与全局 build-only 之间。
5. **等式挖矿（R3）**：全局不等式近紧时，每条成分不等式都是结构约束
   源——ceiling 命中时的强制条件（恰 N 杆/零箱/内部矩形）即构造规格。
6. **双 ledger 汇报（R3）**：下界账（witness 只抬此账）与上界账（松弛
   证书只压此账）分开记，同 instance hash+同假设下两账相遇才准报
   optimal；资源中止不改任何账。

**管线门序泛化（v2.4 补，2026-08-03 owner 认可）**：本判据的管辖对象不只
"一条规则住求解器哪层"，而是**任何管线的门序设计**——构造线/研究线的工作
流同样是管线，其工序位置服从同一套定律：不依赖下层决策即可求值的必要条件
（§0b-1 的健全影子）必须前置为便宜门；按实测拒绝成本从便宜到贵排；早期门
带证书、终审留给精确本体（§0b-4）。**反面校准：W0 pinned seed（08-03 判
死，19/20 号文书）**——"先钉机身、端口后补"把可毫秒级求值、不依赖任何路
由决策的端口合法性隐式埋进末端小时级大求解，六次 UNKNOWN 被读成"难"而非
"无解"；外脑用一个前置影子检查毫秒判死整条线（129/219 绑不上端口，主会话
复算在 repo 语义下更强）。与五月 47,666 惨案构成同构对偶：那次是违反信息
依赖**硬合并**（把依赖下层决策的规则整条上收），这次是违反管线序**硬后置**
（把不依赖下层的必要条件埋到最后）。执行纪律：新开任何构造/求解管线，门序
须显式对照本节过堂并留记录（17 号处方的 G1/G2/G3 天然即此结构，开线时补
过堂）；外脑交付的构造方案以"待审管线设计"身份进场，不因算术闭合美感免检。

> **Shadow-only 实现注（2026-07-24；non-authorizing）：**
> [23_rule_cut_evolution_protocol.md](23_rule_cut_evolution_protocol.md) 记录由本节
> 判据导出的 test/offline-only 静态台账、一致性门、合同矩阵与 onboarding fixture。
> 协议中的 `full_preflight_passed` receipt 绑定
> `fd015a9ac49a182b242895433a2ff2d2e5ee57de`，只验收该 HEAD 的 test/offline shadow
> 维护面；它不修订 §0b 方法论，不改变 production
> runtime、owner、phase gate、authority digest 或 P1.2 封存，也不授权 production
> 接线、family 晋级、owner flip、P1.2 reseal、持久化 schema 变更或新的数学结论。
> 该历史 receipt 不外推为其他 HEAD 上新生成的 authority。

**管线门内归属四则（v2.5，2026-08-03 夜；校准样本=W0 G1 连通性案例，owner 认可后落）**：
v2.4 管的是门与门之间的次序，本批教训在门的**内部**——子问题模型与其过滤器之间，同一套
归属原则要再用一层。四则：①**支撑域判据**（操作卡②）；②**目标耦合测试**（操作卡④）；
③**报警计量完整性**（操作卡⑤）；④**余量-影子定律**（操作卡⑥）。
校准案例：G1 生成器把连通性（支撑域=单房间 196 格，天生房间级）后置为剥落式过滤器，
三重失效叠加——目标（最大化密度）与连通性对抗耦合未实测（146 格摆 11 台→存活 2 台/50 格
才暴露）、剥落把拒绝转译成接受致「丢弃率>70% 即升级」绊线永零（rejected_dead_body=0 而
stripped_to_smaller 168–238）、全局余量仅 2%（3,392 对 3,325）下影子过瘦——目录供给缺 212 格、
G1 双 INFEASIBLE。事后把连通性搬进房间级生成模型：90 秒 CLEAN 134→138、20/20 全存活，
坐实内聚代价是局部的。执行侧配套（与本节同日生效）：新批任务书必须内嵌已填过堂表
（Plan 席产出）；对抗审查席常设一条「报警计量是否被 fail-soft 清零」检查。
另一半诚实账：内聚买到找好解更快，尚未买到不存在性证明（CORNER ≥111 判定 UNKNOWN
未收敛）——健全上界仍是缺口，见 L2 咨询。


**适用域与收敛声明（v2.6，2026-08-03 夜；owner 拍板「范围=整个科学/求解/数学面，不再按场景限定」）**：
本节原则是**尺度无关**的——适用于科学面上任何「知识×计算」的分解边界：管线与管线之间、
门与门之间、门的内部（子问题模型 vs 过滤器）、证明与检查之间、实验设计与分析之间。
v2.2/v2.4/v2.5 不是三个范围各异的规则，是同一组原则在三种边界上的**实例化记录**。
**默认必试（owner 08-03 夜口径：「只要在做求解方向上的东西都要、至少要去试一下」）**：
科学面任何新批/新方案/新实验，开工前至少过一遍操作卡六问——过堂表哪怕逐项填「不适用」
也要留痕，「试过没咬」与「没试」必须可区分；这一步的成本按分钟计，省它没有正当理由。
**收敛规则（防尾巴）**：新场景默认直接用操作卡六问过堂，不为场景增设新版本块；只有发现
**新原则**（六问回答不了的归属决策）才允许版本号前进；判例库自由增长——判例是校准数据，
不是规则的一部分。**边界注**：发布/治理面另有锁面纪律（PROJECT_LOCK 体系），不由本节管辖；
两面在「计量完整性」上的同构不是巧合，但各自权威独立。


**预设锚点判据（v2.7，2026-08-04；owner 从「假设不能只是有道理、必须卡到结构上」的
观察推出，owner 认可后落）**：六问管的是「规则怎么分家」；本条管更早的一步——**分家
之前押下的结构性预设（ansatz）本身**。每条路线都是先押一个结构性预设（G1=25 房间
网格、22 号=14 条带+单向环、cand C=12×12 滑窗），再在预设之上做归属推理；路线间
推理的分歧全部来自预设的分歧。判据：

**好预设不是搭在问题旁边的支架，是插进问题自带榫眼的榫头。榫眼 = 问题算术里余量
为零、所有解被迫同形的结构。** 卡在被迫结构上的预设几乎不损失解空间（所有解本来
就得这样）；卡在「方便/愿望」上的预设在偷偷扔解，且不知道扔了多少。

**预设来源四分类（按价签档次）**：①**算术被迫**（零余量账逼出「只能这样」）——免费，
随便押；②**对称性/WLOG**——便宜，配一行证明；③**求解器方便**（「切了问题就小」）——
必须标价；④**配方/类比**（「这类问题一般用 X」）——必须标价。③④的价签 = 写明扔掉
的解空间范围 + 撤退线。

**撞车诊断（副产）**：多份独立设计的重合点 ≈ 被迫结构（各自独立发现了同一个榫眼），
分歧点 ≈ 愿望区 = 可谈判区；审查火力应集中在分歧区。

**与余量-影子定律（操作卡⑥）的对偶**：同一枚硬币两面——余量趋零处既是危险区
（一切未建模约束必咬）又是榫眼（预设的合法锚点）。零余量既是杀手也是路标。

校准判例（2026-08-04 六席复核数据）：22 号 14 条带的高度账 54+15=69 零余量、带组成
经审计为**唯一解** = ①类免费锚点，其算术全对站得住；46 边界口的周长陷阱（138 格必
铺满两边）= 被迫结构，三次独立设计（cand C 五月线 / 17 号 / 22 号）**全部**钉死边界
= 撞车诊断实证；G1 的 14×14 房间网格 = **半锚**（供电几何是真结构，但杆并不被迫按
网格摆），其愿望半边（机器不跨房/门洞固定死）恰是 L2 全部松绑候选所在；cand C 的
12×12 stride 6 = 无锚（纯手感数字），生产规模第 0 轮死；H20 全场极性交替 = 无锚愿望，
死。现行 G1 章程八条 R-* 已诚实挂「充分限制」牌 = ③类**已挂牌未标价**，价签补齐挂
L2 批。执行侧（与本条同日生效）：过堂表新增「预设锚点」行（模板已更）；v2.6 默认
必试自本条起含⓪锚点问。

**v2.7 补记（执行配方，2026-08-04 同日；owner 提出「多榫眼可否并用/应否系统性找」，
操作化后落）**：①**榫眼组合规则**：每个榫眼登记时带**前提集**——无条件榫眼（从问题
本身算出，前提集空）全兼容可任意叠加；条件榫眼（在某预设家族内被逼出，如 22 号
54+15=69 之于「横带+单格走廊」）只能与同前提家族叠加，合并判据=前提集之并自洽。
设计真正押注的只是前提集，榫眼是前提选定后的免费产物——「找齐榫眼」既白拿搜索空间
缩减，又提前暴露该家族的零余量脆弱点（22 号 5×5 恰 49=49 即审计找齐后现形）。
②**系统性找法=余量审计表**：把问题的每本资源账（面积/边界周长/台数容纳/端口槽位/
供电覆盖/商品源汇/整除/模数）逐行算「容量−需求=余量」按升序排——趋零行=无条件榫眼
清单（设计必钉）；选定预设家族后重算，新增趋零行=条件榫眼+未来脆弱点。**一张表两用**：
正读=锚点清单（设计输入），倒读=危险清单（余量-影子定律的审查输入）。撞车诊断随之
升级为交叉验证：独立设计在趋零行上应精确一致，不一致必有一方算错。首个实例化挂
W0 老路子批第一步（兼为 G1 八条 R-* 补价签的工具）。
③**条件的来源与产率读法（owner 08-04 追问「条件是哪来的」后补）**：条件榫眼的条件
= 押下的③④类（偶含②类）愿望预设本身——条件榫眼是愿望买来的赠品（付解空间，得
被迫结构+搜索缩减）。设计质量的经济学读法 = **单位解空间代价买回的榫眼产率**
（22 号一注条带愿望换一把被迫结构=高产率；G1 房间网格愿望贵榫眼少=假设 B 的经济学
重述）。递归性：愿望→条件榫眼→内层再押愿望→更深榫眼成树，前提集=路径。**隐藏
前提审计技巧**：推导条件榫眼所用的每条前提必须已申报于愿望清单，推导逼暗桩现形
（例：22 号「带组成唯一」的推导消耗「每带一 riser」前提，该前提即必须挂价签）。
④**理论根基（owner 08-04 追问「自由部分为何存在/方法是否唯一/二者关系」后补）**：
自由两源——问题真余量（被迫结构钉不死的地方问题不在乎、设计必须选）+认知余量
（问题在乎但推导比猜贵，愿望=推导太贵处的替代品）；自由为零⟺一切被逼死⟺解可直接
读出⟺问题平凡，故非平凡问题必有自由。方法必不唯一（解层+路径层双重多样性，区别
在贵贱不在对错）；**方法空间的坐标=自由选择，被迫核=一切正确方法的公共部分**——
「方法不止一个」即「自由非空」在方法空间的直译，撞车诊断由此成定义推论而非经验规律。
风险只住认知型自由（真余量型怎么填都留解；认知型愿望可能杀光解=pinned seed 死法），
价签制度专管认知型。动态观：自由/被迫边界随计算投入移动（证死 101、带组成唯一=
昨日自由今日被迫），探测/审计/证书=**用计算购买被迫性**；全项目一句话=不断把自由
转为被迫，直到残余自由小到搜索器啃得动（上界链=同一件事在另一侧的成果）。
⑤**择愿五启发（owner 08-04 追问「该怎么猜」；判例=外脑五次设计解剖）**：愿望非均匀
随机，择法有先验——(1)**瞄准最贵耦合使之按构造消失**（在问题最痛处人工制造条件榫眼：
16 号万能沙漏/22 号单向环/G1 门洞桩）；(2)**锚在精确闭合恒等式上**（70=5×14、54+15=69
——余量审计表零余量行的构造版用法：既是警报也是框架候选清单）；(3)**新愿望=上一张
死亡证书的逆否**（17 号=pinned seed 死因倒写；fix-and-rerun 批=G1 死因倒写）；
(4)**选死得便宜的愿望**（最脆义务配便宜第一门：H20 守此条故 0.018s 判死——好猜的
标准不是不死是死得快）；(5)**产率评分**（候选愿望比「单位解空间代价买回的被迫结构」：
22 号高产率 vs cand C 滑窗零产率零锚而死）。总纲（08-04 owner 追问
「该以试探为主线吗」后修正——初版「五条全优化检验成本」把两类混为一谈）：**主线是伸、
不是探**。问题是只会拒绝的神谕：它在乎什么从不主动说，只对完整提案点头/摇头——
**测量探针**问小问题（探测臂/pricing 实验，纯学习、便宜），**愿望**问大问题（这副骨架
驮得动一个完整解吗），是从榫眼出发向完整见证伸出的悬臂；其试探价值是保险设计出的
**副产品**，不是目的（纯学习有更便宜的工具，为探而愿=本末倒置）。期望收益 =
中奖概率×构造价值 + 死亡概率×信息价值 − 检验成本：启发(1)(2)(3)(5)抬第一项（伸的
技艺），(4)抬第二项、压第三项（保险）。战略节奏=测量→伸→断口判读→再测量→再伸
（lift-loop 的战略尺度形态；现役实例：探测臂(测)→fix-and-rerun 批(伸)→止损门(断口
判读预案)）。每次死亡产出证书喂回 (3)，与「用计算购买被迫性」同构闭环。

**补记⑥·撞车诊断二分修正（2026-08-05，27/28 号双独立样本实测推出，owner 08-05
认可）**：撞车诊断的两半各加一条限定。**重合侧**：先剔除任务书/ASK 强加的共同输入
（两份都遵守带高多重集不构成独立佐证——伪撞车），剩余的自发重合才是被迫结构候选
（且仍是弱证据，非定理）。**分歧侧**：「分歧=自由区」不总成立——先分类：两边都活着
的分歧是真自由度；**一边在该维度宣告『不可行』的分歧不是自由区，是前提冲突**（一方
把自己的选择内化成了被迫结构），暗桩就在那，审查火力应指向该方的隐藏前提。判据=
该维度上有无不可行断言。实证判例：28 号把「3×3 只进 3 高带」（模板-带高纯度）默认为
铁律并据此建不可行定理，27 号把同一维当自由度用（混装 8 台）直接产出可行见证、
当场证伪该定理——分水岭恰落在被误读为「自由区」的分歧维上。

**补记⑦·零余量第三读法：可判性（2026-08-05，22→27/28 号复盘推出，owner 08-05
认可）**：零余量/低自由度有三种读法——杀手（余量-影子定律：未建模约束必咬处）、
路标（榫眼：预设合法锚点）、**快速法庭：自由度越低的愿望判得越便宜——生死都快**。
第三读法的操作规则：**低自由度候选应插队先试**（判定成本低是无条件的，与成败无关；
低自由既可能「几步构造完」也可能「几步撞死」，28 号与 27 号同料异果即实证——事前
确定的只有「判得快」这一件）。反面教材=22 号首件审计已算出「带组成唯一/y0 仅 4 值/
5×5 恰 49=49」这些低自由读数，却全部归档为脆弱性证据、没人翻过来读「剩余是有限
算术→直接算完试试」，判定实验因此迟到十天；病根=求解器项目的工具形状偏置（默认
布局出自 CP-SAT，纸笔可完的构造不入队）。与启发(4)「死得便宜」的关系：⑷选的是
「败局便宜」，⑦选的是「判决便宜」——后者双向。

**补记⑧·切分质量的两个隐藏维度（2026-08-05，band22 正式门盲枚举现场推出，owner
08-05 认可）**：评价一条切分线，除了「切在天然松耦合处」，还有两问：
㈠ **回传带宽**——切口两边怎么通信？「一次一条否定」式的细通道，在被拒方大量提案时
就是枚举墙；好的切分要在拒绝理由可编译时把它整批编译回上游的选项域（工况允许时
「开工前递整本地图」优于「逐轮传一个字」）。
㈡ **工况相关性**——耦合强弱不是问题的静态属性，是「问题×工况」的属性：同一刀在旧
工况下是好刀（binding↔routing 切分在 master 自产稀疏提案下多年无恙，死候选大多死在
便宜的数数门），换工况就成墙（塞满的设计布局让数数门形同虚设，所有死亡挤到 front
一格，细通道现形为 M5 的 33h censored 与正式门的两千余次盲试错）。切分决策入档时应
记下它成立的工况前提，工况迁移时重审。
修法方向的原则：**先加粗通道，不先挪刀**——挪刀退回巨模型会把切分的全部收益还回去
（工具适配/证明模块化/贵贱门序），而加粗通道（固定布局下预筛端口域、按登记语义钉死
见证绑定）保刀保收益。反面教材=同一约束（口面向走廊）在 27 号的构造里是零成本设计
规则、在门外只能事后挨打（三次实证：M5 33h、正式门 2,259+ 来回、27 号零成本）。

**补记⑧续·「问题×工况」的具体判断方法（2026-08-05，owner 认可）**：切缝
（A 提案→B 裁决）的过路费由两个可测量决定：
㈠ **死因谱**——candidates 死在哪条约束上、该约束住在缝的哪一边（死在 A 模型内
不花钱；死在缝对面才付来回费）；
㈡ **否决带宽**——B 每打回一次剪掉 A 多少候选空间，三档：点否决（nogood，最细）＜
族否决＜**可预编译**（拒绝理由在本工况下是常数，整批写进 A 的选项域，最粗）。
**墙的预言式：死因集中在缝对面 × 否决只有点级 = 必撞墙。**
测法不需专门实验——门的拒绝原因日志本身就是缝健康仪表，三步：①抽样看谱（几十个
candidates 按「哪条约束杀的×住哪边」分类）；②对谱查带宽（大头在缝对面→查可否
预编译/族化）；③**先修通道再放量**（预编译没做完不开大预算；08-05 反面实证：冒烟
收据已给出谱=帽 3 内 2/3 front_blocked+routing 零次，未换动作即开正跑→2,259+ 来回）。
工况复审三触发器：①输入密度变了（稀疏自产提案→塞满设计布局）；②变量变常数了
（布局钉死→front 占用可查表，预编译窗口打开）；③预算量级变了（**删失谱勿当真谱**）。
与「从规则推条件性规则」直觉的合流：死因谱告诉你条件性规则该往哪推——往死因大头、
缝对面、可预编译的那条约束上推（实例：「本布局下 front 被占的口不可激活」）。

## 1. 主线（关键路径，串行）

```
P1.2 CLOSED → P1.3 主体 → P1.5+ → P2.0b → 部署时点 #9a / 发布时点防蓄意内鬼硬化桶
```

### 1a. PR2 硬化桶（已裁定延期到发布时点；执行序 = 排期卡正文，此处仅摘要）

阶段1（轻）：#8 argv0/contract digest + #9a 仓库侧收尾 + #6 决策确认 →
批2a：#2 受控 loader + #3 read-once（带 resume/frontier/replay 纯核心抽取）→
批2b：#5-B2 候选域独立枚举（带 outer_search 接缝；批后收 306s 巨无霸测试）→
#5-F part3 设计 spike（带 fused child 实验）→ **#1 最小 TCB 闭包**（吞
l0-snapshot 拆分 + lazy import）→ 阶段4：#9b OS 级写隔离 + #9c 原生 TOCTOU。
pytest 提速余项已全部溶进上述批次（不独立成批，绑定表见排期卡）。
**owner 修正（07-04 晚）：P1.2 收口前提至少含 #1**——先深化再收口。
**owner 再拍板（07-06，同日两变、以晚间为准）**：早间曾扩「收口前提=整条
backlog 编码项」；**同日晚间收窄**——厘清「内鬼=故意而非手滑」后（手滑/外部
篡改已被常开的字节 sha floor 拦死；结构锚/TOCTOU/OS 隔离只对忠实 reseal 后
的蓄意内鬼有意义），所有「仅防蓄意内鬼」硬化（#8 深化/#2/#3/#5-F/#9b/#9c/
Option B）**延期到发布时点、非 P1.2 收口前提**→编码前提实质清空（#1 核心
已做、剩余全在延期桶内），四阶段序转为发布时点执行序。#9a 维持部署时点。
详见记忆卡 deliberate-insider-hardening-deferred-to-release。

### 1b. P1.2 收口（2026-07-07 CLOSED）

十项 close 条件见 [12_go_criteria](12_go_criteria.md)（PR2 TCB 收缩是第 10 项；
07-06 晚 owner 已行使该条「或 owner 明确修改 close scope」活口——防蓄意内鬼类
硬化延期到发布时点、非收口前提，见 1a 尾注）。
路径（owner 2026-07-06 晚拍板版，编码前提已实质清空）：冻结仪式 → 收口外审
（GPT Pro relay 按 owner 需要发）→ **审到 owner 判定足够为止** → owner 关手动门。
该关门动作已于 2026-07-07 由 owner 真实输入完成（gate JSON `owner_manual_decision`，
`status=closed_manual_owner_decision`）；三轮换轴收口外审共 24 簇、
0 个真·上-TCB soundness 洞。07-06 冻结仪式已在主线分支执行（冻结树
`c9b41b3`、门禁全绿、送审包+7 切面提示词已备）。
**「三连 clean 计数」语义澄清（owner 2026-07-06）**：那是 owner 当时图方便的
说法，不是硬判据——实际判据就是「外审到 owner 觉得合适为止」，轮数可多可少；
gate JSON 的 `required_consecutive_clean_full_reviews=3` 与关门确认字段里的
"three clean reviews" 字样保留为机器兼容值（同 `p1_3b_*` 模式），checker pin
死了这个数字，改字段值属于 checker+tests 连锁手术；字段保留为机器兼容值，不再是待收口事项。
配套部署时点任务（不阻塞收口判定、但在真发布前必做）：#9a 生产字节重钉、
真实 campaign→seal 实跑、dependency floor manifest 在 CachyOS 生产机重生成。

### 1c. P1.3A attach spike → P1.3 主体

spike 只回答一个问题：CP-SAT Python 路径能否把 cut 及时变成有效 master
约束（[09](09_phase_1_3_plan.md)；GO 标准 = prod-scale 跑通且 wall-clock
退化 <50%）——已判 GO（07-10）。**收敛性仍是全项目唯一真正的研究级风险**
（cut 体系接上后收不收敛没有理论保证，只能实测；主线解不动时的动作=换
进攻方法（研究线，见 §0），不降命题——L11 属另开新线候选、非退路，
台账 #2）。
主体 = production integration：F1/F6/F7 typed lowering 已落地（F5 为
shadow-only、无 lowering，转正挂 F5 转正批；F2/F3/F4/F9 LEGACY_DIAGNOSTIC；
F8 retired）；Stage B 工程面完成，当前只待 B6 owner promotion。

真生产 registry 注入、route schema 拍板、F2 max-flow witness、
**F3 active_port_witness 硬门**（生产默认开启前二选一）。

### 1e. P2.0 吞吐认证（owner 2026-07-04 改判**必做**；P1.2 历史 scope exclusion 不适用于 P2.0）

P2.0a 残余：toy path-phase 证书 + prototype checker E2E（设计稿已含 v3 终审）。
P2.0b（P1.3 后）：按吞吐稿 §6 落 TP7-S/TP7-D 证书链 + 伪造红测。
P2.0c：D1-D8 实测与 FIFO/game 语义对齐。
形式化侧已预置：TP7-S 等式键边界 4 条定理 + 盲方 T1-T6 必要性陈述蓝图。

## 2. 支线（与主线并行，不碰生产代码/锁面）

### 2a. P3.0 轴 A：范式数学的 Lean 机器检查（已开工，68 条定理落 main）

现状：六模块 68 条、公理审计干净、两轮独立外审（7 会话+盲对拼）全回收。
余项（不依赖主线）：盲方 T1-T6 必要性定理族、C5b 覆盖容量 owner lemma、
TP7-D 验收语义、工程 W 定理对象（availableCuts/SoundAtScope）形式化。
~~等待解锁的：F8~~（**取消，2026-07-08**：owner 游戏规则确认 F8 前提为假
（电杆不需连网），整族退役，形式化 F8 不再有对象；见 1c 注）。
纪律不变：formal/ 不进认证 TCB、不改 gate（16 号 §6.4 政策原样有效）。

### 2b. P3.0c 轴 B：证书侧 proof logging（**本次排入**，待开工）

打"CP-SAT 编码忠实性单点"（瓶颈审计第 2 硬骨头）的终极解。七阶段
（P3.0 设计稿 §P3.0c）；**第一落点 = Phase 0+1：binding 子问题的 PB
独立重建 + VeriPB 证明日志 sidecar 复验**（2-5 周 PoC）。
关键设计约束：**独立重建**（不从生产代码导出编码，保持异构交叉验证价值；
与 PR2 #5-B2、I1 是同一笔投资的三个面）；纯旁路，不写生产路径。
执行位：数学面线程（形式化线的自然延续）；与主线零文件交集。
后续阶段（core 切片器→routing 分流→有理 Farkas checker→nightly 化）
按 PoC 结果再排。

### 2c. TNS 全域无解证书链（设计稿完成，实施未排）

O-1~O-16 义务 + ghost-use inventory（TNS 稿 §6）。数学侧已在 formal/
（覆盖链 + Finset 版全套）。排期建议：P1.2 收口后、P1.3 期间的独立批
（它动 producer/supervisor/publisher 的负向面，收口冻结期内不动）。

## 3. 圈外（明确不做，改判需 owner 裁定）

Q15 跨 base 迁移（Phase 2+）、Q16 多 base 联合优化（Phase 3+）、
Q1p partial-assignment 完备性（缺数学对象）、S_global 收敛性定理
（实验命题）、PBLean 自研验证器（轴 B Phase 6，远期）。ATS/F\* 验证语言
已评估排除（2026-07-11 owner 问询，评估记录
`docs/research/formal_verification_languages_assessment_20260711/`：两者均
不解 CP-SAT 黑盒判定与 spec 忠实性两个真瓶颈；远期 verifier 形式化若做，
以 Lean 优先、与 PBLean 线同向）。

## 4. 拍板台账（owner 决策集中登记；#1-#6、#9-#11 待决，#7/#8 已决存档）

| # | 事项 | 现状 | 影响 |
|---|---|---|---|
| 1 | Q1 状态改写（拆 Q1a/Q1p 进 05 号） | 建议已成稿（Q1a 稿 v2），待裁定 | 05 号 Q1/Q14 行的分级与措辞 |
| 2 | L11 命题降级（钉 blueprint 只证剩 41 个） | 挂起。**owner 2026-07-13 口径纠正:此项定位=「另开一条新线」的候选,不是本目标的退路——本项目目标(全局 max_lex certified)从一开始就不设降级退路**;旧文「最后退路/Plan B」措辞是当时记录不清 | 若将来立项,属新线、不改变主线目标;主线解不动时的正确动作=换进攻方法(见批C 线实测与数学面盘点),非降命题 |
| 3 | GitHub 远端推送（main 停在 07-01） | 待定；建议从 C:\codex pj\zmd_pj 副本推 | 机外冗余 |
| 4 | P2.0b 实现规格批准时点 | 终审判"修复后可作实现规格"，修复已完成 | P2.0b 开工前提 |
| 5 | 168h 执行层债余项排期（OOM 配置雷等） | 部分溶入批2a/2b；余项未排 | 长跑稳定性 |
| 6 | 冻结输入正确性加固（pose 枚举独立重验） | B2（批2b）覆盖一部分；抽样穷举比对未排 | 瓶颈第 6 条 |
| 7 | 批C 四项口径 | **✅ owner 2026-07-13 晚已全拍**(真实输入):①组织性触发判定=「两条腿」(无害性/等价性用 cap 口径矩阵+门6「触发>0」格接受注入式对照演习,自然触发降级为观测项);②alias 口径=一跳为界,多跳归发布时点防内鬼桶(07 号规格已加订正注);③F5 转正批=B6 先走、F5 紧随不合批;④矩阵零头(rollback 演练/多 rect/oracle 开销/prod 层演习点)07-14 白天清 | 批C 收口判据落定;promotion 包按此口径组装;详录批C 计划 01 §5 |
| 8 | **prod 形态适配批插入 B6 前**(07-14 零头演习发现) | **✅ 07-14 已落地**(执行侧按推荐自主推进):根因=F1/F6 投影 `master_scalar_coercions=False` 比 live master(`_pose_mode_token` 对所有族一律 `str()`/`int()`)更严 → 对 prod frozen 的 int orientation(`boundary_storage_port`)fail-closed、flip 后 prod 空动作。修法=3 调用点(state_snapshot F1/F6 + lifecycle live 投影)对称翻转 `=True` 忠实镜像 live master;函数默认严格模式契约不变。双对抗审查(codex soundness 攻击 + opus 镜像忠实性/完整性)均 **0 BLOCK**;三翻转 mutation-verified 守卫;reseal 双文件(V99 dict + JSON sink sha + checker 自 sha,semantic_projection 数值证实不动);全 cuts 857 绿。规格=批C 目录 `02_prod_form_adaptation_batch_spec.md`。**剩 B6 flip(owner 手动)→ F5 转正批** | codex 2 CONCERN(强转放宽输入 schema)定为已知非阻塞=忠实镜像必然、冻结件 int-only 不可发生、发生则 step-8 fail-closed;真要收紧归 artifact/freeze 层(发布时点防内鬼桶) |
| 9 | **PIC-4/PIC-5 证据口径**(文档扫描 07-17 暴露) | 待表态。roadmap 管理口径认为批C 收尾后只剩 B6;但 PROJECT_LOCK 口径仍把 PIC-4/PIC-5 列为 B6 硬前置,而仓库里尚无「prod 形态修复后 APPLIED>0 且完整走完失活/回滚」的归档证据(批C 演习全部 0 cut 生成于形态 gap 修复前) | 要么正式接受现有 harness 层证据充分,要么 B6 前补做一发 prod 注入演习归档 |
| 10 | **front-clear lift 默认值翻转** | 待过夜长跑判读(07-17 晨)。当前维持 default-OFF;lift 语义三面实证正确、OFF 零回归,但 ON 在 30min×单 worker 下 fixed/automatic 均解不动 6×6 锚点;presolve off 已确认为 lift-ON 必要操作配方 | `rab_sep_promotion_20260716/06` 终判;翻转=owner 手动门 |
| 11 | **研究线调参演习 go/no-go** | 待拍板。未测杠杆=portfolio×多 worker(内存外推 55-100G,本机余量存疑)/小时级长预算(首发在跑)/warm-hint 工程;赌注=lift-ON master 证出 INFEASIBLE 即锚点合法上界证书 | 决定研究线下一步火力投放 |
| 12 | **canonical 修正批（四件套+公理 kernel 合批）** | ✅ **08-07 落地收官**（owner 拍板合批；worktree freeze-ritual 完整连锁 2ea99eb+27969ca，合入 main `fab718a`，main 双 gate 绿）：kernel=semantics.axiom_kernel（A1-A11）+四件套+箱槽数口径+7 条旧条款推导注记；canonical 40,371B/b675fb6a…；`mixed_commodity_flow` 与 `item_admission_port_exclusion` 两处随批修正 | 完成；4 条文本审查问题攒 GPT Pro 包 |

## 5. 风险对照（2026-07-02 瓶颈审计 7 条硬骨头 → 本图位置）

①算力硬墙 → 1c 见真章 + 研究线（§0，规约为 4 小实例）；②编码忠实性单点
→ 2b（终极解）+ 批2b B2 + I1（已落）；③cut framework 尚未 certified
promotion（F1/F6/F7 typed lowering 已落、F5 shadow-only，只待 B6 owner 门）
→ 1c；④floor manifest 占位 → 1b 部署时点；⑤168h 执行债 → 台账 5；
⑥冻结输入只证"没变" → 台账 6；⑦手动门 owner-only → 设计如此（1b 终点闸）。

## 6. 文档修订台账（过时点及处置；07-17 文档卫生批全量扫描后更新）

| 文档 | 过时点 | 处置 |
|---|---|---|
| 本文档 §0 | 07-11 起的地质层堆积（三层时间断层、F5 旧口径两处、台账标题与内容矛盾） | ✅ 07-17 重构：§0 工作线快照 + 0a 里程碑指针表 + 0b 方法论；§1c/§5 F5 口径统一 |
| 06 号 | 止于 07-12；RFC-003 同页矛盾；阶段命名段新旧口径同段共存 | ✅ 07-17 增量段+终态化改写 |
| 21 号名词表 | F5 旧口径；缺工作线/批次名录与命名规范 | ✅ 07-17 扩建 |
| NAV_MAP :63 | "RFC-003 pending" 笼统 | ✅ 07-17 精确化（工程面已落，剩门6 随批C） |
| PROJECT_LOCK :388/头部 | 07-11 addendum 含 F5 旧口径；Updated 字段落后正文 | ✅ 07-17 最小修正 |
| README | 当前状态段落止于 07-12 前后；若干 F5 旧口径行 | ✅ 07-17 补七月篇章+定点修正 |
| **01 号 §1.4 / 02 号多处** | F5 旧口径、CutScope 旧 schema（pre-B5a）、source digest 字段列表过时 | ⏳ 待深修批（math-heavy，含 02 号 §3 全族现状矩阵重写）——07-17 扫描清单存 `.artifacts/doc_sweep_20260717/` |
| 研究文书（doc15 开篇 relay 注记、F-6/①′/命题N-UBC 消歧注） | 会话泄漏与命名消歧类 | ⏳ 低危，随各文书下次实质修订搭车 |
| 05 号 Q14/Q1、12 号、08/13 号 | （07-05 处置未变） | 已加注/史料化标注，不动 |
| rules/canonical_rules.json :422-425/:454-458 | 混流无例外条款已定谳写宽；限制口省略理由已判过时（结论保留） | ✅ 08-07 已随 §4 #12 canonical 修正批落地（fab718a，terminal_clause/rationale_restated 两条目承接） |

## 7. 阅读入口（新会话/新协作者按此序）

1. `PROJECT_LOCK.md`（release 红线）→ 2. 本文档（总图）→
3. [06_current_status](06_current_status.md)（当前状态）→
4. 排期卡正文（主线执行序）→ 5. 对应阶段的细节文档/研究稿。
| 08-03 | **剪枝 v2 P2 全线落地（记忆管道修复 + 冻结迁移 + 主批，merge `a7af533`/`d693f89`）**。①**前置三修三轮**（载荷 summary/机器消息跳注/跨层 find + 两轮加固）：P2.2 按 **§3d-bis 军备竞赛退出判据**（新立）退出两张噪声卡的 error_regex 赛道（历史真阳 0），蛇吞尾排除做成 hook 机制（governance_target），find 只读全路径不变量+degraded miss 如实申报。②**cc_memory 冻结迁移**（owner 批）：主席亲判 15 项——3 处迁出（cut 触发机制/pytest-forked SOP/codex 不自动读）、12 处原地存档，最后写入=存档地图条目+truth fact 订正（`e6840c9`）。③**主批+修复批**：记忆层扫描器 `memory_reference_scan.py`（orphan/dangling/never_read/said_card 四 flag，首跑真阳 orphan 1 + 案例4 实锤）、docs 两小调后稳态 0 候选、冻结机制面（boot 横幅/写警告/hook 档案口径/post_tool_shadow 解线）、zmem schema 放宽（pitfall 不再强制 error_regex）、**记忆层 265 测试首次挂进 preflight [memory] lane**、authority pin successor 登记（`ddc75270`，循 8292983 先例主席授权）。codex 对抗审查 BLOCK 15 条→§3d 分诊：修 11（逐条用 codex 落盘 PoC 红前/绿后翻面）、内鬼类 4 声明（07-06 裁决）、deliberate 1 接受。合并后独立 full preflight 19+1 门全绿。**基线判定**（`p2_first_scan_findings.md`）：docs 0 候选稳态保持；memory 9 候选逐条核=**未兑现记忆欠账 0**（静态基线，新 item_id 才是信号）。剩余：P2 收尾批（查漏 LLM 镜头薄 runner）+ P3（两度降级） | 分支 `prune/p2-prefix-fixes-20260803`、`prune/p2-main-20260803`；`.artifacts/prune_v2_20260803/`（design_v2 §3d/§3d-bis、p2_first_scan_findings、preflight 双日志）；codex 封存 `/tmp/codex-security-scans/zmd-pj/6b2fb40_*` |
| 08-03 | **剪枝 v2 P2 整线终结：查漏镜头收尾批 + 首轮真跑（merge `0a4e44c`）**。①确定性外壳 `memory_gap_lens.py`（assemble 指针化证据包 + verify 落地核验防幻觉，无 apply 通路 AST 闭合白名单钉死）：codex 聚焦审查 BLOCK 4 条全修（空白 quote 长度闸/SQLite immutable=1 承 mem.py 先例/黑名单改闭合白名单/surrogate encode-first+候选级 drop），每条 codex probe 红前绿后翻面，合并后独立 full preflight 全绿。②**首轮 LLM 座席（opus）：11 条候选，落地核验 11/11 存活零幻觉，主席裁决 11/11 全采纳执行**——7 条 CORRECT（两张 L0 状态卡现势订正 `d7cbeb9`：批C/ab16 收官入卡、M5 头条补 front 修正前口径条件；5 处文件记忆 description/索引漂移修复）+ 4 条 ADD（对外介绍口径卡/自加固循环失效模式卡/Fable-only 拍板 Why 补录/fixture 绿灯一般化判据）。③**副产实锤**：eval 假红溯源发现主树 `.index` 停在 07-19——P2.2 清空的退役 error_regex 在活 hook 里半月未生效（卡=真相源、hook 消费编译缓存），重建后 34/34 绿；「build-index 必须在主树跑」入纪律卡（`51ad1cf`）。P3 文档语义镜头维持低优先级 defer | `.artifacts/prune_v2_20260803/`（p2_first_scan_findings、gap 座席产出 scratchpad 存档）；`.prune/memory_gap_{evidence,candidates}.json`；分支 `prune/p2-gap-lens-20260803` |
| 08-03 | **W0 D6 验证链从未真跑过——两层互相掩护的缺陷挖出并修复（`3c7680a`）**。承 ab16 收官「6 硬编码路径测试耐久修复」欠账线。①表层：`test_w0_d6_{gate,replay}.py` 的外部输入路径写成 `~/下载/w0回复/`，真实目录是 `~/下载/gpt回复/`，而仓库内 `cleanroom_rederivation_20260718/15_w0_recon_artifacts/` 有逐字节同份 tracked 副本（三方 sha256 一致）→ **45 条测试自落地起 100% 静默 skip**。②被掩护的深层：`project_lock_sha256` 钉的 `a2ec971f…` 声称「当前 checked-in successor」，实测在 `PROJECT_LOCK.md` **51 个历史版本里零命中**（也不等于被 revert 的 `62bc65f` 时点值 `114ea93e…`）=未落地状态算出的幻影，钉在 5 处代码+README；那 45 条只要真跑一次就必红，因 skip 三周无人知。③修法：路径改指仓库内 tracked 副本（测试自带期望哈希即时验证）；lock pin 改钉真实 `64a68024…`——安全依据=D6 历史 root 绑定 `e8130589…`（`57c8b352`）到当前的 110 插入/123 删除**全部落在 AB16 段**，§3B「W0 D6 research-only artifact protocol boundary」逐字未变，新版头部明写 `prior certified, W0, P1.2, Stage B boundaries unchanged`，历史 root 绑定值不变；antecedent fixture 连锁 `94f72b64…`→`7de91e64…`（lock scalar 进 canonical hash，门禁解释器独立重算复核，非新 solver 结果）。**结果：全量门禁 skip 170→125，45 条复活全部通过，独立 full preflight 20 门全绿**（首轮那条 `test_wait_observer_parent_death_sigkill_releases_stopped_child` 经 stash 对照+隔离单跑+二次全量三重复验判定为负载敏感 flaky，非本批回归）。同线核实：R11 过期文案已由 `d5386c4` 修、`host_gate_quarantine/` 已不存在，剩 2 处硬编码路径为 `pytest.fail` 诚实形态不动。**新登记同族隐患**：`test_placements.py` 5 处「池空即跳过」（当前三池非空不触发）、R4 那 4 条等的 `.artifacts/track_b_r4_…` 产物在本机含外置归档全不存在 | 本行；`silent-skip-hides-two-layer-debt` 记忆卡；`.artifacts/prune_v2_20260803/preflight_w0fix{,2}.log` |
| 08-03 | **剪枝 v2 P2 自检轮：扫描器吃自己的狗粮抓出自身判定域缺陷并修复（`fe5fa2b`）**。用当天的记忆扫描器验收当天的卡片工作：orphan/断索引 0、said_card 9→6（当天立卡兑现 3 条历史承诺）；但 dangling_wikilink 14 条里 10 条实为**健康跨层引用**（`[[链接]]`只在引用卡同层解析——三层记忆系统里跨层引用是被鼓励形态,判定域写窄=flag 被噪声淹没）。修=判定域扩为三层并集（档案层 `immutable=1` 只读零侧车、缺失降级宁多报不崩），真仓 **14→4,剩 4 条真悬空恢复 FYI 信号价值**（=值得写而未写的卡）。测试改写钉旧语义 1 条+新增 3 条,红前证 4 条全红,43 passed,独立 full preflight 20 门全绿。注记:不违反 §3d-bis（那管加精度,此为在错误集合里查找）。副产入卡 `sqlite-readonly-immutable-sidecar-trap`（裸 mode=ro 侧车坑 08-03 一日三咬,已修先例不自动传播,委托任务书应显式点名仓内先例符号） | 本行；`.artifacts/prune_v2_20260803/design_v2.md` §5、`preflight_wiki.log` |
| 08-04 | **W0 双咨询回复到货并闭环：六席复核裁决 + 我方文书勘误批（22/23/24 号 `2808653`、裁决+勘误 `5cbb032`）**。①23 号（L2 方向裁决）四指控全坐实且②④比它说的更重：PROBE_REPORT §2 三条「矛盾」全撤（主病根=实测找到值当上界用；健全口径最紧支 3,359>3,325 不闭合，「压向松绑」降级为倾向性证据无证书）、R-PAT-CONN 实现=loose 并集口径弱于登记语义（855/2593=33% 入册 pattern 多含桩分量，strict 过滤供给 3,113→2,749、只删列两轮 INFEASIBLE 更稳，但 C4 零 seam 组合论证 witness 侧缺口登记）、证据锚点从中间态 probe_results.json 改钉 raw 终值；`g1_pattern_generator.py:431` 同口径错登记为重生成级欠账。②22 号（从头征法）=条带+单一有向环+live-pose 精确覆盖新路线：全部【已证明】算术重算无一错，但三处承重洞（5×5 台数零余量+孔位 mod5 约束/3 高带放不下杆真实杆容量≈40/首选核心宏 final 输入无极性正确走廊）。③23 号 CG 对偶界机器：逻辑健全（Lagrangian ε_f 形式可用 CP-SAT 超时 bound）、列空间完备性前提被省略、决定性盲区=pricing 界质量（phase-A bound 540s 从未离开 packing ceiling）。④cand C 考古：owner 记忆的「切块+目录+选页」坐实为 2026-05-21 列生成线（非六月），生产规模 RMP 第 0 轮 INFEASIBLE 死，与 23 号同 paradigm 反角色；仓库两处 `[[v14-review-findings]]` 断链订正。⑤边界七族带孔补证臂已起跑（新证据根）。**待 owner：L2 方向拍板**（菜单=①便宜补证已在跑/②B 侧证书机器先做 pricing 界质量便宜实验/③22 号新线试点先补三洞前置检查；语义收敛+:431 为所选批第一步欠账） | `docs/research/w0_front_aware_20260803/CONSULT_VERDICT_20260804.md`；`.artifacts/w0_probe_hole_20260804/`；wf_ab57bbec-a53 |
| 08-04 | **§0b v2.7 预设锚点判据（owner 从「假设不能只是有道理、必须卡到结构上」推出并认可）**：操作卡加⓪锚点问（七问）——结构性预设必须卡在问题算术的零余量被迫结构（榫眼）上；预设来源四分类①算术被迫免费/②对称WLOG便宜/③求解器方便/④配方类比（③④必须标价=扔掉的解空间+撤退线）；撞车诊断=独立设计重合点≈被迫结构、分歧点≈愿望区；与余量-影子定律互为对偶（零余量既是杀手也是路标）。校准判例：22号带高账零余量=①类锚（构成唯一解）、边界钉死=三次独立撞车实证、G1 房间网格=半锚（愿望半边恰为 L2 松绑候选全部所在）、cand C stride6/H20 极性=无锚而死；G1 八条 R-* =③类已挂牌未标价，价签补齐挂 L2 批。过堂表新增「预设锚点」行 | 本文档 §0b v2.7 |
| 08-04 | **L2 方向拍板（owner）+ 三件收官**。①owner 拍板：主攻 **fix-and-rerun**（修 evaluator strict 语义+`:431`→连通性内聚进生成器→全量重生成+G1 重跑；owner 原意「老路子」指证明机②，听排序论证后改押 fix-and-rerun，②降为止损门后的梯级、22 号备胎入库）。②边界七族带孔探测臂收官（`.artifacts/w0_probe_hole_20260804/`）：七族实测齐停 101（与无孔 126 平台同构），BOTTOM_I1/LEFT_J3 **证 OPTIMAL=101** vs 各自 packing 上界 129/134——**首次拿到证死的 valid 天花板且它比面积账级上界低 28-33 格**（08-04 晚订正：证死对象=loose valid 天花板 101、strict≤101；129/134 系上界读数非可行 witness——「账虚高≥28」成立、「真能装 129」未证，codex refute 二轮抓出）；健全分支穷举仍不闭合（各支 ≥3,359>3,325）。③「裁判自产文书异源复核」家规首轮闭环：codex refute 席过审 CONSULT_VERDICT+PROBE_REPORT——核心错误（实测值冒充上界）未复发，4 项措辞精度指控成立并修正（`7b36e4c`：证书距离 67→至少 68 且 hole 对偶亦承担、576 加 catalog 限定、252-540s 实际时长、「缺健全上界」→「缺足够紧的」）；家规入记忆卡 referee-authored-docs-blind-spot。④fix-and-rerun 批任务书备好（含 v2.7 新版过堂表：预设锚点行带前提集+余量审计表 v1 首个实例化）**待 owner 过目+任务书自身过 codex refute 后开工** | `.artifacts/w0_fixrerun_20260804/opening_brief.md`；`.artifacts/w0_probe_hole_20260804/SUMMARY.md`；`7b36e4c` |
| 08-04 | **fix-and-rerun 批执行完毕：止损终态（BUDGET_CENSORED，禁外推家族死刑）**。代码侧 11 笔提交于分支 `w0/fixrerun-20260804`（strict 单根语义收敛/动态 maxK/连通性内聚单源流+strip 废除/O 义务 gate clause 6 fail-closed/配对 loose 对照解计量——corridor_tax 结构性恒零被 codex BLOCK 抓出后重设计，计量只在被拒侧运行）；三跑重生成协议照旧（参数逐一复原自旧 manifest），并集 760 签名，**strict 无孔基线供给 2,544 vs 3,325 缺 781**（旧 loose 3,113/缺212、旧 strict 重滤 2,749/缺576；算账口径经旧并集复现 3,113/1,672/19 交叉验证）；master INFEASIBLE 收据（gate_union，0.27s deterministic，核=assume_class[6I3]+九cover+total_bodies，receipt 闭合）；台数闸 241≥219 不触发。判读=止损：CLEAN 251 目标 193 未判（UNKNOWN 删失），非 strict 家族死刑。连通税计量：1,090 例排除连通性单独致死、72 例 loose 亦未判、**零税「未证」仅无一坐实**。文书收尾 `f3e624b` 过 codex refute（15 条全成立全修：两条 high 系证据等级病三、四次复发——loose UNKNOWN 并入否定、incumbent 差 28 当真实代价）。四路待 owner：①加深预算定向重生成（默认建议，需 owner 点头）②松绑（价签包）③证明机②（实验包）④22号（补洞包）——三包已交付 ~/下载/（band22 v2 修补中）。merge main 待右线 M5 安静 | `.artifacts/w0_fixrerun_20260804/`（acceptance/supply_account/regen/gate_union）；分支 `w0/fixrerun-20260804` |
| 08-04/05 夜 | **四份回件验收全录 + 见证对齐 + 定理证伪 + ③ 暂退，四路重排待 owner**。①**四场验收工作流、十一席**（25/26/27 每场 1 存档席+2 独立复核席；28 号 1 存档席+1 撞车复核席）逐字入库并逐条裁定：25 号九条 `R-*` 价签八个头条数字全部独立复现（五笔数字修正账：HOLE 保留率 0.07183%、PORTAL 共同分母 4.59%、CORE 买回 ≤7,441、杆锚点 6.816%、隐藏前提漏一条杆预算暗桩）；26 号数学全立、harness 我方机跑通，并抓出 `INFEASIBLE→bound=0` 的 fail-open（红-before-绿收据：未打补丁分析器在全不可行合成输入上真发过一张 `GO_CERTIFICATE_ALREADY_REACHED`）。②**27 号 band22 坐标级见证**：266 设施 + 25 杆 + 1,143 路由格，两席从零重算六谓词零反例；夜里对齐探路把 **291/291 位姿在官方冻结池里唯一解析**（`ambiguous_matches=0`、零偏移换算）、`matching_map_boundary` 未测点的**前提根本不存在**（模型无「资源格」概念，约束已烤进 136 个位姿）、非激活口 front 被机身占用经官方权威九条证据链确认合法（暴露面 11/1,176 全合法，628 个激活口 0 违例）。**但整份见证仍是 research/consultation-aligned**——`VERDICT.json` 首行 `no official checker was run`，端口项只重算精确计数、binding CP-SAT 未跑，路由项仅必要条件；两轮独立复核的范围是**机身与供电子范围**。③**28 号（同一份 v1 送包被意外发出第二次、另一独立会话作答）的「整族不可行定理」结论被证伪**：承重收据 = 27 号 25 根杆实测覆盖 219/219 的直接坐标反例（`Q=20/R=62` 那条旧不等式收据经复算作废——脚本逐段取 floor 与 28 号「整带自由列总数取 floor」定义不符，按原定义 `Q=22`、`3Q=66` 不等式反成立）；两处暗桩=模板纯度前提 + `f_i` 只数全高自由列。**其 §5/§8/§10 全部方向性指挥作废。**④**③ 上界证书路实跑**：主输出字面值 `INVALID_CALIBRATION_FAILED`，补入无 cap 单变量校准后二次重判 `NO_GO`（作用域=旧 g1 连通语义 + cap-3）；统一界 3388 距证书线 64、29 跑零界移动；三道门只做掉 ①③，② 未做 ⇒ **按「暂退（有范围止损）」记账、不写关门**，终局收口欠一次 HEAD 重打重跑（③x，约半天，我方推荐先不做）。⑤**四路重排（待 owner）**：④ band22 暂定主攻（卡点=摄入 driver 不存在 + 两道官方 CP-SAT 门 + 终端固定见证复验），③ 暂退，①② **条件性降级带回滚条款**（④ 任一门判红且不可局部修复即自动重开）。口径纪律：`L` 走 research lower ledger（入账条件按 `00_charter` G3 = 独立 strict checker 零 issue + 复算 ≥(42,6)），**不套用 production CERTIFIED 铸造/发布链，也不复活已关闭的 P1.2 gate**；2,544 一律写成供给上界、781 写成短缺下界。⑥家规二轮闭环：两份自产文书过 codex refute 席，八项处方全部回源核实后落地（`3910ce7`） | `docs/research/w0_front_aware_20260803/CONSULT_VERDICT_TRIPLE_20260804.md`、同目录 `DECISION_PAGE_20260805.md`；`docs/research/cleanroom_rederivation_20260718/{25,26,27,28}_PROVENANCE.md` 与同名交付目录；`.artifacts/w0_fixrerun_20260804/band22_alignment/`（`VERDICT.json`、`alignment_*.json`、`registration_placement_solution.json`）、`.artifacts/w0_fixrerun_20260804/pricing_exp_run/`（`decision.json`、`decision_with_solo_calibration.json`、`failopen_regression_check.json`）；`preflight_c17_night_closeout.log` |
| 08-05 | **M5 存在性复验终局（现行池 f05b1291+front 修正语义，owner 判「有限时间跑不通」停机）**。承 08-03 M5 卡订正的「待现行池复验」欠账,机器空窗自主开跑。尝试1(刀4 原公式 w6/p3/s3/fixed+软cap28G,42G/20G cgroup)=**9min OOM,62G 修订条款对现行池不再成立**(swap 恰顶 20G 帽、RSS 35G 仍爬;池扩 ~18% 后包络越界;cgroup 圈死策略生效,系统零波及)。尝试2(降 w4+软cap22G,防 OOM 轴)=**master 预算内找到可行候选布局**(存在性 master 半场肯定),但 binding↔routing 无帽枚举(py-spy 多针钉在 binding_subproblem.py:1396,CPU/wall≈1.0 满产)**磨 ≥33h 无终态→owner 拍板停机,枚举 censored@33h**(CPU 终值 1d8h46m,内存峰值 29.4G+swap 峰值 17.1G,总足迹全程稳 ~20.5G)。**净结论三条**:①62G 条款失效→1F 生产内存条款需随池版本重标定;②master 可行≠认证级存在——**存在性问题现行口径下回到 OPEN**;③认证枚举墙(07-14 八人会议钉的真墙)在 front 修正后语义下**深化约两个数量级**(同 cell 649s→≥33h,≥183×,censored 只给下界;初记「四个数量级」为算术错,08-05 P4 证伪席+codex 席双独立抓出订正),「可行域只增不减」的乐观预期对 master 层成立、对认证门不成立。M5 卡已就地订正(summary+正文终局段,build-index 主树重建+eval 34/34)。执行纪律注记:枚举帽 env 未设=无帽真枚举系发射后显式决策(加帽终态=ALT_CAP censored 对存在性无价值);监控形态收获=cgroup 内 DONE 标记在整 cgroup 被杀时失效,watcher 须兼看单元终态 | `.artifacts/m5_revalidation_20260803/`(NOTES.md 全程记录+sampler 双日志);`p1-3-batch1-m5-current-20260712` 卡 08-05 订正段 |
| 08-05 | **owner 双拍板**：①**④路开工**——band22 见证 (42,6) 转正线：写摄入 driver+跑官方 binding/routing 门（预算阶梯+censored 入账，M5 33h 枚举墙为成本警报；见证自带已过合同复核的可行绑定/路由方案=易区假设待实测）；②③①三路维持关门/降级/失去动机。②**§0b 补记⑥落地**（撞车诊断二分修正：伪撞车剔除+分歧侧「不可行断言=前提冲突非自由区」判据，27/28 号双样本实测推出）。M5 右线终局（owner 拍板停机 censored@33h）互核笔记在案：右线「master 可行≠认证存在（回 OPEN）」与本线见证构成钳形——见证过官方门将同时关闭该 OPEN | `.artifacts/w0_fixrerun_20260804/m5_crosscheck_20260805.md`；本文档 §0b 补记⑥ |
| 08-05 | **§0b 补记⑦零余量第三读法（owner 认可）**：可判性——低自由度候选判得便宜（生死都快）应插队先试；22 号判定实验因「杀手读法单用+工具形状偏置」迟到十天的复盘教训制度化 | 本文档 §0b 补记⑦ |
| 08-05 | **§0b 补记⑧切分质量两维度（owner 认可）**：回传带宽（细通道=枚举墙，拒绝理由可编译时整批编译回上游）+工况相关性（耦合强弱=问题×工况，切分入档记工况前提）；修法原则=先加粗通道不挪刀；实证=M5 33h/正式门盲枚举/27号零成本构造 | 本文档 §0b 补记⑧ |
| 08-05 | **owner 裁决：空矩形语义=什么都不能有**（设施/杆/传送带/暗管全禁；书面留白+V88 静默宽松读法作废）：负结果与 U 方向安全仍有效；band22 (42,6) 登记资格暂停（22 格穿孔物流+4 口 front 落孔）待严格语义重设计；认证链 routing 占用集修复挂 freeze-ritual 批 | `docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md` |
| 08-05 | **§0b 补记⑧续·切缝判断方法（owner 认可）**：死因谱×否决带宽两测量、墙的预言式、拒绝日志=缝健康仪表、三步流程（看谱→查带宽→先修通道再放量）、工况复审三触发器、死因谱为条件性规则指路 | 本文档 §0b 补记⑧续 |
| 08-05 | **严格空地认证链修复批落地（f16a22c）+ 谓词修订甲案（owner 拍板）**：ghost 格入路由占用集（主路径+固定见证链同批，belt/bridge 共域自动同禁）、孔致阻一律不发 cut（防跨 ghost 超杀）、ghost 上下文 fail-closed；reseal 全套收敛（3 文件+checker 自钉+2 处计划外 pin），checker 双绿、慢 lane 绿、新哨兵 23 条、变异红→绿 10/19；谓词 (5) 补「所有 route cell ∈ G∖R」（01_overview §1.1 + LOCK §1A 已 re-sync）。**P1.2 close claim 因 sha 漂移按 mutation_policy 重开——re-close 与 canonical_rules emptiness 补写、clean-streak 是否清零三项等 owner 真人动作**；现存 checkpoint 不可 resume-campaign（source tree 摘要漂移，施工前已确认无在跑 campaign） | `.artifacts/ghost_strict_fix_20260805/CHANGES.md`；`.artifacts/ghost_strict_fix_plan_20260805/BATCH_PLAN.md` |
| 08-05 | **P1.2 重关技术前置收齐（晚）**：①canonical emptiness 冻结仪式落地（`5f1b974`：emptiness=no_occupant_of_any_kind+裁决出处对象，schema/pydantic 双 required，pin 17,510B/5012…→18,137B/c3666d78…，派生工件字节未变）；②PROJECT_LOCK sha 继承链补齐（`6cfb86a`：d5578f8+5f1b974 两次 LOCK 变更漏更的 6 处 pin+antecedent 重算，欠账在 d5578f8 验收时序）；③f16a22c 对抗审查 codex 判 **PASS_WITH_NOTES 零 soundness 反例**（唯一 FINDING=TST-GHOST-001 测试证据盲区→待办批：5 条测试补丁+防御性 fail-closed 加固）；④`6cfb86a` 上干净全量门收官：主 lane 7,179/0 败、慢 lane PASSED、旧红仅 r4+memory 两片存量。**剩 owner-only：手动门 re-close+clean-streak 归类**（主线建议：owner 主动规则变更+对抗零发现=不清零）。GPT Pro 零信任复查包已出（善意+手误前提，owner 口径） | `.artifacts/emptiness_ritual_20260805/NOTES.md`；`.artifacts/ghost_strict_fix_20260805/ADVERSARIAL_REVIEW_VERDICT_f16a22c.md`；`~/下载/zmd-咨询包/ghost_strict_recheck_20260805.7z` |
| 08-05 | **preflight --full 首次完全绿（20/20 lane，`aa2f05b`）**：两片长期红 lane 同晚破案清零——memory lane 根因=venv 缺 PyYAML（lane 08-03 出生即红，装 6.0.3+进 requirements/lock 后 265 全过）；r4 18 ERRORs 根因=验证器解释器 pin 钉在 .venv-uvbolt-backup（软链坏掉时代身份），实为 08-05 修软链的同日副作用而非陈账（归因修正入记忆卡）。另 TST-GHOST-001 补丁3/4 落地（`873afd4`：五发射面真实-separator 参数化哨兵+终端 fixed-witness E2E，红绿自证带 SHA；补丁1/2+逐mutant收据挂封印批）。主 lane 7,203/0 败 | `.artifacts/preflight_full_green_attempt_20260805.log` |
| 08-05 | **band22 严格语义重设计双回件独立验伤收官（owner 三连问策略首两份）**：GPT Pro 两份 (42,6) 见证**孔位互异**（R1 南缘 x=32..38,y=64..69 / R2 band8 x=3..9,y=30..35 走 h=4 支路）。双席 codex 用自有代码按**现行权威 canonical** 独立重算：两份的承重几何全部成立（266 实例双射、机身 3,544 零重叠、孔∩机身/杆/路由=0、组件零 cross、杆 intersection 覆盖 219/219）；R2 另复跑出 23 杆 CP-SAT 最小性 OPTIMAL(23=23)。反驳点全在叙述层：R1 负例「12/12」实为 any() 判据（负例8 少红一组）+「无机身跨割」全局化为假+勘误对 manifest 覆盖描述错；R2 唯一数字错=M136 实迁 [3,52] 非自报 [3,51]；两包 canonical 均钉旧版（差异已核=恰好 emptiness 两键）。**官方 binding/routing 门均未跑——④路 driver 下一棒**（三大风险：mode→官方 pose 映射、逐商品守恒、binding slot 映射）。第三份回件在飞 | `.artifacts/band22_strict_redesign_replies_20260805/`（VERDICT_R1/R2+r2_evidence/） |
| 08-06 | **GPT Pro 复查 BLOCK 的在库裁决收官（凌晨）**：外审首轮判 BLOCK（非实错——三条认证链离线证据闭包不足：RAB-SEP EMPTY_DOMAIN/whole-layout anchor 独立性/fixed-witness 终端链）。codex 全仓裁决：**三链全部闭合**（RAB builder 显式 ghost 排除+all-or-nothing 证书+25 哨兵+close-kernel pin；reverifier fresh binding 不吃 occupancy、proto 差分探针三态一致；终端链 parent nonce 门+seal/publish 各自重验——行号级证据链＋allowlist 动态求值）；全仓字节下降级 PASS_WITH_NOTES。**真发现两条已落订正**：D-01 首轮内部审查枚举漏 RAB 通道（判决书补订正批注）、D-02 CHANGES「唯一风险」过度声称（勘误段）。第二轮补证包已出（64 文件含全部点名源码+双方判决书均标 UNTRUSTED，`ghost_strict_recheck_v2_20260806.7z` sha bf5e9ec1…）待 owner 上传。P1.2 重关继续挂起等第二轮外审+owner 拍板 | `.artifacts/ghost_strict_fix_20260805/BLOCK_ADJUDICATION_20260806.md` |
| 08-06 | **R3 验伤收官——三见证验伤矩阵齐**：R3（孔 x=21..27,y=30..35 居中带）见证实物独立重算全过（26 杆最小性双路复跑 OPTIMAL 26=26、53 候选独立确认；band14 割 y=63 唯一跨割边；四族表坐标重算精确相等），**但 R3 原话不可原样转述**（协议核心叙述整体向西错一格 x=60..68 实为 x=61..69；负例8 的 G17 未红被 any() 计过）。三份横评：**实物 R3≈R2>R1，原话三份全都有错**（R2 M136 坐标/R3 核心坐标/R1 范围过度声称）——「GPT 叙述层必错、工件层扎实，一切以 JSON 为准」成规律。L 侧现有三个孔位互异、独立验证的严格 (42,6) 候选见证；官方门待 ④路（driver 适配实施中） | `.artifacts/band22_strict_redesign_replies_20260805/r3_strict42_v51/codex_reverify/R3_REVERIFY_REPORT.md` |
| 08-06 | **④路 v2 driver 落地+治理登记收尾+R2 全阶梯开跑（凌晨）**：①driver v2 适配批（`a90e9bb`）——band22_v2_adapter（strict schema 解析+mode→官方 pose 映射六型+active-terminal-only 孔检查依 LOCK:404+ghost 双索引合同 canonical 交叉核验）、run_ladder 三档串行阶梯（intake→固定 master→官方门，censored-stops、24G/禁swap/flock 单例）、22 条新测试；R2 rung1 INTAKE_ACCEPTED（42s，VmHWM 3.9G）。②治理清单登记 08-04/05 证据根+804 源基线（`eb222d0`）——但提交时 `&& tail` 吞退出码带 3 红落地，测试侧金标（counts/roots/path_count 双钥匙）补齐于 `9e28cf9`（38/38 绿；devtools/tests 不在任何门 lane，首绿口径未污染）。③R2 全阶梯（max-rung 3，官方 binding/routing 预算 600s/600s、gate wall 20400s）setsid 开跑，Monitor 盯逐 rung 收据 | `.artifacts/band22_registration_20260805/ladder-r2full-*/LADDER_RECEIPT.json` |
| 08-06 | **二轮外审双判决落档+三轮补件包出**：owner 独立传两次 v2 包，回件 A=`PASS_WITH_FINDINGS`（F-01/02/03 三阻断全闭合；四非阻断：helper 宽松态、变异证据不可逐面归因、f16a22c 叙述对 D2/PCR 过度概括【已在库核实属实——:7404/:7421 在公共 suppressor :7582 之前】、LOCK:711 陈旧引用【属实】）；回件 B=`BLOCK`（唯一理由=F-03 缺 4 个直接依赖源码无法闭包，非发现实错；七攻击面独立确认无泄漏）。三轮补件包 `ghost_strict_recheck_v3_20260806.7z`（sha 2c5ea423…，73 manifest 全核，+4 直接依赖+2 separator 源+2 横幅+新哨兵终态+HEAD 声明与逐条勘误）待 owner 上传。**封印批欠账追加**：CHANGES D2/PCR 勘误、LOCK:711 修复（走 6+1 pin 链）、畸形 ghost cell 异常归一化、逐 mutant manifest | `.artifacts/ghost_strict_fix_20260805/GPT_R2A_*.md`、`GPT_R2B_*.md` |
| 08-06 | **官方 routing 拒绝 band22 见证的条款级定位收官——判 (b) 模型比 canonical 严**：机制=「终端 front 格对外商品完全排他」四约束合谋（port_adherence 恰一 + successor/predecessor 对外商品机身侧流向硬置零【豁免按 (cell,dir,commodity) 键控，主线抽验 :1233/:1271 属实】+ AddAtMostOne(phys) 同格同形&use 形状原子 + 桥仅跨直线）；5 口极小核几何互锁验证（BFS 断连/变体预测吻合）。canonical `mixed_commodity_flow`（07-03 入册）明文允许混流无终端例外、owner 游戏实验证实混流过机器口真机制、见证形态全在模型词汇表内——模型拒的是「同形状按商品选边」的表达力。**影响**：R1/R2/R3 现行模型下永不可注册（与预算无关）；可行性/下界类结论安全，**上界/不可行性/最优性类结论对 canonical 语义带作用域条件**（fork 原文方向口误已订正），SMM4 U/VeriPB UNSAT/负锚点需逐证书盘点 routing 依赖度。附带：单商品 routing TIMEOUT=连通性护栏假环流循环磨（60s 134 incumbent/133 拒），补表达力后仍需性能工作。三出路待 owner：①canonical 加终端排他（与游戏证据相反）②use 变量边级重塑（sealed 大工程）③过渡双口径记账 | `.artifacts/band22_registration_20260805/coupling_verdict_20260806/COUPLING_VERDICT.md` **【08-06 晚已翻案为 (a)-修正，见下方翻案行；本行仅历史记述】** |
| 08-06 | **逐证书作用域盘点收官——(b) 保真缺口零伤及在案证书**：PB-03 VeriPB (1326,34)（带内 OPB=矩形×46 边界口 front 常量格共存，纯几何）、(1190,34)+P≥9（front 接驳格方向容量+模板口几何+供电光环）、SMM4 U=(1188,18)（A004=几何必要引理，模板口计数算术；原条件照旧无新增）、W0 3号/H20（body-front 几何计数/供电层矛盾）——**全部不依赖 routing 模型约束**；round45/W2b/ab16 本非 bound 证书。主线抽验两条承重引用属实。双钳原样成立。两条前瞻守则生效：官方 routing INFEASIBLE 未来作否定证据须显式标 (b) 条件（现无此用法，④路 censoring 合同挡着）；A004 家族 routing 味新引理准入按 (b) 重审 | `.artifacts/band22_registration_20260805/coupling_verdict_20260806/CERT_SCOPE_AUDIT.md` **【(b) 已翻案；本行结论作双保险记录仍成立；binding 层残余经 CERT_SCOPE_AUDIT 批注二复核同样零伤及】** |
| 08-06 | **翻案：(b)→(a)-修正——模型门口排他=游戏语义的正确保守编码**（owner 定谳机器入口无选择权+缓存格类型锁+空窗照单全收→混流到口最坏情况必吞错货→污染/中毒；主线昨日「机器只吸自己要的货」系走私限制口行为的假语义，且 owner 此前已答过一次、主线在压缩中遗失）。三钉齐：分流器对堵住出口会回退（08-05 兄弟线收据，不改结论）、空窗吞入 owner 定谳、**限制口=游戏 v1.1 存在但 canonical 记录在案的刻意省略**（旧理由「省略不排除解」在修正语义下过时→新挂账：作用域声明或远期建模）。连锁：①（canonical 补终端条款）转为推荐方向、②缩水为性能债+P2.0 前置、band22 三见证双语义下真死、严格(42,6) L 侧实质变难（三独立设计全绕不开门口混流=负面信号）；「上界带作用域条件」的昨日分析作废（模型与修正后规则一致）、逐证书盘点成双保险记录。待 owner：canonical 终端条款批（freeze-ritual） | `.artifacts/band22_registration_20260805/coupling_verdict_20260806/REVERDICT_A_REVISED_20260806.md` **【矛盾清单 A 条订正：「模型与修正后规则一致、无作用域条件」过强——正确表述=模型⊆修正后规则，差集=终端胶囊+电池段单口双成品 2-4 道（binding 单商品制），见 REVERDICT 批注】** |
| 08-06 | **速率引理落地——中间产物纯流系皮带帽算术强制（owner 问「纯流可否推出」的回答）**：demand_solver 精确账×belt 1件/tick（=0.5/s，与 owner 2s 头距、IP log_admission=30/min 三方一致）⇒ 满产下 10/17 配方单机运行率恰=1、余者 11/12~21/22；最小分配残道速率∈{5/6..1}两两之和>1 ⇒ **任何两中间产物不可共乘一道**（含种子回路）。唯一速率合法混流域=胶囊(11/60/机)+电池(1/5/机)去核心段（省道上限 2-4 条）。推论：front 排他对中间产物 WLOG 无损；限制口建模必要性缩水为「仅核心前分拣」且若核心多槽则归零——**模拟器判例：IP 仓库提交按 slot:itemType 逐类型开槽（多槽分型方向），待 owner 游戏点头**（实体映射 warehouse↔protocol_core）。水箱无需开（算术直接闭案）。引理入翻案文书附录 | `.artifacts/band22_registration_20260805/coupling_verdict_20260806/REVERDICT_A_REVISED_20260806.md` 附录 **【复算订正：满率口径 10/17（原 9/17 系笔误）；21/22 来自输入侧道；可复现工件 rate_lemma_recompute.py 已落 coupling_verdict_20260806/，中间产物残道两两之和≤1 反例=0】** |
| 08-06 | **口岸语义终定谳（owner）：所有仓库系输入口吃混流**——协议核心 14 输入+协议箱（箱→仓库无线段）逐类型开槽混吃安全（与 IP warehouse-submit 判例一致）；二分法定稿：机器口=单槽污染机制（front 排他=正确编码）/仓库系口=逐型分槽。**限制口建模必要性终裁=零**（中间产物算术禁混+仓库口天然混吃）。残余保真注记：模型 binding 槽位单商品制不能表达单口双成品，缺口被速率引理钉死在胶囊+电池终端段 2-4 道——处置推荐=canonical 批 scope 声明（备选：远期槽集合扩展）。canonical 修正批内容集齐：终端条款+速率引理 scope+限制口理由重述+单口单商品 scope，等 owner 与封印批合批 | `.artifacts/band22_registration_20260805/coupling_verdict_20260806/REVERDICT_A_REVISED_20260806.md` 附录补遗 |
| 08-06 | **勘误（owner 精度修正）**：上行「协议箱…混吃安全」不准确——箱非仓库系口（无连接，仅无线传送缓存入仓库），本体走机器机制：6 缓存格动态定型、第 7 种堵门=**有界混吃**。「仓库系口」准确范围=有线连接仓库的存货口（边界仓储口/核心）。胶囊+电池→核心、限制口=零、canonical 四件套结论均不变，scope 声明按三分法（有线仓储口无限混吃/箱 6 槽有界/机器口配方槽污染）措辞 | 同上附录补遗二 |
| 08-06 | **逐 mutant 变异收据交付（外审欠账清偿）**：15 单变量 mutant（benders 8/fixed-witness 4/routing 3），13 CAUGHT/2 MISSED，预期红名单 15/15 逐节点吻合；每份收据带 diff+原/变异/恢复三段 SHA+全量日志（隔离 worktree 生产，主树零改动）。**2 MISSED=外审怀疑坐实**：M11 TOCTOU 第二次 digest 比较失败侧不可达、M12 digest owner 字段无「同格异归属」覆盖——即封印批测试补强靶子。正面红利：M01 实测证明五发射面哨兵逐面归因+分层防御（suppressor 废掉时四面红、deletion-core/:520 由独立层兜住）；M10 坐实补丁 4 E2E 是伪 CERTIFIED 前唯一拦截层 | `.artifacts/ghost_strict_fix_20260805/mutation_manifests_20260806/SUMMARY.md` |
| 08-06 | **外审包改双包制（owner 主意当天落地）**：小包=任务书+核心证据（v3 重打 645K，「缺文件报名下轮补」划线声明改为「自己去全包查」）；全包=声明 HEAD c518018 完整树+candidate_placements 原位恢复+三个结构 checker（纯 stdlib，`env -i` 最小环境实测全绿：15 obligations/65 nodes/external verified）+codegraph bundle（自带 node 仅需 glibc≥2.28，模拟沙盒从零 init 9.2s+explore 实测可用，文档注 CODEGRAPH_NO_WATCHDOG=1 防单核误杀）+REVIEWER_MAP 导航+4239 条 MANIFEST，7z 48M；结构性消灭「审查者缺文件 BLOCK」失效模式（判决 B 类）。双包均解包抽验：MANIFEST 全过+checker 复跑+canonical sha 逐字节吻合 | 待传×2：v3 `9b401860…`、全包 `3eccf423…` |
| 08-06 | **三轮外审双判决：双 PASS_WITH_FINDINGS，F-03 终端链闭包销案**（上轮唯一阻断，两位独立审查者一致确认；双包制首战成功——全包 4239 条 manifest 过、43/44 文件逐字节同 HEAD、29 节点哨兵独立执行绿）。头号新发现 **F-SND-001（High）主线验真 CONFIRMED**：PCR `patch_routing_core.py:583-585` 对已是 front 格的口坐标再 `+DIR_DELTA` 偏移——正是 front 事故（07-18）修复权威 docstring 点名禁止的旧偏移，生产链当年全改走 `_port_front_cell` identity helper、PCR（LEGACY_DIAGNOSTIC 面）漏网；差分探针本机复现逐字段一致（full FEASIBLE vs PCR INFEASIBLE，replay 同病自洽）。当前 HEAD 不可达（closed allowlist 挡在 controller 前）=无现行失守；归 **PCR/pose-bool promotion 前置硬阻断**清单。F-EV-001（缺逐 mutant 收据）仓库已有=下轮附上即闭；文书勘误族逐条认账。验真批注+全部交付物落档 round3_verdicts_20260806/ | P1.2 重关证据面齐（三轮：BLOCK→PASS_WF+BLOCK证据缺口→双 PASS_WF），等 owner |
| 08-06 | **④路/band22 登记线终态关闭**：RAB 版全阶梯收官——rung1 INTAKE_ACCEPTED(43s)/rung2 MASTER_FEASIBLE(44s)/rung3 UNKNOWN_CENSORED(5.68h，`ladder-r2rab-20260806T094816Z-74ae9903`)；随后 (a)-修正终裁坐实三见证 routing 层永拒（门口混流假语义）、与 binding 枚举无关——**该线关闭**（07-27「④路=新默认主攻」指令就此终结）。RAB 通道本身 soundness 在案仍有效，适用场景回归真墙本身；L 侧重开首选构造=公理系 P1（混流干线 L1 过境+门口纯流末段，`.artifacts/axiom_analysis_20260806/` 预测检验） | 台账 §4 #12 canonical 批+公理 kernel 提案待 owner |
| 08-06 | **封印批收官+P1.2 re-close 落章（owner 会话内批准）**：封印批 `a08ee02` 六项全落（ghost helper 两宽松态收紧/异常归一化/M11+M12 哨兵经变异自证/LOCK I1 勘误/suppressor 勘误注释/完整 reseal 连锁），门全绿（双 checker+pin 链 69/69+全量 PASSED+慢 lane PASSED）；**gate 文件写入 `owner-p1-2-reclose-20260806`**（07-07 原决定存 history；streak 按 owner 口径清零重计、计数仍仓库外；strict JSON+publish gate 双消费者验证过、obligations checker 复跑绿）。同批执行公理 wf 矛盾清单 15 条（速率引理可复现工件落地：10/17 勘误+21/22=输入侧道+核心断言零反例；CERT_SCOPE_AUDIT 批注二零伤及复核；8 张记忆卡+双台账登记）。**新过严面候选上报**：模型 source front 排他与 sink 对称（豁免表 `_source_port_fronts` 抽验实证）而污染论证只覆盖输入口——L 侧重开前待 owner 裁定 | 公理 kernel 提案+canonical 批（§4 #12）待 owner 定形状 |
| 08-06 | **公理系最承重参数空白回填（模拟器侧）**：制造机配方槽系统抽取（IP entity-definition 逐设备）——输入缓冲=每原料一槽×50（grinder 1 槽/filling 2 槽，全口共绑同组）、核心 20×1/箱 6×50 与提案参数表逐字吻合；落定「同商品双带并联」＝瞬时合法+稳态受配方消耗率钳制（非 2×加带），**谓词 (4) `slots=ceil` 换算=需求侧下界、方向安全**——A7 悬空注记降级为「模拟器已闭、游戏终审待 owner」 | `.artifacts/axiom_analysis_20260806/MFG_SLOT_PARAMS_20260806.md` |
| 08-06 | **公理系预测检验三连中（owner 两句定谳+一发探针）**：P2 箱单货占多格=会（canonical 箱条款定槽数口径）；P-c 双带并联游戏=模拟器（谓词(4) ceil 换算游戏侧终审完成）；P-d 空口不轮询对半（双侧定谳）。**P1 L1 过境模型实测 FEASIBLE**（probe_p1_l1_transit.py；首跑 INFEASIBLE 系探针坐标系笔误——模型 N=y+1，域分析器不查 dir 一致性抓不住）——第四轮 GPT 设计的关键自由度坐实，**owner 拍板第四轮开工** | `.artifacts/axiom_analysis_20260806/` 补遗二 |
| 08-06 | **第四轮设计包备料（规则段占位待 owner 公理终审）**：任务书草稿全文成稿——硬约束六条（门口纯流/速率纯流/带帽/三分法/闲置口/输出口保守）+新自由度（L1 过境，探针已证）+上轮死因剖析内嵌+交付合同新增两条（数字禁手抄+字段路径引用）；组装说明含打包清单/验收管线/发包硬序（owner 五件把关项裁定→替换规则段→打包）。**发包前置=owner 审 `AXIOM_REVIEW_FOR_OWNER.md`（owner 拍板顺序：先确定再找）** | `.artifacts/band22_r4_prep_20260806/` |
| 08-06 | **公理终审收官+第四轮设计包成品**：owner 五件★全清（A9 认+精化：配方内置/一机多配方/任意匹配即开工；A11 认；A2 实质裁毕；输出口门口过境安全【附汇流 2s CD 双入竞争最坏减半速率注记】；回退=不放行留上游）。残余 5.2 #2/#3/#4/#6 四条关闭。r4 任务书规则段终版替换（公理摘要+参数表+速率算术+R4 旧读法作废清单），`band22_r4_design_20260806.7z`（sha 6b5ca808…）落咨询包目录待 owner 传。组包发现上轮包 canonical 为严格空语义条款前旧快照（E-05 追记，实害零，本轮换正版 c3666d78）。**source front 模型解锁**列模型优化候选（sealed 面独立 freeze-ritual 批，soundness 方向=放宽须外审）。 | 公理 kernel 提案随 canonical 修正批待 owner 定形状 |
| 08-06 | **source front 解锁侦察修正**：排他非豁免表而是三层结构涌现（port adherence sum==1+每格单物理件+同商品终端豁免），地面同向共乘的真前置=残余#7 混流表达扩展（U-02 结构性 INFEASIBLE），解锁降级为 #7 子项。**双探针实证 L1 垂直借道在输入/输出口 front 均已可用**（`probe_source_front_l1_transit.py` FEASIBLE），零改动增益已拿到；r4 任务书 L1 自由度扩为双向口、包重打（sha b53bb1d7…）。侦察文书 `SOURCE_FRONT_UNLOCK_RECON.md`（含 #7 未来雷区清单：F-SND-001/域构建/全局复验）。 | #7 排期待 owner |
| 08-06 | **P2.0 流量线研究重启**（owner 提醒被压忘）：§3.3 面积上界定为重启第一目标（升格成立则 P2.0 语义下 A 上界压到 ~950-1,100 档、第七谓词改变最优解本身），升格路线文档 `AREA_BOUND_UPGRADE_PLAN.md` 立（七条证明义务：OB1 口径钉死【复跑发现 9,084/9,135/9,246 三口径并存】/OB2 机身预算脚本化/OB3 已闭/OB4 电杆真下界/OB5 计数→Farkas 核心/OB6 双层修正/OB7 语义标签纪律）。与 #7 混流手术解耦可先行。 | OB1-2 机械项先做,OB5 研究主体待排 |
| 08-06 | **双线并行收官（owner 拍板开工的两条）**：①mixflow 混流表达手术（worktree 分支 mixflow-surgery，b9207e7+56977da）——商品子图样 use 设计（下游零改动、连通复验器实测零改动接受混流解），U-02 合流分流与 source front 共乘双翻 FEASIBLE、门口污染防线哨兵两层变异自证、138 例全绿；性能一轮返工后 build +5.6% 达标；**solve 固有代价入档**（不可行证明变难，对抗 proxy 27.7s→120s 无结论）→接入批必做 benders 生产实测+门控开关设计题；意外红利=关掉旧模型一个不可达潜伏接受面（比旧更严）。等外审（brief 就绪）+owner 接入决策。②flowbound 面积上界（88c0911）——A≤1166 无条件严格【模型内】/1012 单层待 OB6，装填 IP K=396⇒P_min 9，front-state L≥308+G1-G6 台账；codex refute 席在审，通过后转正 docs/research/。调度基建副产：子代理工具面卡（无 wf 有 Agent+孙代理路由三方证词）。 | mixflow 外审包待打（等 refute+600s 探针齐）；接入决策 owner |
| 08-06 | **refute 席判决：flowbound 报告核心被驳倒、不得转正（家规兑现）**：①front-state 核心引理 canonical 最小反例（一个 splitter state 同时服务 1 产口+2 耗口，三设施共 front (35,35) 冻结池真实 pose+binding FEASIBLE+非零流量）⇒ L≥308 失证退回 305，A≤1166/1012 失效，可保级=**A≤1167 无条件/1015 单层**；②「第七谓词改变最优解本身」被驳倒——上界对上界推不出最优值变化（L=absent 下无六谓词下界也无 witness 拒绝证明），**上一行台账该句作废**，降级为开放问题；③K=396（refute 席 SCIP 双档交叉验证一致）、F_route=9135、流矩阵满秩全 SOUND；④G 台账多条 REFUTED/GAP+旧数字残留。flowbound 已唤醒按六条清单修正，refute 复核通过才转正。**错误类型=证据等级混用（上界当最优值变化证据），与 19 号文书同族——refute 席前置家规再次自证必要。** | 修正→复核→转正 |
| 08-06 | **mixflow 手术批终收官**（worktree 分支 mixflow-surgery 三提交，末 33c4afa）：600s 探针带回新信号——对抗 proxy 上新模型「慢可行+弱割」而非「慢不可行」（CP-SAT 持续找到局部闭合 incumbent 全被全局连通复验拒掉 guard rejected=4；source-side 割自检全部回退弱 nogood=**割机器是前混流时代写的，接入批需混流适配**）。接入批开放问题三件套齐（门控开关+EXACT_* 白名单连动/割回退定位/benders 生产实测）。座席已收工，名字保留。 | 外审包待打；接入决策 owner |
| 08-06 | **mixflow 外审包成品**：`mixflow_surgery_review_20260806.7z`（42K，sha c704c7b6…）落咨询包目录待 owner 传。自足小包：外审任务书（四个中心问题按重要性排序：不纳伪/不拒真/送达语义丢失处置/性能固有代价）+brief+设计全文+全量 diff+术前术后全文对照+差分测试组；边界声明防审查范围误判（worktree 未合未 reseal、certified flip 属接入批）；「BEFORE=c518018 共同字节」声明经字节级核实后写入。全包沿用 3eccf423。 | owner 传（可与 r4 包同批） |
| 08-07 | **flowbound 线终收官：面积上界报告六轮对抗后转正**（dabb9e5，docs/research/p2_0_area_bound_20260806/）：refute 席正式身份确认「P2.0 语义 research upper ledger：**A≤1167 无条件 / A≤1015 单层【条件·待 OB6】**」。六轮弧线=初判核心引理驳倒→假等号/provenance→cover 等价/跨商品超边（mixflow 成果跨线击中）→singleton 增广→物理恒可行换 formal w=0（穷举 2,048 族验证）→终判可转正；数值 1167/1015/1014 六轮六验一格未动，每轮砍掉的均为表述超算。负结果与反例探针 harness 全部耐久入库；后续攻线（G1×OB6 耦合/证书工程化/ℓ̄ 路径长度）起跑材料齐备。七笔提交 88c0911→dabb9e5。 | 后续攻线待排期 |
| 08-07 | **mixflow 外审判决 BLOCK（zmd-3 GPT Pro，已归档 verdict_20260807/）**：B-01 Blocker=de-mix 解游戏动力学纳伪+**4 格反例封死准入口兜底**（两支路全转弯终端格无直行位，术后 FEASIBLE+复验 failure_count=0，反例脚本随判决交付）；编码层清白（独立穷举 469 组合全匹配/300 随机单商品回归零收窄/sink-front 四边界全过/Q1 Q5 Q6 无洞）；F-02「纯放宽」须改带前提命题；F-03 测试把伪解护成预期须加负例；F-04 性能启用门槛量化清单。**解除条件六条**（certified 默认关+de-mix 三选一【显式 filter/realization gate/禁 de-mix】+4 格反例入常驻负测+M4 改写+性能语料+witness 构件证明）。与我方中心自攻同向但更深——「总能补准入口」被证伪。接入批形状随 owner 三选一。 | owner 定 de-mix 修复路线 |
- 2026-08-07：**mixflow ③保守禁 de-mix 修复批完工验收**（owner 晨拍板③；worktree mixflow-surgery fb76e15，**未合并未 reseal**）。①约束 `_add_demix_ban_constraints` 零新变量两文字蕴含+两层变异自证哨兵；外审 4 格反例入常驻负测，mixflow 22+routing 31 全绿；codex 独立对抗复核 **claim holds**（3448 组 solver 探针+层攻击四向+mutation control）。②基准（同装置对照）：build 19.84→23.88s，solve 帽 120s 下不可行证明 28.3s→术后 TIMEOUT→③修回 113.9s（残余 4 倍差距）。③**混流送达面清零坐实**（走廊/4×4 强制混流 UNSAT；5×5 600s 无结论如实记）：③批=基建+堵洞，红利挂 U-01（仓储口/核心口混流准入，前置=先答「同向共 front 混灌靠什么挡」——两道墙分工发现，`_mixflow_ground_banned` 守卫在该几何是唯一防线）。④六解除条件闭 2/3/4、部分 5，1/6 属接入批；待审 6 问攒 GPT Pro（OPEN_REVIEW_QUESTIONS.md）。**接入决策待 owner**：合入+门控关死 vs worktree 封存等 U-01。证据 `.artifacts/mixflow_demix_ban_20260807/`。
- 2026-08-07：owner 拍板两项——①③批接入取**封存等 U-01 一起接**（省一次 reseal，main 不背零收益复杂度）；②**U-01（仓储系口混流准入）即刻立项开工**（opus 单席接棒 mixflow worktree，基线 fb76e15）。
| 08-07 | **canonical 公理 kernel+四件套修正批收官**：owner 晨拍板合批 → Fable 单席 worktree freeze-ritual（canonical 18,137B/c3666d78→40,371B/b675fb6a 纯 additive；kernel=semantics.axiom_kernel A1-A11+裁决级输入+model_stricter_faces；四件套=terminal_clause/rate_lemma_scope/rationale_restated/port_commodity_scope；箱 slot_count_clause；reseal 连锁=canonical 17 直接 pin+contract/checker/preflight/LOCK 四链含 antecedent 重算）→ 合入 main `fab718a` → **main 双 gate 绿**（首轮双红=主线程 setsid 漏 venv 的环境假红，r2 用 .venv 复跑 full=0/slow=0）。§4 #12 与缺口表 :555 行同日销账。4 条 canonical 文本审查问题攒 GPT Pro 包（A2 保真/边界仓储口三分法域/rate_lemma fail-closed 前件/model_stricter_faces 误读空间） | `docs/research/canonical_batch_20260807/`（RESEAL_MANIFEST/双 gate log/pin 真值审计/定谳存档 7 件） |
| 08-07 | **owner 特化视角双洞察+P2.0 设计稿立项**：①箱口条件准入按当前解空间重估——drain 区内只可能出现终品（sink 在机器口的商品被连通性自动排除）、终品=2 种 ≤6 恒真 ⇒ 种类约束塌缩为加载期 fail-closed 检查（已转 U-01 席核两点：区内只有终品的严格性、rate_lemma_scope 落地后速率前提重估）；②**流量认证特化**——固定 targets ⇒ 19 商品稳态速率=常数 ⇒ P7 退化为线性容量账（use×常数系数），速率引理 canonical 前置今日刚满足；核心设计题=引理双前件对全部可行解的成立方式。owner 拍板先出特化设计稿（opus 席 p20-spec-draft，产物 docs/research/p2_0_specialized_20260807/，过目后定实现立项） | 待设计稿 |
| 08-07 | **P2.0 特化设计稿 v1 完工**（p20-spec-draft 席，`docs/research/p2_0_specialized_20260807/`）：owner 立项命题**前半成立后半证伪**——19 商品稳态速率=常数表【实测,F_route=9,135 第三次独立复算互证】；但「P7=use×常数系数线性账」不成立：6 种中间品（37% 流量）任何最小车道分配下必然分流（3 例鸽巢手算+3 例 CP-SAT,六例全手核）,细流段开出 15 对合法混流窗口——速率排除不了共道。真塌缩在求解结构：多商品流拆「逐商品单商品流+格位打包」,不可行证书=最小割（组合对象）,省掉 v2 有理 Farkas 基建,零前件依赖。**推荐丙案双侧夹逼**（上界=flowbound A≤1167 零前件现役化【五步证明链逐条核过与分道无关】;见证=受限族;相遇即全局 lex 最优,无需支配引理）。兄弟线输入：flowbound 的 L≥308 是限制侧不可进无条件链（陷阱）;mixflow 混流窗口只在细流段（收窄）。canonical 两条精度发现（fill-first=下确界;终品段混流须限定子速率和≤容量）。**欠账：未过独立 refute 席（家规）,排 GPT Pro 包;生产行数未实测（Q1）**。唯一 owner 决策点=长期夹不拢时是否接受降级发布（建议等首轮间隙数字再定） | 待 refute+owner 过目 |
| 08-07 | **U-01 收官三拍板 + 箱口二期改写（主线程裁决，worktree mixflow-surgery 批 fb76e15..1f5c6c3）**：①「汇流区单独可关」否——③禁令+汇流区在 certified 下是一个语义单元（③单开=过严⇒最优性链假 INFEASIBLE 风险；汇流区单开=回 B-01 污染），保险走审查+freeze-ritual 回滚非运行时双态；②口数扫描臂（14/28/56/128）=箱口二期硬前置，触发条件「箱实际被实例化时」（266 mandatory 零箱实例）；③复验面缺 operation_type 必须 fail-loud+端到端哨兵，禁静默退化成更严模型。**箱口二期任务书改写**：「≤6 种静态计数」作废（slot_count_clause 点名退役读法），正确形态=请 owner 裁决箱由 terminal_clause class (2) 提升为 drain 终点（论证=10s flush+谓词6 供电⇒不可毒死；10s 参数已在 canonical、无需追加）。**依赖纪律（防雷）**：汇流区终品性论证必须锚 binding generic_commodities 域（binding_subproblem.py:1175-1223），不得锚 no-orphan 全局门——后者在 axiom_kernel.model_stricter_faces 在册待放开；将来放开 source-front/no-orphan 的批次检索此条。接入批另记：U-01 分支基线早于 fab718a，canonical +67/−10 须按 freeze-ritual 对表非普通 merge | `.artifacts/mixflow_u01_20260807/OPEN_REVIEW_QUESTIONS.md`（Q7-Q19）；worktree DESIGN §11 |
| 08-07 | **owner 裁决：箱=汇流区合法终点（class (2) 提升成立）+ 流程病诊断**。owner 口算戳破：3 入口×1件/2s ⇒ 每 10s 冲刷周期进货 ≤15 件，件数 15≪300、纯流种类 ≤3<6 格 ⇒ **箱堵塞判据（6 格全占）物理不可达**，连暂时堵门都没有（理论例外=混流带 10s 内 7+ 种，本实例仓储系候选仅 2 终品凑不出；即便发生也只等 ≤10s 永不中毒）。canonical class 措辞改判挂下批 freeze-ritual；听诊协议第 3 步简化「诊断臂翻案 ⇒ 直接 freeze-ritual 实现」。**流程病（owner 追问定性）**：规则形态（参数散落条目、分类标签不带可达性）+推理流程（消费标签不重组参数；过严限制永不报警=cut 触发器教训的对偶）+owner-only 闸误用（当停止推导用，应=账算齐再上桌）三症并发；修法=生成式实体参数表脚本、分类条目补界可达性注记、裁决包必带完整参数账（记忆卡 classification-labels-hide-parameters） | 记忆卡；`.artifacts/mixflow_u01_20260807/`（§11.5 听诊协议） |
| 08-07 | **U-01+混吃汇流区批正式验收成立**（worktree mixflow-surgery，fb76e15..c6a9f8b 终封，未 reseal 未接线按纪律留接入批）：§11.13 限制可达性自查表拿新尺子量自己逼出两条订正——禁环降格为「审查经济」非 soundness 义务（环危险与箱堵塞同属吞吐层 out-of-scope，显出成本时第一个摘、摘时注意与已否决剪枝的耦合）；**尺子边界=问危险条件由谁保证不可达**（物理/冻结数据保证 ⇒ 限制描述不存在的东西可删=箱口案；限制自身即保证 ⇒ 它就是守卫必留=drain 出口案），此边界与常设条目同行防止拿尺子删 fail-closed 守卫。守卫分叉+wh_drain 闭包+无环化+红利实证（共乘下车 FEASIBLE/污染孪生 INFEASIBLE 单口翻转）+变异自证双签名互补+两 lane 零真红+六/三臂基准（realistic 14 口 INFEASIBLE@106s 同③量级、128 口=刻意上界）+DESIGN §10-§11.12+外审 Q7-Q19；四项拍板落定（门控否/条件6 fail-loud/听诊协议/箱裁决三层论证）；批内三次自我证伪原位留痕、open_yard 不忠实装置改名保留+忠实版对照。接入批欠账：freeze-ritual rebase（canonical +67/−10）、条件 6 接线+哨兵、口数扫描臂（条件触发）。批席已收口 | worktree `mixflow-surgery` e8fa172；`.artifacts/mixflow_u01_20260807/` |
| 08-07 | **owner 立双向保真公理（§0b 级）**：「守卫堵孔就放心」不对——把所有合法规则放进模型（防拒真）与堵孔（防纳伪）同等重要，此前几乎无视拒真侧。技术形态：max_lex 全局最优证书下过严=假证书（四象限：过严+见证安全/过严+最优性证明假证书/过松+见证假见证/过松+INFEASIBLE 安全）；过严限制只产生缺失答案、永不自曝报警。制度化：公理已中途注入 rule_system_redesign_20260807 工作流（普查缓存复用、分类起重跑）——分类学增设 exclusion 层、规则形态轨加完整性台账（model_stricter_faces 升一等审计面）与墙审计（能力盘点对账=孔审计对偶）、流程轨加双向保真验收步、对抗席回测箱收货口案、决策摘要含首轮墙审计排期。记忆卡 bidirectional-fidelity-axiom | 记忆卡；docs/research/rule_system_redesign_20260807/（工作流产出中） |
| 08-07 | **P2.0 splitfree 重判 round1 收官（owner 制瓶机一枪的完整结案）**：六例翻案四种（owner 的 molding [1,1,1,1,1,1/2] 逐字现于阶梯见证）、buckwheat/sandleaf 站住且升格为任意分配下的纯计数定理（种子回流环奇数劈半，定理 1/2 编号入报告）；必然分流流量 37%→10.5%、分流点 36→2；死因分层（第一层=占空 42 维多胞形自由 ⇒ 端口速率非常数，v1 未见此层；第二层=固定占空后中段切细）；§6 T 表三行判错订正（u 族 219 非 266、42 维参数化非整族清零）；缺陷三=「P1 族空」系非蕴含（分流不违反 P1），甲案死刑撤销改判欠 OB-D+OB-D2、下界半边可直试 P1+P3；canonical rate_lemma_scope 修辞案升格「前件与结论互斥须重写」，方向 b（分配无关版）定为下批 freeze-ritual 默认推荐（含可粘贴 diff，owner 终裁）；18 行 errata 已落 v1 两文档本体（头注指向 REJUDGE_REPORT §8）。报告独立审查进 GPT Pro 批（§9 攻击面自列） | `docs/research/p2_0_specialized_20260807/refute_round1/REJUDGE_REPORT.md` |
| 08-07 | **owner 立规则派生闭包公理（第二条，§0b 级）+ 5满1半条件定理 + GPT Pro 审查包就绪**。公理：规则系统是生成式的（基础×派生组合出下一级，解空间塌点结晶新规则），派生规则该被系统推出而非等人绊倒；owner 直觉当场验算成立=**5满1半条件定理**（条件于钢块免分流，制瓶机分配唯一 5 满+1 半：五前提把每台占空逼进 {1/2,1} 两档、总量定 k=5；无条件仍是 42 维自由——同一问题两层级两答案）。公理已注入重设计工作流（设计席起重跑，含派生规则一等登记/饱和扫描卡点/塌点上报设计义务与正负样板校核）。**GPT Pro 审查包组装完工**：`.artifacts/gpt_pro_review_batch_20260807/`，4 份可发+第 5 份占位（份1 canonical 四问=重构件待核、份2 mixflow Q1-Q6、份3 U-01 Q7-Q19、份4 P2.0 设计稿+重判两层），60 副本 sha256 零不一致，投递序 4→1→2→3（份1问3 依赖份4 §4）；组装中发现两处源材料行号错位（_incoming/_outgoing 镜像滑动，份2 Q2 与份3 Q9）=接入批订正项，包内已桥接。另派 rule-impact-audit 席对 splitfree 结论跑游戏规则全量清点（汇流点 CD 与 A9 多配方两嫌疑+主动搜漏，NOT_IN_CANONICAL 单列） | 记忆卡 rule-derivation-closure-axiom；`.artifacts/gpt_pro_review_batch_20260807/MANIFEST.md` |
| 08-07 | **splitfree 结论游戏规则全量清点收官（owner「都考虑到了吗」的正式答卷）**：两嫌疑定谳——汇流点 CD 不伤主结论（钢块 5满1半 实核零合流；仅有的两处合流是终品 3→1 进核心、均摊下同在、40%+ 裕量）但咬中 REJUDGE §4 共道反例（双不等式取等零裕量+D2 未定谳，引用须带注；另有 39 对反例故结论不倒）；A9 多配方证伪（shaper_1 八配方仅一条吃钢块、其余原料不在本产线——实例特定排除，T-1 残留）。**新立两条全项目级威胁**：T-5 作物族物质闭环存料守恒（占空目标只在特定存料量达到，初态充料 D9 未定谳，此前无人登记）、T-6 制造机多出口并联抽货可加性从未被论证（canonical A7 只写输入侧——n_op 全表的共享承重前提，均摊同样依赖，建议单独立项）。**NOT_IN_CANONICAL 9 条**（前三：饥饿节流等号=占空机制整个无条文；玩家钉死配方与 A9 措辞字面冲突；机器→配方集归属数据缺失）——整批喂重设计批墙审计。7 个模拟器判例已设计未跑（M-2 多出口可加性优先级最高）。正面新发现：阶梯只需分流器缺省对半行为、均摊反而要背压逼出 7/22 类比例=方向 b 又一独立支持。审查包份 4 已追补该清点 | `docs/research/p2_0_specialized_20260807/refute_round1/GAME_RULE_IMPACT_AUDIT.md` |
| 08-07 | **P2 陈旧登记事故（owner 抓获的传播层失效活标本）**：owner 指出「同种货填满已开槽才另开新槽」早已确认，而我方把它报成待判。查证：P2 确于 08-06 晚 owner 定谳（「当然是会的」+满格后开新格），三个登记处**两个已更新**（记忆卡、canonical slot_count_clause adjudicated 字段）、AXIOM_KERNEL_PROPOSAL.md 实体表与推导 #2 两行**漏翻**仍挂「待判」——重设计批机器复核恰读陈旧登记 ⇒ 把已判报成待判、经我转述误降级 owner 裁决。已修：两行补翻（标注补翻日期与原因）、审查包份 1 MANIFEST 加订正注、箱堵塞判据「物理不可达」判决恢复（无需 owner 再看游戏）。**canonical 补写两项挂 freeze-ritual 批**：fill-first 明文（slot_count_clause 现文只写「可占多槽」未写「满格后才开新格」——本次不可达算术的承重前提）＋单槽容量 50（owner 08-07 口述参数，冻结件缺）。定性=传播层失效标本，喂第一性推导席当校验用例（单一真相源+注记层设计正应防此病） | `.artifacts/axiom_analysis_20260806/AXIOM_KERNEL_PROPOSAL.md`（补翻行）；记忆卡 machine-input-no-selectivity-pollution |
| 08-07 | **第一性推导版重设计收官（owner 方法学翻转的执行）**：FIRST_PRINCIPLES_DESIGN（四推论主干：理论文书形态/派生层即做数学/断言必须给出推导唯一纪律/双向对应表三行集）+DIFF_VERDICT（对勘：收敛 15、分歧 8 内第一性版胜 5、赘物 2；推导版自认落败一点——「推得出不必写」被 C-15 证伪，改立两问三格准入判据）+病例校验 53 例（拦 23/补推导 22/部分 4/不管辖 4，补推导 12 条回填零补丁）。**席自纠两案**：①吸收「箱待核」系读到 P2 陈旧登记，已反向订正回「物理不可达」并自认犯了自己写明的纪-3（「机器复核」标签让它免检输入）；②勘察摘要「routing_rules 全死」经回源否掉（pydantic 钉 elevated=1、semantic_validator 读 bridge_mechanics，layers 搬家连带改模型）。**新活标本**：semantic_validator.py:50 报错文案把已退役桥读法写成「冻结真理」（布尔同理由反=代码固化退役读法），挂清理批。补-13（单一陈述位置）四推论落 §3.5。三份侦察报告存 scout_*.md。owner 决策点=semantics 拆分（单独上桌）。份 5 已组、审查包全五份齐 | `docs/research/rule_system_redesign_20260807/`（FIRST_PRINCIPLES_DESIGN/DIFF_VERDICT/scout_×3） |
| 08-07 | **推导席终轮增量**：67 族约束行集并入 FIRST_PRINCIPLES_DESIGN §2.10（正当表初始行集已实测）——新硬数字 **79% 约束零正当化指针**；三样本回源核：B15=全树形态最正确的墙（docstring 自报「会砍可行解」+撤退线，binding_subproblem.py:867-870，登记错位于 docstring 应入台账，落地批正当表首行样板）、I4「边界口恰 46」双写零出处、routing 16 族 rg 实测零规则引用；R15/P13 两条**反向注记**（故意无约束处）⇒ 行集必须容「此处故意为空」行防误补。**补-13 第二次实时发作**：scout_pin_chain.md 主线程与推导席同刻同路径各写一版、后写静默覆盖先写（现存版完整自洽无需改）——同一内容两个陈述位置零信号，正是单一陈述位置机制要杀的病。份 5 攻击面按席建议补「赘物判定复核」（只判 2 项赘物本身可疑） | `docs/research/rule_system_redesign_20260807/FIRST_PRINCIPLES_DESIGN.md` §2.10 |
| 08-07 | **份 6 模拟器盲推导双包组装完工（owner 出题的盲测对照实验）**：小包 349KB/139 文件（registry+simulation+domain 全量+精选）、全包 2.29MB/857 文件（整仓去二进制素材）+CODE_NAV（codegraph 索引 12,493 符号导出、索引产物已清）；快照=upstream 7b946c16（清点席同源，机型配方数逐个复算吻合），**识破 simrun 副本带我方 band22 测试文件不可用（防泄题）**；范围=9 机器/17 配方/2 终产物、映射不确定 0——**§7.3 悬案销账：buckwheat=moss_1 荞花（i18n+终产物链闭合判据），sandleaf=moss_3、valley_battery=battery_3 同定**；盲测纪律机器核查零命中（我方术语全扫）。回件不进 verdict 流程=对照系材料，回来做 canonical 对勘（含「模拟器实现选择」章 vs 公理提案残余清单的互查轴） | `.artifacts/gpt_pro_review_batch_20260807/6_sim_rule_derivation/`；GAME_RULE_IMPACT_AUDIT.md 销账注 |
| 08-07 | **剪枝 P4 首批收官（压实+无时态层，owner 拍板开做）**：三份无时态手册入库（26 规则手册 272 行/27 现状仪表盘 164 行/28 坑册+SOP 422 行，登记 doc_classes living）+ M5 卡 supersede 压实成单层现态卡（3 地层→94 行，`p1-3-batch1-m5-current-20260805`）。执行=隔离 worktree + wf_80bd1fb3 十席（盘点2+起草3+落地1+核验4：可溯性/证伪/读者 3 opus + codex 红利席），核验 11 条 blocking 全修（f62b335）——**我的「四个数量级」算术错被证伪席+codex 双席独立抓出**（649s→≥33h=约两个数量级，台账 32feaaa 已订正、勘误段已交 owner 中转左线）；修复席具名顶回一条误杀（SHA256_MISMATCH 真实存在 `research_run_contract.py:433`，证伪席只 grep 过 D6 目录）=多席互核双向价值。合并 12f895d + 收尾 61919df：主树 build-index（45 active）+ eval 34/34 双解释器、A2（慢测试计数 26 条订正入 CLAUDE.md）/A8（三手册 doc_classes 登记）两笔欠账清账、仪表盘 §9 就地删行=无时态纪律首次实战。扫描器复跑：docs 0 候选、memory 新增 1 条判良性底噪。**full 门禁三跑史**：run1 BLOCKED=发射解释器旧习惯撞 r4 pin 换代（aa2f05b 回正牌 .venv，18 error 假红，继承链卡已补 08-07 段）；run2 BLOCKED=单 xdist worker 于 CPython GC 内 SIGSEGV（coredump 在案、单跑过、非 OOM 非并发干扰）；run3 **PASSED 20 门全绿**。未来批清单=24 张 ≥2 地层卡已盘点落盘 | `.artifacts/prune_v2_20260803/`（design_p4/p4_strata_inventory/门禁三跑日志）；`docs/项目说明/26-28`；merge 12f895d |

- **2026-08-07（晚）｜GPT Pro 批三份回件（份2/4/5）当日核签完毕，全部逐行回源+复跑（opus 三席）**：①份4（P2.0）：24 条 21 ACCEPT、零整条推翻，总判「不能当实现基线」成立；核签反杀 D-06——616 车道门槛对任何合法分配不可达，**可达最小值=622 且阶梯处处取到**（新小定理，验算件入 `verdict/fen4/adjudication_checks/`）；rate_lemma 修法落点更新：缺的前件是**占空约定**非车道约定（canonical 反稀释句两分支均杀引理）；A≤1167 与「包不可复跑」降级为包装欠账（下批外发必带定理报告+EVIDENCE_MANIFEST）；勘误一轮完成度声明不实坐实（6 残留），勘误二轮施工中（机器收据验收）；外审连续域区间证明收作 Part F 正式附录。②份2（mixflow）：certified 现役零受伤（③/U-01 均未入 main）；Q4=U-01 已修（忠实几何在 U-01 翻 FEASIBLE，外审反向旁证 wh_drain 必要性）；Q1 降级输入契约加固（冻结池 744,344 端口机身不变量零违反）；**Q6=真重开**（`item_admission_port_exclusion` 授权语句「无谓词消费它」被③禁令自身破坏＋速率引理腿已被 splitfree 打掉）→owner 决策 B1，前置模拟器判例 D1（splitter 拒收语义）在跑；Q5 补丁拒（replay 从零重跑、不消费旧负结论）；U-01 测试组混入几何不可实现装置（同向多主 front，0/82,829 pose）且是守卫独立承重唯一证据→接入批 A1-A5 立案；记忆卡已打「限制口必要性=零已重开」防退化注。③份5（重设计）：22 条 15 ACCEPT/7 PARTIAL/0 整条驳回，行号转述零错误（历次外审最高质量）；四项重写门槛核签后=**三项纯文书**（投影π+WLOG 组合、typed representations、撤过强声明）+两问三格降编辑项+原子发布根移出门槛（owner 决策下游）；P-11 拒（会让陈旧副本拉平正确副本=C-53 复发）；DIFF 改 PROVISIONAL SELF-COMPARISON（对勘前快照任何地方都不存在，同提交入库实锤）；semantics 拆分决策条件改变——纯语义改动本不触发派生工件重生成、拆分增 pin 不减 pin ⇒ 默认推荐**先落传递依赖根 C1、拿实测成本再定拆不拆**（决策页 `verdict/fen5/ADJUDICATION_fen5.md` §11）；WLOG 组合欠账挂 `model_stricter_faces` 台账（随 freeze-ritual 批）。R3 批A+批B 开工。回件+核签全档：`.artifacts/gpt_pro_review_batch_20260807/verdict/`。
| 08-07 | **文字层增删改查落实性审计（owner 提问触发）+ 两飘点闭环**：逐层×逐操作核完——记忆三层与台账层每格有机器或已实战纪律；抓出①手册无查阅入口（CLAUDE.md/项目说明README 零指针，新会话不可发现）→ 补 CLAUDE.md 权威顺序第5条+README 速查层段+文档计数订正 33（`4d0c7ef`）；②vnext `.index` 陈旧只有纪律无机器（半月潜伏坑的遗留缺口）→ opus 席落地机械守卫：`.index` 内嵌 `cards_digest` 内容指纹（免 mtime 假阳性），陈旧时 `context`/`verify` 打 `!! STALE INDEX` 警告+activation log 记 `stale_index` 位，advisory-only 无 auto-apply、hook 路径异常静默降级；15 条新测试进 memory lane（265→280 全绿），实机 build-index 后 verify/context 新鲜无警告、eval 双解释器 34/34；③手册内容现势性无机械体检=真欠账，登记仪表盘 §9 A9（补法=查漏镜头 docs 适配扩 26-28，未来剪枝批）。28 号 E2 与 CLAUDE.md 同批更新守卫事实（无时态「同批更新」纪律第二次实战） | `cc_memory_vnext/zmem.py`+`tests/test_index_staleness_guard.py`；`4d0c7ef`；仪表盘 §9 A9 |
| 08-07 | **份6 模拟器盲推导对勘收官（opus 对勘席+主线程复核）**：四桶计数 CONVERGE 36 / DIVERGE 3 / NEW-INFO 10 / RATE-LAYER 6 组整体隔离（(c) 章速率定律一律不得当游戏事实引用）；40 处行号抽查零引错（2 处「逐字片段」实为改写，按家规不作引文）。**大额收敛**：17 条配方对冻结 canonical 零差异；266 台账被纯外部输入独立复现 17/17 零失配（52 源头槽账闭合）；70×70+外环5格带、边界 L 形总线结构、核心 14/6、箱 6×50、供电 12×12 严格相交全部盲命中。**X1=唯一新拒真候选墙（需 owner 游戏定谳 Q1）**：模拟器有「存货口」loader_1（3×1、1 入、WarehouseSink、直接入仓），canonical A4「有线入仓侧=仅核心」与之矛盾；主线程复核 07-18 §3.2/§3.6 坐实存货口从未上桌（当年只登记取货口）、AvatarHidden 为纯渲染标志（取货口同挂）排除不了它——若游戏真有，则「终产物必送核心/箱」是自加限制、威胁 lex 最优半边；定谳前维持现状+登记已知拒真面。**X2 桥双声明已收口**（owner §7-4 单向公理为权威；机械枚举 21 实体唯桥有两栖面；净双向通行结构上无法终结；掉头 WLOG 零增益）——不进定谳清单。**X3=A8 外部化裁决单点依赖量化**：266 台静态功耗 3310 kW vs 模拟器基础发电 200 kW，若外部化翻案需 3 热能池+4.5 电池/min（吃掉 1/4 电池产量）反噬 266——挂完整性台账说明行。**箱语义精化**：fill-first 定谳两半成立，精确机制=「6 独立单槽组上取最早可收者」（回归测试钉死），freeze-ritual 批 canonical 措辞按精确版写；单槽容量 50 provenance 条目已成档（entity-definition.ts:835-866，模拟器规则层级，仍待 owner 游戏瞥一眼定级）。墙审计喂入行 L1-L10、owner 定谳候选 Q1/Q2 全在对勘书 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen6/CROSSCHECK_6S.md` |
| 08-07 | **X1 存货口当日被 owner 一句话打回并三行推理关案（撤 Q1）**：owner 指出解空间问题该先推理——推导：边界口类设备（取/存同款贴总线规则）只能落左+下 139 格条带（70+70−角1），46 台 mandatory 取货口×3=138 格，存货口再要 3 格 ⇒ 141>139 **放不下**；故任何容纳 266 mandatory 的可行布局不可能含存货口，模型不建模它零拒真，X1 关案、Q1 撤出 owner 题单。前提集（动谁重推谁）：①产量目标冻结⇒46；②存货口贴总线规则=取货口同款（取货口半 owner 07-18 实测、存货口半模拟器同标志外推）；③口体 3×1；④70×70——产量目标变则重推（与仓库桥条款同触发器）。**流程新规（owner 令）：解空间类问题上桌前必须先过推理关**——推得动就地出结论带前提集，推不动才升级且须点名缺的最小前提，不许裸递。定性=派生闭包公理的现行病例（前提全在同一份对勘书里、无人做乘法），标本喂 6S-乙 对照与重设计病例集 | 对勘书 addendum `.artifacts/gpt_pro_review_batch_20260807/verdict/fen6/CROSSCHECK_6S.md`；记忆卡 rule-derivation-closure-axiom |
| 08-07 | **owner 权威纠正：口述即游戏定谳级（单槽 50 闭案）**：我把箱单槽容量 50 的出处描述为「源头是 owner 口述」并请 owner 游戏再确认，owner 纠正（原话意「我的口述不算游戏实测吗？那这个项目还怎么做」）——口述历来就是权威序第一级的交付形态（07-18 五答、08-06 公理终审皆是），不得因「只是口述」降级待核；唯一合法追问维度=「条款还是例子」（08-06 箱 6 种前科）且形式=直接问。**50 定谳为条款级**，模拟器 entity-definition.ts:835-866 逐字 [50] 为佐证 provenance，随 freeze-ritual 批机械写入 canonical；箱案槽数维度前提转「已定谳待写入」，redesign 决策摘要第 1 件收敛为仅剩 ③墙审计优先级。记忆卡 owner-testimony-is-game-authority 立卡（evidence-grade 表 owner 口述列最高级） | `docs/research/rule_system_redesign_20260807/OWNER_DECISION_SUMMARY.md` 第 1 行订正；记忆卡 owner-testimony-is-game-authority |
| 08-07 | **B1 登记订正（owner 抓获）**：owner 压缩前那句「懂了，那先放着，因为我们需要先系统性的梳理一次游戏规则对解空间的影响」**就是 B1 的决定本身**（=维持现状，随系统性梳理/墙审计首轮带完整清单回桌，准入口为种子案例），我错记成「暂缓待决」反复回挂 owner 题单。已改：26 手册两行、记忆卡 B1 段同步为「已决」；owner 现役待决只剩墙审计优先级排序（首轮清单出来后） | 26 手册 §7/§10 准入口行；记忆卡 machine-input-no-selectivity-pollution |
| 08-07 | **份3（U-01 批 Q7-Q19）核签收官（opus 席，worktree 全程只读实证）**：外审 23 项判定=17 ACCEPT/6 PARTIAL/0 REJECT，总裁决「c6a9f8b 不应接入」成立但理由重排（撑住它的=Q15.3/Q17/Q14；Q7/Q8b/Q18 按份2 先例降输入契约加固）。**①两个拒真反例机制成立、外审装置不合格、核签重建忠实装置翻转复现**：原装置一个要核心机身开洞、一个要三台核心且 9×9 塞 5×5 内腔（全物理不可实现）；核签从冻结池取真 pose 重建（内嵌四条可实现性断言），cell-key INFEASIBLE→layer-key FEASIBLE、rank ON INFEASIBLE→OFF FEASIBLE 原样翻转 ⇒ wh_drain 改格层键+删 rank 两条实锤修复进接入批（A2/A3）；rank 定性订正=新放宽面内过严残余、非回归。**②Q14 反转**：不是证据包不全——canonical 全文零 fill-first、发包件与 main 逐字同 ⇒ DESIGN §11.5.2(a) 真缺前提（与 26 手册:96-97 同句），已在案 freeze-ritual 挂账，外审独立撞同一处。**③核签自挖新缺陷（外审自己埋掉的）**：classify_sink_receiver except 分支把瞬态失败写进程级缓存 ⇒ 一次故障 protocol_core 永久降级 machine、产带证明力假 INFEASIBLE（拒真半边），实测坐实，修法廉价（失败不进缓存+fail-loud），进接入批 A1 同级（A1b）。**④Q19 双向订正**：外审六 delta 全对、我方卡事实断言全对；但非多变量混杂（单旋钮+确定性下游），四个「竞争解释」实为放宽面构成成分；唯一独立未测竞争轴=吸收出口空间分布 ⇒ 记忆卡正面结论降级为未隔离假说（已改卡）。Q11「replay 重建不同模型」REJECT（replay 从冻结输入整链重跑）、但剥字段事实成立=我方 §11.12 前置4 原话；Q13=订正没传播到份3 拷贝（C-53 族）；清单外#2 坐实=份4 后第二起发包漏件事故（zz_optional 全没进 zip）。接入批并集=我方 5 条+外审新增 8 条（核签书 §六）。owner 新决策点=0。诚实边界：现有探针证的是单元级过严面，升「全局最优布局被拒」还缺全基地见证 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen3/ADJUDICATION_fen3.md`＋adjudication_checks/ 7 收据 |
| 08-07 | **份6S-乙（推理范式盲设计）对照收官（opus 席）**：与重设计线=同一问题两份独立答案，**78 可比构件 46 撞车（剔 OUT-OF-SCOPE 后 64%）**——账目类几乎全撞（它的流量账本/有限缓冲活性/批次槽位端口联检与我方余量审计表七行逐行对上，**含 08-07 从箱案倒推的「入量×周期 vs 容量」行=拿到独立外部旁证，已注入 owner 决策点 6**）；行号抽查 15/15 零错。**偷师清单 10 条**按批排定（头三：M-02 结论形态检查+K-07 强度闭合→批2 schema；含糊词强制展开表→批0 纯文书；K-04 超边表示法（=owner 派生闭包公理数据结构化，5 满 1 半五前提塌点在 pairwise 可达域外的现成填法）→批1/批C，候选簇来源换成我方可用三源）；**订正主线程两条预判**（useGate 不偷——消费侧闸更强且 D-17 三重实证条目内声明挡不住；M-01 差集形态在我方已被 C-15 证伪过）。**头号分歧=它整套体系单审计方向**（只防结论比证据强、零构件问「合法的被挡了吗」——问题结构使然非疏忽）⇒ **立引进纪律：每偷一件必须同批答出拒真侧对偶，答不出标单向构件**。副产物：我方保证强度七档尺子跨体系试用出活（发现它完备性判据未标注的循环：实际依赖=登记依赖两边是同一集合两种写法）=七档转正旁证。owner 新决策点=0（决策点 6 旁证已注入既有行） | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen6/CROSSCHECK_6S2.md` |
| 08-07 | **份1（canonical 四条款）核签收官——GPT Pro 六份全闭环**：外审 14 条判定=12 ACCEPT/2 PARTIAL/零推翻；其独立 Fraction 复算脚本仓内复跑逐字节同、28 处 file:line 抽核全准、被疑幻觉的两个 commit id 实为逐字抄自我方冻结件（但我方原句本身归属写错+基准过时两缺陷，改稿时重写）。**①⑥仲裁：份1 与份4 无冲突，冲突是我方 PROMPT 串台**——份4 删的是定理 1（存在型，铺道落进结论⇒前件冗余）、份1 保的是速率引理（禁止型，铺道造反例 11/24⇒前件承重），同名前件在单调性相反的两定理里地位相反；组包席把两结论压成一句「可删」发出、被外审拒收=外审起了该起的作用。份4 核签书免勘误+贴防混淆注，PROMPT_1/INTERNAL_NOTE 留痕订正，记忆卡 sibling-line-receipt-paraphrase 添第二实锤+新判据（转述「前件可删」必带结论形态与单调方向）。**②⑦证据等级订正**：Opt(M)≤lex Opt(G) 是我方 PROMPT 亲手给它的论证，其 ACCEPT=确认非独立推出，任何文书不得写「外审独立复认双向保真公理」；外审真净增量=登记表不可当语义前提+sink-front 按口类拆。**③X1 关案给 #21 修法加第二层**（外审只有口朝向层，格数层它不知道）。**④speed=份1 三前件 (i)(ii)(iii) 为份4 要求的严格超集**，rate_lemma 改稿按它走。**⑤主交付物=freeze-ritual 条款改稿清单 21+5 段**（采纳原文 12/改写 9/新增改期合稿 5，§3 按条款分组带 pin 站点实测），连同 C2.4 合稿纪律（保留 owner 08-06 槽数定谳措辞、fill-first+容量 50 连 provenance 同批入册）与 C2.7 合稿纪律（份1 statement 腿+份2 authority 腿必须合并采纳）。**owner 新决策点=0，B1「先放着」不受影响**。仓内承重档比发包副本旧两处（C26）挂账 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen1/ADJUDICATION_fen1.md`＋adjudication_checks/ 7 收据 |

- **2026-08-08 canonical freeze-ritual 批落地**：`rules/canonical_rules.json` `b675fb6a…`/40,371B → `c3fc3a34…`/59,989B（26 段改稿：rate_lemma 三前件重写＋usage_rule 禁无前提引用、箱条款 fill-first＋单槽 50 入册（owner 口述定谳级，模拟器 entity-definition.ts:835-866 佐证）＋cache_parameters 建档、terminal_clause 口岸三分法＋实例级 discharge 注＋X1 条件式格数腿（四前提入册，存货口贴边半边明标模拟器外推=R4）、model_stricter_faces 4→6 项＋usage_rule/completeness 两兄弟键、准入口降格 scope restriction＋条件式 authority、A2/terminal_clause 引链修复、scope_premises 归属订正）。草案链 v1→主线程七裁→v2→对抗复核【修 4 处后可落地】→v3（F1-F4 修复，V2_TO_V3.diff 恰 3 行 JSON 替换，主线程逐项终核）。落地=opus 落地席按 RESEAL_CHECKLIST 执行＋主线程终核提交：18 pin（2 大写、1 处 .rgignore 藏）＋Chain B（close-kernel reseal，checker 自钉 8c807086… 亲手重算复核）＋Chain C（preflight parity 8c2e5bf3…）＋Chain D（lock 6+1 继承 105cd379…＋antecedent 重算 d2f15e02…，由 test_w0_d6_gate 活验证）＋C24-C26 承重档订正＋scout_pin_chain 快照注。门全绿：两 checker 期望串逐字命中／preflight --full 20 passed／slow lane 33 passed（319s）／定点复跑 184 passed（日志 .artifacts/canonical_reseal_20260808/）。残留扫描亲手重跑：旧 sha/size 命中全数落在 §1C 史料名单＋本批档案 before/after 登记＋已点名假阳性。26/27/28 三页同批（§4.1 两本账三条⚠、§7 准入口行、§8 六项＋两键、§10 退役表、§11 两欠账结清）；归档 docs/research/canonical_batch_20260808/（5 件）。残留：R1 冻结件首含 CJK（strict_json/schema/pydantic/loader 实测全 PASS）、R2 单槽 50 等 owner 游戏侧升 evidence_grade（一字段）、R4 存货口贴边规则半边模拟器外推（销账=owner 游戏瞥一眼或产量目标变更触发重推）。绿灯≠owner 关门动作，本批不产生任何 release closure。

- **2026-08-08 owner 深夜两笔口述定谳（条款级，随 7/8 号组包对话给出）**：①协议箱**单槽容量 50 = 条款**（08-07 已按口述权威闭案，本次 owner 直答「条款」再确认；发现 e3a2b91 落地件 `cache_parameters.evidence_grade` 把 50 错归模拟器级——起草链沿用份6 对勘书早于口述权威裁定的过时框架、主线程终核漏抓，属**保守方向错级**不危及 soundness）；②**仓库存货口与取货口只能放在仓库基线上 = 条款**——X1 关案前提②的存货口半边由「模拟器外推」升格 owner 定谳，**R4 欠账销账、X1 四前提全齐**。两句 canonical 订正挂下一次动 canonical 的批（26 手册 §11 已登记新欠，含精确目标句）；不单独走 reseal。7 号包 DESIGN_DOC §2.2 前提表/§4.2 验证预算样例同步改（zip 重打；剪贴板文件条目是路径引用，自动指向新包）。owner 桌面清空至仅剩墙审计首轮优先级。

- **2026-08-08 7/8 号核签双收官（GPT Pro 批 20260808 闭环）**：**7号**（推理机设计稿对抗审查）=55 ACCEPT/3 PARTIAL/0 REJECT，本批质量最高——根发现[01]「判断须带上下文索引(problemHash/objectiveHash/contextHash)」统摄六个我方未见的可靠性洞；[23]探针方向修正（「负结果反向安全」仅限 A/B 红利语境，证排除时假 UNSAT=假排除，记忆卡已订正）；种子「缺引理只浪费电」兜底论证被判**有前提**（[01]落地前完备性与可靠性不正交，种子已改）；对勘=小棋盘穷举**硬独立撞车**＋「零消费公理当目标源」我方独有压过外审；五设计决策全带推荐、一期 44-56 人日三处改造（实验集撞 prod-scale 单跑铁律→缩尺）；核签自查出[30]归属微错+三处严重级失准；5 决策点全并入立线拍板包不上 owner 桌。**8号**（混合盲推）=防火墙机械执行：15 条 D-* 全入自洽性审计池、169 条注册表事实入准独立池（P1 九机型配方数全表=A9 定量 provenance；P2 70×70+外环5 第二次盲确认；P3 准入口上限 30/min=恰一条带容量）、4 违规（3 条系方法自身缺认识论强度类逼出）；流量抽象体检 41A/3P/0R——**承重头条**：外审指控「方法无跨作业汇总约束」（X-5）成立，核签席进一步自算 266 台账 Σceil−ceil(Σ)=**恰 2 台/34 格**并以推理关**就地关闭**（合并机输出必混流⇒需分拣⇒唯一器件=准入口=面(6)省略对象⇒已建模域内 264 不可达、266 零拒真）——**面(6)省略代价首次量化（≤2台/34格），墙审计种子案例得数字**；两笔 canonical 欠账登 26 §11（「每台机一 operation」前提补登＋「15件/周期」provenance 挂 A7）；传输抽象敏感区 6 条、S5 稳态台数零分歧=抽象保真旁证、**owner 定谳项零条**（「266 还是 264」被推理关拦下未上桌）；P2.0 流量语义喂入清单 13 条就绪（第一优先=「通道」对象的唯一映射，我方 belt/port 两个 per-tick 量正落在空缺上）。批闭环：零新增 owner 决策点；下一步=设计稿 v2 合稿（fen7 ③修法清单 20 项三层＋④合并裁断三条＋种子 §5b-5e）→立线拍板包。
