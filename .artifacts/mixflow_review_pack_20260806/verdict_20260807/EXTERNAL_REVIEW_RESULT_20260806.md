# routing 混流表达手术外审结果

**审查日期**：2026-08-06  
**审查对象**：`mixflow_surgery_review_20260806.7z` 中的手术代码、设计说明、外审 brief 与差分测试  
**判决**：`BLOCK`

## 1. 判决摘要

这次手术对“静态、按商品标注的有向图连通性”实现得相当完整。逐侧覆盖、精确侧、物理态唯一化之间没有发现 CP-SAT 编码漏洞；sink front 的地面生成期禁用也确实把外来商品的 **静态 use 状态** 排除在门口格之外；单商品语义在补充回归中未见收窄。

但手术本体接受一种在游戏动力学下不能保证正确送达的 de-mix 解。内容盲 splitter 不按商品分拣，模型却允许在同一物理 splitter 上声明 `a` 走一支、`b` 走另一支。更关键的是，我构造了一个仅 4 个自由格的解，两条分流支路都只有一个转弯终端格，根本没有直行格可放 brief 所依赖的准入口。该实例术前 `INFEASIBLE`、术后 `FEASIBLE`，术后的全局连通复验器仍返回 `failure_count=0`。

因此，“诚实披露 + 后续 scope 声明”只能把结果降格为“静态连通候选”，不能让它继续承担 certified-exact 的游戏语义 soundness。当前形态不得进入可开启的 certified 接入批。

本分支尚未合入 main、未接入认证路径，所以本判决不表示已有认证结果遭到污染。

## 2. 审查方法与实测

### 2.1 材料完整性

`MANIFEST_SHA256.txt` 所列 7 个文件的 SHA-256 均与实际字节一致。

### 2.2 官方测试与静态检查

在 Python 3.13.5、OR-Tools 9.15.6755 的隔离环境中运行本包 `test_routing_mixflow.py`：

```text
13 passed in 0.34s
```

`routing_subproblem.AFTER.py` 通过 `py_compile` 与 `ruff check`。测试文件本身仅有一个低风险 lint：`pytest` 导入未使用。

由于审查包未包含 `src.models.cp_sat_worker_config`，测试夹具只为该模块提供了单 worker、无内存帽的最小桩。该桩不改变模型变量、约束或求解可行域。

### 2.3 独立的局部编码穷举

对一个 L0 格、两个商品、每商品“未选或选择 44 个合法子图样之一”的全部组合进行穷举。实际枚举出的 469 个可行 use 选择，与“所有 use 进出侧并集恰好属于 44 态 L0 字典”的理论集合完全一致：

```text
actual_assignments   = 469
expected_assignments = 469
unexpected           = 0
missing              = 0
```

结论：M1 所述逐侧覆盖合取在当前 CP-SAT 编码中没有发现漏洞；`phys=0` 时 use 也确实全部被压为 0。

### 2.4 单商品差分回归

随机生成 300 个小型连通自由域，覆盖单源/多源、单 sink/多 sink、可行和不可行端口组合；分别使用 BEFORE 与 AFTER 求解。300 例的 domain status 与 routing status 均一致，未发现单商品可行域收窄。

### 2.5 sink-front 边界补充测试

补充验证了以下边界：

1. 外来商品只在 sink front 的 L1 垂直借道，且与 owner 的 L0 直带垂直交叉：`FEASIBLE`。
2. 同一商品拥有同一 front 的两个对向 sink 口，由一个 splitter 同时送达：`FEASIBLE`。
3. `a` 的 sink front 与 `b` 的 source front 共格：`b` 的地面态被禁用，实例 `INFEASIBLE`。
4. 异商品多 owner sink front：地面全排，实例 `INFEASIBLE`。

这些结果支持 `_mixflow_ground_banned` 的局部门口规则。未发现“多 owner、对向双口、L1/L0 组合”直接绕过生成期排除的代码洞。

## 3. Findings

### B-01：de-mix 解在游戏动力学下纳伪，且存在无准入口槽位的 4 格反例

**级别**：Blocker  
**影响**：术后模型可返回 `FEASIBLE`，静态复验也通过，但抽取出的硬件不能保证商品按声明支路送达，可能把错货送入异商品机器输入口。

材料已经承认根因：内容盲 splitter 会轮转推货、不读取商品类型，静态声明 `a` 走南、`b` 走北并不控制真实货物去向。见：

- `EXTERNAL_REVIEW_BRIEF.md:50-64`
- `DESIGN.md:191-200`

材料提出的物理兑现依赖“每条 de-mix 支路放一个直行准入口”，同时明确原型没有强制支路存在直行格：

- `EXTERNAL_REVIEW_BRIEF.md:65-72`
- `EXTERNAL_REVIEW_BRIEF.md:83-88`
- `DESIGN.md:196-200`

#### 最小反例

只保留 4 个自由格，其余 70×70 格全部占用：

```text
M = (5,5)   合流格
D = (6,5)   分流格
TA = (7,5)  a 的转弯终端格
TB = (6,6)  b 的转弯终端格
```

端口：

