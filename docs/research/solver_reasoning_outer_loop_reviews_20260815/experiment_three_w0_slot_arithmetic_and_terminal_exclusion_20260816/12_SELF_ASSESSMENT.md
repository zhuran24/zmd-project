# 实验三自评：W0 席位算术与固定矩形终局排除

> **评估日期：** 2026-08-16；2026-08-17 完成 canonical 对账复评。
> **当前科学判词：** `THEOREM_TWO_PASS / PROVED_IN_LOCAL_LINE / CANONICAL_ALREADY_PROVED_EXCLUDED`
> **效力边界：** research-only、evidence-only；不产生新 canonical claim truth、candidate transition、endpoint movement、certification、exact-status、stable claim、production lowering 或发布效力。
> **勘误入口：** [`16_CANONICAL_STATE_ERRATUM_20260817.md`](16_CANONICAL_STATE_ERRATUM_20260817.md)。

## 1. 五件套坐标

| 件 | 坐标 | 当前状态 |
|---|---|---|
| 范围 | [`02_JUDGMENT.json`](02_JUDGMENT.json) `scope/context` | 固定 W0、52 个命名 source slots、三标签 ExactlyOne、全局 34/18，只量化 binding selection |
| 条件 | [`03_PROOF.md`](03_PROOF.md) §2 | `LegalW0Binding(b)`，不偷带 041 活动结论 |
| 结论 | [`02_JUDGMENT.json`](02_JUDGMENT.json) `conclusion` | 每个合法 binding 都有 `boundary_port_041:out:0 != __unused__` |
| 证明 | [`03_PROOF.md`](03_PROOF.md) §4–§5 | 两条独立计数链 + 五步非负零和证明；实验数据不是前提 |
| 消费契约 | [`02_JUDGMENT.json`](02_JUDGMENT.json) `consumption_contract` | 只准离线组合与固定候选研究账；禁止 production/certified/跨域消费 |

独立 checker 为 [`04_check_w0_slot_arithmetic.py`](04_check_w0_slot_arithmetic.py)，schema-bound 收据为 [`05_THEOREM_RECEIPT.json`](05_THEOREM_RECEIPT.json)。

## 2. 定理二独立复算

核心结果：

```text
boundary source instances = 46
protocol-core source instances = 1
boundary slots = 46
protocol-core slots = 6
total slots = 52
blue requirement = 34
source requirement = 18
forced unused total = 0
target slot must be active = true
```

需求侧不是只信 `generic_io_requirements.json`：checker 从 canonical `external_boundary` commodity、canonical recipes 与 266 个 mandatory exact instances重新推导 34/18，再与 generic I/O 逐项对拍。

席位侧不是只信 model snapshot：checker 从固定布局、mandatory instance metadata 与 candidate pool 的 selected poses 重新构造 46+6 个物理 slot ID。A_BASELINE snapshot 只用于后续模型对应，不进入定理二前提。

## 3. 负测试

定理二 checker 杀死 8 个变体：

1. 少一个 slot；
2. 多一个 slot；
3. 需求总和改为 51；
4. 删除目标 slot；
5. 制造重复 slot ID；
6. 把 `refinery_blue_iron` 的 ore coefficient 改为 2；
7. 制造 stale input hash；
8. 增加第四个 slot label。

任一变体存活都会阻断定理收据。

## 4. 观测覆盖

冻结 Phase -1 v2 prefix 的事后覆盖：

```text
records = 1007
unique selection digests = 1007
041 active records = 1007
coverage = 1007 / 1007 = 1.0
prefix SHA-256 = e37da2d662a850529122e983c59ab569e0d48e9b9b93279af6bf41e0568d60a1
```

checker 的 `--coverage off` 模式不读取 journal 仍可 PASS；因此覆盖没有偷渡成数学前提。

## 5. 终局 lift

组合对象：

```text
定理二: LegalW0Binding(b) -> Active_041(b)
定理一: Active_041(b) -> not exists routing witness r
```

[`10_check_w0_terminal_exclusion.py`](10_check_w0_terminal_exclusion.py) 重新运行两个 theorem checker，并对八条路径级义务分别记录机器关闭或人工论证状态：

- 输入身份；
- 52-slot 完整性；
- 52 组三标签 ExactlyOne；
- 34/18 全局等式；
- 非-unused 到 source port spec 的映射；
- port specs 与 strict rectangle 进入 exact routing path；
- context transport；
- exact-status 与 stable claim ledger 不干扰。

其中 LIFT-02/03/04 由 snapshot 与 source-audit 的前置 `require` 硬门关闭；LIFT-07/08 分别由 context transport 与保护面哈希检查 fail-closed，随后写入的布尔值只是对已通过硬门的结构化复述，不是第二份独立观测。LIFT-01 输入桥、LIFT-05 导出语义桥和 LIFT-06 第二入口否定只有源码身份、marker 或局部调用计数支持，状态为 `ARGUED_NOT_MACHINE_CHECKED`。当前计数为 5 条机器关闭、3 条人工论证、0 条 `OPEN`；`path_obligations_open=0` 是这些状态硬约束通过后的结构常量。

A_BASELINE snapshot 独立重算：

