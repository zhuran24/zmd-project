---
status: ACCEPTED_DRAFT
source_of_truth: terminology and units must stay aligned with downstream code consumers; geometry semantics are referenced by placement/routing/master specs
last_verified_against: 2026-07-18（实体 generic-input provider 与 owner 语义裁决）
owner: docs-modeling
---
> [!WARNING]
> **DRAFT — 几何/符号体系源自 Gemini deep think Turn 14。§2.4.1、§2.5.3 与 §2.6.1 已按当前 owner 裁决和 PROJECT_LOCK 边界对齐；其余符号定义待终审冻结。**

# 02 全局数学符号、坐标系与度量衡规范 (Global Notation, Coordinates and Units)

## 2.1 文档目的与适用范围

本文档是《明日方舟：终末地》极值排布工程的"几何与代数新华字典"。
在将复杂的物理规则（03章）和刚体实例（05章）映射为计算机内存中的张量与线性代数方程（06~09章）前，必须确立一套绝对无歧义的参照系。本文档锁死了全局坐标系原点、Z 轴路由层级、实体锚点偏移计算法则、局部端口寻址顺序、以及将在后续所有数学约束模型中通用的集合与变量符号。

---

## 2.2 全局离散坐标系与网格 (Global Discrete Grid)

系统采用严密的**离散第一象限正交坐标系**，遵循"左下角原点"范式。

### 2.2.1 二维地面网格域 ($\mathcal{C}$)
主基地被定义为由 $70 \times 70 = 4900$ 个离散网格（Cell）组成的有限整数域 $\mathcal{C}$：
$$ \mathcal{C} = \{ (x, y) \in \mathbb{Z}^2 \mid 0 \le x \le 69, \ 0 \le y \le 69 \} $$
* **原点 $(0, 0)$**：位于主基地的**绝对左下角**。
* **$X$ 轴 (横向)**：自左向右为正方向，取值范围 $x \in [0, 69]$。左侧边界基线位于 $x=0$。
* **$Y$ 轴 (纵向)**：自下向上为正方向，取值范围 $y \in [0, 69]$。下侧边界基线位于 $y=0$。

*(防错红线：任何实体占据坐标必须严格在此闭区间内，如占据 $x=70$ 将引发致命越界异常。几何意义上，离散坐标 $(x, y)$ 代表的是底边位于 $X \in [x, x+1]$，左边位于 $Y \in [y, y+1]$ 的 $1 \times 1$ 绝对正方形物理面。)*

---

## 2.3 多层路由空间 (Multi-layer Routing Space)

为了合法表达"物流桥真三维叠加"的规则（03章），系统的三维物理空间被抽象为带有 Z 轴层级的离散张量 $\mathcal{C} \times \mathcal{L}$，其中 $\mathcal{L} \in \{0, 1\}$：

* **地面层 ($L = 0$)**：
  承载所有实体刚体（制造单位、核心、供电桩、仓库口）、幽灵空地禁区，以及地面传送带、分流器、准入口等。地面层的任何两个非穿透性对象绝对互斥。
* **高架层 ($L = 1$)**：
  仅承载【物流桥】。该层允许与 $L=0$ 层中无 Z 轴阻挡体积的组件（如普通直线传送带）在同一个 $(x,y)$ 坐标上重叠（实现无碰撞跨越）。但**严禁**高架层穿透 $L=0$ 层中具有无穷高 Z 轴属性的物理刚体（如机器本体、供电桩本体、空地禁区）。

---

## 2.4 实体位姿与几何锚点 (Entity Pose & Anchors)

在处理诸如 $6 \times 4$ 这类非对称刚体时，旋转操作极易引发坐标偏移。本系统采用**"旋转后绝对包围盒左下角锚定法"**。

### 2.4.1 位姿状态元组 ($p$)
定义一个实体刚体在网格中的绝对物理状态（位姿, Pose/Placement）为一个四元组 $p = (x, y, o, m)$：
* **$(x,y)$**: 绝对锚点坐标。
* **$o$**: 旋转姿态，$o \in \{0, 1, 2, 3\}$ 分别对应未旋转、顺时针 $90^\circ$、$180^\circ$、$270^\circ$。
* **$m$**: 实体端口/工作模式枚举值（例如方形机器或协议箱指定哪组对边为输入侧与输出侧，协议核心指定左右输出或上下输出姿态）。

