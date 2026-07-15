# 01 — ①′ 第一段：front-free 必要性 soundness 审查（v2 修订版，2026-07-16，对抗验证完成）

> owner 07-16 批准 ①′ 三段批（soundness 审查 → env 分类提升 → prod 注入演习）后的第一段交付。
> **v2 = 对抗验证完成后的修订版**：11 席对抗（V1-V5 攻击/复核共 10 席 opus + 1 席 codex 全文
> 对抗审查，全部只读 HEAD `bf9649a`，零 master solve、零 certified 启动、零仓库写入）。
> 判决摘要：**命题 N 与全部操作性 soundness 结论幸存**（V2/V5 全绿；V1/V3/V4 核心成立带
> 边界记录；codex 对"文书整体"判 refuted——refuted 的是 v1 草案的若干论证表述，不是结论），
> v1 草案的错误已在本版逐条改判，改动处以【v2 改判】标出。主线（Fable）对全部承重新发现
> 做过亲手抽查（build 短路、推论 B 反例机制、raw-empty 不可达、bypass 实际走 UNKNOWN）。
> 背景与 lead 来源见 `../cut_framework_review_gpt56pro_20260710/17_fable_counterfactual_comparison_20260716.md`。
> 验证产物：`/tmp/claude-1000/-home-zhuran24-zmd-pj/5c4e70f0-8e60-497e-b217-46e01be6da76/scratchpad/rab_adv/`
> 各席位目录（v1_seat/v2_seat/v2_recheck/v3_empty_domain/v3_indep/v4/v5_seat/v5_review/codex_seat）。

## §0 要回答的三个问题（答案）

1. 「port front cell 对固定占用非 free ⇒ routing 不可行」是不是真必要条件？——**是**（命题 N，
   三路独立验证幸存：V1 攻击席四臂 empirical、V1 复核席独立构造、codex 强制-feasible 探针）。
2. `benders_loop.py:6850` 旧注释与 precheck 的 PROOF 地位的张力？——**陈迹，无现行 certified
   洞**；但 v1 对其运行时行为的描述有误，本版 §3 改判。
3. EMPTY_DOMAIN 瘦 fallback 在 filter-on 时是否有 unsound 超杀面？——**现行无**（归因完备
   不变量成立，双席穷举 + codex 655 empty-owner 全量扫描均零违例）；但 v1 提议的结构修复
   **不充分**，codex 给出两个 guard 捕获不到的构造场景，本版 §4 升级修复方案。

## §1 命题与裁判【v2 改判：裁判链描述】

**必要性命题 N**：固定 layout L（本 master 解中全部已放实例的体格几何）与任意 binding
selection S——若 S 所选 pattern 的某个 routing-visible 端口的 front cell (a) 出界，或
(b) 被 L 中某实例体格占据，则 (L,S) 在 certified routing 谓词下不可行。

**live 裁判链是两级的**（v1 写成"adherence → post-solve"，错）：
- 第一级（live 主守卫）：`analyze_exact_routing_domain` 对 front∉free_cells 或出界即返回
  `front_blocked`（routing_subproblem.py:448-509）；`RoutingSubproblem.build()` 对任何非
  FEASIBLE 域状态直接 `model.Add(0==1)` 并 return（**:855-861**，在 `_add_port_adherence`
  :869 之前短路；另有 duplicate-front-key 短路 :848-853）。front_blocked 情形
  `_add_port_adherence` 与 `_validate_selected_route_connectivity` 均不被执行
  （三个 blocked 臂实测 `build_stats["port_adherence"]=None`）。
- 第二级（深层独立支撑，非 live 主链）：即便伪造 status=feasible 强行绕过短路（codex 探针），
  被占 front 仍被 active-domain 交集剔除，`_add_port_adherence` 记录 blocked port 并使模型
  INFEASIBLE——N 不依赖第一级的调度正确性。

canonical（游戏语义）层面的 front/belt 语义已由 owner 2026-07-02 四项拍板钉定，本文以
sealed 模型为谓词真值，不重开 canonical 面。

## §2 命题 N 的证明链 v2（锚点全部经对抗席核正）

1. **路由自由域**：体格占用在 routing_subproblem.py:65-69 排除出 free cells；connector
   cells 再于 :347-367 扣除（`_resolve_routing_domain_context`:359、`_port_connector_cells`
   :135-148）。实体占据的 cell 不在 free_cells。
