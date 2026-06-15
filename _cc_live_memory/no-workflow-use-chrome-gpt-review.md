---
name: no-workflow-use-chrome-gpt-review
index_summary: "GPT Pro 外发审查/委托主题索引(原巨型节点已拆);具体设置/通道/风控/降级/并发见各子节点"
description: "GPT Pro 外发审查/委托主题索引(原巨型节点已拆);非必要不用 Workflow、审查外发 GPT Pro 这套规则的总入口,具体设置/通道/风控/降级/并发见子节点"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

> 事实依据: [[fact-conversation-state-is-window-local]]

「非必要不用 Workflow,审查/委托实现外发 GPT Pro」这套规则的索引节点(原 15KB 巨型节点已按事实拆分,提高召回)。按需读对应子节点:

- [[no-gpt-pro-outsource-core]] — 核心裁决:非必要不用 Workflow 多代理;审查/外审/委托实现外发 GPT Pro;Why + How to apply(交付物验收 preflight gate)
- [[no-gpt-send-settings]] — 四条发送设置:Pro·进阶模型 / 终末地 Project / 新会话 / 包走 Project 文件页(来源区)删旧保依赖
- [[no-gpt-packaging-rules]] — 打包规则:除缓存全打 + build_v80_single_win.py + worktree 干净树 sha 唯一名纪律;老审查打包规范已全废
- [[no-gpt-dispatch-vs-manual-riskctrl]] — 发送分工(脚本默认/手动条件)+ 疑似风控停止处置 + 剪贴板交付 + dispatch 后台骤死用 --resume
- [[no-gpt-channel-architecture]] — 通道架构终态:raw CDP 重写 + upload 只打网页端 Edge 9222 + App 9224 fallback + 跑法纪律
- [[no-gpt-dispatch-command-and-downgrade]] — 首选通道 dispatch 命令 + start 脚本 Edge caveat + Pro 静默降级判据(elapsed_s)+ 托底两层
- [[no-gpt-plugin-clipboard-upload]] — 托底通道手动上传:clip_send.ps1 剪贴板 / 插件 file_upload 限制 / sandbox 404
- [[no-gpt-downgrade-evidence]] — 降级机理实证(24 次数据):唯一信号 elapsed_s,明面字段全撒谎,找客服真证据=时长对比
- [[no-gpt-concurrency-field]] — 并发上限已字段化(max_in_flight),旧"最多 2"软上限去掉;仍成立护栏
- [[no-gpt-dispatch-rewrite-0614]] — dispatch 大改:复用页/不关页/模型自检自修/接收侧 model 复核 + cargo-cult 方法论铁律
- [[no-workflow-scope-clarification]] — workflow vs no-workflow 厘清:只「审查判定本身」外发,准备/调研/编排可 workflow

相关:[[zmd-project-entry]]
