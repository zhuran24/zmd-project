# A 设计定案：供电编码手术（架构师 + 对抗审查两阶段 Fable，2026-07-09）

> 工作流 `power-encoding-surgery-design`（wf_66c62d27）。上游：M6 诊断终报（`../p1_3_m6_diagnosis_20260709/07_final_diagnosis.md`）。
> owner 拍板「a，c」后立项。本文件是批 0/批 1 的设计权威材料——批 1 动 sealed 前以此为准。

## 一、架构师报告（阶段 1）

### 候选全判

#### C6 witness 原地重编码：pairwise cover 布尔 + 半具体化几何（线性析取形态移植进坐标表示）

- **mechanism**: 核心张力的直接解法：B1 的 x≤Σcoverers 之所以线性，是因为『谁能覆盖谁』在 pose 级是静态的；但在坐标表示里，『pole slot j 覆盖 powered slot i』本身可以做成一个布尔 cover_lit[i][j]，把几何判定挂在它的 enforcement 上。具体：对每个 powered slot i（src/models/exact_coordinate_master.py:5881-5906 现在的 witness 循环处）与每个 pole slot j，建 cover_lit[i][j]，加 (a) cover_lit ≤ pole_j.active；(b) cover_lit → 4 条矩形相交线性不等式（照抄现有 _add_power_coverage_selected_geometry 的 bounds 形态 5356-5367，把 cover_choice_x/y 换成 pole_j.x/y——这 4 条正是『pole 覆盖矩形 ∩ powered footprint bbox ≠ ∅』的精确判定，footprint 全矩形由 _supports_rectangular_power_coverage 5165-5199 已保证，非矩形模板照旧走 table 路径 5201）；(c) active_i → Σ_j cover_lit[i][j] ≥ 1。这替换掉现在每个 powered slot 的 cover_choice_idx + 3×AddElement-over-变量数组（5543-5553）+选中几何的整条 witness 链。传播机制质变点：CP-SAT 对 OnlyEnforceIf 约束会在被 enforce 的线性式与当前域冲突时把 enforcement literal 直接钉 0——即『pole j 的域够不着 i』会自动变成 cover_lit=0，Σ≥1 随即收紧，这正是 M6 说缺失的反推力；而现有 AddElement 变量数组几乎不反向传播。规模：~763 powered × 763 pole slot ≈ 58 万布尔 + ~290 万短约束，粗看比现有 1.55M booleans 大，但现有 witness 的 element 在 presolve 会展开成同量级蕴含且不可学习；可用两级分块（借用已有 block_element 思路 5429-5492 但方向反过来：powered×pole-block 先粗后细）压规模。另一免费加速：pole slot active 单调链（3421-3423）使 active pole 恰是数组前缀，Σ cover_lit 的传播天然受益。
- **expected_gain**: 对照 M6 证据链推理：实验2（布局钉死仍 UNKNOWN@300s、7.2M 分支）在新编码下 powered 坐标全为常量 → 每个 cover_lit 的 4 条几何立即可判 → 问题坍缩成纯布尔 set-cover + 容量族，B1 数据（同为布尔覆盖形态，49-53s OPTIMAL / 20.6s INFEASIBLE）支持钉死判决进入秒-分钟级、且不再需要 presolve-off 特调（M6b-B 是 94.5s 且要专用火力档）。自由布局 6×6 场景保守估 5-15×（pole 侧仍是 763 坐标槽，不到 B1 双侧布尔的 34×，但冲突学习首次能落在 cover_lit 短子句上，直接攻『0.1% 冲突率无引导溺死』的病灶）。同时服务 INFEASIBLE 方向（M6c (0,0) 187s 类可提速）。
- **cost**: 改动面：exact_coordinate_master.py 单文件内 _add_geometric_power_coverage_constraints 一族方法重写（~5851-5933 及其 5299-5560 的 witness helper 群大部分退役或保留为 env 对照）、build_stats representation 字符串换新（下游有断言此 payload 的测试要跟）。reseal：完整 close-kernel 连锁（65 sealed 之一：obligations JSON、strong-status allowlist 核对、V99 floor、checker 自钉最后、LF 字节纪律）。测试面：新增等价性 A/B 单测 + 现有 power_coverage build_stats 断言更新 + preflight --full + --slow-tests；若保留旧编码为 env 回退，须走 EXACT_* 白名单三件套（allowlist/lock/tests，benders_loop.py:1332-1364 deny-unknown）。六个候选里『收益/改动比』最高。
- **soundness_analysis**: 三分类：等价。论证：现 witness 语义 = ∃ 一个 active pole slot 其覆盖矩形与 powered footprint bbox 相交（元素约束选出该 slot 后做同一组 4 不等式）；新编码 = 同一存在量词的标准布尔析取展开（cover_lit 为半具体化 witness：任一可行解中给真正覆盖者置 1 即满足，反向若 Σ≥1 则至少一个 lit 为真且其 enforce 的几何成立=真覆盖存在）。既不排除任何可行布局（不过约束）也不放进任何假布局（不欠约束）——与 element witness 逐点解等价，可在小实例上做新旧编码可行集/lex 最优值一致性 A/B 测试坐实。两个必须写进测试的细节：mandatory powered（active=None）时 (c) 退化为 Σ≥1 硬约束（对照 5243-5246 table 版已有同款分支）；cover_lit 不进 _slot_binding/cut replay 面（witness 变量本来就不在 3408-3415 的绑定表里），不动 PCR 契约。

#### C1 混合表示：杆侧 pose 级布尔 + 全局 cell 覆盖通道（mandatory 保留坐标，任务⑤+①的合体主刀）

