# 与之前调研的重叠分析 — 2026-05-24

**方法**: grep 全 `docs/research/` 树（INDEX.md + paradigm_search_review_v12 + p3_b_design_v2 + agent_transcripts/）找作者/工具/概念 mention，分 4 档评估增量价值。

---

## 1. 已深度调研 / 已在用（不是新发现）

| 这次推荐 | 之前在哪儿 | mention 次数 | 增量 |
|---|---|---|---|
| **QuickXplain (Junker 2004)** | PCR-CUT 直接在用 + Gemini math review F9 spec | 40 | 0 — 已落地 |
| **VeriPB / cake_lpr** | agent `a7b0041317b6e6139` + `a3356c51d9d10daab` (R11 #6 VeriPB exporter 90min→4-6h) | 9 + 3 | 0 — 已规划 Phase 5 |
| **Pumpkin** | agent `adee29cf670b5c3dc` (Pumpkin v0.3.0 PyPI 2026-02-11 Python binding 已成熟) | 8 | 0 — Pumpkin P3→P2 PoC 候选 |
| **Glasgow** | 同上 (Glasgow gcspy + VeriPB 3.0) | 8 | 0 — Glasgow P3→P2 audit-only |
| **Lübke & Berg CP'25** | `a3356c51d9d10daab` (R13 audit 还纠正过引用错误：CP'25 不是 AAAI'25) | 5 + 3 | 0 — 已 audit |

## 2. 文献已 cite 但没深入读

| 这次推荐 | 之前在哪儿 | 备注 |
|---|---|---|
| **Clautiaux 2007 EJOR** | L14 weighted occupancy README 引用为 "generalized energetic reasoning" 真文献；R12 #6 蓝图 audit "Carlier-Clautiaux-Moukrim 2007 EJOR §3.2 paywalled" | **paywalled formula 不可独立 verify** — 这次值得拿全文 |
| **Ryan-Foster branching** | cand C `paper.md` 引用 arXiv 2509.01218 (2025) "Column-generation for a two-dimensional multi-criteria bin-packing problem" | 这次 da Silva & Schouery 2024 IJOC 是更早更扎实的源 |

## 3. 之前提及但不是作为算法本体调研

| 这次推荐 | 之前在哪儿 | 这次的增量 |
|---|---|---|
| **RoundingSat** | `a3356c51d9d10daab` 仅作为 VeriPB 生态系统组件提及 ("CP'25 #21 Koops VeriPB PB-OPT 工业可用 (RoundingSat/Sat4j 全套 logging 完成)") | **之前 cert 视角，这次 solver 本体视角** — 没人推过把它当 master.solve 替代品 |
| **Hooker LBBD** | `paradigm_search_review_v12/investigated_paradigm_groups/group_b_decomposition.md`: "Subgradient 收敛 stepsize 1/(k+1) 极慢 (Hooker CMU notes)" + "Bergman/van Hoeve/Hooker CMU 主线" | 之前 negative context (subgradient 慢)，这次正面引用 (LBBD 奠基) |
| **Fahle (SBDD)** | `investigated_paradigm_groups/group_d_layout_geometry.md`: "SBDD (Fahle/Schamberger/Sellmann + Gent generic)" — 不同 paper | 同作者不同 paper：之前是 SBDD (symmetry breaking)，这次是 2002 CP-based CG |

## 4. 完全新方向（首次出现）

- **Perron, Didier & Gay (2023) The CP-SAT-LP Solver** — 0 mentions
- **Hoen et al. (2025) SCIP-PB native solver** — 0 mentions
- **Bofill et al. (2022) PB+AMO encodings** — 0 mentions
- **Karlsson & Rönnberg (2023) cut-strengthening evaluation** — 0 mentions
- **Pessoa et al. (2018, 2013) dual stabilization** — 0 mentions
- **Eveborn & Rönnqvist (2004) hybrid Benders CLP** — 0 mentions
- **Davies, Didier & Perron (2024/2025) trail sharing + ViolationLS** — 0 mentions
- **Sadykov et al. (2021) bucket graph labeling** — 0 mentions
- **Pecin et al. (2017) limited memory rank-1 cuts** — 0 mentions
- **Schutt et al. (2011) explaining cumulative propagator** — 0 mentions
- **Shaw & Meel (2020) phase selection heuristics** — 0 mentions
- **da Silva & Schouery (2024) extended Ryan-Foster IJOC** — 0 mentions（cand C paper.md cite 的是 2025 arXiv 后续）

---

## 结论

**真正新的 incremental value 集中在两块**：

1. **CP-SAT internal 视角**（Perron 2023 + Davies 2024/2025 + Bofill 2022 PB encoding）
   - 之前调研都是工具链 / paradigm 层（Pumpkin/Glasgow/VeriPB 是 *别的* solver），没人挖过 OR-Tools **自己**的内部
   - Perron 2023 是 9 月发布后 0 次 cite，明显遗漏

2. **PB solver 作为 master.solve 替代品**（SCIP-PB / RoundingSat）
   - 之前只把它当 cert backbone（VeriPB context），没人当算法主体推过
   - SCIP-PB 完全没出现过，PB Competition 2024 实证冠军被错过

**已在轨道上的不要重复花时间**：QuickXplain（在用）、VeriPB / Pumpkin（已规划 P3→P2）、Lübke & Berg（已 audit）、Clautiaux generalized energetic reasoning（已 cite 但 paywalled，值得补全文）。

---

## Methodology note

grep command used:

```bash
grep -rE "(Hooker|Pessoa|RoundingSat|Devriendt|Karlsson|Rönnberg|Perron, L|Belov|Vanderbeck|Bofill|Clautiaux|Fahle|Schouery|Ryan-Foster|Eveborn|Sadykov|Uchoa|Stuckey, P|Feydy|Ohrimenko|VeriPB|Oertel|Davies, T)" docs/research/
```

Then deduped by author/concept and cross-referenced against this session's recommendations.
