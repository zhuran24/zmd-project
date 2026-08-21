# External heterogeneous audit handoff: I1 round 6B

日期：2026-08-21

```text
status    ROUND6B_READY
worktree  /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504
HEAD      aa517cd35e222672f5f6dcd88beba4689c69cf29
commit    none
re-close  no
```

本文件的 §1–§12 保留第三轮交接快照，§13 保留第四轮外审前终态，§14 保留第五轮输入，§15 保留 owner 范围 A 执行后的第六轮输入，§16 给出第六轮 finding 机械修复后的当前输入。它不是 owner re-close。

## 1. 上轮报告

```text
path   /home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/EXTERNAL_AUDIT_I1_ROUND2_20260820.md
sha256 8a5915ca24cad7d10ab9bfbac1aaa9ebc4da21d53d032d3edb7649241f2019e2
verdict FINDINGS_REQUIRE_FIX
```

第二轮确认 I1 的负证方向没有 soundness 破口，也确认 production runtime observation / cross-check / missing-observation fail-closed 的方向正确；但最终字节因四条 BLOCKER 不可运行，且上一版终稿援引了不存在的收据和早于最终源码的中途自验。本轮将“代码方向”和“封账纪律”分开验收。

## 2. BLOCKER 修复对照

| ID | 上轮问题 | 当前修复 | 第三轮应攻击 |
|---|---|---|---|
| G0 | 未 import `defaultdict`；`utility_operation_by_template` 无 caller，构造即崩 | 删除 profile-constant fallback；从 preprocess-plan strict 派生 `facility_type→utility operation`；ExactSession/Core/Master/LBBD primary+retry/PR2/heuristic 全链显式接线；惰性 fallback 也只读 plan | 搜索全部 production `PortBindingModel` 构造点，确认没有无 plan map 的权威路径或 `OPERATION_PORT_PROFILES` fallback |
| G1 | `routing_context_relaxation_active` 跨函数未绑定 | `_validate_semantics_contract` 返回 strict bool，`build_semantic_model` 显式接收并写入 model | 构造 routing true/false 合同，确认无 NameError，且 token 只在 true 时出现 |
| G2 | expected constructor surface 少第 14 项 | `_EXPECTED_CONSTRUCTOR_PARAMETERS` 包含 `utility_operation_by_template` 并与 production `inspect.signature` 对拍 | 对真实三案确认不再固定落 `BINDING_CONSTRUCTOR_SURFACE_DRIFT`；新增参数应令旧 I1 fail closed |
| G3 | theorem 写 `runtime_relaxations`，checker exact-key set 未更新 | checker exact-key set、数组类型、重复值、model 精确比较和 digest-tamper 红测全部补齐 | 删除/篡改 relaxation 后重算 digest，checker 仍必须拒绝 |

## 3. F0：原 14 条分叉与修后真差分

原机器收据保持原字节：

```text
docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_20260820.json
outcome_changes             14
baseline_pass_current_fail  14
```

上一版终稿把它写成 0，是事实错误。14 条均为 `test_binding.py` stale doubles，已补完整 input/output/utility plan snapshot。

修后权威收据：

```text
docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_POSTFIX_20260820.json
```

第三轮必须直接检查该 JSON：请求 nodeid 必须为 47；baseline/current 必须逐条执行到终点；`outcome_changes` 与 `baseline_pass_current_fail` 必须为 0；临时普通文件副本必须已删除。不要再用“缺工件时同红”替代真差分。

## 4. 实际 runtime observation

仓内不存在 production `extract_reverification_runtime_state()` API。实际链为：

```text
PortBindingModel.build / add_nogood_cut
  → PortBindingModel.extract_conflict_summary()
  → LBBDController._binding_reverify_semantics_contract
  → binding_semantics_contract_v1
  → isolated I1
```

`extract_conflict_summary()` 提供：

```text
routing_context_enabled
overload_separation_enabled
reverification_selection_nogood_count
```

Contract builder 对缺失、bool/int 类型和 `proof_summary.binding_summary` 漂移 fail closed。Whole-layout funnel 必须传入产生 exhaustion 的实际 binding model；无 model observation 不得 mint cut。

## 5. Routing filter 单调性

Routing-aware filter 只删除被堵 port/pattern：

```text
D_r ⊆ D
```

I1 重建未过滤超集 `D`。因此 `I1_INFEASIBLE(D)` 蕴含 `PRODUCTION_INFEASIBLE(D_r)`。I1 在 `D` 中找到 witness 只阻止 negative cut，不证明 `D_r` 可行。

当 production 实际 routing context 为 true 时，semantic model 与 certificate 必须携带：

```text
routing_context_domain_filter_omitted_monotone_superset
```

独立 checker 精确核对。Overload separation 或 selection nogood 非零仍返回 `UNKNOWN`。

## 6. Plan-derived utility map

以下三个快照同源于 `preprocess_plan.utility_operations`：

```text
generic_input_slots_by_operation
generic_output_slots_by_operation
utility_operation_by_template
```

四个曾手抄 pose-optional mapping 的组件已经改为独立读取/验证 model input 中的 plan map：production binding、I1、PB emitter、canonical witness checker。映射歧义必须 fail closed。

Certified constructor 覆盖：

- LBBDController primary binding：certified，统一 snapshot helper；
- LBBDController overload retry：certified，统一 snapshot helper；
- PR2 terminal fixed-witness：certified，显式读取并传三张 plan map；
- heuristic feasible finder：`exploratory_non_authority`，显式读取并传三张 map，不拥有 cut authority。

Proof checker 对以上四处逐个枚举，不再只数 LBBDController 内的两个调用。

## 7. 真实工件三案

```text
candidate artifact size   54,467,709
candidate artifact sha256 f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3
```

三案使用真实 rules、plan、mandatory instances 和 candidate pool；布局是测试确定性选择的 real-pool pose，不是 solver incumbent：

1. mandatory + protocol core：production/I1 可行；
2. 加 plan-derived optional storage box：production/I1 可行；
3. 真实工件上仅将 generic-output 总需求 52→53：production/I1 都判容量不可行，certificate checker 通过。

测试 contract 必须由实际 production conflict summary 构造，不得手填 `False/False/0`。

## 8. Checker 结构义务

第三轮应验证 mutation tests 真正击中：

- runtime 三字段 AST 常量；
- generic input/output 任一侧绕开 plan capacity helper；
- PR2 或 heuristic 移除 utility map；
- theorem/checker 的 runtime-relaxation schema 不一致；
- dynamic import / `getattr(..., "__import__")`；
- whole-layout funnel 绕开实际 binding-model observation；
- `PortBindingModel` 出现未消费的第二张 operation map。

## 9. 最终封账收据

唯一可引用的总收据：

```text
/home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504/.artifacts/i1_round3_self_check_20260820/ROUND3_SELF_CHECK_20260820.json
```

该文件由最终冻结字节运行后生成。第三轮首先核对：

1. 文件真实存在；
2. `status == PASS`；
3. receipt mtime 晚于 `max_bearing_input_mtime_ns`；
4. receipt 记录的 bearing-input digest 与当前 worktree 重算一致；
5. 每个命令都有独立 stdout/stderr 文件与 return code；
6. 生成 receipt 后，没有任何 bearing input mtime 或 digest 变化。

强制命令集合：ruff、preflight strict mypy、closed-package mypy、focused pytest、真实三案、proof gate、strong-status、knowledge check、document doctor、changed gate、framework gate、current code-assets，以及两条 sealed-authority 预期红测试。

两条 sealed-authority 测试必须仍以旧 floor `34e198fc…` 对当前 `benders_loop.py` bytes 不匹配为唯一失败原因；不得改测试、改旧 floor、skip 或 xfail。

## 10. 关键字节 SHA-256

| 路径 | SHA-256 |
|---|---|
| `src/models/binding_subproblem.py` | `b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba` |
| `src/models/master_model.py` | `d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371` |
| `src/search/benders_loop.py` | `461fc6875ca16781c1d0d81720aee98747a3d2c984a4c1bf1afda4f384af1bc3` |
| `src/search/pr2_l0_fixed_witness_core.py` | `eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1` |
| `src/search/heuristic_feasible_finder.py` | `5c885eca5c683e37e41163a53f3bb5f4c9c5f759ce0f52db7e8d0cc5c779770d` |
| `src/search/independent_infeasibility_reverifier.py` | `831fab66ee48baa387e06d0aa3dd7af5a9acd85554d2361698bb141995cbdf8f` |
| `src/search/independent_binding_reverify/__init__.py` | `7fd71f197586e19a9bb19a55f9d1b2b0e2958e0a8f8c06f2a021c59b0e4f91cc` |
| `src/search/independent_binding_reverify/api.py` | `2e312e17c1b93efbfbd10d8cd2e27a5fa439810ec3633bd917ad80695cb0f28e` |
| `src/search/independent_binding_reverify/artifacts.py` | `0dfa71cd1e74100e2d030263d79762bf570ea8139b37eebc68a029f086c49180` |
| `src/search/independent_binding_reverify/capsule.py` | `c923eb7ab9a858dac549ed083fbc4efaaa289f97131a1fddc2c916d29b896f7d` |
| `src/search/independent_binding_reverify/certificate.py` | `5144ad29f2d92444f0b74143587afc9d4866fa951b0781b4a89b31b74b24bf83` |
| `src/search/independent_binding_reverify/protocol.py` | `16aeea60711fbf7dab8a2c7d7d2109ea18e7ab0e081d6e4c53f6d4bc4af02f1e` |
| `src/search/independent_binding_reverify/semantics.py` | `9582cf325c60e861293cdbf8146672b4ab089c3a9c11d639bbe33ba478acf22e` |
| `src/search/independent_binding_reverify/theorem.py` | `b3b63bac981b4d17f6efa43dd110ae3ce76f7fb7f6d2aed74545034eb1beceb5` |
| `src/search/independent_binding_reverify/transport.py` | `16c7c1158220ee7d4ebf3110f270390c84fd1795b34ef65b043da5d94aa6d5de` |
| `certside/sidecar/frontend.py` | `d60c8bf3955f26f85d8087c5553e2398dd0741c8c58bc3579e1c9cc9c0b73f0d` |
| `certside/sidecar/emitter.py` | `83188d850d910665dec83ac33cb7e391f95063af4d4f8635401d04923fa44c6d` |
| `certside/sidecar/canonical_witness_checker.py` | `f0c9b7a59dad2dda120fdcb423d1d26b8861685cb81bce4cbaaec19a8fce74de` |
| `certside/sidecar/parity_check.py` | `626bd87b3ebb41a99d94c7cafe59126f02fc02ac18068d7873535ea4cc6a95f9` |
| `certside/sidecar/run_acceptance.py` | `18a5e409853b786463de4c21ce4bc31c76a6d01a255bb28524b3303703f1ecc0` |
| `scripts/check_p1_2_proof_obligations.py` | `e38beffa53172dd7b577f863bd545e003852f559f72ef5eb918a888f872129d3` |
| `src/search/certified_artifact_contract.py` | `0d8c33834d4b3659dcf82dd2c719a46ec8a35f84ca7f59b893028252cff651ce` |
| `data/proof_obligations/p1_2_proof_obligations.json` | `a64b856489c7397afbfa220b59ad053ccb9ff036376b0d9b36200533063f5647` |
| `src/tests/test_p1_2_independent_infeasibility_reverifier.py` | `d428ad7b5f02f2e791868ebee35b9848cdfb23031765efb6de7b6c4d824f5134` |
| `src/tests/test_independent_binding_arithmetic_parity.py` | `b6168e5d405eacd37d13c7435f9315527fe1d78d73daa3c20ca0168769a3bbec` |
| `src/tests/test_independent_binding_real_artifact_parity.py` | `ab50776402f4ecbae34d4e3843cc255f25973a2fbb2a5548c0abcdb3912c4fc2` |
| `src/tests/test_binding_sidecar_projection_parity.py` | `1182f2198452192dcc6c2cffe9c1dfa89e96d1e8e3ce640550c53946afa17f3a` |
| `src/tests/test_binding.py` | `7d35a23a33a4d6f2c22f8711ee18b3e7dcef9ee5f689738b6db825a478f2be68` |
| `src/tests/test_exact_contract.py` | `044745009da357a34d94d86a06cb2b98867b3a985fea73a19749df36ef4a31f1` |
| `src/tests/test_binding_overload_separation_override.py` | `6d6a34b7ebb14eecb64d6729453e876d26ca7fe4903dd5831702ec9bb602eeb9` |
| `src/tests/test_power_witness_cut_dilution.py` | `4560ee14e804a440d1301c73e70d94396373055cd065be5bf83ef3afdb6c35fb` |
| `scripts/p2_14_evaluator/run_eval_v1_baseline.py` | `89b21e6f0f2e4b3689f973cd5d4f902ca20ff8f6484f82ba143312f37caec405` |
| `data/knowledge/backfill_reviews.jsonl` | `8eb594c71c37d6602ddc66439256c68e93737812e9b44551f5485b9a94e25885` |

机器收据和本 handoff 不做自引用 SHA；审计应直接读取其当前字节。

## 11. 已知边界

- Windows→WSL PB 完整 proof chain 本轮未重跑；
- historical code-assets replay 仍受缺旧 Git object 限制；
- production/arithmetic/PB 系统穷举、selected-pose membership index、routing exhaustion、master `INFEASIBLE` 与 terminal fixed-witness 语义异构化仍延期；
- 本批未 commit，不修改主仓，不修改 `data/review_gates/**`，不声称 owner re-close。

## 12. 第三轮 verdict 后续

- 若有 finding：同一 worktree 修复，所有封账收据作废，最终字节冻结后整套重跑，再发下一轮；
- 若 clean：由 Claude 侧绑定第三轮全文和最终 receipt，呈 owner re-close；只有 re-close 后才允许处理两条旧 authority parity 红测和合入。

## 13. 第四轮机械修复与外审输入

### 13.1 第三轮报告与执行身份

```text
report  /home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/EXTERNAL_AUDIT_I1_ROUND3_20260820.md
sha256  71b9f0b208b131a013a6895f7ef87d0243e8ab69194129992444f6a63ad1de48
verdict FINDINGS_REQUIRE_FIX
executor Claude 侧机械修复席（Sol）
```

第三轮确认代码方向未见 soundness 破口，但最终字节不可编译、POSTFIX 差分为空跑、知识账本含幽灵路径，且第五个 `PortBindingModel` 构造点未被枚举。本节只记录第四轮机械修复和真实自验；不把 KNOWN_RED、研究收据或测试结果提升为 owner re-close。

### 13.2 缺陷到修复与验证的对照

| 第三轮缺陷 | 第四轮终态改动 | 定点验证 |
|---|---|---|
| `master_model.py` 重复 `utility_operation_by_template` kwarg，compile 阶段报 SyntaxError | `src/models/master_model.py:2846` 只保留一次从 model/plan 快照派生的映射传参 | `compileall`、`src.models.master_model`、`src.search.benders_loop` 和 terminal verifier import 全通过；原 14 条 masked binding 测试为 `14 passed` |
| POSTFIX nodeid 把类名点分段误换成目录，整场 `rc=4 / 0 collected` | 重放器按“最长存在 `.py` 模块前缀”转换，余下点分段转为 `::Class`；旧两份收据不覆盖 | canonical POSTFIX2 与独立 revalidation 均为 baseline `47 passed`、current `47 passed`、`outcome_changes=0`、`baseline_pass_current_fail=0` |
| `test_binding.py` 新增 pose-optional stale double 缺局部 `PortBindingModel` import | `src/tests/test_binding.py:1602` 按该文件既有惯例补局部 import；PR2 的兼容再导出保留并以精确 `noqa: F401` 标注 | changed Python surface 37 文件 ruff PASS；14 条 masked binding 测试全绿 |
| `backfill_reviews.jsonl` current review 登记不存在的 `ROUND2_SELF_CHECK_20260820.json` | 该账本没有 append-only 契约；在同一 current review 中只删除幽灵 `reviewed_paths` 元素，并重建八份生成投影 | `devtools/check_knowledge_docs.py` PASS；changed/framework 中 `knowledge_regressions` PASS |
| P2 #14 evaluator 是第五构造点，三张 plan map 全缺且无 authority 分类 | `scripts/p2_14_evaluator/run_eval_v1_baseline.py:51` 一次读取 `load_binding_plan_semantics()` 并显式传三张 map；证明门登记 `exploratory_evaluation_non_authority` 豁免及理由，并拒绝其进入 cut/reverify funnel | 枚举门定点调用返回 `evaluator_errors=[]`；evaluator 与 proof checker ruff/compile 通过 |
| proof checker 的 `main()` 诊断形状自相矛盾，导致真实义务层被 4 条 preflight 红提前遮蔽 | 允许严格的 `CheckError as exc` 单诊断后 `return 2`，并把合法 `errors` 打印引用纳入 AST 白名单 | 门不再早退，真实运行到完整义务层；后续 28 条 issue 原样列为 KNOWN_RED，不修改禁止的 floor/manifest/语义逻辑 |

