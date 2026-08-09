# P1.3 M5 实测入口侦察（cut framework 收敛实测）

只读侦察，2026-07-08。目标：为 M5「收敛实测」设计非 certified 的实测入口。
所有断言均已回源码核实，行号为当前 HEAD 的 `src/...` 生产副本（非 `docs/research/.../shared_infra` 旧拷贝）。

---

## 结论速览（先读这段）

**没有任何 `main.py` 的 mode/flag 能在真实例上跑 attach。** 两条内建路径都不行：
- `--mode certified_exact`：在 `run_benders_for_ghost_rect` 入口就撞 unsafe map fail-closed（`benders_loop.py:8067-8098`），控制器根本不构造。
- `--mode exploratory` / `--exploratory`：能进控制器，但 `_run_exploratory`（`benders_loop.py:4729-4818`）是 **flow-diagnostic-only 循环**，**完全不调 binding/routing 子问题，也永不调 `_maybe_attach_framework_cuts`**。attach 只活在 certified 的 binding+routing 代码路径里。

所以 M5 实测入口 = **直接 Python 调用 harness**（`_cut_framework_attach_enabled` docstring `benders_loop.py:7529-7537` 明说「reachable only from direct (non-certified) invocations and unit tests」）：构造真 session + 真 master + 直接 new `LBBDController(solve_mode="certified_exact")` + 设 `EXACT_CUT_FRAMEWORK_ATTACH=1` + 调 `controller.run_with_status()`，**绕过 `run_benders_for_ghost_rect` 那唯一一处 env 门**。样板见 `src/tests/test_cut_framework_attach_wiring.py`（只是 toy master，M5 要换成真 266 实例 session）。

---

## Q1. 非 certified 跑完整 LBBD（真 266 实例）的入口

### 判定链（unsafe map 在哪检查、谁绕过）

- 总开关 env：`EXACT_CUT_FRAMEWORK_ATTACH`（`benders_loop.py:936`），登记在 certified unsafe map `_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES`（`benders_loop.py:949`）。
- `_cut_framework_attach_enabled`（`benders_loop.py:7529-7537`）：只读该 env，非 false 值即 True。**它自己不查 unsafe map**——门在别处。
- unsafe map 的实际检查点 = `_collect_forbidden_certified_master_domain_env_overrides`（`benders_loop.py:1349-1420`），由 `run_benders_for_ghost_rect` 在 **certified 分支** 调用（`benders_loop.py:8071`）；命中即 `return RUN_STATUS_UNPROVEN, None`（`benders_loop.py:8072-8098`），控制器不构造。
- `collect_certification_blockers`（`benders_loop.py:2032-2136`）**第一行** `if solve_mode != "certified_exact": return []`（`:2041-2042`）——**exploratory 完全跳过所有 blocker 检查**（含 unsafe env、实例模式污染、cut 校验）。
- 但 exploratory 的 `run_with_status`（`:4724-4727`）分派到 `_run_exploratory`，该循环只跑 `_run_flow_diagnostic`（`:4765`），FEASIBLE 就返回、INFEASIBLE 加 flow bottleneck cut——**没有 binding/routing/attach**。

### attach 的唯一可达路径

`_maybe_attach_framework_cuts`（`benders_loop.py:7734-7898`）的唯一生产 caller = `_run_exact_binding_and_routing`（`benders_loop.py:5812`），后者唯一 caller = `_run_certified_exact`（`benders_loop.py:4820`）。即 attach ⊂ certified binding+routing 路径。exploratory 分支根本不进这里。

### M5 harness 设计（直接调用，合法绕过 env 门）

样板：`src/tests/test_cut_framework_attach_wiring.py:135-179`（`_controller` + `_build_miner_master`）。真实例版：

1. `session = create_exact_search_session(PROJECT_ROOT, solve_mode="certified_exact", master_search_profile=...)`（`benders_loop.py:2283`）——加载 frozen 266 实例 + candidate_placements。
2. `master = MasterPlacementModel.from_exact_core(session.core, ghost_rect=(w,h), master_search_profile=...)`。
3. `controller = LBBDController(master=master, cut_manager=CutManager(checkpoint_dir=<scratch>, solve_mode="certified_exact"), project_root=PROJECT_ROOT, solve_mode="certified_exact", master_seconds=..., binding_seconds=..., routing_seconds=..., disable_master_warm_start=<bool>)`（构造签名 `benders_loop.py:3182-3355`）。
4. `os.environ["EXACT_CUT_FRAMEWORK_ATTACH"]="1"`（直调不经 `run_benders_for_ghost_rect`，故不撞 `:8071` 的门）。
5. `status, solution = controller.run_with_status()` → 走 `_run_certified_exact` → binding/routing → attach。
6. 读 `controller.master.build_stats` + `controller.last_proof_summary` 落到 scratchpad（见 Q3/Q5）。

