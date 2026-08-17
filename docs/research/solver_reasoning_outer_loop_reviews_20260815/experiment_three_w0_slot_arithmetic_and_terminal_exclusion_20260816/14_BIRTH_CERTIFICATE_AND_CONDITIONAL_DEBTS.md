# 实验三出生证与条件债务登记

> **文书性质：** 主体为截止 2026-08-16 的历史裁定与条件债台账；2026-08-17 只追加后继勘误索引，不追溯改写原裁定。本文不是当前 exact-status、stable claim、release 或 production authority 真源。
> **出生证状态：** `ISSUED_RESEARCH_ONLY`
> **适用对象：** 实验三固定 `W0-ALIGNMENT`、固定矩形 `R=[1,6]×[51,57]` 的 theorem-two 与 terminal-exclusion dossier。
> **查验记录：** 三面线查验；异源双线复验；结论零分歧。

## 1. 出生证裁定

实验三出生证已发。该裁定承认本 dossier 作为 research-only 历史证据包具备自带收据契约、可复算身份链和明确的非蕴含边界；它不把固定候选排除升级为 production certification、exact-status、stable claim、全局上下界或跨布局结论。

出生证所承认的路径画像为：

```text
5 machine-discharged
3 argued-not-machine-checked
0 open
```

其中 `ARGUED_NOT_MACHINE_CHECKED` 不等于机器证明。LIFT-01 输入运行时桥、LIFT-05 selection-to-port-spec 语义桥与 LIFT-06 无第二 binding bypass 仍只具有显式人工论证。

## 2. 同批必办清偿

| 项目 | 状态 | 清偿证据 |
|---|---|---|
| 收据 schema 自身进入哈希信任根 | `RESOLVED` | `04_check_w0_slot_arithmetic.py` 与 `10_check_w0_terminal_exclusion.py` 在执行 schema 前重算 `13_RECEIPT_ENVELOPE_SCHEMA_V1.json` 完整字节 SHA-256，并要求收据 `contract_identity.receipt_schema_sha256` 与冻结值一致。 |
| schema 双保险 | `RESOLVED` | `06_MODEL_CORRESPONDENCE_MANIFEST.json` 同时把 schema 登记为 `implementation_sources.receipt_schema` 与 `protected_surfaces`；终局 checker 在两条路径分别复核其 SHA-256 与字节数。 |
| 5/3/0 文本对齐 | `RESOLVED` | `08_TERMINAL_EXCLUSION_JUDGMENT.json`、`09_TERMINAL_EXCLUSION_PROOF.md`、`12_SELF_ASSESSMENT.md` 与 `07_MODEL_CORRESPONDENCE.md` 使用同一画像；不再声称八条义务全部 discharged。 |
| 终局研究状态与许可措辞 | `RESOLVED` | mutable dossier 内候选状态统一为 `PROVED_EXCLUDED_RESEARCH`；终局 `granted_effects` 改为 `permits_*`，并声明只限本钉死 research dossier，既不声称已经写账，也不授予 exact、certification、production、release、supervisor 或 publisher authority。 |

清偿提交为本文件所在的同批 Git commit；authority SHA 绑定的前置清偿提交为 `6ee8b42ff035324d935f028eed83ae7329dfa81f`。

## 3. 条件债务

### DEBT-A：authority currency 与 owner authorization 链

- **状态：** `RESOLVED`
- **已闭合内容：** `00_OWNER_AUTHORIZATION_20260816.md` 与 `00_ACCEPTANCE_CRITERIA_FROZEN.md` 均进入两份收据的 `authority_basis`；schema 钉死 `authority_class`、authority 路径与 SHA-256；PASS 路径实时重算文件摘要；[`15_test_receipt_contracts.py`](15_test_receipt_contracts.py) 持久验证磁盘字节、checker 常量与两份收据一致。
- **清偿提交：** `6ee8b42ff035324d935f028eed83ae7329dfa81f` 完成 authority path/SHA 绑定；本文件所在同批提交补齐 currency 与 schema-root 持久测试。

### DEBT-B：terminal premises 与 lift basis 的机器消费

- **状态：** `CONDITIONAL_DEBT`
- **未清偿内容：** `10_check_w0_terminal_exclusion.py` 尚未读取 `08_TERMINAL_EXCLUSION_JUDGMENT.json` 的 `premises` 数组，也未校验 lift step 3/4 的 `basis`。step 4 从“无合法 `(b,r)` 对”跨到固定候选的 dossier-local research classification，包含本批唯一尚未机器核验的跨对象空间 basis。
- **已完成的止血：** step-4 文字已改为 5 条机器关闭、3 条人工论证、0 条 open，不再把 argued 义务冒充 discharged。
- **查验方定序附注（2026-08-16）：** `LIFT-05` 的“非 `__unused__` ⇔ 进入 routing port specs”双向等价是 `PROVED_EXCLUDED` 穷尽性结论的承重点；当前仅有源码 marker 支撑，状态为 `ARGUED_NOT_MACHINE_CHECKED`，只在 research-only 围栏内成立。本 dossier 将来若被援引支撑任何更强主张（升格、外推或 certified 方向），`LIFT-05` 的机器化必须先于 DEBT-B 清偿。定序来源：出生证查验方附注，2026-08-16。
- **触发器：** 下次修改 `10_check_w0_terminal_exclusion.py`，或定理三立案；任一触发即必须读取 terminal premises，并逐项校验 lift step 3/4 basis 后才能交付。

