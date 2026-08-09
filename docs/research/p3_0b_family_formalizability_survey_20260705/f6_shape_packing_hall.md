# F6 — shape_packing_hall（src/cuts/families/shape_packing_hall.py + docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md）

关键澄清：当前实现（代码+spec）不是完整的多形状 Hall matching，而是单形状 `1×L` rigid pose、`placement_rule=left_or_bottom_boundary`、区域限定 left/bottom baseline 的受限版本；多形状 Hall 婚配定理版本被 spec 明确延期到 Phase 1.5+（shape_packing_hall.py:3-17；06_shape_packing_hall.md:92-102,414-417,518-520）。generator/oracle 现况见 dependencies 字段。

## proposition
该 family 编码的"某种不可行性的充分条件"精确形式如下（对当前已实现的受限版本，非 spec 中未来的多形状 Hall 版本）：

对任意状态 S、区域 R ∈ {left_baseline, bottom_baseline}、其对侧区域 R'、facility group g、pose 长度 L ≥ 2、g 的总需求 D = demand(g)、一个"区域需求证书值" d_R，若同时满足：

1. g 的 facility 模板满足 placement_rule = left_or_bottom_boundary 且尺寸恰为 1×L（min(w,h)=1, max(w,h)=L）（检查见 shape_packing_hall.py:359-442）。
2. 把区域 R 与对侧区域 R' 各自按 `ghost_cells ∪ exterior_blocks` 切成若干个 maximal contiguous unblocked interval（helper 定义：src/cuts/helpers/baseline_partition.py:28-38,41-59,65-81）。
3. 定义 C_R = Σ_I floor(len(I)/L)（对 R 的所有 interval 求和），C_R' 同理对 R' 求和。
4. d_R 必须满足下界证明：d_R ≤ max(0, D − C_R')（"对侧最多能放 C_R' 个，所以本侧至少要放 D−C_R' 个"这一鸽笼式下界，shape_packing_hall.py:324-356）。
5. C_R < d_R（Hall witness 严格不等式，在证书里出现两次：一次采信证书本身的值、一次由 validator 独立重算后再核；shape_packing_hall.py:254-264 与 500-540）。

则：不存在一个合法布局，能把 group g 的 D 个 1×L pose 全部放置在 left/bottom baseline 上并同时避开 ghost∪exterior ⇒ 该状态 INFEASIBLE（对应生成一条 sound 的 cut）。

形式化写法：
Σ_{I ∈ partition(R)} floor(len(I)/L) < d_R ≤ max(0, D − C_R')  ⇒ INFEASIBLE。

底层核心引理（一维区间容量上界，鸽笼原理）：任何合法的 1×L pose 必须整体落在某个 unblocked interval 内部（不能跨越 ghost/exterior 阻挡的 cell），因此该区域内可放置的 pose 数量 ≤ Σ_I floor(len(I)/L)；若这个上界小于必须放置的下界需求，矛盾。

spec 文档里的原始/更朴素版本（单区域，未涉及"对侧下界"这层）：区域被 ghost 切成 intervals，`sum_j floor(len(I_j)/L) < demand ⇒ INFEASIBLE`，证明是 "interval capacity upper bound + 总和小于 demand"（06_shape_packing_hall.md:23-38，证明见 06_shape_packing_hall.md:81-90）。2026-06-04 的 amendment 在 spec 里补上了当前代码实现所需的额外必要条件：region_demand 必须由 source-of-truth 下界（即上面第 4 点）推出，且只接受 left_or_bottom_boundary 模板（06_shape_packing_hall.md:561-563）——这是对原始朴素命题的加固，弥补了一个此前的 soundness 缺口。

spec 里描述的、尚未实现的推广（不属于当前已编码命题，仅供对照）：多形状版本的完整 Hall 婚配定理式命题写在 06_shape_packing_hall.md:92-102；LP/Farkas 对偶关系的讨论在 06_shape_packing_hall.md:68-75,141-143。

## argument_type
当前已实现（编码进代码）的核心论证类型：一维区间几何 + 纯计数/鸽笼原理（pigeonhole），不是完整的 Hall 婚配定理匹配存在性判据，也不涉及 LP 对偶/Farkas、最大流最小割、图可达性或集合覆盖论证。

支持证据：
- spec 的单形状证明只用"K*L ≤ len(I)"这类区间容量上界与总和上界的算术（06_shape_packing_hall.md:81-90）。
- helper 把 baseline 转成有序一维 cell 序列，并按 blocked cells（ghost∪exterior）切出 maximal contiguous segment（baseline_partition.py:28-38, 55-81）——这是纯几何/组合切分，不涉及二部图匹配结构。
- 代码只计算 sum(L // pose_length) 并与 region_demand 比较大小（shape_packing_hall.py:319-321, 524-539）——这是计数比较，不是匹配算法。
- 对侧下界（第 4 点条件）也是同样的鸽笼论证：总需求 D 减去对侧最大可放容量 C_R'（shape_packing_hall.py:327-356）。

Hall 婚配定理（真正的二部图匹配存在性判据）、weighted Hall、ILP 可行性、LP/Farkas 对偶——这些在 spec 中被明确列为 future/generalization 内容而非当前已编码内容：多形状 Hall 写在 06_shape_packing_hall.md:92-102；LP/Farkas 关系的讨论写在 06_shape_packing_hall.md:68-75,141-143。当前 cert schema（src/cuts/cert_schema.py:76-91）没有任何 LP dual 相关字段；当前 validator 代码里也没有任何 LP/ILP solver 调用。

结论性事实（非最终判断，只陈述现状）：family 名字里带"Hall"，但当前已实现并被 validator 机械检查的部分，其论证工具是初等计数/鸽笼原理，不是 Hall 定理本身；Hall 定理是 spec 里规划的未来推广方向。

## formalization_needs
按"抽象数学层" vs "绑死具体几何/实例数据层"区分如下（这是事实性拆解，不是可行性结论）：

【抽象数学层——理论上可以做成与具体输入无关、直接对应到 Lean/Mathlib 里通用定理的部分】
- 需要的数学工具：自然数（Nat）算术、整数除法/floor division 的性质、有限 list/Finset 上的求和（Σ）、区间（interval）互不相交（disjoint）的性质、有限网格上"连续未阻塞段"的构造与计数、鸽笼原理（pigeonhole）式的计数不等式引理。
- 核心可形式化的抽象定理（对应当前已实现的受限版本）大致是两条：
  (a) 若干个长度为 L 的 rigid pose 若必须落在若干互不相交的 unblocked interval 之一内部（不能跨越 blocked cell），则可放置总数 ≤ Σ_I floor(len(I)/L)——这本质是一条纯组合数论/计数引理，不需要依赖 Hall 婚配定理，可以完全在抽象层面（对任意有限区间划分）证明。
  (b) 若对侧区域最多能放 C_R' 个，而总需求是 D，则本侧至少要放 max(0, D−C_R') 个——这也是纯算术推导（减法下界），不涉及具体几何。
  这两条组合起来就是当前 family 的核心 soundness 定理，理论上可以写成一条不依赖任何 70×70 具体网格、不依赖任何具体设施数据的通用 Lean 定理（对"任意有限区间集合、任意正整数需求"成立）。

【绑死具体几何/实例数据的部分——"实例级验证"而非"定理级证明"】
- 需要把具体的 70×70 baseline 的 cell 序列、具体的 ghost_cells、exterior_blocks、266 个设施的具体 facility template（尺寸/placement_rule）、具体的 group demand 数值、以及证书（certificate）里的具体 partition_lens/partition_offsets/max_packable 列表，都编码成 Lean 里的具体对象（或者由一个可信 checker 生成对应的 proof term），才能把"这个具体证书对这个具体状态确实满足抽象定理的前提"这件事验证完。
- JSON 解析、严格 schema 校验（strict_json、cert_schema 各字段类型/范围）、SHA256 摘要匹配（ghost_rect_repr、exterior_blocks_digest）、canonical 正则匹配（pose_shape_canonical）——这些更像是工程层面的 TCB（可信计算基）完整性检查或"这份输入数据确实是它声称的那份数据"的可执行验证问题，而不是 cut soundness 数学论证本身的一部分。

【如果未来要形式化 spec 里规划的推广部分（当前未实现，仅供事实记录）】
- 若要形式化多形状版本（spec 06_shape_packing_hall.md:92-102 所述），数学上需要的是：有限二部图匹配存在性判据（Hall 婚配定理，Mathlib 里若有对应形式化）、或等价的 b-matching / 最大流最小割 / ILP 可行性的形式化。
- 若要扩展到 interior rectangle（非仅一维 baseline 区间，06_shape_packing_hall.md:521-523 所述），还需要矩形/网格的相交判定、包含关系、连续块分解等计算几何库支持。
- 当前代码和当前已实现的 family 均不涉及这两类推广，所以当前形式化任务的抽象数学层只需要覆盖上面"抽象数学层"部分列出的初等计数/鸽笼引理，不需要 Hall 定理、不需要最大流最小割、不需要 LP 对偶/Farkas、不需要复杂计算几何——这些都是 spec 规划但代码尚未编码的未来扩展所需，与"当前已实现的 F6 soundness 论证"是两件不同范围的事情，需要在填表时分开标注。

## latent_issues
【spec 文档自承的未解决问题 / TODO / drift（带引用）】
1. 多形状（multi-shape）推广未完成：spec 承认生产环境不止 boundary_storage_port 一种形状，多形状需要 ILP 可行性判定（06_shape_packing_hall.md:518-520）；多形状的完整证明本身仍待补（06_shape_packing_hall.md:92-102,414-417）。
2. Interior region 未覆盖：当前只处理 left/bottom baseline，interior 区域的 shape_hall 扩展仍是待办（06_shape_packing_hall.md:521-523）。
3. Partition offsets 的验证策略存在文档与代码不一致：spec 的 open question 部分说 offsets 只是 debug 用、replay 不需要验证（06_shape_packing_hall.md:524-526），但当前代码已经改为要求 offsets 必须被严格重算并逐一相等（shape_packing_hall.py:23-26,516-520）——即代码比 spec 记录的决定更严格，这是文档滞后于代码的 drift。
4. 与 region_capacity family 的去重（dedupe）策略尚未定，标注为 Phase 1 待办（06_shape_packing_hall.md:527-529）。
5. Multi-region Hall（left+bottom 联合区域）未覆盖，标注为 Phase 1（06_shape_packing_hall.md:530-531）。
6. spec 内部本身存在需求变量的 drift：§5a.bis 说应使用 group.demand（06_shape_packing_hall.md:246-256），但 §5b 的伪代码仍写的是 remaining_count（06_shape_packing_hall.md:272-274）——spec 文档内部前后不一致。当前代码实际使用的是 group_demand = state.groups[group_id].demand（oracle 侧：shape_packing_hall_oracle.py:152；validator 侧：shape_packing_hall.py:283-290），与 §5a.bis 一致、与 §5b 伪代码不一致。
7. spec 里"实现预决策"部分记录的文件路径已过期：spec 写的是 src/cuts/generators/shape_hall_generator.py（06_shape_packing_hall.md:535-540），但当前实际路径是 src/cuts/oracles/shape_packing_hall_oracle.py——路径已重命名/迁移，spec 未同步更新。
8. spec 验收状态部分自己列出 5 个 open question，且承认当前实施仍处于 Phase 1（06_shape_packing_hall.md:542-555）。
9. 2026-06-04 的 amendment 是对此前一个 soundness 缺口的事后修补：承认并修补了 region_demand 若无 source-of-truth 下界证明、或不限定 left_or_bottom_boundary 模板时会不 sound 的问题（06_shape_packing_hall.md:561-563）——即 spec 自己承认这个 family 曾经有一个真实的 soundness 漏洞，现在的第 4 点条件（region_demand ≤ max(0, D − C_R')）就是补丁本身。

【代码里的字面 TODO/FIXME】
codex 检索结果：目标 family/helper/oracle 三个文件里没有发现字面的 "TODO" / "FIXME" 标记。

【代码里的已知限制/注释矛盾，非字面 TODO 但等价于已知缺陷】
1. 多形状 Hall 被代码注释明确标注延期到 Phase 1.5+（shape_packing_hall.py:3-5）。
2. region_demand 真正来自 master.solution（而非人工/覆盖值）也是 Phase 1.5+ 计划；Phase 1.2 阶段 generator 默认是 disabled 状态（shape_packing_hall_oracle.py:15-18,156-163）。
3. validator 文件顶部的 schema 注释仍写"Phase 1.2 generator 使用 region capacity 上界"（shape_packing_hall.py:33-36），这与当前 oracle 里的注释"默认 disabled，因为（简化取法）unsound"（shape_packing_hall_oracle.py:156-163）相互矛盾——codex 明确指出这是代码注释之间的 drift，尚未被清理。
4. master 应用侧（Step 8 apply_to_master）仍是 NotImplementedError，这条 cut family 即便 validator 判定合法也无法真正落地成 master 求解器里的约束（lifecycle.py:1121-1126）——这是整条 F6 pipeline 目前无法闭环生产使用的结构性缺口（与 CLAUDE.md 里记录的 F1-F9 cut lifecycle 未接入生产这一项吻合）。
