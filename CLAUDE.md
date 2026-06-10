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
- `data/preprocessed/candidate_placements.json` (required external large artifact in current lightweight GitHub checkout; restore before certified exact runs)
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
src/search/certified_surface.py  # Central verifier for public CERTIFIED delivery surfaces (V73+)
src/search/certified_frontier.py # Replayable terminal full-frontier evidence (V75+)
src/io/delivery_manifest.py      # Disk-authoritative certified delivery manifest writer (V77/V78)
```

## Active Scope

- Single base: `valley4_protocol_core` 70x70 only
- Other bases (`valley4_infra_outpost`, `wuling_protocol_core`, etc.) are `future_scope`
- Outer-deployment subsystem is adapter-side `future_scope`

## Current Phase: 1.2 spike close (subject projection)

<!-- DOC-SUBJECT:current_project_state FIELD:claude_phase_contract START sha256:9bbcea5209902d09006df4a15d11d8218c5c22dfe1013280a04757d543bd5a47 -->
Current phase: **Phase 1.2 spike close is not formally closed** — the V50 manual owner-count gate remains in force, and V80 anchors certified lifecycle evidence after V57-V80 found sibling findings across condition/domain replay, master-domain and power-witness representation, replayable full-frontier terminal evidence (slicing axes sealed plus canonical admissibility and deny-unknown evidence keys), disk-authoritative delivery-manifest writing, canonical certified manifest publication, certified export surfaces, and closed allowlist `EXACT_*` env handling. The standard remains **3 consecutive independent full reviews with zero algorithmic/soundness findings**, with the count **owner-maintained outside the repo**; the repository no longer grants clean credit from receipts or report metadata. Until an explicit owner manual decision opens P1.3B, do not start the true `PoseBoolExactMaster` LBBD master integration. Naming warning: project-book `P1.3B` is the same implementation body that older CC memory calls `P1.3A 主体`; `src/cuts/lifecycle.py` still keeps `step_8_apply_to_master` as the explicit not-yet-integrated boundary.
<!-- DOC-SUBJECT:current_project_state FIELD:claude_phase_contract END -->

Operational notes:
- 范式已从早期 tuning / Phase-3B 转为 **cut-family LBBD 重设计** (9 个 F1–F9 cut family 当 Benders cut 收紧 master)。
- 单一 living 现状源仍要结合 CC memory `windows-ninth-review-pending` 读；本段只承载会被其它文档投影的 phase contract。


## Knowledge Tree / Handoff Surfaces

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer START sha256:9dd6b559dd17a70fab730793a77d2e4a91c27eedcdfbf1bf81fdeba5f658592f -->
The project uses **one logical knowledge tree with two physical projections**. `docs/` is the stable documentation projection; `cc_context/memory/` is the collaboration-continuity projection. Neither tree is allowed to become a second independent truth source: volatile living claims should be promoted into a subject field and projected to every surface that needs them.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:shared_subject_layer END -->

<!-- DOC-SUBJECT:project_knowledge_tree FIELD:memory_role START sha256:29ad99c8cfd99eeb1c5b120f5028478ab5d2083ee1d4075293639ba3e6c66ea9 -->
The memory tree is the collaboration-continuity surface. It answers: what the previous working window knew, which mistakes were already corrected, what user preferences or process constraints matter, which old statements must not be trusted blindly, and what the next window should read first.
<!-- DOC-SUBJECT:project_knowledge_tree FIELD:memory_role END -->

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

# Run tests (full suite ~7min serial; the parallel form below is ~85s and was
# verified to produce the identical failure set)
python -m pytest src/tests/ -q
# Fast parallel form (pytest-xdist): isolated basetemp also avoids the
# repo-root .pytest_tmp clobbering when several pytest processes run at once
python -m pytest src/tests/ -q -p no:randomly -n 8 --dist loadfile --basetemp="$env:TEMP\zmd_pytest"

# Single-base e2e workflow
python scripts/run_industrial_planner_single_base_e2e.py --run-dir .artifacts/industrial_planner_single_base_e2e

# Visualization only
python main.py --vis
```

## Maintenance scripts (runbook)

### GPT Pro 外发自动化 (2026-06-11 上线, 完整流程已验收)

外发任务全流程脚本化 (打包→上传→发送→等完成→收交付), 跑在本地零 token:

```powershell
# 前置 (一次性): 起专用自动化浏览器 (默认 Edge, -Browser chrome 可切); 首次需手动登录 chatgpt.com
& cc_context\review\gpt_dispatch\start_gpt_automation_chrome.ps1

# 标准用法: 自动打全项目单包 + 发「终末地」Project (Pro·进阶) + 等 + 收
python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --pack --prompt-file <prompt.md>

# 托底/续等: 脚本挂掉或超时后重连同一会话, 不重发任务
python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --resume "<会话URL>"
```

