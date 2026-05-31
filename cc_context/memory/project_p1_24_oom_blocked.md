---
name: p1-24-oom-blocked
description: "2026-05-14 P1 #24 cache trio 4-parallel 验证撞 OOM 9 min 退; readiness gate OOM headroom check 已 land (commit b4bf175); 4-parallel 在本机 48GB RAM 不可行"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-14 P1 #24 实测发现**: 主线第一步 cache trio +15-22% 验证撞 OOM, 不是 wall-clock 瓶颈而是 RAM 撞墙.

**两轮实测数据**:

Run 1 (`.artifacts/p1_24_validation/baseline_run/`, -p 4):
- 命令: `python main.py --campaign-hours 0.5 --parallel-processes 4 --skip-readiness-gate`
- 实际: 9 min 后 worker_process_failed 退出 (status=UNKNOWN)
- dmesg 02:41:38 + 02:44:50 两次 global_oom 杀 worker (每次 total-vm=35GB anon-rss=8GB)
- 4 worker × ~8 GB avg + 单 worker peak 16.8 GB → 主机 48 GB RAM 撞墙

Run 2 (`.artifacts/p1_24_validation/baseline_run_p2/`, -p 2 retry 在 commit b4bf175 后):
- 命令同上 但 `--parallel-processes 2`
- 实际: 3 min 单 worker 飙到 28.14 GB anon-rss, avail 跌到 1.8 GB, swap 5.5 GB used
- swap thrash + 距 OOM 边缘 — 人工 abort 防 OOM 杀
- 关键发现: 单 worker peak 远超原估 12 GB; 实测 28 GB (still 涨), 取 30 GB 作 conservative

**Why 撞 OOM 不奇怪 (audit 早有预警)**: 路线图警告 168h 跑 ~24-40 GiB peak RSS, baseline 状态文件 (5/12) 最后一波 也是 worker_crash_respawn_limit exit=-9 (SIGKILL 即 OOM). 之前误读为 IPC bug.

**How to apply**:
- 本机 (48 GB DDR5) 实测 -p 4 和 -p 2 都撞 RAM (-p 2 单 worker 28 GB 已超 host 一半)
- -p 1 marginal (单 worker 30 GB + host 8 GB = 38 GB, 41 GB available 几乎贴脸)
- 真正可行路径: **96+ GB RAM 硬件升级** 或 **远程跑** (memory 提到 WAN 1 远程)
- P1 #24 cache trio "+15-22%" claim 是基于多 worker parallel 工作负载, -p 1 测出来不能 transfer

**已 land 的 mitigation**:
- `scripts/production_readiness_gate.py` 加 `check_oom_headroom()`
  - 公式: needed = parallel × WORKER_PEAK_RSS_GIB + HOST_OVERHEAD_GIB
  - 第一版 (commit b4bf175): 12 GB/worker + 6 GB host (基于 Run 1 估算)
  - 第二版 (Run 2 实测 calibration): 30 GB/worker + 8 GB host
  - BLOCK if needed > MemAvailable; WARN if > 90%
- 7 tests `src/tests/test_production_readiness_gate_oom.py`
- 现 168h production-class 启动会被 OOM gate BLOCK
- P1 #24 phase 工具 (compare + cache-trio launcher) 也一并 land 备用

**还没做 (跟 [[v4-followup-landed-next-main-line]] 主线下一步对照)**:
- P1 #24 真实测 +15-22% 验证 (要先解决 RAM)
- P1 #12 cache spike 24h 数据 (同样 4-parallel 撞 OOM 风险)
- P1 #7 ε-Certified main flow 集成 (campaign 启动同 RAM 问题)

**A 方案验过 — FAILED** (2026-05-14 03:14, commit 74d0c4a):
- 加 env `EXACT_SUBPROBLEM_MAX_MEMORY_MB=10000` 到 4 处 subproblem solver init
- 实测 -p 2 跑: 启动 2 min 内 worker peak 9.6 GB (贴 cap), 4 min 突破到 27.5 GB
- OR-Tools `max_memory_in_mb` **不限 OS RSS** — 可能只是某 internal SAT structure 限制
- Hook 代码保留 (env 缺/garbage no-op, 未来 fix 或 sub-OOM 场景仍可用)
- 下次别再试这条, 直接走 B (memray) 或硬件路径

