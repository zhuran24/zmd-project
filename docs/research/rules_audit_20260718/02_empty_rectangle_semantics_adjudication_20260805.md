# 空矩形语义裁决：什么都不能有（owner，2026-08-05）

> 本文书按 00 号裁决书同一 SOP 记录一次 owner 规则定谳。触发现场=band22 见证
> 摄入批发现孔内 22 格传送组件（见证自我申报 `hole.route_overlap_cells: 22`），
> 主线核查官方语义时发现代码采用宽松读法，报 owner 后 owner 当场裁决。

## 裁决

**owner 原话（2026-08-05）：「空地当时的定义就是什么都不能有」。**

正式口径：目标空矩形（ghost rect）内**不得存在任何占地物**——设施机身、电杆、
传送带、暗管等全部物流件一律禁止。「空」= 完全净地。

## 裁决前的书面状态（三处权威源核查，全部无法回答本问题）

1. `PROJECT_LOCK.md:58` 认证谓词 (1)：「ghost 内无 **facility**」`all_cells(π) ∩ R = ∅`
   ——只约束设施（含电杆），未提物流件。
2. `rules/canonical_rules.json` `globals.empty_rectangle`：仅
   `{"objective": "max_lex_area_min_side", "min_side_admissibility": 6}`——
   「空」的含义**留白**。
3. V88（`README.md:534`）：「五个下游 consumer 把新 marker 当成了 facility」的
   崩溃修复；`src/search/benders_loop.py:8087-8089` 的
   `# V88: ghost_pick is the empty rectangle marker, not an occupier` 将 ghost
   从 routing 占用集排除是该修复的**静默副作用**，无任何语义裁决记录。

结论：书面规格留白 + 代码静默选宽松边。本裁决填上留白，宽松读法作废。

## 方向安全性（哪些历史结论仍有效）

严格语义的可行集 ⊂ 宽松语义的可行集，故：

- **负结果全部有效**：一切宽松集上证出的 INFEASIBLE/死刑证书（「连允许穿孔
  都不可行」）在严格语义下更成立。
- **上界 U=(1188,18) conditional 有效**：宽松集上的 max ≥ 严格集上的 max，
  上界方向安全。
- **正向见证受损**：band22 (42,6) 见证含 22 格穿孔物流 + 4 个 front 落孔的
  激活端口（左缘边界口 left_17/left_18 因输出 front 在孔内整体失效，另有
  planter M192 / seed_collector M166 各一口需重绑定），**登记资格暂停**，
  需实质性重设计（干线改道+边界口搬位+局部重绑定）。
- 历史上从未铸出正向 CERTIFIED，证明链无既成污染。

## 结构性事实（重设计的核心约束）

band 范式中带高 ≤5，任何 6×7 孔必跨 ≥1 条走廊行（band22 的孔恰跨 y=51、y=57
两条走廊）→ 严格语义下蛇形干线**改道不可避免**，「孔与返回列/riser 共用省地」
（27 号 repair 的核心省法）整体作废。

## 挂账（不在本文书内执行）

1. **认证链修复批（freeze-ritual 级，涉 sealed 面，需排期）**：routing 占用集
   并入 ghost 格——已知 call site ≥4：`benders_loop._extract_occupied_cells`
   （:8081）、`pr2_l0_fixed_witness_core.py:875`、`routing_binding_context.py:97`、
   `heuristic_feasible_finder.py:169`（末者 exploratory 面）；路由预检同口径；
   相应测试与 obligations 核对。
2. band22 严格语义重设计（改道+搬口+重绑定；候选=带新约束的咨询包）。
3. 既往文书「孔 42 格全自由」表述勘误（CONSULT_VERDICT、08-04 夜汇报口径）
   ——挂正式门收官文书更新轮。**已完成（08-05 收官轮）**：
   `CONSULT_VERDICT_TRIPLE_20260804.md` 头部勘误横幅 +
   `27_band22_witness_delivery_20260804/band22_three_holes_repair_report.md`
   SUPERSEDED 横幅（覆盖同目录见证 JSON 与交付清单），正文史料未改字。
4. G1 目录的 hole 语义按同口径复查（线已停，仅记账不阻断）。
5. `rules/canonical_rules.json` 是否补写 emptiness 定义 = frozen 工件变更，
   走 freeze-ritual，与挂账 1 同批评估。
