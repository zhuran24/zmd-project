# P2 #14 AlphaEvolve cut-evolution PoC（2026-05-10）

验证 LLM 能否为 binding subproblem 生成有用的 cut/hint 变体。

## PoC 设计（绕开 OpenEvolve API key 路径）

User 提议"不能直接调用子代理吗"——绕开 OpenEvolve 工具 + Anthropic API key + Google billing 等所有外部依赖：

| 角色 | 实施 |
|---|---|
| LLM proposer | Claude Code Agent tool spawn 子代理 (`ada46d235d22806ab`) |
| Evaluator | 启发式评分（6 维度: API / safety / 注释 / def / context / 新颖） |
| 凭证 | 消耗 Max 订阅 quota，**不需要 API key** |
| 真长跑成本 | $0（PoC），production 才需要钱 |

## 子代理产出 6 个 cut 变体

来源 transcript: `docs/research/agent_transcripts/ada46d235d22806ab.output`

| # | 名字 | 方向 | 评分 |
|---|---|---|---|
| 1 | `hint_input_slot_commodity_diversity_within_box` | box 内多 slot 选不同 commodity | 10.5/11 |
| 2 | `hint_output_slot_prefer_high_demand_commodity` | 按需求量排序 output slot 优先级 | 11/11 |
| 3 | `hint_collocated_io_pair_same_commodity` | 邻近 in/out slot 同 commodity（用 master placement 几何）| 11/11 |
| 4 | `hint_unused_slot_for_oversupply_box` | oversupply slot 推 `__unused__`（capacity-vs-demand）| 11/11 |
| 5 | `hint_facility_template_port_priority` | pose-level binding 域大小启发 | 11/11 |
| 6 | `hint_balanced_commodity_load_per_box` | box 间 commodity 负载均衡（跟 hint 2 anti-overload 互补）| 11/11 |

## Verdict: **GO**

子代理一次 spawn 出 5/6 满分 + 1/6 接近满分变体：
- 全部符合 AI Safety Contract（soft `model.AddHint`，无 `AddBoolOr` 硬 nogood）
- 全部涉及具体 binding context
- 5 个 **新颖维度**（output 优先级 / 几何 collocation / capacity-demand 差额 / pose-level binding / load balancing）

按 R10 audit go/no-go gate "LLM 提议 cut 在评分上能否显著超过手写 baseline"——6/6 都达到 hint 1/2 baseline 同等或更高 → **GO production**。

## 仍 gated 的部分

启发式评分只验证"代码符合规范 + 有项目 context"，**不验证 cut 求解时间真降**。production 跑 OpenEvolve 真 500 iter 用 binding subproblem 微基准 evaluator 才能知道哪个变体真有用。

production 跑路径（按修订后 audit `a6c3a5f3d9dc7d7f6` + `a9d4b8fc01f24e9b9` + `a7460c780eaa03097`）：

| # | 路径 | 成本 | 备注 |
|---|---|---|---|
| 1 | 付 Anthropic API | ~$90-115 | 最稳，跟 Claude Code 同 model |
| 2 | Gemini 3.1 Pro Preview paid Tier 1 | ~$60-70 | 当前 frontier，比 2.5 贵 +60% input |
| 3 | Gemini 2.5 Pro paid Tier 1 | ~$40-50 | OpenEvolve 直接支持 |
| 4 | Vertex AI Gemini + GCP Free Credit ($110) | $0 + 0.5-1 d 集成 | 19 天到期 |
| 5 | $1000 GenAI App Builder credit | ❌ | 仅 Vertex AI Search/Agent Builder, 不 cover Gemini API |

## 文件清单

- `evaluator_results.json` —— 6 变体启发式评分结果
- 子代理 transcript 在 `docs/research/agent_transcripts/ada46d235d22806ab.output`

## 后续

production 真跑推迟到 168h 真长跑跑出 baseline 数据后再决定（按真长跑 binding solve 时间分布看哪个变体潜力最大，OpenEvolve 真 evaluator 给真效果）。
