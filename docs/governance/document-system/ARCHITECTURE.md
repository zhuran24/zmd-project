# ZMD 自描述文档系统架构

状态：CURRENT
系统版本：`2.6.0`
机器入口：`.docsystem/manifest.json`

## 1. 解决什么问题
文档层有两种不同的维护对象。

第一种是项目内容，例如当前状态、研究结论、规范、运行手册和历史证据。第二种是文档框架本身，例如文档类型、继承规则、生成器、检查器和 agent 的操作协议。

只给 agent 一组具体命令，可以让它继续维护第一种对象，却无法解释这些命令为什么存在，也无法安全修改产生命令的框架。反过来，每次操作都加载整套架构，会把任务上下文挤得没有呼吸空间。

本系统采用四层分工：

| 层 | 保存什么 | 普通操作是否默认加载 |
|---|---|---|
| 自举层 | manifest、恢复路径、框架核心边界 | 只加载坐标 |
| 原则层 | 少量稳定不变量及其短原因 | 只加载当前规则引用的原则 |
| 策略层 | 目录默认规则和局部例外 | 由目标路径自动解析 |
| 知识与证据层 | claim、decision、dossier、semantic review、inventory triage、topic、term、validity event、原始报告 | 只加载稳定摘要，需要时再下钻 |

完整知识常驻仓库，最小原则常驻操作卡，具体规则按路径加载，完整框架只在触及 framework core 时加载。

## 2. 固定自举入口
所有工具只硬编码一个路径：

```text
.docsystem/manifest.json
```

manifest 给出：

- 当前系统版本；
- 根 policy 和局部 policy 文件名；
- 架构、维护、恢复和 ADR 坐标；
- invariant 与 schema 坐标；
- knowledge ledger 坐标；
- 可执行 action ID 与命令；
- framework core 路径边界；
- canonical front door、guarded stable document、agent 自举面、注意力预算与兼容跳转注册表；
- current document section registry、分区投影和局部入口约束；
- current 图收束验收投影及其 fail-closed 检查；
- 非变异治理门的 registry、schema、runner、CI 触发面与 profile；
- 事件驱动 intake 的 registry、schema、稳定身份字段、dossier 生命周期和临时文档登记坐标；
- 只读周期审计的 registry、schema、profile、生成队列与修复回路坐标；
- 真实仓库非破坏性落地协议、ACK schema、runner 与操作指南坐标；
- 可选 workspace overlay 及其 tracked canonical target；
- evidence 的 `git_tracked`、`workspace_untracked` 与 `external_root` 存在方式；
- legacy `doc_classes.json` 投影的源和输出；
- 受文档 policy 管理的 Markdown include globs，以及明确不属于文档系统的 exclude globs。

这是一层有意保留的最小公理。继续为 manifest 再设计一个 manifest，只会制造无限向上的楼梯。

### 2.1 真实仓库拓扑与可选 overlay
文档系统把“当前看得见”和“已经进入 Git 历史”视为两件不同的事。`DOC-INV-020` 与 `DOC-ADR-016` 固定三种存在方式：

```text
git_tracked         版本库耐久输入，可进入 tracked 生成投影
workspace_untracked 共享工作区临时输入，可能被并发会话清理
external_root        仓外恢复根，只能通过显式路径、manifest 与摘要引用
```

根 `CLAUDE.md` 与 `AGENTS.md` 在真实仓库中是可选 `workspace_untracked` overlay。它们存在时接受 policy 检查，缺失时不阻断文档系统；tracked 的 `docs/AGENT_OPERATIONS.md` 才是耐久操作指南。任何 tracked 生成页都必须使用 `projection_paths()`，不得把 overlay 当前存在误写成版本库事实。

`.artifacts/**` 同样不能凭目录存在推断为 tracked。artifact evidence registry 分别登记 Git-tracked 输入、workspace evidence 与 external root；frozen `data/artifact_boundaries.json` 只投影 Git-tracked 边界。

## 3. 文档树是一套继承式类型系统
目录中的 `DOC_POLICY.json` 声明该目录的默认契约和少量例外。解析目标文件时，`docctl` 从仓库根向目标父目录逐层合并：

```text
内置 fail-closed 基线
  → 根 DOC_POLICY.json
  → 中间目录 DOC_POLICY.json
  → 最近目录 DOC_POLICY.json
  → dossier lifecycle 动态收紧
  → manifest framework-core 动态收紧
```

policy 文件不授权自身。修改 `docs/research/DOC_POLICY.json` 时，它由祖先 policy 和 manifest 的 framework-core 边界管理，不能通过改写自己的内容先给自己开门。

