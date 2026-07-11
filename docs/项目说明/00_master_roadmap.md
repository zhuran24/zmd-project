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

## 0. 一句话现状（2026-07-11）

P1.2 认证链 **CLOSED**（owner 手动门 `closed_manual_owner_decision`，P1.3 已开放）；
close-kernel 外审已画线收口（2026-07-03），PR2 #5 合入 / #7 通电（07-04）；
三轮换轴收口外审（权限结构 / 数学语义 / TCB 线诚实性）共 24 簇、
0 个真·上-TCB soundness 洞，owner 已于 2026-07-07 显式 `owner_manual_decision` 关门；
**P1.3 已实质推进（2026-07-08 单日 M1-M4）**：attach sizing spike GO
（verdict 见 `docs/research/p1_3a_attach_sizing_spike_20260708/`）；M2 语义
前置三批（F7 stencil 统一 / F8 整族退役-owner 游戏规则拍板 / F3 方向表修正）；
M3 四批（F8 物理删除 / literal 复用缓存 solve 开销 -88% /
`step_8_apply_to_master` 通电+F1 首族翻译 / LBBD 接线+`EXACT_CUT_FRAMEWORK_ATTACH`
unsafe 默认关）；**M4 七批完成（owner 2026-07-08 发话后同日收口）**：attach 链
四族通电（F1 ghost 条件化修复 / F7+等价回归+运行时闸 / F6 SoT override /
F5 全链——BLOCK-2 封口+canonical_relabel+query_liftable 合同+
binding_empty_domain_v1 真 adapter+P-HOM 结构门）+cut 预算闸（2000 满即停发）；
F2/F3/F9/F4 保持 fail-closed（终态理由见 `p1-3-m4-ladder-landed` 卡，非遗漏）；
close-kernel 现 66 sinks（B1.5 后）；**旧 M4 三前置已齐不等于可直接升格**：07-11 Stage B 规格把剩余前置细化为 B1.5-B5（B1.5 已落地）、PIC C/D/E、RFC-002/003 与最后 B6 owner promotion；M5 第一阶段（可行性实测）2026-07-08 收口（本机+Linux 同硬件全配置无首解，
`p1-3-m5-phase1-verdict` 卡）；**M6 诊断课题（owner 2026-07-09 立项）已收口——
首解之墙 = 供电覆盖约束及其 witness 编码（八实验隔离、单一主墙，终报
`docs/research/p1_3_m6_diagnosis_20260709/07_final_diagnosis.md` 与
`p1-3-m6-power-encoding-diagnosis` 卡）；修复方向 owner 已拍板 a+c（2026-07-09）：
**C 修复当日落地（dedup+reseal，`c3d64c4`）；A 批 0 头对头当夜破墙——C1（杆侧
pose 布尔+cov 通道）在完整 266 实例 + 6×6 ghost 上产出项目史首个 master 解
（OPTIMAL@541s/w6，独立复验六项全过含 unforced，w12/w24 OOM 内存条款成立；
C6 判负；`docs/research/p1_3_a_batch0_20260709/README.md`）；M6 头号悬案
「供电可行布局存在性」关闭；同夜 GPT Pro 双轨外审（全项目 bug 审 3 份 + 工具链
评估 3 份）——生产证明链零 BLOCK 三重背书，产出硬化批（attach integrity P0
bypass 修复+dedup 去 proto 反射+footprint clone 绑定，`c7cd6a0`）；批 1
（C1 certified 化）owner 拍板开工：任务书 1A-1F
（`docs/research/p1_3_batch1_design_20260710/00_batch1_workplan.md`）,
1A 骨架已落地（开关默认关、双审 3 BUG 拦截、慢 lane 绿，`b755e80`）,
1B 已落地(cov 通道+witness cell 语义,三轮审查链修 7 实锤,`705ee73`;
seal 依赖 floor 按 CachyOS 宿主重钉+redlines 首次全绿,`a02862a`;慢 lane 30/30);
1C 解级 dominance 剪杆已落地(normalize_certified_power_pole_dominance 纯函数+routing
FEASIBLE 唯一生产点接线,fable+codex 双审首战 6 项修复单全落,`3cc3cf4`;golden digest
双 pin 重钉——proof_summary 新增 power_pole_dominance 审计 key 的预期漂移,`fbc315a`;
慢 lane 30/30);1D C1 编码转正 certified 默认已落地(翻默认五处+witness 7 env
原子移除 unknown fail-closed+S4 防御断言+pre-1A 恢复 direct rebuild,fable+codex
双审第四次规格盲区实证,`a1ae1ed`;终审扩展面:C1 空 powered 义务提前返回+验收盲区
16+1 失败全修——第五/六次盲区实证,含慢 lane witness 真实工件回归显式退回 `fecb495`;
reseal 不动点长链 semantic projection+runtime anchor 首次触发;golden 双 pin 重钉;
慢 lane 30/30);1E 义务层 reseal 已落地(第 15 条义务 PO-CERTIFIED-POWER-POLE-DOMINANCE-NORMALIZATION 入册——14 required_tests+domain faithfulness 追加 1D witness env 负例,checker 双注册,reseal 一轮收敛,字面锚对时 15/65,`4d98314`;验证=义务文件 347 测分族全覆盖+0871b10 对照洗清(解释器间歇病 7 崩三形态物理证据入 memory);慢 lane 30/30);旧 witness
编码 owner 已拍板不留（2026-07-10：certified 层不保留 runtime env 对照/回退）;
1F 生产 replay 与内存条款已落地(A 段=wrapper cgroup 硬帽(--scope+expand-env=no+连通性
探测+值校验 fail-closed)+w6 注入+gate RSS 三档分层(runtime resolver 单一真相源)+C1 真
工件回归,fable+codex 双审第三战 codex 6 BLOCK 全实锤+8 项修复,`f0a7cd4`;B 段 smoke 五连
实验暴露 42G 帽下 6×6 直建撞帽,初判「产品化双回归」,gate w6 档按死值回填 44G,evidence=
07_batch1f_evidence.md,`882287b`)。**批 1 六批(1A-1F)全部落地**;**M5 归因线四刀判决
(2026-07-10 晚)推翻双回归**:第三刀 88f65a5+原型完美复现 b0_4r(OPTIMAL@525s/branches
498 万/conflicts 逐位同=solve 确定性),第四刀产品+原型参数+无帽同样出解(506s)——真相=
**C1 出解时刻有固有 ~60G 级大分配尖峰(RSS>42G+swap 18G),42G 帽+禁 swap 恰好斩断生路**,
「w6 温和<20G」是 30s 空采样假象;产品与原型同分布,family×ghost 网络无害;归因文档=
m5_c1_memory_attribution_20260710.md;**M5 A/B 战场正式解锁**(条款修订已落:wrapper CAMPAIGN_SWAP_MAX 默认 20G+gate 稳态
模型,第五刀实测背书,`b25ba1d`);cut framework 通电前修复批已落地(F1 ghost 轴反置
soundness 修复+F2 scope 全 map 严格相等+F3 step_8 入口完整性纵深+F4 类型卫生+docstring
轴序双修,opus+codex 双审首次零 BLOCK+Workflow 编排首战,慢 lane 31/31,`68b4557`;
replay 诊断残留记 TRIAGE 留通电线);
M5 A/B 战场随首解解锁,挂批 1 完成后**;
**P1.3A attach 通电 spike 进行中(2026-07-10 晚)**:规格书 `docs/research/p1_3a_attach_power_on_spike_20260710/01_spike_spec.md`(`90be2c6`+追加);E1 端到端 exploratory 路线四连死破案(py-spy 抓栈实锤 `_add_port_clearance_constraints` exploratory-only 启发式 prod-scale 爆炸+legacy master/all_facility 双重不可比,教训入 memory 卡)→**形态修订为 certified 直建 harness+step_8 直调**(sanctioned direct 通路);E1' 基线已落(OPTIMAL@513.5s,与第五刀同分布);E2' 通电对照已完成——**判决 GO**(10K cut attach 16.6s+solve +4.1%,总 wall +6.9% 远低于 50% 线;proto 约束 ×4.15 无感;效度边界四条+agnostic-F5 语义缝 TRIAGE 见 02_spike_evidence.md);checklist 已立(03 文档,PIC-0~7+批次划分)且批 A 主体 PIC-3 已落地(`b9fcca9`:BUDGET env 化+fail-closed resolver+双注册,opus+codex 双审,reseal 一轮收敛,慢 lane 31/31);批 B ✅完成(07-11:PIC-0 owner 拍板 (a) certified promote+PIC-1.1 判定双审定稿 `66ccb39`);**阶段 B 工程规格书 ✅定稿(07-11,`cut_framework_review_gpt56pro_20260710/03_stage_b_implementation_spec.md` v3:codex 三条侦察+两轮 opus/codex 双审 53 条全采纳无一驳回,B0-B6 批次序列立,B5≈16 pinned 文件 wiring cut-over,B6=owner promotion)**;阶段 B 工程开工当夜连落三批:B0 ✅(`de2df50` 契约测试壳+AST 守卫)+B1 ✅(07-11 晨,FrozenArtifactBundle+snapshot 层+digest v1,双审 codex 攻击实证 8 修复,新 TCB 双文件 floor 注册)+B1.5 ✅(07-11 晨,typed 平台层:三分支代数+单入口+F5 oracle 复验全通路+v1 adapter;双审 10 BLOCK 8 组修复全落,typed_platform 进 sink 台账 65→66+投影 floor 三层连锁 reseal)+B2 ✅(07-11 午,F1 纵切:CutScope raw preimage carrier(方案 A)+assumptions 复验前移无条件化+投影含 slot 身份+F1→COMPILABLE+双拒 differential;侦察三缝先拍板、双审 6 条全落、codex 中断主会话接管;五 pinned reseal+plugin 进 floor;cuts 全量 643)+B3 ✅(07-11 午后,F6 纵切:shape_packing_hall_typed plugin(12-phase snapshot-native 平价+fingerprint 照 F1 定格)+oracle preimage 捕获(恒 ghost-bound)+F6 projection+registry COMPILABLE+借名测试迁 cutset 一次搬干净;侦察=主会话三路 fan-out(codex 通道中断期)九项拍板先行;双审 codex 抓 literals=() 真放宽洞(framing 前拦截修复)+VALIDATED 出口跳检(requires_ghost_bound 声明式封死)等 7 条全落;stale-exterior 新收窄追认;cuts 全量 712;reseal 四文件+新 plugin 入 floor)+B4 ✅(07-11 傍晚,F7 纵切:power_hitting_set_typed(八段平价)+requires_ghost_bound+F7 projection 含 coverer rows+blocked digest 公共原语;双审 codex 抓 JSON-native TOCTOU/冻结宽容真放宽洞(原子冻结遍历修复);cuts 777;阶段 B 族纵切全部完成,剩 B5 wiring+B6 owner)+B5a ✅(07-11 夜,wiring cut-over:typed 链首次通电进 benders 编排三路 match+typed_apply plan interpreter(新 TCB)+resolver(ModelScopeBinding 唯一构造)+step_6/7 attestation 化(violation filter 退役追认)+F5 apply 物理删除(PIC-2 消灭)+replay 双表(PIC-6 清理);实现=主会话 fan-out opus(codex 通道死);双审双 opus:设计 AGREE_WITH_AMENDMENTS+攻击 PASS 七面零逃逸;reseal floor 5 重钉+2 新增+sink 3+自钉;cuts 769;B5b 收官)+B5b ✅(07-11 深夜,AST lockdown:add_*→_lower_* 双层改名+F5 物理退役+AST caller 钉+getattr 旁路拒绝(59 桶 TRIPWIRE)+precheck 前移原子化+F6/F7 8 skip 迁移 typed 全链+哨兵 5 转绿;双审设计 AGREE+攻击 PASS,5 LOW 三修一注记;reseal floor 4+sink 3+自钉;cuts 773;**阶段 B 工程面全部完成,仅剩 B6 owner promotion 手动门**);M5 A/B 首战(07-11 凌晨四刀)已把「默认参数病态」证伪关闭(smoke#4 实死于禁 swap 旧条款;修订条款下默认组合 OPTIMAL@649s,参数仅 wall 差异 +3.6%~+27.8%,PIC-7 关闭,证据 m5_ab_param_bisect_20260711.md);
防蓄意内鬼硬化桶（#8 深化/#2/#3/#5-F/#9b/#9c/Option B）延期到发布时点，#9a 为部署时点任务；
形式化线（P3.0 轴 A）68 条定理两轮外审闭环；吞吐（P2.0）已改判必做、
设计稿 v2(含 v3 终审) 完成；证书侧（P3.0c 轴 B）路线图定型、待开工。

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
退化 <50%）。**这是全项目唯一真正的研究级风险所在**（cut 体系接上后收不
收敛没有理论保证，只能实测；退路见 §4 拍板台账 L11）。
主体 = active F1-F7+F9 的 production integration（F8 retired）；F1/F5/F6/F7 direct Step-8 已落地，当前按 B6 owner promotion(B0-B5b 已全落地,阶段 B 工程面完成)，未变）

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

## 4. 拍板台账（owner 未决事项，集中登记）

| # | 事项 | 现状 | 影响 |
|---|---|---|---|
| 1 | Q1 状态改写（拆 Q1a/Q1p 进 05 号） | 建议已成稿（Q1a 稿 v2），待裁定 | 05 号 Q1/Q14 行的分级与措辞 |
| 2 | L11 命题降级退路（钉 blueprint 只证剩 41 个） | 挂起（算力墙的最后退路） | P1.3 实测不收敛时的 Plan B |
| 3 | GitHub 远端推送（main 停在 07-01） | 待定；建议从 C:\codex pj\zmd_pj 副本推 | 机外冗余 |
| 4 | P2.0b 实现规格批准时点 | 终审判"修复后可作实现规格"，修复已完成 | P2.0b 开工前提 |
| 5 | 168h 执行层债余项排期（OOM 配置雷等） | 部分溶入批2a/2b；余项未排 | 长跑稳定性 |
| 6 | 冻结输入正确性加固（pose 枚举独立重验） | B2（批2b）覆盖一部分；抽样穷举比对未排 | 瓶颈第 6 条 |

## 5. 风险对照（2026-07-02 瓶颈审计 7 条硬骨头 → 本图位置）

①算力硬墙 → 1c 见真章 + 台账 2 退路；②编码忠实性单点 → 2b（终极解）+
批2b B2 + I1（已落）；③cut framework 尚未 certified promotion（F1/F5/F6/F7 direct attach 已落，Stage B/PIC 待完）→ 1c；④floor manifest 占位 → 1b
部署时点；⑤168h 执行债 → 台账 5；⑥冻结输入只证"没变" → 台账 6；
⑦手动门 owner-only → 设计如此（1b 终点闸）。

## 6. 文档修订台账（本次盘点发现的过时点及处置）

| 文档 | 过时点 | 处置 |
|---|---|---|
| 05 号 Q14 | "形式化不投资" | 已加注（2026-07-05，指向本文档 §2a/2b） |
| 05 号 Q1 | 无 Q1a/Q1p 拆分信息 | 已加注（指向 Q1a 稿 v2，标注待裁定） |
| 12 号 SUPERVISOR OPERABLE | "当前不成立"基于 06-26 基线 | 已加注（07-04 入口落地，语义以 PROJECT_LOCK 为准） |
| 排期卡 title/summary | 仍写"先收口后深化"（正文已修正） | 已修正卡片头部 |
| PROJECT_LOCK `Updated` 字段 | 已同步至 2026-07-11 | 已更新：P1.2 owner-close、F8 retirement、partial attach 与 Stage B 边界 |
| README 中后段旧 hash/旧叙事 | b35e5f9 等不可解析、"未合入"旧段 | 已有后注文化兜底；增量清理随下次 README 大修 |
| 08 号后半 | P1.2B 各 family "待实施"是史料 | 文档自带历史化标注，不动 |
| 13 号 | 估时已史料化 | 文档自带标注，不动 |

## 7. 阅读入口（新会话/新协作者按此序）

1. `PROJECT_LOCK.md`（release 红线）→ 2. 本文档（总图）→
3. [06_current_status](06_current_status.md)（当前状态）→
4. 排期卡正文（主线执行序）→ 5. 对应阶段的细节文档/研究稿。