- **mechanism**: 杆是全同 1-mode 设施（3333-3348：mode 被钉死、非 active 时坐标钉在域角落），是唯一适合单独 pose 化的族。手术：废除 763 个坐标 pole slot（3325-3442 全族：x/y/family IntVar、shell distance dx/dy/d_lo/d_hi、family lookup 表 3390-3393——每槽 ~14 变量的机器全拆），换成 p_k 布尔（k 遍历 facility_pools['power_pole'] 的 ~4.7K poses，池已被 _power_coverers_by_template_pose master_model.py:4890 与 table 编码 5207 当权威用）。覆盖通道：每格 c 建 cov[c]，加 cov[c] ≤ Σ_{k 覆盖 c} p_k（4900 条线性，系数来自 pose 的 power_coverage_cells——与 exact_campaign.py:1194 终端验证器同一数据源）；这正是 B1 34× 的 x≤Σcoverers 形态原样落在杆侧。powered 侧（坐标 IntVar）接口两选一：(i) witness cell：wx/wy 约束在 footprint 内（每轴 2 条线性，宽高用现成 _slot_footprint_width/height），flat=wy*70+wx，AddElement(flat, cov 数组, 1) 挂 active_i——每 powered slot 只剩 1 个 element 且指向全局共享的 cov 数组（跨设施学习可迁移）；(ii) C6 的 pairwise 形态但对 pole-pose 常量盒半具体化。重叠：每个 pole pose 是常量矩形，以 presence=p_k 的常量 OptionalIntervalVar 注入现有 AddNoOverlap2D（3467-3468）——注意这会给最重传播器加 4.7K 固定 interval，需实测；替代路是杆间 AtMostOne per cell（pose_bool_exact_master.py:581-583 现成写法）+ 杆-设施重叠单独编码。容量族简化红利：family 成员静态化（每 pose 的 family 编译期定死），count_var == Σ p_k∈family 纯线性，shell lookup 表全退役；6299-6304 的杆数上界照搬。
- **expected_gain**: 六候选中理论上限最高：两侧覆盖逻辑全布尔化后与 B1 证据形态同构（34× 的直接对应物），且顺手消灭 M6 出土的三个次级负担——763×14 变量的槽机器、family shell lookup 表、『30GB RAM 真凶』注释（2100-2103）指的槽上界浪费。钉死场景（M6 实验2）预计秒级；自由 6×6 预计进入 B1 量级（分钟内首解或 INFEASIBLE）。风险敞口：4.7K 常量 interval 进 no_overlap 的传播代价未实测（可能吃掉部分收益），与 763 element 换 1 shared-array element 的净效应需批0 原型验证。
- **cost**: 六候选中改动面第二大（仅次于 C5）：槽创建/绑定/对称链/容量族/extract_solution 的 pole 分支全动；_slot_binding 里 pole 条目形状变（3408-3415）→ from_exact_core 克隆路径与 proposal 材料里引用 pole slot key 的面要全查（L4a 注释 3445-3450 明示 cut runtime literal 对 pole slot 敏感——杆虽留在 master 但换了名字空间，candidate_proof_replay/强状态面要过一遍）。reseal 完整连锁 + slow lane + 等价性 A/B 测试 + pose 池完整性 assert 新测试。工期估 C6 的 2-3 倍。
- **soundness_analysis**: 三分类：等价，但挂在一条必须机器检查的引理上——『pose 池 = 杆槽坐标域的完整格点枚举』。若 candidate_placements 的 pole 池在域边缘有裁剪差异（哪怕缺 1 个格点），新编码就是过约束（危险：排除真可行布局→威胁穷尽性）。缓解：build 时 assert 池枚举与 _template_full_mode_rect_domains['power_pole'] 的格点集一一对应，不对则 fail-closed（照 additive-only 检查的先例）。第二引理：常量 interval 注入 no_overlap 与原 763 槽可变 interval 语义等价（枚举方向：任意杆布局 ↔ 唯一 p 向量，两侧互模拟，杆数 ≤763 由 6299 上界继续保证——p 表示天然无槽数上限问题，反而消掉了 763 这个 worst-case 常量）。witness-cell 接口 (i) 的等价性：footprint 全矩形 ⇒ 『∃占用格被覆盖』⇔『∃ footprint 内格 c 且 cov[c] 可为 1』⇔ element 可满足；cov 只有 ≤ 方向不会虚报覆盖（cov[c]=1 强制 Σp≥1）。既不欠约束（cov 无假阳性）也不过约束（任意真覆盖可令对应 cov=1）。

#### C3 保留 witness + 强传播冗余有效不等式（窗口化杆数下界 / Hall-式密度 / 容量族区域化）

- **mechanism**: 不动 witness 本体，在 _add_global_valid_inequalities（5935 起）新增蕴含式家族。三个具体族：(a) 窗口杆数下界：把全局唯一的容量下界 Σ coeff_family × count_var ≥ demand（6340-6362，现在只有每 template 一条全网级）区域化——对固定窗口网格 W（如 10×10 分块），powered slot 的 region literal（2792-2798 已现成把 (mode,x,y) 绑到盒子）给出『被迫落在 W 内』的布尔证据，杆侧补 tile 隶属布尔（763 槽 × ~49 tile 的盒式半具体化，同 _add_region_constraints 2740-2745 写法），加 Σ_{i 的 region⊆W} region_lit_i 的需求 ≤ 覆盖惠及 W 的 tile 内杆数 × 容量系数上界。(b) Hall-式：多个 powered 区域的膨胀窗口并集小时，并集内杆数 ≥ ⌈需求/单杆容量上界⌉。(c) 把 ghost 三 tightener 之一的 power capacity screen（3765-3767 调用，现为 anchor 条件化的建模期筛）从 screen 升级为模型内窗口不等式。膨胀窗口 D(R) 的几何引理直接复用 5356-5367 的 4 不等式常量化：pole 锚点必在 R 按 radius+最大跨度膨胀的盒内。
- **expected_gain**: 对照 M6：机制段说 witness 的病是『每步看起来还行、深处才发现覆盖格局挤死』——窗口下界恰好把『挤死』提前到浅层（打包决策一旦让某窗口 powered 密度超过其膨胀窗杆容量上限，立即冲突且学到 region_lit 级短子句）。但它不解决 witness 本体的 element 布尔海洋与 763 槽机器，M6 实验2（钉死仍溺死）表明单靠它大概率不破墙——定位是辅助刀，估 2-5×，对 INFEASIBLE 方向（存在性 OPEN 问题、(0,0) 类角落锚）收益比 FEASIBLE 方向大，和终报副产物2『F1/F6 类 cut 可提前剪』呼应。
- **cost**: 六候选中最低：纯增量（不改任何既有约束），代码集中在 valid-inequality 区 + 新 tile literal helper；37K 级新布尔可控。仍是 sealed 文件改动 = 完整 reseal 连锁，但无表示变化、无 cut/extract/绑定面影响、build_stats 只增不改。测试面 = 每族蕴含性单测 + 常规门禁。适合作为 C6/C1 之上的第二批叠加，而非独立主刀。
- **soundness_analysis**: 三分类：等价（合法蕴含不等式——每条都是现有约束系统的逻辑推论，可行集不变）。但这是三分类里最容易『写错一条就滑进过约束』的地带，两个具体危险点要逐条出示引理：(1) 容量系数方向——_power_pole_family_coefficients 在 6360 已被当『单杆最多供养数上界』用于 ≥ 下界，方向正确；窗口化时需 restriction 单调引理（杆限制在窗口内其容量只减不增，成立）。(2) 『被迫落在 W』的判定必须只用 region literal 为真的分支（region_lit → 在盒内是半具体化方向，安全），不能用域推断的『大概在』。每条不等式配一个独立单测：随机小实例上加与不加解集一致。

