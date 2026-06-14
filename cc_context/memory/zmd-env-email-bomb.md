---
name: zmd-env-email-bomb
description: zmd owner 邮件轰炸根因复盘——归档 GPT 审查 probe(cc_context/review/*_probe.py)带 ruff error 入库→连续 push 连红每红一封;三层教训:gate ruff 扫全仓含 cc_context 入库前必 ruff check、纯文档/归档 commit 不豁免 preflight、push 后 gh run list -L 1 回看
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

- **邮件轰炸第二次发生 (2026-06-12, 35 封, 根因复盘)**: 06-11 21:02Z 归档 GPT r1 审查 probe (`cc_context/review/*_probe.py`) 原样入库带 9 个 ruff error → 之后 **23 个 push 连红** (每红一封邮件), 整夜无人察觉, 直到 owner 翻邮箱。三层教训缺一不可: ① **gate 的 ruff 扫全仓含 `cc_context/`** —— 归档 GPT 交付里的 .py (probe 等) 不是"只读工件豁免区", 入库前必 `python3.13 -m ruff check <file>` (GPT probe 风格默认是脏的); ② **"纯文档/归档/handoff 盖章" commit 不豁免 preflight** —— 恰恰是这类"感觉安全"的 commit 引爆的; ③ **本地零拦截链**: pre-commit hook 只做 stamp + authoritative-check(fail-soft, 不 lint; 原 memory 镜像覆盖块 2026-06-14 已移除), post-commit 自动 push → 唯一 lint gate 在 CI 侧, 所以 **每次 push 后(至少每个工作段落一次) `gh run list -L 1` 回看一眼结论**, 红了立刻修——CI 反馈只进 owner 邮箱, CC 不主动查就永远不知道。修复 commit `4390b38` (probe 风格修复, run 27385921347 转绿)。

相关:[[zmd-checkout-env]] [[zmd-env-ci-gate]]
