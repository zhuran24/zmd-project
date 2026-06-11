# 路 B 决策报告:terminal validator → proof-carrying certificate 的工作量与去留

## TL;DR

路 B 总量级:**全做 ≈ 4–6 人·月(低信心)**,其中能独立先做的"见证(witness)侧"约 5–9 人·周(中信心),真正的核心——**每个被剪枝候选的 INFEASIBLE(不可行)自带证明**——单独就是 1–3 人·月且带研究级风险(闭合见证可能根本做不到 solver-free 可查,见 §4)。最关键的两个未知:① 这个核心模块和 P1.3B(真 master 集成)在结构上是同一团工作,而 P1.3B 本身被 owner gate 锁着;② CP-SAT 唯一机器可查的证明格式(DRAT/LRAT)对本项目所有模型都不适用,核心证明机制得在求解器外面自己重建。我的倾向:**不把路 B 整体设为 P1.2 闭合阻塞项,划到 P1.3+ 与 master 集成合并推进**;但可以考虑把 2–3 个低成本、不碰 gate 的 witness 侧模块(见 §5 的 M1/M2/M4)作为 P1.2 可选加固——是否值得为此推迟闭合,由 owner 拍板。

---

## 1. 路 B 在本项目的精确定义

**proof-carrying certificate(自带证明的证书)= 交付工件里附带一份"足以让独立验证器从零重算、确认结论为真"的证明对象,验证器不信任任何自报标签。** 这不是新发明——项目数学文档早就把它定为 certified_exact 的 soundness 标准:输出必须伴随 mathematical proof object,且"必须 replay-validatable(可跨 session/跨硬件重放验证)";validator 是唯一信任边界,oracle(出题/出 cut 的求解侧)默认按"可能说谎"对待,validator 必须从冻结数据 + cert 独立重算,不引用 oracle 的任何声明。
(来源:`C:\claude pj\zmd_pj\docs\项目说明\01_overview.md` §1.3、`02_mathematical_foundations.md` §2.2/§2.6、`21_glossary.md` 的 cert 条目)

**和现状的本质区别一句话:**

- 现状(terminal validator,P1.2 落地的范式)= 重算一批**必要条件**(几何不重叠、矩形真的空、266 个强制设施都在、电力格子相邻……),然后**信任 status 标签**放行。候选记录里的 `proof_summary` 字段只被检查"是不是一个 Mapping(字典)",内容任意、不可重验(`src/search/exact_campaign.py:1412`)。
- 路 B = 工件携带**充分证明**,验证器从零重算确认。伪造的工件根本通不过重算,不需要像 V81–V98 那样逐字段堵"deny-unknown(拒绝未知字段)"的公开面。

外审 prompt 自己把这条边界讲得最直白(`cc_context\review\GPT_v99_外审_prompt.md` line 21):"terminal validator 不可能完整复刻 master+binding+routing 的全部证明义务(那等于重解)"——这也是当初 P1.2 没做路 B 的核心理由(阶段排序,不是永久否决;无集中决策文档,是从各轮 sealing.md + PROJECT_LOCK §3A 反推的)。

**现行边界:** 每轮 sealing.md 都把 "proof-carrying candidate certificates" 列为 future work;persisted exact_safe_cuts 已降级为纯 telemetry(遥测数据,不是证明);P1.2 与之后的线划在 `src/cuts/lifecycle.py::step_8_apply_to_master`(显式"尚未集成"边界),P1.3B 须 owner 手动决定才开。
(来源:`docs\research\p1_2_v82_*.md`、`p1_2_v83_*.md`、`CLAUDE.md` Current Phase 段、`data\proof_obligations\p1_2_proof_obligations.json`)

---

## 2. 现状信任边界 = 路 B 要替换什么

Area C 把三个验证器文件(`exact_campaign.py` / `certified_surface.py` / `certified_frontier.py`)逐点扒了一遍。先说结论:**整个验证器没有一处调用 CP-SAT,全部是结构检查 + 纯 Python 重算 + 哈希比对**。强弱分布如下,每个 weak 点 = 路 B 的一块工作面:

**已经够强、不用动的(真重算):**
- 空矩形存在性:从冻结 pose 表重铺占用格,前缀和确认矩形真空(`exact_campaign.py:965-1006`)
- 单布局最大性:暴力扫所有 (w,h) 证明"**这个**布局下没有更大空矩形"(`exact_campaign.py:1099`)——注意只证单布局,不证全局
- ghost 锚点与 master 决策的绑定(`exact_campaign.py:408-477, 970-997`)
- 强制覆盖 + 设施类型核对(`exact_campaign.py:800-839`)
- 候选域重生成 + 防切片(`certified_frontier.py:291-357`)

