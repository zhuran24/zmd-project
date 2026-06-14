---
name: zmd-round2-dispatch-fix-state
description: "P1.2 闭合 Round2 已结: master_geometry 真 reachable false-CERTIFIED → 连续干净计数 RESET 到 0(已修+推送 382d764/F-GM-BS-R2-01)。下一步重启 Round3/4/5 三轮连续干净。+ dispatch 4 类故障 team 修复 + owner 离线全自主裁决。续接先读本节 + handoff。"
metadata:
  node_type: memory
  type: project
  originSessionId: 67838178-96da-41c7-bafe-56199802815e
---

# P1.2 闭合 Round2 已结 + dispatch 根治 — 2026-06-15 会话

> 续接: 先读本节 + `_cc_live_memory/handoff_windows_ninth_review_pending.md`。目标(Stop-hook): **P1.2 闭合 = 我这边计数到 3 轮连续干净去偏置白板审(每轮 0 次 certified 路径 reachable false-CERTIFIED reset);自己判、拿不准开 team;计数到 3 自己宣布闭合。**

## 闭合计数现状(关键)
- **Round 1**: 干净(3 finding 全 canonical-unreachable hardening, 0 reset)= 曾计数 1。LOCK: F-BIND-BS-01/F-BL-BS-01/H-PRE-BS-01。
- **Round 2**: 8 面已收齐(7 面零 finding, 全核扎实做过 + master_geometry 1 条)。master_geometry = **真 default-env canonical reachable false-CERTIFIED**: boundary-port feasibility screen 用 occupied∪connector 当 ghost hard blocker 比契约严; 默认 certified_exact 路径(benders_loop ~2305-2404)硬返回 INFEASIBLE 无下游兜底; 但默认 routing 不排除 ghost cell(_extract_occupied_cells 跳 ghost_pick, F1-F9 cut family 的 ghost-blocked 不在默认路径)→ belt 可穿空矩形 → connector-在-ghost port 真可路由 → screen 误筛真可行候选 → max_lex 下丢真最大矩形 = false-CERTIFIED。真 canonical 134 pose: occupied x=0/y=0, connector x=1/y=1, corner-region ghost 触发。
- 四重独立自验(不裸信): routing-trace + red→绿回归 + 全量 3137 passed 无回归 + 真 canonical pose 几何。
- **→ Round 2 非干净, 闭合连续计数 RESET 到 0**(R1 不计入新 streak, 因它漏了此 bug)。
- master_geometry 已修+推送: commit **382d764**(分支 project-foundation), LOCK **F-GM-BS-R2-01**, blocking_cells 改 frozenset(occupied_cells), CI green。

## NEXT(续接第一步)
- **重启计数: 需 Round 3/4/5 三轮连续干净**(在已修代码上)→ 计数到 3 自己宣布闭合。
- Round 3 发之前: ① 等 integrator 合好健壮 dispatch(见下)② 重新打 HEAD(含 382d764)快照传 Project 来源区 ③ 8 面提示词更新 snapshot 引用(脚本/手改)。
- sound-verifier(fable)/patch-verifier(opus)报告: 我已确凿自验, 它们是 post-hoc 确认; 若反对则 reconcile 具体证据(概率低)。

## dispatch 脚本 4 类故障 + team 修复(Round 3 健壮性)
4 patch 已就位 `补丁包/gpt_deliveries/round2/_fixes/`(dl/rescue/send/collect-fixer), integrator(fable)合并中(冲突图见 EVIDENCE 同目录 / 我给 integrator 的消息)。根因统一: 后台 tab 节流 + page 漂到 /project(非 /c/)→ collect 读空 + 下载 click 被 compositor 丢 + 误判降级 + 404 救援死循环。collect-fixer 已用后端 interpreter download 端点取回全部缺失 REVIEW。
- A 下载捕获: 坐标 click 后加 JS element.click()(后台 tab 可靠触发)。
- B 收集空: collect 入口锚回 /c/ + wait_done 覆盖 /project 漂移 + 后端读失败留痕 + sandbox 链接兜底。
- C 发送/降级: conv_url 反查 + fail-closed 闸 + 降级判据加 conv_url 守卫。
- D 404 死循环: collect 返回 dl_status, rescue 只在真 sandbox_404 触发, capture_failed 走纯文本兜底。
- 合并后我复核 env-off 不变 + 不破已成功 4 面再提交。

## owner 行为裁决(feedback, 必守)
- **离线(owner_sleep=true)→ 全自主**: 一切自己拍板; 不准出现「只有 owner 能定」的事; 不 ping/不打扰。
- **压缩纪律**: 每个小环节结束查上下文, 近阈值→确认 shell→更新记忆→压缩。本会话曾失守冲到 621.9k 被怒斥; 救火/密集多消息中也必须守第①步。见 cc-autonomous-compaction-protocol。
- GPT severity 系统性偏高, finding 必独立对抗核 reachability(见 gpt-delivery-owner-patch-and-severity / gpt-delivery-adversarial-agent-review); 不裸信子代理/GPT/自己 trace, 红→绿双证 + 真数据复现 + 全量回归。
- 判 reset vs clean 的判据(Round1 先例): canonical-reachable false-CERTIFIED = reset; canonical-unreachable(需 hand-built/monkeypatch/malformed)= hardening 不重置。

## 插件浏览器坑
Claude-in-Chrome 插件默认连未登录 Chrome(`chrome-search://local-ntp`), 非 dispatch 用的登录态 Edge 9222。要用插件操作 chatgpt 须先 `list_connected_browsers`+`select_browser` 选登录态 Edge, 或走 raw CDP @ Edge 9222 后端读。

相关: [[zmd-project-entry]] overnight-certified-surface-review-arc gpt-delivery-no-blind-trust [[no-gpt-channel-architecture]] chatgpt-throttled-tab-render
