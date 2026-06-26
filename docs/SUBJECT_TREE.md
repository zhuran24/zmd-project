# Subject 文本状态

`docs/subjects/` 目前是便于集中阅读的主题说明集合，不是自动 transclusion 的 source registry。文件中的 `DOC-SUBJECT` 注释只保留来源追踪价值，不会被脚本同步，也不会被 preflight 校验。

当前维护规则：

- `PROJECT_LOCK.md`、机器义务和 phase gate 优先于 subject 文本。
- 修改 subject 文件不会自动修改 README、项目说明或 cc_memory；需要逐个更新实际消费面。
- `cc_memory/memory.db` 是独立的协作记忆图，只能通过 `cc_memory/mem.py` 操作；不存在 `cc_context` 第二投影。
- 发现相互冲突时，以当前工作树代码行为和上述权威文件为准，并直接修正所有现行文本副本。

当前主题入口见 `docs/subjects/README.md`。
