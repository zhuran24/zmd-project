---
name: phase3b-progress
description: "(SUPERSEDED 历史快照) Phase 3B tuning 范式 S0-S18 执行追踪. ⚠️ 该范式早被取代 (→B1→cut-family LBBD→当前 P1.3A), 非项目现状; 现状权威源见 [[windows-ninth-review-pending]]. 保留作历史, 别当 live 恢复源"
type: project
originSessionId: 732c4476-d6e3-489a-9d77-f2a9ed5b0e92
---
> ⚠️ **SUPERSEDED 历史快照 (2026-06-02 标注)**: 本文件是 **2026-05-06 起 Phase 3B tuning 范式**的执行追踪, 那套范式**早已被取代** (27-lever 全死 → B1 pose-bool → cut-family LBBD → **当前 P1.3A**)。下面"## 当前阶段：Accumulation Loop"是**当时**的状态, **不是项目现状** —— 别据此误判项目仍在 Phase 3B。**项目现状权威源 = [[windows-ninth-review-pending]]** (per [[memory-currency-protocol]] §2/§3: 现状只信单一 living 源)。本文件保留作历史。

## 当前阶段：Accumulation Loop（S8→S9 过渡）  *(← 历史, 见上方 superseded banner)*

**计划文档：** `docs/phase3b_repair5_acceleration_tuning_ai_plan.md`

### 已完成
- 项目从 Codex 迁移到 Claude Code（2026-05-06）
- CLAUDE.md 全局 + 项目级（2026-05-06）
- Preflight gate 脚本 + pre-commit hook（2026-05-06）
- 审查策略树存入 memory（2026-05-06）
- S0: Repair5 clean baseline 验证 — 91 focused tests passed, preflight no-write OK, dry-run OK
- S1: 环境冻结 — i9-13900KS HT-off 24T, DDR5-7600 48GB, Python 3.13.13, ortools 9.15.6755
- S2: Telemetry scaffold 验证 — src/runtime/ 模块全部可用（从Codex继承）
- S3: Baseline reproduction — 两个5分钟baseline run完成，scorecard生成
  - Prod workers (4/4/4/4): 27.58 GiB RSS, 53% CPU, 2 candidates/5min
  - Default workers (8/8/4/8): 23.28 GiB RSS, 68% CPU, 3 candidates/5min
  - 两组都有1次失败（MemoryError / worker crash 0xC0000409）
- S5: Config matrix 完成（2026-05-07）— 7个配置profile测试完毕
  - 最佳新配置: 2x12 (53.2% CPU利用率, 39.24 GiB RSS)
  - 崩溃边界: 1x16 触发 CP-SAT stack buffer overrun — 硬限制
  - 所有配置 private bytes 稳定在 ~50 GiB — 说明CP-SAT有虚拟内存提交上限
  - Baseline built-in defaults (8/8/4/8) 仍然CPU利用率最高 (68.1%) — 需要研究原因
  - Page file 从 32GB 调到 64GB 后所有配置稳定运行
- 看门狗系统上线（2026-05-07）
  - `scripts/loop_heartbeat.ps1` — 15分钟超时自动恢复
  - `scripts/update_loop_heartbeat.py` — 心跳更新器
  - OSError resilience 修复 — telemetry采样器在page file压力下不再崩溃

### 关键发现
- 每个候选评估代价极高：5分钟只能跑2-3个候选
- Master placement 初始迭代返回 UNKNOWN — 对70x70问题规模正常
- 48GB RAM 够用但余量不大（peak 39.96 GiB for 4x8 = 83%）
- Default workers (8/8/4/8) CPU利用率更高但RSS更低 — 值得进一步研究
- 16 workers per CP-SAT process 是硬崩溃边界（0xC0000409）
- 所有配置 private bytes ~50 GiB，与 worker 数无关 — 虚拟内存提交有上限

- S6: Stage-specific worker matrix 完成（2026-05-07）— 8个W0-W7 profile
  - W6 (3x 8/6/2/6) 最佳CPU利用率 77.3%，是W0 baseline的2.6倍
  - Master workers是主导因素：8 workers consistently beats 4 or 6
  - Binding可安全降到2 workers（轻量子问题）
  - 3进程优于4进程——更少IPC开销
  - 但W6 private bytes 83 GiB，需要注意page file压力
  - Top 3候选：W6 (3x 8/6/2/6), W7 (2x 12/8/2/8), W4 (4x 8/6/2/6)

### Worker Crash Resilience + Memory Guardian（2026-05-07）
- `exact_parallel_scheduler.py` 添加了两层防护：
  1. 波间刷新：每个wave成功后，关闭旧worker，启动全新进程（防C++状态腐蚀）
  2. 波内重生：worker崩溃时，drain已有结果→重启所有workers→重新派发未完成task（最多2次）
- `run_phase3b_local_tuning_profile.py` 添加内存看门狗：
  - 系统可用 RAM < 4 GiB 时自动杀 solver 进程，保护 Claude Desktop 不被 OOM
  - 修复 `env_overrides` 在 no_execute 时的 UnboundLocalError
