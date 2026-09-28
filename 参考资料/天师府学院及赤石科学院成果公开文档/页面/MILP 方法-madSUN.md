# MILP 方法-madSUN

> 原文：https://docs.qq.com/aio/DTmluZ1diWlpQZldw?p=7BCvIqLlLXp7eVi672wpKy　上级：[理想系统的流量理论](理想系统的流量理论.md)

为了增加可读性，本文档的描述相较于实际的 MILP 约束略有简化（例如对分支进行的 Big-M 线性化都予以省略）。

## 变量

对每条边 $e = (u, v) \in E$：

- $v_e \in [0, 1]$ 流量（<code>v</code>）

- $v_e^{H,\text{in}} \in [0, 1]$ 入口处高流量状态的流量（<code>v\_H\_in</code>）

- $v_e^{L,\text{in}} \in [0, 1]$ 入口处低流量状态的流量（<code>v\_L\_in</code>）

- $v_e^{H,\text{out}} \in [0, 1]$ 出口处高流量状态的流量（<code>v\_H\_out</code>）

- $v_e^{L,\text{out}} \in [0, 1]$ 出口处低流量状态的流量（<code>v\_L\_out</code>）

- $f_e \in \{0, 1\}$ 是否满（<code>is\_full</code>）

- $b_e \in \{0, 1\}$ 是否阻塞（<code>is\_blocked</code>）

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
v_e &=
\begin{cases}
v_e^{H,\text{in}} & \text{if } b_e = 0 \\
v_e^{L,\text{in}} & \text{else}
\end{cases} \\
&=
\begin{cases}
v_e^{H,\text{out}} & \text{if } b_e = 1 \\
v_e^{L,\text{out}} & \text{else}
\end{cases} 
\end{aligned}
$$

且

$$
v_e^{H,\text{in}} \ge v_e^{L,\text{in}}, \quad v_e^{H,\text{out}} \ge v_e^{L,\text{out}}
$$

直观理解为：

1. 分叉节点<b>阻塞的下游的流量</b>比<b>流通的下游的流量</b>低

2. 汇聚节点<b>流通的上游的流量</b>比<b>阻塞的上游的流量</b>低

### 满状态

$$
f_e = 1 \implies v_e = v_e^{H,\text{in}} = v_e^{L,\text{in}} = v_e^{H,\text{out}} = v_e^{L,\text{out}} = 1
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

- 源出边：

$$
b_e = 1, \ \forall e \in \delta^+(\text{In})
$$

- 汇入边：

$$
b_e = 0, \ \forall e \in \delta^-(\text{Out})
$$

符合阻塞限流的基本情况。

### 阻塞传播

<b>分叉节点 </b><b>$u$</b><b>（唯一入边 </b><b>$e^*(u)$</b><b>，出边集 </b><b>$O(u) = \delta^+(u)$</b><b>）：</b>

$$
\begin{aligned} 
b_{e^*(u)} &\le b_e + f_{e^*(u)}, \quad \forall e \in O(u) \\
\sum_{e \in O(u)} b_e &\le |O(u)| - 1 + b_{e^*(u)} - f_{e^*(u)}
\end{aligned}
$$

<b>汇聚节点 </b><b>$u$</b><b>（唯一出边 </b><b>$e^*(u)$</b><b>，入边集 </b><b>$I(u) = \delta^-(u)$</b><b>）：</b>

$$
\begin{aligned}
b_e &\le b_{e^*(u)} + f_{e^*(u)}, \quad \forall e \in I(u) \\
b_{e^*(u)} &\le \sum_{e \in I(u)} b_e + f_{e^*(u)}
\end{aligned}
$$

直观理解为：

1. 分叉节点入边阻塞，则存在阻塞出边（入边满时失效）

2. 分叉节点出边全阻塞，则入边阻塞（入边满时失效）

3. 汇聚节点存在阻塞入边，则出边阻塞（出边满时失效）

4. 汇聚节点出边阻塞，则存在阻塞入边（出边满时失效）

## 目标函数

没有设置目标函数，只是寻找可行解，即目标函数为：

$$
\max{0}
$$
