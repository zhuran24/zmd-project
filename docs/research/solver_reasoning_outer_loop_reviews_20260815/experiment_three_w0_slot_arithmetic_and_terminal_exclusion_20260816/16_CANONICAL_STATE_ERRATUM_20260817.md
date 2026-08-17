# 实验三 canonical/local 状态勘误（2026-08-17）

> **状态：** `EFFECTIVE_ERRATUM / RESEARCH_ONLY`
> **生效日期：** 2026-08-17
> **适用对象：** 本目录中固定 `W0-ALIGNMENT`、矩形 `R=[1,6]×[51,57]` 的 theorem-two 与 terminal-exclusion 文书。
> **裁断来源：** local-optional 坐标 `.artifacts/outer_loop_recon_20260817/B_VERDICT_FULL_20260817.md`，SHA-256=`16a2c6b3db19cbce6747c7169c31e5743c69934613c9bee9df6e6212b80c7bdc`。
> **机器对账收据：** [`LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json`](../LEDGER_RECONCILIATION_ERRATUM_RECEIPT_20260817.json)。
> **解释优先级：** 对 canonical 状态、问题进展与 endpoint delta 的解释，以本勘误和上述对账收据为准；历史冻结件、Judgment、checker 与收据保留原字节。

## 1. 勘误结论

实验三的数学证明和 checker 结果保留。需要撤回的是把本地证明线的认识变化记成 canonical 研究账变化。

历史文书中的：

```text
UNKNOWN -> PROVED_EXCLUDED_RESEARCH
ΔM_bottom = -1
第一项非零的固定候选排除注记
```

不得再解释为 canonical candidate transition、canonical endpoint delta 或主线首次非零问题进展。

正确口径是：

```text
local proof line:
UNPROVED_IN_THIS_LINE -> PROVED_IN_THIS_LINE

canonical candidate:
PROVED_EXCLUDED -> PROVED_EXCLUDED

canonical ΔM:
0
```

“第一笔非零候选排除交易”与同义表述全部撤回。

## 2. 双层状态账

| 账户 | before | after | 变化 |
|---|---|---|---|
| 本地证明线 | `UNPROVED_IN_THIS_LINE` | `PROVED_IN_THIS_LINE` | 正，完成一条本线替代证明 |
| canonical 定理状态 | `ALREADY_KNOWN` | `ALREADY_KNOWN` | 0 |
| canonical candidate 状态 | `PROVED_EXCLUDED` | `PROVED_EXCLUDED` | 0 |
| canonical `ΔM` | 0 | 0 | 0 |
| `L` | `ABSENT` | `ABSENT` | 0 |
| `U` | 不由本实验修改 | 不由本实验修改 | 0 |
| 全局 `M_t` | `N_A_NOT_READY` | `N_A_NOT_READY` | 0 |
| evidence assurance | 既有叙述、枚举与来源复算 | 增加独立 checker、负测与可重放收据 | 正 |
| replay capability | 较弱 | 较强 | 正 |

`PROVED_EXCLUDED_RESEARCH` 可以继续作为本 dossier 的局部结果标签，但不能再与 canonical `UNKNOWN -> PROVED_EXCLUDED` 的箭头绑定。

## 3. 与 current claims 的关系

对账使用 `data/knowledge/claims.jsonl` 的 current snapshot，稳定身份以 claim ID 为准：

| 实验对象 | 关系 | current claim | 正确计价 |
|---|---|---|---|
| 实验一定理一：041 活动时的一格冲突 | `INSTANCE_COROLLARY_OF` | `CLAIM-STRICT-HOLE-AVOIDS-X1-Y1` | semantic novelty=`NONE`；evidence increment=`MECHANIZED_ONE-PORT_COROLLARY` |
| 实验三定理二：generic output 52=52 槽饱和 | `EQUIVALENT_TO` | `CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED` | semantic novelty=`NONE`；evidence increment=`MECHANIZED_REPROOF` |
| 实验三固定 6×7 候选终局 | `SUBSUMED_BY` | `CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE` | canonical candidate 早已排除；本实验提供指定候选的替代机械证明 |
| 实验三终局中的 041 冲突分量 | `INSTANCE_COROLLARY_OF` | `CLAIM-STRICT-HOLE-AVOIDS-X1-Y1` | 只覆盖一个命名端口实例，不等于一般 x=1/y=1 轨道定理的完整机械化 |

