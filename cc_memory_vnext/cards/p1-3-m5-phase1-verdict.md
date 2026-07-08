---
id: p1-3-m5-phase1-verdict
kind: decision
title: P1.3 M5 第一阶段 verdict(2026-07-08):本机无法打开 attach 战场(<=3600s 无首解+automatic 组合原生崩);四层性能税诊断;A/B 转生产机窗口待 owner 拍板
summary: M5 收敛实测第一阶段收口。本机(Win11/24核/47.7GB)穷举配置空间(ghost 6-40/预算 90-3600s/w1-12/presolve 默认-diet-off/fixed-automatic/过滤-全 portfolio/ghost-aware 解锁)全部无法产出第一个 master 候选——LBBD 卡第 1 步,binding/routing 永不开审,attach 零触发。唯一理论出路(presolve 出头后 automatic portfolio)在本机 OR-Tools 上两发原生段错误(ortools.dll 0xC0000005 不同偏移)。四层性能税:①solve() 强制 probing/symmetry>=3 → 单线程 presolve 吃 500s+(branches=0 booleans=0 dtime~18.76 指纹,对模型规模强敏感——probing1 在 8x8 够用 6x6 又卡死);②presolve-off → 搜索立跑但 portfolio 塌缩单路(fixed 与 automatic+无过滤 branches 几乎一致 ~7.15M,restarts=0);③ghost-aware 修复机器被 anchor 限 64 整体跳过,解锁后重建出完整布局但 2s 验证 mini-solve 也卡 presolve → 32 个全假阴性 none_compatible;④MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX 砍掉 feasibility_pump/violation_ls(首解主力)。历史战场出土:data/solutions/cuts_6x6.json 5 条 whole-layout cut = 历史在 ghost 6x6 真实出过候选(机器/预算/master 版本未知,当前 coordinate_exact_v2 是 Phase 3C 重做)。结构不变量:266 设施占 3544/4900 格(72%),空格恒 1356,ghost 上限 ~36x36。
scope:
  domains:
    - p1-3-master-cut-integration
    - m5-convergence
    - master-performance
  paths:
    - docs/research/p1_3_m5_convergence_20260708/m5_phase1_verdict.md
    - docs/research/p1_3_m5_convergence_20260708/notes_phase1.md
    - docs/research/p1_3_m5_convergence_20260708/m5_cell_runner.py
    - src/models/master_model.py
    - src/models/cp_sat_worker_config.py
  symbols:
    - build_exact_candidate_warm_start
    - apply_master_cp_sat_subsolver_filter
    - MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX
status: active
priority: P0
triggers:
  intents:
    - run-m5-ab
    - solve-master-feasibility
    - tune-master-cp-sat
    - promote-cut-framework
  keywords:
    - M5
    - presolve
    - UNKNOWN
    - master 解不动
    - feasibility
    - 收敛实测
    - A/B
    - ortools 崩溃
    - 0xC0000005
    - EXACT_MASTER_CP_MODEL_PROBING_LEVEL
    - EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS
  negative_keywords: []
  paths:
    - docs/research/p1_3_m5_convergence_20260708/m5_cell_runner.py
  symbols:
    - apply_master_cp_sat_subsolver_filter
  error_regex:
    - "0xc0000409|0xc0000005|ucrtbase|ortools\\.dll"
  examples:
    - M5 A/B 什么时候能跑
    - master 为什么一直 UNKNOWN
    - presolve 卡死怎么办
activation:
  layer_hint: L1
  must_know: false
  reason: 任何重启 M5 A/B、调 master CP-SAT 参数、或诊断 master UNKNOWN/崩溃的会话都必须以本卡为起点,否则会重走 4 小时诊断老路或重蹈并发 OOM/崩溃组合。
provenance:
  op: record
  reason: 2026-07-08 M5 第一阶段实测收口,verdict 与全部数据进库(commits 204119b/4985b72/d9c0ca6/+定稿)。
  evidence:
    - "verdict 定稿: docs/research/p1_3_m5_convergence_20260708/m5_phase1_verdict.md(配置穷举表+四层税+资源方案四选项推荐 3+4)"
    - "13 个 cell 原始 JSON: results_smoke/ + results_scan/;两探针: probes/"
    - "崩溃 WER: ortools.dll 0xC0000005 两发(偏移 0x7ae290/0x80e689),ucrtbase 0xC0000409 两发(P2/P4 并发 OOM)"
  updated_at: "2026-07-08"
---

M5 第一阶段(可行性侦察)2026-07-08 收口。核心结论与四层税见 summary;完整材料 `docs/research/p1_3_m5_convergence_20260708/`。

== 后续会话操作纪律(硬教训) ==

- **master solve 串行铁律**:两个 prod-scale master 并发 solve = 47.7GB 吃穿 → ucrtbase abort(0xC0000409)双杀。一次只跑一个,分离进程+日志+Monitor。
- **危险组合勿碰**:6x6(prod-scale 大模型)+ automatic branching + presolve-on(含 diet)在本机 OR-Tools 原生段错误(ortools.dll 0xC0000005);带 `EXACT_SUBPROBLEM_MAX_MEMORY_MB` 也崩。
- harness 全部旋钮见 `m5_cell_runner.py --help`(白名单 env 7 个 + 测量专用 `--no-subsolver-filter` monkeypatch——绝非 certified 旋钮)。
- 电脑重启会杀分离进程:重启后先查 `scan_progress.log` done 行 + 结果 JSON 是否落盘,再决定重挂(脚本都在 `$env:TEMP\m5_*.ps1`,会话 Temp 目录可能被清,必要时从本卡+verdict 重构)。

== 挂 owner 的拍板(不阻塞) ==

- **A/B 实测资源方案**(verdict §资源方案):推荐 3+4(M5 第一阶段按实测收口+四层税诊断反哺生产,A/B 挂 Linux 生产机窗口);选项 2(本机过夜)胜率低不推荐。
- 升格决定(M4 三前置只剩它)不受影响——M5 是效果计量非正确性验收,attach 链正确性由 M4 测试+等价回归背书。

== 四层税的生产复核线索(反哺项,归 P1.3/P1.21 性能债) ==

1. `master_model.py:11527,11533` 强制 probing/symmetry>=3 —— 冷启动首解场景的 presolve 黑洞;但可能是 Phase 3C 按「有 incumbent 增量求解」调的,复核要分场景。
2. `EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS=64` 使 ghost-aware warm-start 对一切现实 ghost 失效;its 验证 profile 无旋钮(空 profile=CP-SAT 默认),唯二 env = VALIDATION_SECONDS/MAX_ANCHORS。
3. `MASTER_IGNORE_SUBSOLVERS_FOR_MAX_LEX` 含 feasibility_pump/violation_ls——对首解反向优化;复核时与 Windows OR-Tools 稳定性问题分开评估。
4. 生产 wrapper 不设任何以上 env——生产靠 EXACT_PARALLEL_PROCESSES 多 ghost 并行 + >=24h 硬磨。