### 2.4.2 绝对锚点定义 (Anchor Point $x, y$)
对于原始尺寸为 $W \times H$ 的设施：
1. **生成旋转后外包围盒 (Post-rotation Bounding Box)**：
   若 $o \in \{0, 2\}$，包围盒尺寸为 $w = W, h = H$；
   若 $o \in \{1, 3\}$，包围盒尺寸反转为 $w = H, h = W$。
2. **锚点落位**：
   设施的锚点 $(x, y)$ **永远定义为其在当前姿态 $o$ 下，物理包围盒的最左下角格子的绝对坐标**。

### 2.4.3 占格投影函数 $\text{Occ}(i, p)$
在位姿 $p$ 下，设施 $i$ 占据的地面绝对坐标集合恒定为：
$$ \text{Occ}(i, p) = \{ (x', y') \in \mathcal{C} \mid x \le x' \le x + w - 1, \ y \le y' \le y + h - 1 \} $$
*(核心优势：此定义彻底消灭了坐标系旋转矩阵带来的负数坐标偏移计算，使得不越界判定被极度简化为 $x + w - 1 \le 69$ 且 $y + h - 1 \le 69$。闭区间 $\le w - 1$ 完美规避了差一错误。)*

### 2.4.4 供电桩覆盖几何域函数 $\text{Cov}(p)$
对于供电桩本体（尺寸 $2 \times 2$，其覆盖不受旋转影响），其在位姿 $p=(x, y, 0, m)$ 下的供电覆盖点集 $\text{Cov}(p)$ 严格定义为以本体为中心向四向各延展 5 格：
$$ \text{Cov}(p) = \{ (x', y') \in \mathcal{C} \mid x - 5 \le x' \le x + 6, \ y - 5 \le y' \le y + 6 \} $$
*(注：本体 $x$ 坐标占用 $x$ 和 $x+1$。向右延伸 5 格到达 $x+1+5 = x+6$，向左延伸 5 格到达 $x-5$。总宽度为 $(x+6) - (x-5) + 1 = 12$ 格。绝对精确！)*

---

## 2.5 端口局部索引与方向 (Local Port Indexing & Directions)

当实体需要在其边缘生成传送带接驳口时，采用**"四边局部 1D 坐标系"**进行寻址。

### 2.5.1 四向连通向量
定义全局方向集合 $Dir = \{N, S, E, W\}$：
* $N$ (North): $(0, +1)$
* $S$ (South): $(0, -1)$
* $E$ (East): $(+1, 0)$
* $W$ (West): $(-1, 0)$

### 2.5.2 局部边缘寻址
对于任意在当前姿态下尺寸为 $w \times h$ 的矩形实体包围盒，其边缘的局部索引（加上锚点偏移后）定义如下：
* **底边 (Bottom Edge)**：$Y = y$，横坐标为 $x + k \ (k \in [0, w-1])$，遍历方向**从左至右**。出向向量为 $S$。
* **顶边 (Top Edge)**：$Y = y + h - 1$，横坐标为 $x + k \ (k \in [0, w-1])$，遍历方向**从左至右**。出向向量为 $N$。
* **左边 (Left Edge)**：$X = x$，纵坐标为 $y + k \ (k \in [0, h-1])$，遍历方向**从下至上**。出向向量为 $W$。
* **右边 (Right Edge)**：$X = x + w - 1$，纵坐标为 $y + k \ (k \in [0, h-1])$，遍历方向**从下至上**。出向向量为 $E$。

### 2.5.3 Generic-input provider 与实体端口

定义 operation 到通用输入容量的完整映射为 $G_{in}(o)$。当前非零 provider 为：

- `box_sink`：$G_{in}=3$；协议箱是 `3×3` 实体，具有一侧 3 个输入口、对侧 3 个输出口和四种正交端口模式。
- `protocol_core`：$G_{in}=14$；mandatory 核心的选定 pose 具有 14 个实体输入口与 6 个实体输出口。

对被选中的 provider 实例 $i$ 及 pose $p$，$G_{in}(o_i)$ 必须严格等于该 pose 的实体 `input_port_cells` 数量；任何容量/几何漂移都 fail-closed。Binding 把每个正数 `required_generic_inputs` 商品分配到一个具体实体输入口。被分配的口携带坐标与方向，是 routing 的真实 sink terminal；生产该商品的输出口仍是 routing source，因此成品必须端到端可路由。

设总需求槽数 $D=\sum_k d_k$，真实 mandatory exact provider 容量为
$C_{man}=\sum_{i\in\mathcal{I}_{man}}G_{in}(o_i)$，则协议箱的 certified 下界为：

$$ B_{box}=\left\lceil\frac{\max(0,D-C_{man})}{3}\right\rceil $$

