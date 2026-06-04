---
name: github-backup
description: "2026-06-01 起项目+CC上下文实时备份到私有 GitHub zhuran24/endfield-exact-solver. 每 commit 自动 push (post-commit hook). memory 在 ~/.claude 仓库外靠 cc_context/memory 快照备份, 改 memory 后要 sync. 含 gh 认证/credential re-setup 踩坑点 (换机重装必看)."
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

2026-06-01 起: 仓库 + CC 上下文实时备份到**私有 GitHub `github.com/zhuran24/endfield-exact-solver`**。动机: 老电脑坏过、得找人从硬盘提数据, 不能只靠本地。**库必须保持 private** —— cc_context 备份含 memory (内有 Gemini API key 等 secret, 见 [[gemini-math-consultant]]), 转公开即泄密 (这是"库设私有"的决策依据)。**硬约束**: ① **绝不翻 public** (一翻即泄 key); ② **禁 rebase / 重写历史** (filter-branch 清 key 会重写 SHA, 而 memory/docs 到处引 commit SHA, 全失效); ③ 免费私库**无 secret-scanning push protection**, 带 key 推不会被拦 (= 责任全在"别翻 public")。key 留私库历史是用户拍板可接受风险, 不 scrub / 不吊销 (见 [[gemini-math-consultant]])。

## ⚠️ 第三条暴露轴: review 包外发给 LLM 厂商 (跟 GitHub-public 不同, 2026-06-02 实证)

key 留私库历史防的是 GitHub 公开; 但**把仓库文件打成 review 包发给外部 LLM (GPT pro / Gemini) 是另一条暴露轴**, 上面的"私有"决策没覆盖它。**v22 spike review 包漏过 key 并已发给 GPT pro** —— `scripts/gemini_cross_check_*.py` (~10 文件) 内嵌 live key `AIzaSyC8D0a_...`, v22 build 没排除 → OpenAI 现持有。用户 2026-06-02 说"key 先放一放、算解决"(**不轮换、不吊销**), 但**防再漏的 build 规则必须固化**:

- **review 包 build 必排除**: ① `cc_context/` 整目录 (含**整棵 memory 树** + key + GPT prompt + 旧包自身) ② `scripts/gemini_cross_check*.py` (内嵌 live key) ③ `.git/.venv/.claude`。
- **secret 扫描 = 0 当 build 硬闸**: build 后扫整包 `AIzaSy` 等 secret pattern, 命中 ≠ 0 不准交付 (这道闸我自己跑、不委托)。注意扫描 pattern 别写太宽——`docs/research/.../gemini_cross_check_*` 的**归档 prompt/response** 是 reviewer 要的 Gemini archive 且无 key, 别误杀 (v23 build 时撞过这个 false-positive)。
- 历史坑: `build_v22_win.py` 的 `REPO` 是旧 dual-slug `zmd\zmd` (仓库上移后失效) + 仓库整理后 `cc_context/` 进了仓库才暴露这条 —— v23+ build 脚本已修 REPO 路径 + 加 cc_context/gemini 排除。

详见 [[gemini-math-consultant]] (key 来源) + [[windows-ninth-review-pending]] (v22 漏 + 轮换待定的当时状态) + 打包簇 [[index-packaging-cluster]]。

## 机制
- **每次 commit 自动 push**: `.git/hooks/post-commit` 跑 `git push origin HEAD`, 失败记 `.git/auto-push.log` 但不阻断 commit (下次成功 push 补齐)。正常 commit 即实时上 GitHub。
- **credential helper = gh 全路径** (`gh auth setup-git` 配的 `!'C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Links\gh.exe' auth git-credential`), **PATH 无关**, 任何 shell / hook 里 git push 都能认证。
- git 身份 (repo-local): `zhuran24 <3240314610@qq.com>`。

