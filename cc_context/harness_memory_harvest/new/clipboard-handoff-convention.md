---
name: clipboard-handoff-convention
description: "用户裁决(2026-06-11):凡是要 owner 复制的东西(路径/命令/提示词/文件)直接送进剪贴板,别只打在聊天里;专用脚本 C:\\Users\\22957\\clip_send.ps1;发包三件套顺序=包完整路径→提示词→包文件(2026-06-12 追加)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

用户裁决:**给 owner 任何需要复制的东西(路径、命令、URL、提示词全文、文件),直接送进剪贴板**,聊天里照常打出来供核对,但别让 owner 手动框选复制。

**Why:** owner 的操作成本最低化;且 Windows 剪贴板的两类行为差异让"一次交付多个待粘贴物"成为可能。

**How to apply:**
- 专用脚本 `C:\Users\22957\clip_send.ps1`(已实测):
  - `-Text "<字符串>"` — 路径/命令/URL 直接进剪贴板(进历史)
  - `-TextFile <path>` — 文件**内容**作为文字进剪贴板(进历史)
  - `-Image <p1>,<p2>,...` — 图片按位图进剪贴板(进历史;多张逐张压入历史、最后一张占当前位;PNG 透明/GIF 动画会丢,保真改用 -Files 发文件本体)
  - `-Files <p1>,<p2>,...` — 文件本体进 file-drop,**可一次多个文件**
  - 组合调用时脚本内顺序固定:文字先、文件后
- **关键机制(用户科普)**:文字/图片会进**剪贴板历史**(Win+V 翻得到);**文件 file-drop 不进历史**,只占当前位、复制后须马上粘贴。
- **致命坑(2026-06-11 实测)**:裸调 `[Clipboard]::SetFileDropList($col)` 的数据**随设置进程退出而消失**(同进程验证是假阳性)——必须 `$do = DataObject; $do.SetFileDropList($col); [Clipboard]::SetDataObject($do, $true, 10, 100)` 显式 copy=true 冲刷给系统;验证必须**跨进程**做。clip_send.ps1 已内置正确姿势,任何场合写内联剪贴板代码(含给子代理的指令)都不要再用裸 SetFileDropList。
- **时序坑(2026-06-12 实测)**:连续多次 clip_send(同一命令行里 `;` 串联)写入太快,剪贴板**历史**后台服务来不及抓第一条就被覆盖 → 历史漏录(owner Win+V 看不到)。多条入历史时**每条之间 `Start-Sleep 2`**。
- **发包标准姿势(2026-06-12 用户追加裁决, 三件套)**:入剪贴板顺序 = **① 包完整路径(文字) → ② 提示词全文 → ③ 包文件本体**。即先 `clip_send.ps1 -Text "<包完整路径>"`,再 `clip_send.ps1 -TextFile <prompt.md> -Files <包.zip>`(或脚本一次组合调用,保证文字按 路径→提示词 顺序入历史、文件压轴占当前位)。owner 用法: Ctrl+V 贴包文件 → Win+V 翻历史依次取提示词、路径。**Why 路径必须有**: 文件 file-drop 条目不进历史,剪贴板一被覆盖文件就丢且无法找回;路径文字垫在历史里,owner 任何时候都能据它自己去拿文件,不用再喊 CC 重发。
- **变体(2026-06-12 当天晚些, 包改走 ChatGPT Project 文件页后)**: GPT 外发包不再随消息发附件 (见 [[no-workflow-use-chrome-gpt-review]] 第 4 条) → 剪贴板只放 **路径→提示词** 两条文字, **不放包文件本体** (贴进会话就又变附件模式); 三件套完整版仍适用于其它"要把文件本体交到 owner 手上"的场景。
- 其它场景灵活套用同一思路(多个待粘贴物=利用历史排队,文字垫底、文件压轴)。

关联 [[no-workflow-use-chrome-gpt-review]](发包手动通道的上游场景)。
