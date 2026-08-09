# `22×54` 分边 marked-membrane：待准入必要性证明

| 项目 | 当前值 |
|---|---|
| 文档性质 | 数学必要性草案 |
| 证据截止 | `2026-07-24` |
| 状态 | **UNADMITTED — PAUSED BEFORE STRICT RECOMPUTATION** |
| 当前账本 | `U=(1188,22)`，`L=absent` |

## 目标命题

设 `R` 是一个 `22×54` 的 body-cell-empty 矩形。`T_in` 表示 628 个 active
facility-terminal incidences 中 access cell 位于 `R` 的数量；`M_in` 表示
110 个 marked incidences 中位于 `R` 的数量。

本轮准备检验的必要命题是：

```text
T_in + M_in <= 209.                         (SMM-209)
```

该命题尚未准入。当前代码只实现合成 fixture 模型核；完整 strict contact
corpus、独立复算和坐标级对抗均未运行。

## 已建立的上游算术

已验证的 R4/B1 authority 给出：

- active terminal 总数 `628`；
- marked terminal 总数 `110`；
- 每个矩形外 access cell 满足 `t(z)+m(z)<=4`；
- required bodies 与至少九根电线杆在 `R` 外占用至少 `3580` 格；
- 可供 `R` 与矩形外 access cells 使用的总格数为 `4900-3580=1320`。

因此一旦 `(SMM-209)` 成立：

```text
T_out + M_out >= 738-209 = 529
N >= ceil(529/4) = 133
area(R)+N >= 1188+133 = 1321 > 1320.
```

矛盾排除 `22×54`。反之，`T_in+M_in=210` 只给
`ceil((738-210)/4)=132`，恰好达到 `1188+132=1320`，不能排除 ceiling。
所以 `209/210` 是本轮固定且不可放宽的判定边界。

## Control 与 treatment

control 仅表达现有两个独立聚合界：

```text
T_in <= 124
M_in <= 88
```

其 combined optimum 必须是 `212`。若 control 不能复现 212，本轮模型失真。

treatment 只增加以下相关性：

1. 四条有向边的接触容量分别为 `22,22,54,54`，不合并成周长；
2. 同一边上的 contact intervals 两两不交；
3. partial contact 必须占用对应 directed endpoint，单端点至多一个；
4. 同一实心设施至多接触 `R` 的一条边；
5. 同一 manufacturing instance 的 input/output face 是互斥备选，不是两个
   可独立使用的 body；
6. protocol core 是一个实体，它的两个对侧三口 output faces 至多选择一个
   与 `R` 接触；
7. raw-output exact binding、final-input provider 与实际端口 offset 从 strict
   instance 重建；任何安全放松都只能增加可行 contact，不能删掉真实布局。

第 6 项是当前聚合账的主要相关性缺口：ordinary membrane 的 core `+3` 与
marked membrane 的两个 `(9,3)` face 不能由互相独立的虚拟 core 同时取得。
是否足以把 optimum 从 212 压到 209，必须由完整模型回答，本文不预判结果。

## 实布局到模型的必要映射

未来 geometry admission 必须逐项证明：

- 每个真实 contact 可在相同 directed side 上生成一个 model contact；
- full/partial 的 overlap 长度、active ports 与 marked ports 不被低估；
- body nonoverlap 推出的 interval 与 endpoint 互斥没有额外偷强；
- mode、orientation、operation-group multiplicity 与 provider binding 均完整；
- boundary clipping、矩形 anchor 与 map edge 只会减少真实 contact，因此
  anchor-independent 模型确为放松；
- final-input addend 不因 provider 选择而被错误删除；
- 任一真实布局映入后得到相同的 `T_in+M_in`。

任一映射义务缺少证明或出现坐标反例，状态保持 `UNADMITTED`。

## 后续 proof 与账本边界

若几何三门最终得到 checked optimum `<=209`，后续 OPB 将编码：

```text
存在 treatment assignment 且 T_in+M_in >= 210
```

只有该公式获得 RoundingSat proof、VeriPB `VERIFIED UNSATISFIABLE`，并由
独立 composition gate 证明旧 band 加 `(22,54)/(54,22)` 恰好覆盖
`lex>(1188,18)`，研究账本才可更新为 `U=(1188,18)`。

当前没有这一 claim，也不建立 `(18,66)` attainability、witness、optimality
或 production `CERTIFIED`。
