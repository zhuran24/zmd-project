# 三态 MILP 方法-madSUN \& jnk

> 原文：https://docs.qq.com/aio/DTmluZ1diWlpQZldw?p=zYHEMI5ffFh10ksMQjNW7h　上级：[理想系统的流量理论](理想系统的流量理论.md)

本方法因为具有更高的对称想，比原先的 MILP 具有更快的求解速度，在表述上也更美观一些。

较于初版，这里利用阻塞、流通两个变量表示三种状态（正常、阻塞、满），参考以下表格：

|  |  |  |
| --- | --- | --- |
| <b>是否阻塞</b> | <b>是否流通</b> | <b>边状态</b> |
| 否 | 否 | 非法 |
| 是 | 否 | 阻塞 |
| 否 | 是 | 流通 |
| 是 | 是 | 满 |

为了增加可读性，本文档的描述相较于实际的 MILP 约束略有简化（例如对分支进行的 Big-M 线性化都予以省略）。

## 变量

对每条边 $e = (u, v) \in E$：

- $v_e \in [0, 1]$ 流量（<code>v</code>）

- $v_e^{H,\text{in}} \in [0, 1]$ 入口处高流量状态的流量（<code>v\_H\_in</code>）

- $v_e^{L,\text{in}} \in [0, 1]$ 入口处低流量状态的流量（<code>v\_L\_in</code>）

- $v_e^{H,\text{out}} \in [0, 1]$ 出口处高流量状态的流量（<code>v\_H\_out</code>）

- $v_e^{L,\text{out}} \in [0, 1]$ 出口处低流量状态的流量（<code>v\_L\_out</code>）

- $b_e \in \{0, 1\}$ 是否阻塞（<code>is\_blocked</code>）

- $\bar{b}_e \in \{0, 1\}$ 是否流通（<code>is\_unblocked</code>）

## 约束

### 流量守恒

对每个内部节点 $u$（$u \neq \text{In}$ 且 $u \neq \text{Out}$）：

$$
\sum_{e \in \delta^-(u)} v_e = \sum_{e \in \delta^+(u)} v_e
$$

### 流量状态确定

对每条边 $e$：

$$
\begin{aligned}
v_e &= v_e^{L,\text{in}} = v_e^{H,\text{out}} \quad \text{if } b_e = 1 \\
v_e &= v_e^{H,\text{in}} = v_e^{L,\text{out}} \quad \text{if } \bar{b}_e = 1 \\
\end{aligned}
$$

且

$$
v_e^{H,\text{in}} \ge v_e^{L,\text{in}}, \quad v_e^{H,\text{out}} \ge v_e^{L,\text{out}}
$$

同时要求

$$
b_e + \bar{b}_e \ge 1
$$

直观理解为：

1. 分叉节点<b>阻塞的下游的流量</b>比<b>流通的下游的流量</b>低

2. 汇聚节点<b>流通的上游的流量</b>比<b>阻塞的上游的流量</b>低

3. 一条边不能既不阻塞又不流通，但可以既阻塞也流通（即满）

### 满状态

$$
b_e = 1 \wedge \bar{b}_e = 1 \implies v_e = 1
$$

即一条边达到了流量上限。

### 均分（共享变量）

- 分叉节点 $u$ 的所有出边共享 $v^{H,\text{in}}$：

$$
v_e^{H,\text{in}} = v_{e'}^{H,\text{in}}, \quad \forall e, e' \in \delta^+(u)
$$

- 汇聚节点 $u$ 的所有入边共享 $v^{H,\text{out}}$：

$$
v_e^{H,\text{out}} = v_{e'}^{H,\text{out}}, \quad \forall e, e' \in \delta^-(u)
$$

直观理解为：分叉节点所有流通的下游流量相同，汇聚节点所有阻塞的上游流量相同。

### 边界阻塞

- 源的出边：

$$
b_e = 1, \ \forall e \in \delta^+(\text{In})
$$

- 汇的入边：

$$
\bar{b}_e = 1, \ \forall e \in \delta^-(\text{Out})
$$

符合阻塞限流的基本情况。

### 阻塞传播

<b>分叉节点 </b><b>$u$</b><b>（唯一入边 </b><b>$e^*(u)$</b><b>，出边集 </b><b>$O(u) = \delta^+(u)$</b><b>）：</b>

$$
\begin{aligned}
\bar{b}_e &\le \bar{b}_{e^*(u)}, \quad \forall e \in O(u) \\
\bar{b}_{e^*(u)} &\le \sum_{e \in O(u)} \bar{b}_e + b_{e^*(u)}
\end{aligned}
$$

<b>汇聚节点 </b><b>$u$</b><b>（唯一出边 </b><b>$e^*(u)$</b><b>，入边集 </b><b>$I(u) = \delta^-(u)$</b><b>）：</b>

$$
\begin{aligned}
b_e &\le b_{e^*(u)}, \quad \forall e \in I(u) \\
b_{e^*(u)} &\le \sum_{e \in I(u)} b_e + \bar{b}_{e^*(u)}
\end{aligned}
$$

直观理解为：

1. 分叉节点存在流通出边，当且仅当入边流通

2. 分叉节点入边阻塞，当且仅当所有出边阻塞

3. 汇聚节点存在阻塞入边，当且仅当出边阻塞

4. 汇聚节点出边流通，当且仅当所有入边流通

这里看似和旧的实现在处理满边时有所出入，然而实际上当分叉节点的入边或汇聚节点的出边满时，2. 和 4. 自动成立并失去约束，因此同旧版一样，所有规则在遇到满边时都停止传播。

## 目标函数

没有设置目标函数，只是寻找可行解，即目标函数为：

$$
\max{0}
$$
