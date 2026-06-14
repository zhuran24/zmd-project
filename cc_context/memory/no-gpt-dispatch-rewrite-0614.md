---
name: no-gpt-dispatch-rewrite-0614
description: "dispatch 大改(2026-06-14 owner 裁决,commit 51e5c47/9465731):复用页+不关页(upload_project_file.py 加 --reuse-tab-id/--no-close,一页到底零 churn)+模型自检自修(verify_model 真打开『智能水平』菜单点 Pro 扩展,Radix 要 CDP click_xy)+接收侧 model 复核(collect 复核 slug 含 pro 不符并入 suspected_downgrade→exit 5);cargo-cult 方法论铁律=改前先理清严谨因果链别凭猜加 workaround"
metadata:
  node_type: memory
  type: feedback
---

**dispatch 大改 (2026-06-14 owner 裁决, commit 51e5c47/9465731): 复用页 + 不关页 + 模型自检自修 + 接收侧 model 复核。** ① **一页到底零 churn**: upload_project_file.py 加 --reuse-tab-id (复用 dispatch 已开的 tab, 不再 PUT /json/new 开空页) + --no-close (传完留页给发送); dispatch sources 流程让同一 tab 走 blank→sources→composer。靠"dispatch 调 upload 子进程时事件循环阻塞、那条 page-ws 此刻空闲"避免两连接同操一 tab 的竞态 (子进程阻塞 = 天然串行边界); 同端点 (Edge 9222) 才复用, App 9224 各自开 tab。② **模型自检自修**: verify_model 从"只警告"升级成"不是 Pro 扩展就真打开『智能水平』菜单点过去" —— DOM 实地探明: 模型按钮 aria-haspopup=menu, 菜单项 role=menuitemradio 文本 "Pro 扩展" 带 aria-checked (同级有 极速/均衡/高级/超高/GPT-5.5); 开菜单要真实 pointer (CDP click_xy), .click() 对 Radix 不可靠。③ **接收侧 model 复核**: collect() 复核回复 model-slug 含 "pro", 不符并入 suspected_downgrade → exit 5 (与生成时长 min-gen-seconds 降级同档; test 模式 --min-gen-seconds 0 不升级)。④ **cargo-cult 教训 (owner 方法论铁律, 务必记)**: upload 之前"先开空页/先去主页再导航"是我把某次问题根因猜错留下的迷信式防御绕路 —— owner 原话"遇到问题理清逻辑, 链条不清楚不严谨就不要进行误认, 不然跟拜神有什么区别"。这次先读真实 CDP/页面代码搞懂因果 (churn 真根因 = 两处 PUT /json/new 开空页 + upload finally 无条件关 tab + upload/dispatch 两进程各开 tab) 才重构掉。**通用原则: 改前先理清严谨因果链, 别凭猜加 workaround。** ⑤ selfguard -SendSeqB64 单 worker 串行排多条 (msg1→见忙确认起回合→等空闲→msg2), 避免两次 -Send 抢同一空窗竞态 (owner 实现); 配 precompact skill。⑥ 模型对不对/降没降级是脚本两端的活, 别手动复盘也别每次报告念叨"真 Pro" (owner 嫌烦), 详见 gpt-delivery-acceptance-discipline 记忆。
