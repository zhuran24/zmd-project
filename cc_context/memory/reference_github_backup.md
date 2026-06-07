---
name: github-backup
description: "2026-06-01 起项目+CC上下文实时备份到私有 GitHub；当前 repo_url 由 INSTANCE 槽从 git remote 推导。 当前不再假设每 commit 自动 push；发布通过显式 GitHub 上传包或普通 git push 分支完成。 memory GitHub 发布面在 cc_context/memory, 当前观察点另有 _cc_live_memory 字节镜像, 改 memory 后两边要同步. 含 gh 认证/credential re-setup 踩坑点 (换机重装必看)."
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

2026-06-01 起: 仓库 + CC 上下文开始备份到 GitHub；当前目标由 `repo_url` INSTANCE 从 git remote 推导（本观察点为 `github.com/zhuran24/zmd`）。动机: 老电脑坏过、得找人从硬盘提数据, 不能只靠本地。**2026-06-06 supersede**: 当前树不再允许明文 API key / token 作为“私库可接受风险”存在；Gemini 脚本只读 `GEMINI_API_KEY`, preflight 有 secret scan。**硬约束**: ① 仍不要随意翻 public; ② 正常开发不 rebase / 不重写历史, 除非用户明确决定做 secret-history purge; ③ 免费私库未必有 push-protection, 所以当前树 secret=0 必须由本地 gate 保证。

## ⚠️ 第三条暴露轴: review 包外发给 LLM 厂商 (跟 GitHub-public 不同, 2026-06-02 实证)

key 留私库历史防的是 GitHub 公开; 但**把仓库文件打成 review 包发给外部 LLM (GPT pro / Gemini) 是另一条暴露轴**, 上面的"私有"决策没覆盖它。**v22 spike review 包漏过 key 并已发给 GPT pro** —— `scripts/gemini_cross_check_*.py` (~10 文件) 曾内嵌 live key, v22 build 没排除 → OpenAI 现持有。2026-06-06 当前策略改为：当前树 scrub + gate 防再漏；旧 credential 建议 owner 侧轮换/吊销；review build 规则继续固化。

- **review 包 build 必排除**: ① `cc_context/` 整目录 (含**整棵 memory 树** + GPT prompt + 旧包自身) ② `scripts/gemini_cross_check*.py` (需环境变量, 但仍不该进入 review 包) ③ `.git/.venv/.claude`。
- **secret 扫描 = 0 当 build 硬闸**: build 后扫整包 Gemini/OpenAI/GitHub/private-key 等 secret pattern, 命中 ≠ 0 不准交付 (这道闸我自己跑、不委托)。注意扫描 pattern 别写太宽——`docs/research/.../gemini_cross_check_*` 的**归档 prompt/response** 是 reviewer 要的 Gemini archive 且无 key, 别误杀 (v23 build 时撞过这个 false-positive)。
- 历史坑: `build_v22_win.py` 的 `REPO` 是旧 dual-slug `zmd\zmd` (仓库上移后失效) + 仓库整理后 `cc_context/` 进了仓库才暴露这条 —— v23+ build 脚本已修 REPO 路径 + 加 cc_context/gemini 排除。

详见 [[gemini-math-consultant]] (key 来源) + [[windows-ninth-review-pending]] (v22 漏 + 轮换待定的当时状态) + 打包簇 [[index-packaging-cluster]]。

## 当前发布机制（2026-06-06 之后）
- **显式发布，不再假设自动推送**：当前发布面使用 GitHub 上传包或普通 `git push origin <branch>`。旧 `post-commit auto-push` 是 CC 本机历史机制，不是 repo-native 契约。
- **repo-native gate**：`scripts/preflight_gate.py` 是权威门禁；本地 hook 由 `.githooks/pre-commit` + `scripts/install_hooks.py` 安装，只是便利层。GitHub 侧应跑 `.github/workflows/project_foundation.yml`。
- **credential helper**：换机时仍可用 `gh auth setup-git` 建立 GitHub 凭据，但不要把 token/key 写入仓库或 memory。
- **git 身份**：repo-local author 仍由本机 `git config user.name/user.email` 决定。

