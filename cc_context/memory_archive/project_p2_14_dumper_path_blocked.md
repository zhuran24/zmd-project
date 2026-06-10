---
name: p2-14-dumper-path-blocked
description: 168h 0 LBBD dump 根因不是 worker→main IPC, 而是 master 构造里嵌套 CP-SAT 无 timeout 无限 hang. commit 2915d6f 加 env-gated max_time_in_seconds, fallback 链接管.
type: project
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
## 真 root cause (py-spy 实证 2026-05-11 23:32)

不是 worker→main IPC bug. 是 `_solve_exact_local_power_capacity_compact_rect_cpsat`
(`src/models/master_model.py:6801`, 行号 @ 2026-06-01, master_model.py 持续增长易漂,
**以函数名为准**) 嵌套 CP-SAT 子求解漏设 `max_time_in_seconds`.
一个 degenerate template 让它无限 hang → master 构造永远不返回 → 永远不进
LBBD → dumper 0 触发.

Parallel mode 表面"卡 IPC": worker 自己 hang 在同处, main `_result_queue.get()`
等永远来不了的 result. 单进程 (A 实验) 直接在 main 暴露 hang.

stack:
```
_solve_exact_local_power_capacity_compact_rect_cpsat (master_model.py:6801)
_exact_local_power_capacity_coefficients (master_model.py:7130)
_prepare_power_pole_families (exact_coordinate_master.py:1996)
build_exact_core
run_outer_search
```

## Fix (commit 2915d6f) — **部分验证, 不是完全 fix**

加 env-gated `solver.parameters.max_time_in_seconds` (env
`EXACT_LOCAL_CAPACITY_CP_SAT_MAX_SECONDS`, default 60s).
超时 → status=UNKNOWN → 既有 raise `_CompactRectCpSatFallback`
→ rectangle_frontier_dp → bitset MIS → cpsat fallback (4 层兜底, 每层都是
exact 算法).

**已验证 (部分)**:
- py-spy fix 后 stack 通过 _prepare_power_pole_families 进入 _run_certified_exact
  Benders 主循环——**master 构造不再 hang**
- preflight 9/9 + 全套 pytest 2122 passed / 60 skipped / 244s
- L2 自审: 求解语义未变 (capacity 数值在 fallback 下应一致), max_lex 不受影响

**未验证 (真 blocker)**:
- master.solve() 本身能不能在 30min master_seconds 内出 SAT/OPTIMAL?
  - 8 个 RUNNING candidate 都是大面积难 candidate (69x19, 67x20, ..., 70x6)
  - 历史数据: campaign created 2026-05-09, updated 2026-05-11, attempts
    127-137. **但 attempts 不等于 master.solve 跑完次数** — 是
    mark_candidate_started 次数. 修嵌套 hang 之前, 每次 watchdog 重启都在
    master 构造卡死 (_prepare_power_pole_families), mark_result 从没被调,
    candidate 保持 RUNNING + attempts++. 实际**任何 candidate 都没真跑过
    完整 master.solve()**.
  - 所以"master 30min 求不到 SAT" 是**未经验证的 prediction**, 不是 evidence.
    2026-05-12 这次 long_validate 是 fix 后**第一次**让 master.solve 真跑
    完整 30 min, 结果未知 (snapshot 后才知道).
  - 真的 168h "0 LBBD dump" 双重原因:
    1. 嵌套 CP-SAT 无 timeout 让 master 构造 hang (已修 ✓)
    2. master.solve 在难 candidate 上 30min 求不到 SAT → 永远不进 binding
       subproblem → dumper 永不触发 (未解决 ✗)

## OOM 风险 (2026-05-12 实证, parallel * master_workers 总 thread 数要严格控)

第一次让 master.solve 真跑完整时撞 OOM:
- 4 outer worker * master CP-SAT 8 inner threads = 32 thread
- 单 worker master.solve 在 70x70 + 266 facility 上 heap 增长到 10 GB
- 4 worker = ~30 GB+, 加 main + system → 撞 46 GB RAM 上限
- dmesg: `Out of memory: Killed process 2998768 anon-rss:10926488kB`
- main 检测到 worker 死 → status=UNKNOWN 退出

**安全配置 (2026-05-12 验证 workable)**:
```bash
EXACT_MASTER_CP_SAT_WORKERS=4 \
EXACT_BINDING_CP_SAT_WORKERS=4 \
EXACT_ROUTING_CP_SAT_WORKERS=4 \
bash scripts/run_campaign_linux.sh \
  --parallel-processes 2 \
  ...
```
- parallel=2 * master_workers=4 = 8 inner thread total (was 32)
- 2 worker 各 ~8 GB = 16 GB, 加 main 几 GB = ~20 GB, 远低于 46 GB ceiling
- 启动 ~57s 后 mem 20 GB / 26 GB free, pkg 74°C 正常负载

