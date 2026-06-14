---
name: zmd-env-memory-sync
description: zmd pre-commit memory sync 现状——只 auto-stamp handoff INSTANCE 槽, 整目录镜像覆盖块已移除别加回(会用 harness 十几条覆盖 cc_context 几十条=删数据);共维护文件改动靠手动双写三处
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **pre-commit memory sync 时序坑 (2026-06-13 实测; 2026-06-14 更新)**: 原 pre-commit hook 有"把 harness 侧记忆整目录镜像进 cc_context"的覆盖块, 它在 staging 之后写工作树 → commit 收旧版、sync 新内容留工作树未暂存, 偶发 `live mirror byte drift` BLOCK。**2026-06-14 该整目录覆盖块已移除** (它会用 harness 十几条覆盖 cc_context 几十条 = 删数据; 两树已是不同内容集, 见下条 hook 说明)。现 pre-commit 只 auto-stamp handoff 的 INSTANCE 槽 (仍可能在 staging 后改 handoff 工作树留少量残余, 但范围小到只 handoff)。**harness↔cc_context 的共维护文件 (zmd-checkout-env / zmd-project-entry / no-workflow-use-chrome-gpt-review / workflow-approval-not-avoidance) 改动靠手动双写三处** (cc_context/memory + _cc_live_memory + harness `~/.claude/projects/<slug>/memory`), 不再自动镜像。commit 后工作树有 handoff 残余仍可能, 内容正当补 chore commit 收掉。

相关:[[zmd-checkout-env]]