v1 把已经存在的 policy 路径视为稳定锚点，禁止在同一变更中直接删除或移动。否则 guard 与受保护内容可以一起从当前树中消失，使未改动的后代静默落回更宽松的祖先规则。需要重组时先保留原锚点并完成等价迁移；真正的 policy retirement 要等显式协议落地后再开放。

policy 变化分为三档：新增精确路径规则且不改变既有规则为 `coverage_update`；修改局部文档合同为 `contract_change`；改变 schema、resolver、继承算法、manifest 或核心不变量才是 `framework_semantic_change`。前两档仍由 policy 解析、intake 与 doctor 严格检查，但不能因为“新增一页文档需要登记 policy”就自动升级为 L3 框架迁移。

只有 Git 可见的 policy 才拥有治理效力。被 ignore 的本地 `DOC_POLICY.json` 不参与解析，避免私有工作区文件静默改写仓库规则；新增且尚未提交的 policy 只要没有被 ignore，仍可在同一变更中接受检查。

同一 policy 内，广域规则先于精确规则合并：以 `/` 结尾的 `prefix` 提供目录基线，`glob` 提供形状基线，`paths` 与 `path` 提供显式例外；`paths` 的每个成员都按同等精确路径处理，不能靠塞入一个无关的长路径制造优先级。同一精确度的两个匹配规则若给同一 scalar 不同值，会 fail closed。规则数组顺序不决定胜负。跨目录继承仍受“只能静默收紧”的 mutation 约束。

契约主要回答：

- `document_class`：这是什么；
- `authority_role`：它能说明什么；
- `mutation`：怎样才能改；
- `context_level`：agent 需要加载多少背景；
- `purpose`：这份材料唯一负责什么；
- `volatile_facts`：能否承载会变化的现态；
- `section_refs`：当前文档属于哪些稳定问题域，以及应从哪个局部入口进入；
- `source_paths` 与 `generator_action`：生成页应从哪里穿透更新；
- `invariant_refs`、`adr_refs`、`knowledge_refs`：规则背后的原则、设计决定和项目知识；
- `required_reads` 与 `after_change`：操作前后的最小闭环。

大部分文件不需要自己的 front matter。目录 policy 提供默认值，只有例外才写 rule。

## 3.2 知识表示、authority 与 decision 真源
知识记录还需要把三个彼此正交的问题拆开：

```text
representation_class  → 这条记录在表示系统中的位置
authority              → 这条命题的认识论等级
evidence.storage       → 这份证据的耐久与恢复合同
```

`AUTHORITATIVE_CURRENT` 表示 `claims.jsonl` 中当前承担稳定身份的记录，不等于 `machine`。`machine` 只有在 `authority_basis` 指向当前 Git-tracked 机器真源，且 knowledge checker 实际执行具名 verifier 核对承重字段时成立。历史执行收据、外审 prose 和 workspace artifact 无论多完整，都不能凭材料形态获得 machine 等级。

`decisions.jsonl` 是 `non_authorizing` 的 append-only 查询登记册。每条记录用 `external_decision_id` 和 `authority_source` 指向真正的 owner source，checker 验证路径、JSON pointer 或文本片段与登记字段一致。claim 的 `decision_ids` 只建立可发现性链接；它不把登记册变成第二个 owner authority 面。

稳定 ID 的语义仍不可原地改写。schema 增加必填语义字段时，intake 只接受 registry 中声明的精确版本迁移，并且只放行“字段此前不存在、迁移后新增”的那一组字段；任何同时发生的旧字段变化仍 fail closed。
四种 `representation_class` 与 DOC_POLICY 的 `document_class` 映射由 `current_state.json` 唯一声明并由 checker 精确核对。未来不可变 `OWNER_RULING_EVENT` 档案面落地前，不为 decision register 私自扩出第五类。

## 3.3 真实仓库落地不是普通 patch apply
供应快照与共享工作区可能拥有不同 tracked/untracked 拓扑。累计补丁必须同时执行逐路径 `git apply --check` 与供应基线字节比较：已登记漂移先保存落地时点原字节与 SHA-256，再按 typed ACK 迁移新增语义；未知漂移阻断。基础路径必须形成一个可核验的直接提交，适配协议必须随后以 tracked、committed 形态安装。append-only 目标按字节前缀核验，规范 successor 由规划时的补丁与供应基线机械导出并密封，只在迁移通过后安装；workspace overlay 只人工调和。runner 不提供清理、自动 staging 或提交能力。完整协议见 [真实仓库落地指南](REAL_REPOSITORY_LANDING.md)。

## 4. 操作卡与渐进式加载
标准入口：

```bash
.venv/bin/python devtools/docctl.py context <path> --intent edit
```

默认输出是一张短卡，包含：

