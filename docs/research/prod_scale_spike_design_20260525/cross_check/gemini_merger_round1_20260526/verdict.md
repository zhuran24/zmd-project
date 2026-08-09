# Gemini 3 Pro cross-check verdict — Prod-scale spike MERGER (Round 1)

**Date**: 2026-05-26
**Model**: `gemini-3-pro-preview` (resolved from listed catalog; the `gemini-3-pro` alias in memory `reference_gemini_math_consultant.md` returns 404)
**Token usage**: prompt 5695 / response 2607 / thoughts 2640 / total 10942
**Source files**:
- prompt: `prompt.txt`
- request: `request.json`
- raw JSON: `gemini_response_raw.json`
- text reply: `gemini_response.md`

---

## 1. Gemini overall verdict

**NOT_GO**

理由 (Gemini 原话): "Spike 选取的 LBBD 收敛指标 (G15: search tree node 单调减) 在 OR-Tools CP-SAT 的 portfolio search 与 presolve 机制下数学上不成立, 且抛弃 100K cut scale 测试将直接在 168h prod run 中触发 OOM/超时盲区, 必须修正这两大基石才能启动."

---

## 2. Finding count by severity

| Severity | Count | IDs |
|---|---|---|
| BLOCKER | 1 | F1 (G15 单调减 metric 数学不成立 + stub 设计漏 Benders 动力学) |
| HIGH | 3 | F2 (砍 100K cut blind spot), F3 (50 inst probe 5-10 min cap 过松), F6 (5 iter 不足以触发 LBBD phase transition) |
| MEDIUM | 2 | F4 (G3 60s 过松, 容忍 SWIG 反模式), F5 (2 PR 重写 fidelity gap 无机制保证) |
| LOW | 0 | — |

Plus:
- **C6 missing-risk** 3 项 (CP-SAT threading non-determinism / cut staleness purge / source_digest invalidation 跨 candidate)
- **C7 residual P1.3A risk** 3 项 (sub-problem cut structure gap / inner subprob timeout 策略 / "optimal but unprovable" trap)

---

## 3. 3-sentence main finding summary

1. **G15 是数学错的 metric**: Gemini 论证 CP-SAT 加 cut 后 presolve 会重排 variable substitution + root dual bound, search tree node count 不单调甚至会激增 (反例: cut 触发更短 infeasibility path 时 wall-time 减但 node count 增) — 必须换成 dual bound improvement / multi-iter wall-time 收敛性 metric; 同时 stub 必须读 master current assignment 产 targeted no-good 才能模拟 Benders 真动力学.
2. **砍 100K cut 是 168h 致命盲区**: Gemini 用 168h / 60s/iter ≈ 10,000 iter × 10 cut/iter ≈ 100K cut 累积量化 + OR-Tools protobuf arena 在 50K→100K 越 L3 cache boundary 容易触发超线性 RSS (撞 L24 30 GB 死法) 论证, 必须恢复 100K 挡位.
3. **5 iter LBBD 完全 cover 不到 phase transition**: 前 5 iter 切的都是 trivial infeasibility, iter 7+ 才进 marginal cut 区域 presolver 开始失效 (L16 + B1 path-2 死在 10 iter UNPROVEN), Gemini 建议 ≥15 iter 才能观察 iter 10-15 solve time variance.

---

## 4. Agent (Claude) 自评 sanity check — Gemini finding vs 8 路 sibling blind spot

**核心问题**: Gemini 这些 finding 是真新 (8 路 sibling 没 cover), 还是已经 cover 但 merger 折掉了?

### F1 (G15 单调减 metric + stub 设计) — **真新 finding, 严重**

- 8 路 sibling 检查: correctness §1.3 + integration §1 都强调 step 8 + multi-iter, throughput §1.1 提了 `cut_translate_p99_us` 但没提 node count 非单调性. **none** of 8 路 explicitly 论证 CP-SAT presolve 重排导致 node count 不单调.
- Merger §6 blind spot #4 自承 "没真懂 OR-Tools 9.15 CP-SAT internals" → 正好被 Gemini fingerpoint.
- Merger §6 blind spot #3 自承 stub fidelity 风险, mitigation 是 "G15 看 search tree node 趋势不看具体 verdict" → 但 G15 metric 本身错, 这个 mitigation 自相矛盾.
- **判定**: BLOCKER 真. 必须 fix 才进 spike 实施.

