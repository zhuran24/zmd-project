# D step 2 Hint Trials — 2026-05-16

5 个 hint trial 的 campaign state + telemetry 归档. 验证 community blueprint hint 注入对 master FEASIBLE 率的影响.

**verdict** (见 `docs/lever_verdicts.md` L7 / L8 / L10): 5/5 候选全 UNKNOWN, hint integration 完美 (telemetry 798 AddHint 一次不多), 但 master 内在难度导致无法突破 UNKNOWN.

---

## 文件清单

| 文件 | 内容 |
|---|---|
| `baseline_pre_hint_state.json` | 之前 14h baseline trial 终态 (workers=1, master_seconds=1800, default profile, 无 hint). 78 candidates 大部分 UNKNOWN |
| `baseline_pre_hint_telemetry.json` | baseline telemetry |
| `trial1_state.json` | 第一次 fresh trial: master_seconds=600, workers=1, default profile, hint on, --start-area 默认 (1300+ area candidates) — 用户中途 kill (geometry mismatch) |
| `trial2_state.json` | 重启 --start-area=500, 还在 wide-thin (70×6) — 用户中途 kill |
| `trial3_state.json` | --start-area 500 + --min-side 10 + --max-aspect-ratio 2.5 + master_seconds 600 + workers 1 + default profile → 3 candidates 全 UNKNOWN (35×14 / 33×15 / 31×16) |
| `trial4_state.json` | --start-area 410 + --min-side 15 + --max-aspect-ratio 1.9 (target blueprint natural 15×27 shape) + master_seconds 600 + workers 1 + default profile → 2 candidates 全 UNKNOWN (**27×15** blueprint exact match + 24×17) |
| `trial5_state.json` | 同 trial4 但换 `--master-search-profile exact_coordinate_ghost_first_v1` → 同 candidates 同结果 (UNKNOWN), profile 切换不影响 |
| `trial6_state.json` | master_seconds=3600, workers=1 — 启动 4 分钟用户 spot **workers=1 跟 A 路径不对**, kill |
| `trial7_final_state.json` | master_seconds=3600, workers=8 (8 P-core 满载), target 27×15 → 60min wall + ~7min CPU/worker → 仍 UNKNOWN |
| `trial7_final_telemetry.json` | trial7 telemetry: 1 solve_attempt + 266 hinted_instances + 798 master_hinted_literals (= 266 × 3 AddHint per slot) + UNKNOWN |
| `zmd_hint_trial*.log` | 各 trial 启动 log (确认 community hint 加载) |

---

## 关键数据点

### 27×15 candidate 在 4 种配置下都 UNKNOWN

| trial | master_seconds | workers | profile | 结果 |
|---|---|---|---|---|
| trial4 | 600 | 1 | default | UNKNOWN |
| trial5 | 600 | 1 | ghost_first_v1 | UNKNOWN |
| trial7 | 3600 | 8 | default | UNKNOWN |

3 种 axis (时间 ×6, worker ×8, profile 切换) 全 saturation, 27×15 (blueprint natural empty rect 15×27 exact match) 仍 UNKNOWN. **Master 对该 candidate inherent 难解**, 不是参数问题.

### Telemetry 验证 hint 整链零损耗

每次 trial: `master_hinted_literals_sum == 266 × 3 × solve_attempt_count` 完美匹配. AddHint 一次不多一次不少.

### Baseline 对比

baseline 14h 跑 78 candidates: 65/78 UNKNOWN (83%), 13/78 INFEASIBLE, 0/78 FEASIBLE. hint trial 同区域全 UNKNOWN, **没退化**.

---

## 怎么用

`scripts/analyze_hint_vs_baseline.py` 对比:

```bash
python scripts/analyze_hint_vs_baseline.py \
  docs/research/d_step2_hint_trials_20260516/baseline_pre_hint_state.json \
  docs/research/d_step2_hint_trials_20260516/trial7_final_state.json
```

输出 candidate transition matrix (UNKNOWN→FEASIBLE, UNKNOWN→INFEASIBLE 等 upgrade 信号).

---

## Memory 链

- [[project_d_step2_hint_landed]] — D step 2 完整状态
- [[lever_verdicts]] L7 / L8 / L10 verdict