- 退出码: 0=交付到手 / 2=完成无附件 / 3=异常(看 attention 截图) / 4=超时 / 5=疑似降级。详见 `cc_context/review/gpt_dispatch/README.md`。
- **Pro 静默降级 (owner 经验)**: 不在任何明面标注, 唯一判据 = 真实任务完整生成 <1min。脚本自动刷新重跑一次 (`--downgrade-retries`), 仍快 → exit 5, CC 改走 Claude-in-Chrome 插件通道 (Edge, 已登录) 托底重发。轻量测试传 `--min-gen-seconds 0`。
- 内建: 附件 404 自动救援 (sandbox 文件回收后让 GPT 重新生成再收)、浏览器 tab 自动回收、非预期状态截图+DOM 现场落盘。

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

### 数字单一来源 (authoritative_numbers core node)

<!-- DOC-SUBJECT:authoritative_numbers FIELD:runbook_summary START sha256:4fabdc1ac355deea3bf2ba6678b33a985d76bb09370b995c1edc136a81386ac8 -->
Repeated review/package numbers must flow through `docs/research/p1_2_spike_sizing_gate_20260601/authoritative_numbers.json` and `scripts/gen_authoritative_numbers.py`. Prose projections should link to that core node instead of hand-copying volatile current values, unless the number is explicitly historical and dated.
<!-- DOC-SUBJECT:authoritative_numbers FIELD:runbook_summary END -->

> 评审包/文档里反复出现的权威数字 (cuts 计数 / sizing 投影 / F3 / remap) 不要散在各处手抄。**核心节点 = `docs/research/p1_2_spike_sizing_gate_20260601/authoritative_numbers.json`**。架构**意图** = core-node + projection + forcing-function (同 [[memory-currency-protocol]] 给 handoff 的 stamp)。**诚实现状 (v28 外审 catch)**: forcing 半边落地, **projection 半边仍是未接线契约** (current_claims() 无消费者, 包 README 仍硬编码会漂)。

```powershell
# 重算/刷新核心节点 (cuts 计数从 src/tests/cuts 实时 collect; sizing 仅在 spike fixture 在场时, 见下)
python scripts/gen_authoritative_numbers.py
python scripts/gen_authoritative_numbers.py --check   # exit 1 = 核心节点 stale
```

- **强制函数 (真 gate)** = `src/tests/test_authoritative_numbers_currency.py` (任何 pytest run 变红): 断言核心节点 == 实时计算。**master 上只焊 `cuts_tests_total`** (最易漂); sizing/F3/remap 见核心节点 `_meta.enforcement_tiers`。**不扫散文也不扫 projection_targets** —— 文档会 meta-讨论数字 (changelog 引旧值当历史 / "别把 36/50 读成 72%"), 裸扫到处误报。
- **`--check` 未接 CI/pre-commit 硬 gate** (本机 pre-commit 仅 warn-loud, 不阻断); 真 gate 是上面那个 pytest 测试。
- **sizing 6 个数字** 由 `sizing_gate.compute_sizing_numbers()` 算, 输入 fixture 在 `data/cuts/spike/` (build 时从 spike 分支 overlay, master 无) → master 不现算, 是冻结 spike 值; 仅包内/spike 上下文可复现。
- **build 投影 (未接线契约)**: 包 build 脚本的 README 当前 claim 数字**应** `from gen_authoritative_numbers import current_claims` 注入 (changelog 历史字面量不动) —— 但**目前没接** (current_claims 无消费者, build_v28 仍硬编码历史值 vs 核心节点当前值)。接了之后包 README 才是真投影; 在那之前它会漂、不自动报红。

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

启动 168h 大跑前手动跑这个，缺一项 hard blocker 就 BLOCK。检查项（**11 项 = 5 blocker + 6 warning，以 `production_readiness_gate.py` docstring + `gate_check()` 为准**）：
pacman freeze 已启用 (Linux only)、venv + ortools 可导入、preflight 核心
守卫测试通过、kernel 是 cachyos-bore 变种、磁盘 ≥100 GiB free、git
working tree 干净、THP enabled、jemalloc 装且 LD_PRELOAD 配置、进程
cpu_affinity 限定 P-core、**`EXACT_POWER_PLACEMENT_SUBPROBLEM` 未启用 (exploratory blocker)**、**OOM headroom (parallel × peak_worker_RSS + host < MemAvailable, blocker)**。Exit code: 0=ready, 1=blocked。

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
的收益）；readiness gate 全部检查项 (11 项, 见上) 会自动 flag 漏配置。

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
- production wrappers (run_campaign_p2_workers1.sh / run_campaign_workers2.sh) default 自动注入

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

