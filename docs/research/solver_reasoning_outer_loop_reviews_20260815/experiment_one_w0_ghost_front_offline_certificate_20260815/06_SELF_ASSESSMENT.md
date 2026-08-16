# 实验一第一号对象自测：W0 活动边界源口与 strict-empty 矩形冲突

> **判读日期：** 2026-08-15
> **验收基准：** [`00_ACCEPTANCE_CRITERIA_FROZEN.md`](00_ACCEPTANCE_CRITERIA_FROZEN.md)
> **判读上限：** 本结果只支持“固定 W0 上存在一个短、独立可验、覆盖观测 binding 家族的语义证书”。它不支持真实系统闭环、跨布局家族普遍性、低余量梯度或全局 lex 面貌变化。

## 1. 结论摘要

第一号对象得到一个条件式定理：

\[
\forall b,
\operatorname{Active}_{041}(b)
\Longrightarrow
\neg\exists r\;
\operatorname{Routable}_{P5}(W0,R,b,r).
\]

触发器只有一个原子：`boundary_port_041` 的唯一输出 slot 在绑定方案中成为活动 source terminal。

证明核心只有一个格：candidate pool 与固定布局共同给出该口唯一前格 \((1,53)\)；固定 strict-empty 矩形为 \([1,6]\times[51,57]\)，所以该格在矩形内。活动口要求该格接受 belt，而 strict-empty 规则禁止任何 belt 或物流部件进入该格，形成直接矛盾。

实验观测不进入证明。冻结的前 1007 个不同 binding selection 只在证明完成后用于计算 \(|\operatorname{Ext}(J)|\)。

## 2. 证书大小

### 语义核心

| 量 | 数值 |
|---|---:|
| 触发器原子 | 1 |
| 从 pinned 字节与 canonical 规则重导的语义事实 | 6 |
| 反证步骤 | 5 |
| 主证书总原子口径（5 个编号步骤 + 1 个触发原子） | 6 |
| 被主证书列举的 binding digest | 0 |
| 被主证书列举的完整 assignment | 0 |

主证书只使用 `boundary_port_041`。同样被矩形覆盖的 `boundary_port_042` 是独立冗余 corollary，不计入主证书大小。

### 耐久复算包

| 文件 | 字节数 | 角色 |
|---|---:|---|
| `01_JUDGMENT.json` | 5,275 | 范围、hash、触发器、结论、proof-object 与覆盖源身份 |
| `02_PROOF.md` | 7,220 | 自包含数学证明与边界 |
| `03_check_w0_ghost_front_certificate.py` | 27,347 | 标准库独立 checker；直接计数证明正文的编号步骤并对拍覆盖源路径契约 |
| `04_COVERAGE_SNAPSHOT.json` | 2,763 | 观测覆盖前缀身份，不是证明前提 |

checker 比逻辑证书大，是因为它承担 54.5 MB candidate pool 解析、291 个固定实例的 pose 重导、3644 个 body cell 的重建、hash 校验以及可选观测前缀复验。不能把复算器源码长度当成数学证明长度。

## 3. 覆盖数 \(|\operatorname{Ext}(J)|\)

冻结测量对象是 `DEEP-W0-ALIGNMENT` 事件 journal 的前 1007 条完整记录：

- event index 为 1 至 1007；
- 1007 个 `selection_digest` 互异；
- 前缀 SHA-256 为 `e37da2d662a850529122e983c59ab569e0d48e9b9b93279af6bf41e0568d60a1`；
- 每条记录恰有一个 `boundary_port_041` 活动 source 记录，前格均为 \((1,53)\)；
- 因而观测覆盖为

\[
|\operatorname{Ext}(J)|=1007,
\qquad
\frac{|\operatorname{Ext}(J)|}{1007}=100\%.
\]

这只是对冻结观测前缀的覆盖。它不证明 W0 数学上所有可能的 binding selection 都满足触发器。

冗余 sibling `boundary_port_042` 也覆盖 1007/1007，但主证明不依赖它。

## 4. checker 成本

复算命令：

```bash
.venv/bin/python docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/03_check_w0_ghost_front_certificate.py --coverage required
```

checker 只使用 Python 标准库，不 import：

- Phase -1 harness；
- binding 或 routing 模型；
- solver；
- 项目运行代码。

七次新进程复算结果：

| 模式 | 外部墙钟中位数 | 最大值 |
|---|---:|---:|
| 证明复算，不读观测 journal | 0.622488 s | 0.624747 s |
| 证明复算并核对 1007 条覆盖 | 0.646711 s | 0.650226 s |

全量复算中位数约为 180 秒 v1 watchdog 窗口的 0.359%，成本尺度相差约 278.3 倍。两者任务不同，所以这只是 checker 廉价性的尺度比较，不是 solver A/B 加速结论。

单次 `--coverage required` PASS 中，约 0.513 秒用于载入 candidate pool、重导固定布局并核对证明正文步数，约 0.022 秒用于覆盖 journal 前缀与路径契约复核。真正用于未来 binding 上检查触发器的操作只是一次 membership lookup，比完整离线复算器还轻得多；本实验没有对这一未来消费路径做运行时测量。

