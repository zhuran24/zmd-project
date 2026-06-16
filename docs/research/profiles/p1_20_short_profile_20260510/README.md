# P1 #20 短跑性能分析（2026-05-10）

CP-SAT 求解器一次约 10 分钟的 short profile，目的是用 `py-spy --native` 找到真实热点，给后续优化（编译器、缓存、CP-SAT 参数）打底。

## 跑测设置

- 命令: `bash scripts/profile_short_run.sh 1200 0.4`
- main.py 参数: `--campaign-hours 0.4 --parallel-processes 1`
- py-spy 参数: `record --native --subprocesses --rate 100 --duration 1200`
- 主机: 13900KS / CachyOS / cmdline 已含 mitigations=off + isolcpus=0-7 + nohz_full=0-7 + rcu_nocbs=0-7 / PPD performance / HWP boost

## 实际只跑到第 1 个 master 迭代

main.log 末尾 `Iteration 1/30 status=UNKNOWN`，main.py 在第 1 个迭代求解 UNKNOWN（不知道结果） 后退出，**没有走到 binding / routing 阶段**。原因：master 阶段在 600 秒时间限制内没解出，触发 outer search 提前退出。

意味着这份 flamegraph 主要反映:
- master 模型构建（Python + ortools）
- CP-SAT presolve（含对称性检测、传播、probing 加载）
- master 求解 search 早期

**不包含**: binding 子问题、routing 子问题、Benders 切割管理。这部分要等真正 168h campaign 启动后 attach 抓中段。

## Top 热点

| samples | % | 函数 | 解读 |
|---|---|---|---|
| 7151 | 12.07% | `std::__introsort_loop` (libortools) | C++ STL 排序 — 头号热点 |
| 7068 | 11.93% | `std::__adjust_heap` (libortools) | STL 堆调整 — 紧随其后 |
| 2792 | 4.71% | `clock_nanosleep` ← `AbslInternalSleepFor` | 多 worker 互斥锁等待（absl sync） |
| 1316 | 2.22% | `build_exact_core` (master_model.py:2358) | Master 模型构建（Python） |
| 1281 | 2.16% | `run_benders_for_ghost_rect` (benders_loop.py:4779) | LBBD 主循环 |
| 741 | 1.25% | `DetectAndExploitSymmetriesInPresolve` | CP-SAT 对称性检测 |
| 727 | 1.23% | `FindCpModelSymmetries` | 同上 |
| 712 | 1.20% | `PropagateDomainsInLinear` | 线性约束域传播 |
| 729 | 1.23% | `_exact_local_power_capacity_coefficients` | 电力容量系数计算 |
| 712 | 1.20% | `_solve_exact_local_power_capacity_*` | 电力容量子模型求解 |
| 697 | 1.18% | `_add_ghost_constraints` | ghost 矩形约束添加 |

## 行动建议（按 ROI 排序）

1. **跑 168h 真 campaign 时 attach py-spy** 抓 binding/routing 中段，补全本次缺的部分（Phase 3C P1 #20 part 2）
2. **试 CP-SAT `symmetry_level=0`** —— 项目已经做过手动对称性破坏，CP-SAT 内部对称检测占 ~3% 可能是冗余先验，去掉应该正向。1 行参数实验。
3. **C++ 排序/堆 12% 是上游代码** —— 我们改不了，但 P1 #13 编译器优化（-march=native + LTO + PGO）对 SIMD 向量化排序应该能拿到 +3-5% 中的一部分
4. **absl 同步 4.7%** —— 8 worker 内部互斥锁等待。P0 #2 决定生产用 4 worker 已经能砍掉一半
5. **Python 层 master 构建 5-8%** —— 一次性成本，168h 摊销后比例小，低优先级

## Caveats

- py-spy 报告 `behind in sampling`：`--native` 解栈太重导致 100 Hz 跟不上，**部分 sample 丢失**（最终 59244 samples / 2 errors）。热点比例统计仍准确，绝对量偏少。
- **单 worker 跑** 不反映生产 4-worker 的真实分布（worker 间 contention 会更明显）
- master UNKNOWN 1 次就退出 = 这次 profile 实际只覆盖 master 阶段头 10 分钟
