---
id: agent-longrun-wait-wake-protocol
kind: decision
title: teammate 型子代理等长跑命令会静默睡死——长命令必须走 harness 后台机制,每任务段完成必须发消息,主线程对长跑代理保持"进程没了人没醒就 ping"的巡检
summary: 实测两例(2026-07-03 同一天):teammate 型子代理(Agent 工具带 name 派出、SendMessage 通信的那种)用自管方式等长跑命令(detached 启动+自己轮询日志/自设等待器),命令结束后【没有任何通知投递】,代理不会醒——例一 slow lane 跑完代理多睡 45 分钟;例二 ritual 执行代理等的全量 pytest 01:43 跑完、代理睡到次日 15:47(14 小时),期间 owner 离开、主线程也只有被动事件唤醒,整条链路静止一夜。**能可靠唤醒 teammate 的只有两样:发给它的消息、harness 跟踪的后台任务完成通知**;进程本身消失不产生任何事件。协议(派活任务书必须写死):①代理跑 >2 分钟的命令一律用 harness 后台执行机制(run_in_background 类,完成自动唤醒),禁止 detach+自管轮询;②每完成一个任务段立刻 SendMessage 一行状态给主线程再继续——消息链保证任何时刻至少有一方会被唤醒;③代理若等不受自己控制的外部条件,必须报备"在等什么",巡检责任移交主线程;④主线程侧:对每个长跑 teammate 做元数据巡检(进程在不在/日志与 transcript 的 mtime 还动不动),发现"事完了人没醒"立即 ping——但注意主线程自己也是事件驱动的,owner 长时间离开时被动巡检不会发生,必要时挂定时唤醒(cron/心跳)兜底。
scope:
  domains:
    - multi-agent
    - orchestration
    - infra
  paths: []
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - spawn-teammate-agent
    - wait-longrun-command
    - diagnose-stuck-agent
  keywords:
    - 子代理
    - teammate
    - 唤醒
    - 睡死
    - idle
    - 等待器
    - 后台
    - run_in_background
    - 巡检
    - slow lane
    - 长跑
    - 没回来
    - 卡住
  negative_keywords: []
  paths: []
  symbols: []
  error_regex: []
  examples:
    - 子代理怎么一直没回来
    - 派一个长任务的 teammate 子代理
    - 它等的进程跑完了但它没动静
activation:
  layer_hint: L1
  must_know: false
  reason: 派长任务 teammate 时若任务书不写等待协议,代理会自然用 detach+轮询的方式等长命令,然后静默睡死;发现时已损失几十分钟到十几小时。同日两踩,第二次整夜。
provenance:
  op: record
  reason: 2026-07-03 ritual 执行代理睡死 14 小时(等的 pytest 01:43 完成、次日 15:47 被主线程手动 ping 醒),owner 追问"进程会不会唤醒子代理"时机制被点破;同日早些时候 slow lane 已有一次同型 45 分钟例。
  evidence:
    - "例一:round-19 收尾代理的 --slow-tests 进程结束后任务状态停在 in_progress,主线程查进程列表发现空、手动 ping 后才续跑。"
    - "例二:ritual 执行代理 01:22 idle 等自起的全量 pytest,pytest 01:43 完成(pytest_cache mtime 为证),代理 transcript 停在 01:22,睡至 15:47 被 ping;工作区改动与测试结果完好,损失纯为时延。"
  updated_at: "2026-07-03"
---
teammate 型子代理的长跑等待/唤醒协议(2026-07-03 同日两踩后钉死)。

== 机制事实 ==
能唤醒 teammate 代理的事件只有:①发给它的 SendMessage/主线程消息;②harness 跟踪的后台任务(run_in_background 类)完成通知;③它派的孙代理完成通知。**裸进程结束不是事件**——代理若 detach 起进程再自己轮询,一旦回合结束挂起,就没有任何东西能叫醒它。主线程同理也是事件驱动:owner 不在、没人发消息时,主线程的"巡检兜底"根本不会执行。

== 协议(派活任务书写死这四条)==
1. **>2 分钟的命令一律 harness 后台机制挂**(完成自动唤醒发起者),禁止 detach+自管轮询/自设等待器。
2. **每任务段完成即发一行状态消息**给主线程(消息内容抽象化不受影响),再继续下一段——保证消息链上总有一方被唤醒。
3. **等外部条件必须报备**"在等什么",巡检责任显式移交主线程。
4. **主线程巡检手法**:查进程列表(还在=正常等)、代理 transcript/工作区 mtime(动=活着)、任务列表状态;"事完了人没醒"→ ping 即活,活不会丢(状态在磁盘),损失纯为时延。owner 长时间离开的时段,若还有长跑 teammate 挂着,考虑 cron/定时唤醒兜底。

== 2026-07-11 追加:等待条件永不满足的僵尸 watcher ==
第五坑:watcher 的等待条件若只匹配成功形态(如 `until grep "passed|failed"`),被等对象**崩溃时日志没有 summary 行**,watcher 永久死循环(实例:e3.log 等待器因测试 SIGSEGV 无 summary 挂了 17 小时,owner 从 UI shell 计数发现)。协议补丁:①watcher 的匹配条件必须含失败/崩溃形态(faulthandler 栈标记/exit 行),或干脆 `-c` 加超时上限;②换路线放弃某个实验时,**先杀它的 watcher 再走**(放弃清单=进程+采样器+等待器三件套)。
