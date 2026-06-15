---
name: zmd-round2-dispatch-fix-state
description: "P1.2 闭合 Round2-4 状态: Round2(master_geometry)+Round3(scheduler)各 1 真 reachable false-CERTIFIED reset(已修 382d764/3bc08b0)。Round4=重启 streak 第 1 轮,进行中(已收 4/8 面全 CLEAN/不重置:benders HARDENING + master_geometry/binding/campaign 零 finding)。连续干净计数仍 0,需 R4/R5/R6 三连干净。+ 顺序单 tab 派发 + 逐面对抗 reachability 核 + GPT 硬化补丁可破 soundness 门须全量验。续接先读本节 + handoff + round4/_TALLY.md。"
metadata:
  node_type: memory
  type: project
  originSessionId: 67838178-96da-41c7-bafe-56199802815e
---

# P1.2 闭合 Round2-4 状态 — 2026-06-15 会话

> 续接: 先读本节 + `_cc_live_memory/handoff_windows_ninth_review_pending.md` + **`补丁包/gpt_deliveries/round4/_TALLY.md`(Round4 逐面裁决 durable 台账, gitignored 但在磁盘)**。目标(Stop-hook): **P1.2 闭合 = 我这边计数到 3 轮连续干净去偏置白板审(每轮 0 次 certified 路径 reachable false-CERTIFIED reset);自己判、拿不准开 team;计数到 3 自己宣布闭合。**