### 13.3 第四轮机器收据

```text
canonical diff
  path   docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_POSTFIX2_20260820.json
  sha256 c57860492232108c41edaf23ccd53ee5301b3ba7027766a8e1e81eff834ed99d
  result baseline 47 passed / current 47 passed / zero divergence

independent diff revalidation
  path   .artifacts/i1_round4_self_check_20260820/MASKED_REAL_DIFF_POSTFIX2_REVALIDATION.json
  sha256 b4d9fa61ccf9884183823cdf6ee6d83c6bb01b5ee2a2dd52f794ce2f2d13458e
  result substantive fields exactly match canonical POSTFIX2

total self-check
  path   .artifacts/i1_round4_self_check_20260820/ROUND4_SELF_CHECK_20260820.json
  sha256 f46dd09a1e7221e4e0a99a8ec2d605407caeacb0d31c8be48d7d7c9770520e2a
  status PASS_WITH_KNOWN_REDS
  tally  5 PASS / 10 KNOWN_RED / 0 UNEXPECTED_RED
  bearing_digest 40d89397bd1a0b8edc2560cb4e138d1e289dfadd8cf09ead42df7a3d60bb18fe
```

`PASS_WITH_KNOWN_REDS` 只表示全部 15 道命令都得到预期分类且无未解释红，不表示代码面全绿。每条命令都有起止时间、return code、独立 stdout/stderr 文件及 SHA-256；JUnit 命令另有逐 node 计数。日志先在 worktree 外暂存，knowledge/code-assets 门完成后再原子搬入 `.artifacts`，避免 in-progress 本地证据目录污染自身门；搬入后 bearing digest 再核仍不变。两棵 worktree 的临时候选工件均已删除，index 为空，主仓只读。

### 13.4 第四轮第一批自验快照（G3 收尾前）

| 门 | 终态 | 结果或原因 |
|---|---|---|
| compile/import smoke | PASS | `master_model`、`benders_loop`、terminal verifier、P2 evaluator 全可编译/import |
| ruff changed surface | PASS | 37 个 Python 文件，0 issue |
| strict mypy preflight core | KNOWN_RED | 13 文件中 12 文件共 144 errors；为既存 checker AST typing、master duplicate definitions、OR-Tools/sidecar 类型债，超出机械清单 |
| closed package + PR2 + heuristic mypy | KNOWN_RED | 11 文件中 3 文件共 9 errors；含 `BindingSemanticModel.runtime_relaxations` 缺失与既存 PR2/heuristic 类型债 |
| focused pytest | KNOWN_RED | 333 tests：318 passed / 12 failed / 3 skipped；11 条为 runtime-relaxation model/checker 脱节，1 条为既存 Stage-B alias digest 漂移；3 个真实工件案在 focused 中按测试契约 skip，另行真跑 |
| 真实工件三案 | KNOWN_RED | 3 failed / 0 skipped；production 运行到终点，但 I1 因 `BindingSemanticModel` 缺 `runtime_relaxations` 返回 `EXCEPTION` |
| 47-node 双侧真差分 | PASS | baseline 47 passed、current 47 passed、零分叉；两次独立真放实质一致 |
| P1.2 draft proof gate | KNOWN_RED | 28 issues：strong-status allowlist、7 个 manifest test anchor、sink/v99 floor、runtime anchor 与旧 operation-map AST 断言；禁止 reseal |
| strong-status | KNOWN_RED | heuristic allowlist hash/写入位置 12 条漂移；allowlist 位于禁止修改的 `data/proof_obligations` |
| knowledge check | PASS | 幽灵路径消失，知识真源与八份生成投影一致 |
| docctl doctor | KNOWN_RED | 05:33–06:13 早批文档系统改动导致 maintenance projection stale；按任务书不改 |
| docctl changed | KNOWN_RED | 仅 `docsystem_changed`、`docsystem_doctor`、`document_system_regressions`、`maintenance_audit_regressions` 四 lane BLOCK；knowledge lanes 已 PASS |
| docctl framework | KNOWN_RED | 仅 document-system self-consistency 与 maintenance-projection 两 lane BLOCK，归属早批文档系统改动 |
| current code-assets | PASS | current worktree inventory PASS；historical replay 未运行 |
| sealed-authority 两红测 | KNOWN_RED（预期） | 精确 2 tests / 2 failures / 0 errors / 0 skipped；唯一差异仍是旧 floor `34e198fc…` 与 `benders_loop.py` `461fc687…` |

### 13.5 第四轮外审建议重点

1. 先攻击清单外新暴露的 `certificate.py:115`：checker 读取 `BindingSemanticModel.runtime_relaxations`，而 model 只公开 `routing_context_relaxation_active`。它使真实三案全红，是当前最直接的运行阻断；本机械席因 certificate/semantics 语义边界未修。
2. 核对 `master_model.py` 中 mypy 报出的重复 `_resolve_utility_operation_by_template` 定义与连续两次局部变量声明。这些不属于第三轮指定的 `:2847` 重复 kwarg，第四轮未越界处理。
3. 独立复算 proof gate 的 28 条 issue，区分禁止 floor/manifest reseal、旧 checker 断言和真正实现缺口；不得把门终于能报告完整问题误读为第四轮新引入 28 个缺陷。
4. 复核 P2 #14 evaluator 的 authority 豁免是否充分：它必须继续保持离线 baseline/hint 评估性质，不能进入 `reverify_whole_layout_infeasibility`、persisted nogood 或 publication 状态。
5. 对 canonical POSTFIX2 的 47 个 converted nodeid 逐条检查，尤其确认 `test_witness_fixed_geometry_router.py::FixedGeometryRouterWorkerTests::...` 没有再被转成目录路径；同时核对两侧 outcome 不是空集。
6. 把 05:33–06:13 文档系统批次与 I1 提交面继续切开。doctor/changed/framework 的已知红不能由本批静默修复，也不能归咎于幽灵 review 路径。
7. 核验总收据的 staging/relocation 字段、每条 stdout/stderr SHA、receipt mtime 与 bearing digest；`.artifacts` 日志出现于门运行之后，不参与承重字节。
8. 本轮仍是 `NOT_RE_CLOSED / NOT_COMMITTED`。只有第四轮外审裁 clean 并经 owner re-close，才允许处理 sealed-authority floor 或合入。

### 13.6 G3 runtime-relaxation 接口收尾与 ROUND4B 自验

`BindingSemanticModel`、证书生成器和独立 checker 现共享同一运行时松弛序列：

- `src/search/independent_binding_reverify/semantics.py:153` 增加不可变字段 `runtime_relaxations: tuple[str, ...]`；
- `src/search/independent_binding_reverify/semantics.py:484` 按 `_validate_semantics_contract()` 返回的实际 routing 布尔填充：true 时为单 token tuple，false 时为空 tuple；
- `src/search/independent_binding_reverify/theorem.py:49` 直接把 model 字段序列化为证书数组，不再独立重算；
- `src/search/independent_binding_reverify/certificate.py:43-118` 的 exact key set、数组类型、非空字符串、无重复、routing 布尔预期和 model 精确一致规则保持不变。

| 受影响门 | ROUND4 | ROUND4B |
|---|---|---|
| compile/import smoke | PASS | PASS |
| ruff changed surface | PASS | PASS |
| closed package + PR2 + heuristic mypy | 9 errors / 3 files；含 1 条缺失 `runtime_relaxations` | 8 errors / 2 files；缺失属性为 0，余下均为 PR2/heuristic 既存债 |
| focused pytest | 318 passed / 12 failed / 3 skipped；11 条同根因 | 329 passed / 1 failed / 3 skipped；仅 Stage-B alias digest 漂移 |
| 真实工件三案 | 0 passed / 3 failed | 3 passed / 0 failed / 0 skipped |
| P1.2 draft proof gate | 28 issues | 29 issues；新增项仅为本批改动 `theorem.py` 后预期的 close-kernel sink hash drift |
| strong-status | 12 findings | 12 findings，形状不变 |

```text
ROUND4B receipt
  path    /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504/.artifacts/i1_round4_self_check_20260820/ROUND4B_SELF_CHECK_20260820.json
  sha256  d72c34a3a53c0b58c5cc54ab1805c106530dd8962e1bc0715c36c6b68c6312f6
  status  PASS_WITH_KNOWN_REDS
  tally   3 PASS / 4 KNOWN_RED / 0 UNEXPECTED_RED
  bearing 2edc4d64607ee9d58181e31d1ef1a6a655ee6346e4694eda3de1af95ec14a403
  max bearing input mtime_ns 1787283632688818593
  receipt mtime_ns           1787284182424108934
```

收据逐命令记录 return code、stdout/stderr SHA-256；pytest 另记 JUnit SHA 与逐 node 计数。两次真实工件临时接入均在 `finally` 删除，index 为空。收据写后 bearing snapshot 重算一致；代码与收据字节此后冻结，HANDOFF 和 `.artifacts/**` 明确不进入 bearing digest。

### 13.7 剩余红三桶归属（第四轮外审前快照；当前清单见 §14.5）

#### 13.7.1 属 reopen/re-seal 流程

| 红点 | 桶 | 理由 |
|---|---|---|
| sealed-authority：`test_p1_2_manifest_and_registered_sink_bytes_remain_at_sealed_hashes` | reopen/re-seal | 唯一失败是旧 floor `34e198fc…` 与当前 `benders_loop.py` 字节不符；测试与 floor 均禁止在未重开时修改。 |
| sealed-authority：`test_protected_surfaces_match_398f872_except_authorized_preflight_successor` | reopen/re-seal | 同一旧 authority floor 漂移；属于 owner 重开—重关，不是实现修复。 |
| strong-status：`heuristic_feasible_finder.py` source SHA mismatch | reopen/re-seal | allowlist 真源位于禁止修改的 `data/proof_obligations`，需随 reseal 更新。 |
| strong-status：line 323 unregistered `heuristic_status` write | reopen/re-seal | 机械行位漂移必须由 sealed allowlist 重封。 |
| strong-status：line 353 unregistered `heuristic_status` write | reopen/re-seal | 机械行位漂移必须由 sealed allowlist 重封。 |
| strong-status：line 387 unregistered `heuristic_status` write | reopen/re-seal | 机械行位漂移必须由 sealed allowlist 重封。 |
| strong-status：line 417 unregistered `heuristic_status` write | reopen/re-seal | 机械行位漂移必须由 sealed allowlist 重封。 |
| strong-status：line 295 stale allowlist entry | reopen/re-seal | 旧 AST 行位登记失效，真源在 sealed allowlist。 |
| strong-status：line 339 stale allowlist entry（第一项） | reopen/re-seal | 旧 AST 行位登记失效，真源在 sealed allowlist。 |
| strong-status：line 373 stale allowlist entry（第一项） | reopen/re-seal | 旧 AST 行位登记失效，真源在 sealed allowlist。 |
| strong-status：line 403 stale allowlist entry（第一项） | reopen/re-seal | 旧 AST 行位登记失效，真源在 sealed allowlist。 |
| strong-status：line 339 stale allowlist entry（重复登记项） | reopen/re-seal | allowlist 内存在第二条同坐标旧登记，仍只能在重封时清理。 |
| strong-status：line 373 stale allowlist entry（重复登记项） | reopen/re-seal | allowlist 内存在第二条同坐标旧登记，仍只能在重封时清理。 |
| strong-status：line 403 stale allowlist entry（重复登记项） | reopen/re-seal | allowlist 内存在第二条同坐标旧登记，仍只能在重封时清理。 |
| proof gate：strong-status checker composite failure | reopen/re-seal | 上述 12 条作为一个 proof-gate issue 上浮，根因仍是 sealed allowlist。 |
| proof gate：close-kernel sink hash drift `scripts/check_p1_2_proof_obligations.py` | reopen/re-seal | registered sink 字节已改，需重开 close claim 后重封 SHA。 |
| proof gate：close-kernel sink hash drift `src/models/master_model.py` | reopen/re-seal | registered sink 字节已改，需重开 close claim 后重封 SHA。 |
| proof gate：close-kernel sink hash drift `src/search/pr2_l0_fixed_witness_core.py` | reopen/re-seal | registered sink 字节已改，需重开 close claim 后重封 SHA。 |
| proof gate：close-kernel sink hash drift `src/search/independent_binding_reverify/theorem.py` | reopen/re-seal | ROUND4B 因 G3 接线新增的预期机械 SHA 红；实现测试已绿。 |
| proof gate：`binding_subproblem.py` v99 `source_sha256` 未 reseal | reopen/re-seal | v99 封印哈希落后于当前字节。 |
| proof gate：`binding_subproblem.py` current hash drift from v99 floor | reopen/re-seal | 同一 sealed floor 的当前字节对账红。 |
| proof gate：`master_model.py` v99 `source_sha256` 未 reseal | reopen/re-seal | v99 封印哈希落后于当前字节。 |
| proof gate：`master_model.py` current hash drift from v99 floor | reopen/re-seal | 同一 sealed floor 的当前字节对账红。 |
| proof gate：`benders_loop.py` v99 `source_sha256` 未 reseal | reopen/re-seal | v99 封印哈希落后于当前字节。 |
| proof gate：`benders_loop.py` current hash drift from v99 floor | reopen/re-seal | 同一 sealed floor 的当前字节对账红。 |
| proof gate：`heuristic_feasible_finder.py` v99 `source_sha256` 未 reseal | reopen/re-seal | v99 封印哈希落后于当前字节。 |
| proof gate：`heuristic_feasible_finder.py` current hash drift from v99 floor | reopen/re-seal | 同一 sealed floor 的当前字节对账红。 |
| proof gate：`certificate.py` v99 `source_sha256` 未 reseal | reopen/re-seal | v99 封印哈希落后于当前字节。 |
| proof gate：`certificate.py` current hash drift from v99 floor | reopen/re-seal | 同一 sealed floor 的当前字节对账红。 |
| proof gate：`semantics.py` current hash drift from v99 floor | reopen/re-seal | 当前字节已含 runtime-relaxation 接线，需在重封时更新 floor。 |
| proof gate：`theorem.py` v99 `source_sha256` 未 reseal | reopen/re-seal | v99 封印哈希落后于当前字节。 |
| proof gate：`theorem.py` current hash drift from v99 floor | reopen/re-seal | 当前字节已改为消费 model 字段，需在重封时更新 floor。 |
| proof gate：`pr2_l0_fixed_witness_core.py` v99 `source_sha256` 未 reseal | reopen/re-seal | v99 封印哈希落后于当前字节。 |
| proof gate：`pr2_l0_fixed_witness_core.py` current hash drift from v99 floor | reopen/re-seal | 同一 sealed floor 的当前字节对账红。 |
| proof gate：certified artifact runtime-anchor semantic projection SHA | reopen/re-seal | runtime anchor 是 checker floor 的字节承诺，本批不允许直接刷新。 |

