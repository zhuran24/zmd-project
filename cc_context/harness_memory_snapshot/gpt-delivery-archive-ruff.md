---
name: gpt-delivery-archive-ruff
description: "把 GPT 交付的 .py 工件(probe/脚本)原样归档进仓库前必须先 python3.13 -m ruff check——CI preflight 的 ruff 扫全仓含 cc_context/review/,归档不是豁免区;实测 r1 probe 原样入库 9 个 ruff error → 23 个 push 连红 → owner 收 35 封失败邮件;归档/盖章类 commit 同样走 preflight"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

**归档纪律 (2026-06-12 邮件轰炸教训)**: 把 GPT 交付的 .py 工件 (probe/脚本) **原样归档进仓库前必须 `python3.13 -m ruff check`** —— CI preflight 的 ruff 扫全仓含 `cc_context/review/`, 归档不是豁免区。r1 probe 原样入库 9 个 ruff error → 23 个 push 连红 → owner 收 35 封失败邮件 (修复 `4390b38`)。归档/盖章类 commit 同样要走 preflight, 详见 [[zmd-checkout-env]]。

母节点 [[gpt-delivery-no-blind-trust]]。
