# L15 — Set-Packing Branch-and-Bound Prover (GPT L14 升级建议)

## 当时项目情况

L14 weighted occupancy 数学能力上限后. GPT 建议 paradigm-level investment: set-packing prover (1-2 月工作). 项目决定先 PoC 验底层假设.

## 为什么走这条路

GPT 假设: **set-packing 核心是项目 stuck 的层**. paradigm 自写 prover 用 weighted LP 作 dual bound, 直接在 (x_{g,p}) 整数变量上搜.

如果 set-packing 核心解决, prover 比 CP-SAT 快几个数量级.

## 实验过程

3 小时 PoC. 关键实验 Step A 跟 Step B 对比:

- **Step A** (full master.solve via LBBD): 27×15 anchor (22,28) → 30 min UNKNOWN. anchor (0,0) corner → 10 min UNKNOWN.
- **Step B** (**minimum set-packing CP-SAT**, 只 demand + cell exclusivity + ghost-forbidden, 不含 master 多余约束): 跑 6 个 anchor.

## 实验结果

Step B 实测:

| anchor | result |
|---|---|
| 27×15 corner (0,0) 1 worker 60s | **INFEASIBLE 2.4s, 0 branch** |
| 27×15 interior (22,28) 8 worker 5 min | **OPTIMAL feasible 7.2s 12K branch** |
| 27×15 corner 8 worker | INFEASIBLE 2.3s |
| 28×15 corner (0,0) | INFEASIBLE 2.3s |
| 28×15 interior (21,27) | OPTIMAL 7.1s |

**Set-packing 核心 CP-SAT 几秒搞定**, 不是瓶颈.

**Step D 锁瓶颈**:
| Config | vars | constraints | master.solve wall | status |
|---|---|---|---|---|
| skip_power=True | 24,824 | 69,910 | **65.9s** 2 LBBD iter 完整 | UNPROVEN |
| skip_power=False (full) | 57,668 | 132,515 | **30 min UNKNOWN** | UNKNOWN |

**真瓶颈 = `_add_geometric_power_coverage_constraints`**.

## 经验跟教训 (含瓶颈理解更新)

- **新错估类型: paradigm 攻错层** (跟算法/前提/数学能力都不同). GPT 假设 set-packing 是瓶颈, 实测 CP-SAT 几秒解决, paradigm 攻错层.
- **瓶颈理解更新**: 真瓶颈不在 set-packing 核心, 在 master **多余的 power_coverage 约束** (disjunctive coverage over-many-pair, CP-SAT 跟 LP-MIP 一样 stuck).
- **省了 1-2 月 paradigm investment** — PoC 3h 出 verdict 救 1-2 月.

## code/

- `code/` 含 minimum set-packing PoC (poc_minimum_setpacking.py, ~150 LOC) + Step A/B/D 对比 trial + 全 logs
- 详 `code/README.md`
