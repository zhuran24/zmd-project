---
name: zmd-env-ci-gate
description: zmd CI=GitHub Actions project-foundation gate, 每次 push 跑 preflight_gate.py --ci(17 项)失败给 owner 发邮件(频繁 push 红一次=邮件轰炸);落地前必本地跑同款全绿;pytest 盖不到三类:frozen-artifact hash/LF 行尾政策/记忆树死链
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

> 事实依据: [[fact-forcing-function-required]]

- **CI = GitHub Actions `project-foundation` gate**:每次 push(main/project-foundation 分支)跑 `python scripts/preflight_gate.py --ci`(17 项),失败给 owner 发邮件——push 频繁时红一次就是邮件轰炸(V80 落地实测几十封)。**任何落地(尤其外发委托交付)commit 前必须本地跑同款命令全绿**;pytest 盖不到其中三类:frozen-artifact hash(`preflight_gate.py::FROZEN_ARTIFACTS`,改 canonical_rules 必须同批推进 sha256)、LF 行尾政策(`data/line_ending_policy.json`)、记忆树死链(删 memory 节点必须同时清全树 wikilink 引用)。

相关:[[zmd-checkout-env]] [[zmd-env-email-bomb]] [[zmd-env-prepush-gate]]