```text
a source: front M, dir E   -> a 在 M 使用 W→E
b source: front M, dir N   -> b 在 M 使用 S→E

a sink:   front TA, dir S -> TA 为 W→N 转弯终端
b sink:   front TB, dir E -> TB 为 S→W 转弯终端
```

术后抽取结果的关键两格：

```text
M phys: merger  {S,W}→E
  a use: W→E
  b use: S→E

D phys: splitter W→{N,E}
  a use: W→E
  b use: W→N
```

实测：

```text
BEFORE: INFEASIBLE
AFTER:  FEASIBLE
AFTER connectivity validator: connected=True, failure_count=0
```

真实 splitter 只按轮转选出口。合流带出现合法到达序列 `a, a, b` 时，若出口轮转为 `E, N, E`，第二个 `a` 会进入北支路并抵达 `b` 的输入口。静态 sink-front use 虽然只有 `b`，真实货物并不会遵守这个标签。

该反例还封死了准入口兜底：D 后的两条支路都只剩一个终端格，且 TA、TB 都是转弯带。准入口按材料定义只能直行，因此两条支路均无可部署位置。共享段前放准入口不能完成 de-mix，因为分支尚未出现。

相关实现位置：

- 子图样 use 生成：`routing_subproblem.AFTER.py:1131-1175`
- 逐侧耦合：`routing_subproblem.AFTER.py:1187-1296`
- 静态连通复验：`routing_subproblem.AFTER.py:1937-2046`
- 复验通过即返回 FEASIBLE：`routing_subproblem.AFTER.py:2148-2164`

#### 为什么 scope 声明不够

scope 声明可以准确描述“这里只证明静态标注图连通”，但不能把一个不可按所给硬件兑现的路由变成游戏语义合法。当前抽取 schema 只输出 belt/splitter/merger/bridge，不输出准入口，也没有独立 realization witness。若该状态仍可进入 certified 路径，语义只是被文字改名，伪解仍然存在。

scope-only 处置仅在以下条件下可接受：该结果被明确降格为研究或见证阶段的 `STATIC_CONNECTIVITY_FEASIBLE`，且技术上禁止其晋升为 `CERTIFIED`。

#### 必要修复

优先方案是把内容盲传播建模为真实语义：混合商品集合进入 splitter 后，默认传播到每个出口；只有显式 item-filter/准入口组件才能缩窄某一出口的商品集合。filter 必须进入物理态、占格、直行方向、itemId 与抽取 witness。

较小但保守的方案是：在未建模 filter 时禁止 de-mix。任何共享同一输入通道的商品，在内容盲 splitter 上不得声明不同的出口集合。该方案会牺牲本手术主要表达力，但不会纳伪。

若坚持把准入口留在 routing 模型之外，至少需要一个独立的、接入认证链的构造性 realization gate，证明并输出：

1. 每个 de-mix 出口在到达任何异商品 sink 或再次合流前，有可占用的直行 filter 格；
2. filter 不与终端带、桥或其他物理件冲突；
3. 被拒货物有回到分流器并最终进入自身支路的进展性证明，不会形成死锁；
4. 生成的 filter 布局通过游戏侧复验。

仅要求“每支路存在一个直行格”仍不足以覆盖循环、重合流和拒货死锁，但它至少能排除本反例。

### F-02：M4 的“纯放宽”论证在 RoutingSubproblem API 域上不成立

**级别**：Major proof finding  
**影响**：不会把游戏非法布局变合法，但当前 INFEASIBLE 方向的证明文本使用了一个字面为假的蕴含。

`EXTERNAL_REVIEW_BRIEF.md:104-110` 以“手术是纯放宽”为前提，主张新模型 INFEASIBLE 蕴含旧模型 INFEASIBLE。但同一文件 `:132-142` 又明确说明，多 owner sink-front 全排会把旧模型接受的手造 fixture 收紧为 INFEASIBLE。

独立复现的最小输入：

```text
free = {(1,0), (2,0), (3,0)}
iron、copper 的 source 均位于 (1,0), dir E
iron、copper 的 sink 均位于 (3,0), dir W
```

结果：

```text
BEFORE: FEASIBLE
AFTER:  INFEASIBLE
```

收紧来自 `routing_subproblem.AFTER.py:1048-1062` 的多 owner 地面全排。该 fixture 按材料论证无法由合法 placement/binding 产生，所以这不是“不拒真”的实质失败；但 M4 必须改写为带前提的命题，例如：

```text
对满足 placement/binding 可达性不变量的生产输入，旧可行解均可嵌入新模型；
额外的多 owner 收紧只拒绝游戏非法或上游不可达输入。
```

同时，任何依赖“旧模型曾 INFEASIBLE”来证明 layout cut 安全的代码或文档，都必须显式携带上述生产输入前提，不能再把全 API 域的纯单调性当作理由。

### F-03：现有测试证明了局部守卫承重，却没有覆盖动态 soundness

**级别**：Major test finding

`test_routing_mixflow.py:206-230` 把 U-02 的静态 de-mix 作为正例；`test_connectivity_validator_accepts_mixflow_solution`（`:343-348`）只确认同一静态标注图被复验器接受。因此测试会稳定地把 B-01 的伪解保护成预期行为。

