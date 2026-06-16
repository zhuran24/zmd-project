# Path 15 — PGW-UB (Positive Global Witness + UB Closure)

## 当时项目情况

Path 12-14 全死 (3 paradigm cut 框架同质). GPT v4 review.

## 为什么走这条路

GPT v4 plan: 完全不同方向 — **正向 witness + UB closure** (不是反向 cut).
- Phase 0-1: 找 positive witness (FEASIBLE layout)
- Phase 2: Route-aware pinned LNS master, top-k blocker unpin + 改 master 局部
- paradigm 不写 cut, 不依赖 master 加约束累积

跟 Path 12-14 不同 dimension — 反向 cut 全死, 试正向.

## 实验过程

Phase 0 cheap gate ~1h. 8 anchor production data 实测 P0.3 locality signal.

## 实验结果

| anchor | blocked_owners | top5_cov | sac |
|---|---|---|---|
| interior_22_28 | 276 | 0.048 | 22 |
| interior_10_10 | 311 | 0.046 | 71 |
| interior_44_30 | 312 | 0.046 | 80 |
| interior_15_40 | 286 | 0.053 | 12 |
| small_10x10 | 324 | 0.044 | 73 |
| small_15x10 | 327 | 0.046 | 78 |
| small_15x15 | 327 | 0.046 | 77 |

target: blocked ≤120, top5_cov ≥0.55, sac ≤5. **实测全 fail, top5_cov 10x off**.

0/7 eligible anchors 满足 P0.3 子条件.

## 经验跟教训 (含瓶颈理解更新)

- **第一个 Phase 0 cheap gate 直接 fail** 的 paradigm (前 Path 13/14 都 GO).
- **Root cause**: production data 的 routing residual 是**全图 conjunction**不是 spatial-cluster. top 5 blocker owners 只占 4.6%-5.3% 总压力 — LNS unpin top-k 改 5% 没动 95%, 退化 full master 重 solve.
- **瓶颈理解更新**: routing 问题在 production 上是全图 conjunction, 不是 local spatial-cluster. 这是跟 PCR-CUT 同 root finding 但 from 正向方向.
- **paradigm-level meta-finding** (4 paradigm 后): 2 大类 paradigm 都试过死了 (局部反馈+master cut / 正向 witness+UB closure).

## code/

- `code/` 含 paths/15_positive_global_witness/phase0_pgw_probe.py (360 LOC trial script, 不改 src)
