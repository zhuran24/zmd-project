# v12 Paradigm Search Review (with code) — 2026-05-20

## 包目的

项目在 CP-SAT + LBBD framework 内 24 lever 全 verdict 死之后, 调研了 32 个 paradigm 方向看是否有现成可调用的 algorithm 范式能 break. 4 个候选方向仍 alive, 其余 NO-GO. 包整理这些调研结果 + 24 lever 历史实施 + 共享 production code + 当前对 problem 瓶颈的理解, 提交 review.

## 包结构

```
v12_paradigm_search_review_with_code/
├── README.md                                   ← 你正在读
├── 01_PROJECT_STATE.md                         ← 项目当前完整状态 + 当前候选 list
├── 02_LEVER_HISTORY_24_DEAD.md                 ← 24 lever 累积 verdict (高层 timeline)
├── 03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md    ← 瓶颈理解 5 阶段演变
├── alive_candidates/                           ← 4 个还 alive 候选 (每个文件夹 README + paper)
│   ├── lever_25_ihs/                          ← Implicit Hitting Set (AAAI 2026)
│   ├── lever_26_benders_symmetry/             ← Benders symmetry framework (arxiv 2511.22251)
│   ├── candidate_a_cdcl_warmstart/            ← Hybrid CDCL + CP-SAT (arxiv 2512.18034)
│   └── candidate_c_column_generation/         ← Column gen (远期备选)
├── dead_paths/                                 ← 24 个已死 lever, 每个一文件夹 (README + code/)
│   ├── L01_to_L10_coordinate_master_era/      ← 早期 coordinate master 工程优化
│   ├── L12_v8_anchor_slicing/                 ← GPT v8 算法错估
│   ├── L13_v10_witness_preflight/             ← GPT v10 前提错估
│   ├── L14_weighted_occupancy/                ← GPT 加料后数学能力上限
│   ├── L15_setpacking_prover/                 ← GPT paradigm 攻错层
│   ├── L16_lazy_power_completion/             ← master 端 OK cut 端 instance-level 不够
│   ├── B1_paradigm_pose_bool_master/          ← B1 paradigm 真 GO (master form 切换)
│   ├── B1_phase4_routing_convergence/         ← B1 内 LBBD 上层 routing cut 不收敛
│   ├── B1_phase5_cell_cut/                    ← 3 种 cut form 全 over-restrictive
│   ├── B1_phase6_path1_master_port_selection/ ← master 持 port-selection 不可解
│   ├── B1_phase6_path2_lazy_demand_cut/       ← lazy demand cut 10 iter 不收敛
│   ├── path12_rab_sep/                        ← Routing-Aware Binding Separator
│   ├── path13_sac_hull/                       ← Separator-Aware Capacity Hull
│   ├── path14_pcr_cut/                        ← Patch-Certified Routing Conflict Core
│   ├── path15_pgw_ub/                         ← Positive Global Witness + UB Closure
│   ├── path16_goc_c2/                         ← Global Optional-Owner C2 Core
│   ├── path17_d2_subproblem/                  ← D2 Commodity Cell-Flow (sub-problem 路径)
│   └── L23_augmented_master_candidate_d/      ← Augmented master Candidate D (today)
├── investigated_paradigm_groups/               ← 32 paradigm 调研 NO-GO (没真实施)
│   ├── group_a_solver_families.md              ← Choco/Gecode/MZ/Z3/Picat/clingo/SCIP/LCG
│   ├── group_b_decomposition.md                ← CG/Lagrangian/Modern Benders/DDs
│   ├── group_c_cut_bound.md                    ← Lift-and-project/PBO/MaxSAT/Reformulation
│   ├── group_d_layout_geometry.md              ← VLSI/2D BPP/MER/geost/Symmetry
│   ├── group_e_applied.md                      ← Factory game/Quantum-inspired
│   └── group_f_2026_extra.md                   ← 2026-01~05 window 校验补充
└── shared_infra/                               ← 跨 lever 共享 production code
    ├── README.md
    ├── src/models/                             ← pose_bool_exact_master / master_model / d2_commodity_flow_core / etc
    ├── src/search/                             ← benders_loop / d2_separator
    ├── docs/lever_verdicts.md                  ← 24 lever 源 truth
    ├── PROJECT_LOCK.md                         ← 项目硬约束
    └── CLAUDE.md                               ← 项目 instructions
```

(提问 list 是**独立 prompt 文件**, 跟此 zip 包分开发送, 不在包内. 请先一字不落读完包里所有文件, 然后看独立 prompt 文件作答.)

## 重要说明

请**一字不落读完所有文件**, 然后看独立的 prompt 文件回答问题. 包里所有 paradigm 描述都基于 2026-05-20 校验完成的状态.

## 读包建议

1. 先读 **README.md (此文档)** 跟 **01_PROJECT_STATE.md** 拿 problem 全景
2. 读 **02_LEVER_HISTORY_24_DEAD.md** 跟 **03_BOTTLENECK_UNDERSTANDING_EVOLUTION.md** 理解 timeline + 瓶颈认知演变
3. 读 **alive_candidates/** 每个 (4 个文件夹) — README + paper
4. 读 **dead_paths/** 每个 (18 个文件夹) — 每个 README 简短, 关键 detail 在 `code/` 子目录
5. 读 **investigated_paradigm_groups/** 6 个 group 文件
6. 读 **shared_infra/** README + 至少 4 个核心 file (`master_model.py` + `pose_bool_exact_master.py` + `benders_loop.py` + `binding_subproblem.py`)
7. **最后**看独立 prompt 文件回答问题

未读完前不要开始回答. **任何依据 abstract / paper 内容的判断必须 cross-reference paper 原文**.

## 包外参考

- 项目主仓 git commit `5469885` (2026-05-20 上午 L23 verdict)
- 之前 review 包 v3 ~ v11 (GPT 历次 paradigm review, 不在此包)
