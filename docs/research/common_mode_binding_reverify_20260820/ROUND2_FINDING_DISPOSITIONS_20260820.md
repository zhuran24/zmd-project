# Round-2 external audit finding dispositions

日期：2026-08-20

源报告：

```text
/home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/
EXTERNAL_AUDIT_I1_ROUND2_20260820.md
```

本页只记录处置，不构成第三轮外审 verdict，也不构成 P1.2 re-close。

## BLOCKER

| ID | 第二轮发现 | 处置 |
|---|---|---|
| G0 | `binding_subproblem.py` fallback 使用未 import 的 `defaultdict`；`utility_operation_by_template` 没有 production caller | 删除 `OPERATION_PORT_PROFILES` fallback；新增 strict preprocess-plan loader 与 atomic-text loader；ExactSearchSession/ExactMasterCore/Master/LBBD primary+retry/PR2/heuristic 全链显式生产和消费 plan map；constructor 的惰性 fallback 也只读 preprocess plan |
| G1 | `semantics.py` 在 `build_semantic_model` 引用未绑定的 `routing_context_relaxation_active` | `_validate_semantics_contract` 改为返回实际 routing-relaxation bool，调用点显式接收；返回 semantic model 时只使用该已绑定值 |
| G2 | I1 的 `_EXPECTED_CONSTRUCTOR_PARAMETERS` 少 `utility_operation_by_template` | expected constructor surface 与 production `inspect.signature(PortBindingModel.__init__)` 对齐；真实合同不再固定退 `BINDING_CONSTRUCTOR_SURFACE_DRIFT` |
| G3 | theorem 写出 `runtime_relaxations`，独立 certificate checker 没有该字段 | `certificate.py` 的 exact key set、类型/重复值检查和 semantic-model 精确比较全部补齐；增加即使重算 digest 仍拒绝 relaxation 篡改的红测 |

## F0：被缺工件遮住的回归

原始机器收据 `MASKED_REAL_DIFF_20260820.json` 保持原字节，并如实记录：

```text
outcome_changes             14
baseline_pass_current_fail  14
```

14 条都在 `test_binding.py`。它们是 plan snapshot 合同增长后 stale doubles 未同步的同类回归。修复包括统一 controller stub、完整 input/output/utility 三张 map，以及 direct constructor fixture 的 plan-derived map。

修后使用真实 54 MiB artifact 对原 47 个 nodeid 做 baseline/current 逐条重放，结果写入 `MASKED_REAL_DIFF_POSTFIX_20260820.json`。该 postfix 收据必须由最终冻结字节重新生成，不能沿用修复中途结果。

## 运行态合同与结构门

- 运行态字段只从实际 `PortBindingModel.extract_conflict_summary()` 读取；仓内没有虚构的 `extract_reverification_runtime_state()` production API。
- Contract 缺任一运行态字段、类型错误或与 `proof_summary.binding_summary` 不一致时，funnel fail closed。
- Checker 用 AST 拒绝三个 runtime field 写成常量。
- Generic input/output 两侧都必须调用 plan-derived capacity-map helper。
- `PortBindingModel` 只允许一张被实际读取的 `utility_operation_by_template` 字段；未消费的派生别名不允许存在。
- Checker 枚举四个 production-source constructor：LBBDController primary、LBBDController retry、PR2 terminal fixed-witness、heuristic finder。Heuristic 明确标为 exploratory/non-authority，但仍必须接收 plan map。

## 收口纪律修复

第二轮外审查明上一版对话终稿引用了不存在的自验收据，且最终四个承重文件的 mtime 晚于所援引的中途自验。该终稿和数字全部撤销。

第三轮封账执行以下硬规则：

1. 先完成全部源码、测试、manifest、知识投影和 handoff；
2. 记录最终承重字节的最大 mtime 与 digest；
3. 此后运行 ruff、双 mypy、focused、真实三案、proof gate、doctor、changed/framework gate；
4. 每个命令的 stdout/stderr/return code 落 worktree-local `.artifacts`；
5. 只有全部预期通过且两条 sealed-authority 测试以预期原因保持红，才生成总 receipt；
6. 总 receipt 的 mtime 必须晚于最后一个承重文件；
7. 总 receipt 生成后不再改任何源码、测试、manifest、知识源或 handoff。若发生改动，整套自验作废重跑。