## CC memory 备份要点（当前 repo-native 规则）
memory 的 GitHub 发布面在 `cc_context/memory/`；当前 clean 观察点还跟踪 `_cc_live_memory/` 作为字节镜像，二者必须同步。旧 CC live path `~/.claude/projects/D-----zmd/memory` 只作为本机历史来源，不再是 repo-native gate 的默认路径。**改了 memory 后，同步 `cc_context/memory/` 与 `_cc_live_memory/` 并运行 `python scripts/check_memory_tree.py --require-live-mirror`**。

`cc_context/` 结构：`cc_context/memory/` 记忆快照 + `global_CLAUDE.md` + `README_CC_HANDOFF.md` + `HANDOFF.md`; 维护脚本在 `cc_context/tools/`; 审查打包工件在 `cc_context/review/`。root 只放项目源。

## gh 认证 re-setup 踩坑 (换机 / 重装时按这个走, 省得再踩)
1. gh 装 winget 用户级: `C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Links\gh.exe` (新 shell 才进 PATH, 老 shell 用全路径)。
2. `gh auth login` 在 `!` 非交互下会**跳过"用 gh 认证 git"** → 登录后**必跑** `gh auth setup-git --hostname github.com`, 否则 git 走 GCM 无凭据, 私库 push 报 `Repository not found` (404 不是真没库)。
3. 仓库有 `.github/workflows/*.yml` → token 必须有 `workflow` scope, 否则 push 被 GitHub 拒。补: `gh auth refresh -s workflow --hostname github.com` (**非交互必带 `--hostname`**, 否则报 "--hostname required when not running interactively")。
4. **git commit 身份 ≠ gh 认证邮箱** —— git 不会自动用 GitHub 登录邮箱署名, 是两回事。换机/重装首 commit 会卡 `Author identity unknown`, 必须单独 `git config user.name/user.email` (name 可 `gh api user` 拉 = zhuran24, email 用 `3240314610@qq.com`)。
5. `gh auth login` 交互序列: GitHub.com → HTTPS → "用 gh 凭据认证 git" 选 **Yes** → web 设备码。注意 **login 默认不需 `--hostname`, 唯独 `refresh` 在非交互 TTY 必须显式带**。

## 不入库 / 外部制品
`.venv` / 可再生 review 包 / 缓存 / `*.zip` `*.7z` / `data/checkpoints|solutions|telemetry` 不进普通源码提交。`data/preprocessed/candidate_placements.json` 是 certified-exact 生产输入, 但当前 lightweight GitHub checkout 明确把它作为外部大制品处理: 缺省不在工作树, 恢复后必须用 `python scripts/check_external_artifacts.py --require candidate_placements` 校验 size/hash, 不要重新塞回普通 Git。

## 旧 CC hook 机制（历史，不再作为当前契约）
旧环境曾有机器本地 `.git/hooks/pre-commit` / `post-commit` 自动 memory-sync、stamp、push。该机制依赖外部 CC live path 和本机 GitHub 凭据，**不是当前 repo-native publish contract**。当前规则是：

- 本地便利 hook：运行 `python scripts/install_hooks.py` 安装 tracked `.githooks/pre-commit`。
- 强制门禁：直接运行 `python scripts/preflight_gate.py`；CI 运行 `python scripts/preflight_gate.py --ci --base-ref <ref>`。
- memory currentness：`cc_context/tools/stamp_living_status.py` 已 repo-native，默认可检查 `cc_context/memory`，preflight 会检查 INSTANCE drift。
- live mirror：如果 `_cc_live_memory/` 存在，preflight 要求它与 `cc_context/memory/` 字节一致。

### ⚠️ 维护义务 (用户明确要记: "以后才会知道要及时去整理")
SessionEnd 会产生 `SessionEnd WIP auto-checkpoint` commit, 在历史里**会堆积**。**周期性 squash 整理** —— 建议 phase boundary / GPT review 打包前, 把连续的 WIP auto-checkpoint commit squash 成一个有意义的 commit, 否则历史越来越乱、git log/bisect 难用。这是已知 trade-off (用户接受 "WIP 可事后 squash" 换不丢活)。跟 [[memory-currency-protocol]] 同精神 (周期维护别让东西堆死)。

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[memory-tree-structural-health]] — cc_context 维护工具 = 同棵树
