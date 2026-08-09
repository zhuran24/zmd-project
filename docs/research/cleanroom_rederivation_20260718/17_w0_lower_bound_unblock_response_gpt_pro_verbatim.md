## 结论

这次**还没有求出能够通过 strict checker 的完整 6×7 下界见证**，所以项目账本暂时仍应保持：

```text
U = (1188,18)
L = absent
```

但下界长期卡住的主要病根已经找到了，而且不是泛泛的“搜索空间太大”，而是当前 W0 路线的起点本身就不可完成。

## 真正的问题：当前 geometry seed 不是合法暖启动

我对 pinned W0 geometry seed 做了一个不调用求解器的逐本体重算，直接根据 strict instance 中的 physical mode 和 port 定义，检查每台机器的输入、输出 access cell 是否：

1. 在 70×70 地图内；
2. 没有被任何固定 facility body 占据；
3. 能满足某个真实 operation class 的输入、输出端口数量。

结果是：

* 219 台制造设施中，**129 台无法承担任何一个同尺寸的真实 operation class**；
* 其中 **128 台连最基本的“至少一个输入前格和一个输出前格”都无法同时获得**；
* 132 个 3×3 body 中，只有 43 个位置还能承担某种 3×3 class；
* 49 个 5×5 body 中，只有 33 个位置还能承担某种 5×5 class；
* 38 个 6×4 body 中，只有 14 个位置还能承担某种 6×4 class。

还有两个非常直接的支持集缺口：

```text
3L 需要 109 个位置，但固定 seed 中只有 43 个位置能承担 3L
6G 需要  32 个位置，但固定 seed 中只有 14 个位置能承担 6G
```

这意味着，**即使完全删除 commodity binding、transport component、directed reachability 和 endpoint uniqueness，这份固定 seed 仍然不可能完成。**

所以旧 seed 并不是“219 台机器已经摆好，只差接线”，而是其中大量机器被周围 body 挤到只剩输入面或只剩输出面，甚至四面全堵。现有 seed 所检查的 `two-cell attachment windows` 只是瓦片或主干尺度的余量，不能推出瓦片内每一台机器都拥有自己的合法端口面。

这就是下界一直像陷在沼泽里的核心原因：后面的 class swap、attachment slot 扩张、routing 加时，实际上都在尝试给一张先天无法绑定端口的本体图接线。

## D6 为什么一直失败

我把 D6 gate 分层重建了一遍，只保留：

* body placement；
* operation class；
* physical mode；
* exact active input/output port 数量；
* access cell 必须在局部范围内且不能被 body 占据；
* fixed pole、power、cycle row 和 6×7 protected rectangle。

全部 transport placement、component pattern 和 reachability flow 都删除。

结果如下：

| D6 模型                          | 结果                | 含义                                     |
| ------------------------------ | ----------------- | -------------------------------------- |
| 只摆 17 个 body，保留原孔洞和 tile split | 可行，0.07 秒         | 面积本身塞得下                                |
| 加上真实 mode 与 active fronts      | 不可行，30.07 秒       | 冲突在端口前格层已经发生                           |
| 取消两瓦片固定 type split，保留原孔洞       | 仍不可行，12.42 秒      | 只调整两瓦片装载表不够                            |
| 取消原固定孔洞，保留 type split          | `UNKNOWN`，20.01 秒 | 无数学结论                                  |
| 同时取消固定孔洞和固定 type split         | 可行，15.03 秒        | class 总数、pole、cycle、power 保留时，端口几何可以完成 |

最后一个可行解把两个 tile 的尺寸分布从原来的：

```text
tile (1,2): 5×3x3 + 3×5x5 + 1×6x4
tile (2,2): 5×3x3 + 1×5x5 + 2×6x4
```

改成：

```text
tile (1,2): 5×3x3 + 2×5x5 + 1×6x4
tile (2,2): 5×3x3 + 2×5x5 + 2×6x4
```

这个解没有保留 6×7 空洞，所以不是下界见证。但它说明了两件非常重要的事：

第一，D6 不是因为 17 个 body 的绝对面积超过容量。

第二，D6 的 full gate 并不是到 routing 才失败。它在“固定孔洞、固定 pole/cycle 环境、固定装载表、真实 mode 与端口前格”这一层已经死了。

目前还不能把其中某一个单独宣布为最小冲突核，因为“只取消孔洞”的实验是 `UNKNOWN`。最稳妥的判断是：**原孔洞位置和周围的固定结构不能继续与局部 class allocation 一起钉死。**

## 我也尝试了直接重做全图 front 模型

我进一步构建了一个全图匿名模型：

* 不使用 219 个命名实例；
* operation class 只按计数出现；
* 允许重新选择 body anchor、mode 和 active ports；
* 保留旧 pole、cycle 和固定 6×7 孔洞；
* 删除旧的 macrocell class allocation 与 tile type allocation；
* 暂时不建 routing。

模型规模约为：

```text
16,368 个 placement-mode 候选
209,767 个变量
310,684 个约束
```

