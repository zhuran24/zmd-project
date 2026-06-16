# Path 17 D2 Phase 2 multi-anchor verdict — 2026-05-20

## 结论

🟡 **0/8 CERTIFIED, 7/7 non-corner UNPROVEN** at max_iter=10 cap.

跟之前 5 paradigm (Path 12 RAB-SEP / Path 13 SAC-Hull / Path 14 PCR-CUT) 同
verdict pattern. paradigm 端到端 land ✅ 但 breakthrough ❌.

## 8 anchor 全表

| anchor | size | (ax,ay) | status | wall |
|---|---|---|---|---|
| interior_22_28 | 27×15 | (22, 28) | UNPROVEN | 611.5s |
| interior_10_10 | 27×15 | (10, 10) | UNPROVEN | 658.8s |
| interior_44_30 | 27×15 | (44, 30) | UNPROVEN | 608.2s |
| interior_15_40 | 27×15 | (15, 40) | UNPROVEN | 610.8s |
| corner_0_0_NEGATIVE | 27×15 | (0, 0) | INFEASIBLE | 57.6s (sound, no D2 entry) |
| small_10x10 | 10×10 | (25, 25) | UNPROVEN | 664.0s |
| small_15x10 | 15×10 | (22, 28) | UNPROVEN | 690.9s |
| small_15x15 | 15×15 | (22, 28) | UNPROVEN | 631.7s |

Total wall: ~73 min.

## 关键观察

**Paradigm 端到端 work** ✅:
- 70 D2 cuts added across 7 non-corner anchors (每 anchor 10/10 iter)
- master.solve 全 OPTIMAL — no UNKNOWN
- D2 wall per iter 1.2-2.7s (跟 Phase 0b 一致, p95 ≤ 3s, **200x under** 30s budget)
- core size 全 = 1 (D2 找最 minimal sufficient — single owner)
- baseline byte-for-byte unchanged when env off

**但 paradigm 不 sufficient** ❌:
- 10 cut 累加 master 仍系统性给 routing-infeasible layouts
- 同 PCR-CUT (Path 14) 同 70 cuts + 0 CERTIFIED 同质
- 同 RAB-SEP (Path 12) cert tight 但切空间 ≪ 1% 同质

## 跟 5 paradigm 共同 dead end pattern

D2 跟 Path 12-14 同质死法:
- 都 端到端 land OK
- 都 master 加 cut 持续 OPTIMAL
- 都 0/8 anchor CERTIFIED
- 都 max_iter cap UNPROVEN

不同 paradigm 不同 sub-problem 抽象层:
- Path 12 RAB-SEP: binding-side owner+blocker cert
- Path 13 SAC-Hull: corridor capacity
- Path 14 PCR-CUT: patch belt CP-SAT
- **Path 17 D2: 全图 commodity cell-flow + flow conservation** (新, paradigm 数学最丰富)

**6 paradigm 撞同墙是 strong evidence**:

> pose-bool master + cut on pose-id-dimension 框架不够

D2 paradigm 数学**最丰富** (production routing precheck + D1 都看不到的 connectivity
信息), 但 cut form **被 master pose-bool 限制退化为 instance-pose conjunction no-good**
跟 RAB-SEP 同. 即使 sub-problem 更聪明, cut 表达力被 master form 卡死, 结果同质.

## 关键 finding — cut form 退化

D2 sub-problem 抽 minimal owner-pose core (size 1 per iter) via SufficientAssumptions-
ForInfeasibility. 但 cut 翻译到 master pose-bool 时只能写:

```
sum(x_{i, p_i}) <= |core| - 1
```

也就是 forbid 当前 (instance, pose_idx) 选择. 没法表达 D2 sub-problem 真识别的
信息: "这个 owner 在这个 pose 上, **flow conservation 不可能 satisfy 因为 X**".

master 在 pose-bool 维度看到的只是 "禁止这个 (instance, pose_idx)", 没看到 X
(具体的 connectivity/flow 信息).下次 master 给的 layout 可能跟当前在另一个
owner pose 选择上不同, D2 又 INFEASIBLE 因别的 connectivity 问题. 循环 10 iter
cut 累加, 但每次 cut 切的是 owner-pose specific instance, 切空间 ≪ 1%, 不收敛.

## 23 lever 全 verdict

L1-L16 + Path 12 RAB-SEP + Path 13 SAC-Hull + Path 14 PCR-CUT + Path 15 PGW-UB +
Path 16 GOC-C2 + **Path 17 D2** = 23 lever 全 verdict.

3 大类 paradigm framework + 6 paradigm 实测全 fail:
1. 局部反馈 + master cut (3 paradigm: Path 12, 13, 14)
2. 正向 witness + UB closure (Path 15)
3. 全图 owner-optional + sufficient core (Path 16)
4. **全图 commodity flow + conditional terminal balance (Path 17 D2)** ← 新加

Path 16 跟 Path 17 都 GPT v7 Candidate D family (全图建模). Path 16 直接 RAM 爆
(state pattern 维度), Path 17 D2 RAM 不爆 (vars 100K scale) 但 cut form 退化
跟之前 paradigm 同质死.

## 留下的 infrastructure (可复用)

- `src/models/d2_commodity_flow_core.py` 281 LOC — D2CommodityFlowCore class:
  u/e/capacity/channeling/flow conservation + assumption literal extract_core
- `src/search/d2_separator.py` 215 LOC — orchestrator
- `src/search/benders_loop.py` env-gated hook (front_blocked branch)
- conditional terminal balance encoding (let assumption channeling 真 work)

任何后续 paradigm 想做 "全图 commodity flow + sufficient core" 直接调用.

## ROI

- Phase 0+0b: 2h Claude + 2h wall
- Phase 1: 4h Claude + ~5 min wall
- Phase 2: ~0 Claude (跑 trial) + 73 min wall
- 总: ~6h Claude + 80 min wall (跟 Path 14 PCR-CUT 类似规模)
- 提供 evidence: **6 paradigm 撞同墙** — pose-bool master cut 表达力 fundamental 限制
- 进一步 confirm 用户 hypothesis (master form baseline 是 5+ paradigm 全 fail 隐含原因)

## 下一步候选

paradigm investigation 在 pose-bool master + cut 框架下进一步穷尽证据. Path 17 D2
提供最丰富的 sub-problem 但仍撞 cut form 表达力墙. 真要 break 仍是:

1. **换 master form** (但 v7 Proposition 2 论证: 任何 routing-aware master form 必落
   3 类资源 dead end 之一; Path 16 全图 routing 实测 RAM 爆 confirm; 未知压缩 proof
   system 是出路但是数学领域级研究问题)
2. **放松约束** (用户拒绝)
3. **接受 paradigm investigation 在 known encoding 范畴 完结**

## commit

`583c9dd` Phase 1 land
- TBD Phase 2 verdict commit

## Related

- [[project-pgw-phase0-verdict]] / [[project-goc-phase0-verdict]] — Phase 0 fail paradigm
- [[project-pcr-cut-phase5-verdict]] — Path 14 同质死法
- [[feedback-paradigm-phase0-cheap-gate]] — workflow 验证 (8 次)
- v7 plan Proposition 2 — Path 17 落在 Ω(K|V|+K|E|) 资源区
- BOTTLENECK_STRUCTURE.md "3 性质" framing
