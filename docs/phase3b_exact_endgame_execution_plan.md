---
status: SUPERSEDED_HISTORICAL
source_of_truth: historical execution-plan snapshot only; current state is governed by PROJECT_LOCK.md and docs/项目说明/06_current_status.md
last_updated: 2026-04-17
owner: phase3b-exact-endgame
---

# Phase 3B 详细计划与执行书（从当前状态到项目最终结束）

> ⚠️ **HISTORICAL / SUPERSEDED (2026-06-04)**：本文件描述的 **Phase 3B tuning paradigm** 路线（B2/B5/B7 等）已被 **cut-family LBBD 重设计** 取代（见 `CLAUDE.md` / `PROJECT_LOCK.md`）。当前主线 = **Phase 1.2 spike close**（F1–F9 cut family）。下方内容保留作历史路线记录，**非当前现状**；frontmatter 的 `ACCEPTED_DRAFT` / `last_updated: 2026-04-17` 按历史读。

## 0. 这份文件覆盖什么

这份文件只覆盖**当前项目剩余主线里最重要的那一段**：

- `valley4_protocol_core` 70×70 的 **Phase 3B**
- 也就是：从“现在已经完成的单基地交付 / 消费层产品化状态”继续推进，直到
  **full-scale 70×70 solver 级 exact `CERTIFIED` 终局真正落地**，并把这个终局
  重新回灌进当前已经完成的单基地 release / viewer / landing / frontdoor /
  entrypoints / surface-health 体系里，最后完成项目收尾。

这份文件**不**覆盖：

- 重新激活其他基地
- 重新把 outer-deployment 拉回默认关键路径
- 为未来多基地提前扩宽当前单基地合同

这些边界与当前主计划一致：现阶段唯一活跃面仍然是
`valley4_protocol_core` 70×70，其他基地继续保留为 `future_scope`。turn0file0

---

## 1. 当前起点（2026-04-17）

### 1.1 已经完成的部分

按当前仓库状态，下面这些主线工作已经基本收口：

1. **单基地活跃合同已经压稳**
   - 活跃合同只剩 `valley4_protocol_core` 70×70。
   - 其他基地与 outer-deployment 都已被明确收窄到 `future_scope`。

2. **3A 产品/交付层“最终蓝图”已经有固定交付版本**
   - 当前 active release：`valley4_protocol_core_70x70_r20260416`
   - 当前 delivery status：`ready_for_single_base_delivery`

3. **第四阶段消费层/UI 产品化尾巴已经收口**
   - repo-front、current landing、viewer、latest bundle、aggregate entrypoints
     都已打通
   - `current_surface_health.json` 当前是：
     `clean · 229 checks · 0 drift`

### 1.2 仍然没完成、也是 3B 的真正目标

当前仓库里**还没有** checked-in 的 full-scale exact 终局产物。也就是：

- 还没有 checked-in 的 `data/checkpoints/exact_campaign_state.json`
- 还没有 checked-in 的 `data/checkpoints/exact_campaign_telemetry.json`
- 还没有 checked-in 的 `data/solutions/final_solution.json`
- 还没有 checked-in 的 `data/blueprints/optimal_blueprint.json`
- 还没有 checked-in 的 `data/solutions/certified_delivery_manifest.json`
- 单基地产品面里关于 exact 终局的口径现在仍然是**硬编码 `open`**，而不是从真实
  solver 终局状态派生出来

换句话说，**3A/产品层的“可交付版本”已经有了，但 3B/求解器层的“full-scale
exact CERTIFIED 终局”还没有闭环。**

### 1.3 当前 exact 主线可直接复用的现成基础

当前仓库里已经有一整套可继续推进 3B 的 exact runtime 基础：

- `main.py`：`certified_exact` / `exploratory` 顶层入口
- `src/search/outer_search.py`：外层 exact candidate orchestration
- `src/search/exact_campaign.py`：campaign state / resume / artifact-hash contract
- `src/search/exact_parallel_scheduler.py`：coordinator-only writer 的并行波次调度
- `src/io/delivery_manifest.py`：从 exact campaign state 导出
  `certified_delivery_manifest.json`
