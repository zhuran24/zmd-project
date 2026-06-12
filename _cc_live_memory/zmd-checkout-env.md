---
name: zmd-checkout-env
description: zmd 当前 Windows checkout 的环境事实——无 venv 用全局 Python、commit 即 push、大文件外置
metadata: 
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

zmd 项目当前环境(2026-06-10 盘点,接手自 Codex):

- 工作区 `C:\claude pj\zmd_pj` 是轻量 GitHub checkout(zhuran24/zmd,分支 project-foundation)。**旧 `D:\追光\zmd` 已不存在**,CC 旧记忆里的 D 盘路径全部失效。
- **无 `.venv`** — 用全局 Store Python 3.13(直接 `python`),依赖已装全(ortools 9.15.6755 匹配项目要求)。
- **坑(2026-06-12 实测踩过): Store Python 会半夜自动升级并弄坏 `python` alias** —— 3.13.13→3.13.14 升级后 `python`/`python.exe` 执行别名静默失败(无输出 exit 49/9009,会话中途突然挂),但 **`python3.13.exe` alias 是好的**(完整 AppX 上下文, user site-packages/ruff/pytest 全正常)。修法: 改用 `python3.13` 跑一切;或等重启自愈。别用「真身 exe + PYTHONPATH」组合——pytest-randomly/ruff shim 在那条路上断。**连带症状**: pre-commit hook 内部调 `python` 的检查会静默失败并误报 (实测 commit 时报 "authoritative_numbers.json STALE" 但 `python3.13 scripts/gen_authoritative_numbers.py --check` = up to date, 焊死的 currency 测试也绿)——alias 坏掉期间 hook 的 WARN 先用 python3.13 复核再信。
- **坑(实测踩过):** PowerShell 里 `& ".venv\Scripts\python.exe" xxx; Write-Host "exit: $LASTEXITCODE"` 这种写法,venv 不存在时 `&` 失败但 Write-Host 把整条命令洗成 exit 0,看起来像通过。**判断"脚本通过"必须看到脚本自己的输出**(如 "P1.2 proof obligation check passed"),不能只看 exit code。
- **post-commit hook 自动 push GitHub** — commit ≈ 发布到远程,提交前要想清楚。推送历史在 `.git/auto-push.log`。
- `data/preprocessed/candidate_placements.json`(certified exact 必需输入)**已就位且随时可再生 (2026-06-12 wireless 修复后)**: 本地树有 (45,773,799B, sha `adcc2a6e…`), 被 .gitignore (外置策略持久化, 防 add -A 误推 45MB); 丢了用 `python3.13 src/placement/placement_generator.py` 现场再生 (~3s, 双机验证 bit 级确定性)。**旧 53.6MB/`d5e3911f…` 版本已 superseded**——zmd.7z 老归档里的是带病旧版, 不可作恢复源; campaign resume 撞旧 hash 会 fail-closed (by design)。
- `补丁包/` 目录(仓库根)= Codex 接手期 v29→v78 的外审包/补丁存放处,zip/7z 被 gitignore;`最近补丁审查情况.txt` 是 0 字节空文件。
- **全量 pytest 必须独占跑**:pytest.ini 配 `--basetemp=.pytest_tmp` 在仓库根,多个 pytest 进程并发(如审查 agent 同时跑测试)会互删对方临时目录 → Windows 上随机出现 FileExistsError / setup ERROR / "顺序依赖失败"假象。跑全量前确认没有并发 agent 在跑测试,必要时先删 `.pytest_tmp`。
- **全量加速跑法(已验证失败集与串行一致)**:`python -m pytest src/tests/ -q -p no:randomly -n 8 --dist loadfile --basetemp="$env:TEMP\zmd_pytest"` —— xdist 8 worker 并行 ~85s(串行 ~7min),独立 basetemp 顺便防并发污染。已写进项目 CLAUDE.md Commands 段。
- **全量测试基线 = 全绿 (2026-06-12 wireless 修复 fbb0466 起, 项目史上首次)**: 2900 passed / 74 skipped / 0 failed (xdist ~97s)。旧「约 20 个环境性失败」清单 (test_binding 10E + test_regression 5 + test_routing 3 + …) **已作废**——根因是工件外置, 现工件回树后全转绿。**今后任何 failed 都是真问题, 没有豁免名单。**
- **CI = GitHub Actions `project-foundation` gate**:每次 push(main/project-foundation 分支)跑 `python scripts/preflight_gate.py --ci`(17 项),失败给 owner 发邮件——push 频繁时红一次就是邮件轰炸(V80 落地实测几十封)。**任何落地(尤其外发委托交付)commit 前必须本地跑同款命令全绿**;pytest 盖不到其中三类:frozen-artifact hash(`preflight_gate.py::FROZEN_ARTIFACTS`,改 canonical_rules 必须同批推进 sha256)、LF 行尾政策(`data/line_ending_policy.json`)、记忆树死链(删 memory 节点必须同时清全树 wikilink 引用)。
- **邮件轰炸第二次发生 (2026-06-12, 35 封, 根因复盘)**: 06-11 21:02Z 归档 GPT r1 审查 probe (`cc_context/review/*_probe.py`) 原样入库带 9 个 ruff error → 之后 **23 个 push 连红** (每红一封邮件), 整夜无人察觉, 直到 owner 翻邮箱。三层教训缺一不可: ① **gate 的 ruff 扫全仓含 `cc_context/`** —— 归档 GPT 交付里的 .py (probe 等) 不是"只读工件豁免区", 入库前必 `python3.13 -m ruff check <file>` (GPT probe 风格默认是脏的); ② **"纯文档/归档/handoff 盖章" commit 不豁免 preflight** —— 恰恰是这类"感觉安全"的 commit 引爆的; ③ **本地零拦截链**: pre-commit hook 只做 memory 同步(fail-soft 不 lint), post-commit 自动 push → 唯一 lint gate 在 CI 侧, 所以 **每次 push 后(至少每个工作段落一次) `gh run list -L 1` 回看一眼结论**, 红了立刻修——CI 反馈只进 owner 邮箱, CC 不主动查就永远不知道。修复 commit `4390b38` (probe 风格修复, run 27385921347 转绿)。

相关:[[zmd-project-entry]]
