---
name: v4-followup-landed-next-main-line
description: "2026-05-14 v4 follow-up + 大 hygiene 全 land, 下次 session 接主线: P1 #24 cache trio 实测 / P1 #12 cache spike / P1 #7 ε-Certified"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-14 session 完成状态 (8 个新 commit 后, HEAD = fe83c41)**:

GPT v4 review 6 个 finding + 元层面 1 个 + ruff/mypy 大 hygiene 全部 land. 主分支干净, working tree 干净, full pytest 2144 passed.

- `5e4973d` F1 + F2 + F4: cut replay resolver + power witness gate + conftest cache hermeticity + 10 个 lifecycle test 固化
- `63c7231` F5 + bandit 4 MEDIUM: readiness gate untracked-code BLOCK + tempfile + urlopen allowlist
- `30b1932` PROJECT_LOCK proof object lifecycle 规则 + preflight CORE_TEST_FILES 108
- `d393f06` 清 OCR 工具 + data/telemetry 进 .gitignore
- `a50c61f` G1 ruff 分层 (515→0) + G2 mypy 核心 2 文件进 preflight
- `831c3fb` G4 benders_loop.py 8→0 mypy + ruff exclude .claude/worktrees
- `13fa8e2` G3 master_model.py 69→0 mypy + master+benders 进 mypy gate (4 文件)
- `fe83c41` G3 跟 Agent diff 完整对齐 (group dict annotation)

**Preflight 现 8 步**: 冻结 hash / 禁路径 / AI 安全 / 精确-探索隔离 / 调研 audit / **mypy 4 core lifecycle** / **ruff 全仓 0 警告** / pytest 核心 108.

---

**主线 (下次 session 接)**: "之前的优化验证" — 当时被 v4 audit 打断, 现在 v4 全做完该回去验证 P1 优化收益是不是真的存在.

按 `docs/phase3c_optimization_roadmap_v1.md` 优先级 + 用户原话 "验证改进后的效率":

1. **P1 #24 cache-aware pack 实测 +15-22%** (最直接, 最高优先级)
   - 三件套已 land (jemalloc LD_PRELOAD + P-core taskset + THP) 走 `scripts/run_campaign_linux.sh` wrapper
   - 起点: 启 1-2h 短长跑, taskset 钉 P-core (cpu0-7) + jemalloc + PYTHONMALLOC=malloc, 跟 baseline 比 throughput
   - 验证: 是不是真 +15-22% (path: P0 #6 audit `a2dfaa35dbefe2a3a` 修正过 stack-efficiency 折扣)
   - 跑法: `bash scripts/run_campaign_linux.sh --campaign-hours 1.0 --parallel-processes 4`

2. **P1 #12 cache spike 24h 数据** (gate by repeat rate ≥15%)
   - 24h campaign 启动加 `EXACT_SUBPROBLEM_REPEAT_PROBE=1`
   - 跑完 `python scripts/analyze_subproblem_repeat_rate.py` 看 global binding subproblem repeat_rate
   - 决策: ≥15% → GO 做 cache trio 主体 (5-7 天); <15% → KILL

3. **P1 #7 ε-Certified main flow 集成** (prep 已 done R11)
   - outer_search 三阶段 ε 调度 (commit bfe4e17 P1 #7 main 最后一公里) 已 land
   - 主体: campaign 启动验证三阶段切分 (25h/50h/85h+8h 缓冲) 真生效
   - 跟 P1 #24 一起跑, 看长跑 dual gap 收敛速度

4. **D 第 2 步: 主求解器 hint 注入 + production data** (task #40 pending)
   - 已有 GPT-5.5 Pro 多模态识别出的 3+2 种子 (D 第 1 步, commit `4e5d9c0` P2 #14 evaluator v1.1)
   - 集成成 main solver hint, 跑出 production data 看 hint 真减不减 wall-time

5. **readiness gate OOM 安全检查** (task #38 pending, 长期低优先级)

**已记 follow-up memory (不在主线上)**:
- [[phase3a-ip-delivery-readme-cleanup]] — Phase 3B 核心完工后改 README + IP delivery 历史化
- [[benders-loop-mypy-followup]] — 已 land! G3+G4 全清了, 这条 obsolete (但留着记录历史)

**Why 记这条**: 下次 session 接进来时, 不需要回顾整个 v4 audit 经过, 直接看这条就知道 (a) 上次干了啥 (b) 主线下一步是哪几条 (c) 优先级排序. 跟 [[phase3c-roadmap]] 配合用.

**触发场景**: 用户问"接着干什么"/"继续主线"/"验证优化效率"时直接看这条.