## OR-Tools mem cap 实证 (2026-05-12)

CP-SAT `solver.parameters.max_memory_in_mb` **默认 10000 MB = 10 GB**.
OOM 那次 worker rss 达到 10.9 GB 略超 cap, OS OOM kill 比 OR-Tools 内部
stop 还快. 这给量化判据:

**OOM 安全判据 (CachyOS 46 GB RAM 主机)**:
```
parallel_processes * max_memory_in_mb (per worker) ≤ available_RAM * 0.7
2 * 10 GB = 20 GB ≤ 46 * 0.7 = 32 GB  ✓ 当前安全配置
4 * 10 GB = 40 GB ≤ 46 * 0.7 = 32 GB  ✗ 之前 OOM 配置
```

注意单 worker 不会同时跑 master + binding + routing solver (Benders 是顺序),
所以 worst-case per worker = max(master, binding, routing) 的一个, 通常是
master. 但**所有 worker 同时跑同一 stage** (parallel CP-SAT), 所以
parallel * max_mem 是真 ceiling.

readiness gate (#38 task) 应该:
- 读 EXACT_*_CP_SAT_WORKERS env (worker count 影响 thread, 不直接影响 max_mem)
- 读 parallel_processes 参数
- check `parallel * 10 GB ≤ MemTotal * 0.7`
- 输出建议: "降 parallel 到 X" 或 "降 max_memory_in_mb 到 Y" 或 "加 RAM"

经验法则 (实证):
- parallel_processes * EXACT_MASTER_CP_SAT_WORKERS ≤ 8 比较安全 (thread 平衡)
- parallel_processes * 10 GB ≤ 32 GB (mem 平衡, default cap)
- 两条限制都不冲, 取严格的一条
- 如果想用 swap (47 GB) 缓冲, master.solve 卡 swap 等于慢千倍, 跟 OOM 体感差不多, 不可行

## 真完整 fix 的 next step (按可能性排)

1. **Lookahead/probe 模式** — outer_search.py FRONTIER_PROBE_MODE_AUTO 路径
   可能已经实现 "先跑小 candidate" 机制 (line 553+ frontier_probe_mode branch).
   验证: 25 min snapshot 看 dumper 有没有触发, 触发了说明现有机制就够用.
2. **Warm start hint** — 给 master 一个 hand-crafted valid solution 作为 hint,
   让 master.solve() 立刻有 incumbent → 进 LBBD. 涉及 P1 #7 已有的 hint
   persistence infrastructure.
3. **小 candidate fresh campaign** — 新开 campaign 不 resume, 从 small grid
   开始. 丢历史 INFEASIBLE 信息但能快速出 SAT 收 production dump.
4. **Fixture 路径** — 接受 P2 #14 短期 production data 收不到, 用现有 pytest
   fixture + hand-crafted 实例做 evaluator training data 起步.

## 历史教训 (写入审查策略)

- 之前 168h 卡的 "worker→main IPC" hypothesis 是 py-spy 只看 main 没看 worker
  的误判. 多进程 hang 必须 py-spy 全部 worker 进程, 不光看 main.
- 嵌套 CP-SAT 求解器**必须**设 `max_time_in_seconds`. master_model.py 还有
  类似潜在 hang site:
  - `:5574` `_solve_exact_local_power_capacity_cpsat` (legacy path, raise
    RuntimeError 非 fallback) — 留作 defer (行号 @ 2026-06-01, 以函数名为准)
- L1.5 dynamic_review_smoke 5min 短跑不足以抓这种 hang
  (master.solve() 第一轮没 warm start 本就慢 30min-2h, 5min 0 dump 不必然是 bug).
  审查树需补 py-spy 自动 stack 取证 step.

## 仍待办

- L1.5 smoke 升级: 加 "master 进入 Benders 主循环" 断言 (py-spy / log marker)
- main.py:14-15 sys.stdout TextIOWrapper 丢 line buffering, 重定向到 file 时
  Python -u 不生效 → 长跑前期 0 输出 (确实在跑, 只是 buffer 未 flush)
- master_model.py `:5574` legacy `_solve_exact_local_power_capacity_cpsat` 同样
  漏 timeout, 但 raise RuntimeError 非 fallback. 影响范围未知, 留 audit.
  (行号 @ 2026-06-01, 以函数名为准。)

## 链 (补连 2026-06-01)
- [[multiprocess-hang-inspect-all]] — hang 排查法
