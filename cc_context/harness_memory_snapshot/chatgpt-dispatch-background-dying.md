---
name: chatgpt-dispatch-background-dying
description: "CC harness 后台跑 gpt_dispatch 必骤死(exit 58/255,心跳健康进程被外部掐 run_log 无错误尾巴)→对策=Start-Process detached 进程重定向文件+后台 shell 盯 run_log;Start-Process ArgumentList 带空格路径必须自带内嵌引号;dispatch stdout 接 head 类管道会拿满即关管道带崩;dispatch 唤醒=每单挂一个后台 bash until grep finish(Monitor/tail-f watcher 已退役,跨压缩丢映射)"
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

CC harness 后台运行 gpt_dispatch 的骤死问题、detached 进程对策、传参坑、与唤醒通道定版(2026-06-12/13):

- **CC harness 后台跑 dispatch 必骤死(2026-06-12 三次实测: exit 58 ×2 / exit 255)**:心跳健康时进程被外部掐,run_log 无错误尾巴。**对策定版**:长等待一律 `Start-Process` **detached** 进程 (stdout/err 重定向文件) + 后台 shell 盯 run_log——detached 不受 harness 收割;骤死后从 run_log 取会话 URL detached 跑 `--resume`(raw 引擎 resume 收件已实证可靠)。**Start-Process 传参坑 (06-13 实测)**: ArgumentList 里带空格的路径必须自带内嵌引号 (`'"C:\claude pj\...\x.py"'`), 裸传会被按空格劈开 (python 报 can't open file 'C:\\claude')。**另一坑: dispatch stdout 接 head 类管道 (`Select-Object -First N`) 会拿满即关管道**,旧版 print 踩 OSError 22 把 attach 都带崩(已加固 Reporter best-effort print,但别这么接)。
- **dispatch 唤醒 = 单通道后台 shell, Monitor/tail-f watcher 已退役 (2026-06-13 owner 裁决)**: Monitor 的唤醒映射跨上下文压缩会丢 (实测压缩后 finish 事件没拉起 CC), 而 `Bash run_in_background` 的**完成通知**跨压缩可靠。**为什么不用「Monitor 实时流 + 后台 shell」双保险**: 两者盯**同一个** run_log, 不是独立链路, Monitor 没托底价值还反复产孤儿 (忘清理/exit 255 假警报)。**定版 = 每单 dispatch 只挂一个后台 bash** `until grep -q '"finish"' <out_dir>/run_log.jsonl; do sleep 15; done` (单次完成唤醒)。shell 也挂了的兜底 = 任何告一段落时刻直接查 run_log + 按 owner 规则发下一个排队请求当唤醒源。压缩前 stamp 里写死 out_dir/会话 URL。

相关:[[chatgpt-browser-automation-pitfalls]]
