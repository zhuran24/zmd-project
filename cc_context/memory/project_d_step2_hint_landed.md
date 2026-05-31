---
name: d-step2-hint-landed
description: "2026-05-16 D step 2 integration land: scripts/blueprint_to_master_hint.py + benders_loop.py env injection + production wrappers default, all committed. 短 trial 等 production data 信号."
metadata:
  type: project
  originSessionId: f961efc3-93a4-4068-a05d-b7f8f4592d35
---

**D step 2 (task #40) integration 落地状态 (2026-05-16)**:

## Commits

1. `8395a27` — converter + 10 hand-verified samples + regression test
2. `6948eb0` — benders_loop.py env injection + wrapper default
3. `2456c99` — workers2 wrapper update + analyze_hint_vs_baseline.py

## 工作流程

```
blueprint JSON (user-tuned, 1175 devices)
    ↓ scripts/blueprint_to_master_hint.py
master hint JSON (Dict[instance_id, pose_idx], 225 entries)
    ↓ data/hints/blueprint_2026_05_13_master_hint.json
    ↓ EXACT_COMMUNITY_BLUEPRINT_HINT_PATH env (wrapper auto-set)
benders_loop._run_certified_exact merges with greedy hint
    ↓ master.solve(solution_hint=...) via apply_solution_hint
    ↓ AddHint per slot var
CP-SAT search biased toward user-tuned positions
```

## 验证

- 10 sample 手动推导 vs 脚本输出 100% match (test_blueprint_to_master_hint.py)
- py-spy 实测 master.solve at line 11368 actively running with hint applied
- 226/226 blueprint facility device 中 225 映射到 project pose (唯一 miss 是 hub origin (41,61) 超出项目 anchor max 60 — 项目几何边界保留, 不是 bug)
- "[community-hint] loaded ... 224 overrides" 日志 confirms env load + 合并工作

## Blueprint 几何特性 (重要发现)

- Blueprint natural largest empty rect: **15×27 = area 405, min_side 15**
- 项目 certified path 从 large area 往下扫
- candidate area > 405 时 blueprint hint 几何不匹配, master 不可能用 hint 找 FEASIBLE
- 真正 hint match 的 candidate area ≤ 500 且 min_side ≥ 10 (blueprint's natural shape range)
- 短 trial 30min/master_seconds 600s 不够看完所有 area<500 candidate, 需要 24h+ trial

## 生产数据收集计划

下次跑生产数据 trial:
1. 用 `bash scripts/run_campaign_p2_workers1.sh --campaign-hours 24.0` (wrapper 自动注入 hint env)
2. Trial 末跑 `python scripts/analyze_hint_vs_baseline.py /tmp/zmd_pre_hint_state.json data/checkpoints/exact_campaign_state.json`
3. 看是否有 UNKNOWN→FEASIBLE 或 UNKNOWN→INFEASIBLE 的 decisive 升级

## 关键文件

- `scripts/blueprint_to_master_hint.py` — converter (rotation→port_mode 锁映射)
- `src/tests/test_blueprint_to_master_hint.py` — 10 hand-verified regression
- `src/search/benders_loop.py:3565-3604` — env injection (community overrides greedy)
- `scripts/run_campaign_p2_workers1.sh` — production wrapper (hint default on)
- `scripts/run_campaign_workers2.sh` — fallback wrapper (hint default on)
- `data/hints/blueprint_2026_05_13_master_hint.json` — generated hint (225 entries)
- `/home/zhuran24/下载/BP-2026-05-13 08_35_36.blueprint(1).json` — 用户最终 blueprint

## 链

- [[d-step2-blueprint-converter-state]] D step 2 准备状态 (pre-integration)
- [[ip-v2-blueprint-lp-modeling]] 已验证 blueprint
- [[2026-05-15-ram-session-misdirected]] 上次 session RAM 跑偏 lesson, 这次走 quality 路径
