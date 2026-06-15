---
name: zmd-env-prepush-gate
index_summary: ".git/hooks/pre-push(机器专属不入库)强制跑 preflight_gate.py --hook(20 项 ≈20s)BLOCK 就物理挡 push,逃生口 ZMD_SKIP_PUSH_GATE=1;装机坑 PYTEST_ADDOPTS 反斜杠被 shlex 吃掉必 tr 转正斜杠"
description: zmd 机械门禁——.git/hooks/pre-push(机器专属不入库)强制跑 preflight_gate.py --hook(20 项 ≈20s)BLOCK 就物理挡 push, 逃生口 ZMD_SKIP_PUSH_GATE=1;装机坑 PYTEST_ADDOPTS 反斜杠被 shlex 吃掉必 tr 转正斜杠;残余敞口=查工作树近似/换机要手动重装
metadata:
  node_type: memory
  type: project
  originSessionId: 01ce64d2-c550-4722-ba4f-1042a3935678
---

> 事实依据: [[fact-forcing-function-required]]

- **机械门禁已装 (2026-06-12, 一劳永逸层, owner 问"怎么保证不再犯"的答案)**: `.git/hooks/pre-push` (机器专属不入库) 强制跑 `preflight_gate.py --hook` (20 项 ≈20s), 任一 BLOCK 就物理挡掉 push (commit 留本地, 修好重推自动补齐); 逃生口 `ZMD_SKIP_PUSH_GATE=1 git push origin HEAD` (紧急用)。同时 post-commit auto-push 改成失败时控制台大声报 + tail `auto-push.log` (原版 `2>&1` 全吞进 log = 可见性黑洞本洞)。**装机坑**: hook 里注入 `PYTEST_ADDOPTS` 隔离 basetemp 时, Windows 反斜杠路径会被 pytest 的 shlex 解析当转义符吃掉 (实测 71 errors), 必须 `tr '\\' '/'` 转正斜杠。**残余敞口(诚实边界)**: ① 检的是工作树近似, 不是被推 commit 的快照——双线程共用 checkout 时另一线程脏 WIP 可能误挡 (误挡是响的, 无害); ② `--hook` 与 CI `--ci` 的 diff-range 类检查可能有范围差; ③ 换机/重 clone 后 hook 不在, 按本条手动重装。`gh run list -L 1` push 后回看降级为兜底纪律。

相关:[[zmd-checkout-env]] [[zmd-env-ci-gate]] [[zmd-env-auto-push]]