- 是否允许当前意图；
- 文件类别、authority、mutation 和用途；
- 若命中固定入口，显示 entrypoint ID、模式与注意力预算；
- 目标所属 section、该 section 的唯一局部入口与一句职责摘要；
- 相关 invariant 的一句原因；
- 真正写入源和 generator；
- 相关 dossier、claim 或 decision 摘要；
- 当前 dossier 的语义审阅、可用性核对或长尾分诊状态；
- 与该 dossier 相关的稳定 topic 坐标；
- 必须读取的指南或 ADR；
- 完成后应运行的命令。

agent 不需要预先背诵所有目录规则。它只需要知道，在操作目标前查询目标路径。

四个上下文等级：

| 等级 | 典型对象 | 默认上下文 |
|---|---|---|
| L0 | 普通 living 文档、稳定导航 | 操作卡和原则短因 |
| L1 | claim、decision、规范、活跃研究包 | L0 加相关知识和 authority 边界 |
| L2 | 局部 `DOC_POLICY.json`、兼容治理控制 | 父子 policy、相关不变量和局部影响 |
| L3 | manifest、schema、invariants、resolver、框架指南 | 完整架构包、维护协议、ADR、迁移和测试要求 |

等级描述注意力预算，不授予 authority。

## 5. mutation 语义
保护强度从低到高为：

```text
direct < governed < append_only < generator_only < owner_only < immutable
```

- `direct`：可在 purpose 和 authority 边界内直接编辑。
- `append_only`：只能追加新的日期条目或显式更正，不能改写旧记录。
- `governed`：可改，但必须读取所列框架材料并原子更新测试和投影。
- `generator_only`：只能改 `source_paths`，再运行 `generator_action`。
- `owner_only`：只有明确 owner 动作可以修改。
- `immutable`：正文保留；更正通过 erratum、successor、superseding claim 或 decision 表达。

子 policy 可以静默提高保护强度。降低保护强度必须在发生放松的同一 overlay 中显式引用一个当前有效、authority effect 为 `scope_boundary`、且 scope 包含 `document-system` 或 `document-policy` 的 owner decision。祖先曾经使用过的 decision 不能被后代暗中复用。

## 6. dossier、回填审阅与知识账本的动态联动
`docs/research/<package>/...` 的目录 policy 只声明一般规则。`docctl` 还会查询 `data/knowledge/dossiers.json`：

- `active` dossier 可以在其研究作用域内修正和追加；
- `historical` 或 `superseded` dossier 自动收紧为 `immutable`；
- claim 和 decision 通过 `dossier_ids` 反向关联到操作卡。

inventory、triage、semantic review 和 promoted knowledge 是四层不同状态：

```text
dossier 已登记
  ≠ 未审材料已完成分诊
  ≠ 已完成声明范围内的语义审阅
  ≠ 已把可复用结论提升为 claim
```

`data/knowledge/backfill_triage.json` 对没有 current review 的历史 dossier 做穷尽且唯一的分流。它保存 disposition、优先级、理由和 reopen trigger，但明确不是 semantic review。一个已关闭或遗留 dossier 不能同时拥有 current review 和 triage，也不能两者都没有；由 intake 新开的 `active` workflow 在 typed closure 前是显式例外，既不算 semantic review，也不进入历史 triage。

`data/knowledge/backfill_reviews.jsonl` 记录某个 dossier 已经审了哪些路径、得到哪些 claim、还剩哪些未决问题，以及何时需要重审。它不复制研究正文，也不把“已审”伪装成“结论成立”。同一 dossier 只能有一条 current review；后续重审新建 review ID，并通过 `supersedes` 保留审阅历史。`availability_and_provenance` review 只核对 local-optional payload 的存在性、路径和来源，不计作 semantic review。

claim 可选的 `reasoning_profile` 给已经通过语义审查的推理成果增加机器可查询的操作分类，例如：

- 条件已经解除、仍是条件式、发生 scope shift、已被反例推翻，还是仅为方法或未决实验；
- 它执行的是预建模排除、候选筛选、约束选择、边界收紧、语义划分，还是反例/发现方法；
- 它与 solver 的关系是 pre-model reduction、candidate filter、model constraint、experimental cut，还是不适用；
- 对“通用传播无法完成分离”的证据是 `none`、`experimental_only` 还是 `formal`。

最后一项故意采用高门槛。某次 cut 零激活、某批实例未分离，最多登记为实验边界；只有命题、作用域和证明均明确时，才能标为 `formal`。

可复用数学 claim 还可以携带 `derivation_profile`。它只回答三件事：该节点是定义、原子引理、复合定理、账本投影、方法、反例还是开放义务；它属于哪些稳定数学推导族；它经过哪些验证方式。真正的推导边由 claim 顶层的 `dependencies` 和 `supersedes` 表达，statement、premises、authority 与 evidence 仍是命题真源。