- `docs/frontier_probe_strategy.md`：probe-first exact-safe 操作指导
- `docs/parallel_configuration.md`：48GB 机器上的并行/内存指导
- `temp_scripts/benchmark_parallelism.py`：并行度/worker-profile/acceptance benchmark harness
- `src/tests/test_exact_contract.py`、`test_parallel_scheduler.py`、
  `test_delivery_manifest.py`、`test_master.py`、`test_binding.py`、
  `test_routing.py`：当前最重要的 exact 主线回归面

### 1.4 当前 exact 起点的硬数据（来自当前仓库工件）

下面这些数字，是这份执行书后续所有阶段的**起点基线**：

- grid：`70 × 70`
- mandatory exact instance count：`266`
- mandatory occupied-area lower bound：`3544`
- generic-input induced `protocol_storage_box` lower bound：`1`
- safe static occupied-area lower bound：`3553`
- safe area upper bound（ghost rectangle area upper bound）：`1347`
- current admissible candidate domain count（`min_side >= 6`）：`1196`
- candidate-placement pool total：`81,795` poses across `7` facility types

这意味着 3B 不是“从零开始搭 exact”，而是从一个已经成形但尚未收敛到 full-scale
terminal proof 的 exact runtime 继续往前推。

### 1.5 当前已知 benchmark / telemetry 起点（来自现有 benchmark bundle）

当前最新存档 benchmark 证据，可作为 3B 第一轮执行时的起始参考：

1. **Production acceptance 基线（2026-03-24 bundle）**
   - `prod_1x1`：约 `0.0154` candidate/s
   - `prod_2x4`：约 `0.0269` candidate/s
   - `prod_4x4`：约 `0.0534` candidate/s
   - `prod_2x8`：约 `0.0270` candidate/s

   当前已知基线下，`prod_4x4` 是最适合作为**默认长跑 operating profile** 的起点。

2. **Process priority acceptance**
   - `prod_4x4 high` 与 `prod_4x4 normal` 没显示出足够大的稳定收益差
   - 因此 3B 默认不把“高优先级”当成主解法，只保留为可选补充配置

3. **Pre-master frontier precheck serial bench**
   - 当前一份 10-candidate serial bench 中，`9/10` 在 pre-master 阶段就被
     `boundary_port_all_anchors_infeasible` 消掉
   - 剩余 `1` 个 candidate 仍然停在 `UNKNOWN`

这说明：

- precheck 路径已经有明显价值
- 但 UNKNOWN/UNPROVEN 仍然是 3B 的核心阻塞面之一

---

## 2. 3B 最终完成态（Definition of Done）

3B 的真正完成，不是“某一次跑出了一个看起来不错的结果”，而是下面两层都完成。

### 2.1 Solver 层完成态

必须同时满足：

1. full-scale `70×70` exact campaign 的最终状态是 **`CERTIFIED`**
2. 终局不是“某次单候选 certified”而已，而是**全域穷尽后**的 certified terminal result
3. `ExactCampaign` 的状态满足 resume contract，且 artifact hashes 一致
4. `best certified result` 单调性没有被破坏
5. 下面这些 exact 终局工件都存在并彼此一致：
   - `data/checkpoints/exact_campaign_state.json`
   - `data/checkpoints/exact_campaign_telemetry.json`
   - `data/solutions/final_solution.json`
   - `data/blueprints/optimal_blueprint.json`
   - `data/solutions/certified_delivery_manifest.json`
6. `exact_campaign_state.json` 中应满足：
   - `final_status == "CERTIFIED"`
   - `final_result` 非空
   - `last_stop_reason.reason == "search_exhausted_all_candidates"`

### 2.2 Repo / 产品层完成态

solver 终局拿到之后，还必须把“当前单基地消费层”一起收完：

1. 当前所有单基地消费面不再硬编码 `exact_full_scale_certified.status = open`
2. release / viewer / landing / frontdoor / entrypoints / surface-health
   全部改为**从真实 exact 终局证据派生** exact 状态
3. 以 exact-certified 结果为基础，重新 promotion 一版最终 release
4. repo-front 当前入口页能明确告诉 reviewer / 脚本消费者：
   这个 active release 已经不再只是 `delivery-ready`，而是已经关联到真实的
   solver-side full-scale exact certified closeout
