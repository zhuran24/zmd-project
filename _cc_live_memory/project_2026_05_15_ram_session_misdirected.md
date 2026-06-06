---
name: 2026-05-15-ram-session-misdirected
description: "2026-05-15 一整个 session 优化 master RAM (verified -57%), 但 14h production trial 0 feasible — 真瓶颈是 master.solve 解不动, 非 RAM"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-15 session 重要 lesson (诚实评估)**:

一整个 session 调 master CP-SAT RAM:
- workers=8→1 verified plateau 30→12.19 GiB (-57%)
- -p 2 + workers=1 = 36 GiB fits 47 GiB hardware 解锁 任务 #67
- 8 commits land (heuristic finder + env hooks + production wrappers + gate)
- 2188 pytest pass, race condition bug 修

**但实际生产 14h trial (workers=1 + -p 2)**:
- 跑 51 new candidates **全 UNKNOWN**
- 0 FEASIBLE found
- 跟 baseline 8 workers + -p 1 跑过 27 candidates 0 FEASIBLE 一样

**真瓶颈**: master.solve 在 30 min cap 内既证不了 INFEASIBLE 也找不到 FEASIBLE.
减 RAM **不解决** 这个 — 时间不够 / search space 太大 / model 太难.

## 下次开 session 别再走的死路

RAM 优化 (worker count / env params / model encoding) — 至少在本 problem
config 下不是 lever. 跑了一整天证明 RAM 减半但 0 feasible 提升.

## 真 lever (下次先试)

1. **Community blueprint hint** (D 第 2 步, task #40): GPT-5.5 Pro identified
   3+2 community blueprints in ~/linwin_share/gpt_handoff.zip. 注入 master.AddHint
   理论上让 master 跳过早期 search → 直接 verify hint feasibility
2. **`master_seconds` 调大** (main.py:195 default 1800 = 30 min): 改 7200 (2h)
   减 candidate 数但每个 candidate 跑久, 可能突破 UNKNOWN
3. **Objective relaxation**: max_lex(area, min_side) 难求. 改成 phase 1 找 any
   feasible (drop objective) + phase 2 优化. CP-SAT 9.15 是否 supports 待 verify
4. **Static prune from INFEASIBLE pattern**: 13 INFEASIBLE 全 70xN (N=7-19),
   说明 thin-strip ghost 几何不可能. 加 aspect ratio filter / min_side filter
   减 candidate pool 从 1196 → ~600

subagent a65ad1e22499d8239 在 trial 末尾 launch 调研这 3 个方向, 等 finding.

## 关键 numbers (for next session 不重跑)

| config | RAM peak | 14h trial result |
|---|---|---|
| workers=8 + -p 1 (baseline) | 30 GiB | 27 candidates / 0 FEASIBLE |
| workers=2 + -p 1 (spike#5) | 16.4 GiB | 1 candidate UNKNOWN |
| workers=1 + -p 1 (spike#6) | 12.19 GiB | 1 candidate UNKNOWN |
| workers=4 + -p 1 (spike#7) | 20.44 GiB | 1 candidate UNKNOWN |
| workers=1 + -p 2 (14h trial) | ~25 GiB total | 51 candidates / 0 FEASIBLE |

## 链

- [[30gb-real-culprit-power-coverage]] RAM verdict
- [[d-step1-gpt-handoff]] community blueprint 来源 (D 第 1 步)
- [[rewrite-path-exhausted]] 旧 RAM-only verdict
- [[no-sleep-loop-for-goal-hook]] sleep loop 浪费 5h CPU lesson
