# R3 双证书对抗复核 verdict（2026-07-20，codex exec ultra 对抗席，14 攻击面全 CONFIRMED）

> 委托与原始产出：`.artifacts/cleanroom_r3_adversarial/`（prompt.txt/exec.log；本文件为 verdict 原文入库存档，仅加此头注）。
> 结论：证书 A（P≥9）与证书 B（(1190,34)）均 SURVIVES——(1190,34) 自此享受 certified 待遇；唯一旁支修正=09 号:133 条件光环筛选句需保留"恰 9 杆"前件。

## 审查边界

- 只审逻辑、离散几何与 strict 语义前提；未运行 `verify_r3_certificates.py`，不重复数值复算。
- 权威语义取自 `strict/external/problem_instance.json`；`strict/external/problem.md` 与 schema 仅用于核对其人读解释。
- 以下把空矩形写成整数格集合 `R=[x0,x1]×[y0,y1]`。设施 body 是实心整数格矩形；一个 port 的 access 格是其 body 格沿 port 方向正交一步所得。
- `CONFIRMED` 表示该攻击面未能产生反例，且给出的证明链在 strict 语义下闭合；`REFUTED` 表示找到反例或不可修补的推理断点。

## 证书 A：供电光环 ⇒ `P≥9`

### A1 — CONFIRMED

固定一根杆 `q`，令 `S_q` 是被分配给它的制造机集合。对每台 `F∈S_q`，840 条局部不等式给出

`|F| ≤ Σ_{c∈F} λ_q(c)`。

同一真布局中各设施 body 两两格不交，且所有 `λ_q(c)≥0`，所以

`Σ_{F∈S_q}|F| ≤ Σ_{F∈S_q}Σ_{c∈F}λ_q(c) = Σ_{c∈∪S_q}λ_q(c) ≤ Σ_c λ_q(c)=396`。

量词没有洞：每台受电制造机的覆盖杆集合非空，从中任选一根并且只记一次即可；不要求杆与机器之间单射，也不要求不同杆的 stencil 不交。把一台多重覆盖机器同时记给两杆会违反“分配给一根”，让同杆两台机器共享 body 格则违反 nonoverlap。原证明位置：`09_r3_response_gpt_pro_verbatim.md:125-129`。

### A2 — CONFIRMED

权威实例在 `problem_instance.json:2378-2386` 明载 coverage 偏移为 `[-5,6]²`，并把

`required_rule` 钉为 `at_least_one_body_cell_covered`。

三个制造模板均为 `requires_power: true`（`problem_instance.json:334-335,736-737,1210-1211`）。strict 人读原文也明确要求至少一个 **body cell** 落入裁剪后的 coverage（`problem.md:31-33`）。因此“只有 access 格进 coverage、body 不进”的最近反例不满足供电规则，不能进入可行布局。

### A3 — CONFIRMED

相对杆锚点 `(0,0)`，一个锚在 `(ax,ay)` 的 `W×H` body 与 `C=[-5,6]²` 相交，当且仅当

`-5-W+1 ≤ ax ≤ 6` 且 `-5-H+1 ≤ ay ≤ 6`。

这正是脚本 `verify_r3_certificates.py:56-59` 的两个半开 `range(...,7)`。与杆体 `{0,1}²` 相交当且仅当

`-W+1 ≤ ax ≤ 1` 且 `-H+1 ≤ ay ≤ 1`，

正由脚本 `:62-63` 排除。四种形态的完备计数为：

- `3×3`：`14²-4²=180`，锚点边界 `[-7,6]²`；
- `5×5`：`16²-6²=220`，锚点边界 `[-9,6]²`；
- `6×4`：`17·15-7·5=220`，边界 `[-10,6]×[-8,6]`；
- `4×6`：`15·17-5·7=220`，边界 `[-8,6]×[-10,6]`。

最低角锚点只以 body 的东北角格 `(-5,-5)` 接触 `C`，最高角锚点只以西南角格 `(6,6)` 接触，均被包含。真实地图的 body-in-grid 约束只会从这个相对 placement 超集中删项，不会产生目录外 placement。

### A4 — CONFIRMED

strict 规定设施 bodies 不得重叠（`problem.md:13-15`），并专门声明 pole body 也参加 nonoverlap（`:31-33`）；杆体模板确为实心 `2×2`（`problem_instance.json:1213-1225`）。不存在杆与制造机共格的合法 mode。

坐标检查：杆体为 `{0,1}²` 时，`3×3` 制造机锚在 `(-2,-2)` 会包含杆格 `(0,0)`，既被 840 枚举过滤又在真布局中非法；锚在 `(2,0)` 只沿东侧贴边、不共格，仍被保留。过滤没有把合法贴边误当重叠。

### A5 — CONFIRMED

