# Whole-layout binding common-mode hardening

日期：2026-08-20

Dossier：`DOSSIER-COMMON-MODE-BINDING-REVERIFY-20260820-0268E9394D`

## 当前状态

```text
ROUND3_READY_PENDING_EXTERNAL_AUDIT
NOT_RE_CLOSED
NOT_COMMITTED
```

本 dossier 处理 whole-layout negative cut 的 binding I1 复验面，以及核对过程中发现的 binding PB sidecar 投影漂移。它不宣称关闭 master `INFEASIBLE`、routing exhaustion、terminal fixed-witness 或全部 local cut family 的 common-mode 风险。

本批触碰 P1.2 close-kernel sealed 面。Owner 裁断为不豁免治理：合入前必须完整执行“重开 P1.2 close claim → 外部异源审计 → owner re-close”。本 worktree 中的 proof-obligation 重封只是待审草稿；两条旧 sealed-authority parity 测试必须保持红。

## 外审轮次

第一轮外审确认闭式定理方向安全，但要求补能力合同、plan 派生和真实负例。第二轮外审确认 soundness 仍无破口，同时发现最终字节不可运行，以及上一轮自验收据不存在、结果与最终字节错位。

第二轮报告：

```text
/home/zhuran24/zmd-pj/.artifacts/gpt_harvest_20260818/
EXTERNAL_AUDIT_I1_ROUND2_20260820.md
```

第三轮输入见 [`EXTERNAL_AUDIT_HANDOFF_20260820.md`](EXTERNAL_AUDIT_HANDOFF_20260820.md)。最终自验的唯一机器权威位于 worktree-local `.artifacts`，不再由对话终稿代替。

## 闭世界独立证明包

```text
src/search/independent_binding_reverify/
├── __init__.py
├── api.py
├── artifacts.py
├── capsule.py
├── certificate.py
├── protocol.py
├── semantics.py
├── theorem.py
└── transport.py
```

职责：

- `api.py`：production 稳定入口与 parent-side envelope 校验；
- `transport.py`：fresh `python -I -B`、fresh pycache、nonce 与真实 wall-time timeout；
- `capsule.py`：child executor；
- `artifacts.py`：五份 authority artifact 的 strict read、regular-file/symlink 检查与 SHA-256 binding；
- `semantics.py`：独立重建 operation profile、selected pose、generic capacity 与 runtime relaxation；
- `theorem.py`：闭式容量定理与确定性显式 witness 构造；
- `certificate.py`：不 import theorem builder 的独立 certificate/witness checker；
- `protocol.py`：版本化 request、response、certificate 与能力合同。

旧入口 `src/search/independent_infeasibility_reverifier.py` 只做兼容 re-export，不承载证明逻辑。

## Plan 派生链

以下语义全部来自同一份 `preprocess_plan.utility_operations`：

```text
generic_input_slots_by_operation
generic_output_slots_by_operation
utility_operation_by_template
```

`utility_operation_by_template` 是 `facility_type → operation_type` 的反向映射；同一 facility template 若对应多个 utility operation，所有消费者都 fail closed。它不再以
`protocol_storage_box → box_sink`、`power_pole → power_supply` 的手抄表存在于 production binding、I1、PB emitter 或 canonical witness checker。

Certified 主链：

```text
preprocess_plan 原始字节
  → ExactSearchSession 单次 snapshot
  → ExactMasterCore
  → MasterPlacementModel
  → LBBDController._binding_snapshot_kwargs
  → primary / overload-retry PortBindingModel
  → binding_semantics_contract_v1
  → isolated I1
```

Terminal fixed-witness 构造点独立读取同一 plan 并显式传入三张映射。Heuristic feasible finder 也显式传入三张映射，但它被 checker 标记为 `exploratory_non_authority`，不拥有 certified cut authority。

## 运行态能力合同

Production 不再为以下字段写常量：

```text
routing_context_enabled
overload_separation_enabled
reverification_selection_nogood_count
```

实际值由产生本次 exhaustion 的 `PortBindingModel.extract_conflict_summary()` 提供：

- `routing_context_enabled` 来自模型真实 `routing_context is not None`；
- `overload_separation_enabled` 来自实际 build conflict summary；
- `reverification_selection_nogood_count` 是 `add_nogood_cut` 真正加入 clause 的累计数。

`LBBDController._binding_reverify_semantics_contract` 对三个字段做 strict type 与缺失检查；whole-layout funnel 必须携带实际 binding model。没有 model observation 时直接 fail closed，不会回退到 `False / False / 0`。

### Routing filter 的单调松弛

令未经过 routing-aware 过滤的 binding domain 为 `D`，production 过滤后的 domain 为 `D_r`。过滤器只删除被堵 port/pattern，因此：

```text
D_r ⊆ D
```

I1 重建未过滤的 `D`。若 I1 在更大的 `D` 上给出容量不可行证书，则任意子集 `D_r` 也不可行：

