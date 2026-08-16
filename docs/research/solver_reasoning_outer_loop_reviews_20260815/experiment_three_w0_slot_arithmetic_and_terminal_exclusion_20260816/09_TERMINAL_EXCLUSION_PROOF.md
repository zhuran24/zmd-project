# 固定 W0 布局下 6×7 矩形的 binding+routing 终局排除

> **Judgment：** `J-W0-FIXED-RECT-BINDING-ROUTING-EXCLUDED-V1`
> **研究候选状态：** `PROVED_EXCLUDED_RESEARCH`
> **范围：** 固定 `W0-ALIGNMENT` 与矩形 `R=[1,6]×[51,57]`，钉死 current binding+routing research model。
> **独立复算器：** [`10_check_w0_terminal_exclusion.py`](10_check_w0_terminal_exclusion.py)

## 1. 主张

在本 dossier 声明的固定研究模型作用域中，不存在一对 `(b,r)` 同时满足：

1. `b` 是 W0 binding contract 接受的合法绑定；
2. `r` 是固定布局与固定矩形下满足 canonical predicate 5 的 routing witness。

形式化地：

\[
\neg\exists b,r\;
\bigl(
LegalW0Binding(b)
\land
Routable_{P5}(W0,R,b,r)
\bigr).
\]

因此，固定 W0 布局中的该 6×7 矩形在研究候选账中由 `UNKNOWN` 转为 `PROVED_EXCLUDED_RESEARCH`。

## 2. 前代定理一

[`J-W0-GHOST-FRONT-BOUNDARY-041-V1`](../experiment_one_w0_ghost_front_offline_certificate_20260815/01_JUDGMENT.json) 已独立证明：

\[
Active_{041}(b)
\Longrightarrow
\neg\exists r\;
Routable_{P5}(W0,R,b,r).
\]

理由是 `boundary_port_041` 的唯一 front cell 为 `(1,53)`；活动 source 要求该格接受 belt terminal，而 `(1,53)∈R` 且 strict-empty 禁止矩形内任何 logistics occupant。

定理一只是一条条件式定理。它自身没有证明每个合法 binding 都触发 `Active_041`。

## 3. 新定理二

[`J-W0-GENERIC-OUTPUT-SLOT-SATURATION-041-V1`](02_JUDGMENT.json) 从钉死字节独立证明：

\[
LegalW0Binding(b)
\Longrightarrow
Active_{041}(b).
\]

承重算术为：

\[
|S|=46+6=52,
\qquad
D_{blue}+D_{source}=34+18=52.
\]

每席 ExactlyOne，故

\[
\sum_s unused_s=52-34-18=0.
\]

所有 `unused_s` 为非负 0/1 量，所以每个席位都必须活动，特别是 `boundary_port_041:out:0`。

这条全称证明不依赖 1007 份观测 selection。journal 只提供 1007/1007 的事后覆盖对拍。

## 4. Context transport

定理一的 `contextHash` 是：

```text
5e15112638b849e3b04b674be30fd4c0b7c8fd41f73caecfce5f05b44cc1bded
```

定理二明确把该值登记为 `base_contextHash`，并只增加钉死的 binding-contract 前提，形成：

```text
f66d8a2c0334be01b419229da97d8c32fc19bfb4d5fa07e2cd6e370e40e79a28
```

共享的 problem、objective、canonical rules、candidate pool、W0 layout 和 rectangle identity 均未变化。

定理一原本对任意 binding selection 陈述条件式蕴含。把讨论域收窄到满足 `LegalW0Binding` 的 selection，不会使该蕴含失效。形式上是 context 增强（加入前提）下的单调 transport：

\[
\Gamma\vdash P\to Q
\quad\Longrightarrow\quad
\Gamma,\Delta\vdash P\to Q.
\]

这里 `Δ` 就是定理二新增的 binding-contract 前提。

## 5. 路径级 lift 义务

槽级算术要升到当前 fixed-layout binding+routing path，必须把 [`07_MODEL_CORRESPONDENCE.md`](07_MODEL_CORRESPONDENCE.md) 的八条义务全部入账，并明确区分机器关闭与人工论证。

