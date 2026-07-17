# front 错位 P0 事故：普查总报告与修复批方案（2026-07-18）

> **事故**：全仓端口/front 几何错位一格——冻结池端口坐标在本体外第 1 格
> （599,384 条全量零例外，对抗席亲手重扫确认），下游机械 front=端口+
> `_DIR_DELTA` 检查体外第 2 格；游戏真实规则（owner 游戏内实测定谳
> 07-18）：端口在本体边缘格，使用中端口的体外第 1 格须可放传送带
> （贴脸死 / 隔 1 格通 / 1 格带合法 / 两相对口共享中间格）。
> **双向污染**：第1空第2占→假 INFEASIBLE；第1占第2空→假放行。
>
> 发现链：owner 为 GPT Pro 干净房间实验审规格书时质疑"端口应在本体上"
> → specs/06 示例与冻结数据矛盾 → 游戏实测定谳。
> 普查：3 codex 席（机械+数据全量取证 / 历史 40 条三态重判 / 语义草案+
> completeness）+ 1 fable 对抗席（12 组 P0 论断 11 CONFIRMED 1 PARTIAL、
> 独立复算、6 条找漏、路径 b 五路攻击）。原始材料
> `.artifacts/front_offset_incident_20260718/`（三份 codex JSON）+
> 对抗席结果（见本文档引用）。

## §1 因果链（全部亲证）

1. specs/06 设计：口在本体边缘格（JSON 示例 y=20/23）——与游戏一致；
2. `src/placement/placement_generator.py:50-108` `get_edge_ports`：口写在
   `y+h`/`y-1`（体外第 1 格）——**偏移引入点**（把设计里的"带子格"当
   "口格"写入）；
3. `src/models/routing_binding_context.py:104-108`：front=口+δ——再推一格；
4. 全部下游继承（binding RAB filter / routing terminal/adherence/终验 /
   FCL lift 查表 / F3 oracle+validator 共模 / pose 池生成期错位剪枝）。

## §2 普查结论（经对抗验证的关键事实)

- **重解释可行性**：599,384 端口全量满足 in-grid、s∉body、s-δ∈body、
  曼哈顿距 1——路径 b（端口坐标重解释为带子格自身）无一例外成立。
- **污染的默认在线面**：routing 侧（terminal/adherence/precheck/终验+
  `benders_loop` 的 front_blocked→持久化 nogood 发射链，**不经 I1 复验**
  ——假 INFEASIBLE 进 master 的默认车辆，对抗席找漏 P0）；binding 侧仅
  RAB-ON 条件性污染。terminal fixed-witness 的 connector-body backstop
  （pr2_l0_fixed_witness_core:836-854）行为在路径 b 下**恰好正确**，挡住
  了"第 1 格被 body 占"的假放行穿透发布边界。
- **completeness 缺角（生成期错位剪枝）**：66,405 → 应为 68,469，缺
  **2,064 pose**（3×3 +544 / 5×5 +528 / 6×4 +520 / core +472；对抗席用
  池 anchor 分布独立重算逐池吻合）。全部条件于 OQ8（地图最外圈格能否
  承载 terminal 带）。
- **terminal rederivation 与路径 b 兼容**：纯路径 b 不动生成器与 45MB
  → `generate_all_pools` 字节不变 → rederivation 继续 PASS，无死锁；
  死锁仅在批 3 补域换钉时按 freeze ritual 处理。
- **路径 b 比预想更便宜**：route-state 双向索引下一格带+相对口共享中格
  **零状态空间改动**即可表达；豁免键平移自动跟走。
- **保全清单**（亲证不受影响）：不重叠/placement/供电三谓词、demand
  SSOT（620 需求无坐标参与）、四实例规约、symmetry 去重、empty-domain
  verifier（但其不能背书 front 语义——信任边界写明）、方法论 v2.2、
  证明日志工具链。

## §3 修复批方案（对抗席 batch_plan 全文采纳，owner 拍板执行）

- **批 0 裁决与实测前置（owner-only，无代码改动）**：
  ①theorem scope 拍板：窄域（66,405 池内 exact）vs 补域（68,469 全游戏
  域，触发批 3 重钉）；②游戏实测 OQ8（最外圈格承载带，决定批 3 生死）、
  OQ1（他商品带过境口前格）、OQ2（pole 共格）优先，OQ3-7 后置（8 条
  实测步骤见 semantics 席成果）；③RAB/FCL 处置（推荐随批 1 同批修复）；
  ④冻结新 certified publication（事故 addendum 进 LOCK）。
