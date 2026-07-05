---
id: concurrent-session-shared-index-hazard
kind: pitfall
title: 并发会话共享 git index 的提交风险
summary: 本 repo 常有并发会话共享同一工作区和 .git/index；提交前必须看 status，提交只带自己的 pathspec——既别多扫进别人 staged 的，也别漏提 pins/钉死表依赖的文件（reseal 提交要覆盖完整一致集，否则 CI close-kernel 逮 source-hash drift）。
scope:
  domains:
    - git-concurrency
    - workspace-hygiene
  paths:
    - .git/index
    - cc_memory/memory.db
  symbols:
    - git_commit_pathspec
    - shared_index_hazard
status: active
priority: P0
error_regex:
  - "\\$ [^\\n]*git[\\s\\S]{0,800}index\\.lock"
triggers:
  intents:
    - git-commit
    - workspace-hygiene
  keywords:
    - git status
    - git commit
    - pathspec
    - 暂存
    - 并发会话
    - shared index
    - memory.db
  negative_keywords: []
  paths:
    - .git/index
    - cc_memory/memory.db
  symbols:
    - git_commit_pathspec
    - shared_index_hazard
  error_regex:
    - "index\\.lock"
    - "shared index"
  examples:
    - 准备提交当前修复但工作区有别的会话改动
    - 为什么不能 git commit -m 不带 pathspec
activation:
  layer_hint: L0
  session_start_l0: true
  must_know: true
  reason: 提交风险会把别的会话改动扫进当前提交；git 操作是回合中途自发衍生的典型动作，prompt 召回逮不到，升常驻（recall-trigger 讨论 resident-design 席「最该常驻」裁决，2026-07-03 落地）。
provenance:
  op: record
  reason: 从旧 cc_memory fact concurrent-session-shared-index-hazard-20260617 提炼。
  evidence:
    - python cc_memory/mem.py read concurrent-session-shared-index-hazard-20260617 --body
    - design/recall-trigger-discussion-20260628.md §3.2 resident-design 席三卡裁决
updated_at: "2026-07-06"
---
这个仓库经常有多个会话共用同一工作区和同一个 `.git/index`。另一个会话 `git add/rm` 的文件可能已经在共享 index 里；如果当前会话直接 `git commit -m ...`，会把别人 staged 的核心文件一起提交。

铁律：提交前重新看 `git status --short`、`git diff --stat` 和 staged 路径；只用带明确 pathspec 的提交命令提交自己负责的文件。涉及 `cc_memory/memory.db` 尤其要局部提交。

**hook 强制层已改为条件生效（owner 2026-07-06 指令）**：`pre_tool_risk_gate.py` 的并发形状（git-add-broad / git-commit-all / git-commit-no-pathspec / git-push-force / rm-rf / remove-item-recurse-force）现在只在检测到多个 CC 会话时拦（CLI 进程计数 + 本项目 transcript 近 30min 活跃探针；检测异常按多会话 fail-safe）。所以**单会话环境 hook 不拦 ≠ 纪律失效**——机器判定单会话时冲突对象不存在，`git add -A` 等才被放行；一旦多会话，拦截照旧。frozen-artifact-write 与并发无关，任何时候都拦。

**对偶坑（2026-06-28 PR2-b 实证）：pathspec 不仅别多扫、也别漏。** 显式 pathspec 提交 reseal/close-kernel 类改动时，若 pins 引用的被修改文件未一并提交，就会出现提交树里 pins 期望新 sha、文件仍是旧版，CI close-kernel checker 报 source-hash drift（本地 `--full` 读磁盘工作树会过、CI 读已提交树才挂）。所以 pathspec 要【精确等于】这次逻辑改动的完整一致集：用 `git status` 枚举所有相关 `M`（尤其建在别会话未提交改动之上时），push 前核对 `git show HEAD:<file>` 的 sha = 钉死表期望值。详 cc_memory `pathspec-must-cover-full-reseal-set`。