可复用的选择或分离机制还可以携带 `separation_profile`。它把容易混成一团的能力拆开：候选从哪里来、怎样挑选、怎样验证、覆盖是否完备、在哪一层消费，以及 baseline 比较是无对照、非识别性、受控还是 formal。它不会把 supplied-candidate checker 升级成 autonomous separator，也不会把领域排除自动升级成 generic-propagation impossibility。

历史更正与负结果还可以携带 `validity_profile`。它区分直接反例、语义替代、作用域修正、实现失效、实验失效、归因更正、路线撤回和修复后重验，并记录受影响层、判定依据、复用策略、修复状态与时间作用域。`status=refuted` / `superseded` 以及含 `supersedes` 边的 claim 必须给出该 profile；被标为 `superseded` 的旧节点必须有反向 successor，避免标题宣布“已替代”却没有可追踪的新命题。

四种 profile 不互相替代：

```text
reasoning_profile   → 它怎样改变候选、模型或 solver 工作流
derivation_profile  → 它在数学证明组合中扮演什么角色
separation_profile  → 候选来源、选择、验证、完备性、消费与 baseline
validity_profile    → 它为何失效或换代、哪些层受影响、怎样安全复用
dependencies        → 它直接依赖哪些已登记前件
supersedes          → 它显式取代哪些旧语义节点
```

因此 agent 编辑某份研究报告时，不只看到“这是 historical”，还会看到相关 claim 的稳定 ID、状态和命题摘要，以及 current review 或 inventory triage。topic registry 再把 claim、dossier label、术语和开放问题连接为稳定入口。原始证据仍留在 dossier，操作卡和账本不复制完整证明。

八份知识投影分别回答不同问题：

- `CURRENT.md`：现在能陈述什么；
- `CATALOG.md`：有哪些 claim、decision、dossier 和 review，并展开每条 claim 的完整结构化摘要；
- `REASONING_LEDGER.md`：推理成果怎样分类、数学推导链如何由直接边组合、选择/分离/消费机制如何落位，以及历史 dossier 的语义回填覆盖到哪里；
- `VALIDITY_LEDGER.md`：哪些命题被反驳或替代、为何失效、如何换代、修复是否重验以及旧材料还能怎样安全引用；
- `BACKFILL_LEDGER.md`：哪些 dossier 做过 semantic review、哪些只核对了可用性、哪些仍在 inventory triage；
- `TOPIC_INDEX.md`：按稳定主题连接 claim、dossier label、术语、入口和开放问题；
- `TERMINOLOGY.md`：canonical label、alias、定义、区别和来源；
- `OPEN_QUESTIONS.md`：对全部 `status=open` claim 做去重后的当前开放问题投影。

## 7. 文档治理门与 production preflight
两道门并列且作用域不同：

- document governance gate 检查文档职责、知识投影、policy、引用、artifact evidence、current code-assets 与框架回归；它不授予数学、owner、certification 或 release authority。
- `scripts/preflight_gate.py` 检查 production、certification 与 release 合同；它不能替代文档知识治理。

任一道门阻断，都不能把整体状态陈述为通过。`preflight_gate.py --full` 会运行 `pytest src/tests/`，因此可能间接执行文档系统回归，但这不把两道门合并成一套 authority。

`changed`、`full` 与 `weekly` profile 只运行当前 Git tree 可机械复验的 lane。依赖仓外冻结 Git object 的 `code_assets_history` 只存在于手工 `historical_replay` profile；运行者必须先恢复完整 object graph，不能让唯一的定时任务永久红灯。

Git 非变异收据只覆盖 tracked 状态与 manifest 显式声明的 workspace overlay。任意并发产生的 untracked 工件不在指纹中，避免把别的 agent 写入误归因给 checker。lane scratch 默认位于系统临时目录，也可由 `ZMD_DOCUMENT_GOVERNANCE_SCRATCH_ROOT` 指向仓外可写目录。

## 8. framework core 如何管理自己
framework core 至少包括：

- `.docsystem/**`；
- 所有 `DOC_POLICY.json`；
- `data/repository_governance/document_system/**`；
- `data/knowledge/schemas/**`；
- `docs/governance/document-system/**`；
- `devtools/docctl.py`；
- knowledge projection/checking 工具；
- 定点框架测试；
- 生成的 legacy `doc_classes.json`；
- 前门注册表、section registry、相应 schema 与由它们生成的兼容跳转、分区页和收束验收页；
- 非变异治理门的 registry、schema、runner、CI workflow 与红测；
- intake registry、ephemeral lifecycle registry、写入/关闭命令与相应红测；
- periodic maintenance registry、只读 audit runner、生成队列与相应红测。

这些路径由 manifest 作为不可由局部 policy 放松的最终收紧层。命中它们时，context 自动提升到 L2 或 L3，并加入架构、维护、ADR 和框架测试坐标。