- **批 1 certified 主链语义原子批**（单提交完整 reseal，修复批 α 先例
  放大版）：routing_subproblem 域扣除反转+四链 identity 化、
  routing_binding_context front=stored、binding filter、fixed_witness
  义务注记（I1 清白面与盲区）、benders_loop 发射链、FCL offsets、
  PROJECT_LOCK ~14 条改判、canonical_rules 裁决文（LF hash 双钉）、
  specs/06 三处、快测 fixture 反转+6 类回归矩阵、慢 lane 4 项、
  obligations 8 sink + checker 自钉最后。验收=两 checker+preflight
  --full+--slow-tests+rederivation 仍 PASS+旧持久化 nogood 经 source
  digest 全部失效声明。
- **批 2 certified 不可达面收尾**（第二次小 reseal）：pose_bool/D2/
  patch/abstract/separator/deletion-core/F3 族+oracle 异构重推/io+render
  交付面标注。
- **批 3 候选域补齐批**（条件于批 0 OQ8）：生成器判界修正+重生成
  68,469 域+三处换钉+完整 freeze ritual；OQ8 判死则本批取消、窄域
  scope 永久化写入 LOCK。
- **批 4 历史重判与实验重跑**（非 sealed，批 1 后并行）：40 条三态
  重判落 addendum（作废件头部标记不删史料）；作废实验按原 seed 用
  corrected-front 重跑（RAB drill/FCL golden/witness 战绩/PB 6×6/
  round1-5）；重跑完成前"24 杠杆穷尽""结构墙"等全称判词保持撤回。

## §4 诚实边界

- 普查为只读零改动；本文档不改判任何 LOCK 条款（批 1 才动）；
- "路径 b 站得住"的五路攻击结论来自单席对抗（多席对抗留批 1 评审）；
- FrontUsable 的 blocker 闭集在 §5 批 0 裁决后部分闭合（body 类已定谳；
  belt-belt 细分 OQ3-7 仍开放，由 routing 层既有约束裁决、不进 front
  谓词）；
- 池计数口径消歧：boundary 实为 2×68=136（含两拐角 pose，canonical
  要求保留、数据对、spec 表 134/[1,66] 是文档错——随批 1 勘误）。

## §5 批 0 裁决记录（owner 2026-07-18 03:27-03:3x，真实输入）

1. **theorem scope = 补域（68,469）**：owner 实测 OQ8 通过（最外圈格
   可放传送带）+ owner 2026-07-13 既有铁律"全局 max_lex certified 目标
   无退路"推论排定，owner 未异议。执行序=批 1 止血先行 → 批 3 补域
   换钉跟上。窄域 scope 永久化条款不再需要。
2. **OQ8**：地图最外圈格**可以**承载传送带 → 批 3 成立，2,064 缺角
   pose 全部为游戏合法摆位。
3. **OQ1**：口前格被其他商品的带子占用 **≠ 堵死**——可经十字交叉
   （`routing_cross_junction`，canonical_rules.json:410-412）借道。
   **owner 补充定谳（两轮）**：①弯带不兼容十字交叉——口前格上的
   他商品带若在该格为弯带形态，该口即被占死；②借道仅限"横穿直带"
   ——他商品带与口出向垂直直穿时可上十字交叉解决。推论（canonical
   文本一致）：与口出向平行同轴的他商品直带同样堵（十字只认垂直
   交叉）。此三分在树内已双份强制：canonical 文本 +
   `routing_subproblem.py:1105-1125` `_add_bridge_constraints`
   （非"belt+直行+垂直轴"组合一律互斥），批 1 无需新增代码；
   带-带细分属 routing 层裁决，不进 placement/binding 层 front 谓词。
4. **OQ2**：电线杆算设施本体 → 压口前格 = 堵。与现有建模（pole body
   参与不重叠/占格）一致，无需改动。
5. **FrontUsable blocker 闭集（据 1-4 定谳）**：堵 = 任何设施本体
   （含电线杆）；不堵 = 传送带类组件（belt-belt 共格关系由 routing
   层既有 cross/合流约束在求解时裁决，不进 placement/binding 层的
   front 谓词）。修正后 front 谓词收敛为：**口前格（=stored 坐标格）
   不被任何设施本体占据且在图内**。OQ3-7（同向共享/cross 贴口等）
   均为 routing 层细节，不阻塞批 1。
6. **RAB/FCL 处置**：随批 1 同批修复（owner："按你的来"）。
