# CLAUDE.md — Endfield IndustrialPlanner Exact Solver

## Project Overview

70x70 grid exact maximum empty rectangle solver for Arknights: Endfield IndustrialPlanner.
Objective: `max_lex(area, min_side)` — maximize area first, then min-side.
266 mandatory facility instances, OR-Tools CP-SAT, Benders decomposition (master -> binding -> routing -> flow).

## Exactness Constitution (from PROJECT_LOCK.md)

- `certified_exact` and `exploratory` are **strictly separate paths**. Never mix them.
- Exact objective is `max_lex(area, min_side)`. `min_side >= 6` is admissibility, not tie-break.
- No hard `50 power poles + 10 storage boxes` cap in exact mode — that's exploratory-only.

## Forbidden Changes

- Reintroducing exploratory caps as exact-mode bounds
- Treating exploratory artifacts as certified proof
- Changing campaign/artifact/proof schemas without updating lock/spec/test together
- Rebinding globally pooled resources into per-line hard bindings without new proof basis
- Adding exterior-path requirement for the ghost rectangle

## Source of Truth

Certified path is grounded in:
- `rules/canonical_rules.json` (consolidated preprocess/recipe/target/commodity truth)
- `data/preprocessed/candidate_placements.json`
- `data/preprocessed/mandatory_exact_instances.json`
- `data/preprocessed/generic_io_requirements.json`

Everything under `src/adapters/`, `src/render/`, `data/exports/`, `data/examples/` is **postprocess-only** — never redefines solve schemas.

## Architecture

```
main.py                          # Entry point
src/search/outer_search.py       # Outer candidate loop + frontier
src/search/benders_loop.py       # Benders decomposition (LBBD)
src/models/master_model.py       # CP-SAT placement master
src/models/exact_coordinate_master.py  # Ghost rectangle enforcement
src/models/binding_subproblem.py # Port binding
src/models/routing_subproblem.py # Grid routing
src/models/flow_subproblem.py    # Multi-commodity flow diagnostic
src/search/exact_campaign.py     # Campaign persistence + resume
src/search/exact_parallel_scheduler.py  # Multi-process parallel waves
```

## Active Scope

- Single base: `valley4_protocol_core` 70x70 only
- Other bases (`valley4_infra_outpost`, `wuling_protocol_core`, etc.) are `future_scope`
- Outer-deployment subsystem is adapter-side `future_scope`

## Current Phase: 3B Optimization / Acceleration

- Phase 3A (delivery/productization): Complete, release `r20260416`
- Phase 3B (full-scale exact proof): In progress
- Acceleration plan: `docs/phase3b_repair5_acceleration_tuning_ai_plan.md`
- 4 lanes: A=safety/observability, B=deterministic tuning, C=AI sidecar, D=runtime diagnostics
- AI is shadow-only sidecar: no proof source, no formal pruning, no checkpoint writes

## AI Safety Contract

AI modules may ONLY:
- Suggest candidate ordering (order_only)
- Classify UNKNOWN/UNPROVEN results
- Explain tuning experiments
- Suggest CP-SAT hints (as hints, not constraints)

AI modules must NEVER:
- Delete candidates or declare infeasibility
- Write to `data/checkpoints/`, `data/solutions/`, `data/blueprints/`
- Modify certified proof source or campaign hash
- Change final preflight semantics
- Authorize final 168h production run

## Commands

```powershell
# Run solver (default certified_exact mode)
python main.py --campaign-hours 168.0 --parallel-processes 4

# Run tests
python -m pytest src/tests/ -q

# Single-base e2e workflow
python scripts/run_industrial_planner_single_base_e2e.py --run-dir .artifacts/industrial_planner_single_base_e2e

# Visualization only
python main.py --vis
```

## Maintenance scripts (runbook)

> **重要**：用户可能会问"上游更新了怎么办"——答案是这两条命令，不是手动复制文件。

```powershell
# Refresh JamboChen/endfield-calc vendored snapshot (recipes + items + facilities)
python scripts/refresh_endfield_calc_snapshot.py
# Optional: --dry-run / --commit <SHA>

# Refresh hsyhhssyy/IndustrialPlanner vendored BASES (7 base definitions)
python scripts/refresh_industrial_planner_bases.py
# Optional: --dry-run / --branch v2 / --commit <SHA>
```

