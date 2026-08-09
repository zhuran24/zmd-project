# L16 — Lazy Power Completion (GPT v11 提出)

## 当时项目情况

L15 锁定真瓶颈 = `_add_geometric_power_coverage_constraints`. GPT 出 v11 paradigm 直接针对 power_coverage encoding.

## 为什么走这条路

GPT v11 plan: **Lazy Power Completion 架构** — master 跳 coverage 留 pole slot, completion sub-problem 解电杆, Benders cut 回灌. 直接绕开 power_coverage 是真瓶颈的判断 (L15 锁定).

## 实验过程

### Phase 0 mini-PoC (1 Claude day)
- 加 `EXACT_LAZY_POWER_COMPLETION` env flag (PROJECT_LOCK L4b)
- 改 `exact_coordinate_master.build()` 跳 `_add_geometric_power_coverage_constraints` 但留 pole slot
- 写 `scripts/phase0_lazy_power_completion_probe.py`

### Phase 3 deletion-based core minimizer (after Phase 0 verdict)
- 写 `scripts/phase3_core_minimizer.py` linear deletion + powered-first order

## 实验结果

### Master gate: PASS ✓
- first solve: **81.8s OPTIMAL** (vs production 30 min UNKNOWN — master 端方向**真对**)
- vars: 54,616 (GPT 估 ≤ 26K 错估, pole slot 不算)

### Completion gate: NO-GO ✗
- first layout: **INFEASIBLE 134/220 uncovered** (5 个 crusher_blue_iron 反复 uncovered)

### Cut loop 10 iter (loose nogood cut): NO-GO ✗
| iter | master(s) | uncovered |
|---|---|---|
| 1 | 81.8 | 134 |
| 3 | 87.0 | **133 (-1)** |
| 4-10 | 88-94 | **133 (stuck 7 iter)** |

### Phase 3 tight cut (deletion-based core minimizer 缩到 size 6): NO-GO ✗
6 iter master 加 6-instance cut **振荡不收敛** (134→125→133→133→133→123).

## 经验跟教训 (含瓶颈理解更新)

- **跟 L12-L15 不同** — L16 master 端方向真对 (81s vs 30 min hard evidence), 但 **cut 端 instance-level Benders 不够**.
- **瓶颈理解更新**: 即使 tight cut (size 6, -97% from 220), master 仍选 categorically uncoverable layouts 不收敛.
- **paradigm-level finding**: instance-level Benders cut 在 problem geometry 下 doesn't propagate enough. 需要禁 "几何位置不可 cover 的 facility 摆位" 跨所有 instance, 但这是 paradigm-level 改动, GPT v11 explicit reject ("豪猪式约束").

## code/

- `code/` 含 Phase 0 probe + Phase 3 deletion core + 10 iter cut loop log
- 详 `code/README.md`
