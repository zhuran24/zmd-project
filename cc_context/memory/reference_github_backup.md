---
name: github-backup
description: "2026-06-01 起项目+CC上下文实时备份到私有 GitHub zhuran24/endfield-exact-solver. 每 commit 自动 push (post-commit hook). memory 在 ~/.claude 仓库外靠 cc_context/memory 快照备份, 改 memory 后要 sync. 含 gh 认证/credential re-setup 踩坑点 (换机重装必看)."
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

2026-06-01 起: 仓库 + CC 上下文实时备份到**私有 GitHub `github.com/zhuran24/endfield-exact-solver`**。动机: 老电脑坏过、得找人从硬盘提数据, 不能只靠本地。

## 机制
- **每次 commit 自动 push**: `.git/hooks/post-commit` 跑 `git push origin HEAD`, 失败记 `.git/auto-push.log` 但不阻断 commit (下次成功 push 补齐)。正常 commit 即实时上 GitHub。
- **credential helper = gh 全路径** (`gh auth setup-git` 配的 `!'C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Links\gh.exe' auth git-credential`), **PATH 无关**, 任何 shell / hook 里 git push 都能认证。
- git 身份 (repo-local): `zhuran24 <3240314610@qq.com>`。

## CC memory 备份要点 (关键, 最易漏)
live memory 在 `~/.claude/projects/D-----zmd/memory` (**仓库外**)。仓库里 `cc_context/memory/` 是它的**快照副本**——靠它才推得上 GitHub。**改了 memory 后, commit 前要 sync**: 把 live memory 覆盖到 `cc_context/memory` 再 git add + commit (auto-push 带走)。否则 GitHub 上的 memory 是旧的。`cc_context/` 还含 global_CLAUDE.md + 维护脚本 (normalize_memory_links / report_link_graph / deorphan_links)。

## gh 认证 re-setup 踩坑 (换机 / 重装时按这个走, 省得再踩)
1. gh 装 winget 用户级: `C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Links\gh.exe` (新 shell 才进 PATH, 老 shell 用全路径)。
2. `gh auth login` 在 `!` 非交互下会**跳过"用 gh 认证 git"** → 登录后**必跑** `gh auth setup-git --hostname github.com`, 否则 git 走 GCM 无凭据, 私库 push 报 `Repository not found` (404 不是真没库)。
3. 仓库有 `.github/workflows/*.yml` → token 必须有 `workflow` scope, 否则 push 被 GitHub 拒。补: `gh auth refresh -s workflow --hostname github.com` (**非交互必带 `--hostname`**, 否则报 "--hostname required when not running interactively")。

## 不入库 (gitignore 已挡)
`.venv` / `.artifacts` / `.upstream_clones` / `_codex_archive` / 缓存 / `*.zip` `*.7z` (review 包 regenerable) / `data/checkpoints|solutions|telemetry`。`data/preprocessed/candidate_placements.json` 53MB 入库 (>50MB GitHub 警告但 <100MB 硬限, 推得上)。

## 待定增强 (用户可选, 还没开)
- **pre-commit memory-sync hook**: 每 commit 自动 sync live memory → cc_context, 免手动。
- **CC Stop hook auto-commit+push WIP**: 防 session 间机器死丢未提交的活, 代价 = WIP commit 进历史。
