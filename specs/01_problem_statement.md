---
status: CURRENT_CODE_ALIGNED
source_of_truth: code-first; objective and admissibility must match src/search/outer_search.py and src/search/exact_campaign.py
last_verified_against: 2026-03-24
owner: exact-search
---

# 01 问题陈述

## 1. 项目目标

项目在 `70 x 70` 网格上联合求解设施摆放、供电覆盖、端口绑定和双层路由，目标是在所有硬约束满足的前提下，找到**最大的合法连续空矩形**。

`certified_exact` 与 `exploratory` 必须严格隔离：

- `certified_exact` 只允许使用 exact-safe 输入、exact-safe cuts 和可审计证据链。
- `exploratory` 允许使用试探、调参与兼容路径，但其结果不得冒充正式认证证据。

## 2. 严格精确目标

当前仓库的严格精确目标真源固定为：

$$
\max_{\text{lex}} (\text{area}, \text{min\_side})
$$

其中：

- `area = w * h`
- `min_side = min(w, h)`

这意味着：

- 先最大化面积。
- 面积相同的情况下，再最大化短边。

因此：

- `4x3` 必须优于 `6x2`
- `20x20` 必须优于 `40x10`

以下内容都**不是** `certified_exact` 的目标真源：

- `Phi(w, h)` 饱和打分
- `(area, width, height)` 作为正式 tie-break
- 任意经验型长宽比启发式

## 3. 候选域可接受性规则

当前代码与测试仍保留以下**硬 admissibility rule**：

$$
\min(w, h) \ge 6
$$

它的含义是：

- 候选空矩形短边小于 6 时，直接不进入严格精确候选域。
- 这是候选域过滤规则，不是 lexicographic objective 的一部分。

## 4. 严格精确约束边界

空矩形本身只要求：

- 存在
- 连续
- 与设施不重叠

它**不要求**：

- 接触地图边界
- 与外部存在连通路径

也就是说，完全被包围的合法空矩形依然是允许的。

## 5. 关于可选设施数量的口径

`power_pole = 50` 与 `protocol_storage_box = 10` 这类数字如果被提及，只能视为 `exploratory` 的历史/兼容性提示；它们**不是** `certified_exact` 的硬上界。

## 6. 当前文档边界

本文件当前只锁定：

- 项目目标
- 严格精确 objective
- 候选域 admissibility 规则
- empty rectangle 的几何合法性边界
- exact / exploratory 分离边界

运行时 orchestration、campaign、artifact 和输出契约，分别以下列文件为准：

- `specs/11_pipeline_orchestration.md`
- `PROJECT_LOCK.md`
- `FILE_STATUS.md`
