# 维护 ZMD 文档系统

本指南回答“怎样安全改变文档框架”。普通文档内容维护先使用路径操作卡，不必通读本文件。

## 1. 所有文档操作的统一入口

修改或新建前：

```bash
.venv/bin/python devtools/docctl.py context <path> --intent <read|edit|create|move|delete>
```

完成写入与显式生成后，先查看本次 diff 触发的 intake 事件，再检查完整 diff 契约并运行共享只读验收门：

```bash
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/docctl.py audit --profile weekly
.venv/bin/python devtools/docctl.py gate --profile changed
```

`changed` / `full` / `weekly` 只检查当前树；冻结历史 object replay 使用手工 profile：

```bash
.venv/bin/python devtools/docctl.py gate --profile historical_replay
```

该命令要求完整外部 Git object graph。不要把它放回定时 profile。治理 lane 的 scratch 默认使用系统临时目录；需要指定时设置 `ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT`，目标必须在仓库之外。

`intake` 只显示当前事务触发的事件、阻断原因和后续 action；`check --changed` 复用同一解析结果。不要分别维护两套日常写入规则。

查看完整框架坐标：

```bash
.venv/bin/python devtools/docctl.py guide
.venv/bin/python devtools/docctl.py explain DOC-INV-001
.venv/bin/python devtools/docctl.py explain DOC-ADR-001 --full
```

`context` 返回的规则、短原因、写入源和检查命令是当前目标的有效契约。不要根据文件名或旧经验猜维护方式。

## 2. 按等级维护

### L0：普通内容变化

适用于 living 文档和稳定导航。

1. 读取操作卡。
2. 只在 `purpose` 范围内改正文。
3. 不复制 CURRENT、机器 gate 或知识账本中的易变值。
4. 运行操作卡列出的检查。

### L1：知识、规范或活跃研究变化

1. 读取操作卡和相关 claim、decision、dossier 摘要。
2. 区分证据、解释和 authority。
3. 结论含义不变时，可给原 claim 增加证据。
4. 命题、scope、premises 或 authority effect 实质变化时，新建 ID 并显式 supersede。
5. 关闭研究包前，把可复用结果提升为 claim，或记录无可复用结论的原因。
6. 在 `backfill_reviews.jsonl` 写入本次审阅范围、产出、未决项和下次触发条件。dossier 已登记或已进入 triage 都不等于已完成语义审阅。
7. 推理型 claim 需要可查询时，填写 `reasoning_profile`；其中 `generic_propagation_evidence=formal` 必须有明确命题、作用域和正式证明，实验零激活只能记为 `experimental_only`。
8. 可复用数学 claim 需要进入组合推导图时，填写 `derivation_profile`，并只在顶层 `dependencies` 中列直接前件。不要把传递闭包、完整证明或 authority 结论复制进 profile。
9. 选择或分离机制需要可查询时，填写 `separation_profile`，分别登记候选来源、选择方式、验证方式、完备性、消费落点和 baseline。validator 能检查 supplied candidate，不等于已有 autonomous separator；预算耗尽、未到达或零激活不能写成固定点。
10. `separation_profile` 不授予 authority。把 research-only 结论消费为 model omission、model constraint 或 objective bound 前，必须由 scoped claim 的 statement、premises、evidence 和 authority effect 单独支撑。
11. 历史 claim 被反例、语义裁决、实现缺陷、fixture 缺陷或归因复判影响时，填写 `validity_profile`，明确事件类型、受影响层、依据、复用策略、修复状态与时间作用域。`refuted` / `superseded` 不能只靠标题表达。
12. 语义替代必须新建 successor 并写 `supersedes`；被标为 `superseded` 的旧节点必须有反向 successor。`supersedes` 不是依赖边，也不能用一个更强但不同主题的定理随意覆盖旧 claim。
13. `current_after_repair` 只在修复已经 `revalidated` 时使用；实现修复、实验更换和 proof replay 各自只恢复声明范围，不自动恢复整条路线。
14. 每条 validity event 都要按 `DOC-INV-010` 保留方向性：先写清受影响层，再写复用策略；修复 validator 不等于恢复 experiment，恢复 experiment 不等于恢复 theorem 或 route verdict。
15. 命题含义不变而只增加验证方式时，可以保留 claim ID 并扩充 evidence / verification modes；命题、scope 或 premises 实质变化时仍按新 ID 与 `supersedes` 处理。
16. 新建 semantic review 时，同一事务从 `backfill_triage.json` 移除该 dossier；不得让 review 与 triage 重叠。
17. 新术语或概念别名进入 `terminology.json`；新主题入口进入 `topics.json`。不要在手写页面复制第二份 glossary 或 topic ledger。
18. 重建并检查知识投影。

### L2：局部 policy 变化

先判定变化级别：

- `coverage_update`：只给新内容增加精确 `path` / `paths` 规则，既有默认值和规则不变；运行 intake、doctor 与相关内容测试，不要求 L3 ADR。
- `contract_change`：改变既有文件的 mutation、authority、lifecycle、required reads 或局部继承；读取父子 policy，评估受影响路径并运行 doctor。
- `framework_semantic_change`：改变 schema、resolver、manifest、继承算法或核心 invariant；进入 L3，原子更新架构、ADR、迁移和测试。


