核验日期：**2026-07-04（Asia/Tokyo）**。我把“证书侧”拆成四条路线来核实：**PB/VeriPB、MIP/VIPR、CNF/LRAT、LP/Farkas**。结论先放在前面：你们设计稿里“轴 B”的大方向是对的，但把 `cake_lpr / PBLean / CakePB / VIPR` 混在一个桶里会造成路线误判；另外，“Glasgow/Pumpkin 已支持 VeriPB 3.0”这句话需要修正，**Glasgow 可确认是 VeriPB 3.0 原生日志路线，Pumpkin 当前更像 DRCP/LCG 证明路线，不应等同列入 VeriPB 3.0 原生输出**。

## 1. 生态现状核实

### 1.1 VeriPB 3.0：生态是活的，但“谁原生输出”要重新裁边界

**确认结论。** VeriPB 3.0 仍是 0-1 PB / cutting-planes 证明日志这条线的核心格式。VeriPB 官网把它定义为“通用 correctness certificates proof format”，底层是 pseudo-Boolean / cutting-planes over 0-1 integer linear inequalities，并且明确说当前文档对应 **SAT Competition 2025** 使用的版本。官网列出的可产生日志工具包括 BreakID、CaDiCaL、CGSS、Exact PB solver、**Glasgow Constraint Solver**、Glasgow Subgraph Solver、Pacose、PaPILO、QMaxSATpb、RoundingSat、satsuma、Scuttle 等；这份官方清单**没有列 Pumpkin**。([VeriPB][1])

**Glasgow 可确认。** Glasgow Constraint Solver 的 README 明确写着“current implementation is using the VeriPB 3.0 proof format”，并说明 `--prove` 或 API 的 `ProofOptions` 会生成 `.opb` 与 `.pbp`，再用 `veripb` 检查。也就是说，**Glasgow 是当前可直接纳入 VeriPB 3.0 sidecar PoC 的较稳对象**。([GitHub][2]) 另外，Glasgow 2026 年还有 CP 2026 接收论文，内容是用 VeriPB 为 projected enumeration / counting 做 proof logging，说明这条线在 2026 仍有活跃开发。([Enlighten Publications][3])

**Pumpkin 需要降级为“另一路候选”，不是 VeriPB 3.0 同级已确认。** CPMpy 对 Pumpkin 的接口文档显示，Pumpkin 是 TU Delft ConSol Lab 的 LCG CP solver，`solve(..., prove=True)` 产出的是 `.drcp` 与 `.lits`，而不是直接的 VeriPB `.pbp`；同一文档还写着 optimization under assumptions unsupported、proof-logging under assumptions unsupported。([CPMpy][4]) 这意味着 Pumpkin 也许有证书研究价值，但对你们“binding/routing 子问题 INFEASIBLE 做旁路证书复验”的工程路线来说，它不能和 Glasgow 一起被描述为“VeriPB 3.0 原生可用”。

**经形式化验证的 PB 检查器：CakePB 是主线，PBLean 是 2026 新星但工程成熟度较低。** CakeML checkers 页面把 `cake_pb` 系列列为 PB proofs 的 verified checker / frontend，并明确区分了 `cake_lpr`（CNF UNSAT）、`cake_pb`（PB decision/optimization）、`cake_vipr`（MILP results）。它还说 `cake_lpr` 与 `cake_pb` 已用于审计 annual SAT competition outputs。([CakeML][5]) CakePB 仓库描述为“formally verified proof checker for pseudo-Boolean reasoning”，基于 CakeML，仓库创建于 2024-02-09。([GitLab][6]) VeriPB 官网也说明 Rust VeriPB checker 可以 elaborate 到 CakePB 的 kernel format，CakePB 本身用 CakeML 形式化验证。([VeriPB][1])

**PBLean 的定位要谨慎。** PBLean 是 2026 年很值得关注的新路线：论文 arXiv v2 日期为 **2026-04-02**，描述其把 VeriPB kernel-format proofs 导入 Lean 4，reflection checker 的 soundness 在 Lean 中完全证明，支持 VeriPB kernel rules，并能把检查结果变成 Lean theorem。([arXiv][7]) 但仓库层面看，PBLean 到 **2026-06-02** 才发布 v0.3.0 的 Lean 4.30.0 port，仓库体量很小，所以我建议把它放在“后续降低翻译层 TCB / Lean 证据闭环”的阶段，而不是第一阶段工程依赖。([GitHub][8])

### 1.2 VIPR 与 exact-SCIP：这条线已经从“exact-SCIP 生态”变成“SCIP 10 exact mode + VIPR + cake_vipr”

**确认结论。** VIPR 是 exact rational correctness certificates for mixed-integer LP solver results 的格式和工具集，仓库说明它用于 LP-based branch-and-cut certificates，包含技术规范 v1.0/v1.1，以及 `vprchck`、parallel checker、`viprcomp` 等工具；`viprcomp` 需要 SoPlex 来补全不完整证书。([GitHub][9])

