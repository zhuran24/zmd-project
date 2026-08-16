# 实验三：W0 席位算术引理与固定矩形终局排除

> **当前状态：** `COMPLETE_RESEARCH_ONLY / PROVED_EXCLUDED_RESEARCH`
> **日期：** 2026-08-16
> **性质：** `research_only / non_authorizing`
> **定理二判词：** `PASS`
> **固定候选判词：** `UNKNOWN → PROVED_EXCLUDED`
> **认证与发布效力：** 无。

本目录承载实验一的第二条离线定理，以及它与第一条定理的组合终局主张。验收判据先于证明提交；两条独立 checker 均使用标准库并从钉死字节复算承重事实。

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
| 八字段 PASS 收据 | [`05_THEOREM_RECEIPT.json`](05_THEOREM_RECEIPT.json) |

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
- [`11_TERMINAL_RECEIPT.json`](11_TERMINAL_RECEIPT.json)：八字段终局 PASS 收据；
- [`12_SELF_ASSESSMENT.md`](12_SELF_ASSESSMENT.md)：读者视角自评、什么不算、保留风险与重开触发器；
- [`13_RECEIPT_ENVELOPE_SCHEMA_V1.json`](13_RECEIPT_ENVELOPE_SCHEMA_V1.json)：定理与终局两份八字段收据共用的机器 envelope schema。

终局 checker 重新运行两条 theorem checker，核验 6 份 theorem 身份文件，并从 A_BASELINE JSON snapshot 重算：

```text
variables                         17,190
constraints                          289
generic-output slots                  52
generic-output literals              156
target ExactlyOne constraint         273
blue exact-count constraint          287 = 34
source exact-count constraint        288 = 18
path obligations                 8 / 8 discharged
terminal negative tests          6 / 6 killed
```

## 终点候选账

当前 `L=ABSENT`，所以全局 `M_t` 继续是 `N_A_NOT_READY`，没有制造数值 sentinel。

本批只登记固定候选交易：

```text
candidate = W0-ALIGNMENT | x=1,y=51,w=6,h=7
state = UNKNOWN -> PROVED_EXCLUDED
evidence_type = EXACT_SINGLETON_EXCLUSION_BY_COMPOSED_THEOREMS
ΔM_bottom = -1
global M_t = N_A_NOT_READY -> N_A_NOT_READY
ΔL = ZERO_BY_SCOPE
ΔU = ZERO_BY_SCOPE
```

## 与实验二金丝雀的关系

实验二的冻结科学判词仍为 `INCONCLUSIVE`。本批的新静态证明解释了 treatment 残余 binding contract 在数学上为空，但没有把当时 20 秒窗口内未观测到的 solver terminal 倒签成已观测 `INFEASIBLE`。

## 非蕴含

本包不产生：

- production `CERTIFIED`、exact-status、supervisor、publisher 或 release 效力；
- stable claim ledger 写入；
- production lowering、通用 D3/D4 或 theorem registry 常态化；
- 其他布局、其他矩形、score band、上下界或全局最优性结论；
- current binding model 与完整 adjudicated-game 语义等价；
- 1007 份观测的证明地位；
- 对实验二 `INCONCLUSIVE` 的历史重判。
