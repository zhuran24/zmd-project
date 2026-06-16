# Literature Review — 2026-05-24

**触发**: 用户 `/deep-research 目前还有哪些论文对我们项目有帮助和参考意义的`

**方法**: 4 个并行 Opus subagent + WebSearch，按当前 active paradigm + 1 个 paradigm shift 候选分方向：

1. `agent_1_column_generation.md` — 列生成 / 分支定价（Cand C 主线支持）
2. `agent_2_lbbd_cuts.md` — LBBD cut strengthening（PCR-CUT 路径支持）
3. `agent_3_cpsat_internals.md` — CP-SAT 内部技巧
4. `agent_4_paradigm_shift.md` — 未尝试 paradigm 候选（PB / MaxSAT / DD / 2D packing / SDP）

**对照基线**: 27 paradigm 死路 + Cand C Phase 1 GO + SMT-MT Phase 1 marginal + PCR-CUT Phase 5 marginal

---

## Top Recommendations (REVISED post DA review — 见 `da_review_checkpoint2.md`)

> **修订原因**: DA checkpoint 2 给 REVISE verdict。原 Tier 1 Perron 标"必读"过强 (anchoring bias)；原 Tier 2 SCIP-PB **paradigm shift claim 基于过时 HiGHS 死因诊断** (项目 memory 已记 HiGHS 死因不是 LP simplex 是 propagation buffer × workers) — DA 评第 28 paradigm 死路高概率候选，**KILL 或硬 gate**。原 Tier 3 Pessoa LP→CP transfer 未验证，可能害 m10 sound bound ramp。

### Tier 1 — 诊断参考（1h，降级自"必读"）

**Perron, L., Didier, F., & Gay, S. (2023). The CP-SAT-LP Solver (Invited talk). *CP 2023*, LIPIcs Vol. 280, Article 3.**

项目主求解器作者唯一 internal mechanism paper。直接解答：`linearization_level` 改了为啥 RAM 涨 / master 12.8 GB peak 里 CP/LP/SAT 各占多少。**用作诊断工具，不是 paradigm 输入** — 27 paradigm 死路里 solver-knob 类仅占 ~3 个，多数死路在 paradigm 层。

URL: https://drops.dagstuhl.de/storage/00lipics/lipics-vol280-cp2023/LIPIcs.CP.2023.3/LIPIcs.CP.2023.3.pdf

### Tier 2 — Cand C Phase 2 主线直接相关（升级自原 Tier 3）

**Fahle, T., Junker, U., Karisch, S. E., Kohl, N., Sellmann, M., & Vaaben, B. (2002). Constraint programming based column generation for crew assignment. *Journal of Heuristics, 8*(1), 59–81.**

CP pricing 而非 LP/DP pricing 的奠基论文。Cand C 用 CP subproblem 做 pricing，paradigm 直接对齐，被 DA 评为 Top 3 里真正最相关那篇。Cand C Phase 2 启动前必读。

### Tier 3 — 选读（LP→CP transfer 未验证）

- **Pessoa et al. (2018) Automation and combination of stabilization techniques in CG, IJOC 30(2)** — 前提 LP master + continuous dual。项目是 pose-bool CP + m9 proxy dual，stabilization 可能让 proxy dual drift 离真 dual 更远，反害 m10 sound bound ramp。先 m9/m10 ramp 5→80 inst 实测稳了再考虑。
- **da Silva & Schouery (2024) Extended Ryan-Foster, IJOC, arXiv:2308.03595** — non-binary extension 在项目里没有 use case，over-citation。

### KILL 或硬 gate — 原 Tier 2 paradigm shift bet

**Hoen et al. (2025) SCIP-PB, arXiv:2501.03390 + Devriendt et al. (2021) RoundingSat**

DA C1 critical issue 三连击：
1. HiGHS 死因诊断错（不是 LP simplex 是 propagation buffer × workers），SCIP-PB 类比失效
2. Latency-bound 矛盾 — SCIP-PB cutting plane + PaPILO 同样稀疏矩阵随机访问，更 pointer-chasing 不更少
3. Survivorship bias — PB Competition 448 unsolved 几何更接近项目 dense linear；L15 set-packing 同款死法（底层 paradigm sound + benchmark 实证 但项目语境失效）

**硬 gate 条件**: 进 Phase 0 前先 4h spike 看 OPB clause count + RAM，并写出 differential diagnosis "为啥不跟 L15/HiGHS/v8 同款死"。写不出来 KILL。

### 新缺口（DA 指出，应补充调研）

1. **Cand C Phase 1 → Phase 2 真正 blocker 诊断** — m9/m10 gap ramp 5→80 inst 怎么变？该是 Tier 1
2. **大规模 CP-SAT production case study** — Google routing/scheduling 280K+ vars 实测数据，不是 internal mechanism paper
3. **死掉 paradigm 的 differential diagnosis 模板** — 任何新推荐都该 explicit "为啥不跟 L15/HiGHS/v8 同款死"

