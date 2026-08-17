# 推理外环账本对账协议 v1

> **状态：** `ACTIVE_RESEARCH_GOVERNANCE_V1`
> **生效日期：** 2026-08-17
> **适用范围：** 本 dossier 以及明确声明继承本协议的后继推理外环研究工作。
> **效力边界：** 本协议只约束研究消费动作的可采纳性与记账口径，不修改 `data/knowledge/claims.jsonl`，不授予 production、certified、release、supervisor 或 publisher 权限。
> **规格来源：** local-optional 坐标 `.artifacts/outer_loop_recon_20260817/B_VERDICT_FULL_20260817.md`，SHA-256=`16a2c6b3db19cbce6747c7169c31e5743c69934613c9bee9df6e6212b80c7bdc`。
> **核心不变量：** 想法可以自由产生；当一条工作开始消费共享算力、共享身份或共享真相时，必须先取得 `LEDGER_RECONCILIATION_RECEIPT`。

## 1. 两种知识状态必须分开

`UNKNOWN` 不是绝对状态。每个状态都必须指明知识基准 `K`：

```text
Status_K(subject)
```

本协议至少区分：

```text
UNKNOWN_IN_LOCAL_LINE
PROVED_IN_LOCAL_LINE
CANONICAL_UNKNOWN
CANONICAL_PROVED_EXCLUDED
PROVED_ELSEWHERE
```

“本线尚未证明”不能写成“canonical 账本尚未知”。本地证明线可以发生：

```text
UNPROVED_IN_THIS_LINE -> PROVED_IN_THIS_LINE
```

只有 canonical before-state receipt 证明对象此前确为 `CANONICAL_UNKNOWN`，才允许登记 canonical `UNKNOWN -> PROVED`。

canonical claim 真源是 `data/knowledge/claims.jsonl` 中 `status=current` 的记录。`docs/CURRENT.md` 是生成投影，不替代机器真源。current decisions、命题 lineage 与证据身份属于对账输入，但不能把非 current 史料抬成 current claim。

## 2. 永远不挂闸的自由区

以下活动不要求对账收据：

- 草稿推理与私有 scratchpad；
- 小规模、可随时丢弃的探索；
- 提出猜想；
- 几分钟内结束、不会取得共享身份或写入共享真相的局部 probe。

自由区可以产生想法和候选解释，但不得在没有收据时声称数学新颖性、铸造稳定命题身份、申请高预算、写 endpoint delta 或进入求解器消费面。

## 3. 必须挂对账的消费点

以下任一动作发生前，必须生成并审阅 `LEDGER_RECONCILIATION_RECEIPT`：

1. 冻结正式实验协议；
2. 申请高预算运行或共享算力；
3. 声称“新定理”，或 mint 新 theorem／`Judgment` ID；
4. 写入 candidate 状态、上下界、`M_t` 或任何 endpoint delta；
5. 把命题编译、lowering 或援引为 solver constraint；
6. 写 claim ledger、命题 evidence root 或稳定 lineage；
7. 进入认证、发布或 owner 决策包。

同一工作跨越多个消费点时可以复用同一收据，但前提是 problem、objective、context、ledger snapshot、目标 subject 与 intended role 均未变化。任一身份变化都使旧收据失效。

## 4. `LEDGER_RECONCILIATION_RECEIPT` 最小字段

每份收据至少包含下列字段：

| 字段 | 约束 |
|---|---|
| `problemHash` | 问题身份的 SHA-256；不得只写文件名或自然语言标题。 |
| `objectiveHash` | 目标函数与比较顺序的 SHA-256。 |
| `contextHash` | 当前假设集合、固定对象与语义作用域的 SHA-256。 |
| `canonical_subject_key` | 被研究、编译或写账对象的稳定规范键。 |
| `ledger_snapshot_digest` | 对账所用 canonical ledger 精确字节的 SHA-256。 |
| `queries_used` | 实际执行的 ID、关键词、结构字段与 lineage 查询；不得只写“已搜索”。 |
| `matched_claim_ids` | 所有 current match 的稳定 claim ID；允许空数组，但不得省略。 |
| `target_lineage_status` | 目标与 current、stale、superseded、冲突 lineage 的关系。 |
| `relation` | 只能使用 §5 的受控枚举。 |
| `canonical_before_state` | canonical ledger 在实验前对 subject 的状态。 |
| `intended_experiment_role` | novelty、strengthening、replication、mechanization、consumption test、benchmark 等预注册角色。 |
| `allowed_effects` | 本次工作可产生的最大效力，必须按最窄作用域填写。 |
| `non_implications` | 明确不产生的 claim、endpoint、production、certified 与跨域效力。 |

建议同时记录 `receipt_id`、生成时间、ledger 路径与 digest 算法。需要表达证明论细节时，可以增加 `semantic_relation_detail`，使用 `INSTANCE_COROLLARY_OF`、`EQUIVALENT_TO`、`SUBSUMED_BY` 等关系词，但它不能替代 §5 的 admission relation。

