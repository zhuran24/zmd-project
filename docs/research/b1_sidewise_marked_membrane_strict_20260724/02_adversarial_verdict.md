# `SMM-209` 对抗判读

| 项目 | 当前终态 |
|---|---|
| 文档性质 | 数学与翻译层对抗 verdict |
| 证据截止 | `2026-07-24` |
| 几何判决 | **PASS — ADMITTED_FOR_PB_ENCODER** |
| 正式 authority 判决 | **FORMAL_AUTHORITY_INCOMPLETE** |
| authority run | `run-20260723T161302Z-SMM2` |
| 账本 | `U=(1188,22)`，`L=absent` |

## 判读范围

本 verdict 审查 `SMM-209` 是否为 strict instance 的必要条件，以及它是否被
完整、透明地翻译成排除 `(22,54)` 与 `(54,22)` 的 PB。它不把内部 solver
结果提升成缺少终态资源 authority 的全局上界。

## 数学对抗结果

以下攻击面均已关闭：

1. **实体而非 face 计数。** protocol core 的两个对侧三口 face 只贡献一个
   entity-max `r=3`；manufacturing input/output faces 也按同一实体取最大值。
2. **partial contact 重用。** 四条有向矩形边共有八个 endpoints；body
   nonoverlap 使一个 endpoint 至多对应一个 partial-contact entity，同一
   axis-aligned solid body 不能接触 body-free `R` 的两条不同边。
3. **top-eight 完整性。** strict census 精确得到
   `[3,3,3,3,2,2,2,1]`，和为 `19`；可选 storage box 与 final inputs 不会
   增大 marked budget。
4. **ordinary/marked 双计数。** 使用
   `T_in<=124` 与 `M_in<=85`，外部 weighted incidences 为 `529`；本层没有
   把 110 marks 误当成新的 ordinary terminals。
5. **local cap 与取整。** 从 `t(z)+m(z)<=4` 得
   `ceil(529/4)=133`，不是向下取整。
6. **orientation 与 tie-break。** 完整枚举 `6<=w,h<=70`；
   `lex>(1188,18)` 相对旧 band 的差集恰为两个有向尺寸，没有漏掉
   area `1188` 的 tie-break。

primary 与 independent a002 对所有上述数值一致。对 independent 的
top-eight、combined cap、operation/entity join、band delta 或 strict input
作联合突变时，verdict builder 失败关闭。

## 历史 a001

`geometry-authority-a001` 与 `recomputations-a001/primary.json` 是不可变历史。
independent v1 对 47 个 `generic_io` required instances 使用了错误的
operation-group membership 假设，报
`flat operation-instance join mismatch`。因此 a001 没有通过双复算，也没有
形成 admission。a002 没有覆盖这些字节；它在新 authority 中同时固定 v1、
v2 与 strict input，并由 v2 独立重建 schema 分区。

## Translation verdict

`translation-a001/translation_gate.json` 逐项通过：

- strict entity census 与 `SMM-209` 独立重推；
- old band `2084`、candidate band `2086` 与 exact delta 独立枚举；
- exactly-one OPB header、变量语义与 constraint multiset 精确匹配；
- build manifest reseal、geometry admission 与 PB authority 重放；
- formula/proof 工具身份及单实例资源 preflight 闭合。

这允许执行一次正式 attempt；它不预先授权上界更新。

## 最终 admission

唯一正式 attempt 内部证明结果为 `VERIFIED UNSATISFIABLE`。外层 terminal
observer 在 unit 卸载后只能读到 resource properties 的默认值，不能把
终态与启动时的 `35/39/16 GiB` 合同连接起来。按预注册 fail-closed 规则：

```text
geometry admission = PASS
translation admission = PASS
internal proof verification = PASS
terminal resource authority = FAIL
final decision = FORMAL_AUTHORITY_INCOMPLETE
upper_bound_update_authorized = false
```

所以本轮允许保留几何条件和内部 proof 作为研究证据，但不允许把账本更新为
`U=(1188,18)`，也不允许宣称 witness、attainability、optimality、全局
infeasibility 或 production `CERTIFIED`。
