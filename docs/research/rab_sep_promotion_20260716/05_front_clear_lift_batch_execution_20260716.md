# 05 — front-clear 上收批：实施批执行记录（2026-07-16）

> **历史失效标记（Batch 4，2026-07-18）**：本文依赖错位 front 的全池
> golden、corpus 与“零 mismatch”证明力已撤销（FCL-03）；工程结构资产
> 是否保留及 corrected-front 恢复条件见
> [历史重判附录](../front_offset_incident_20260718/01_historical_rejudgment_addendum.md)。

> 设计与审查收口 = doc 04 v2（四席对抗验证 wf_d123bca7：soundness×2
> codex/opus + encoding codex + cost/scope codex；判决与逐条处置见其 §9）。
> 本文书 = 实施批（任务 4-8）执行账目。基线 HEAD `815a73e`。

## §1 改动清单

**sealed（4 文件，close-kernel reseal）**：

| 文件 | 内容 |
|---|---|
| `src/models/port_binding.py` | demand SSOT 三件：`is_routing_visible_output_commodity`（RFSC 输出排除谓词）、`routing_visible_port_demands(op, rfsc)`（每侧 routing-visible 需求，generic op fail-closed raise）、`routing_free_sink_commodities_from_generic_inputs`（RFSC 集派生） |
| `src/models/binding_subproblem.py` | filter `:972` / extract_port_specs 两处 / generic output 段共三个消费点改经 SSOT 谓词（行为零变化重构，92 测试回归）。**注**：raw 分桶最初误放 `extract_conflict_summary`，被慢 lane golden semantic digest 测试抓出（诊断字段污染 proof 面 → digest 漂移），改判挪到 benders 侧 helper、binding 完全还原 |
| `src/models/exact_coordinate_master.py` | ①`_resolve_front_clear_lift_enabled_from_env`（严格值域，垃圾值抛错）；②`_create_front_clear_free_cells`（4,900 free Bool + 1×1 optional interval 独立 `_front_clear_*` 列表 + padded 72×72 常量0边圈）；③`_front_clear_offsets_by_mode`（逐 mode front 偏移派生 + 四个定理前提 fail-closed 哨兵：矩形/self-front/同侧不重/平移不变）；④`_add_front_clear_lift_demand_constraints`（mode 条件索引式 + AddElement + 每侧 Sum≥demand + padding 界校验；未 profile op 出范围跳过）；⑤build() 接线：初始 NoOverlap = B∪F、ghost combined 保持 B∪G（生死线：free 绝不进 `_core_*`）；⑥export/bind core binding 携带 lift identity（clone 不重读 env）；⑦build_stats + interval 计数口径含 free |
| `src/search/benders_loop.py` | env 双注册（`_CERTIFIED_KNOWN_ENV_NAMES` + `_CERTIFIED_OPERATIONAL_ENV_ALLOWLIST` 带依据注释）；模块级 `_front_clear_lift_scope_raw_empty_instances` 分桶 helper（**纯诊断，不进 conflict summary/proof 记录**——golden digest 事故的改判形态）+ controller `_front_clear_raw_empty_by_iteration` + `[front-clear] raw empty_binding_domain total=X lift_scope=Y` 逐迭代打印（raw 口径验收遥测，F-05 假绿面的解法；lift OFF 时零输出零状态） |

**非 sealed**：`test_front_clear_lift_demand_ssot.py`（26）、
`test_front_clear_lift_master.py`（17，含 R11 击杀哨兵与咬合哨兵）、
`test_front_clear_lift_full_pool_golden.py`（1 slow，conftest 已登记）、
`test_rab_sep_soundness_sentinels.py`（+1 遥测分桶）、`test_exact_contract.py`
（+1 env 双注册）、PROJECT_LOCK **F-GM-FCL-01**、NAV_MAP、18_workflow_env_config、
checker/obligations JSON（reseal）。

## §2 验证结果（阶梯 1-2 已过）

**阶梯 1（build-only 审计，真 prod 数据 6×6）**：
- 拓扑：恰 2 条活跃 NoOverlap；一条精确 = B∪F（10,471 = body 5,571 + free
  4,900）、一条精确 = B∪G（9,796）；零未知成员；**无任何约束同时含 free 与
  ghost**；dedup 正确拒清（deduped=False）。
- 规模逐位吻合审查席 F5 独立实算：219 slot / 1,702 index+element / 6,808
  mode 等式 / 876 mode 文字 / 17 组覆盖 / 2 组出范围 / demand 表全对。
- 全部定理前提 fail-closed 哨兵在真池零触发。
- 成本：master build 15.02s（基线 ~14.8s）；build 期峰值 RSS 5.9 GiB。

**阶梯 2（全池黄金对照，slow 测试）**：17 组 × 逐组池全扫 =
**286,636 pose**，双向 front 集相等 + padded row/column/f 三断言零违规
（51.4s）。

**单元/哨兵**：lift master 哨兵 17/17（ghost 内 front 可自由=R11 击杀哨兵、
堵 front ON 判死/OFF 可行=咬合哨兵、env 严格值域、clone identity、flat id
单射）；SSOT 26/26；RAB 哨兵回归 51/51；env 契约 2/2。

## §3 reseal 轮次与两个教训

批中 reseal 三轮（smoke 前 4 pin / 防御分支后 exact master 再 pin / golden
事故修复后 binding+benders 再 pin）。**教训一（R16 活案例）**：一次手抄
64 位 sha 丢 2 字符，被「程序化比对 pin vs 实际」抓出——第三轮起 sha 全程
字节级程序替换+终验，不过眼手。**教训二（proof 面清洁）**：诊断字段放进
conflict summary 会流进候选 proof 记录，慢 lane 的 golden semantic digest
测试（`test_p1_min_tcb_closure_redlines`）当场抓漂移——诊断遥测一律放
controller/stdout 侧，proof 面零新增键（哨兵已钉：summary 无 lift_scope
键）。双 checker 每轮后全绿（15/67、65/83 口径不变）。

## §4 门禁

- 第一轮 preflight --full：绿（19 gates / 4470 tests）。
- 第一轮 --slow-tests：**1 failed**（golden semantic digest 抓 proof 面污
  染，见 §3 教训二）→ 修复 + 第三轮 reseal 后全套重跑（终态见 commit）。

## §5 移交与遗留（任务 9 = 验证阶梯 3-5，批提交后）

1. **阶梯 3**：raw 事件 corpus 持久化 runner + 无 solve 结构 checker
   （六步设计=doc 04 v2 §5；含实际 proto 接线检查 + RAB-nonempty 负控）。
2. **阶梯 4**：单锚点 live smoke（到达 binding 且 scope 桶 raw=0 严格判据；
   NOT_EVALUATED 不判绿）。
3. **阶梯 5**：同 revision 独立进程 lift OFF/ON A/B（逐迭代遥测落盘 +
   systemd-run MemoryMax/MemorySwapMax 保护 + 一次一个 solve 铁律）。
4. 判读后默认值翻转 = owner 拍板项。
5. 已知边界：lift 只覆盖 219/266（generic op 47 个不在内，RAB 通道兜底）；
   预算数字仍是 UNVALIDATED FORECAST（阶梯 5 校准）。