**weak/信任点(路 B 工作面),按严重度排:**

| # | 信任点 | 现状 | 证据 |
|---|---|---|---|
| 1 | **per-candidate 状态标签**(最大缺口) | CERTIFIED/INFEASIBLE 标签被原样信任;全 frontier"穷尽"论证完全建立在未验证的标签上。一个误标 INFEASIBLE 的候选会让非最优结果通过认证,现有三个文件**都抓不到** | `certified_frontier.py:186-221, 393-420` |
| 2 | persisted cut "重放" | 只做结构解析 + 锚点下标算术,不重放铸造该 cut 的 CP-SAT,不验证 cut 真排除了不可行区域 | `exact_campaign.py:1209-1239, 1414-1433` |
| 3 | 电力验证 | 只查"杆的覆盖格碰到设施格"的几何集合覆盖,没有容量/连通性/电网模型 | `exact_campaign.py:891-953` |
| 4 | optional 下界充分性 | 只查数量下界 + 上限,"这些箱子够不够路由"的证明缺失,代码注释自己标了 deferred to future proof-carrying certificate | `exact_campaign.py:908-924, 912-916` |
| 5 | 路由可行性 | 终端验证完全不碰 belt 路由——胜出布局"能不能真把货运起来"没有重验 | binding/routing/flow 子问题均不被验证器调用 |
| 6 | 跨布局全局最优性 | = 单布局最大性 + "搜索自报穷尽了所有更大候选"(后者靠 #1 的标签) | `certified_frontier.py:199-238` |
| 7 | allowlist/字符串门 | final_result/stop_reason/search_stats 全是反伪造的形状门,不是证明(代码注释明说 "until such fields have a replayable proof contract") | `exact_campaign.py:51-110, 295-313` |
| 8 | 冻结工件公理 | 一切归约到"四个 sha256 锁定的 JSON 工件是对的"——这是公理不是证明,路 B 也不解决它 | `exact_campaign.py:267, 1146` |

`certified_surface.py` 整体只证"交付包的新鲜度/一致性"(防 stale、防偷换),数学 soundness 全部委托给上表(`certified_surface.py:205` 是唯一进真数学的调用)。

---

## 3. 分模块工作量拆解

跨 5 个 area 去重合并后(D 的子问题视角 + E 的数学视角 + C 的缺口视角对同一件事的估计已并行):

| 模块 | 要建什么 | 工作量档(信心) | 依赖 | 能复用的现有件 |
|---|---|---|---|---|
| **B1. binding 子问题 INFEASIBLE 核心** | 给每个绑定选择加 assumption 字面量(可开关的标记变量),INFEASIBLE 时用 `SufficientAssumptionsForInfeasibility` 抽最小冲突子集,落成可重放 BendersCut;强制 num_workers=1 | **3–5 人·天(中)** | D2 模式;workers=1 | `src/models/d2_commodity_flow_core.py` 的 extract_core 近乎直接套用 |
| **B2a. routing 几何 precheck 证书正规化** | 把 `analyze_exact_routing_domain` 已有的 front_blocked / disconnected 组合证书(几何推导、本就可独立重验)升格为正式可重放证书 | **2–3 人·天(中高)** | 无 gate | precheck 输出本身;PCR-CUT 的 fail-closed replay 模式 |
| **B2b. routing 全量 CP-SAT 路由器 INFEASIBLE 见证** | 现在 `extract_conflict_set()` 直接返回 None——precheck 过了但精确路由器仍 INFEASIBLE 时**完全没有见证**。给最大的子问题加 assumption 层 | **1.5–2.5 人·周(低)** | workers=1 的性能代价 | D2 模式(但模型大得多) |
| **B3. flow 子问题 Farkas/min-cut 证书** | 把 `_extract_bottlenecks` 的"所有有端口的都算瓶颈"启发式换成真对偶射线/最小割。GLOP 不暴露射线,要走 highspy 镜像(presolve 必须关) | **3–5 人·天(中)**;若维持 diagnostic-only 锁则 **0** | PROJECT_LOCK 是否放行 flow 出 cut(现在禁止) | `docs\research\cand_c_column_generation_phase2_20260521\farkas_certificate.py`(已自验通过,项目里唯一能跑的 LP 不可行证书抽取链,GLOP/HiGHS 的坑已踩平) |
| **B4. Farkas 见证生成器泛化 + F1 LP-dual 接入** | 把 farkas_certificate.py 从死掉的列生成宿主里抽出来,接进 F1 region_capacity oracle 已预留的 `lp_dual_ray_b64` 字段 + 写 replay 校验器(纯线性代数核对 yᵀA≤0、yᵀb>0,不用 solver) | **1–2 人·周(中)** | OracleCert schema | 同上 + `src/cuts/oracles/region_capacity_oracle.py` 预留字段 |
| **B5. 证书容器 schema + 两段式 gate 框架** | 通用证书对象(proof_source/solver_invoked 标注 + gate/evidence/checks 三段 + fail-closed runtime guard),去 anchor119 化 | **≈1 人·周(中)** | 定清证书层级(candidate/anchor/region) | `src/search/phase3b/coordinate_validation/` 整套 schema 模式(注意只抄 schema,别抄那 40+ 个审查仪式文件) |
| **B6. 证书生命周期接线(generate→validate→replay→translate)** | 按 CP_SAT_INTEGRATION_NOTES 强制节奏接进 LBBD 循环:replay 验证通过才翻成普通 CP-SAT 约束;ghost-bound 证书用 OnlyEnforceIf | **2–3 人·周(低–中)** | **撞 step_8_apply_to_master gate** | `src/cuts/lifecycle.py` 9 步管线 + 各 family validator + PCR-CUT 已跑通的同类接线 |
| **B7. ★per-candidate INFEASIBLE 证书(cut-bundle + 闭合见证)** | 路 B 的心脏:每个剪枝候选附带可独立核查的不可行证明(F1–F9 cut 序列化 + Farkas 射线/unsat core + **闭合见证**:证明这堆 cut 合起来排除了全部剩余指派空间),让 frontier 穷尽论证不再信标签 | **1–3 人·月(低)**;闭合见证是研究级,可能进一步膨胀或失败 | **= P1.3B 主体,owner gate 锁定,不能单方面开** | BendersCut/condition_set 已持久化的序列化;PCR-CUT signature-lifting;per-family validator |
| **B8. 路由/流可行性见证(witness 半边补全)** | 给胜出候选附 belt 路径或流量指派,验证器图论重查"每个商品需求真能运到"——补上 §2 #5 | **2–4 人·周(低–中)** | specs/08 MCF 模型;路径见证 vs 流见证的表示选型 | `flow_subproblem.py`、specs/08 的 MCF 公式、既有电力扫描模式 |
| **B9. 电力证书升级** | 从格子相邻集合覆盖升到容量/连通性证明 | **≈1 人·周(中)** | canonical_rules 里得先有电力容量语义(目前只有 needs_power + coverage_cells,**语义本身缺失是前置**) | `exact_campaign.py:616, 891-952` 既有覆盖结构 |
| **B10. master 最优性证书 + 全局最优性聚合** | 把 best_objective_bound 写进 proof_summary + 把"所有更优 (area,min_side) 候选的 INFEASIBLE 证书之并"组装成显式全局最优陈述 | **1–2 人·周 + 1 人·周胶水(低/中)** | B7(真实成本在那边,这是聚合层) | `certified_frontier.py` 支配剪枝逻辑 + `_best_empty_rect_objective` 已给一半 |
| **B11. 独立 verifier CLI** | 单入口:冻结工件哈希 + witness + cut bundle + frontier 证据 → publishable/blocked,断言零 solver 调用 | **1–2 人·周(中)** | B7 的证书对象先存在 | `certified_surface.py` 整套 fail-closed 组合 |
| ~~B12. DRAT/LRAT 机器可查证明~~ | 须把子问题重编码为纯 SAT + 关 presolve/线性化/对称/并行 | **多人·周,实际不可行(不建议)** | — | 无可复用 |

**合计:** witness 侧(B1/B2a/B3/B4/B5/B8/B9,大多不撞 gate)≈ **5–9 人·周**;核心证明侧(B6/B7/B10/B11,撞 P1.3B gate)≈ **2–4 人·月,低信心**。全量 ≈ **4–6 人·月(低信心)**。

---

## 4. 关键风险与硬限制

**CP-SAT 证书能力的硬天花板(area D 实测,ortools 9.15.6755):**

1. **DRAT/LRAT(机器可独立核查的 UNSAT 证明日志)对本项目全部模型不可用。** 参数存在,但 proto 注释明确限定:纯 SAT 问题 + workers=1 + presolve 关 + linearization≤1 + symmetry≤1。zmd 的 master/binding/routing 全是带整数变量、presolve、2D no-overlap 的 CP-SAT——**"CP-SAT 会给我们可验证的证明日志"这句话对本代码库是假的**,除非整个重编码(B12,不建议)。
2. **assumption core 是"缩小过但不保证最小",且只能 workers=1。** 它本身仍是 solver 的声明,不是机器可查证明——要么再用 QuickXplain(项目已有 CPMpy PoC)压成真最小核,要么 replay 重解核子集来确认。现有 D2 路径读 `EXACT_D2_CP_SAT_WORKERS` 可 >1,**已是隐患**,新代码必须硬锁 1。
3. **INFEASIBLE 时没有任何 objective bound**;best_objective_bound 只能证最优性 gap,不能证不可行——两类证书要两套机器。
4. **没有 lazy constraint 回调**;唯一合法节奏是"replay 验证通过 → 翻成普通约束 → 重解"(`docs\research\p3_b_design_v2_20260521\external_review\gemini_math_review_bundle_20260523\notes\CP_SAT_INTEGRATION_NOTES.md`)。
5. **GLOP/pywraplp 不暴露对偶射线**,Farkas 证书必须走 highspy 镜像且 presolve 必须关——已踩平但必须遵守。

**数学侧风险(更要命):**

6. **闭合见证(termination witness)可能和搜索本身一样难。** 序列化 cut 容易;难的是 solver-free 验证器要证明"这堆 cut 的合取真排除了**全部**剩余指派空间"。Farkas/代数型 cut 可查;no-good(禁解组合)型 cut 的覆盖论证可能要枚举"没有未被切到的指派"——这是 B7 的研究级核心风险,做不出来整条路 B 的承诺就打折。
7. **L14 数学证伪(已 DEAD):LP 松弛类证书对 interior anchor 证不动**(LP optimum 严格 =1.000,90%+ 锚点是 interior)——`cc_context\memory_archive\project_l14_weighted_occupancy_dead.md`。Farkas 不是万能钥匙。
8. **L15 锁定的真瓶颈是 `_add_geometric_power_coverage_constraints` 的 disjunctive 编码**(任何 LP/MIP/CP-SAT 都卡)——对已经快的 set-packing 核心出证书没意义,证书要打中这层才有效。
9. **跨 instance cut lifting 被 PROJECT_LOCK 禁止** → 每个 INFEASIBLE frontier 候选要自己的完整 cut-bundle,证书体积和成本线性涨。

**流程风险:**

10. **B7 撞 gate:** 它本质就是 PoseBoolExactMaster/P1.3B 集成,需要 owner 手动放行,不能单方面开工。改 proof schema 也受"lock/spec/test 三件套同改"约束。
11. **verifier 的 solver-free 属性是设计资产**;任何要求验证器内重解的方案都会破坏独立性/性能模型。便宜路线是可查见证(IIS/nogood 并集),但见上条 6。
12. phase3b 那条最接近 proof-carrying 的链停在 diagnostic-only,anchor119 目录堆了 40+ 审查仪式文件却始终 runtime_enablement_allowed=False——**复用 schema 时警惕继承仪式膨胀,真缺的是 deterministic witness 抽取实现**。
13. **路 B 不解决公理层:** 四个 sha256 锁定工件的正确性仍是公理。路 B 把信任面从"几十个标签和字符串"压缩到"四个冻结 JSON",压缩极大但不归零。

---

## 5. 增量交付路径

可以切,而且 witness 侧和核心侧天然解耦。每块独立可验、各自有价值:

- **M1(3–5 人·天):binding assumption core(B1)。** 立即让 binding 的 INFEASIBLE 从"无见证"变"有最小冲突核",顺手修 D2 的 workers>1 隐患。不撞 gate。
- **M2(2–3 人·天):routing precheck 证书正规化(B2a)。** 现在事实上的路由证书(几何推导)升格为正式可重放对象。不撞 gate。
- **M3(1–2 人·周):Farkas 生成器泛化 + F1 LP-dual 接入(B4)。** 激活 OracleCert 预留字段,replay 是纯线性代数。不撞 gate。
- **M4(≈1 人·周):电力证书升级(B9)。** 直接消掉 §2 #3。前置:canonical_rules 先表达电力容量语义。
- **M5(2–4 人·周):胜出候选的路由/流可行性见证(B8)。** 消掉 §2 #5——**只给 winner 一个候选做**,不需要 P1.3B,witness 半边即告完整。
- **M6(1–3 人·月,低信心,需 owner 开 P1.3B):per-candidate INFEASIBLE cut-bundle + 闭合见证(B6+B7+B10)。** 消掉 §2 #1/#2/#6——路 B 的全部承诺兑现在这里,风险也全在这里。
- **M7(1–2 人·周):verifier CLI 组合(B11)。** 依赖 M6 的证书对象。

**关键观察:M1–M5(约 5–9 人·周)不撞 owner gate,可独立交付且每个都消掉 §2 的一个具体 weak 点;但 §2 #1(标签信任,最大缺口)只有 M6 能消,而 M6 被 gate 锁着。** 也就是说:不开 P1.3B,路 B 最多做到"witness 半边完整 + 子问题有核",全局最优性照样信标签。

---

## 6. 给 owner 的判据建议

**先把一个本质讲诚实——路 A(GPT 逐轮挖缝凑三连零)和路 B 在证明力上的区别:**

路 A 的三连零,即使达成,证明的是"**公开面上不再有'伪造成本低'的可重放维度**"——是反伪造外壳的完备性,**不是数学 soundness**。全 frontier 穷尽论证仍然 100% 建立在未验证的 INFEASIBLE 标签上(`certified_frontier.py:199,213`);一个误标候选照样能让非最优结果通过认证,且三连零状态下依然抓不到。V81–V98 十八轮 finding 越挖越窄、外审 prompt 开始主动引导 reviewer"剩余缺口若全属 proof-carrying provenance 范畴请论证后报零"(v99 line 21)——这正是路 A 收敛到自身天花板的信号:**剩下的缝都是只有路 B 能补的那一类**。路 B 则直接把"信标签"换成"重算证明",反伪造逐字段堵的需求随之消失。两条路修的不是同一个东西:路 A 修壳,路 B 修芯。

**选项一:路 B 进 P1.2 当阻塞项**
- 代价:P1.2 闭合至少推迟 4–6 人·月(低信心估计),且 M6 含研究级风险——闭合见证做不出来时 P1.2 会被一个可能失败的研究项无限期挂起。
- 自相矛盾点:路 B 的心脏(B7)结构上 = P1.3B 主体,而 P1.3B 按现行裁决要等 P1.2 闭合后 owner 手动开——把 B7 塞进 P1.2 等于让 P1.2 阻塞在"必须先开 P1.3B"上,**逻辑上自锁**,除非 owner 同时重划 phase 边界。
- 什么情况下选它:owner 认定"未验证标签"这个缺口大到不能带着它宣布 P1.2 闭合,且接受重划边界 + 数月延迟 + 研究风险。

**选项二:划 P1.3+(我的倾向)**
- 理由:① P1.2 的定位本来就是 terminal 公开面 fail-closed 封堵,文档从 v83 起每轮都把 proof-carrying 连续披露为 future work——划过去不是降级,是兑现既有承诺;② B7 和 P1.3B 是同一团工作,合并做避免两次开同一刀;③ 路 A 的残余缺口已被外审 prompt 明确归类为 provenance 范畴,reviewer 据此报零是制度允许的闭合方式。
- 代价:P1.2 闭合时的"CERTIFIED"语义要诚实标注——它的全局最优性主张依赖未重验的求解器标签 + 四个冻结工件公理。建议闭合文案里显式写明这条信任残余,别让"CERTIFIED"字面被外界读成"自带数学证明"。
- 可加的折中:把 M1/M2/M4(合计约 2 周,不撞 gate、低风险、各自消一个 weak 点)作为 P1.2 的可选加固塞进闭合前窗口;M5 视 owner 对"witness 半边完整"的估值决定进 P1.2 尾巴还是 P1.3 头。

**第三个隐含选项(成本最低):owner 直接改判据。** 现行"3 连零"判据在路 A 天花板已现的情况下,继续逐轮外发的边际收益是挖出越来越窄的壳层 finding。owner 可以按 v99 prompt 已铺好的路:接受一轮"reviewer 论证剩余缺口全属 proof-carrying 范畴 + 报零 finding"作为合格的 clean review,把三连零的达成从"壳上再也挖不出缝"改读为"壳已完备、芯的缺口已显式登记为 P1.3+ 工作"。这与选项二配套使用,不需要任何代码改动。

**一句话判据:如果 owner 要的是"P1.2 闭合时交付物的最优性主张经得起独立数学重验"——那只有路 B,且要接受数月 + 研究风险 + 重划 phase 边界;如果 owner 接受"P1.2 = 反伪造外壳完备 + 信任残余显式登记",那么划 P1.3+ 与 master 集成合并,是工程上重复劳动最少的排法。**
