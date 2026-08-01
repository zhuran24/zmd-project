# Project Memory Export

Generated from `cc_memory/memory.db`. Do not hand-edit this file; run `python cc_memory/mem.py export`.

Fresh session:

```bash
python cc_memory/mem.py boot
```

## Stats

- facts: 4
- entries: 11
- hard edges: 7
- pending relation suggestions: 3

## Start Here

- `cc-memory-meta-index` — cc_memory meta-index: PINNED/RULE, 读写纪律/关系/检索/git/hooks 入口。
- `memory-runtime-protocol` — 新会话 boot;查询 search/read --body/--semantic;改记忆 impact/read → set-fact/add-entry --force(订正)/ supersede(真取代)→ finalize…

## Active Facts

- `fact-generated-memory-md-is-view` — cc_memory/exports/MEMORY.md 由 memory.db 生成, 可删可重建, 禁止手改当真相源。
- `fact-hard-edge-soft-link-separation` — DEPENDS_ON/DERIVED_FROM/SUPERSEDES/CONTRADICTS 是硬边触发传播; MENTIONS/RELATED_TO/SUPPORTS 只帮助检索和阅读。
- `fact-impact-before-memory-change` — 改 fact 或 entry 前先跑 impact/read, 只重写硬依赖影响面。
- `fact-single-source-memory-db` — cc_memory/memory.db 是唯一活记忆真相; Markdown exports 和 archive 都不是源状态。

## Entries

- `batch-c-execution-day-20260713` — cf76bed/34cb0aa/9deec8f 三批打通判定基建;probe_8/9/10 三 cell.json:A/B 逐位等价 wall+0.48%、复跑逐位复现 wall+0.20%;§1b 扫描落空;矩阵 5h 可完;cap vs 穷尽判据=新拍板项
- `batch-c-f6-binding-routing-enum-loop` — probe_6/7 定案:binding 秒解→routing precheck 拒→add_nogood 重解的枚举循环,~1轮/s 数千轮未收敛;FIXED_SEARCH/编排慢/presolve 三假说证伪;cf76bed 注入修复有效但对时长无救;触发正地方=frontier 难点
- `batch-c-kickoff-findings-20260713` — 批C(PIC-4/5+门6)开工实录:binding 无段级帽+FIXED_SEARCH 锁死并行等五发现;组织性触发仍未判定;owner 目标无退路口径+替代进攻路线盘点指针
- `batch-c-leftover-day-20260714` — 门6 prod 演习揭示共享 snapshot 构建(F1 投影 coercions=False)在 frozen 数据 int orientation 上 raise→prod 整条 attach fail-closed(所有族含 power),不止 F1/F6;新增 prod 形态适配批插 B6 前…
- `codex-needs-explicit-read-memory` — Codex 记忆 2026-06: RULE, 子代理不会自动读 CLAUDE/cc_memory, 提示词要写明。
- `cut-framework-stage-b-current-20260712` — 07-12 文档实态外审 F12 消解:F1/F6/F7=COMPILABLE typed 链唯一写 master;F5=ShadowValidated 无 lowering(真 adapter verifier 前 fail-closed);F2/F3/F4/F9=LEGACY_DIAGNOSTIC…
- `p1-3-batch1-m5-current-20260712` — 07-12 文档实态外审 F12 消解:Batch1 完成、C1 默认、首解存在性关闭、M5 默认参数病态证伪(smoke#4 死于旧内存条款,~60G 固有尖峰);单跑铁律保留;不要再申请 owner 拍板或把性能当可行性 blocker
- `test-lane-current-20260712` — 取代 07-04 提速条目的快照数字(5.5min/slow 19/60 sinks 已过时);批次 commit 的 cuts N 都是当时快照;慢 lane 解释器 flake SOP=pytest-forked,xdist 禁用
