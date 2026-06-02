---
name: external-review-reproducibility
description: "GPT 全量审查报告 reproducibility 不足, 必须配下载副本; 同一轮 sandbox 链接 vs 二次重建可能 finding 列表都不一样"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

GPT-5.5 Pro 全量审查跑两次同一个 prompt 可能产出**不同的 finding 列表**, 即使 in-distribution 都是 OPUS-级模型。

v3 review (2026-05-13) 实例:
- **第一次**: GPT 沙盒生成 5 finding + 元层面 3 条 (548 行报告), sandbox 链接 `sandbox:/mnt/data/...` 几小时后"文件已过期" (ChatGPT sandbox temp file lifecycle)
- **第二次**: 用户让 GPT 重建一份, 产出 4 power-subproblem finding (224 行), **独有 P0 #2 (pole alternatives exhaustion) 第一次没出**
- 我合并成 6 条 follow-up, 但第一次的 sandbox 报告完整内容只剩在 chat transcript 里 (压缩前)

**Why:** LLM 全量审查不是确定性管道, sampling temperature + tool order + chat context 都影响 finding 顺序和深度。即使是 frontier 模型 (Opus 4.7 / Sonnet 4.6 / GPT-5.5 Pro), 同一份代码包 + 同一 prompt 跑两次可能 miss 不同的点。**单次报告不能当真理**, 多次报告交叉才能信。

**How to apply:**
- 每次外部 review 包给出时, 在 README 里**明确写 "请把报告 markdown 同时下载到本地"** — 不要光靠 sandbox 链接
- 用户拿到 sandbox 报告**立刻 cp 到 `~/下载/` 持久副本**, 不要拖几小时
- 同一份审查包**可以跑 2-3 次**抓不同 sampling 的 finding (尤其是元层面问题), 然后合并
- 如果两次报告冲突, 信**保守的那条** (cut 过切风险 / exactness 风险 / data loss 风险方向)
- v4+ 跟之后的审查包都应该带这条提示, 不只 v3 这次
- 跟 [[verify-solver-param-claims]] 同源: 不要信单一信源, 必须 verify

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[gpt-review-prompt-armor]] — 单跑有 variance → armor 强制多死法/多份交叉
- [[index-packaging-cluster]] — 外审打包簇 hub
- [[no-causal-claim-from-n1]] — 同 prompt 两跑不同 = 别从 N=1 归因(同根)
