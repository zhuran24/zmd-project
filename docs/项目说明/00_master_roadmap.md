# 00 — 总路线图（master roadmap）

> **本文档的地位（先读这段）**：全项目工作线的**总图 + 排期快照 + 指针**，
> 2026-07-05 起立此存照。它不复制各阶段计划的细节（细节仍在 08/09/10 与
> docs/research/ 各设计稿），也**不是**状态权威——release 边界以
> `PROJECT_LOCK.md` + gate JSON 为准，当前实现状态以
> [06_current_status](06_current_status.md) + [soundness_gap_roadmap](soundness_gap_roadmap.md)
> 为准，主线执行序以 owner 拍板的排期卡
> （`cc_memory_vnext/cards/p1-2-closeout-then-tcb-backlog-order.md`，
> **以其正文 2026-07-04 晚修正版为准**）为准。本文档过时时，以上述权威为准
> 并回来修这里。
>
> **为什么有这份文档**（2026-07-05 盘点结论）：此前"阶段之间的总图"散在
> 05 号汇总表、排期卡与各研究稿里，没有单一入口；且 2026-07-04/05 两天
> 新增了整条形式化验证线（P3.0 双轴）与吞吐改判（P2.0 必做），旧计划
> 文档没有它们的位置。08/09/10/13 是"史料+现行混排"的 ledger，**保持
> 原样加注、不重写**；总图由本文档承担。

## 0. 一句话现状（2026-07-18）

P1.2 认证链 **CLOSED**（2026-07-07 owner `owner_manual_decision`）。P1.3 进行中，
三条活跃工作线的位置：

| 工作线 | 现在在哪 | 下一步 | 等谁 |
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

| 07-19 | 值夜批：RAB-on SIGSEGV 复现销项（clean 逐字一致；根因=内存超频环境层）+FCL 生产 lift A/B 收齐（on 臂 0 cuts/2.4h→lift 默认 OFF 维持）+owner 第 4 笔域缺口定谳（未启用口朝外/被堵合法）→codex 修复池 82,829+严格三层规格书（validator 不外发）→合并 `b1cf014` 终态门双绿；R1 严格版外发 GPT Pro；rounds 1-5 重跑清单三梯队；stop hook v1.7（23 键泄漏修复） | `front_offset_incident_20260718/03`-`04`；`cleanroom_rederivation_20260718/strict/` |

### 0b. 方法论：规则归属判据 v2 → v2.2（2026-07-17 三轮推出 v1/v2/v2.1；07-18 两轮补 cut 方法论与四问统一）

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

### 1e. P2.0 吞吐认证（owner 2026-07-04 改判**必做**；旧文档"圈外"口径作废）

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
