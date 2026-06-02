---
name: full-pytest-after-vendor-refresh
description: 每次 vendor sync / 大版本升级后，跑一次完整 pytest 套件，不能只信 pre-commit hook 的核心守卫子集 (~108, 随加守卫漂移, 以实跑为准)
type: feedback
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

每次跑 `scripts/refresh_endfield_calc_snapshot.py` 或 `scripts/refresh_industrial_planner_bases.py` 这类 vendor sync 脚本后，**手动跑一次 `python -m pytest src/tests/ -q`**（约 6 分钟），不能光信 commit 时的 pre-commit hook。

**Why:** 用户 2026-05-08 在 session 后期问"审查呢，数学确定性的审查怎么感觉没存在感了"。我跑完整 pytest 才发现 `test_endfield_calc_semantic_mapping.py` 还 hardcode 着 v0.5.2 的 130/172/14，但我之前的 vendor refresh（v0.5.2→v0.6.2）只改了 `test_endfield_calc_typescript_snapshot.py`。这个 bug 潜伏了几天，commit 时的 pre-commit hook 没抓到，因为它只跑核心守卫子集（preflight gate `CORE_TEST_FILES`，守卫 certified path），不跑全套。**(注: "86" 已漂移 —— 实核现 collect ~108 个, v4 follow-up 加了守卫文件; 数会随加守卫变, 以实跑为准, 别记死。)**

**How to apply:**
- 跑完任意 `scripts/refresh_*.py` 后立刻跑 `python -m pytest src/tests/ -q`
- 全套 ~6 分钟，可以扔后台跑同时干别的
- 看到 ❌ 立刻修，不要拖到下次发现
- **不要信 pre-commit hook 的 PASSED**——它只测 certified path 守卫子集，不测 vendor adapter / IndustrialPlanner 转译 / endfield-calc semantic mapping 这些
- 同样适用于：依赖升级（`pip install -U ortools` 等）、`canonical_rules.json` 修改、任何外部 fixture 重构
- 顺便：项目主分支当前有 ~29 个长期 baseline failures（Codex 时期遗留），跑全套时要会区分"我引入的"vs"baseline"——拿 git stash 抽走改动后再跑同测试，仍 fail 就是 baseline

## 链 (补连 2026-06-01)
- [[autopilot-with-review-gate]] — 审查闸跑全测

## 链 (补连 2026-06-02 连通审计 whcb890zi)
- [[audit-verify-before-archive]] — 别信 cheap gate 独立跑全 — 同 don't-trust-cheap-signal 家族