**C 方案验过 — 数据不可信** (2026-05-14 03:18):
- `scripts/p2_14_evaluator/run_eval_v1_baseline.py --limit 100` 跑 ptmalloc vs jemalloc
- ptmalloc avg 1.589 ms, jemalloc avg 1.752 ms → jemalloc **慢 10%**!
- 跟 P1 #24 audit "+5-10% jemalloc" claim 反向
- 但 binding fixture 太小 (2 instances/placements, 毫秒级 solve, single-thread): jemalloc 优势在 multi-thread contention, single-thread small-alloc 反效果. 跟 production 4-thread 大候选 workload 不匹配, 数据不能 transfer
- 单点 microbench 不能验 P1 #24 cache trio long-run combined claim

**B' 方案 (CP-SAT 参数 sweep) — 不是 lever** (2026-05-14 03:42):
- 加 generic env `EXACT_SUBPROBLEM_PARAMS="key=val,..."` hook (commit pending)
- Sweep 4 combo: default / clause_cleanup 激进 / + probing 关 / + linearization 关
- 各 -p 1 跑 2 min, fresh wipe state
- 4 combo @120s RSS 都 ~10.8-11.3 GB, 差异 <5% → **CP-SAT 参数对 RSS 无影响 (在 2 min 内)**
- 因为 2 min 内主要 frontier exploration setup, CP-SAT 真 solve 还没起步

**关键推翻 (2026-05-14 03:48)**: 真正的 RSS 大头跟 cuts persist 没关系!
- Fresh wipe state 跑 -p 1 trajectory:
  - 0:57 → 8.87 GB
  - 1:57 → 10.76 GB (1.9 GB/min, 平稳)
  - **2:57 → 30.01 GB** (19 GB/min, 瞬间飙)
- 跟 backup state 跑同样飙到 28+ GB. **不是 cuts 累积 / 历史加载, 是单 candidate 70x70 binding/routing 进入 CP-SAT 真解题阶段 OR-Tools 一次性 alloc 18-20 GB**
- 这是 problem-size 硬性下限, 70x70 + 266 facility + LBBD master 内 var/constraint 数本身就大

**所有软方向都死**:
- CP-SAT 参数 sweep: 不影响 model 大小
- Cuts persistence 优化: cuts 还没产就撞墙
- jemalloc / THP / cache trio: alloc 速度优化, 不减总量
- Fresh start: 同样飙 30 GB

**Why 记**: 下次 session 想跑 P1 #24 / P1 #12 / P1 #7 任何要 4-parallel 长跑的, 先看这条避免重复撞 OOM. 替代路径是先 -p 2 验证, 数据 OK 再考虑硬件升级.

**硬件方向被用户明确排除 (2026-05-14 04:30)**:
- 加内存条 / 上服务器 / 第二台机器 / 租云 全部不可行 (预算限制)
- 跟 [[hardware-constraint-single-machine]] 的 WAN 远程方向也不再考虑 — 用户明确说"硬件方面这条路断了哪怕是组服务器目前暂时也没有可行性"
- 真路径只剩软件: 算法重构 / 换 solver / 模型重构 / 数学结构利用 / proof 切片重设计

**GPT-5.5 Pro v5 包已发 (2026-05-14 04:39)**:
- `~/linwin_share/zmd_code_v5.zip` 18 MB 干净版 (没 v3/v4 历史; 单一 RAM 瓶颈问题专项)
- 沿用 `~/linwin_share/zmd_deps_v4.zip` (5/10 后 requirements 没改)
- 包结构: `code.tar.xz` + `bin/7zz` + `meta/` (global_CLAUDE.md + 34 memory + preflight 11/11 + pytest 2151 passed + p1_24_validation 6 组实测数据 + dmesg OOM 证据)
- README 极简版 (~25 行) 不嵌包内, 直接 chat 输出给 GPT — 因为今天 finding/数据/commits 全在 zip 里 GPT 自己能查
- 等 GPT 回复. 后续整 reply 进 docs/research/ + 写 follow-up issue
