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

### 0b. 科学面方法论：知识与计算的归属判据（尺度无关）v2 → v2.6（2026-07-17 三轮推出 v1/v2/v2.1；07-18 两轮补 cut 方法论与四问统一；07-20 干净房间 R2/R3 外部收编；08-03 管线门序泛化；08-03 夜门内归属四则+分层重排）

> **【操作卡·日常入口】适用域=科学/求解/数学面的**任何**「知识×计算」分解边界（v2.6，见文末声明）。本节自 v2.5 起分两层：这张卡是执行入口（按决策时刻排的六问），
> 其下正文各版本块是推导依据与判例库，内容互为映射；日常按卡执行，起争议回正文仲裁。**
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

## 7. 阅读入口（新会话/新协作者按此序）

1. `PROJECT_LOCK.md`（release 红线）→ 2. 本文档（总图）→
3. [06_current_status](06_current_status.md)（当前状态）→
4. 排期卡正文（主线执行序）→ 5. 对应阶段的细节文档/研究稿。
| 08-03 | **剪枝 v2 P2 全线落地（记忆管道修复 + 冻结迁移 + 主批，merge `a7af533`/`d693f89`）**。①**前置三修三轮**（载荷 summary/机器消息跳注/跨层 find + 两轮加固）：P2.2 按 **§3d-bis 军备竞赛退出判据**（新立）退出两张噪声卡的 error_regex 赛道（历史真阳 0），蛇吞尾排除做成 hook 机制（governance_target），find 只读全路径不变量+degraded miss 如实申报。②**cc_memory 冻结迁移**（owner 批）：主席亲判 15 项——3 处迁出（cut 触发机制/pytest-forked SOP/codex 不自动读）、12 处原地存档，最后写入=存档地图条目+truth fact 订正（`e6840c9`）。③**主批+修复批**：记忆层扫描器 `memory_reference_scan.py`（orphan/dangling/never_read/said_card 四 flag，首跑真阳 orphan 1 + 案例4 实锤）、docs 两小调后稳态 0 候选、冻结机制面（boot 横幅/写警告/hook 档案口径/post_tool_shadow 解线）、zmem schema 放宽（pitfall 不再强制 error_regex）、**记忆层 265 测试首次挂进 preflight [memory] lane**、authority pin successor 登记（`ddc75270`，循 8292983 先例主席授权）。codex 对抗审查 BLOCK 15 条→§3d 分诊：修 11（逐条用 codex 落盘 PoC 红前/绿后翻面）、内鬼类 4 声明（07-06 裁决）、deliberate 1 接受。合并后独立 full preflight 19+1 门全绿。**基线判定**（`p2_first_scan_findings.md`）：docs 0 候选稳态保持；memory 9 候选逐条核=**未兑现记忆欠账 0**（静态基线，新 item_id 才是信号）。剩余：P2 收尾批（查漏 LLM 镜头薄 runner）+ P3（两度降级） | 分支 `prune/p2-prefix-fixes-20260803`、`prune/p2-main-20260803`；`.artifacts/prune_v2_20260803/`（design_v2 §3d/§3d-bis、p2_first_scan_findings、preflight 双日志）；codex 封存 `/tmp/codex-security-scans/zmd-pj/6b2fb40_*` |
| 08-03 | **剪枝 v2 P2 整线终结：查漏镜头收尾批 + 首轮真跑（merge `0a4e44c`）**。①确定性外壳 `memory_gap_lens.py`（assemble 指针化证据包 + verify 落地核验防幻觉，无 apply 通路 AST 闭合白名单钉死）：codex 聚焦审查 BLOCK 4 条全修（空白 quote 长度闸/SQLite immutable=1 承 mem.py 先例/黑名单改闭合白名单/surrogate encode-first+候选级 drop），每条 codex probe 红前绿后翻面，合并后独立 full preflight 全绿。②**首轮 LLM 座席（opus）：11 条候选，落地核验 11/11 存活零幻觉，主席裁决 11/11 全采纳执行**——7 条 CORRECT（两张 L0 状态卡现势订正 `d7cbeb9`：批C/ab16 收官入卡、M5 头条补 front 修正前口径条件；5 处文件记忆 description/索引漂移修复）+ 4 条 ADD（对外介绍口径卡/自加固循环失效模式卡/Fable-only 拍板 Why 补录/fixture 绿灯一般化判据）。③**副产实锤**：eval 假红溯源发现主树 `.index` 停在 07-19——P2.2 清空的退役 error_regex 在活 hook 里半月未生效（卡=真相源、hook 消费编译缓存），重建后 34/34 绿；「build-index 必须在主树跑」入纪律卡（`51ad1cf`）。P3 文档语义镜头维持低优先级 defer | `.artifacts/prune_v2_20260803/`（p2_first_scan_findings、gap 座席产出 scratchpad 存档）；`.prune/memory_gap_{evidence,candidates}.json`；分支 `prune/p2-gap-lens-20260803` |
| 08-03 | **W0 D6 验证链从未真跑过——两层互相掩护的缺陷挖出并修复（`3c7680a`）**。承 ab16 收官「6 硬编码路径测试耐久修复」欠账线。①表层：`test_w0_d6_{gate,replay}.py` 的外部输入路径写成 `~/下载/w0回复/`，真实目录是 `~/下载/gpt回复/`，而仓库内 `cleanroom_rederivation_20260718/15_w0_recon_artifacts/` 有逐字节同份 tracked 副本（三方 sha256 一致）→ **45 条测试自落地起 100% 静默 skip**。②被掩护的深层：`project_lock_sha256` 钉的 `a2ec971f…` 声称「当前 checked-in successor」，实测在 `PROJECT_LOCK.md` **51 个历史版本里零命中**（也不等于被 revert 的 `62bc65f` 时点值 `114ea93e…`）=未落地状态算出的幻影，钉在 5 处代码+README；那 45 条只要真跑一次就必红，因 skip 三周无人知。③修法：路径改指仓库内 tracked 副本（测试自带期望哈希即时验证）；lock pin 改钉真实 `64a68024…`——安全依据=D6 历史 root 绑定 `e8130589…`（`57c8b352`）到当前的 110 插入/123 删除**全部落在 AB16 段**，§3B「W0 D6 research-only artifact protocol boundary」逐字未变，新版头部明写 `prior certified, W0, P1.2, Stage B boundaries unchanged`，历史 root 绑定值不变；antecedent fixture 连锁 `94f72b64…`→`7de91e64…`（lock scalar 进 canonical hash，门禁解释器独立重算复核，非新 solver 结果）。**结果：全量门禁 skip 170→125，45 条复活全部通过，独立 full preflight 20 门全绿**（首轮那条 `test_wait_observer_parent_death_sigkill_releases_stopped_child` 经 stash 对照+隔离单跑+二次全量三重复验判定为负载敏感 flaky，非本批回归）。同线核实：R11 过期文案已由 `d5386c4` 修、`host_gate_quarantine/` 已不存在，剩 2 处硬编码路径为 `pytest.fail` 诚实形态不动。**新登记同族隐患**：`test_placements.py` 5 处「池空即跳过」（当前三池非空不触发）、R4 那 4 条等的 `.artifacts/track_b_r4_…` 产物在本机含外置归档全不存在 | 本行；`silent-skip-hides-two-layer-debt` 记忆卡；`.artifacts/prune_v2_20260803/preflight_w0fix{,2}.log` |
| 08-03 | **剪枝 v2 P2 自检轮：扫描器吃自己的狗粮抓出自身判定域缺陷并修复（`fe5fa2b`）**。用当天的记忆扫描器验收当天的卡片工作：orphan/断索引 0、said_card 9→6（当天立卡兑现 3 条历史承诺）；但 dangling_wikilink 14 条里 10 条实为**健康跨层引用**（`[[链接]]`只在引用卡同层解析——三层记忆系统里跨层引用是被鼓励形态,判定域写窄=flag 被噪声淹没）。修=判定域扩为三层并集（档案层 `immutable=1` 只读零侧车、缺失降级宁多报不崩），真仓 **14→4,剩 4 条真悬空恢复 FYI 信号价值**（=值得写而未写的卡）。测试改写钉旧语义 1 条+新增 3 条,红前证 4 条全红,43 passed,独立 full preflight 20 门全绿。注记:不违反 §3d-bis（那管加精度,此为在错误集合里查找）。副产入卡 `sqlite-readonly-immutable-sidecar-trap`（裸 mode=ro 侧车坑 08-03 一日三咬,已修先例不自动传播,委托任务书应显式点名仓内先例符号） | 本行；`.artifacts/prune_v2_20260803/design_v2.md` §5、`preflight_wiki.log` |
