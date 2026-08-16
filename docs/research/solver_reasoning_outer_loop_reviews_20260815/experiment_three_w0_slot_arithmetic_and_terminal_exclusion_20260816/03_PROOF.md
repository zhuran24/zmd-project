# W0 generic-output 席位算术引理

> **Judgment：** `J-W0-GENERIC-OUTPUT-SLOT-SATURATION-041-V1`
> **结论状态：** `PROVED_IN_PINNED_BINDING_CONTEXT`
> **效力：** research-only、evidence-only；不产生 production lowering、认证、exact-status、stable claim 或发布效力。
> **机器陈述：** [`02_JUDGMENT.json`](02_JUDGMENT.json)
> **独立复算器：** [`04_check_w0_slot_arithmetic.py`](04_check_w0_slot_arithmetic.py)

## 1. 范围

本证明只讨论 [`01_CONTEXT_MANIFEST.json`](01_CONTEXT_MANIFEST.json) 钉死的 W0 binding context：

- 固定布局 `W0-ALIGNMENT`；
- 固定 canonical rules、candidate pool、266 个 mandatory exact instances、generic I/O 与布局字节；
- 52 个命名 generic-output 席位；
- 每个席位的标签域为 `{blue_iron_ore, source_ore, __unused__}`；
- 每席恰好选择一个标签；
- 全局精确计数为 `blue_iron_ore=34`、`source_ore=18`。

只对满足该 binding contract 的绑定方案 `b` 量化。定理描述的是当前钉死模型契约中的必要性质，不声称该契约等于所有 adjudicated-game 合法绑定。

本证明不读取 solver 轨迹，不使用 C 臂 timeout，不使用 A/B selection 顺序，也不把 1007 条观测当作前提。观测只在证明完成后用于覆盖对拍。

## 2. 条件

定义 `LegalW0Binding(b)`：

1. 对每个席位 `s`，存在三个 0/1 指示量

   \[
   blue_s,\ source_s,\ unused_s\in\{0,1\},
   \]

   且

   \[
   blue_s+source_s+unused_s=1;
   \]

2. 全局满足

   \[
   \sum_s blue_s=34,
   \qquad
   \sum_s source_s=18.
   \]

目标席位记为

```text
s_041 = boundary_port_041:out:0
```

`Active_041(b)` 当且仅当 `unused_{s_041}=0`。

## 3. 结论

在钉死上下文中：

\[
\forall b,
LegalW0Binding(b)
\Longrightarrow
Active_{041}(b).
\]

等价地，`boundary_port_041:out:0` 在任何合法 W0 binding 中都不能取 `__unused__`；它必须绑定 `blue_iron_ore` 或 `source_ore`。

## 4. 两条独立计数链

### 4.1 席位侧：46 + 6 = 52

独立复算从固定布局的 `solution` 字段开始，以 mandatory instance metadata 决定 operation type，再以 candidate pool 中所选 pose 的 `output_port_cells` 落出物理席位。

固定布局包含：

- `boundary_port_001` 至 `boundary_port_046`，共 46 个 `boundary_io` 实例；
- `protocol_core_001`，共 1 个 `protocol_core` 实例。

46 个 boundary port 的所选 pose 各有且仅有 1 个 output port，因此贡献

\[
46\times1=46
\]

个席位。

`protocol_core_001` 的所选 pose 有且仅有 6 个 output ports，因此贡献 6 个席位。

故席位全集大小为

\[
|S|=46+6=52.
\]

复算得到的 ID 必须精确等于：

- `boundary_port_001:out:0` 至 `boundary_port_046:out:0`；
- `protocol_core_001:out:0` 至 `protocol_core_001:out:5`。

目标 `boundary_port_041:out:0` 属于该全集。

### 4.2 需求侧：34 + 18 = 52

Pinned canonical `commodity_metadata` 把且只把以下两种 commodity 标成 `external_boundary`：

```text
blue_iron_ore
source_ore
```

对全部 266 个 mandatory exact instances 按 `operation_type` 计数：

- `refinery_blue_iron` 有 34 台；
- `crusher_source` 有 18 台。

Pinned canonical recipes 给出：

```text
refinery_blue_iron.inputs.blue_iron_ore = 1
crusher_source.inputs.source_ore = 1
```

因此由 mandatory instances 与 canonical recipes 独立重导的 external-boundary 需求是：

\[
D_{blue}=34\times1=34,
\qquad
D_{source}=18\times1=18.
\]

该重导值还必须与 pinned `generic_io_requirements.json` 的 `required_generic_outputs` 逐项相等。于是：

\[
D_{blue}+D_{source}=34+18=52=|S|.
\]

这条闭式等式不是实验结果，也不依赖 solver 是否能在预算内给出终态。

## 5. 证明

任取一个满足 `LegalW0Binding(b)` 的绑定方案 `b`。

1. 对 52 个席位的 per-slot ExactlyOne 等式求和：

   \[
   \sum_s blue_s+
   \sum_s source_s+
   \sum_s unused_s=52.
   \]

2. 代入全局精确计数：

   \[
   34+18+\sum_s unused_s=52.
   \]

3. 化简得：

   \[
   \sum_s unused_s=0.
   \]

4. 每个 `unused_s` 都是非负 0/1 量；非负数之和为 0，故对所有席位都有

   \[
   unused_s=0.
   \]

5. 特别地，目标席位满足

   \[
   unused_{s_{041}}=0,
   \]

   因而 `Active_041(b)`。

证毕。

## 6. 为什么这不是搜索偏好

A 臂曾观测到许多不同 selection 都让 041 活动，但有限样本本身只能说明“被看到的 selection 都如此”。本证明的量词来自 52/34/18 的闭式算术：只要一个绑定满足声明的合法性条件，就必然没有任何 unused 席位。

因此，“041 总是活动”不是 CP-SAT 的分支顺序、`SELECT_MAX_VALUE`、随机种子或 1007 个样本共同造成的经验规律，而是固定 binding contract 的逻辑后果。

## 7. 事后覆盖边界

冻结的 1007 条 W0 event prefix 可用于复核：

- 记录数为 1007；
- selection digest 互异数为 1007；
- 每条记录都出现一个非空 commodity 的 `boundary_port_041` 活动 source；
- 覆盖率为 1007/1007。

该覆盖可关闭而核心 checker 仍 PASS。它不参与 §5 的任何一步，也不能替代“所有合法绑定”的全称证明。

## 8. 消费契约

本定理当前只允许：

1. 与实验一的条件式不可路由定理做离线组合；
2. 为固定 W0 布局、固定矩形建立研究面候选排除；
3. 作为后续 owner 审查的 proof object。

本定理当前不允许：

- 写入 production solver 或 certified cut；
- 修改 exact status、stable claim ledger、supervisor 或 publisher；
- 外推其他布局、矩形或规则版本；
- 把 current-model 的单 commodity slot contract 冒充完整游戏语义；
- 直接声称全局 lex 上界、下界或最优性变化。

若任一承重输入、席位构造、ExactlyOne 契约、全局需求计数或目标 slot grounding 变化，本 Judgment 立即 stale，必须重新证明。