**exact-SCIP 现状需要更新为 SCIP 10 exact mode。** SCIP 文档说明，exact mode 通过 `exact/enable = TRUE` 开启，证书通过 `certificate/filename` 输出；该证书可由 VIPR 或 formally verified CakeML checker 检查。文档也明确警告：如果启用 cutting-plane separation，证书可能不完整，需要 `viprcomp` 补全。([SCIP][10]) SCIP FAQ 进一步说明，SCIP 10 中 certificate 只覆盖 presolving 之后的 branch-and-bound tree；若要针对原问题验证 certificate，可能需要禁用 presolving。([SCIP][11])

**VIPR 的形式化验证实现存在：cake_vipr。** CakeML checkers 页面把 `cake_vipr` 列为“checking Mixed Integer Linear Programming (MILP) results”，并和 `cake_lpr`、`cake_pb` 放在同一个 verified checkers 列表里。([CakeML][5]) SCIP 10 technical report 对 exact mode 的 VIPR 证书内容描述得更具体：证书包含 exact problem、primal/dual solutions、derivations，derivation 中包含 inequalities 的 conical combinations、Chvátal-Gomory cuts、disjunction logic；报告还说已有 C++ proof checker 和更 rigorous 的 HOL4/CakeML checker。([arXiv][12])

**工程含义。** 对你们来说，VIPR 不是 PB/VeriPB 的替代品，而是 **MIP / exact rational branch-and-bound 旁路**。如果 routing 子问题能自然线性化成 flow / assignment / connectivity MILP，VIPR 路线比把一切强行塞进 OPB 更合理；如果 binding 子问题主要是布尔、基数、互斥、覆盖、蕴含，则 VeriPB/CakePB 更轻。

### 1.3 cake_lpr：成熟，但边界是 CNF/LRAT，不是 CP-SAT/LBBD 的通用钥匙

`cake_lpr` 是 CNF UNSAT proof checker，支持 LPR/LRAT 这类 SAT 证明。CakeML checkers 页面把它明确描述为 `cake_lpr`: checking CNF UNSAT proofs，与 `cake_pb`、`cake_vipr` 是不同工具。([CakeML][5]) 因此，对你们的 CP-SAT/LBBD 场景，`cake_lpr` 只在两种情况下相关：

第一，某个子问题能被你们**独立、完整、可审计地编译为 CNF**，并用 SAT 求解器产出 LRAT/LPR 证明。这个适合很小的布尔核，例如互斥、覆盖、简单 implication graph。

第二，OR-Tools CP-SAT 的 proof flags 只覆盖纯 SAT 子集时，也许可以作为“极窄范围”的证明路线。OR-Tools 参数文件在 “Proofs” 部分明确写着 LRAT/DRAT 输出和检查在 **Dec 2025** 的状态下只支持 pure SAT，且要求 `cp_model_presolve=false`、`linearization_level<=1`、`symmetry_level<=1` 等限制。([OR-Tools][13]) 这对你们的 CP-SAT binding/routing 子问题，尤其有 integer linear constraints、global constraints、presolve、LBBD nogood 的场景，基本不能当作主路。

## 2. 对照表：候选工具 × 成熟度 / 形式化验证 / 接口成本