5. 最终 README / PROJECT_LOCK / FILE_STATUS / CHANGELOG / 相关 specs / tests
   全部对齐

只有 2.1 + 2.2 都完成，3B 才算真正结束。

---

## 3. 3B 的总原则

### 3.1 不扩宽支持面

整个 3B 期间：

- 不重启其他基地
- 不把 `future_scope` 拉回活跃面
- 不把 outer-deployment 拉回默认关键路径

### 3.2 不混淆 3A 与 3B

- 3A 已经拿到了 delivery-ready 的固定 release
- 3B 追的是 solver-side 的 full exact terminal proof

任何文档、脚本、frontdoor 文案，都不能再把两者混成一件事。

### 3.3 任何 exact-safe 改动都要尊重 artifact-hash reset 事实

`ExactCampaign` 当前 resume contract 的 artifact hash 真源是这 4 个文件：

- `rules/canonical_rules.json`
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

因此：

- 只要 3B 某轮工作改了其中任意一个，就**不应该假装延续旧 campaign**
- 应显式接受 campaign reset，并把“为什么 reset”当成正常证据，而不是意外

### 3.4 先用诊断 profile 定位，再用生产 profile 长跑

- 问题定位优先 `1x1` 或低并发 profile
- 生产长跑优先从当前已知最强起点 `prod_4x4` 开始
- 任何更激进的并行配置，都必须先过 benchmark acceptance 再进入主线

### 3.5 不把 UNKNOWN 当成“有进展”的终态

3B 的核心不是“能长时间跑”，而是：

- 能把 UNKNOWN / UNPROVEN 逐类压缩
- 能持续把候选域缩小
- 最后能拿到 `search_exhausted_all_candidates` 的 certified close

---

## 4. 从现在到项目结束的全流程路线图

下面这条路线，是从当前状态到最终收尾的**唯一推荐顺序**：

1. **B0：冻结起跑线并建基线清单**
2. **B1：加固 recovery / resume / telemetry 操作面**
3. **B2：推进 exact-safe lower bounds / prechecks / dominance，继续缩域**
4. **B3：系统性清理 UNKNOWN / UNPROVEN 阻塞类**
5. **B4：确定生产 campaign 的默认 operating profile**
6. **B5：先拿 first certified anchor，再持续 resume 到全域穷尽**
7. **B6：冻结 exact 终局证据包**
8. **B7：把 exact-close 状态回灌到当前单基地 release / UI / scripts surface**
9. **B8：最终文档、治理、交付与归档收尾**

下面把每一阶段展开。

---

## 5. B0：冻结起跑线并建基线清单

### 5.1 目标

把“3B 从哪儿开始”固化成一份 checked-in 或至少 reviewable 的基线记录，避免后面重复争论“到底是从哪一版开始推进的”。

### 5.2 本阶段要做的事

1. 记录当前 repo 起点：
   - active release id
   - current surface health
   - 当前 exact source-of-truth 4 文件的 SHA256
   - 当前 candidate-domain count / area upper bound / mandatory lower bound

2. 固化当前 exact baseline tests：
   - `test_exact_contract.py`
   - `test_parallel_scheduler.py`
   - `test_delivery_manifest.py`
   - `test_delivery_manifest_compatibility_exports.py`
   - `test_master.py`
   - `test_binding.py`
   - `test_routing.py`

3. 固化当前 benchmark / telemetry 基线：
   - 一次 `parallelism-study`
   - 一次 `production-acceptance`
   - 一次 1 小时以内的 diagnostic exact run（允许 UNKNOWN，但要留下 checkpoint 和 telemetry）

4. 形成一份 3B 起跑线 manifest（建议后续新增）：
   - `.artifacts/phase3b_startline/startline_manifest.json`
   - `.md`
   - `.txt`

### 5.3 建议命令

```bash
python -m pytest \
  src/tests/test_exact_contract.py \
  src/tests/test_parallel_scheduler.py \
  src/tests/test_delivery_manifest.py \
  src/tests/test_delivery_manifest_compatibility_exports.py \
  src/tests/test_master.py \
  src/tests/test_binding.py \
  src/tests/test_routing.py
```