#### C4 杆域收缩 + 对称破缺强化（安全部分：克隆链强化；危险部分：槽上界收缩；条件安全：有用杆 dominance）

- **mechanism**: 三个子件分开评审。(a) 克隆链强化【安全】：现有杆槽链只有 active 单调 + family 单调 + 同 family 内 order_key 单调（3421-3432）。补『同 family 且相邻槽的 (x,y) 字典序』或把 order_key 链升级为全局字典序，进一步压 763 全同槽的置换空间；同时给 witness 选择加前缀域收缩（active 前缀性质使 cover_choice_idx 的有效域 = 前缀，可显式加 cover_choice_idx < Σ active 的蕴含）。(b) 槽上界收缩【危险】：EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE（2106-2113）的 certified 化——源码注释自己写明『若实例真需要 > override 个 pole，master INFEASIBLE 假阳性』（2103）。(c) 有用杆 dominance【条件安全】：杆 active → 至少覆盖一个 powered。关键源码事实：终端认证验证器已经强制比这更严的条件——exact_campaign.py:1243-1253 要求每个杆是至少一个 powered 的唯一覆盖者、且杆数 ≤ powered 数，否则 unforced_power_pole_instance fail-closed；即发布面早已只接受『每杆有用』的解。
- **expected_gain**: (a) 分支数常数因子削减（M6 实验2 的 7.2M 分支中相当份额是全同槽置换与 witness 指派自由度），单独不破墙；(c) 在 witness 表示下编码贵（需 763×763 具体化『被谁引用』），在 C1 的 p_k 表示下几乎免费（p_k ≤ Σ 覆盖范围内 powered 占用证据）——所以 (c) 应作为 C1/C6 落地后的搭车项而非独立批次。整体定位：抛光件，预期 1.5-3×。
- **cost**: (a) 极小（对称区几十行）+reseal 连锁；(b) 判死不计；(c) 中等且依赖主刀选型，另需把 dominance 论证写进 docs/proof obligations（checker 锚点面 check_p1_2_proof_obligations 可能要登记新义务）。
- **soundness_analysis**: (a) 等价：全同克隆槽的置换 WLOG，是既有链（3421-3432）的同类延伸，逐条可证。(b) 过约束（危险，不推荐 certified 化）：除非附带实例级『所需杆数上界』的机器可查证明，否则直接威胁穷尽性主张——INFEASIBLE 证明在收缩域上不成立于原问题。若真要用，只能做成阶梯（收缩域 FEASIBLE 可信、INFEASIBLE 必须回退全域复证——而复证恰是原墙，等于白干），故判死。(c) 表面过约束、实为 objective-preserving dominance：任意可行布局迭代删除非唯一覆盖杆——删除只释放格子（no_overlap 单调放松）、被删杆当时不是任何人的唯一覆盖者所以覆盖谓词保持、杆自身不需供电（6290 显式排除 power_pole 于 powered 集）、杆无端口所以 binding/routing 不受影响、ghost 矩形不变——终态满足约束且 lex 目标不变。所以加进 master 不排除任何『目标值可达』的布局，穷尽性对 lex-最优主张成立；但严格说 master 可行集变了，dominance 引理必须写进 proof obligations 文档并配测试，属于『需 owner 认可的论证升级』而非纯等价。

#### C2 签名桶/region literal 粒度粗覆盖蕴含（a=冗余叠加【等价】；b=替换 witness【欠约束+下游闭环】）

