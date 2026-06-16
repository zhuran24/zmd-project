## Round 3 Overall Verdict
GO_WITH_MINOR (Defer to Phase 1.5+)

代码在数学和形式化契约上已经非常坚固。Round 2 的修复全部有效，且没有引入新的 soundness 漏洞。Round 3 深度审查发现了 2 个边缘的 fail-closed 语义瑕疵（Untrusted Oracle 契约执行不严、Validator 异常定性过重），但不影响核心的 soundness，可作为 minor follow-ups 留到 Phase 1.5+ 接入真实 adapter 时一并处理。

---

## Round 2 Fix Verify

- **R2#A 0.1s floor 移除**: **CORRECT**
  - *Verify 细节*: 边界 `remaining <= 0.0` 严格安全。关于 `gen_t0` (generator 外部起点) 与 `t0` (minimizer 内部起点) 的 reconcile：因为 `gen_t0 < t0`，所以 `oracle_cb` 里的 `remaining` 会比 minimizer 的 `budget.max_seconds` 更早耗尽。当 `remaining <= 0` 时，`oracle_cb` 返 `"TIMEOUT"`，minimizer 收到后标记 `had_inconclusive = True` 并继续下一次循环。由于此时 minimizer 自己的 `time.monotonic() - t0` 可能还差几微秒才到 `max_seconds`，它可能会多跑 1-2 次极快的空转循环（每次都立刻被 `oracle_cb` 的 TIMEOUT 拦截），直到 minimizer 自己的 wall-clock 也达标并退出。这在数学上绝对安全，且彻底消除了 adapter 收到微小 deadline 的风险。
- **R2#A.2 size_after cross-check**: **CORRECT**
  - *Verify 细节*: 顺序合理。由于 `len(cert_triples) == cert_size_after`，且后续 `_validate_cert_literals_match` 强制要求 `len(cut.literals) == len(cert_triples)`，根据传递性，`len(cut.literals) == cert_size_after` 已经得到了严格保证。不需要再额外写直接的 cross-check，闭环已完美合拢。
- **R2#B 15s buffer**: **CORRECT**
  - *Verify 细节*: 15s 绝对够用。因为 generator 的 budget 默认是 10s，这意味着**任何成功生成的 cut，其对应的 core 必然曾在 <10s 的时间内被 adapter 证明为 INFEASIBLE**。Validator 只是对这个已经 minimized 的 core 做 *单次* re-query，给予 15s 的 deadline 相当于提供了 >50% 的 buffer 来吸收机器负载 noise。逻辑自洽。
- **R2#C frozenset equality**: **CORRECT** (但 R2 诊断有偏差)
  - *Verify 细节 (Dup Bypass)*: 攻击向量**不成立**。因为 `_validate_forbidden_pose_pattern` 严格拒绝了 cert 端的 dup，所以 `cert_triples` 的长度就是其 unique 元素的数量。如果 `cut.literals` 包含 dup，它的 unique 数量必然小于其长度。为了通过 frozenset 相等性检查，`cut.literals` 的 unique 数量必须等于 `cert_triples` 的长度；但前置的 length check 又要求 `cut.literals` 的总长度等于 `cert_triples` 的长度。这就倒逼 `cut.literals` 必须没有任何 dup。数学上无懈可击。
  - *Verify 细节 (Anonymity 诊断)*: R2 说 "包含 slot_index 违反 anonymity" 其实是**误诊**。Anonymity (I3) 约束的是 cut 与 master state 匹配时的行为；而这里是 cert payload 与 cut object 的**完整性校验 (Integrity)**。Cert hash 的计算依赖 canonical sort (包含 slot_index)，所以 validator 必须严格校验 slot_index 是否一致。R2 的 fix (改用 frozenset) 歪打正着地做对了，因为它消除了序列化可能带来的顺序强依赖，提升了鲁棒性，但保留 slot_index 是绝对正确的。