1. 查询目标 `DOC_POLICY.json` 的 context。
2. 同时读取父级 policy 和 `DOC-INV-005`。
3. 优先改目录默认值，只有真实例外才增加 rule。
4. `prefix` 必须以 `/` 结尾；广域规则可由更精确的 `glob`、`paths` 或 `path` 规则细化；同一精确度的匹配规则不得设置冲突 scalar，声明顺序没有优先权。
5. 跨目录继承导致保护强度降低时，必须在该 overlay 中显式引用当前有效、authority effect 为 `scope_boundary`、且 scope 包含 `document-system` 或 `document-policy` 的 owner decision。不能继承祖先的 decision 当作通用通行证。
6. 重新生成 legacy 投影并运行 doctor 和定点测试。

### L3：框架语义变化

命中 manifest、schema、invariants、`docctl.py`、框架指南或 framework-core 边界时：

1. 阅读 `ARCHITECTURE.md`、本文件和相关 ADR。
2. 判断变化属于实现修复、兼容扩展、行为变化还是不变量变化。
3. 同步修改 schema、解析器、说明、迁移、兼容投影和测试。
4. 行为变化新增 ADR。不要重写已接受 ADR 的结论。
5. 不变量变化必须同步架构表、维护协议、回归测试和 owner-visible decision 记录。
6. 运行完整框架验收。
7. 若变化触及治理 lane、profile、runner 或 CI，必须同时更新 gate registry/schema、`docctl doctor`、红测和本地/CI 共用入口。

事件协议本身由 `data/repository_governance/document_system/intake.json` 与 schema 定义；改变事件、稳定身份字段、owner companion 或 lifecycle 语义属于框架行为变化，必须按 [`DOC-ADR-014`](ADR/014-event-driven-document-intake.md) 同步解析器、指南和红测。

Accepted ADR 还必须加入 `.docsystem/manifest.json` 的 `adrs` 映射。文件编号、`DOC-ADR-NNN` 稳定 ID 和映射键必须一致；未登记 ADR 与重复路径都会 fail closed。

## 3. 新增普通文档

推荐使用：

```bash
.venv/bin/python devtools/docctl.py new document docs/<path>.md --title "标题"
```

命令会先解析目标父目录 policy。若结果仍是 `unmanaged`，先决定该目录应该继承哪类契约，不要靠单文件例外把未知类别藏起来。

新增后至少验证：

```bash
.venv/bin/python devtools/docctl.py context docs/<path>.md --intent edit
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/docctl.py check --changed
```

新 Markdown 必须在同一变更中获得非 `unmanaged` 的有效 policy；若它承担 current 职责，还必须已有显式 `section_refs`。不要先创建未知文档，再把分类留给后续整理。

## 4. 新增研究 dossier

```bash
.venv/bin/python devtools/docctl.py new research-dossier \
  docs/research/<name_YYYYMMDD> --title "研究标题" \
  --date YYYY-MM-DD --topic <stable-topic>
.venv/bin/python devtools/build_knowledge_docs.py --write
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/check_knowledge_docs.py
```

命令会原子创建 dossier 的 `README.md` 并在中央 `data/knowledge/dossiers.json` 写入 `active` workflow；不再要求先建目录、以后再刷新登记。中央 ledger 是唯一 dossier 真源，不创建第二份可独立编辑的局部状态文件。

研究期间 dossier 为 `active`，可以修正和追加。转为 `historical` 或 `superseded` 后，`docctl` 会自动把正文收紧为 `immutable`。后续更正使用 erratum、successor 或 superseding claim，不回写旧报告。

### 关闭 dossier 或回填历史 dossier

一次完整的语义审阅事务至少包含：

1. 确认 review 的 `review_scope` 和实际读取路径；
2. 把可复用正结论、条件式边界、负结果或反例登记为 claim；
3. 对没有可复用结论的材料明确写出 `outcome` 与原因；
4. 在 `backfill_reviews.jsonl` 新建稳定 review ID，并关联 dossier 与 claim；
5. 仍未解决的问题写入 `unresolved`，不要用空 claim 填满账本；
6. 若重审，创建新 review 并 supersede 旧 review，不改写旧审阅历史；
7. 若 dossier 原在 `backfill_triage.json`，同一事务将其移除；空组一并删除；
8. 重建全部八份知识投影。

review 只证明“这批材料按声明范围被审过”。它不证明 report 正确，也不自动提升 claim 的 authority。`availability_and_provenance` 只核对路径、可用性与来源，必须保持 deferred，并且不计入 semantic review。

尚未语义审阅的 legacy dossier 必须唯一落入 `backfill_triage.json` 的一个组。triage 只能表达分流、优先级、理由和 reopen trigger，不能写 `no_reusable_claim`，也不能生成 authority 结论。由新 intake 打开的 `active` workflow 在关闭前既不算 semantic review，也不进入历史 triage。

关闭新 workflow 时，先在同一变更中写 current semantic review 和必要的 claim/decision，然后执行：