## 5. 压缩率

冻结前缀中，每个 binding selection 都获得一个 285-literal 点状 nogood：

\[
1007\times285=286{,}995
\]

个点状 literal。

主证书由 5 个编号反证步骤与 1 个触发器原子组成；6 个语义事实是这些步骤的重导输入，不另加到本项 atom 口径。用盲推导给出的粗略口径：

\[
\frac{\ln(1007)}{5}=1.382946
\]

nats／proof step；若把触发器也计入证书原子：

\[
\frac{\ln(1007)}{6}=1.152455
\]

nats／certificate atom。

另一个直观但不可当作形式复杂度的对比是：

\[
\frac{286{,}995}{6}=47{,}832.50.
\]

也就是每个语义证书原子对应约 4.78 万个既有点状 literal。两种对象的表达能力不同，所以该比值只用于显示“逐点记忆”和“家族解释”的数量级差异，不是严格 proof-complexity 定理。

## 6. 对冻结“看到什么才算数”的逐条判读

### 一个短证明覆盖大量具体状态

**通过，局部口径。** 六个重导事实被压进五步编号反证，连同一个触发原子形成 6-atom 计数口径，覆盖 1007 个不同 binding selection。证明正文较长是为了保存上下文、边界和复算说明；承重逻辑是单格必占／禁占矛盾。

### 证书不包含每个覆盖案例的 ID、hash 或完整 assignment

**通过。** Judgment 没有 1007 个 `selection_digest`，也没有 1007 份 assignment。固定布局 hash 只用于界定 problem context，不参与触发条件，也不是黑名单谓词。

### 证书可以由小型 checker 独立复算

**通过。** checker 为单文件、标准库实现；从 canonical 规则、candidate pool、固定布局与固定矩形原始字节重导结论，不调用产生观测的 harness 或 routing precheck。

### 检查证书比逐点解决多个高成本案例便宜

**通过成本尺度检查，不构成系统加速证明。** 完整证明加覆盖复算的七次中位数为 0.646711 秒；冻结窗口原本花费大量 binding 求解并逐个产生 285-literal nogood。由于没有做 lowering 或 on/off A/B，本条只证明 checker 廉价，不证明真实消费收益。

### 作用于困难、低余量或 near-frontier 区域

**未建立。** W0 确实位于观测到的深枚举墙上，但本实验没有证明它是当前 lex 前沿附近的代表，也没有比较不同 slack 层。因而不能用本证书验证低余量梯度或全局前沿价值。

## 7. 对冻结“什么不算”的逐条排除

### 把一万个失败 assignment 列成一万个 nogood

**不是。** 主证书没有列举 binding；1007 条 journal 只用于事后覆盖测量。

### 用完整布局 hash 做黑名单

**不是。** 固定布局 hash 是 Judgment 的 scope identity。触发器是可解释的结构谓词 `Active_041(b)`；换一个绑定只要满足该谓词，同一证明继续成立。

### 把求解器最终搜索轨迹重新包装成证明

**不是。** 证明只使用 canonical 文本和 pinned 输入字节。删除事件与 feedback journal 后，`--coverage off` 仍可独立证明结论。

### 只覆盖一个具体案例，而且没有任何参数化

**不是，但范围仍然很窄。** 布局和矩形固定，绑定变量被全称量化；证书覆盖满足触发器的一族 binding。它尚未参数化到其他布局或矩形。

### 排除的候选全部远低于 lex 前沿

**本实验无法判定。** 它没有把该局部 family 投影到四维矩形参数空间，也不声称推进上界或下界。因此本项不能记为通过，只能记为尚未触及。

## 8. 缩圈教训

经验摘要最初显示两个贯穿 1007 条观测的 ghost-front 签名。证明阶段删除了两类不承重条件：

1. 删除 `boundary_port_042`，因为 `boundary_port_041` 单独就足以产生矛盾；
2. 删除具体 commodity `source_ore`，因为前格冲突与商品身份无关。

最终条件圈只保留一个活动输出口原子。圈内不存在可活对象，因为条件本身与 pinned strict-empty 语义形成直接逻辑矛盾；这不是通过 1007 次失败归纳出来的统计断言。

## 9. 分层判词

| 盲推导层级 | 本实验判词 |
|---|---|
| 短语义证明的存在性 | **局部阳性**：W0 固定上下文存在 6-atom 条件式证书，观测覆盖 1007/1007 |
| 在真实系统上成立一次 | **未测试**：owner 冻结 lowering 与 D3/D4 |
| 跨案例家族普遍性 | **未测试**：没有冻结式跨布局 holdout |
| 改变全局问题面貌 | **未测试**：没有 lex 前沿投影、上界或下界变化 |

因此，本结果把 Phase -1 的“一个高频局部摘要”推进成了“一个不依赖实验数据的条件式定理”，并验证了短证书与廉价独立检查器确实存在。它仍然只是盲推导现象阶梯的第一层、固定实例内部的最窄局部阳性，不得升级成推理外环整体有效的判词。
