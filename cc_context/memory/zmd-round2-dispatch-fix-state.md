---
name: zmd-round2-dispatch-fix-state
description: "P1.2 闭合 Round2-4 状态: Round2(master_geometry)/Round3(scheduler end-of-wave)/Round4(scheduler mid-wave)各 1 真 reachable false-CERTIFIED reset,均已修(382d764/3bc08b0/f8a0333,LOCK F-GM-BS-R2-01/F-SCHED-BS-R3-01/F-SCHED-BS-R4-01)。连续 3 轮都在 scheduler 相邻代码挖到真洞 = 闭合不该提前。连续干净计数仍 0,R5 起重启 streak,需 R5/R6/R7 三连干净。方法: 顺序单 tab 派发 + 逐面对抗 reachability 核 + GPT 补丁红→绿对≠安全须全量回归 + 修一个 timing≠修一类 bug。续接先读本节 + handoff + round4/_TALLY.md。"
metadata:
  node_type: memory
  type: project
  originSessionId: 67838178-96da-41c7-bafe-56199802815e
---

# P1.2 闭合 Round2-4 状态 — 2026-06-15 会话

> 续接: 先读本节 + `_cc_live_memory/handoff_windows_ninth_review_pending.md` + **`补丁包/gpt_deliveries/round4/_TALLY.md`(Round4 逐面裁决 durable 台账, gitignored 但在磁盘)**。目标(Stop-hook): **P1.2 闭合 = 我这边计数到 3 轮连续干净去偏置白板审(每轮 0 次 certified 路径 reachable false-CERTIFIED reset);自己判、拿不准开 team;计数到 3 自己宣布闭合。**

## 闭合计数现状(关键)
- **连续干净计数 = 0**。Round 2/3/4 **各 1 真 reachable false-CERTIFIED reset**,均已修复。
- **Round 4 已完成 = RESET(非干净)**。8 面收齐:7 面 CLEAN/不重置(benders HARDENING + master_geometry/binding/campaign/cuts/preprocess/routing 零 finding),**scheduler 1 个 canonical-REACHABLE false-CERTIFIED(F-SCHED-MIDWAVE-CRASH-01)→ Round 4 非干净 → 计数维持 0**。
- **R5 起重启 streak**(需 R5/R6/R7 三连干净 → 计数到 3 自宣闭合)。基线新 HEAD = **f8a0333**(含 mid-wave 修复)。
- 历史 reset(三轮都在 scheduler 相邻代码,去偏置白板审在持续找真洞 = 闭合本就不该提前):
  - **R2** master_geometry: boundary screen 用 occupied∪connector 当 ghost blocker 比契约严 → false-INFEASIBLE 过剪 → false-CERTIFIED of optimality,修 **382d764** / LOCK **F-GM-BS-R2-01**。
  - **R3** scheduler: run_wave() 末端无进程退出码 seal(exitcode 只在 queue.Empty 分支查)→ worker 交付末 RESULT 后非零死亡误报 completed=True,修 **3bc08b0** / LOCK **F-SCHED-BS-R3-01**;cuts CutScope alias = HARDENING(F-CUT-BS-R3-01,src/cuts/ step_8 NotImplementedError 未接生产)。
  - **R4** scheduler: **mid-wave crash+respawn** —— 见下详核,修 **f8a0333** / LOCK **F-SCHED-BS-R4-01**。