## 8. 当前职责表面、固定前门与生成式导航
### 8.1 当前文档分区
全局职责表可以证明 current surface 已被显式分类，但不能替代靠近材料的局部前门。当前分区的机器真源是 [`sections.json`](../../../data/repository_governance/document_system/sections.json)，由 local `DOC_POLICY.json` 的 `section_refs` 连接成员，再生成 [`SECTION_INDEX.md`](../../SECTION_INDEX.md)：

```text
section registry + effective policy
  → docctl render-sections
  → docs/SECTION_INDEX.md
```

每个 section 具有稳定 ID、唯一入口、入口类型、必须链接的目标、相关分区和可选注意力预算。一个 current 文档可以属于多个 section，但历史证据不会因为被某个入口引用就升级为 current。`docctl doctor` 会阻断未知 section、重复入口、缺失 required link、超预算入口、零成员分区和未归类 current Markdown。

[`GUIDANCE_INDEX.md`](../../GUIDANCE_INDEX.md) 与 `SECTION_INDEX.md` 分工不同：前者是按 document class 展开的全量职责投影，后者是按问题域组织的局部入口与成员表。修改 section、局部入口或成员归属的方法见 [`MAINTAINING.md`](MAINTAINING.md)。

旧 research `INDEX.md`、`docs/specs_index.md` 与 subject tree 文档不再充当含混的 master index。旧路径保持 generator-only 跳转，原始正文进入具名 transcript 或 `docs/history/navigation/` 的 immutable 快照。

### 8.2 当前职责投影与固定前门
知识投影回答“项目知道什么”，policy 投影回答“哪些文档现在仍承担维护职责”。二者不能混成同一张表。

`docs/` 与 `docs/项目说明/` 的宽泛默认均为 `unmanaged`。深度一 Markdown 只有被精确 policy 规则命中，才能成为 current guidance、normative contract、generated projection 或 historical evidence。这样旧阶段计划不会因为仍位于熟悉目录中就静默继承 `living` 身份。

当前职责索引由以下命令生成：

```bash
.venv/bin/python devtools/docctl.py render-guidance --write
```

它把全仓有效 policy 中承担当前职责的路径投影到 `docs/GUIDANCE_INDEX.md`。该页面只负责可发现性，不授予 authority；historical evidence 不进入这张当前表。修改当前文档的分类、职责或路径时，必须先修改最近的 `DOC_POLICY.json`，再重建职责索引并运行 `docctl doctor`。

`GUIDANCE_INDEX.md` 与八份知识投影是两种不同生成物：前者由 policy resolver 生成，后者由 knowledge generator 生成。它们共享 generator-only 纪律，但真源和问题域不同。

入口本身另有一个更窄的结构化层：

```text
data/repository_governance/document_system/entrypoints.json
  → docctl render-entrypoints
  → 旧 FILE_STATUS、subject tree、current-status、glossary 与 dashboard 路径
```

registry 只声明固定入口的角色、必须连接的目标、注意力预算，受防漂移保护的稳定文档，以及兼容跳转的 successor 和维护边界。它不复制当前 gate、hash、上下界或测试数量。根 README、`docs/README.md`、`docs/START_HERE.md`、`docs/项目说明/README.md`、根 `CLAUDE.md` 与 `docs/AGENT_OPERATIONS.md` 仍是人工维护的有界 surface；旧状态和旧地图路径改为 generator-only redirect。

`CLAUDE.md` 只保留每次任务都必须知道的自举、authority 和隔离边界。测试 lane、freeze ritual、求解、发布、Git 与故障处理迁入 `docs/AGENT_OPERATIONS.md`，由任务按需加载。`docctl doctor` 同时检查入口路径唯一、canonical surface 与 guarded document 的 required link、防漂移模式、policy 类型、预算、redirect target 与生成结果新鲜度。

## 9. legacy `doc_classes.json` 的位置
`devtools/docs_reference_scan.py` 仍从固定路径读取：

```text
data/repository_governance/doc_classes.json
```

为了不同时维护两套分类真源，该文件现在是兼容投影：

```text
legacy_doc_scan_base.json
  + 各目录 DOC_POLICY.json 中的 legacy_projection 片段
  → docctl render-legacy
  → doc_classes.json
```

旧扫描器的三类 `locked / historical / living` 只服务其引用完整性语义，不等同于新系统更细的 document class。兼容映射不能授予编辑权限或 owner authority。

## 9.1 current 图收束验收
[`CONVERGENCE_REPORT.md`](../../CONVERGENCE_REPORT.md) 由 `docctl render-convergence` 生成。它把有效 policy、前门注册表、section registry 和仓库内 Markdown 链接编译成一份验收结果：