2. **状态门（live 主守卫）**：front 出界/∉free ⟹ analyze 判 `front_blocked`（:448-509）⟹
   build() 于 :855-861 落 `0==1` 短路。**这是 N 在现行执行链上的直接成立点。**
3. **深层支撑**：route 变量只在 commodity active cells 上创建、两层（地面/高架）共用同一
   active 集（真实主锚 :990-1054；`_add_continuity_constraints`:1141-1148 是其中一环）——
   **高架桥不能跨越实体占据 cell**（V1 实测：1-cell 实体 gap ⟹ relaxed_disconnected/
   INFEASIBLE，gap 自由对照臂 FEASIBLE）。`_peel_terminal_core`（定义 :263-304，三处守卫
   永不剥 front cell）⟹ 正常 feasible 路径下所有 front 必 ∈ active，`_add_port_adherence`
   （:1278-1319）内 front∉active⟹0==1 的分支在正常路径是**防御性死分支**（转正批哨兵测试
   钉此结构，防未来"清理"build 短路引洞）。
4. **binding 侧无逃生门**：每个 placed operation facility 必须恰选一个 pattern
   （`_build_fixed_operation_domains`，binding_subproblem.py:985-1044，AddExactlyOne :1040）；
   selected pattern 的 routing-visible 端口全部进入 `extract_port_specs()`（:1360-1426，
   **occupancy-blind**——全链 `[dict(spec) for spec in ...]` 全量拷贝，无占据感知过滤，
   blocked port 不可能被中途悄悄丢掉）。**V2 一致性已实测卸除条件**：filter
   （`_filter_pose_binding_domain`，binding_subproblem.py:901-943，可见端口规则 :926-931）
   的 routing-visible 端口集与 extract_port_specs 输出**恰相等**（全 17 个 op_type ×
   286,636 poses = 36,036,528 patterns / 159,631,248 ports 全枚举，违规 0；
   `routing_free_sink_commodities` :524 一次性构建、全仓零变异，两处引用同源不可分叉）。
5. 综合 1-4：front 出界或被实体占 ⟹ 第一级短路 0==1；即便绕过第一级，第二级 active-域
   剔除 + adherence 仍 0==1 ⟹ 完整模型 INFEASIBLE。**命题 N 成立（模型级，双层支撑）。∎**

推论 A（precheck front_blocked 的 PROOF 地位成立）：precheck 与 build 用同一 analyze
（同一 front 公式 + 同一自由域），precheck front_blocked ⟹ build 必短路 0==1。

推论 B【v2 改判——v1 全称表述为假】：v1 写"同 commodity 的 front 落多个分量 ⟹ 无解"，
codex 构造出真反例：**两个互不连通分量各自含该 commodity 的 source 与 sink 时，analysis=
feasible、完整 router FEASIBLE**（:550-588 是逐分量检查 component_sources/component_sinks，
两者均非空的分量合并进 active_union，不产生 relaxed_disconnected；主线亲读核正）。正确
命题为：**同 commodity 存在某个"有 front 但缺 source 或缺 sink"的分量 ⟹ analyze 判
`relaxed_disconnected`（:553-585）⟹ build 短路 0==1**。代码的 reject status 本身 sound
（只拒缺 counterpart 的情形）；错的是 v1 的书面推论范围。此改判不影响 RAB filter（filter
只用出界/占据两种拒因，与分量无关）。

推论 C（RAB filter 必要性，a fortiori）：filter 只按【出界 ∨ 固定实体占据】拒 pattern——
是 N 的弱化（全"少拒"方向；self-occupied 豁免按 free 处理 = 比模型更宽松 = 安全方向，
V1 实测）。凡 filter 拒的 pattern，任何选它的 selection 都触发 N ⟹ filter 是谓词的
**合法松弛**（V2 实测实为端口集相等，比"⊆"更强）。

## §3 `:6850` 旧注释的判决：陈迹，非既有洞【v2 改判：运行时行为与拦截机制描述】

判决方向不变：**无现行 certified 洞，注释是 B1 pose-bool 旧世界陈迹**。三处 v1 描述改判：

