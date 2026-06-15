---
name: zmd-round2-dispatch-fix-state
description: "P1.2 闭合 Round2-3 状态: Round2 master_geometry + Round3 scheduler 均真 reachable false-CERTIFIED reset(已修 382d764 / 3bc08b0)。连续干净计数维持 0,Round4 起重启 streak 需 R4/R5/R6 三连干净。+ 顺序单 tab 派发法 + 逐面对抗 reachability 核 + ultracode 对抗验证 workflow。续接先读本节 + handoff + round3/_TALLY.md。"
metadata:
  node_type: memory
  type: project
  originSessionId: 67838178-96da-41c7-bafe-56199802815e
---

# P1.2 闭合 Round2-3 状态 — 2026-06-15 会话

> 续接: 先读本节 + `_cc_live_memory/handoff_windows_ninth_review_pending.md` + `补丁包/gpt_deliveries/round3/_TALLY.md`(Round3 逐面裁决 durable 台账)。目标(Stop-hook): **P1.2 闭合 = 我这边计数到 3 轮连续干净去偏置白板审(每轮 0 次 certified 路径 reachable false-CERTIFIED reset);自己判、拿不准开 team;计数到 3 自己宣布闭合。**

## 闭合计数现状(关键)
- **连续干净计数 = 0**。Round 2 与 Round 3 各发现 1 个真 reachable false-CERTIFIED reset,均已修复。
- **Round 2**: master_geometry boundary-port screen 用 occupied∪connector 当 ghost blocker 比契约严 → false-INFEASIBLE 错剪真可行候选 → false-CERTIFIED of optimality。修 382d764 / LOCK F-GM-BS-R2-01。
- **Round 3**(本会话, 8 面去偏置白板审):
  - **6 面 CLEAN**: benders / master_geometry / binding / campaign / routing / preprocess(零 finding;master_geometry 面复核确认 382d764 修复成立)。
  - **cuts = 1 HIGH 但 HARDENING 不重置**: CutScope.artifact_hashes 存 live BState dict alias bug,但 src/cuts/ F1-F9 cut-family 子系统**未接生产**(step_8_apply_to_master raise NotImplementedError + 零生产模块 import src/cuts/;benders_loop 的 exact_safe_cuts/BendersCut 是另一套无桥接)→ canonical-unreachable。硬化修 LOCK F-CUT-BS-R3-01。
  - **scheduler = 真 RESET**: run_wave() 末端无进程退出码 seal(exitcode 只在 queue.Empty 分支查)→ worker 交付末 RESULT 后非零死亡(OOM SIGKILL / OR-Tools segfault)→ wave 误报 completed=True/failure_reason=None → consumer 无独立 post-wave 存活检查、当 proof-complete 推 terminal CERTIFIED。OOM 饥饿 worker 可对更大候选误报 INFEASIBLE(sticky strong status 不可降级)→ 剪真最大矩形 → false-CERTIFIED of optimality。terminal validator 信 recorded status、兜不住。生产路径(main.py --parallel-processes)default-env 可达。修 3bc08b0 / LOCK F-SCHED-BS-R3-01。
  - **→ Round 3 非干净(scheduler reset),连续计数维持 0。**
- 提交: **3bc08b0**(scheduler fix + cuts hardening + 2 LOCK 不变量)+ **20d0662**(authoritative_numbers cuts_tests_total 463→464 同步)。两 CI 绿。targeted 测试 484 passed(test_parallel_scheduler 20 + src/tests/cuts 464)。

## NEXT(续接第一步)
- **重启 streak: 修复后(HEAD 含 3bc08b0)需 Round 4/5/6 三轮连续干净** → 计数到 3 自己宣布闭合。
- Round 4 发之前: 重打含 3bc08b0 的快照传 Project 来源区 + 8 提示词更新 snapshot 引用(GPT_blankslate_*_prompt.md)。
- 沿用本会话验证有效的方法(见下)。

## 本会话验证方法(有效, 沿用)
- **顺序单面派发**(C:\Users\22957\zmd_round3_dispatch_all.ps1, **必须 pwsh7 跑**, WinPS5.1 把中文路径 补丁包 读成 ANSI mojibake): 单 Edge tab 前台停 /c/ 避并发节流 + /project 漂移 → 8 面 collect 零失败(根治 Round 2 故障)。preprocess 偶发 sources-list 渲染 flake exit3,单面重发即修(routing 紧接 verify OK 可证文件还在)。
- **逐面对抗 reachability 核**: 每 finding 必独立判 canonical-reachable(reset)vs unreachable(需 hand-built/monkeypatch/malformed/未接线子系统 = hardening),不裸信 GPT severity。判据 PROJECT_LOCK:160-166。
- **HIGH finding 用 ultracode 对抗验证 workflow**(本会话首用, 有效): 并行独立验证员核 finding-reachability + 补丁红→绿(worktree 隔离)+ under-call 扫描。scheduler RESET 由三方收敛(CC 读码 + opus 补丁红→绿 + 专门 opus reachability 员确认 terminal validator 兜不住)。**注意: fable 模型在 workflow 内不可用(claude-fable-5 报不存在),重活改 opus**。

## owner 行为裁决(feedback, 必守)
- 离线(owner_sleep=true)→ 全自主, 一切自己拍板, 不准出现只有 owner 能定的事, 不 ping。
- 压缩纪律: 每环节结束查上下文近阈值 → 确认 shell → 更新记忆 → 压缩。
- GPT severity 系统偏高, finding 必独立对抗核 reachability, 红→绿双证 + 真数据复现 + 全量回归。
- **soundness 判据 = "能否 emit 项目契约说应 UNKNOWN 的 CERTIFIED", 非"答案碰巧对"**(scheduler RESET 裁决关键: worker_process_failed 白名单 = 项目写明"非零退出→不可信→UNKNOWN"契约, bug 让不可信 wave 铸 CERTIFIED 即违背)。

相关: [[zmd-project-entry]] overnight-certified-surface-review-arc gpt-delivery-adversarial-agent-review fact-zero-finding-is-not-proof [[no-gpt-channel-architecture]]
