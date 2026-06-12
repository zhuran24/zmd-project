# GPT Pro 外发自动化

把「打包 → 上传 → 发送 → 等完成 → 收交付」整条流程交给本地脚本跑,全程零 token(只在起止时看一眼)。

## 前置(每次 Edge 重启后跑一次)

```powershell
& cc_context\review\gpt_dispatch\start_gpt_automation_chrome.ps1
```

默认连**用户日常 Edge 主实例**(owner 裁决:不搞独立 profile,直接用已登录状态,零配置)。行为:端口已通直接报就绪;Edge 在跑但没带端口 → **温和关窗后带 9222 重启并恢复会话标签**(⚠️ 会重启用户正用着的浏览器,执行前注意);Edge 没跑 → 直接带端口启动。`-Isolated [-Browser chrome|edge]` 切独立 profile 模式备用(那个才需要首次手动登录)。

## 用法

(2026-06-12 起 `python` = Program Files 主环境, 依赖齐全可直接用; `python3.13` 商店版备份也行。
子进程走 `sys.executable` 跟随入口。)

```powershell
# 标准: 自动打全项目单包 (除缓存全打) + 发任务 + 等 + 收
python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --pack --prompt-file <prompt.md>

# 指定现成包 (可多个 --package)
python ...\dispatch_gpt_task.py --package X.zip --prompt-file prompt.md

# 托底/续等: 脚本挂了或超时后, 重连同一会话接着等/补收, 不重发任务
python ...\dispatch_gpt_task.py --resume "https://chatgpt.com/g/.../c/<id>"
```

## Project 文件页上传器 (包递交通道, 2026-06-12 跑通)

包走 Project「来源」文件区, 不随消息发附件 (owner 裁决)。`upload_project_file.py`
引擎 = raw CDP page 级 ws (与 claude-in-chrome 插件共存); 字节通道 = 分块灌进页面构造
内存 File (页面内 sha256 比对); 完成判据 = 监听挂载 POST `/backend-api/projects/<id>/files`
返回 200, 再刷新复核条目仍在 + 行菜单出「下载」。**上传期间脚本不碰 UI** —— 提前刷新
会掐断 in-flight 挂载请求, 文件传上去了却挂不到 Project (2026-06-12 对照实测)。

```powershell
# 标准每轮工作流: 删旧快照(保白名单, 默认依赖包) + 传新包
python cc_context\review\gpt_dispatch\upload_project_file.py --file <包.zip> --replace

# 运维: 只读枚举 / 精确删除
python ...\upload_project_file.py --list
python ...\upload_project_file.py --delete-name <文件名.zip>
```

⚠️ `--replace` 是白名单语义 (删除**所有**不在 `--keep` 里的 .zip) — owner 可能正在
手动操作文件区时**不要跑** (2026-06-12 事故: 测试窗口期 owner 手传的包被清, 靠本地
副本救回); 动手前 delete_targets 日志会亮出完整删除清单。同名已存在默认点「跳过」
(幂等), `--on-duplicate overwrite` 改点「仍然上传」。退出码: 0=挂载成功+复核通过 /
1=环境错误 / 3=异常(看 attention 截图)。

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
| 5 | 疑似 Pro 静默降级(重试后生成仍 <`--min-gen-seconds`,默认 300s;2026-06-11 实测 70s 降级回复曾溜过旧 60s 判据成 exit 2) | 交付已收但不可信;Claude 改走插件通道(Edge,已登录)重发 |
| 1 | 环境错误(CDP 不通/包不存在) | 起 Chrome / 查路径 |

## Pro 静默降级(owner 经验,2026-06-11)

降级**不在任何明面标注**(model-slug 照样写 pro),唯一判据是行为:**真实任务完整生成 <1min 极大概率被限**。脚本处置阶梯:①自动刷新页面 + 要求重新完整执行(`--downgrade-retries`,默认 1 次);②仍快 → exit 5,由 Claude 切到 Claude-in-Chrome 插件通道(Edge,已登录)托底重发。轻量测试任务跑得快是正常的,传 `--min-gen-seconds 0` 关闭检查。

## 完成检测原理

双信号 + 稳定窗口:①「停止生成」按钮消失(主信号,秒级响应);② 最后一条回复文本长度连续 3 次轮询(30s)不变(兜底,防选择器漂移)。两者同时满足、且 assistant 消息数达到发送前基线 +1,才判完成;轮询 10s 一次。(曾有「继续生成」按钮自动点击逻辑,2026-06-11 owner 裁决移除——现版 ChatGPT 实测不存在该按钮,宽文本匹配反而有误点风险。)

## 第三托底通道:ChatGPT 桌面 App(2026-06-11 打通)

App 是 Electron(Chromium 内核),内部加载的就是 chatgpt.com 网页前端,**DOM 与网页版同构**,dispatch 脚本可直接驱动——不同客户端可能在不同限流池,Edge 通道被静默限时值得切:

```powershell
& cc_context\review\gpt_dispatch\start_gpt_automation_chrome.ps1 -App     # App 带 CDP 9224 启动
python cc_context\review\gpt_dispatch\dispatch_gpt_task.py --cdp-url http://localhost:9224 --pack --prompt-file <md>
```

关键约束:**必须用 `Invoke-CommandInDesktopPackage` 以 MSIX 包身份启动**(start 脚本 -App 已封装)——裸跑 WindowsApps 里的 exe 会因拿不到包上下文而主进程崩溃(弹 "A JavaScript error occurred in the main process");App 不支持开新标签页,脚本自动复用主窗口页面且结束时不关它。完整托底链:脚本@Edge 主实例(9222)→ 插件@Edge(手动)→ 脚本@App(9224)。

## 网络抖动 / 页面卡死恢复

等待期每拍先做页面活性探测(`document.readyState`);连续 2 拍(~20s)无响应 → **同 URL 新开页面、关掉老页面**(owner 处方;比 reload 可靠——渲染进程挂死时 reload 自己也会卡),换新页面继续等,稳定计数清零。恢复失败(网络还断着)下一拍重试;3 次换页后仍无响应 → attention 退出,`--resume` 可在网络恢复后续等。此路径未经真实网络故障实测(无法按需复现),逻辑保守:恢复失败时退回旧页面继续轮询,不会比不恢复更糟。

## 已知边界

- ChatGPT DOM 改版可能破选择器(集中在 dispatch 脚本顶部的 JS 探针常量:`_STOP_VISIBLE_JS` / `_LAST_ASSISTANT_JS` / `_candidates_js` / `MODEL_BTN_TEXTS` 等,改那里即可;旧文档说的 `SEL` 字典在 2026-06-12 raw-CDP 重写后已不存在)
- 多轮追问不在 V1 范围:GPT 若反问而不是交付,脚本会以 exit 2 收文本,由我判断后用 --resume 或新任务跟进
