# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目是什么

《明日方舟：终末地》70×70 基地（266 个 mandatory 设施）的 **certified-exact 最大空矩形求解器**，目标 `max_lex(area, min_side)`。Python 3.13，CP-SAT（OR-Tools）。入口 `main.py`（默认 `--mode certified_exact`）。

## 权威顺序（先读这段）

1. **`PROJECT_LOCK.md`** 是 release 边界最高权威（`F-*`/`PCR-*`/`CUT-*` fail-closed 条款）；与任何其他文档/记忆冲突时以它为准。
2. **`README.md`** 是完整的项目 handoff 史料（六章决策记录：架构、认证链、PR1/PR2 saga、坑、开放问题）。它是记录不是命令，凡涉及证明/认证的断言先对源码自查。
3. `NAV_MAP.md` 是调用链导航（注意：只列了主链约 7 个 `src/search` 模块，实际认证链还依赖 `certified_artifact_contract.py`、`candidate_proof_replay.py`、`pr2_l0_micro_verifier_core.py`、`pr2_l0_true_verifier_child.py`、`exact_parallel_scheduler.py` 等十余个未列出模块）。
4. **`docs/项目说明/00_master_roadmap.md`**（2026-07-05 立）是全项目工作线的**总图 + 排期快照 + owner 拍板台账**——问"接下来做什么/某条线排在哪/哪些事等 owner 定"先看它。它不是状态权威（release 边界仍以 1 为准，当前实现状态以 `06_current_status` + `soundness_gap_roadmap` 为准）。

**⚠ 本仓库是交付副本，git 历史被重建过**：README 里引用的所有 commit hash（`b35e5f9`、`9bbb3a6`、`099f5a3`…）在本仓库 `git cat-file` 均不可解析——它们是原机器的历史，只能当叙事线索，不能 `git show`。本仓库无 remote。分支：`main`、`topology-opt`（S0-S3 diagnostic 模块已进 main 历史，是 main 祖先；生产接线未做）。原 `pr2-5-domain-frontier-gate`（close-kernel 硬化线）已于 `6e06922` 合入 main（round-19/20 全吸收）、分支指针已删。核对 HEAD 以实测为准，别死认文档里记的 hash。

## 常用命令

```powershell
# 门禁（最重要的本地/CI gate；从仓库根跑）
python scripts/preflight_gate.py              # staged 变更范围
python scripts/preflight_gate.py --full       # 全量（mypy/ruff/pytest，但仍跳过 @slow）
python scripts/preflight_gate.py --slow-tests # 独立慢 soundness lane（串行、长超时、~13min）
python scripts/preflight_gate.py --ci --base-ref origin/main   # CI diff 模式

# 两个结构 checker（注意：均无 argparse，传 --help 也会直接跑完整检查）
python scripts/check_p1_2_proof_obligations.py        # 通过输出: 15 obligations anchored; 65 proof-bearing sink files sealed
python scripts/check_strong_status_write_allowlist.py # 通过输出: 65 AST nodes, 83 allowlist entries

# 单跑一个测试（固定顺序 + 独立 basetemp，避免并发互踩）
python -m pytest -p no:randomly --basetemp=.pytest_tmp/one src/tests/test_exact_contract.py::test_name -q

# 开发期 advisory 测试选择器（codegraph affected 算受影响闭包；碰锁面/checker/frozen 工件一律 exit 2 建议跑全量；不进 CI 硬门）
python scripts/select_tests_for_paths.py <改动文件...>   # 或 --git-diff

# 求解（正常链终点是 CANDIDATE_PROPOSED，不会产出 CERTIFIED）
python main.py                                # 默认 certified_exact；--campaign-hours >= 24 触发 production gate
# 生产跑走 wrapper：scripts/run_campaign_linux.sh（Linux）/ scripts/run_prod_*.ps1（Windows）
# supervisor seal 生产入口是独立命令 scripts/run_supervisor_seal.py（从已提交 proposal marker 驱动，不由 main.py 顺手执行）

# 外部大工件（candidate_placements.json，45,774,305 字节，SHA256 a914ba63...；45,773,799/adcc 是拐角修复前 superseded/hash-incompatible 旧版；lightweight checkout 可能缺失）
python scripts/check_external_artifacts.py --require candidate_placements
python scripts/restore_external_artifacts.py candidate_placements --source <file> --force
```

