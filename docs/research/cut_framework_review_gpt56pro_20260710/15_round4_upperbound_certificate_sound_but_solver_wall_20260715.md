# 15 — round-4(2026-07-15):上界证书 sound+紧凑已钉死,新墙=CP-SAT 在真锚点证不动 INFEASIBLE

> 承 doc 14。工作流 `wf_00da6a46-ab9`(4 Work[soundness/terminate 各 claude+codex] + 2 Verify[faithful claude / overall codex]),zero-sealed 只读。harness 在 `scratchpad/spike_round5/`。

## 0. 一句话结论
round-4 把"上界那条缝"从 round-3 的"对抗席推测"**钉成了 sound + 紧凑、双模型 + 对抗杀不掉**——round-2 的"上界没有便宜证书/硬墙"正式翻掉。**但拿到证书的最后一步(CP-SAT 在真锚点证出 INFEASIBLE)是新硬墙:sound 的 10.7K-var 紧凑模型摆在那,三个真锚点 7×7/6×8/8×6 全 UNKNOWN@1200s。** 墙从"没有便宜证书/撞 32G 墓碑"前移到"证书 sound 且小、但 solver 证不动"。

## 1. Soundness(命题 UBC:紧凑 front_clear-lifted master INFEASIBLE ⟹ 合法 certified-infeasible 上界证书)= 确认 sound,对抗杀不掉
- **双模型一致**:sound:claude=`conditional`、sound:codex=`sound_holds`。核心逻辑 = 松弛反驳定理:M=∧(全问题必要条件)是松弛,M∧front_clear UNSAT ⟹ 无真可行解 ⟹ 该 ghost 尺寸不可行。**安全方向非对称**:对 INFEASIBLE 上界证书,M 可任意"更松"仍 sound(越松越难 UNSAT,但一 UNSAT 就有效);唯一 unsound 方向 = 编码比全问题"更严"(见 [[projection-must-mirror-live-master-not-stricter]])。
- **对抗验证两席均未击杀**:verify:faithful(claude)=`refuted=False/clean`——亲手读完 v2 全 1349 行,无任一"更严"破口、构造不出"真可行却被拒"反例;当前 8 个 solve JSON 里三真锚点全 UNKNOWN,**没有任何真锚点 INFEASIBLE 被铸出**,唯一的 INFEASIBLE 全在毛面积 ghost(60×60/50×50/42×42 及加 area-cut 的 37×37/41×41,均真面积>4900、非假证书;36×36=4849≤4900 正确返 UNKNOWN)。verify:overall(codex)=`refuted=False/concern`——主线不被推翻。
- **成立条件(证书必须显式携带+重算)**:①generic-output 物理槽饱和不变量——名义容量 46×1+1×6=52 == required 52 == 实际(冻结快照 136 boundary_io pose 物理输出槽恒=1、6728 protocol_core 恒=6、物理>名义者 0、provider 闭合仅 boundary_io/protocol_core、可选设施 power_pole/box 不产 generic);**通用形式(名义容量)被前轮 codex 驳倒**(若某 pose 物理输出 cell>名义槽,一个 provider 吸收全需求令他者槽 unused → 对他者收 demand 过严 → 假 UNSAT),故 reverifier 必须重算"物理槽=名义槽 且 nominal==real==required",失败则 generic demand 降 0 或判 UNKNOWN,**绝不 fail-closed 保留 demand**。②M 建为不比全问题更严的松弛(build 义务,orientation int/str、occupied_cells 强转陷阱)。③ghost 原点全覆盖(7×7=4096 原点,用全域 x/y 决策,round4 harness 正确)。
- **I1 recompute-check 设计就绪**:reverify_front_lifted_master_unsat(哈希门控 5 冻结工件+源码 closure digest → 第二套白名单 builder 重建"更弱或等价"模型[不加载历史 cuts/symmetry/producer tightening,那些可能 unsound-更严] → build-only 审计[>1M vars/RSS>10G→UNKNOWN] → 单次异构 seed bounded solve → 仅字面 INFEASIBLE 才 CONFIRMED)。把死循环的"∀binding∀routing 枚举"坍缩成单个 bounded CP-SAT UNSAT。**暂不可执行**(无 INFEASIBLE 可复核)——性能/完备性阻塞,非 soundness 阻塞。

## 2. Termination(能否真拿到证书)= 新硬墙,双模型一致 still_unknown
- term:claude 与 term:codex 都 `still_unknown`:紧凑模型在**三真锚点 7×7/6×8/8×6 全 UNKNOWN**(codex:1200s,275137/451199/355138 分支,best_bound 0,单 worker VmHWM~1.65G;claude:7×7 600s UNKNOWN 74287 分支,复现一致)。
- **只有毛面积 ghost 秒判 INFEASIBLE**(60×60=0.051s,diagnostic_only)——证明 INFEASIBLE 链路通,不是目标锚点证书。40×40/41×41 虽面积矛盾但 CP-SAT 内建能量推理漏判(UNKNOWN);连"明显可行"的 1×1 ghost 都跑不出 FEASIBLE(presolve 卡/搜索找不到)——**不是编码坏或 OOM,是满足性模型本身对 CP-SAT 极难**。
- **新杠杆(term:claude v3)**:显式线性 area-cut(Σbody 面积 3553 + 4×active_poles + ghost_area ≤ 4900,非重叠蕴含的合法冗余不等式,只检出不误杀)——抓到 CP-SAT 能量推理漏掉的面积不可行(41×41/40×40 从 UNKNOWN 变 INFEASIBLE)。**但只对毛面积 ghost 有用,7×7 离面积墙远,救不了目标锚点。** 它示范了"加合法冗余割能让 solver 证出本来证不动的 INFEASIBLE"这条路。

## 3. 净判读 + 下一步
- **进展是实打实的**:上界证书 存在 + sound(条件明确)+ 紧凑(10.7K vars,29.4M 墓碑彻底证伪)+ 对抗杀不掉 + I1 复核设计就绪。round-1~3 的"没有便宜证书/上界硬墙/撞墓碑"全部被翻。
- **新墙**:sound 的紧凑模型 solver 证不动真锚点(1200s UNKNOWN)。**不是堆时间能解(600→1200s 零改善)**。
- **最便宜方向(zero-sealed,不碰认证核心)**:给这个 sound 松弛**加更强的合法冗余割(area-cut 已示范)/ 更好对称破除 / 分解**,让 CP-SAT 在真锚点上收敛。这是纯可解性工程。若仍证不动 → owner 级岔口(换算力/换证明技术/接受边界)。

## 4. 质量与诚实边界
6 席 claude+codex 双模型 + 2 席对抗验证,0 fatal 驳倒。全 zero-sealed 只读、未跑 master/main.py、未铸强状态。soundness 的严格证明(逻辑)+ 亲手代码复核(routing_subproblem.py:347/359/378/439-509、pose_bool_exact_master.py:315-343/244-313、binding_subproblem.py:1047-1086/1360-1426、master_model.py:2014-2039/2425)+ 亲手实算(饱和不变量 0 违反、area 边界 4922−37²=3553 一致)均已落。未验:紧凑 lift 能否在预算内终止(仍 UNKNOWN)、三 ghost 实际 UNSAT、area-42 witness 与 up-closure(证书链外部依赖)、harness M 忠实性逐条形式核验(暂不 load-bearing 因无 INFEASIBLE 产出)。结论是研究判读,非 certified 结果。
