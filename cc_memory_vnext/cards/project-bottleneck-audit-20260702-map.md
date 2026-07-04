---
id: project-bottleneck-audit-20260702-map
kind: reference
title: 2026-07-02 全项目瓶颈审计(12 条,逐条核实)已归档——读它先看时效对照;仓库备份现状(bundle×2+E: 副本,远端 main 停 07-01)
summary: 另一会话 37-agent 工作流对全项目做的「最终目标瓶颈」审计:8 维度×fable/codex 16 份报告 → 12 条瓶颈 → 逐条独立核查(VERDICT+file:line)。已归档 docs/research/project_bottleneck_audit_20260702/(main a91acc6),README 带逐条时效对照——**快照(07-02 深夜)早于 07-03 画线与 07-04 合并/通电批次,直接引用条目结论前必看对照表**。仍成立的硬骨头:算力硬墙(第一多米诺)、CP-SAT 编码忠实性单点(复验同构造器同库,无异构编码)、F1-F9 未接入、dependency floor manifest 占位、168h 执行层债、冻结输入只证「没变」不证「正确」、P1.2 手动门。已过时:seal 校验跳过+pr2-5 未合(6e06922 已合)、#7 通电缺口(349c56c 已通)、clean-review 无终止循环(07-03 画线)。
scope:
  domains:
    - roadmap
    - audit
    - backup
  paths:
    - docs/research/project_bottleneck_audit_20260702/README.md
  symbols: []
status: active
priority: P2
triggers:
  intents:
    - plan-next-work
    - project-risk-question
  keywords:
    - 瓶颈
    - bottleneck
    - 审计
    - 备份
    - bundle
    - 零冗余
    - 编码忠实性
    - dependency floor
    - 算力墙
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 项目最大的风险/瓶颈是什么
    - 仓库有没有备份/异地副本
    - 编码忠实性单点审过没有
activation:
  layer_hint: L1
  must_know: false
  reason: 谈项目风险/排期/备份时该想起:①有一份逐条核实过的 12 条瓶颈图,但快照过时,引用前必看 README 时效对照;②备份现状(见正文)——别再重复做已做过的 bundle,也别把远端 main 当最新。
provenance:
  op: record
  reason: owner 2026-07-05 把另一会话的瓶颈审计产物路径交来「看看这个」;triage+归档+备份后固化指针与事实。
  evidence:
    - "归档 main a91acc6(分支同内容 24c96ab,合并自动消解)"
    - "备份实测:zmd_git_backup_2026-07-05 bundle verify okay;E: 副本 hash 一致"
updated_at: "2026-07-05"
---
== 审计是什么、怎么读 ==
另一会话(5d3c7602)2026-07-02 深夜跑的 37-agent 工作流:8 维度(history/cert-chain/solver-math/gates/branches/release/tests/ops)× fable/codex 双模型独立阅读 → 合成 12 条「挡最终目标」瓶颈 → 每条由独立核查员回源码逐条验证(VERDICT: CONFIRMED/PARTLY + severity 复核 + file:line)。质量高、证据密,但**快照早于 07-03 owner 画线与 07-04 合并/通电批次**——归档 README(docs/research/project_bottleneck_audit_20260702/README.md)有逐条时效对照表,引用任何条目前先看它,别把已解决项(seal 校验跳过、#7 通电、clean-review 循环)当现状复述。

== 仍成立的硬骨头(2026-07-05 实测口径,按审计排序)==
1. 算力硬墙:全尺度 0 端到端 certified FEASIBLE、27 lever 全死、UNKNOWN=terminal stop;唯一没有已知工程路径的环节(B1 已证 master 单层可破,墙在 LBBD cut 收敛)。
2. CP-SAT 编码忠实性单点:I1/fixed-witness 复验与生产共用同一构造器+同一 CP-SAT 库,false-INFEASIBLE 方向同错同过;placement-local cut 甚至不过 I1(binding overload 侧 a731764 已补)。与 TNS v3 稿「禁共享 parser/异构复验 TCB 纪律」同根,PR2 #5 B2 独立枚举是同方向排期项。
3. F1-F9 未接入(step_8 仍 NotImplementedError)= P1.3 主体;F5 置换墙数学已由设计稿 v3 预先覆盖。
4. dependency floor manifest 是 dev/CI 占位字节,重生成只能在 CachyOS 生产机做(fail-closed 不静默,但是生产前硬前置)。
5. 168h 执行层债:48GB -p≥2 OOM vs watchdog 硬编码 -p4、无缓存全量 re-replay、墙钟含死亡时间、Windows wrapper 不默认 resume。
6. 冻结输入只证「没变」不证「正确」:pose 池枚举完整性零机制覆盖(「该有的 pose 在不在」没人检)。
7. P1.2 手动门 owner-only(设计如此)。
8. 文档漂移残留:PROJECT_LOCK §1A binding 锚 :930/:976/:1022 实际 +117 行,仍未修。

== 备份现状(2026-07-05 实测,别重复做/别误判)==
- 本仓库无 remote;GitHub 私有远端 zhuran24/zmd_pj 存在但 main 停在 07-01 推送(不含 6e06922 合并及之后全部工作);推送来自另一工作副本 C:\codex pj\zmd_pj。旧远端 zhuran24/zmd 已删。**要不要推送最新 main 是 owner 的决定,代理别擅自推。**
- 全分支 bundle:C:\Users\22957\zmd_git_backup_2026-07-05\zmd_pj_all_2026-07-05.bundle(verify okay)。
- 920-commit 原史料 bundle:C:\Users\22957\zmd_git_backup_2026-06-16\(README 引的 b35e5f9 等原机 hash 连它也解析不出,史料仲裁已断)。
- E:\zmd_backups\ 有以上两个 bundle + 审计完整产物集的第二物理盘副本(hash 校验一致)。
- 审计完整产物集(raw JSON/37-agent journal/工作流脚本/衍生摘要):C:\Users\22957\zmd_bottleneck_audit_20260702\。
