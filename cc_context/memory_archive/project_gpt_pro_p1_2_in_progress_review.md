---
name: gpt-pro-p1-2-in-progress-review
description: "2026-05-24 GPT pro P1.2 in-progress review (Phase 1.1 GO 后, F2/F4 generator land 后): 9 action verdict. 主线 ✅, F5 orbit-aware + F9 fixture + mini Step 8 spike 是 3 个未确认 audit. 立刻 land sound ≠ converge 警句 + dark matter telemetry 硬闸 + cut store 评分淘汰."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-24 GPT pro 收到 Phase 1.1 final polish v12 review pkg 后, **接着** 又给了 P1.2 in-progress 大段 review (9 section). 主要看本地状态 188 cuts pass / mypy strict / exit_criteria 0 FAIL, 提醒 Phase 1.1 闭环 ≠ 168h 必收敛.

## 核心结论 (我同意)

主线**不换**, 当前数学工具链方向 (OR-Tools CP-SAT + LBBD 外循环 + 自写 cut / cert / replay / validator) 是项目目前最合理选择. PB / RoundingSat / SCIP-PB 可做 Phase 1.5+ cheap-gate sidecar 不主线重写. Lean / Coq 太早.

## 9 条 action item verdict (我的 evaluation)

### ✅ 同意 + 立刻 land (3 条)

1. **"sound ≠ converge" 降温段** — `docs/项目说明/06_current_status.md` 已加. 任何"唯一可走 paradigm" / "最终数学工具"类措辞**降温**为"目前证据下最值得继续推进的主线; 收敛性仍需 ramp 数据确认".
2. **dark matter telemetry 硬闸** — 连续 N 次 unexplained infeasible (cut family 都 sound 但 master 仍卡) 不写日志就完, 必触发 family 设计复盘 (是不是补 F10 / 强化 F2/F4 / 承认 9 family 不够). 落地 Phase 1.3 telemetry plan §X.
3. **cut store 评分 / 淘汰策略** — sound cut 越多越好的天真假设错; cut 多 → CP-SAT propagation/rebuild/memory 慢. Phase 1.5+ cut store rotation/GC 必加分 (frequency hit + age + family rarity). 已跟 [[proof-object-lifecycle]] memory 一致, 但要硬门槛.

### ⚠️ 同意但**时机要重新讨论** (3 条 audit task)

4. **F5 orbit-aware / multiset lift audit** — F5 已 land + 3 round GO_WITH_MINOR. multiset anonymity 在 `lifecycle.py state_machine_v2 §5` 已 cover (frozenset equality, slot_index 不进 soundness). 但 "132 个同类 manufacturing instance 的 orbit-aware lift" GPT 担心退化成 cut 垃圾场. **审计任务**: 写一个 132 同 group 的 fixture 验 F5 cut 是不是一次只锁单实例还是全 orbit, ratio telemetry.
5. **F9 non-trivial envelope fixture audit** — F9 已 land 9-phase validator + area-only invariant. GPT 担心 `max_allowed_area` 退化成 F1 的复述 (每 cell 最多 1 facility). **审计任务**: 写"比 F1 更紧"的 fixture (e.g. 5x5 W, F1 上限 25 facility, F9 area_capacity 上限 < 25 才有意义).
6. **mini Step 8 spike 时机** — GPT 建议提前到 F6/F7/F8 之间或之前. 我选 **F6 完后做** — 理由: F5 + F9 + F2/F4 + F6 已覆盖 4 大 family 形态 (literal-based / area-based / edge-cut / hall-marriage), spike 看这 4 种能不能一致接 master 比 9 种全完再发现接不进风险小. F7/F8 在 spike 之后再做.

### 📝 已实施 (基于过时 state) (2 条)

7. **F2/F4 generator 提前** — 2026-05-24 已 land (commit `92224c4` → `01d368a` → `d5e653d` 3 Gemini round close GO_WITH_MINOR). Dinic node-split helper + 2 oracle + 7 regression test. GPT review 写时 generator 还是 stub.
8. **F9 先 proof 再实现** — 已实施 (5 commit + 5 Gemini round incl R3 wrong patch revert). area-only invariant + safe_ub static formula + 9-phase validator. proof 在 `cut_family_specs/09_density_envelope.md` + `MATHEMATICAL_FOUNDATIONS.md §3`.

### ❌ 我不完全同意 (1 条)

9. **"所有 family shadow → true attach"** — 同意 shadow 习惯好, 但 F1/F3 已 attach (Phase 1.1 land). 全员强 shadow 等于回退 P1.1. 更合理: **新 family (F2/F4/F5/F6/F7/F8/F9) Phase 1.2 默认 shadow, Phase 1.3 ramp 前分批 true attach**. 这跟 `docs/项目说明/09_phase_1_3_plan.md` (跟) 已 align, 不是新闸.

## 立刻 land 状态 (2026-05-24 session 末)

- ✅ Sound ≠ converge 警句 (06_current_status.md)
- ✅ 本 memory (9 verdict 钉住)
- ✅ Audit task TODO 加 Task list (action 4/5/6)
- ⏸ dark matter telemetry 硬闸 + cut store 评分 → Phase 1.3 plan doc 加 (defer)

## Refs
- [[phase-1-2-progress]] — Phase 1.2 全 7 family 已 close (本 review 写于 2026-05-24, 当时 F6/F7/F8 尚待启; 现均 Gemini GO close, 已进 P1.3A)
- [[design-phase-n-parallel-agents]] — N=5 子代理 protocol (启 F6 前)
- [[gemini-review-algorithm-math]] v4 — Gemini per-commit cross-check
- `docs/项目说明/06_current_status.md` — sound ≠ converge 段落