```bash
.venv/bin/python devtools/docctl.py close-dossier DOSSIER-... \
  --closed-at YYYY-MM-DD \
  --review-id REVIEW-... \
  --outcome <knowledge_promoted|negative_results_promoted|decision_recorded|no_reusable_claim|superseded_by_dossier> \
  [--claim-id CLAIM-...] [--decision-id DECISION-...] \
  [--successor-dossier-id DOSSIER-...] \
  [--no-reusable-claim-reason "..."]
```

typed closure receipt 关闭后不可原地改写。outcome 必须与关联对象相符，例如 `knowledge_promoted` 需要 claim，`no_reusable_claim` 需要明确原因，`superseded_by_dossier` 需要 successor。

对于 `tracked_state=local_optional` 的 dossier，轻量 checkout 可以没有本机 artifact。`reviewed_paths` 仍必须在路径结构上属于该 dossier；checker 先做无穿越的前缀归属校验，再按 optional 语义处理文件缺失。不能为了让缺失 artifact 通过检查而把 review 指向 dossier 外部，或把实际只审了一个文件的记录伪装成 `full_dossier`。

## 5. 临时文档与本机证据

### 5.1 临时文档

临时 Markdown 只能放在显式 `document_class=ephemeral` 的目录，例如 `docs/drafts/`。创建时必须同时登记到期与退出语义：

```bash
.venv/bin/python devtools/docctl.py new document docs/drafts/<name>.md \
  --title "临时标题" --date YYYY-MM-DD \
  --expires-at YYYY-MM-DD \
  --exit-action <delete|archive|promote> \
  [--successor-path docs/history/...|docs/...] \
  --rationale "为什么需要这份短期材料"
```

`delete` 禁止 successor；`archive` 和 `promote` 必须预先声明一个不同的 durable successor。到期或任务完成后执行：

```bash
.venv/bin/python devtools/docctl.py exit-ephemeral docs/drafts/<name>.md --exited-at YYYY-MM-DD
```

命令会原子删除或移动正文，并从 active ephemeral registry 移除记录。不要只删正文、只删登记，或把过期日期向后挪来掩盖积压。

### 5.2 local-optional evidence

新的本机大工件不能由普通 dossier refresh 静默登记。准备好真实 payload、内部 manifest 和 tracked 恢复说明后执行：

```bash
.venv/bin/python devtools/docctl.py register-local-evidence .artifacts/<package> \
  --title "证据包标题" \
  --manifest-path .artifacts/<package>/<manifest> \
  --recovery-instructions .artifacts/README.md \
  --opened-at YYYY-MM-DD --topic <stable-topic> \
  [--source-locator "稳定外部坐标"]
```

登记会计算 manifest SHA-256，并以 `local_optional` active workflow 写入中央 dossier ledger。轻量 checkout 可以缺少 payload，但恢复说明必须留在 tracked 仓库中；不能用空占位或伪造 hash 换取绿色检查。

## 6. 新增目录 policy

只有目录的维护语义确实不同于父目录时才新增 `DOC_POLICY.json`。

最小步骤：

1. 从最近祖先 policy 复制 schema 版本和必要字段。
2. 用 `defaults` 描述该目录的大多数成员。
3. 用少量 `rules` 描述真实例外。
4. 若旧引用扫描器需要看到该目录，在 `legacy_projection` 中贡献 rule 或 out-of-scope note。
5. 运行：

```bash
.venv/bin/python devtools/docctl.py context <new-dir>/DOC_POLICY.json --intent edit
.venv/bin/python devtools/docctl.py render-legacy --write
.venv/bin/python devtools/docctl.py render-guidance --write
.venv/bin/python devtools/docctl.py render-entrypoints --write
.venv/bin/python devtools/docctl.py render-sections --write
.venv/bin/python devtools/docctl.py render-convergence --write
.venv/bin/python devtools/docctl.py render-maintenance --write
.venv/bin/python devtools/docctl.py doctor
.venv/bin/python devtools/docctl.py gate --profile framework \
  --lane document_system_regressions
```

不要给每个文件都加 policy。默认继承是常态，局部声明是例外。

### policy 路径的退役边界

当前 v1 不允许直接删除或移动已经存在的 `DOC_POLICY.json`。policy 是目录保护的锚点，删除它可能在不触碰后代文件的情况下把整棵子树降回更宽松的祖先规则。需要合并目录策略时，先在原路径保留一个可解析的兼容 policy，把有效规则迁到父级并增加回归测试；待未来引入带基线比较、迁移声明和 owner decision 的 retirement 协议后，再移除锚点。

新增内容的精确 policy 覆盖属于 `coverage_update`，既有局部合同调整属于 `contract_change`；只有改变 schema、resolver、manifest、继承算法或核心 invariant 的 `framework_semantic_change` 才必须进入 L3，并同步架构、ADR、迁移和框架测试。

## 7. 修改 policy schema 或继承算法

以下变化属于框架行为变化：

- 新增、删除或改变 contract 字段；
- 改变 selector 匹配语义；
- 改变 list 合并或 scalar 冲突规则；
- 改变 mutation 保护顺序；
- 改变 policy 自身治理方式；
- 改变 dossier 或 framework-core 动态收紧。

完整变更包应包含：

```text
新 ADR 或明确引用已有 ADR
schema 变化
resolver 变化
旧 policy 迁移
ARCHITECTURE / MAINTAINING 更新
正例、反例和回归测试
legacy 投影重建
```

