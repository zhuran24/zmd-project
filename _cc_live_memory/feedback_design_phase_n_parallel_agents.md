---
name: design-phase-n-parallel-agents
description: "实时推进代码设计阶段 (新 family kickoff / 复杂 algorithm 抉择 / 接口决策), 启 N=2-8 parallel opus 子代理各带不同 slant, main 当 merger. audit 链 (Gemini per-commit + GPT pro 大节点) 是事后, 此 protocol 是事前补 main 同种 RLHF bias. 2026-05-24 user 提议, 2026-05-25 user 加严 N=8."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

实时推进代码设计阶段, main 启 N 路 parallel opus 子代理各带不同 slant, 自当 merger.

**Why**: main Claude 同种 RLHF bias 在设计当下容易"看上去都对", 实际 Gemini cross-check 出洞 (per gemini-review-algorithm-math Day 15/16a/16b round 14 catch 3 致命 bug + 2 schema 漏之教训). audit 链 (Gemini per-commit + GPT pro 大节点 + ultrareview) 是**事后**催熟, parallel 子代理是**事前**预防. 异种 ensemble 已是项目既有 (Gemini + GPT pro 异源), 但 implementation 设计当下还是 main 一个人埋头写完才发出去 — 那个时间窗口 audit 链够不到, N 路并行子代理才覆盖.

User 原话 2026-05-24:
- "实时推进代码设计的时候这里还是只有你一个人来做"
- "建议 N=5, 这周额度要用不完了喵，要亏钱了喵"

**How to apply**:

触发时机 (高 ROI):
- 新 family 实施 kickoff (F5/F6/F7/F8/F9 各一次)
- 复杂 algorithm 抉择 (bounded core minimizer 怎么写 / Hall witness 格式 / LP relax oracle 边界 / cell-flow arc model)
- 接口 / abstraction 决策 (helper 跨 family 复用 / oracle ↔ validator 边界 / master delegate 怎么挂)

不触发 (低 ROI / 噪音):
- apply external patch (已 designed)
- refactor / rename / move file
- doc update / commit msg / build script
- 已 frozen 实施 (spec → code 翻译, 没设计空间)

N 取值:
- 默认 N=2 (基线: correctness-leaning + throughput-leaning 已 catch 大部分单视角盲点)
- **额度多 / hard task / paradigm 层抉择: N=8** (user 偏好, 2026-05-25 起此值)
- 紧时回 N=2 或 N=3

8 路 prompt slant (N=8 用):
1. **correctness-paranoid**: fail-closed soundness, oracle 不可信, TIMEOUT/UNKNOWN/exception 保留旧状态, cert 完整 audit trail, validator trust boundary. R3/R4 加严风格旗帜
2. **resource-throughput**: budget 分配, deletion order heuristic, QuickXplain partition tree, algorithm 真 useful 不是摆设
3. **adversarial-schema**: cert 是 hostile environment 来, schema 加严 (bool!=int / strict base64 / 类型强制), R4 catch 的 6 类漏洞风格 + 主动找设计自己的 blind spot
4. **integration-first**: 跟 lifecycle 9 step / CutStore / F1-F4 / master delegate / 现有 helper 怎么接, 避免重复, 接口风格一致
5. **simplicity-LoC**: 最小可行实现, 砍 over-engineering, readability > flexibility, 不引入新 abstraction 除非必须
6. **rollback-safety**: 失败时 graceful degrade 路径, abort criteria 量化, 回滚 boundary, 已 land 状态怎么 undo
7. **observability**: telemetry / logging / py-spy / RSS sample / proto bytesize 怎么测内部发生了什么. 不只 final verdict, 真发生在 spike/family 内部能 reconstruct
8. **historical-paradigm-context**: 设计要呼应 27 lever 历史 / paradigm_death_baseline, 防止设计自己撞已知死路. cite specific dead lever + 解释为啥本设计不重蹈

N=2 默认 slant: 路 1 (correctness-paranoid) + 路 4 (integration-first).

实操注意:
- spawn 必走**单 message multi Agent tool call** parallel (per CLAUDE.md "无依赖 tool call 并行")
- model 按 [[subagent-model-by-weight]] 重量定 — 设计探索属重活, opus 仍是默认; paradigm 级特别重要可上 fable。`subagent_type="general-purpose"` (default)
- `run_in_background=true` (user 期间能 idle 或干别的, 不 block chat)
- 子代理 0 history, prompt self-contained:
  - 项目背景 (Endfield + 当前 phase)
  - 必读 spec 绝对路径
  - 现已知约束 (PROJECT_LOCK / Gemini math review verdict / R3/R4 加严层)
  - 期望 output 格式 (模块结构 + 关键决策 rationale + 接口 + 测试策略 + 自评 trade-off / blind spot)
  - 具体 slant
