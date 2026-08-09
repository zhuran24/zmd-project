# Pricing 界质量判定实验与精确 Lagrangian 记账

> research-only：本报告、脚本和短跑均不构成正式证书，不登记任何界。
>
> 适用范围：包内 25-region 分区、当前 fixed/reserved 掩码、`R-BODY-IN-REGION`、`R-FRONT-IN-REGION`、`R-PORTAL-FIXED`、`R-POWER-LOCAL` 与 strict 单分量语义。结论不外推到更宽的布局问题。

## 0. 结论先行

【已证明】`03_our_assessment_of_the_machine.md §2.2` 的草稿方向是对的，但必须补上 bucket 运输等式的自由对偶变量，并先做消元。消元后的 bucket 权重是

\[
w_b(\mu)=\max_{c\in S_b}(A_c-\mu_c)
       =A_b-\min_{c\in S_b}\mu_c,
\]

其中第二个等号使用了本实例中同一 bucket 可服务的 class 都属于同一 template、body 面积相同这一事实。对 family `f` 的合法 pricing 上界记为

\[
B_f\ge \max_{p\in P_f}\left\{\sum_b w_b(\mu)a_{fpb}-\lambda h_{fp}\right\}.
\]

则精确的 anytime 上界是

\[
\boxed{U^*\le \sum_f m_f B_f+\sum_c d_c\mu_c+\lambda.}
\]

若写成 `B_f=π_f+ε_f`，则得到包内草稿形式。这里的 `ε_f` 是有符号上界，负数不应截到 0。截到 0 仍安全，但会白白丢掉已经证明的收紧量。

【已证明】按本包已有的 hole-aware 组合基线，最直接的施工门槛是：若 `CLEAN` 无孔 pricing 的合法局部上界从 146 降到 **142 或更低**，同时保留包内现有 `CLEAN+hole≤129`、边界孔算术界和 `CORNER+hole≤85`，三类互斥孔分支的统一上界就降到 **3324**。四格 local drop 经 16 倍乘数变成 64 格，正好补齐 3388 到 3324 的距离。这里的 129/85 来自随附 `MAX_POLES_PER_REGION=3` 模型，因此这张 3324 证书明确属于包内 cap-3 scope；主实验的 no-cap 上界可以安全用于该较小 scope，但不能反过来把 129/85 外推成 no-cap 上界。

【强论据】30 分钟足够买到“加权目标下界会不会动”的判定，不足以声称覆盖真实 master 的全部对偶区域。下面的主协议在 24 逻辑核上使用 5 个并发进程、每进程 4 workers，固定部分约 11.5 分钟 solver cap，加上 Python 建模、I/O 和调度，设 **20 分钟硬停**；只有落入中间地带才允许使用剩余 10 分钟。

【猜测】基于包内无孔纯面积跑的 144 至 540 秒 flat-bound 记录，先验偏向 NO-GO。但这个先验不能替代实验，因为 bucket 权重会把目标改成选择性 packing，且可能出现负系数。GO/NO-GO 的数字门见第 3 节。

---

# 1. 请求 1：可直接执行的实验协议

## 1.1 Pricing 目标与分支方式

【已证明】对固定合成对偶 `(μ,λ)`，每个 family 必须求

\[
Q_f(\mu,\lambda)=\max_{p\in P_f}\left\{\sum_b w_b(\mu)a_{fpb}-\lambda h_{fp}\right\}.
\]

实验不在一个 CP-SAT 里做 hole 的大析取，而是分别解：

```text
Q_f^0 = max{ Σ_b w_b n_b : 合法局部 pattern, h=0 }
Q_f^1 = max{ Σ_b w_b n_b - λ : 合法局部 pattern, h=1 }
Q_f   = max(Q_f^0, Q_f^1)
```

【已证明】分支后取 `max` 与原问题完全等价；固定 `h` 会删掉一层析取，通常比单模型更利于 bound。`CORE` 的 hole pose 为空，所以 `Q_CORE^1=-∞`；其无孔空 pattern 已由随附脚本实测为合法且最优值 0。

## 1.2 完整变量表

数量是从包内现有枚举器逐项重放得到的。边界族指七个 `LEFT/BOTTOM` family；它们的 body pose 数相同，pole 数在 138 到 139 之间。

| 符号 | 域 | 语义 | CLEAN | 边界族 | CORNER | CORE | 相对 `08_area_probe.py` |
|---|---|---|---:|---:|---:|---:|---|
| `x_j` | Bool | 选择 body pose `j=(template, orientation, anchor, wide_side, level)` | 2740 | 2360 | 2044 | 0 | 保留，但删除 cheapest-level 过滤，枚举全部 8 个 template-level bucket |
| `g_a` | Bool | 选择 2×2 pole anchor | 157 | 138–139 | 123 | 20 | 保留 |
| `o_v` | Bool | 非 fixed cell `v` 被 body 或 pole 占据 | 196 | 182 | 170 | 101 | 保留 |
| `q_v` | Bool | `v` body-free 且位于指定根的连通自由子图 | 196 | 182 | 170 | 101 | 保留；strict 主臂使用单根 |
| `F_uv` | Int `[0,N]` | 有向网格边上的单商品流 | 728 | 674 | 624 | 314 | 保留 |
| `s_r` | Int `[0,N]` | 根供给 | 1 | 1 | 1 | 1 | strict 保留；loose 校准臂用全部 live stubs |
| `h_r` | Bool | 选择一个 6×7 或 7×6 hole pose | 144 | 127 | 112 | 0 | 保留；只在固定 `h=1` 分支建立 |
| `n_b` | Int `[0,21]` | bucket `b` 的 selected body 数 | 8 | 8 | 8 | 8 | 新增 |

【已证明】`x_j` 的 2740/2360/2044 是“先枚举全部 capability level”后的语义列空间。实现可再做一项精确 presolve：若同一 template 链上两个连续 level 的 `w_b` 相同，较高 level 在相同 anchor/side 上被较低 level 支配；若 `w_b≤0`，存在一个同值或更优的最优解删除该 body 和不再需要的 pole。该 presolve 只在权重已知后执行，不是原来的 cheapest-level-only 漏列。

代表性逐 level pose 数：

| family | M3 level 1/2/3 | M5 level 1/2 | M6 level 3/4/5 |
|---|---:|---:|---:|
| CLEAN | 448 / 448 / 448 | 272 / 272 | 284 / 284 / 284 |
| 任一边界族 | 392 / 392 / 392 | 232 / 232 | 240 / 240 / 240 |
| CORNER | 344 / 344 / 344 | 200 / 200 | 204 / 204 / 204 |

