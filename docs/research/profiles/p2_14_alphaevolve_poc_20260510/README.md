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

## Verdict: **GO（Anthropic + Gemini 双路径均通过）**

| Proposer | 跑出变体 | 平均分 | 满分变体 | 新颖维度 | Verdict |
|---|---|---|---|---|---|
| Opus 4.7 (Agent 子代理) | 6 | **10.92** / 11 | 5/6 | 5 | GO |
| Gemini 3.1 Pro Preview | 6 | **10.17** / 11 | 1/6 | 2 | GO（质量 -6.9%） |

按 R10 audit go/no-go gate "LLM 提议 cut 在评分上能否显著超过手写 baseline"——两个 model 都 ≥ baseline → 双路径 production 可走。

### Opus 6 变体（同 family 直接外推）

子代理 `ada46d235d22806ab` 一次 spawn 出 5/6 满分 + 1/6 接近满分。新颖维度：output 优先级 / 几何 collocation / capacity-demand 差额 / pose-level binding / load balancing。详见 `evaluator_results.json`。

### Gemini 6 变体（独立 PoC, 已验证）

`gemini-3.1-pro-preview` 同 prompt 跑出 6 变体（详见 `evaluator_results_gemini.json`）：

| # | 名字 | 评分 | 跟 Opus 6 个对比 |
|---|---|---|---|
| 1 | `adjacent_direct_insertion` | 9/11 | ≈ Opus 变体 3 重叠 |
| 2 | `single_commodity_output_homogeneity` | 10/11 | ≈ Opus 变体 2 视角差 |
| 3 | `index_based_port_packing` | 10/11 | ≈ Opus 变体 4 思路重叠 |
| 4 | `recipe_proportional_input` | 10.5/11 | **新颖**（input 镜像 Opus output） |
| 5 | `pure_storage_box` clustering | 11/11 ⭐ | **完全新颖**（hint 2 反向） |
| 6 | `central_port_high_volume` | 10.5/11 | 部分新颖（内部微几何） |

特点：
- 全 6 个 AI Safety Contract OK，全 6 个 binding context OK
- 2 / 6 跟 Opus 高度重叠（变体 1 + 3）—— Gemini 命中率较低
- 2 / 6 完全新颖（变体 4 input 镜像 + 变体 5 storage clustering）—— Opus 没产
- 变体 1 用了未定义 helper（`get_common_commodities` / `adj_port_pairs`），落地成本略高

Token usage: 775 input + 2371 output + 1963 thinking = 5109 total。

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