- 【改判 1】"router 跑起来也只会立即 INFEASIBLE"错。实际 LBBD 行为（codex 定向单测 +
  主线亲读 :7540-7560）：bypass 只翻转 local precheck_status，routing model 仍收到原
  front_blocked analysis ⟹ build 短路后 controller 检查 build 期域状态非 feasible ⟹
  记 `unexpected_routing_build_domain_status` 并 **return RUN_STATUS_UNKNOWN**（:7548-7560，
  不进 solve）。方向仍保守（fail-closed 到 UNKNOWN），但机制与 v1 所写不同。bypass 分支
  本身是 live code（:6850-6860），非死代码。
- 【改判 2】两个门控 env 的拦截机制**不同**（v1 写"都走 proof-semantics blocker"）：
  `EXACT_B1_BYPASS_ROUTING_PRECHECK`（known :1036、非 operational）走第一循环
  proof-semantics blocker（:1518-1540，code=`proof_semantics_exact_env_not_certified`）；
  `EXACT_USE_POSE_BOOL_MASTER` 因同时在 unsafe-override map（:985-993），第一循环 :1516
  continue 跳过、由第二循环（:1542-1553）以专用 code=`pose_bool_master_not_certified` 拦。
  V5 双席独立脚本实证：单开各 1 blocker、双开 2 blockers、8 个真值变体全拦、bypass 站点
  激活集与守卫 enabled 集的 truthiness gap=∅。
- 【改判 3】"认证路径不可达"的完整前提 = **env 固定 + heartbeat callback 可信**：守卫
  （4 处启动防线：outer_search.py:1770 return UNPROVEN + benders_loop.py:2412/2494 raise +
  :8988 heartbeat blocked，全在 master build 之前，覆盖三条执行路径收敛点）之后 callback
  仍会执行且 env 在其后被重读（:9049-9057）；可信生产 callback 不改 env，故非现行洞，但
  前提须写明。另记：pose-bool 无 master 级内在 fail-closed（master_model.py:2601-2609 若
  真到达会照建 delegate）——防线全在 env 启动守卫，防线真实形态记录在案。（注：V5 席
  引 CLAUDE.md"master fail-closed"说 pose-bool 层缺失系误读——CLAUDE.md 那句说的是
  `EXACT_POWER_PLACEMENT_SUBPROBLEM`，对 pose_bool 只说 env 守卫，与实态一致，无需修。）
- 处置不变：注释文字修正挂**分类提升批**（动 sealed 文件需 reseal，不在本段做）。

## §4 EMPTY_DOMAIN cert / 瘦 fallback 的 soundness 全枚举【v2 改判：row 1 + 修复方案升级】

通道（benders_loop.py:6439-6505）：空域实例优先配 cert（`core_size>1` 才用 :6467，
cut_type=`rab_sep_clear_deficit_certificate`），否则瘦 fallback
`_build_conflict_from_instance_ids(solution,[owner])`:8099 = `{owner: 当前pose}`
（cut_type=`binding_pose_domain_empty_nogood`）。

| 情形 | 落点 | 判定 |
|---|---|---|
| raw 空 | —— | 【v2 改判】**当前实现不可达**：`_enumerate_side_binding_patterns`（port_binding.py:143-155）端口不足时 raise ValueError、无 required slots 时返回 `[()]`、否则回溯 ≥1，**永不返回空 list**（主线亲读核正）；且 EMPTY_DOMAIN 通道整体是 **RAB-only**——rab OFF 时 filter 被 :1008 的 `and domains` 跳过，:1015 的空检不可达（3,200 真 pose 采样 empty=0）。v1 写"rab on/off 均可发生"为假。该分支保留为防御性代码，soundness 判定空真 |
| filter 空 + blockers≥1 | cert（core≥2） | **sound**（V3 双席逐格实证，含 MIXED 混合拒因变体：出界+双 blocker 单 pattern，union 完整 core=3）：cert 主张「owner@pose ∧ 各 blocker@pose 不可共存」；联合指派下每 raw pattern 原拒因逐一保持 ⟹ 域仍空 ⟹ 由 N 无 routing-可行 binding。ghost-agnostic（证明未用 ghost） |
| filter 空 + blockers=∅ | 瘦 fallback | **sound（现行）**：归因完备不变量（下）⟹ blockers 空 ⟹ 全部拒因=出界 ⟹ pose 内在（网格不动），全局 pose 禁合法 |