| 候选工具或格式                                                 |                                                                                                     2026-07 状态与成熟度 |                                                    是否经形式化验证 | 与本项目接口成本与建议                                                             |
| ------------------------------------------------------- | -----------------------------------------------------------------------------------------------------------------: | ----------------------------------------------------------: | ----------------------------------------------------------------------- |
| **VeriPB 3.0**                                          |                                          活跃。官网列出 SAT/CP/PB/MaxSAT/子图/预处理相关工具，SAT Competition 2025 使用。([VeriPB][1]) | 格式本身不是“验证器”，Rust checker 可 elaborate 到 CakePB。([VeriPB][1]) | 中到高。需要从 canonical 子问题导出 OPB/PB，并用可产生日志的 solver 重解。建议作为 binding 子问题第一主线。 |
| **Rust VeriPB checker**                                 |                                               工程 checker，GitLab 显示 2025-05 创建，已有多分支、多 tag、多 release。([GitLab][14]) |          checker 自身不是最终形式化根，但可接 CakePB kernel。([VeriPB][1]) | 低到中。可先用作快速 sidecar，再逐步切到 CakePB。                                        |
| **CakePB / cake_pb**                                    |                                     成熟的 verified PB checker，CakeML 页面称已用于 SAT competition outputs 审计。([CakeML][5]) |                是。基于 CakeML 的 PB proof checker。([GitLab][6]) | 中。只要 VeriPB 证明链打通，接入成本可控。推荐作为 PB 证书最终检查器。                               |
| **PBLean**                                              |                                             2026 新路线，arXiv v2 为 2026-04-02，GitHub v0.3.0 为 2026-06-02。([arXiv][7]) |   是，Lean 内证明 checker soundness，产出 Lean theorem。([arXiv][7]) | 高。短期不建议堵主线；中长期可用于“验证编码层”以减少翻译 TCB。                                      |
| **Glasgow Constraint Solver**                           |                                                                       可确认原生 VeriPB 3.0 proof logging。([GitHub][2]) |                       solver 不验证，proof 可由 VeriPB/CakePB 检查。 | 中到高。适合把 CP-ish 约束重新建模成 GCS 可表达的模型，做离线复验。                                |
| **Pumpkin / DRCP**                                      |               活跃 LCG CP solver，但 CPMpy 接口产出 `.drcp/.lits`，proof logging under assumptions unsupported。([CPMpy][4]) |            未找到可作为你们主线的成熟 formally verified DRCP checker 证据。 | 高。不建议第一阶段纳入“证书侧可信闭环”，可作为研究候选。                                           |
| **RoundingSat / Exact PB solver / Sat4j proof logging** |                VeriPB 生态里重要 PB/optimization 求解器；2025 CP 论文报告了 RoundingSat 和 Sat4j 的 proof logging 工作。([DROPS][15]) |                                  通过 VeriPB → CakePB 可形式化检查。 | 中。对 OPB 化后的 binding/简单 routing 子问题有吸引力。                                 |
| **SCIP 10 exact mode + VIPR**                           |                                         当前主流 exact MIP 证书路线。exact mode 输出 VIPR，支持 exact rational MILP。([SCIP][10]) | 可用 VIPR C++ checker，也有 CakeML/HOL4 checker 路线。([CakeML][5]) | 中到高。routing 若可线性化为 MILP，优先考虑；注意 presolve/cuts 证书洞。                      |
| **VIPR C++ checker / viprcomp**                         |                                          VIPR 仓库提供 checker、parallel checker、certificate completion 等。([GitHub][9]) |                    C++ checker 本身不是最终形式化根；cake_vipr 是形式化路线。 | 中。可作为 MIP sidecar 的工程第一步。                                               |
| **cake_vipr**                                           |                                                      CakeML verified checker 列表中明确存在，用于 MILP results。([CakeML][5]) |                                                          是。 | 中。建议在 VIPR 工程链稳定后接入 nightly。                                            |
| **SoPlex exact**                                        |        2026 仍活跃，SoPlex 8.0.2 于 2026-04 随 SCIP Suite 10.0.2 发布，支持 rational input 的 exact LP solution。([SoPlex][16]) |             未找到独立、通用、形式化验证的 SoPlex LP Farkas proof checker。 | 低到中。适合“精确 LP/Farkas 生成器 + 自研有理检查器”。                                     |
| **QSopt_ex**                                            |                经典 exact rational LP solver，官方页面仍是 2009 版本；SCIP 10 报告仍把它列为 exact LP interface 选项之一。([滑铁卢大学数学系][17]) |                  未找到现代 formally verified proof-log checker。 | 中。可作 fallback，不建议作为新主线。                                                 |
| **OR-Tools CP-SAT LRAT/DRAT flags**                     |                                                                  只适用于 pure SAT 且限制很多；不覆盖一般 CP-SAT。([OR-Tools][13]) |                                    若产出 LRAT，可用 cake_lpr 检查。 | 对本项目主问题基本低价值，只适合极小 CNF kernel。                                          |
| **OR-Tools assumptions unsat core**                     | CP-SAT proto 支持 assumptions 并返回 sufficient assumptions for infeasibility，但不保证 minimal/irreducible。([OR-Tools][18]) |                                            否。core 不是 proof。 | 低成本高实用，但只能作为缩小证书范围的 diagnostic，不可当最终证明。                                 |
| **cake_lpr**                                            |                                                  成熟 CNF UNSAT checker，已用于 SAT competition outputs 审计。([CakeML][5]) |                                                          是。 | 对 CP-SAT/LBBD 主链相关性低；只有 CNF 化子核才值得接。                                    |

## 3. OR-Tools CP-SAT 无通用 proof log 时，binding/routing INFEASIBLE 的现实旁路

你们的背景材料里说主栈是 Python 3.13 + OR-Tools，LBBD master 给 layout，两个 child 子问题做 binding/routing feasibility；最终证书依赖“更优候选不可行”，所以 INFEASIBLE trust 是关键。这个判断非常准确。真正要避免的是“主模型 builder 错了，复验模型也复用同一个 bug，于是两边一起过”的双生稻草人。

### 路径 A：把 CP-SAT 子问题翻译成 PB/OPB，用 VeriPB solver 重解并检查证书

**适用场景。** binding 子问题如果主要是布尔选择、assignment、exactly-one/at-most-one、cover、蕴含、容量上界、线性 0-1 约束，这条路最自然。VeriPB 处理的是 0-1 integer linear inequalities 和 cutting-planes 证明，正好覆盖这类模型。([VeriPB][1])

**推荐组合。** 第一阶段用 OPB exporter + Glasgow/RoundingSat/Exact PB solver 等产生日志，先用 Rust VeriPB checker 快速跑通，随后接 CakePB。Glasgow 可确认 `--prove` 产出 `.opb/.pbp` 并用 `veripb` 检查；CakePB 是 verified PB checker，VeriPB 官网也说明 Rust checker 可 elaborate 到 CakePB kernel。([GitHub][2])

