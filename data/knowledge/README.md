# 结构化知识层

这里保存文档知识脊柱的机器真源。它不替代 `PROJECT_LOCK.md`、canonical rules、proof obligations 或 owner gate，而是给结论、决定、证据包、审阅状态、主题和术语稳定身份，再生成统一查询页。
## 文件职责

- `current_state.json`：声明机器源、CURRENT 章节、必需 singleton slot、inventory 根和知识生成输出。文档前门与兼容跳转由 document-system registry 管理。
- `claims.jsonl`：一行一个 claim，写明 statement、scope、premises、consequences、`does_not_imply`、依赖、换代、表示位置、authority basis、decision 链接和证据耐久层。
- `decisions.jsonl`：non-authorizing、append-only 的 decision 查询登记册；每条记录必须指向外部 owner 真源并保存 supersession，登记册本身不授予 authority。
- `dossiers.json`：`docs/research/` 与 `.artifacts/` 一级证据包 inventory。
- `backfill_reviews.jsonl`：一行一次声明范围内的审阅。它记录读过哪些路径、得到哪些 claim、未决项和重审触发条件。
- `backfill_triage.json`：对没有 current review 的 dossier 做穷尽且唯一的分流。triage 是 inventory coverage，不是 semantic review。
- `topics.json`：稳定 `TOPIC-*` 入口，把 claim、dossier topic label、术语、入口和开放问题连接起来。
- `knowledge_census.json`：唯一人工维护的知识层数字验收 fixture；checker 将其与账本计算值比较，测试不再散落当前计数。
- `terminology.json`：稳定 `TERM-*` 词汇坐标，登记 canonical label、alias、定义、区别和来源。
- `schemas/`：上述结构的 JSON Schema。
生成结果为：
- [`docs/CURRENT.md`](../../docs/CURRENT.md)
- [`docs/CATALOG.md`](../../docs/CATALOG.md)
- [`docs/REASONING_LEDGER.md`](../../docs/REASONING_LEDGER.md)
- [`docs/VALIDITY_LEDGER.md`](../../docs/VALIDITY_LEDGER.md)
- [`docs/BACKFILL_LEDGER.md`](../../docs/BACKFILL_LEDGER.md)
- [`docs/TOPIC_INDEX.md`](../../docs/TOPIC_INDEX.md)
- [`docs/TERMINOLOGY.md`](../../docs/TERMINOLOGY.md)
- [`docs/OPEN_QUESTIONS.md`](../../docs/OPEN_QUESTIONS.md)
八份知识页面都禁止手工修改。它们在文档树中的 section 归属见 [`docs/SECTION_INDEX.md`](../../docs/SECTION_INDEX.md)。
## inventory、triage、review 与 claim

这四层不能合并：

```text
dossier 已登记
  ≠ 未审材料已分诊
  ≠ 声明范围内已做语义审阅
  ≠ 可复用结果已经提升为 claim
```

每个 dossier 必须恰好满足一种覆盖状态：

1. 有且只有一条 current review；或
2. 恰好位于一个 current triage 组。

两者不能重叠，也不能同时缺失。`review_scope=availability_and_provenance` 只核对 local-optional payload 的存在性、路径和来源，必须保持 `outcome=deferred`，不计作 semantic review。

把 triage dossier 晋升为 semantic review 时，必须在同一事务中：

1. 新建 current review；
2. 从 triage 组移除该 dossier；
3. 删除已经为空的 triage 组；
4. 重建并检查全部投影。

triage 不能声明 `no_reusable_claim`，因为没有语义审阅就不能得出“没有可复用结论”。

## claim 表示、authority 与 evidence

三组字段回答不同问题，不能互相替代：

```text
representation_class  → 记录在表示系统中的位置
authority              → 命题的认识论等级
authority_basis        → checker 能复核的依据与 source
evidence.storage       → git_tracked / workspace_untracked / external_root
```

当前 `claims.jsonl` 的稳定记录使用 `AUTHORITATIVE_CURRENT`，这只说明它们承担当前 claim 身份，不表示它们都是 `machine`。`machine` 必须使用 `machine_verified` basis，指向当前 Git-tracked 机器真源并由 `verification_id` 选择的 checker 实际核对承重字段。历史运行收据封顶 `research_authority`。

workspace evidence 必须显式 `optional=true`，可能被共享会话清理；external evidence 还必须给出恢复说明。两者可以支持研究叙事，但不能进入 machine basis。