- output cap: ≤3000 字中文大白话, 不端着, 重 design 不重 implementation 细节
- **main 当 merger (核心质量保证, 不是 trivial 后处理)**:
  - 2026-05-24 user 提醒 + 文章 cite: "合成步骤是串行的, 不能并行, 本身也要消耗不少 token 和算力", 占总时间 20-50%. 必须算 budget 一部分, 不能急着省跳过. 现实类比: "5 个人同时思考问题, 最后还要开会统一意见, 会议时间比单个人思考还长". 这步省了 = N=5 沦为浪费.
  - **merger 步骤**:
    1. **先 skim 全 N 份再 deep-read** — 防 anchoring on 先读那份的 framing
    2. **按 slant 维度对比** — correctness 路看 fail-closed 覆盖度; throughput 路看 budget 利用率; adversarial 路看 schema 加严点; integration 路看接口一致性; simplicity 路看 LoC + readability. 各路只在自己强项上算分, 不强求全能
    3. **取交集** — 全 N 都说 "必须这样" → 高信号必入; 取各路 strong point — 独家亮点评估是否纳入; 警惕各路独家盲点 (slant bias 副作用)
    4. **resolve disagreement** — main 必须自己拍板, 不要"两条路都说有道理我都写进去"导致 final 内部矛盾. **disagreement 是 catch hidden bias 入口不是噪音** — 哪 2-3 路 strongly disagree, 那是看 hidden assumption 的窗口
    5. **merger 输出格式**: final design + 每路 slant 核心建议摘要 (1-2 句) + disagreement list + 怎么 resolve + main 自评 blind spot
  - **anti-patterns**:
    - 跳过 merger 直接选一份 (常见浪费 mode, N=5 等于 N=1)
    - merger output 只给 final design 没附 N 路 raw + disagreement (user 看不到 reasoning trace, 无法 audit merger 决策)
    - merger 用 throughput-slant 风格急着出 final (没 paranoia 跟自己 5 路 spawn 的初衷矛盾)
    - merger 跟某一路框架 anchor, 其他路被当 "也说了类似的" 一笔带过 (隐性 N=1)
  - **user-visible transparency**: merger output 给 user 时**含 5 路 raw + main 合并 reasoning**. 这不是 niceness, 是让 user audit "main 决策对不对" 的必要 trace. 等于 main 给自己加了 reviewer.
- 实施前必经 Gemini cross-check (per gemini-review-algorithm-math)
- 实施后 commit + Gemini per-commit cross-check (既有 protocol)

**先决条件**: 设计假设要稳了才能 spawn N 路 agent — 假设变 spawn 是空转. 跑 GPT pro 大节点 audit 期间不要 fire (audit 可能改 spec). 等 audit verdict 落地 → spec frozen → 再 kickoff design spawn.

**Cost**: N=5 一轮 opus 子代理 ~5-15 min wallclock, 几十到几百 K tokens. N=8 同 wallclock (parallel), token 跟 N 成 ~线性, merger 时间略增. 比 GPT pro 大节点 audit cheap 一个量级, 比 N=2 多 ~4x. Max plan 额度 weekly reset, 周末未花就 sunk cost — 这周额度多时 N=8 是理性 burn.

## 实战验证 (2026-05-25 session, F6/F7/F8 3 batch N=5 spawn)

Protocol works. 每 batch 都 catch 至少 1 个 main 单独短期难 catch 的 critical finding:

- **F6 batch**: correctness-paranoid catch spec self-inconsistency — `group.demand=46` 全 group 但 spec active_assumption 拆 left=23 bottom=23, cert 单 region 必用 per-region demand 不 group total. Main 一人 design 时 align spec §5b 会埋雷.
- **F7 batch**: correctness-paranoid catch **canonical_rules ↔ spec drift** — spec §1a/§3 写 "1×1 pole" 但 canonical_rules `power_pole.dimensions={w:2, h:2}` (2×2). Throughput agent 实证 4761 candidate pole pose. 跟数据.
- **F8 batch**: correctness-paranoid catch 两 critical:
  1. `pole_to_pole_jump_radius` canonical 无 field (只有 `power_coverage_radius=5` 是 pole→facility, semantically 不同) — caller-supplied
  2. protocol_core anchor 是 **state-dependent** (master 从 7200-pose pool 选), 不固定
  - Throughput agent 警告 `build_power_network` ~1.5s/call + cert.power_graph_b64 ~4MB/cut — design 全删 graph snapshot + evaluator 走 scope-binding monotone-preserved invariant (跟 F6 R2 同 pattern)

实测耗时:
- 每 batch spawn 5 agents parallel: ~5-15 min wallclock return (single longest agent dominates)
- main merger 实际 ~5 min (深读 5 份 + 对比 + 拍板)
- single batch end-to-end (spawn → merger → implement → gate → commit): ~30-50 min

Sub-agent quality 跨 batch 一致 — opus model 在每 slant 都给可用产出. 没出现 "某 agent 完全跑偏" 的浪费 batch.

merger anti-pattern 实战教训 (避):
- F8 batch: 我开始 implement F8 用 literal mode (literals=non-None), 没仔细看 spec `_FAMILY_MODE_MAP["power_grid_reach"] = "geometric"` 锁. 这是**没听 merger output 里某路 raw 的细节**导致. fix 重做 cut object + tests. cost ~15 min. 教训: merger output 必 cite spec line, main implement 时 reread spec 必含 mode lock.
- **2026-05-26 prod-scale spike batch** (跟 [[main-merger-scope-creep-bias]] 配套): N=8 design simplicity slant explicit 划界 "spike 不接 LBBD 外循环 / 不答'P1.3A close 了吗'", main merger D3 折中时 dilute 成 "5 iter × 3 candidate + sub-problem stub" 隐性 N=1, leak 进 P1.3A 主体. 2 round Gemini cross-check 全 NOT_GO + 10 finding fix 但 0 catch phase boundary leak. User 2026-05-26 catch + force shrink 回 simplicity scope (20-29h → 8-12h Claude). 教训: **simplicity slant explicit phase boundary 划界必 verbatim listen**, 不 fold; Gemini cross-check 看不见 phase boundary 层 audit, user 是唯一可信 phase boundary auditor.

**Refs**:
- gemini-review-algorithm-math — main 同种 bias 实际案例
- gpt-error-types-taxonomy — 3 类错估 (算法 / 前提 / 数学能力上限)
- [[lazy-mode]] — 替 user 想, 不无谓盖章
- [[paradigm-phase0-cheap-gate]] — 每 paradigm 实施前 Phase 0 cheap gate (跟此 protocol 不冲突, cheap gate 验前提, N 路并行验设计方案)

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[long-op-background-mode]] — N=8 spawn = 长跑用 background