| ID | 义务内容 | 证据类型 |
|---|---|---|
| `W0-LIFT-01` | W0 输入身份与定理二一致 | source hash + theorem checker |
| `W0-LIFT-02` | 实际 binding model 构造 52 个 source slots | source AST/text audit + model snapshot |
| `W0-LIFT-03` | 每 slot 三标签 ExactlyOne | source audit + 52 组 snapshot 约束 |
| `W0-LIFT-04` | 全局 exact counts 为 34/18 | source audit + snapshot constraints 287/288 |
| `W0-LIFT-05` | 非-unused 导出 source port；unused 不导出 | `extract_selection/extract_port_specs` audit |
| `W0-LIFT-06` | port specs 与 strict rectangle 进入 exact routing path，无第二 binding bypass | Phase -1 fixed-layout harness audit + routing source identity |
| `W0-LIFT-07` | 两定理 context transport 合法 | 两 checker PASS + shared identity check |
| `W0-LIFT-08` | 研究排除不写 exact status/claim ledger | protected-surface hash check |

当前画像为 LIFT-02/03/04/07/08 五条机器关闭，LIFT-01/05/06 三条显式人工论证且未被机器完整覆盖，零条 `OPEN`。人工论证不冒充机器证明，终局效力仍受本页与 Judgment 的 research-only 边界限制。

A_BASELINE model snapshot 不是定理二的数学前提。它只独立确认当前 constructed CpModel 与抽象 contract 的对应：

- 17,190 variables；
- 289 constraints；
- 52 个 generic-output slot group，共 156 个 literals；
- 每组三标签 ExactlyOne；
- constraint 287 为 52 个 blue literals 的 `sum=34`；
- constraint 288 为 52 个 source literals 的 `sum=18`。

终局 checker 必须逐组重算这些事实，不能只信本页转述。

## 6. 组合证明

任取一个满足当前 W0 binding contract 的绑定 `b`，并反设存在 routing witness `r`。

1. 由定理二，`b` 必满足 `Active_041(b)`。
2. 由 context transport，定理一可在当前增强 context 中使用。
3. 由定理一，`Active_041(b)` 蕴含不存在满足固定布局、固定矩形与 predicate 5 的 routing witness。
4. 这与反设的 `r` 矛盾。
5. 因而对每个合法 binding `b`，都不存在 routing witness。
6. 所以不存在任何合法 `(b,r)` 对。
7. 路径账中五条机器义务已关闭，三条语义桥具有显式人工论证且零条义务 `OPEN`；在不把这三条论证冒充机器证明的前提下，固定 W0 矩形在声明的 research-only 作用域内记为 `PROVED_EXCLUDED_RESEARCH`。

证毕。

## 7. 终点候选账

当前下界仍是：

```text
L = ABSENT
```

因此 Endpoint Metrics Protocol v1 下的全局 `M_t` 没有数值语义，继续保持：

```text
M_t = N_A_NOT_READY
```

本批登记的是候选级交易，而不是伪造全局 `M_t`：

| 字段 | 变化 |
|---|---|
| subject | `W0-ALIGNMENT | x=1,y=51,w=6,h=7` |
| candidate state | `UNKNOWN → PROVED_EXCLUDED_RESEARCH` |
| evidence type | `EXACT_SINGLETON_EXCLUSION_BY_COMPOSED_THEOREMS` |
| unresolved candidate mass without lower bound | `ΔM_bottom = -1` |
| canonical global `M_t` | `N_A_NOT_READY → N_A_NOT_READY` |
| `ΔL` | `ZERO_BY_SCOPE` |
| `ΔU` | `ZERO_BY_SCOPE` |

这是本路线第一笔非零的固定候选排除交易，但不是 research upper ledger、certified frontier 或 exact-status 更新。

## 8. 与金丝雀 `INCONCLUSIVE` 的关系

实验二金丝雀的历史判词保持不变：

```text
INCONCLUSIVE
```

当时 C 臂在 20 秒内没有产生 binding proposal，也没有获得 `INFEASIBLE` 终态。因此它只能报告删失，不能报告 family collapse 或 solver UNSAT。

本批通过静态算术证明残余 binding contract 为空，解释了 C 臂面对的数学对象；但这条新证据不倒签成 C 臂当时已经观察到 terminal。两条证据线分别回答：

- 金丝雀：运行时在冻结预算内看到了什么；
- 本批：钉死 contract 在数学上蕴含什么。

前者不回改，后者独立新增。

## 9. 非蕴含

本证明不产生：

- production `CERTIFIED` 或 exact-status 变化；
- stable claim ledger 写入；
- supervisor、publisher 或 release effect；
- production lowering 或通用 D3/D4；
- 其他布局、其他矩形或全局 score band 排除；
- research upper/lower bound 更新；
- current binding model 与完整 adjudicated-game 语义等价；
- 金丝雀历史判词重判；
- 1007 份观测的证明地位。

任一定理、输入或路径对应义务失效时，本终局 Judgment 必须转 stale 并重新复算。
