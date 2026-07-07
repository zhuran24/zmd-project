# 11 — 当前认证链依赖图

> 本文描述 2026-06-26 工作树。历史 cut-family 计划的依赖关系见 `docs/research/`，不能覆盖
> 当前 producer/supervisor/publisher 与 owner gate 边界。

## 11.1 候选求解依赖

```text
canonical rules + preprocess plan + hash-bound artifacts
  -> placement master
  -> binding
  -> exact routing + selected-graph connectivity guard
  -> power / terminal whole-layout checks
  -> internal RUN_STATUS_CERTIFIED candidate verdict
```

`src/models/flow_subproblem.py` 是旁路连续 LP 诊断器。它不位于 certified acceptance 的
必经 gate 上，`INFEASIBLE`/`UNKNOWN` 也不能单独产生 proof-bearing elimination。

whole-layout persisted nogood 只有通过
`src/search/independent_infeasibility_reverifier.py` 的独立复验，才可进入当前证据链。

## 11.2 Campaign authority 依赖

```text
candidate records
  -> strict frontier exhaustion
  -> outer_search commits CANDIDATE_PROPOSED
       + terminal frontier evidence
       + sink replay request
       + fixed-witness capsule/material
  -> scripts/run_supervisor_seal.py（生产 supervisor 入口，独立命令、marker 驱动，不由 main.py 顺手执行）
  -> ExactCampaign.supervisor_seal()
       + canonical disk reread
       + current hash check
       + sink replay
       + fixed-witness verification
       + pre/post disk currentness
  -> durable terminal CERTIFIED checkpoint
```

producer 不能跳过 supervisor。内部 candidate `CERTIFIED`、proposal marker 或 caller-memory
payload 都不能替代 supervisor seal。

## 11.3 Public publication 依赖

```text
supervisor-sealed campaign
  + valid terminal evidence
  + current exact bytes/source closure
  + owner-closed P1.2 publish gate
  -> publish_verified_certified_delivery_surface()
  -> final_solution.json
  -> optimal_blueprint.json
  -> certified_delivery_manifest.json
  -> full surface re-verification
```

当前 owner gate 为 `blocked_manual_review_count`，所以 public publication 应 fail closed。
serializer、adapter、viewer、report 和 compatibility export 只能生成非权威派生物。

## 11.4 P1.2 open-work dependency

```text
PR1 publication-boundary hardening                IMPLEMENTED in worktree
fixed-witness + independent whole-layout replay   IMPLEMENTED in worktree
publish-open gate + central publisher             IMPLEMENTED in worktree
PR2 controlled/read-once verifier TCB              OPEN
review package immutable commit materialization   IMPLEMENTED in worktree
archive/review policy completeness                 PARTIAL
owner manual close decision                        BLOCKED
```

这些条件不能互相替代。机器 checker 通过不等于 owner gate 关闭；owner 决定也不能替代技术
证据和同一工作树验证。

## 11.5 Future cut-family integration

`src/cuts/` 的 F1–F9、lifecycle 与 Step 8 production master integration 属于后续 P1.3
人类命名阶段。当前它们不能被写成已接入默认 certified master，也不能借用 flow diagnostic
或历史 review pass 证明 P1.2 已闭。
