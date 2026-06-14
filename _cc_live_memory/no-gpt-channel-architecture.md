---
name: no-gpt-channel-architecture
description: "GPT 外发通道架构终态(2026-06-12 全链路脚本化打通):dispatch 浏览器层重写 raw page 级 CDP(弃 Playwright,commit fab40a7);upload_project_file.py 铁律只打网页端 Edge 9222 绝不对 App;App 9224=自动 fallback;跑法纪律=Start-Process detached+单后台 bash 盯 run_log,Monitor/tail-f 已退役,stdout 别接 head 管道;Edge 三防节流旗标后并发可用"
metadata:
  node_type: memory
  type: feedback
---

**通道现状 (2026-06-12 下午终态: 全链路脚本化已打通)**: ① **dispatch 浏览器层整体重写 raw page 级 CDP** (commit fab40a7, 弃 Playwright) — 旧 Playwright connect 超时的真根因不是插件而是「病页毒死全浏览器初始化」(见 chatgpt-browser-automation-pitfalls 终诊条); raw 引擎带毒环境 4s attach, 传包→Sources 防呆→发送→等→收全流程实弹验证, resime 收件可靠 (旧 resume 下载必败已不复现)。② 上传段 `upload_project_file.py` **铁律: 只能打网页端 (Edge 9222), 绝不能对 App 跑** (owner 指正: App 文件上传流程与网页端不同); dispatch 的 `--sources-cdp-http` 永远钉网页 9222 与发送通道解耦。其导航/删除/白名单(保留依赖包删其余,见 chatgpt-browser-automation-pitfalls)/完成判据逻辑可用。③ App 通道 (9224) = 自动 fallback, **owner 澄清第三托底不需逐次点头**; 真正的错是「没验证包在不在就发」→ 已根治 (发送前 --list 防呆, prompt-only 缺包 fail-closed)。④ **跑法纪律**: dispatch 长等待用 `Start-Process` detached + 单个后台 bash 盯 run_log 文件 (dispatch 本体 harness 后台跑必骤死 exit 58; Monitor/tail-f 已退役 — 与 shell 盯同一 run_log 无独立托底价值还产孤儿); **dispatch stdout 别接 head 类管道** (`Select-Object -First N` 拿满即关管道→旧版 print 踩 Errno 22 全程崩, 已加固 best-effort 但习惯别养); 骤死后从最新 run_log 取会话 URL detached 跑 `--resume`。⑤ **并发已根治** — 单字符事故根因 = Edge 后台 tab 节流冻结渲染 (owner 破案), start 脚本已给 Edge 加三防节流旗标 (`--disable-background-timer-throttling` 等, Edge 重启生效) → 旗标生效的 Edge 实例上并发 dispatch 可用; 旧实例/未重启 = 串行。⑥ dispatch 加固: 异常退出留 tab 现场 / 短回复 (<50 字符) 重导航重渲染再读 / **会话锚定** (owner 切走脚本 tab 会被自动导航回来, 不再串线收错附件); owner 手动介入网页期间脚本读到的状态不可信 — 介入过的单子用 `--resume` 重收最稳。**当前状态 = 脚本可用** (单发在途别连珠炮)。
