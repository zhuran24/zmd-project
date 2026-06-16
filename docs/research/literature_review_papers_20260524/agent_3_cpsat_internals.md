# Agent 3 — CP-SAT 内部技巧调研

**Agent ID**: a7ff932c68952d8f9
**Model**: Opus
**Date**: 2026-05-24
**方向**: 项目用 OR-Tools CP-SAT 9.15，latency-bound 工作负载

---

## 1. CP-SAT 内部论文（核心，直接对口）

**Perron, L., Didier, F., & Gay, S. (2023). The CP-SAT-LP solver (Invited talk). In *Proceedings of CP 2023*, LIPIcs Vol. 280, Article 3.**
- Relevance: **HIGH**。项目主求解器作者亲自写的内部 mechanism paper，不是 user-tutorial。讲了 CP-SAT 怎么在 CDCL 上叠 CP + LP + MaxSAT，linearization gradient、symmetry handling、LNS portfolio 都有提。
- Concrete use: 项目 channeling-heavy + dense linear 的 model，对照看 CP-SAT 的 linearization_level 在 LP relaxation 里到底跑什么——能解释为什么 level 改了反而 RAM 涨（线性化复制约束）；以及 master 12.8 GB peak 里多少是 LP working memory。
- Risk: invited talk 体裁，缺细节实现，需要配合源码读。
- URL: https://drops.dagstuhl.de/storage/00lipics/lipics-vol280-cp2023/LIPIcs.CP.2023.3/LIPIcs.CP.2023.3.pdf

**Davies, T. O., Didier, F., & Perron, L. (2025). Parallelising Lazy Clause Generation with Trail Sharing. In *CPAIOR 2024 proceedings* (Springer LNCS).**
- Relevance: HIGH。介绍 Buffered Work Stealing + trail sharing，这是 OR-Tools 9.15 后实际跑的并行模式（取代了纯 portfolio）。
- Concrete use: 项目现在 workers=1 是因 RAM (12.8 GB → 30 GB at 8 workers)。如果未来上 64 GB+ 机器，重新 enable workers，**关键是看 trail sharing 是不是 share 整个 binary clauses 还是仅 root-level facts**——前者会爆 inter-worker memory。论文给的 ratio 能预估 RAM 涨幅。
- Risk: 论文 benchmark 是 MiniZinc challenge 类小 model（≤10K vars），项目 280K vars 推断要打折。
- URL: https://link.springer.com/chapter/10.1007/978-3-031-95973-8_13

**Davies, T. O., Didier, F., & Perron, L. (2024). ViolationLS: Constraint-Based Local Search in CP-SAT. In *CPAIOR 2024 proceedings* (Springer).**
- Relevance: MEDIUM-HIGH。讲了 CP-SAT 内部的 LNS / CBLS sidecar 怎么 portfolio 集成。
- Concrete use: 项目用 community blueprint hint 注入 (AddHint) 是 cold start；ViolationLS 描述的 "feasibility jump" 模式可以**手动驱动**——把 hint 当 initial solution 喂进 LNS-style 改进循环，让 CP-SAT 在 master infeasibility 时 violation-relax 而不是直接 UNKNOWN。
- Risk: API 暴露程度未知，可能需要 patch OR-Tools 才能访问。
- URL: https://link.springer.com/chapter/10.1007/978-3-031-60597-0_16

---

## 2. LCG 系列

**Ohrimenko, O., Stuckey, P. J., & Codish, M. (2009). Propagation via lazy clause generation. *Constraints*, 14(3), 357–391.** — LCG 奠基论文，Chuffed 同源。
- Relevance: MEDIUM。理解 CP-SAT explanation 机制的根。Propagator-as-clause-generator paradigm。
- Concrete use: 自定义 cut（PCR-CUT、SAC-Hull、F9 area cut）如果未来要从外循环搬进 internal lazy constraint，必读。
- Risk: 不会立刻影响 latency-bound 瓶颈。

**Feydy, T., & Stuckey, P. J. (2009). Lazy Clause Generation Reengineered. In *CP 2009*.** — 工程化 LCG，性能层。
- Relevance: MEDIUM。讲怎么减 LCG overhead（项目主 cost）。

---

## 3. Symmetry detection

**Mears, C., García de la Banda, M., Wallace, M., & Demoen, B. (2013). A novel approach for detecting symmetries in CSP models. *Constraints*.** + 后续 lsv-graph automorphism 工作。
- Relevance: LOW-MEDIUM for this project。原因：Lever 26 (Benders symm) 已验 m5=1.0 全 trivial orbit。
- Concrete use: 如果未来扩到多 base（valley4_infra_outpost 等 future_scope），base 间可能出现 symmetry，再回来读。
- Risk: 现 scope 无收益。

---

## 4. Restart strategies

**Audemard, G., & Simon, L. (2018). On the Glucose SAT solver. *International Journal on AI Tools*, 27(1).** — Glucose LBD + 快速 Luby restart。
- Relevance: MEDIUM。CP-SAT 默认 Luby-based。
- Concrete use: 项目 master.solve 经常 5min UNKNOWN 5.5M branches（v8 anchor trial）— 这是 restart 太频繁还是太稀疏的 signal 不明。读这篇能判断要不要调 restart_strategy / restart_period（OR-Tools 暴露的两个 param）。
- Risk: 实测可能负 ROI（同 shared_tree 教训），先做 1 candidate spike 再决定。

