# 文档知识层架构

项目现在采用“机器 authority + 结构化知识账本 + 自动投影 + 历史证据库”的四层模型。

1. `PROJECT_LOCK.md`、canonical rules、proof obligations 和 owner gate 各自管辖不可混写的问题域。
2. `data/knowledge/claims.jsonl` 给结论稳定身份，`decisions.jsonl` 记录决定与 supersede，`dossiers.json` 登记证据包。
3. `docs/CURRENT.md` 与 `docs/CATALOG.md` 由生成器产生，不手工复制会变化的状态。
4. `docs/research/` 与 `.artifacts/` 保存过程和原始证据，默认不因标题或日期自动获得当前权威。

稳定任务入口是 [`../START_HERE.md`](../START_HERE.md)。维护规则和命令见 [`../../data/knowledge/README.md`](../../data/knowledge/README.md)。

此结构同时解决两种不同问题：authority 顺序回答“冲突时信谁”，catalog 与稳定 ID 回答“怎样知道自己已经找全相关结论和证据”。
