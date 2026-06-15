---
name: zmd-project-entry
index_summary: "项目记忆体系在哪/接手读文件顺序/双写规矩;指向 _cc_live_memory/handoff 为单一现状源"
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
注意(2026-06-13 审计沉淀):同一条记忆在 harness 树与仓库镜像两边同名时,仓库副本会把 harness-only 的双方括号 wikilink(目标只在 harness 树里)**故意降为纯文本**——否则 CI 的 memory-tree 死链 gate 会 BLOCK(有翻车先例,连字面写出双方括号都会触发,本条措辞就是被 gate 现场拦过一次后改的)。所以 harness 版与仓库版哈希不同**不一定是漂移**,先 diff 内容判方向再同步;从 harness 整文件拷进镜像前,检查文内全部 wikilink 目标是否都存在于项目树。

**超长行 living 文件编辑 (2026-06-14):** 台账 `cc_context/review/p1_2_closure_evidence.md` (~82KB) 与 handoff 都是单行几 KB 的超长行,**Read/Edit 工具读不动** (token 超限,且 Edit 强制先 Read 成死锁)。改它们用 PowerShell:替换走 `Get-Content -Raw` + `[regex]::Matches($c,[regex]::Escape($old)).Count -eq 1` 校验唯一 + `$c.Replace()` + `Set-Content -NoNewline -Encoding UTF8`;handoff 加 stamp 走数组插入 (找 `stamp #N` 行 index → `$lines[0..($i-1)]+$new+$lines[$i..]` → Set-Content → `Copy-Item` 到另一镜像 → `Get-FileHash` 验两边一致)。

相关:[[zmd-checkout-env]]
