---
name: cc-watchdog-api-resume
description: "CC 会话 API/网络中断自动续跑看门狗 cc_api_watchdog.ps1 (C:\\Users\\22957\\cc_watchdog\\): 检测 transcript jsonl 里统一标记 isApiErrorMessage (429/529/socket断开/订阅) + 文件 90s 没动 = 卡住, kernel32 WriteConsoleInput 注入「继续」续跑; 静默常驻 start_hidden.vbs, 进程定位 SelfSessionId/GuardPid 映射, usage limit 每 10min 重试"
metadata:
  node_type: memory
  type: reference
  originSessionId: 37712a00-f4f3-4562-a3e0-d17d137f4de6
---

## API 断线自动续跑看门狗 (cc_api_watchdog.ps1)

在 `C:\Users\22957\cc_watchdog\`。常驻, 日志 `cc_watchdog\watchdog.log`, 单实例 mutex。**完全静默运行** (用户要求无窗口): 开始菜单「CC断线自动续跑」走 `start_hidden.vbs` (wscript Run 隐藏模式; `powershell -WindowStyle Hidden` 会闪窗所以不用), 停止走「CC断线看门狗-停止」或脚本 `-Stop`; 无窗口所以状态只能看日志 (每小时 heartbeat)。

关键机制 (排查/复用时的非显而易见点):
- **检测不枚举报错文案**: CC transcript jsonl 里任何 API/网络错误 (429/529/socket断开/订阅) 都写统一结构化标记 `"isApiErrorMessage":true` (带 `error`/`apiErrorStatus` 字段, model=`<synthetic>`)。卡住 = 最后一条 user/assistant 消息带该标记 + 文件 90s 没动。错误条目后会跟一条同时刻 `type:system`, 判定要跳过非 user/assistant 行。
- 对原始 JSONL 行做 `"type":"user"` 这类正则是**结构安全的**: 字符串值内引号必转义为 `\"`, 不会被消息正文里引用的报错文字误触发 (用户消息引用报错原文曾差点造成误报)。
- **进程定位不能用文件创建时间配对** (resume 会续写同一个 jsonl, 创建时间≠进程启动): 用「启动时间早于报错时刻的 claude 进程」过滤 + 注入后回查 transcript 是否前进自校验, 30s 没动换下一候选。**会话→pid 精确映射**: per-session 进程命令行 (`-SelfSessionId <guid> -GuardPid <pid>`) 就是活映射表, STALL 恢复时按 jsonl 文件名直查并提为第一候选, 查不到才回落「启动时间早于报错」旧启发式 (旧启发式曾连错 3 个窗口误注「继续」)。
- **注入用 kernel32 WriteConsoleInput** 写目标控制台输入缓冲 (FreeConsole→AttachConsole(pid)→CONIN$), 不抢焦点不碰剪贴板; 中文走 UnicodeChar 无 IME 问题; 文本和回车分两批隔 350ms 发, 防 TUI 粘贴启发式吞回车。注入助手是子进程, 用退出码回报 (>0=事件数)。
- 撞 usage limit 时会每 ~10min 发一次「继续」, 上限重置后自动续上 (有意为之)。

与 `cc_model_selfguard.ps1` 的两套自助工具互不依赖, 后者见 [[cc-selfguard-context-send]]。