## 1.3 完整约束表

| 编号 | 约束 | 数量级 | 处理 |
|---|---|---:|---|
| P1 | 每格 occupier `AtMostOne`，并令 `o_v=Σ occupier` | 每格 1 至 2 条 | 保留 |
| P2 | reserved cell `o_v=0` | 8–31 | 保留 |
| P3 | `q_v+o_v≤1` | 每非 fixed 格 1 条 | 保留；relaxed baseline 删除 `q` 与本约束 |
| P4 | live stubs 与 fixed fronts 强制 `q_v=1` | 8 到 31 | 保留 |
| P5 | 对每个 pose 的 wide/narrow side：`Σ q_v≥required·x_j` | `2|J|` | 保留；relaxed baseline 改用 `Σo_v+required·x_j≤|side|` |
| P6 | body 被至少一根 selected local pole 覆盖 | `|J|` | 保留 |
| P7 | selected pole 至少覆盖一个 selected body | `|G|` | 新增的精确支配约束，排除纯障碍 pole |
| P8 | 固定 `MAX_POLES_PER_REGION=3` | 1 | 主臂删除，形成安全过覆盖；只在兼容性/校准臂设为 3 |
| P9 | hole pose 内每格 `q_v=1`，且 `ExactlyOne(h_r)` | `42|H|+1` | 保留；relaxed baseline 改为 `o_v=0` |
| P10 | 每条 flow arc：`F_uv≤Nq_u`、`F_uv≤Nq_v` | `2|E_dir|` | 保留 |
| P11 | 每格流平衡：`in+s-out=q_v` | 每格 1 条 | 保留 |
| P12 | `n_b=Σ_{j:bucket(j)=b}x_j` | 8 | 新增 |
| P13 | branch objective `max Σ_b w_b n_b-λh` | 1 | 替换纯面积目标 |
| P14 | `objective≤P_f^h`，其中 `P_f^h` 是合法 relaxed packing cap | 1 | 新增；防止搜索 bound 在已知 cap 之上漂浮 |

删除项：

| 原项 | 处理 | 理由 |
|---|---|---|
| `pose.level == cheapest_level` | 删除 | 加权目标下不 WLOG |
| `sum(poles) >= 1` | 删除 | 空 pattern 必须存在；负权重时它可能最优 |
| 固定 pole cap 3 | 主臂删除 | 删除限制只扩大 pricing 可行集，所得上界仍合法；同时规避“cap 3 未证明无损”的漏列风险 |
| `area_lb/area_ub` 与 phase-B area decision | 删除 | 实验只需要加权最大化的 anytime bound；合法 objective cap 由 P14 提供 |
| 纯面积目标 | 删除 | 改为精确 bucket 权重 |

【已证明】删除 pole cap 3 会让局部可行集变大，因此只可能把 `B_f` 抬高，不会制造错误证书。若最终正式证书明确只针对“每区至多 3 杆”的登记限制，也可以保留 cap 3；本实验主臂选择更保守的过覆盖口径。记账器同时输出两条互不混淆的读数：no-cap Lagrangian hybrid，以及复用 129/85 的 supplied cap-3 exactly-one-hole 分支界。

## 1.4 Capability level、bucket 与实际计数

```text
M3 level 1 -> M3_1i1o
M3 level 2 -> M3_1i2o+2i1o
M3 level 3 -> M3_1i3o+2i1o
M5 level 1 -> M5_1i1o
M5 level 2 -> M5_1i2o
M6 level 3 -> M6_3i1o
M6 level 4 -> M6_4i1o
M6 level 5 -> M6_5i1o
```

【已证明】每个 selected pose 已承诺 capability level 和一对 front sides，所以 `n_b` 是线性计数。最终 incumbent 还要由 `evaluate_pattern()` 重新计算实际 bucket；脚本同时记录 credited 和 actual objective，并断言 `actual≥credited`。由于 bucket 权重沿 capability 链单调不降，任意物理 pattern 都能把每个 body 重新标成其实际最高能力而不改 footprint、pole 或连通性，因此 modeled optimum 与 evaluator bucket optimum 相同。

## 1.5 三组合成对偶

### Class 对偶与 hole 对偶

| 组 | `μ_3L` | `μ_3O2` | `μ_3O3` | `μ_3I2` | `μ_5L` | `μ_5O2` | `μ_6I3` | `μ_6I4` | `μ_6I5` | `λ` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D0_AREA | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| D1_SCARCITY_PRICES | 1 | 7 | 6 | 7 | 2 | 10 | 2 | 12 | 12 | 15 |
| D2_SLACK_EDGE_SELECTIVE | 12 | 12 | 0 | 12 | 30 | 0 | 30 | 30 | 0 | -20 |

### Family `π_f` 锚点

| 组 | CLEAN | LEFT_J1 | LEFT_J2 | LEFT_J3 | BOTTOM_I1 | BOTTOM_I2 | BOTTOM_I3 | BOTTOM_I4 | CORNER | CORE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D0_AREA | 146 | 134 | 134 | 134 | 134 | 134 | 134 | 134 | 118 | 0 |
| D1_SCARCITY_PRICES | 135 | 124 | 124 | 124 | 124 | 124 | 124 | 124 | 109 | 0 |
| D2_SLACK_EDGE_SELECTIVE | 164 | 149 | 149 | 150 | 149 | 149 | 150 | 149 | 136 | 0 |

### 消元后的 8 个 bucket 权重

bucket 顺序为 `M3_1 / M3_2 / M3_3 / M5_1 / M5_2 / M6_3 / M6_4 / M6_5`。

| 组 | 权重向量 | `Σd_cμ_c` | `Σm_fπ_f` | 加 `λ` 后锚点总界 |
|---|---|---:|---:|---:|
| D0_AREA | `9/9/9/25/25/24/24/24` | 0 | 3392 | 3392 |
| D1_SCARCITY_PRICES | `8/8/8/23/23/22/22/22` | 629 | 3137 | 3781 |
| D2_SLACK_EDGE_SELECTIVE | `-3/-3/9/-5/25/-6/-6/24` | 3462 | 3805 | 7247 |

对三组的解释：

