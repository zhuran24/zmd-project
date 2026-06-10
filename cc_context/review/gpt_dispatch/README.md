# GPT Pro 外发自动化

把「打包 → 上传 → 发送 → 等完成 → 收交付」整条流程交给本地脚本跑,全程零 token(只在起止时看一眼)。

## 一次性准备

```powershell
# 1. 起专用自动化 Chrome (独立 profile, CDP 9222; 已在跑则直接报就绪)
& cc_context\review\gpt_dispatch\start_gpt_automation_chrome.ps1
# 2. 首次使用: 在弹出的窗口里手动登录 chatgpt.com 一次 (cookie 长期有效)
```

## 用法

```powershell
# 标准: 自动打全项目单包 (除缓存全打) + 发任务 + 等 + 收
python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --pack --prompt-file <prompt.md>

# 指定现成包 (可多个 --package)
python ...\dispatch_gpt_task.py --package X.zip --prompt-file prompt.md

# 托底/续等: 脚本挂了或超时后, 重连同一会话接着等/补收, 不重发任务
python ...\dispatch_gpt_task.py --resume "https://chatgpt.com/g/.../c/<id>"
```

默认发到「终末地」Project(`--project-url` 可换),模型沿用 Project 记住的 Pro·进阶(脚本只校验不切换,不像 Pro 会报 attention)。

## 输出(默认 `补丁包/gpt_deliveries/<时间戳>/`)

- 回复里的全部文件附件(zip 自动校验可解 + 报条目数)
- `final_reply.md` — GPT 最后回复全文
- `run_log.jsonl` — 各阶段状态,等待期每分钟一条心跳,可 tail 监控
- `attention_*.png` / `.html` — 非预期状态的截图 + DOM 现场(托底用)

## 退出码

| code | 含义 | 托底动作 |
|---|---|---|
| 0 | 交付附件已到手 | 无 |
| 2 | 回复完成但没有文件附件 | 读 final_reply.md 决定下一步 |
| 3 | 异常(未登录/错误横幅/未预期 DOM) | 看 attention_* 截图,必要时 --resume |
| 4 | 超时(默认 3.5h) | 看心跳判断是否还在跑,--resume 续等 |
| 1 | 环境错误(CDP 不通/包不存在) | 起 Chrome / 查路径 |

## 完成检测原理

双信号 + 稳定窗口:①「停止生成」按钮消失(主信号,秒级响应);② 最后一条回复文本长度连续 3 次轮询(30s)不变(兜底,防选择器漂移)。两者同时满足才判完成,轮询 10s 一次。「继续生成」按钮出现会自动点掉。

## 已知边界

- ChatGPT DOM 改版可能破选择器(集中在脚本顶部 `SEL` 字典,改那里即可)
- 多轮追问不在 V1 范围:GPT 若反问而不是交付,脚本会以 exit 2 收文本,由我判断后用 --resume 或新任务跟进
