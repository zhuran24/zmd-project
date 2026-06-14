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

母节点 [[gpt-delivery-no-blind-trust]]。
