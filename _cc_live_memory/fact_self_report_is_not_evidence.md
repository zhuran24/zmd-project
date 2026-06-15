---
name: fact-self-report-is-not-evidence
index_summary: "自验摘要/metadata/单次结果不裸信,靠独立复现和端到端验收"
description: "抽象事实: 外部模型/工具/我自己的自验摘要、明面元数据、单次结果都不是最终证据; 可信度来自独立复现、对拍、端到端验收和可判别 probe。"
metadata:
  node_type: memory
  type: fact
---

## 抽象事实

自称验过、明面 metadata、model slug、thinking marker、单个 targeted test、一次 agent verdict，都只是线索，不是最终证据。尤其外发 GPT Pro 的交付：找洞能力强不等于补丁可信；自验摘要和明面模型字段都可能骗我。

可信的闭合来自我能独立复现的判别链：原始 finding 可复现，probe 能区分 patched/unpatched，补丁打上后端到端测试和 preflight 通过，必要时用独立 oracle/fuzz/proof 对拍。GPT Pro 降级这类通道问题，当前唯一可靠信号是生成耗时，而不是明面字段。

## 首批投影

- [[verification-independent-backstop]] — 验证类任务不能只信 main 或子代理转述。
- [[no-gpt-downgrade-evidence]] — 明面字段撒谎,降级以 elapsed_s 判。
- [[agent-vs-workflow-dispatch]] — 外发是获取候选/审查,不是橡皮图章。