#### 13.7.2 真缺陷待后批修复

| 红点 | 桶 | 理由 |
|---|---|---|
| proof gate：缺 `test_round3_certificate_checker_rejects_runtime_relaxation_tamper` required-test anchor | 真缺陷待修 | 测试已存在，名称仅写入门不消费的 `test_anchors`，未进入实际校验的 `required_tests`；不是新文件登记或 SHA floor 问题。修复落点在 sealed manifest，执行仍需先 re-open。 |
| proof gate：缺 `test_round3_checker_enumerates_non_controller_binding_constructors` required-test anchor | 真缺陷待修 | 同一 manifest 字段误登记。 |
| proof gate：缺 `test_round3_checker_rejects_constant_runtime_observation` required-test anchor | 真缺陷待修 | 同一 manifest 字段误登记。 |
| proof gate：缺 `test_round3_checker_rejects_generic_input_plan_bypass` required-test anchor | 真缺陷待修 | 同一 manifest 字段误登记。 |
| proof gate：缺 `test_round3_checker_requires_runtime_relaxation_validation` required-test anchor | 真缺陷待修 | 同一 manifest 字段误登记。 |
| proof gate：缺 `test_round3_exact_session_carries_plan_utility_operation_map` required-test anchor | 真缺陷待修 | 同一 manifest 字段误登记。 |
| proof gate：缺 `test_round3_pose_optional_synthesis_loads_plan_utility_map` required-test anchor | 真缺陷待修 | 同一 manifest 字段误登记。 |
| proof gate：`PortBindingModel` operation-map surface found `_utility_operation_by_template` 与 `_pose_optional_operation_by_template` | 真缺陷待修 | checker 要求单一且名为 `utility_operation_by_template` 的消费属性，production 保存完整 source map 与派生过滤视图；需后批裁定消除重复状态还是修正 AST 义务，单纯 reseal 不能解决。 |
| strict mypy preflight core：144 errors / 12 files | 真缺陷待修 | checker AST typing、sidecar import/type annotation、OR-Tools stub 与生产代码返回类型等既存债，不是封印 SHA。 |
| closed-package mypy：`heuristic_feasible_finder.py:136` arg-type | 真缺陷待修 | `facility_pools` 的抽象容器类型与 `PortBindingModel` 构造签名不一致。 |
| closed-package mypy：`heuristic_feasible_finder.py:153` return-value | 真缺陷待修 | 返回 tuple 的 list element 抽象类型不一致。 |
| closed-package mypy：`pr2_l0_fixed_witness_core.py:132` no-any-return | 真缺陷待修 | 声明返回 dict 的函数泄漏 `Any`。 |
| closed-package mypy：`pr2_l0_fixed_witness_core.py:348` `CpModel.AddBoolOr` attr-defined | 真缺陷待修 | OR-Tools typing surface 未对齐。 |
| closed-package mypy：`pr2_l0_fixed_witness_core.py:1993` no-any-return | 真缺陷待修 | 声明返回 list[dict] 的函数泄漏 `Any`。 |
| closed-package mypy：`pr2_l0_fixed_witness_core.py:2023` no-any-return | 真缺陷待修 | 声明返回 list[dict] 的函数泄漏 `Any`。 |
| closed-package mypy：`pr2_l0_fixed_witness_core.py:2205` no-untyped-def | 真缺陷待修 | 函数缺返回类型标注。 |
| closed-package mypy：`pr2_l0_fixed_witness_core.py:2214` assignment | 真缺陷待修 | `str | None` 赋给 `str`。 |
| `master_model.py:2022/2078` `_resolve_utility_operation_by_template` 重复定义 | 真缺陷待修 | mypy `no-redef`，是 production 源码重复实现，不是 floor 漂移。 |
| `master_model.py:2407/2408` `utility_operation_by_template` 连续重复声明 | 真缺陷待修 | mypy `no-redef`，是局部源码重复声明。 |
| focused：Stage-B coordinate delegate alias digest `ba1baf…`→`c0e07e…` | 真缺陷待修 | 需后批判断 dataflow surface 实质变化并更新实现或 digest；不属于 I1 G3。 |

#### 13.7.3 早批文档归属

| 红点 | 桶 | 理由 |
|---|---|---|
| `docctl doctor` maintenance projection stale | 早批文档归属 | 由 05:33–06:13 文档系统批次造成，随该批切分处理。 |
| changed gate：`docsystem_changed` | 早批文档归属 | 唯一 blocker 是 maintenance projection stale。 |
| changed gate：`docsystem_doctor` | 早批文档归属 | 同一早批投影未刷新。 |
| changed gate：`document_system_regressions` | 早批文档归属 | self-consistency 测试只见 maintenance projection stale。 |
| changed gate：`maintenance_audit_regressions` | 早批文档归属 | `docs/MAINTENANCE_QUEUE.md` 与早批真源投影不一致。 |
| framework gate：`document_system_regressions` | 早批文档归属 | 64 条中仅 real-repository self-consistency 因 stale projection 红。 |
| framework gate：`maintenance_audit_regressions` | 早批文档归属 | 9 条中仅 phase-close projection freshness 红。 |

### 13.8 ROUND4B 边界

- G3 接口断裂已消除；真实三案与同根因 focused 11 条均复绿；
- ROUND4B 不修改 `data/proof_obligations/**`、`data/review_gates/**`、review gate 或两条 sealed-authority 测试；
- 未处理 Stage-B alias digest、master 重复定义、既存 mypy 债、operation-map checker/model 契约和早批文档 lane；
- 本 worktree 仍未 commit、未 re-close，主仓真实工件只读临时接入且已删除。

### 13.9 清单外发现

- 在 ROUND4/ROUND4B 日志已经落入 `.artifacts/i1_round4_self_check_20260820` 的当前 worktree 上，`devtools/check_knowledge_docs.py` 会以 `unregistered=.artifacts/i1_round4_self_check_20260820` 阻断。ROUND4 收据中的 knowledge PASS 发生在日志仍暂存于 worktree 外、证据目录尚未搬入之前；该目录登记属于证据治理后续，不由 G3 接口修复处理。
- `docctl intake --changed` 通过事件分类，但继续报告 `data/proof_obligations/p1_2_proof_obligations.json` 缺 authority-change companion 的既有 warning；本批不修改 owner-governed authority companion。

## 14. 第四轮外审修复与第五轮输入

### 14.1 第四轮外审坐标

```text
report  /home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/EXTERNAL_AUDIT_I1_ROUND4_20260820.md
sha256  e25c3d413e590d83d408a154564d8bbaea9ee50765111695ea8c2936beb1330f
verdict FINDINGS_REQUIRE_FIX
scope   代码面与既有收据面通过；修复范围限于证据登记、三桶账本、可复现 argv 与最终全门收据
```

第四轮外审未发现 soundness 破口或虚构收据。阻断项是一个证据登记缺口、一组 required-test/覆盖文字失真，以及四项收据和归属精度问题；这些修复没有修改 sealed authority、proof-obligation floor、review gate、certificate/theorem/semantics 逻辑或 05:33–06:13 早批真源。

### 14.2 F-1 至 F-6 修复对照

| 外审项 | 终态修复 | 验证 |
|---|---|---|
| F-1 BLOCKER：收据目录未登记 | 按一级 `.artifacts/<package>` 的仓内机制运行 `docctl register-local-evidence`，在 `data/knowledge/dossiers.json` 登记 `DOSSIER-I1-ROUND4-SELF-CHECK-20260820-0CFC3F056C`；manifest 为冻结的 ROUND4B 收据，恢复说明为 tracked `.artifacts/README.md`；`knowledge_census.dossiers_total` 227→228，并重建八份知识投影。`artifact_evidence_inputs.json` 只负责 direct root files，因此不添加目录项。 | knowledge rc 1→0；code-assets current rc 1→0；changed 从 8 个 BLOCK 收敛到 4 个既有文档系统 BLOCK。 |
| F-2 HIGH：required-test 与覆盖账本不实 | 7 条 anchor 拆成 3 条“测试实存但字段未消费”与 4 条“具名测试不存在”；新增 checker 规则零 mutation 覆盖一行；范围决定显式留给 owner。 | 全仓 tracked 符号搜索：3 条实存、4 条零定义；新增诊断串只有 checker 本体命中，无测试引用。 |
| F-3 MEDIUM：mypy argv 不可字面重放 | ROUND4C 两条 mypy 命令都在 argv 数组和 `command_display` 中记录 `--follow-imports=silent`。 | strict core 精确复现 144 errors / 12 files / 13 checked；closed package 精确复现 8 errors / 2 files / 11 checked。 |
| F-4 LOW：重复解析函数理由不足 | 桶②明确记录两个同名函数语义不同：先定义版本在映射歧义时 raise；遮蔽后存活版本静默丢弃歧义项。后批目标是消除语义分叉并恢复现场 fail closed，不只是删除 `no-redef`。 | 第四轮外审读码坐标 `master_model.py:2022/2078`；本批不改实现。 |
| F-5 LOW：`MAINTENANCE_QUEUE.md` 批次归属错误 | 桶③明确记录该文件 mtime 为 `2026-08-20 15:05:36.744456 -07:00`，属于 GPT 第三棒执行期；对应 lane 的根因仍是 05:33–06:13 早批真源未形成新鲜 phase-close projection。 | mtime_ns `1787263536744455602`；不把输出文件自身归入早批窗口。 |
| F-6 LOW：最终字节未跑满 15 门 | 新建 ROUND4C 收据，按 ROUND4 的 15 门顺序在登记后的最终承重字节上全部重跑。 | 6 PASS / 9 KNOWN_RED / 0 UNEXPECTED_RED；62 个承重文件前后 digest 与 mtime 全同。 |

### 14.3 F-1 三门登记前后对照

| 门 | 登记前 | 登记后 / ROUND4C | 收敛结论 |
|---|---|---|---|
| `devtools/check_knowledge_docs.py` | rc=1，`unregistered=.artifacts/i1_round4_self_check_20260820` | rc=0，PASS | 证据目录进入中央 dossier inventory，知识真源与投影新鲜。 |
| `devtools/check_repository_code_assets.py check-current` | rc=1，workspace-untracked `.artifacts` 路径缺 local evidence declaration | rc=0，PASS | 一级目录由 dossier registry 派生为合法 evidence boundary。 |
| `devtools/docctl.py gate --profile changed` | rc=1，8 个 BLOCK：4 个文档系统 lane + `knowledge_integrity`、`knowledge_regressions`、`code_assets_current`、`code_assets_regressions` | rc=1，4 个 BLOCK：`docsystem_changed`、`docsystem_doctor`、`document_system_regressions`、`maintenance_audit_regressions` | F-1 同根因 4 lane 全部消失；剩余 4 lane 是既有文档系统批次。 |

登记前后日志及其 stdout/stderr SHA 已纳入 ROUND4C 收据的 `f1_registration_gate_comparison`，并验证 `verified_8_to_4_lane_convergence=true`。

### 14.4 required-test 事实与待 owner 范围决定

以下 3 个具名测试实存，但当前只位于门不消费的 `test_anchors`，未进入 `required_tests`：

- `test_round3_certificate_checker_rejects_runtime_relaxation_tamper` — `src/tests/test_p1_2_independent_infeasibility_reverifier.py`；
- `test_round3_exact_session_carries_plan_utility_operation_map` — `src/tests/test_exact_contract.py`；
- `test_round3_pose_optional_synthesis_loads_plan_utility_map` — `src/tests/test_binding.py`。

以下 4 个具名测试在 tracked 源码中没有定义；按当前 checker 要求，后批不能只移动 manifest 字段，必须先新增对应测试再登记：

- `test_round3_checker_enumerates_non_controller_binding_constructors`；
- `test_round3_checker_rejects_constant_runtime_observation`；
- `test_round3_checker_rejects_generic_input_plan_bypass`；
- `test_round3_checker_requires_runtime_relaxation_validation`。

其中 constant-runtime 与 generic-input 的部分语义已有 `test_package_checker_rejects_constant_runtime_contract_fields`、`test_package_checker_requires_plan_derived_generic_input_admission` 覆盖，但这不使上述 4 个具名符号存在，也不覆盖全部新增 checker 规则。当前没有 mutation 测试保护 runtime-relaxation 证书/model 双校验、五个 `PortBindingModel` 构造点枚举和 evaluator `exploratory_evaluation_non_authority` 豁免；删除这些 checker 规则不会使现有测试变红。

**待 owner 裁的范围决定：**

| 选项 | 做法 | 代价 |
|---|---|---|
| A：补 mutation 测试 | 为 runtime-relaxation 校验、五构造点枚举、evaluator 豁免及当前缺失的具名 anchor 建立真正击中 checker mutation 的测试，再写入 `required_tests`。 | 工作量与维护面较大，但每条新增守卫都有直接回归保护，要求集与测试名一一对账。 |
| B：修正 checker 要求集 | 把确有等价既有覆盖的要求改指向实存测试名，并删除或改写错误的具名要求；对仍无等价覆盖的新增 checker 规则是否接受暂时无 mutation 保护，需要一并明确。 | 改动较小，但必须逐项证明语义等价；若不另补测试，会显式保留“守卫自己没人守”的回归风险。 |

本批不选择 A 或 B，也不修改 sealed manifest/checker 要求集。

### 14.5 当前剩余红三桶清单

本节取代 §13.7 作为 owner 重开—重关决策的当前清单。

#### 14.5.1 桶①：reopen/re-seal（35 行）

§13.7.1 的 35 个逐项红点原样有效，第四轮外审逐条确认无误塞。本桶计数校验为：sealed-authority 2 + strong-status 12 + proof-gate strong-status composite 1 + close-kernel sink 4 + v99 floor 15 + runtime anchor 1 = **35**。本批没有修改其中任何测试、floor、allowlist 或 manifest。

#### 14.5.2 桶②：真缺陷待后批修复（21 行）