### DEBT-C：契约负测、异常收敛与 schema 类型覆盖

- **状态：** `RESOLVED`
- **已闭合内容：** [`15_test_receipt_contracts.py`](15_test_receipt_contracts.py) 持久登记 manifest 条数/ID/required-evidence 漂移、15 类收据 schema 变体、schema 摘要 identity 漂移、schema 字节降格篡改、未知 keyword 与 authority currency；两个 checker 顶层均以 `Exception` 收敛为 typed FAIL；`verified_scope` 已列出允许字段、字段类型、PASS 必填集与 `additionalProperties: false`。
- **清偿提交：** 本文件所在同批 Git commit。

### DEBT-D1：object space 与复合角色关系式

- **状态：** `CONDITIONAL_DEBT`
- **未清偿内容：** 本 dossier 尚未给 theorem、model-path rejector 与 candidate-ledger updater 的 `object_space` 具名，也未写出 rejector 与 ledger-updater 的角色关系式。当前 terminal Judgment 同时承载“不存在 `(b,r)`”与 dossier-local 候选分类，二者的 object-space 关系仍只有显式散文边界，尚无机器可核的角色关系式。
- **触发器：** 终点度量协议修订，或定理三立案；触发后须引用三面模型的 object-space/transport 规则，并显式区分 rejector 结论与 ledger-updater 许可。

### DEBT-D2：`M_bottom` 形式定义

- **状态：** `CONDITIONAL_DEBT`
- **未清偿内容：** 当前引用的 Endpoint Metrics Protocol v1 只定义 `M_t`，未形式定义 `M_bottom`；本 dossier 的 `delta_M_bottom=-1` 只有“无下界时未解决候选质量减少一”的文字解释，只能保留为未授权消费的描述字段，不能冒充协议内已定义量或进入 granted effects。
- **触发器：** Endpoint Metrics Protocol 修订，或定理三立案；触发后须先给出 `M_bottom` 的对象域、计数单位、基线、更新律与它和 `M_t` 的关系，再允许继续消费该字段。

### DEBT-E：research 后缀与 granted effects 限界

- **状态：** `RESOLVED`
- **已闭合内容：** mutable dossier 的候选状态统一为 `PROVED_EXCLUDED_RESEARCH`；冻结验收件不回改。两份收据都带人读 `granted_effects_scope`；schema 按 outcome 精确限制 effect 枚举；终局 effects 只许可 dossier-local classification 与 research note，不再声称不存在实体的 ledger write，也不许可消费未定义的 `M_bottom`。
- **清偿提交：** 本文件所在同批 Git commit。

## 4. 重开规则

本登记中的 `RESOLVED` 只对所列机制与当前钉死字节成立。以下任一事件会重开对应条目：

- authority 文件、schema、checker 或 compact receipt 身份链变化；
- path obligation 数量、ID、required evidence 或 5/3/0 状态画像变化；
- terminal Judgment 增删 premise、lift step 或对象空间；
- Endpoint Metrics Protocol 为 `M_bottom` 建立、修改或拒绝形式定义；
- research candidate ledger 获得实体真源、写入协议或更高 authority。

## 5. 2026-08-17 后继账本勘误索引

2026-08-17 canonical ledger 对账确认：实验三开始前，current claims 已经覆盖槽饱和数学、x=1/y=1 禁碰轨道和固定 V0-A 6×7 候选排除。本文件前四节继续作为 2026-08-16 出生证与债务史料；它们不再单独决定 canonical candidate before-state 或 endpoint delta。

现行解释必须同时读取：

- [`16_CANONICAL_STATE_ERRATUM_20260817.md`](16_CANONICAL_STATE_ERRATUM_20260817.md)；
- [`../LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json`](../LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json)；
- [`../LEDGER_RECONCILIATION_PROTOCOL_V1.md`](../LEDGER_RECONCILIATION_PROTOCOL_V1.md)。

后继裁断的账目是：本地证明线 `UNPROVED_IN_THIS_LINE → PROVED_IN_THIS_LINE`；canonical candidate `PROVED_EXCLUDED → PROVED_EXCLUDED`；canonical `ΔM=0`。“第一笔非零候选排除交易”已撤回。

DEBT-D2 仍作为历史条件债保留，记录旧 envelope 曾出现未定义的 `M_bottom` 字段。当前 canonical 账已经停止消费该字段，所以本次勘误不需要、也不允许为它补造定义。只有后续协议明确重新引入 `M_bottom` 时，DEBT-D2 才按原触发器重开。
