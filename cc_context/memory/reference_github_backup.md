---
name: github-backup
description: "2026-06-01 起项目+CC上下文实时备份到私有 GitHub zhuran24/endfield-exact-solver. 每 commit 自动 push (post-commit hook). memory 在 ~/.claude 仓库外靠 cc_context/memory 快照备份, 改 memory 后要 sync. 含 gh 认证/credential re-setup 踩坑点 (换机重装必看)."
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

2026-06-01 起: 仓库 + CC 上下文实时备份到**私有 GitHub `github.com/zhuran24/endfield-exact-solver`**。动机: 老电脑坏过、得找人从硬盘提数据, 不能只靠本地。**库必须保持 private** —— cc_context 备份含 memory (内有 Gemini API key 等 secret, 见 [[gemini-math-consultant]]), 转公开即泄密 (这是"库设私有"的决策依据)。

## 机制
- **每次 commit 自动 push**: `.git/hooks/post-commit` 跑 `git push origin HEAD`, 失败记 `.git/auto-push.log` 但不阻断 commit (下次成功 push 补齐)。正常 commit 即实时上 GitHub。
- **credential helper = gh 全路径** (`gh auth setup-git` 配的 `!'C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Links\gh.exe' auth git-credential`), **PATH 无关**, 任何 shell / hook 里 git push 都能认证。
- git 身份 (repo-local): `zhuran24 <3240314610@qq.com>`。

## CC memory 备份要点 (关键, 最易漏)
live memory 在 `~/.claude/projects/D-----zmd/memory` (**仓库外**)。仓库里 `cc_context/memory/` 是它的**快照副本**——靠它才推得上 GitHub。**改了 memory 后, commit 前要 sync**: 把 live memory 覆盖到 `cc_context/memory` 再 git add + commit (auto-push 带走)。否则 GitHub 上的 memory 是旧的。`cc_context/` 结构 (2026-06-01 整理): `cc_context/memory/` 记忆快照 + `global_CLAUDE.md` + `README_CC_HANDOFF.md` + `HANDOFF.md`; **维护脚本在 `cc_context/tools/`** (normalize_memory_links / report_link_graph / deorphan_links); **审查打包工件在 `cc_context/review/`** (build_v22*.py / GPT九审_prompt.md / 打包原则_汇总.md / 2 个 zip)。root 只放项目源。

## gh 认证 re-setup 踩坑 (换机 / 重装时按这个走, 省得再踩)
1. gh 装 winget 用户级: `C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Links\gh.exe` (新 shell 才进 PATH, 老 shell 用全路径)。
2. `gh auth login` 在 `!` 非交互下会**跳过"用 gh 认证 git"** → 登录后**必跑** `gh auth setup-git --hostname github.com`, 否则 git 走 GCM 无凭据, 私库 push 报 `Repository not found` (404 不是真没库)。
3. 仓库有 `.github/workflows/*.yml` → token 必须有 `workflow` scope, 否则 push 被 GitHub 拒。补: `gh auth refresh -s workflow --hostname github.com` (**非交互必带 `--hostname`**, 否则报 "--hostname required when not running interactively")。

## 不入库 (gitignore 已挡)
`.venv` / `.artifacts` / `.upstream_clones` / `_codex_archive` / 缓存 / `*.zip` `*.7z` (review 包 regenerable) / `data/checkpoints|solutions|telemetry`。`data/preprocessed/candidate_placements.json` 53MB 入库 (>50MB GitHub 警告但 <100MB 硬限, 推得上)。

## 已启用自动化 hook (2026-06-01)
- **pre-commit memory-sync** (`.git/hooks/pre-commit`, 机器专属不入库): 每 commit 前把 live memory (`~/.claude/.../memory`) 镜像进 `cc_context/memory` + git add (temp-swap 安全式, cp 失败不动旧备份)。免手动 sync, 每个 commit 自动带最新记忆。
- **SessionEnd WIP 兜底** (`.claude/settings.json` SessionEnd → `scripts/cc_wip_backup.ps1`, 入库随备份走): session 优雅退出若有未提交改动, 自动 `git add -A` + commit `SessionEnd WIP auto-checkpoint` (→ pre/post-commit 链同步 memory + push)。堵 session 间丢 WIP 的窗口。**机器崩溃(进程被杀)不 fire**, 崩溃靠 post-commit auto-push + 勤 commit 兜。

### ⚠️ 维护义务 (用户明确要记: "以后才会知道要及时去整理")
SessionEnd 会产生 `SessionEnd WIP auto-checkpoint` commit, 在历史里**会堆积**。**周期性 squash 整理** —— 建议 phase boundary / GPT review 打包前, 把连续的 WIP auto-checkpoint commit squash 成一个有意义的 commit, 否则历史越来越乱、git log/bisect 难用。这是已知 trade-off (用户接受 "WIP 可事后 squash" 换不丢活)。跟 [[memory-currency-protocol]] 同精神 (周期维护别让东西堆死)。
