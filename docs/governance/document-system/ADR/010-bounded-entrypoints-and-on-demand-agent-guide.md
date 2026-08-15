# DOC-ADR-010：有界前门与按需 agent 操作手册

状态：Accepted
日期：2026-08-12

## 背景

知识脊柱已经把当前状态、claim、历史有效性和文档职责变成结构化投影，但仓库仍有另一种漂移风险：入口页会逐渐重新吸收所有内容。根 README、文档 README、项目手册 README、`CLAUDE.md` 和旧状态兼容页若没有显式角色与体积边界，就会再次变成多个“总览”；其中 `CLAUDE.md` 还会把大量只在少数任务中有用的命令、冻结流程和故障经验长期占据 agent 默认上下文。

只靠人工约定“保持简短”不可验证。只把长手册删除，又会让 agent 失去完整操作知识和框架下钻路径。

## 决定

1. 由 `.docsystem/manifest.json` 固定发现机器可读的 `data/repository_governance/document_system/entrypoints.json`。registry 声明稳定 ID、路径、角色、注意力预算、必须可发现的目标，受防漂移保护的稳定文档，以及兼容跳转的 successor 坐标。
2. 仓库前门、agent 自举、详细 agent 操作手册、文档前门、任务路由、唯一当前状态投影、职责索引和项目手册前门均为单例角色。
3. `FILE_STATUS.md`、旧文档树、旧 subject tree、旧 roadmap、旧 open-questions、旧 current-status、旧 glossary 和旧 dashboard 保留为兼容跳转。它们由 registry 生成，不能再直接编辑或承载独立正文。
4. 根 `CLAUDE.md` 只保存每次任务都必须知道的自举、authority、环境和 certified/exploratory 边界。详细命令、测试 lane、freeze ritual、Git 与故障处理迁入 `docs/AGENT_OPERATIONS.md`，按任务加载。
5. `docctl context` 在普通操作卡中显示命中的 entrypoint ID、模式和注意力预算；`docctl doctor` 检查路径唯一性、文件存在、policy 类型、canonical/guarded required link、防漂移模式、redirect target、预算与生成结果新鲜度。
6. `docs/GUIDANCE_INDEX.md` 同时生成固定入口图，使 entrypoint contract 对人类可发现，但该投影不授予新的 authority。

## 结果

- 入口的职责与注意力预算成为机器可检查结构，而不是文案愿望。
- agent 默认上下文保留少量可类推原则；低频但重要的操作知识仍在仓库中完整可达。
- 旧路径继续工作，却不能重新长成独立状态账或 glossary。
- 新增或替换前门属于框架语义变化，必须同步 manifest、policy、指南、测试和生成投影。

## 不做什么

本决定不把所有导航写进 registry，不替代 `DOC_POLICY.json` 的 lifecycle/authority/mutation 语义，也不把当前 gate、hash、上下界或测试数量复制进入前门声明。registry 只描述入口职责、可发现性和兼容跳转。
