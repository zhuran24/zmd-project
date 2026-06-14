---
name: no-gpt-dispatch-vs-manual-riskctrl
description: "GPT 外发的发送分工与风控处置:单发默认 CC dispatch 脚本自动发,多路并行/额度紧时改 owner 手动;疑似风控(脚本连续降级/App 卡顿)=无自动托底,停一切自动外发落盘等 owner;owner 手动发走 clip_send.ps1 剪贴板交付;dispatch wait/collect 后台必骤死(exit 58)用 --resume 重连"
metadata:
  node_type: memory
  type: feedback
---

**发送分工(2026-06-11 用户裁决):单发任务默认 CC 用 dispatch 脚本自动发;只有多路并行外发(脚本不支持同浏览器并发,start/cleanup 会互关 tab)或 CC 自己的额度快用尽时,才改由用户手动发**(跟 GPT 那边的额度无关)。CC 手上有现成包+prompt 时别把单发推回给用户。**风控经验**: 脚本通道一个窗口期连发 ~4 单左右就可能触发风控 (即使单发在途也别连珠炮); 同时在途的旧软上限"最多 2"已于 06-14 字段化(见 no-gpt-concurrency-field)。**疑似风控(脚本连续降级/App 卡顿)= 无自动托底,停下来**(2026-06-11 裁决):插件通道本质也是同一浏览器同一账号的自动化,同样会被风控——换通道硬试只会加重。处置 = **停止一切自动外发**,把待发的包+prompt 路径落盘进 handoff/现场,等 owner 手动发或风控冷却。交 owner 手动发时跑 `C:\Users\22957\clip_send.ps1 -TextFile <prompt.md> -Files <包.zip>`:提示词文字先进(滚入剪贴板历史)、包文件后进(占当前位,文件不进历史)→ owner 先 Ctrl+V 贴包、再 Win+V 翻历史贴提示词(详见 clipboard-handoff-convention)。已发出的会话仍可用脚本 `--resume <URL>` 盯回复+收附件(只读不发,不刺激风控;注意 resume 跳过降级检测,收件后自查生成耗时)。风控下脚本已发出的请求视为废弃(生成会被降级/不可信),重要任务用剪贴板交 owner 手动重发,别指望"已发出的那条会正常生成"。`--package <现成包>` 比 `--pack` 重打包好 (sha 不漂)。**骤死坑**: CC harness 后台跑 dispatch 的 wait/collect 必被掐 (exit 58/255, 心跳健康时死, run_log 无尾)——`--resume "<URL>"` 重连续盯可救; **resume 页下载另有坑** (click_download canceled=True 三连, 同附件 owner 手动下载正常)——兜底 = owner 手动下, 拿到后尽快 TaskStop 脚本防它发多余救援追问。
