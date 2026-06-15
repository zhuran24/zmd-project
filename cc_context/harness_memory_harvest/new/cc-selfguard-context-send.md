---
name: cc-selfguard-context-send
description: "CC 自查上下文长度 + 给自己窗口发消息/斜杠命令 (cc_model_selfguard.ps1, C:\\Users\\22957\\cc_watchdog\\): -Context 只读返回 context_used_tokens/limit/pct (解析底栏 ctx 段, 须 -FooterProbe 隔离子进程 + 光标锚定读屏); -Send 注入 /compact 等 (默认 detached 排程等空闲, -SendNow 即时; 必须用 PowerShell 工具调防 git bash 把 /compact 转成路径); 安全边界=只认自己窗口、占用拒绝、结果码 0/3/4/5/6"
metadata:
  node_type: memory
  type: reference
  originSessionId: 37712a00-f4f3-4562-a3e0-d17d137f4de6
---

## 上下文自查 `-Context` + 给自己发消息 `-Send` (cc_model_selfguard.ps1)

在 `C:\Users\22957\cc_watchdog\`。CC 在自己会话里**按需调用**的脚本命令 (不是常驻守护), 只认/只动自己这条线程。自识别两路径都实测通过: 优先 `CLAUDE_CODE_SESSION_ID` env (CC 的 shell 子进程自带); 无 env 兜底「父进程链找 claude pid」。与 API 断线看门狗 (见 [[cc-watchdog-api-resume]]) 互不依赖。

**`-Context` 线程上下文自查** (纯只读): `powershell -File C:\Users\22957\cc_watchdog\cc_model_selfguard.ps1 -Context` 返回自己线程的上下文 JSON。**核心 = 上下文长度**: `context_raw` (底栏 ctx 段原文如 `"150.7k / 1.00M (15.1%)"`) + `context_used_tokens`/`context_limit_tokens` (k/M 后缀换算成 token 数) + `context_used_pct`; 解析自底栏 `ctx:[██░░] used / limit (pct%)`, 解析不出时这几字段 null。还返回 session_id / jsonl / project_dir / claude_pid / footer_model。**坑**: `-Context` 主进程绝不能自己读屏 —— ReadScreen 的 FreeConsole 会把 conpty stdout 弄丢 (exit 0 但无输出); 底栏必须走 `-FooterProbe` 一次性隔离子进程 + 临时文件回传。
- 读屏机制: `AttachConsole(pid)` + `ReadConsoleOutputCharacterW` 读底栏 `<cwd> | <Model> | ctx:[..] N / 1.00M (x%)`。**读屏须光标锚定**: 窗口 rect 会卡在滚回区不跟内容走 (抓到窗口停在 7..36 行而光标在 566 行), TUI 帧永远画在光标附近 → 读 `[cur.Y-44, cur.Y+10]` (底栏在输入行下方几行, 必须读过光标)。

**`-Send` 给自己窗口发消息**: `powershell -File ...cc_model_selfguard.ps1 -Send "/compact"` 往**自己当前窗口**注入任意消息/斜杠命令 (典型: -Context 看到 ctx 快满 → 给自己发 /compact)。**默认排程模式**: 派 detached `-SendWorker` 等「本回合结束 (连续 4 次×2s 无生成迹象) + 输入框确认为空」再注入 —— CC 从工具里调时自己回合还在跑, 同步等空闲 = 等自己 = 死锁, 必须 detached; 结果看 `selfguard.log` (`sendworker: 注入完成 code=0`), 超时默认 30min (`-SendTimeoutMinutes`)。`-SendNow` = 立即注入 (生成中被 TUI 当排队消息; **-SendNow 是开关不是参数**, `-SendNow "/compact"` 会报 ParameterArgumentTransformationError)。
- **安全边界**: 只认自己窗口 (父链 claude pid); 输入框有内容 (owner 草稿) 一律拒绝/等待, 绝不清字; 全程不发 ESC; worker 文本经 base64 传 (防引号转义坑); 多行压单行 (中途回车会提前提交)。结果码 0=已提交 / 3=输入框被占 / 4=文本滞留 / 5=读屏失败 / 6=attach失败。
- **排程模式空闲识别** (三处坑后定稿): 生成迹象只扫**屏幕尾部 15 行** (真 spinner 永远紧贴输入框上方) + 计时须在括号内 `'\((\d+m )?\d+s · '` (滤掉回合结束后永驻屏上的总结行 `Cooked for 1m 6s …`)。坑: 检测器会读到屏上**关于检测器的讨论**而自咬 → 收尾汇报里别写会命中检测正则的字面示例。
- **⚠️ git bash 路径转换坑**: 经 Bash 工具调 `-Send /compact` 时 `/compact` 被 MSYS 当 Unix 路径转成 `C:/Program Files/Git/compact` (注入垃圾) → **必须用 PowerShell 工具调脚本** (不转换); 错发了先 Stop-Process 旧 worker pid 再重发, worker 命令行的 `-SendB64` 参数可 base64 解码核对实际注入文本。

何时该自主跑 /compact 的协议 (400k 触发 + 压缩前记忆树仪式 + 睡觉状态选发送模式) 见 [[cc-autonomous-compaction-protocol]]。