| # | 红点 | 理由 |
|---:|---|---|
| 1 | 缺 `test_round3_certificate_checker_rejects_runtime_relaxation_tamper` required-test anchor | 测试实存，但只登记在门不消费的 `test_anchors`；sealed manifest 重开后才能修正。 |
| 2 | 缺 `test_round3_checker_enumerates_non_controller_binding_constructors` required-test anchor | 具名测试全仓不存在；按当前要求须先造测试再登记，或由 owner 选择修正要求集。 |
| 3 | 缺 `test_round3_checker_rejects_constant_runtime_observation` required-test anchor | 具名测试全仓不存在；存在部分等价语义测试不等于该符号存在，处置取决于 owner 对 A/B 的裁定。 |
| 4 | 缺 `test_round3_checker_rejects_generic_input_plan_bypass` required-test anchor | 具名测试全仓不存在；存在部分等价语义测试不等于该符号存在，处置取决于 owner 对 A/B 的裁定。 |
| 5 | 缺 `test_round3_checker_requires_runtime_relaxation_validation` required-test anchor | 具名测试全仓不存在；按当前要求须先造测试再登记，或由 owner 选择修正要求集。 |
| 6 | 缺 `test_round3_exact_session_carries_plan_utility_operation_map` required-test anchor | 测试实存，但只登记在门不消费的 `test_anchors`；sealed manifest 重开后才能修正。 |
| 7 | 缺 `test_round3_pose_optional_synthesis_loads_plan_utility_map` required-test anchor | 测试实存，但只登记在门不消费的 `test_anchors`；sealed manifest 重开后才能修正。 |
| 8 | 新增 checker 规则零 mutation 测试覆盖 | runtime-relaxation 证书/model 校验、五构造点枚举与 evaluator 豁免由 checker 守卫，但守卫本身没有测试；A/B 范围决定待 owner 裁。 |
| 9 | `PortBindingModel` operation-map surface 同时存在 `_utility_operation_by_template` 与 `_pose_optional_operation_by_template` | production 保存完整源图与派生过滤视图；需裁定消除重复状态还是修正 AST 义务，单纯 reseal 不能解决。 |
| 10 | strict mypy preflight core：144 errors / 12 files | checker AST typing、sidecar import/type annotation、OR-Tools stub 与生产返回类型等既存债，不是封印 SHA。 |
| 11 | closed-package mypy：`heuristic_feasible_finder.py:136` arg-type | `facility_pools` 抽象容器类型与构造签名不一致。 |
| 12 | closed-package mypy：`heuristic_feasible_finder.py:153` return-value | 返回 tuple 的 list element 抽象类型不一致。 |
| 13 | closed-package mypy：`pr2_l0_fixed_witness_core.py:132` no-any-return | 声明返回 dict 的函数泄漏 `Any`。 |
| 14 | closed-package mypy：`pr2_l0_fixed_witness_core.py:348` `CpModel.AddBoolOr` attr-defined | OR-Tools typing surface 未对齐。 |
| 15 | closed-package mypy：`pr2_l0_fixed_witness_core.py:1993` no-any-return | 声明返回 list[dict] 的函数泄漏 `Any`。 |
| 16 | closed-package mypy：`pr2_l0_fixed_witness_core.py:2023` no-any-return | 声明返回 list[dict] 的函数泄漏 `Any`。 |
| 17 | closed-package mypy：`pr2_l0_fixed_witness_core.py:2205` no-untyped-def | 函数缺返回类型标注。 |
| 18 | closed-package mypy：`pr2_l0_fixed_witness_core.py:2214` assignment | `str | None` 赋给 `str`。 |
| 19 | `master_model.py:2022/2078` `_resolve_utility_operation_by_template` 重复定义 | 两个实现语义不同：先定义版本遇 template→operation 歧义时 raise；遮蔽后存活版本静默丢弃歧义项。后批须消除语义分叉并保留现场 fail closed，而不只是删掉重复定义。 |
| 20 | `master_model.py:2407/2408` `utility_operation_by_template` 连续重复声明 | production 局部源码重复声明，非 floor 漂移。 |
| 21 | focused：Stage-B coordinate delegate alias digest `ba1baf…`→`c0e07e…` | 后批判断 dataflow surface 是否实质变化并更新实现或 digest；不属于 I1 G3。 |

#### 14.5.3 桶③：文档系统外线归属（7 行）

| # | 红点 | 理由 |
|---:|---|---|
| 1 | `docctl doctor` maintenance projection stale | 根因是 05:33–06:13 文档系统早批真源变化，随该批切分处理。 |
| 2 | changed gate：`docsystem_changed` | 唯一 blocker 是 maintenance projection stale。 |
| 3 | changed gate：`docsystem_doctor` | 同一早批投影未刷新。 |
| 4 | changed gate：`document_system_regressions` | self-consistency 测试只见 maintenance projection stale。 |
| 5 | changed gate：`maintenance_audit_regressions` | `docs/MAINTENANCE_QUEUE.md` 当前字节 mtime 为 15:05:36，属于 GPT 第三棒执行期，不在 05:33–06:13 窗口；lane 根因仍是早批真源未形成新鲜 phase-close projection。 |
| 6 | framework gate：`document_system_regressions` | real-repository self-consistency 因同一 stale projection 红。 |
| 7 | framework gate：`maintenance_audit_regressions` | phase-close projection freshness 因同一根因红。 |

**当前三桶合计：35 + 21 + 7 = 63 行。** F-1 登记后消失的 knowledge/code-assets 四个 lane 不再进入剩余红桶。

### 14.6 ROUND4C 最终收据

```text
path       /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504/.artifacts/i1_round4_self_check_20260820/ROUND4C_SELF_CHECK_20260820.json
sha256     b5885dff392bb65a2ac1e1ef88d91b9b5c40903ef307be570305b22cac96f440
status     PASS_WITH_KNOWN_REDS
tally      6 PASS / 9 KNOWN_RED / 0 UNEXPECTED_RED
bearing    3d31ffc15933832f19443db799d6318c997950e0435dc697160d50042dbb6e3d
files      62
max input  1787286114100115546
receipt    1787286686918030365
```

`max input < receipt`，且 receipt 落盘后 bearing snapshot 再算完全相同；收据字节落盘后未修改。全部 15 条命令记录完整 argv、cwd、环境覆盖、return code、起止时间、stdout/stderr SHA；pytest 另有 JUnit SHA 与逐 node 计数。两条 mypy 的实际 argv 为：

```text
/home/zhuran24/zmd-pj/.venv/bin/python -m mypy --strict --explicit-package-bases --follow-imports=silent scripts/check_p1_2_proof_obligations.py src/models/master_model.py src/search/benders_loop.py src/search/certified_artifact_contract.py src/search/independent_infeasibility_reverifier.py certside/sidecar/frontend.py certside/sidecar/emitter.py certside/sidecar/canonical_witness_checker.py certside/sidecar/parity_check.py certside/sidecar/run_acceptance.py src/tests/test_p1_2_independent_infeasibility_reverifier.py src/tests/test_independent_binding_arithmetic_parity.py src/tests/test_independent_binding_real_artifact_parity.py

/home/zhuran24/zmd-pj/.venv/bin/python -m mypy --strict --explicit-package-bases --follow-imports=silent src/search/independent_binding_reverify/__init__.py src/search/independent_binding_reverify/api.py src/search/independent_binding_reverify/artifacts.py src/search/independent_binding_reverify/capsule.py src/search/independent_binding_reverify/certificate.py src/search/independent_binding_reverify/protocol.py src/search/independent_binding_reverify/semantics.py src/search/independent_binding_reverify/theorem.py src/search/independent_binding_reverify/transport.py src/search/pr2_l0_fixed_witness_core.py src/search/heuristic_feasible_finder.py
```

### 14.7 第五轮关键 SHA-256

§10 所列代码、checker 与测试 SHA 未因本批账本修复发生变化。新增或刷新治理面如下：

| 路径 | SHA-256 |
|---|---|
| `data/knowledge/dossiers.json` | `7b2c79d713eab26a18f9e2ea3cd4d326bf26e66e13bc629d9f939f2c9d0b76b3` |
| `data/knowledge/knowledge_census.json` | `76c3fd0ef8ce12b03a161f60f069fee481694d72dcce477fcd60022468623f67` |
| `docs/BACKFILL_LEDGER.md` | `a42721ef7f48cb6f69b5ef72b1c2e2a93b402060ff10b7ae3273bc81856530ab` |
| `docs/CATALOG.md` | `d17f2e4578c849c35e90011c8368940d84d8e5a2951e7355fd1650484287eb44` |
| `docs/CURRENT.md` | `61dc29459a4b2fcae4074d3ff64db40baf1e57c1862f3153ef9c5995d731be61` |
| `docs/OPEN_QUESTIONS.md` | `c891098fa490084b0f67a72cc6b1884de12e5a649100e528b41b89b2e482ba40` |
| `docs/REASONING_LEDGER.md` | `c559d77b9cd32d624fab09acb0bc5ae676a5188659fa1105e05bd846d2a7abe3` |
| `docs/TERMINOLOGY.md` | `edfb5f7ed5700a4d534732f91b6a8317ae37d171a835e489d74a4f2c3fb3586e` |
| `docs/TOPIC_INDEX.md` | `06dd68cc358e64c28a7095427884a11d479f2ca47f34f7d6d3c03a1b24befb66` |
| `docs/VALIDITY_LEDGER.md` | `07b3e8f0d8fa7c5b43839d7d39a482f752784fd711310b99fd73d72542948880` |
| `.artifacts/i1_round4_self_check_20260820/ROUND4C_SELF_CHECK_20260820.json` | `b5885dff392bb65a2ac1e1ef88d91b9b5c40903ef307be570305b22cac96f440` |

HANDOFF 不做自引用 SHA；第五轮应直接读取当前字节。

### 14.8 第五轮复核重点

第五轮只需复核第四轮外审指定的两个面：

1. F-1：确认 dossier 登记、`dossiers_total=228` 与投影 SHA；抽放 knowledge、code-assets current、changed 三门，确认 rc 为 0、0、1，changed 仅剩 4 个文档系统 BLOCK；核对 ROUND4C 的 8→4 日志链。
2. F-2：核对 3 个实存测试与 4 个缺失符号；确认桶②新增“checker 规则零 mutation 覆盖”一行，A/B 范围决定保持待 owner 裁；确认 F-4/F-5 理由已经并入当前清单。

不需要为第五轮复核重跑代码语义、sealed authority 或真实工件全套；ROUND4C 已覆盖最终承重字节。本 worktree 仍为 `NOT_RE_CLOSED / NOT_COMMITTED`，index 为空，主仓只读。


## 15. I1_ACLOSE 范围 A 执行与第六轮输入

### 15.1 状态、上轮判词与执行身份

```text
status    ROUND6_READY
verdict   NOT_RE_CLOSED / NOT_COMMITTED
worktree  /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504
HEAD      aa517cd35e222672f5f6dcd88beba4689c69cf29
commit    none
index     empty（ACLOSE receipt 与文书交付终检均已核验）
```

第五轮外审报告位于：

```text
/home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/EXTERNAL_AUDIT_I1_ROUND5_20260820.md
verdict CLEAN_FOR_REOPEN
```

`CLEAN_FOR_REOPEN` 只允许进入机械 reopen 与 owner 指定的范围 A，不表示 re-close。owner 于 2026-08-20 选择范围 A：re-close 前补齐三组新 checker 守卫的 mutation 测试，使全部 required-test anchor 指向实存测试并进入强制层。

本批由 Opus 协调线拆解派活并裁断；Sol 子席执行两次基底合流、守卫测试补写、五层 reseal 的机械部分和 reopen 登记；Opus 席负责守卫假绿核验与封印范围裁断；2026-08-05 先例考据由 Sol 席完成。执行与核验链是 **Sol 执行 + Opus 核验/裁断**，两源均已深度参与；第六轮外审不应沿用“Sol 执行、Opus 完全外部”的旧身份假设。

### 15.2 两次基底更新与文档系统终态

基底按协调线要求两次更新：

```text
e73add1 → 3b02787 → aa517cd
第一次冲突 12 个；第二次冲突 10 个
```

处置规则没有把生成投影当作 merge 真源：`docs/` 下九张知识投影与 `data/knowledge/knowledge_census.json` 均由机器真源重建；`data/knowledge/dossiers.json` 做并集合并，终态为 272 条，知识门报告无 missing/extra。合并集合包含 upstream 的 43 份 research dossier 与 errata，以及 I1 侧两条登记。

`docs/governance/document-system/MAINTAINING.md` 已按当前测试合同统一维护回归时钟：

```text
data/knowledge/dossiers.json::ledger_reviewed_at     2026-08-20
devtools/tests/test_document_maintenance_audit.py    2026-08-20
全部 active dossier 最新 opened_at/date             2026-08-20
```

三者精确相等；机器断言位于 `src/tests/test_document_system.py:415-439`。基底刷新与全量投影重建消除了 §14.5.3 的七条文档系统红；ACLOSE receipt 中 `docctl doctor`、changed profile、framework profile 均为 PASS。没有借此修改门、测试、authority floor 或 sealed review 记录。

复算：

```bash
cd /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504
/home/zhuran24/zmd-pj/.venv/bin/python devtools/check_knowledge_docs.py
/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py doctor
/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py gate --profile changed
/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py gate --profile framework
```

### 15.3 五个 checker 守卫 mutation 测试

新增测试位于 `src/tests/test_p1_2_independent_infeasibility_reverifier.py:1436-1669`；整文件当前为 60 tests。五个具名测试及其直接攻击面如下：

| 测试 | 目标诊断 | mutation | 非恒真对照 |
|---|---|---|---|
| `test_round3_checker_enumerates_non_controller_binding_constructors` | `must contain exactly one enumerated PortBindingModel constructor; found 2` | 在 heuristic 副本末尾追加顶层 `PortBindingModel(...)` 构造 | 真源路径调用同一 checker，断言诊断不存在 |
| `test_round3_checker_requires_runtime_relaxation_validation` | `must validate theorem runtime_relaxations`；`must compare runtime_relaxations to the reconstructed semantic model` | 错拼 certificate 字段；删除 certificate/model 比较块 | 同上 |
| `test_round3_checker_rejects_constant_runtime_observation` | `binding capability contract field is not wired to its runtime observation` | 四个 contract 字段分别错接到另一非恒定运行时变量 | 同上 |
| `test_round3_checker_rejects_generic_input_plan_bypass` | `production generic-input provider admission must be plan-derived`，且断言诊断计数恰为 2 | input capacity map 改接 output capacity map | 同上 |
| `test_round3_checker_requires_evaluator_non_authority_exemption` | evaluator 豁免元组、理由及 proof-bearing funnel 隔离诊断 | 篡改豁免；向 evaluator 注入 funnel 调用 | 同上 |

删除守卫的离线反证使用当前 checker 的临时副本：逐一删除目标守卫后，每次都只打红对应新增断言；不删除守卫时同一测试集合全绿。第六轮可用独立 basetemp 重放整文件：

```bash
cd /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504
/home/zhuran24/zmd-pj/.venv/bin/python -m pytest -p no:randomly -p no:cacheprovider \
  --basetemp=/tmp/claude-1000/-home-zhuran24-zmd-pj/f6f386e3-1fb1-441b-ae38-2c85b2baf49e/scratchpad/round6-pytest-p1-2 \
  -q src/tests/test_p1_2_independent_infeasibility_reverifier.py
```

### 15.4 required-test anchor 闭合

`obligations[13]` 的 `test_anchors` 从 7 增至 8，新增 `test_round3_checker_requires_evaluator_non_authority_exemption`；`required_tests` 从 48 增至 56。当前八条 anchor 均有唯一实存定义，且八条均进入 `required_tests`：

| anchor | 定义文件 | 强制层 |
|---|---|---|
| `test_round3_checker_rejects_constant_runtime_observation` | `src/tests/test_p1_2_independent_infeasibility_reverifier.py` | 是 |
| `test_round3_checker_rejects_generic_input_plan_bypass` | 同上 | 是 |
| `test_round3_checker_enumerates_non_controller_binding_constructors` | 同上 | 是 |
| `test_round3_checker_requires_runtime_relaxation_validation` | 同上 | 是 |
| `test_round3_certificate_checker_rejects_runtime_relaxation_tamper` | 同上 | 是 |
| `test_round3_pose_optional_synthesis_loads_plan_utility_map` | `src/tests/test_binding.py` | 是 |
| `test_round3_exact_session_carries_plan_utility_operation_map` | `src/tests/test_exact_contract.py` | 是 |
| `test_round3_checker_requires_evaluator_non_authority_exemption` | `src/tests/test_p1_2_independent_infeasibility_reverifier.py` | 是 |

复算口径：读取 `data/proof_obligations/p1_2_proof_obligations.json::obligations[13]`，逐名搜索 `src/tests/**/*.py` 的顶层 `def`，再验证每个名字同时属于 `required_tests`。

### 15.5 五层封印与执行顺序

本批实查封印共有五层；旧 reseal 规程只覆盖前三层中的部分机械面：

| 层 | 载体 | 本批终态 |
|---|---|---|
| ① manifest sink hash（73 项） | `data/proof_obligations/p1_2_proof_obligations.json::close_kernel_contract.sink_files` | 已重签；当前 73/73 与磁盘字节相符 |
| ② checker v99 floor（133 路径） | `scripts/check_p1_2_proof_obligations.py::CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH` | 已重签；当前 133/133 相符，本次处理九项漂移 |
| ③ sealed-authority parity floor | `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` 内硬编码 | 未动；归 owner re-close，必须继续红 |
| ④ strong-status 写点清单 | `data/proof_obligations/strong_status_write_allowlist.json` 与 checker 的 SHA/size 双 pin | 已按最小语义重建，83→79 条；strong-status 门 PASS |
| ⑤ Stage-B 语义封印 | `src/tests/cuts/test_stage_b_contracts.py::_COORDINATE_DELEGATE_ALIAS_USE_DIGEST` | 未收口；见 §15.9.3，保留为本批遗留 |

