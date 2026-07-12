---
id: p1-3-m6-power-encoding-diagnosis
kind: decision
title: M6 诊断终报(2026-07-09):master 首解之墙=供电覆盖约束及其 witness 编码(八实验隔离,单一主墙);盲打包解全部供电不可行;修复方向 A 编码手术/B power-aware 构造挂 owner
summary: owner 立项「首解为何这么难」诊断,四路 Fable 侦察+八个隔离判决实验收口。**诊断:供电一关任何形态秒/分钟级可解(钉死 2-5s OPTIMAL;自由+6×6 全 4225 锚 110s OPTIMAL);供电一开任何形态溺死(钉死/自由/单锚/无 ghost 全 UNKNOWN,百万分支+0.1% 冲突率无引导形态)——打包规模/ghost 析取/anchor 多重性/种子/求解器参数全部无辜。**机制:witness 式供电编码(几何 element+763 自由杆槽)传播反推力≈0,与打包耦合搜索学不到可泛化子句;布局钉死+火力下供电子模型可判定(94-333s INFEASIBLE 证明)。副产物:①盲打包解全灭(greedy×3+CP-SAT 最优×1 全部供电不可行)→天真两阶段死刑,构造启发式必须 power-aware;②供电可行布局存在性 OPEN(从未产出一份,亦无不可行证明);③(0,0) 角锚 187s 可证不可行(疑边线端口容量,F1/F6 cut 价值+1);④冗余双 no_overlap_2d 出土(core-only 版被 ghost overlay 组合版包含,最重传播器×2 浪费,低风险修复项);⑤钉死验证管线打通(presolve-off+火力 profile,分钟级判决任意候选布局)。考古辅证:witness 编码 prod-scale 有史以来零 FEASIBLE(原机 24h campaign 检查点实证);B1 pose-bool 线性供电编码同类题 53s OPTIMAL(34×);「历史解出过 6×6」考证为缩减问题(72 机+599 杆旧工件时代)不构成反例。修复方向呈 owner:A=供电编码手术(witness→线性 x≤Σcoverers,reseal 量级,双证据背书);B=power-aware 构造启发式(不碰 sealed,产物走钉死验证管线,命中即首解+战场开);C=顺手修双 no_overlap_2d。M5 A/B 挂 A/B 任一落地后。
scope:
  domains:
    - p1-3-master-cut-integration
    - m6-diagnosis
    - master-performance
    - power-encoding
  paths:
    - docs/research/p1_3_m6_diagnosis_20260709/07_final_diagnosis.md
    - src/models/exact_coordinate_master.py
    - src/models/master_model.py
  symbols:
    - _validate_coordinate_forced_hint
    - build_exact_core
    - skip_power_coverage
status: superseded
priority: P0
triggers:
  intents:
    - fix-power-encoding
    - build-power-aware-constructor
    - run-m5-ab
    - solve-master-feasibility
  keywords:
    - 供电编码
    - witness
    - 首解
    - power coverage
    - M6
    - 诊断
    - skip_power_coverage
    - ghost_anchor_filter
    - 两阶段
  negative_keywords: []
  paths:
    - docs/research/p1_3_m6_diagnosis_20260709/07_final_diagnosis.md
  symbols:
    - skip_power_coverage
  error_regex: []
  examples:
    - master 为什么解不出来
    - 供电编码怎么修
    - M5 什么时候能跑
activation:
  layer_hint: L1
  must_know: false
  reason: 任何 master 性能/首解/供电编码/M5 解锁相关工作必须以本卡为起点;不知道「供电是单一主墙+盲打包死刑」会重走两天弯路或设计出错误的修复。
provenance:
  op: record
  reason: 2026-07-09 M6 诊断课题收口(owner 立项,四路 Fable 侦察+八实验)。
  evidence:
    - "终报: docs/research/p1_3_m6_diagnosis_20260709/07_final_diagnosis.md(证据链表+机制+修复分级);01-04 侦察报告;m6*.py/json 全部脚本与判决数据"
    - "关键判决: M6b-A 钉死无供电 3/3 OPTIMAL 2.6-5.3s vs M6b-B 同布局有供电 INFEASIBLE 94.5s;M6d 自由无供电全锚 OPTIMAL 110s vs M6f 自由有供电无 ghost UNKNOWN 905s"
  updated_at: "2026-07-09"
---
> **Superseded 2026-07-12(修复批 β/文档实态外审 F10/F11)**:当前态见 `p1-3-batch1-m5-current-20260712`。本卡仅作批次/历史证据保留,不再参与 active recall;正文中的「当前状态/待办/OPEN」段落均为当时快照,勿再据此行动。


M6 诊断课题（owner 2026-07-09 立项）终报见 summary 与 `docs/research/p1_3_m6_diagnosis_20260709/07_final_diagnosis.md`。

== 后续工作的硬前提 ==

- **任何构造启发式必须 power-aware**（盲打包解 4/4 全灭）；验收走已打通的钉死验证管线（`_validate_coordinate_forced_hint` + presolve-off 火力 profile，分钟级判决）。
- 供电可行布局存在性 OPEN——修复 A/B 的任何一个也同时服务「证明不存在」方向。
- 消融/诊断用的全部开关（skip_power_coverage/ghost_anchor_filter/EXACT_USE_POSE_BOOL_MASTER 等）在 certified unsafe-map，**只用于测量诊断，严禁回流 certified 路径**。
- (0,0) 角锚 INFEASIBLE 是 exact-safe 信号：角落锚吃边线格 → 边线端口容量一票否决——F6/F1 类 cut 能提前剪这类 anchor（cut framework 价值论证素材）。