纯实现 bug 修复不强制新增 ADR，但必须证明外部行为未改变，并加入能让旧 bug 复现为红、修复后翻绿的测试。

## 8. 修改核心不变量

不变量不是普通文案。修改 `invariants.json` 时必须同时：

1. 说明旧原则为什么不足；
2. 新增 ADR，或用新 ADR 显式 supersede 旧决定；
3. 更新 `ARCHITECTURE.md` 的 invariant 表；
4. 更新本维护协议中的操作后果；
5. 增加或修改 checker/test 覆盖；
6. 评估所有现有 policy 是否需要迁移；
7. 更新系统版本。

`docctl check --changed` 会检查这一原子变更的最低陪同文件。

## 9. 生成页和兼容投影

### 八份知识投影

```bash
.venv/bin/python devtools/build_knowledge_docs.py --write
.venv/bin/python devtools/check_knowledge_docs.py
```

禁止直接修改 `docs/CURRENT.md`、`docs/CATALOG.md`、`docs/REASONING_LEDGER.md`、`docs/VALIDITY_LEDGER.md`、`docs/BACKFILL_LEDGER.md`、`docs/TOPIC_INDEX.md`、`docs/TERMINOLOGY.md` 或 `docs/OPEN_QUESTIONS.md`。

知识生成器写入的全局 source digest 也是生成页字节的一部分。任何 ledger 只要会改变某份投影的正文或 source digest，就必须列入该投影在 `DOC_POLICY.json` 中的 `source_paths`；不能因为正文语义未变而省略摘要依赖。新增知识源或调整摘要覆盖范围时，应逐份核对八个投影的 declared source，并用框架回归测试锁定穿透关系。

### 当前职责索引

```bash
.venv/bin/python devtools/docctl.py render-guidance --write
.venv/bin/python devtools/docctl.py render-guidance --check
```

`docs/GUIDANCE_INDEX.md` 是有效 policy 的兼容查询投影，不是手写总索引。新增、移动、退出或重新分类承担当前职责的文档时，先修改最近的 `DOC_POLICY.json`，再重建本页。`docs/` 与 `docs/项目说明/` 的广域默认保持 `unmanaged`；深度一 Markdown 必须由精确规则声明 lifecycle 和唯一职责。

不要为了让 doctor 通过而把整个目录重新设成 `living`。正确动作是把真实 current surface 列为 living/normative/generated，把旧计划和快照列为 historical，把没有职责的新增文件留在 fail-closed 状态直到完成分类。

### 当前文档分区与局部前门

current 文档的稳定问题域由以下真源声明：

```text
data/repository_governance/document_system/sections.json
```

local `DOC_POLICY.json` 通过 `section_refs` 声明成员归属。新增 current Markdown 时，必须复用已有 section，或在确实出现新的稳定问题域时原子新增 section record、局部入口、policy、ADR/指南与测试。不要把每个目录或每个文件都变成 section。

修改分区时按以下顺序进行：

1. 确认 section 的唯一职责和 entry path；入口应靠近材料并保持在声明的注意力预算内。
2. 修改 `sections.json` 与受影响的 local policy；入口自己的有效 contract 必须引用该 section ID。
3. 在入口正文中链接全部 `required_targets`。required link 表达最小可发现性，不复制目标的易变内容。
4. 运行：

```bash
.venv/bin/python devtools/docctl.py render-sections --write
.venv/bin/python devtools/docctl.py render-guidance --write
.venv/bin/python devtools/docctl.py doctor
```

退出旧局部索引时，不直接删除路径或把旧正文改写成今天的目录。先将原始正文复制到具名 historical payload，核对字节 hash；再把旧路径登记为 `generated_redirect`，建立 generator-only policy，并从 guarded/current 列表移除。若旧文件其实只覆盖一个特定阶段，应把载荷命名为 transcript 或阶段索引，避免继续使用含混的 `INDEX` 标题。

`SECTION_INDEX.md` 是 section registry 与有效 policy 的生成投影，`GUIDANCE_INDEX.md` 是全量 current responsibility 投影。前者按问题域路由，后者按职责类型枚举；不得手工合并成第二套总索引。

### 固定前门与兼容跳转

固定入口、attention budget、required link 和历史兼容跳转由以下真源声明：

```text
data/repository_governance/document_system/entrypoints.json
```

修改 canonical front door 时，必须同时检查对应 `DOC_POLICY.json`、入口正文、`ARCHITECTURE.md` 和定点测试。根 `CLAUDE.md` 只保留每次任务必需的自举边界；低频操作知识进入 `docs/AGENT_OPERATIONS.md`，不能通过放宽预算把长手册重新塞回默认上下文。

registry 中的三类记录分工如下：

- `surfaces`：唯一现行前门、authority 或生成入口，并可为人工入口设置注意力预算；
- `guarded_documents`：仍保留原职责、但必须链接现行真源且不得复制易变状态的稳定文档；
- `generated_redirects`：退出当前职责的旧路径，由 generator-only 页面维持兼容。

同一路径和稳定 ID 只能属于其中一类。把文档从 guarded 转为 redirect，或从普通文档晋升为 canonical surface，都属于框架语义变化，必须同步 policy、ADR/指南和回归测试。

