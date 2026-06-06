---
name: multiprocess-hang-inspect-all
description: 多进程 hang debug 时, py-spy 必须 dump 所有 worker 进程 stack, 不能只看 main; 只看 main 会误判 "IPC bug" 而实际 worker 自己 hang
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
多进程程序 (multiprocessing / multiprocessing.Process) hang 时, **必须 py-spy
dump 所有 worker 进程 stack, 不光看 main**.

**Why:** 2026-05-11 P2 #14 dumper 0 触发, 当时只 py-spy main 看到卡
`multiprocessing/queues.py:111 get()`, 推断 "worker→main IPC bug". 实际真因
是 worker 自己 hang 在 master 构造的嵌套 CP-SAT 无 timeout (master_model.py:6736),
main 等 worker result 永远等不到. 浪费 1+ session 在 IPC 假设上.

**How to apply:**

多进程 hang debug 流程:
1. `pgrep -af "main.py.*campaign-hours"` → 主进程 PID
2. `pgrep -P <main_pid>` 递归列子进程 (worker subtree)
3. **每个 PID 都跑** `sudo py-spy dump --pid <PID>`, 包括 main + 所有 worker
4. main 卡 queue.get → 检查 worker 在干啥. **worker hang = 真因**, main 只是
   被动等
5. 单进程 (`--parallel-processes 1`) 复现是黄金验证 — 把 IPC 排除掉, 直接在
   main 暴露真 hang

特别针对 CP-SAT / OR-Tools 多线程 solve, py-spy 报 `active+gil` vs `active`
都说明 C++ 在跑, GIL 状态不一定可靠区分.

切记: 多进程框架的 "等结果" 行为很容易被误判为 "通信 bug", 实际**绝大多数
是被等的那一端自己卡住**.

## 链 (补连 2026-06-01)
- [[shell-wrapper-pgrep-self-match]] — 进程调试 lore
- [[p2-14-dumper-path-blocked]] — hang 实例
