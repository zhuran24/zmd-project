---
name: concurrent-claude-sessions-repo-collision
description: "两个 CC 会话并发操作同一 git 仓库的事故指纹与处置;遇\"工作树状态自己在变\"先查进程别动仓库"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

owner "线程分支" 设置(开多会话/切换)可能**遗留一个孤儿 CC 会话**,与当前会话**并发操作同一个 git 仓库**。2026-06-13 zmd 实录:孤儿会话 e8a750c5 (claude.exe 16312) 与本会话 20690dc4 (34628) 同抢仓库,它把 git 历史从 r8 一路 commit 到 r14(本会话 summary 停在 r8 但 git 已到 r14 = 它干的)。

**事故指纹(三条一起出现基本可锁定并发会话):**
1. **git 工作树/暂存区状态在诊断期间自己变** —— 连抓几次 `git status`,文件列表不一样(一会儿是 staged 的 A 批,一会儿变成 working-tree 的 B 批)。我只跑了只读命令,状态却在变 = 另有进程在操作。
2. **reflog 却干净** —— 全是正常 commit + push,没有 reset/checkout/rebase 痕迹。因为 `git checkout <旧commit> -- <file>` 这类操作**只改工作树/index、不动 HEAD,不留 HEAD reflog**;并发会话的某步操作以这种形式留下"看似回退到旧版"的 staged 改动。
3. **git 历史超出本会话已知** —— commit 数/最新 commit 远超 summary/记忆里的状态(另一会话在持续 commit+auto-push)。

**险情(必须避免):** 本会话一度把那批"看似回退到旧版"的 staged 改动判成"坏状态",准备 `git reset --hard` 恢复 —— **那会直接抹掉另一会话正在做的活跃工作**(它当时在应用一个 HIGH 修复)。是 owner 一句"再多检查"拦下的。**教训:不可逆操作(reset --hard / commit / push)前,凡是"状态在变"或解释不通,先查进程,别动仓库。**

**诊断方法(PowerShell):**
- `Get-CimInstance Win32_Process -Filter "Name='claude.exe'"` —— 列所有 claude.exe;多于一个 = 有并发会话。对比 CreationDate 分辨。
- 自己是哪个 claude.exe:看自己工具子进程(pwsh/bash)的 ParentProcessId 链 → 根 claude.exe = 自己。
- 找孤儿在干嘛:`Get-CimInstance Win32_Process -Filter "ParentProcessId=<它的pid>"` 看它的 bash/python 子进程(有=正在跑命令,空=空闲)。`check_line_endings.py` 等 hook 进程出现 = 它正在 commit。
- 活跃 session:`cc_watchdog\contexts\*.json` 心跳(15s 刷新),近几分钟刷新的 = 活跃会话。

**处置铁律:**
- 确认唯一会话前**绝不动仓库**(不 reset/commit/push/改文件)。
- **绝不杀 claude 进程**(见全局 CLAUDE.md 自我保护)。让 **owner 手动停**孤儿会话。
- owner 停孤儿会话会**触发它的 SessionEnd hook → 自动 WIP commit**(`chore: SessionEnd WIP auto-checkpoint`,未 push),把它工作树的半成品兜底保存,不丢。
- 接管时:`git reset --soft <兜底前的commit>` 把 WIP 退回暂存 → 补全验收(独立重验,**用 `git worktree add <旧commit>` 隔离做修复前红复现**,不污染主树)→ 转成规范 commit + push(WIP 被 squash 掉)。

**Why:** 多会话并发同一仓库 = git index/工作树/commit 互相打架;盲目 reset 抹掉别人的活,盲目 commit 撞别人的 push。诊断指纹(状态在变 + reflog 干净)和 SessionEnd 兜底机制是安全接管的关键。

**How to apply:** 接手会话先做基本一致性核对(summary vs `git log` vs `git status`);三者矛盾或"状态在变"→ 立即查进程,别动仓库,需要时让 owner 介入。相关:[[cc-api-watchdog]](守护/会话机制)、[[zmd-checkout-env]](commit=auto-push)。
