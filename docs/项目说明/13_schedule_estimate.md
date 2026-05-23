# 13 — 排期估算 (Claude pace, 不按人类工程师)

per `[[work-time-estimates]]` Claude 节奏估:

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

