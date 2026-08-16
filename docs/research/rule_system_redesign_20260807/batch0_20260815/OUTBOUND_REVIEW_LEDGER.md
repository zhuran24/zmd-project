# 外发登记台账 v1

> 建册日期：2026-08-15
>
> 范围：规则系统重设计线及其直接前代在 2026-08-07 组装并投递的 GPT Pro 审查包。首批登记为 fen1 至 fen5；fen6 是模拟器盲推导对照，不是“审我们的材料”，故不混入本批审查包首批数据。
>
> 权威边界：本台账记录“发给谁、发了什么字节、回了什么、何时失效”。外审回复与本地核签不自动等于 owner 裁决；历史包的存在也不证明它仍代表当前树。

## 1. 记账规则

1. 每次外发先建唯一 `OUT-*` 行，再投递；包内容任何字节变化都新建 id，不能原地换包。
2. 包 sha 是实际投递 zip 的 SHA-256；若历史只留下归档包而无法证明与上传字节相同，必须标 `ARCHIVE_BYTES_ONLY`，不得补造同一性。
3. 冻结件快照单列路径与 sha；没有冻结件就写“不适用”，不能拿 zip sha 代替内部快照身份。
4. 会话平台 id 缺失时写 `MISSING`，不根据目录名猜造；目录别名只能作为仓内追踪代号。
5. 回件原文、评审自产附件、本地核签分三层登记。消费时优先引用本地核签，并回读其证据，不把 raw reply 当 owner authority。
6. 语义、代码或 canonical 换代后，原行不删除；新增“当前有效性”和“失效通知”事件。没有证据证明通知已送达，就写 `NOT_EVIDENCED`。
7. 状态受控词：`STAGED / SENT / RETURNED / ADJUDICATED / SNAPSHOT_SUPERSEDED / INVALIDATED / CLOSED_HISTORICAL`，可并列。

## 2. 首批索引

| id | 主题 | 投递日 | 收件通道 | 包状态 | 当前有效性 |
|---|---|---|---|---|---|
| OUT-20260807-FEN1 | canonical 权威文本四问 | 2026-08-07 | GPT Pro 独立会话，仓内代号 fen1，平台 id `MISSING` | RETURNED + ADJUDICATED | SNAPSHOT_SUPERSEDED；只按历史快照消费 |
| OUT-20260807-FEN2 | routing 禁 de-mix soundness | 2026-08-07 | GPT Pro 独立会话，仓内代号 fen2，平台 id `MISSING` | RETURNED + ADJUDICATED | CLOSED_HISTORICAL；代码快照限定 |
| OUT-20260807-FEN3 | U-01 仓库准入/混流 | 2026-08-07 | GPT Pro 独立会话，仓内代号 fen3，平台 id `MISSING` | RETURNED + ADJUDICATED | CLOSED_HISTORICAL；代码快照限定 |
| OUT-20260807-FEN4 | P2.0 特化设计与重判 | 2026-08-07 | GPT Pro 独立会话，仓内代号 fen4，平台 id `MISSING` | RETURNED + ADJUDICATED | CLOSED_HISTORICAL；以后续勘误与核签为入口 |
| OUT-20260807-FEN5 | 规则系统重设计双版本 | 2026-08-07 | GPT Pro 独立会话，仓内代号 fen5，平台 id `MISSING` | RETURNED + ADJUDICATED | CLOSED_HISTORICAL；立项不等于方法逐项批准 |

## 3. 逐包记录

### OUT-20260807-FEN1