机械执行顺序为 **A→B→C→D→F→E→V**：

- A：把原有七条 anchor 并入 `required_tests`（48→55）并重算语义投影 P；第五个新测试随后同批补入，使最终数为 56；
- B：把 `certified_artifact_contract.py::LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256` 更新为 P；
- C：把 checker 的 `P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_SHA256` 更新为 P；
- D：把 checker v99 floor 的 133 路径更新到当前字节；
- F：最小重建 strong-status allowlist，并刷新 checker 的 SHA/size 双 pin；
- E：最后更新 manifest 73 sink，使其覆盖 B/C/D/F 的终态字节；
- V：运行终态全量复验。

顺序承重：F 会改变 checker 字节，必须早于 E；`src/search/certified_artifact_contract.py` 同时属于 ①②，B 必须早于 D、E。第四层属于本批范围的明文依据是 `PROJECT_LOCK.md:237-239`：close-kernel 的强状态 allowlist 必须通过，受保护字节漂移后必须按同一工作树重封。

reseal 程序自身采用以下失败保护：

1. floor 或 sink 路径缺失立即硬失败；
2. 每个定点正则要求唯一命中；
3. 重建 allowlist 时，每个 AST finding 的语义元组必须已存在于该模块旧 allowlist，禁止借重建铸造新授权；注入新语义元组已验证会拒绝执行；
4. 写前证明 canonical JSON dump 能逐字节还原原文件，避免序列化漂移；
5. 前后拍全树 SHA，要求新增 0、删除 0、变更集合只允许四个封印文件；
6. 写后运行全量复验；二次运行报告 `files changed: 0`。

重签后 P1.2 proof gate 从 29 条 issue 收敛到 1 条；唯一剩余项是 `PortBindingModel` 同时暴露 `_pose_optional_operation_by_template` 与 `_utility_operation_by_template`。该项是语义结构缺陷，不能由 reseal 消除。strong-status 门已转绿。

### 15.6 73 sink 的 reseal 前后 SHA-256

复算口径严格是“reseal 前 manifest 记录值 → 当前 manifest 记录值”，不是直接把 `git show aa517cd` 的 67 项旧路径集与当前 73 项比较。reseal 前 manifest SHA-256 为：

```text
a64b856489c7397afbfa220b59ad053ccb9ff036376b0d9b36200533063f5647
```

它可由以下 S3 备份 patch 对 `git archive HEAD` 中的 manifest 施加精确 `git apply --include=data/proof_obligations/p1_2_proof_obligations.json` 还原：

```text
/tmp/claude-1000/-home-zhuran24-zmd-pj/f6f386e3-1fb1-441b-ae38-2c85b2baf49e/scratchpad/s3_backup_20260821T090936Z/tracked_worktree.patch
```

前后路径集合均为 73 项、无新增、无删除；**5 项变化、68 项未变**：

| # | sink path | reseal 前 | reseal 后 |
|---:|---|---|---|
| 1 | `scripts/check_p1_2_proof_obligations.py` | `958c9a6195ffb22181456758463e08c8f322f4ac57b4be9110d86be2abbce264` | `d1f05c70fc90b78f0e4662fb7a0757b320bad63feda9a5924eb8e6de17910c80` |
| 2 | `src/models/master_model.py` | `ad7d8a1b698b9451f2a9e5dbb34086cde49b32ef948d06305ebad67e17537258` | `d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371` |
| 3 | `src/search/certified_artifact_contract.py` | `0d8c33834d4b3659dcf82dd2c719a46ec8a35f84ca7f59b893028252cff651ce` | `3bc22369557d2547a40f098e1094da8121ba0ec2ee9c531079c250598bb5e591` |
| 4 | `src/search/independent_binding_reverify/theorem.py` | `e2e572222c89871cf4bd643e9589f1d191e8a128f30fd9ae3fe8897f01927773` | `b3b63bac981b4d17f6efa43dd110ae3ce76f7fb7f6d2aed74545034eb1beceb5` |
| 5 | `src/search/pr2_l0_fixed_witness_core.py` | `622319e552d3f664894dc0e46d9f2262986002b4a74a98c14902955a539afd2f` | `eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1` |

第六轮应读取当前 manifest 的 73 个 `path/source_sha256`，对每个路径直接计算 `sha256sum`；当前自查结果为 mismatch 0。

### 15.7 未动的 authority 面与 reseal 终态

以下文件相对当前 `HEAD aa517cd` 逐字节未变：

| 路径 | 当前 SHA-256 | 与 HEAD |
|---|---|---|
| `data/review_gates/phase_1_2_spike_close.json` | `80bc45f174f18d52d648a80d968a9e178e6ed6da4bbdd71ec89a2d97b59b45dc` | 相同 |
| `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` | `d70b18bf1081056267513451f169fac81280252ca48a8bd5d4ec178878d9d2fe` | 相同 |
| `data/knowledge/decisions.jsonl` | `3ce94d269206885b69cb08e2bf9364cd60e768f921d9b54d9ee9aeb1d5c6020c` | 相同 |

两条 sealed-authority parity 测试仍精确为 2 tests / 2 failures / 0 errors / 0 skipped；旧 floor `34e198fc…` 与当前 `src/search/benders_loop.py` `461fc687…` 不同是唯一根因。本批未 skip、未 xfail、未改 parity 文件、未改 review gate，也没有用 manifest 重签冒充 owner re-close。

五层机械面关键终值：

```text
checker                          d1f05c70fc90b78f0e4662fb7a0757b320bad63feda9a5924eb8e6de17910c80
manifest                         0b828c5bf1e2cee2aa084977d113f82fd9a2cc561124bc86ffffc7e7e52a4b10
certified_artifact_contract.py   3bc22369557d2547a40f098e1094da8121ba0ec2ee9c531079c250598bb5e591
strong-status allowlist          0ca803f1b2a512eb8967ac5eed2b9ffbcf0b3435e8102a4a17f0c7fd5f0799b7
semantic projection P            cc5ed8abbef16c95e4c7e4b758e9478ba7b414bc8cad30a327dde72283f02e94
```

### 15.8 P1.2 mechanical reopen 登记

2026-08-05 先例中的 reopen 主登记位于旧 `docs/项目说明/00_master_roadmap.md` 台账行，结构包含日期、批次身份、授权触发、改动对象、验证状态、显式状态转移、未完成 owner 动作和证据坐标。该先例没有 `DECISION-P1-2-REOPEN-*`：reopen 是 sink 的 mutation policy 机械后果，不是 owner decision。

当前 `00_master_roadmap.md` 已冻结，活载体改为 `docs/项目说明/HISTORY.md:57-65`。本批登记三处：

1. `HISTORY.md` 增加八槽等价记录，明确 `source_sha256_drift_reopens_p1_2_close_claim` 触发 **reopened**，同时明确 owner re-close 尚未发生；
2. `DOSSIER-COMMON-MODE-BINDING-REVERIFY-20260820-0268E9394D` 保持 `lifecycle=active`、`relevance=current_evidence`、`workflow.closure=null`，summary 更新为范围 A 与 reseal 完成后的当前证据状态；
3. `data/knowledge/backfill_reviews.jsonl` 新增 `REVIEW-20260820-COMMON-MODE-BINDING-REVERIFY-ROUND5-REOPEN`，其 `status=current`、`outcome=deferred`、`supersedes` 指向旧 review；旧 review 转为 `superseded`，原语义正文未被改写。

`data/knowledge/decisions.jsonl` 与 `data/review_gates/**` 没有本批 diff；不存在 `DECISION-P1-2-REOPEN-*`。这符合 mechanical reopen 的先例结构，但不产生 re-close authority。

**终态账本陈旧项：** successor review 的 `unresolved` 仍写“ACLOSE_SELF_CHECK 收据尚未落盘”，其 `next_review_trigger` 也包含“ACLOSE_SELF_CHECK 收据落盘”；当前收据已经存在且 SHA-256 为 `887ee04e…`。因此该 review 的触发条件已经满足、文字已落后于当前事实。它是本次文书核验新发现的承重账本陈旧项；因本任务禁止修改承重字节，留给后批新增或更新合规 review，不在 HANDOFF 内伪装为已闭合。

### 15.9 §14.5 三桶清单终态订正

#### 15.9.1 原桶① 35 行逐项处置

原桶①的 35 行中，33 行已由忠实 reseal 消除，2 行按 owner 边界保留。逐项终态如下：

| # | §14.5.1 原红点 | 终态 | 核验 |
|---:|---|---|---|
| 1 | sealed-authority：manifest / registered sink bytes parity | **保留** | parity 测试未动；旧 `34e198fc…` 对当前 `461fc687…`，仍失败 |
| 2 | sealed-authority：protected surfaces parity | **保留** | 同一旧 authority floor，仍失败 |
| 3 | strong-status：heuristic source SHA mismatch | 已消 | allowlist source SHA 重签；strong-status PASS |
| 4 | strong-status：line 323 unregistered write | 已消 | allowlist 最小重建 |
| 5 | strong-status：line 353 unregistered write | 已消 | 同上 |
| 6 | strong-status：line 387 unregistered write | 已消 | 同上 |
| 7 | strong-status：line 417 unregistered write | 已消 | 同上 |
| 8 | strong-status：line 295 stale entry | 已消 | stale 坐标清理 |
| 9 | strong-status：line 339 stale entry（第一项） | 已消 | 同上 |
| 10 | strong-status：line 373 stale entry（第一项） | 已消 | 同上 |
| 11 | strong-status：line 403 stale entry（第一项） | 已消 | 同上 |
| 12 | strong-status：line 339 重复 stale entry | 已消 | 重复登记随最小重建消除 |
| 13 | strong-status：line 373 重复 stale entry | 已消 | 同上 |
| 14 | strong-status：line 403 重复 stale entry | 已消 | 同上 |
| 15 | proof gate：strong-status composite | 已消 | strong-status 子门 PASS |
| 16 | close-kernel sink drift：checker | 已消 | manifest sink 重签 |
| 17 | close-kernel sink drift：`master_model.py` | 已消 | 同上 |
| 18 | close-kernel sink drift：`pr2_l0_fixed_witness_core.py` | 已消 | 同上 |
| 19 | close-kernel sink drift：`theorem.py` | 已消 | 同上 |
| 20 | v99：`binding_subproblem.py` manifest `source_sha256` | 已消 | v99/manifest 当前一致 |
| 21 | v99：`binding_subproblem.py` current hash floor | 已消 | 同上 |
| 22 | v99：`master_model.py` manifest `source_sha256` | 已消 | 同上 |
| 23 | v99：`master_model.py` current hash floor | 已消 | 同上 |
| 24 | v99：`benders_loop.py` manifest `source_sha256` | 已消 | 同上；不等于 parity floor 已更新 |
| 25 | v99：`benders_loop.py` current hash floor | 已消 | 同上 |
| 26 | v99：`heuristic_feasible_finder.py` manifest `source_sha256` | 已消 | 同上 |
| 27 | v99：`heuristic_feasible_finder.py` current hash floor | 已消 | 同上 |
| 28 | v99：`certificate.py` manifest `source_sha256` | 已消 | 同上 |
| 29 | v99：`certificate.py` current hash floor | 已消 | 同上 |
| 30 | v99：`semantics.py` current hash floor | 已消 | 同上 |
| 31 | v99：`theorem.py` manifest `source_sha256` | 已消 | 同上 |
| 32 | v99：`theorem.py` current hash floor | 已消 | 同上 |
| 33 | v99：`pr2_l0_fixed_witness_core.py` manifest `source_sha256` | 已消 | 同上 |
| 34 | v99：`pr2_l0_fixed_witness_core.py` current hash floor | 已消 | 同上 |
| 35 | certified artifact runtime-anchor projection SHA | 已消 | projection P 重签为 `cc5ed8ab…` |

桶①终态：**33 已消 / 2 按边界保留**。不得把 ①②④ 的机械重签误读成第 ③ 层 owner parity floor 已经关闭。

#### 15.9.2 原桶② 21 行逐项处置

| # | §14.5.2 原红点 | 终态 |
|---:|---|---|
| 1 | runtime-relaxation tamper required-test anchor | **已闭合**：实存并进入 `required_tests` |
| 2 | constructor enumeration required-test anchor | **已闭合**：新增实存测试并进入强制层 |
| 3 | constant runtime observation required-test anchor | **已闭合**：新增实存测试并进入强制层 |
| 4 | generic-input bypass required-test anchor | **已闭合**：新增实存测试并进入强制层 |
| 5 | runtime-relaxation validation required-test anchor | **已闭合**：新增实存测试并进入强制层 |
| 6 | ExactSession utility-map anchor | **已闭合**：实存并进入 `required_tests` |
| 7 | pose-optional utility-map anchor | **已闭合**：实存并进入 `required_tests` |
| 8 | 新增 checker 规则零 mutation 覆盖 | **已闭合到范围 A 的五个具名守卫**；每条有删守卫反证。不得扩大解读为整个 checker 已有 mutation 覆盖，见 §15.10.1 |
| 9 | 两张 operation-map 消费属性 | **保留**：proof gate 唯一 1 issue |
| 10 | strict mypy core 144 errors / 12 files | **保留**：KNOWN_RED |
| 11 | heuristic `:136` arg-type | **保留**：closed mypy |
| 12 | heuristic `:153` return-value | **保留**：closed mypy |
| 13 | PR2 `:132` no-any-return | **保留**：closed mypy |
| 14 | PR2 `:348` `AddBoolOr` attr-defined | **保留**：closed mypy |
| 15 | PR2 `:1993` no-any-return | **保留**：closed mypy |
| 16 | PR2 `:2023` no-any-return | **保留**：closed mypy |
| 17 | PR2 `:2205` no-untyped-def | **保留**：closed mypy |
| 18 | PR2 `:2214` assignment | **保留**：closed mypy |
| 19 | `master_model.py` 两个异义同名 resolver | **保留**：先定义 fail closed、后定义静默丢歧义的语义分叉仍需后批处理 |
| 20 | `master_model.py` 连续重复局部声明 | **保留** |
| 21 | Stage-B alias digest | **保留且归属订正**：是本批自己的未收口第五层，不是外来项 |

原桶②的 1–8 已按 owner 范围 A 闭合；9–21 共 13 行仍开放。

#### 15.9.3 Stage-B alias digest 的归属订正

`src/tests/cuts/test_stage_b_contracts.py:851` 在 `HEAD aa517cd` 的 pin 是：

```text
74297d2e9c7679ffcfb7b8f1ee56d74f19dd5c92ae2bbdca9571056283ad6bbc
```

当前 worktree 已把它更新为：

```text
ba1baf510ac63a0a6fc269d521ca19c7b3c18c64f27237b2cd100cc68068d0a8
```

当前实现重新计算得到：

```text
c0e07e47a43311c4facc7e967ea39b86e66851cc2fec5ab157ba6b7fa31498a4
```

这证明本批原本已经把该层纳入 reseal 意图，只是在最终字节集合继续变化后没有再次完成语义收口。因此 §14.5.2 将它写成“不属于 I1 G3”的外来后批项不准确：**它是 I1_ACLOSE 自己的遗留**。本批仍不机械更新 pin，因为必须先判断 coordinate-delegate alias 的 dataflow surface 是否有实质语义变化；该判断属于语义裁断，不属于字节重签。

#### 15.9.4 原桶③七行全部消失

