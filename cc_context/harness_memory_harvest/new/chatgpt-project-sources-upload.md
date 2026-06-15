---
name: chatgpt-project-sources-upload
description: chatgpt.com Project 来源(Sources)文件区上传——两级流程(切 tab=sources→点添加源弹模态框→点上传按钮才触发 input file chooser);字节通道=分块 base64 灌页面构造内存 File(DOM.setFileInputFiles 路径背书进不了管道);真完成判据=挂载 POST 200 不是文件名出现;上传期间别捅 UI/别提前刷新;--replace 白名单删旧逻辑+同名对话框坑+upload_project_file.py
metadata: 
  node_type: memory
  type: reference
  originSessionId: d4206461-b836-4607-899b-5e644bbe37f6
---

chatgpt.com Project「来源(Sources)」文件区脚本上传的完整 UI 流程、字节通道与完成判据(2026-06-12 18MB 实测跑通):

- **Project「来源(Sources)」文件区上传是两级流程**:不是点一下就弹文件选择器。完整链 = ① URL 切到 `<project>?tab=sources`(或点页面「来源」tab) → ② 点「+ 添加源」**只弹一个模态框**(标题「添加源」, 含拖放区 + 四按钮: 上传 / 文本输入 / Google 云端硬盘 / Slack), **此步不弹 chooser** → ③ 再点模态框里的「**上传**」按钮, 才触发隐藏 `input[type=file]`(`accept=空`接受任意/`multiple=true`/在 DOM 里)的 `.click()` → 弹原生文件对话框。Playwright 正确写法 = 点添加源 → 等模态框 → `with page.expect_file_chooser(): 点「上传」按钮` → `chooser.set_files(...)`。⚠️ 别把②当成直接弹 chooser(点添加源就 `expect_file_chooser` 会超时)。上传成功判据 = 来源列表里同名条目出现(zip 条目副标题显示「文件内容可能无法访问」属正常, 不影响 GPT 解包)。
- **✅ 来源区脚本上传已跑通(2026-06-12, 18MB 实测): 字节通道 = 分块 base64 灌页面构造内存 File; 真完成判据 = 挂载 POST 200**。两个根因: ① `DOM.setFileInputFiles` 注入的路径背书 File 字节进不了上传管道 → 改 Runtime.evaluate 分块 atob→Uint8Array 灌进页面(1MB/块)、页面内 `new File([blob],name)` + `crypto.subtle.digest` 与本地 sha256 比对、`DataTransfer` 喂给被劫持标记的 input + 派发 change(内存背书字节与手动选文件等价); ② **就算字节传上去了, 提前刷新页面会掐断 in-flight 的挂载请求** — 管道四步 = `POST /backend-api/files`(注册)→`PUT <blob>/raw`(字节,201)→`POST .../process_upload_stream`→**`POST /backend-api/projects/<g-p-id>/files`(挂载,最后一步)**, 看到行菜单出「下载」1 秒就 reload 的对照组文件消失、静等 30s 的对照组持久化。**正解 = page-ws 上 Network.enable 监听挂载 200 再收尾; 上传期间不捅任何 UI**(开行菜单也疑似有干扰), 收尾复核 = 刷新后条目仍在 + 行菜单出「下载」。实现 = `upload_project_file.py`(--replace/--list/--delete-name; --keep 白名单)。⚠️ --replace 白名单语义会删**测试窗口期 owner 手传的新文件**(2026-06-12 事故, 靠本地副本救回) — owner 可能正在动文件区时别跑, 跑前看 delete_targets 日志。
- **来源区可用的 UI 事实(2026-06-12)**:① **行菜单状态(owner 纠正)**= 上传中是「**移除**」一项, 传完才是「下载」+「删除」两项 → 「下载」出现 = 字节已传完(比文件名出现可靠, 文件名是乐观占位); 但**它不保证挂载完成**, 真完成判据用挂载 POST 200(见上条)。② **删除 UI**= 点该行 `button[aria-label="源文件操作"]`(首点有时只 hover 出 kebab 图标, 要重试点) → 菜单(下载/删除) → 点「删除」**立即生效、无确认框**(所以"探一下删除流程"会直接真删, 别在生产数据上试探)。③ **--replace 删旧逻辑(owner 裁决)**= **不靠同名**(旧快照包版本名会变, 跟新包不同) → 改**白名单保留依赖包 `zmd_py313_linux_x86_64.zip`、删其余所有 .zip**, 再传新包。④ **同名**会弹「文件已经存在」对话框(跳过/仍然上传); **成功判据别用 `body.innerText` 数文件名**(对话框同名文本污染计数 = 假阳性), 数 `:not([role=dialog])` 内列表条目。⑤ **导航坑**: `PUT /json/new?<url>` 靠查询参数导航实测卡 `about:blank` → 改开空 tab + 显式 `Page.navigate`; 且列表条目比「添加源」按钮渲染慢, 轮询到按钮后要再多等几秒才能数到已有条目(否则枚举/计数为 0)。

相关:[[chatgpt-browser-automation-pitfalls]] [[chatgpt-package-snapshot-hygiene]] [[no-workflow-use-chrome-gpt-review]]