### F2 (100K cut 盲区) — **半新, sibling 有 hint 但 merger 折掉**

- throughput slant §1.1 原 propose 100K (10K/50K/100K), correctness slant 反对 100K (50K 已极限), merger D5 取 correctness 立场.
- Gemini 用 168h/60s ≈ 10K iter × 10 cut/iter ≈ 100K 量化论证 — 这个 168h 反推 throughput slant 没明确写, **simplicity** 完全没碰, **historical-paradigm** L24 30 GB 引用 + cut staleness 也没量化.
- merger §3 unique 表 throughput "3 filter ablation" 全 defer P1.3A, 但 cut count ramp 上限取舍没量化论证.
- **判定**: HIGH 真. throughput slant 原立场被 Gemini 量化加固, merger 折取错.

### F3 (50 inst probe 5-10 min cap) — **真新**

- D1 resolve "工时 +1h" 只算 implementation, 没量 probe 自身 timeout 阈值.
- simplicity slant 原 propose 50 inst subset 是替代主路径, 没量 probe timeout.
- mini Step 8 baseline 10K cut @ 50 BoolVar = 114ms build + 2ms solve, Gemini 推 50 inst probe 全 lifecycle ≤ 5s 合理, 给 5-10 min 多 60-120x margin — 这个量化 8 路都没做.
- **判定**: HIGH 真. trivial fix (timeout 15s) 立刻可加.

### F4 (G3 60s 过松) — **半新, sibling 有量但论证角度不同**

- throughput §1.1 给 G3 build wall ≤ 6000ms @ 10K, correctness 给 ≤ 60000ms (60s), merger 取 correctness 立场.
- Gemini 用 10K cut × 100 boolean terms = 10^6 terms × OR-Tools C++ vectorized 1-2s 论证 60s 容忍 10-30x margin, 容忍 Python for 循环逐条 `model.Add()` 反模式 — 这个反模式角度 8 路没提.
- throughput 立场被 Gemini 加固 (6s @ 10K vs merger 60s).
- **判定**: MEDIUM 真, 但收紧到 15s 可能过激 (Gemini 没考虑 Python 9 family translator dispatch overhead). 建议 ≤ 20-30s.

### F5 (2 PR 重写 fidelity gap) — **真新**

- rollback-safety §1.1 propose 2 PR 不 cherry-pick, 但没说重写后怎么保 spike validated 性能特征不丢.
- 没任何 slant 提 protobuf checksum / hash compare 机制保 fidelity.
- Gemini 类比 L13 hidden assumption 死法 — 比喻贴切.
- **判定**: MEDIUM 真. fix (protobuf checksum) 实施 cost 低.

### F6 (5 iter LBBD 不足) — **半新, historical slant L16 / B1 path-2 cover 类似但没量化 phase transition**

- historical-paradigm slant L16 / B1 path-2 死法引用是 10 iter UNPROVEN, 但 merger 取 5 iter (integration G8 + correctness 合).
- Gemini 论证 "iter 7+ 才进 marginal cut presolver 失效区" — phase transition 概念 8 路没用.
- merger D3 折中是 "5 iter × 3 candidate = 15 master.solve" (跨 candidate 算 15 个), Gemini 立场是单 candidate 内 iter 深度 ≥ 15.
- **判定**: HIGH 真. 5 iter 跟 L16 / B1 path-2 历史死法对不上, 应至少 10 iter (sweep 拉 spike wall 1-2h 仍 acceptable per 7-day cap).

### C6 missing risks — **3 项都真新, 8 路确实没 cover**

1. **CP-SAT threading non-determinism**: 8 路完全没碰 thread-safety / model.Clear() race. Gemini 提的是 G13 adversarial quarantine 在多线程 cut add 下交错可能 abort — 这是 spike 真要 single-worker 排除还是要 cover risk 的设计决策, 现 merger §5.3 NOT-scope 已 "Multi-process/multi-worker (spike single worker)", 算 risk-managed 但应文档化.
2. **Cut staleness / purge**: 8 路提了 "active filter" (LRU/Score/Hybrid) 是过滤逻辑, 但没明确 cut purge 机制 (purge ≠ filter, purge 是物理删, filter 是逻辑屏蔽). 168h 累积 cut RSS 是 Gemini 用 100K cut 锚定的 derived risk.
3. **Source_digest invalidation 跨 candidate**: 这个 Gemini 提得最深 — outer search 切 candidate 时 source_digest 不变 (因为 canonical_rules + preprocessed 不变), 但 ghost_id 变, store cache 需 invalidate. 8 路 sibling 完全没碰跨 candidate 的 store state transition. **这条 missing risk 最该进 spike scope**.