§14.5.3 的 `docctl doctor`、changed 四个 document-system lane、framework 两个 lane均已转绿。根因不是降低门槛，而是两次基底更新带入 main 侧新鲜投影，再由合并后的机器真源全量重建；`ledger_reviewed_at`、maintenance regression clock 与最新 active dossier 日期也已统一。原桶③终态为 **7 已消 / 0 保留**。

原三桶 63 行的终态盘点为：桶①保留 2、桶②保留 13、桶③保留 0，共 **15 行开放项**。ACLOSE receipt 把这些相关项聚合成 5 个 KNOWN_RED 命令分类；“15 行开放项”与“5 个 KNOWN_RED 门”是不同计数口径，不能相加或互换。

### 15.10 交后批、owner 与第六轮外审的新增发现

#### 15.10.1 checker mutation coverage census：48 处零覆盖

对当前 `scripts/check_p1_2_proof_obligations.py::_check_independent_infeasibility_reverifier_contract` 做 AST 串行 census：函数位于 `:14083-14858`，共有 **69** 处 `errors.append(...)`。逐 mutation 删除诊断写点并分别运行本轮五个新测试与其余既有测试，分类为：

```text
本轮五个新测试独家守住   8
既有测试独家守住         9
需要同时删除两份才会红   4
完全零覆盖               48
合计                     69
```

该 census 在范围 A 之外，登记供后批选择是否建立 checker-wide mutation suite。范围 A 的五个测试闭合了指定守卫“是否还在岗”，没有闭合整个函数的 mutation 覆盖。

#### 15.10.2 两组重复守卫的单删静默

当前 checker 存在两组重复诊断：

- generic-output plan-derived：`:14507` 与 `:14688`；
- runtime field must-not-be-constant：`:14263` 与 `:14666`。

单独删除任一副本不会使 60 个测试变红；必须同时删除两份才触发缺口。当前整套测试中，只有 `test_round3_checker_rejects_generic_input_plan_bypass` 对目标诊断使用了严格计数断言，而且它守的是 generic-input，不是上述 generic-output 重复项。后批若保留重复防线，应建立“每个副本各自有作用”的理由与测试；若视为重复实现，应去重并把唯一守卫直接锁住。

#### 15.10.3 五个新测试守的是 token 形状，不是数据流性质

异源核验在当前字节上构造了五个绕过：

1. 把 runtime observation 常量化藏进死分支；
2. 保留要求的直接调用，但丢弃返回值；
3. 以别名 `_M = PortBindingModel` 进行第二次构造；
4. 使用 `import as` 加 `getattr` 进入 proof-bearing funnel；
5. 把关键比较改成 `if False and ...`。

每个绕过都同时满足：被守性质实质失效、结构守卫不报错、五个新增测试保持全绿。结论必须精确表述为：**新增 mutation 测试证明指定 token 守卫仍在，不证明被命名的数据流性质在任意源码改写下仍成立。** 把“五条测试绿”写成“五项性质已由 checker 证明”属于过度解读。

这不是新发现的 production soundness 破口。`PROJECT_LOCK.md` 将该面定义为 small structural close kernel，而不是 theorem prover；威胁模型已经区分：日常手滑与外部篡改由常开的 source SHA floor 阻断，而上述绕过只有在攻击者先忠实 reseal 自己的蓄意改写后才有意义，属于延期的内鬼模型硬化。第六轮应核对 HANDOFF 是否如实保留了这一边界，而不是要求结构 checker 冒充数据流证明器。

#### 15.10.4 owner 范围 A 尚无 tracked authority companion

`docs/research/common_mode_binding_reverify_20260820/OWNER_INSTRUCTION_20260820.md:9` 明确自称“不是 owner authority source”，不能作为 proof-obligation authority-change companion。`data/knowledge/schemas/decision.schema.json` 要求 decision 具备 `authority_source`，知识治理合同要求它指向外部 owner source；当前没有为范围 A 新建 decision，`data/knowledge/decisions.jsonl` 也相对 HEAD 未变。

执行侧若自行把会话转达改造成 companion，就会替 owner 铸权。本批没有这样做。交 owner 裁断二选一：

1. 落一份只覆盖范围 A 原话的窄 companion；
2. 明确授权把仓外会话逐字抄录到 tracked authority source，再由 non-authorizing decision register 引用。

#### 15.10.5 `--refresh-dossiers` 会回退维护时钟并改写无关 dossier

当前 `data/knowledge/dossiers.json::ledger_reviewed_at` 为 `2026-08-20`，而 `data/knowledge/current_state.json` 仍为 `2026-08-18`。`devtools/build_knowledge_docs.py:3554-3557` 的 `refresh_dossiers()` 无条件用后者覆盖前者；`:3474-3484` 又会重写 auto-indexed dossier 的 `entry_file/title/kind/tracked_state/date/topics/summary`。在隔离副本执行：

```bash
/home/zhuran24/zmd-pj/.venv/bin/python devtools/build_knowledge_docs.py --refresh-dossiers --write
```

会把维护时钟退回 `2026-08-18`，并改写两个无关 band22 dossier 的入口、标题与摘要，稳定造成文档回归 1 failed 与 changed gate rc=1。本批用不带 `--refresh-dossiers` 的八条生成命令规避；根因没有修复。第六轮不得在当前冻结 worktree 直接执行该命令，应在一次性副本复现。

#### 15.10.6 pytest 固定 basetemp 的并发陷阱

`pytest.ini:2` 把所有 pytest 进程默认钉在 `<repo>/.pytest_tmp`。并发进程会互相删除该目录；`docs/AGENT_OPERATIONS.md:83` 已明确记录。ACLOSE 的所有 pytest 门均显式传入独立 `--basetemp`。第六轮并行复验也必须为每个进程使用不同目录，不能依赖全局默认值。

#### 15.10.7 reopen review 的收据状态已经陈旧

如 §15.8 所述，`REVIEW-20260820-COMMON-MODE-BINDING-REVERIFY-ROUND5-REOPEN` 仍把“ACLOSE receipt 未落盘”列为 unresolved；当前事实与其相反。该项不是测试红，但会误导后续检索者对 re-close 输入是否完整的判断。第六轮应把它列为治理 finding 或要求后批触发 successor review；不能用本 HANDOFF 的 prose 替代中央 review 真源修复。

### 15.11 ACLOSE 最终自验收据

唯一的 ACLOSE 总收据：

```text
path    /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504/.artifacts/i1_round4_self_check_20260820/ACLOSE_SELF_CHECK_20260820.json
sha256  887ee04e2bd4f35d5e7e7d05bc1b8618052d0cf4cd757c09ff826681751a09db
status  PASS_WITH_KNOWN_REDS
tally   10 PASS / 5 KNOWN_RED / 0 UNEXPECTED_RED
```

承重链：

```text
bearing file count              63
bearing digest                  e4259948ab2a8364d37026cb7faa94adef71f28a26e57908bd3127f71357c8e0
max bearing input mtime_ns      1787305368962747418
receipt mtime_ns                1787306053608327808
receipt > max input             true
before commands digest          e4259948ab2a8364d37026cb7faa94adef71f28a26e57908bd3127f71357c8e0
after commands digest           e4259948ab2a8364d37026cb7faa94adef71f28a26e57908bd3127f71357c8e0
after receipt current recheck   63/63 SHA and mtime exact; mismatch 0
```

HANDOFF、`.artifacts/**`、POSTFIX2 canonical diff 和 `ACLOSE_PROGRESS.md` 在 receipt 中明确列为 nonbearing outputs；本 HANDOFF 不做自引用 SHA。

15 道命令终态：

| 门 | 分类 | 结果 |
|---|---|---|
| compile/import smoke | PASS | rc=0 |
| ruff changed surface | PASS | rc=0 |
| strict mypy core（13 files） | KNOWN_RED | 144 errors / 12 files；排序错误集 SHA `1814084d92f67362ceb8ee4e7b74b82460c67d391895273cb5c4c37539562997` |
| closed package + PR2 + heuristic mypy（11 files） | KNOWN_RED | 8 errors / 2 files；排序错误集 SHA `c5c0674d503f8d912c8d7e0f97bdde8991fbdecac1b197976aab35db21cee4b2` |
| focused pytest | KNOWN_RED | 341 tests：337 passed / 1 failed / 3 skipped；唯一失败为 Stage-B alias digest |
| 真实工件三案 | PASS | 3 passed / 0 failed / 0 skipped |
| 47-node masked real diff POSTFIX2 | PASS | baseline/current 均跑到终点，零分叉 |
| P1.2 proof gate | KNOWN_RED | 恰 1 issue：双 operation-map 消费属性 |
| strong-status | PASS | rc=0，79 条 allowlist |
| knowledge check | PASS | rc=0 |
| docctl doctor | PASS | rc=0 |
| docctl changed | PASS | rc=0 |
| docctl framework | PASS | rc=0 |
| current code-assets | PASS | rc=0 |
| sealed-authority parity | KNOWN_RED（预期） | 2 tests / 2 failures / 0 errors / 0 skipped |

关键日志/JUnit 指针：

| 工件 | SHA-256 |
|---|---|
| `aclose_05_focused_pytest.junit.xml` | `1239b6b1964bad429cd786fbbaf1c580b0fbf5d56afd27a2572169c772834bfc` |
| `aclose_06_real_artifact_three_cases.junit.xml` | `9c3b11a76e5ab5ebd5aee76a85e299bfa8cc736ede5ac48f4dc4df3dd64d6dcf` |
| `aclose_08_p1_2_draft_proof_gate.stdout.log` | `177d1bcc22406978d0df5173d50d661bc0d1f2b1d7ec93050b188e017528c9d8` |
| `aclose_15_sealed_authority_expected_red.junit.xml` | `abe25d7112aca43c4a6d6dd85dd3206de8ab003a1f330873a4cdc510ed708519` |

两条 mypy 门本批把承重比对量改为排序后的错误集合 SHA；原始 stdout/stderr 仍完整落盘并由 receipt 记录 SHA，但不再把并行顺序可能变化的原始输出字节误当承重等价量。

### 15.12 第六轮外审重点与建议顺序

1. **五层封印盘点。** 独立枚举 manifest 73 sinks、v99 133 paths、parity floor、strong-status allowlist 与 Stage-B alias digest；确认 ①②④ 已忠实重签、③未动、⑤明确遗留，没有第六层封印被遗漏。
2. **五个新 mutation 测试的真实能力。** 复跑 60-test 文件和删守卫反证；同时重放 §15.10.3 的五种绕过，确认 HANDOFF 对“token 锁、数据流盲”的描述没有夸大或缩小。
3. **sealed-authority 两红原封不动。** 对 `phase_1_2_spike_close.json`、parity 测试文件和 `decisions.jsonl` 做 HEAD/current 字节比较；核对 JUnit 仍只有两条旧 floor 失败。
4. **receipt 承重面与时间链。** 重算 receipt SHA、63 文件 digest、每个 log/JUnit SHA、`max_input_mtime_ns < receipt_mtime_ns`，并确认 receipt 后 63/63 字节与 mtime 未漂移。
5. **三桶订正。** 抽查原桶① 35 行的 33 消/2 留、桶② 1–8 闭合与 9–21 保留、桶③ 7 行全消；特别核对 Stage-B 是本批遗留，不是外来项。
6. **reopen 治理。** 核对 HISTORY、dossier 与 successor review 的机械 reopen 语义，不接受虚构 `DECISION-P1-2-REOPEN`；同时把 successor review 的“receipt 未落盘”陈旧文字列入 finding。
7. **owner authority 缺口。** 要求范围 A companion 的 owner 处置，不允许执行侧把 `OWNER_INSTRUCTION_20260820.md` 升格为 authority source。
8. **文档刷新回归。** 只在一次性副本复现 `--refresh-dossiers` 的时钟回退和无关 band22 dossier 改写，禁止污染冻结 worktree。
9. **席位独立性。** 本批 Opus 已参与核验和封印裁断，Sol 已执行机械面；第六轮宜优先选未参与本批的外部源。若复用任一来源，报告必须显式披露身份重叠。

### 15.13 ACLOSE 承重面终态 SHA-256

下表是 ACLOSE receipt 冻结的全部 63 个承重输入；它是第六轮复算基线，不表示每个文件都由范围 A 首次创建。HANDOFF 自身不在表内，也不做自引用 SHA。