该抵扣是 **instance-aware**：仅定义 `protocol_core` 模板不能获得 14 槽抵扣；必须存在真实 mandatory exact core 实例。Mandatory 协议箱及未来声明的 provider 按同一 operation-capacity 规则计入。Certified session 从已哈希的 `preprocess_plan.json` 同一字节快照解析整张 provider map，并将整张 map 原子传递和比较；不得退化为单 operation 标量或二次磁盘读取。

---

## 2.6 核心代数符号字典 (Algebraic Notation Dictionary)

为确保后续约束规划方程（MIP/CP-SAT 模型）的高维推导绝对无歧义，统一定义以下集合与索引变量：

### 2.6.1 集合 (Sets)
| 符号 | 定义说明 | 规模大小 (本工程) |
| :--- | :--- | :--- |
| $\mathcal{C}$ | 主基地所有可用二维网格坐标集合 | 4900 |
| $\mathcal{I}_{\text{man}}$ | 强制必选刚体实例集合 (机器219+核心1+边界口46) | 266 |
| $\mathcal{I}_{\text{opt}}$ | 可选刚体实例集合：协议箱 (provider-aware residual-optional) + 供电桩 (residual-optional)，激活数均为决策变量 | 非固定 † |
| $\mathcal{I}$ | 全局实体总集 ($\mathcal{I} = \mathcal{I}_{\text{man}} \cup \mathcal{I}_{\text{opt}}$) | 266 + 可变 † |
| $\mathcal{K}$ | 商品(物料)类型集合，如矿石、中间品等 | 见 04 章 |
| $\mathcal{P}_i$ | 实例 $i$ 所有合法的(不越界、无自相矛盾的) 离散候选摆位集合 | 将由 06 章生成 |

> †  **[PROJECT_LOCK 对齐]** certified_exact **无**硬 `50 供电桩 + 10 协议箱`(合计 60)/ 总集 326 cap —— 该数字按 PROJECT_LOCK §1 仅为 exploratory-only guidance，禁止作为 exact-mode 上界重新引入 (Forbidden Change)。真实 master 对供电桩用 residual-optional(下界由 07 章 §7.6 供电覆盖给出、上界为候选位姿池规模)；对协议箱按真实 provider 实例的实体 generic-input 容量计算 residual 下界（当前 mandatory core 的 14 槽已覆盖 demand 2，故下界为 0），额外选箱受 fresh V94 dominance 约束。旧 “60 / 326” 是 exploratory 坐标模型遗留，仅作 illustrative 参考。

### 2.6.2 系统决策变量 (Decision Variables)
| 符号 | 变量域 | 定义说明 |
| :--- | :--- | :--- |
| $z_{i, p}$ | $\{0, 1\}$ | **核心位置变量**。当且仅当实例 $i$ 采取候选位姿 $p \in \mathcal{P}_i$ 放置时，值为 1。 |
| $x_i$ | $\{0, 1\}$ | **存在性变量**。当且仅当可选实例 $i \in \mathcal{I}_{\text{opt}}$ 被激活放置时，值为 1。*(注：对于 $i \in \mathcal{I}_{\text{man}}$，$x_i \equiv 1$)* |
| $u_{w,h}$ | $\{0, 1\}$ | **空地状态变量**。当系统在外层循环中枚举到尺寸为 $w \times h$ 的空地且验证合法时，值为 1。 |
| $f_{c, d, L}^k$ | $\mathbb{Z}^+$ | **物流流量变量**。在层级 $L$ 的格子 $c$ 处，商品 $k \in \mathcal{K}$ 是否沿方向 $d$ 流经的稳态速率。 |

---

## 2.7 时间基准与吞吐量度量 (Time & Throughput Metrics)

为消灭所有配方计算与传送带容量校验中的浮点数误差，系统中涉及时间与流量的参数，统一映射至离散的 **Tick (刻)** 域：

* **1 基础时间周期 (Tick)** $\equiv$ 物理时间 2.0 秒。
* **传送带极限容量 (Belt Capacity)** $\equiv$ $1.0$ 物品 / Tick。
* **机器极速吞吐率 (Max Port Throughput)** $\equiv$ $1.0$ 物品 / Tick。
* **拓扑度数约束 (Port Degree)**：实例 $i$ 的输入/输出插管根数 $D_{\text{in}}(i)$ 与 $D_{\text{out}}(i)$ 为绝对整数常量（由 04 章 4.8 节矩阵给定）。稳态方程中，路由算法必须且只能为其接入**精确等于度数限额**的连线。
