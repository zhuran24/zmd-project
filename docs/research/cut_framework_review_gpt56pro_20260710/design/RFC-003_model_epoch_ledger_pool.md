# RFC-003：让生命周期真正约束已注入 master 的 cut

状态：评审建议稿，不应盲目 apply。

## 1. 问题

ACTIVE/HOLD/QUARANTINE 目前只描述 CutStore 记录。CP-SAT 约束一旦 Add 进现有模型，CutStore 把 cut 改成 HOLD 或 QUARANTINE 并不能撤回约束。战报也明确承认约束不可删除，预算满只能停发，真正 eviction 要等 master rebuild。

因此，当前状态机在最关键的物理层没有效力。一个已 attach 的 cut 后来因 source、artifact、scope 或 validator 漂移而失效时，模型仍可能带着它继续 solve。对 exact release 来说，这不是“状态管理尚不完善”，而是生命周期语义没有闭环。

此外，生产 attach 路径不经过 CutStore、serialize/deserialize/replay；cut_id 含时间戳，缺少 semantic fingerprint；只有总数预算，没有重复、支配、活性或成本选择。

## 2. 决策：append-only ledger + model epoch

新增不可变模型世代：

```python
@dataclass(frozen=True)
class ModelEpoch:
    epoch_id: str
    source_digest: str
    artifact_set_digest: str
    master_schema_version: str
    enabled_family_manifest_digest: str

@dataclass(frozen=True)
class CutLedgerEvent:
    seq: int
    event: Literal[
        "GENERATED", "REJECTED", "VALIDATED", "PREPARED",
        "APPLIED", "HELD", "QUARANTINED", "SUPERSEDED"
    ]
    cut_id: str
    semantic_fingerprint: str
    model_epoch_id: str | None
    reason_code: str
    payload_digest: str
    timestamp: str
```

每次 master build 创建新 epoch。APPLIED 事件必须记录 cut 的 `ConstraintPlan` digest、condition scope 和 master 返回的 attach receipt。求解结果只能由未 poisoned 的 epoch 发布。

## 3. Poison 与 rebuild 规则

任何已 APPLIED cut 后来进入以下状态，当前 epoch 立即 `POISONED`：

* proof/integrity/validator 失败；
* source 或必需 artifact 变化；
* compiler/master adapter version 不兼容；
* ghost 条件绑定被证明不完整；
* replay 与原 attach plan 不一致。

POISONED epoch 可以保留诊断数据，但不能继续产生可发布结论。下一轮必须 rebuild master，仅注入当前 replay 后 ACTIVE 的 cut。HOLD 只表示该 cut 不进入新 epoch；它不能从旧 epoch 中“逻辑撤回”。

若只是 cut 对当前 ghost 不匹配且原约束正确地带有 ghost `OnlyEnforceIf` 条件，该 cut 可以继续留在同一 epoch，因为条件本身实现了物理失活。ledger 需要记录 condition scope，replay 要验证条件变量确实对应同一 ghost anchor。

## 4. CutRecord 与 proof 分离

`Cut`/proof 对象保持不可变，不再带 `is_quarantined` 与 `quarantine_reason`。生命周期数据放在 ledger 派生视图：

```python
@dataclass(frozen=True)
class CutRecordView:
    cut_id: str
    semantic_fingerprint: str
    latest_state: Literal["ACTIVE", "HOLD", "QUARANTINE"]
    applied_epochs: tuple[str, ...]
    last_reason: str
```

这消除 `Cut.is_quarantined` 与 `CutStore.quarantined/held` 两套状态源。

## 5. semantic fingerprint 与去重

cut_id 继续作为事件身份，但 pool 去重使用语义指纹：

```text
SHA256(
  family
  + proof/body canonical semantic projection
  + exact model scope/condition
  + source and required dependency digests
  + compiler semantics version
)
```

不得包含时间戳、iteration、oracle 名称或审计计数。相同 fingerprint 的重复 cut 只增加 hit/generation 计数，不重复注入。

family-specific dominance 可后置，但先实现安全的严格等价去重。对于 F1/F6，可再实现同 scope、同左端表达下更紧 RHS 支配更松 RHS；对于 F5/F7，只有经过证明的集合包含关系才做 subsumption。

## 6. CP-SAT 适用的 cut 选择指标

经典 LP cut efficacy 不能原样照搬到 CP-SAT，但仍需要选择层。建议最少记录：

* 当前 incumbent 的 violation margin；
* plan arity、presence term 数、encoded literal 数；
* core/body 大小；
* semantic duplicate rate；
* family、scope 和 ghost anchor 的覆盖多样性；
* apply/build wall time；
* attach 前后传播域削减或固定变量数；
* solve time、branches、conflicts、RSS 的 A/B 变化；
* 命中次数与最近命中 epoch。

首版 selector 可按硬预算做 family quota + duplicate filter + 小 plan 优先，不必立即实现复杂打分。预算满后不再生成只是保险丝，不是 cut management。

## 7. production 入口

生产路径应是：

```python
for raw in generators.generate(snapshot):
    result = validate_and_compile_cut(raw, snapshot, registry)
    ledger.record(result)
    if isinstance(result, CutRejection):
        continue
    if pool.is_duplicate(result.plan.semantic_fingerprint):
        ledger.record_rejected(..., "semantic_duplicate")
        continue
    selected.append(result)

for compiled in selector.select(selected, budget_remaining):
    receipt = master.apply_compiled_cut(compiled)
    ledger.record_applied(compiled, receipt, epoch)
```

campaign restart 时先读 ledger 中 proof envelope，再做 deserialize、scope、validator、compile、plan fingerprint 全链 replay。不能直接相信上次 APPLIED 状态。

## 8. 最小持久化格式

建议 JSONL 或 SQLite WAL。JSONL 易审计，SQLite 更利于索引。无论格式，必须有：单调 seq、事件 hash chain、source/manifest digest、cut payload digest、model epoch、reason code。崩溃恢复只消费 fsync 成功的完整事件。

## 9. 测试与上线门

1. 已 APPLIED cut 变 QUARANTINE，旧 epoch 禁止 publish，rebuild 后约束不存在。
2. ghost-bound cut 的 condition literal 与 anchor 映射错位，attach fail-closed。
3. 相同语义、不同 cut_id/iteration 的 cut 只 attach 一次。
4. ledger crash 截断恢复，不得把 PREPARED 当 APPLIED。
5. restart 后每个活跃 cut做全链 replay，任一步失败不进入新 epoch。
6. batch0/C1 基线上做 cut off/on A/B：目标值和独立复验等价；记录 generated/rejected/applied、family、原因、branches/conflicts/wall/RSS。
7. rollback 演练：关闭 family 或回滚 compiler 后，能从 ledger 重建无该 cut 的 clean epoch。

## 10. 代价

append-only ledger、semantic dedup、epoch poison/rebuild 最小闭环约 4 至 8 人日，差异主要取决于现有 master rebuild/checkpoint 接口。加入 family-specific dominance、传播收益测量和自适应 selector 再增加约 4 至 8 人日。六维 watcher 可保留为未来优化，但在 ledger、rebuild 和真实热路径数据之前，不应作为生产正确性的依赖。