- 每个非兼容跳转的 current 成员是否能从其 section 入口到达；
- 可变 current 文档的有效职责是否唯一；
- `reference_only` / `forbidden` 文档是否复制登记的易变状态模式；
- current 正文是否仍经生成式兼容跳转下钻。

报告只验证文档职责层，不授予数学、phase、release 或 certification authority。生成报告和 `docctl doctor` 使用同一个审计函数，避免说明页与 checker 各写一套规则。

## 9.2 非变异治理门
治理门同时固定“检查什么”与“绿色结果对应哪棵输入树”。它的机器真源由 manifest 固定：

```text
.docsystem/manifest.json
  → governance_gate.json + governance_gate.schema.json
  → devtools/document_governance_gate.py
  → local / pull request / push / weekly
```

每条 lane 通过 argv 直接启动，不在 CI 中复制 shell 命令清单。runner 为每条 lane 分配独立进程和仓库外临时目录，并把 pycache、pytest basetemp、ruff、mypy 与通用临时坐标导向该目录。默认并发上限为 4，避免多个 Python/pytest lane 在低核或内存受限机器上形成资源风暴。检查前后都计算 `git_declared_state_v2`：HEAD、index entries、tracked worktree 状态，以及 manifest 显式声明的 workspace overlay bytes/mode 必须完全一致。任意其他 untracked 文件不属于 checker 输入，避免把并发 agent 的写入误归因给当前 lane。任何 lane 失败、超时或声明输入指纹变化都会阻断整门。

manifest 内的 `test_timing_receipt` 保存文档系统与知识回归的串行 pytest call-phase 实测依据。收据以 8 秒为集中 slow registry 阈值，并绑定被测文件摘要、测试数量、最大 call 节点和处置结果；`docctl doctor` 在测试字节漂移后要求重新测量。文件总耗时、setup 聚合或并发争用不能替代 call-phase 证据。该合同由 `DOC-ADR-019` 固定。

`changed` profile 用于本地交付、pull request 和 push，只检查当前工作树可验证的职责、知识、引用、artifact boundary、current code-assets、回归、lint 和类型。`full` 与 `weekly` 仍只验证当前树；冻结历史 code-assets replay 位于手工 `historical_replay` profile。缺少外部 Git object 时，历史 profile 必须 fail closed，但不能让唯一的 schedule 永久红灯。

```bash
.venv/bin/python devtools/docctl.py gate --profile changed
.venv/bin/python devtools/docctl.py gate --profile full
```

生成动作仍然是显式写事务，必须在进入治理门之前完成。治理门本身从不以“先自动修复再验收”的方式改写输入树。

## 9.3 事件驱动 intake 与同一知识事务
日常维护的入口不是一份额外手写清单，而是 manifest 指向的 [`intake.json`](../../../data/repository_governance/document_system/intake.json) 与相应 schema。它不复制 claim、decision 或 dossier 的内容，只声明 Git-visible 变化必须伴随哪些结构化动作：

```text
目标路径 + Git diff + 有效 policy
  → docctl intake --changed
  → 文档创建、生成页穿透、dossier 登记/关闭、authority companion、
     稳定知识身份、临时文档退出、本机证据可恢复性事件
  → docctl check --changed
  → 统一非变异治理门
```

普通 agent 仍先运行 `docctl context`。完成写入后，`docctl intake --changed` 只投影当前 diff 触发的事件、阻断原因和后续 action，不把完整框架塞入注意力。`docctl check --changed` 复用同一事件解析结果，因此 intake 与最终 diff 门不会各维护一套规则。

新 tracked research dossier 通过 `docctl new research-dossier` 原子创建入口文件并写入中央 `dossiers.json`，以 `active` workflow 开始。关闭前先建立 current semantic review 和必要 claim/decision，再通过 `docctl close-dossier` 写 typed closure。中央 dossier ledger 仍是唯一真源，不在研究目录下增加第二份可独立修改的 dossier 状态。

临时文档只允许位于显式 `ephemeral` policy 下，并登记在 [`ephemeral_documents.json`](../../../data/repository_governance/document_system/ephemeral_documents.json)。创建时必须声明到期日、退出动作和理由；archive/promote 还要预先声明 durable successor。退出由 `docctl exit-ephemeral` 原子移动或删除正文并清除 active registry 记录。新 local-optional evidence 则由 `docctl register-local-evidence` 记录 manifest、SHA-256 和稳定恢复说明。

owner-only authority 路径改变时，intake 会寻找同一事务新增、以 `authority_change` evidence 精确引用改变路径的 non-authorizing decision companion。当前 `companion_check.blocking=false`，缺少 companion 只产生 warning，不授予也不撤销 owner authority；未来 `OWNER_RULING_EVENT` 档案面成熟后，只需翻转 registry 开关即可提升为阻断。已有 claim、decision 和 dossier ID 不能被删除或原地改写语义身份；含义变化通过新 ID 与显式 supersession 表达。