## 5. Admission relation 与处置

`relation` 只能取：

```text
NO_CURRENT_MATCH
EQUIVALENT_CURRENT
STRONGER_CURRENT
WEAKER_CURRENT
CONFLICT
STALE_ONLY
AMBIGUOUS
```

关系方向固定为“拟研究目标相对于 current ledger”：

| 对账结果 | 行为 |
|---|---|
| `NO_CURRENT_MATCH` | 可以作为 novelty experiment；仍须遵守 scope、验证与 endpoint 规则。 |
| `EQUIVALENT_CURRENT` | 不阻断，但只能登记 replication、mechanization 或 consumption test；canonical endpoint delta 默认为 0。 |
| `STRONGER_CURRENT` | current ledger 已有更强结论；较窄目标不得申报问题进展，只能做实例化、复算、证据加固或消费测试。 |
| `WEAKER_CURRENT` | 可以作为 strengthening experiment；必须明确新增的严格更强部分。 |
| `CONFLICT` | 阻断一切消费动作，先解决语义、输入、作用域或证据冲突。 |
| `STALE_ONLY` | 允许继续研究，但必须记录 stale lineage，确认不存在 current equivalent／stronger match；不得把 stale 史料当 current truth。 |
| `AMBIGUOUS` | 不阻断思考，阻断 novelty、预算、稳定身份、endpoint 与 lowering 写入，直到消歧。 |

`matched_claim_ids=[]` 不自动等于 `NO_CURRENT_MATCH`。收据还必须证明查询覆盖了 canonical subject、同义标题、作用域、依赖与 lineage。

## 6. Endpoint before-state 硬门

任何 candidate 状态、上下界或 endpoint delta 除 §4 字段外，还必须记录：

```text
before_state_source
before_state_digest
before_state_claim_ids
local_line_before_state
canonical_before_state
```

缺少这些字段时，不允许写：

```text
UNKNOWN -> PROVED
UNKNOWN -> PROVED_EXCLUDED
ΔM != 0
ΔL != 0
ΔU != 0
first nonzero progress
```

若本线新完成证明，而 canonical ledger 在开工前已经覆盖对象，正确记账是：

```text
local line:
UNPROVED_IN_THIS_LINE -> PROVED_IN_THIS_LINE

canonical subject:
ALREADY_PROVED -> ALREADY_PROVED

canonical endpoint delta:
0
```

checker PASS、机械化增强或证据 assurance 提升都不能替代 canonical before-state。

## 7. 密封选择器盲测

真正的盲态 novelty 实验采用密封选择器：

1. 协调席先对 canonical ledger、current decisions 与 lineage 完成对账；
2. 只选择 `NO_CURRENT_MATCH`，或确有 strengthening 价值的 `WEAKER_CURRENT` 目标；
3. 生成 receipt，记录其 digest，并在执行期间密封；
4. 执行席只读取原始问题、数据、冻结协议与允许的观测，不读取 ledger 或 receipt 内容；
5. 实验结束后揭盲，重新核对 ledger snapshot 与结果作用域；
6. 只有揭盲后仍满足 novelty 或 strengthening 条件，才能进入稳定身份或 endpoint 申请。

密封只隐藏答案，不隐藏输入身份、预算、停止条件、验证标准或非蕴含边界。

## 8. 已知答案闭卷基准

故意使用已知答案校准观察、猜想、证明、验证或消费器官时，协议头部必须在发射前标记：

```text
KNOWN-ANSWER CLOSED-BOOK BENCHMARK
```

该标签要求：

- 明确 matched claim 与已知答案范围；
- 预注册一个很小的硬预算上限，并用墙钟、事件数或计算量给出可执行单位；
- theorem novelty 与 canonical endpoint delta 固定为 0；
- 允许登记的增量只限 capability、assurance、replay、mechanization 或 consumption behavior；
- 不得把通过结果表述为全局方法论已验证、家族普遍性已成立或主线问题取得进展。

## 9. 本批回溯对账

实验一、二、三的回溯结果登记在 [`LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json`](LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json)。实验三的 canonical/local 状态勘误见 [`16_CANONICAL_STATE_ERRATUM_20260817.md`](experiment_three_w0_slot_arithmetic_and_terminal_exclusion_20260816/16_CANONICAL_STATE_ERRATUM_20260817.md)。

历史冻结协议、Judgment、checker 与收据不回写。后继勘误负责给出解释优先级，不能借改写历史字节伪造“当时已经对账”。

## 10. 非蕴含

本协议不意味着：

- 每个草稿、猜想或廉价 probe 都要经过行政审批；
- 对账结果可以替代数学证明、独立 checker 或完整原问题 verifier；
- `NO_CURRENT_MATCH` 自动证明目标有价值、可证或值得高预算；
- research receipt 可以写 production ledger、认证面或发布面；
- 一次对账可以永久覆盖未来 ledger 漂移。
