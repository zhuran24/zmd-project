---
id: codegraph-before-grep
kind: decision
title: 符号导航先用 CodeGraph 再 grep/read
summary: 做符号查找、调用链、caller/callee 或影响面定位前，先检查并使用 CodeGraph；它是导航缓存，不是证明证据。
scope:
  domains: [code-navigation, symbol-lookup]
  paths: []
  symbols: [codegraph]
status: active
priority: P1
triggers:
  intents: [symbol-lookup, call-chain-tracing, caller-callee-analysis, impact-analysis, code-navigation]
  keywords: [CodeGraph, codegraph, 符号查找, 调用链, caller, callee, impact, grep, read, rg]
  negative_keywords: []
  paths: [.codegraph/]
  symbols: [codegraph]
  error_regex: []
  examples:
    - 先找一下这个函数在哪里被调用
    - 我要追一下 outer_search 到 supervisor_seal 的调用链
    - 改这个 symbol 前先看影响面和 callers
activation:
  layer_hint: L1
  must_know: true
  reason: 符号导航直接 grep/read 容易漏掉调用关系和影响面。
provenance:
  op: record
  reason: 从 CLAUDE.md CodeGraph 规则和旧记忆 use-codegraph-before-grep 提炼为主动路由提醒。
  evidence:
    - "CLAUDE.md CodeGraph code index section"
    - "python cc_memory/mem.py read use-codegraph-before-grep --body"
updated_at: "2026-06-26"
---
做符号查找、调用链追踪、caller/callee 检查或 impact 定位时，第一步先看 CodeGraph，而不是默认开大范围 `grep`、`rg`、逐文件 read，或直接派 agent 扫代码。先运行 `codegraph status .` 判断当前 checkout 是否有可用索引；索引存在时优先用 CodeGraph 的 explore/node/callers 能力拿结构化结果，再决定是否需要补充源文件读取。

如果索引过期，用 `codegraph sync .` 刷新；如果本 checkout 需要重建索引，再按项目规则使用 `codegraph init .`。Codex 启动后如果看不到 CodeGraph MCP 工具，可以重启 agent 或退回 shell 命令形式。`.codegraph/` 是 git 忽略的可再生导航缓存，不要把它当成协作记忆、证明证据或可替代 `PROJECT_LOCK.md`、源码审阅、测试和 gate 的权威来源。

这张卡的边界是代码导航：它提醒"先用 CodeGraph 定位结构"，不是禁止 grep/read。CodeGraph 给出候选符号、调用路径和影响面后，涉及精确行为、证明边界、冻结输入或发布结论时，仍要回到源码、项目锁、测试和相关 preflight 结果做最终判断。