**翻译层工作量。** 对 binding：大约 **2 到 5 周**可做出可用 sidecar，前提是你们已有干净的 canonical 子问题 schema 和约束 ID。工作内容是写一个不复用 CP-SAT builder 的 OPB emitter、固定整数域与布尔变量映射、输出 constraint map、跑 solver、收 proof、检查 proof。对 routing：如果 routing 包含 circuit、table、automaton、no-overlap、路径连通性等 CP global，翻译成 PB 的工作量会膨胀到 **6 到 12 周以上**，并且 proof 文件可能大很多。

**语义忠实性风险。** 这是这条路最大的刺。OPB emitter 本身会成为新的 TCB。缓解方式不是“相信 emitter”，而是让 emitter 从一个 canonical JSON/ protobuf 约束层读取，不复用 CP-SAT builder；然后对小规模实例做 exhaustive enumeration，对中等实例做随机 witness 对比，对 infeasible case 做 mutation tests。中长期可以考虑 PBLean 的 verified encoding 路线，因为 PBLean 论文明确把 verified encodings 作为缩小 translation gap 的目标之一。([arXiv][7])

**运行成本。** 离线可接受，在线不建议。PB Competition 2026 的 proof 规则给了一个现实尺度：UNSAT/OPT proof size limit 可到 100GB，VeriPB verification limit 可到 5 小时。([CRIL][19]) 这不是说你们会碰到这个上限，而是说明“证书日志”天然可能很重。工程上应先 nightly/sample audit，不要放进主链。

### 路径 B：把子问题翻译成 MILP，用 SCIP 10 exact mode 输出 VIPR，再用 VIPR/cake_vipr 检查

**适用场景。** routing 如果本质上能表达成 flow、multi-commodity flow 的简化版、assignment + connectivity cuts、time-expanded network、资源容量线性约束，那么 MIP/VIPR 比 PB 更自然。SCIP 10 exact mode 支持 exact rational MILP，能输出 VIPR 证书；VIPR 本身就是 exact rational branch-and-cut certificate 格式。([SCIP][10])

**翻译层工作量。** 如果你们已有 LP/MIP 风格的 routing 诊断模型，**3 到 6 周**能做 PoC；如果要把 CP-SAT global constraints、reified constraints、optional intervals、circuit/automaton 之类完整线性化，按 **8 到 14 周**估更现实。binding 若是纯 0-1 线性，也可以走这条，但一般不如 PB/VeriPB 轻。

**语义忠实性风险。** 风险集中在 big-M、整数域缩放、strict inequality 消除、可选约束 reification、presolve 后证书对应原问题这几处。SCIP 文档和 FAQ 都提醒了 presolving / cutting-plane separation 对证书完整性的影响：SCIP 10 的 certificate 只覆盖 presolved problem 的 branch-and-bound tree，若要验证原始实例可能需要禁用 presolving；若切平面分离导致不完整证书，需要 `viprcomp` 补全。([SCIP][10])

**运行成本。** exact rational MIP + proof logging 不适合在线主链。它适合 nightly 的“样本复验”、release gate 的“关键 infeasible replay”、以及调试时“最小不可行核复验”。如果 routing 模型大，优先配合路径 C 的 assumption-core shrink，只把核心约束送到 MIP/VIPR。

### 路径 C：使用 assumptions-based unsat core 只做“缩小问题”，再独立重验

**关键结论。** assumptions core 可以很有用，但**不是证书**。OR-Tools CP-SAT proto 说明 assumptions 字段允许在 infeasible 时返回 `sufficient_assumptions_for_infeasibility`，但该集合只保证足以推出 infeasible，不保证 minimal 或 irreducible；只有 single-thread、无 objective 的情形才会尝试 minimize，否则可能包含所有 assumptions。([OR-Tools][18])

**工程价值。** 它适合给每组业务约束一个 assumption literal，然后 CP-SAT 先返回一个 sufficient core；之后把 core 对应的约束子集导出到 PB/VIPR/LP checker。这样 sidecar 的规模可能小很多。CPMpy 文档也说明 OR-Tools 支持 assumptions / unsat core，但 OR-Tools Python 接口不是 incremental。([CPMpy][20])

**风险。** 2026 年还出现了 OR-Tools GitHub issue #5141：CP-SAT 在 presolve 开启时返回的 core 可能包含不在 assumptions 里的 literal；该问题于 2026-04-20 打开，复现于 main 和 v9.15/v9.14，关闭 presolve 后示例返回正确。([GitHub][21]) 所以你们不能把 core 当可信对象，只能把它当“候选子问题切片器”。工程上应强制检查：返回 literal 必须属于输入 assumptions；core 模式不带 objective；尽量 `num_workers=1`；必要时为 core extraction 禁用 presolve；最后仍需 PB/VIPR/LP 独立 checker 接受。

**工作量与成本。** 包装 assumption literal 和约束分组通常 **1 到 3 周**。运行成本低，收益可能很高，特别是 infeasible 子问题中只有少数业务规则冲突时。判据是 core 约束数能稳定缩到原模型的 **30% 以下**，并且 sidecar 对 core 的验证通过率高。