旧 `FILE_STATUS`、document tree、subject tree、current-status、dashboard、glossary、roadmap 和 open-question 路径都是 generator-only compatibility redirect。修改它们的目标或边界时，改 registry 后运行：

```bash
.venv/bin/python devtools/docctl.py render-entrypoints --write
.venv/bin/python devtools/docctl.py render-entrypoints --check
.venv/bin/python devtools/docctl.py render-sections --write
.venv/bin/python devtools/docctl.py render-sections --check
.venv/bin/python devtools/docctl.py render-convergence --write
.venv/bin/python devtools/docctl.py render-convergence --check
.venv/bin/python devtools/docctl.py render-guidance --write
.venv/bin/python devtools/docctl.py doctor
```

不要直接编辑生成跳转页。新增 redirect 时还要给该路径建立精确 policy，声明 `generator_action=docsystem.render_entrypoints` 和 registry source；退出旧路径时保留 archive 坐标或显式记录为何无需历史 payload。

### Tracked artifact compatibility projection

`data/artifact_boundaries.json` is a generated schema-v1 surface for the frozen certified checker.
Its semantic inputs are `data/knowledge/dossiers.json` plus
`data/repository_governance/artifact_evidence_inputs.json`; direct root files and runtime prefixes
belong in the latter, while dossier roots never receive a second manual registry.

```bash
.venv/bin/python devtools/artifact_evidence.py render --write
.venv/bin/python devtools/artifact_evidence.py check
.venv/bin/python scripts/check_artifact_boundaries.py
.venv/bin/python devtools/check_repository_code_assets.py check
```

The generator may emit compatibility-only quote-prefixed records for the frozen line-oriented Git
consumer. Do not interpret those strings as semantic repository roots. Do not hand-edit the output
or patch the certified checker to compensate for stale projection data; change the declared inputs,
regenerate, and let the frozen consumer prove backward compatibility. A checker change instead
requires the owner-authorized certified-source reset and replay process.

### legacy doc_classes

```bash
.venv/bin/python devtools/docctl.py render-legacy --write
.venv/bin/python devtools/docs_reference_scan.py validate-registry
```

`data/repository_governance/doc_classes.json` 是兼容输出。语义源是 local policy 中的 `legacy_projection` 片段和 `legacy_doc_scan_base.json`。

## 10. 变更、移动和删除

移动文件前，对旧路径和新路径分别运行 context。移动可能同时改变：

- document class；
- mutation；
- authority role；
- dossier membership；
- legacy scan coverage；
- 相关 claim 的 evidence path。

`docctl check` 会关闭 Git rename detection，把移动按“旧路径删除 + 新路径创建”同时检查，避免只看新路径而绕过旧目录的 immutable 或 owner-only 边界。

删除 historical evidence、owner authority、framework core 或 generated source 默认 fail closed。通常正确动作是保留旧材料，新增 successor、supersedes 或 redirect。

## 11. 定期审计和事件写入的分工

事件写入由 `docctl intake --changed` 解释、由 `docctl check --changed` 强制，负责：

- 新 Markdown 在同一事务中获得有效 policy；承担 current 职责时同时得到显式 section；
- 新 dossier 以 active workflow 登记，关闭时写 current review 与 typed outcome；
- 新结论获得稳定 claim/decision ID，既有 ID 不原地改写语义身份；
- owner-only authority 变化由 intake 寻找同一事务新增的 non-authorizing decision companion；当前缺失 companion 为 default-off warning，只有 registry 将 `companion_check.blocking` 翻为 `true` 后才成为阻断；
- 临时文档拥有期限和退出动作，local-optional evidence 拥有 manifest 摘要与恢复说明；
- 当前状态变化立即重建投影。

周期审计负责：

- 从 `BACKFILL_LEDGER` 的 triage 组中安排语义回填，并在晋升 review 时原子移出 triage；
- 查已审 dossier 中漏掉的 claim；
- 查重复 claim、topic 覆盖空洞和 terminology alias 分裂；
- 查过期 living 文档；
- 查未关闭的临时材料；
- 查框架说明和工具是否漂移。

周期审计发现的问题仍通过同一写入管道修复，不建立第二套永久 dashboard。机器配置和生成队列分别位于：

```text
data/repository_governance/document_system/maintenance_audit.json
docs/MAINTENANCE_QUEUE.md
```

标准节奏：

```bash
# 每周或每累计一批文档相关提交：机械错误阻断，语义队列保持可见
.venv/bin/python devtools/docctl.py audit --profile weekly

# 深度语义维护：warning 与 error 都阻断
.venv/bin/python devtools/docctl.py audit --profile deep

# phase close：加入完整阶段边界清单；需要可重复收据时显式固定日期
.venv/bin/python devtools/docctl.py audit --profile phase_close --as-of YYYY-MM-DD

# 接受 finding 并修复原真源后，重建确定性投影
.venv/bin/python devtools/docctl.py render-maintenance --write
```

