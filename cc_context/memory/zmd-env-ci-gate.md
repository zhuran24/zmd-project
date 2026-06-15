---
name: zmd-env-ci-gate
index_summary: "CI=GitHub Actions project-foundation gate,每次 push 跑 preflight_gate.py --ci(17 项)失败给 owner 发邮件;落地前必本地跑同款全绿;pytest 盖不到三类:frozen-artifact hash/LF 行尾政策/记忆树死链"
description: zmd CI=GitHub Actions project-foundation gate, 每次 push 跑 preflight_gate.py --ci(17 项)失败给 owner 发邮件(频繁 push 红一次=邮件轰炸);落地前必本地跑同款全绿;pytest 盖不到三类:frozen-artifact hash/LF 行尾政策/记忆树死链
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

> 事实依据: [[fact-forcing-function-required]]

- **CI = GitHub Actions `project-foundation` gate**:每次 push(main/project-foundation 分支)跑 `python scripts/preflight_gate.py --ci`(17 项),失败给 owner 发邮件——push 频繁时红一次就是邮件轰炸(V80 落地实测几十封)。**任何落地(尤其外发委托交付)commit 前必须本地跑同款命令全绿**;pytest 盖不到其中三类:frozen-artifact hash(`preflight_gate.py::FROZEN_ARTIFACTS`,改 canonical_rules 必须同批推进 sha256)、LF 行尾政策(`data/line_ending_policy.json`)、记忆树死链(删 memory 节点必须同时清全树 wikilink 引用)。

- **CI 没有外置大工件 `candidate_placements.json`(45.8MB gitignored)→ 读真 candidate 的新测试在 CI 必红、本地 pre-push 却绿(本地有该文件)= 隐形 email-bomb 源**(2026-06-15 实测: binding 回归测试读真 candidate 害 CI 连红 3 个 commit)。新测试要 candidate 必须先 `if not candidate_path.exists(): pytest.skip(...)`(项目对外置工件标准处理)或自写 fake candidate 进 tmp;pre-push gate 漏这类是因本地有 candidate。**外发委托交付的 .py 测试入库前, 凡 read `data/preprocessed/candidate_placements.json` 的一律加 skip-if-absent 守卫。**

相关:[[zmd-checkout-env]] [[zmd-env-email-bomb]] [[zmd-env-prepush-gate]]
