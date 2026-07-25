# `22×54` entity-max marked-membrane 必要性证明

| 项目 | 终态 |
|---|---|
| 文档性质 | 研究级纸面必要性证明 |
| 证据截止 | `2026-07-24` |
| 本层状态 | **PAPER_NECESSITY_PASS** |
| 适用几何 | body-cell-empty `22×54` rectangle |
| 上游账本 | `U=(1188,22)`，`L=absent` |

本文只证明一条待机器复算和对抗准入的必要条件。纸面证明本身不改变上界，
不建立 witness、attainability、optimality、全局不可行性或 production
`CERTIFIED` 结论。

## 1. 记号与上游引理

令 `R` 为 body-cell-empty 的 `22×54` 轴对齐矩形，`S=22+54=76`。
`T_in` 是 628 个 active terminal incidences 中 access cell 位于 `R` 的数量；
`M_in` 是 110 个 marked incidences 中 access cell 位于 `R` 的数量。

已准入的 R4/B1 几何链给出：

```text
T_in <= S+48 = 124.
```

它还给出 110 个 marks 的定义：

- 每个 manufacturing input/output face 标记
  `max(0, active_count-2)` 个必然 active 的 noncorner incidences，共 58 个；
- 46 个 boundary raw outputs 与 protocol core 的六个 raw outputs 是 52 个
  raw-provider slots 的全集，且全部为 noncorner，exact binding 使它们全
  active；
- 两个 final inputs 不属于 marked 集。

## 2. Full contact

对一个 port-bearing face，令其实体边长为 `s`，该 face 上的 marks 数为 `r`。
strict 模板逐 face 满足 `2r<=s`。

若实体边完整接触 `R` 的一条边，则接触区间长度为 `s`，暴露的 marks 至多
`r`，因此 full contact 对

```text
2 * exposed_marks <= contact_length
```

成立。同一 `R` 边上的 contact intervals 因 body nonoverlap 两两不交，
所以全部 full contacts 的 contact length 总和不超过
`perimeter(R)=2S=152`。

## 3. Partial contact 与 entity-max 预算

partial contact 的实体边跨过某一条有向矩形边的端点。令实际 overlap 长度为
`ell`，暴露 marks 数为 `e`。显然

```text
e <= ell
e <= r
```

相加得到：

```text
2e <= ell+r.                                (1)
```

一条矩形边有两个端点，四条边合计八个 directed endpoints。同一端点若有两个
partial contacts，两块实心 body 都会占用端点外侧的同一条法向 body cell，
违反不重叠，所以每个 directed endpoint 至多一个 partial contact。

同一实心轴对齐 facility 也不可能接触 body-free `R` 的两条不同边：若它同时
接触两条相邻边，它的矩形 hull 包含对应的 `R` 角 body cell；若接触两条对边，
body 的投影跨过 `R` 内部。两者都与 `R` body-cell-empty 矛盾。因此八个
partial contacts 的 `r` 必须来自至多八个不同实体。

## 4. Strict entity census

对每个实体，取其所有可接触 marked faces 的 `r` 最大值；manufacturing 的
input/output faces 仍属于同一个实体。protocol core 的两个对侧三口 raw
output faces 也属于同一个 `9×9` 实体，不能展开成两个实体。

strict census 为：

| entity-max `r` | 实体数 | 来源 |
|---:|---:|---|
| 3 | 4 | 3 个 `packaging_battery` + 唯一 protocol core |
| 2 | 3 | 3 个 `filling_capsule` |
| 1 | 89 | 43 个 manufacturing + 46 个 boundary raw bodies |
| 0 | 170 | 其余 manufacturing |

可选 storage box 和两个 final-input incidences 的 marked contribution 为零，
不会增大此预算。八个不同实体的最大 `r` 之和因此是：

```text
3+3+3+3+2+2+2+1 = 19.                      (2)
```

把 full contacts 的半密度账与每个 partial contact 的式 (1) 相加，再用式
(2)：

```text
2*M_in <= perimeter(R)+19
           = 152+19
           = 171,
M_in <= floor(171/2) = 85 = S+9.           (3)
```

这个 `19` 是完整的 top-eight entity-max endpoint budget，不是只把旧账里的
core face 数量减一。

## 5. `SMM-209` 与 ceiling 排除

由上游 ordinary membrane 和式 (3)：

```text
T_in + M_in <= 124+85 = 209.               (SMM-209)
```

矩形外的 weighted incidences 至少：

```text
(628-T_in)+(110-M_in) >= 738-209 = 529.
```

已准入的 local access-cell lemma 为每个外部 access cell
`t(z)+m(z)<=4`，故外部 access cells 至少：

```text
ceil(529/4) = 133.
```

required bodies 与至少九根电线杆已在 `R` 外占用 3580 格，因此 `R` 与外部
access cells 合计最多可用 `4900-3580=1320` 格。但：

```text
22*54 + 133 = 1321 > 1320.
```

矛盾排除 normalized `22×54`，也排除 oriented `22×54` 与 `54×22`。

## 6. Band composition 与 claim 边界

旧机器验证 authority 已排除完整 `lex>(1188,22)` band。对
`6<=w,h<=70` 独立枚举，`lex>(1188,18)` 与旧 band 的差集必须恰为：

```text
{(22,54), (54,22)}.
```

因此只有在以下各层全部通过后，研究账本才可从 `(1188,22)` 更新为
`(1188,18)`：

1. 两个不互相 import 的 strict 复算精确重建 top-eight `19` 与 `SMM-209`；
2. 坐标/模式级对抗 verdict 通过；
3. geometry admission 通过；
4. 独立 PB translation gate 重建旧 band 与新 ceiling pair 的精确并集；
5. RoundingSat 产出 UNSAT proof，且 VeriPB 3.0.2 返回唯一
   `s VERIFIED UNSATISFIABLE`。

失败、UNKNOWN、超时、资源越界、proof cap 或任一身份漂移都保持
`U=(1188,22)`、`L=absent`。