**合法性**：这是测量 harness、非认证跑。`run_with_status()` 最多返回 `RUN_STATUS_*` + proof_summary，**没有能力 mint CERTIFIED**（durable CERTIFIED 只经 `scripts/run_supervisor_seal.py` → `supervisor_seal()`，harness 不碰）。前提是输出必须隔离（Q5）。

**注意**：ghost_rect 需给定；`run_benders_for_ghost_rect` 正常还做 pre-master precheck（boundary/mandatory rectangle）+ ghost anchor filter，直调 harness 会跳过这些启动 precheck。对「measure attach 对 master 求解 wall-clock 的影响」这个目标不影响，但要清楚 harness 不是完整生产链复刻。

---

## Q2. attach 触发条件 + 历史频率数据

### 触发点（两个，都在 `_run_exact_binding_and_routing`）

- **binding-INFEASIBLE**：`benders_loop.py:6038-6061`，`trigger="binding_infeasible"`（`:6057`），紧接 whole-layout nogood（`binding_exhausted=True`，`:6062-6070`）。
- **routing-exhausted**：`benders_loop.py:7175-7193`，`binding_status="EXHAUSTED"/routing_status="ALL_INFEASIBLE"`，`trigger="routing_exhausted"`（`:7192`）。

即每次某个 LBBD 迭代的 layout 被 binding 判死 或 所有 binding 选择的 routing 都判死时，attach 各触发一次。

### 一次 attempt 几轮 LBBD

- `benders_max_iter` 默认 **30**（`main.py:225`）；production `--master/binding/routing-seconds` 默认各 **1800s**（`main.py:221-223`）。
- attach attempt 次数 ≤ 到达 binding 的 LBBD 迭代数 ≤ 30。每 attempt 内部预算闸 2000（见 Q3）。

### 历史频率数据：**没找到（不确定，标注）**

- es 全盘扫 `exact_campaign_state.json` / telemetry / `subproblem*.jsonl` / `*campaign*.log`：只捞到 **test-tmp 与 `zmd-pj-old` 旧 worktree** 的 alias checkpoint，**当前仓库无已提交的生产 campaign telemetry** 记录 binding-INFEASIBLE/routing-exhausted 频率。`data/checkpoints/`、`data/solutions/` 是 gitignore 禁提交路径（CLAUDE.md §7）。
- 唯一的频率类 instrument = `subproblem_invocation_counter`（`src/runtime/subproblem_invocation_counter.py`）：env `EXACT_SUBPROBLEM_REPEAT_PROBE=1` 门控（`:29-32`），dump `data/telemetry/subproblem_repeat_<pid>.jsonl`（`:11`），离线 `scripts/analyze_subproblem_repeat_rate.py` 聚合。但它测的是 binding/routing **输入 repeat-rate**（P1 #12 spike，`_spike_record("binding", solution)` 在 `benders_loop.py:5821-5822`），**不是 trigger 类型频率**，且未见已生成的 dump。
- 唯一有据的相关观测：M4 card `p1-3-m4-ladder-landed.md:89` —— **生产 binding_infeasible 分支碰到的全是 demand-等式型 INFEASIBLE（反单调、不可 lift），F5 adapter 会拒发**，故真实例上 binding_infeasible 触发时 F5 常零产出，只有 F1/F6/F7 几何族能落。另 `benders_loop.py:6277-6280` 注：pose-bool master 下 front_blocked precheck ~500-600 ports、cut accumulation「15 iter 不收敛」——一条真实非收敛观测（但那是 pose-bool master，非默认 coordinate master）。

---

## Q3. 实测指标采集点 + 持久化

### 三类指标的写入点

