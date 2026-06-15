---
name: gpt-delivery-acceptance-discipline
description: "外发 GPT Pro/owner 补丁的本地验收纪律主题索引——总原则=GPT 自验永不可信、CC 价值在复现判别+端到端验收+连带收尾;细分见各子节点"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

外发 GPT Pro(及 owner)拿回的补丁/审查交付的本地验收纪律。总原则: **GPT 自验摘要永不可信**, CC 的价值在"复现判别 + 端到端验收 + 连带收尾", 不是橡皮图章。本节点拆成以下聚焦子节点:

- [[gpt-delivery-no-blind-trust]] — 核心原则 + 4 条 why(自验只跑 targeted/补丁自带 bug/probe 可能不判别/probe 硬编码 Linux 路径)+ 标准验收链 7 步(reviewer probe 复现→git apply→patched 转拒→独占全量 xdist→preflight_gate 全绿→修连带→推锚 commit)。
- [[gpt-delivery-probe-discrimination]] — probe 不判别时的判别手段: git stash 对比、git apply --include 红→绿双证。
- [[gpt-delivery-completeness-semantic-consumers]] — 完备性断言陷阱: 数据流入口唯一 ≠ 语义消费点唯一(F-03→R3 被 RAB filter 推翻)+ r2→r3→r4 收敛模式。
- [[gpt-delivery-archive-ruff]] — GPT .py 工件归档进仓库前必 ruff(归档不是 CI 豁免区, 邮件轰炸教训)。
- [[gpt-delivery-owner-patch-and-severity]] — owner 亲发补丁也走全验收 + pre-push mypy gate 挡 Optional[str] + 严重度自判(availability vs soundness)。
- [[gpt-delivery-dont-track-model-downgrade]] — 模型对不对/降没降级是脚本的活, 别手动盯也别挂嘴边, 默认信脚本 exit code。
- [[gpt-delivery-adversarial-agent-review]] — ultracode 开时对 HIGH soundness patch 起对抗 subagent 静态验证(只读不跑测试)。

关联 [[zmd-checkout-env]]、[[zmd-project-entry]]、[[no-workflow-use-chrome-gpt-review]]。
