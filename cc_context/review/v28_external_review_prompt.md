# 终末地 IndustrialPlanner 精确求解器 — Phase 1.2 spike close 严格闭关审查

## 现状与本包

项目是 Arknights: Endfield 工业规划器的 **certified-exact** 求解器:在 70×70 网格上求最大空矩形,目标 `max_lex(area, min_side)`(先最大化面积,再最大化最短边),需在 266 个强制设施实例约束下**证明最优**。引擎是 OR-Tools CP-SAT + Benders/LBBD 分解(master 放置 → binding 端口 → routing 布线 → flow 诊断);收紧 master 的范式由 9 个 cut family(F1–F9)构成,每个 family 既是 cut 生成器又是 cut 验证器。

**真瓶颈不是找可行解,而是证明上界**:certified 路径必须保证 (a) 每条加进 master 的 cut 都是 sound 的——不会因一个伪造/错算的 cert 而错误剪掉合法布局;(b) spike 所验证的 prod-scale master 集成,在真实规模下数值可行。本包是 **Phase 1.2 spike close 大节点**的交付:在进入 P1.3A(真 `PoseBoolExactMaster` 接入 LBBD + 多轮收敛)之前,验证 prod-scale 的 sizing 与 cut-family soundness 是否站得住。

**包内含**:完整项目 `src`(9 个 cut family 实现+验证器、master/binding/routing/flow 子问题)、spike 代码镜像(`code_context/spike/`,带 `SHA256SUMS.spike_code.txt` 逐字节清单)、spike 数据/telemetry/`verdict.md`、sizing gate 脚本 `docs/research/p1_2_spike_sizing_gate_20260601/sizing_gate.py` + `RESULTS.md`、cut family 测试(cuts 子集 418 passed)、全部 spec/docs。**包不含**:CC 侧交接/记忆/打包脚本工件,以及含密钥的 `scripts/gemini_cross_check*.py`(排除以免泄漏 API key)——这些与 certified 证明无关,排除是刻意的。

**上一轮审查 verdict = GO_WITH_MINOR,3 处 doc-currency 补丁已应用 → 本包。** 此外本包在外审之间经过一轮严格内部多代理审查,逮到并修复了一个 **HIGH 级 F7 soundness 漏洞**:F7(`power_hitting_set`)验证器此前**未**把 cert 内的数值字段(`pole_radius`)与 `state.canonical_rules` 的 source-of-truth 交叉核对(fail-open),意味着一个把 `pole_radius` 篡改后的伪造 cert 可能通过验证、错误地收紧 master。现已补 `_validate_pole_radius_sot`(fail-closed,镜像 F8 早有的同款守卫),cuts 测试 413→418。**这个洞此前数轮外审都漏了**——所以本次审查的首要 axis 是:**还有没有同源的兄弟漏洞**。

详细 README 在包内 `README.md`(顶层)与 `project/README.md`。

## 已 verdict NOT_GO 的 paradigm 历史(欢迎挑战)

项目在落到当前 cut-family LBBD 范式前,已对 27 个 lever 给出 NOT_GO verdict(anchor slicing / witness preflight / weighted occupancy / set-packing prover / lazy power completion / augmented master / IHS / Benders symmetry 等),死因 + reproducer 见包内 docs。当前活范式 = pose-bool master(B1)+ 9 cut-family LBBD。

这些不是「禁止讨论」,是「当时数据/当时方法 verdict NOT_GO」。如果你看到我们当时漏的角度、有新算法跨过当时门槛、或 prior reproducer 数据本身有问题,**直接 push back**,不要因 prior verdict 自我审查。

## 本次审查重点(按 axis)

