---
name: no-gpt-concurrency-field
description: "GPT 外发并发上限已字段化(2026-06-14 owner 放开):旧软上限「最多 2 条在途」去掉,改由 C:\\Users\\22957\\cc_watchdog\\gpt_dispatch_concurrency.json 的 max_in_flight 控制(null=不限默认;整数 N=最多 N 条在途未收完);CC 每次发新外发前读此字段定并发度;dispatch 脚本本身无硬并发 gate;仍成立护栏=在途未收完别清旧快照、每单只挂一个后台 shell、包走文件区"
metadata:
  node_type: memory
  type: feedback
---

> 事实依据: [[fact-decision-boundary-is-ability]]

**并发上限已字段化 (2026-06-14 owner 放开)**: GPT 外发"一次最多 2 条在途"的旧软上限 owner 裁决去掉——需要发多少条就发多少条。现由字段控制: `C:\Users\22957\cc_watchdog\gpt_dispatch_concurrency.json` 的 `max_in_flight` (null=不限=当前默认; 整数 N=最多 N 条同时在途未收完)。CC 每次发新外发请求前读此字段决定并发度。dispatch 脚本本身无硬并发限制 (代码里没有 max_in_flight gate, grep 确认), 旧上限纯是 CC 操作软规则, 现移到字段。**Why**: 一刀切写死"最多 2"在记忆里, 风控冷却后也没人改回来, owner 要的是可调旋钮; 风控复发时把 max_in_flight 设回整数即可临时收紧, 而非永久卡死。**仍成立的护栏 (与并发数无关, 别一起去掉)**: 在途单未收完别清旧快照包 (传新包加 --keep-old-snapshots, sha 唯一名防并发覆盖)、每单 dispatch 只挂一个后台 shell 当唤醒源、包走 Project 文件区模式。
