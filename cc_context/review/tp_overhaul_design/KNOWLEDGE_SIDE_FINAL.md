# 知识侧 normalize 最终方案 (km-arbiter)

> **v5 状态头 (最新, 反映实际落地)**: owner/team-lead 已按 **GPT 7-fact 路线**落地到 live 树
> (7 个 fact_*.md + MEMORY.md 抽象事实层块 + fact gate + exemptions + harness sync 已 apply)。
> 真 live 树实测 `check_memory_tree.py --require-live-mirror` = **exit 0** (head 55d8c33+, 102 节点, 7 fact)。
> 我的 2 个复验 finding 都已按推荐修法解决 (F1 design-creative-use-team 加 fact 回指; F2 harness sync gate
> 降 warning)。下方 v4 的「retype scope」是我吸收 skeptic 后的备选方案, **已被 owner 的落地动作 supersede**
> —— 留作记录, 不是当前实现。registry 抉择见 **§7 (最新追加)**。
>
> ---
>
> ## (历史) v4 — 吸收 skeptic 反 transclusion, team-lead scope 裁决
>
> 状态: 备选方案 (已被 7-fact 落地 supersede)。我未动 live 树。
> 全部字节/节点/wikilink/gate 结果**在当前真 repo 副本实测**。
>
> **一句话**: 不照搬 GPT 的「新建 7 个 fact 副本」(违反本树自己的反 transclusion 架构)。最终 =
> **0 个 repo 新建 + retype 2 个既有权威节点成 type:fact + 既有投影 wikilink 回指 + 1 个 harness 真新建
> + ledger + forcing-gate**。已验证 repo 形态 exit 0 (facts=2, edges=15, exemptions=49, MEMORY.md 19685)。

---

## 0. 方向修正 (诚实记录: 我吸收 skeptic, 推翻自己 v3)

v3 我采纳 GPT「新建 7 个独立 fact」。**这违反了 `memory-tree-structural-health` §实例/分身模型自己确立的架构** (实测引原文):

> 「**规则/判断**类: **不 transclude 逐字副本** (满树重复=clutter)。靠 **wikilink 链接** (指权威节点不重述)。
> **漂移恰发生在抄了值/重述了规则而非"指"的地方**。」

GPT 的 fact body 是**重述的抽象** (不是指针) = 副本 = 新 drift 债 = **正是要治的病**。km-skeptic 对, team-lead 倾向
skeptic 的 scope 对。**正确 normalize = 把既有权威节点 retype 成一等 fact (不造副本) + 投影 wikilink 它**, 不是新写 7 份抽象。

---

## 1. 最终四块方案 (能直接照着落地)

### ① ledger (standing-authorizations.json) — 做
两边同意。真值源、非 fact 簇、过尺子。落 `cc_context/memory/standing-authorizations.json`, schema
`{action, requires_user, condition, note}` (gpt_dispatch / workflow / commit_push / memory_sync / opsec 等每项
requires_user 真假)。harness 留轻量索引 stub。CLAUDE.md「授权/例外的权威枚举」指向它, 不在散文临场解释。
> 这是把"要不要问"从临场感觉变查表, 独立于 fact 簇成立。

### ② retype/link 既有 (不造副本) — 核心动作

| 抽象事实 | 承载方式 | 具体 slug + 加什么 |
|---|---|---|
| decision-boundary (判据=能自己做 + 目标/先例/放开开关=站着授权) | **retype `root-cause-over-symptom`** 成 `type: fact` | frontmatter `type: feedback`→`type: fact` (name 不变, 所有 `[[root-cause-over-symptom]]` 引用不变)。它已含两层 (实测含"放开/既定授权/额度", 且 body 第二段就是"能做却请示"的根) + 已是卸责病族上游 |
| forcing-function-required | **retype `memory-currency-protocol`** 成 `type: fact` | 同上改 1 行。rule#7 是这条的权威表述 + 有 stamp 实例 |
| (上面两个 fact 的投影) | **保持 feedback, wikilink 指 fact** | lazy-mode / no-reply-means-agree / workflow-approval-not-avoidance / no-gpt-concurrency-field / subagent-for-closed-loop-tasks 指 root-cause; structural-health / authoritative-numbers-single-source / zmd-env-ci-gate / zmd-env-prepush-gate 指 memory-currency。**多数已经在指** (实测 15 个投影已引这两 fact) |
| evidence-before-story | **不新建、不 retype** | no-causal-claim-from-n1 已是权威; 让 verify-solver-param-claims / verification-independent-backstop wikilink 它 (km-facts-codex 对) |
| self-report / external-claims | **不新建** | 整族 no-gpt-* + agent-vs-workflow-dispatch + harness gpt-delivery-* 已厚覆盖; wikilink 既有 |

