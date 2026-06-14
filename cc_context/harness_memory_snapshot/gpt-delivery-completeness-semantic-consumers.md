---
name: gpt-delivery-completeness-semantic-consumers
description: "完备性断言(「X 是唯一入口/在此过滤即完备」)的陷阱:数据流入口唯一 ≠ 语义消费点唯一——F-03→R3 实测被 RAB build-time filter 推翻(它不经 port specs 却独立消费同一语义);必须按语义全仓 grep 穷举所有读处,不是只追一条数据流;附 r2→r3→r4 修复收敛模式"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

**「唯一通道」论证教训 (2026-06-12 F-03→R3, 自己栽的)**: 验收 F-03 时我论证「`extract_port_specs` 是商品进 routing 的唯一入口, 在此过滤=完备」——下一轮 reviewer 就用 RAB build-time filter 推翻 (它不经 port specs、独立消费同一「端口 front 可达性」**语义**)。

教训: **数据流入口唯一 ≠ 语义消费点唯一**; 这类完备性断言必须按"语义"全仓穷举消费点 (grep 该语义的所有读处), 不是只追一条数据流。

修复链收敛模式也值得复用: r2 修主通道 → r3 修侧门+加未来 fail-closed 守卫 → r4 专门一轮穷举确认——每轮 brief 把上轮修复点名为攻击面, 让 reviewer 找"同类的下一个"。

母节点 [[gpt-delivery-no-blind-trust]]。