## 9.4 只读周期审计与统一修复回路
事件驱动 intake 处理“变化发生时是否立即入账”，周期审计处理“长期演化后是否仍有遗漏、碰撞或陈旧”。二者只有不同触发入口，没有不同写入真源：

```text
现有 policy / knowledge / lifecycle / Git-visible history
  → docctl audit --profile weekly|deep|phase_close
  → read-only findings
  → 原有 intake、knowledge、policy 或 owner transaction
```

`weekly` 只让机械错误阻断，适合定期 CI；`deep` 把逾期 warning 也视为阻断；`phase_close` 额外列出阶段边界需要人工逐项处置的表面。生成的 [`MAINTENANCE_QUEUE.md`](../../MAINTENANCE_QUEUE.md) 固定使用配置中的快照日期和 `phase_close` profile，因此可重复构建，也不会随系统时钟悄悄改变提交内容。

审计层刻意不保存“finding 已关闭”的独立状态。Git 最近触达日期只是复核触发器，open claim 是研究队列，inventory coverage 也不等于 semantic review。任何被接受的 finding 都必须回写真正负责该语义的 ledger 或 policy，再重新生成队列。这样盘库可以发现漏网之鱼，却不会长成第二个 current dashboard。

阶段性重构收口后的日常入口、框架再开启条件与 fail-closed 交接统一见 [`STEADY_STATE.md`](STEADY_STATE.md)。该页是维护合同，不是新的当前状态副本。

## 10. 核心不变量
以下原则的机器真源是 `data/repository_governance/document_system/invariants.json`。本节提供完整架构坐标，操作卡只摘取相关原则的短原因。