### C7 residual P1.3A risk — **全新, 8 路只 cover 到 spike 边界, 没 forecast spike GO 后剩下啥**

- Sub-problem cut structure gap (stub vs real binding/routing) — merger §6 #3 blind spot 自承但没 mitigate
- Inner subprob timeout 策略 — 8 路 0 提
- "Optimal but unprovable" trap (找到 max_lex 但 proof 剩余 candidate infeasibility 168h 不够) — 8 路 0 提, 但这其实是 P1.3A 主体甚至 P1.3B 的 risk, spike scope 内 cover 不现实, 应入 P1.3A risk register

---

## 5. 推荐主对话下一步

按 finding severity 分流:

### 必须做才能进 spike 实施 (BLOCKER + 2 HIGH)
1. **F1 (BLOCKER)**: 改 MERGER §5.4 G15 metric — 删 "search tree node 单调减 ≥30%", 改 "dual bound improvement per iter ≥ X%" 或 "multi-iter wall-time 收敛". 同时 D3 stub 设计加 "stub 必须读 master current assignment 产 targeted no-good (sum(chosen)<=len-1) 切当前解", 不能返 fixed verdict.
2. **F2 (HIGH)**: 改 MERGER §5.2 cut count ramp 恢复 100K — `1K / 10K / 50K / 100K`, G8 RSS ≤ 20 GB 必须在 100K 挡位验. 工时增 1-2h CP-SAT wall (100K 比 50K 多~50-100s).
3. **F6 (HIGH)**: 改 MERGER §5.2 multi-iter LBBD ≥ 15 iter (替 5 iter × 3 candidate). 工时增 1-2h wall.

### 应做但可批量 (1 HIGH + 2 MEDIUM)
4. **F3 (HIGH)**: 加 MERGER §5.4 G_probe = "50 inst probe wall ≤ 15s, 超时 abort". trivial 1 行加.
5. **F4 (MEDIUM)**: 收紧 G3 build wall ≤ 30s (折中, 不取 Gemini 15s 因 9 family translator dispatch overhead 未量).
6. **F5 (MEDIUM)**: 加 MERGER §5.1 2 PR 流程要求 "PR #2 P1.3A 实施 integration test 必须 emit 同结构 cp_model protobuf, hash compare spike verdict 的 baseline protobuf hash".

### 必入 spike scope (C6 missing risk)
7. **新加 G16 跨 candidate source_digest invalidation**: spike 3 candidate 切换时 verify store cache 真清空, ghost_id 真切, source_digest 真重新 emit (即便 byte-equal).

### 入 P1.3A risk register (C7 residual)
8. 主对话写 P1.3A 入口 doc 加 "spike 已验 / spike 没验" 两栏 risk register, sub-problem stub fidelity / inner timeout 策略 / proof early-stopping 全显式入 "spike 没验".

### Cross-check 回路
9. **不接受 spike 实施前 NOT_GO** — per [[gemini-review-algorithm-math]] v4 + [[design-phase-n-parallel-agents]] §7, MERGER 改完后再发 Gemini round 2 验 fix effective. 若 round 2 GO_WITH_MINOR 或 GO, 才进 spike 实施.

---

## 6. 主对话备注

- Gemini 没 push back 的决策 (隐含 GO): C1 81K BoolVar 全量主路径 / C5 2 PR 流程 paradigm (只 push back fidelity 机制) / C7 spike GO ≠ paradigm GO 的边界
- Gemini 自承 epistemic posture: "合理严谨但对 CP-SAT 内部机制过度自信"
- 没有 ritual GO — 6 finding 全 severe 且引证具体 (CP-SAT presolve / Laurent Perron 文献 / 168h 反推算术 / 10^6 terms 复杂度), 符合 audit 模式而非夸傻
- 此 round 跟 [[adversarial-soundness-audit]] Layer 2 (假 cert pass 类) 不同, Gemini 主攻 Layer 2 的 paradigm 死法预测 (G15 = 跟 v8 同 metric 错配), 是 Gemini 在算法层最强的视角
