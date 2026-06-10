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
- **无 `.venv`** — 用全局 Store Python 3.13.13(直接 `python`),依赖已装全(ortools 9.15.6755 匹配项目要求)。
- **坑(实测踩过):** PowerShell 里 `& ".venv\Scripts\python.exe" xxx; Write-Host "exit: $LASTEXITCODE"` 这种写法,venv 不存在时 `&` 失败但 Write-Host 把整条命令洗成 exit 0,看起来像通过。**判断"脚本通过"必须看到脚本自己的输出**(如 "P1.2 proof obligation check passed"),不能只看 exit code。
- **post-commit hook 自动 push GitHub** — commit ≈ 发布到远程,提交前要想清楚。推送历史在 `.git/auto-push.log`。
- `data/preprocessed/candidate_placements.json`(53.6MB,certified exact 必需输入)外置未恢复;恢复命令和 SHA256 见 START_HERE.md。轻量测试不需要它,certified 大跑前必须恢复。
- `补丁包/` 目录(仓库根)= Codex 接手期 v29→v78 的外审包/补丁存放处,zip/7z 被 gitignore;`最近补丁审查情况.txt` 是 0 字节空文件。
- **全量 pytest 必须独占跑**:pytest.ini 配 `--basetemp=.pytest_tmp` 在仓库根,多个 pytest 进程并发(如审查 agent 同时跑测试)会互删对方临时目录 → Windows 上随机出现 FileExistsError / setup ERROR / "顺序依赖失败"假象。跑全量前确认没有并发 agent 在跑测试,必要时先删 `.pytest_tmp`。
- **全量加速跑法(已验证失败集与串行一致)**:`python -m pytest src/tests/ -q -p no:randomly -n 8 --dist loadfile --basetemp="$env:TEMP\zmd_pytest"` —— xdist 8 worker 并行 ~85s(串行 ~7min),独立 basetemp 顺便防并发污染。已写进项目 CLAUDE.md Commands 段。
- 全量测试基线(2026-06-10 晚,V79 后独占跑;V80 后 2788 passed 失败集不变):约 20 个环境性失败(candidate_placements.json 53.6MB 外置未恢复 → test_binding 10 ERROR + test_regression 5 + test_routing 3 + test_master/preprocess_golden 等 FileNotFoundError),其余全绿。新环境跑出 fail 先对照环境性清单再判断是不是真回归。
- **CI = GitHub Actions `project-foundation` gate**:每次 push(main/project-foundation 分支)跑 `python scripts/preflight_gate.py --ci`(17 项),失败给 owner 发邮件——push 频繁时红一次就是邮件轰炸(V80 落地实测几十封)。**任何落地(尤其外发委托交付)commit 前必须本地跑同款命令全绿**;pytest 盖不到其中三类:frozen-artifact hash(`preflight_gate.py::FROZEN_ARTIFACTS`,改 canonical_rules 必须同批推进 sha256)、LF 行尾政策(`data/line_ending_policy.json`)、记忆树死链(删 memory 节点必须同时清全树 [[引用]])。

相关:[[zmd-project-entry]]