- **mechanism**: 利用已存在的 region literal 基建（2777-2822：每 slot×bucket×region 一个盒式布尔，且有 AddExactlyOne 完备划分 2820）。C2a：保留 witness，对每个 powered slot 的每个 region R 加必要条件 region_lit ∧ active → Σ_{杆 tile ⊆ D(R)} 杆 tile 隶属布尔 ≥ 1，其中 D(R) = R 按 radius+footprint 膨胀（与 C3 共享杆侧 tile literal 基建）。C2b：走 EXACT_LAZY_POWER_COMPLETION 的既有结构（3477-3486：留杆槽、跳几何 witness，build_stats 记 lazy_power_completion_v1）但不再裸跳——把 C2a 的粗必要条件 + 容量族留在 master 当『近似覆盖引导』，真覆盖交给 completion 子问题闭环 + 割回灌。
- **expected_gain**: C2a 单独：与 C3 同量级（2-5×，region 级短子句）。C2b 若闭环收敛：master 侧回到 M6b-A 形态（2.6-5.3s OPTIMAL）+ 引导后的少轮 completion——总收益潜在最大但方差也最大（L16 前科）。
- **cost**: C2a：低-中（与 C3 共享基建，纯增量+reseal）。C2b：高且不止代码——unsafe-map 解封 + 割生命周期依赖（step_8_apply_to_master 仍 NotImplementedError，src/cuts/lifecycle.py:1121-1126，恰是 P1.3 主线未完件）+ 收敛性无先验保证。C2b 不该进默认计划，留作 C6/C1 都失败后的 owner 拍板升级项。
- **soundness_analysis**: C2a：等价（蕴含冗余，同 C3 的论证纪律，膨胀几何引理逐条证）。C2b：欠约束——master 可行集是真可行集的严格超集，master『解』可能覆盖不可行。下游闭环三层盘点：(1) 提案层——certified 链正常终点是 CANDIDATE_PROPOSED，supervisor seal 的隔离子进程重验 + 终端验证器 exact_campaign.py:1237-1238 对覆盖缺失 fail-closed（power_coverage_missing），所以假 CERTIFIED 不可能发生，soundness 底线在；(2) 收敛层——真正的风险不是 soundness 是活性：L16 历史（B1 README 对比表）master 81s OPTIMAL 但 completion cut 10 轮不收敛总 wall 15min 死；(3) 语义层——解封 EXACT_LAZY_POWER_COMPLETION 本身在 certified unsafe-map（benders_loop.py:962-965 lazy_power_completion_not_certified），是 owner 级语义决定。C2b 的新赌注 = C2a 粗条件让 master 提案『几乎可覆盖』从而 completion 少轮收敛——有逻辑但无实验证据，且 M6 副产物1（盲打包解全部供电不可行）提示引导不足时提案质量极差。

#### C5 整表示切换：PoseBoolExactMasterDelegate 生产化升格（终极手段）

- **mechanism**: 现成整机存在：src/models/pose_bool_exact_master.py（1410 行）已实现 pose-bool master 全家（覆盖约束即线性 x≤Σcoverers，595-623；cell exclusivity AtMostOne 581-583；ghost 族 585），由 EXACT_USE_POSE_BOOL_MASTER 切换（master_model.py:2595-2606），B1 Phase 0 实测 53s OPTIMAL（~34×）且 end-to-end 试跑 master+binding 已通。手术 = 把它从 unsafe-map（benders_loop.py:954-957）升格为 certified 默认表示。
- **expected_gain**: 34× 直接证据背书，六候选中确定性最高的性能路径（C-PB 消融 cell 就是它的 6×6 验证器）。但收益与 C1/C6 大部分重叠——若 C6/C1 已破墙，C5 的边际收益只剩表示层统一。
- **cost**: 全项目最大：双表示并存的维护税或整链迁移（extract/hint/cut/replay/verifier/供应材料五个面，B1 README Phase 2 audit 列了改动点但那是 exploratory 视角，certified 化还要加 PROJECT_LOCK 文本、unsafe-map 重画、全部 slow-soundness lane 重跑）。留作战略备胎：仅当 C6 与 C1 在批0 头对头都不达门时，作为 owner 拍板的表示层换代提案。
- **soundness_analysis**: 目标等价（两表示都以 candidate_placements 冻结池为placement 权威），但穷尽性重审面全项目最大：坐标表示的整套证明材料形状（slot binding、cut runtime literal、proposal replay、verifier child 的期望）都以坐标语义写成；历史 5 条 6×6 cut 本就是 pose 表示产物（01_ablation_map 硬事实）说明 cut 可迁移但要重审 replay 契约；B1 README Phase 6.2 证明『master 持端口选择』死路 → 端口/路由必须留在子问题，边界责任要重新画。这不是一个编码改动，是 PCR-* 条款级的表示层决定——正因如此 M6 修复方向 A 的措辞是『线性形态或其他强传播编码』而不是『切 pose-bool』。

### 架构师推荐

主刀选 C6（witness 原地重编码为 pairwise cover 布尔 + 半具体化几何）：它是核心张力的最小解——不需要把设施位置离散成 pose 布尔，就把 B1 证据里真正起作用的『线性覆盖析取 + 可学习布尔』形态原样移植进坐标表示；soundness 三分类里是最干净的等价（同一 ∃-witness 语义换编码，可用小实例新旧一致性 A/B 机器验证），改动面收在单文件的 witness 方法族内，不碰 slot 绑定/cut replay/验证器契约。C1（杆侧 pose 化 + cell 覆盖通道）作为同场对照的备刀：理论上限更高（与 B1 34× 形态同构、顺手拆掉 763×14 槽机器），但等价性挂在 pose 池完整性引理上且改动面大 2-3 倍——两者在批0 用 M6 已打通的钉死验证管线头对头实测后再定胜者，不预先押注。C3 窗口化有效不等式与 C4a 对称链强化是低成本辅助，跟批装载；C4b 槽上界收缩判死（源码自认假 INFEASIBLE 风险，威胁穷尽性）；C4c 有用杆 dominance 是 C1/C6 落地后的搭车项（终端验证器 exact_campaign.py:1243-1253 已在发布面强制同条件，master 侧对齐它有 dominance 引理护航但需 owner 认可论证升级）。C2b（lazy completion 解封）与 C5（整表示切换）都是 owner 级语义决定 + 大方差路径，明确排除出默认计划、留作两级升级备胎。这个排序同时守住红线：批0 全程不碰 sealed 文件、结果不回流 certified；批1 才进 reseal 连锁，且过约束类候选一个都不放进 certified 路径。

### 批次计划（架构师版）