> **为什么 retype root-cause 而非 lazy-mode** (精确化 skeptic 一处事实): grep 实测 **lazy-mode 完全不含
> "目标=站着授权/放开开关=授权"层** (站着/授权/放开/额度/并发 全 False) —— 它只讲"替用户想/少问"。
> goal=授权那层在 root-cause (放开/既定授权/额度 全 True)。lazy-mode 装不下 decision-boundary 的 goal 半边,
> 故 retype root-cause (含两层), lazy-mode 保持 feedback 指它。
>
> **技术点**: retype 用 `type: feedback → type: fact` (GPT gate 的 `_is_fact_node` 直接认 `^type: fact$`),
> **不用** team-lead 措辞的 `node_role: fact` (gate 认不出, 需额外改 gate)。两者效果一样, 前者改 1 行 frontmatter。
> retype 后该节点不再是 projection candidate (不需引别的 fact), 作为 fact 需 ≥1 backlink (已满足); sync 投影
> 看文件名前缀不看 type, 不受影响。

### ③ 真新建 fact: 仅 1 个, 落 harness

**`review-proves-presence-not-absence`** (= GPT 的 zero-finding-is-not-proof, 认识论母命题):
- 抽象: 审查只证「有问题」、永远证不了「没问题」; reviewer 零 finding 与「能力到上限」结果不可区分; 终结靠
  独立对拍/fuzz/proof-carrying 或多轮独立零 finding + owner 仓库外计数。
- **为什么这条够格真新建** (过 team-lead 判据 + skeptic「真缺才建」): grep 实测 repo **无任何节点承载这个
  认识论命题** —— verification-independent-backstop 是**操作层** (派 backstop/不切窄/re-audit, body 无"证不了无问题"),
  handoff 是现状源 (P1.2 闭合标准是现状不是命题母节点)。它连的投影 (四线 + calibration) **大多在 harness**。
- **落 harness** (`~/.claude/.../memory/review-proves-presence-not-absence.md`), 不进 repo (投影在 harness, 且 repo
  gate 不扫 harness)。repo 侧若要可见, 防孤立锚用 `[[verification-independent-backstop]]` (repo 真节点)。
- body 用 GPT 的 zero-finding body (质量好) 即可, 改 name 为 review-proves-presence-not-absence。

> 净真新建 = **1 个 (harness)**。repo 新建 = **0**。完全落在 team-lead「0-2」目标内。

### ④ forcing-gate (并入 check_memory_tree.py) — 做, opt-in + fail-soft

采用 GPT patch 的 `_check_fact_projection_contract` (km-forcing 验证过, 只查引用图、语义忠实诚实交人工):
- fact 节点 (type:fact / name fact-* / 文件名 fact_*) 必须 ≥1 projection backlink;
- 新 feedback/projection 节点须引 ≥1 fact, 否则进 `memory_fact_projection_exemptions.txt` baseline;
- stale_exemptions (已补 ref 却没出列) + unknown_exemptions 报红 → baseline 只缩不涨。

**两处必改 (我复验抓的, 见 §2)**:
1. **Finding 2**: GPT 把 `_check_harness_projection_sync` 进 **errors** (硬阻断 pre-push)。**改为 warnings**
   (跟既有 _check_harness_mirror 一致) —— 否则 owner 本机每次 pre-push 被无关 harness 存量 drift 卡死, 违反项目
   "harness 不进自动 gate"哲学。这是 opt-in/fail-soft 原则在它自己身上的应用。
2. **exemptions baseline 按本方案重算**: GPT 的 40 行 baseline 是给"新建 7 fact"算的。本方案 retype 2 个既有
   → baseline = 所有不引这两 fact 的 feedback projection = 实测 **49 行** (我已生成, 见落地)。

> gate 识别 fact 用 `type: fact`, 所以 retype 的两个节点会被 gate 当 fact、要求有 backlink (已满足)。

---

## 2. 独立复验结论 (team-lead 铁律: 不裸信 GPT 自报 = review-proves-presence 现场)