### 路径 D：纯 SAT / LRAT / cake_lpr

这条路只适合很小的 Boolean kernel。OR-Tools 的 LRAT/DRAT proof flags 在 Dec 2025 的说明中仍限 pure SAT，且有 presolve、linearization、symmetry 等限制；这不覆盖你们一般的 CP-SAT child。([OR-Tools][13]) 如果某个 binding 子核能完整 CNF 化，当然可以用 SAT solver + LRAT + cake_lpr；但不要把它写成 CP-SAT 证书侧主线。

## 4. LP / Farkas 侧：2026 年可用组合与 GLOP 共存建议

### 4.1 现成组合

**组合 1：SCIP 10 exact mode + VIPR + VIPR checker / cake_vipr。** 这是“solver 给证书 + 独立检查”最完整的一条线，尤其当 LP infeasibility 嵌在 MILP branch-and-bound 证明里。SCIP 10 exact mode 支持 rational MILPs，无 numerical tolerances，使用 GMP/MPFR/Boost；它输出 VIPR，报告中把证书内容描述为 exact problem、solutions、derivations，derivation 包含 conical combinations 等。([arXiv][12]) 同时，SCIP 文档确认 certificate 可由 VIPR 或 formally verified CakeML checker 检查。([SCIP][10])

**组合 2：SoPlex exact + 自研有理 Farkas checker。** SoPlex 官方页面说明它对 rational input 的 exact LP solution 有特殊支持，包含 iterative refinement、exact rational LU、continued fraction approximations，且 2026-04 发布了 8.0.2。([SoPlex][16]) 我没有找到 2026 年“`SoPlex` 标准输出 Farkas proof log + 现成 formally verified external checker”的强证据。因此比较现实的做法是：用 SoPlex exact 或 SCIP exact LP interface 生成/确认不可行性，再把 Farkas dual ray 以有理数导出，由你们自己的小 checker 检查。

**组合 3：QSopt_ex + 自研有理 Farkas checker。** QSopt_ex 是经典 rational LP solver，官方页面说明它使用 GNU MP，为 rational input 提供 exact rational solution，但官方版本信息很老。([滑铁卢大学数学系][17]) SCIP 10 报告仍把 QSopt_ex 列为 exact LP interface 选项之一，不过 SoPlex 是默认路线。([arXiv][12]) 所以 QSopt_ex 更适合作 fallback 或交叉验证，不建议作为新工程主依赖。

### 4.2 有理 Farkas checker 其实可以很小，重点是规范化

对单个不可行 LP，证书检查器不必很复杂。你们可以把所有约束规范化为有理数矩阵，然后检查一个有理 multiplier 向量是否满足 Farkas 条件。典型形式是：对 `A x ≤ b`，给出 `λ ≥ 0`，检查 `λᵀ A = 0` 且 `λᵀ b < 0`；如果有等式、变量上下界、自由变量，先统一转成标准不等式或在 checker 中显式处理符号约束。这个 checker 可以先用 Python `fractions.Fraction` 或 GMP 绑定实现，后续再搬到 Lean / CakeML 做形式化。

这条小 checker 的价值在于：它把“求解器是否诚实”降级为“这串有理数是否真能推出矛盾”。只要 checker 独立于 GLOP/CP-SAT/MIP builder，并读取 canonical LP schema，它的可信边界很清楚。

### 4.3 与浮点 GLOP 共存：可以后验有理化，但不能当成熟证书主线

OR-Tools GLOP 是 OR-Tools 的 in-house LP solver，文档强调它是快速、内存友好、数值稳定的 LP solver。([Google for Developers][22]) 但“浮点 solver 给了一个 infeasible / ray”本身不是形式化证书。成熟的共存方式应当是：

第一步，GLOP 继续用于主链诊断和快速筛查。

第二步，如果能提取 dual ray 或等价诊断信息，就把浮点 ray rationalize，例如限制分母、清零小系数、按约束尺度归一化，然后交给**独立有理 Farkas checker**。如果 checker 接受，证书成立，GLOP 的数值过程不在 TCB 里。

第三步，如果 rationalization 失败，不要调阈值硬过，直接用 SoPlex exact 或 SCIP exact mode 重解该 LP，再导出有理证书。

我没有找到足够证据表明“GLOP 后验有理化 + 标准现成形式化 checker”在 2026 已是成熟通用实践。可把它作为性能优化，而不是可信根。

## 5. 分阶段接入方案

### Phase 0：先建 canonical 子问题与独立 emitter，不碰主链

**目标。** 把 binding/routing/LP diagnostic 都导出为一个 canonical、可版本化、带 constraint ID 的中间格式。CP-SAT builder、PB emitter、MIP emitter、LP/Farkas checker 都只读这个格式，不能互相复用核心建模代码。

**工作量。** **1 到 2 周**。如果当前模型 builder 已经强耦合业务对象和 OR-Tools API，可能要 **3 到 4 周**。

**依赖。** 约束 ID、变量域规范、整数缩放规则、strict inequality 消除规则、objective 与 feasibility 分离规则。

