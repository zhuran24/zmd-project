# DOC-ADR-011：显式文档分区与旧局部索引退役

状态：Accepted
日期：2026-08-12
系统版本：1.8.0

## 背景

`GUIDANCE_INDEX.md` 已经能够枚举所有承担当前职责的文档，但全量职责表回答的是“有哪些 current surface”，不是“某类问题应该从哪里进入”。仓库仍依赖若干分散的手写地图，例如旧 research `INDEX.md`、`docs/specs_index.md` 和 subject tree 文档。它们的标题与目录位置容易让读者误以为自己看到了整个分区，实际却只覆盖一个历史阶段或一小组文件。

仅继续增加链接不能解决这个问题。局部入口若没有稳定身份、唯一职责和成员边界，就会在目录演化后再次变成隐藏地图。反过来，把每个 Markdown 都塞进一个手写总索引，也会建立新的同步真源并扩大 agent 的默认注意力负担。

## 决定

1. 在 `.docsystem/manifest.json` 中登记机器可读的 section registry 与生成投影。`data/repository_governance/document_system/sections.json` 为每个当前问题域声明稳定 section ID、唯一入口、入口类型、必须链接的目标、相关分区和可选注意力预算。
2. `DOC_POLICY.json` 契约增加可继承的 `section_refs`。承担 authority、规范、当前说明、生成查询、结构化知识、治理或 framework-core 职责的 Markdown 必须至少属于一个显式分区；一个文档可以跨分区，但每个分区只有一个登记入口。
3. `docctl context` 只向 agent 投影目标文件实际命中的 section 与局部入口。完整成员表由 `docctl render-sections` 生成到 `docs/SECTION_INDEX.md`，不默认塞入每次操作上下文。
4. `docctl doctor` 检查 section ID、入口唯一性、入口 policy、required link、注意力预算、当前文档覆盖、成员非空和生成页新鲜度。section 不授予 authority，入口也不能把 historical evidence 提升为 current guidance。
5. 旧的 research、spec 和 subject 地图退出当前职责：原始载荷按字节保存在明确命名的历史文件中，旧路径改为 generator-only compatibility redirect，并指向新的局部入口或具名 transcript。
6. 规范、运行、研究、历史、主题、形式化验证、兼容层和仓库治理各自获得靠近材料的有界前门。全局 `GUIDANCE_INDEX` 继续承担完整职责投影，`SECTION_INDEX` 只承担按问题域路由，二者不得合并成新的巨型总览。

## 结果

- agent 可以由目标路径获得少量、可类推的局部坐标，而不必预读整棵文档树。
- 当前但零入链的规范、runbook 或框架文档会被 checker 阻断。
- 旧索引路径继续可用，却不能重新承载另一套手写成员表。
- 移动文档或改变职责时，必须同步 local policy、section registry、生成投影和回归测试。
- 历史 transcript、冻结 delivery 和旧地图保留原貌；它们的可发现性由 history front door 提供，而不是通过追随现态改写正文。

## 不做什么

本决定不让目录名自动成为 section，不要求逐文件 front matter，也不把 claim、decision、gate 或当前数值复制到 section registry。分区只保存操作域、入口和导航约束；项目语义仍由 authority 文件、结构化知识账本和原始证据承担。
