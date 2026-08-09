# 补丁 D：九条 R-* 的判定实验规格

基线 `H0` 固定为 canonical rules SHA256 `5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05` 与 mandatory instances SHA256 `545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6`。【已证明】

所有实验只判 G1 几何或 catalog 供给，不判 G2 路由、G3 端口绑定，也不产生完整生产 witness。【已证明】

所有 CP-SAT 实验都必须记录 `OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN`、墙钟、随机种子、模型版本、目标值和 best bound；`UNKNOWN` 一律归入“超时未证”。【已证明】

## D1-BODY-POSE-ENUM：`R-BODY-IN-REGION`

### 被判定命题

`H0` 的单体候选位姿中，跨 14 倍数房缝的制造机与杆位姿数量等于报告给出的候选域差值；该命题只涉及单体位姿，不涉及多个实例互不重叠或 master 可拼装性。【已证明】

### 模型伪代码

```text
for template in {M3, M5, M6, POLE}:
    baseline = enumerate_H0_legal_poses(template)
    kept = []
    removed = []
    for pose in baseline:
        rooms = { floor(x/14), floor(y/14) for every body cell (x,y) }
        if len(rooms) == 1: kept.append(pose)
        else: removed.append(pose)
    assert len(kept) + len(removed) == len(baseline)
report per-template counts
report 132*M3 + 49*M5 + 38*M6 instance-pose incidence totals
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| 板面与房格 | `70×70`，`5×5` 个 `14×14` 房间 |
| 模板 | M3=`3×3`，M5=`5×5`，M6=`6×4/4×6`，POLE=`2×2` |
| H0 候选数 | `17,952 / 16,896 / 16,900 / 4,761` |
| mandatory 制造台数 | `132 / 49 / 38` |
| 房缝 | `x,y ∈ {14,28,42,56}` |

以上常量来自 `06_geometry_constants.md` 与 `08_original_domain_baseline.md`，且受 H0 哈希约束。【已证明】

### 规模、预算与终止

最多扫描 `17,952+16,896+16,900+4,761=56,509` 条位姿，每条最多检查 30 个 body cells，变量为零，约束为零。【已证明】

预算上限为单进程 2 秒、64 MiB；完整遍历且守恒断言通过即终止，异常或预算耗尽记为未证。【强论据】

### 三种结果判读

- 可行：完整枚举发现至少一个跨缝位姿，并给出精确差值，直接证明本限制在候选位姿域杀解。【已证明】
- 不可行：完整枚举后跨缝集合为空，证明本限制在该模板的 H0 单体候选域免费，但不证明全局免费。【已证明】
- 超时未证：只能说明本次枚举未完成，不能改变任何价签；标准库枚举若超时，应先查实现错误而非作科学推断。【已证明】

## D2-FRONT-SEAM-PAIR：`R-FRONT-IN-REGION`

### 被判定命题

在 body 仍完全归本房的条件下，允许 active front 跨一条正交房缝，会使至少一个双房目标从不可行变可行，或严格提高双房 lexicographic packing 目标。【强论据】

### 模型伪代码

```text
REPRESENTATIVES = {
  CLEAN-CLEAN: seam (1,1)-(2,1),
  LEFT-CLEAN:  seam (0,1)-(1,1),
  BOTTOM-CLEAN: seam (1,0)-(1,1),
  CORNER-BOTTOM: seam (0,0)-(1,0)
}
for each seam in REPRESENTATIVES:
    build the two adjacent 14x14 rooms with their exact fixed masks
    for target in {body_count 8/10} x {hole 0/1} x {area C-8/C}:
        solve STRICT:
            body inside owner room
            every required active front inside owner room
            enforce all other selected R-* identically
        solve RELAXED:
            body inside owner room
            active front may occupy the 14-cell neighbor edge band
            front cell must be in-grid, body-free, and in the declared free component
            add seam-cell exclusivity and simultaneity matching
        compare feasibility, then lex objective (body area, body count, capability vector)
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| 物理缝 | 纵向 `4×5=20`，横向 `5×4=20`，合计 `40` |
| 双房网格 | `28×14` 或 `14×28` |
| 边带长度 | 每缝 `14` 格 |
| 模板与 front 需求 | 九行类表的 `r_in/r_out`，总需求常数 `574` |
| Phase-A 代表缝 | `(1,1)-(2,1)`、`(0,1)-(1,1)`、`(1,0)-(1,1)`、`(0,4)-(1,4)` |
| Phase-A 目标集 | body count `{8,10}`、孔 `{0,1}`、面积目标 `{C−8,C}`，共 `4×2×2×2=32` 对 |
| Phase-B 复现集 | 从其余 36 条缝按固定顺序取 8 条，每条只跑 Phase-A 中差异最大的一个 target |
| `C` | 两房各自 current packing ceiling 之和，只作目标刻度，不作 witness |