```text
I1_INFEASIBLE(D) ⇒ PRODUCTION_INFEASIBLE(D_r)
```

反方向不使用。I1 在 `D` 中构造 witness 只会阻止 negative cut，不会证明过滤后的 `D_r` 可行。

当 production 实际开启 routing context 时，semantic model 和 certificate 都必须携带：

```text
routing_context_domain_filter_omitted_monotone_superset
```

独立 certificate checker 精确核对该数组。Overload separation 或已累计 selection nogood 尚无同等级简单合同，任一实际非零/开启状态都令 I1 返回 `UNKNOWN`。

## 闭式证书

Child 独立 strict-read：

```text
rules/canonical_rules.json
rules/preprocess_plan.json
data/preprocessed/generic_io_requirements.json
data/preprocessed/candidate_placements.json
data/preprocessed/mandatory_exact_instances.json
```

对当前纯 binding 模型，负证条件只有：

```text
sum(positive generic requirements) > physical generic slots
```

分别在 input/output 两侧独立检查。只有真实 deficit 才产生 `ARITHMETIC_INFEASIBLE`。容量充足时物化逐端口 `CONSTRUCTIVE_FEASIBLE` witness；独立 checker 复核完整槽集、坐标、方向、商品重数、unused 槽、runtime relaxation、artifact/model/solution identity 和全部 digest。

异常、timeout、routing-only exhaustion、未知约束族、plan/pose/artifact drift、certificate 失配、overload separation 或 selection nogood 均返回 `UNKNOWN`，不铸造 whole-layout cut。

## Sidecar 对账

PB emitter 与 canonical witness checker 现在共同要求：

```text
physical generic input ports  == plan declared generic input slots
physical generic output ports == plan declared generic output slots
```

shortfall、exact、surplus 三边界由 production、emitter、canonical checker 同时覆盖。Pose-optional synthesis 使用 model input 中的 plan-derived `utility_operation_by_template`，不再使用共享手抄常量。

## 真实工件验证口径

真实工件身份：

```text
path   /home/zhuran24/zmd-pj/data/preprocessed/candidate_placements.json
size   54,467,709 bytes
sha256 f05b1291a51d64a1bc40507146e95f3257effaaf2b795a0fa83f85f5d8d280d3
```

三案使用真实五工件和真实 pose pool，但布局是测试确定性选择的 `pose_idx=0` 布局，不是求解器产出的 incumbent：

1. 266 mandatory instances，真实 `protocol_core`，production 与 I1 均可行；
2. 同一布局增加 plan-derived pose-optional storage box，production 与 I1 均可行；
3. 保持真实 rules、plan、instances 与 candidate pool，只将 generic-output 总需求从 52 控制性增加到 53，production 与 I1 均判容量不可行，独立 certificate checker 通过。

前两案返回 `DIVERGED_FEASIBLE` 是相对于测试主动传入的 `binding_exhausted=True` 声明而言，不能描述成 production 与 I1 对可行性意见相反。

## F0 归因修正

原始 `MASKED_REAL_DIFF_20260820.json` 如实记录修复前：

```text
outcome_changes             14
baseline_pass_current_fail  14
```

第一版终稿把它错写成零，且错误地从“缺工件时 baseline/current 同红”推断没有后续回归。14 条 stale test doubles 已修复；修后必须使用真实工件逐条重放原 47 个 nodeid，权威结果见：

```text
MASKED_REAL_DIFF_POSTFIX_20260820.json
```

详细方法和口径见 [`BASELINE_ATTRIBUTION_20260820.md`](BASELINE_ATTRIBUTION_20260820.md)。

## Checker 结构门

Proof checker 现在同时锁定：

- package 文件集合与闭世界 import graph；
- dynamic import、`__import__`、`getattr(..., "__import__")`、`sys.modules`、`eval/exec/compile` 等绕过面；
- certificate checker 不得 import theorem builder，且必须核对 `runtime_relaxations`；
- production input/output provider 两侧都必须调用 plan-derived capacity map；
- `PortBindingModel` 只能保留一张被实际读取的 `utility_operation_by_template` 字段；
- `LBBDController` 两个构造点必须统一 unpack `_binding_snapshot_kwargs`；
- terminal fixed-witness 与 heuristic constructor 必须显式传三张 plan map；
- runtime contract 三字段不得是 AST 常量，必须读取 production `extract_conflict_summary`；
- whole-layout cut 必须先通过独立 capsule admission 才能 mint persisted cut。

## 明确不推出

本批不产生 production cut promotion，不改变求解上下界，不产生 durable/public `CERTIFIED`，不证明三方语义全等，也不证明 P1.2 已重新关闭。

仍延期：

- production CP-SAT / arithmetic I1 / PB sidecar 的系统穷举；
- selected-pose membership index 或 Merkle proof；
- routing exhaustion 的完整异源证明；
- master `INFEASIBLE` 的完整异源证明；
- terminal fixed-witness 的语义异构化；
- Windows→WSL PB 全链在本 Linux worktree 的新收据。