**值不值得做的判据。** 小规模实例能 exhaustive enumeration，对比 CP-SAT 与 canonical evaluator；每个 INFEASIBLE 都能定位到 constraint IDs；历史 bug 能被重新注入并被独立 emitter 暴露。这个阶段本身就值得做，因为它先处理“翻译层成为新单点”的根病。

### Phase 1：binding 子问题 PB/VeriPB sidecar

**目标。** 对 binding INFEASIBLE 建立 OPB sidecar：canonical → OPB → Glasgow/RoundingSat/Exact PB solver → VeriPB proof → Rust VeriPB checker → CakePB。

**工作量。** **2 到 5 周**做出工程 PoC，**再 2 到 3 周**接 CakePB、CI 包装、proof artifact 存档。

**依赖。** 至少一个稳定 proof-logging solver，建议先 Glasgow 或 RoundingSat；Rust VeriPB checker；CakePB。Glasgow 的 VeriPB 3.0 输出是已确认事实。([GitHub][2]) CakePB 的 verified checker 角色也是已确认事实。([CakeML][5])

**值不值得做的判据。** 对 20 到 50 个历史/合成 binding infeasible 样本，sidecar 能独立复验；proof 检查时间进入 nightly 预算；至少能抓住 3 类 seeded encoding bug，例如漏掉互斥、容量符号反转、蕴含方向反转。

### Phase 2：assumptions core 只做缩小器

**目标。** 在 CP-SAT child 中给每组约束加 assumption literal，先抽 sufficient unsat core，再只把 core 子集送到 Phase 1 或 Phase 3 的 sidecar。

**工作量。** **1 到 3 周**。

**依赖。** OR-Tools assumptions API、约束分组策略、core literal 校验、单线程/无 objective 的 core extraction 模式。CP-SAT 文档明确 core 不保证 minimal/irreducible，且 2026 issue 显示 presolve 下有返回非 assumption literal 的风险，所以这一步必须防御式实现。([OR-Tools][18])

**值不值得做的判据。** core 平均约束数小于原模型 30%，且所有 core 都能被独立 sidecar 验证；一旦出现 core literal 不在 assumptions 中，自动降级为全量 sidecar 或 presolve-disabled core extraction。

### Phase 3：routing 子问题分流，PB 或 VIPR 二选一，不要一刀切

**目标。** 对 routing infeasible 选择证书路线：如果 routing 可表达为 0-1 线性约束且规模不爆，走 PB/VeriPB；如果更像 network flow / MILP，走 SCIP exact + VIPR + cake_vipr。

**工作量。** PB routing 约 **6 到 12 周**；MIP/VIPR routing 约 **4 到 10 周**，取决于当前 routing 模型是否已有线性结构。

**依赖。** 对 MIP/VIPR，依赖 SCIP 10 exact mode、VIPR checker、后续 cake_vipr。SCIP 文档确认 exact mode 和 certificate 输出，但也明确 presolve/cuts caveat。([SCIP][10])

**值不值得做的判据。** 对代表性 impossible routing case，sidecar 能在 nightly 预算内复验；VIPR/VeriPB proof 不因模型线性化而爆炸；禁用 presolve 后仍能在可接受时间内处理关键样本，或者可接受“验证 presolved problem + 独立记录 presolve-disabled 抽样”的折中。

### Phase 4：LP/Farkas 有理 checker

**目标。** 先不追求大而全的 VIPR，把不可行 LP 的 Farkas certificate 做成最小可信单元：canonical LP → 有理 ray → independent rational checker。

**工作量。** checker **2 到 5 周**；接 SoPlex exact / SCIP exact LP interface 再加 **4 到 6 周**。如果只做 GLOP ray rationalization 试验，可能 **1 到 2 周**有初版，但不能当最终证书链。

**依赖。** SoPlex exact 或 SCIP exact；有理数库；LP 约束规范化。SoPlex 2026 仍活跃并支持 rational input exact LP solution。([SoPlex][16])

**值不值得做的判据。** checker 能接受所有合成 infeasible LP 的正确 ray，拒绝符号扰动/系数扰动的假证书；GLOP rationalization 通过率如果低于 80%，就不要投入太多优化，直接改用 exact LP 生成证书。

### Phase 5：把 checker 放入 nightly/release gate，而不是在线主链

**目标。** 证书侧 first-class artifact：每个被抽样的 INFEASIBLE child 保存 canonical instance、solver log、proof、checker output、constraint map、版本 hash。

**工作量。** **2 到 4 周**。

**依赖。** 容器化工具链、proof artifact 存储、CI 超时策略、失败 triage 流程。PB/VIPR proof 可能很重，PB Competition 2026 的 proof limit 和 verification limit 说明这类 artifact 不能按普通日志看待。([CRIL][19])

**值不值得做的判据。** nightly 中 checker failure 的分类清楚：建模 bug、翻译 bug、solver timeout、proof checker bug、数值/rationalization failure。只要失败能被稳定分类，这一步就值得进入 release gate。

### Phase 6：PBLean / Lean verified encoding，作为 TCB 收口，不作为第一落点

