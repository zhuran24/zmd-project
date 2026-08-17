# 实验三：W0 席位算术引理与固定矩形终局排除

> **当前状态：** `COMPLETE_RESEARCH_ONLY / PROVED_IN_LOCAL_LINE / CANONICAL_ALREADY_PROVED_EXCLUDED`
> **日期：** 2026-08-16；2026-08-17 完成 canonical 对账勘误。
> **性质：** `research_only / non_authorizing`
> **定理二判词：** `PASS`；相对于 current ledger 为 `EQUIVALENT_TO` 既有槽饱和 claim。
> **固定候选判词：** 本地证明线 `UNPROVED_IN_THIS_LINE → PROVED_IN_THIS_LINE`；canonical candidate `PROVED_EXCLUDED → PROVED_EXCLUDED`。
> **勘误入口：** [`16_CANONICAL_STATE_ERRATUM_20260817.md`](16_CANONICAL_STATE_ERRATUM_20260817.md)。
> **认证与发布效力：** 无。

本目录承载实验一的第二条离线定理，以及它与第一条定理的组合终局主张。验收判据先于证明提交；两条独立 checker 均使用标准库并从钉死字节复算承重事实。2026-08-17 对账确认这些数学和固定候选在实验前已由 current claims 覆盖，因此本包的增量属于机械化、assurance 与 replay capability，不属于新 claim truth 或 canonical endpoint movement。

## 一句话结果

固定 W0 binding contract 恰有 52 个 generic-output 席位，精确需求为 `blue_iron_ore=34` 与 `source_ore=18`，因此所有席位都必须活动，尤其 `boundary_port_041:out:0` 必活动。实验一定理又证明 041 活动会在 strict-empty 矩形内要求 `(1,53)` 成为 belt terminal，产生矛盾。故固定 `W0-ALIGNMENT` 布局下矩形 `x=1,y=51,w=6,h=7` 不存在当前研究模型接受的 binding+routing witness。

## 冻结入口

- [`00_OWNER_AUTHORIZATION_20260816.md`](00_OWNER_AUTHORIZATION_20260816.md)：本批窄授权与非蕴含边界；
- [`00_ACCEPTANCE_CRITERIA_FROZEN.md`](00_ACCEPTANCE_CRITERIA_FROZEN.md)：不可回改的验收标准；
- [`01_CONTEXT_MANIFEST.json`](01_CONTEXT_MANIFEST.json)：问题、目标、上下文、输入、前代定理、coverage 与路径证据身份。

验收判据的主树提交先于定理提交，具体身份由 theorem receipt 的 chronology 字段记录。

## 定理二五件套

| 件 | 坐标 |
|---|---|
| 范围、条件、结论、消费契约 | [`02_JUDGMENT.json`](02_JUDGMENT.json) |
| 不依赖实验数据的证明 | [`03_PROOF.md`](03_PROOF.md) |
| 纯标准库 checker | [`04_check_w0_slot_arithmetic.py`](04_check_w0_slot_arithmetic.py) |
| schema-bound PASS 收据 | [`05_THEOREM_RECEIPT.json`](05_THEOREM_RECEIPT.json) |

定理二 checker 独立重导：

```text
boundary slots       46
protocol-core slots   6
total slots           52
blue requirement      34
source requirement    18
forced unused total    0
041 must be active   true
```

八个负变体全部被杀。coverage-off 不读 journal 仍 PASS；required 模式另确认 1007 个互异 selection 中 041 活动为 1007/1007，且该覆盖明确不是证明前提。

## W0 终局组合

- [`06_MODEL_CORRESPONDENCE_MANIFEST.json`](06_MODEL_CORRESPONDENCE_MANIFEST.json)：路径级承重身份与八条 lift 义务；
- [`07_MODEL_CORRESPONDENCE.md`](07_MODEL_CORRESPONDENCE.md)：槽级 contract 到实际 binding/routing research path 的逐步对应；
- [`08_TERMINAL_EXCLUSION_JUDGMENT.json`](08_TERMINAL_EXCLUSION_JUDGMENT.json)：固定候选的结构化终局 Judgment；
- [`09_TERMINAL_EXCLUSION_PROOF.md`](09_TERMINAL_EXCLUSION_PROOF.md)：定理二 × 定理一的七步组合证明；
- [`10_check_w0_terminal_exclusion.py`](10_check_w0_terminal_exclusion.py)：终局独立 checker；
- [`11_TERMINAL_RECEIPT.json`](11_TERMINAL_RECEIPT.json)：schema-bound 终局 PASS 收据；
- [`12_SELF_ASSESSMENT.md`](12_SELF_ASSESSMENT.md)：读者视角自评、什么不算、保留风险与重开触发器；
- [`13_RECEIPT_ENVELOPE_SCHEMA_V1.json`](13_RECEIPT_ENVELOPE_SCHEMA_V1.json)：定理与终局两份收据共用且被 checker 摘要钉死的机器 envelope schema；
- [`14_BIRTH_CERTIFICATE_AND_CONDITIONAL_DEBTS.md`](14_BIRTH_CERTIFICATE_AND_CONDITIONAL_DEBTS.md)：出生证裁定、同批清偿状态与条件债触发器史料；
- [`15_test_receipt_contracts.py`](15_test_receipt_contracts.py)：manifest、schema、authority currency 与 schema 字节篡改的持久负测；
- [`16_CANONICAL_STATE_ERRATUM_20260817.md`](16_CANONICAL_STATE_ERRATUM_20260817.md)：在不回写历史 Judgment、checker 与收据的前提下，订正 canonical/local 状态与 endpoint 账目。

