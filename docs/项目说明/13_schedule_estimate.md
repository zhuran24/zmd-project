# 13 — 排期估算 (Claude pace, 不按人类工程师)

per `[[work-time-estimates]]` Claude 节奏估:

> **(2026-06-04 现状)** 下方 Phase 1.2 §11 的 5 family (F5-F9) 估时已成历史——F5-F9 **已落地**（Phase 1.2 spike close 闭关中，见 [06](06_current_status.md)）。本表作早期排期参考读，非当前待办。（另：本表的 `§10/§11/§12/§13` 等是**旧单体 plan 章节号**，对应本目录 sub-doc 见各 phase plan [08](08_phase_1_2_plan.md) / [09](09_phase_1_3_plan.md) / [10](10_phase_1_5_plan.md)。）

- Phase 1.2 §10 入门 7 项 — 单步 30-60 min Claude, 累计 ~5-7 commit, ~3-4 小时
- Phase 1.2 §11 5 family 实施 — 每 family ~1-2 commit + Gemini cross-check,
  累计 ~10-15 commit, ~6-10 小时 Claude work
- Phase 1.3 §12 propagator 集成 + perf opt — paradigm work, ~10-20 小时 Claude
  + master CP-SAT 真集成 wall-clock 死时间 (build / 测时间不可压)
- Phase 1.5+ §13 production integration — 跟真生产 data schema 设计耦合, 估
  随 Phase 1.5 data pipeline 进度

实际 wall-clock 主要消耗在 168h campaign 长跑 (cut framework 修改不直接影响
campaign 时间), 不在 Claude implementation 时间.

---