```bash
python temp_scripts/benchmark_parallelism.py \
  --suite-kind parallelism-study \
  --suite-output .codex_test_logs/phase3b/parallelism_startline.json
```

```bash
python temp_scripts/benchmark_parallelism.py \
  --suite-kind production-acceptance \
  --suite-output .codex_test_logs/phase3b/production_acceptance_startline.json
```

```bash
EXACT_CP_SAT_WORKERS=1 \
python main.py \
  --mode certified_exact \
  --campaign-hours 1 \
  --parallel-processes 1 \
  --frontier-probe-mode auto \
  --master-seconds 120 \
  --binding-seconds 120 \
  --routing-seconds 120 \
  --benders-max-iter 15
```

### 5.4 退出门

只有当下面都成立，B0 才算完成：

- baseline tests 绿
- benchmark summary 留档
- 至少有一份 current exact checkpoint + telemetry 被保存
- 起跑线 manifest 可供 reviewer/后续开发直接读取

---

## 6. B1：加固 recovery / resume / telemetry 操作面

### 6.1 目标

把 168 小时级 exact campaign 真的变成“敢停、敢续、敢换 profile、敢诊断”的工程面，而不是一条脆弱的一次性长跑命令。

### 6.2 本阶段要做的事

1. **把 campaign lifecycle 看清楚**
   - clean start
   - clean resume
   - artifact-hash mismatch reset
   - worker failure 后保留 best certified result
   - time budget exhaust -> UNKNOWN
   - candidate UNKNOWN / UNPROVEN -> stop and retain evidence

2. **补可读性工具（建议新增）**
   建议新增一个只读 inspector，例如：
   - `scripts/inspect_exact_campaign_state.py`

   它至少应汇总：
   - current final status
   - last stop reason
   - candidate status counts
   - best certified candidate objective
   - artifact hashes
   - resume compatibility
   - telemetry path / delivery manifest path

3. **明确 workspace policy**
   - 调参和中间长跑都在 workspace copy 里做
   - repo 本体只接受“最终冻结工件”
   - 中途 UNKNOWN/UNPROVEN 证据不直接污染 checked-in 主路径

4. **把 reset 当成显式事件管理**
   每次改动 exact hash 4 文件之一，都必须记录：
   - why reset happened
   - which artifact changed
   - which benchmark baseline was invalidated

### 6.3 退出门

- 所有 resume / reset / stop-reason 分支都有明确脚本或明确人工操作说明
- campaign state 可以被独立 summarize，而不用肉眼翻 JSON
- 长跑中断不会导致“状态还在，但证据不可读”的局面

---

## 7. B2：推进 exact-safe lower bounds / prechecks / dominance，继续缩域

### 7.1 目标

尽可能在**不改变 exact proof semantics** 的前提下，让真正需要进入 master/binding/routing 的候选数继续下降。

### 7.2 当前已知有效方向

当前仓库已经证明有价值的方向包括：

- safe static occupied-area lower bound
- boundary-port anchor feasibility precheck
- frontier pruning / dominance
- exact-safe probe scheduling
- exact core reuse / cut replay / telemetry aggregation

3B 接下来要做的是继续把这些“已经有但还不够”的 exact-safe 缩域能力往前推。

### 7.3 本阶段要做的事

1. **逐项审视 precheck elimination reasons**
   特别是当前已知高频项：
   - `boundary_port_all_anchors_infeasible`

2. **把“高频 UNKNOWN 前的 cheap eliminations”继续前推**
   原则是：
   - 能在 pre-master 证伪的，不要拖到 master
   - 能在 master 前给出 exact-safe negative screen 的，不要拖到 binding/routing

3. **lower-bound / dominance 改动必须自带三类证据**
   - exact-safe 论证
   - regression tests
   - candidate-domain / precheck-elimination / throughput 的 before-after 对比

4. **每次缩域改动后必须重新做 B0 的 baseline 局部复测**
   因为这类改动极可能改变 hash 真源，旧 campaign 需要被视为 reset。

### 7.4 建议追踪指标