**承重不变量（归因完备性）——已双席实证**：`build_routing_binding_context`
（routing_binding_context.py:59-71）中 `occupied` 与 `owner_by_cell` 同一循环同源填充 ⟹
front 被实体占必有 blocker 归因（穷举探针违例=0；codex 三个全尺度基底 655 个 empty owner
全量扫描：missing attribution / owner-in-blockers / blocker omission 均=0）；blocker=None
的拒绝只剩出界（:100-108）；self-occupied 防御分支（:112-121）按 free 处理、不构成拒绝
（under-filter 安全方向）。blocker 收集是全部 raw patterns 拒因的 **union、无 break**
（:936-937），不是最小 IIS；benders 可能为每个 empty owner 各加一条 cert（非"只选一个
最小 cert"——v1 措辞修正）。

**结构性弱点（非现行 unsound，转正前必修）【v2 升级——v1 方案被 codex 证伪为不充分】**：
现行安全是实现耦合的巧合安全（依赖归因完备不变量 + core 构成细节 + `core_size>1` 分支）。
v1 提议"filter-empty 且 blockers≥1 时禁止瘦 fallback"，codex 构造出两个该 guard 捕获
不到的场景（均需人为破坏 builder 不变量才可达，现行 builder 下不可达）：
① 归因缺失 context ⟹ blockers=[]、core=1 ⟹ 瘦 fallback照走（guard 依赖的 blockers 本身
就是空的）——移走真实 blocker 后同 owner pose 的小 router FEASIBLE = 若可达即超杀；
② partial-drop：cert 静默丢失一个 blocker 但 core 仍=2 ⟹ 照走 cert，而不完整 cert=超杀。
**升级后的结构保证（转正批工程义务）**：逐 pattern 保存拒绝证明，落 cut 前校验
「每个非出界拒因均有 blocker 归因 ∧ conflict_set∖{owner} ⊇ 全部 blocker」，任何缺失
fail-closed 跳过（该 owner 本轮无 cut；全部 owner 被跳时走既有 cut_stall 路径返回
UNKNOWN——benders_loop.py:6523-6525，比 v1 所写"退回整层 selection nogood"更保守）；
配归因完备性哨兵测试。

**附加潜伏面（V4 双席发现，转正批清单）**：`build_routing_binding_context` 的填充循环
**不排除 ghost_pick**（routing_binding_context.py:61-71），与全仓其它 occupied 提取器
（benders_loop.py:7927/7943 V88、binding_subproblem 的 `_is_non_facility_placement_marker`）
不对称；当前无害仅因 facility_pools 无 `ghost_rect` key ⟹ 空池 continue。若未来 ghost
cells 进 occupied：empty-domain 判定变 ghost-anchor-dependent 而 nogood 仍 unconditioned
全 anchor 应用 ⟹ 跨 ghost 超杀。**修复：加显式 non-facility-marker skip（结构保证）。**
注意瘦 fallback 的 sound 与 cert conflict_set 的 ghost-free **双双压在这同一个空池巧合上**。

## §5 持久化 / 重放 / ghost 作用域【v2 改判：因果解释 + I1 措辞】

- ghost-agnostic 结论成立，但因果机制改正（v1 解释错）：**不是**"未登记类型天然按
  ghost-agnostic 处理"——cut_manager 的登记表（cut_manager.py:24-27）只决定某些 power cut
  **必须**带 condition（`_validate_certified_condition_requirement`:186-209），shape 校验
  只对非空 condition 生效（:138-151）。RAB 两型无条件的真实原因 = **producer 不传
  condition_set**（benders_loop.py:6494-6501）⟹ master 建无条件 nogood
  （exact_coordinate_master.py:7846-7849）。对 ghost-agnostic cut 而言 unconditioned=正确
  语义（§4 证明未用 ghost）。
- 【v2 改判】I1 措辞：v1 写"非其复验对象即保守 UNKNOWN"有误导性——两型 RAB cut
  **根本不进 I1**（I1 唯一生产调用点=benders_loop.py:8857，只处理 kind=`whole_layout_nogood`
  :8914；RAB 两型 kind=`placement_local_nogood`），得到的是**零独立复验**而非保守兜底。
  soundness 全押生成期证明（命题 N）+ 归因完备不变量单点 ⟹ §4 升级修复与哨兵测试的
  权重相应上调。
- 持久化/重放（V4 双席独立坐实）：persistence 按 candidate_key=(ghost_w,ghost_h)
  per-ghost keyed（exact_campaign.py:3042-3044；parallel 分发同 key），ghost-A 的 cut
  结构上到不了 ghost-B；certified 下重放循环是死代码（benders_loop.py:9312/9322-9327，
  V82 硬置 raw_candidate_cuts=[]），cut 每进程内重生成、绝不跨 restart/checkpoint 复用。