维护回归的默认审计日必须精确等于全部 active dossier 中最新的 `opened_at` / `date`，并与 `data/knowledge/dossiers.json::ledger_reviewed_at` 相等。新增 active dossier 使该日期前移时，必须在同一事务把 `devtools/tests/test_document_maintenance_audit.py` 的回归时钟与 `ledger_reviewed_at` 一起滚动到最新登记日；`src/tests/test_document_system.py` 同时验证这两项精确相等，并在失败诊断中具名显示回归日期与最新登记日，既阻断过早时钟，也不允许用任意未来日期掩盖后续登记漂移。`devtools/tests/test_document_maintenance_audit.py` 另以具名 active dossier 验证早于其登记日的快照会报告陈旧。这个日期只是测试视界，不是 authority：不得借滚动测试时钟改写 `maintenance_audit.json::snapshot_as_of`，也不得倒签 dossier 来绕过 future-record 红测。

不要通过编辑 `MAINTENANCE_QUEUE.md` 或新增“已关闭 finding”账本消除待办。Git 最近触达日期只提示“该复核了”，不能替代 semantic review。修改 check、profile、阈值或严重度语义属于 framework-core 变化，必须同步 `DOC-INV-019`、[`DOC-ADR-015`](ADR/015-periodic-semantic-maintenance-audit.md)、runner、投影和红测。

## 12. 验收命令

写事务与验收事务必须分开。先显式重建受影响投影：

```bash
.venv/bin/python devtools/docctl.py render-legacy --write
.venv/bin/python devtools/docctl.py render-guidance --write
.venv/bin/python devtools/docctl.py render-entrypoints --write
.venv/bin/python devtools/docctl.py render-sections --write
.venv/bin/python devtools/docctl.py render-convergence --write
```

确认 diff 后，统一运行 intake、完整 diff 检查和 manifest-owned 的只读门：

```bash
.venv/bin/python devtools/docctl.py intake --changed
.venv/bin/python devtools/docctl.py check --changed
.venv/bin/python devtools/docctl.py gate --profile changed
```

phase boundary 或拥有完整 Git object graph 的正式审计改用：

```bash
.venv/bin/python devtools/docctl.py gate --profile full
```

`changed`、`full` 与 `weekly` 只验证当前工作树可证明的文档、知识、artifact 和 current code-assets 表面；依赖冻结 Git object 的历史 replay 单独位于手工 `historical_replay` profile。不能用 current profile 的 PASS 替代完整历史 replay，也不能让缺失外部对象的 replay 把唯一 schedule 永久染红。对已经提交且工作树干净的分支，应传入 `--base <merge-base>`，否则 diff-aware lane 只能看到 index/worktree 变化；PR 与 push workflow 会自动提供 base。框架检查通过只说明文档治理结构一致，不构成数学证明、owner 关门或 production certification。

## 12.1 维护治理门

治理门坐标固定为：

```text
data/repository_governance/document_system/governance_gate.json
data/repository_governance/document_system/governance_gate.schema.json
devtools/document_governance_gate.py
.github/workflows/document-governance.yml
```

新增或修改 lane 时：

1. 命令必须以 `{python}` 开头并使用 argv，不注册 shell 片段、`-c` 内嵌脚本或 `--write`、`--fix`、`--apply` 一类写模式。
2. 每条 lane 声明 timeout、required paths、base 参数方式和只读隔离协议。
3. 把 lane 放入至少一个 profile，并明确它属于 current 验收还是需要完整历史对象的 replay。
4. 临时文件、pycache、pytest basetemp、ruff 与 mypy cache 必须使用 runner 分配的仓外 `{temp}`，不得依赖工作树内事后清理；lane 的 `environment` 也不得覆盖 runner-owned 的 PATH、HOME、Python、Git、temp 或 cache 坐标。
5. pull request、push 和周期 CI 只调用共享 runner；workflow 不复制 lane 命令。
6. 同步更新 `DOC-INV-017`、`DOC-ADR-013` 所要求的指南、doctor 和 `devtools/tests/test_document_governance_gate.py`。
7. 默认并发上限保持为 4；确需调整时必须给出资源依据和对抗回归。单条 landing 回归 lane 的 timeout 是 300 秒，不得以缩短预算掩盖低速机器上的完整事务。
8. 新增或实质修改 `src/tests/test_document_system.py`、`src/tests/test_knowledge_docs.py` 或集中 slow registry 后，串行运行 manifest `test_timing_receipt.command`，按 call phase 的 8 秒阈值更新输入摘要、最大节点和 slow registry 处置。不得用整文件总耗时代替单项 call-time。
9. 先单独运行目标 lane，再运行 `changed` profile，并确认 gate 的前后 Git-visible fingerprint 相同。

治理门可以并行运行 lane，但不能自动生成、格式化或修复源树。需要写入的 render 操作必须在 gate 之前作为显式事务完成。并发与慢测实测边界由 `DOC-ADR-019` 固定。

## 12.2 Tracked artifact evidence 兼容投影

tracked `.artifacts/**` 的语义根来自 dossier ledger，直接根文件和 runtime-only 前缀来自 `data/repository_governance/artifact_evidence_inputs.json`；`data/artifact_boundaries.json` 只是供冻结 schema-v1 checker 使用的生成投影。direct-root 回归必须直接比较解析后的 `workspace_root_files` 与 semantic input 的 `workspace_untracked.root_files` 列表，不维护会随登记自然漂移的散落计数字面量。相关 dossier 或输入变化后，必须原子执行：