设地图格集为 `G`。真受电条件是

`F ∩ ((q+C)∩G) ≠ ∅`，

它必然推出 `F∩(q+C)≠∅`，所以用未裁剪 `C` 建立的 840 placement 超集覆盖全部真放置。又因 `λ≥0`，

`Σ_{c∈G}λ_q(c) ≤ Σ_c λ_q(c)=396`。

杆靠地图边缘时，stencil 出格只会删除非负权重；主证明始终把完整 396 当单杆容量上界，没有反向使用。`09...md:133` 的 `C_q(R)` 再删除矩形内权重，方向同样只减不增。

### A 旁支量词告警（不击杀 `P≥9`）

`09...md:133` 的 “Any selected nine pole anchors must satisfy ...” 若被解释成“当布局有 `p>9` 时，任取其中九根”，则并不由前文推出；正确的一般式应对 **全部已放置杆** 求和。该句在后续 Stage A 的明确前件“exactly nine pole columns”（`09...md:287-289`）下成立。这个限定不进入 `3325≤396p`，也不进入证书 B 仅使用的 `p≥9` 杆体面积账，因此是旁支筛选语的量词告警，不是证书 A 主结论的反例。

## 证书 B：端口膜 ⇒ `(1190,34)`

下面令某条矩形边的切向整数区间为 `J`，与它相邻的设施侧区间为 `I`，`|I|=s`；contact 长度定义为 `ℓ=|I∩J|`。

### B1 — CONFIRMED

若 `0<ℓ<s`，则 `I` 不可能包含于 `J`。整数区间性迫使 `I` 从 `J` 的左端或右端伸出，并包含相应端点格；这就是证明所需的“跨端点”（更精确地说：命中该端点并向边区间外延伸）。

最近反例 `J=[0,5], I=[1,3]` 没跨端点，但此时 `ℓ=3=s`，是 full contact；真正 partial 的 `I=[5,7]` 只交 `{5}`，必跨右端点。原证明位置：`09...md:156-164`。

### B2 — CONFIRMED

固定矩形一条边的一个端点，任何跨该端点的 partial contact 都必须占据端点正外侧的同一个 body 格；两台设施同时跨越会立即 body 重叠。即使把“同一端点”理解为同一个几何角，来自两条相邻边的两个 partial contact 也会共同占据该角的外对角格。

坐标例：`R=[0,5]²`。跨 top-right 的 top-side partial body 必含 `(5,6)` 并向 `x≥6` 延伸；跨同一角的 right-side partial body 必含 `(6,5)` 并向 `y≥6` 延伸。两个实心矩形都含外对角格 `(6,6)`，故不能并存。只在 `(6,6)` 对角贴角而没有正交相邻的 body，则没有 access 格进入 `R`，不构成 contact。

因此每个有向边端点至多一个 partial contact；原文按四条边各两个端点给 `≤8` 是安全的宽松上界，甚至没有利用相邻边之间的额外互斥。

### B3 — CONFIRMED

同一矩形边上的每个 contact 格唯一对应其正外侧 body 格。两台设施的 contact 区间若在该边共享一个格，它们就占据同一个外侧 body 格，违反 nonoverlap。因此 bottom/top 各贡献至多 `w`，left/right 各至多 `h`，故

`L≤2w+2h=2(w+h)`。

角格双计不是漏洞。`R=[0,5]²` 时，可令一个 `3×3` body 为 `[3,5]×[6,8]`，另一个为 `[6,8]×[3,5]`；两 body 不交，却可分别从 top/right 使用同一个角 access 格 `(5,5)`。此时 `K` 有两个 incidence，`L` 也在 top/right 各计一次，而 `2(w+h)` 本来就把该角作为两条有向边的位置各计一次。

### B4 — CONFIRMED

设设施 `F=[a,b]×[c,d]`。若 west/east 两侧各有一个 access 格落入同一矩形 `R=X_R×Y_R`，则存在

`(a-1,yW),(b+1,yE)∈R`，其中 `yW,yE∈[c,d]`。

因为 `X_R`、`Y_R` 都是整数区间，`a∈X_R` 且 `yW∈Y_R`，于是 body 格 `(a,yW)∈F∩R`，与空矩形矛盾。north/south 同理。因此 R 不可能同时邻接制造机的输入、输出两条对侧，单机进入 R 的活跃制造端口数确实至多 `max(I,O)`。

坐标化失败反例：`F=[2,4]²` 的 west/east access 可取 `(1,2)`、`(5,4)`；任何同时包含二者的矩形必包含 body 格 `(2,2)`。

### B5 — CONFIRMED

