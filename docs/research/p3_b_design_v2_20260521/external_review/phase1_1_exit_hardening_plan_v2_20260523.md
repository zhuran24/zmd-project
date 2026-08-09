# Phase 1.1 Exit Hardening + Phase 1.2 Entry Plan v2

状态: **Phase 1.1 可以正式通过**。

这版计划书替代旧版 `PHASE_POST_1_1_REFACTOR_PLAN.md` 作为下一阶段施工入口。旧版方向基本对，但把“已经验证的东西、下一步待做的东西、远期设想”混在一起，容易让执行者误以为 Phase 1.3/1.5 的一些内容已经只是接线工作。v2 把边界重新划清。

---

## 1. 当前结论

Phase 1.1 的目标不是让 cut framework 直接进 168h 生产长跑，而是证明 F1-F4 的 validator / evaluator / replay / store 这条链是 sound 的。经过本次 exit hardening 后，Phase 1.1 达到 GO 条件:

- F1 `region_capacity`、F2 `cutset`、F3 `port_exposure`、F4 `component_reach` 的 validator 继续通过原有 adversarial regression。
- `EXACT_FAMILY_VALIDATOR_STRICT` 默认改为 ON，未知 family / 漏注册 family 不再有 silent path。
- `source_digest` 从占位字符串改为内容 hash。
- `ghost_rect` tuple 语义锁定为 `(x, y, x_span, y_span)`，并有非方形测试。
- `on_ghost_rect_changed` 的测试注入口改成显式 unsafe API，默认路径继续走 full `replay_cut`。
- mypy / bandit / radon / vulture / ruff 已清到 Phase 1.1 exit 标准。

剩余的 `step_2_minimize`、`step_8_apply_to_master`、F5-F9、生产 commodity route schema、CP-SAT 真 attach 都不是 Phase 1.1 的验收范围，进入 Phase 1.2 后按下面顺序做。

---

## 2. 旧计划书需要修正的地方

### 2.1 lifecycle 名称修正

旧版叫“9-step lifecycle”，但正文列了 `0..9`，实际是 10 个编号。v2 统一说法:

- **核心 9 步**: generate → minimize → serialize → deserialize → validate → attach-scope → evaluate → apply-to-master → replay/regression。
- `canonicalize` 是所有步骤共用的哈希/序列化基础工具，不单独算业务生命周期步骤。

这样后续不会再出现“9 步但列 10 项”的审计口径混乱。

### 2.2 Phase 编号修正

旧版把 `P1.11` 同时用作“Phase 1.2 入门 7 项”和“F5 pattern_nogood”，容易误导执行。

v2 改成:

- **P1.2A**: entry hardening，已经在本次补丁中完成大部分并作为 Phase 1.1 exit hardening 落地。
- **P1.2B-F5**: pattern_nogood。
- **P1.2B-F6**: shape_packing_hall。
- **P1.2B-F7**: power_hitting_set。
- **P1.2B-F8**: power_grid_reach。
- **P1.2B-F9**: density_envelope。
- **P1.3A**: CP-SAT attach spike。
- **P1.3B**: benders_loop / master integration。

### 2.3 Phase 1.3 不再假设“只剩接线”

旧版写得像 CP-SAT lazy constraint / propagator 已经确定可行。v2 加硬门槛:

**进入 P1.3B 前，必须先做 P1.3A attach spike。**

P1.3A 只回答一件事: 当前 Python OR-Tools CP-SAT 路径到底能不能在预期时机把 cut 变成有效 master 约束。如果不能直接做 lazy attach，就必须改为 solve-rebuild / shadow telemetry / C++ hook / hard-constraint rebuild 之一。F5-F9 不以“能动态加 lazy constraint”为前提写死。

### 2.4 F6 / F7 / F9 proof obligation 修正

旧版把 greedy / LP relax 写得太像证明。v2 明确:

- F6 Hall cut 不能用 greedy 失败当不可行证明。validator 必须重算 Hall violation witness，例如 `S` 和 `N(S)`，并确认 `|N(S)| < |S|`；或者跑精确 matching / max-flow。
- F7 hitting-set cut 不能用 greedy / LP 近似当“无覆盖”的证明。validator 必须验证安全下界或对偶证书；近似算法只能做 generator hint。
- F9 density envelope 的 `max_density` 必须是安全上界，不能是经验估计。等号不 cut，只有严格 `>` 才 cut。

### 2.5 F8 mode 修正

F8 是 **geometric family**。cert 可以引用 power pole 的 group/pose 作为上下文，但 lifecycle body 不能走 literal multiset path。若实现者想把 F8 写成 literal family，必须先改 PROJECT_LOCK，而不是在 family 内偷换。

### 2.6 telemetry 单位修正

旧版同时出现 `≤100 µs/call` 和 `p95 < 50 ms`，口径冲突。v2 改为:

- hot path evaluator: p95 目标 ≤ 500 µs，stretch goal ≤ 100 µs。
- validator / replay: 可以是 ms 级，单独统计。
- telemetry 写盘: 不进 hot path，单独统计 overhead。

---

## 3. Phase 1.1 exit hardening 已落地内容

### 3.1 source_digest 真 hash

`source_digest` 现在由 state 中的 source data 内容稳定计算，不再使用 `"poc_source_digest"`。哈希输入包括:

- `canonical_rules`
- `candidate_placements`
- `mandatory_exact_instances` / `instance_to_facility_type`
- `facility_templates`
- `commodity_demands`
- `commodity_routes`