| 字段 | 值 |
|---|---|
| 审查对象 | canonical 规则权威文本四个承重条款 |
| 投递包 | `.artifacts/gpt_pro_review_batch_20260807/zmd_review_fen1_canonical.zip` |
| 归档包字节 / SHA-256 | `45,445` / `439124dcf7647a4246e974586e1a52f59ede313621e83e5f595b51bc5d25f5d6` |
| 投递字节同一性 | `ARCHIVE_BYTES_ONLY`：现有档案与组包清单相符，但仓内没有平台侧上传回执可证明上传字节逐字相同 |
| 冻结件快照 | `1_canonical_text/canonical_rules.json`，SHA-256 `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca`；`preprocess_plan.json`，SHA-256 `5c669c4fa48d2ed77a3283f06c1d5f97f7542c92253c41ba31fbaba0b313c4ee` |
| 收件人/会话 | GPT Pro 独立会话；仓内代号 `fen1`；平台会话 id `MISSING` |
| 回件原文 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen1/REPLY_VERBATIM.md` |
| 本地核签 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen1/ADJUDICATION_fen1.md` |
| 当前状态 | `RETURNED + ADJUDICATED + SNAPSHOT_SUPERSEDED` |
| 换代原因 | 2026-08-08 canonical 批重写 `rate_lemma_scope`、box 相关条款及其他字段；本包不能代表当前 canonical 字节 |
| 失效通知 | 对原 GPT Pro 会话的单独通知 `NOT_EVIDENCED`；2026-08-15 在本台账补登当前消费者警示 |
| 消费规则 | 可引用它对旧快照的发现及核签方法；任何“当前 canonical 仍如此”的断言必须回读当前 `rules/canonical_rules.json` |

### OUT-20260807-FEN2

| 字段 | 值 |
|---|---|
| 审查对象 | routing 禁 de-mix 约束的 soundness，Q1 至 Q6 |
| 投递包 | `.artifacts/gpt_pro_review_batch_20260807/zmd_review_fen2_mixflow.zip` |
| 归档包字节 / SHA-256 | `76,351` / `c822907a755d02894bb4738b9e957e63b6b2e7a44bab111414bc858d78f488c6` |
| 投递字节同一性 | `ARCHIVE_BYTES_ONLY` |
| 被审代码身份 | `fb76e15` 快照，关键源码以 `src_*_at_fb76e15.py` 随包；冻结件快照不适用 |
| 收件人/会话 | GPT Pro 独立会话；仓内代号 `fen2`；平台会话 id `MISSING` |
| 回件原文 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen2/REPLY_VERBATIM.md` |
| 本地核签 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen2/ADJUDICATION_fen2.md`；模拟器判读 `.artifacts/gpt_pro_review_batch_20260807/verdict/fen2/SIM_JUDGE_D1.md` |
| 当前状态 | `RETURNED + ADJUDICATED + CLOSED_HISTORICAL` |
| 失效/作用域通知 | 包内已明示代码快照；后续 U-01 代码晚于 `fb76e15`。单独通知原会话 `NOT_EVIDENCED`，但核签已按快照差异重判 |
| 消费规则 | 只能把 finding 投影到当前树后再声称“仍存在/已修”；不得直接把旧行号当现态 |

### OUT-20260807-FEN3

| 字段 | 值 |
|---|---|
| 审查对象 | U-01 门口排他放宽、混吃汇流区及其消费者，Q7 至 Q19 |
| 投递包 | `.artifacts/gpt_pro_review_batch_20260807/zmd_review_fen3_u01.zip` |
| 归档包字节 / SHA-256 | `155,476` / `713e5d9849a58ca1868da0b4056431dbf594e6195a1cfd36f08c52e098b726f8` |
| 投递字节同一性 | `ARCHIVE_BYTES_ONLY` |
| 被审代码身份 | `c6a9f8b`，另有中间态 `4e479a4` 的可选材料未进 zip |
| 冻结件快照 | 不适用。暂存目录中的 `zz_optional_canonical_rules_MAIN.json` 未进投递 zip；其 SHA-256 为 `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca`，仅用于解释包内版本落差，不得冒充“已随包” |
| 收件人/会话 | GPT Pro 独立会话；仓内代号 `fen3`；平台会话 id `MISSING` |
| 回件原文 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen3/REPLY_VERBATIM.md`，另存原始 `3回复.txt` |
| 本地核签 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen3/ADJUDICATION_fen3.md` |
| 当前状态 | `RETURNED + ADJUDICATED + CLOSED_HISTORICAL` |
| 失效/作用域通知 | `PROMPT_3.md` 已向评审明示 U-01 代码树与 main canonical 的版本落差；后续当前树消费仍须重新定位符号 |
| 消费规则 | 回件对 `c6a9f8b` 的否定不能直接外推为整个现行范式家族的死刑；以核签逐项结论为入口 |

### OUT-20260807-FEN4

