# P2 #31 Pumpkin LCG PoC（2026-05-10）

验证 Pumpkin 0.3.0 (TU Delft ConSol-Lab) 作为 binding subproblem 备选求解器的可行性。

## 路径选择: Pumpkin vs Glasgow

并行调研后 Pumpkin > Glasgow:

| 项 | Pumpkin 0.3.0 | Glasgow CP2026 |
|---|---|---|
| 状态 | 2025 MiniZinc Fixed Search 铜牌 | "no stable API" pre-release |
| 装 | `cargo install pumpkin-solver` 4m10s | cmake build 3m |
| FlatZinc 输入 | 直接吃 `.fzn` | input 格式不直接吃 .fzn (json 中间格式), 卡死 |
| 卖点 | DRCP unsat cert + extract_core MUS | VeriPB proof logging |
| **PoC 结果** | ✅ **GO**（3 R10 gate 通过） | ❌ **KILL**（input format 卡死 + agent 调研预测 >70% NO-GO） |

## Pumpkin PoC 结果

### 装通

```bash
sudo pacman -S rust              # 30s
cargo install pumpkin-solver     # 4m10s compile
cargo install pumpkin-checker    # 1m30s compile (DRCP verifier)
```

### 跑通 INFEASIBLE demo

3 约束 INFEASIBLE FlatZinc demo（`infeasible_demo.fzn`）:
- `c0: x = 1` (`int_lin_eq`)
- `c1: y = 1` (`int_lin_eq`)
- `c2: x + y <= 1` (`int_lin_le`)

```bash
pumpkin-solver --proof-path proof.drcp --proof-type full infeasible_demo.fzn
# =====UNSATISFIABLE=====

pumpkin-checker infeasible_demo.fzn proof.drcp
# parse-flatzinc: 0.0003s
# parse-proof: 0s
# validate: 0.000013s
# Proof is valid!
```

### R10 audit go/no-go gate

| Gate | 状态 |
|---|---|
| 装通 + 跑通 INFEASIBLE | ✅ |
| DRCP proof 生成 | ✅ |
| **DRCP proof 机器验证 PASS** | ✅ **核心差异化兑现**（CP-SAT 9.15 没这能力） |
| MUS extraction | ⏳（DRCP 含 nogood 但需后处理提取，非直接 CLI flag） |
| 速度对比 CP-SAT | ⏳（需要 head-to-head benchmark on 项目 binding 实例） |

## Verdict: GO（Pumpkin 路径可继续深入）

PoC 通过 3 个核心 gate (装通 / UNSAT / proof verify)，差异化卖点（认证可验证 INFEASIBLE）兑现。

**下一步**（gated by 168h 大跑 baseline）:
1. 写 ortools.sat.python.cp_model → Pumpkin FlatZinc dumper（1-2 天 Claude pace）
2. dump 项目某个 binding subproblem INFEASIBLE 实例做 head-to-head: CP-SAT 9.15 deletion-based MUS vs Pumpkin DRCP extract_core
3. 评估 "认证可验证 INFEASIBLE" 是否成为 Phase 3C cert pipeline 一环

## checker 支持的 FlatZinc constraint subset

实测 `pumpkin-checker 0.3.0` 只支持非常 minimal 的 constraint set:

| 支持 | 不支持 |
|---|---|
| `int_lin_eq`, `int_lin_le` | `int_eq`, `int_le`, `int_ne` |
| `pumpkin_all_diff` | `bool_clause`, `array_*` |

PoC demo 必须用 linear constraint 重写。这一限制对 production 整合是个考虑点——所有 constraint 必须重写成 linear form 才能被 verifier 检验。

## Glasgow CP KILL 原因

- input format 不直接吃 `.fzn`（试 `fzn-glasgow demo.fzn` 报 JSON parse error），需要 minizinc preprocess pipeline
- 排查 input format 投入 30+ min 后, ROI 已经低于 Pumpkin 在 R10 gate 通过
- agent 调研已经预测"Glasgow 纯性能 KILL 概率 >70%"+ "无 stable API"
- 决定不再深入

## 文件清单

- `infeasible_demo.fzn` — 3 约束 INFEASIBLE FlatZinc demo
- `run_demo.sh` — solver + verifier 运行 wrapper
- `proof.drcp` — Pumpkin 输出的 DRCP proof（验证通过）
- `run_log.txt` — 完整运行日志