批0【研究原型，不碰 sealed，~3-5 天】：在 docs/research 新课题目录建原型 harness（骨架抄 m5_cell_runner/m5_ablation_runner 纪律：create 后设开关、重建 core、JSON 透明记录、w12+42G 硬帽、一次一个），用子类/monkeypatch delegate 方式实现 C6 与 C1 两套编码原型，各自可叠加 C4a 对称强化旋钮。验收门 G0.1：M6 实验2 复刻（greedy 钉死布局）在默认火力下 ≤120s 给出 FEASIBLE/INFEASIBLE 判决（基线：presolve-off 特调 94.5s、默认档 300s+ UNKNOWN）；G0.2：6×6 全锚自由布局 600s/w12 内首解或 INFEASIBLE（基线全 UNKNOWN）；G0.3：build 规模 ≤2× 基线 booleans（proto 直方图对照）；G0.4：任何 FEASIBLE 解必须过独立覆盖复验脚本（照 exact_campaign.py:1227-1253 逻辑重写，不 import 生产码）。两候选都过门→选改动面小的 C6；只 C1 过→C1；都不过→把 G0 数据打包呈 owner 拍板 C2b/C5 升级。批1【生产落地，reseal 量级，~1 周】：胜者编码进 exact_coordinate_master.py 作为 certified 默认（旧编码若保留为对照需走 EXACT_* 白名单三件套），新旧编码等价性单测（随机小实例可行集+lex 最优值一致）+ build_stats representation 断言更新 + 完整 reseal 连锁（obligations→allowlist→V99→checker 自钉最后，LF 字节纪律，提交 pathspec 覆盖全集）。验收门 G1.1：preflight --full 与 --slow-tests 全绿 + 两 checker 通过输出达标；G1.2：6×6 战场复跑破首解之墙（判决落地，UNKNOWN 消失）；G1.3：M5 收敛 A/B 解锁（终报排期条款兑现）。批2【可选增强，按需】：仅当批1 后首解时间仍 >10min 量级时投入——C3 窗口化下界与 C4c 有用杆 dominance 各自独立 A/B（同 G0 阶梯），每条蕴含不等式配蕴含性单测；C4c 需先把 dominance 引理写进 proof obligations 并请 owner 认可。升级备胎（不排期，触发条件=批0 双败或批2 后仍不达标）：C2b lazy completion 解封（依赖 cut lifecycle step_8 通电，恰是 P1.3 主线）与 C5 pose-bool 表示换代，均为 owner 拍板项。

## 二、对抗审查报告（阶段 2）

### 逐候选判定

#### C6 witness 原地重编码（pairwise cover 布尔 + 半具体化几何） — **SOUND**

- **reasoning**: 等价性主张经对抗核查成立：现 wide-element witness 语义（exact_coordinate_master.py:5569-5608 的 cover_choice_idx + 3×AddElement + 5391-5402 四不等式，mandatory 分支 Σ≥1 对照 5277-5281）就是『∃ active pole 其覆盖矩形∩powered footprint bbox≠∅』，C6 是同一存在量词的标准布尔析取展开；且仓库里已有同语义 pairwise 先例——table 路径 5236-5287 本来就是 cover_lit 编码（5265 cover_lit≤pole.active、5279 Σ≥1）。几何判定与 B 层（exact_campaign.py:1231-1238 用 occupied cells×power_coverage_cells 精确复验）在矩形 footprint 前提下一致，该前提由 _supports_rectangular_power_coverage(5200-5234) 门控且它同时校验 pose 的 coverage_cells=全裁剪矩形。找过约束路径：未找到——任一真覆盖者置其 lit=1 即满足，半具体化方向（lit→几何）不排除任何可行布局。找欠约束路径：只有一条且架构师已含解法——(a) cover_lit≤pole_j.active 是 soundness 关键而非优化：inactive pole slot 坐标被钉在域角落（3349-3350），漏掉 (a) 会让角落附近的 powered slot 拿假覆盖（欠约束，seal 层才被拦）。三个修正：①『改动面收在单文件』不成立——benders_loop.py:985-999 的 _CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS 把 certified witness 编码 env 钉死在 canonical 值，换默认编码必动 benders_loop 常量+allowlist 测试，reseal pathspec 要含它；②架构师引 5243-5246/5543-5553 等行号有轻微漂移（实际 5277-5281/5586-5588），语义引用无误；③『非矩形模板照旧走 table』表述不准——现 dispatch 是全有全无（5890-5891），不是按模板分流。附带条件：小实例新旧可行集+lex 值 A/B 等价测试、G0.3 规模门（582K lit + ~2.9M 半具体化约束非小数目，性能是实验问题不是 soundness 问题）。

#### C1 混合表示（杆侧 pose 布尔 + 全局 cell 覆盖通道） — **RISKY**

- **reasoning**: 等价性挂在两条引理上，第一条我已实测坐实为当下为真：candidate_placements.json 的 power_pole 池 = 4761 poses = 完整 69×69 anchor 格阵（直接读工件验证，x/y 均 0-68 无缺格），且中位 pose coverage_cells=144=12×12 与 radius=5 一致——但注意默认 shell-lookup 编码（2090 置 True、3353-3398）下坐标杆 (x,y) 域是完整矩形域、并不受池约束，两表示相等恰恰只因池=全格阵，所以 build 时 fail-closed 断言（池↔_template_full_mode_rect_domains['power_pole'] 格点一一对应）绝不可省，工件一换即是穷尽性破口。第二引理（常量 interval 注入 no_overlap 与 763 可变槽互模拟）论证成立，且 p_k 表示消掉 763 槽帽反而移除一个潜在过约束源（帽本身依赖 6334-6339 同款 dominance 包络）。风险留存三处：(i) witness-cell 接口对非矩形 footprint 的 bbox 洞是欠约束（与现 5200-5210 注释同一坑），必须保留同款矩形门控；(ii) _slot_binding 的 pole 条目（3408-3415）形状变，proposal/replay 契约面全查——好消息是 F7 cut attach（7296-7384）实际解析的是 pose 池 coverer 表+powered pose literal 而非 pole slot，割面暴露比架构师担心的窄；(iii) 4.7K 常量 interval 进最重传播器、763 element 换共享 cov 数组 element 的净效应无实验数据（element 恰是 M6 钉死的弱传播机制，共享数组能否质变是批0 要回答的空问题）。批0 头对头定位正确。

#### C3 冗余有效不等式（窗口杆数下界/Hall/screen 升级） — **RISKY**