### 命令坑（都被实测坐实过）

- **preflight 退出码只有 0/1**。docstring 和旧文档声称 "exit 2 = pass with warnings"，代码里根本没有返回 2 的分支（`GateResult.exit_code`，`scripts/preflight_gate.py:117-121`）。
- **`--full` ≠ 全部测试**：仍带 `-m "not slow"`。改认证核心（producer/seal/publish/checker）后必须单独跑 `--slow-tests`，否则慢 soundness 测试是盲区。
- `@slow` 不是散落的装饰器，而是**集中登记**在 `src/tests/conftest.py` 的 `_SLOW_TEST_NODEIDS` 集合（2026-07-04 按实测全量对时后 19 条，只留真慢的）。新写 ≥8s 的慢测试必须去 conftest 登记，否则会被 fast lane 意外跑到；retune 用无并发串行的 `-m slow --durations` 全量扫描，别在有并发 pytest 时测时长（会挤出假红/虚高）。
- `pytest.ini` 的全局 `--basetemp=.pytest_tmp` 意味着**并发跑 pytest 会互删临时目录**——多窗口/并发时各自覆盖 `--basetemp` 为独立子目录。
- `requirements.txt` 声明了 `pytest-randomly` 但当前环境未必装了它；想稳定复现顺序永远显式加 `-p no:randomly`。
- `candidate_placements.json` 缺失时部分测试（`test_binding.py`、`test_routing.py` 的一些用例）会在 fixture 阶段抛 `FileNotFoundError` 硬失败而非优雅 skip——排查"一批测试莫名 error"先查这个工件在不在。
- `main.py` 的 `--exploratory` 会**覆盖** `--mode`；`--skip-readiness-gate` 只跳启动门、不跳 freeze monitor。
- Windows 生产 wrapper（`run_prod_*.ps1`）**不会**像 Linux wrapper 那样自动注入 `--resume-campaign`，要显式传 `-ResumeCampaign`，否则重跑丢进度。
- `scripts/package_review_snapshot.py` 打包的是 **committed git tree**，不含未提交的脏改动。
- `production_readiness_gate.py` 是 Linux（CachyOS/pacman）导向的，Windows 上直接跑会 BLOCK，且它会 `mkdir .artifacts`（非纯只读）。

## 大图架构

### 1. 铁律：`certified_exact` 与 `exploratory` 两条路径严格隔离

只有 `certified_exact` 能产出证明材料；exploratory 的 caps/hints/probes/sidecars **永不能升格为证据**。这条铁律在代码里是硬的：exploratory 路径若意外命中 `RUN_STATUS_CERTIFIED`，会在 `src/search/outer_search.py:2892-2909` 被静默降级为 `RUN_STATUS_UNPROVEN`。`min_side >= 6` 是候选 admissibility 规则（权威在 `rules/canonical_rules.json`），不是目标 tie-break；exact 模式**没有** "50 电线杆 + 10 协议箱" 硬上限（那是 exploratory-only 引导值）。

### 2. 求解管线（三条执行路径收敛到同一核心）

```
main.py → run_solve() → outer_search.run_outer_search()
   串行 / 并行(exact_parallel_scheduler) / exploratory 三条路径
   → 全部收敛到 benders_loop.run_benders_for_ghost_rect()
      ├ exact_coordinate_master.py   默认 certified 坐标 master（CP-SAT）
      ├ pose_bool_exact_master.py    env 门控备选，被 benders_loop 的 env 守卫挡在 certified 路径外
      ├ binding_subproblem.py        certified gate：端口绑定 + 精确计数
      ├ routing_subproblem.py        certified gate：连通性（不是吞吐！）——CP-SAT FEASIBLE 后
      │                              还要过 _validate_selected_route_connectivity 全局复验
      ├ flow_subproblem.py           GLOP 连续 LP，diagnostic-only，其 INFEASIBLE 永不产生 exact-safe cut
      └ independent_infeasibility_reverifier.py  whole-layout nogood 落 cut 前的独立复验（I1）
```