`C` 只能作为目标刻度，不能把 `146/134/118` 读成可行布局。【已证明】

### 规模、预算与终止

每个双房模型预计 2,000 至 4,000 个布尔变量、5,000 至 15,000 条约束；Phase A 为 32 对，Phase B 最多 8 对，共最多 40 对；每侧 10 秒，总墙钟硬上限 `40×2×10=800` 秒。【强论据】

任一 paired target 两侧都证 `OPTIMAL`，或一侧 `INFEASIBLE` 而另一侧 `FEASIBLE/OPTIMAL`，即可登记该 target；预算耗尽即停止，不补推未跑目标。【已证明】

### 三种结果判读

- 可行：relaxed 可行而 strict 不可行，或两侧均证最优且 relaxed 目标更好，证明本限制在该双房切片杀解，并给出可复现见证。【已证明】
- 不可行：relaxed 也证不可行，只否定该 target；若全部预登记 target 两侧均证最优且相同，只能说该实验网格未测出价格，不能证明全局免费。【已证明】
- 超时未证：任一配对侧 `UNKNOWN` 都不能用于 strict/relaxed 优劣判定，也不能把“没找到 relaxed witness”写成不可行。【已证明】

## D3-PORTAL-FIXED-VS-MOVABLE：`R-PORTAL-FIXED`

### 被判定命题

把每条有邻居的房边从固定两格桩改成“14 格中选择两格，邻房两侧选择一致”，会恢复至少一个当前固定桩档位没有的 valid pattern 或更优局部目标。【强论据】

### 模型伪代码