## CC memory 备份要点 (关键, 最易漏)
live memory 在 `~/.claude/projects/D-----zmd/memory` (**仓库外**)。仓库里 `cc_context/memory/` 是它的**快照副本**——靠它才推得上 GitHub。**改了 memory 后, commit 前要 sync**: 把 live memory 覆盖到 `cc_context/memory` 再 git add + commit (auto-push 带走)。否则 GitHub 上的 memory 是旧的。`cc_context/` 结构 (2026-06-01 整理): `cc_context/memory/` 记忆快照 + `global_CLAUDE.md` + `README_CC_HANDOFF.md` + `HANDOFF.md`; **维护脚本在 `cc_context/tools/`** (normalize_memory_links / report_link_graph / deorphan_links / extract_session_turns / list_unresolved_links / **stamp_living_status** [pre-commit 调, 自动 stamp handoff 可推导现状字段] 等, 以实际 ls 为准); **审查打包工件在 `cc_context/review/`** (build_v22/v23/v24*.py / GPT_v24复审_prompt.md 等 / 打包原则_汇总.md / deps / zip, 随版本增长, 以实际 ls 为准)。root 只放项目源。

## gh 认证 re-setup 踩坑 (换机 / 重装时按这个走, 省得再踩)
1. gh 装 winget 用户级: `C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Links\gh.exe` (新 shell 才进 PATH, 老 shell 用全路径)。
2. `gh auth login` 在 `!` 非交互下会**跳过"用 gh 认证 git"** → 登录后**必跑** `gh auth setup-git --hostname github.com`, 否则 git 走 GCM 无凭据, 私库 push 报 `Repository not found` (404 不是真没库)。
3. 仓库有 `.github/workflows/*.yml` → token 必须有 `workflow` scope, 否则 push 被 GitHub 拒。补: `gh auth refresh -s workflow --hostname github.com` (**非交互必带 `--hostname`**, 否则报 "--hostname required when not running interactively")。
4. **git commit 身份 ≠ gh 认证邮箱** —— git 不会自动用 GitHub 登录邮箱署名, 是两回事。换机/重装首 commit 会卡 `Author identity unknown`, 必须单独 `git config user.name/user.email` (name 可 `gh api user` 拉 = zhuran24, email 用 `3240314610@qq.com`)。
5. `gh auth login` 交互序列: GitHub.com → HTTPS → "用 gh 凭据认证 git" 选 **Yes** → web 设备码。注意 **login 默认不需 `--hostname`, 唯独 `refresh` 在非交互 TTY 必须显式带**。

## 不入库 (gitignore 已挡)
`.venv` / `.artifacts` / `.upstream_clones` / `_codex_archive` / 缓存 / `*.zip` `*.7z` (review 包 regenerable) / `data/checkpoints|solutions|telemetry`。`data/preprocessed/candidate_placements.json` 53MB 入库 (>50MB GitHub 警告但 <100MB 硬限, 推得上)。

## 已启用自动化 hook (2026-06-01)
- **pre-commit memory-sync** (`.git/hooks/pre-commit`, 机器专属不入库): 每 commit 前把 live memory (`~/.claude/.../memory`) 镜像进 `cc_context/memory` + git add (temp-swap 安全式, cp 失败不动旧备份)。免手动 sync, 每个 commit 自动带最新记忆。
  - ⚠️ **预期行为非失败 (改 memory 时反复遇到)**: 只改了 live memory 时, **首次 `git commit` 常报 "nothing to commit"** —— 因为 hook 在这次 commit 的快照算完后才 git-add 同步的 memory, 留在 index 里。**再 `git commit` 一次**即成功 (两步时序)。post-commit 已抢先 push 时, 后续手动 push 报 **"Everything up-to-date"** 也是正常 (已上去了)。
  - **跨分支 (spike) 改动用 git worktree**: 守 PROJECT_LOCK 的 spike/master 隔离, 改 spike 代码走 `git worktree add <wt> <spike-branch>` + `git -C <wt> commit` (共用同一 `.git`, 不动 master working tree)。**验 push 已落必须 `git ls-remote origin <branch>`** —— worktree commit 的 post-commit push log 写进 worktree 自己的 git dir, **不进主 `.git/auto-push.log`**, 翻主 log 看不到 (本 session 一度误判 spike 没 push)。**spike commit 用 `--no-verify` 是正当例外** (与 [[autopilot-with-review-gate]] "别 --no-verify" 抵触但合理): pre-commit 的 memory-sync + stamp_living_status 会把整个 `cc_context/memory` git-add 进 spike commit, 污染历来 clean、off-老-master、本无 `cc_context/memory` 的 spike 分支 (且该 hook 对 spike 分支报错跳过、非验证闸) → spike commit 走 `--no-verify` 正确且与分支历史一致。
