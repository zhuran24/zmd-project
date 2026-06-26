---
id: offline-mode-autonomy-criterion
kind: decision
title: 离线/在线自主行为只认 owner_sleep.flag
summary: 所有自主行为的离线/在线判据是 owner_sleep.flag 是否存在；Codex/Claude 绝不从“我走了/我回来了/发消息”自行推断。
scope:
  domains:
    - autonomy-mode
    - owner-availability
  paths:
    - C:/Users/22957/cc_watchdog/owner_sleep.flag
  symbols:
    - owner_sleep.flag
    - offline_mode_autonomy_criterion
status: active
priority: P0
triggers:
  intents:
    - autonomous-run
    - offline-mode
  keywords:
    - 离线模式
    - 在线模式
    - owner_sleep.flag
    - 自主行为
    - 我走了
    - 我回来了
    - 无人值守
  negative_keywords: []
  paths:
    - C:/Users/22957/cc_watchdog/owner_sleep.flag
  symbols:
    - owner_sleep.flag
  error_regex: []
  examples:
    - owner 说我走了是否能自动开启离线模式
    - 需要判断当前能不能无人值守自主推进
activation:
  layer_hint: L1
  must_know: false
  reason: 离线/在线推断错误会改变代理自主行为边界。
provenance:
  op: record
  reason: owner 2026-06-20 定；从旧 cc_memory 节点 offline-mode-autonomy-criterion 提炼。
  evidence:
    - python cc_memory/mem.py read offline-mode-autonomy-criterion --body
updated_at: "2026-06-26"
---
所有“离线才做/在线才做”的自主行为只看 `C:\Users\22957\cc_watchdog\owner_sleep.flag`：存在就是离线，不存在就是在线。开关只能来自 owner 明确说开启/关闭离线模式。

不要因为 owner 说“我走了”“我回来了”、发了一条消息、或有任意交互就自动建删标记。owner 可能人在电脑前但不盯线程，偶尔说话也不代表离线模式结束。
