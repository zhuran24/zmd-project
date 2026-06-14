---
name: no-gpt-packaging-rules
description: "外发 GPT 的打包规则:除缓存文件外全项目打(build_v80_single_win.py);r7 纪律=用 git worktree 干净树打+复制成 sha 前缀唯一名防并发覆盖+交付前 Get-FileHash 核对;老审查打包规范(no-priming/7-section/armor/7z)已全废"
metadata:
  node_type: memory
  type: feedback
---

**打包规则(唯一存留):除缓存文件外全项目打**(排除 .git/__pycache__/.pytest_*/.ruff_cache/.venv/.upstream_clones/*.pyc/输出 zip/prompt 文件/`補丁包/`(包套娃))。build 脚本在 `cc_context/review/build_v80_single_win.py`(单包,自包含,gpt_dispatch --pack 调用它;分卷版已归档 review/archive/)。**打包纪律 (r7 教训)**: ① build 脚本固定输出同名 zip, 多会话共用工作区会被并发覆盖 (sha 漂了险些传错包) → **每轮包用 `git worktree add --detach <tmp> HEAD` 的干净树打 + 立刻复制成 sha 前缀唯一名** (如 `zmd_r7_snapshot_<sha8>.zip`), prompt 只指认唯一名; ② 干净树打的副产品 = 不混入脏 WIP 和未跟踪历史归档 (裸 pytest 误收集杂物源), 包从 ~18MB 降 ~12MB; ③ **交付前最后一步重新 `Get-FileHash` 核对 = prompt 里的 sha**。**老的审查打包规范(no-priming/7-section prompt 模板/armor/7z 策略等)2026-06-10 全部废除**,备份在 `cc_context/memory_archive/` 与 `cc_context/review/archive/`。给 GPT 的 prompt 直接讲任务+约束+交付物即可。