- **实例/分身 transclusion 引擎** (2026-06-02, `.git/hooks/pre-commit` 在 memory-sync **之前**调 `cc_context/tools/stamp_living_status.py`, fail-soft `|| true` 绝不阻断 commit): 记忆树的**单一真相源 + transclusion** 模型。`INSTANCES` 注册表 = 一批**可推导事实**的唯一权威值 (`latest_review_package` 读 `cc_context/review/LATEST_PACKAGE.json` / `spike_head` / `current_phase` 读 CLAUDE.md / `repo_url` 读 git remote)。任意 memory 节点里 `<!-- INSTANCE:<id> -->…<!-- /INSTANCE:<id> -->` 槽 (示例用 `<id>` 占位, 真槽 id 用注册表真名) 是该实例的**分身**; 引擎每 commit 扫**全树**把实例当前值 transclude 进所有分身槽 → **重复的可推导值结构上不可能 drift** (改实例源, 一刷全分身同步; 同一 `repo_url` 现投影在 handoff + review_strategy 两处)。**这是治"现状/重复值漏更"根因的强制函数** —— 那根因 = 这些值散多节点、没强制函数, 光记规则 (被动文本) 治不住 (记完 rule#7 又犯)。**只治可推导值; 规则/判断靠 wikilink 不 transclude** (逐字副本满树=clutter)。另: handoff 判断散文没提最新包版本时 **stderr 大声 warn** (判断类推不出只能 warn)。**护栏**: 只改槽内、resolver 失败保留旧值不 blank、逐文件 try/except、幂等。**扩展**: 加实例=往 INSTANCES 加 resolver; 加分身=节点里插 `INSTANCE:id` 槽。**hook 机器本地不入库, 换机要重建** (PYV 探 .venv → 调脚本 `|| true`, 在 SRC sync 前)。模型详 [[memory-tree-structural-health]]。
- **SessionEnd WIP 兜底** (`.claude/settings.json` SessionEnd → `scripts/cc_wip_backup.ps1`, 入库随备份走): session 优雅退出若有未提交改动, 自动 `git add -A` + commit `SessionEnd WIP auto-checkpoint` (→ pre/post-commit 链同步 memory + push)。堵 session 间丢 WIP 的窗口。**机器崩溃(进程被杀)不 fire**, 崩溃靠 post-commit auto-push + 勤 commit 兜。

### ⚠️ 维护义务 (用户明确要记: "以后才会知道要及时去整理")
SessionEnd 会产生 `SessionEnd WIP auto-checkpoint` commit, 在历史里**会堆积**。**周期性 squash 整理** —— 建议 phase boundary / GPT review 打包前, 把连续的 WIP auto-checkpoint commit squash 成一个有意义的 commit, 否则历史越来越乱、git log/bisect 难用。这是已知 trade-off (用户接受 "WIP 可事后 squash" 换不丢活)。跟 [[memory-currency-protocol]] 同精神 (周期维护别让东西堆死)。

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[memory-tree-structural-health]] — cc_context 维护工具 = 同棵树