```bash
.venv/bin/python devtools/artifact_evidence.py render --write
.venv/bin/python scripts/check_artifact_boundaries.py
.venv/bin/python devtools/artifact_evidence.py check
.venv/bin/python devtools/check_repository_code_assets.py check
```

不要通过修改冻结 checker、添加 Git ignore、手写投影前缀，或把 commit inventory 改成 worktree 语义来消除失败。供应树缺少历史 Git object 时，历史 baseline replay 保持 fail closed，并在交付说明中记录边界。

## 13. 失效恢复

如果 manifest 或 resolver 无法运行，读取 `.docsystem/RECOVERY.md`。恢复通路是固定自举的一部分，不能依赖已经损坏的生成页。

相关设计决定：`DOC-ADR-001`、`DOC-ADR-002`、`DOC-ADR-003`、`DOC-ADR-004`、`DOC-ADR-005`、`DOC-ADR-006`、`DOC-ADR-007`、`DOC-ADR-008`、`DOC-ADR-009`、`DOC-ADR-010`、`DOC-ADR-011`、`DOC-ADR-012`、`DOC-ADR-013`、`DOC-ADR-014`、`DOC-ADR-015`、`DOC-ADR-016`、`DOC-ADR-017`、`DOC-ADR-018`、`DOC-ADR-019`、`DOC-ADR-020`。

## Phase 3 收束规则

`DOC-ADR-012` 固定了四项机器验收：section 内局部可达、可变 current purpose 唯一、手写 current 文档不复制登记的易变状态，以及 current 正文不链接生成式兼容跳转。

新增 current Markdown 时，除了 policy 与 `section_refs`，还必须从该 section 的入口或已可达成员建立真实 Markdown 链接。修改 `volatile_facts`、common forbidden patterns 或职责唯一性算法属于框架语义变化，必须原子更新 invariant、ADR、架构、迁移和定点测试。

退出 current 职责的长文先做字节保真快照，再将 successor 改写为稳定合同。旧 URL 需要保留时登记 generator-only redirect；current 导航必须直接链接 successor，不能经 redirect 绕行。

## Phase 4 治理门规则

`DOC-ADR-013` 固定了统一只读验收面。generator 负责显式写入，gate 只对既有 Git-visible 输入做验收。任何 checker 若需要改写文件，必须拆成独立 render 与 check；CI 只能选择 registry profile，不能维护第二份 lane 清单。current-only code-assets 检查与历史 replay 必须保留不同 action、不同 lane 和不同结果声明。`DOC-ADR-019` 进一步固定最大 4 lane 并发、landing lane 的 300 秒预算，以及绑定测试输入摘要的串行 call-phase 慢测收据。


## Phase 4 事件 intake 规则

`DOC-ADR-014` 固定事件驱动写入面。`intake.json` 只声明变化类型和 companion 义务，不复制 claim、decision 或 dossier 正文。修改 intake 协议、稳定语义字段、owner path rule、closure outcome、ephemeral registry 或 portability 规则时，必须同步 manifest/schema、`DOC-INV-018`、架构与维护指南、定点 intake 红测和治理门 lane。`docctl check` 必须复用 `intake_changed`，不得维护平行判断。
## Phase 4 周期审计规则

`DOC-ADR-015` 固定周期盘库边界。审计配置只声明 profile、check、阈值和 action，不复制知识正文；runner 只读现有真源，生成页由固定快照重建。修改维护审计时必须同步 manifest/schema、`DOC-INV-019`、架构与维护指南、`devtools/tests/test_document_maintenance_audit.py`、治理门 lane 和所有受影响投影。审计 finding 的处理结果必须体现在原 ledger 或 policy 中，不能在平行维护账本里单独关闭。

## 真实仓库存在方式

新增输入时必须声明 `git_tracked`、`workspace_untracked` 或 `external_root`。可选 `CLAUDE.md` / `AGENTS.md` overlay 不得成为 tracked 投影硬输入；artifact 当前存在也不能替代 `git ls-files --cached`。这套边界由 `DOC-INV-020` 与 `DOC-ADR-016` 管理。
## Phase 4 知识 authority 接口规则

`DOC-ADR-017` 固定 knowledge ledger 的权威接口：

1. 修改 claim 时必须同时维护 `representation_class`、`authority_basis`、`decision_ids` 与每份 evidence 的 `storage`。`updated_at` 只在语义、状态、scope 或 authority 变化时更新，不因单纯增加一份同义 evidence 自动刷新。
2. `authority=machine` 必须选择已有具名 verifier，并把其全部 tracked source 列入 evidence；新增 verifier 属于知识治理合同变化，需有定点红测。不能用完整运行收据替代机械核验。
3. `decisions.jsonl` 只能追加 non-authorizing 查询记录。每条记录必须指向外部 owner source；更正使用新 ID / supersession，不把 prose 登记册改造成第二个 owner 真源。`ruling_event_id` 在正式 OWNER_RULING_EVENT 档案面落地前保持 `null`。
4. workspace-untracked evidence 必须 `optional=true`，external evidence 还必须有恢复说明；二者不得进入 machine authority basis。不要通过 `git add -A` 把本机工件转正。
5. claim 的 statement、scope、premises、authority effect 或稳定结论实质变化时创建 successor，并保留旧条目及 validity/supersession 方向。
6. 修改 schema、表示映射、authority 准入或 decision pointer 语义后，依次运行 knowledge generator、knowledge checker、`docctl doctor`、知识回归和 changed governance profile。
7. 知识层 inventory 数量变化时只更新 `data/knowledge/knowledge_census.json` 这一份刻意维护的 acceptance fixture；测试读取 fixture 并验证关系，不在代码中新增散落数字。
8. schema 新增稳定语义字段时，在 `intake.json` 为该 ledger 登记精确版本迁移和允许新增的字段；迁移只允许 absent→present，不得借机改写既有 semantic fields，并必须有正反两面的 intake 回归。