| 路径 | SHA-256 |
|---|---|
| `.docsystem/manifest.json` | `22c690519ac9f130eef86b9bbb0a97493e0bd1981cc67371df34e73c7eaaa005` |
| `CLAUDE.md` | `89094fcba4992e589620b5464e973f025d5294c8d25ac39958f023bfc706c849` |
| `certside/README.md` | `5e3870eb0e8d65f409c5e5cddc998c1989c98e53099a95583c58a47b58aab25e` |
| `certside/sidecar/canonical_witness_checker.py` | `f0c9b7a59dad2dda120fdcb423d1d26b8861685cb81bce4cbaaec19a8fce74de` |
| `certside/sidecar/emitter.py` | `83188d850d910665dec83ac33cb7e391f95063af4d4f8635401d04923fa44c6d` |
| `certside/sidecar/frontend.py` | `d60c8bf3955f26f85d8087c5553e2398dd0741c8c58bc3579e1c9cc9c0b73f0d` |
| `certside/sidecar/parity_check.py` | `626bd87b3ebb41a99d94c7cafe59126f02fc02ac18068d7873535ea4cc6a95f9` |
| `certside/sidecar/run_acceptance.py` | `18a5e409853b786463de4c21ce4bc31c76a6d01a255bb28524b3303703f1ecc0` |
| `data/knowledge/backfill_reviews.jsonl` | `c9a1492943b799d38875bb4a320355f28cedab1becd2d6b33d55636b271cbfb7` |
| `data/knowledge/dossiers.json` | `f0dedf4d6dc7d7daa33b07ee9313e93044f40db16937a39826b58539e14148e4` |
| `data/knowledge/knowledge_census.json` | `0ee38e639ab953797fbd2cc4130fc5a1423bbc900d2982d34360edf83270752b` |
| `data/proof_obligations/p1_2_proof_obligations.json` | `0b828c5bf1e2cee2aa084977d113f82fd9a2cc561124bc86ffffc7e7e52a4b10` |
| `data/proof_obligations/strong_status_write_allowlist.json` | `0ca803f1b2a512eb8967ac5eed2b9ffbcf0b3435e8102a4a17f0c7fd5f0799b7` |
| `data/repository_governance/code_assets.json` | `26e673edb52f6e33d53a1d7077240f299292e74635a252f9a886ed20c6795819` |
| `devtools/tests/test_repository_code_assets.py` | `e135fa369f5749cd5bdc1e381e7e4334db782369d24871ae62df870ea913ddc8` |
| `docs/BACKFILL_LEDGER.md` | `0f91fb9eddb92eac7b72291df1359cdcf97215d51b2c3ac76ad758e5ff3316f7` |
| `docs/CATALOG.md` | `d183db4f75b3242ba57119160ce088a0feb24f444c8e4c5c8461b07ef5b93736` |
| `docs/CURRENT.md` | `4f03b9a57d0382b78768ac66724cdf12f2be2e46541da7af6922e83252c9ba44` |
| `docs/MAINTENANCE_QUEUE.md` | `d1a8b5a5b8ae96c43761a4e5bd018bad557ba243acc6adaecde57a626d87bc67` |
| `docs/OPEN_QUESTIONS.md` | `80dfbae307ea476e396b86db8529820e18e2243eb63f9ab2ce285b665cb32197` |
| `docs/REASONING_LEDGER.md` | `65d80b81000e80edb4ab001db25cc98e9acd7a2c3bf83fb80956f8ade8ff3b2f` |
| `docs/TERMINOLOGY.md` | `36e5dbcaeebe8dd6ffaa82c67e566a7eb1587554a11d4ab2978919f86687627d` |
| `docs/TOPIC_INDEX.md` | `dbff89cb71431b5075a9a2ee9cba3c62218484dddff47b4310b98b45637df8bc` |
| `docs/VALIDITY_LEDGER.md` | `03831e78610e295e5d50189ce42349e787282229de184494903c77cc70582a8e` |
| `docs/governance/document-system/MAINTAINING.md` | `c92a4e58e554d4403a66546cec48d58a56001bbb6f6eead2469b51402bf7b524` |
| `docs/research/common_mode_binding_reverify_20260820/BASELINE_ATTRIBUTION_20260820.md` | `a59f9024289cc3ab9ac9983d3f30821afd914adad11a524e64a1a4dc1eb87e96` |
| `docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_20260820.json` | `4cf1257f83c0125d5af892b2c1d78445c23f9026e4773f386e4c55298505878b` |
| `docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_POSTFIX_20260820.json` | `e23c1e44111db1e0ba8f978b2e8b4a7c8e090c04986015fb766fe9324cc77973` |
| `docs/research/common_mode_binding_reverify_20260820/OWNER_INSTRUCTION_20260820.md` | `ea37487e9e01dd9dcb89430aec86f5bb7a7071852b05e64975204c9f2ee70261` |
| `docs/research/common_mode_binding_reverify_20260820/README.md` | `4b290df50c271ce5b3f074b10c2e06e0ec4de53c7a21763fe7cf273063b18ffd` |
| `docs/research/common_mode_binding_reverify_20260820/ROUND1_LOW_DISPOSITIONS_20260820.md` | `83a976f226d6ed417a3891a9e920d2e3036169e56511fb966761b3e26794101b` |
| `docs/research/common_mode_binding_reverify_20260820/ROUND2_FINDING_DISPOSITIONS_20260820.md` | `a8b54f4871b93d76f36a57f0f9abe2a188f970ddb18a640c73636a195b37240f` |
| `docs/项目说明/HISTORY.md` | `f175c4b9809d32a1756e75a1d5bdb8ad34f2fa2b1ccb3e9a132e833593fd5fd2` |
| `scripts/check_p1_2_proof_obligations.py` | `d1f05c70fc90b78f0e4662fb7a0757b320bad63feda9a5924eb8e6de17910c80` |
| `scripts/p2_14_evaluator/run_eval_v1_baseline.py` | `89b21e6f0f2e4b3689f973cd5d4f902ca20ff8f6484f82ba143312f37caec405` |
| `src/models/binding_subproblem.py` | `b5c6ebf84b31ef35a73e596d34eab96e2609f08e43cd3c2ff322e369646c5eba` |
| `src/models/master_model.py` | `d1ada57bc6dcef1818341b26dfd482fb7c1623d106734b8f1a49061c2e7c1371` |
| `src/search/benders_loop.py` | `461fc6875ca16781c1d0d81720aee98747a3d2c984a4c1bf1afda4f384af1bc3` |
| `src/search/certified_artifact_contract.py` | `3bc22369557d2547a40f098e1094da8121ba0ec2ee9c531079c250598bb5e591` |
| `src/search/heuristic_feasible_finder.py` | `5c885eca5c683e37e41163a53f3bb5f4c9c5f759ce0f52db7e8d0cc5c779770d` |
| `src/search/independent_binding_reverify/__init__.py` | `7fd71f197586e19a9bb19a55f9d1b2b0e2958e0a8f8c06f2a021c59b0e4f91cc` |
| `src/search/independent_binding_reverify/api.py` | `2e312e17c1b93efbfbd10d8cd2e27a5fa439810ec3633bd917ad80695cb0f28e` |
| `src/search/independent_binding_reverify/artifacts.py` | `0dfa71cd1e74100e2d030263d79762bf570ea8139b37eebc68a029f086c49180` |
| `src/search/independent_binding_reverify/capsule.py` | `c923eb7ab9a858dac549ed083fbc4efaaa289f97131a1fddc2c916d29b896f7d` |
| `src/search/independent_binding_reverify/certificate.py` | `5144ad29f2d92444f0b74143587afc9d4866fa951b0781b4a89b31b74b24bf83` |
| `src/search/independent_binding_reverify/protocol.py` | `16aeea60711fbf7dab8a2c7d7d2109ea18e7ab0e081d6e4c53f6d4bc4af02f1e` |
| `src/search/independent_binding_reverify/semantics.py` | `9582cf325c60e861293cdbf8146672b4ab089c3a9c11d639bbe33ba478acf22e` |
| `src/search/independent_binding_reverify/theorem.py` | `b3b63bac981b4d17f6efa43dd110ae3ce76f7fb7f6d2aed74545034eb1beceb5` |
| `src/search/independent_binding_reverify/transport.py` | `16c7c1158220ee7d4ebf3110f270390c84fd1795b34ef65b043da5d94aa6d5de` |
| `src/search/independent_infeasibility_reverifier.py` | `831fab66ee48baa387e06d0aa3dd7af5a9acd85554d2361698bb141995cbdf8f` |
| `src/search/pr2_l0_fixed_witness_core.py` | `eae892a25f2e97c8f8cca4f58c205c8c18e829c7deba3407628aeab69c79eda1` |
| `src/tests/cuts/test_stage_b_contracts.py` | `75fcf7c0f5ffe07b3b8f7f988d1ab83fed614e4e2248566ae447cad61f371a31` |
| `src/tests/test_binding.py` | `7d35a23a33a4d6f2c22f8711ee18b3e7dcef9ee5f689738b6db825a478f2be68` |
| `src/tests/test_binding_overload_separation_override.py` | `6d6a34b7ebb14eecb64d6729453e876d26ca7fe4903dd5831702ec9bb602eeb9` |
| `src/tests/test_binding_sidecar_projection_parity.py` | `1182f2198452192dcc6c2cffe9c1dfa89e96d1e8e3ce640550c53946afa17f3a` |
| `src/tests/test_document_system.py` | `28e91301fa9d694cba9a62836a583be3ba738708df792bffaeb52d98d4e18b5e` |
| `src/tests/test_exact_contract.py` | `044745009da357a34d94d86a06cb2b98867b3a985fea73a19749df36ef4a31f1` |
| `src/tests/test_independent_binding_arithmetic_parity.py` | `b6168e5d405eacd37d13c7435f9315527fe1d78d73daa3c20ca0168769a3bbec` |
| `src/tests/test_independent_binding_real_artifact_parity.py` | `ab50776402f4ecbae34d4e3843cc255f25973a2fbb2a5548c0abcdb3912c4fc2` |
| `src/tests/test_p1_2_fix_5_toctou_atomic_snapshot.py` | `54f2307f6a95352e67f2069d919f9b248e1f325c75b3d8d0744aef753dcd7ea3` |
| `src/tests/test_p1_2_independent_infeasibility_reverifier.py` | `d245892ff52a6b932ff2aab2500d0a4bbfb4bc4516dd43942ec003cc01aba914` |
| `src/tests/test_power_witness_cut_dilution.py` | `4560ee14e804a440d1301c73e70d94396373055cd065be5bf83ef3afdb6c35fb` |
| `src/tests/test_wireless_front_consumers_r4.py` | `2ea0ef80248dc7187597a48bf505be82d5b1a258b17e177ad6325ca0e732e57e` |

### 15.14 第六轮后的状态机边界

当前唯一合法终判：

```text
ROUND6_READY / NOT_RE_CLOSED / NOT_COMMITTED
```

- 若第六轮有 finding：在同一 worktree 修复后，当前 ACLOSE receipt 作废；重新冻结承重字节、重跑完整 15 门、刷新 HANDOFF，再进入下一轮外审。
- 若第六轮 clean：把第六轮全文、ACLOSE receipt、mechanical reopen 登记和范围 A authority companion 缺口一并呈 owner；只有 owner 显式 re-close 后，才可更新第 ③ 层 parity floor、处理两条旧红测与合入。
- Stage-B 第 ⑤ 层、双 operation-map proof issue、typing 债、checker-wide 48 处零覆盖、`--refresh-dossiers` 回归和 stale successor review 均不得因第六轮 clean 静默消失；各自需要明确后续处置或 owner 边界。
- 本批不 commit、不 `git add`、不修改主仓 tracked 文件；第六轮文书完成后仍须核验 index 为空。

## 16. 第六轮 finding 机械修复与 ROUND6B 输入

### 16.1 当前状态与边界

```text
status    ROUND6B_READY
verdict   NOT_RE_CLOSED / NOT_COMMITTED
worktree  /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504
HEAD      aa517cd35e222672f5f6dcd88beba4689c69cf29
index     empty
```

第六轮外审判词为 `FINDINGS_REQUIRE_FIX`（1 HIGH / 3 LOW / 0 BLOCKER）。本机械批只执行外审处方：回退一行 Stage-B pin、登记四项后续处置、按 ACLOSE 原顺序重跑 15 门并生成新收据。73 sink、133 路径 v99 floor、79 条 strong-status allowlist 和三份 authority 面均未重签或修改。

### 16.2 HIGH-1：Stage-B alias pin 回退与开放单

`src/tests/cuts/test_stage_b_contracts.py::_COORDINATE_DELEGATE_ALIAS_USE_DIGEST` 的处置为：

```text
第六轮修复前 pin   ba1baf510ac63a0a6fc269d521ca19c7b3c18c64f27237b2cd100cc68068d0a8
HEAD 可信基线 pin  74297d2e9c7679ffcfb7b8f1ee56d74f19dd5c92ae2bbdca9571056283ad6bbc
第六轮修复后 pin   74297d2e9c7679ffcfb7b8f1ee56d74f19dd5c92ae2bbdca9571056283ad6bbc
当前实现实算       c0e07e47a43311c4facc7e967ea39b86e66851cc2fec5ab157ba6b7fa31498a4
```

`ba1baf51…` 对应不到任何代码状态，已从机器基线移除。测试继续按预期红，当前可读含义是 **Stage-B alias digest 从 `74297d2e…` 漂移到 `c0e07e47…`**。开放单为：在语义复核 coordinate-delegate alias dataflow 变化后才可重封；禁止把 pin 直接改成当前实现值 `c0e07e47…`，因为那会用字节重签替代语义裁断。

回退后该测试文件 SHA-256 为 `c1ba003306669434be5cb65c4783946e62896f66d5b79af73dc4fc3d9d5005cb`，与 `HEAD aa517cd` 逐字节相同；因此它不再属于未提交承重路径，R6FIX 收据的承重文件数由 63 自然降为 62。

### 16.3 LOW 处置一：checker 48 处零 mutation 覆盖具名清单

口径保持 §15.10.1 的逐 `errors.append` mutation：单独删除写点后，`src/tests/test_p1_2_independent_infeasibility_reverifier.py` 的 60 tests 仍全绿。具名写点如下；这是后批 checker-wide mutation suite 的输入，本批不改 checker 或测试。

| # | checker 行 | 守卫名 / 诊断 |
|---:|---:|---|
| 1 | 14108–14110 | stable binding reverify facade import |
| 2 | 14123–14126 | controller class 无 decorator/base/metaclass |
| 3 | 14129–14133 | controller class 无 attribute lookup/write hooks |
| 4 | 14154–14157 | whole-layout funnel 必须 undecorated |
| 5 | 14159 | funnel 不得 shadow independent reverifier |
| 6 | 14166 | funnel 必须调用 persisted nogood mint |
| 7 | 14168 | independent admission 必须早于 mint |
| 8 | 14177 | capsule admission required-source boundary |
| 9 | 14187 | certified primary/retry construction points |
| 10 | 14210 | binding capability contract required source token |
| 11 | 14212–14214 | contract 必须观察 producing binding model summary |
| 12 | 14228–14231 | contract runtime observation argument |
| 13 | 14238–14240 | contract 恰返回一个 literal object |
| 14 | 14258–14260 | contract observed field 存在性 |
| 15 | 14282 | legacy facade re-export package API |
| 16 | 14284 | legacy facade 不保留 proof implementation |
| 17 | 14301–14305 | closed package 文件集合精确匹配 |
| 18 | 14332–14334 | `import` 非 stdlib 模块禁止 |
| 19 | 14339–14341 | relative import 不得逃逸 closed package |
| 20 | 14350–14352 | `from ... import` 非 stdlib 模块禁止 |
| 21 | 14362–14364 | dynamic import attribute 禁止 |
| 22 | 14381 | dynamic import namespace 禁止 |
| 23 | 14383 | dynamic import string 禁止 |
| 24 | 14390 | `sys.modules` access 禁止 |
| 25 | 14418 | required public function 缺失时传播 `CheckError` |
| 26 | 14431 | package API 直接调用 isolated capsule |
| 27 | 14449 | certificate checker 不得 import theorem builder |
| 28 | 14454 | transport isolation token 完整 |
| 29 | 14456 | transport 不得 `shell=True` |
| 30 | 14489–14493 | `PortBindingModel.build` constraint-family surface |
| 31 | 14521–14524 | provider literal collection 禁止 |
| 32 | 14532–14535 | provider literal mapping 禁止 |
| 33 | 14544–14547 | terminal verifier 加载唯一 plan semantics snapshot |
| 34 | 14556–14558 | terminal verifier 恰构造一个 `PortBindingModel` |
| 35 | 14571–14574 | terminal constructor 三个 plan-derived keyword |
| 36 | 14590–14593 | heuristic path 恰保留一个显式 constructor |
| 37 | 14601–14604 | heuristic constructor non-authority classification |
| 38 | 14632–14635 | contract 恰读取一个 `extract_conflict_summary` |
| 39 | 14650 | contract return object 存在性 |
| 40 | 14664 | runtime field 存在性 |
| 41 | 14673 | plan field 存在性 |
| 42 | 14700–14703 | single consumed utility operation-map surface |
| 43 | 14716–14719 | utility map 恰一次赋值且被 synthesis 消费 |
| 44 | 14724–14726 | fallback 从 preprocess plan 加载 utility map |
| 45 | 14728–14731 | fallback 不得使用 `OPERATION_PORT_PROFILES` |
| 46 | 14744–14747 | LBBDController 恰两个 snapshot-funnel constructors |
| 47 | 14757–14760 | 每个 LBBD constructor 解包 snapshot kwargs |
| 48 | 14838–14841 | 非 controller constructor 三个 plan-derived keyword |

### 16.4 LOW 处置二：重复守卫账订正

§15.10.2 对两组守卫的后批建议由本节取代：

- `:14507` / `:14688` generic-output 组是实测等价重复：predicate、helper 与精确消息均相同；单删任一副本 60 tests 全绿。去重建议只适用于这一组。
- `:14263` / `:14666` runtime-field 组不是等价副本：前者覆盖 `routing_context_enabled`、`overload_separation_enabled`、`reverification_selection_nogood_count`、`source_rejected_selection_count` 四字段，后者只覆盖前三字段；缺字段消息也分别为 `missing observed field` 与 `missing runtime field`。朴素去重会静默丢掉 `source_rejected_selection_count` 覆盖，禁止按“重复实现”直接删除任一整块。

### 16.5 LOW 处置三：proof gate 恰 1 issue 的后批处方

当前 production `src/models/binding_subproblem.py` 与 I1 `src/search/independent_binding_reverify/semantics.py:875` 一带各自实现一次 pose-optional operation-map 过滤。后批应在两侧各保留过滤实现，并补生产过滤与 I1 过滤的 parity 断言；不得为消红删除 `_pose_optional_operation_by_template` 派生属性，也不得在本机械批修改语义逻辑。proof gate 继续以恰 1 issue fail closed。

### 16.6 LOW 处置四：token-lock 内鬼硬化延期项

§15.10.3 的内鬼模型硬化清单增加一个更廉价绕过：删除真实 `runtime_relaxations` 比较逻辑，仅把比较哨兵串原样留在注释中，纯子串守卫仍会满足，指定 mutation 测试保持绿。该项与死分支、丢弃返回值、constructor alias、`import as + getattr`、`if False and ...` 一并进入后批结构守卫硬化；不把范围 A 的 token-lock 测试提升为数据流证明。

