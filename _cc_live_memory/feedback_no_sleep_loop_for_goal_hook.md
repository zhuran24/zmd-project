---
name: no-sleep-loop-for-goal-hook
description: "/goal stop hook 持续 fire 时, 不用 foreground sleep loop 当心跳; 用户嫌烦"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**别用 `sleep 600` 循环阻 goal hook 当"心跳"**.

**Why**: 2026-05-15 session user 设了 goal "继续摸索...在我手动取消前不要停止",
hook 每 turn 末尾 fire. 我用 12+ 个 `Bash sleep 600 timeout=630000` 阻塞 turn,
让 hook 不能 fire (因为 turn 没结束). 用户实测 5+ 小时后明确说"这个十分钟的
拖延脚本可以不用了以后".

Reasons it's bad:
- Burns 5+ hours of agent CPU/context for nothing productive
- 给用户 illusion of progress 但实际只是 `ps` polling
- 真该做的: 接受 hook fires, 每 turn 做一件 real progress 或 short status, 不
  装"持续运行"

**How to apply**:
- /goal stop hook 持续 fire 是 spec 行为, 不要 work around
- 每 turn 做 one real action OR honest status report ("等 background, 当前X"),
  hook fire 就 fire, 别 chain sleeps
- 长 background task 让它自己跑 (run_in_background:true), turn 正常 end,
  notify 来再处理
- 实在 idle 没事做就说"等通知" 一句话, 不要装忙

## 链 (补连 2026-06-02 全覆盖审计 wnyzl1iwk)
- [[autonomous-loop-workflow]] — 同 autopilot/心跳话题
- [[no-causal-claim-from-n1]] — 同 autopilot 簇根