**目标。** 对最核心的 binding 编码，把 canonical constraint 到 PB theorem 的映射放进 Lean，PBLean 导入 VeriPB proof 后产出 Lean theorem，进一步降低翻译层 TCB。

**工作量。** **2 到 4 个月**，取决于团队 Lean 熟练度和 canonical schema 复杂度。

**依赖。** PBLean、Lean 4、项目内部约束语义 formalization。PBLean 2026 论文已经证明了这条路线的理论吸引力，但仓库仍处早期工程阶段。([arXiv][7])

**值不值得做的判据。** 只有当 Phase 1/3 已经证明 sidecar 能抓到真实 bug，并且你们确实要把“翻译层”从工程信任降到形式化信任时，Phase 6 才值得做。否则它会变成漂亮但吃人的象牙塔。

## 6. 对设计稿“轴 B”的事实性修正建议

下面按你们设计稿中的说法逐条改。

### 修正 1：`VeriPB 3.0（PB 证明格式, Glasgow/Pumpkin 已支持）`

**问题。** Glasgow 支持 VeriPB 3.0 可确认；Pumpkin 当前资料显示的是 DRCP proof logging，CPMpy 文档产出 `.drcp/.lits`，且 proof logging under assumptions unsupported。官网 VeriPB solver list 也没有列 Pumpkin。([GitHub][2])

**建议替换文本。**

> VeriPB 3.0（PB / 0-1 ILP cutting-planes 证明格式；Glasgow Constraint Solver、RoundingSat、Exact PB solver、若干 MaxSAT/子图/预处理工具可产生日志；Pumpkin 当前应归入 DRCP/LCG proof logging 候选，不与 Glasgow 同等视为 VeriPB 3.0 原生路线）。

### 修正 2：`VIPR（MIP 证书格式, exact-SCIP 生态）`

**问题。** “exact-SCIP 生态”表述偏旧。2026 应写成 SCIP 10 exact mode：`exact/enable=TRUE`，`certificate/filename` 输出 VIPR；证书可由 VIPR 或 CakeML checker 检查。但要同时写明 presolve/cutting-plane caveat。([SCIP][10])

**建议替换文本。**

> VIPR（exact rational MILP / branch-and-cut 证书格式；SCIP 10 exact mode 可输出 VIPR，工程 checker 为 VIPR 工具链，形式化路线为 cake_vipr；SCIP 10 证书主要覆盖 presolved problem 的 branch-and-bound tree，涉及 presolve 或 cutting-plane separation 时需要禁用相关功能或用 viprcomp 补全）。

### 修正 3：`cake_lpr / PBLean(验证过的检查器)`

**问题。** 这里混淆了三个层次。`cake_lpr` 是 CNF UNSAT / LRAT/LPR 检查器，不是 PB 检查器；PB 侧的 CakeML 主线是 `cake_pb` / CakePB；MIP 侧是 `cake_vipr`；PBLean 是 Lean 4 中导入 VeriPB kernel proofs 的新路线，不能替代 CakePB 的工程成熟度。([CakeML][5])

**建议替换文本。**

> 形式化检查器需按证书语言区分：CNF/LRAT 侧为 cake_lpr；PB/VeriPB 侧为 CakePB/cake_pb，PBLean 可作为 Lean 证明集成与验证编码的后续路线；MIP/VIPR 侧为 cake_vipr。

### 修正 4：`LP dual 与 TP7-S Farkas 证书导出 VIPR/VeriPB 格式`

**问题。** 这句话过宽。VeriPB 只适合 0-1 PB / cutting-planes 证明，不是一般 LP Farkas 证书格式；VIPR 适合 SCIP exact / MILP branch-and-bound 证书，也不是所有 GLOP/Farkas ray 的自然输出格式。对单个 LP infeasible，最直接的路线是“有理 Farkas ray + 独立有理算术 checker”。SCIP 10 exact mode 的 VIPR 证书确实包含 conical combinations 等可表达 Farkas-like 推导，但这属于 VIPR/MILP 证书链。([arXiv][12])

**建议替换文本。**

> LP/Farkas 侧单独建一条有理证书路线：对不可行 LP 输出有理 Farkas ray，并由独立有理算术 checker 复验；若 LP/MILP 通过 SCIP 10 exact mode 求解，则可输出 VIPR 并用 VIPR/cake_vipr 检查；VeriPB 仅用于 0-1 PB 化后的子问题，不作为通用 LP Farkas 格式。

### 修正 5：`OR-Tools CP-SAT 无原生 proof log`

**问题。** 方向对，但建议加一句限定，避免以后读者发现 OR-Tools 有 LRAT/DRAT 参数后误解。OR-Tools 的 proof 参数截至 Dec 2025 说明为 pure SAT-only，且约束条件很多，不适用于一般 CP-SAT/LBBD child。([OR-Tools][13])

**建议替换文本。**

> OR-Tools CP-SAT 对一般 CP-SAT 模型没有可用的通用 proof log；虽然参数中存在 LRAT/DRAT proof 输出/检查选项，但截至 Dec 2025 仅支持 pure SAT 且要求关闭/限制 presolve、linearization、symmetry 等，因此不覆盖本项目 binding/routing child 的一般模型。

