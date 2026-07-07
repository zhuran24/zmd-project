---
id: p1-3-m2-coverage-stencil-ruling
kind: decision
title: owner 双拍板(2026-07-08):①F1-F9 覆盖语义统一 12×12 stencil(弃欧氏,批 A 已落地);②电杆不需连电网(协议核心自动无线连)→F8 前提为假、retired-false-premise、物理删除搭 M3 车
summary: P1.3 M2(F7/F8 coverage reconcile + canonical→geometry 统一)的两项 owner 裁定(2026-07-08)。裁定②(批 B):owner 玩家确认「电线杆不需要连电网,协议核心自动连上它们」→F8 power_grid_reach 整个 family 的数学前提为假=retired-false-premise(非改几何);主链六谓词无洞(从未要求电杆连通);F7 前提仍真;F8 物理删除搭 M3 reseal 车,当前先退役标注;形式化 F8 取消。裁定①(批 A,原文):内容:F7(power_hitting_set)/F8(power_grid_reach)及全体 F1-F9 helper 的供电覆盖几何统一到 certified 主链现役的 12×12 square coverage stencil,覆盖谓词=相交(承接 owner 2026-07-07 相交裁定);helper 现存的欧氏 cell-distance/Liang-Barsky/AABB 覆盖判定退役,不得再作任何 certified 语义来源。后果:①F7/F8 的 helper/oracle/validator/cert payload 换 stencil 谓词,补 helper-vs-master 判定一致性回归测试后方可进 certified/attach;②形式化 F8 定理(P3.0 轴 A 等待项)由此解锁;③若某处保留欧氏实现只能作 non-certified 遥测且必须显式标注。裁定理由:游戏真实规则=正方形(主链已按其冻结认证),欧氏是早期 helper 直觉实现,无数学收益;选欧氏则 F7/F8 永久出局 certified、电力不可行只能靠 whole-layout nogood 兜底。实施按 M2 盘点清单(改动面盘点 agent 进行中,落地后在此补指针)。
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
    - "owner 原话(2026-07-08):「嗯,选方形」;批 B:「那些电线杆是不需要连电网的。或者说,在基地内,协议核心会自动连上它们」。"
    - "F8 假前提史料链(codex 查证 2026-07-08,防复活):前提源自 Gemini round 14 构造反例(gemini_round_14_cut_families.md:43-67),round 15 建议独立成族;从无游戏规则引用;Gemini round 5 曾明确质疑(canonical 无 pole-to-pole 字段,p1_2b_f8_power_grid_reach_gemini_round5_20260525/),当时被「接受为 Phase 1.2 简化」搁置——教训:外审接受≠游戏规则确认,规则问题必须问 owner。"
    - "主链 coverage-only 确认:master_model.py:4881-4910 约束=sum(coverer poles)>=facility_selected,无 BFS/component/core-source;protocol_core needs_power:false 且不参与供电语义(pr2_l0_artifact_core.py:984-999 只认 power_pole 为覆盖者)。"
    - "owner 追加确认(2026-07-08):协议核心(=基地核心,9×9 最大单位)不会直接给周围设施供电——主链供电谓词(设施须被电杆 stencil 覆盖)与游戏规则完全一致,不松不严:电杆是唯一供电者、放下即生效。供电覆盖谓词的忠实性自此有 owner 玩家确认背书,该语义面无遗留悬念。"
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

== 落地进度 ==

- **批 A 已落地(2026-07-08,commit 03c7f4e)**:CoverSet helper 换 stencil(Chebyshev/矩形,与 gen_power_pole 逐字同构)、oracle 版本 bump(power_cover_v2_stencil / power_grid_reach_v2_coverset_stencil)、19 条等价回归(test_helpers_power_cover_stencil.py,含方圆差异带 case)、F8 混合状态标注、survey 文档 banner。注意 power_cover_oracle.py 在 PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS 钉面,本批已走一轮 reseal(V99 dict+obligations JSON+checker 自钉)——「src/cuts 不触 sealed」的旧认知是错的,见 [[p1-3-kickoff-recon-facts]] 更正段。
- **批 B 已由 owner 游戏规则确认关闭(2026-07-08)**:owner 原话「那些电线杆是不需要连电网的。或者说,在基地内,协议核心会自动连上它们」——**F8 power_grid_reach 的数学前提(电杆须经 pole-jump 链连通 protocol_core 才供电)为假**。游戏规则=电杆放下即自动无线连核心。处置:①F8 定性为 retired-false-premise,不是改几何而是退役;②certified 主链无洞(六谓词只要求设施被 stencil 覆盖,从未要求电杆连通,与游戏规则一致);③F7 前提仍真(它就是主链覆盖谓词的 cut 化),批 A 修的几何继续有效;④物理删除 F8(cert_schema/lifecycle family map/replay dispatch 都在 reseal 钉面)**搭 M3 的 reseal 车**,现阶段先做退役标注(oracle/family/helper docstring+文档终态化,这些文件不在钉面零 reseal);⑤形式化 F8(P3.0 轴 A 等待项)取消而非解锁,要知会形式化线。
- **批 C-1 已落地(2026-07-08,commit c4326f1)**:DIRECTION_OFFSETS N/S 对齐 canonical(旧表对真实工件彻底错误——全量 599,384 port 实测,N/S 的 front cell 旧表下全落进设施体内;oracle/validator 共享错表自洽+测试全用 E/W 双层掩盖);port_exposure_v2_canonical_dirs;3 条 N/S 钉子测试。F2/F4 确认不受影响(无标签 4-邻接,无方向标签语义)。
- **批 C-2 待做**:F1/F6/F9 几何原语的 SoT 对照测试(region/baseline/window 是 family 私有数学对象不必统一,但 occupied_cells/canonical dims 消费点补对照钉子)。

== 直接后果 ==

1. M2 可以全速实施(盘点清单出来即列小计划动手)。
2. 形式化 F8(P3.0 轴 A 的等待项)解锁——Lean 侧 CoverSet/graph reach 按 stencil 语义陈述。
3. M4 的 F7/F8 接线批以本裁定为验收前提之一。

== 为什么(留给后人) ==

游戏真实规则就是正方形(主链按其冻结、已过认证链);欧氏是 helper 早期直觉实现。两形状边角一圈格子判定相反→helper 按圆产 cut 会错杀主链视角合法(甚至最优)的布局=false-INFEASIBLE soundness 洞,这正是穷尽性证明最怕的洞型。「选欧氏」无任何数学收益,只省一批改码钱,代价是电力两 family 永久出局。
