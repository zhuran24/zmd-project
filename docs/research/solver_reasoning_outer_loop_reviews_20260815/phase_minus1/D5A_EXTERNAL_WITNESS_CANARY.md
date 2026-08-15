# D5a：外部完整布局终验 canary 管道分析

> **对象：** `STRICT42-V51`，原件 SHA-256 `2050c4052bcd30f2acb3eeb21106ca14e388304531ea4b71f1d0724b1f937f0f`。
> **性质：** research-only 源码与载体分析；没有把历史自述、旧 route 或自带 validator 升格为当前认证证据。
> **判定：** `ADAPTER_REQUIRED / CURRENT_DIRECT_ENTRY_NO`。

## 1. Canary 能提供什么

外部 witness 是自定义 `band22-witness/2`，原文已明确“不是 official-checker serialization，未运行 official checker，不声称认证”。它包含：

- 46 个边界口；
- 219 台制造设施；
- 单独存放的 protocol core；
- 26 根 power pole；
- `7×6` strict hole；
- 628 个 active ports；
- 1113 个 route components。

因此它携带了完整布局、端口选择和一条显式路线，而不是只有坐标骨架。

其 `generic_io_requirements` 与 `mandatory_exact_instances` SHA 仍等于当前输入，但 canonical rules SHA 已从 witness 钉住的 `501284...` 漂移为当前 `c3fc3a...`，且 witness 没有钉当前 `candidate_placements.json`。当前重新适配必须按现行 canonical/pool 逐项重验，不能复用历史“通过”口径。

静态映射结果：46+219 个列表设施中，按 `instance_id + anchor` 只有 45 个在当前 pose pool 中唯一，220 个仍有多个 orientation/port-mode 候选；protocol core 另存，26 根 pole 也需生成当前 optional instance identity。故 adapter 必须消费 witness 的 `mode`、active-port 方向/前格与 body cells 来唯一解析 pose，不能只按坐标就近匹配。

## 2. 现有 fixed-witness verifier 的真实输入

公共入口 `terminal_fixed_witness_capsule.build_terminal_fixed_witness_projection_at_sink` 接收：

```text
campaign authority state
+ candidate_records
+ final_result
+ current artifact/source bindings
```

底层 `verify_terminal_fixed_witness` 不是裸布局准入器。`_resolve_terminal_witness_identity` 在开始几何和求解复验前，先要求：

- authority state 中已有对应 candidate record；
- record 的 `status == CERTIFIED`；
- record solution 与 `final_result.placement_solution` 一致；
- record 已有 candidate-proof，且其中 `solution_digest` 与当前记录一致；
- ghost identity、candidate key 和输入摘要全部闭合。

所以把外部 JSON 直接送入现有入口不可行。为了通过前置形态检查而自行写入 `CERTIFIED` 和 candidate-proof，会伪造 proposal/campaign authority，违反本 canary 的边界。

## 3. 即使完成包装，是否绕开当前墙

不能。

现有 verifier 在完成身份检查后会重新：

1. 从 placement solution 构建 `PortBindingModel`；
2. 解一份 binding selection；
3. 运行 exact routing precheck；
4. build/solve routing；
5. precheck reject 或 routing infeasible 时加 selection nogood；
6. 继续枚举下一个 binding alternative，直到找到 FEASIBLE routing、预算耗尽或 alternatives exhausted。

其固定预算为 binding 600 秒、routing 600 秒，并共享总 solve envelope。外部 witness 已携带的 628 个 active ports 与 1113 个 route components不会被当成固定 binding/routing certificate 消费。

因此“只把外部布局包装成当前 candidate record”仍会原样重走 binding↔routing alternative 枚举，不满足 D5a 的 canary 成功条件。

## 4. `CANDIDATE_PROPOSED` 是否提供弱状态入口

仓库存在 `CANDIDATE_PROPOSED`，但当前入口由 outer search 在完整 frontier 逻辑中生成：先建立 final result 和候选记录，做 sink replay，再调用 fixed-witness capsule，最后写 proposal marker。它不是一个接收任意外部布局的独立 submission API。

所以当前有“弱于 CERTIFIED 的状态”，但没有“外部 candidate → weak proposal”的受控适配面。

## 5. 最小缺件

需要新增一个与发布 authority 正交的 research/admission 三段式接口：

```text
ExternalWitnessAdapter
→ FixedExternalWitnessVerifier
→ ExternalCandidateReceipt
```

### A. `ExternalWitnessAdapter`

输入自定义 witness 与当前 frozen inputs，输出当前 placement solution、ghost、fixed active-port carrier、fixed route carrier及逐字段映射 receipt。所有歧义 fail closed；不得自行铸造 candidate status。

### B. `FixedExternalWitnessVerifier`

直接核验外部携带的具体 witness，而不是重新寻找 witness：

- 当前 pose/body、mandatory 完整性、strict hole、power；
- active ports 是否由当前 pose/规则允许且满足精确 binding 需求；
- route components 是否匹配 active ports、占用、方向、组件合法性和逐 commodity/source/sink 连通性；
- digest-bound 输入与输出。

若不给固定 active ports 或 route carrier，允许回退到现有枚举器，但 receipt 必须标为 `ENUMERATION_FALLBACK`，不能计作 D5a 成功。

### C. `ExternalCandidateReceipt`

只能生成 research-only/weak receipt，例如 `EXTERNAL_CANDIDATE_VERIFIED`；之后若要进入正式线，应由独立 proposal builder 和 supervisor 消费。adapter/verifier 不得写 `CANDIDATE_PROPOSED`、`CERTIFIED`、seal 或 publisher surface。

## 6. D5a 判词

- **外部布局能否直接进入当前 terminal fixed-witness 链：** 否。
- **能否通过诚实的薄包装进入：** 否；当前入口要求已有 `CERTIFIED` 记录和 candidate-proof。
- **包装后是否避免同一枚举墙：** 否；现有 verifier会重新枚举 binding alternatives，并忽略外部 route carrier。
- **最小 adapter 是否有限且清晰：** 是，但它必须包含“固定 binding + 固定 route 的独立验证器”，不能只做 schema 转换。
- **本 canary 对 Phase -1 的含义：** 当前 D5a 不提供 GO 信号；若 D1/D2 其他部分很强，仍需把上述 admission vertical slice 作为立项前或立项首批的硬缺件提交 owner，而不能声称现有 witness 终验入口已打通。
