# 03 — ①′ 第三段判读：prod 注入演习（单发 6×6 锚点，2026-07-16）

> 数据 = `.artifacts/rab_drill_20260716/arm_rab/`（cell.json / run.log / mem.log）；
> harness = `rab_drill_runner.py`（本目录）。A/B 基线 = 批C 门6 `drill_arm1`
> （同配方 fixed/probing3/symmetry3/单worker/alt_cap200、同 6×6 锚点、RAB off）。
> owner 预批口径 = "单发不算长跑"；实际 wall 51.5 min（6 迭代帽）。

## §1 原始结果

| 指标 | arm1（RAB off，07-14） | arm_rab（RAB on，本次） |
|---|---|---|
| 终态 | UNKNOWN（binding alt_cap 200 耗尽 = F-6 踏车） | UNKNOWN（**MAX_ITERATIONS=6 帽**，fail_closed_unknown） |
| wall | 566s | 3089s（≈6 × ~510s master 重解） |
| 细粒度 exact-safe cut | **0** | **1293**（全部 `EMPTY_DOMAIN` 型） |
| binding 枚举轮数 | 数百轮（踏车） | **0**（`enumerated_bindings=0`） |
| routing 上场次数 | 0 | 0（`routing_attempts=0`） |
| 内存峰值 | —— | VmHWM 19.98 GiB / RSS 峰 19.57 GiB / **swap 峰 8.07 GiB（运行早期，非收尾）** / 同采样 RSS+swap 峰 21.60 GiB |

逐迭代 RAB 遥测（6/6 迭代全部点火）：216/218/214/217/216/213 条 cert，
core size **min=2 / median=3 / p90=4 / max=4-5**，跨迭代形态完全稳定。
cert 合计 1294、落 cut 1293（差 1 = 一条未被采纳，方向保守；原因未定——
`_add_exact_persisted_nogood` 的失败面不止 dedup，序列化/attach/register
均可返回 false，当时的"dedup 拒重"推测撤回【04 审查 F-07 订正】）。
**thin fallback forbidden 触发 = 0 次**——真 prod 数据上每个空域 owner 都带
完整归因 cert（归因完备不变量的生产侧面验证）。certified 启动守卫对
`EXACT_B1_ROUTING_AWARE_BINDING=1` 放行（`815a73e` 收编的 prod 级验证）。

## §2 三个问题的答案

1. **EMPTY_DOMAIN 触发率**：每迭代 ~215 个 owner（占 266 实例的 ~81%）、
   6/6 迭代 100% 点火。counterfactual 在贪心基底上的 219/266 + core 2-7
   在真实 master 解上逐项复现（core 上界还略紧：≤5）。
2. **cert core 分布**：中位 3、p90 4——每条 cut 禁一个 {owner_pose+blocker_poses}
   组合族，对照旧 865-literal 整层 nogood（杀单点）小两个数量级，且全部
   经 F-BL-R11-01 结构守卫出证（零 fail-closed 跳过 = 零证书缺损）。
3. **master 吃细粒度 cut 的收敛行为**（诚实判读）：
   - **F-6 踏车被结构性绕开**：binding 枚举 0 轮——旧形态"binding 秒解→
     routing 拒→学 1 点→重来"的循环根本没转起来，学习单位从
     「~1 点/秒」变成「~215 族/次 master 重解」。
   - **但 6 迭代内无收敛迹象**：每轮 master 重解 ~510s 不降（fixed 单worker
     下重解成本 ≈ 冷解），每轮空域 owner 数稳定在 ~215 不减。master 在
     被禁组合外仍有海量"front 同样被堵"的等价替代解。
   - **结论边界**：本单发只证明通道工作正常 + 踏车被绕开，**不证明**
     迭代式 cut 学习能在可用时间内收敛到 6×6 anchor 的判定。

## §3 数据指向的下一步设计问题（owner 拍板项，不自启动）

每轮 ~215 个 owner 空域、逐轮换汤不换药——这个形态直接支持 round-3
（doc 13/14）的方向：**front-clear 必要条件上收 master**（build 期让 master
知道"被占 front 的 pose 组合不可行"，而不是每轮 510s 学一批再重解）。
迭代通道（本批已转正）与上收（未做，涉及 master 编码设计）是互补两级：
- 短期便宜杠杆：调 master 重解预算/worker 数、提高迭代帽换更长观测窗
  （余量判断注意：单 worker 同采样 RSS+swap 峰已 21.6G，且历史 w6 有
  41.6G+18.6G swap 非线性尖峰先例——多 worker 不能按单 worker 线性外推）；
- 结构杠杆：front-clear 约束进 master（新批次，soundness 论证可直接
  复用 01 文书的命题 N——同一必要条件，只是换了 enforcement 位置）。

## §4 诚实边界

- 单发、单锚点（6×6）、单配方（fixed/单worker）——收敛判断样本量=6 迭代，
  外推到其它 anchor/配方属推断。
- UNKNOWN 是迭代帽人为截断（fail-closed 正确方向），不是求解器判定。
- arm1 与 arm_rab 的 ortools 同为 9.15 线但非同日执行（间隔 2 天、
  中间落过 `815a73e` 批），A/B 的"唯一变量"以配方与代码面为准。