- candidate domain count
- frontier size
- precheck elimination count / ratio
- solve-attempt count
- `master_status == UNKNOWN` 的占比
- `candidate_returned_unknown` / `candidate_returned_unproven` 的 stop frequency

### 7.5 退出门

至少满足下面两条中的两条以上：

- candidate domain 明显缩小
- precheck elimination ratio 明显上升
- 长跑 acceptance baseline 的 candidate throughput 没有被明显拖慢
- UNKNOWN 密度下降

---

## 8. B3：系统性清理 UNKNOWN / UNPROVEN 阻塞类

### 8.1 目标

把“为什么 stop 在 UNKNOWN / UNPROVEN”从零散个案，变成一张稳定的、可逐个清除的 blocker taxonomy。

### 8.2 当前必须明确区分的 blocker 层级

至少要把 UNKNOWN / UNPROVEN 拆成下面几层：

1. **Pre-master 之前就应当被消掉却没消掉**
2. **Master 阶段 UNKNOWN**
   - zero-branch unknown
   - start incompatible unknown
   - ghost-aware start失败但未能给出 infeasible proof
3. **Binding 阶段 UNKNOWN / timeout**
4. **Routing 阶段 UNKNOWN / timeout**
5. **Wave merge / worker failure / orchestration 层问题**

### 8.3 本阶段要做的事

1. 对 top frontier / top repeated blockers 建最小复现集
2. 每类 blocker 至少要有：
   - 一个最小复现 fixture 或 benchmark slice
   - 一个回归测试
   - 一个明确“修完之后怎样判断真的改善”的指标
3. 严禁“靠更长时间预算”掩盖分类不清的问题
4. 对 recurring UNKNOWN，要优先回答两个问题：
   - 这是本来就该 `INFEASIBLE` 的吗？
   - 还是本来就该 `CERTIFIED`，只是当前 proof path 太弱？

### 8.4 建议阶段内产物

建议新增一套 blocker inventory，例如：

- `.artifacts/phase3b_unknown_triage/blocker_inventory.json`
- `.md`

其中至少记录：

- candidate key
- objective
- stop stage
- stop reason
- first seen / last seen
- repro command
- linked test name
- current disposition（open / mitigated / fixed / superseded）

### 8.5 退出门

- top recurring UNKNOWN/UNPROVEN blocker 已被分类
- 每个 blocker 都有对应测试或 bench
- 下一轮长跑里出现“未知的新 UNKNOWN 类型”的概率明显下降

---

## 9. B4：确定生产 campaign 的默认 operating profile

### 9.1 目标

在当前 48GB 约束下，明确哪一套配置是“默认生产长跑配置”，哪一套配置只用于诊断。

### 9.2 当前建议默认配置

基于现有 benchmark 证据，3B 当前默认建议是：

- **诊断 profile**：`1x1` 或低 worker 单进程
- **生产 profile**：`prod_4x4`
  - `parallel_processes = 4`
  - `EXACT_CP_SAT_WORKERS = 4`

这与当前 `docs/parallel_configuration.md` 的 48GB 指导一致：
`4` 个 parallel workers 是安全起点，`5` 需要额外确认，`6+` 不应默认使用。

### 9.3 本阶段要做的事

1. 固化 `prod_4x4` 作为当前默认长跑起点
2. 任何改动 master/binding/routing/precheck/lower-bound 之后，都要重新做一次
   production acceptance
3. 暂不把 `process-priority high` 作为默认策略
4. 只有在新 benchmark 反证时，才允许更换默认生产配置

### 9.4 建议命令

```bash
EXACT_CP_SAT_WORKERS=4 \
python main.py \
  --mode certified_exact \
  --campaign-hours 168 \
  --parallel-processes 4 \
  --resume-campaign \
  --frontier-probe-mode auto
```

### 9.5 退出门

- 一个明确的默认生产 profile 被记录下来
- 变更 profile 的门槛和 benchmark 验证规则被写清楚

---

## 10. B5：先拿 first certified anchor，再持续 resume 到全域穷尽

### 10.1 目标

把“长期 exact campaign”拆成两个更可控的目标：

1. **先拿到 first certified anchor**
2. **再继续 resume，直到 `search_exhausted_all_candidates`**

### 10.2 为什么必须先 anchor、再 exhaustion