更强地，一台实心矩形设施不能同时接触 `R` 的任意两条不同边。对边由 B4 排除；以相邻 top/right 为例，若设施分别含 top 外侧格 `(x,y1+1)` 和 right 外侧格 `(x1+1,y)`，其中 `x∈[x0,x1]`、`y∈[y0,y1]`，设施的矩形闭包必含交叉格 `(x,y)∈R`，矛盾。

最近绕角尝试对 `R=[0,5]²` 使用 body 格 `(5,6)` 与 `(6,5)`；任何包含二者的实心矩形也包含 `(5,5)∈R`。把 body 整体移到东北象限虽不压 R，却只剩对角接触，没有正交 access。只有 L 形或凹形 body 才能绕角，而权威实例只有 `width×height` 实心矩形。因此一台设施不会贡献两段 contact，excess 账没有重复使用同一设施的 baseline。

### B6 — CONFIRMED

固定一个 access 格 `z`，只有 N/E/S/W 四个正交邻格可能承载指向 `z` 的 port body 格；对每个邻格，指向 `z` 的方向唯一。第五个 terminal incidence 必须依赖以下至少一种非法情形：body 重叠、同一 `(body_cell,direction)` 上的双物理口，或一个物理口被重复绑定。

前两者分别被 nonoverlap 和已核 strict 模板排除；原论证也明示一物理口一绑定（`09...md:608-610`）。同一 body 格即使有不同方向的口，它们访问的是不同格，不能在 `z` 产生第五个 incidence。splitter/merger/crossing 的多方向属于 access 格内的 transport 组件能力，不会创造额外 facility terminal。故每格 `≤4` 成立；四向各来一个只是达到上界，不是反例。

### B7 — CONFIRMED

protocol core 的两种 mode 都把 6 个 output 严格分成对侧 `3+3`（`problem_instance.json:1362-1415,1551-1604`）。由 B4/B5，同一空矩形至多面对其中一侧，故 core output 至多贡献 3。

全局 final input 恰有 2 个，provider 仅 core/storage box（`problem_instance.json:1870-1886,3742-3752`），所以无论二者绑定到 core、box 或各一处，都只能再贡献 2。14 个 core input 是物理候选口，不是 14 个活跃 final terminal。core 是独立模板而非 manufacturing，未在 `K` 中先算一次。

需要注意，若两枚 final 都绑 core，同一矩形不能同时贴 core 的 input 边和 output 边，实际 core 贡献还小于 5；若 final 绑两个 box，则 `3 core outputs + 2 box finals` 才是这项宽松上界的组合。无论哪条路径都不超过 `+5`。

### B8 — CONFIRMED

权威目标明确为 `body_cells_only: true`（`problem_instance.json:1892-1895`），原论证假设也明确说矩形可含 transport components 与 active access cells（`09...md:650-654`）。端口膜没有把矩形偷换成全空区：它只把 628 个 active terminal incidence 按 access 坐标分成“在 R 内”和“在 R 外”，仅对后一类要求外部 body-free access 格。

矩形内铺满 transport/access 不改变这笔账；外部额外 routing 格、storage-box body 或第十根以后杆体均被忽略，只会让真实布局更拥挤，是安全松弛而非越界强化。外部 active access 格与所有 facility bodies 不交由 strict `problem.md:13-15` 保证。

### B9 — CONFIRMED

令

`F(w,h)=wh+ceil((580-w-h)/4)`。

置 `t=580-w-h`，则对整数维度

`F(w+1,h)-F(w,h) = h + ceil((t-1)/4)-ceil(t/4) ∈ {h-1,h}`。

合法矩形 `h≥6`，所以增宽一步净增至少 5；交换 `w,h` 同理。ceil 的锯齿每步最多回落 1，不能抵消乘积项，原文 `09...md:199` 的“两维增大左边不减”实际是严格递增。

扫描 `6..70` 覆盖所有合法边长；因不等式与 lex 目标只依赖 `wh`、`min(w,h)`、`w+h`，可纯数值地令 `w≤h`，不需要额外布局反射假设。故已复算得到的 lex-max `(1190,34)` 没有被单调性或扫描完备性击穿。

## 两证书总 verdict

- **证书 A 主结论 `供电光环 ⇒ P≥9`：CONFIRMED / SURVIVES。** A1-A5 全部成立。仅 `09...md:133` 的旁支条件筛选句需要保留“exactly nine”前件；这不影响主证书。
- **证书 B 主结论 `端口膜 ⇒ (1190,34)`：CONFIRMED / SURVIVES。** B1-B9 全部成立；依赖的 `P≥9` 也已在证书 A 中闭合。没有发现规格外强化、角点漏账、同设施双段、每格第五口或 ceil 单调性反例。

结论：这轮对抗审查未能击杀两个主 certified 候选；它们可以保留 certified 状态，但 A 的 conditional-halo 文案应把 “selected nine” 改成 “all placed poles”，或显式加上 `p=9` 前件。
