---
name: long-op-background-mode
description: spawn Agent / Bash 长跑（> 1 min）默认 run_in_background:true，让主对话持续 active 续 cache TTL
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

任何**主对话会进入 silent 等待状态**的长任务（spawn Agent / Bash 长跑 / pytest 全跑 / WebFetch 大文件 等），**默认用 `run_in_background: true`** 而不是前台等结果。

**Why:** Anthropic prompt cache 是 sliding window 5 min 默认 TTL（Max 订阅可能 1 小时但 2026-03 有过 regression 不能 100% 确认）。每次 inference completion 续 TTL。**主对话 silent 期间不发 completion**，cache 走 wall-clock 失效。下次说话整段历史重传，全价 input（10 倍贵）。

具体场景：
- spawn Agent foreground → 我等 result 5+ 分钟 silent → 心跳 event 进 conversation 但排队等 Agent return → cache 已过期
- Bash 默认前台跑 pytest 全套 7 分钟 → 同款 silent 等待 → cache 过期
- 即使开 Monitor heartbeat 也救不了——event 排队等我 turn

修订规则：
- **spawn Agent**: 默认 `run_in_background: true`，除非确认 < 1 min 任务（grep / git log / sanity check 这种）
- **Bash 长跑**: 默认 `run_in_background: true`，配 Monitor 等关键 stdout / 完成通知
- **Bash 短命令**: ls / cat / git status / grep 几秒回的，前台 OK
- **Monitor**: 持续观察 / 等条件触发 / stdout 每行触发我 turn → 同时跑 + 续 cache，最稳 pattern

**How to apply:**

- 估单步任务时长 > 1 min → 自动 background
- foreground 工具调用必须能在 < 1 min 完成
- 写完 commit / 写完文件 / 验证 pytest 86 守卫这种快速验证可前台
- 长 audit agent（5-15 min spawn）必须 background
- pytest 全套（7 min）必须 background

**Memory 重要等级**: 跟 `feedback_research_roi_metric.md` 同级。两条规则配套：前者管"调研产物 audit 必要性"，本条管"长任务执行模式".

**2026-05-10 触发记录**: User 提"工作时穿插心跳"+"程序跑也要 background"。verify by audit `a98d6642e43ea08c8`：sliding TTL refresh 在 inference completion 时，主 silent 等待真会失效；当前 3 min Monitor heartbeat 在我 silent 等待期间也救不了（event 排队）。
