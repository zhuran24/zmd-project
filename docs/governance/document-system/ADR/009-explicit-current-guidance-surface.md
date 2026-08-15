# DOC-ADR-009：显式当前职责表面与生成式导航

状态：Accepted

日期：2026-08-12
系统版本：1.6.0

## 背景

Phase 1 与 Phase 2 已经建立唯一现态、结构化 claim、dossier、topic 和术语投影，但旧文档的生命周期仍有一处结构性缺口：`docs/` 与 `docs/项目说明/` 使用宽泛的 `living` 默认值。只要文件落在这些目录，它就会被当成需要持续维护的当前说明，即使它实际是旧阶段计划、一次性排期、历史分析或冻结交付稿。

这种默认值使“当前维护面”无法被精确枚举。它也把生命周期判断重新交给文件名和人的记忆，与自描述文档系统的目标相冲突。

## 决定

1. `docs/` 与 `docs/项目说明/` 的目录默认值改为 `unmanaged`。所有深度一 Markdown 必须由显式规则分类。
2. 当前职责不再由手写总索引维护，而由 `docctl render-guidance` 从每个路径的有效 policy 生成 `docs/GUIDANCE_INDEX.md`。
3. 生成索引只列承担当前职责的类型：locked authority、generated projection、normative、living、structured knowledge、governance control 与 framework core。historical evidence 不进入当前职责面。
4. 新增、移除或重新分类当前文档时，必须同时修改最近 policy 并重建职责索引。这样路径变化和职责变化在同一事务中发生。
5. 历史原文保留在 immutable snapshot 或原有 historical 文档中；兼容路径只提供短跳转，不再重复当前状态、开放问题或术语正文。

## 原因

显式分类把“这份文件现在还负责什么”变成机器可检的契约。生成式职责索引则让全局导航保持完整，又不建立第二套人工真源。

将宽泛默认改为 fail closed 会增加一次性的分类工作，但以后新增文件若没有明确职责会立即暴露，而不是静默长成新的 living 文档。

## 后果

- `docs/` 和 `docs/项目说明/` 的每个深度一 Markdown 都必须有显式 policy 命中。
- `docs/GUIDANCE_INDEX.md` 为 generator-only，直接编辑会被阻断。
- 历史文档可以继续被 claim evidence、旧行号引用或 dossier 使用，但不会出现在当前职责索引中。
- 当前职责索引只表示维护职责与导航，不提升任何文档的 authority。
- 改变显式分类、生成算法或纳入类型集合属于框架变化，必须同步 schema、指南、测试和 ADR。

## 被拒绝的方案

### 继续使用目录级 living 默认

拒绝。它省掉局部规则，却无法区分当前手册与历史计划，正是 living 面持续膨胀的根因。

### 手工维护一份“当前文档列表”

拒绝。它会成为另一个需要同步的索引，并重演旧 `DOC_TREE_COMPLETENESS` 的漂移。

### 给每个 Markdown 增加 front matter

拒绝。大多数文件已能由目录 policy 和少量精确规则表达。逐文件 front matter 会制造大量重复元数据和迁移噪声。