```text
for topology in {clean interior, right-rim clean, top-rim clean, top-right rim corner,
                 LEFT_J1,J2,J3, BOTTOM_I1,I2,I3,I4, fixed CORNER}:
    for target in TARGETS:
        solve FIXED with local stubs
            {(13,6),(13,7),(0,6),(0,7),(6,13),(7,13),(6,0),(7,0)} minus fixed bodies
        solve MOVABLE:
            for each live neighbor edge e and position p in 0..13: select[e,p]
            sum_p select[e,p] == 2
            selected cells are body-free and in the designated component
            pair model equates the two sides of a seam
            no stubs are required on board-rim edges
        compare valid/optimal outcomes
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| 固定局部桩 | `(13,6),(13,7),(0,6),(0,7),(6,13),(7,13),(6,0),(7,0)` |
| nominal/live | `200/180`，其中 internal `160`、board rim `20` |
| 拓扑代表 | `12` 个可求解代表：4 个 CLEAN 邻接拓扑、3 个 LEFT、4 个 BOTTOM、1 个 fixed CORNER；CORE 只记录 `NO_POSE` 诊断 |
| 目标 body count | `{8,10}` |
| 孔标志 | `{0,1}` |
| 面积目标 | `{C,C−8}`，`C∈{146,134,118}` 只作目标刻度 |
| 目标上限 | `12×2×2×2=96` 个 paired targets；CORE 不进入此乘积 |

固定家具坐标必须按 `06_geometry_constants.md` 原样加载，不能用“空房”代替边界或 CORE mask。【已证明】

### 规模、预算与终止

每模型预计 2,000 至 4,000 个布尔变量、少于 15,000 条约束；每侧 3 秒，96 对总硬上限 600 秒。【强论据】

优先跑 FIXED 证死或低目标的条目，MOVABLE 一旦找到反例即保存完整占格、桩选择和连通证书；每条仍须完成对应 strict 侧才能构成 paired 结论。【已证明】

### 三种结果判读

- 可行：MOVABLE 可行而 FIXED 证不可行，或双方证最优且 MOVABLE 更好，证明固定坐标杀了该局部解。【已证明】
- 不可行：MOVABLE 证不可行只否定该 target；全部 96 对无差异也只说明预登记目标未测到价格。【已证明】
- 超时未证：任何一侧 `UNKNOWN` 都不形成价签证据，尤其不能把 FIXED 超时视作 MOVABLE 优胜。【已证明】

## D4-PAT-CONN-PAIRED：`R-PAT-CONN`

### 被判定命题

在完全相同的局部 target 与其他约束下，strict 单根分量语义相对 loose 多源含桩分量语义会删除可行 pattern 或降低最优 packing/capability 目标。【强论据】

### 模型伪代码

```text
for class in nine non-CORE region classes:
    for area_target in {C-16, C-8, C}:
      for body_count in {8,9,10}:
       for hole in {0,1}:
        solve LOOSE:
            flood/flow may start from every live stub
            every required anchor belongs to the union of stub-bearing components
        solve STRICT:
            choose canonical free live stub root
            all live stubs, required fixed fronts, active fronts and hole cells
            belong to that one root component
        keep all body/front/power/hole constraints byte-identical
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| region classes | `CLEAN`、7 个边界类、`CORNER`，共 `9`；CORE 无 pose 单列记录 |
| 面积目标 | 每类 `C−16,C−8,C` |
| 台数 | `8,9,10` |
| 孔标志 | `0,1` |
| paired targets | `9×3×3×2=162` |
| 历史校准 | `855/2,593` 列分歧，供给 `3,113→2,749`；只作 catalog 校准 |

历史 catalog 数不能代替本实验的同目标 paired 结果。【已证明】

### 规模、预算与终止

每侧 2 秒，162 对总硬上限 650 秒；预计每模型 1,500 至 3,500 个布尔变量与同阶流变量，约束少于 15,000 条。【强论据】

每个 target 必须保留相同随机种子与决策顺序；若 strict/loose 模型除连通编码外发生差异，该 pair 作废。【已证明】

### 三种结果判读

- 可行：LOOSE 可行而 STRICT 证不可行，或双方证最优且 LOOSE 更好，直接证明 strict 单分量在该目标杀解。【已证明】
- 不可行：LOOSE 也证不可行，只说明该目标与连通放松无关；全部目标相同仍不能证明完备解空间免费。【已证明】
- 超时未证：LOOSE 或 STRICT 任一 `UNKNOWN` 都不得计入“相同”或“无价格”；现有 15 个 loose UNKNOWN 正属于此类。【已证明】

## D5-POWER-DOMINO：`R-POWER-LOCAL`

### 被判定命题

允许正交邻房杆跨缝供电，会恢复至少一个在 local-only 供电下不可行的双房 body geometry，或降低该 geometry 的最小杆数。【强论据】

### 模型伪代码

