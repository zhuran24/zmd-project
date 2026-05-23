# 14 — 风险评估 + mitigation + rollout policy

defer / 已知 risk + 失败回滚策略.

### 14.1 GPT pro v5 verdict 排序 (最先爆 → 后)

1. **source_digest placeholder** — Phase 1.2 §10.3 必修
   - mitigation: hash 真 file content + replay 时验证 + cross-session test
   - rollback: 退到 placeholder, production 不 ship

2. **strict default 0** — Phase 1.2 §10.1 必修
   - mitigation: F5-F9 实施每加 1 family 加 register + missing-validator test
   - rollback: env override 显式 strict=0 (dev only)

3. **F2 commodity_demand registry** — Step M+N 已 partial close
   - mitigation: registry schema 评估 (Phase 1.5+ §13.2)
   - rollback: 暂时 F2 oracle stub 不 emit

4. **HR5 GHOST_AGNOSTIC exterior_blocks invalidate watcher** — Phase 1.3 §12.3
   - mitigation: Step F evaluate 重算保 sound, watcher 是 efficiency
   - rollback: Phase 1.3 没 propagator 集成时不需要

5. **HR1 thread-safe** — Phase 1.3+ §12.4 评估
   - mitigation: 现 CP-SAT propagator 单线程
   - rollback: multi-thread 时 cache invalidate 跨 worker

6. **HR3 free-placement / HR4 non-rect ghost** — Phase 1.5+ 真生产 data
   pattern 出现时再决策

### 14.2 Phase 1.2/1.3 实施风险

- **F5 deletion+QuickXplain perf**: NP-hard. mitigation 限 ≤ N literal
- **F6 Hall theorem 实施复杂**: mitigation 先 greedy 后 LP
- **F7 power hitting-set NP-hard**: mitigation LP relax 近似
- **F8 ghost_rect tuple 反惯例 bug**: mitigation Phase 1.2 §10.4 lock 必先
- **F9 density sound 边界**: mitigation 加 negative test
- **Phase 1.3 lazy → hard constraint master 性能**: mitigation 阶梯启用 (F1
  单 family 跑通后 F2-F9)
- **propagator hot path perf**: mitigation parsed cert cache + incremental
  BFS + watcher 三件套 (Step H TODO)

### 14.3 rollout / migration policy

cut framework 从 Phase 1.1 (4 family 单测) → 1.2 (5 family 加) → 1.3 (真接 benders_loop 主流程) → 1.5+ (production 168h campaign 含 cut store) 是渐进, 每阶段切换政策:

**Phase 1.1 → 1.2 切换 (strict gate default ON, Phase 1.2 first commit)**
- 切换点: §10.1 `EXACT_FAMILY_VALIDATOR_STRICT` 默认 `"0"→"1"` 是 Phase 1.2 **first commit**, 不是 5 family 都加完才开
- 理由: Phase 1.2 加 F5-F9 时, 新 family 在 strict gate 下若 dispatch 表漏注册会立刻 fail-closed → 不会沉默漏 cut. 5 family 全加完才开 = 漏注册的 family 沉默通过 4-5 commit, 等回头加 strict 测时已经堆 5 commit debug 难.
- revert criterion: 若 strict ON 后真生产 trial 30 min 内 ≥ 1% cut 被 schema_err reject 且非 spec drift → 临时 OFF + 排查 schema 跟 src 的 drift, 不是 framework bug
- revert 方法: 单 commit revert `EXACT_FAMILY_VALIDATOR_STRICT` default (env 一行改), 不影响其他

**Phase 1.2 → 1.3 切换 (cut framework 接进 benders_loop)**
- 切换点: §13 P1.21 step_8 apply_to_master 真集成 master.AddLinear 时, env-gated 默认 OFF
- 渐进 ramp:
  - Phase 1.3 first commit: env-gated 默认 OFF, unit test 在 mock master 上验
  - 1 candidate trial OFF baseline + ON enable 各 1 次, 对比 outcome
  - 24h shadow trial (env ON 但 cut 不真 attach, telemetry-only) → 看 §20 metric (cut count / valid rate / replay reject rate)
  - 24h half-trial (env ON + cut 真 attach + telemetry full) → metric 健康 + outcome 不退化 → GO 168h
- revert criterion: 真生产 168h trial 出现 (a) 168h-campaign-time wall-clock ≥ baseline + 20% / (b) outcome FEASIBLE → INFEASIBLE 反向 / (c) telemetry replay reject rate ≥ 5% → 立刻 env OFF + 单 commit revert master integration line
- revert 方法: env OFF 即可瞬时 disable; 不需要 git revert (framework 仍在 src/, 只是 master 不调用)

**Phase 1.3 → 1.5+ 切换 (production integration, commodity registry 真接 data pipeline)**
- 切换点: §13.1 commodity_demands / commodity_routes 从 mock fixture 切真生产 data pipeline 注入
- 不开关 toggle, 直接切 — 但 fallback: registry 若 None → §6 现状的 fail-closed HOLD (per Step M)
- revert criterion: 真 data pipeline 注入后 F2/F4 cut quarantine count ≥ Phase 1.3 baseline × 2 → registry schema 跟 src 不 align, 回到 §13.2 决策 (commodity_id vs route_id) 重审

**全 phase 通用 (任何 Step / Phase 通不过 GO)**
- 任 phase 通不过 GO 标准 → 不推下一 phase, 单独 debug commit
- 每 Step (A-O 跟未来 P+) commit 独立, git revert 单 step 不影响其他
- Audit verdict NOT GO 不 archive 假数据, reproduce verify 真才 commit ([[audit-verify-before-archive]])
- 大节点 audit 不通过 → 打包 next round, 不强推

**hot-roll (env toggle) vs phase-roll (src 改) 区分**
- env toggle (`EXACT_FAMILY_VALIDATOR_STRICT` / `EXACT_USE_POSE_BOOL_MASTER` 等): 瞬时切, 不需 git revert, 反复 toggle 不留 audit trail
- src 改 (新 family / 新 step / 新 watcher): git commit, revert 走 `git revert <SHA>`, 留完整 trail
- 政策: 任何 paradigm 决策 (B Design v2 invariant) 改动必 phase-roll (src 改 + PROJECT_LOCK 同步), 不准 env toggle 绕

---

