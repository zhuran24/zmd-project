---
name: cc-autonomous-compaction-protocol
description: "自主压缩协议 (owner 指令, 过夜/无人值守标准动作): 每个告一段落跑 -Context 自查 context_used_tokens, ≥~400k (1M context 会话的压缩点, 别擅自放大) → 先把该记的全记进记忆树再发 /compact; 唯一硬规则=记完立刻压两步紧连不插活; 压缩前从头系统扫一遍 (漏网 owner 指令/工具新知 + handoff stamp/双镜像/台账/commit + 唤醒源 + 残留 watcher); 发送模式按 owner_sleep.json 选 -SendNow 即时 vs 排程等候"
metadata:
  node_type: memory
  type: reference
  originSessionId: 37712a00-f4f3-4562-a3e0-d17d137f4de6
---

## 自主压缩协议 (owner 指令, 过夜/无人值守循环标准动作)

跑 `-Context` / `-Send` 的工具机制见 [[cc-selfguard-context-send]]; 本节是「什么时候、按什么流程」自主压缩的协议。

**owner 2026-06-15 怒斥重申「给我记牢了」四步走(verbatim): ① 每次小环节结束就检查上下文长度 → ② 到 400k 阈值附近了 → ③ 确定有 shell(唤醒源)→ ④ 更新记忆树 → ⑤ 压缩上下文。** 我那次把它误说成「三步」、漏了第①步「先查上下文长度」当触发, 被 owner 当场戳穿暴怒。**要害 = 不是等 owner 喊才查, 是【每个小环节一结束就主动查上下文长度】当例行触发**; 近 400k 才走后面的 shell→记忆→压缩。

在每个「告一段落」时刻 (一轮验收完成、双发出去进入等待、长任务收尾、一个小环节结束) 跑 `-Context` 自查 `context_used_tokens`; **≥ ~400k** → 把该记的记全再发 /compact 压缩。**这 400k 是给 1M context 会话定的压缩点** —— 200k 上限物理上根本到不了 400k, 所以这数从来就是 1M 情况下的值; 曾误判过 558k 还说「空间充裕」、又瞎推「该放 750k」, 都被 owner 戳穿, **别再擅自放大**。
- **唯一硬规则 (owner 强调)**: 记忆树更新与压缩必须**紧连着** —— 记完立刻发 /compact, 两步之间不插任何其它工作 (隔着干的活不在记忆里, 压缩一来就丢)。
- **压缩前检查流程**: ① **更新记忆树是一次单独的专门任务, 不是边干活边顺手记** —— 压缩决定做出后**从头系统性扫一遍**: (a) 回放本窗口对话找**没落树的 owner 在途指令/规则修正 + 工具新知** (曾漏网: 「睡觉状态不要动」「修好了不用回」「-SendNow 参数语法」); (b) handoff stamp 完整? 双镜像同步? harness 记忆/索引? 台账? commit?; (c) 检查项必须**工具现场验证**, 不准凭印象打勾; (d) 注入失败重试时学到的新知识也要回写再压缩。② **唤醒源检查**: 在途任务的后台 shell 若已自然退出, 压缩后没人拉起 CC = 孤儿挂死 → 正常走流程把队列下一单请求发出去 (在途任务就是天然唤醒源, 不挂假闹钟)。③ **残留 watcher 清理**: 进程级扫已完成单子该退没退的 watcher 杀掉, 在途单的 bash 父子对保留。④ 全部确认后才 `-Send /compact`。
- **发送模式按 owner 睡觉状态选**: 状态字段 `C:\Users\22957\cc_watchdog\owner_sleep.json` (CC 维护: owner 说「睡觉了」→ true; owner 回来说话 → false; **例外: owner 明示「睡觉状态不要动」则保持不随对话翻转**; 睡觉期间修好的东西不用专门汇报, 落记忆/stamp 即可)。`sleeping=true` → 用 `-SendNow` 即时模式 (owner 不在, 无草稿风险); `false` → 用排程等候模式 (防打断 owner 正在输入)。