- **reasoning**: 『合法蕴含不等式=可行集不变』的大方向对，但对抗审查找到两条具体的过约束滑坡，均是『写错一条就排除真布局』级：(1) tile 包含方向——杆数下界类（(a)(b)）若按『tile⊆膨胀窗 D(W)』计数，anchor 落在跨 D(W) 边界 tile 里的真覆盖杆无 lit 可计，真可行布局被判违约→过约束；下界方向必须用『tile∩D(W)≠∅』的超集计数（代价=不等式变弱但保真）。上界计数方向恰相反。每条不等式的包含方向要单独出示引理，不能一句『同 2740-2745 写法』带过。(2) 膨胀几何的非对称 off-by-one——2×2 杆使 anchor 盒为 [cell-r-1, cell+r]（每轴负向 r+1、正向 r），这正是现 5391-5402 常量里 '+2+radius-1' 与 '-radius' 的不对称来源；任何按对称 r 膨胀的新窗口都会把 x0=cell-r-1 的真覆盖杆排除。架构师『复用 4 不等式常量化』的本能对，但引的 5356-5367 行号偏了且未点破不对称本身就是陷阱。另核实：powered 侧 region literal 有 ExactlyOne 完备划分（2803/2817/2820）故 LHS 计数被强制为真值且是安全的低估方向；容量系数下界族先例真实存在（6334-6339 及 6377 起的 per-template ≥demand 族）。定位为批2 辅助刀正确，但每条不等式除蕴含性单测外必须加随机小实例加/不加解集一致 A/B——单测验的是『我写的这条』，A/B 验的才是『我以为的那条』。

#### C4a 对称链强化 — **RISKY**

- **reasoning**: 三个子件里两个没内容、一个如字面执行是 UNSOUND：(1)『同 family 相邻槽 (x,y) 字典序』——order_key 就是 x·scale_x+y·scale_y+mode（2553-2560、2703-2710），杆 mode 被钉死（3348），故同 family order_key 单调链（3429）已经就是 (x,y) 字典序，此项=纯冗余零增量。(2)『order_key 链升级为全局字典序』——过约束实锤：family=shell 距离是 (x,y) 的环状水平集函数，对 lex 序必然非单调；现有 family 单调链（3423）与全局 lex 链并存时，任何含 family 序/lex 序不一致杆对的布局（如边缘壳杆 (0,34) 与内部壳杆 (34,34)）在槽指派上两链必违其一→该杆多重集整体不可表示→排除真可行布局、威胁穷尽性。除非同时拆掉 family 链并重证（架构师未提），此子件判死。(3) cover_choice_idx<Σactive 前缀不等式——有效推论（active 前缀性质 3421-3422 + 选中槽必 active），安全但在 C6 落地后 witness 索引变量整个消失，此项失效。净评估：C4a 作为『跟批装载的安全抛光件』的定性不成立，应从计划中降为『仅保留(3)且仅当主刀不是 C6』。

#### C4b 槽上界收缩 certified 化 — **UNSOUND**

- **reasoning**: 与架构师判死一致，证据链完整：源码注释自认『若 instance 真需要 > override 个 pole，master INFEASIBLE 假阳性』（exact_coordinate_master.py:2100-2103），且 EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE 已在 certified unsafe-map（benders_loop.py:958-961，'tightens the certified master domain'）——项目自己的 fail-closed 体系已把它定性为收缩 certified 域。INFEASIBLE 证明在收缩域上对原问题不成立，直接击穿 lex-最优穷尽性主张；『收缩域 FEASIBLE 可信/INFEASIBLE 回退全域』的阶梯方案回退步恰是原墙，架构师『等于白干』的自判成立。维持判死，不得进 certified 路径，诊断/研究用途照 unsafe-map 纪律。

#### C4c 有用杆 dominance — **RISKY**

- **reasoning**: dominance 引理本体经对抗核查站得住且有仓内先例：终端验证器条件确认为『每杆是至少一个 powered 的唯一覆盖者且杆数≤powered 数』（exact_campaign.py:1243-1253，镜像 pr2_l0_artifact_core.py:1036-1045）；master 里已存在同类 dominance 依赖的不等式——Σ杆active≤powered 总数（6334-6339），说明这个论证等级已被 certified master 接受过，不是全新论证类别。迭代删除论证的空洞补查：杆不在 powered 集（5179-5192、6291 均排除 power_pole）✓；『杆无端口/不参与 routing』两个子前提我未在源码逐一验证，必须作为引理义务写明并配测试，不能像架构师那样默认。但发现一个架构师漏掉的关键错位：C4c 的 master 约束（杆→覆盖≥1 个 powered）严格弱于验证器要求（唯一覆盖者）——两杆互相冗余地覆盖同一组设施时 C4c 满足而验证器照拒，所以 C4c 单独并不能消除 seal 拒绝风险（见 blocking issue：全链缺解级 dominance 剪杆步）。定位修正：真正该做的是提案前的解级剪杆（对具体解迭代删非唯一覆盖杆，验证器全量重验兜底、soundness 零风险），master 侧 C4c 降为可选传播增强；两者都需 dominance 引理进 proof obligations + owner 认可论证升级。

#### C2a region 粗覆盖蕴含（冗余叠加） — **RISKY**

- **reasoning**: 概念可救但字面公式含过约束反例：『region_lit∧active→Σ_{杆tile⊆D(R)}≥1』——真覆盖杆的 anchor 必在 D(R) 内（膨胀算对的前提下），但它所在的 tile 可以跨出 D(R) 边界，此时无任何『⊆D(R)』的 tile 含它，真可行布局的真值扩展给出 Σ=0<1→该布局被模型判死→过约束、威胁穷尽性。修复方向明确：求和范围改『tile∩D(R)≠∅』（跨界 tile 里非覆盖杆会造成松弛，不等式变弱但保持有效）。加上与 C3 共享的膨胀不对称陷阱（anchor 盒负向 r+1 正向 r，见 5391-5402 常量），C2a 的每条蕴含都要逐条出示两个引理（包含方向+膨胀常量）并配蕴含性单测+小实例 A/B。powered 侧 region literal 基建本身可信（2803 sum-channel + 2817/2820 ExactlyOne 使真值被强制）。作为 C6/C1 之上的批2 叠加可以，但『低-中成本』定价应上调：证明纪律成本才是大头。

