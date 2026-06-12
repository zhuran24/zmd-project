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
- **无 `.venv`** — **主环境(2026-06-12 起) = `C:\Program Files\Python313\` 的 python.org 3.13.14(`python`,无自动更新)**,依赖从商店版 `pip freeze` 经 TUNA 镜像 `--no-deps` 全量克隆(249 包,ortools 9.15.6755;克隆当天全量 pytest 2923 绿)。**已知良性不一致**: litellm 钉 `jsonschema==4.23.0` 但实装 4.25.1(与源环境一致)——pip 解析器会因此 ResolutionImpossible,**克隆/批量补装必须 `--no-deps`**。商店版(`python3.13`)保留作备份,此后不再保证同步;装新依赖默认进主环境。git hooks(pre-push/pre-commit)解释器优先级已翻成 `python` 优先。
- **坑(2026-06-12 实测踩过): Store Python 会半夜自动升级并弄坏 `python` alias** —— 3.13.13→3.13.14 升级后 `python`/`python.exe` 执行别名静默失败(无输出 exit 49/9009,会话中途突然挂),但 **`python3.13.exe` alias 是好的**(完整 AppX 上下文, user site-packages/ruff/pytest 全正常)。修法: 改用 `python3.13` 跑一切;或等重启自愈。**结局(06-12 晚收口)**: owner 为摆脱商店自动更新装了 python.org 3.13.14 到 Program Files 并设为默认(起初忘装包,`python` 一度 ModuleNotFoundError);已 `pip freeze --no-deps` 克隆补齐并验证全绿,**现在 `python` = 主环境**(见上),商店版降为备份。商店自动更新再坏也只伤备份,不用专门关。别用「真身 exe + PYTHONPATH」组合——pytest-randomly/ruff shim 在那条路上断。**连带症状**: pre-commit hook 内部调 `python` 的检查会静默失败并误报 (实测 commit 时报 "authoritative_numbers.json STALE" 但 `python3.13 scripts/gen_authoritative_numbers.py --check` = up to date, 焊死的 currency 测试也绿)——alias 坏掉期间 hook 的 WARN 先用 python3.13 复核再信。
- **坑(实测踩过):** PowerShell 里 `& ".venv\Scripts\python.exe" xxx; Write-Host "exit: $LASTEXITCODE"` 这种写法,venv 不存在时 `&` 失败但 Write-Host 把整条命令洗成 exit 0,看起来像通过。**判断"脚本通过"必须看到脚本自己的输出**(如 "P1.2 proof obligation check passed"),不能只看 exit code。
- **post-commit hook 自动 push GitHub** — commit ≈ 发布到远程,提交前要想清楚。推送历史在 `.git/auto-push.log`。
- **pre-commit memory sync 时序坑 (2026-06-13 实测)**: pre-commit hook 的 instances/memory sync 把 harness 侧记忆新内容写进 repo 工作树**发生在 staging 之后** → commit 收的是 add 时的旧版, sync 写的新内容留在工作树未暂存; 若恰好只写了一边镜像, pre-push gate 会报 `live mirror byte drift: MEMORY.md` BLOCK。处置 = 看工作树残余 diff (通常是 handoff description/MEMORY.md 索引行的 harness 同步), 内容正当就补一个 chore commit 收掉再推。commit 后工作树有 memory 文件残余不是异常, 是该 hook 的固有时序。
- `data/preprocessed/candidate_placements.json`(certified exact 必需输入)**已就位且随时可再生 (2026-06-12 wireless 修复后)**: 本地树有 (45,773,799B, sha `adcc2a6e…`), 被 .gitignore (外置策略持久化, 防 add -A 误推 45MB); 丢了用 `python3.13 src/placement/placement_generator.py` 现场再生 (~3s, 双机验证 bit 级确定性)。**旧 53.6MB/`d5e3911f…` 版本已 superseded**——zmd.7z 老归档里的是带病旧版, 不可作恢复源; campaign resume 撞旧 hash 会 fail-closed (by design)。
- `补丁包/` 目录(仓库根)= Codex 接手期 v29→v78 的外审包/补丁存放处,zip/7z 被 gitignore;`最近补丁审查情况.txt` 是 0 字节空文件。
- **全量 pytest 必须独占跑**:pytest.ini 配 `--basetemp=.pytest_tmp` 在仓库根,多个 pytest 进程并发(如审查 agent 同时跑测试)会互删对方临时目录 → Windows 上随机出现 FileExistsError / setup ERROR / "顺序依赖失败"假象。跑全量前确认没有并发 agent 在跑测试,必要时先删 `.pytest_tmp`。
- **全量加速跑法(已验证失败集与串行一致)**:`python -m pytest src/tests/ -q -p no:randomly -n 8 --dist loadfile --basetemp="$env:TEMP\zmd_pytest"` —— xdist 8 worker 并行 ~85s(串行 ~7min),独立 basetemp 顺便防并发污染。已写进项目 CLAUDE.md Commands 段。
- **全量测试基线 = 全绿 (2026-06-12 wireless 修复 fbb0466 起, 项目史上首次; 当时 2900 passed)**: 0 failed / 74 skipped (xdist ~2min)。**passed 数随修复回归滚动上涨 (06-13 凌晨已 2967), 当前精确值以台账 `cc_context/review/p1_2_closure_evidence.md` 头部与 handoff 最新 stamp 为准, 别引用本条的历史数**。旧「约 20 个环境性失败」清单已作废——根因是工件外置, 现工件回树后全转绿。**今后任何 failed 都是真问题, 没有豁免名单。**
- **CI = GitHub Actions `project-foundation` gate**:每次 push(main/project-foundation 分支)跑 `python scripts/preflight_gate.py --ci`(17 项),失败给 owner 发邮件——push 频繁时红一次就是邮件轰炸(V80 落地实测几十封)。**任何落地(尤其外发委托交付)commit 前必须本地跑同款命令全绿**;pytest 盖不到其中三类:frozen-artifact hash(`preflight_gate.py::FROZEN_ARTIFACTS`,改 canonical_rules 必须同批推进 sha256)、LF 行尾政策(`data/line_ending_policy.json`)、记忆树死链(删 memory 节点必须同时清全树 wikilink 引用)。
- **邮件轰炸第二次发生 (2026-06-12, 35 封, 根因复盘)**: 06-11 21:02Z 归档 GPT r1 审查 probe (`cc_context/review/*_probe.py`) 原样入库带 9 个 ruff error → 之后 **23 个 push 连红** (每红一封邮件), 整夜无人察觉, 直到 owner 翻邮箱。三层教训缺一不可: ① **gate 的 ruff 扫全仓含 `cc_context/`** —— 归档 GPT 交付里的 .py (probe 等) 不是"只读工件豁免区", 入库前必 `python3.13 -m ruff check <file>` (GPT probe 风格默认是脏的); ② **"纯文档/归档/handoff 盖章" commit 不豁免 preflight** —— 恰恰是这类"感觉安全"的 commit 引爆的; ③ **本地零拦截链**: pre-commit hook 只做 memory 同步(fail-soft 不 lint), post-commit 自动 push → 唯一 lint gate 在 CI 侧, 所以 **每次 push 后(至少每个工作段落一次) `gh run list -L 1` 回看一眼结论**, 红了立刻修——CI 反馈只进 owner 邮箱, CC 不主动查就永远不知道。修复 commit `4390b38` (probe 风格修复, run 27385921347 转绿)。
- **机械门禁已装 (2026-06-12, 一劳永逸层, owner 问"怎么保证不再犯"的答案)**: `.git/hooks/pre-push` (机器专属不入库) 强制跑 `preflight_gate.py --hook` (20 项 ≈20s), 任一 BLOCK 就物理挡掉 push (commit 留本地, 修好重推自动补齐); 逃生口 `ZMD_SKIP_PUSH_GATE=1 git push origin HEAD` (紧急用)。同时 post-commit auto-push 改成失败时控制台大声报 + tail `auto-push.log` (原版 `2>&1` 全吞进 log = 可见性黑洞本洞)。**装机坑**: hook 里注入 `PYTEST_ADDOPTS` 隔离 basetemp 时, Windows 反斜杠路径会被 pytest 的 shlex 解析当转义符吃掉 (实测 71 errors), 必须 `tr '\\' '/'` 转正斜杠。**残余敞口(诚实边界)**: ① 检的是工作树近似, 不是被推 commit 的快照——双线程共用 checkout 时另一线程脏 WIP 可能误挡 (误挡是响的, 无害); ② `--hook` 与 CI `--ci` 的 diff-range 类检查可能有范围差; ③ 换机/重 clone 后 hook 不在, 按本条手动重装。`gh run list -L 1` push 后回看降级为兜底纪律。

相关:[[zmd-project-entry]]