当前仓库已经有 probe-first exact-safe 思路。它的价值是：

- 一个中等面积的 `CERTIFIED` anchor，往往能 prune 掉大批 objectively-worse-or-equal 候选
- 比一长串 top-layer `INFEASIBLE` 证明更快建立“真正有用的上界/下界夹逼”

### 10.3 建议执行节奏

#### A. Anchor loop

- 目标：尽快拿到第一份 `CERTIFIED`
- 配置：短时 budget + probe mode + 低并发诊断或中等并发
- 失败处理：
  - 若仍旧 UNKNOWN/UNPROVEN，回到 B3
  - 若 precheck 改善空间明显，回到 B2

#### B. Resume-to-prune loop

- 目标：基于已拿到的 best certified result 继续 resume
- 配置：默认生产 profile（当前建议 `prod_4x4`）
- 关注：
  - prune gain
  - frontier shrink
  - duplicated work 是否仍为 false
  - campaign_valid_after_run 是否持续为 true

#### C. Exhaustion loop

- 目标：把剩余 potential domain 真正扫完
- 终止条件：
  - `last_stop_reason.reason == search_exhausted_all_candidates`
  - `final_status == CERTIFIED`

### 10.4 本阶段核心纪律

- 任何 UNKNOWN/UNPROVEN stop，都不是终点，只是 triage 入口
- 任何 hash 真源变化后，旧 campaign 只可用于对比，不能冒充同一条连续证明链
- 每次长跑都必须留 checkpoint + telemetry + operator summary

### 10.5 退出门

- 至少拿到一个 first certified anchor
- 后续 resume 能稳定复用 best certified result 做 pruning
- 最终 campaign 在非 exploratory 证据链下走到 `search_exhausted_all_candidates`

---

## 11. B6：冻结 exact 终局证据包

### 11.1 目标

在 solver 层真正拿到 terminal certified end-state 之后，形成一个**不可混淆、可再检查、可长期引用**的 exact 终局证据包。

### 11.2 必须存在的工件

至少要冻结这些：