1. 【已证明】D0 位于规范 dual 域 `μ≥0, λ自由, π自由`，且目标逐字退化成纯 body area。它是与现有 21 份结果可比较的控制组。
2. 【强论据】D1 给小需求 class 较高价格，但 bucket 消元取 `min μ`，所以高 level bucket 仍可被低价 base class 吸收，三个 template 内的 level 权重全部相等。它专门测试运输层的“链遮蔽”几何。
3. 【猜测】D2 是对选择性 packing 的压力测试：低 level 收益非正，只剩最高 level 正收益，同时 `λ=-20` 奖励 hole。它覆盖“多数 pose 不值得选，剪枝可能显著改善”的一端，也覆盖 all-level 枚举膨胀的一端。

`π` 合法性：

- 【已证明】D0 的 `π` 就是不带孔 packing ceiling；hole 不增加 body area，所以对两支都合法。
- 【已证明】D1 的最大单位面积收益是 `23/25=0.92`。故 `ceil(0.92×146)=135`、`ceil(0.92×134)=124`、`ceil(0.92×118)=109` 是合法 cap；`λ=15` 只会降低 hole 支。
- 【已证明】D2 的正 bucket 权重都不超过相应 body area，hole 支额外获得 20。用 hole 算术面积 cap 得 `max(146,144+20)=164`；五个 H129 边界为 149；两个 H130 边界为 150；`CORNER` 为 `max(118,116+20)=136`。

【强论据】这三组覆盖三种目标形状，不覆盖真实 master 的未知对偶区域。D1、D2 的总锚点界很高，不能被误读成候选证书 dual。它们是 solver-bound 行为探针，不是“真实 dual 的代表样本”。

## 1.6 最便宜的实例选择

主判定只跑以下五种 branch，每种乘三组 dual，共 15 个任务：

| branch | 选择理由 |
|---|---|
| CLEAN，无孔，strict | 16 倍杠杆；任何 1 格 local drop 等于 16 格全局 drop |
| LEFT_J3，无孔，strict | 包内 strict 边界七族中 gap 最大，134 对 109/110；作为困难边界代表 |
| CLEAN，有孔，strict | hole 自由度高，已有 loose bound 129；检查 strict 与加权目标共同作用 |
| LEFT_J3，有孔，strict | H130 的最坏边界孔算术分支代表；统一上界由这类分支控制 |
| CORNER，有孔，strict | 最受限、已知易证实例；用于辨别“所有 hole 都易”还是只限 CORNER |

另加一条兼容性校准：`D0_AREA + CORNER + hole + loose + max_poles=3`，240 秒。包内同口径曾在 124.10 秒证到 85。若新脚本在目标机 240 秒仍不能把 bound 压到 90 或更低，本次环境/模型改造不具可比性，判定应标为 `INVALID_CALIBRATION_FAILED`，不能标 NO-GO。

【强论据】不先跑全部十族的原因是 CLEAN 决定全局杠杆，LEFT_J3 代表最难边界相位，CORNER-hole 是阳性控制。其余六个边界 family 只在中间地带补跑；CORE 无 body pose，已单独验证空列值 0。

## 1.7 预算阶梯与并发

目标机排程：5 个 CP-SAT 进程并发，每个 `num_workers=4`，占 20 逻辑核，余 4 核给 Python 建模、GLOP、I/O 与系统。一次只让一个 solver 使用其进程内 4 workers。

| 阶段 | 任务 | 每任务 solver cap | 最大任务数 | 波数 | 理论波长 |
|---|---|---:|---:|---:|---:|
| S0 | 15 个 branch 的无连通 relaxed packing | 15 s | 15 | 3 | 45 s |
| S1 | 15 个 strict 主任务 | 15 s | 15 | 3 | 45 s |
| S2 | 必跑 6 个加所有有早期下降者，最多 8 个 | 60 s | 8 | 2 | 120 s |
| S3 | 评分最高且覆盖三种目标形状的 4 个任务，seed 0；并行塞入 1 个 loose 校准 | 240 s | 5 | 1 | 240 s |
| S4 | 同 4 个关键任务，seed 1 | 240 s | 4 | 1 | 240 s |

固定 solver cap 合计约 690 秒。S0 的 bound 直接作为每个固定 branch 的合法 `P_f^h`，并以 `objective≤P_f^h` 写回 S1 到 S4，避免 CP-SAT 的原始搜索界在一个已经知道无效的高空区间游荡。分析器一方面按 `max(no-hole,hole)` 形成各 dual 的 no-cap Lagrangian hybrid；另一方面把 D0 的 no-cap 读数作为较小 cap-3 scope 的合法上界，与随附 129/85 做 exactly-one-hole 九分支记账。

升级规则：

```text
S1 -> S2:
  必跑:
    D0 CLEAN no-hole
    D1 CLEAN no-hole
    D2 CLEAN hole
    D0 LEFT_J3 no-hole
    D2 LEFT_J3 hole
    D0 CORNER hole
  再加入任一满足 drop >= 1 或 closure >= 0.10 的任务
  按 multiplicity * drop 排序，总数最多 8

S2 -> S3:
  保证 D0/D1/D2 均有代表，优先 CLEAN，再取最高 leverage
  总数 4

S4:
  原样重复 S3 四项，只改 random_seed=1
```

## 1.8 Bound 轨迹与记录 schema

使用 OR-Tools 9.15 的 `CpSolver.best_bound_callback` 做事件式记录，不从另一个线程轮询 solver。轨迹含两个层次：

1. `raw_bound_scaled`：CP-SAT 原始 best bound；
2. `bound_scaled`：`min(raw_bound, legal_branch_cap)` 的已认证轨迹。

在 `t=0` 先写入 S0 cap；之后每次 bound 真下降才追加事件。右连续重采样坐标固定为：

```text
0, 1, 2, 5, 10, 15, 30, 60, 120, 240 秒
```

每次运行至少记录：

```json
{
  "family": "CLEAN",
  "hole": false,
  "strict": true,
  "dual": "D1_SCARCITY_PRICES",
  "scale": 1,
  "mu_scaled": {"...": 0},
  "lambda_scaled": 15,
  "pi_scaled": 135,
  "bucket_weights_scaled": {"...": 23},
  "objective_cap_scaled": 132,
  "max_poles": null,
  "seed": 0,
  "workers": 4,
  "runtime": {"python": "3.13.x", "ortools": "9.15.6755"},
  "model_signature_sha256": "... coordinates, options and model-size signature ...",
  "model_size": {"variables": 0, "constraints": 0, "kept_levels": {}},
  "build_wall_seconds": 0.0,
  "solve_wall_seconds": 0.0,
  "bound_events": [
    {"t": 0.0, "bound_scaled": 132, "source": "explicit"}
  ],
  "incumbent_events": [
    {"t": 4.2, "objective_scaled": 91, "credited_bucket_counts": {}}
  ],
  "final_validation": {
    "evaluator_ok": true,
    "independent_audit_ok": true,
    "actual_bucket_counts": {},
    "actual_objective_scaled": 91
  }
}
```

