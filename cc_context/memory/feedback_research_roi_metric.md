---
name: research-roi-metric
description: 判断调研是否还值得继续，关键不是"调研当下有没有 land 代码"，而是"实施带宽是否能消化未来的金矿"
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

调研某个方向值不值得继续，用 **ROI = 节约时间 / 调研时间** 判断，但**节约时间窗口要扩到"路线图被消化完之前"**，不能只看调研结束当下有没有 land 代码。真正的 stop signal 是**「实施带宽饱和」**而不是「金矿数」或「调研当下未兑现」。

**Why（v1 错误的修正）：** 我 2026-05-08 第一版规则写 "未落地金矿 ROI = 0 / 潜在 100× 兑现 0 → 立刻停"。**这个判定有 bug**——把"调研结束那一刻还没 land"等同于"调研无价值"，漏算 3 块：

1. **延迟兑现**：调研产物（roadmap、估值、排序）要等后续 N 天/周实施期才兑现成 commit。事实是：2026-05-08 停调研那天 0 个 land；2 天后 49 个 commit 把 50+ 金矿里高价值部分全 land 或 demoted。如果按"当下 0 ROI"停，**这 49 个 commit 没有方向、没有优先级**，根本不会发生。
2. **路线图本身就是 deliverable**：`phase3c_optimization_roadmap_v1.md` 是已交付 artifact，不是"未落地金矿"。
3. **Audit 救火依赖调研产物**：11/11 量化金矿 audit 救了 30-65 工程小时，这些 audit 全建立在调研产物上。没有调研就没有 audit 对象。

用户 2026-05-10 反推这个逻辑漏洞，纠正了 v1。

**How to apply (revised)：**

- **节约时间窗口** = 实施期（后续 N 天 / 周）内**预计**能兑现的工程时间节省（不只是调研结束当天）。预测 ROI ≤ 1 才停。
- **调研时间** 包括 prompt 撰写 + agent wall-clock + 读结果 + 归档整理。Round 10 实测 ~22 min（8 agent 并行 × ~3min wall + 我 ~12min 处理）。
- ROI 排序原则不变：
  - **高 ROI** = 项目特异知识（玩家 hint / OnlyEnforceIf 审计）→ 论文搜不到，调研唯一来源
  - **中 ROI** = 工具/参数级洞察（SMAC3 1 行替换、shared_tree 配置）→ 落地成本极低
  - **低 ROI** = 大方向理论 / 排除清单 → 价值在防止重复调研，但单条贡献小
- "明确排除"也算正 ROI，节约的是**未来 session 的重复调研时间**。要写进 roadmap 的"Excluded"段。

**真正的 stop signal：「实施带宽饱和」** —— 不是"调研无 ROI"

- 已有 N 个金矿排队等落地，实施速度跟不上调研速度时停。
- 类比仓库：货堆 50 件等出货，再进新货不解决问题——要先把仓库清掉再进货。
- 信号是 "**实施带宽到顶**"，不是 "**调研产出价值低**"。
- 当排队队列收敛（大部分金矿已 land 或 demoted），实施带宽空出来 → 可以重启调研。

**调研重启的判断**：

- 实施队列 ≤ 10 项 + 剩余项多数 gated by 真长跑数据 / 大工程时间 → 带宽空出，可以再调研
- 距离上轮调研已经过 N 周（学术 / 上游软件有新发布）→ 信息池更新
- 但每次重启**只做 1 round**（避免 R1-R10 那种连环堆积失控）

**Bonus**：让用户校准时间预算（我自己的"金矿"判断常太宽松）。如果用户说"挖不完的样子"——基本是带宽到顶，停！

**关键纠正记录**：
- v0 (失败的)："5 连无金矿才停" → 金矿门槛漂移，永不停
- v1 (有 bug 的)："未落地金矿 ROI = 0 → 立刻停" → 漏算延迟兑现，会过早停止
- v2 (现行)："实施带宽饱和才停 / 队列消化后可重启" → 算延迟兑现 + 算未来 N 天的 commit 兑现速度

**2026-05-10 R13 数据点（强化"audit 必须做"规则）**：

按 v2 规则重启了 R13 调研（8 方向并行），但**直接把 agent 报告 commit 进路线图**（叮嘱 prompt "必须 WebSearch / WebFetch / 不要凭训练数据"，但**没做 R12-style follow-up audit**）。结果用户提醒后补 audit 4 个高 stakes 方向，发现：

- **4/4 audit 都 PARTIALLY 翻盘**（跟历史 5/5 audit 翻盘率一致，叮嘱 prompt 不能替代 source-verify audit）
- 具体错：
  1. DeepSeek V3 价格已过期（被 V4 取代）
  2. cvc5 pin 版本（1.3.3 → 1.3.4，调研当天升 patch）
  3. Pumpkin all_different + table 已实现（transcript 说缺失）
  4. Lübke&Berg paper 是 CP'25 不是 AAAI'25 + plateau-based 不是 paper claim + CP'24 作者搞错 + cake_lpr 日期年份错

**强化规则**：
- 调研 round 出 verdict → 进路线图 / commit 之前 **必须** 做 follow-up source-verify audit（不只 prompt 叮嘱）
- audit 是 **零信任假设**——重新 fetch transcript 引用的所有 URL，不要 trust transcript 的描述
- audit ROI: ~15 min agent + ~10 min processing → 救事实错 4 处 + 防 commit-level 尴尬。比 R5/R7/R11 的工程时间救火（~5-20 hours）便宜，但仍是必做。
- **整理 audit 触发条件**: 任何 R-N 调研 round 在路线图新增 / 修订条目前都要审；不只参数级 / 算法级，**版本号 / 日期 / 工具状态 / paper 引用 / API 价格**都要审

**记忆重要等级**：跟 `feedback_verify_solver_param_claims.md` 同级。两条规则配套：前者管"参数级金矿"，本条管"调研产物 commit 前的 zero-trust audit"。

## 链 (补连 2026-06-01)
- [[archive-research-transcripts]] — 调研归档触发
