# Endpoint Metrics Protocol v1

> **状态：** `FROZEN_ON_FIRST_COMMIT`。本文件首次进入 Git 的提交即为冻结身份；后续发现缺口只能新建 v2，不原地改写 v1 判据。
> **作用域：** W0 一元 lowering 金丝雀及其后续同类 research-only 实验的终点计价；不建立新的 certified authority，也不修改现有研究上下界账。

## 1. 类型化空值

所有指标必须使用下列状态之一，不得把它们压成数值 `0`：

- `MEASURED`：对象、干预和 evaluator 均已就绪，得到实际数值；
- `ZERO_MEASURED`：在已通过灵敏度检查的 evaluator 上实测差分为零；
- `ZERO_BY_SCOPE`：由 Judgment 的量化范围和消费极性可证明该实验不可能改变该账户；
- `N_A_NOT_READY`：对象、消费者、干预或测量语义尚不存在；
- `UNKNOWN_UNMEASURED`：指标有定义但本轮未测；
- `CENSORED`：已经测量，但预算或观察窗没有给出目标判词；
- `NOT_REACHED`：执行轨迹没有到达该快照点；
- `SENSOR_UNVALIDATED`：evaluator 尚未通过正控、负控和 stale 控制。

## 2. 一库、三本存量账、一张四格流水

本实验不新建三套可变真源。知识、能力和期权是同一组结构化事实的只读投影：

1. **知识账：** 已经严格知道什么；
2. **能力账：** 当前系统已经能可靠执行什么，必须区分 `IMPLEMENTED`、`VERIFIED`、`AUTHORIZED_FOR_EXPERIMENT` 与 `AUTHORIZED_FOR_PRODUCTION`；
3. **期权账：** 哪些已验证资产等待哪些类型化互补项和触发器。

每次实验另写一张四格差分流水：

| 层级 | 语义／搜索状态 | 资源／执行轨迹 |
|---|---|---|
| 切面 | theorem trigger、reject set、域 envelope、family 计数、lowering effect | 本层调用数、墙钟、CPU、RSS、checker 开销 |
| 终点 | 下界、上界、未关闭 score band、lex 优越矩形质量及 proof obligations | 到达同一里程碑或终态的端到端墙钟、CPU、RSS 与阶段迁移 |

Soundness、scope identity 和 lowering 不越权单列硬闸，不参与收益兑换。

## 3. Lex 终点对象

固定网格和准入规则下，准入矩形宇宙为

\[
\mathcal R=\{(x,y,w,h)\in\mathbb Z^4:\;x,y\ge0,\;x+w\le W,\;y+h\le H,\;w,h\ge6\}.
\]

每个坐标矩形是独立对象。得分为

\[
s(R)=(wh,\min(w,h)),
\]

先比较面积，再比较最短边。

每个矩形在同一 `problemHash/objectiveHash/contextHash` 下只有三种证明状态：

- `WITNESSED`；
- `PROVED_EXCLUDED`；
- `UNKNOWN`。

固定布局中的 binding family 被排除，不等于矩形被 `PROVED_EXCLUDED`。

下界：

\[
L_t=\max_{lex}\{s(R):R\text{ 有当前有效 witness}\}.
\]

没有 witness 时记 `L_t=ABSENT`，不得制造数值 sentinel。

外包围最高得分：

\[
U_t=\max_{lex}\{s(R):R\text{ 尚未被 sound 地排除}\}.
\]

当 `L_t` 存在时：

\[
M_t=|\{R:s(R)\succ L_t,\;R\text{ 尚未被排除}\}|.
\]

同时报告：

- `G_t`：仍未完全关闭、且 lex 优于 `L_t` 的 score-band 数；
- `B_t`：最高未关闭 score band `U_t` 中尚未排除的矩形数；
- `H_t(a,m)`：最高若干 score band 的矩形计数直方图。

当 `L_t=ABSENT` 时，`M_t` 记 `N_A_NOT_READY`；如需总未决质量，另名为 `M_bottom_t`，不得混名。

## 4. 残余搜索 envelope

真实联合可行解数通常不可廉价精确计算。本协议只允许带证据类型的 envelope：