把 GPT patch 打到**当前真 repo 副本**跑它改后的 gate:
- GPT 自报「gate passed nodes=101」→ **真 repo exit 1** (它在自己 snapshot 验, 缺 owner 06-14 新加的
  design-creative-use-team)。**自报失实** —— 这条复验本身就是 review-proves-presence / self-report-is-not-evidence 的活案例。
- patch 能干净打 (dry-run exit 0)、双写 cc_context+_cc_live 正确、live-mirror byte-identical —— 这些 GPT 做对了。
- **本方案 (0 repo 新建 + retype 2) 真 repo 实测 exit 0** (facts=2, edges=15, exemptions=49, MEMORY.md 19685, live mirror byte-identical)。

两个 finding (都已在方案内处理):
- **F1**: GPT baseline 漏 design-creative-use-team (缺口穷举确认只此 1 个)。本方案重算 baseline 已含它, 不复发。
- **F2**: harness sync 硬 gate → 降 warning (§1④)。

---

## 3. 落地步骤 (team-lead 可直接照做)

```powershell
# 1. retype 2 个既有节点 (cc_context/memory + _cc_live 双写, 各改 1 行 frontmatter):
#    root-cause-over-symptom.md / feedback_memory_currency_protocol.md: type: feedback -> type: fact
# 2. 给尚未指这两 fact 的少数投影补 wikilink (实测 15 个已指, 缺的补 [[root-cause-over-symptom]] /
#    [[memory-currency-protocol]]); evidence 簇给 verify-solver-param-claims / verification-independent-backstop
#    补 [[no-causal-claim-from-n1]] (若想让 no-causal 也升 fact 可选, 但非必须)
# 3. 新建 standing-authorizations.json (ledger) + harness 索引 stub
# 4. 新建 harness review-proves-presence-not-absence.md (用 GPT zero-finding body, 锚 [[verification-independent-backstop]])
# 5. 并入 gate: check_memory_tree.py 加 _check_fact_projection_contract (取自 GPT patch),
#    但 _check_harness_projection_sync 进 warnings 不进 errors (F2)
# 6. 建 cc_context/memory_fact_projection_exemptions.txt = 不引两 fact 的 feedback projection (实测 49 行)
# 7. 字节同步 live mirror:  robocopy cc_context\memory _cc_live_memory *.md /MIR
# 8. 同步 harness:          python cc_context\tools\sync_memory_to_harness.py --apply
# 9. 验证:
python scripts\check_memory_tree.py --require-live-mirror   # 期望 exit 0 (facts=2)
python cc_context\tools\check_harness_links.py               # harness 死链复查 (含 review-proves)
```

硬约束 (实测): _cc_live_memory 存在 → CI/pre-push 自动 --require-live-mirror → repo 与 _cc_live **逐字节一致**
(retype 的 2 个文件两边都要改, 用 robocopy /MIR 而非手敲)。

---

## 4. 给 exec-arbiter 的上游根因 fact slug (已发)

注入文案末尾 wikilink = **`root-cause-over-symptom`** (retype 成 type:fact 后即「decision-boundary / 能做却请示」
的认识论母 fact, name 不变)。
> 修正: v3 我发的是 `fact-decision-boundary-is-ability` (GPT 新建副本 slug)。本方案不新建该副本, 改 retype
> root-cause —— 所以正确 slug 是 `root-cause-over-symptom` (它现在就是那个 fact)。**已重新通知 exec-arbiter。**

---

## 5. 后续迁移 + 第二轮注意

第一轮: retype 2 fact + 既有投影回指 + ledger + 1 harness fact + gate + 49 豁免 baseline。
第二轮按簇消灭 baseline (授权边界 → 证据/叙事 → GPT交付 → 验证终结), 每迁: 投影加 `[[fact]]` wikilink (不重述) +
从 exemptions 删行 (gate stale_exemptions 强制闭环)。
- **不做 140 节点全树重构** (skeptic 对: index 父节点已是两层)。
- **第二轮 F5/F6/F7 簇** (GPT交付/审查/opsec) 投影纯 harness-only: repo fact body **不能 `[[harness-only-slug]]`**
  (unresolved 硬阻断); 那些 harness 投影用 `[[verification-independent-backstop]]` 当 repo 锚 (projection-codex 提醒)。

---

## 7. registry 抉择: 注册 subject vs 手搓 fact 节点 (最新, 据 sync_doc_subjects.py + registry 源码实测)

