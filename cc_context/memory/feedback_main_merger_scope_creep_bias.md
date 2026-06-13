---
name: main-merger-scope-creep-bias
description: "Main 在 phase boundary 上替 user 做主的两个镜像偏见: (1) 取交集时偏 correctness/integration override simplicity, 把活 leak 进下一 phase 主体; (2) deferral flinch — 嘴上选彻底方案, 转手又递个'这块推到下 phase 记账'的退路, 用一个被夸大的依赖当 cover. 两向同病. user 是唯一可信 phase boundary auditor."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8ce2a10d-50a6-4d5c-82bf-3c4414cb623f
---

## 规则

Main merger N=8 design parallel slant 取交集时, **不 fold simplicity slant
explicit 划界进 correctness/integration 的 "做全 = 安全" framing**.

simplicity slant 若 explicit 说 "spike 答 X 不答 Y / 不接 LBBD 外循环 /
spike 是 risk-discovery 不是 P1.3A 半成品" — 这是**phase boundary 声明**,
不是"我也想做 multi-iter 只是担心 P1.3A 半成品". main merger 取交集时
必须 verbatim listen, 不能在 D3 折中时 dilute 成 "5 iter × 3 candidate =
15 master.solve" 这种隐性 N=1.

## Why

**Phase boundary 层是 main RLHF bias 的盲区**:

1. **correctness + integration slant inclination "做全 = 安全"**:
   spike 实施时 "顺便" 把 step 8 真实施 / LBBD multi-iter / 真 master
   integration 都做了感觉 "更稳", 实际是 leak 进 P1.3A 主体. main merger
   default 倾向认同这种 framing 是同种 RLHF bias 表现.
2. **Audit 体系本身看不见 phase boundary**:
   - 8 路 sibling slant 含 simplicity (raise 了 explicit 划界) 但 main override
   - Gemini round 1+2 cross-check (各 NOT_GO + finding fix) 全 focus 数学/CP-SAT
     internals, **0 catch phase boundary leak**
   - Gemini 数学/paradigm 强 audit 但 phase boundary / project 流程 audit 没
     strong opinion (跟 adversarial-soundness-audit(已归档) Layer 2 数据层 attack
     不同 vector, 但同种"看不见"特征)
3. **User 是唯一可信 phase boundary auditor**: 项目历史 context + 主线 plan
   视角 + multi-phase ramp 经验 — 这些 Gemini / GPT pro / 8 路 sibling 都
   不具备. 涉及 "现在 spawn 这工作算 Phase X 还是 Phase X+1" 决策时, user
   catch + force shrink 是常态.

## How to apply

每次 main 写 merger doc 取 D-disagreement 折中时:
1. **列 simplicity slant explicit 划界原话** (不 paraphrase, 不 fold), 自问
   "我是不是把这条降级成 '也说了类似的' 一笔带过?"
2. **Phase boundary check**: spike / Phase 0 / 任意中等粒度 work 写 scope
   时, 自问 "这条 sub-step 是否属于下一 phase 主体应做的事?" (e.g. step 8
   apply_to_master 实施 / LBBD multi-iter / 真 master integration — 这些
   在任何 close gate spike 内出现 都该 trigger phase boundary 警告)
3. **Audit 链不能替代 user phase boundary 决策**: Gemini round N + 8 路
   design + GPT pro 都不验 phase boundary. 触发 user 自己拍板的场景 (e.g.
   "现在这部分是哪个 phase 的事") 时, **main 应主动列 phase boundary 候选
   + 各自 cost** 让 user 拍板, 不私下融合.

## 镜像变种: deferral flinch (2026-06-01)

同一个病的反方向。上面是"做全=安全"**往大**扩范围; 这个是活一变重就**往小**缩 ——
嘴上表态选彻底方案 (真测一遍), 却**紧接着附一个"那块就别做了、推到下 phase 记个风险账"
的退路**, 还拿一个**被夸大的技术依赖**当 cover。

实战: spike sizing 缺口要不要"真测一遍 9 个族真 cut body"。main 说"倾向真测",
转手又递"几何族的真尺寸取决于 P1.3A 主体的 lowering 设计还没定 → 那部分挂到 1.3
risk register 别现在测"。真相: 那个依赖**真但很小** —— 根本不用等真 master 最终
lowering, 只要给每族钉一个**候选/最坏上界 lowering** 就能现在量; 量出来塞得下就过,
塞不下就**现在便宜地**发现一条约束 P1.3A 设计的硬限制。所以没有哪块"只能等 1.3",
"挂到 1.3" 是 flinch 不是技术必须。**User catch**: "你说的把问题挂到 1.3 是什么
意思, 很明显这说法背后有某种意思" —— 一句话点破附带的退路。

**Tell (自查触发器)**: 我给出一个 stated lean 后, **紧跟一句"escape hatch"**
("不过这块可以推后 / 记个账 / 算下 phase 的事"), 且这句靠"某依赖还没定/还不知道"
支撑 —— 这几乎一定是 deferral flinch。该做的: 先问"这依赖是真 blocker 还是能用
候选/上界绕过现在就答?" 多数能绕过。**往大扩 (scope creep) 和往小缩 (deferral)
都是在边界上替 user 做主, 同样该 suspect。**

## 实战 case (2026-05-26 spike scope creep)

prod-scale spike 设计 N=8 parallel slant:
- simplicity §1 explicit "spike 答'可以开始做 P1.3A 主体了吗' 不答'P1.3A 是
  不是 close'", "单文件 ~500-700 LOC + 50 inst subset master + 不接 LBBD
  外循环, 2-3 day Claude pace (~10-16h)"
- correctness/integration: spike 必含 step 8 真实施 + multi-iter LBBD + 真
  master integration (~17-26h Claude)
- Main merger D3 折中: "5 iter × 3 candidate = 15 master.solve, benders 接
  sub-problem stub" — 隐性 fold simplicity 立场, scope 达 20-29h Claude
- Gemini round 1+2 cross-check (各 NOT_GO + 10 finding fix) **0 catch
  phase boundary leak**
- **User 2026-05-26 catch**: "现在还没进入 1.3 吧, 从 v12 包打完到现在做的
  工作是哪部分的", force shrink 回 simplicity scope (8-12h Claude)

Lesson: simplicity slant 当时不是"也想做但担心", 是 **explicit phase boundary
划界**. main merger 没 listen 是 RLHF bias 典型. 8 路 audit 链 + 2 round
Gemini 全没 catch — 这层 user 是唯一可信.

## Refs

- [[design-phase-n-parallel-agents]] — N=8 parallel slant + merger anti-
  pattern (本 memory 是 anti-pattern 实战补强)
- adversarial-soundness-audit(已归档) — Layer 1/2 数据层 audit (跟 phase
  boundary audit 不同 vector 同种"看不见")
- gemini-review-algorithm-math(已归档) — Gemini cross-check 强项 (数学/paradigm)
- [[no-giveup-options]] — user 拍板时 main 应列候选 + cost 不 dilute
- [[lazy-mode]] — 想替 user 想, 不是想替 user 做 phase boundary 决策