派生读数：

```text
P      = S0 relaxed branch upper bound
B(t)   = strict certified best bound at t
I(t)   = best validated incumbent objective
drop   = P - B
gap    = P - I
closure= (P - B) / max(1, P - I)
T1     = first t with drop >= 1
T25    = first t with closure >= 0.25
late_drop = B(60) - B(240)
leverage  = family_multiplicity * drop
```

【强论据】`closure` 是区分“负系数让 incumbent 降得更快，但 bound 更糟”与“bound 真变好”的关键。只看 incumbent 会把更大的搜索 gap 误判为进步。

## 1.9 可执行伪代码

```python
for dual in [D0, D1, D2]:
    weights = {
        b: max(A[c] - dual.mu[c] for c in SERVABLE[b])
        for b in BUCKETS
    }

    for family, hole in PRIMARY_BRANCHES:
        P[dual, family, hole] = solve_relaxed_pricing(
            weights=weights,
            lambda_=dual.lambda_,
            family=family,
            fixed_hole=hole,
            seconds=15,
            workers=4,
            max_poles=None,
        ).best_objective_bound

parallel_run_all_15(seconds=15, strict=True, cap=P, seed=0)
selected_60 = mandatory_6 + tasks_with(drop >= 1 or closure >= 0.10)
parallel_run(selected_60[:8], seconds=60, strict=True, cap=P, seed=0)
selected_240 = choose_four_covering(D0, D1, D2, prefer="CLEAN/leverage")
parallel_run(selected_240 + [loose_corner_hole_control], seconds=240, seed=0)
parallel_run(selected_240, seconds=240, seed=1)

for dual in [D0, D1, D2]:
    for family in FAMILIES:
        B_family = max(B_nohole, B_hole)  # missing branch uses legal cap
    L[dual] = sum(m[f] * B_family[f] for f in FAMILIES) \
              + sum(d[c] * dual.mu[c] for c in CLASSES) \
              + dual.lambda_

verdict = apply_numeric_gates(trajectory, L, calibration)
```

随附命令：

```bash
PY=/path/to/python3.13
$PY run_protocol.py \
  --out-root ./pricing_protocol_out \
  --python "$PY" \
  --bundle ../pricing_exp/11_runnable

$PY analyze_protocol.py ./pricing_protocol_out/manifest.json \
  --out ./pricing_protocol_out/decision.json
```

---

# 2. 请求 2：`ε_f` 到全局界的换算与阈值

## 2.1 一般 Lagrangian 换算

定义 signed reduced-cost upper：

\[
\epsilon_f=B_f-\pi_f.
\]

则

\[
L=\sum_fm_f(\pi_f+\epsilon_f)+\sum_cd_c\mu_c+\lambda.
\]

所以每下降 1 个 local objective unit：CLEAN 使全局界下降 16；其余每个 family 下降 1。D1、D2 的换算斜率完全相同，只需把下表的 3392 零点分别换成 3781、7247；这也显示它们是目标形状探针，而非近证书 dual。

### 以 D0 pure-packing 3392 为零点

| 只改变的项目 | local `ε` | 全局界 |
|---|---:|---:|
| CLEAN | 0 | 3392 |
| CLEAN | -1 | 3376 |
| CLEAN | -2 | 3360 |
| CLEAN | -3 | 3344 |
| CLEAN | -4 | 3328 |
| CLEAN | -5 | 3312 |
| 七个边界 family 全部取同一个 `ε` | -1 | 3385 |
| 七个边界 family 全部取同一个 `ε` | -4 | 3364 |
| 七个边界 family 全部取同一个 `ε` | -8 | 3336 |
| 七个边界 family 全部取同一个 `ε` | -9 | 3329 |
| 七个边界 family 全部取同一个 `ε` | -10 | 3322 |
| 任一 non-CORE 单倍 family 单独下降 | -64 | 3328 |
| 任一 non-CORE 单倍 family 单独下降 | -68 | 3324 |
| 24 个 non-CORE region 对应 family 全部每区下降 1 | -1 | 3368 |
| 24 个 non-CORE region 对应 family 全部每区下降 2 | -2 | 3344 |
| 24 个 non-CORE region 对应 family 全部每区下降 3 | -3 | 3320 |

各 family 单独改变时的逐族表：

| family | multiplicity | `ε=-1` 时全局界 | `ε=-2` 时全局界 | `ε=-4` 时全局界 | 若只靠本族达到 3324 |
|---|---:|---:|---:|---:|---|
| CLEAN | 16 | 3376 | 3360 | 3328 | `ε≤-5` 已足够，得到 3312 |
| LEFT_J1 | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| LEFT_J2 | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| LEFT_J3 | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| BOTTOM_I1 | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| BOTTOM_I2 | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| BOTTOM_I3 | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| BOTTOM_I4 | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| CORNER | 1 | 3391 | 3390 | 3388 | 需 `ε≤-68` |
| CORE | 1 | 3391（纯代数） | 3390（纯代数） | 3388（纯代数） | 实际 `Q_CORE=π_CORE=0`，不可再降 |

【已证明】相对 pure baseline，CLEAN local drop 4 只得到 3328，还差 4；例如再从四个 non-CORE 单倍 family 各压 1，或从这些 family 合计压 4，才到 3324。CLEAN local drop 5 单独足够。

## 2.2 Exactly-one-hole 三支的精确阈值

令：

```text
dC0 = 146 - B(CLEAN, no-hole)
dC1 = 129 - B(CLEAN, hole)
dj0 = 134 - B(boundary j, no-hole)
dj1 = H_j - B(boundary j, hole)
dR0 = 118 - B(CORNER, no-hole)
dR1 =  85 - B(CORNER, hole)

H_j = 129 for LEFT_J1, LEFT_J2, BOTTOM_I1, BOTTOM_I2, BOTTOM_I4
H_j = 130 for LEFT_J3, BOTTOM_I3
```

