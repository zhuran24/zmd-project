# Phase 1.1 Exit Audit and Fix Report

本报告记录本次对 Phase 1.1 的最终检查、发现的问题、修复内容和验收结果。

## 1. 审查范围

检查范围:

- `src/cuts/` framework code
- `src/tests/cuts/` cut framework tests
- `docs/research/p3_b_design_v2_20260521/*` active specs
- 原计划书 `PHASE_POST_1_1_REFACTOR_PLAN.md`

不在本次范围:

- F5-F9 的正式实现
- CP-SAT / benders_loop 真集成
- production commodity route schema 重构
- `highspy` / `pyscipopt` optional solver 依赖补齐

## 2. 发现并修复的问题

### 2.1 strict gate 默认关闭

问题: `EXACT_FAMILY_VALIDATOR_STRICT` 默认是 `"0"`，Phase 1.2 加新 family 时可能漏注册但不立刻暴露。

修复: 默认改为 `"1"`。现有 F1-F4 均已注册，测试通过。

### 2.2 source_digest 是占位字符串

问题: 多处使用 `"poc_source_digest"`，跨 session replay 无法区分 source data 变化。

修复: 新增 `compute_source_digest(state)`，根据 source data 内容做稳定 sha256；运行时 `__*` cache 不进入 hash。lifecycle generator、region_capacity oracle、replay scope check 均改用真 hash。

### 2.3 validator 大函数复杂度偏高

问题: F1-F4 validator 在多轮审查中不断加 check，函数变大，后续容易漏接线。

修复: 拆 helper。radon 现在最高 C(15)，无 D 级函数。

### 2.4 F3 unused evaluator

问题: `evaluate_literal_port_exposure` 未被使用，容易变成第二套过期逻辑。

修复: 删除，F3 统一走 `evaluate_literal_multiset`。F3 的 family-specific soundness 保留在 validator 内。

### 2.5 ghost_rect tuple 语义不够清楚

问题: 旧注释写 `(x,y,h,w)`，helper 实际按 `(x,y,x_span,y_span)` 做 AABB，F8 容易横竖反。

修复: 注释和计划书统一成 `(x, y, x_span, y_span)`；新增非方形测试。

### 2.6 test replay stub 注入口太像生产 API

问题: `on_ghost_rect_changed(replay_fn=...)` 允许外部传 stub，容易绕过 full family validator。

修复: 改为 `unsafe_test_replay_fn`，并要求 `allow_unsafe_test_replay_fn=True`。默认生产路径只走 `replay_cut`。

### 2.7 mypy / bandit / vulture / ruff hygiene

问题: strict typing、assert、dead code、unused imports 会干扰 Phase 1.2 审计。

修复:

- `src/cuts/` mypy strict 清零。
- `src/cuts/` bandit 0 issues。
- vulture 使用白名单只保留明确的 phase boundary API。
- ruff 默认和取消 per-file ignores 后均通过。

### 2.8 active spec drift

问题: active docs 仍有旧 `PoseId=int/Tuple`、`symmetry_lift`、F3 up/down/left/right、F2/F4 registry drift。

修复:

- `state_machine_v2.md`: `PoseId = str`。
- `cut_lifecycle_v2.md`: family list/mode 删除 `symmetry_lift`，加入 F8/F9。
- `03_port_exposure.md`: direction 改为 `N/S/E/W`。
- `02_cutset.md`: 写明 contributing commodity 集合语义、registry、cross-partition route。
- `04_component_reach.md`: 写明 commodity route registry、separator in-grid + owner/ghost。

## 3. 最终验收命令

```bash
python -m pytest src/tests/cuts/ -q
python -O -m pytest src/tests/cuts/ -q
ruff check src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
ruff check --config "lint.per-file-ignores={}" src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
python -m mypy --strict --explicit-package-bases src/cuts/
bandit -r src/cuts/
radon cc src/cuts/ -s -a
vulture src/cuts/ src/tests/cuts/ scripts/vulture_cuts_whitelist.py
```

结果:

- cuts pytest: 178 passed
- cuts pytest under `python -O`: 178 passed
- ruff: pass
- mypy strict: pass
- bandit: 0 issues
- radon: average A, no D
- vulture: pass

## 4. 非阻塞项

全项目 `src/tests` collect 仍有 4 个 optional solver import error，来自缺失 `highspy` 和 `pyscipopt`。这些测试不是 Phase 1.1 cut framework gate。后续可以二选一处理:

1. 把 HiGHS / SCIP wheel 加进 `zmd_deps_v3`；或
2. 给这些测试加 optional dependency skip。

## 5. 结论

Phase 1.1 可以正式通过，进入 Phase 1.2。进入后不要直接做 master attach，应先按 `PHASE_POST_1_1_REFACTOR_PLAN_v2.md` 执行 P1.2B-F5 到 F9，并在 P1.3 前做 CP-SAT attach spike。
