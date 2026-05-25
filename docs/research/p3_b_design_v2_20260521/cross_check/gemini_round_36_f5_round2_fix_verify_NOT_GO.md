## Round 2 Verdict (一句话)
NOT_GO — 修复引入了新的边界条件不稳 (0.1s deadline storm) 与硬编码超时隔离风险，且 Validator 存在多处 Schema 交叉校验遗漏与严格顺序依赖。

## A. 算法错估
- **[HIGH] `src/cuts/oracles/pattern_nogood_oracle.py:126` — 0.1s deadline 导致 guaranteed-to-fail 探测风暴**
  - **问题**: `remaining = max(0.1, budget.max_seconds - (_time.monotonic() - gen_t0))`。当时间逼近 budget 边缘时，`remaining` 会被强行置为 0.1s。CP-SAT 等底层 solver 在 0.1s 内连 presolve 都做不完，必然返回 TIMEOUT。
  - **Reproduce**: 假设 budget=10s，在 9.95s 时进入下一次 deletion iter。`oracle_cb` 传给 adapter 0.1s deadline，adapter 必然 TIMEOUT，返回 `had_inconclusive=True`。接着 loop 检查 `time.monotonic() - t0 >= 10.0`，如果此时才 9.98s，它会**继续**下一个 literal，再次发起 0.1s 的必败 query。这不仅浪费 CPU，还把本该是 `CoreStoppedReason.TIMEOUT` 的干净退出，变成了污染 `is_minimal` 的 spurious TIMEOUT。
  - **修建议**: 移除 `max(0.1, ...)`，如果 `remaining <= 0`，直接在 `oracle_cb` 内抛出特定异常或返回 `TIMEOUT`，或者让 deletion loop 统一接管时间检查，不要在 callback 里做 0.1s 兜底。

- **[MEDIUM] `src/cuts/families/pattern_nogood.py:136` — Validator 漏校验 `size_after` 与实际 pattern 长度的一致性**
  - **问题**: Validator 校验了 `size_after >= 0` 且 `<= size_before`，也校验了 `forbidden_pose_pattern` 非空，但**没有**交叉校验 `len(forbidden_pose_pattern) == size_after`。
  - **反例**: 恶意/Buggy 节点伪造 Cert，`size_after=1`，但 `forbidden_pose_pattern` 塞了 100 个 literal。Validator 会接受这个 Cert（只要这 100 个 literal 确实 INFEASIBLE），导致审计字段 `size_after` 语义被破坏。
  - **修建议**: 在 `_validate_core_minimization` 或 pattern 校验处增加 `if len(cert_triples) != cm["size_after"]: return schema_err`。

## B. 前提错估
- **[HIGH] `src/cuts/families/pattern_nogood.py:40` — Validator 10s 死亡线与 Generator 预算的系统性冲突**
  - **问题**: Claude 在 Fix #3 中把 Validator 的 deadline 硬编码为 10.0s，试图对齐 Generator 的默认 budget。但前提错估了：
    1. Generator 的 `budget` 是参数传入的，如果调用方传了 `max_seconds=20.0`，Validator 依然死守 10s，导致合法 Cut 100% 被 Quarantine。
    2. 即使 budget 也是 10s，如果 Generator 在 9.9s 找到了 INFEASIBLE core，Validator 机器由于负载波动，重算耗时 10.1s，就会触发 TIMEOUT。
  - **修建议**: Validator 的 re-verify deadline 必须具备充足的 Buffer（例如 `30.0` 秒，或读取 Cert 中记录的实际耗时 + 50% buffer）。验证者的超时阈值必须严格大于证明者的单步最大耗时。

## C. 数学能力上限
- **[MEDIUM] `src/cuts/families/pattern_nogood.py:228` — `_validate_cert_literals_match` 违反 Multiset 无序性**
  - **问题**: `literal_triples != cert_triples` 使用了严格的 Tuple 顺序比对。虽然 Generator 产出时两者顺序一致（都是 canonical sort），但 Cut 作为一个逻辑实体，其 `literals` 本质是 Multiset。如果 CutStore 在序列化/反序列化（或存入 DB）时打乱了 `cut.literals` 的顺序，该校验会报 `unsound`。
  - **修建议**: 应该比较 `sorted(literal_triples) == sorted(cert_triples)`，或者用 `Counter` 比对，消除对外部系统保持列表顺序的脆弱依赖。

## D. 修复 verify 表格

| Fix | Verdict | 理由 |
|---|---|---|
| #1 cert_payload witness 移除 | CORRECT | 彻底移除了跨 worker 不稳定的 witness bytes，Soundness 退回到仅依赖 Oracle re-query INFEASIBLE，逻辑自洽且符合 F5 语义。 |
| #3 deadline 10s match | NEW_GAP | 见 Finding B。硬编码 10s 无法适配动态 budget，且缺乏机器性能波动的 ε buffer，会导致系统性 Quarantine。 |
| #4 remaining deadline closure | PARTIAL | 确实防止了总时间无限累积，但 `max(0.1, ...)` 引入了必败的 0.1s 探测风暴（见 Finding A）。 |
| #5 input dedup canonical_sort | PARTIAL | 逻辑上正确修复了重复 triple 浪费 call 的问题，但遗留了过时的注释（见 Finding E）。 |

## E. Round 1 漏 finding (新发现)
- **[LOW] `src/cuts/helpers/bounded_core_minimizer.py:176-179` — 逻辑变更导致注释变为死代码/误导**
  - **问题**: 代码写着 `# Defensive: literal already removed in a prior iter (only possible if the input has dup triples — canonical sort doesn't dedupe).` 但 Fix #5 已经让 `canonical_sort_assignment` 具备了 dedup 功能。这意味着 `if lit not in current_core:` 变成了永远不会触发的死代码，且注释与当前行为完全矛盾。
- **[LOW] `src/cuts/oracles/pattern_nogood_oracle.py:127` — Witness blob 接收但未使用，接口语义冗余**
  - **问题**: `verdict, _blob = sub_problem_oracle.query(...)`。既然 Fix #1 已经明确 F5 彻底抛弃 witness bytes，`SubProblemOracleAdapter.query` 协议仍强制返回 `bytes` 会对 Phase 1.5 的实现者造成误导（他们可能会花代价去提取 IIS/Core bytes，结果 F5 根本不用）。建议在 Protocol 层面明确 F5 adapter 只需要返回 `OracleVerdict`，或者允许返回 `None`。

## F. Overall verdict
NOT_GO — 核心验证逻辑（Validator Deadline 缺乏 Buffer、严格顺序依赖、Schema 漏校验）和生成逻辑（0.1s 探测风暴）仍存在导致合法 Cut 被误杀或系统资源浪费的缺陷，必须在 Phase 1.2 彻底清理。