- `data/checkpoints/exact_campaign_state.json`
- `data/checkpoints/exact_campaign_telemetry.json`
- `data/solutions/final_solution.json`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/certified_delivery_manifest.json`

建议再补一层更小的 exact-status 汇总（建议新增）：

- `data/solutions/exact_full_scale_status.json`
- `data/solutions/exact_full_scale_status.md`

建议该汇总至少包含：

- `status`：`open | certified`
- `campaign_state_path`
- `campaign_telemetry_path`
- `delivery_manifest_path`
- `final_solution_path`
- `optimal_blueprint_path`
- `best_certified_result.ghost_rect`
- `last_stop_reason`
- `artifact_hashes`
- `proof_summary_schema_version`

### 11.3 本阶段要做的事

1. 对 exact terminal result 做一次一致性审查：
   - final solution / blueprint / delivery manifest 是否来自同一 best certified result
2. 校验 resume contract 仍然成立
3. 冻结 artifact hashes
4. 形成一份“reviewer 一眼能看懂”的 exact terminal summary

### 11.4 退出门

- 终局 exact 证据包完整
- reviewer 不需要运行 solver，也能确认“这是 full-scale terminal certified result，而不是一次中途 certified candidate”

---

## 12. B7：把 exact-close 状态回灌到单基地 release / UI / scripts surface

### 12.1 这是 3B 里最容易被漏掉、但必须做完的一段

当前单基地 release / viewer / landing / frontdoor / entrypoints / surface-health
已经收口得很好，但它们现在对 exact 终局的理解仍然是：

- “`open`，并且这是一个固定说明文本”

这在 3A/第四阶段是正确的；但一旦 3B solver close 真正落地，**当前这套产品面如果不改，就会继续对用户说“exact 还是 open”，造成信息倒挂。**

### 12.2 本阶段要做的事

1. **去掉硬编码 `open`**
   当前至少需要重构这些路径，让 exact 状态来自真实 solver evidence，而不是常量：
   - `scripts/run_industrial_planner_single_base_e2e.py`
   - `scripts/build_industrial_planner_single_base_delivery_release.py`
   - `src/render/industrial_planner_single_base_delivery_viewer.py`
   - `src/render/industrial_planner_single_base_delivery_landing.py`
   - `src/render/industrial_planner_single_base_delivery_frontdoor.py`
   - `src/render/industrial_planner_single_base_delivery_entrypoints.py`
   - `src/render/industrial_planner_single_base_delivery_surface_alignment.py`
   - `src/render/industrial_planner_single_base_delivery_surface_health.py`

2. **引入 exact-status resolver（建议新增）**
   建议新增一个统一读取 exact 终局状态的小层，例如：
   - `src/io/exact_status.py`
   - `scripts/build_exact_full_scale_status.py`

   让所有消费层都通过同一个 resolver 读取：
   - 现在是 `open`
   - 将来可以变成 `certified`

3. **把测试从“只接受 open”升级成“至少支持 open / certified 两种状态”**
   当前很多测试直接断言 `status == "open"`。3B close 之后，这些测试必须升级成：
   - open path 仍成立
   - certified path 也成立

4. **重新 promotion 一版 exact-certified 的 active release**
   当 exact 终局证据包冻结后，应 promotion 一个新的 release id，例如：
   - `valley4_protocol_core_70x70_rYYYYMMDD_exact_certified`

   然后刷新：
   - current release pointer
   - current viewer pointer
   - current landing
   - repo frontdoor
   - active entrypoints
   - current surface health
   - no-drift audit

### 12.3 退出门

- 当前单基地所有入口面都能准确显示 exact 已闭环
- 不再有任何“明明 exact 已完成，但 frontdoor 还说 open”的残留面

---

## 13. B8：最终文档、治理、交付与归档收尾

### 13.1 目标

把 3B 结束后的 repo 状态，真正收成“项目完成态”而不是“跑出来了但说不清”。

### 13.2 本阶段要做的事

1. 更新治理文件：
   - `PROJECT_LOCK.md`
   - `FILE_STATUS.md`
   - `CHANGELOG.md`
   - `README.md`

2. 更新与 exact runtime 相关的 specs/docs：
   - `specs/11_pipeline_orchestration.md`
   - 相关 benchmark / probe / parallel docs
   - 任何 still-open 的 exact-status note

3. 归档最终证据与 benchmark：
   - baseline bundle
   - final acceptance benchmark
   - terminal exact evidence bundle
   - final delivery release bundle

4. 形成最后的 reviewer handoff：
   - 起点是什么
   - 终点是什么
   - exact 终局证据在哪
   - 当前 active release / frontdoor 指向哪一版

### 13.3 退出门

- repo 顶层 README 与 frontdoor 都能清楚表述“项目已完成到什么程度”
- 治理文件不再保留过时的 open 说法
- reviewer 可以从 repo 直接读出终局结论

---

## 14. 3B 的执行节奏：每个循环怎么跑

3B 不是一条线性“写代码 -> 长跑一次 -> 成功”的流程。更现实的执行循环是：

1. **选一个 blocker 或缩域点**
2. **先补/改测试**
3. **再改 exact-safe 代码或 orchestration**
4. **跑 baseline tests**
5. **跑小型 benchmark / diagnostic campaign**
6. **看 UNKNOWN/UNPROVEN / throughput / prune 指标有没有改善**
7. **若 exact hash 真源变了，显式 reset campaign**
8. **通过后再发起新一轮长跑**
9. **若长跑拿到更强证据，再进入下一轮 triage / pruning**
10. **直到拿到 terminal `search_exhausted_all_candidates` certified 终局**

这是 3B 推荐的唯一健康节奏。

---

## 15. 必须固定下来的决策规则

### 15.1 什么时候必须 reset campaign

只要这 4 个 hash 真源之一变了，就必须 reset：

- `rules/canonical_rules.json`
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

### 15.2 什么时候不允许宣称 3B 完成

只要下面任意一条不成立，就不许宣称 3B 完成：

- `final_status == CERTIFIED`
- `last_stop_reason.reason == search_exhausted_all_candidates`
- exact terminal artifacts 齐全
- 单基地当前入口面已经不再写 `open`

### 15.3 什么时候必须从长跑退回 triage

出现以下任一情况时，不应继续“盲跑”：

- recurring UNKNOWN 类型没有分类
- benchmark acceptance 明显退化
- duplicated work 变 true
- campaign_valid_after_run 不再稳定为 true
- stop reason 没法通过现有 telemetry 解释

---

## 16. 风险清单与对应对策

### 风险 A：UNKNOWN 长期压不下去

**对策：**

- 强制 blocker taxonomy
- 每类 blocker 绑定最小复现和测试
- 不允许只靠加时长回避分类

### 风险 B：lower-bound / precheck 改动带来错误剪枝

**对策：**

- exact-safe 论证 + regression + benchmark before-after 三件套缺一不可
- 所有缩域改动都要走 B0/B2 局部回归

### 风险 C：并行配置看起来更快，但实际引入内存压力或吞吐不稳定

**对策：**

- 48GB 默认从 `prod_4x4` 起步
- 不用 `6+` 进程做默认配置
- 任何更激进配置先过 acceptance benchmark

### 风险 D：solver close 了，但产品面仍停在 open

**对策：**

- 把 B7 视为 3B 的正式组成部分，而不是收尾可选项
- 所有 current-surface builders/tests 一起升级

### 风险 E：release/product surface 与 solver evidence 脱节

**对策：**

- 引入统一 exact-status resolver
- 让 e2e / release / frontdoor / health 都从同一 exact status manifest 读取

---

## 17. 最终交付树（项目结束时应该长成什么样）

项目最终结束时，建议至少能从 repo 里直接找到下面这些东西：

### 17.1 Exact 终局证据

- `data/checkpoints/exact_campaign_state.json`
- `data/checkpoints/exact_campaign_telemetry.json`
- `data/solutions/final_solution.json`
- `data/blueprints/optimal_blueprint.json`
- `data/solutions/certified_delivery_manifest.json`
- `data/solutions/exact_full_scale_status.json`（建议新增）

### 17.2 Final active release / consumer surface

- `data/examples/industrial_planner/active_single_base_delivery_release.json`
- `data/examples/industrial_planner/active_single_base_delivery_viewer.json`
- `data/examples/industrial_planner/current_delivery/index.html`
- `data/examples/industrial_planner/index.html`
- `data/examples/industrial_planner/active_single_base_delivery_entrypoints.json`
- `data/examples/industrial_planner/current_surface_health.json`

### 17.3 Final governance

- `README.md`
- `PROJECT_LOCK.md`
- `FILE_STATUS.md`
- `CHANGELOG.md`
- relevant specs / runbooks / guides

---

## 18. 最终验收清单

### 18.1 Solver 层

- [ ] exact terminal campaign state 已冻结
- [ ] final status = `CERTIFIED`
- [ ] stop reason = `search_exhausted_all_candidates`
- [ ] final solution / blueprint / delivery manifest 一致
- [ ] benchmark / telemetry / checkpoint 都可复读

### 18.2 Repo / 产品层

- [ ] 当前 active release 绑定到 exact terminal evidence
- [ ] frontdoor / entrypoints / surface health 不再显示 `open`
- [ ] no-drift audit clean
- [ ] current bundle / latest bundle / viewer / landing 全部刷新

### 18.3 治理层

- [ ] PROJECT_LOCK / FILE_STATUS / CHANGELOG / README 全部更新
- [ ] 文档不再把 3B 说成 open item
- [ ] 其他基地仍然保持 `future_scope`

当 18.1 + 18.2 + 18.3 全部打勾时，当前项目才算真正从“现在的 3A+产品化已收口状态”走到了“3B exact 主线也完成”的最终结束态。

---

## 19. 一句话版本

**从现在到项目最终结束的唯一正确路线是：先冻结 3B 起跑线与 benchmark 基线 → 再加固 recovery/resume/telemetry → 再继续推进 exact-safe 缩域与 UNKNOWN/UNPROVEN 清理 → 再用稳定生产 profile 长跑到 full-scale `CERTIFIED` 且 `search_exhausted_all_candidates` 的终局 → 再把这个 exact-close 结果回灌进当前单基地 release / viewer / frontdoor / health 全部入口面 → 最后做治理与归档收尾。**
