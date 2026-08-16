# 实验一第一号对象：W0 ghost-front 离线短证书

> **状态：** `COMPLETE_RESEARCH_ONLY`
> **日期：** 2026-08-15
> **对象：** 固定 `W0-ALIGNMENT` 布局、固定 candidate pool、固定 canonical 规则和固定 6×7 strict-empty 矩形；只对 binding selection 量化。
> **边界：** 本目录不接入求解器，不包含 lowering，不触碰 D3/D4、认证面或发布面。

## 五件套坐标

| 要件 | 坐标 | 内容 |
|---|---|---|
| 1. 范围 | [`01_JUDGMENT.json`](01_JUDGMENT.json)、[`02_PROOF.md`](02_PROOF.md#1-judgment-范围) | `problemHash`、`objectiveHash`、`contextHash`、固定文件字节与 binding-only binder |
| 2. 条件／触发器 | [`01_JUDGMENT.json`](01_JUDGMENT.json)、[`02_PROOF.md`](02_PROOF.md#2-便宜触发器) | `boundary_port_041` 的唯一输出 slot 成为活动 source terminal；一次 membership lookup |
| 3. 结论 | [`01_JUDGMENT.json`](01_JUDGMENT.json)、[`02_PROOF.md`](02_PROOF.md#3-结论) | 所有满足触发器的 binding selection 都不存在 canonical predicate 5 routing witness |
| 4. 证明 | [`02_PROOF.md`](02_PROOF.md) | 从 canonical 规则、candidate pool、固定布局与矩形字节重导的一格必占／禁占反证 |
| 5. 独立 checker | [`03_check_w0_ghost_front_certificate.py`](03_check_w0_ghost_front_certificate.py) | 标准库单文件，不 import harness、solver、binding/routing 模型或其他项目代码 |

## 冻结验收与自测

- [`00_ACCEPTANCE_CRITERIA_FROZEN.md`](00_ACCEPTANCE_CRITERIA_FROZEN.md)：证明动笔前提交的盲态验收判据；
- [`04_COVERAGE_SNAPSHOT.json`](04_COVERAGE_SNAPSHOT.json)：v2 deep W0 journal 前 1007 条的冻结观测身份，只用于事后测量 \(|\operatorname{Ext}(J)|\)；
- [`05_CHECK_RECEIPT.json`](05_CHECK_RECEIPT.json)：独立 checker PASS 与七次成本基准；
- [`06_SELF_ASSESSMENT.md`](06_SELF_ASSESSMENT.md)：按冻结“看到什么才算数／什么不算”逐条判读。

## 定理核

固定 candidate pool 与布局给出：

```text
boundary_port_041 unique output front = (1,53)
fixed strict-empty rectangle = [1,6] × [51,57]
```

若一个 binding selection 激活该 source terminal，canonical front identity 要求在 \((1,53)\) 使用 belt terminal；strict-empty 规则又禁止任何 belt 或物流部件进入同一格。因此该 binding selection 不可路由。

观测中同样存在 `boundary_port_042 → (1,56)` 的冗余矛盾，但主证书刻意只保留一个活动端口原子。

## 复算

完整证明与覆盖复算：

```bash
.venv/bin/python docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/03_check_w0_ghost_front_certificate.py --coverage required
```

只复算数学证书，不读取 Phase -1 journal：

```bash
.venv/bin/python docs/research/solver_reasoning_outer_loop_reviews_20260815/experiment_one_w0_ghost_front_offline_certificate_20260815/03_check_w0_ghost_front_certificate.py --coverage off
```

checker 要求本机保留 Judgment 中钉死的两份 W0 local-optional 输入，以及 `--coverage required` 模式下的 v2 journal 前缀。缺失时 fail-closed；不会改用 harness 重新生成或猜测输入。

## 判词

- 短语义证明存在性：**固定 W0 上局部阳性**；
- 冻结观测覆盖：**1007/1007** 个不同 binding selection；
- 独立 checker：**PASS**，证明加覆盖七次新进程外部墙钟中位数 **0.643410 s**；
- 真实系统消费、lowering、holdout 家族性、低余量梯度与全局 lex 影响：**全部未测试**。

因此本目录把经验高频障碍推进成了一个窄范围条件式定理，但不把第一层局部阳性升级为推理外环整体有效。