```text
variables = 17,190
constraints = 289
generic-output slots = 52
generic-output literals = 156
target ExactlyOne constraint = 273
blue exact-count constraint = 287, domain [34,34]
source exact-count constraint = 288, domain [18,18]
```

终局 checker 杀死 6 个运行路径变体：context 错配、重开一条 lift 义务、删除目标 ExactlyOne、把 blue requirement 改为 33、把历史 envelope 中的候选差分改成 0、把金丝雀历史判词改成 `INFEASIBLE`。[`15_test_receipt_contracts.py`](15_test_receipt_contracts.py) 另把 manifest 条数/ID/evidence 漂移、schema 收据变体、schema 字节篡改与 authority currency 固化为可重复运行的 tracked 负测。候选差分负测只证明旧 envelope 按旧契约自洽；2026-08-17 勘误后，它不再支撑 canonical `ΔM=-1`。

## 6. 终点候选分类与 canonical 对账

当前下界仍为 `L=ABSENT`，所以全局 `M_t` 继续是 `N_A_NOT_READY`。本批没有虚构数值基线。

现行双层账目：

```text
candidate = W0-ALIGNMENT | x=1,y=51,w=6,h=7
local proof line = UNPROVED_IN_THIS_LINE -> PROVED_IN_THIS_LINE
canonical candidate = PROVED_EXCLUDED -> PROVED_EXCLUDED
evidence = ALTERNATE_MECHANIZED_PROOF_FOR_NAMED_6X7_CANDIDATE
canonical ΔM = 0
global M_t = N_A_NOT_READY -> N_A_NOT_READY
ΔL = ZERO
ΔU = ZERO
```

实验前已有三条 current claims：定理一是 `CLAIM-STRICT-HOLE-AVOIDS-X1-Y1` 的 `INSTANCE_COROLLARY_OF`；定理二与 `CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED` 为 `EQUIVALENT_TO`；固定候选终局被 `CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE` `SUBSUMED_BY`。因此 semantic novelty 为 `NONE`，真实增量是机械化、证据 assurance 与 replay capability。

历史 Judgment、checker 与 receipt 中的 `UNKNOWN -> PROVED_EXCLUDED_RESEARCH` 和 `delta_M_bottom=-1` 保留为不可回写的旧 envelope 字段，不是 canonical transaction。当前不存在由本实验新写入的 candidate ledger 交易。

## 7. 与金丝雀的关系

实验二的冻结科学判词保持：

```text
INCONCLUSIVE
```

本批没有把 C 臂 20 秒 timeout 重写成 observed `INFEASIBLE`。新证据独立证明 residual binding contract 为空，只能作为后续数学解释；它不改变当时运行窗口没有 terminal observation 的事实。

## 8. “什么不算”逐条自查

| 不合格形态 | 本批检查 |
|---|---|
| 把 1007 个样本当全称证明 | 未发生；coverage off 独立 PASS |
| 把 selection hash 黑名单包装成定理 | 未发生；证明对象只有 52/34/18 与 ExactlyOne |
| 只引用 model snapshot，不从规则与输入重导 | 未发生；slot 与 demand 各有独立字节重导链 |
| 定理成立但 consumer/lift 未核 | 部分发生并已显式降级：5 条机器关闭、3 条仅人工论证；terminal premises 与 lift step 3/4 basis 仍是 DEBT-B，禁止把当前 PASS 解读为这些桥已机核 |
| 把 current-model restriction 冒充完整游戏语义 | 未发生；Judgment 与终局文书反复限定 current pinned model |
| 把本地无知写成 canonical `UNKNOWN`，并据此声称候选进展 | **历史上发生，已于 2026-08-17 勘误。** 正确口径为本地 `UNPROVED_IN_THIS_LINE → PROVED_IN_THIS_LINE`、canonical `PROVED_EXCLUDED → PROVED_EXCLUDED`、canonical `ΔM=0`；“第一笔非零候选排除交易”撤回。 |
| 把单候选排除写成全局 `M_t` 或 bound 变化 | 全局 `M_t`、`L`、`U` 始终未变；旧 `delta_M_bottom=-1` 已撤回其 canonical metric 解释，只保留在历史 envelope 字节中。 |
| 用新证明倒签金丝雀 PASS | 未发生；历史判词保持 `INCONCLUSIVE` |
| checker PASS 自动获得认证或发布权 | 未发生；schema-bound 收据把许可式 `granted_effects`、人读限界与 `non_implications` 分离 |

## 9. 保留风险与重开触发器

最强保留边界有两层：其一，终局排除依赖当前 binding contract 的模型忠实性，而该 contract 已知包含 current-model scope restrictions；本批没有证明它与完整 adjudicated-game 绑定语义等价。其二，本实验没有发现 current ledger 之外的新数学；若不先完成 canonical 对账，同一已知结论仍可能再次被误记为问题进展。

以下任一变化必须使结论 stale：

- candidate pool、mandatory instances、generic I/O、canonical rules 或 W0 layout 字节变化；
- generic-output slot 构造、三标签域、ExactlyOne 或 34/18 等式变化；
- `__unused__` 与 active source port 的导出语义变化；
- routing path 出现绕过当前 binding model 的新入口；
- theorem one 的 strict-empty/front-cell 前提变化；
- 任一 model-correspondence 义务被重新打开。
