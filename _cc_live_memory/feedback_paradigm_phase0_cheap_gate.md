---
name: paradigm-phase0-cheap-gate
index_summary: "新 paradigm 实施前必走 Phase 0 (≤1h cheap gate) 验前提, GO 后再投 Phase 1."
description: "paradigm 实施 workflow — Phase 0 必是 cheap gate (≤ 1h) 验证 paradigm 前提, GO 后再投资 Phase 1 真 implement. 避免大投资后才发现 paradigm 前提不满足"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**Rule**: 任何新 paradigm 实施分 Phase, **Phase 0 必是 cheap gate** (≤ 1h Claude
pace) 验证 paradigm 前提是否成立. GO 后才投资 Phase 1+ 真 implement.

**Why**:
- RAB-SEP Phase 0 monkey-patch PoC 30 min 验 binding domain filter 工作 (213 empty owners)
- SAC-Hull Phase 0 oracle 30 min 验 22 violations
- PCR-CUT Phase 0 oracle 30 min 验 patch coverage 98% SAC
- 三次 paradigm 都 Phase 0 ≤ 30 min 出 GO/NO-GO verdict

如果直接跳 Phase 1 (真 implement, 几百 LOC, 几 hour), 发现前提不满足才回头 —
浪费 6-10h Claude work.

**How to apply**:
- 新 paradigm 实施前**写 Phase 0 PoC**:
  - monkey-patch / standalone script
  - 不动 production code
  - 验证 paradigm 关键数学/资源前提
  - 30 min - 1h Claude work
- Phase 0 GO 标准要**明确量化** (e.g. "覆盖率 ≥ 70%, 资源 ≤ 阈值, wall ≤ Xs")
- Phase 0 NO-GO 时**接受 verdict**, 不强行 implement Phase 1
- Phase 0 GO 后 Phase 1 真 implement, 仍带 Phase 0 标定的资源 bound 作 abort condition

**Phase structure 模板**:
```
Phase 0: cheap gate (≤ 1h) — paradigm 前提验证
Phase 1: production land (4-8h) — 真 implement, 资源 bound abort
Phase 2: soundness gate (2-3h) — replay validate / proof object
Phase 3+: optimization + integration
Phase N: multi-anchor verdict campaign
```

**反例** (没做 Phase 0 直接 Phase 1):
- Path 08 路线 1 (master 持 port-selection) 直接写 v1/v2/v3 4 form, 后才发现
  333K vars / 867K constraints UNKNOWN. 如果 Phase 0 oracle 先估 vars 数, 不
  会浪费 4 form 实施时间.

**适用**:
- 新 paradigm review (GPT 给的)
- 内部 brainstorm 出的方向
- 大 LOC (≥ 300 LOC) 实施前必走 Phase 0

**不适用**:
- bug fix / refactor (没 paradigm 前提)
- 小 feature (< 100 LOC) — 直接写就比写 Phase 0 快

**Related**:
- [[work-time-estimates]] — 工时按 Claude pace 估
- [[research-roi-metric]] — 节约时间 ÷ 投入时间
- [[avoid-micro-optimization-spiral]] — < 5% 占比 停手换方向