---

## 5. Branching heuristics

**Liang, J. H., Ganesh, V., Poupart, P., & Czarnecki, K. (2016). Learning Rate Based Branching Heuristic for SAT Solvers. In *SAT 2016*.** — LRB。
- Relevance: MEDIUM。CP-SAT 用 VSIDS 衍生，LRB 在 hard combinatorial 上 +100 instances over VSIDS。
- Concrete use: OR-Tools 不直接暴露 LRB 切换，但可以 patch。优先级低于 hint injection。

**Cherif, M. S., Habet, D., & Terrioux, C. (2021). Combining VSIDS and CHB Using Restarts in SAT. In *CP 2021*.** — VSIDS+CHB hybrid。
- Relevance: LOW-MEDIUM。同上，无直接 OR-Tools knob。

**Refalo, P. (2004). Impact-Based Search Strategies for Constraint Programming.** + **Michel, L., & Van Hentenryck, P. (2012). Activity-Based Search for Black-Box CP Solvers.**
- Relevance: MEDIUM。Activity-based 是 CP-SAT 部分 worker 用的 strategy。
- Concrete use: 项目 280K pose-bool 是稀疏 binary domain — activity-based 应表现好。可考虑 `search_branching: PORTFOLIO_SEARCH` 强制覆盖默认。

---

## 6. Warm-starting / phase saving

**Shaw, A., & Meel, K. S. (2020). Designing New Phase Selection Heuristics. In *SAT 2020*.**
- Relevance: HIGH。直接讨论 phase saving 的失败模式（exactly 项目症状：5min UNKNOWN no improvement）。
- Concrete use: AddHint 在 CP-SAT 里是 polarity hint，**但 phase saving 会覆盖**。这篇讲 hint vs. learned-phase 的 interplay。可能解释为什么 community blueprint hint 在 D step 2 实测帮助有限——hint 被 phase save 冲掉了。
- Risk: 改 phase strategy 可能 break exactness（不会，phase 只影响 search order 不影响 sound）。

---

## 7. Parallel CP-SAT

见 §1 trail-sharing paper。补充：**HordeSat (Balyo et al., 2015)** 作为 massive-portfolio 对照点 — 项目跑不到这个 scale。

---

## 特殊关注 — Dense linear / channeling

**Bofill, M., Coll, J., Suy, J., & Villaret, M. (2022). SAT encodings for Pseudo-Boolean constraints together with at-most-one constraints. *Artificial Intelligence*, 302.**
- Relevance: HIGH。项目 power_coverage / connector / port-binding 全是 dense linear + AMO 混合。论文 verdict: **Generalized Totalizer + AMO-aware encoding** 比纯 sequential counter 在 dense PB 上 +30-50% propagation efficiency。
- Concrete use: 项目 master 里 dense linear constraint 现在 CP-SAT 默认是 sequential counter 编码（看 model.Validate 输出能确认）。如果手动 reformulate 成 GTE-style auxiliary tree，可能减 BCP touch points → 直接打 latency-bound 痛点。
- Risk: 重写 encoding 工作量大，且 PROJECT_LOCK 锁 schema — 必须 Phase 0 cheap gate 先 verify 单 candidate 不退化 exactness。
- URL: https://arxiv.org/pdf/2110.08068

**Huang, J. (2008). Universal Booleanization of Constraint Models. In *CP 2008*.** — channeling-heavy model 的 boolean encoding 系统化方法。
- Relevance: MEDIUM。讲 channeling-heavy 模型的 variable explosion 怎么收敛。

---

## Top 3 推荐（按 actionable ROI）

1. **Perron, Didier & Gay (2023) The CP-SAT-LP Solver** — 必读。是 CP-SAT 唯一的 official internal paper，直接解答"为什么我的 linearization_level 改了 RAM 涨"、"master.solve 12.8 GB 里哪部分是 CP / LP / SAT"。读完能 calibrate 所有 OR-Tools knob 的 mental model。零实施风险。

2. **Bofill et al. (2022) SAT encodings for PB+AMO constraints** — 项目唯一可能打到 latency-bound 痛点的方向。Dense linear (power_coverage / connector) 是项目 BCP miss 大头，GTE-with-AMO 在 propagation cost 上有量级证据。Phase 0 cheap gate：单 candidate 手动 reformulate 一个 dense constraint，量 master solve time + branches → GO 才推广。

3. **Davies, Didier & Perron (2025) Trail Sharing for LCG** + **Davies, Didier & Perron (2024) ViolationLS** 并列 — 前者是未来 workers≥2 重新启用时的必修；后者给"hint → LNS feasibility jump"的内部机制路径，比单纯 AddHint 更激进。两者都是 CP-SAT 主作者，跟项目 OR-Tools 9.15 直接对齐。

**避开**：Symmetry detection（Lever 26 已死）、LRB/CHB（OR-Tools 不暴露 knob）、restart strategy 调参（同 shared_tree 教训风险）。
