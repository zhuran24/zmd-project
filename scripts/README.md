# scripts/ 目录入口分类

当前 tracked source inventory（2026-06-06，不含 `__pycache__`）：423 个 `.py` + 13 个 `.ps1` + 12 个 `.sh` + 2 个 `.md` + 1 个 `.fzn` + 1 个 `.mjs` = 452 个文件。大部分仍是 Phase 3B / cut-family / delivery 的 artifact 生成器、审计器、spike 工具和历史 helper；不是每个脚本都是日常入口。

这份 README 列**真正的入口点**, 你日常会跑的脚本. 完整 Phase 3B 列表见 `docs/phase3b_module_index.md`.

脚本默认分五类读：

| 类别 | 怎么看 |
|---|---|
| 当前推荐入口 | campaign wrapper、preflight、delivery e2e、vendor refresh |
| Gate / 审计 | `preflight_gate.py`、`production_readiness_gate.py`、`audit_*` |
| Artifact 生成器 | `build_*`，通常输出 `.artifacts/` 或 delivery bundle |
| Spike / profiling | `*_poc.py`、`*_spike_*`、`profile_*`，默认历史参考 |
| Future scope / historical | larger-base、outer-deployment、早期 Phase 3B tuning 辅助面 |

---

## 启 / 停 / 监控 168h campaign (Production Critical)

| 脚本 | 用途 |
|---|---|
| `run_campaign_p2_workers1.sh` | **推荐** wrapper 启 168h: `-p 2 + workers=1` + community hint + jemalloc + P-core taskset |
| `run_campaign_workers2.sh` | Fallback wrapper: `workers=2` (RAM 中等) |
| `run_campaign_linux.sh` | 底层 wrapper, 上面两个都调它. jemalloc LD_PRELOAD + cpuset pinning + THP sanity |
| `campaign_watchdog.sh` | 后台 daemon, 监控 main.py 崩溃自动重启 (singleton lock via flock) |
| `stop_campaign.sh` | 停 campaign + 子进程树, 不动 Claude 本身. 见 CLAUDE.md "停 168h campaign" 段 |
| `temp_logger.sh` | 后台温度 logger, 168h 启动时启 (CSV 输出到 data/telemetry/) |

启 168h 标准流程: 见 `CLAUDE.md` "Linux campaign 启动 wrapper" 段.

---

## Pre-commit / Pre-campaign Gates (Production Critical)

| 脚本 | 何时跑 |
|---|---|
| `preflight_gate.py` | **pre-commit hook 自动跑**. 8 层守卫 (hash / 路径 / AI safety / exact-exploratory 隔离 / mypy / ruff / pytest). 见 `docs/env_variable_index.md` E/F 组 |
| `production_readiness_gate.py` | **启 168h 前手动跑**. 9 项 hard check (pacman freeze / venv / OOM headroom / THP / jemalloc / kernel) |
| `pacman_campaign_freeze.sh` | 冻结 / 解冻 pacman 关键包 (campaign 期间防 -Syu 升级) |

---

## Hint / 蓝图工具 (D step 2 land 2026-05-16)

| 脚本 | 用途 |
|---|---|
| `blueprint_to_master_hint.py` | IP v2 blueprint JSON → `Dict[instance_id, pose_idx]` master hint |
| `hint_coverage_report.py` | 审计 hint coverage % + pose_idx 范围有效性 |
| `analyze_hint_vs_baseline.py` | trial 跑完对比 baseline state vs hint state (UNKNOWN→FEASIBLE 等升级信号) |

---

## IP v2 蓝图工具 (LP + 静态验证)

| 脚本 | 用途 |
|---|---|
| `ip_v2_blueprint_validator.py` | IP v2 蓝图静态校验 (传送带类型 + 端口连通性) |
| `ip_v2_blueprint_steady_state_lp.py` | IP v2 蓝图稳态产量 LP solver (验证物料平衡) |
| `annotate_blueprint_issues.py` | (⚠️ 未进 git — 仅早期 Linux host 工作树有, 当前 clone 缺此脚本, 需用时重写) 把 validator 发现的 issue 标在 FINAL.jpg 上 (可视化) |

