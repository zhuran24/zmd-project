---
id: concurrent-session-untracked-file-wipe
kind: pitfall
title: 共享工作区里新写的 untracked 文件可能被并发会话清掉——目录级新工作先在仓库外做,经 worktree 以 tracked 提交落库
summary: 2026-07-05 实测——在共享工作区新建 formal/(5 个文件,lakefile/toolchain/lean 源)后几分钟内,除最后写的 1 个文件外全部消失;当时并发主线会话正在热改 src/search(工作树 dirty)。机制未坐实(推测=并发会话的清理动作,git clean 类),但防御规则独立于机制成立:**共享工作区中未提交(untracked)的文件随时可能消失,别在里面攒多步工作**。tracked 文件不受 git clean 影响,提交=安全。
scope:
  domains:
    - workflow
    - git
  paths: []
  symbols: []
status: active
priority: P1
error_regex:
  - "Could not find file"
  - "no configuration file with a supported extension"
triggers:
  intents:
    - create-new-directory-in-repo
    - multi-step-file-work
  keywords:
    - untracked
    - git clean
    - 消失
    - 文件不见
    - 并发会话
    - 新目录
    - worktree
  negative_keywords: []
  paths: []
  symbols: []
  error_regex:
    - "Could not find file .*claude pj"
    - "no configuration file"
  examples:
    - 刚写的文件怎么不见了
    - 要在仓库里建一个新目录做多步工作
activation:
  layer_hint: L1
  must_know: false
  reason: 在共享工作区新建文件/目录前该想起——多步工作(要 build/迭代的)先在仓库外私有目录做,完成后经临时 worktree 拷入+立即 add+commit(窗口秒级);单文件小改动也尽量写完即提交。
provenance:
  op: record
  reason: 2026-07-05 formal/ 初版被清事件;与 [[concurrent-session-shared-index-hazard]] 同根(共享工作区),但机制不同(那条是 staged 裹挟,这条是 untracked 消失)。
  evidence:
    - "时间线:formal/ 5 文件写于 lake build 前 ~4 分钟,build 报 no configuration file;Get-ChildItem 实测仅存最后写的 F5OrbitLift.lean;es 全盘无 lakefile.toml;同刻 git status 显示主线会话 3 个 M + 2 个新 ?? 在 src/search"
updated_at: "2026-07-05"
---
== 防御规则(按代价从低到高选)==
1. **单文件产物**:写完立刻 git add+commit(精确 pathspec),窗口秒级。
2. **目录级/要迭代 build 的工作**(如 Lean 项目、原型):在仓库外私有目录开发(例 `C:\Users\22957\zmd_formal_dev\`),完成后经临时 worktree(`C:\Users\22957\wt_main_tmp` 模式)拷入并提交——worktree 有独立 index,也顺带绕开 [[concurrent-session-shared-index-hazard]]。
3. 别假设"我刚写的还在":跨回合继续 untracked 工作前先 Test-Path。

== 已知边界 ==
- tracked 文件(含已 staged?)不被 git clean 碰;真正安全线=进了 commit。
- 事发时另一会话在跑 PR2 #1(热改 src/search 并新建 pr2_l0_*_core.py)——它自己的 untracked 新文件没消失,说明清理(若是清理)可能带路径过滤;别依赖这一点。