- `EXACT_B1_ROUTING_AWARE_BINDING` → known 非 operational（:1049 / :1518-1540）：certified
  下现状 fail-closed，正是分类提升批要动的面（先例=probe_8→`9deec8f`，但本 env 属真
  proof-semantics 面，提升依据=本审查 v2 + 已完成的对抗验证）。

## §6 对抗验证结果（V1-V5 + codex，2026-07-16 执行完毕）

| 席位 | 判定 | 要点 |
|---|---|---|
| V1 必要性（攻击+复核） | concern（N 幸存） | 四臂+独立构造均无反例；port_specs 全链 occupancy-blind；医出 v1 证明锚点错位（build :855 短路才是 live 守卫）→ 本版 §1/§2 已改判 |
| V2 端口集一致性（攻击+复核） | **holds** | 36M patterns / 159.6M ports 全枚举 0 违规，两集恰相等；RFSC 同源零变异；潜伏记账：commodity accessor 不对称（filter `.get` vs model 严格取值，当前不可达） |
| V3 EMPTY_DOMAIN 矩阵（攻击+复核） | concern（核心成立） | row2/3 逐格实证 sound、归因不变量穷举零违例;医出 row1 raw-empty 不可达 → 本版 §4 已改判 |
| V4 作用域/I1（攻击+复核） | concern（核心成立） | per-ghost keyed + 零重放坐实;医出 I1 措辞误导 + ghost_pick skip 缺失 → 本版 §5/§4 已改判 |
| V5 bypass 不可达（攻击+复核） | **holds** | 独立脚本双复现：4 处启动守卫、真值变体全拦、truthiness gap=∅；医出 v1 拦截机制归因不精确 → 本版 §3 已改判 |
| codex 全文对抗审查 | 文书 refuted / 操作结论全确认 | 推论 B 真反例（本版已改判）；强制-feasible 探针独立支撑 N；hybrid generic-output 探针揭消费者边界潜伏缺口；瘦 fallback 修复方案升级（本版 §4 采纳）；确认当前 artifacts/生产调用图下无现行 RAB overcut 或 certified soundness 洞 |

## §7 转正批（第二段）工程义务清单（由本审查产出）

1. env 分类提升本体：`EXACT_B1_ROUTING_AWARE_BINDING` 进 operational allowlist，
   allowlist/lock/tests 三同步（CLAUDE.md env 白名单纪律）。
2. `benders_loop.py:6850` 注释修正（按 §3 v2 的准确表述：bypass ⟹ build 短路 ⟹
   controller UNKNOWN，certified 下双 env 各自被拦）。
3. 瘦 fallback 结构保证（§4 升级版：逐 pattern 拒因校验 fail-closed，非仅 blockers≥1 禁用）。
4. 哨兵测试组：①front_blocked ⟹ build :855 短路 + `port_adherence=None`（防"清理"短路引洞）；
   ②归因完备性（occupied/owner_by_cell 同源）；③adherence 死分支结构（front 必∈active）。
5. `routing_binding_context` 加显式 non-facility-marker（ghost_pick）skip。
6. commodity accessor 统一（filter :930 `.get('commodity','')` → 与 model :1373 同为严格
   取值；当前不可达，顺手修，方向=filter 忠实镜像 model）。
7. generic output/input disjoint 不变量断言（codex hybrid 探针：PortBindingModel/RAB 消费者
   缺 disjoint invariant，当前被 semantic_validator:145-158 间接挡住；加 fail-closed 断言
   使其成为结构保证）。

## §8 诚实边界

- 本文全部行号/语义出自 HEAD `bf9649a`（主线亲读 + 11 席对抗核正）；未跑任何 master/
  certified 链。**master 吃细粒度 cut 后的收敛性仍未验**——那是第三段（prod 注入演习，
  owner 已预批的单发 ~500s 探针）要回答的问题，本审查不为其背书。
- 命题 N 的成立以 sealed 模型为谓词真值；模型对游戏的忠实性是 07-02 owner 已拍板的
  canonical 面，不在本段重开。
- codex 的两个"巧合安全"反例场景（§4①②）在现行 builder 下**不可达**，是对"未来重构
  破坏不变量"的风险论证，不是现行洞——引用时勿升格。