### 当前 Windows checkout 环境 (2026-06-10)

- 当前工作区 `C:\claude pj\zmd_pj` 是轻量 GitHub checkout (zhuran24/zmd); 旧 `D:\追光\zmd` 位置已不存在。
- **本 checkout 无 `.venv`** — 直接用全局 Store Python 3.13.13 (`python`), 依赖已装全 (ortools 9.15.6755)。CLAUDE.md/记忆里的 `.venv\Scripts\python.exe` / `.venv/bin/python` 写法是旧环境遗留, 在这里会假成功或报错。
- `data/preprocessed/candidate_placements.json` (53.6MB) 外置未恢复; certified exact 大跑前按 START_HERE.md 的 restore 命令恢复。
- post-commit hook 会自动 push GitHub (commit ≈ push); pre-commit 的 memory 镜像源 (旧 slug `D-----zmd`) 不存在会静默跳过 → 改记忆需手动双写 `_cc_live_memory/` 与 `cc_context/memory/`。

## Conventions

- All changes touching exact boundaries must update: PROJECT_LOCK.md, FILE_STATUS.md, relevant spec, relevant tests
- Postprocess/adapter changes don't need lock updates but must not widen proof semantics
- Test with `python -m pytest src/tests/ -q` before any commit
- `_codex_archive/` contains historical Codex (GPT) workspace artifacts — read-only reference, not active code
- **非必要不用 Workflow, 任务外发 GPT Pro (2026-06-10 用户裁决, 当晚精简版)**: 默认自己干或单个 Agent 子代理; 审查/外审/委托实现类任务用 Claude in Chrome 浏览器插件发到 chatgpt.com, **不开本地多代理审查 workflow**。发送设置三条: **① 模型选 Pro·进阶 (= GPT Pro 扩展模式); ② 发在 ChatGPT「终末地」Project 里; ③ 非必要不用老窗口 (新任务默认新会话)**。**打包 = 除缓存文件外全项目打** (build 脚本 `cc_context/review/build_v80_*.py`); 老的审查打包规范 (no-priming/prompt 模板/armor/7z 等) 已废除, 备份在 `cc_context/review/archive/` 与 `cc_context/memory_archive/`。"必要" = 用户明确点名, 或离不开本地多路编排且无法外发。(实测教训: 审查 workflow 38min + API 超时挂 critic + 审查 agent 并发跑 pytest 互删 `.pytest_tmp` 污染全量。)
- **子代理模型默认 opus**: 派遣 sub-agent (Agent 工具 / Workflow 内 `agent()`) 默认用 **opus** — 通常靠继承主会话模型即可, 不必显式传 `model`。仅特定情况 (如纯机械/批量活想省额度) 才显式降到 sonnet/haiku。**Agent 工具无独立 effort/thinking-budget 旋钮** —— 控制力度唯一硬杠杆是 `model` 参数, 软杠杆是 prompt 措辞; harness 底层 reasoning-effort 没暴露在 Agent 参数里。
- **现状类 memory 守 `[[memory-currency-protocol]]`**: 身份 vs 现状分离 (身份根 memory 只放稳定身份 + 指向 living 现状源的指针) + 单一 living 现状源 (恰好一条权威「当前 phase」, 其余带日期标 snapshot/历史) + phase 转换更新仪式 (close/milestone 时更新 living 源 + 给旧状态加 superseded/历史标) + memory 引用仓库文件用相对路径不用绝对 `D:\...`。
- **项目结构卫生**: root 只放项目源 (main.py / src/ / docs/ / rules/ / specs/ / scripts/ 等); CC / handoff / 外部审查工件统一归 `cc_context/` —— `memory/` 记忆备份 + `memory_archive/` 老记忆归档 (单份) + `tools/` 记忆维护脚本 + `review/` 外发打包工件 (build 脚本 / GPT prompt; 老工件在 `review/archive/`)。**别在 root 散落** review 包 / prompt / build 脚本。新建这类工件直接放 `cc_context/review/`。**为何收口 cc_context 而非另起顶层**: pre-commit hook 依赖 `cc_context/memory` 路径做 memory-sync, 另起顶层会破坏它。移动 tracked 文件用 `git mv` 留 rename 历史; 移动后回填 memory 里的旧路径引用防新 staleness。
