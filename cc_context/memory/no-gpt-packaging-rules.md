---
name: no-gpt-packaging-rules
index_summary: "除缓存全打(build_v80_single_win.py);r7 纪律=git worktree 干净树打+复制成 sha 前缀唯一名防并发覆盖+交付前 Get-FileHash 核对;老审查打包规范已全废"
description: "外发 GPT 的打包规则:除缓存与 cc_context 外全项目打(build_v80_single_win.py);**cc_context(协作/审查工件区)必须排除**——否则 72 份 algoaudit finding 详表+八面台账+记忆树泄露给外审 GPT 破坏白板与独立性(2026-06-16 根因修);r7 纪律=git worktree 干净树打+复制成 sha 前缀唯一名防并发覆盖+交付前 Get-FileHash 核对;老审查打包规范已全废"
metadata:
  node_type: memory
  type: feedback
---

**打包规则(唯一存留):除缓存文件外全项目打**(排除 .git/__pycache__/.pytest_*/.ruff_cache/.venv/.upstream_clones/*.pyc/输出 zip/prompt 文件/`補丁包/`(包套娃))。build 脚本在 `cc_context/review/build_v80_single_win.py`(单包,自包含,gpt_dispatch --pack 调用它;分卷版已归档 review/archive/)。**打包纪律 (r7 教训)**: ① build 脚本固定输出同名 zip, 多会话共用工作区会被并发覆盖 (sha 漂了险些传错包) → **每轮包用 `git worktree add --detach <tmp> HEAD` 的干净树打 + 立刻复制成 sha 前缀唯一名** (如 `zmd_r7_snapshot_<sha8>.zip`), prompt 只指认唯一名; ② 干净树打的副产品 = 不混入脏 WIP 和未跟踪历史归档 (裸 pytest 误收集杂物源), 包从 ~18MB 降 ~12MB; ③ **交付前最后一步重新 `Get-FileHash` 核对 = prompt 里的 sha**。**老的审查打包规范(no-priming/7-section prompt 模板/armor/7z 策略等)2026-06-10 全部废除**,备份在 `cc_context/memory_archive/` 与 `cc_context/review/archive/`。给 GPT 的 prompt 直接讲任务+约束+交付物即可。

**⚠️ cc_context 必须排除 (2026-06-16 根因发现 + 修复)**: 早期 build 的 `EXCLUDED_DIR_NAMES` 不含 cc_context, 而 `rglob("*")` 全量遍历(连 .gitignore 都不看)→ **整个 `cc_context/` 被打进外审包**。实证旧包 **4646 文件里 cc_context 占 2164**, 含 **72 份 `algoaudit_*.md` finding 详表** + `p1_2_closure_evidence.md` 八面台账 + 108 个 `cc_context/memory` 审查轨迹记忆。后果: 之前**每一轮外审**(含八面三连 clean 那些)GPT 都能翻到"我们审过什么 / 分了哪八个面 / 找到过哪些 bug / 连零计到几", **白板审前提与所有历史外审的独立性从打包层就被破坏**(GPT 是否真去读 cc_context 不确定 → 结论不一定被污染, 但独立性保证没了)。修复 = `build_v80_single_win.py` 的 `EXCLUDED_DIR_NAMES` 加 `"cc_context"`。**外审只需项目源 (main.py / src / rules / specs / data)**。要给 GPT 导航地图须**单独显式加白名单**(且剥掉 god_nodes 等引导成分, 见 [[graphify-codegraph]])。