---

## Vendor refresh (mechanical sync, 不自动改 canonical_rules)

| 脚本 | 用途 |
|---|---|
| `refresh_endfield_calc_snapshot.py` | 从 JamboChen/endfield-calc 上游同步 items.ts / recipes.ts / facilities.ts |
| `refresh_industrial_planner_bases.py` | 从 hsyhhssyy/IndustrialPlanner v2 同步 7 个 base 定义 |

详见 `CLAUDE.md` "Maintenance scripts (runbook)" 段.

---

## Industrial Planner Delivery (Phase 3A artifact 生成)

| 脚本 | 用途 |
|---|---|
| `build_industrial_planner_single_base_delivery_release.py` | 生成 IP v3 repo delivery release bundle |
| `build_industrial_planner_full_demand_fixture.py` | full demand fixture 生成 |
| `build_industrial_planner_single_base_delivery_frontdoor.py` | frontdoor / browse-first 主页生成 |
| `audit_industrial_planner_checked_artifact_suite.py` | 审计 checked artifact |
| `audit_industrial_planner_full_demand_deployment_matrix.py` | 审计 full demand deployment matrix |
| `audit_industrial_planner_full_demand_support_suite.py` | 审计完整支持套件 |
| `run_industrial_planner_single_base_e2e.py` | E2E 端到端验证流程 |

Phase 3A release 完后这些**不再频繁跑**, 但 vendor refresh 后或 surface 修改时要 re-run.

---

## CachyOS / Linux 环境配置 (一次性)

| 脚本 | 用途 |
|---|---|
| `cachyos_setup.sh` | CachyOS 装 Python 3.13 + venv + jemalloc/tcmalloc/mimalloc + THP + ortools sanity |

详见 `CLAUDE.md` "Linux migration setup" 段.

---

## Spike / Profiling / 调研工具

| 脚本 | 用途 |
|---|---|
| `anchor_slicing_ram_poc.py` | RAM POC (验证 anchor slicing 不解 30 GB 大头, memory 记录) |
| `profile_phase3b_forced_anchor_master.py` | forced anchor master 性能分析 |
| `run_phase3b_local_tuning_profile.py` | 本地 tuning profiling + metrics |
| `run_phase3b_checkpoint_free_overlay_timing_probe.py` | overlay timing probe |
| `p1_24_cpsat_param_sweep.sh` | P1 #24 CP-SAT 参数 sweep |
| `analyze_subproblem_repeat_rate.py` | P1 #12 spike subproblem repeat rate 分析 |
| `mus_extraction_poc.py` | CPMpy MUS 提取 PoC |

这些是 spike 一次性工具, 跑完不再用.

---

## Phase 3B Audit/Probe 生成器 (252 个 build_phase3b_*)

详见 `docs/phase3b_module_index.md`. **不是入口**, 是 audit artifact 生成器, 跟 `src/search/phase3b_*` 一对一对应.

跑一个 `build_phase3b_X.py` = 生成 `.artifacts/.../X.json`, 然后 `test_phase3b_X.py` 验证 artifact.

---

## 临时 / 历史 / 不再 active

| 脚本 | 状态 |
|---|---|
| `pumpkin_poc/` 子目录 | Pumpkin solver PoC, ephemeral, `.gitignore` 已忽略其产物 |
| 各种 `*_spike_*` / `*_poc.py` | 历史 spike 一次性, 留作 reference 不删 |

---

## 怎么找一个具体脚本

```bash
# 按名字
ls scripts/ | grep <keyword>

# 按 vintage (最新改的)
ls -lt scripts/*.py | head -10

# 按 import (谁调它)
grep -rn "from scripts.<name>" src/ scripts/
```

---

## Memory 链

- [[reference_cachyos_paste_and_nm]] — CachyOS 环境
- [[project_d_step2_hint_landed]] — D step 2 hint 链
- [[project_endfield_solver]] — 项目总览