相对包内已有 hole-aware 基线，各互斥分支为。由于 `CLEAN+hole=129` 与 `CORNER+hole=85` 的原跑带 pole cap 3，本表是 supplied cap-3 scope 的精确分支记账；无孔项即使来自 no-cap pricing 仍可安全用于此表，因为它是更大可行集的上界。

| 分支 | 基线 | 收紧后上界 | 达到 `≤3324` 的充要线性条件 |
|---|---:|---|---|
| hole 在 CLEAN | 3375 | `3375-15dC0-dC1-Σdj0-dR0` | `15dC0+dC1+Σdj0+dR0 ≥ 51` |
| hole 在 H129 边界 `k` | 3387 | `3387-16dC0-Σ(j≠k)dj0-dj1[k]-dR0` | `16dC0+Σ(j≠k)dj0+dj1[k]+dR0 ≥ 63` |
| hole 在 H130 边界 `k` | 3388 | `3388-16dC0-Σ(j≠k)dj0-dj1[k]-dR0` | `16dC0+Σ(j≠k)dj0+dj1[k]+dR0 ≥ 64` |
| hole 在 CORNER | 3359 | `3359-16dC0-Σdj0-dR1` | `16dC0+Σdj0+dR1 ≥ 35` |

统一上界是上述九个具体分支的 `max`，不是 `min`，四类条件必须同时成立。

### CLEAN 无孔 bound 的杠杆

保持其他现有界不动：

| `B(CLEAN,no-hole)` | `dC0` | hole-aware 统一界 | 距 3324 |
|---:|---:|---:|---:|
| 146 | 0 | 3388 | 64 |
| 145 | 1 | 3372 | 48 |
| 144 | 2 | 3356 | 32 |
| 143 | 3 | 3340 | 16 |
| **142** | **4** | **3324** | **0** |
| 141 | 5 | 3308 | 已越线 |

【已证明】`B(CLEAN,no-hole)≤142` 是当前 hole-aware 数字下最简单的充分条件。该条件使用的 129/85 是 cap-3 scope 上界；若正式目标改成不限制杆数的过覆盖模型，必须重新取得对应 no-cap hole 上界，不能沿用这两个数。

【已证明】若只能压到 143，则还需补 16 个对所有当前最坏边界孔分支都生效的 global units。一个具体充分组合是 `dR0≥16`，即 `CORNER` 无孔 bound 从 118 压到 102；此时 CLEAN-hole、所有边界-hole、CORNER-hole 三类条件均满足。它只是坐标示例，不是性能预测。

【已证明】只继续收紧 `CLEAN+hole` 或 `CORNER+hole` 不会改变当前 3388 的最坏边界-hole 分支。hole-specific bound 必须按“孔可以落在哪里”逐支覆盖。

## 2.3 GO 数字门

以下是施工投资门，不是数学定理。

1. **GO-CERTIFICATE**【已证明】：满足以下任一项：任一 dual 的 no-cap Lagrangian hybrid `L≤3324`；或 D0 的 supplied cap-3 exactly-one-hole 统一分支界 `≤3324`。这时实验已经给出数值上界，下一步不是“决定是否造”，而是固化对应 scope 的可复核证书链。
2. **GO-DIRECT**【猜测】：D0 的 supplied cap-3 exactly-one-hole 统一分支界在 240 秒内达到 `≤3332`，且 `D0/CLEAN/no-hole` 的 `B(60)-B(240)≥1`。这代表离证书最多 8 格，且最高杠杆 branch 的 bound 仍在移动。
3. **GO-SHAPE**【猜测】：三组 dual 中至少两组同时满足：
   - 某个 CLEAN branch 相对 S0 cap 的 local drop `≥4`；
   - 五个主 branch 的 median `closure≥0.25`；
   - 至少一个任务 `late_drop≥1`。

GO-SHAPE 的含义不是这些合成 dual 已接近证书，而是“加权目标确实改变了 bound 的可解性”；真实 master dual 值得用 2 至 4 天去获取。

## 2.4 NO-GO 数字门

先通过校准。随后以下条件必须全部成立：

1. 【强论据】S3/S4 的四个关键任务都完成 seed 0 与 seed 1 两次 240 秒运行：
   - D0 CLEAN no-hole；
   - D1 CLEAN no-hole；
   - D2 CLEAN hole；
   - D2 LEFT_J3 hole。
2. 【猜测】每次都满足 `P-B<1`，并且 `B(60)-B(240)<1`。整数目标下即“240 秒一格也没啃，最后 180 秒也没有下降”。
3. 【猜测】全部已升级任务的最大 `closure<0.10`。
4. 【猜测】D0 supplied cap-3 exactly-one-hole 界相对 3388 的 reduction `<16`，即连 CLEAN 的一个 local unit 杠杆都没有兑现。
5. 【强论据】loose CORNER-hole 校准在 240 秒内达到 bound `≤90`；否则结果是环境失配，不是 NO-GO。

满足全部条件，输出 **NO-GO**。这是可证伪的业务判据：任一关键任务出现一格 bound drop、任一 closure 达 0.10、或校准失败，都会推翻 NO-GO。

## 2.5 中间地带

若既不 GO 也不 NO-GO，使用硬预算剩余的最多 10 分钟，不造 master：

| 补充实验 | 任务数 | 每任务 | 5 并发墙钟上限 | 目的 |
|---|---:|---:|---:|---|
| 取表现最好 dual，补齐七个边界的无孔和有孔 | 14 | 120 s | 360 s | 检查 LEFT_J3 是否可外推 |
| CLEAN 无孔/有孔，`max_poles=None` 对 `3`，两个 seeds | 4 | 60 s | 60 s | 定位 pole overcoverage 的界代价 |
| CLEAN 最佳 dual，flow 编码对 parent-depth 编码 | 2 | 240 s | 240 s，可与前项交叠 | 判断弱点是否来自流松弛 |

【猜测】补跑后仍没有任何 `drop≥2` 或 `closure≥0.15`，按 NO-GO 处理；若 parent-depth 单项让 CLEAN local drop 达 3，则把“换连通编码”计入两天原型范围，而不是直接放弃。

---

# 3. 请求 3：规范 primal/dual 与精确不等式

## 3.1 Primal

集合与参数：

```text
F: 10 个 region family，multiplicity m_f
P_f: family f 的完整合法局部 pattern 集，可安全过覆盖，不可漏列
B: 8 个 bucket
C: 9 个 operation class
S_b: bucket b 可服务的 class 集
E={(b,c): c in S_b}
a_fpb: pattern p 的 bucket b body 数
h_fp: pattern 是否携带 hole
d_c: class demand
A_c: class body area
```

