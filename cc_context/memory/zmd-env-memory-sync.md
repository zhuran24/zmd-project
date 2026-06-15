---
name: zmd-env-memory-sync
index_summary: "pre-commit memory sync 只 auto-stamp handoff INSTANCE 槽,整目录镜像覆盖块已移除别加回(会用 harness 十几条覆盖 cc_context 几十条=删数据);共维护文件改动靠手动双写三处"
description: zmd 记忆三处同步现状——AI auto-memory 真正召回读 harness 不是 cc_context;repo→harness 投影靠 sync_memory_to_harness.py(snake 投影类自动);pre-commit 只 auto-stamp handoff INSTANCE 槽;kebab 共维护节点双写三处 + check_memory_tree warn 兜底
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **pre-commit memory sync 时序坑 (2026-06-13 实测; 2026-06-14 更新)**: 原 pre-commit hook 有"把 harness 侧记忆整目录镜像进 cc_context"的覆盖块, 它在 staging 之后写工作树 → commit 收旧版、sync 新内容留工作树未暂存, 偶发 `live mirror byte drift` BLOCK。**2026-06-14 该整目录覆盖块已移除** (它会用 harness 十几条覆盖 cc_context 几十条 = 删数据; 两树已是不同内容集, 见下条 hook 说明)。现 pre-commit 只 auto-stamp handoff 的 INSTANCE 槽 (仍可能在 staging 后改 handoff 工作树留少量残余, 但范围小到只 handoff)。**harness↔cc_context 的共维护文件 (zmd-checkout-env / zmd-project-entry / no-workflow-use-chrome-gpt-review / workflow-approval-not-avoidance) 改动靠手动双写三处** (cc_context/memory + _cc_live_memory + harness `~/.claude/projects/<slug>/memory`), 不再自动镜像。commit 后工作树有 handoff 残余仍可能, 内容正当补 chore commit 收掉。

- **harness 召回树补齐 + repo→harness 投影工具 (2026-06-14)**: 关键认知 — **AI auto-memory 真正自动召回读的是 harness (`~/.claude/projects/<slug>/memory/`), 不是 cc_context/memory**。体检发现两树几乎不重叠: repo 有 60+ 节点 (几十条 `feedback_*` 工作规则 + `project_*`/`reference_*`/`user_profile`) harness 召回树**根本没有** → owner 写的规则 AI 召回不到, `CLAUDE.md` 里 `[[subagent-model-by-weight]]` 等 wikilink 跨树跳空。已把 61 个缺失节点投影进 harness (snake 文件名 → frontmatter `name` 的 kebab; 内容字节级原样; handoff 现状源只放指针 stub 防漂) + 建 3 个索引父节点 (collaboration-rules-index / project-knowledge-index / reference-resources-index, 均 harness-only, 故此处纯文本不 wikilink 防 repo 端 unresolved BLOCK) + MEMORY.md 加导航 (控 <24KB 截断线)。**防再漂工具 = `python cc_context/tools/sync_memory_to_harness.py --check`(报 drift) / `--apply`(投影+重建索引)**: 单向 repo→harness, 只自动管 snake 投影类 (feedback_/project_/reference_/user_), 跳过 handoff_。上面第一段那批 kebab 共维护节点 (no-gpt-*/zmd-env-* 等 AI 在 harness 写、双向都可能更新的) **不进 sync 自动覆盖**, 靠 `check_memory_tree.py` 的 `harness↔cc_context co-maintained drift` warn 提醒人工判方向 (2026-06-14 已一次性 repo→harness 对齐 19 个)。

相关:[[zmd-checkout-env]] [[memory-tree-structural-health]] [[memory-currency-protocol]]
