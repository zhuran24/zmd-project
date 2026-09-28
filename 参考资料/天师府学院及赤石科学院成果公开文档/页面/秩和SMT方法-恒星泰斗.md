# 秩和SMT方法-恒星泰斗

> 原文：https://docs.qq.com/aio/DTmluZ1diWlpQZldw?p=s9nBAOnOCdeCVTBmCjljm8　上级：[理想系统的流量理论](理想系统的流量理论.md)

## 秩和SMT方法

### 恒星泰斗定义

对于边$\ e=(u,v)$，定义状态$\ \iota(e), \omega(e) : E \rightarrow \{0,1\}$。

$\ \iota(e)=1$时表示：

$$
每当u尝试向e输入物品时，e都有空间让物品输入
$$

$\ \omega(e)=1$时表示：

$$
每当v尝试向e请求物品时，e都有物品输出
$$

每条边有如下三种状态

|  |  |  |
| --- | --- | --- |
| 状态 | $\iota_e$（can\_in） | $\omega_e$（can\_out） |
| EMPTY | 1 | 0 |
| FULL | 0 | 1 |
| PARTIAL | 1 | 1 |

所以满带的集合$\ F$，称为固定边集合，定义为：

$$
F = \left\{ e | x_e = c_e \right\}
$$

#### 传播定律

传播定律定义为：

$$
e,p(v)\notin F\ \Longrightarrow\ (\iota_e\Rightarrow\iota_{p(v)}),
\qquad e\in\delta^+(v),\ v\in S,
$$

$$
e,q(v)\notin F\ \Longrightarrow\ (\omega_e\Rightarrow\omega_{q(v)}),
\qquad e\in\delta^-(v),\ v\in C.
$$

#### 局部最大定律

局部最大定律定义为：

分流器 $v$ 上的输出边，只要 $\iota_e=1$，就满足

$$
x_e\ge x_f\qquad\text{对所有 }f\in\delta^+(v)
$$

汇流器 $v$ 上的输入边，只要 $\omega_e=1$，就满足

$$
x_e\ge x_f\qquad\text{对所有 }f\in\delta^-(v)
$$

#### 仓库边的状态

对于仓库的出边，设置为FULL。对于仓库的入边，设置为EMPTY

### 实现方法

如果对每条边都赋上$\ \iota(e), \omega(e)$，由局部最大定理，我们可以得到：

对于分流器$\ v \in S$

$$
e,f \in \delta^+(v) , e \neq v , \qquad (\iota(e) = 1 且 \iota(f) = 1) \Rightarrow (x_e = x_f)
$$

对于汇流器$\ v \in C$

$$
e,f \in \delta^-(v) , e \neq v , \qquad (\omega(e) = 1 且 \omega(f) = 1) \Rightarrow (x_e = x_f)
$$

可以发现，状态$\ \iota,\omega$相当于给出了若干等式。

再加上流量守恒：

$$
\sum_{e\in\delta^-(v)}x_e=\sum_{e\in\delta^+(v)}x_e,\qquad v\in I.
$$

和固定边集：

$$
x_e = 1, \qquad e \in F
$$

最终可以得到一个线性方程组：

$$
Ax=b
$$

如果$\ \mathrm{rank}(A) = |E|$，此时方程是满秩的，有唯一解。而同时满足流量非负，传播定律和局部最大定律，则该解为合法解。

由于直接枚举$\ \iota,\omega,F$是不可取的，使用SMT处理满足流量非负、传播定律和局部最大定律的约束。
