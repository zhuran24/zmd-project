---
name: avoid-micro-optimization-spiral
index_summary: "占比 <5% 就停手换方向."
description: 优化时先确认目标 phase 占总耗时的百分比，<5% 就停手换方向
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
做性能优化时，**每发现一个 hot 子 phase，先算它占"实际瓶颈总耗时"的百分比，<5% 就停下找别处**，不要继续深挖。

**Why:** Codex 在终末地项目最后 2-3 天（2026-05-04 那段）陷在 `_index_pools()` 函数的 micro-optimization 螺旋里——S105 → S148，**40+ 个 S 步骤**全部在切分模型构建阶段（约 13 秒）的子 phase。问题是真正瓶颈是 CP-SAT 搜索本身（4-30 分钟），调优 `_index_pools()` 那 1-2 秒的 subphase **对总耗时贡献 < 0.1%**。整段时间产出基本为零，最后还卡在"诊断工具自己有 bug"上，迁移到 Claude 时计划被迫中断。

**How to apply:**
- 看到"X subphase 是当前热点"时，先问"这个 subphase 占整体真正瓶颈的多少比例"
- 比例 < 5% 立刻停手，去找其他真正占大头的瓶颈
- 不要被"再深一层 instrumentation 又发现新热点"的递归吸引
- 真正的瓶颈不会在 13s 的建模里，会在求解器搜索本身（learned clauses、分支决策、剪枝）
- 如果当前层级已经在 < 5%，往**上**走（重新审视全局），而不是往**下**钻

## 链 (补连 2026-06-01)
- [[optimization-strategy]] — 互补
