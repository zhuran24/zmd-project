---
name: gpt-delivery-probe-discrimination
description: "验收 GPT/owner 补丁时 probe 可能不判别(toy 走 INFEASIBLE 不碰权威路径,patched/unpatched 同结果)——判别手段:git stash 对比(unpatched FAIL/patched PASS),或更干净的 git apply --include 只打 test hunk 跑红→再 --include 打 src fix 跑绿,一条龙红→绿双证 finding 真实+补丁有效"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

验收外发补丁(GPT 或 owner)时,**reviewer 的 probe 可能根本不判别**——patched 和 unpatched 返回同样结果,无法坐实 finding 真实或补丁有效。这时必须换更硬的判别手段。

**为何会不判别(V97 实测)**:本地 toy 用 INFEASIBLE 场景,根本不走 CERTIFIED 的权威路径,patched/unpatched 返回同样结果。

**判别手段(从简到精)**:

- **git stash 对比**:`git stash push <补丁动的 src 文件>` 跑 reviewer 回归确认 unpatched **FAIL**、pop 后 patched **PASS**,才坐实 finding 真实 + 补丁有效。

- **git apply --include 红→绿(比 stash 更干净, 2026-06-14 face 6/8 实证)**:`git apply --include='src/tests/*' p` 只打 test hunk → 跑红复现 finding → `git apply --include='src/<srcdir>/*' p` 再打 src fix → 跑绿。一条龙红→绿双证 finding 真实 + 补丁有效。

**GPT probe 硬编码路径坑**:GPT probe 常硬编码 Linux 路径(`/mnt/data`),在 Windows 崩在 print/relative_to 行——但核心逻辑在崩之前已执行,看崩之前的输出或改用本地路径重写。

母节点 [[gpt-delivery-no-blind-trust]]。
