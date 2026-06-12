---
name: zmd-project-entry
description: zmd 项目(终末地 70x70 精确求解器)的入口指针——每个新会话先读哪些文件、记忆体系在哪
metadata: 
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

zmd 项目(`C:\claude pj\zmd_pj`)自带完整的项目级记忆体系,**不要在 harness memory 里复制项目状态,只存指针**。

**Why:** 项目有"一棵逻辑知识树、两个物理投影"的架构(docs/ = 稳定文档投影,cc_context/memory/ = 协作连续性投影,_cc_live_memory/ 与后者保持镜像)。harness memory 再抄一份就成了第三真相源,会漂。

**How to apply:** 新会话接手时按此顺序读:
1. `_cc_live_memory/handoff_windows_ninth_review_pending.md` — **单一 living 现状源**,当前 phase/交接状态只信这条(以正文 stamp 编号最大的块为最新现状;顶部 06-11 协议块与其余 stamp 是层叠历史)
2. `_cc_live_memory/MEMORY.md` — CC 记忆树索引(feedback/project/reference;2026-06-10 瘦身后约 60+ 条活记忆,老记忆单份归档在 cc_context/memory_archive/)
3. 项目 `CLAUDE.md` + `START_HERE.md` — phase contract 投影 + 仓库导览
4. `docs/PHASE_1_2_CLOSE_GATE.md` — 当前关门协议(V50 手动 owner-count gate)

改记忆的规矩:**必须手动双写** `_cc_live_memory/` 和 `cc_context/memory/` 两份(pre-commit 镜像源指旧 slug `D-----zmd` 已不存在,同步会静默跳过)。改完用 Get-FileHash 验证两边一致。

相关:[[zmd-checkout-env]]
