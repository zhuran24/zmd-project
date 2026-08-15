# 11 — 认证链依赖图

> 本页只描述稳定依赖关系，不保存阶段完成度、owner 决定值、cut-family 当前成员或
> backlog 状态。唯一现态投影见 [`../CURRENT.md`](../CURRENT.md)，claim、decision 与
> dossier 关系见 [`../CATALOG.md`](../CATALOG.md)。知识脊柱启用前的原文保存在
> [`../history/status/11_dependency_graph_pre_knowledge_spine_20260811.md`](../history/status/11_dependency_graph_pre_knowledge_spine_20260811.md)。

## 11.1 候选求解依赖

```text
canonical rules + preprocess plan + hash-bound exact inputs
  -> placement master
  -> binding
  -> exact routing + selected-graph connectivity guard
  -> power / terminal whole-layout checks
  -> internal candidate verdict
```

`src/models/flow_subproblem.py` 是旁路诊断器，不是 certified acceptance gate。whole-layout
proof-bearing elimination 只有经过 `src/search/independent_infeasibility_reverifier.py` 的
独立复验，才可进入 exact-safe 证据链。

## 11.2 Campaign authority 依赖

```text
candidate records
  -> strict frontier exhaustion
  -> outer_search commits CANDIDATE_PROPOSED
       + terminal frontier evidence
       + sink replay request
       + fixed-witness material
  -> scripts/run_supervisor_seal.py
  -> ExactCampaign.supervisor_seal()
       + canonical disk reread
       + source/input currentness checks
       + sink replay
       + fixed-witness verification
       + pre/post disk currentness
  -> durable terminal CERTIFIED checkpoint
```

producer、caller-memory payload、内部 candidate verdict 或 proposal marker 都不能替代
supervisor seal。

## 11.3 Public publication 依赖

```text
supervisor-sealed campaign
  + valid terminal evidence
  + current exact input/source closure
  + owner-controlled publish gate
  -> publish_verified_certified_delivery_surface()
  -> final_solution.json
  -> optimal_blueprint.json
  -> certified_delivery_manifest.json
  -> full surface re-verification
```

owner gate 的当前值只读机器 gate 与 [`../CURRENT.md`](../CURRENT.md)。gate 允许进入下一阶段
不等于已有可发布结果；测试、receipt、seal 或 checker PASS 也不能自动推出 release。
serializer、adapter、viewer、report 与 compatibility export 只能生成非权威派生物。

## 11.4 Cut 与研究依赖

```text
research observation / counterexample / paper proof
  -> stable claim or dossier
  -> explicit authority review
  -> optional research-ledger effect
  -> separate production admission and owner promotion, when applicable
```

cut family 的 validator、lowering、shadow、retired、attach 与 promotion 是不同状态维度。
当前矩阵与 B6 决定只查 [`../CATALOG.md`](../CATALOG.md)，不能从历史计划、一次 PASS 或
“active”一词反推 production admission。

## 11.5 状态与计划分离

- “现在是什么”：[`../CURRENT.md`](../CURRENT.md)
- “为什么相信”：[`../CATALOG.md`](../CATALOG.md) 中的 claim、decision 与 evidence
- “接下来做什么”：[`ROADMAP.md`](ROADMAP.md)
- “稳定方法怎么用”：[`REASONING_METHOD.md`](REASONING_METHOD.md)
- “事件何时发生”：[`HISTORY.md`](HISTORY.md)
- “迁移前文档当时怎么说”：[`../history/status/`](../history/status/)
