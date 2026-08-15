# DOC-ADR-016｜真实仓库拓扑与 workspace overlay

状态：Accepted
日期：2026-08-14

## 问题

供应快照把真实仓库中的大量本机证据当成了 tracked 文件。若治理系统只观察“文件当前存在”，就会把 `workspace_untracked` 错认成 `git_tracked`，并让生成页、计数和定时门建立在不存在的 Git 耐久性上。根 `CLAUDE.md` 与 `AGENTS.md` 还由多个会话共同维护，在真实仓库中是可选 untracked overlay，不能成为 tracked 投影的硬输入。

## 决定

1. evidence 明确区分 `git_tracked`、`workspace_untracked` 与 `external_root`。
2. frozen `artifact_boundaries.json` 只投影 `git_tracked` 输入；语义消费者可同时识别 workspace evidence，但不得借此宣布其已 tracked。
3. `.docsystem/manifest.json` 登记可选 workspace overlay。overlay 存在时接受 policy 校验，缺失时不阻断 tracked 文档系统。
4. 所有 tracked 生成页只从 tracked 路径生成，并排除 workspace overlay。
5. 定时治理只检查当前树可机械复验的 lane；依赖仓外历史对象的 replay 只能手工触发。
6. Git-visible 非变异指纹只覆盖 tracked 状态与显式声明的 workspace 输入，不能把任意并发 untracked 写入归因于 checker。

## 后果

- 供应快照中的全 tracked artifact 拓扑会被如实判为不适配，而不是伪装成真实仓库通过。
- `CLAUDE.md` / `AGENTS.md` 可继续为本机 agent 提供轻量入口，但 tracked `AGENT_OPERATIONS.md` 才是耐久的维护指南。
- 新的存在方式必须进入结构化 registry，不能靠目录位置或当前可见性猜测。