### 修正 6：`VeriPB export 需要第三方 solver（Glasgow/Pumpkin/exact-SCIP）重解`

**问题。** 这句话把三条不同证书路线混在一起。Glasgow 是 VeriPB；Pumpkin 是 DRCP；SCIP exact 是 VIPR，不是 VeriPB。([GitHub][2])

**建议替换文本。**

> 旁路重解应分三类：PB/VeriPB sidecar 使用 Glasgow、RoundingSat、Exact PB solver 等产生日志并由 VeriPB/CakePB/PBLean 检查；MIP/VIPR sidecar 使用 SCIP 10 exact mode 产生日志并由 VIPR/cake_vipr 检查；Pumpkin/DRCP 作为 CP proof logging 研究候选，暂不列为第一阶段可信闭环依赖。

## 7. 最终建议

第一落点不要从“全项目形式化”开始，而是从 **binding INFEASIBLE 的离线 PB sidecar** 开始。它最可能在 4 到 8 周内形成实用闭环：canonical instance、独立 OPB emitter、VeriPB proof、CakePB 检查、CI artifact。第二落点是 **assumptions core shrinker**，但只把它当切片器。第三落点才是 **routing 的 MIP/VIPR 或 PB 分流**。LP/Farkas 侧建议并行做一个很小的有理 checker，因为它便宜、清晰，而且可以立刻把 GLOP 浮点诊断从“我相信它”变成“这串有理数确实推出矛盾”。

把轴 B 写成一句话就是：

> 主链仍用 OR-Tools CP-SAT / GLOP 追求速度；证书侧不改主链，离线从 canonical 子问题独立导出 PB/MIP/LP 旁路模型，分别用 VeriPB/CakePB、VIPR/cake_vipr、有理 Farkas checker 复验 INFEASIBLE。assumptions core 只负责缩小复验范围，不作为证明。PBLean 暂列为后续降低翻译层 TCB 的 Lean 集成路线。

[1]: https://veripb.org/ "VeriPB"
[2]: https://github.com/ciaranm/glasgow-constraint-solver "GitHub - ciaranm/glasgow-constraint-solver: A constraint programming solver with support for proof logging · GitHub"
[3]: https://eprints.gla.ac.uk/386496/ " Proof Logging for Projected Enumeration (and Counting?) Problems in VeriPB "
[4]: https://cpmpy.readthedocs.io/en/gcs_optimal/_modules/cpmpy/solvers/pumpkin.html "cpmpy.solvers.pumpkin — CPMpy 0.9.24 documentation"
[5]: https://cakeml.org/checkers.html "Verified Proof Checking"
[6]: https://gitlab.com/MIAOresearch/software/CakePB "MIAO / Software / CakePB · GitLab"
[7]: https://arxiv.org/html/2602.08692v2 "PBLean: Pseudo-Boolean Proof Certificates for Lean 4"
[8]: https://github.com/leansolving/pblean "GitHub - leansolving/pblean: Verified pseudo-Boolean proof checking in Lean 4 · GitHub"
[9]: https://github.com/scipopt/vipr "GitHub - scipopt/vipr: VIPR: Verifying Integer Programming Results · GitHub"
[10]: https://www.scipopt.org/doc-10.0.0/html/EXACT.php "SCIP Doxygen Documentation: How to use the numerically exact solving mode"
[11]: https://www.scipopt.org/doc/html/FAQ.php "SCIP Doxygen Documentation: Frequently Asked Questions (FAQ)"
[12]: https://arxiv.org/html/2511.18580v1 "The SCIP Optimization Suite 10.0"
[13]: https://or-tools.github.io/docs/cpp/sat__parameters_8proto_source.html "Google OR-Tools: ortools/sat/sat_parameters.proto Source File"
[14]: https://gitlab.com/MIAOresearch/software/VeriPB "MIAO / Software / VeriPB · GitLab"
[15]: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2025.21 "Practically Feasible Proof Logging for Pseudo-Boolean Optimization"
[16]: https://soplex.zib.de/ "SoPlex"
[17]: https://www.math.uwaterloo.ca/~bico/qsopt/ex/ "www.math.uwaterloo.ca"
[18]: https://or-tools.github.io/docs/cpp/cp__model_8proto_source.html "Google OR-Tools: ortools/sat/cp_model.proto Source File"
[19]: https://www.cril.univ-artois.fr/PB26/ "Pseudo Boolean Competition 2026"
[20]: https://cpmpy.readthedocs.io/en/latest/solvers.html "Solvers — CPMpy 0.9.24 documentation"
[21]: https://github.com/google/or-tools/issues/5141 "CP-SAT: `sufficient_assumptions_for_infeasibility()` returns a literal that is not in the assumption list (presolve only) · Issue #5141 · google/or-tools · GitHub"
[22]: https://developers.google.com/optimization/lp/lp_example "Solving an LP Problem  |  OR-Tools  |  Google for Developers"
