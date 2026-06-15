---
name: no-gpt-downgrade-evidence
index_summary: "24 次交付数据:4 路并发触发 Sentinel 后脚本特征发送降到 40-70s,手动(Edge/App)仍真 Pro;唯一可靠信号=elapsed_s(model_slug/thinking_marker 全撒谎);找客服真证据=时长对比非 HAR sentinel 请求"
description: "GPT Pro 降级机理+通道实证(2026-06-11 夜 24 次交付数据):4 路并发触发 Sentinel 后脚本特征发送被降到 40-70s,手动发送(Edge 或 App)仍吃真 Pro;唯一可靠降级信号=elapsed_s(model_slug/thinking_marker 明面字段全撒谎,连真 Pro 也 none);App=独立手动通道;找客服真证据=时长对比(手动 43min vs 脚本 40-70s),HAR 里 sentinel 请求不算证据"
metadata:
  node_type: memory
  type: feedback
---

> 事实依据: [[fact-self-report-is-not-evidence]]

**降级机理 + 通道实证(2026-06-11 夜, 24 次交付数据)**: 脚本发送白天 21h / 20+ 次全真 Pro(elapsed_s 21-44min), 直到一次 4 路并发触发 Sentinel(~22:16)→ 此后**脚本特征发送被降到 40-70s, 但手动发送(Edge 或 App)仍吃真 Pro**(22:42 手动 R2 = 43min, 轻量手动测试秒回健康)。**唯一可靠降级信号 = elapsed_s**: `model_slug` 全程 `gpt-5-5-pro`、`thinking_marker` 全程 `none`(连真 Pro 也 none), 明面字段全撒谎。**App = 独立手动通道**, Edge 脚本被 flag 时 App 仍能正常手动发; 但裸开 App 无 CDP 9224 → `--resume` 盯不了, 手动收交付到 `C:\22957\download`。**"HAR 里有 sentinel 请求" 不算证据**(sentinel 是所有 ChatGPT 会话通用的请求门, 人人都有, 客服一看就知道); 找客服的唯一真证据是时长对比(同 Project / slug, 手动 43min vs 脚本 40-70s)。