定理二几乎完整机械重证了槽饱和 claim。定理一只机械化了 041 实例。终局 checker 只给出命名 6×7 候选的替代证明，没有机械穷尽 W0 的全部 admissible 矩形，也没有重建一般轨道定理的 23 个 front、周期结构与最长空段证明。

## 4. 历史文件保留规则

以下文件保留原字节，不做追溯回写：

- `00_ACCEPTANCE_CRITERIA_FROZEN.md`；
- `05_THEOREM_RECEIPT.json`；
- `08_TERMINAL_EXCLUSION_JUDGMENT.json`；
- `10_check_w0_terminal_exclusion.py`；
- `11_TERMINAL_RECEIPT.json`；
- `13_RECEIPT_ENVELOPE_SCHEMA_V1.json`。

这些文件中的 legacy 字段只表示当时 dossier 自己的局部认识口径。历史 terminal checker 仍会要求 `delta_M_bottom=-1`，它的 PASS 只证明旧 envelope 按旧契约自洽，不证明该字段具有 canonical endpoint 语义。

现行叙述文档改用双层状态口径，并从入口页链接本勘误。任何后续消费者若直接读取历史 JSON 或 checker 摘要，必须同时读取本勘误和根目录对账收据。

## 5. 形式化冲突与未决项

### 5.1 历史 checker 与 canonical 账目不一致

仓库现状中，terminal checker 和 receipt schema 仍把 `delta_M_bottom=-1` 当作旧 envelope 的必填值；裁断要求 canonical `ΔM=0`。本批不修改历史 checker、schema 或 receipt，而用后继勘误建立解释优先级。若未来要让机器直接输出 canonical endpoint receipt，必须创建新版本协议与 checker，不能原地换义旧字段。

### 5.2 `M_bottom` 没有形式定义

Endpoint Metrics Protocol v1 没有定义 `M_bottom` 的对象域、计数单位、基线与更新律。旧 `delta_M_bottom` 字段因此不具备 canonical metric 身份。本勘误直接撤回其 canonical 消费，不自行补造定义。

### 5.3 claim 行号不是稳定身份

本次发现坐标为 snapshot 第 10、13、85 行。行号会随 ledger 演化漂移，后续引用必须使用 claim ID，并随 receipt 记录 ledger snapshot digest。

## 6. 待回挂 evidence 义务

`data/knowledge/claims.jsonl` 本批只读。以下 evidence link 只登记为待办，不在本批写入：

1. 把 `04_check_w0_slot_arithmetic.py` 挂到 `CLAIM-BOUNDARY-GENERIC-OUTPUT-SLOTS-SATURATED`，role=`mechanized reproof`；
2. 把实验一 `03_check_w0_ghost_front_certificate.py` 挂到 `CLAIM-STRICT-HOLE-AVOIDS-X1-Y1`，role=`instance-level mechanized corollary`；
3. 把 `10_check_w0_terminal_exclusion.py` 挂到 `CLAIM-BAND22-V0A-STRICT-HOLE-INCOMPATIBLE`，role=`alternate proof for the named 6x7 candidate`。

这些待办必须在另获 stable claim ledger 写权限后完成。回挂时不得把局部 checker 描述成一般轨道定理或全部 W0 admissible 域的完整机械证明。

## 7. 非蕴含

本勘误不改变：

- 两条 theorem checker 与 terminal checker 的历史 PASS；
- 实验二的 `INCONCLUSIVE`；
- claim statement、status 或 authority；
- production、certified、release、supervisor 或 publisher 表面；
- `L`、`U`、全局 `M_t` 或 exact-status；
- 任何 P0-P5 研究步骤的授权或执行状态。