它在几套运行门限内没有返回终态，因此不能解释成不可行。不过它暴露出另一个工程问题：即使去掉 commodity 和 routing，只要把 24 个供电区域的 body/front 遮挡关系全部揉进一个 CP-SAT，初始化、传播和全局对称仍然很重。

这说明下一步不能只是“把旧 monolithic model 再跑久一点”。需要把本地几何预先编译成列。

## 最有希望的新主线

我建议把下界构造改成：

### 1. Front-aware pattern generator

不再生成 body-only seed，而是对每个 14×14 power cell，必要时对两个相邻 cell 组成的 domino，生成完整局部 pattern。

每个 pattern 必须已经包含：

* manufacturing body 的位置和 template；
* 每个 body 的 physical mode；
* 真实 active input/output ports；
* 每个 active port 的 access cell；
* pole body；
* 各 operation class 的计数向量；
* 四条边上的 service seam 和 portal signature；
* 可选 6×7 或 7×6 body-only hole；
* 本地 body、power、front legality 全部通过。

也就是说，**pattern 的最小单位不再是“放下一块矩形”，而是“放下一台端口确实能用的机器”。**

### 2. Exact-cover pattern master

令 `z[t,p]` 表示区域 `t` 选择 pattern `p`。主问题只负责：

```text
每个区域恰选一个 pattern
每个 operation class 的全局数量精确匹配
全图恰选一个 6×7 或 7×6 hole
hole 与任何 facility body 不相交
相邻 pattern 的 service seam 和 portal 相容
```

这会把几十万 body/mode/front 变量，压缩为几百到几千个 pattern 选择变量。

实例 ID 暂时不进入 master。相同 operation group 内的命名实例在几何成功后按坐标排序赋值，避免排列对称。

### 3. Hole 必须成为全局变量

6×7 空洞不应继续固定在 D6 的 `(29,28)`。

它最适合放在：

* 原本就需要 body-free 的 service corridor；
* 两条 corridor 的交叉区；
* cycle 或 backbone 穿过的区域；
* hole-domino 专用 pattern 中。

strict objective 只统计 facility body，transport 可以穿过空洞。因此空洞应该和运输走廊重叠利用，而不是被当成 routing 禁区。

hole 所在区域的 pole anchor 也必须由 pattern 决定，不能同时固定 hole 和 pole，再要求剩余几何自行吞下全部 class。

### 4. Routing 最后做，而且先做一个通用 SCC

规则允许：

* 一条 lane 同时携带多种 commodity；
* 所有 19 种 commodity 共用同一 component；
* 没有 capacity 或 throughput 限制。

因此第一版 witness 可以采用一个很强但完全合法的充分构造：

1. 所有 active output 以正确方向进入同一个 directed strongly connected network；
2. 所有 active input 由该 network 以正确方向接出；
3. network 上每条 lane 都声明携带全部 19 种 commodity。

这样每种商品的任意 output 都能到达任意同商品 input，反向覆盖条件也自动满足。

routing 的首个目标就从“19 套商品网络”缩成：

```text
一个通用 directed SCC
+ 574 个 manufacturing terminal 方向接口
+ boundary/core 的 generic terminals
```

如果这个充分条件过强，再按 free-space component 或 commodity family 分片，而不是一开始恢复完整多商品路由模型。

## 下一阶段应该按三个门槛推进

**G1，pattern 覆盖门槛：**
先不生成 route，求出完整 body、pole、mode、active-front 和 6×7 hole。硬指标是 `dead_for_any_actual_class = 0`，并且所有 operation class 计数精确匹配。

**G2，portal/SCC 门槛：**
在固定 G1 geometry 上构造通用 directed SCC。失败必须返回 access isolation、portal incompatibility、free-space articulation 或 component direction obstruction，不能只返回笼统的整图不可行。

**G3，strict witness 门槛：**
补齐 required instance IDs、commodity bindings 和 route component JSON，直接运行独立 strict checker。只有 checker 零 issue，并复算出至少 `(area,min_side)=(42,6)`，才能正式登记下界。

## 交付包

压缩包中包括：

* 完整研究报告；
* solver-free seed 端口面审计脚本；
* D6 body/front 分层 probe；
* 全部原始 JSON 结果和结果矩阵；
* 可直接 `git apply` 的补丁；
* `SHA256SUMS.txt`。

补丁已做 clean-directory `git apply --check`，两个脚本已通过 Ruff 和 `py_compile`，7z 也完成了解压回验与逐文件哈希校验。

[下载下界解锁诊断包与补丁](sandbox:/mnt/data/zmd_lower_bound_unblock_20260730.7z)

压缩包 SHA-256：

```text
0c23cdde992ff08d110fad02440703e870f14fe07eeda51cc8eb4e865748fd61
```

下一轮主线应直接实现 G1 的 front-aware pattern catalog 与 exact-cover master。旧 geometry seed、D6 class swap 和单纯延长 routing 时间不应再继续占用主要计算预算。