**A. Soundness(首要)** — 9 个 cut family 的验证器,是否每个都把 cert 内的数值字段与 `state.canonical_rules` source-of-truth 交叉核对、fail-closed?刚在 F7 找到一个 fail-open 漏洞(见上)。请**对抗性地**检查 F1–F6、F8、F9 是否存在同源兄弟洞:能否构造一个数值被伪造(放大/缩小某 capacity / radius / coverage)的 cert,让某个 family 的验证器误判为合法、从而错误剪掉本应保留的布局?各 family 的 fail-open 判定路径在哪、缺哪个 SoT 交叉核对?

**B. Sizing-math 正确性** — sizing_gate 的投影数(type-pool 81,795;concrete master proxy 325,747;F9 single-group 784 / same-template 4,608 / all-manufacturing 11,644;F4 20,157;OR-Tools 线性约束 ~4.03 bytes/term、BoolOr ~10.01 bytes/term)是否 sound?特别是 **F9 single-group invariant**:验证器(`src/cuts/families/density_envelope.py`)拒绝 witness group ≠ cert group,从而把单条 F9 cut 的向量界在 784(单组上界);11,644 是跨组 all-manufacturing 压力代理、4,608 是同模板代理。这个「单组上界」推断对吗?有没有路径让单条 cut 实际触及跨组规模?

**C. Phase-boundary 决策(请明确选项)** — spike 交付是否足以**关闭** Phase 1.2 这个大节点、进入 P1.3A(真 `PoseBoolExactMaster` 接入 LBBD + 多轮收敛)?请明确在以下之间选:(a) 现在可关闭、进 P1.3A;(b) spike 证据不足,需补哪些**具体**证据才能关;(c) 交付结构有问题需重构。**不要 default 接受「现状已 ship 看起来合理」**——如果 (b)/(c) 更 sound,直接 push back。

**D. Doc-currency / reproducibility** — 包内所有文档(顶层 README、`project/README`、`verdict.md`、`RESULTS.md`、sizing_gate 注释)对权威数字是否一致(cuts 418、F3 micro-probe 12/12、remap_audit 36/150 pairs = 24%、F9 single-group)?有没有 stale claim(某处仍写旧值)?数字能否从包内脚本/数据复现?

**E. Exactness constitution / scope creep** — 有没有违反项目宪法(`PROJECT_LOCK.md`):把 exploratory cap 当 exact-mode 上界、跨 instance lift cut(F9 锁单组 / within-instance)、把 exploratory 工件当 certified proof、或改 proof/cert schema 而未同步 lock/spec/test?

## 优先关注方向(不限于此)

- F1–F9 验证器的 fail-open 兄弟洞(对抗性构造伪 cert)
- sizing 投影的隐藏前提(单组上界、proxy 代理的代表性)
- spike → P1.3A 的证据链是否够 close 大节点
- 文档间数字一致性 + 可复现性
- **不限于以上** —— 任何你认为威胁 certified 正确性的角度

## 硬性输出约束(两条)

1. **不可达必须形式化证明** — 若 finding 暗示某方向「做不到 / 必须 X / 不能 defer / 某界不可能」,**必须给形式化证明**:complexity reduction(problem X ≤_p problem Y 的具体构造)、proof-system lower bound(resolution / cutting-plane unsat proof size 下界,cite Haken / Beame–Pitassi 等)、resource inequality(变量数 / 内存 / 时间的具体不等式),或引文献(paper / theorem 名 + 年份)。**不接受** "I believe" / "intuitively" / "based on my experience" / "通常这样" 等 vague claim;若确实只能给直觉,请显式标 "intuition only, no formal bound"。

2. **给出补丁并打包** — 不要只指出问题,对每个可修的 finding 给出能直接落地的补丁(哪个文件、改成什么,最好是可 apply 的 diff 或替换用代码/文案片段,可标把握度);补丁与 finding **不必 1:1**(一个补丁可覆盖多条,怎么组织你定)。最后把审查说明文档 + 补丁以压缩包(zip)形式给出。

## 最后将文档和补丁以压缩包的形式给出

包 sha256: `c00a957c73f1a05b532de73451aff8676fc0e3303dfc453bd62630e4b06e5253`