- `proof_summary["cut_framework_attached"]`（int，attached cut 数）：`benders_loop.py:6055`（binding）与 `:7191`（routing）。随后 `self.last_proof_summary = dict(proof_summary)`（`:6071` 等）。
- `master.build_stats["cut_framework_attach_last"]`（详情 dict `{trigger, iteration, generated, attached, attached_by_family}`）：`benders_loop.py:7891-7897`（正常）；预算耗尽变体 `{...,"budget_exhausted":True,"budget":2000}` 在 `:7783-7790`。
- `master.build_stats["coordinate_framework_cut_count"]`（统一预算计数器）：在 delegate 的 add_*_cut 里自增。F1 见 `exact_coordinate_master.py:7218-7220`（同处还写 `coordinate_region_capacity_cut_count`:7217、`coordinate_region_capacity_last_cut`:7221）；F6/F7/F5 的 `add_baseline_packing_cut`/`add_power_pose_exclusion_cut`/`add_pattern_nogood_cut`（`exact_coordinate_master.py:7261/7423/7351`）同样自增该统一计数器。预算闸读它 `benders_loop.py:7779-7791`，`EXACT_CUT_FRAMEWORK_ATTACH_BUDGET=2000`（`:946`）。
- 附：F5 还写 `master.build_stats["coordinate_pattern_nogood_last_cut"]`（wiring test `:424` 读 `pattern_size`）。

### 持久化到 campaign 输出的实况

- `cut_framework_attached`（int）**在 proof_summary 里 → 会持久化**：`run_benders_for_ghost_rect` 把 proof_summary 经 `_emit_campaign_heartbeat`/`campaign.update_candidate_running_proof_summary` + `campaign.save()`（`benders_loop.py:8048-8055`）落到 `data/checkpoints/exact_campaign_state.json`。
- **`cut_framework_attach_last` 与 `coordinate_framework_cut_count` 只在 `master.build_stats`（进程内存），不进 proof_summary、不进 checkpoint**。`_exact_cut_ladder_summary`（`benders_loop.py:4626-4633`）只汇 fine_grained/binding_domain_empty/routing_front_blocked/routing_precheck，**不含** framework 计数。**这是 M5 的采集缺口**：per-family attach 明细（`attached_by_family`）今天不落盘——M4 card `:99` 说「attached_by_family 数据源已就位」指的就是它在 build_stats 里存在，但没接持久化。
- **对 M5 harness 的含义**：直调 harness 不经 campaign，直接在 `run_with_status()` 返回后读 `controller.master.build_stats`（拿 `coordinate_framework_cut_count`、`cut_framework_attach_last`）+ `controller.last_proof_summary`（拿 `cut_framework_attached`、`benders_iterations`、`master_search_summary`、wall-clock），自己写 scratchpad/telemetry。**别指望现有 checkpoint 给全 per-family 数据。**

---

## Q4. 对照实验（attach on vs off）要控的变量 + A/B 先例

### 必须钉死的混淆变量

- **warm-start hint**：`--disable-master-warm-start`（`main.py:243`）→ 控制器 `disable_master_warm_start`（`benders_loop.py:3182` 参数、`_run_certified_exact:3841` 用它）。A/B 两侧须一致；greedy/ghost hint 给定实例是确定性的，两侧同开或同关皆可，但必须相同。
- **worker 数（关键混淆）**：`EXACT_CP_SAT_WORKERS`（stage 专属 env > 它 > 内置默认，CLAUDE.md §6）；production profile 锁 `EXACT_CP_SAT_WORKERS=4` + `parallel_processes=4`。**CP-SAT 多 worker 是 portfolio、搜索路径与 wall-clock 都非确定**——A/B 想干净对比 wall-clock 应 **pin workers=1**，或多 seed 取分布。否则 attach 与否的差异被 worker 抖动淹没。
- **时间预算**：master/binding/routing_seconds 三者两侧相同。
- **master_search_profile**：两侧同 profile（默认 `exact_coordinate_guided_branching_v4`）。attach 改的是 master 约束集，本就会改 CP-SAT 搜索——这正是要测的信号；其余全部钉死才能归因。
- **实例/ghost_rect/seed**：同 session、同 ghost_rect。

### A/B 跑法先例：**无**