- **R2#LOW1 stale comment**: **CORRECT** (已清理)
- **R2#LOW2 Protocol witness Optional[bytes]**: **CORRECT** (已更新)

---

## New Findings (round 3 catch)

### 1. [MEDIUM] `VALID_ORACLE_VERDICTS` 定义了但未使用，导致 Untrusted Oracle 返回 Bogus 字符串时被静默视为 FEASIBLE
- **file:line**: `src/cuts/helpers/bounded_core_minimizer.py` 行 171-175
- **问题陈述**: 
  代码在行 38 定义了 `VALID_ORACLE_VERDICTS: frozenset[str] = frozenset(("INFEASIBLE", "FEASIBLE", "UNKNOWN", "TIMEOUT"))`，但在 `deletion_minimize_core` 的主循环中**完全没有使用**。
  如果一个有 bug 的 untrusted adapter 返回了非法字符串（例如 `"BOGUS"`），代码的 `if/elif` 分支会将其 fall-through。它既不会更新 `current_core`，也不会设置 `had_inconclusive = True`。结果是：这个 literal 被保留，且 `is_minimal` 依然可能在最终保持为 `True`！这违反了 `is_minimal=True` 必须建立在所有保留的 literal 都被严格证明为 `FEASIBLE` 的契约上。
- **建议 fix**:
  在 `try` 块内获取 verdict 后，立刻校验其合法性，非法则抛错走 fail-closed：
  ```python
  verdict = oracle(trial_core)
  if verdict not in VALID_ORACLE_VERDICTS:
      raise ValueError(f"Oracle returned invalid verdict: {verdict!r}")
  ```

### 2. [LOW] Validator re-verify 阶段 Oracle 抛出异常时，返回 "unsound" 语义过重
- **file:line**: `src/cuts/families/pattern_nogood.py` 行 327-332
- **问题陈述**:
  在 `_reverify_sub_problem_oracle` 中，如果 adapter 抛出异常（例如真实的 Gurobi adapter 遇到瞬时网络抖动或 OOM），validator 会返回 `_vr("unsound", ...)`。
  在系统语义中，`unsound` 意味着 "这个 cut 在数学上被证明是假的"，可能会导致 master solver 永久丢弃该 cut 甚至惩罚 generator。而异常仅仅是 "Verifier 暂时无法验证"。根据 fail-closed 原则，这里应该退化为 quarantine 状态。
- **建议 fix**:
  将异常捕获的返回值从 `"unsound"` 改为 `"timeout"`（在当前 ValidationKind 中，timeout 是标准的 quarantine 表达）：
  ```python
  except Exception as e:
      return _vr("timeout", t0, f"sub-problem oracle re-verify raised {type(e).__name__}: {e} (quarantined)")
  ```

---

## Sanity Arguments (为什么没有漏掉其他漏洞)

1. **Empty Core Bypass 免疫**: 攻击者无法通过伪造 `size_after=0` 的 cert 来注入空 cut。因为 `_validate_forbidden_pose_pattern` 强制要求 pattern 必须是 non-empty list，且 `deletion_minimize_core` 内部有 `if not trial_core: continue` 的硬拦截，确保 core 至少保留 1 个 literal。
2. **Wall-clock Leak 彻底封死**: Generator 层的 `oracle_cb` 严格传递 `remaining` 递减时间，Minimizer 层有 `time.monotonic() - t0` 的兜底 check，Validator 层有独立的 15s 绝对上限。三层时间控制互不依赖且方向一致，杜绝了任何恶意/卡死的 sub-problem 耗尽 worker 线程池的可能。

## 建议 final Phase 1.2 action

**GO_WITH_MINOR**
当前代码已完全满足 Phase 1.2 的验收标准。建议将上述 2 个 Finding (Bogus verdict check & Exception quarantine) 记录为 minor follow-ups，在 Phase 1.5 接入真实 `binding_subproblem` adapter 时顺手修复即可。无需再进行 Round 4。