### Tier 4 — PCR-CUT 强化

- **Karlsson, E., & Rönnberg, E. (2023). Computational evaluation of cut-strengthening techniques in LBBD. *Operations Research Forum, 4*(3), 67.** — 3000 instance 实证；QuickXplain 单走是经验最佳之一但论文建议补 greedy-then-deletion 两阶段。
- **Bofill, M., Coll, J., Suy, J., & Villaret, M. (2022). SAT encodings for Pseudo-Boolean constraints together with at-most-one constraints. *Artificial Intelligence, 302*.** — GTE-with-AMO encoding 在 dense PB 上 +30-50% propagation。

### Tier 5 — Future watch（不急）

- Oertel et al. (2025). Practically feasible proof logging for PB optimization. CP 2025 — 若 PB paradigm GO，cert 系统升级
- Davies, Didier & Perron (2025). Parallelising LCG with Trail Sharing. CPAIOR 2024 — 未来 RAM 解锁 workers≥2 时必读
- Clautiaux, F., Jouglet, A., Carlier, J., & Moukrim, A. (2007). EJOR 183(3), 1196-1211 — 兜底 dual bound 注入

### 跳过（确认死路或不匹配）

- MaxSAT 类（RC2, EvalMaxSAT）—— encoding 膨胀严重
- Decision Diagrams (BDD/MDD) —— 2D grid 没自然 stage 划分
- SDP / Lasserre —— 70×70 远超 tractable scope
- Symmetry detection —— Lever 26 已死

---

## 与之前调研重叠分析

详见 `overlap_with_prior_research.md`。简表：

| 这次推荐 | 之前出现位置 | 增量 |
|---|---|---|
| QuickXplain | 40 次提及，PCR-CUT 在用 | 0 — 已落地 |
| VeriPB / cake_lpr | agent `a7b0041317b6e6139` + `a3356c51d9d10daab` | 0 — 已规划 Phase 5 |
| Pumpkin / Glasgow | agent `adee29cf670b5c3dc` | 0 — Pumpkin P3→P2 候选 |
| Lübke & Berg CP'25 | `a3356c51d9d10daab` (R13 audit 纠正过引用) | 0 |
| Clautiaux 2007 EJOR | L14 weighted occupancy 引用 + R12 #6 | 中 — paywalled 没读全，值得拿全文 |
| Ryan-Foster | cand C `paper.md` 引用 arXiv 2509.01218 | 中 — da Silva 2024 IJOC 是更早更扎实源 |
| RoundingSat | 仅 VeriPB 生态系统 context（1 次） | **高 — 之前 cert 视角，这次 solver 本体** |
| Perron 2023 CP-SAT-LP | 0 次 | **高 — 完全新** |
| Hoen 2025 SCIP-PB | 0 次 | **高 — 完全新** |
| Bofill 2022 PB+AMO | 0 次 | **高 — 完全新** |
| Karlsson & Rönnberg 2023 | 0 次 | **高 — QuickXplain 之外 family 对比** |
| Pessoa 2018/2013 | 0 次 | **高 — cand C Phase 2 关键** |
| Eveborn 2004 hybrid CLP | 0 次 | **高 — paradigm anchor** |
| Davies 2024/2025 | 0 次 | **高 — CP-SAT 并行内部** |
| Sadykov 2021 / Pecin 2017 | 0 次 | 中 — VRP-flavored 转移成本 |

---

## Source agents (full transcripts)

| File | Agent ID | Direction |
|---|---|---|
| `agent_1_column_generation.md` | a55268203c92cc1fa | Branch-and-price stabilization / 2D packing CG / CP-based pricing |
| `agent_2_lbbd_cuts.md` | a0911f796fdfb6be8 | LBBD cut strengthening / MUS / placement-routing |
| `agent_3_cpsat_internals.md` | a7ff932c68952d8f9 | CP-SAT internals / LCG / branching / restarts / PB+AMO encoding |
| `agent_4_paradigm_shift.md` | aafb98bbac9f82ba7 | PB / MaxSAT / DD / 2D packing exact / SDP / presolve |

---

## Suggested Next Action (REVISED post DA)

按 ROI 排：

1. **今天 1h**：读 Perron-Didier-Gay 2023 CP-SAT-LP paper（诊断工具，零风险）
2. **Cand C Phase 2 启动前**：读 Fahle 2002 (CP-based CG 奠基)
3. **新缺口 — 优先于 SCIP-PB**：先做 m9/m10 gap ramp 诊断 (5→80 inst trend)，先找 Google production 大规模 CP-SAT case study
4. **SCIP-PB / RoundingSat**：**先 4h spike OPB clause count + differential diagnosis "为啥不跟 L15/HiGHS 同款死"** → 通过才进 Phase 0
5. **PCR-CUT Phase 6（如开）**：读 Karlsson & Rönnberg 2023 + Bofill 2022