- `EXACT_CARDINALITY`；
- `BOX_UPPER_BOUND`；
- `MODEL_SIZE`；
- `OBSERVED_TRACE`。

快照点固定为：

- `S0`：输入准入后、master 建模前；
- `S1`：master 静态传播后、搜索前；
- `S2`：固定布局后、binding build 完成、首次 solve 前；
- `S3`：一份 binding selection 交给 routing precheck 前；
- `S4`：routing build 完成、solve 前；
- `S5`：终态或 terminal verifier。

W0 金丝雀必须报告：

- `S2.target_slot_domain_cardinality`；
- `S2.target_slot_active_value_count`；
- `S2.generic_output_domain_cardinality_sum`；
- `S2.generic_output_box_bits = sum(log2(domain_size))`；
- `S3.binding_proposals`、`routing_prechecks`、`point_nogoods` 与 literal 总数；
- `S4` 若未到达则写 `NOT_REACHED`，不得写零成本；
- `S5.terminal_status` 与 `censor_status`。

## 5. 资源向量与热点迁移

每臂记录：

```text
wall_seconds
cpu_seconds
peak_rss_bytes
binding_build_seconds
binding_solve_seconds
binding_solve_calls
binding_proposals
routing_precheck_seconds
routing_prechecks
routing_build_seconds
routing_solve_seconds
routing_solves
checker_seconds
terminal_status
censor_status
```

周期性 progress 是下界；精确事件数只认 append-only journal 的完整落盘行，两种口径不得相加。

热点迁移本身不是失败。失败条件是：迁移未被记录，或终点语义没有更强收益时，端到端资源出现超出预冻容差的回归。

## 6. Evaluator 灵敏度门

任何真实运行中的“零”在被消费前，endpoint evaluator 必须通过纯合成 fixture 的三类控制：

### 正控制

1. 加入更高面积 witness，`L` 上升；
2. 加入同面积、更高 `min_side` witness，`L` 按第二关键字上升；
3. 排除最高 band 的非最后一个矩形，`B` 减一但 `U` 不动；
4. 排除最高 band 的最后一个矩形，`U` 降到下一 band且 `G` 减一；
5. 删除一个一元 binding 域值，S2 envelope 按冻结公式变化。

### 负控制

1. 排除不优于 `L` 的矩形，`M/G/U` 不变；
2. 重复登记同一 witness 或 exclusion，结果幂等；
3. W0-local binding theorem 不写 rectangle-level exclusion 时，终点账户保持 `ZERO_BY_SCOPE`。

### Stale 控制

1. `contextHash`、premise fingerprint 或 evaluator input identity 不匹配时 fail-closed；
2. `L=ABSENT` 时不得输出普通 `M_t`；
3. 未到达 routing build 时必须输出 `NOT_REACHED`。

灵敏度测试只证明 evaluator 接线和基本语义正确，不证明账本覆盖了所有潜在成本维度。未覆盖维度必须在报告中显式列债。

## 7. 冻结与换代

v1 冻结以下内容：公式、空值类型、snapshot 点、资源字段、聚合方式、容差来源与判词分类。后续新增指标只允许：

- 新建 v2；
- 保留 v1 历史判词；
- 能回算则作为旁注补算；
- 不能回算则写 `UNAVAILABLE_FOR_V1_RUN`。

禁止在看见结果后改主指标、权重、空值语义或 pass/fail 门槛。

## 8. 判词分类

| 终点语义 | 端到端资源 | 判词 |
|---|---|---|
| 不变 | 下降 | `ENDPOINT_NEUTRAL_COMPUTE_GAIN` |
| 不变 | 容差内不变 | `ENDPOINT_NEUTRAL_INFRASTRUCTURE` |
| 不变 | 显著上升 | `LOCAL_GAIN_COST_REGRESSION` |
| 改善 | 不上升 | `ENDPOINT_PROGRESS` |
| 改善 | 上升 | `PROGRESS_WITH_PRICE`，交 owner 裁量 |
| 不可比或删失 | — | `INCONCLUSIVE` |

四格账不压成加权总分；不同货币之间不允许自动兑换。