终局 checker 重新运行两条 theorem checker，核验 6 份 theorem 身份文件，并从 A_BASELINE JSON snapshot 重算：

```text
variables                         17,190
constraints                          289
generic-output slots                  52
generic-output literals              156
target ExactlyOne constraint         273
blue exact-count constraint          287 = 34
source exact-count constraint        288 = 18
path obligations                 5 machine-discharged + 3 argued; 0 open
terminal path negative tests     6 / 6 killed
persistent contract test file    15_test_receipt_contracts.py
```

## 终点候选分类与 canonical 对账

当前 `L=ABSENT`，所以全局 `M_t` 继续是 `N_A_NOT_READY`，没有制造数值 sentinel。

2026-08-17 对账后的唯一现行口径是：

```text
candidate = W0-ALIGNMENT | x=1,y=51,w=6,h=7
local proof line = UNPROVED_IN_THIS_LINE -> PROVED_IN_THIS_LINE
canonical candidate = PROVED_EXCLUDED -> PROVED_EXCLUDED
evidence_type = ALTERNATE_MECHANIZED_PROOF_FOR_NAMED_6X7_CANDIDATE
canonical ΔM = 0
global M_t = N_A_NOT_READY -> N_A_NOT_READY
ΔL = ZERO
ΔU = ZERO
```

历史冻结件、terminal Judgment、checker 与 receipt 中的 `UNKNOWN → PROVED_EXCLUDED_RESEARCH` 和 `delta_M_bottom=-1` 保留原字节，只能按当时 dossier-local 认识口径读取。它们不再具有 canonical candidate transition 或 endpoint metric 含义；“第一笔非零候选排除交易”已撤回。

## 与 current claims 的关系

| 对象 | 关系 | current claim | 新增价值 |
|---|---|---|---|
| 实验一定理一的 041 一格冲突 | `INSTANCE_COROLLARY_OF` | `CLAIM-STRICT-HOLE-AVOIDS-X1-Y1` | `MECHANIZED_ONE-PORT_COROLLARY` |
| 实验三定理二的 52=52 槽账 | `EQUIVALENT_TO` | `CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED` | `MECHANIZED_REPROOF` |
| 实验三固定 6×7 候选终局 | `SUBSUMED_BY` | `CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE` | 命名候选的替代机械证明 |

三项 semantic novelty 均为 `NONE`。完整逐实验账目见根目录 [`LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json`](../LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json)。

## 条件债触发器

以下任一工作开始前必须同时读取 [`14_BIRTH_CERTIFICATE_AND_CONDITIONAL_DEBTS.md`](14_BIRTH_CERTIFICATE_AND_CONDITIONAL_DEBTS.md) 与 [`16_CANONICAL_STATE_ERRATUM_20260817.md`](16_CANONICAL_STATE_ERRATUM_20260817.md)：再次修改 `10_check_w0_terminal_exclusion.py`、定理三立案，或 Endpoint Metrics Protocol 修订。前两类工作必须处理 DEBT-B/DEBT-D1；若未来重新引入 `M_bottom`，度量协议工作必须处理 DEBT-D2。当前 canonical 账不消费 `M_bottom`。

## 与实验二金丝雀的关系

实验二的冻结科学判词仍为 `INCONCLUSIVE`。本批的新静态证明解释了 treatment 残余 binding contract 在数学上为空，但没有把当时 20 秒窗口内未观测到的 solver terminal 倒签成已观测 `INFEASIBLE`。

## 非蕴含

本包不产生：

- production `CERTIFIED`、exact-status、supervisor、publisher 或 release 效力；
- stable claim ledger 写入；
- production lowering、通用 D3/D4 或 theorem registry 常态化；
- 新的 canonical claim truth、candidate transition 或 endpoint movement；
- 其他布局、其他矩形、score band、上下界或全局最优性结论；
- current binding model 与完整 adjudicated-game 语义等价；
- 1007 份观测的证明地位；
- 对实验二 `INCONCLUSIVE` 的历史重判。