| ID | 原则 | 它保护什么 |
|---|---|---|
| `DOC-INV-001` | 单一可变真源 | 防止多个手写“当前状态”独立漂移 |
| `DOC-INV-002` | 历史证据不追随现态重写 | 保留证据的时间含义和认知演化 |
| `DOC-INV-003` | 语义变化必须显式换代 | 防止稳定 claim/decision ID 暗中换命题 |
| `DOC-INV-004` | 生成内容只能穿透真源更新 | 保证投影可重复构建且不会被手修分叉 |
| `DOC-INV-005` | 局部策略只能静默收紧 | 防止子目录绕过父级保护 |
| `DOC-INV-006` | 框架变化原子完成 | 防止 schema、工具、指南和测试彼此漂移 |
| `DOC-INV-007` | 治理入口必须可发现并可恢复 | 保证框架自身有人能找到、理解和修复 |
| `DOC-INV-008` | 按需揭示而非全量灌输 | 控制 agent 注意力成本，同时保留类推能力 |
| `DOC-INV-009` | 证据、解释与权威分离 | 防止报告、测试或 artifact 越权成为当前裁决 |
| `DOC-INV-010` | 失效与修复必须保留方向性 | 防止局部修复被误写成整条旧证据链复活 |
| `DOC-INV-011` | 语义审阅与目录覆盖分离 | 防止 inventory 或 triage 冒充已经读懂历史材料 |
| `DOC-INV-012` | 当前职责表面必须显式可导航 | 防止宽泛目录默认把历史材料静默提升为 living，或让新的当前入口失去全局坐标 |
| `DOC-INV-013` | 前门职责唯一且入口有界 | 防止多个前门重新复制现态，或把完整操作手册塞回 agent 默认上下文 |
| `DOC-INV-014` | 当前文档必须归属显式分区 | 防止 current 规范或 runbook 零入链，并让旧局部索引退出 master-map 职责 |
| `DOC-INV-015` | 局部入口必须覆盖当前分区成员 | 防止只有 section 标签却无法从局部前门自然到达的 current 孤岛 |
| `DOC-INV-016` | 当前职责必须唯一且不经退役入口传播 | 防止含糊职责、手写易变状态和 retired redirect 重新长回 current 图 |
| `DOC-INV-017` | 治理验收必须只读且对应同一输入树 | 防止 checker 静默改写源树、并行 lane 共享临时状态，或本地与 CI 验收面分叉 |
| `DOC-INV-018` | 文档事件必须在同一知识事务中闭合 | 防止新文档、研究包、authority 与稳定知识身份先落盘、以后再补登记 |
| `DOC-INV-019` | 周期审计只发现欠账，不建立平行真相 | 防止盘库 finding、Git 日期或手工 dashboard 演化成第二套 claim、review 或 authority |
| `DOC-INV-020` | 存在方式必须显式建模 | 防止把 workspace-untracked 或 external evidence 误认为 Git-tracked 权威输入 |
| `DOC-INV-021` | 知识表示位置、认识论权威与 owner 真源必须分离 | 防止历史收据、当前表示或查询登记册越权成为 machine/owner authority |
| `DOC-INV-022` | 真实仓库落地必须保留漂移字节并显式迁移语义 | 防止静态排除清单吞掉快照后 owner 记录、欠账或 workspace 知识，并禁止破坏性整树回滚 |
| `DOC-INV-023` | 收口后维护必须回到统一事务 | 防止用连续批次、手写完成页或放宽门禁代替事件写入、周期审计和显式框架迁移 |
## 11. 设计决定
- `DOC-ADR-001`：采用目录继承 policy 和渐进式上下文，而不是逐文件 front matter 或全量手册注入。
- `DOC-ADR-002`：把框架自身纳入 framework core，并保留最小自举和恢复协议。
- `DOC-ADR-003`：把 legacy `doc_classes.json` 改为分布式声明的生成投影。
- `DOC-ADR-004`：把 dossier inventory、curation review 和 promoted claim 分层，并生成推理总表。
- `DOC-ADR-005`：用可选 derivation profile 与显式依赖边表示数学推导组合，而不把完整证明复制进账本。
- `DOC-ADR-006`：用可选 separation profile 分开候选来源、选择、验证、完备性、消费落点与 baseline 证据。
- `DOC-ADR-007`：用 validity profile 与强制反向 successor 表达反例、语义更正、实现/实验失效、归因修正和重验谱系。
- `DOC-ADR-008`：把 semantic review、availability review 与 exhaustive inventory triage 分开，并生成 topic 与 terminology 投影。
- `DOC-ADR-009`：把当前职责改为精确 policy 分类，并从有效策略生成 `GUIDANCE_INDEX.md`；宽泛目录默认不再静默授予 living 身份。
- `DOC-ADR-010`：用结构化前门注册表、注意力预算和生成式兼容跳转收束仓库入口，并把详细 agent 操作从默认自举面按需下沉。
- `DOC-ADR-011`：用显式 section、唯一局部前门与生成分区表组织 current 文档，并把含混旧索引退役为兼容跳转或具名历史载荷。
- `DOC-ADR-012`：从 current Markdown 链接图计算局部可达性、职责唯一性、易变状态和退役入口隔离，并生成收束验收报告。
- `DOC-ADR-013`：以 manifest-owned 的统一非变异门运行本地与 CI 文档治理，并用 Git 可见状态指纹绑定验收输入。
- [`DOC-ADR-014`](ADR/014-event-driven-document-intake.md)：用事件驱动 intake、类型化写入命令和同一知识事务关闭日常维护灰区。
- [`DOC-ADR-015`](ADR/015-periodic-semantic-maintenance-audit.md)：用只读 profile 和可重建 finding 队列发现长期欠账，并把所有修复送回既有真源事务。
- [`DOC-ADR-016`](ADR/016-real-repository-topology-and-workspace-overlays.md)：把 Git tracked、workspace-untracked 与 external root 分开建模，并让历史 replay 退出唯一的定时 profile。
- [`DOC-ADR-017`](ADR/017-executable-knowledge-authority-and-nonauthorizing-decisions.md)：把 representation、epistemic authority、evidence durability 与 owner source 拆开，并让 machine/decision 指针由 checker 实际核验。
- [`DOC-ADR-018`](ADR/018-nondestructive-real-repository-landing.md)：用动态冲突测量、落地时点原字节归档、typed ACK 和非破坏性 successor 安装管理真实仓库适配。
- [`DOC-ADR-019`](ADR/019-bounded-governance-concurrency-and-slow-test-evidence.md)：给治理并发设置资源上界，并以绑定输入摘要的串行 call-phase 收据决定 slow registry 处置。
- [`DOC-ADR-020`](ADR/020-steady-state-transition-and-maintenance-handoff.md)：用 manifest-owned 常态维护合同收束阶段性重构，并以语义变化而不是连续批次决定是否重新开启框架。

ADR 保存“为什么变成这样”。本文件描述“当前系统是什么”。安全改变它的方法见 [`MAINTAINING.md`](MAINTAINING.md)。manifest 的 `adrs` 映射是 Accepted ADR 的完整注册表。ADR 文件名编号必须与稳定 ID 一致；新增 ADR 若没有同时登记，会被 `docctl doctor` 阻断。

## 12. 不应塞入结构的内容
policy 和 manifest 不复制：

- 长篇数学证明；
- 完整研究报告；
- 当前 gate、U/L、hash、测试数等易变值；
- owner authority 的平行副本；
- 每个文件重复的 YAML front matter；
- 大段操作手册。

结构保存操作语义和稳定坐标，knowledge ledger 保存结论语义，原始文档保存证据。这三层相互链接，但不互相冒充。


当前职责收束验收见 [`docs/CONVERGENCE_REPORT.md`](../../CONVERGENCE_REPORT.md)。