#### C2b lazy completion 解封 + 粗引导 — **RISKY**

- **reasoning**: 欠约束候选的下游兜底核实：真实且双层——seal 隔离子进程与终端验证器对覆盖缺失 fail-closed（exact_campaign.py:1237-1238 power_coverage_missing，镜像 pr2_l0_artifact_core.py），假 CERTIFIED 无路径，soundness 底线在。但架构师『走既有结构』的说法经全仓 grep 击穿：EXACT_LAZY_POWER_COMPLETION 在 src 里只有 master 侧跳过 witness 的分支（3477-3486）、unsafe-map 条目（benders_loop.py:962-965）和两个测试——completion 子问题本体不存在，仓里唯一的供电子问题机器是 L4a 禁用的 delegated 路径（whole-layout nogood，benders_loop.py:5674-5686），其割形态正是 B1 README 记载 L16 十轮不收敛死掉的那个。所以 C2b 实际=从零建 completion 子问题+割回灌（step_8_apply_to_master 仍 stub，lifecycle.py:1162 与模块 docstring L15）+owner 级 unsafe-map 解封+对抗 L16 收敛前科，三重依赖叠加。M6 副产物1（盲打包解全灭）进一步压低『粗引导后少轮收敛』赌注的先验。同意排除出默认计划；若启用，激活条件应加一条：C2a 粗条件先在批2 独立验证有正收益。

#### C5 PoseBoolExactMasterDelegate 生产化升格 — **NEEDS_EXTERNAL_REVIEW**

- **reasoning**: 34× 性能证据真实（B1 README 五 anchor 实测表），但 certified 化的穷尽性重审面是全项目最大且有一条现成的定性反证：unsafe-map 给它的封禁理由就是『pose-bool master does not construct the certified full ghost-anchor domain』（benders_loop.py:954-957）——按现状它连 certified 所需的完整 ghost anchor 域都不构造，穷尽性 by construction 不成立，升格是补建+重审整个表示层而非解封。另两条硬事实支撑降级处理：(i) B1 原型 scope 明示 residual optional powered 覆盖等面未完整（README scope 段），residual powered 模板的覆盖约束在 581-623 的 mandatory/required_optional 循环之外；(ii) 历史 5 条 6×6 cut 是 865-instance 旧 pose 表示产物（01_ablation_map L31-32），cut/replay 契约需整体重画。这是 PCR-* 条款级表示层换代，owner 拍板+外部审查是正确归属；同意仅作双败备胎。若真触发，评审重心=ghost anchor 域完整性与 proposal/replay/verifier 三面契约迁移，而非覆盖编码本身。

### 阻断性发现（blocking issues）

1. 【全链级，架构师计划未覆盖】master→seal 之间不存在任何冗余杆剪除步：extract_solution（exact_coordinate_master.py:6798-6854）原样输出所有 active 杆、outer_search 对 power_pole 零处理（grep 零命中），而两层验证器都要求每杆是某 powered 的唯一覆盖者（exact_campaign.py:1243-1253、pr2_l0_artifact_core.py:1036-1045），master 任何编码（含 C6/C1）都不阻止冗余杆——G1.2『破首解之墙』的解走到 seal 会以 unforced_power_pole_instance 被拒。批1 必须加：提案前解级 dominance 剪杆（对具体解迭代删非唯一覆盖杆；验证器全量重验兜底、soundness 零风险）+ dominance 引理登记进 proof obligations。

2. 【G0.4 验收门设计错误】批0 独立复验脚本若照抄 exact_campaign.py:1227-1253 全段，会把合法的含冗余杆 master 解误判为失败——批0 门只应检覆盖（1227-1238），unforced 检查（1243-1253）单独记录不作门。

3. 【C6 reseal 全集缺项】benders_loop.py:985-999 的 _CERTIFIED_POWER_WITNESS_CANONICAL_ENV_DEFAULTS 把 certified witness 编码 env 钉在 canonical 值——换默认编码必动 benders_loop 常量与 env allowlist/lock/tests 三件套，『改动面收在单文件』不成立，批1 提交 pathspec 与 reseal 连锁要把它计入。

4. 【C6 实现红线】cover_lit ≤ pole_j.active 是 soundness 必需项而非优化：inactive 杆槽坐标钉在域角落（exact_coordinate_master.py:3349-3350），漏掉它=角落附近 powered slot 可拿假覆盖（欠约束）；必须配一条『inactive 杆不得作证人』的针对性单测。

5. 【C4a 判词修正】『order_key 链升级为全局字典序』与 family 单调链（3423）冲突：family=shell 距离对 (x,y) 字典序非单调，两链并存使 family/lex 序不一致的杆对布局整体不可表示=过约束判死；『同 family (x,y) 字典序』则已被 order_key（=x·scale+y·scale+mode，2553-2560）链 3429 蕴含=零增量。C4a 从『安全抛光件』降为基本无内容，不再跟批装载。

6. 【C3/C2a 两条必写引理】(1) tile 包含方向：杆数下界类不等式的计数范围必须是『tile∩膨胀窗≠∅』超集而非『tile⊆膨胀窗』——字面版会把 anchor 在跨界 tile 的真覆盖杆排除（过约束反例已构造）；(2) 膨胀不对称：2×2 杆使 anchor 盒为每轴 [cell-r-1, cell+r]（对应 5391-5402 的 '+2+radius-1'/'-radius' 常量），对称 r 膨胀=off-by-one 过约束。每条新不等式配蕴含性单测+随机小实例加/不加解集一致 A/B。

7. 【C2b 事实纠正】completion 子问题在仓内不存在（EXACT_LAZY_POWER_COMPLETION 只有 master 跳过分支 3477-3486；唯一供电子问题机器是 L4a 禁用路径 benders_loop.py:5674-5686），step_8 仍 stub（lifecycle.py:1162）——『走既有结构』表述失实，激活成本按从零建设估。

