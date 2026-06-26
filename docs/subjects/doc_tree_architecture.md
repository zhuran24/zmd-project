# 文档树架构

当前文档树采用“多文件、显式 authority、人工同步”的简单模型：

- `PROJECT_LOCK.md` 约束 exactness 与发布边界。
- JSON 机器义务和 phase gate 约束可执行状态。
- living docs 解释当前实现。
- `docs/research/` 保存带日期的历史证据。
- `cc_memory/memory.db` 保存协作记忆图，但不自动投影到文档。

历史上曾设计 subject/projection transclusion，并在若干文件中留下 `DOC-SUBJECT` 注释。当前仓库没有 registry、sync tool 或 preflight enforcement，所以这些注释不能被描述成自动一致性保证。任何状态变更都必须直接更新所有实际消费文档和相关 memory node/edge。