- 1990 tests passed，6 tuning harness tests 全部通过

### S8 Medium Confirmation 结果（2026-05-07）
- **核心发现：48 GiB RAM 是硬上限**
  - 所有配置（2/3/4进程）在 30min 运行中都达到 ~45 GiB RSS
  - CP-SAT 内存增长是问题根源，与 worker 配置无关
  - Built-in (8/8/4/8) 吞吐最高：3 candidates/9.6min
  - W0 (4/4/4/4) 最稳定但最慢：2 candidates/22min
  - W7 (2x12/8/2/8) 资源不足直接 WinError 1450
- S8 结果表：
  | W0 4x4/4/4/4 | 22min | 2 cand | 0xC0000409 | 45.6G |
  | Built-in 4x8/8/4/8 | 9.6min | 3 cand | MemoryError | 44.6G |
  | W6 3x8/6/2/6 | 18min | 2 cand | 0xC0000409 | 45.2G |
  | W7 2x12/8/2/8 | 16min | 0 cand | WinError 1450 | 45.5G |

### Accumulation Loop（2026-05-07）
- **战略决策**：S8 证明 48GiB RAM 是所有配置共同天花板，Lane B（确定性调优）在此硬件上到顶
- 用户指出"数据量不代表性能"——S8 样本量太少（2-3 candidates/config）无法做有效对比
- **转为双目标积累模式**：一边跑 campaign 积累进度，一边收集 AI 训练数据
- 配置选择：built-in defaults (8/8/4/8)（无确定性证据证明其"最优"，但最简单）
- 新增 `accumulation_builtin_24h` profile（24h campaign 预算）
- 新增 `scripts/run_accumulation_loop.ps1`（crash-resume 循环脚本）
- 修复 `exact_campaign.py`：resume 时允许升级 campaign_hours + 清除 time_budget_exhausted 停止标记
- 安全限制从 1h 放宽到 48h（168h 硬限制不动）

### S9 准备工作（2026-05-07 进行中）
- **关键认识：在 Claude Code 里跑 solver 行不通** — Claude Code 自身占 ~10-15GiB 内存，
  solver 启动 30秒就被 memory guardian 杀。积累循环必须独立 PowerShell 窗口跑。
- **新增 `scripts/refresh_ai_dataset_from_campaign.py`** — 从 campaign state checkpoint
  直接提取 AI 训练数据（geometry/frontier_metrics/precheck/solver_metrics/labels）。
  当前 10 个样本（3 INFEASIBLE precheck-eliminated + 7 RUNNING）。
- **AI 安全合同澄清**：AI 只改变候选**跑的顺序**，不改变**跑不跑**。
  每个候选最终都必须由 solver 跑过并出数学结论（precheck 算 solver 的一部分，不算 AI）。
- **`replay_scheduler.py` 已存在于 `src/ai_accel/`**，待集成
- **待办**：等用户独立跑积累循环积累足够样本后（建议 30+ 候选），开始训练 candidate ranker

### 当前状态（2026-05-07 晚）
- Campaign state: 10 候选触达（3 INFEASIBLE: 70x11/70x12/70x19, 7 RUNNING: 42x32/56x24/58x23/61x22/64x21/67x20/69x19）
- 用户考虑切到 Claude Code CLI 减少内存占用（CLI 比桌面端 Electron 轻几百MB-1GiB）
- CLI 和桌面端共享 `~/.claude/`，会话历史互通，memory 互通

### 下一步
- 用户独立跑 `.\scripts\run_accumulation_loop.ps1` 积累候选数据
- 数据够了（30+ 候选）后训练 candidate ranker（S9 核心）
- S7: Priority/Affinity（低优先级，可选）

### 关键文件
- Baseline scorecard: `.artifacts/phase3b_accel_tuning/00_baseline/baseline_scorecard.json`
- S5 scoreboard: `.artifacts/phase3b_accel_tuning/01_config_matrix/s5_matrix_scoreboard.json`
- S6 scoreboard: `.artifacts/phase3b_accel_tuning/02_stage_workers/s6_stage_worker_scoreboard.json`
- Hardware profile: `.artifacts/phase3b_accel_tuning/00_baseline/hardware_profile.json`
- Tuning runner: `scripts/run_phase3b_local_tuning_profile.py`（S5 matrix + S6 stage-specific profiles）
- AI dataset (legacy v0): `.artifacts/phase3b_ai_accel_20260429/01_feature_dataset/`（3 samples）
- AI dataset (latest, from campaign): `.artifacts/phase3b_ai_dataset_latest/`（10 samples，会随 accumulation 增长）
- Accumulation loop: `scripts/run_accumulation_loop.ps1` + `accumulation_builtin_24h` profile
- Dataset refresh: `scripts/refresh_ai_dataset_from_campaign.py`
- Watchdog: `scripts/loop_heartbeat.ps1` + `scripts/update_loop_heartbeat.py`

**Why:** 用户要求全自动推进，每天早上做一次 /ultrareview
**How to apply:** 每完成一个阶段更新此文件，便于上下文压缩后恢复