Both scripts are mechanical sync only:
- Update `third_party_snapshots/.../SOURCE_METADATA.json` (version, commit, observed_counts, previous_*)
- Print a diff report (counts changed, new entities)
- **Do NOT touch** `canonical_rules.json` — extending the 17-recipe canonical projection is a PROJECT_LOCK gate, separate manual decision
- **Do NOT auto-edit** `BORROWED_COMPONENTS.md` / `CHANGELOG.md` / `FILE_STATUS.md` / specs — release-note phrasing stays editorial

Tests `src/tests/test_endfield_calc_typescript_snapshot.py` and `src/tests/test_industrial_planner_bases_snapshot.py` read `SOURCE_METADATA.json` for expected counts, so refresh runs do not require test edits.

### Linux migration setup (CachyOS target — switched from Fedora 2026-05-08)

```bash
# Phase 3C P2 #19 bring-up checklist after CachyOS install
bash scripts/cachyos_setup.sh             # dry-run, prints commands
bash scripts/cachyos_setup.sh --apply     # actually install/configure
```

Covers Python 3.13 + venv + requirements + jemalloc/tcmalloc/mimalloc
allocators + THP madvise check + cgroups v2 + zram check + ortools
sanity + cachyos-bore kernel verify + IgnorePkg recommendation for
168h campaign stability. Default mode is dry-run so user can review
each step before applying.