## Round 4 scheduler mid-wave reset 详核(F-SCHED-MIDWAVE-CRASH-01)
- 机制:run_wave() mid-wave queue.Empty 分支。worker 交付 task N 的 INFEASIBLE 后、task N+1 仍 pending 时非零死亡(OOM SIGKILL / OR-Tools native segfault)→ drain 记 crashed-gen INFEASIBLE 进 results_by_seq → `_respawn_all_workers()` 置 `self._processes=[]` 再 start() 填健康新一代 → **崩溃旧进程对象被抹掉** → end-of-wave seal(R3/3bc08b0 加的)查 self._processes 只见健康新一代、不触发 → completed=True/failure_reason=None,跨 generation 结果混成 proof-complete wave。consumer(outer_search)fail-open:identity 检查只查 dispatch_seq/candidate 不查存活,crash 结果照过;`_total_crash_respawns` 递增但 consumer 零引用 → 无独立 crash 遥测。sticky INFEASIBLE 不可降级 → 永久剪真最大矩形 → max_lex false-CERTIFIED of optimality。
- 裁决 = **REACHABLE_RESET**(与 R3 同 class,仅 timing 不同;R4 更险——respawn 主动抹崩溃进程让 R3 seal 结构性失效)。证据阶梯:① 读真码确认机制;② RED probe 当前 HEAD 复现 completed=True;③ consumer fail-open 码证;④ **3-opus 对抗 workflow 全判 REACHABLE_RESET/high,含被指派力证 hardening 的 refuter 诚实承认无法反驳**;⑤ 补丁 green(2 回归 + 22 scheduler + V81 门)+ **全量 xdist 3141 passed / 0 failed**。
- 修:crash-drain 用 scratch validated_results_by_seq;覆盖全 task → 保留 + 仍在场崩溃进程被 seal 转 worker_process_failed;有 pending → 清空全部 tainted prefix + respawn **重跑全部 task**(非仅 pending);达上限 → discard latch + 清空。崩溃 generation 结果永不跨 respawn 边界。

## 关键教训(本轮新增 + 沿用)
- **修一个 timing ≠ 修一类 bug**:R3 的 3bc08b0 seal 只盖 end-of-wave,mid-wave respawn 路径(R3 回归把 `_respawn_all_workers` stub 成 no-op、从未覆盖)结构性绕过 → R4 才挖出。修复一个崩溃 timing 后要主动查**所有** timing/分支(还有没有别的路径绕过同一守卫)。
- **GPT 补丁红→绿对 ≠ 安全,必跑全量回归**(benders V81 门教训保留):benders 补丁红→绿过却破 V81 静态门(字面 pattern-match),只全量逮到。本次 mid-wave 补丁全量 0 failed、无 gate 冲突,才提交。
- **HIGH/Critical finding 用 3-opus 对抗 workflow 做 reachability 终判**:含一个被指派"力证 hardening/救 streak"的 refuter;refuter 诚实驳不倒才判 reset。reset 是清零大事不靠我单方。

## 本会话验证方法(有效, 沿用)
- **顺序单面派发**(zmd_round4_dispatch_all.ps1, pwsh7):单 Edge tab 前台停 /c/ 避并发节流 + /project 漂移。今天面慢(生成 20-66min;66min = 真 Pro 扩展深思非降级 —— 降级判据才是 <1min 太快)→ 逐面 waiter 截止放宽到 75min。
- **逐面对抗 reachability 核**:每 finding 独立判 canonical-reachable(reset)vs unreachable(需 monkeypatch solve 逻辑/hand-built/malformed/未接线子系统 = hardening),判据 PROJECT_LOCK:160-166,不裸信 GPT severity。零 finding 面也独立核「使任何残留问题不可达的载荷主张」是否真成立(如 cuts 三连主张、preprocess exact-ceiling、routing 消费侧 deny-unknown)。

## owner 行为裁决(feedback, 必守)
- 离线(owner_sleep=true)→ 全自主,一切自己拍板,不准出现只有 owner 能定的事,不 ping。
- 压缩纪律: 每环节结束查上下文(-Context),近 ~400k(1M 会话压缩点别擅自放大)→ 先更新记忆树 → /compact。
- soundness 判据 = "能否 emit 项目契约说应 UNKNOWN 的 CERTIFIED",非"答案碰巧对"。

相关: [[zmd-project-entry]] overnight-certified-surface-review-arc gpt-delivery-adversarial-agent-review gpt-delivery-no-blind-trust fact-zero-finding-is-not-proof [[no-gpt-channel-architecture]]
