# v14 — P3 Design B Architecture Stress Test (2026-05-21)

## 包目的

项目 (Arknights: Endfield 70×70 工业规划器 certified exact solver) 经过 27 个
lever paradigm investigation 全 verdict 死后, 决定走 **P3 Design B** — 自研一
个 feature-level cut engine, 不是继续在通用 CP-SAT solver 加 cut.

这个包提交给独立审稿做 **architecture stress test**: 你的任务是尝试**构造一
个 "恶魔构型"** (devil's configuration), 使得 Design B 的 5 类 cut 无法将其
剪枝. 如果你能构造出来, 说明 B core 不完备; 如果你确信构造不出来, 说明 5 类
cut 在所选 facility geometry 下足够 cover.

包**没有**项目历史 transcript / 之前外审 verdict / Claude 主对话内容. 包内每
个 doc 都是 standalone — 即使你之前完全没接触过本项目, 也能从包里读完所有
背景跟决策依据. 任何依据 abstract / claim 的判断, 请 cross-reference 包内
源码 (`shared_infra/full_source.tar.xz` 含项目当前 src snapshot).

## 包结构

```
v14_p3_b_design_review/
├── README.md                                ← 你正在读
├── 00_PROJECT_OVERVIEW/
│   ├── two_layer_architecture.md            ← outer (candidate enumeration) + inner (LBBD) 架构
│   ├── 266_mandatory_breakdown.md           ← facility type 分布 + perimeter constraint
│   └── PROJECT_LOCK_constraints.md          ← certified_exact + 48 GB + 168h 硬约束
├── 01_PARADIGM_HISTORY/
│   ├── 27_lever_deaths_summary.md           ← 死法 5 大类 + 共同 root cause
│   ├── cand_c_phase_0_1_2_v3_verdicts.md    ← cand C 实测数据 (5/20/40/80/160/266 ramp)
│   └── geometric_deadlock_data.md           ← 96% 利用率几何死结 + boundary_storage_port × perimeter trap
├── 02_DESIGN_CANDIDATES/
│   ├── design_a_cand_c_plus_cuts.md         ← 设计 A: cand C + cut language
│   ├── design_b_feature_level_engine.md     ← 设计 B: 自研 master state machine + cut store + 5 cut family + proof lifecycle
│   └── B_vs_A_tradeoff.md                   ← B 严格 stronger 论证 (项目方判断, 仍欢迎 GPT 反驳)
├── 03_B_DESIGN_DETAILS/
│   ├── master_state_machine.md              ← state schema + trail + undo
│   ├── cut_object_lifecycle.md              ← 6 step: generate→serialize→deserialize→validate→resolve→replay→regression
│   ├── 5_cut_family_definitions.md          ← region capacity / cutset / port exposure / component / pattern no-good / symmetry-lifted
│   ├── bitset_kernel_options.md             ← Rust pyo3 vs C++ pybind11 vs numpy
│   └── reuse_from_cand_c.md                 ← Phase 2 v3 + B1/PCR-CUT/D2/SMT-MT 复用清单
├── 04_KNOWN_UNSOLVED_ISSUES/
│   ├── boundary_port_perimeter_trap.md      ← 46 boundary_port × 3 cells / 276 perimeter cells
│   ├── manufacturing_cluster_trap.md        ← 132 个 manufacturing_3x3 最大类潜在 trap
│   ├── m10_sound_cross_scale.md             ← A3 set covering 在 80 inst sound 性临界
│   └── 96_pct_utilization_death.md          ← 几何根因
└── shared_infra/
    └── full_source.tar.xz                   ← 项目 src/ snapshot (复用上一包 snapshot, 同 git commit 5469885)
```

(独立 prompt 文件不在包内, 由用户单独发到 GPT 窗口.)

## 读包建议

1. 先读 **README.md (此文档)** + **00_PROJECT_OVERVIEW/** 3 个 → 拿 problem 全景
2. 读 **01_PARADIGM_HISTORY/** 3 个 → 理解 27 lever 死法 + cand C 实测 + 几何死结
3. 读 **02_DESIGN_CANDIDATES/** 3 个 → 理解 A vs B 的选择依据
4. 读 **03_B_DESIGN_DETAILS/** 5 个 → 你要 stress test 的具体设计在这
5. 读 **04_KNOWN_UNSOLVED_ISSUES/** 4 个 → 项目自己识别的潜在 trap, 这些是
   你构造 "恶魔构型" 的 candidate 起点
6. 解压 `shared_infra/full_source.tar.xz`, 至少浏览 `src/models/pose_bool_exact_master.py`
   + `src/search/benders_loop.py` + `src/models/binding_subproblem.py` 三份核心
   code (其中前两份各 47K / 268K 行, binding 37K)

## Prior context (来自项目主对话历史, 不在 zip 内)

- 项目用 Gemini fat-context 做过两轮独立审稿, 都 verdict 推 **Design B 严格 stronger** (具体 verdict 内容**不**在此包内, 防止过度污染你的判断). Gemini 推 10 day preparation plan, 其中 Work Item 1.1 就是 "GPT 做 architecture stress test" — 即此包.
- 项目方判断 cand C (column generation, Design A 路径) 已穷尽现有 cut language
  可调空间: Phase 2 v3 实测 80 inst m10 整数解 False, 160/266 inst RMP 0 iter
  INFEASIBLE. 详见 `01_PARADIGM_HISTORY/cand_c_phase_0_1_2_v3_verdicts.md`.
- **不**接受 heuristic / ε 松弛 / 概率算法. PROJECT_LOCK 要求 certified_exact.

## Stress test 任务摘要

详细任务在**独立 prompt 文件** (用户单独发, 不在 zip 内). 简化:

1. 读完所有包内 md + 至少浏览 shared_infra src
2. **任务核心**: 构造恶魔构型 — 即 facility 配置 + ghost rectangle candidate
   使得 B core 5 类 cut 无法剪枝
   - 构造不成: 论证为什么 5 类 cut 完备 (要给数学论证, 不是 "我觉得")
3. 评估 B core architecture 各组件
4. 复用清单 (Phase 2 v3 + 死路 paradigm) 是否合理
5. 给 implementation phase plan (3-5 月 timescale)

## 包外参考

- 项目主仓 git commit `5469885` (2026-05-20, 跟此包 src snapshot 对齐)
- shared_infra 含 full_source.tar.xz (src/ 全 snapshot)
  via symlink (zip 时会 deref 成 real file).