变量：

```text
z_fp >= 0     family f 采用 pattern p 的区域数，允许分数
 y_bc >= 0    bucket b 的供给运输给 class c，仅在 (b,c) in E 建立
```

规范上界 LP：

\[
\begin{aligned}
\max\quad & \sum_{(b,c)\in E} A_c y_{bc}\\
\text{s.t.}\quad
&\sum_{p\in P_f}z_{fp}=m_f &&\forall f \tag{C1}\\
&\sum_{f,p}a_{fpb}z_{fp}-\sum_{c\in S_b}y_{bc}=0 &&\forall b \tag{C2a}\\
&\sum_{b:c\in S_b}y_{bc}\le d_c &&\forall c \tag{C2b}\\
&\sum_{f,p}h_{fp}z_{fp}=1 && \tag{C3}\\
&z,y\ge0.
\end{aligned}
\]

【已证明】任一满足当前限制的完整布局映射为整数 `z,y`，C2b 取等，目标为 3325。故该 LP 的最优值 `U*<3325` 蕴含当前限制档位无解。反向不成立。

## 3.2 Dual 与符号方向

对偶变量：

| primal 约束 | dual | 域 |
|---|---|---|
| C1 family convexity equality | `π_f` | free |
| C2a bucket transport equality | `γ_b` | free |
| C2b class upper bound | `μ_c` | `μ_c≥0` |
| C3 exactly-one-hole equality | `λ` | free |

Dual：

\[
\begin{aligned}
\min\quad & \sum_fm_f\pi_f+\sum_cd_c\mu_c+\lambda\\
\text{s.t.}\quad
&\pi_f+\sum_b\gamma_ba_{fpb}+\lambda h_{fp}\ge0
&&\forall f,p,\\
&-\gamma_b+\mu_c\ge A_c
&&\forall (b,c)\in E,\\
&\mu_c\ge0,\quad \pi_f,\gamma_b,\lambda\text{ free}.
\end{aligned}
\]

第二组约束等价于

\[
-\gamma_b\ge A_c-\mu_c\quad\forall c\in S_b.
\]

令

\[
w_b=-\gamma_b=\max_{c\in S_b}(A_c-\mu_c).
\]

给定 `μ` 时，取最小合法 `w_b` 只会放松 pattern 对偶约束，不增加 dual 目标，因此该消元是精确的。pattern 约束变成

\[
\pi_f\ge \sum_bw_ba_{fpb}-\lambda h_{fp}.
\]

## 3.3 Anytime 不等式的逐步核对

对任一 primal 可行解：

\[
\begin{aligned}
U
&=\sum_{b,c}A_cy_{bc}\\
&=\sum_{b,c}(A_c-\mu_c)y_{bc}+\sum_c\mu_c\sum_by_{bc}\\
&\le\sum_bw_b\sum_cy_{bc}+\sum_c\mu_cd_c\\
&=\sum_{f,p,b}w_ba_{fpb}z_{fp}+\sum_c\mu_cd_c\\
&=\sum_{f,p}\left(\sum_bw_ba_{fpb}-\lambda h_{fp}\right)z_{fp}
  +\lambda\sum_{f,p}h_{fp}z_{fp}+\sum_c\mu_cd_c\\
&\le\sum_fB_f\sum_pz_{fp}+\lambda+\sum_c\mu_cd_c\\
&=\boxed{\sum_fm_fB_f+\sum_c\mu_cd_c+\lambda}.
\end{aligned}
\]

每一步分别使用：`w_b` 定义、C2b、C2a、C3、pricing upper、C1。

### `λ` 的位置

【已证明】C3 是右端为 1 的等式，所以 dual objective 中是 `+λ`；pricing 目标中是 `-λh_p`。`λ` 可以正、负或零。正 `λ` 惩罚 hole 列，负 `λ` 奖励 hole 列；全局 `+λ` 与恰好一张 hole 列的 `-λ` 正确抵消。

### `ε_f<0` 是否截断

若 solver 给出

\[
\max_p\left\{\sum_bw_ba_{fpb}-\lambda h_{fp}-\pi_f\right\}\le\epsilon_f,
\]

则令 `π'_f=π_f+ε_f`，所有 pattern 约束仍满足。因此：

\[
U^*\le\sum_fm_f(\pi_f+\epsilon_f)+\sum_cd_c\mu_c+\lambda.
\]

【已证明】`ε_f<0` 时不截断。若实现把 `δ_f=max(0,ε_f)` 定义成“非负违约 allowance”，公式仍安全，但严格更弱。

### CLEAN 的 16 倍塌缩

【已证明】聚合变量满足 `Σ_pz_CLEAN,p=16`，因此 CLEAN 的 `B`、`π`、`ε` 项都乘 16。该 LP 塌缩与 16 个逐 region convexity 约束等价，因为这 16 个 region 的 pattern 集、bucket signature 和 hole signature 完全相同，且没有残余 per-region coupling。

## 3.4 机器记账伪代码

```python
from fractions import Fraction

for b in BUCKETS:
    w[b] = max(Fraction(A[c]) - mu[c] for c in SERVABLE[b])

for f in FAMILIES:
    B0 = legal_upper_from_nohole_pricing[f]
    B1 = legal_upper_from_hole_pricing.get(f, -INF)
    B[f] = max(B0, B1)

family_term = sum(m[f] * B[f] for f in FAMILIES)
class_term  = sum(d[c] * mu[c] for c in CLASSES)
hole_term   = lambda_
L = family_term + class_term + hole_term

print({
    "family_terms": {f: m[f] * B[f] for f in FAMILIES},
    "class_terms": {c: d[c] * mu[c] for c in CLASSES},
    "hole_term": lambda_,
    "upper_bound": L,
    "certificate": L < 3325,
})
```

【已证明】正式代码应先把 GLOP 浮点 dual snap 到一个共同有理网格，例如 `1/1000`，然后以该 snapped dual 作为实际 dual，CP-SAT 目标整体乘 1000 变成整数。不能把每个 bucket 权重独立四舍五入后仍按原 dual 记账。随附 `lagrangian_accounting.py` 使用 `Fraction` 做 exact bookkeeping。

---

# 4. 请求 4：时间盒与放弃条件

## 4.1 实验本身

