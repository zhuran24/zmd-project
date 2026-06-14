---
name: chatgpt-download-behavior-global-leak
description: CDP setDownloadBehavior 是浏览器全局状态且不随 ws 断开复位——不复位会让 owner 手动下载的文件持续静默消失进交付目录变 GUID 乱码名;修复=退出复位 default+按 frameId 过滤;手动解药=browser-ws 发 setDownloadBehavior default;--out-dir 相对路径=下载全 canceled(Edge cwd 不是 repo 根解析不了→入口 Path.resolve);resume 页下载 canceled 故障 raw-CDP 重写后已不复现
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

CDP `Browser.setDownloadBehavior` 的全局副作用、相对路径 canceled 大案、以及 resume 页下载故障(2026-06-12):

- **⚠️ setDownloadBehavior 是浏览器全局状态且不随 ws 断开复位 (2026-06-12 owner 抓的, 最伤一条)**: 旧版收完附件不复位 → 之后 owner 在 Edge 任何标签页手动下载的文件**持续静默消失**进交付目录且变 GUID 乱码名。修复 (commit dda2210) = ① DownloadWatch 退出时复位 `behavior=default` (best-effort, ws 已断靠浏览器重启兜底); ② `downloadWillBegin` 按自己页面 frameId 过滤, 不抢同窗口期手动下载。**脚本被硬杀来不及复位时的手动解药**: browser-ws 发一条 `Browser.setDownloadBehavior {behavior:default}` 即可。症状识别 = owner 说"下载的东西不见了" → 先查 gpt_deliveries 最新目录里的 GUID 文件。
- **⚠️ --out-dir 相对路径 = 下载全 canceled (2026-06-12 深夜五连败大案, owner「手动下载一次成功」线索定案)**: 手传 `--out-dir '补丁包\...'` 相对路径被原样喂给 `Browser.setDownloadBehavior.downloadPath` — **Edge 进程解析不了相对路径** (它的 cwd 不是 repo 根), `downloadWillBegin` 正常发 guid 但 `downloadProgress` 立刻 `state=canceled`。**极具迷惑性**: python 侧写日志/截图全正常 (python cwd 在 repo 根); 救援重生成无效 (问题不在 GPT 侧); 默认 out_dir 走 `repo_root /` 拼接是绝对路径所以从没踩过。诊断排除链: 并发互踩(独占复测推翻)→CDP 复位(无效)→Edge 重启(无效)→owner 手动下载成功 = 定位 CDP 接管路径。修 = 入口 `Path(args.out_dir).resolve()` (已带注释焊死)。
- **resume 页下载故障**: 早期 (2026-06-12 上午) 的 resume 下载 canceled 故障在 raw-CDP 重写后已不复现 (同日下午: resume 模式 3 附件含 patch/zip 全收, 裸 browser-ws DownloadWatch 每次点击新开 session)。若再遇 canceled 三连, 兜底仍是 owner 手动下载 + 尽快 TaskStop 防 404 救援追问骚扰会话。

相关:[[chatgpt-browser-automation-pitfalls]] [[chatgpt-attachment-capture]]
