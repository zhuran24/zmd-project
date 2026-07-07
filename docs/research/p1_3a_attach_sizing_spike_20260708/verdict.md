# P1.3A attach sizing spike — verdict（2026-07-08）

**判决：GO（增量 attach 形态可行），带两个硬性工程前置。**
本 spike 只回答"可以按什么形态开始做 step_8 / P1.3 主体"，**不**表示 P1.3
主体完成、不解禁任何 PROJECT_LOCK 边界、不证明 cut 体系接入后收敛
（收敛是 M5 / roadmap 1c 的实测命题）。

## 0. spike 是什么、替代了什么

roadmap 1c 要求的 P1.3A spike（GO 判据 = prod-scale 跑通 + wall-clock 退化
<50%，见 `docs/项目说明/09_phase_1_3_plan.md`）。2026-05 的旧 spike 设计
（`docs/research/prod_scale_spike_design_20260525/MERGER.md`，收窄成
sizing-only）**从未实施**，且针对已被换掉的 PoseBoolExactMaster（81K
BoolVar）；本 spike 在现役 CoordinateExactMasterDelegate 上重建了全部
sizing 数字。测量脚本与原始输出在本目录（`m1_*.py` / `raw_v*.jsonl`）。

测量口径：真生产入口（`load_project_data` → `build_exact_core` →
`from_exact_core` → `add_benders_cut` → `solve(60s)`），合成 cut 负载
（pattern 型 8-literal，组内不重复采样贴生产解形态），单进程，
Windows 48GB 本机。solve 侧绝对值偏保守：生产第 1 轮带完整 greedy
warm-start hint（`build_exact_candidate_warm_start`），本 spike 裸跑。

## 1. 实测数字

### 1a. 0-cut 基线（coordinate_exact_v2）

| 量 | 值 |
|---|---|
| build_exact_core | 38.9s，64,103 var / 108,024 constr |
| from_exact_core 克隆 | 26.8s (8×8) / 35.7s (12×10) / 53.6s (20×16) |
| RSS | 2.4GB（core）/ +0.5-0.7GB per clone |
| 生产 master solve 预算 | 60s/轮（`master_model.py:11424` 默认；LBBD 传 `master_seconds`）|

### 1b. pattern 型 cut 注入挡位（8 literal/条，ghost 12×10，全部 attach 成功）

| 累计 cut | add 成本 | solve python wall | solver 内部 wall | **劈叉（proto 传输等开销）** | RSS |
|---|---|---|---|---|---|
| 0 | — | 68.7s | 66.0s | 2.8s | 3.0GB |
| 100 | 66.7 ms/条 | 82.3s | 78.8s | 3.5s | 3.1GB |
| 1,000 | 94.3 ms/条 | 74.5s | 65.8s | 8.7s | 3.9GB |
| 5,000 | 116.9 ms/条 | 155.5s | 85.1s | 70.5s | 7.8GB |
| 10,000 | 252.0 ms/条 | 327.3s | 95.3s | **232.0s** | 12.2GB |

- add 累计成本到 10K 条 ≈ 30 分钟；成本曲线超线性（66→252ms/条）。
- **劈叉列是核心发现**：python↔C++ 边界的 model proto 序列化/传输随模型膨胀
  超线性增长，10K cut 时每次 solve 白付 232s（0-cut 的 83 倍）。
- RSS ≈ 0.9MB/条（裸实现）。
- solver 内部 wall 超 60s time limit（10K 时 95s）：CP-SAT 的 time limit 在
  presolve 阶段控制粒度粗，大模型下超限放大。

### 1c. 作废/污染的数据点（记录以防误用）

- v1 whole 型 99.99% attach 被拒：合成负载让同 group 对称 instance 撞同
  pose_idx，触发 `_conflict_pose_entries` 的 alias fail-closed（刻意纪律，
  `exact_coordinate_master.py:6977-6988` 注释明写）。生产真实解不会发生。
  v2 改组内不放回采样后 15,000/15,000 全部成功。
- v2 whole 型 0-cut solve 1073s：pattern 场景 10K-cut model `del` 后内存未
  即时回收（RSS 13.9GB 起跑），整机逼近 swap，该数据点量的是内存压力不是
  solve 成本，**无效**。whole 型（266 literal/条）的干净每条成本未测得，
  按 literal 比例外推 ≈ 2-8s/条；生产 whole-layout nogood 每 attempt 只有
  个位数条，非瓶颈，补测非阻塞。