| 时点 | 动作 | 不满足时 |
|---|---|---|
| 0–2 min | 完成 S0/S1；确认 15 个 JSON、版本、model signature、cap 与 callback 都存在 | 立即停，修 harness；不解释性能 |
| 2–12 min | 完成 S2/S3 | 应已出现 GO 信号、NO-GO flat 信号或明确中间态 |
| 12–20 min | 完成 seed 1 重复与校准 | 20 分钟硬停并运行 analyzer |
| 20–30 min | 只允许第 2.5 节的中间态补跑 | 30 分钟无条件停 |

【强论据】不得把 30 分钟耗在 10 family × 3 dual × 两孔态 × 两 seed 的无门控全量矩阵上。先利用 CLEAN 的 16 倍杠杆做筛选，信息价值更高。

## 4.2 GO 后造机器的阶段检查点

以 8 小时工程日计，硬上限 4 日：

| 检查点 | 必须完成 | 数字门 | 不过即停 |
|---|---|---|---|
| 4 工时 | GLOP 固定 catalog primal、规范 dual、signed-ε 记账、分支 max、精确单测 | finite-catalog primal/dual gap `≤1e-7`；D0 重放 3392；负 ε 单测通过 | 数学/符号链未闭合，不继续写 pricing |
| 12 工时 | CLEAN 与 LEFT_J3 的全 level pricing，hole/no-hole，真实 catalog dual 输入 | 至少一个真实或实验 dual 在 240 秒出现 `drop≥1`，且 evaluator/audit 全通过 | 若真实 dual 与三组合成 dual 全 flat，停 |
| 20 工时 | 10 family oracle、并发调度、一次完整 CG/Lagrangian sweep | 合法全局 bound 相对初始合法 cap 改善 `≥32`；若 `<16`，停 | 说明远不足以补 64 |
| 28 工时 | 至少三轮 master/pricing 交替，保留每轮 anytime bound | 全局 bound `≤3333` 或累计改善 `≥56`，且最近一轮仍改善 `≥2` | 若停在 `>3333` 且一整轮无改善，停 |
| 32 工时，硬停 | 固化 manifest、dual、每族 pricing bound、记账报告 | `≤3324`；或仅在 `≤3332` 且最后 4 工时仍改善 `≥4` 时允许一次人工复核 | 其余一律放弃本机路线 |

【猜测】最后一行的“≤3332 且仍在移动”只允许做收尾复核，不把项目自动延长到第五天。

---

# 5. 请求 5：风险、触发信号与补丁

## 5.1 Bucket 加权后，bound 会更松还是更紧

【已证明】没有单调关系。目标改变后，CP-SAT 的 LP/cut relaxation、branching 和对称性都改变；不能由纯面积 bound 推出加权 bound。

两个方向的可区分读数：

| 现象 | 读数 | 判读 |
|---|---|---|
| 负权重让大量 pose 被支配，问题更容易 | 相对 D0，`T1` 更早、`closure` 更高、`P-B` 真正增大 | 加权目标使 bound 更紧 |
| 选择性目标只压低 incumbent | `P-I` 变大，但 `P-B≈0`，closure 更低 | relaxation/搜索更松，不能用于证书 |
| all-level 变体造成对称膨胀 | build/presolve 增长，bound 事件更晚，去掉 equal-weight level 后恢复 | 枚举成本而非几何难度 |

主判定使用 `closure` 与 `late_drop`，不是“找到的 pattern 分数”。

## 5.2 其余风险

| 风险 | 触发条件 | 观测信号 | 可执行补丁 | 等级 |
|---|---|---|---|---|
| bucket 链遮蔽 | 高价 class 与低价 base class 共属高 level bucket | 多组不同 `μ` 产生完全相同 `w_b` | 每轮记录 `μ→w`；对相同 `w` 的 dual 去重，改采样 bucket-weight 空间 | 【已证明】 |
| all-level 对称膨胀 | 多个 level 权重相同 | pose 数约 2.7 倍，objective 不变 | 先全枚举，再用 equal-weight dominance 删除高 level | 【已证明】 |
| 空 pattern 被漏掉 | 所有正权重消失或 λ 使 hole 支不利 | solver 报 infeasible 或被迫选 pole/body | 删除 `Σg≥1`；CORE/全负权重单测必须返回 0 | 【已证明】 |
| pole cap 3 漏列 | 最优 relaxed/strict pattern需要 4 根以上 | cap3 与 none 的 upper 相差 `≥1` | 主证书用 none；若只证 cap3 限制，报告标题与 manifest 明示 scope | 【强论据】 |
| `π`/cap 太松污染轨迹 | callback 初始 bound 高于已知 packing cap | 早期 bound 下降只是在追已知 cap | S0 先算 branch cap，P14 写进模型，记录 raw 与 certified 两条轨迹 | 【已证明】 |
| hole 分支记错 | 把三个位置分支取 min 或只跑一类 | 单个 hole bound 很漂亮但 unified 不变 | 固定 hole/no-hole pricing，family 内取 max；area branch 间再取 max | 【已证明】 |
| 浮点 dual 四舍五入 | GLOP dual 非整数 | CP-SAT 目标与记账差 1 个 scale unit | snap 到共同有理网格，保存原值、snap 值与 scale | 【已证明】 |
| pose-level 与 evaluator bucket 不一致 | incumbent 的 actual objective 小于 credited | `actual_ge_credited=false` | 立即判模型无效；改为 exact capability literals或按 evaluator bucket 重建 objective | 【已证明】 |
| 单商品流 relaxation 过弱 | incumbent 快速提高，bound 长期钉住 P | closure 接近 0 | 中间态只对 CLEAN A/B parent-depth；以 bound 而非 runtime 选编码 | 【强论据】 |
| LEFT_J3 不代表全部边界相位 | LEFT_J3 有 drop，补跑其他 family 后消失 | 全边界 sweep 方差大 | 中间态补齐 14 个边界 branch | 【强论据】 |
| 多线程随机性 | seed 0/1 bound 轨迹不同 | 仅一个 seed flat 或下降 | NO-GO 必须两个 seed；GO 的合法 bound 可取两次运行的 min | 【已证明】 |
| 合成 dual 不覆盖真实区域 | 三组都 flat 或只有极端 D2 易解 | 无法外推 master dual | 结论只写业务 GO/NO-GO；不写“已覆盖真实 dual” | 【强论据】 |
| 环境/语义漂移 | loose CORNER-hole 不复现已知易例 | 240 秒 bound仍 >90 | 标 INVALID，核对 OR-Tools、workers、pole cap、模型 hash | 【强论据】 |