CERTIFIED 证明的是 6 个谓词（ghost 内无设施 / 两两不重叠 / placement_rule / 端口精确计数 / 路由连通 / 供电覆盖）+ lex 最优性；**吞吐/带宽/离散容量流明确 OUT-OF-SCOPE**（`PROJECT_LOCK.md` §1A B 块）。`src/cuts/` 的 cut lifecycle **部分接通、certified 下禁用**（截至 2026-07-10）：`step_8_apply_to_master` 已接 F1/F5/F6/F7（其余族 fallback `NotImplementedError`）；`benders_loop` 的 direct attach（`_maybe_attach_framework_cuts`）由 `EXACT_CUT_FRAMEWORK_ATTACH` 门控且在 certified unsafe-map 里禁用；F8 已从 `CutFamily` 退役。

### 3. 认证三权分立（需跨 4-6 个文件才能看清）

```
producer（outer_search.py）        只能提交 CANDIDATE_PROPOSED + proposal 材料
  → scripts/run_supervisor_seal.py（生产入口，独立命令，从 marker 驱动）
  → ExactCampaign.supervisor_seal()（exact_campaign.py:3566）唯一 durable CERTIFIED mint
       委托 pr2_l0_micro_verifier_core.run_l0_supervisor_seal()
       → 隔离子进程（-I -S -B -X pycache_prefix）跑 pr2_l0_true_verifier_child.verify()
  → publish_verified_certified_delivery_surface()（certified_surface.py）唯一公开发布器
       stage→commit→verify→rollback 四段事务；resolve_p1_2_publish_open_gate() 在链上被查 3 次
```

反绕过守卫是硬编码的：`mark_campaign_stopped(status="CERTIFIED")` 直接 raise；`save()` 检测三处 unsupervised CERTIFIED claim 并 raise（`exact_campaign.py:2564-2579, 3658-3661`）。**`supervisor_seal()` 的生产入口是 `scripts/run_supervisor_seal.py`（独立命令，从 marker 驱动）；跑完 `main.py` 仍只会得到 `CANDIDATE_PROPOSED`**——这是刻意留开的操作链缺口（PR2 #7 "最后通电"），且 #7 通电已于 2026-07-04 落地；不是 bug，也不是 P1.2 closure。

### 4. P1.2 手动门（已关，2026-07-07）：任何绿灯仍不等于"owner 关门动作"

release 由 owner 手动门管辖：`data/review_gates/phase_1_2_spike_close.json`。**P1.2 已于 2026-07-07 由 owner 显式 `owner_manual_decision` 关闭**（`status: "closed_manual_owner_decision"`、`next_phase_entry.allowed=true`），当前阶段为 **P1.3**（生产 master/cut 集成，`step_8_apply_to_master` 待做）。纪律不变：clean-review 计数**保存在仓库外**、仓库刻意不推导；checker PASS、preflight 绿、测试全过、seal 方法存在——都不得改写为 owner 关门动作或 release closure（`PROJECT_LOCK.md:130-137`）——本次关闭是 owner 真实手动输入，不是自动推导。同理 close-kernel 结构门只证"登记结构未漂移"，不证明求解数学正确。

### 5. Frozen artifacts 与 freeze-ritual

proof 输入被字节级 hash 钉死（`scripts/preflight_gate.py` 的 `FROZEN_ARTIFACTS` + `EXTERNAL_FROZEN_ARTIFACTS`；runtime 侧 `certified_artifact_contract.py` 把路径/sha/size 写死在源码常量里）：`rules/canonical_rules.json`、`rules/preprocess_plan.json`（additive-only：出现顶层 `recipes`/`production_targets`/`commodity_roles` 即 fail-closed，`src/interchange/preprocess_context.py`）、`data/preprocessed/mandatory_exact_instances.json`（266 实例）、`generic_io_requirements.json`、`candidate_placements.json`（45,774,305 字节，SHA256 `a914ba6348544b7ef44d0834629c6dcf90f39fa5564e0cd4c50af6af550c444b`；拐角修复前的 45,773,799 字节 / SHA256 `adcc2a6e8a1daaa9dea6cae68883301ad07ce123fa286b55dcbe79ca2f34bec0` 版本 superseded、hash-incompatible；旧的 53,594,995 字节版本必须被 `artifact_hash_mismatch` 拒绝，**别"好心"更新 expected hash**）。