```text
REPRESENTATIVES = {
  CLEAN-CLEAN: seam (1,1)-(2,1),
  LEFT-CLEAN:  seam (0,1)-(1,1),
  BOTTOM-CLEAN: seam (1,0)-(1,1),
  CORNER-BOTTOM: seam (0,0)-(1,0)
}
for each seam in REPRESENTATIVES:
    build exact two-room fixed masks
    for target in {body_count 8/10} x {hole 0/1} x {area C-8/C}:
        solve LOCAL:
            every machine body has >=1 cell in a pole stencil anchored in owner room
        solve CROSS_ORTHO:
            a machine may use pole stencils anchored in either of the two rooms
        objective = lex(max body area, max body count, min pole count)
        if CROSS_ORTHO improves:
            freeze body geometry and solve exact minimum set cover for poles
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| 杆 body | `2×2` |
| 覆盖模板 | `[a−5,a+6]×[b−5,b+6]`，即 `12×12` |
| 正交缝 | `40` |
| 两房 pole anchors | 最多 `2×13×13=338`，再扣 fixed masks |
| 关系域校准 | total `562,500`，same-room `396,900`，orthogonal cross `151,200` |
| Phase-A 目标 | 4 个代表缝 × body count `{8,10}` × 孔 `{0,1}` × 面积 `{C−8,C}` = `32` 对 |
| Phase-B 复现 | 从其余 36 条缝按固定顺序取 8 条，每条跑 Phase-A 差异最大的一个 target |

本实验不把 `R-POLE-CAP` 当作 `R-POWER-LOCAL` 的推论；主 paired run 可固定 cap=3 作现行档位比较，发现反例后必须另跑 uncapped minimum-pole 校验。【已证明】

### 规模、预算与终止

每侧预计约 2,600 个 body/pole/flow 布尔变量、少于 10,000 条约束；Phase A 32 对、Phase B 最多 8 对，共最多 40 对；每侧 10 秒，总硬上限 `40×2×10=800` 秒。【强论据】

斜邻恢复另设 16 个四房角点小实验，每侧 10 秒，总附加上限 320 秒；它不得与正交结果重复计价。【已证明】

### 三种结果判读

- 可行：CROSS_ORTHO 可行而 LOCAL 证不可行，或固定 body 后最小杆数更少，证明 local-only 在该切片杀解。【已证明】
- 不可行：CROSS_ORTHO 也证不可行，只否定该 target；双方最优相同只说明该目标没有利用跨缝关系。【已证明】
- 超时未证：任一侧或 minimum-set-cover 校验超时，都不能声称跨缝供电必要或无用。【已证明】

## D6-POLE-CAP-3-VS-4：`R-POLE-CAP`

### 被判定命题

存在 otherwise-valid 的局部 body geometry，其精确最小本地供电杆数等于 4，且 cap=4 相对 cap=3 恢复可行性或提高最优目标。【强论据】

### 模型伪代码

```text
for class in nine non-CORE region classes:
  for hole in {0,1}:
    solve CAP3 with sum(pole_vars) <= 3
    solve CAP4 with sum(pole_vars) <= 4
    objective = lex(max body area, max body count, max capability, min poles)
    if CAP4 improves:
        freeze all body poses
        solve SET_COVER_MIN with no hard cap
        verify optimum pole count == 4
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| classes | `9` 个非 CORE 类 |
| hole | `{0,1}` |
| paired solves | `9×2×2=36` |
| local pole anchors | 空房最多 `13×13=169` |
| cap values | `3` 与 `4` |
| raw nonoverlap ceiling | `7×7=49` 根，只作搜索域尺度 |

`3,392/67/146/134/118/366` 都在 cap=3 下产生，不得作为 CAP3 优于 CAP4 的输入结论。【已证明】

### 规模、预算与终止

每侧 10 秒，36 次求解总硬上限 360 秒；每个改善候选的固定-body set cover 再给 2 秒，最多保存 20 个候选。【强论据】

若 cap=4 只通过放入可删除的冗余杆改善搜索轨迹，而 fixed-body 最小杆数不等于 4，该样本不得计入科学价签。【已证明】

### 三种结果判读

- 可行：CAP4 恢复可行或提高经证最优目标，且 fixed-body 最小杆数证为 4，证明 cap=3 杀了真实局部几何。【已证明】
- 不可行：CAP4 也证不可行只否定该目标；所有 18 pairs 证同最优只能说明所测 Pareto 面未需要第 4 杆。【已证明】
- 超时未证：CAP3、CAP4 或 set cover 任一 `UNKNOWN` 都不形成价签，不能用“CAP4 找得慢”支持 cap=3。【已证明】

## D7-HOLE-VOCABULARY：`R-HOLE-IN-REGION`

### 被判定命题