---

# 6. 请求 6：NO-GO 后更便宜的合法 `ε_f` 来源

合法上界可以取多个来源的最小值：若 `B_f^(k)≥Q_f` 各自成立，则 `min_k B_f^(k)` 仍是合法上界。

| 方案 | 怎么算 | 合法性 | 单任务代价 | 预期紧度 |
|---|---|---|---:|---|
| A. Weighted packing CP-SAT，无连通 | 保留 body/front/pole/hole，删除 `q/F`；最大化同一 bucket 目标 | 可行集是 strict pricing 的超集，所以 optimum 是上界 | 5–15 s | 【强论据】最便宜且通常比面积密度紧；已作为 S0 |
| B. 全模型显式 LP relaxation | 把 `x,g,o,q,h` 放到 `[0,1]`，flow 连续，用 GLOP 求 max | 整数 feasible set 包含在 LP feasible set 内 | 约 0.1–5 s | 【猜测】flow big-M 可能很弱，但确定、可复现 |
| C. Pose-cell set-packing LP | 只保留 pose 冲突、reserved、front 必要条件、hole、pole coverage 的线性放松 | 删除连通与部分 integrality，只扩大可行集 | 1–10 s | 【猜测】通常强于纯面积/knapsack，弱于带 cuts 的 CP-SAT |
| D. Bucket/template 整数背包 | 对每 bucket 用 body area、最少 front-free、至少一杆 4 格等必要资源；解小型 knapsack | 只使用每个合法 pattern 都满足的必要不等式 | <0.1 s | 【强论据】非常便宜；选择性 D2 可能比面积 cap 好，几何上仍粗 |
| E. 预计算 separator surrogate | 枚举 region 网格的小 vertex cuts；若 required cells 落 cut 两侧，至少一个 cut cell 必须 free | 每条 cut 都是 strict 连通的必要条件 | 1–30 s | 【猜测】能针对 flow 弱点，成本远低于完整 parent model |
| F. 7×14 strip/分块 DP 上界 | region 分成两条 7×14 strip，跨 strip body/连通冲突放松；分别 DP 后合并 | 放松跨块约束只会抬高 optimum | 0.1–5 s | 【猜测】对 hole/边界 mask 可能较紧，实现约 1 日 |
| G. CP-SAT root-only/cut-only cap | 固定短时间，禁用大规模 tree 或只取 root 后的 best bound | solver 返回的 best bound 本身合法 | 1–10 s | 【猜测】适合快速比较参数；不保证优于 A/B |

### 具体背包上界示例

对固定 branch 取可用 body 预算 `K_f^h`，令每 bucket 的 body area 为 `A_b`，解：

\[
\max\sum_bw_bn_b\quad
\text{s.t. }\sum_bA_bn_b+4\cdot\mathbf 1[\sum_bn_b>0]\le K_f^h,
\quad n_b\in\mathbb Z_{\ge0}.
\]

再加 template body-count ceilings、front-free 必要预算和已证的 packing ceiling。所有约束都必须是合法 pattern 的必要条件，不能使用未证明的“平均 front 消耗”。

【强论据】A、B、C、D 可以在正式机器之前独立实现，并与 CP-SAT strict bound 取 `min`。其中 A 已包含在本交付脚本。没有任何一个替代方案可先验保证补齐 64 格；它们的价值是把“CP-SAT tree 不动”与“所有廉价 relaxation 本身就太松”区分开。

---

# 7. 实现校验与本地短跑

## 7.1 已完成的机器校验

- 【已证明】原包顶层、`11_runnable/` 与 `12_raw_results/` 的 SHA-256 manifest 全部通过。
- 【已证明】随附 10 个单元测试通过，覆盖 3325 census、三组 bucket 权重、三个 dual 锚点总界、负 `ε` 不截断、3375/3388/3359 孔分支、CLEAN 16 倍杠杆、`CLEAN≤142→3324`、level dominance 与坐标完整性。
- 【已证明】CORE strict 空 pattern 在本地返回 `OPTIMAL=0`，0 body、0 pole，evaluator 与 independent audit 均通过。

## 7.2 本地 pilot，只验证 harness，不做 GO/NO-GO

本地容器是 Python 3.13.5、5 逻辑核、约 5.9 GB；目标环境是 Python 3.13.13、24 逻辑核、47.7 GB。因此下表不能替代目标机协议。

| 任务 | branch cap | incumbent | final certified bound | solver wall | 读法 |
|---|---:|---:|---:|---:|---|
| D1 CLEAN relaxed | 135 | 132 | 132，OPTIMAL | 18.88 s | weighted packing 本身把 cap 压了 3；这是合法替代上界 |
| D1 CLEAN strict，显式 cap 132 | 132 | 78 | 132 | 20.01 s | strict solver 未在 relaxed cap 下再啃一格；incumbent 已由两套审计通过 |
| D2 CORNER hole strict | 136 | 38 | 136 | 5.01 s | 短跑无 bound 下降；只证明 callback/cap/审计链可运行 |

【强论据】pilot 显示为什么必须区分两段 drop：`π-P` 是廉价 packing relaxation 带来的收紧，`P-B_strict` 才是连通模型搜索继续证明出来的收紧。把两者混成一个“CP-SAT 下降”会误判算法来源。

---

# 8. 交付文件

| 文件 | 用途 |
|---|---|
| `pricing_bound_decision_report.md` | 本报告 |
| `pricing_probe.py` | 全 level bucket-weighted pricing、branch cap、轨迹与审计 |
| `duals.json` | 三组合成 dual 的完整坐标 |
| `lagrangian_accounting.py` | exact `Fraction` 记账与 hole branch 算术 |
| `run_protocol.py` | 24-core 分阶段执行器 |
| `analyze_protocol.py` | 读取 manifest 并执行 GO/NO-GO 数字门 |
| `make_tables.py` | 重算阈值表 |
| `generated_tables.md/json` | 机器重算结果 |
| `test_deliverable.py` | 10 个单元测试 |
| `pilot_*.json` | 本地 harness pilot 原始输出 |

最终施工建议：先在目标机原样运行 20 分钟协议，并同时查看 analyzer 的 no-cap Lagrangian hybrid 与 supplied cap-3 exactly-one-hole 界。只有 analyzer 给出 GO，或中间态补跑明确达到第 2.3 节的 shape 门，才投入完整 master；否则把工程预算转向第 6 节的 relaxed/set-packing/knapsack 合法上界组合。