8. 【C1 前置断言不可省】pole 池今天恰=完整 69×69 格阵（4761 poses，已实测 candidate_placements.json 坐实），但默认 shell-lookup 编码下坐标杆 (x,y) 域不受池约束（2090、3353-3398），等价性纯靠池=全格阵这一工件事实——build 时池↔域格点一一对应的 fail-closed 断言必须与 C1 原型同批落地，工件演化即是穷尽性破口。

### 修订后建议（定案）

维持架构师主线但做五处修订。主刀仍选 C6（唯一 SOUND 判定：与现 witness 逐点等价可机器验证，且 table 路径 5236-5287 本就是同语义 pairwise 先例），C1 作批0 头对头备刀（RISKY：池完整性引理已实测当下为真，但 fail-closed 断言必须随原型同批落地）——这两条按原批0 计划实测定胜者。修订一（最重要，架构师漏项）：批1 范围必须加『提案前解级 dominance 剪杆』——两层验证器（exact_campaign.py:1243-1253 / pr2_l0_artifact_core.py:1036-1045）要求每杆是唯一覆盖者，而 master 任何编码都不阻止冗余杆、extract 到 seal 之间无任何剪除步，不加此步则破墙之解到 seal 必死；解级剪杆由验证器全量重验兜底、soundness 零风险，同时把 dominance 引理写进 proof obligations（此步吸收 C4c 的核心价值，master 侧 C4c 降为可选传播增强）。修订二：G0.4 只用覆盖检查（1227-1238）作门，unforced 检查记录不判死。修订三：C6 批1 reseal 全集加 benders_loop.py:985-999 canonical env 面与 EXACT_* 三件套；实现红线 cover_lit≤pole.active 配针对性单测。修订四：C4a 从跟批清单移除（同 family lex=order_key 链已有的零增量；全局 lex 升级=与 family 链冲突的过约束，判死；前缀不等式在 C6 下失效）。修订五：批2 的 C3/C2a 每条不等式必须先出示 tile 包含方向引理与膨胀不对称引理（anchor 盒 [cell-r-1, cell+r]）再写代码，蕴含性单测+小实例解集 A/B 双检。C4b 维持判死；C2b/C5 维持排除出默认计划（C2b 按『completion 子问题从零建』重估成本，C5 的外审焦点=unsafe-map 自述的 ghost anchor 域不完整问题而非覆盖编码）。红线核查通过：批0 全程不碰 sealed、结果不回流 certified 的设计与 unsafe-map/create 时序纪律（01_ablation_map L91-93）一致。
## 三、附录：B1 历史证据（34×）可靠性评级（owner 拷问后定稿，2026-07-09 18:46）

owner 拷问「线性编码为什么会有效——历史证据可靠吗？推理链是什么？」后的定稿评级。**批 1 的下注依据是机制链，不是 34×**。

### 三处污染（34× 只算提示，不算证明）——▲第 2 条经 07-09 晚 cachy 老仓考古修订

1. **非受控归因**：B1 Phase 0 同时换了表示层（坐标 IntVar→pose 布尔）+ 供电编码（→线性 x≤Σcoverers），34× 是合力，无法归因供电编码单独多少。C6 保留坐标只换供电编码——34× 对它无直接预测力（设计审查同调：保守估 5-15×）。
2. **▲修订（老仓考古 `01_cachy_archaeology_b1_evidence.md` 证伪初版怀疑）**：初版评级怀疑「53s 出自供电假可行漏洞修补前的欠约束模型」——考古坐实 **Phase 0 的供电语义是干净的**（pole pose 已按 ghost 过滤、无 coverer 即禁 pose，`poc_pose_bool_with_power.py` 原文为证）。53s 的真实欠约束在**端口/路由责任边界**（Phase 0 范围明确不含 binding/routing；Phase 4 才发现 master 不知 port direction，Phase 6 双路修补皆死）。净效果：**53s 作为「线性供电编码在 master 级有效」的证据比初评更硬**——它测的恰好是我们要它校准的东西（供电 master 首解），只是绝不能当端到端指标。03_encoding_archaeology.md:88 的 pre-R11 假-FEASIBLE 缝警告仍有效，但只约束「复跑旧快照代码」场景。B1 判死的真实原因（port/routing 无法可解规模进 master + lazy cut 不收敛）与当前坐标架构无关——binding/routing 本就在子问题里，正是现架构的优势面。
3. **规模外推**：B1 是 27×15 窄带单 anchor；我们是全盘 4225 anchor。

### 可单独引用的硬部分（▲考古后扩为两条）

- **B1 的 20.6s INFEASIBLE**：欠约束只会放大可行域、不会凭空制造不可行——即便模型欠约束仍能快速证明不可行，说明该编码形态的**证明能力（传播强度）是真的**。
- **▲B1 的 49-53s OPTIMAL（限定 master 级供电首解口径）**：考古证实 Phase 0 供电语义干净（ghost 过滤 + 空 coverer 禁 pose），该数字可作「线性覆盖编码打穿供电 master 首解」的直接证据引用——但范围只到 master+binding，端到端收敛正是 B1 的死因，不可外推。

### 真正的下注依据（机制链四步，非历史）

病征（百万分支 + 0.07-0.1% 冲突率 = 传播器不喊停、教训不可复用）→ element-over-variable-arrays 是 CP-SAT 教科书级弱传播（witness 编码每 powered slot 3×AddElement）→ M6 钉死实验直接佐证（布局变常量 → element 弱点消失 → 同一子模型从永远 UNKNOWN 变 94s INFEASIBLE 证明）→ 线性形态逐项对症（cover_lit 挂 enforcement：域漂离即钉 0 = 死路上层喊停；冲突子句短而通用 = 可学习）。**批 0 的 C6 实测冲突率 90-150× 提升已兑现此链的传播预言**（README 结果表），未兑现的是净收益（节点变重代价）。

### 已知的三个「我可能错」

代价端未算清（净收益=剪枝−开销，只有实测能答）；病因可能不止编码（供电可行布局存在性 OPEN——若不存在，任何编码只能更快证不可行）；presolve 理论上也能展开 element（反驳：我们的 presolve 恰是永远跑不完的税）。批 0 的结构就是冲着便宜证伪来的。