把房内孔洞词汇从 144 个 `6×7/7×6` 候选扩大为 2,025 个 `6≤w,h≤14` 候选，会恢复 valid pattern 或改善局部最优目标；另一个独立命题是允许同形跨缝会恢复双房 valid geometry。【强论据】

### 模型伪代码

```text
PART A, one room:
  for each non-CORE class:
    solve CURRENT with shapes {(6,7),(7,6)}
    solve LOCAL_ALL with every width,height in 6..14
    require exactly one distinguished hole in the local target
    compare lex(max body area, max body count, max capability)

PART B, seam domino:
  for each physical seam representative:
    solve CURRENT with hole wholly in one room
    solve CROSS with 6x7/7x6 hole allowed to cross that seam
    enforce every hole cell body-free and in the negotiated free component
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| H0 all-board rectangle witnesses | `[Σ_{w=6}^{70}(71−w)]²=4,601,025` |
| current local vocabulary | `25×(9×8+8×9)=3,600`，即 `144/room` |
| all local shapes | `25×[Σ_{w=6}^{14}(15−w)]²=25×45²=50,625`，即 `2,025/room` |
| same-shape all-board | `2×65×64=8,320` |
| seam tax | `8,320−3,600=4,720`，其中单缝 `3,760`、双缝交点 `960` |
| classes | `9` 个非 CORE 类；CORE 无 hole pose 单列记录 |

“恰 1 个 distinguished hole”是 master C3 的独立约定，多孔损失不得塞进本实验的 R-HOLE 价签。【已证明】

### 规模、预算与终止

PART A 每类每档 20 秒，总硬上限 360 秒；LOCAL_ALL 的 hole selector 从 144 增至 2,025，约 14.06 倍。【已证明】

PART B 取 40 条物理缝，每侧 5 秒，总硬上限 400 秒；若 crossing component 编码超过此预算，本条对跨缝联合价签登记为“无便宜完备实验”。【强论据】

### 三种结果判读

- 可行：LOCAL_ALL 或 CROSS 可行而 CURRENT 证不可行，或证最优目标更高，证明当前孔洞词汇在该切片杀解。【已证明】
- 不可行：放宽档也证不可行只否定该 target；全部已测条目无差异不能覆盖 4,601,025 个 H0 见证位置。【已证明】
- 超时未证：任何 `UNKNOWN` 都不能被计为“更大词汇无帮助”，也不能反推当前 6×7/7×6 已足够。【已证明】

## D8-CORE-FRONT-MASK：`R-CORE-FRONT-RESERVE`

### 被判定命题

把 CORE 的 14 个 input fronts 从“全留空”改成“至少 2 个留空”，会恢复恰好 8 个满足其余单体 mask 的 2×2 杆锚点；该命题不声称这些锚点可形成完整 CORE pattern。【已证明】

### 模型伪代码

```text
build exact fixed bodies, live portal stubs and fixed front sets
required_outputs = 46 boundary fronts + 6 core output fronts
core_inputs = 14 listed input fronts
for each region-contained manufacturing pose and 2x2 pole anchor in CORE room:
    exact54_ok = body avoids required_outputs and leaves >=2 core_inputs body-free
    all66_ok   = body avoids required_outputs union core_inputs
    apply identical BODY, FRONT, fixed-body and live-stub masks
count exact54_ok, all66_ok, and exact54_ok minus all66_ok
emit recovered anchor coordinates
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| core body | anchor `(3,59)`，`9×9`，orientation `1` |
| core input fronts | `(2,60..66)` 与 `(12,60..66)`，共 `14` |
| core output fronts | `(4,58),(7,58),(10,58),(4,68),(7,68),(10,68)`，共 `6` |
| boundary output fronts | `46` |
| true required fronts | `46+6+2=54` |
| current reserved fronts | `66=54+12` |
| CORE room | region `(0,4)`，坐标 `x=0..13,y=56..69` |

### 规模、预算与终止

少于 2,000 条单体候选记录，变量和约束为零；预算 1 秒、32 MiB，完整扫描和集合守恒断言通过即终止。【强论据】