### 16.7 R6FIX 15 门收据

```text
path       /home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504/.artifacts/i1_round4_self_check_20260820/ACLOSE_R6FIX_SELF_CHECK_20260820.json
sha256     4c0474fa21e164dd10cc7bfbaaa96e128b4d627de7d2d92696fdab7a280b099c
status     PASS_WITH_KNOWN_REDS
tally      10 PASS / 5 KNOWN_RED / 0 UNEXPECTED_RED
bearing    a8f7a7413d1d3854adfe94d11d0e051fa1dfd8d67e50fab8afa6b554748e42ce
files      62
max input  1787305368962747418
receipt    1787309220274695619
```

冻结纪律成立：before/after/final bearing digest 三次相同，receipt mtime 晚于最大承重输入 mtime，收据落盘后未修改。旧 `ACLOSE_SELF_CHECK_20260820.json` 保留原字节与 SHA-256 `887ee04e2bd4f35d5e7e7d05bc1b8618052d0cf4cd757c09ff826681751a09db`，未被覆盖。

五条 KNOWN_RED 的终态为：strict mypy 排序错误集 SHA `1814084d92f67362ceb8ee4e7b74b82460c67d391895273cb5c4c37539562997`；closed-package mypy 排序错误集 SHA `c5c0674d503f8d912c8d7e0f97bdde8991fbdecac1b197976aab35db21cee4b2`；focused pytest 唯一失败为 Stage-B `74297d2e…→c0e07e47…`；proof gate 恰 1 issue；sealed-authority node-selected 子集恰 2 tests / 2 failures，唯一漂移项均为 `benders_loop.py`。

### 16.8 未动 authority 面与最终 SHA 增量

| 路径 | SHA-256 | 终核 |
|---|---|---|
| `data/review_gates/phase_1_2_spike_close.json` | `80bc45f174f18d52d648a80d968a9e178e6ed6da4bbdd71ec89a2d97b59b45dc` | 与 HEAD 逐字节相同 |
| `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` | `d70b18bf1081056267513451f169fac81280252ca48a8bd5d4ec178878d9d2fe` | 与 HEAD 逐字节相同 |
| `data/knowledge/decisions.jsonl` | `3ce94d269206885b69cb08e2bf9364cd60e768f921d9b54d9ee9aeb1d5c6020c` | 与 HEAD 逐字节相同 |

相对 §15.13 的 SHA 表，唯一源码增量为：

| 路径 | 第六轮输入 SHA-256 | ROUND6B SHA-256 |
|---|---|---|
| `src/tests/cuts/test_stage_b_contracts.py` | `75fcf7c0f5ffe07b3b8f7f988d1ab83fed614e4e2248566ae447cad61f371a31` | `c1ba003306669434be5cb65c4783946e62896f66d5b79af73dc4fc3d9d5005cb` |
| `ACLOSE_R6FIX_SELF_CHECK_20260820.json` | 不存在 | `4c0474fa21e164dd10cc7bfbaaa96e128b4d627de7d2d92696fdab7a280b099c` |

HANDOFF 不做自引用 SHA。当前合法状态为 `ROUND6B_READY / NOT_RE_CLOSED / NOT_COMMITTED`；Stage-B 语义裁断、四项 LOW 后批处置、owner re-close 与两条 authority parity floor 均保持开放。

## 17. Owner re-close 终态与 READY_TO_COMMIT

### 17.1 当前状态

```text
status    RE_CLOSED_PENDING_COMMIT
terminal  READY_TO_COMMIT
owner     2026-08-21 session widget：范围 A、clean-review 连胜保留、P1.2 re-close、allowlist 历史 id 永久接受
HEAD      aa517cd35e222672f5f6dcd88beba4689c69cf29（detached，未 commit）
index     cached content 为空；仅 OWNER_AUTHORITY_COMPANION_20260821.md 为 intent-to-add
main      tracked 与 cached content 均干净
```

六轮外部审计已由 R6B `CLEAN_FOR_REOPEN` 收敛。review gate 为 `closed_manual_owner_decision`、`updated_at=2026-08-21`；08-06 `owner_manual_decision` 对象保留为 append-only decision register 的稳定历史锚，08-21 successor authority 由窄 companion 与 `DECISION-P1-2-RECLOSE-20260821` 承载。

### 17.2 Stage-B 语义复核与五层封印终态

HEAD/当前 alias-use record 均为 152 条，集合差异恰为 `src/models/master_model.py::build_exact_core` 同一 `ExactMasterCore(...)` constructor statement 的 1 删除 / 1 新增；唯一新增字段为已纳入六轮审计的 `generic_output_slots_by_operation` 与 `utility_operation_by_template` 快照。`coordinate_binding` acquisition、alias 名、消费、private backend 与 facade 路径均未改变。未发现未经审计的语义变化，Stage-B pin 已重封为 `c0e07e47a43311c4facc7e967ea39b86e66851cc2fec5ab157ba6b7fa31498a4`，目标测试通过。

sealed-authority parity 的两处 `benders_loop.py` floor 已由 `34e198fc…` 更新到最终字节 `461fc6875ca16781c1d0d81720aee98747a3d2c984a4c1bf1afda4f384af1bc3`，整文件 6 tests 通过。73 sink 与 133 项 v99 floor 对最终磁盘复算均为 mismatch 0；本次新增 authority/登记面均不在 73 sink，故机械 reseal 为 no-op，未铸造新授权。

### 17.3 Owner authority 与维护登记

- `OWNER_AUTHORITY_COMPANION_20260821.md` 记录四项 owner 信号及 Stage-B 逐处复核；该文件不含更宽的 promotion/release 权限。
- `DECISION-P1-2-I1-RANGE-A-20260821` 以 `scope_boundary` 覆盖两份 proof-obligation authority change；`DECISION-P1-2-RECLOSE-20260821` 以 `phase_gate` 覆盖 review gate，并引用六轮报告、R6B 与三份 ACLOSE receipt。
- `REVIEW-20260821-COMMON-MODE-BINDING-REVERIFY-RECLOSE` supersede reopen review。allowlist id 尾号 `_295` 登记为历史命名、非坐标承诺；守卫实际位于 `:309`，SHA+size 双 pin 与语义元组/坐标门不受影响，owner 永久接受且不要求重命名。
- proof gate 的 production/I1 operation-map parity 断言继续归后批，本次保持恰 1 issue fail closed。

### 17.4 CLOSE 终收据

```text
path      .artifacts/i1_round4_self_check_20260820/ACLOSE_CLOSE_RECEIPT_20260821.json
sha256    33f01bc9b68e663dace5f87b37edf492a4438c6f056a340963dfc3db8c1e9d8e
status    PASS_WITH_KNOWN_REDS
tally     12 PASS / 3 KNOWN_RED / 0 UNEXPECTED_RED
bearing   67 files / 8baa1d65707b40c3be42fdc151ec7533b09ec63f4522216b1ae37f1a3f688acd
mtime     receipt 1787311823059192093 > max bearing input 1787311185768494458
```

三条 KNOWN_RED 精确为 strict mypy `144 errors / 12 files`、closed-package mypy `8 errors / 2 files`、P1.2 proof gate 恰 1 issue。focused pytest 为 341 tests：338 passed / 0 failed / 3 skipped；sealed-authority node-selected 子集 2/2 passed。旧 `ACLOSE_SELF_CHECK_20260820.json` 与 `ACLOSE_R6FIX_SELF_CHECK_20260820.json` 保持原 SHA `887ee04e…` / `4c0474fa…`，未覆盖。

### 17.5 Re-close delta SHA-256

| 路径 | SHA-256 |
|---|---|
| `docs/research/common_mode_binding_reverify_20260820/OWNER_AUTHORITY_COMPANION_20260821.md` | `67be6d01e28887b743a53001d2d7faf40e59b57d66d19ed02b210484f8fcf314` |
| `src/tests/cuts/test_stage_b_contracts.py` | `d71671667e77acaecfb1c165ba299f18de59827600953e1efac2d5c743af3d25` |
| `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` | `6ded3c1ece9a366a299429588c46907f9b7e624796f8012b9df5f58d52ba6e57` |
| `data/review_gates/phase_1_2_spike_close.json` | `e2dc36ccf7406aafdefa12fd8d8c59d8c34cd2de4a1549c56da305881c0fc9f8` |
| `data/knowledge/decisions.jsonl` | `f699a8aa0bf60366f0161999eb23050a9313194b3c1f6ba97dc96350abd091b4` |
| `data/knowledge/backfill_reviews.jsonl` | `f0d4918127d582cee636824378837b3ab98df8cc5ee4cb73a24f4256021cb333` |
| `data/knowledge/knowledge_census.json` | `b138d4adb5f374a9985c5621e05a0e8350bc24fbead083018094408ad07c7bb7` |
| `docs/BACKFILL_LEDGER.md` | `ebe3796ab317957e5261d2a9fd93905ec229a0275191aebe1b6eca97bd6ab8f6` |
| `docs/CATALOG.md` | `140eccde8ec772bab309f660ad896674ad09c716f9b3075896c006fc904add9b` |
| `docs/CURRENT.md` | `8026e47cc1f93a51e83ccf8f1dc9410a9d83832f935b997c0124bc3013f97b6d` |
| `docs/OPEN_QUESTIONS.md` | `0cf5a009da7cd05b0ed0826b339362c5991d6ed7398fc99656574a012a780ea9` |
| `docs/REASONING_LEDGER.md` | `6ddd3248bbbdc1158a32fcbf4b5f044335c9f80a391549a2a1e6e26145e8bb17` |
| `docs/TERMINOLOGY.md` | `9f3a638b16030414d6fd8f63565ab88ca2ec0a235edb5979e95b578fbecfa2df` |
| `docs/TOPIC_INDEX.md` | `c9d49ee95fbd60b9e8d60913880b04a7f7692fc81398db6a3a33f9168c3e9a53` |
| `docs/VALIDITY_LEDGER.md` | `c2fd9731b590cffc7f47a967d73b48cb23a6987382660b41c0a8afbe4161da94` |
| `docs/MAINTENANCE_QUEUE.md` | `d4d8b07c1006c0309dc67e23084884a69ee5889cbc991b74bf158a84b259f422` |
| `.artifacts/i1_round4_self_check_20260820/ACLOSE_CLOSE_RECEIPT_20260821.json` | `33f01bc9b68e663dace5f87b37edf492a4438c6f056a340963dfc3db8c1e9d8e` |

HANDOFF 继续不做自引用 SHA；本节写入位于 receipt 明确排除的 nonbearing 路径。

### 17.6 两刀 commit 计划（仅计划，未执行）

**刀一：早批文档系统 lane**

- message 草稿：`docs(document-system): 固化维护回归时钟一致性`
- 精确 pathspec（3）：
  - `.docsystem/manifest.json`
  - `docs/governance/document-system/MAINTAINING.md`
  - `src/tests/test_document_system.py`

**刀二：I1 common-mode binding re-close 本体**

- message 草稿：`feat(certified): 收口 I1 binding 独立复验并重新关闭 P1.2`
- 精确 pathspec（66）：
  - `certside/README.md`
  - `certside/sidecar/canonical_witness_checker.py`
  - `certside/sidecar/emitter.py`
  - `certside/sidecar/frontend.py`
  - `certside/sidecar/parity_check.py`
  - `certside/sidecar/run_acceptance.py`
  - `data/knowledge/backfill_reviews.jsonl`
  - `data/knowledge/decisions.jsonl`
  - `data/knowledge/dossiers.json`
  - `data/knowledge/knowledge_census.json`
  - `data/proof_obligations/p1_2_proof_obligations.json`
  - `data/proof_obligations/strong_status_write_allowlist.json`
  - `data/repository_governance/code_assets.json`
  - `data/review_gates/phase_1_2_spike_close.json`
  - `devtools/tests/test_repository_code_assets.py`
  - `docs/BACKFILL_LEDGER.md`
  - `docs/CATALOG.md`
  - `docs/CURRENT.md`
  - `docs/MAINTENANCE_QUEUE.md`
  - `docs/OPEN_QUESTIONS.md`
  - `docs/REASONING_LEDGER.md`
  - `docs/TERMINOLOGY.md`
  - `docs/TOPIC_INDEX.md`
  - `docs/VALIDITY_LEDGER.md`
  - `docs/research/common_mode_binding_reverify_20260820/ACLOSE_PROGRESS.md`
  - `docs/research/common_mode_binding_reverify_20260820/BASELINE_ATTRIBUTION_20260820.md`
  - `docs/research/common_mode_binding_reverify_20260820/EXTERNAL_AUDIT_HANDOFF_20260820.md`
  - `docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_20260820.json`
  - `docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_POSTFIX2_20260820.json`
  - `docs/research/common_mode_binding_reverify_20260820/MASKED_REAL_DIFF_POSTFIX_20260820.json`
  - `docs/research/common_mode_binding_reverify_20260820/OWNER_AUTHORITY_COMPANION_20260821.md`
  - `docs/research/common_mode_binding_reverify_20260820/OWNER_INSTRUCTION_20260820.md`
  - `docs/research/common_mode_binding_reverify_20260820/README.md`
  - `docs/research/common_mode_binding_reverify_20260820/ROUND1_LOW_DISPOSITIONS_20260820.md`
  - `docs/research/common_mode_binding_reverify_20260820/ROUND2_FINDING_DISPOSITIONS_20260820.md`
  - `docs/项目说明/HISTORY.md`
  - `scripts/check_p1_2_proof_obligations.py`
  - `scripts/p2_14_evaluator/run_eval_v1_baseline.py`
  - `src/models/binding_subproblem.py`
  - `src/models/master_model.py`
  - `src/search/benders_loop.py`
  - `src/search/certified_artifact_contract.py`
  - `src/search/heuristic_feasible_finder.py`
  - `src/search/independent_binding_reverify/__init__.py`
  - `src/search/independent_binding_reverify/api.py`
  - `src/search/independent_binding_reverify/artifacts.py`
  - `src/search/independent_binding_reverify/capsule.py`
  - `src/search/independent_binding_reverify/certificate.py`
  - `src/search/independent_binding_reverify/protocol.py`
  - `src/search/independent_binding_reverify/semantics.py`
  - `src/search/independent_binding_reverify/theorem.py`
  - `src/search/independent_binding_reverify/transport.py`
  - `src/search/independent_infeasibility_reverifier.py`
  - `src/search/pr2_l0_fixed_witness_core.py`
  - `src/tests/cuts/test_rule_cut_evolution_authority_parity.py`
  - `src/tests/cuts/test_stage_b_contracts.py`
  - `src/tests/test_binding.py`
  - `src/tests/test_binding_overload_separation_override.py`
  - `src/tests/test_binding_sidecar_projection_parity.py`
  - `src/tests/test_exact_contract.py`
  - `src/tests/test_independent_binding_arithmetic_parity.py`
  - `src/tests/test_independent_binding_real_artifact_parity.py`
  - `src/tests/test_p1_2_fix_5_toctou_atomic_snapshot.py`
  - `src/tests/test_p1_2_independent_infeasibility_reverifier.py`
  - `src/tests/test_power_witness_cut_dilution.py`
  - `src/tests/test_wireless_front_consumers_r4.py`

两刀都先对各自清单执行精确 `git add -- <pathspec...>`，再用同一清单提交；禁止 `git commit -a`。第五轮在案的四个 intent-to-add 路径 `README.md`、`OWNER_INSTRUCTION_20260820.md`、`test_binding_sidecar_projection_parity.py`、`test_independent_binding_arithmetic_parity.py` 均明确归刀二；`.artifacts/**` 与本机 overlay `CLAUDE.md` 不进入任一刀。