`decisions.jsonl` 每条记录都必须 `non_authorizing=true`，通过 `external_decision_id` 与 `authority_source` 指向真正 owner source。登记册按 byte-prefix append-only 维护；唯一例外是 `intake.json` 明确声明并逐字段核验的 v1→v2 一次性迁移。claim 的 `decision_ids` 只是字段级可发现性链接，不会把 decision register 变成 authority。

## 新结论进入账本

1. 确认 authority 域，不能用研究报告覆盖机器 gate 或 frozen rules；为 claim 选择与 authority 对应的 typed `authority_basis`。
2. 在 `claims.jsonl` 建立稳定 ID，写清楚推出什么和不推出什么。
3. 关联提供证据的 dossier ID 与具体 evidence path，并标明每份证据的 `storage`；只有 Git-tracked source 可进入 machine basis。
4. 命题、scope、premises、authority effect 或认识论等级实质变化时新建 ID，并用 `supersedes` 或 validity 关系连接；同义补证不能暗中换命题。schema 新增字段的迁移只按 intake registry 明示的 absent→present 字段放行。
5. 只有需要进入 CURRENT 的 active claim 才占用 singleton `slot`；被 supersede 的旧 claim 保留其历史 slot 坐标，active 唯一性只在当前记录间检查。
6. 更新相关 topic 与 term 坐标，再运行生成器和 checker。

可选 profile 分别回答不同问题：

- `reasoning_profile`：条件处置、操作效果、solver 关系、发现方式和通用传播证据等级；
- `derivation_profile`：数学角色、稳定推导族和验证方式；
- `separation_profile`：候选来源、选择、验证、完备性、消费层和 baseline；
- `validity_profile`：反例、语义替代、实现或实验失效、归因更正、修复与复用边界。

profile 不改变 statement、status 或 authority。一次零激活、预算耗尽或未观察到分离不能升级成 generic propagation impossibility。

## dossier 审阅

一次 semantic review 至少要：

1. 声明真实 `review_scope` 与 `reviewed_paths`；
2. 区分正结论、条件式边界、反例、实验观察、方法价值和无可复用结果；
3. 把可复用结果登记为 claim，而不是塞进 review summary；
4. 把未决项写入 `unresolved`；
5. 再审时新建 review ID，并用 `supersedes` 保留历史。

review 只证明声明路径被整理过，不证明报告正确，也不会自动提升 authority。

## 新证据包

```bash
.venv/bin/python devtools/build_knowledge_docs.py --refresh-dossiers --write
```

refresh 会补登记新的一级研究包，并刷新 `auto_indexed` 条目。它不会覆盖 curated 字段，也不会静默删除消失的 tracked dossier。新 dossier 在关闭前必须得到 semantic review，或被显式放入 triage 组。

## 检查

```bash
.venv/bin/python devtools/build_knowledge_docs.py --write
.venv/bin/python devtools/check_knowledge_docs.py
.venv/bin/python devtools/docctl.py doctor
```

知识 checker 会验证 schema、ID 唯一性、依赖与换代无环、反向 successor 完整性、证据耐久层、machine authority 的具名 verifier、decision 外部指针及承重字段、表示分类映射、dossier inventory、review 唯一性、review/triage 穷尽互斥、topic 全覆盖、term alias 不碰撞、profile 边界和八份生成页的新鲜度。文档前门、兼容跳转与职责投影由 `docctl doctor` 检查。两者都不替代数学审查、owner decision、preflight 或 production certification。

## 事件驱动 workflow

新 tracked research dossier 使用 `devtools/docctl.py new research-dossier` 打开，中央 `dossiers.json` 是唯一可写真源。active workflow 关闭前，必须在同一 Git-visible 事务中新增或更新 current semantic review，并用 `devtools/docctl.py close-dossier` 写入 typed outcome。closure receipt 不原地改写，后续更正使用 successor、erratum 或新的 claim/decision。

既有 claim 与 decision ID 的 statement、scope、premises、consequences、does-not-imply、dependencies 或 supersession 等语义身份字段不能原地换义。新增证据或非语义 profile 仍需满足 schema；命题含义变化时创建新 ID，并显式连接换代方向。

所有知识事务完成投影后运行：

```bash
.venv/bin/python devtools/build_knowledge_docs.py --write
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/check_knowledge_docs.py
```