预期恢复坐标为 `(1,60),(1,63),(1,66),(12,59),(12,60),(12,64),(12,65),(12,66)`；它们是机器复算目标，不应硬编码成算法输出。【已证明】

### 三种结果判读

- 可行：差集非空并精确为 8，证明额外 12 front reserve 在单杆锚点域有直接价格。【已证明】
- 不可行：完整扫描差集为空，证明该 proxy 下额外 mask 免费，但不证明多体 CORE pattern 免费。【已证明】
- 超时未证：扫描未完成不能支持任何结论；若零求解器枚举超时，应审计实现和输入规模。【已证明】

## D9-BOUNDARY-LAYOUT-SCREEN：`R-BOUNDARY-LAYOUT`

### 被判定命题

47 个合法无标签边界铺法中，至少一个相位在固定现行 core 时严格扩大单体候选向量，或改变 live-stub/fixed-front mask；这是一项低成本筛查，不是完整布局比较。【强论据】

### 模型伪代码

```text
enumerate one 70-cell arm:
    choose 23 nonoverlapping length-3 intervals
    classify whether corner cell is used
combine left and bottom arms, reject simultaneous corner use
assert total unlabeled occupancy arrangements == 47
for each arrangement:
    place the fixed current core
    reject fixed-body collisions
    rebuild boundary fronts, all 66 reserved fronts, live portal stubs and region classes
    enumerate M3/M5/M6/POLE single-body domains under BODY+FRONT masks
    record vector V=(M3,M5,M6,POLE,live_stubs,usable_cells)
compare each V with current phase
```

### 输入常量表

| 常量 | 数值 |
|---|---|
| 单臂长度 | `70` |
| 区间 | `23` 个长度 `3`、互不重叠 |
| 单臂铺法 | `C(70−2×23,23)=C(24,23)=24` |
| 单臂角分类 | 不占角 `1`，占角 `23` |
| 双臂合法铺法 | `1×1+23×1+1×23=47` |
| current core | `(3,59)`, `9×9`, orientation `1` |
| H0 core poses | `62×62×2=7,688` |
| 房内 core rung | `25×6×6×2=1,800` |

47 是无标签占格铺法数，不是 46 个已编号边界实例的排列数。【已证明】

### 规模、预算与终止

低成本筛查最多约 `47×56,509<2.66` 百万条单体位姿测试，预算 5 秒、128 MiB。【强论据】

完整恢复 7,688 个 core pose 会改变固定 mask、region classes，并允许 core 跨缝；它需要大规模 catalog 重生成与全局家具决策，本包没有小时级以下的完备实验，因此本条完整联合价签登记为“无便宜完备实验”。【强论据】

### 三种结果判读

- 可行：某相位的候选向量逐分量不差且至少一分量更好，证明现行相位杀了明显的单体候选；若只在不同分量互有胜负，则形成 Pareto 备选而非统治结论。【已证明】
- 不可行：完整枚举 47 相位均不优，只证明该单体 proxy 没找到更好相位，不能证明固定相位或固定 core 免费。【已证明】
- 超时未证：未完成 47 相位枚举不能排除其他相位；完整 core/layout 联合问题超预算时也不能推断当前布局必要。【已证明】

## 实验结果登记的共同防错条款

同一几何若同时因 `R-PORTAL-FIXED` 与 `R-PAT-CONN` 被删，只能登记一次联合价签，不得把相同 witness 在 D3 与 D4 的“恢复量”相加。【已证明】

`R-BODY-IN-REGION` 与 `R-FRONT-IN-REGION` 的结果必须以前者为基线、后者报增量，不能把 40.52% 与 30.46% 再相加。【已证明】

`R-POWER-LOCAL` 与 `R-POLE-CAP` 在 paired 模型中可同时固定为现行值，但实验报告必须另做 uncapped minimum-pole 校验，避免把 cap 的价格错记给 local power。【已证明】

任何 `INFEASIBLE` 只在已写明的局部模型、target、限制档位内成立，不是否定 H0 原问题，也不是完整生产不可行结论。【已证明】