Why CachyOS not Fedora: Fedora 41-44 all fail to boot on user's ASUS
Z790 (BIOS memory fragmentation + GRUB 2.06 can't coalesce). CachyOS
ships **Limine** as default EFI bootloader (verified via repo config
`src/modules/bootloader/bootloader.conf` `efiBootLoader: "limine"`)
which bypasses the GRUB 2.06 issue at root with no user action
needed during install. Plus cachyos-bore kernel default brings
BORE/EEVDF scheduler +5-10% on top of base Linux migration's +15-35%.
Earlier `scripts/fedora_setup.sh` removed (recoverable from git
history if needed).

### 168h campaign 关键包冻结 (CachyOS 滚动稳定性)

```bash
# 168h campaign 启动前 freeze 关键包不被 pacman -Syu 升级
bash scripts/pacman_campaign_freeze.sh --enable

# 当前状态查询
bash scripts/pacman_campaign_freeze.sh --status

# campaign 结束后解冻让系统跟最新
bash scripts/pacman_campaign_freeze.sh --disable
```

锁的包：linux-cachyos*, glibc, python, jemalloc, gperftools。平时（非
campaign 期间）应保持 unfreeze。脚本通过在 `/etc/pacman.conf` 里加带
markers 的 `IgnorePkg` 行实现，可可逆 toggle。

### 168h campaign 启动前 readiness gate

```bash
python scripts/production_readiness_gate.py
```

启动 168h 大跑前手动跑这个，缺一项 hard blocker 就 BLOCK。检查项：
pacman freeze 已启用 (Linux only)、venv + ortools 可导入、preflight 86
守卫测试通过、kernel 是 cachyos-bore 变种、磁盘 ≥100 GiB free、git
working tree 干净、THP enabled、jemalloc 装且 LD_PRELOAD 配置、进程
cpu_affinity 限定 P-core。Exit code: 0=ready, 1=blocked。

跟 `pacman_campaign_freeze.sh --enable` 配套用：先 freeze → 再跑
readiness gate → 全 OK 才启动 campaign。

### Linux campaign 启动 wrapper (P1 #24 cache-aware pack)

```bash
# 把 P1 #24 前 3 件套（jemalloc LD_PRELOAD + P-core taskset + 利用系统 THP）
# 一并打包，对 main.py 的所有参数都透传
bash scripts/run_campaign_linux.sh --campaign-hours 168.0 --parallel-processes 4
bash scripts/run_campaign_linux.sh --vis
```

包了三件套（个体 ROI 经 P1 #24 audit `a2dfaa35dbefe2a3a` 修正）：
- jemalloc LD_PRELOAD: +5-10%（缓 ptmalloc 多线程 contention）
- taskset P-core 自动检测+pin: +2-5%（i9-13900KS cpu0-7 5.6GHz vs E-core 4.5GHz）
- THP `[always]`：CachyOS 系统级默认，wrapper 仅 sanity check 不动
- jemalloc + `PYTHONMALLOC=malloc`：让 Python 解释器自己的 pymalloc arena 也走 jemalloc（不然 jemalloc 只 hook C 层）→ 收益从 +5-10% 升到 +7-13%
- 合计 +15-22%（不是路线图原 claim 15-30% 因 stack-efficiency 折扣）

启动 168h campaign **必须**用这个 wrapper（直接 `python main.py` 会丢两件套
的收益）；readiness gate 9/9 项检查会自动 flag 漏配置。

### Community blueprint hint 注入 (D step 2, 2026-05-16 落地)

```bash
# 用用户手调 IP v2 blueprint 生成 master.solve hint JSON
python scripts/blueprint_to_master_hint.py
# 默认输入 /home/zhuran24/下载/BP-2026-05-13 08_35_36.blueprint(1).json
# 默认输出 data/hints/blueprint_2026_05_13_master_hint.json (225 entries)

# Trial 启动时 wrapper 自动注入 EXACT_COMMUNITY_BLUEPRINT_HINT_PATH
bash scripts/run_campaign_p2_workers1.sh --campaign-hours 24.0

# 跑完用 analyze 脚本对比 baseline vs hint (UNKNOWN→FEASIBLE 等升级信号)
python scripts/analyze_hint_vs_baseline.py BASELINE_STATE.json HINT_STATE.json
```

机制：
- `scripts/blueprint_to_master_hint.py` 读 IP v2 blueprint, 产 `Dict[instance_id, pose_idx]`
- rotation → (orientation, port_mode) 映射 hand-verified 10 sample 100% match
- `EXACT_COMMUNITY_BLUEPRINT_HINT_PATH` env 让 `benders_loop._run_certified_exact` 在每个 candidate 初始 greedy hint 后 merge 进 community hint (community 覆盖 greedy on overlap, 因为 user-curated > heuristic)
- 然后正常 `master.solve(solution_hint=...)` → `apply_solution_hint` 调 AddHint per slot
- production wrappers (run_campaign_p2_workers1.sh / workers2.sh) default 自动注入

适用 candidate 范围：blueprint natural max empty rect = 15×27 = area 405. 项目 certified path 从 large area 往下扫, hint 只对 area ≤ 500 + min_side ≥ 10 范围有意义. 大 area candidate (>1000) hint 几何不可能 match.

测试 / 回归保护：
- `src/tests/test_blueprint_to_master_hint.py` — 10 hand-verified sample (rotation×facility_type combo)
- `src/tests/test_community_hint_env_injection.py` — 9 edge case (empty/missing/malformed/非 int)

### 停止 168h campaign（清残留）

```bash
bash scripts/stop_campaign.sh             # graceful: TERM → 5s → KILL 残留
bash scripts/stop_campaign.sh --force     # 直接 SIGKILL, 不等
bash scripts/stop_campaign.sh --dry-run   # 只列, 不杀
```

清的范围：`main.py --campaign-hours` 主进程 + 其 multiprocessing.spawn
worker 子树 + `campaign_watchdog.sh` + stale
`/tmp/zmd_campaign_watchdog.lock`。**不动** Claude Code 自己的进程 + 心跳
watcher（tail -F zmd_heartbeat / iter=0…HEARTBEAT bash loop）。

为啥需要专门脚本：手 `pkill -f python` 会误杀心跳 watcher 的 bash sleep
loop + Claude Code subprocess pool；递归杀 main 的 subprocess tree 也是因
为 multiprocessing.spawn 父死子不一定立刻 exit（孤儿被 pid 1 接管, CP-SAT
仍跑）。脚本递归 pgrep -P 父→子，先 TERM 5 秒后 KILL 残留。

### CachyOS 主机生产力调优（host-level，2026-05-10 落地）

针对 i9-13900KS + CP-SAT 长跑工作负载已经做了几件 host-level 调优——这些是
系统状态，不是项目代码。168h campaign 启动前应该 verify 都生效：

```bash
# CPU 频率 / 升频
powerprofilesctl get                                              # 应 = performance
cat /sys/devices/system/cpu/intel_pstate/hwp_dynamic_boost        # 应 = 1
systemctl is-enabled hwp-dynamic-boost.service                    # 应 = enabled

# Cmdline (重启后才生效) — 应包含:
#   mitigations=off isolcpus=0-7 nohz_full=0-7 rcu_nocbs=0-7
cat /proc/cmdline

# 温度监控 (campaign 启动时后台启)
nohup bash scripts/temp_logger.sh 60 > data/telemetry/temp_log.csv 2>&1 &
# 输出 CSV: timestamp_iso,pkg_c,ecore_max_c,max_pcore_freq_mhz
# pkg_c 从 /sys/class/thermal/x86_pkg_temp 直接读 (受 isolcpus 影响小)
# 注意: 开 isolcpus=0-7 后 lm_sensors 的 coretemp 模块不再报 P-core 温度,
# 但 x86_pkg_temp thermal zone 一直工作 → 用 pkg_c 作 throttle 主信号
# 监控 pkg_c 持续 ≥ 90°C → 撞 thermal throttle → PPD 切回 balanced
```

### sysctl tuning (永久, /etc/sysctl.d/99-zmd-tuning.conf)

```
vm.dirty_background_ratio = 3        # 默认 10. page cache 写回更平滑
fs.inotify.max_user_watches = 1048576 # 默认 8192. 防 telemetry 大量小文件撞 limit
```

systemd-sysctl.service 启动时自动 apply, 重启不丢。


调优明细（修改记录）：
- **PPD performance** + **HWP dynamic boost systemd unit** (P0+P1, 立即生效, 2026-05-10)
- **mitigations=off + isolcpus=0-7 + nohz_full=0-7 + rcu_nocbs=0-7**
  写进 `/boot/loader/entries/linux-cachyos.conf`（systemd-boot, 不是 Limine）。
  备份 `linux-cachyos.conf.bak.20260510_pre_isolcpus`。
  P-core (cpu0-7) 完全从 kernel scheduler 隔离；nohz_full 关每秒 1000 timer
  tick；rcu_nocbs 把 RCU callback 移到 E-core。168h 长跑减少 context switch
  抖动 +1-3% 吞吐。**重启后生效**——LTS entry 不动留作 fallback。
- **跳过**：OOM score adj (普通用户写不到 < 0)、systemd-run cgroup 隔离 (复杂度高收益边际)、CPU undervolt (崩溃丢 168h 进度风险高)。

### P2 #18 MUS via CPMpy QuickXplain PoC

```bash
# 装 CPMpy (CPMpy 0.10.0 PyPI 包 pyproject 限 ortools<=9.14, 但 API
# 兼容 9.15; --no-deps 绕过 dep constraint 即可, R13 audit 验证可用)
.venv/bin/pip install --no-deps "cpmpy>=0.10.0"

# 跑 PoC (微型 INFEASIBLE demo)
.venv/bin/python scripts/mus_extraction_poc.py
```

PoC 验证 CPMpy 0.10.0 MUS API 在 OR-Tools 9.15 上工作: deletion-based
mus + QuickXplain 都从 6 约束的 INFEASIBLE demo 精确提取 3 约束的最小核心
(50% reduction). Production 集成 (重写项目 binding/routing subproblem
为 CPMpy DSL 或 OR-Tools→CPMpy 桥接器) 是 ~1 周量级工作, 不在 PoC 范围.

来源: 路线图 P2 #18, R5 `a3bef849bbe8777ab` + R13 audit `ae3860a1dc6cbabb8`.

### P1 #12 cache-trio spike (24h instrumentation, gate 决定要不要做主体)

```bash
# 24h campaign 启动时把 spike env 打开（zero-impact when off）
EXACT_SUBPROBLEM_REPEAT_PROBE=1 bash scripts/run_campaign_linux.sh \
    --campaign-hours 24.0 --parallel-processes 4

# 跑完后 aggregate 各 worker 的 repeat-rate 数据
python scripts/analyze_subproblem_repeat_rate.py
```

输出全局 binding subproblem repeat_rate（lower bound — 跨 pid 不做 hash
dedup）。判定：rate ≥ 15% → GO 做 cache trio 主体（5-7 天工作）；< 15%
→ KILL（cache trio 没用）。审计来源：P1 #12 audit `a36d33351616095f1`。

数据落 `data/telemetry/subproblem_repeat_<pid>.jsonl`，每 5 min append
一次 summary snapshot。worker process 各自一个文件，offline 聚合。

### PCR-CUT (Patch-Certified Routing Conflict Core, 2026-05-19 Phase 4 hook)

Env-gated paradigm. master OPTIMAL → routing precheck front_blocked branch 里
**优先**走 PCR-CUT (替 deletion-core / lazy_demand / cell_cut). 它跑真 patch
belt CP-SAT 找最小 conflict core, signature lifting 后加 master nogood:

```bash
# 单 anchor trial (Phase 4 hook)
EXACT_USE_POSE_BOOL_MASTER=1 \
EXACT_B1_PATCH_ROUTING_CORE=1 \
EXACT_MASTER_GHOST_ANCHOR_FILTER=22,28 \
.venv/bin/python docs/research/pcr_cut_patch_routing_conflict_20260519/phase4_lbbd_hook_trial.py
```

env 全表:
- `EXACT_B1_PATCH_ROUTING_CORE=1` — 开关
- `EXACT_B1_PATCH_ROUTING_CORE_TOP_K=3` — 每 iter 评 top-K patches
- `EXACT_B1_PATCH_ROUTING_CORE_SECONDS=10` — separator 总预算
- `EXACT_B1_PATCH_ROUTING_CORE_PER_PATCH_SECONDS=5` — 每 patch solve 上限
- `EXACT_B1_PATCH_ROUTING_CORE_MAX_CELLS=900` — patch 资源 cap
- `EXACT_B1_PATCH_ROUTING_CORE_QX_CAP=32` — QuickXplain oracle 调用 cap

paradigm 流程 (Phase 0/1 GO, Phase 2-4 land 2026-05-19):
- Phase 0: top patch (≤770 cells) cover 98% SAC pressure ✅
- Phase 1: 8 anchor patch belt CP-SAT 21/21 INFEASIBLE, p95 2.5s ≤ 5 / 34K vars ≤ 160K ✅
- Phase 2: replay validate (presolve=false workers=1) + QuickXplain minimize
- Phase 3: signature lifting (within-instance only — PROJECT_LOCK 禁跨 instance)
  → `sum_i sum_p x_var[i,p] <= K-1` master nogood
- Phase 4: benders_loop front_blocked branch env-gated hook
- Phase 5 (TBD): multi-anchor campaign + ablation
- Phase 6 (TBD): proof lifecycle + regression hardening

fail-closed: 任一 cut replay 不成 INFEASIBLE 不加. cut 全 reject 后自然回落
到既有 deletion-core / lazy-demand / cell-cut path. 修改 src 不破坏 env-off
行为 — 之前 13 lever + Path 12/13 全 verdict 不变.

### Local upstream reference clones (offline, not vendored)

`.upstream_clones/` is **gitignored** and holds full clones for offline browsing/diffing. Currently contains:

- `.upstream_clones/industrial_planner_v2/` — full `hsyhhssyy/IndustrialPlanner` v2 branch (~50 MB shallow clone). Use for reading `src/domain/registry.ts`, `src/sim/engine.ts`, etc. without network. Refresh: `cd .upstream_clones/industrial_planner_v2 && git pull`.

These clones are **NOT** part of the build, are NOT scanned by tests, and do NOT count as vendored data. Vendored slices live under `third_party_snapshots/`.

## Dependencies

- Python 3.13
- ortools (9.15.6755), pydantic (>=2), numpy, matplotlib, psutil, pandas, jsonschema, Pillow

## Conventions

- All changes touching exact boundaries must update: PROJECT_LOCK.md, FILE_STATUS.md, relevant spec, relevant tests
- Postprocess/adapter changes don't need lock updates but must not widen proof semantics
- Test with `python -m pytest src/tests/ -q` before any commit
- `_codex_archive/` contains historical Codex (GPT) workspace artifacts — read-only reference, not active code
