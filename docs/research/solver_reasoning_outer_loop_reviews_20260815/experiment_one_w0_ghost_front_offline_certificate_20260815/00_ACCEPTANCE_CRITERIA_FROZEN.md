# 实验一：W0 障碍离线短证书验收判据冻结

> **冻结状态：** `FROZEN_BEFORE_CERTIFICATE_CONSTRUCTION`
> **冻结日期：** 2026-08-15（America/Los_Angeles）
> **来源：** [`round4_blind_observability_experiment_sequence_and_binding_routing_wall_review.md`](../round4_blind_observability_experiment_sequence_and_binding_routing_wall_review.md)，该推导在 Phase -1 实测数据对评审席揭盲之前产出。
> **适用范围：** 本目录的实验一第一号对象。下列“测什么／看到什么才算数／什么不算”正文逐字取自第四轮盲推导；任何实验结果不得反向修改本文件。

## 测什么

对一个已经确认不可行或具有强制结构的子问题，寻找一个独立可验的语义证书 \(J\)。

测量：

- \(J\) 使用多少个原始事实、系数和中间概念；
- 检查 \(J\) 需要多少成本；
- \(J\) 覆盖多少个具体 assignment、binding 或矩形；
- 被覆盖对象是否位于当前 lex 前沿附近；
- 相比逐个判断这些对象，证书短了多少。

可以粗略定义语义压缩率：

\[
C(J)=
\frac{\log |\operatorname{Ext}(J)|}
{\operatorname{Size}(J)},
\]

其中 \(\operatorname{Ext}(J)\) 是这条判断能够同时解释、排除或构造的具体状态集合。

真正重要的不是公式本身，而是“一个短对象代表多少具体组合”。

## 看到什么才算数

以下现象算数：

- 一个几十行以内、或少量算术关系组成的证明，覆盖了大量具体状态；
- 证书不包含每个被覆盖案例的 ID、hash 或完整 assignment；
- 证书可以由小型 checker 独立复算；
- 检查一次证书，比逐点解决其中任意几个高成本案例都便宜；
- 它作用于困难区域，尤其是低余量、near-frontier 区域，而不只是显然很差的矩形。

这一层允许发现过程非常昂贵。哪怕先花了很久才发现一条短证明，它仍然证明了“短证明存在”。

但它只证明数学压缩性存在，不证明架构在经济上有用。

## 什么不算

- 把一万个失败 assignment 列成一万个 nogood；
- 用完整布局 hash 做黑名单；
- 把求解器最终搜索轨迹重新包装成“证明”；
- 只覆盖一个具体案例，而且没有任何参数化；
- 排除了很多候选，但这些候选全部远低于当前 lex 前沿。

这种东西可以短路程序，但没有证明存在语义压缩。