## 2. 根因（源码坐实）

1. **presence literal 零复用**：`_pose_present_literal`
   （`exact_coordinate_master.py:6949-6975`）每条 cut 每个 pose 都
   `NewBoolVar` + N 条 `AddImplication` + 1 条 `AddBoolOr`，变量名携带每条
   cut 唯一的 `cut_tag`——同一 (slot_set, pose_tuple) 在不同 cut 间完全
   重建。add 成本、RSS、proto 膨胀（进而 solve 劈叉）三者同源于此。
   生产现状无恙（whole-layout nogood 每 attempt 个位数条），F1-F9 接入后
   cut 上千即为灾难。
2. **每轮 solve 全量传 proto**：现生产形态"增量 add + 每轮新 CpSolver"
   意味着每轮 solve 都重付整个 model proto 的跨边界成本，与 cut 累积量
   成超线性。

## 3. GO 的两个硬性工程前置（step_8 形态输入）

1. **content-addressed presence literal 复用**：以 (slot 集合标识,
   pose_tuple) 为 key 的 literal 缓存，把 `cut_tag` 从 literal 身份中解耦
   （tag 只留 telemetry）。alias fail-closed 纪律不变——复用是"同 key 同
   literal"，与"同条 cut 内两成员撞同 literal 必拒"正交。预期把 add 成本
   与 proto 膨胀降一个量级（8-literal cut 在窄 pose 域下 literal 复用率
   极高）。落点：M3 实现 step_8 时一并做进 coordinate delegate，带
   before/after 复测。
2. **active cut 总量预算**：裸实现下 solve 劈叉在 ~2.5-3K cut 处越过
   60s 预算的 50% 退化线。attach 进 master 的活跃 cut 集合必须有总量
   预算（千级起步），配 CutStore 的 held/eviction 机制（原 P1.5+ 的
   eviction 至少要最简版提前到 M4 F5 接线批，与 F5 telemetry 的
   10^5 撞墙 / 10^3 工作阈值配合）。literal 复用落地后复测，再决定预算
   能否放宽到 10K+。

## 4. 三条 PoC 路线的裁决（09 号计划 §P1.3A）

| 路线 | 裁决 |
|---|---|
| sub-route 1 solve-rebuild（实际=现生产增量 add 形态） | **主路线 GO**。09 号"每轮 rebuild model"的假设与现实不符：生产是 per-attempt build + 轮内增量 `add_benders_cut`（含 witness 失效），API 已被 whole-layout nogood 生产验证。 |
| sub-route 3 hard-constraint rebuild | 不需单独 PoC。重建成本已知（core 38.9s + clone 27-54s），是增量形态的天然退路；step_8 接口留 rebuild 模式开关即可。 |
| sub-route 2 C++ propagator hook | 维持 defer（≥1 周投资，且 python 侧瓶颈在 proto 边界不在 propagator）。 |

## 5. 对大计划的其余输入

- **09 号 §12.2 的 hot-path 优化清单要重排序**：本 spike 证明第一瓶颈是
  literal/proto 层（python↔C++ 边界），不是 evaluate 热路径；evaluate
  优化仍归 M5。
- **内存预算**：裸实现 0.9MB/条 × 并行 worker 数在 4-worker 下 10K cut
  ≈ +36GB，不可行；literal 复用后重估。生产已有
  `EXACT_SUBPROBLEM_MAX_MEMORY_MB` / gate RSS 参数，M3 接线时 cut 侧
  内存要纳入同一预算体系。
- **同进程连续 model 的内存滞留**（§1c 第二条）：`del` 后 proto/求解器
  内存不即时回收。生产 worker 进程连续跑多个 task 有同样暴露面——M3
  接线批检查 worker 的 model 生命周期与显式回收。
- solve time limit 的 presolve 粒度问题：大模型下 60s 预算实际可能跑
  95s+，M5 收敛实测时 wall-clock 统计要按实测 wall 不按预算值。

## 6. 边界声明

- spike GO ≠ P1.3 主体完成、≠ 收敛保证、≠ 解禁 27 lever paradigm 边界。
- 未测：真 binding/routing subproblem 下的 LBBD 多轮动态、multi-worker、
  168h 累积、whole 型干净每条成本、warm-start hint 下的 solve 绝对值。
- 全部测量为旁路只读脚本，未改任何生产文件、未触 sealed 面。