## 闭合计数现状(关键)
- **连续干净计数 = 0**。Round 2(master_geometry)与 Round 3(scheduler)各 1 真 reachable false-CERTIFIED reset,均已修复。
- **Round 4 = 重启 streak 第 1 轮(目标干净 #1),进行中**。基线 HEAD = 6be75f5(含 3bc08b0)+ 6c15c26(8 prompt snapshot 引用更新);快照 zmd_snapshot_8a44d536;candidate_placements sha adcc2a6e。
  - **已收 4/8 面,全 CLEAN / 0 reachable reset**:
    - **benders** = 1 HIGH finding(pre-master precheck elimination 宽松 `int()`/`bool()` 转 proof 计数,称 malformed boolean 可铸 RUN_STATUS_INFEASIBLE)但 **HARDENING canonical-unreachable 不重置**:3 opus 对抗验证员一致 HIGH —— producer(master_model.py evaluate_boundary_port_feasibility / evaluate_exact_candidate_mandatory_rectangle_prechecks)恒产良构 int,probe 靠 monkeypatch;default 路径 candidate_precheck_artifacts in-memory deepcopy 无 JSON round-trip;mandatory partial 路径因 time_budget=0.0 默认不可达。
    - **master_geometry** = 零 finding(§5 再证 382d764 occupied-only 修复成立 + V81 guard 完好;446 targeted passed;geometry probe nonrect_occupied=0)。
    - **binding** = 零 finding(status 契约 monkeypatch probe 全 fail-closed;INVALID_INPUT/empty-domain 隔离;§4 build() 坏输入抛异常 = canonical-unreachable 可用性边界非 reset)。
    - **campaign** = 零 finding(9 不变量节 + 189 targeted passed + adversarial probe 5 类 checkpoint 篡改全 fail-closed;强状态单调 + terminal CERTIFIED 五者共立 + persisted cut 不重放)。
  - **待收 4 面**:cuts / preprocess / routing / scheduler。重点核 **scheduler(3bc08b0 末端进程退出码 seal 修复成立?)** + **cuts(3bc08b0 CutScope snapshot 修复成立?是否新 finding)**。
- 历史 reset: Round 2 = master_geometry boundary screen 用 occupied∪connector 当 ghost blocker 比契约严 → false-INFEASIBLE 过剪 → false-CERTIFIED of optimality,修 382d764 / LOCK F-GM-BS-R2-01。Round 3 = scheduler run_wave() 末端无进程退出码 seal(exitcode 只在 queue.Empty 分支查)→ worker 交付末 RESULT 后非零死亡误报 completed=True → consumer 当 proof-complete 铸 CERTIFIED,修 3bc08b0 / LOCK F-SCHED-BS-R3-01;cuts CutScope.artifact_hashes alias bug = HARDENING(src/cuts/ step_8 NotImplementedError 未接生产),修 F-CUT-BS-R3-01。

## Round 4 新教训:GPT 硬化补丁可破 soundness 门,须跑全量回归
- benders 的 `benders_loop_soundness_fix.patch` 经完整验证:git apply 干净 + **红→绿判别成立**(只打测试 hunk 在未修 src 跑 → 2 测试 RED `assert True is False`,证 bug 真 + 测试有判别力;打 src 修复 → GREEN,证补丁有效)。
- **但全量回归(xdist 隔离 3140 passed)逮到 1 失败**:`scripts/check_p1_2_proof_obligations.py`(V81 门, check 在 1313-1322)要求字面串 `not bool(entry.get("partial_due_to_time_budget", False))` 在 benders_loop.py **出现 ≥2 次**(两 predicate 各一);补丁把两处重构进共享 helper `_all_anchor_infeasible_pre_master_payload_triggered` → 语义保留但字面消失 ×2 → 门红。**GPT 只跑 targeted(全量 13% 超时)没发现**。
- **决策不应用**:finding canonical-unreachable(无真实可达 soundness 洞要补)+ 应用须同改 V81 soundness forcing-function 门(敏感手术)+ 补丁把可 grep 审计的 V81 字面 guard 换成 helper(可审计性负向)+ 闭合审查职责是判 soundness 非重构扩 scope。已回退两文件、V81 门恢复绿。
- **可复用规律**:① GPT 补丁红→绿对 ≠ 安全,必跑**全量回归**(targeted 漏 gate 冲突);② canonical-unreachable 硬化若要 soundness-gate 手术,通常不值得应用;③ 静态 proof-obligation 门按**字面** pattern-match,语义等价的重构也会破它。归 gpt-delivery-no-blind-trust 一族。

## 本会话验证方法(有效, 沿用)
- **顺序单面派发**(zmd_round4_dispatch_all.ps1, pwsh7 跑): 单 Edge tab 前台停 /c/ 避并发节流 + /project 漂移。**今天面慢**(生成 20-66min;master_geometry 66min = 真 Pro 扩展深思,非降级/卡死 —— 降级判据才是 <1min 太快)→ 逐面 waiter 截止放宽到 75min;premature 短截 waiter 会 spurious TIMEOUT,无害但按真实状态重挂。
- **逐面对抗 reachability 核**: 每 finding 独立判 canonical-reachable(reset)vs unreachable(需 monkeypatch/hand-built/malformed/未接线子系统 = hardening 不重置),判据 PROJECT_LOCK:160-166,不裸信 GPT severity。
- **HIGH finding 用 ultracode 对抗验证 workflow**: 3 独立 opus 验证员核 producer 侧 + refute reachability(fable workflow 内不可用 → opus)。benders HARDENING 由三方收敛(2 producer-trace + 1 refuter,refuter 还佐证此区唯一真 reachable reset = 382d764 已修)。

## owner 行为裁决(feedback, 必守)
- 离线(owner_sleep=true)→ 全自主,一切自己拍板,不准出现只有 owner 能定的事,不 ping。
- 压缩纪律: 每环节结束查上下文(-Context),近 300k → 先更新记忆树 → /compact。
- GPT severity 系统偏高,finding 必独立对抗核 reachability,红→绿双证 + 真数据复现 + **全量回归(非仅 targeted)**。
- soundness 判据 = "能否 emit 项目契约说应 UNKNOWN 的 CERTIFIED",非"答案碰巧对"。

相关: [[zmd-project-entry]] overnight-certified-surface-review-arc gpt-delivery-adversarial-agent-review gpt-delivery-no-blind-trust fact-zero-finding-is-not-proof [[no-gpt-channel-architecture]]
