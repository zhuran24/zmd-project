---
name: gpt-delivery-owner-patch-and-severity
description: "owner 亲发的 patch 同样不裸信、走全验收(2026-06-14 owner 发的 generic_io loader 补丁原样破 166 测试,删了共用 loader 的空需求早退,需收窄为保留早退+仅非空 input 才校验);pre-push mypy gate(preflight_gate [15/17])守 4 文件挡 GPT 的 Optional[str] 雷,ruff 不查类型;严重度自判:availability(漏声明→false-INFEASIBLE 保守失败)≠ soundness(false-CERTIFIED),P1.2 闭环只认后者,availability 标 LOW 加固"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

**owner 通道补丁同样不裸信 + 严重度自判 (2026-06-14 face 6/8 double Pro 验收):**

- **owner 发的 ≠ 对的, 同样走全验收**: double Pro 里 **owner 亲发的 patch (F-BIND-R8-02 generic_io loader 完整性) 原样破 166 测试**——它删了 loader 的空需求早退, 而该 loader 被 master + 大量空需求 toy/test 共用; CC 收窄为「保留早退 + 仅非空 input 才校验」, 全量 3048 绿才合。

- **probe 对比升级 (比 stash 更干净)**: `git apply --include='src/tests/*' p` 只打 test hunk → 跑红复现 finding → `git apply --include='src/<srcdir>/*' p` 再打 src fix → 跑绿, 一条龙红→绿双证 finding 真实 + 补丁有效。(详见 [[gpt-delivery-probe-discrimination]])

- **pre-push mypy gate**: `scripts/preflight_gate.py [15/17]` mypy 守 4 文件 (cut_manager / power_placement_subproblem / master_model / benders_loop), **ruff 不查类型**, GPT 的 `Optional[str]` 雷只有它能挡 (commit 被挡在本地, 修完才 push)。

- **严重度自判**: GPT/owner 标 HIGH 的可能只是 availability (漏声明 → false-INFEASIBLE 保守失败) 而非 soundness (false-CERTIFIED); P1.2 soundness 闭环只认后者, 前者标 LOW 加固。

- **GPT 严重度自评系统性偏高, 必须独立核 reachability 才采信 (2026-06-15 去偏置白板审实证, 本会话最大技术教训)**: 去偏置白板审 8 面挖出 3 条 finding, GPT 自评 **CRITICAL / HIGH / HIGH**; 3 个独立对抗 agent 静态核验**全部下修为 conditional/hardening —— 没一条在 canonical+默认 env 可达 live false-CERTIFIED**(binding: solution 键与 master `source_instances` 同源、缺失实例只有 hand-built / 破哈希门畸形工件能造; benders: 所有 conflict id 与 solution 同源、silent-drop 分支真实路径打不到; preprocess: 当前 utility_operations key 与 17 个 recipe id 交集空)。**我先信了 GPT 的 CRITICAL/HIGH、当场跟 owner 说「P1.2 闭合彻底不成立、certified 路径有真 false-CERTIFIED」, 之后被对抗核验打脸、当场收回。** 教训: **GPT 的 severity 自评只标「后果档」(若触发有多严重)、不标「可达性」(canonical+默认 env 到底能不能走到), 于是几乎总把 conditional/hardening 报成 CRITICAL/HIGH。采信前必须独立核「真实路径能不能走到」(数据按构造自洽吗? id 同源吗? 交集空吗?)。没这道 reachability 对抗核, 就会把 hardening 当 live false-CERTIFIED 误落进 certified 源、还误报闭合崩。** 落地时严重度据实下修记 LOCK(本轮 F-BIND-BS-01/F-BL-BS-01/H-PRE-BS-01 都标 conditional/hardening + 写明「GPT 自评 X → 对抗核验下修」)。见 [[fact-self-report-is-not-evidence]] [[fact-zero-finding-is-not-proof]]。

母节点 [[gpt-delivery-no-blind-trust]]。