**改任何被钉文件 = freeze-ritual**：更新 pinned hash → 重生成依赖产物 → 重跑 gate。改 close-kernel sealed 文件还要走完整 reseal 连锁（V99 floor 常量、obligations JSON、strong-status allowlist、checker 自钉**最后**算）。**reseal 铁律**：pin sha 按 LF 字节算（`git show HEAD:<file> | sha256`），绝不用 Python `write_text`/`json.dump` 直接写 tracked 文件（Windows 会写 CRLF，`.gitattributes` 强制 LF → 本地绿 CI 挂）；提交 pathspec 必须覆盖 reseal 全集。

### 6. Strict JSON 与 env 白名单

- 所有 proof 路径 JSON 解析走 `src/io/strict_json.py`（拒绝重复 key、NaN/Infinity、`1e400` 溢出）。**当前公开函数名是 `loads_strict_json` / `load_strict_json` / `load_strict_json_exact_decimal`**（README 史料里的 `load_strict_json_file`/`load_strict_json_path` 是旧名，源码中已不存在）。
- `certified_exact` 下 `EXACT_*` 环境变量是**闭合白名单 deny-unknown**（`src/search/benders_loop.py:1332-1364`）：未知的 `EXACT_*` 名字*仅凭存在*就 fail-closed。新增 env knob 必须同时更新 allowlist/lock/tests。worker 数优先级：stage 专属 env > `EXACT_CP_SAT_WORKERS` > 内置默认；值非正整数直接抛异常，不静默回退。
- `EXACT_POWER_PLACEMENT_SUBPROBLEM=1` 被至少四层机制挡在 certified/生产路径外（master fail-closed、benders env 守卫、Linux wrapper、readiness gate），exploratory/取证专用。

### 7. 禁提交路径

绝不提交生成的 proof 输出：`data/checkpoints/`、`data/blueprints/optimal_blueprint.json`、`data/solutions/final_solution.json`、`data/solutions/certified_delivery_manifest.json`。注意 `data/solutions/` **不是整目录忽略**（.gitignore 精确路径，其余审计文件正常跟踪）。`src/ai_accel` 不得触碰 proof 路径（preflight 扫描强制）。

### 8. CI（`.github/workflows/`）

- `project_foundation.yml`：主 gate（`preflight_gate.py --ci`）+ 独立 slow-soundness job（`--slow-tests`，Linux，~13min，会先恢复 candidate_placements）。
- `industrial_planner_checked_artifacts.yml` / `industrial_planner_single_base_delivery_surfaces.yml`：交付面回归（后者的 alignment audit 标了 `continue-on-error: true`，不是硬门）。

## 读代码的工具约定

- **符号/调用链/影响面定位先用 CodeGraph，别默认全仓 grep**（省大量 token）：CLI `codegraph explore|callers|callees|impact|search`，或 MCP 工具（本项目已注册 `codegraph serve --mcp`）。索引是可重生 cache（`.codegraph/`，git-ignored；`codegraph status .` 查状态、`codegraph init .` 重建，全仓 ~20s）。它**不是权威**：proof 敏感的结论必须回到源码 + `PROJECT_LOCK.md` + 目标测试核实；feature 分支上可能 stale（`codegraph sync .`）。
- 内容/文本搜索用 Grep；按文件名找文件用 `es`（Everything CLI）。

## 记忆系统（本机协作基建，随交付副本迁入）

- `cc_memory/`（SQLite，pull 型全量历史库）：`python cc_memory/mem.py boot|search|read <id> --body|impact|add-entry|set-fact|finalize`。改记忆前先 `impact`；改完 `finalize` 收口；`exports/MEMORY.md` 是生成视图别手改。memory.db 有意进 git。
- `cc_memory_vnext/`（push 型主动卡片层）：`python cc_memory_vnext/zmem.py verify|build-index|context|eval`。卡片 `cards/*.md` 是真相源，`.index/` 是可重建缓存。
- 两层的 hook 接线在 `.claude/settings.local.json`（SessionStart/UserPromptSubmit/PostToolUse/Stop）。
