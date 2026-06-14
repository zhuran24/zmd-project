---
name: fact-zero-finding-is-not-proof
description: "抽象事实: 审查零 finding 只能说明该审查没找到问题,不能证明没有问题; 终结需要独立性可保证的对拍/fuzz/proof,或多轮独立零 finding 加外部计数闭合。"
metadata:
  node_type: memory
  type: fact
---

## 抽象事实

审查只能证明「发现了问题」；零 finding 不能证明「没有问题」。零 finding 与 reviewer 到达能力上限在结果上不可区分。尤其长上下文/外发模型/多轮审查，负结果必须按能力边界解释。

真正能推进到闭合的东西是独立性更强的证据：本地差分对拍、fuzz、独立 oracle、proof-carrying verifier、fresh full re-audit、以及 owner 仓库外维护的连续独立零 finding 计数。零 finding 可以计数，不能单次封神。

## 首批投影

- [[verification-independent-backstop]] — re-audit 不能降 scope/rigor,必须 fresh full。
- [[memory-currency-protocol]] — living 计数/状态不能散文手抄。
- [[authoritative-numbers-single-source]] — 计数走单一来源和 gate。