## 14. 维护真实仓库落地协议

稳定入口与完整指南：

```bash
.venv/bin/python devtools/document_patch_landing.py --help
.venv/bin/python devtools/docctl.py landing -- --help
```

架构解释位于 `docs/governance/document-system/REAL_REPOSITORY_LANDING.md`。真实目标尚未安装适配层时，规划必须使用补丁包自带的 runner、protocol、protocol schema 与 ACK schema；供应基线目录是必填输入，不能只依赖 hunk 冲突，因为字节已经漂移的文件仍可能被 Git 认为可直接应用。

落地事务按以下边界维护：

1. `plan` 同时比较补丁目标、供应基线和真实工作区，密封原补丁、协议 bundle、漂移字节、基线路径与由基线加补丁推导出的 package successor；未知 tracked 漂移或 untracked collision 必须阻断。
2. `apply-base` 只应用计划中的基础路径。操作者必须用生成的 NUL pathspec 精确 staging，并在规划 HEAD 之后形成唯一一个直接提交；`confirm-base` 核对提交路径集合和字节。
3. 适配层必须随后以 tracked、committed 形态安装，且三份协议文件必须与计划 bundle 字节一致。只把文件复制进工作树不构成安装。
4. `begin-migration` 在仓内写入前完成全部预检，并把每份漂移源按 `landing/<date>/<landing-id>/...` 保存为字节保真归档；同一天多次落地不得互相覆盖。
5. ACK 中的 `required_strings` 必须实际来自对应归档源。对 JSONL 目标，record ID、归档路径、源摘要和承重字符串必须共存于同一条指定记录，不能靠文件中分散字段拼装通过。
6. append-only 目标按迁移前字节前缀验证。package successor 只能使用计划中密封的字节，不能接受操作者另行指定的外部 successor 目录。
7. `finalize-migration` 必须先验证所有 successor，允许在中断后识别“旧字节”或“精确 successor 字节”并继续；出现第三种字节形态时阻断。
8. workspace overlay 只人工调和，不进入 tracked 生成页，也不得被精确 staging 列表带入 Git。

落地协议属于 framework core。修改 `landing.json`、两份 schema、runner 或 landing guide 时，必须在同一变更中更新：

1. `DOC-INV-022` 的当前解释；核心决定变化时新增 successor ADR，不改写 accepted ADR；
2. `test_document_patch_landing.py` 的完整成功事务和对抗红测；
3. manifest 的 landing 坐标、governance gate 的 landing regression lane，以及该 lane 的隔离环境；
4. `docctl doctor` 对 protocol/schema/runner/guide、target format 和 obligation coverage 的交叉核验；
5. `.docsystem/RECOVERY.md` 的仓外 bootstrap 与 fail-closed 恢复路径；
6. 所有受影响的生成投影和引用注册表。

新增普通冲突路径不能直接塞入固定排除列表。先判断它是否属于已有迁移类型；若不是，新增 typed migration kind、obligation schema 和对抗测试。任何协议扩展都必须证明非冲突字节漂移、未知 untracked collision、计划或 snapshot 篡改、错误基础提交、append-only 改写、ACK 伪造、JSONL 记录错位、提前覆盖 successor 和未提交协议安装仍然 fail closed。

落地 runner 不得获得 staging、commit、reset、clean 或 amend 能力。需要改变这条边界时，必须由新的 owner 决定和框架 ADR 显式裁定，不能只改实现。

## 15. 阶段性重构收口后的常态维护

常态运行合同见 [`STEADY_STATE.md`](STEADY_STATE.md)。普通内容、知识和局部 policy 变化不再自然延伸新的 Phase 或 Batch，而是回到 `context → intake → check → changed gate`；周期遗漏由 weekly/deep/phase-close 审计发现，修复仍写回原真源。

只有核心 invariant、schema、resolver、authority 准入、治理 runner、真实仓库 landing 或 owner 权威档案面发生语义变化时，才以新的独立框架迁移重新开启。该迁移必须同时包含新 ADR、系统版本、兼容或数据迁移、定点红测和完整治理收据。

外部 Git object graph、档案根或 owner source 缺席时继续 fail closed。不得为了宣布“完成”而跳过 lane、改写冻结摘要、降低 authority、把 workspace evidence 批量加入 Git，或新增一份手写完成状态页。该边界由 `DOC-INV-023` 与 [`DOC-ADR-020`](ADR/020-steady-state-transition-and-maintenance-handoff.md) 固定。