另有两个较小的断言缺口：

- U-02 的 L1 fallback 分支只要求“存在某个地面 splitter”，没有确认它就是两商品共享的 de-mix 点，也没有验证两商品去向，见 `:217-230`。
- `test_u02_split_destinations_are_disjoint` 实际只检查每个 use 的侧是 phys 侧的子集，没有检查商品出口互斥或 disjoint，见 `:233-243`。

修复后应增加至少一条负例：上面的 4 格无 filter 槽位实例必须 `INFEASIBLE`，或必须由独立 realization gate 拒绝。若 filter 被显式建模，则测试应断言抽取 witness 中确实包含两个合法 filter，而不是只检查静态 use 标签。

### F-04：性能风险方向判断正确，但启用门槛与可复现实证不完整

**级别**：Major enablement finding

`DESIGN.md:232-266` 如实记录 build 从 2.4× 返工到 +5.6%，也记录术后在 120s/600s 探针上无结论；`:301-315` 已提出默认关闭、割适配与 benders 生产实测。这些方向是正确的。

当前材料仍不足以支撑启用：

1. `DESIGN.md:230` 提到的 `bench_mixflow_prodscale.py`、原始日志与 600s telemetry 不在 `MANIFEST_SHA256.txt` 的 7 个文件中，外审无法独立复验数字。
2. 没有给出 feature gate 的量化通过阈值，例如 p50/p95 wall time、峰值内存、首次连通 incumbent 时间、guard rejection 数、fallback nogood 比例、累计 cut/nogood 数。
3. 只有对抗性不可行 proxy 和 6 商品同构缩放描述，缺少可行、不可行、桥密集、终端密集、真实 benders 候选的分层语料及多 seed/worker 重复。
4. 弱 nogood 会让模型持续增长并反复重建 solver，需设置拒绝次数、模型增长与总时间上限，并确认 TIMEOUT 永不被上游解释为 INFEASIBLE。

在 B-01 修复前，性能优化不能替代 soundness。修复后，certified 路径的开关应默认关闭，只有量化门槛全部通过才能开启。

## 4. 中心问题逐项答复

### 4.1 不纳伪

**不通过。** `_mixflow_ground_banned` 对静态 L0 门口 use 的局部排除没有发现直接漏洞，但动态错货可以从上游内容盲 splitter 进入“静态上纯净”的 sink front。4 格反例证明这种伪解还可能没有任何准入口部署槽位。

### 4.2 不拒真回归

**单商品轴通过。** 局部编码穷举与 300 个随机单商品场景均未发现 BEFORE 可行而 AFTER 不可行。多 owner 的跨商品收紧使全 API 域不再纯单调，但其已知反例属于游戏非法或上游不可达输入，应修正文档前提。

### 4.3 “静态连通 ⇒ 正确送达”的丢失

**scope-only 不可接受于 certified 路径。** 它可以作为研究状态的诚实标签，但不能继续使用 `CERTIFIED` 的游戏可实现性含义。更好的方案是显式建模 item filter，或增加构造性 realization gate；在此之前保守禁止 de-mix。

### 4.4 性能固有代价

**风险识别方向基本完整，验收机制不完整。** 默认关闭、割适配、benders 实测是必要三件套，但还需可复现脚本/日志、量化阈值、真实语料、多次重复、内存与拒绝循环上限。

## 5. Q1-Q6 结论

- **Q1**：未发现逐侧覆盖的 CP-SAT 编码洞。独立穷举完全匹配理论集合。
- **Q2**：必须采取语义动作。scope 声明只适合降格为静态候选，不足以保留 certified 含义。
- **Q3**：必须上升为模型约束或独立 realization 证明。4 格转弯终端反例证明“总能补准入口”为假。
- **Q4**：未发现对 `_mixflow_ground_banned` 的直接 L0/L1 几何绕过；但上游动态错分会绕过“静态门口纯流”的保护目标。
- **Q5**：未发现唯一化与跨层边平衡产生幻影 splitter。逐层唯一化、物理层互斥和 directed edge count 组合在审查场景中行为正确。
- **Q6**：core 14 保持保守排除只可能拒真，不会因本手术纳伪；作为本轮范围切分可接受。

## 6. 解除 BLOCK 的最低条件

1. certified 路径默认关闭本手术，研究路径与认证状态严格分离。
2. 修复 de-mix 语义，选择“显式 filter + witness”“独立 realization gate”或“禁止 de-mix”之一。
3. 将 4 格无 filter 槽位反例加入常驻负测，并增加真实物品传播/过滤复验，不再只复验静态标签图。
4. 修正 M4 的单调性论证，明确生产输入前提及多 owner 的语义收紧。
5. 提供性能脚本、原始日志、固定 corpus、量化阈值与 timeout/fallback 的 fail-closed 端到端测试。
6. 完成 witness adapter 的子图样兼容后，抽取结果必须包含或引用实现 de-mix 所需的物理构件证明。

在上述条件完成前，本手术可以保留在隔离研究分支，但不能进入会影响 certified 判定的接入批。