- `scripts/run_campaign_linux.sh`、`scripts/run_prod_*.ps1` 都是单配置生产 runner，**没有 attach on/off A/B 逻辑**。
- 唯一的 attach driver = `test_cut_framework_attach_wiring.py`，unit-scale、mock 掉 state builder（`:210-216`）。
- 结论：**M5 必须新写 A/B harness**（Q1 的直调结构 × {attach 开、attach 关} × 固定其余变量），无现成 wrapper 可复用。

---

## Q5. 风险

### 铁律：exploratory / 直调产物不得升格为证据

- 硬拦点存在且有效：exploratory 若命中 CERTIFIED 会在 `outer_search.py:2892-2909` 被强制降级为 `RUN_STATUS_UNPROVEN`（`search_status`/返回值都改写）。
- 但 M5 harness 走的是 `solve_mode="certified_exact"`（为了拿 binding/routing），只是绕过了 `run_benders_for_ghost_rect` 的 env 门。**它的输出天然不是证据，且必须保证不成为证据**：
  1. **绝不** 把结果喂 `scripts/run_supervisor_seal.py` / `supervisor_seal()`（唯一 durable CERTIFIED mint，CLAUDE.md 认证三权分立）。
  2. **绝不** 写 `data/checkpoints/`、`data/solutions/`（认证面路径、且禁提交）——harness 的 `CutManager(checkpoint_dir=...)` 与任何输出都指向 scratchpad 或 `data/telemetry/`。
  3. **绝不** 记入仓库外的 clean-review 计数（P1.2/升格门，`PROJECT_LOCK.md:130-137`）。
- harness 不调 `publish_verified_certified_delivery_surface`、不调 seal，`run_with_status()` 本身无 mint 能力，故只要输出隔离，升格路径不存在。**升格仍是 owner 显式决定**（M4 card `:95`，三前置只剩这条）。

### M1「同进程连续 model 内存滞留」对长实测的影响

- CP-SAT 约束加了不能删（`benders_loop.py:940-945` 预算闸的整个理由）；attach 在同一 master 上累加，预算 2000 封顶单 master 的增长。
- 但 **跨 candidate 在同一进程复用**会踩 M1 verdict 的「连续 model 内存滞留」暴露面（M4 card `:101`「生产 worker model 生命周期核查（M1 内存滞留暴露面）」列为 M5 待办）。长 A/B 跑多个 candidate 若都在一个 Python 进程里，RAM 单调涨、可能 OOM，且内存压力会污染 wall-clock 测量。
- **建议**：每个 (candidate, attach 开/关) cell 用 **独立子进程**（对齐生产 `parallel_processes` 用 subprocess 的做法），跑完即回收；每 candidate fresh session+master。既隔离 M1 滞留，又让 wall-clock 干净。CLAUDE.md「原生进程隔离」也支持这个方向。

---

## 附：关键文件/行号索引

- 总开关 env + unsafe map + 预算常量：`src/search/benders_loop.py:936, 946, 949`
- attach 使能判定：`benders_loop.py:7529-7537`
- unsafe map 检查（certified-only）：`benders_loop.py:1349-1420`（调用点 `:8071`，fail-closed `:8072-8098`）
- blocker solve_mode 短路：`benders_loop.py:2041-2042`
- exploratory 循环（无 binding/routing/attach）：`benders_loop.py:4724-4818`
- certified 循环：`benders_loop.py:4820+`；binding/routing：`:5812`
- attach 触发（binding）：`benders_loop.py:6055-6070`；（routing）：`:7175-7193`
- attach 主体 + telemetry 写入：`benders_loop.py:7734-7898`（`attach_last` `:7891`、预算变体 `:7783`）
- step_8 master 翻译（4 族接线 + 未接线 fail-closed）：`src/cuts/lifecycle.py:1162-1402`
- 统一计数器自增（F1）：`src/models/exact_coordinate_master.py:7218-7220`
- master add_*_cut 委托（fail-closed）：`src/models/master_model.py:12095-12197`
- 直调 harness 样板：`src/tests/test_cut_framework_attach_wiring.py:135-179, 205-249`
- 频率 probe：`src/runtime/subproblem_invocation_counter.py:29-32, 87-103`
- exploratory→certified 降级（铁律）：`src/search/outer_search.py:2892-2909`
- main.py mode/参数：`main.py:199-262, 268`
- M5 待办与 soundness 背景：`cc_memory_vnext/cards/p1-3-m4-ladder-landed.md:89, 97-104`
