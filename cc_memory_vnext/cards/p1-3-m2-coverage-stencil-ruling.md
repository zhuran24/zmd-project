---
id: p1-3-m2-coverage-stencil-ruling
kind: decision
title: owner 拍板(2026-07-08):F1-F9 cut helper 覆盖语义统一到 12×12 square stencil(弃欧氏)——M2 语义前置的核心裁定
summary: P1.3 M2(F7/F8 coverage reconcile + canonical→geometry 统一)的 owner 裁定,2026-07-08 owner 原话「选方形」。内容:F7(power_hitting_set)/F8(power_grid_reach)及全体 F1-F9 helper 的供电覆盖几何统一到 certified 主链现役的 12×12 square coverage stencil,覆盖谓词=相交(承接 owner 2026-07-07 相交裁定);helper 现存的欧氏 cell-distance/Liang-Barsky/AABB 覆盖判定退役,不得再作任何 certified 语义来源。后果:①F7/F8 的 helper/oracle/validator/cert payload 换 stencil 谓词,补 helper-vs-master 判定一致性回归测试后方可进 certified/attach;②形式化 F8 定理(P3.0 轴 A 等待项)由此解锁;③若某处保留欧氏实现只能作 non-certified 遥测且必须显式标注。裁定理由:游戏真实规则=正方形(主链已按其冻结认证),欧氏是早期 helper 直觉实现,无数学收益;选欧氏则 F7/F8 永久出局 certified、电力不可行只能靠 whole-layout nogood 兜底。实施按 M2 盘点清单(改动面盘点 agent 进行中,落地后在此补指针)。
scope:
  domains:
    - p1-3-master-cut-integration
    - cut-framework
    - power-coverage-semantics
  paths:
    - src/cuts/helpers/power_network.py
    - src/cuts/families/power_hitting_set.py
    - src/cuts/families/power_grid_reach.py
    - src/cuts/oracles/power_cover_oracle.py
    - src/cuts/oracles/power_grid_reach_oracle.py
  symbols: []
status: active
priority: P0
triggers:
  intents:
    - implement-m2-reconcile
    - wire-f7-f8
    - formalize-f8
    - modify-power-coverage
  keywords:
    - stencil
    - 12x12
    - 欧氏
    - coverage
    - 覆盖语义
    - F7
    - F8
    - power_hitting_set
    - power_grid_reach
    - reconcile
  negative_keywords: []
  paths:
    - src/cuts/helpers/power_network.py
  symbols: []
  error_regex: []
  examples:
    - F7/F8 的覆盖模型用哪个
    - stencil 还是欧氏
    - 形式化 F8 什么时候解锁
activation:
  layer_hint: L1
  must_know: false
  reason: M2 实施与 M4 F7/F8 接线批、形式化 F8 都必须按此裁定;不知道会沿用 helper 现存欧氏语义=直接重新埋雷(false-INFEASIBLE cut 错杀合法布局的 soundness 洞)。
provenance:
  op: record
  reason: 2026-07-08 owner 在 M1 verdict=GO 交付后、听取两模型差异讲解(方形 vs 圆形边角一圈判定相反、错杀=soundness 洞)后拍板「选方形」。真实 owner 输入,非推导。
  evidence:
    - "owner 原话(2026-07-08):「嗯,选方形」。"
    - "背景:soundness_gap_roadmap.md:21 canonical→geometry 语义半=P1.3-before-F1-F9 前置;docs/research/p3_0b_family_formalizability_survey_20260705/ f7/f8 文档标 landmine;PROJECT_LOCK 相关条款(F7/F8 footprint SoT fail-closed)。"
    - "承接裁定:供电覆盖谓词=相交(owner 2026-07-07,见 commit fdbf98c 所记)。"
  updated_at: "2026-07-08"
---

2026-07-08 owner 拍板:**F1-F9 cut helper 的覆盖几何统一到 12×12 square stencil,弃欧氏**。

== 裁定内容 ==

- 唯一覆盖语义 source-of-truth = certified 主链现役的 12×12 square coverage stencil,谓词=相交(设施 footprint 与 stencil 有交集即覆盖,承接 07-07 裁定)。
- F7/F8 helper/oracle/validator/cert 的欧氏 cell-distance、Liang-Barsky 线段裁剪、AABB 判定全部退役;任何保留的欧氏代码只能是显式标注的 non-certified 遥测。
- F7/F8 attach 进 certified master 的前置 = 换谓词完成 + helper-vs-master 判定一致性回归测试在位。
- 全体 F1-F9 helper 的其余自有几何原语(覆盖/方向/相邻/footprint)同批盘点统一(canonical→geometry 语义半的完整履行,不只 F7/F8)。

== 直接后果 ==

1. M2 可以全速实施(盘点清单出来即列小计划动手)。
2. 形式化 F8(P3.0 轴 A 的等待项)解锁——Lean 侧 CoverSet/graph reach 按 stencil 语义陈述。
3. M4 的 F7/F8 接线批以本裁定为验收前提之一。

== 为什么(留给后人) ==

游戏真实规则就是正方形(主链按其冻结、已过认证链);欧氏是 helper 早期直觉实现。两形状边角一圈格子判定相反→helper 按圆产 cut 会错杀主链视角合法(甚至最优)的布局=false-INFEASIBLE soundness 洞,这正是穷尽性证明最怕的洞型。「选欧氏」无任何数学收益,只省一批改码钱,代价是电力两 family 永久出局。