运行时缓存键如 `__pose_id_cache__` 被忽略，避免 O(1) cache 改变跨 session identity。

### 3.2 strict registration gate 默认 ON

`EXACT_FAMILY_VALIDATOR_STRICT` 默认从 `"0"` 改为 `"1"`。Phase 1.2 新增 F5-F9 时，如果 validator 漏注册，会 fail-closed，而不是悄悄跳过。

### 3.3 validator helper 拆分

F1-F4 的大 validator 被拆成小 helper。现在 radon 最高为 C(15)，没有 D 级函数。这样后续加 F5-F9 时更容易审计“假 cert 能不能骗过 validator”。

### 3.4 F3 专用未用 evaluator 移除

`evaluate_literal_port_exposure` 被删除，F3 统一走 `evaluate_literal_multiset`。F3 的特殊 soundness 仍在 validator 内检查，不在 evaluator 里重复维护两套逻辑。

### 3.5 ghost_rect 语义锁定

`ghost_rect` tuple 明确为 `(x, y, x_span, y_span)`。非方形 fixture `(10,20,3,7)` 锁定转换为 `(10,20,13,27)`，避免 F8 接入时高宽互换。

### 3.6 unsafe test replay 注入口收紧

`CutStore.on_ghost_rect_changed` 默认只能走 full `replay_cut`。测试想传 stub，必须显式使用 `unsafe_test_replay_fn=...` 且 `allow_unsafe_test_replay_fn=True`。生产误用 stub 的风险降下来。

---

## 4. Phase 1.2 执行顺序

### P1.2B-F5: pattern_nogood

先做 F5，因为它连接 lifecycle step 2 minimize，是 literal path 的最小闭环。要求:

- deletion-based MUS 先落地；QuickXplain 可随后加。
- literal 数超过阈值时 fail-safe，不做指数级搜索。
- validator 不能只相信 oracle 的“这是 unsat core”声明，必须能重放或绑定到已有 infeasible witness。

### P1.2B-F6: shape_packing_hall

要求:

- cert 包含可独立验证的 Hall violation witness。
- greedy 只允许作为找 witness 的方法，不能作为证明。
- 至少覆盖 basic count violation、local Hall violation、false-positive attack 三类测试。

### P1.2B-F7: power_hitting_set

要求:

- cert 表达清楚: 是证明“无可行覆盖”，还是证明“必须包含某些 pole”。
- 如果使用 LP relax，validator 验安全对偶 / 下界；不要把近似解当不可行证明。
- F7 是 literal family，进入 `evaluate_literal_multiset`。

### P1.2B-F8: power_grid_reach

要求:

- F8 仍是 geometric family。
- 先复用 `ghost_geometry.py` 的 Liang-Barsky helper。
- 必须覆盖 degenerate segment、corner touch、axis-aligned、endpoint inside、非方形 ghost rect。

### P1.2B-F9: density_envelope

要求:

- `max_density` 是安全上界。
- 等号不 cut；只有 `cert_density > max_density` cut。
- 如果上界来自 F6/Hall helper，必须写明复用边界。

---

## 5. family-level enable matrix

进入 P1.3 之前，每个 family 要分开开关，不能“一键全开”。建议矩阵:

| Family | Phase 1.2 单测 | P1.3 shadow | P1.3 true attach | 备注 |
|---|---:|---:|---:|---|
| F1 region_capacity | ON | ON | ON | 已最稳 |
| F2 cutset | ON | ON | guarded | 生产 route_id schema 未定前谨慎 |
| F3 port_exposure | ON | ON | guarded | active_port_witness 仍是 Phase 1.5+ |
| F4 component_reach | ON | ON | guarded | commodity route schema 未定前谨慎 |
| F5 pattern_nogood | after P1.2B-F5 | shadow first | guarded | 依赖 infeasible witness |
| F6 shape_packing_hall | after P1.2B-F6 | shadow first | guarded | 依赖 proof witness |
| F7 power_hitting_set | after P1.2B-F7 | shadow first | guarded | NP-hard，严禁 heuristic proof |
| F8 power_grid_reach | after P1.2B-F8 | shadow first | guarded | 依赖 ghost geometry |
| F9 density_envelope | after P1.2B-F9 | shadow first | guarded | 上界必须安全 |

---

## 6. Phase 1.1 final gate

本次补丁后的验收结果:

| Gate | Result |
|---|---:|
| `pytest src/tests/cuts/ -q` | 178 passed |
| `python -O -m pytest src/tests/cuts/ -q` | 178 passed |
| `ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py` | pass |
| `ruff --config "lint.per-file-ignores={}" ...` | pass |
| `mypy --strict --explicit-package-bases src/cuts/` | pass |
| `bandit -r src/cuts/` | 0 issues |
| `radon cc src/cuts/ -s -a` | average A, no D |
| `vulture src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py` | pass |

全项目 `src/tests` collect 仍有 4 个 optional solver import error: `highspy` / `pyscipopt` 缺失。这不是 cut framework Phase 1.1 gate 的一部分，也不阻塞进入 Phase 1.2；如果后续要把 `zmd_deps_v3` 定义成全项目完整离线依赖，需要单独补 HiGHS / SCIP wheel 或把这些测试标成 optional skip。

---

## 7. GO / NO-GO 结论

**Phase 1.1: GO。**

可以进入 Phase 1.2，但必须按 v2 顺序做，不要跳过 P1.2B 的 proof obligation，也不要直接进入 P1.3 master attach。

下一步推荐第一 commit: `P1.2B-F5 pattern_nogood skeleton + validator + tests`。