team-lead 追加: `cc_context/knowledge/` 是官方 control layer, 有现成 `sync_doc_subjects.py --check` forcing function,
新 gate 别重复它。我读了 README + PROJECT_SUBJECT_PROJECTIONS.json + sync_doc_subjects.py 源码, 结论如下。

### 7.1 两个系统是不同层, 零重叠 (不是手搓平行系统)

| | sync_doc_subjects (registry) | fact gate (_check_fact_projection_contract) |
|---|---|---|
| 管什么 | 同一段**文字**在多处的**字面副本同步** (transclusion) | memory 树内**节点间的引用边存在性** (graph shape) |
| subject 在哪 | `docs/subjects/*.md` 的 `<!-- SUBJECT-FIELD -->` 块 | memory 树 `type:fact` 节点 |
| projection 是什么 | 同一段文字嵌进 CLAUDE.md/docs/memory 的 `<!-- DOC-SUBJECT -->` **字段块** (带 sha256) | feedback 节点里的 `[[fact-x]]` **wikilink 边** |
| 查什么 | block body + marker sha == subject field (**byte 同步**) | fact 有 ≥1 回指 + 新 feedback 引 fact (**edge 存在**) |
| 现状 | 真 repo exit 0 (6 subjects/19 fields/30 projections) | owner 已落地, 真 repo exit 0 (7 facts/24 edges) |

**一个查 byte 同步, 一个查 edge 存在。registry 根本管不了 memory 树内的 wikilink 引用图** (它只认
SUBJECT-FIELD/DOC-SUBJECT 标记块)。所以 fact gate **不重复** sync_doc_subjects, 它填的是 registry 的盲区。
km-forcing 已同步此边界。

### 7.2 「任务推进方式」该注册 registry 还是手搓 fact? — 答: 都不是 registry, 已落 fact

逐项过 (据实测, 诚实对 team-lead「优先注册 registry」给出不同判断):
- **registry subject 的用例 = 同一段文字有多处字面副本、需防漂**。grep 实测: 「回合出口门/四终态」内容
  **只在 CLAUDE.md(行为契约) + lazy_mode/fact 节点(memory 协作层), docs 树里完全没有** (docs/subjects 6 个
  全是项目内容治理类, 无行为规则)。
- 关键: lazy-mode / root-cause / fact 节点**不是 CLAUDE.md 那段文字的字面副本**, 是「同一抽象的不同侧面/不同节点」。
  registry 的 transclusion 同步的是**逐字副本**; 把不同侧面的节点硬塞成一个 subject 的 projection 块 = 误用 (它们
  body 不同, --check 会永远 drift)。所以 **「任务推进方式」不适合注册成 registry subject**。
- 它适合的正是 **fact 节点 + wikilink 引用图** (已落地的 7-fact 路线): fact 是抽象, lazy-mode 等是不同侧面的
  投影, wikilink 回指 —— 这是 registry 管不了、fact gate 正好管的层。
- **所以: 不注册 registry, 以已落地的 fact 节点承载。** 与 team-lead「优先注册」相反, 理由是 registry 的
  字面同步语义不匹配「不同节点写同一抽象的不同侧面」。

### 7.3 一个真实的 registry 候选 (供 exec/owner 定, 不在知识侧 scope)

grep 发现 `cc_context/global_CLAUDE.md` (repo 镜像, 19332B, 旧版「懒狗」段) 与 `~/.claude/CLAUDE.md`
(home, 8132B, 新版「回合出口门」段 + 含 `[[fact-decision-boundary-is-ability]]`) **不同步**。
**若**这两处本该是同一份全局 CLAUDE.md 的副本 → 这才是 registry transclusion 的真用例 (注册成 subject 防漂)。
但两者大小差异大 (19332 vs 8132), 可能 repo 镜像是历史快照而非活副本 —— **我不下「该同步」的因果结论**
(N=1 看到不同 ≠ 该同步)。这归 exec/owner 确认两者关系后定, 超出知识侧 normalize scope。

### 7.4 ledger (standing-authorizations.json) 落点

确认落 **`cc_context/knowledge/standing-authorizations.json`** (与 PROJECT_SUBJECT_PROJECTIONS.json 同住
control-layer)。它是**真值数据 (json)**, **不进 registry 的 subjects** (registry subject 是 docs/subjects/*.md
的 markdown field, 不是 json 数据)。ledger 是独立 control-layer 文件, 自成一类。CLAUDE.md 已引用此路径。
