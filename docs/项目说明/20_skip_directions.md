# 20 — 默认 skip 的方向 (历史死路 baseline)

> **历史/策略边界**：此处“跳过”只表示当时路线选择，不证明对应风险在当前代码中已闭合。


后续重构不再 propose 这些. 详 `docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md`（27 lever；live 权威 timeline 在 CC memory `paradigm-death-timeline-27-lever`）.

- **HiGHS / Gurobi 替 OR-Tools**: PoC 42 GB > 30 GB OR-Tools (Phase 3B repair5)
- **多机分布式**: 硬件 1 主机 + 1 远程, WAN 延迟 ≥ 100 ms
- **LP relaxation 替 CP-SAT**: B1 pose-bool master 已 verdict 死, master.solve
  解不动是 inherent
- **27 lever 死路**: B1 / PCR-CUT / SAC-Hull / D2 / cand C / L01-L27 — 各
  paradigm_death_timeline.md cite 死法
- **Step A-O 已 close 的 finding**: GPT v1-v6 + Gemini r33-35 catch + 8 invariant
  全 close, 不重复 (除非加新 evidence)

---