| 字段 | 值 |
|---|---|
| 审查对象 | P2.0 特化设计、第一轮重判及复算件 |
| 投递包 | `.artifacts/gpt_pro_review_batch_20260807/zmd_review_fen4_p2_0.zip` |
| 归档包字节 / SHA-256 | `114,288` / `3750e04c4c700538ca53c6d51fee51b90e18320365dad00fd4748bfc535303b4` |
| 投递字节同一性 | `ARCHIVE_BYTES_ONLY` |
| 冻结件快照 | 不适用；该包是设计/复算审查包 |
| 收件人/会话 | GPT Pro 独立会话；仓内代号 `fen4`；平台会话 id `MISSING` |
| 回件原文 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen4/REPLY_VERBATIM.md` |
| 本地核签 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen4/ADJUDICATION_fen4.md` |
| 当前状态 | `RETURNED + ADJUDICATED + CLOSED_HISTORICAL` |
| 包装欠账 | 投递 zip 未含若干 `zz_optional_` 承重附件，核签已把相关项降级为包装欠账；未来外发不得复用“暂存目录存在 = 已随包”的读法 |
| 失效通知 | 后续勘误已在仓内文书留痕；对原会话单独通知 `NOT_EVIDENCED` |
| 消费规则 | 以核签与勘误后二次扫描为准；raw reply 不能覆盖后续独立复算 |

### OUT-20260807-FEN5

| 字段 | 值 |
|---|---|
| 审查对象 | 规则系统重设计的第一性版本、病例驱动版本、对勘与失败分类 |
| 投递包 | `.artifacts/gpt_pro_review_batch_20260807/zmd_review_fen5_redesign.zip` |
| 归档包字节 / SHA-256 | `111,300` / `14562c964ba9b1fb4d94fd6b4bc7126c41543098a0f23a51ad28de74f9f1bd20` |
| 投递字节同一性 | `ARCHIVE_BYTES_ONLY` |
| 冻结件快照 | 不适用；包内是 docs 侧设计与审查题面 |
| 收件人/会话 | GPT Pro 独立会话；仓内代号 `fen5`；平台会话 id `MISSING` |
| 回件原文 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen5/REPLY_VERBATIM.md` |
| 本地核签 | `.artifacts/gpt_pro_review_batch_20260807/verdict/fen5/ADJUDICATION_fen5.md` |
| 当前状态 | `RETURNED + ADJUDICATED + CLOSED_HISTORICAL` |
| 当前作用域 | owner 2026-08-13 允许本线立项；2026-08-15 又接受第 4 件、准许 `rules/derived/` 非冻结立架（`3d34687`）。其余七件仍逐项待裁；fen5 审过与单项获批都不等于整套方法已获 owner 批准 |
| 失效通知 | 未整体失效；任何被后续事实或 owner 裁决改写的局部仍须通过连锁账逐项标注 |
| 消费规则 | 当前落地批以 `FINAL_DESIGN.md` 批表、owner 状态追记和 fen5 核签共同约束，不单独拿 raw reply 充当施工授权 |

## 4. 首批完整性与已知缺口

- 首批审查包行数：`5`，非空。
- 五包均有归档 zip、完整 SHA-256、回件原文与本地核签路径。
- 五个历史 GPT Pro 会话的平台会话 id 均未在仓内材料登记，状态统一为 `MISSING`；本台账不追猜。
- 现有 zip sha 是 2026-08-15 对仓内归档包实测值；缺平台上传回执，所以均保守标 `ARCHIVE_BYTES_ONLY`。
- fen6S/fen6F 属盲推导实验，若后续需要统一登记，应另建 `OUT-BLIND-*` 类型，不能借“外审”名义混入本表。

## 5. 新外发前检查

| 检查 | 结果 |
|---|---|
| 已先建 `OUT-*` id |  |
| zip 路径、字节数、SHA-256 已实测 |  |
| 冻结件/代码/文档快照身份分别登记 |  |
| 收件会话与独立性要求已登记 |  |
| 暂存目录与实际 zip 内容已用 `unzip -l` 对账 |  |
| `zz_optional_` 是否随包逐项写明 |  |
| 旧包是否需要失效通知或范围警示 |  |
| 回件归档、核签与连锁重写负责人已预分配 |  |
