# 对抗审查 — 规则形态轨设计稿（DESIGN_rule_form.md）

**日期**：2026-08-07　**席位**：对抗审查席（拒真/反例双职）　**被审对象**：同目录 `DESIGN_rule_form.md`（605 行）
**输入**：`failure_taxonomy_and_requirements.md`、`canonical_anatomy.md`、仓库现场（附录 B 全部为本席机器核实，命令与结果可复跑）
**施工边界**：只读仓库，只写本文件；未改 canonical、`src/`、`scripts/`、锁面文件；未跑 git 提交。

**一句话判决**：设计稿的分层骨架与成本形状分析站得住（§0），但它的**自验收章节 §7.1 不成立**、**两枪止血中的第二枪（C-15）回测失败**、**owner 点名的 exclusion 侧回测（箱收货能力被关三周）两个新装置都抓不到**，并且把最高频的两个产出面（`consumers[]`、`model_faces.candidates`）放进了冻结件——用的正是它自己论证「L2 不能进冻结件」的反面。共 **5 条 FATAL / 13 条 MAJOR / 7 条 MINOR**。

---

## 0. 先说站得住的部分（避免被读成整体否决）

以下四项经核实成立，修改建议不触及它们：

1. **成本形状的纠正是对的**：「成本 ≈ 固定 reseal 底价 × 批次数 + 抄录风险 × 接触条目数」与「不能一次改一个字段」——08-07 批实测 27 个 modified 文件一次提交（附录 B-9），碎批确实会把底价乘上批次数。
2. **否决选项 (c) 的四条论证成立**，尤其「失去 additive 安全论证」这一条：`facility_templates` 确被整体 deepcopy 进 tracked 派生工件，动它当场作废「八段 byte-identical」验收。
3. **L2 不进 `FROZEN_ARTIFACTS` 的三条理由成立**（节拍、权威等级、冻结文件表达不了条目级失效）。
4. **`reachability` 这个字段本身是本设计最有价值的发明**——把「参数在同一页」升级为「必须写出那一行算术」，正面回应分类学 F-2 漏洞③（参数早就在相邻两栏、六轮无人相乘）。本文对它的攻击全部针对**豁免口径**，不针对字段本身。

---

## 1. 逐病例回测（owner 点名的三案 + exclusion 侧）

回测口径：假设该机制在病例发生**当时**已全部上线（不追究排期），逐环节问「作者/checker 在那一刻会不会红」。

### 1.1 箱案（C-17，第一枪）— **部分挡住，但四道门里三道可合法绕过**

设计稿 §7.1 声称「四个独立位置挡住同一条病」。逐条核：

| 设计稿声称的门 | 回测结论 | 依据 |
|---|---|---|
| 实体条目 `buffer.slot_capacity` 必填 ⇒ 缺则进 `missing[]` | **弱**。`missing[]` 只产生一个计数，设计全文没有任何闸消费这个计数（§5.4 的方向暴露栏只消费 capability 的 `not_verified`，不消费 entity 的 `missing`）。按设计自己的 K-4 判据，无卡点的计数就是便签。另：08-06 的 `6 组×50` 其实已在 `AXIOM_KERNEL_PROPOSAL` 参数表里（分类学 F-2 漏洞③），所以当时未必会落进 `missing[]` | 设计 §5.4 vs §7.1 |
| 判据条目必填 `reachability` | **成立**。`slot_count_clause.statement` 确含 `blocks exactly when`（附录 B-4），词形触发器会打中 | 附录 B-4 |
| 作者写 `NOT_ASSESSED` ⇒ checker 红 | **不成立**。禁令只对 `scope: certified` **且** `direction: stricter` 的条目生效。箱条款是 owner 游戏实测的**游戏语义**陈述，按 §2.1 的 `direction` 定义（模型 vs 游戏）它就是 `exact`；`mixed_commodity_flow.statement` 自己写着 throughput OUT-OF-SCOPE、certified 谓词只管连通与几何，`scope` 也不该是 `certified`。⇒ 合法写 `direction: exact` + `verdict: NOT_ASSESSED`，绿灯通过。设计 §7.1 那一行是把该条目**误标**成 certified+stricter 才红的 | 附录 B-4、设计 §2.1/§7.1 |
| 闭包扫描独立命中（`capacity_vs_arrival`） | **不成立**。①它需要的正是同一个 `slot_capacity`；②`reachability.condition` 在设计里是**散文字符串**（"6 个缓存槽同时全占"），扫描器无法机器消费；③`capacity_vs_arrival` 这个检测器要把「口速率×冲刷周期」与「槽数×单槽容量」配对——**这个配对就是当时缺的那条领域洞察**，把它写进检测器等于假设结论已知 | 设计 §2.1 可达性块、§2.3 规则 3 |

**结论**：四道门不独立（三道共同悬在同一个缺失参数 + 同一个词形判定上），真正有效的只有「`reachability` 必填」这一道，且它的 `NOT_ASSESSED` 出口对这条病例是敞开的。→ 见 D-02。

### 1.2 均摊案（C-15，第二枪）— **挡不住**

设计的装置是：`premises[].kind: convention` + 形态 checker「凡 statement/derivation 出现分配/取值/摊派语义的算术，`premises` 里必须至少有一条 `kind: convention` 或 `assumption`，否则红」。

现场事实（附录 B-5）：`rate_lemma_scope.statement` 已经写着 `(ii) minimal-lane-allocation convention`——**C-14 那条约定当时已经在条目里了**。作者迁到新形态时会把它填成 `kind: convention`，checker 的存在性条件（≥1 条）**当场满足**，而缺的第二条约定（台间占空均摊）照样不在。

这与 C-16 是同一形态：**在已经找到的那条前件之上做加固，给缺的那条盖绿章**。设计 §3.2「防住 C-15/C-14（写条目时红）」这句被证伪。

补充证据（同型装置已经失败过一次）：`rate_lemma_scope` 全文唯一的 `usage_rule` 已经明文要求「引用者必须 discharge 两条前件」，C-25 仍然发生。设计的 `dischargeable_in`/`not_dischargeable_in` 是同一装置的字段化版本，且仍由作者自填——设计没有解释「这次为什么不同」。→ 见 D-05、D-12。

### 1.3 front 案（C-01/C-02）— **挡不住，且设计放弃了仓库里已经跑着的解法**

错的那个量是「口坐标 = 机身体外第几格」。新形态的实体镜像字段集是 `geometry{w,h,rotatable,is_solid_z}` / `ports{physical_inputs,outputs,port_rule}` / `buffer` / `cycle`——**没有任何一格装得下这个几何锚**，因此也不会有人把它写进 `missing[]`。设计 §8.3 自己把 C-01/C-02 列进「明确挡不住的」。

但仓库里已经有一台专治这一型的机器，设计一次都没提：`src/tests/cuts/test_helpers_power_cover_stencil.py` 把 `semantics.power_coverage_stencil` 与**三处实现**（`power_cover` helper / `placement_generator.gen_power_pole` / live master 的覆盖判据）钉成逐格等值，还刻意保留了「退役欧氏模型给出相反答案」的 divergence band——就是「哨兵必须选守卫是唯一防线的几何」那条纪律的实例（附录 B-3）。这台机器同时反驳了设计反复引用的前提「semantics 区零消费方 ⇒ 改它除哈希外无行为可观测面」。→ 见 D-08、D-14。

### 1.4 exclusion 侧回测（owner 点名）：**完整性台账与墙审计都不会更早抓到箱案**

**(a) `model_faces` 双向登记表**：§4.2 的三个登记触发器逐个空转——
- 「实现改动者」：箱的 class(2) 不是实现改动，是 canonical 条款；
- 「论证作者：支点是『模型碰巧更严』」：当时全线（我 + U-01 席 + 设计席）都认为它是**游戏真语义**，不是模型更严，所以不触发；
- 「拒真席：提交候选面 + 一个游戏合法但被模型拒的实例」：要举出那个实例，先得做 `15 vs 300` 那行算术——**这正是缺的那一步**。台账只装已经被怀疑的面。

**(b) 能力盘点（墙审计）**：三个枚举源里唯一的机器源是上游 IP 注册表。仓内已 vendored 该注册表（`src/adapters/industrial_planner/device_type_registry.json`，60,688 字节），实测**没有 slot / capacity / flush 任何字段**（附录 B-6）——它给的是 id / runtimeKind / size / requiresPower / ports / tags。⇒ 即便 S5 全量建成，箱的 6×50 与 10 s 也抽不出来。
更硬的一点：箱的收货能力本质是**吞吐**，而 K-7 把吞吐钉死为 OUT-OF-SCOPE，CAP 条目的 `model_expressibility` 会被正当地填成 `out_of_scope` 并归档——**新装置提供了一个把本案合法归档的出口**。

**(c) 覆盖率账**：`total / expressible / not_expressible / not_verified` 四数里，箱案不属于任何一格（它不是「能力不可表达」X-5，是「在册限制的界不可达」X-3）。**墙审计覆盖 X-5，不覆盖 X-3**，而箱案是 X-3。

**回答 owner 的问题**：不能。要更早抓到它，需要的是第三类审计对象——**「在册限制的界可达性台账」**（有界、可枚举：所有带数值界/阻塞条件的条款 × 其到达侧参数），加上「`NOT_ASSESSED` 的界不得被下游当既定前提消费」这一条消费侧闸。两者都不在本设计里。→ 见 D-02、D-06。

**顺带（不必等 S5，今天就能做）**：vendored 注册表 × canonical `facility_templates` 的差集是一条 30 行脚本就能跑的对账，`item_log_admission` / `item_pipe_admission` 就在注册表里（附录 B-6）——C-06 那类「整类器件不在册」今天即可命中。设计把它排到最后一阶段，白白压着一条已经能跑的机器对账。

---

## 2. 编号缺陷清单

### FATAL

---

**D-01｜FATAL｜`_epoch` 当「所有持久化结论的规则版本戳」是 unsound，且它重复发明了已有的机器版本号**

设计 §3.2：「`_epoch` 是一个只在 `semantics` 分区内部、每次语义区变更递增的整数……L2 的前提指纹与**所有持久化结论的规则版本戳**都绑它。」

- **不安全**：持久化 nogood / cut / 证书依赖的是 `globals`（tick、带容量）、`facility_templates`（几何）、`recipes`——这些都是 **L0**，改它们**不会**动 `semantics._epoch`。用 `_epoch` 当失效戳 ⇒ L0 一改，旧 nogood 静默存活。这正是 C-03 的病（结论缓存不绑规则版本、错结论被沉淀成持久化 cut）换个马甲复发，而且这次是**设计明文规定的**。
- **重复发明**：canonical 的字节 sha 已经是一个永不移动错、机器求得、runtime 可读（`certified_artifact_contract.py` 源码常量 + campaign hash 闭包）、且已被 17 处 pin 面维护的版本号。设计另造一个**靠人记得递增**的整数——而「靠人记得更新 pin」正是 C-49 的病因。
- **内部自相矛盾**：「不流入任何派生工件」与「所有持久化结论带它」不可兼得——带着它的持久化结论就是派生工件。

**修法**：①持久化结论的失效戳一律绑 **canonical sha**（过失效是安全方向，欠失效是 unsound）；②细粒度失效交给 L2 的 `premise_fingerprint`（它本来就覆盖逐前提现场取值，比 `_epoch` 更细）；③`_epoch` 若保留，降级为纯人读标记，写死「不得作任何失效判据」，并在 schema 里禁止它出现在任何 fingerprint 输入里。

---

**D-02｜FATAL｜§7.1 自验收不成立：四道门不独立，其中三道可合法绕过（箱案回测，详见 §1.1）**

`NOT_ASSESSED` 的禁令口径（certified ∧ stricter）对**游戏语义类条款**天然不适用，而箱条款正是这一类；`missing[]` 无消费闸；闭包扫描既缺同一个参数、又要求把散文 `condition` 机器化（设计未要求）、还得先把领域洞察编进检测器。

**修法**（三条，全部零冻结成本或低成本）：
1. **消费侧闸（最有效、可立即上线）**：任何 `reachability.verdict != "reachable"`／`== NOT_ASSESSED` 的条款，**不得作为承重前提被 L2 条目或承重文书引用**——与设计自己给 `candidates` 写的规则同规格。这条闸不需要动 canonical，落在文书模板 + L2 schema 上。
2. **`reachability.condition` 必须形式化**：`{参数 refs[], 关系式, 比较方向}`，使 checker 能对 `computation` 做**独立重算**而不是读散文。没有这一步，`verdict` 只是一句声明。
3. **`NOT_ASSESSED` 禁令改口径**：不看 scope/direction，改为「凡 statement 断言了数值界或阻塞条件的条目一律禁 `NOT_ASSESSED`」，同时把 `NOT_ASSESSED` 与 entity `missing[]` 的计数一并写进 §5.4 的方向暴露栏（让它有消费点）。

---

**D-03｜FATAL｜`consumers[]` 放在冻结件里 ⇒ 每写一篇引用条款的承重文书都要走一次 freeze-ritual**

§2.1 的 L1 条目与 §4.1 的 face 条目都必填 `consumers[]`，且 §4.1 规则 3 要求「论证作者……必须在**那条面的条目里**登记反向引用」，卡点是「文书入库/外发前」。canonical 是冻结件：加一行 consumer = 17 处 pin + 连锁 B/C/D + 全量门 + 慢 lane。

这与设计 §1.2 论证「L2 不能进冻结件」用的是**同一条理由**（高频、可撤销的产出付不起固定底价，结果是没人跑），设计却没把它应用到自己最高频的字段上。按 `slow-for-safety-can-be-slow-death` 判据：结构性走不完的保守支不是真选项。

**修法**：canonical 内只留稳定 `id`；**所有反向引用移到 L3 生成视图**（V2/V4），由扫描 L2 条目的 `premises[].ref` 与文书里的机器可解析引用标记自动生成；`consumers` 的完整性由 currency 测试（生成即比对）保证，不由人手登记。

---

**D-04｜FATAL｜`model_faces.candidates`（拒真席收件箱）放进 canonical ⇒ 拒真席被 ritual 成本掐死**

§4 把 `stricter` / `looser` / `candidates` 三个子表全部放进 `semantics.axiom_kernel`。`candidates` 是**提交箱**——它是整个 exclusion 补线里更新最频繁的面（每次承重文书评审都可能新增），每条提交要付一次完整 reseal。

结果可预测：拒真席要么不提交，要么攒批到季度级；而设计把 R-16 拒真席列为「把 2.5 : 16 补成一个成套层的最小集」之一。**补线的主装置被自己的形态锁死。**

**修法**：`candidates`（含 `rejection_risk`、`sentinel` 状态、`excluded_game_legal_instance` 草案）全部落 L2 `rules/derived/`；**只有 owner 裁定后的 `stricter` / `looser` 面进 canonical**，与设计自己写的「L2 → L1 晋级」通道完全一致。这也顺带解决 D-03 的一半。

---

**D-05｜FATAL｜C-15 回测失败：约定类前件的 checker 判据（≥1 条 convention）被已有的那条前件满足（详见 §1.2）**

存在性判据在这个病理上是错的形状：缺的从来不是「有没有约定」，是「**哪些自由变量的取值是被选的、每个选了什么**」。

**修法**：把无界的「前件完备性」换成**有界的自由变量覆盖率**——
- 条目的 `parameters[]` 已经强制列出所有量；在此基础上要求：凡 statement/derivation 中出现除法、摊派、per-lane / per-machine 归一化的算术，必须逐项声明其**分母的自由度来源**（`allocation_choices[]`：`{被分配的量, 自由度维数, 选定的约定, 该约定失效时结论怎么变}`）。
- 自由度维数是可机器求的（同一 operation 的实例数、车道数取自 L0），checker 断言 `allocation_choices` 覆盖每一个出现在算术里的分母，而不是「≥1 条」。
- C-15 的 42 维台间占空正是一个漏掉的分母（`x_op` 摊到 6 台），这条判据会打中它；C-14 的车道分配是另一个分母，两条都要写。

---

### MAJOR

---

**D-06｜MAJOR｜exclusion 侧回测失败：完整性台账 + 墙审计都抓不到箱案；墙审计覆盖 X-5 不覆盖 X-3（详见 §1.4）**

**修法**：新增第三类审计对象「**在册限制的界可达性台账**」——枚举面 = 所有带数值界或阻塞条件的条款（今天是有限的十几条），每条一行：{界的表达式, 到达侧参数, verdict, 最近核算日期, 谁在消费它}；并把 CAP 的 `out_of_scope` 取值改为必须附一句判定：「若该能力被表达，解空间会不会变大」——`yes` 的 out_of_scope 条目照样进 `not_verified` 计数，堵住把箱案合法归档的出口。

---

**D-07｜MAJOR｜「schema 是最便宜的有牙杠杆」与「schema 加入 FROZEN_ARTIFACTS」互斥，设计同时主张两者**

§3.1 的论证是「schema 不在 `FROZEN_ARTIFACTS` 里 ⇒ 改它零 pin 链 ⇒ 这是把形态要求变成有牙的最便宜路径」，紧接着建议把它加进 `FROZEN_ARTIFACTS`。冻结之后，形态契约的每次调整（S4 打开 required、S6 白名单去旧字段、以及此后每一次条目形态演进）都要付 pin + **连锁 C**：`scripts/preflight_gate.py` 的字节被 `src/tests/cuts/test_helpers_power_cover_stencil.py` 同族的 `test_rule_cut_evolution_authority_parity.py::_PROTECTED_SURFACE_SHA256` 钉住，而且那不是一行 sha——它带着「唯一授权后继」的叙事注释（附录 B-7）。「边际成本只有一行常量加一次 sha 更新」低估了。

**修法**：二选一，或换钉法——**把 schema 的 sha 钉在一个测试常量里**（例如现有 parity 测试新增一个受保护面条目），这样改 schema 不动 `preflight_gate.py` 字节、不触连锁 C，同样做到「改它要留痕、不能静默放松」。若坚持进 `FROZEN_ARTIFACTS`，必须在 §3.5 对照表里把「schema 改」从「(a) 改 schema、pydantic 不动」的低成本格挪出来。

---

**D-08｜MAJOR｜「semantics 区零消费方」被过度概括，导致设计放弃了一台仓库里已经在跑的机器**

现场：`src/tests/cuts/test_helpers_power_cover_stencil.py:100` 直接读 `rules["semantics"]["power_coverage_stencil"]`，把它与三处实现钉成等值，并保留 divergence band 防假 INFEASIBLE（附录 B-3）。所以正确表述是「**semantics 无 solve-path 消费方，但已有一条 canonical↔实现的等值哨兵**」。设计据「零消费方」把 C-02/C-08（规则改了实现没跟）整类判进「形态挡不住」，是从一个过宽的前提推出的放弃。

**修法**：L1 条目增两个字段 `implementation_anchors[]`（文件:行 或符号）与 `parity_sentinel`（测试 nodeid），按 power_cover 先例逐条补给高危条款（空矩形占用集、A5 front-cell 约定、箱口数、`_port_front_cell` 家族）。这比 V2 的文本索引强得多（见 D-09），且 08-07 批已经把实现锚点写进 A5 散文（附录 B-8），把散文抬成字段是纯 additive。

---

**D-09｜MAJOR｜V2 的「参数 → 代码 call site」列不可靠机器求出，且设计把 `authoritative_numbers` 先例读反了**

先例的自述（`src/tests/test_authoritative_numbers_currency.py` docstring）是：「**刻意不去扫散文里的过期整数**——文档是元文本地讨论这些数字，扫描到处假阳；健壮的强制函数是『核心节点值 == 现场重算』（零假阳风险）」。它只强制了**一个**可现场重算的数。设计把它读成「视图整体可以靠 currency 测试」。
而代码 call site 恰恰不可现场重算到所需保真度：C-41 已实证拼接字符串骗过 grep、`.rgignore` 把整类活代码投影出默认结果。

**修法**：V2 只保留可现场重算的列（canonical 内引用、L2 前提引用、frozen 工件内引用），代码侧改用 `implementation_anchors`（D-08）+ codegraph impact 查询作**辅助**，并在视图头部显式标注该列**非完备**（不完备的索引被当完备用，就是 C-27 的形态）。

---

**D-10｜MAJOR｜L2 currency 测试造出反向棘轮：canonical 越改越贵，与本设计的首要目标相反**

`premise_fingerprint` 覆盖「前提路径 + 现场取值」，currency 测试对每条 ACTIVE 条目重算、不符即红。⇒ canonical 改一个 `globals` 参数，**所有引用它的 ACTIVE L2 条目当场红**，该批必须连带处理完才能过门。而 L2 条目由饱和扫描自动增殖。**canonical 批的成本随 L2 规模线性增长**——设计的出发点是让 canonical 改动变便宜。

**修法**：分级失效 —— ①指纹不符的条目**自动**转 `STALE`（数据更新，不是人工裁决），不红；②只有当 `STALE` 条目**有 consumers**（被承重文书或更高 level 条目引用）时才阻断；③自动扫描产出的条目默认 `status: UNREVIEWED`，不计入阻断集。

---

**D-11｜MAJOR｜自动生成的 L2 条目缺审查闸，会成为「可复跑外观」的新一层错误来源**

设计给 L1←L2 设了晋级闸（owner 裁决/外审定谳），但 L2←L2 没有闸：`level = 1 + max(前提 level)` 允许扫描产出的 `unreachability` 条目**立刻**进入下一轮的前提池。一条取错参数或漏前件的机器结论，会带着 `receipt` / `recompute_cmd` 的踏实外观往上传播——C-32 四轮定谳的错型（勤奋全落在可复跑层，复跑的踏实感掩护未查的前提）在新架构里获得了自动繁殖能力。

**修法**：扫描产出一律 `UNREVIEWED`，须过一次拒真/反例席判定才转 `ACTIVE`；`premises` 中含 `UNREVIEWED` 的条目 **level 不递增、不可被任何文书引用**；`saturation_runs[]` 里同时记「本轮产出 n 条、已判 m 条」，未判条数进方向暴露栏。

---

**D-12｜MAJOR｜`dischargeable_in` 仍是作者自填，「封死 C-25」是过度声称**

§1.3 称 `scope == certified` 的条目必须每条前件的 `dischargeable_in` 都含 `certified`，「这一条同时封死 C-25」。但 C-25 的发生机制是**没人意识到**那条前件在 certified 下结构上不可 discharge；同一个人在新形态下会照样写 `dischargeable_in: ["certified"]`，checker 全绿。同型装置（`usage_rule` 要求 discharge 两条前件）已经失败过一次。

**修法**：把声明变成**可机器否证**的——`discharge_evidence` 必须是存在的路径或存在的测试 nodeid；`discharge_evidence == "MISSING"` 时 schema 强制 `dischargeable_in` 不含 `certified`。这样「没给证据就不能声称可 discharge」，从自由声明降为有代价声明。

---

**D-13｜MAJOR｜统一 required 字段集与实测条目形态冲突，S4 会把认证载入路径打红**

实测 `semantics` 下 14 个键（附录 B-1）：除 `_note` 外，`axiom_kernel`（kernel：status/adopted/role/scope_premises/axioms/…）与 `power_coverage_stencil`（纯参数对象：radius/anchor_footprint/coverage_shape）**都没有 `statement`**，不是 clause 形态。设计 §3.2 的 schema 收紧方案（`patternProperties` + 逐条目 `required` + `additionalProperties:false`，白名单只列 `_note/_epoch/_entry_contract/_template/_derivation_matrix/entities`）会把这两个键判红。

而 schema 校验在**两个**执行点硬失败：`preprocess_context._validate_preprocess_source_schemas`（认证载入）与 `placement_generator.load_templates`（冻结候选池生成路径），设计只算了前者（附录 B-2）。

**修法**：条目形态分三类（`clause` / `parameter_object` / `kernel`），`required` 按类分开（`entities` 归 parameter_object）；S4 落地前先跑一次离线断言「现行 canonical 字节 × 新 schema = 通过」，并把两个执行点都写进验收清单。

---

**D-14｜MAJOR｜front 型（C-01/C-02）无承载位，且已有解法未被复用（详见 §1.3）**

**修法**：同 D-08；另把 A5 这类「实现锚点型公理」单列一类，`implementation_anchors` 必填——A5 已经点名了 `_port_front_cell` 这个唯一转换点，把它抬成字段后，C-02 那种「某个 LEGACY_DIAGNOSTIC 面还在用 `port+DIR_DELTA`」可由 anchors 清单 + 反向扫描机械查出。

---

**D-15｜MAJOR｜「补齐批」实为整体重排的改名，设计用来枪毙选项 (c) 的理由同样适用于它**

补齐批的接触面：13 个条目全部（`required` 全开 + `applies_to` 拆三字段 + `predicate_status` 全覆盖）+ 3 处父句原地改写 + 新增 `semantics.entities` + `model_stricter_faces` 由字符串改结构化对象。这已经是 `semantics` 区的全量重写。设计 §3.4 判 (c) 死刑的核心理由是「重写过的散文不可机器验证等价，人眼逐行已被 C-15 证伪」，而补齐批的验收手段正是「逐条目的**人工裁决记录**」——同一手段在 (c) 是死刑理由、在自家批次是可接受。K-1 明令重排批必须带逐条目机器 diff。

**修法**：把补齐批再切成两批——
- **搬迁批（机器可验）**：拆字段、加必填、`model_faces` 结构化、`entities` 新增。全部是字段级搬迁，可逐字段映射机器比对（旧值 → 新位置逐项断言相等）。
- **改写批（不可机器验）**：仅 3 处父句 + `superseded_readings`。条目数小到可以逐条走双席裁决 + owner 确认，且与 D-16 的在案决策冲突一并上桌。

---

**D-16｜MAJOR｜实体镜像的等值锚只覆盖不承重的字段；承重参数是仓内第四份拷贝且 provenance 不可复验**

§2.2 规则 2 要求镜像与 `facility_templates` **双向等值**——但 `facility_templates` 只有 `dimensions/rotatable/needs_power/is_solid_z/port_rule` 五键（附录 B-1），承重参数一个都不在里面：
- **口数**另有一份在**冻结**的 `rules/preprocess_plan.json`：`utility_operations.box_sink.generic_input_slots = 3`、`generic_output_slots = 0`（附录 B-6）。注意语义还不同（generic slot ≠ 物理口：箱有 3 个物理输出口但 generic_output_slots 记 0）。镜像写 `physical_outputs: 3` 与它并排放着，**零等值检查**。
- **buffer / cycle**（6 槽、单槽 50、10 s）来自**未 vendored** 的模拟器源码快照 `IndustrialPlanner@8da9017a`——仓内 vendored 的 `device_type_registry.json` 实测无 slot/capacity/flush 字段（附录 B-6）。⇒ 一个进冻结件的承重数字，**在仓内无法复验**。

结果：新增的是第四份拷贝（canonical 散文 / preprocess_plan / 镜像 / 批次参数表），承重部分零等值锚——这正是 C-12 的形态（参数表是批次工件、与条目零交叉引用），只是搬进了冻结件。

**修法**：①口数与 `preprocess_plan` 建显式对照字段（含「generic slot vs physical port」的差异说明），checker 断言两者关系而非相等；②buffer/cycle 必须配 **vendored 抽取产物 + 抽取脚本 + 收据 + 上游 commit**，并加一条与 `src/adapters/industrial_planner/*.json` 同族的 currency 检查；做不到就不许进冻结件，先留在 L2。

---

**D-17｜MAJOR｜视图当权威的缓解手段在本仓已被证伪**

§3.3 承认 (b) 引入净新增风险（视图被当证据），缓解 = 「视图头部写死非权威声明 + 每个数字带出处路径」。反证：被当标签消费的 `mixed_commodity_flow.terminal_clause` 是**冻结的、owner 裁决的、正文里就写着 "slot-count wording is deliberate" 的**权威条款；`rate_lemma_scope` 甚至内嵌了 `usage_rule`。两者都没挡住（C-17 / C-25）。一个更短、更方便、一键可达的生成视图只会被更多地当标签，不会更少。

**修法**：闸放到**消费侧**并做成机器判据——承重文书与 L2 条目的前提集中出现 `docs/generated/` 路径即红（与 `src/cuts/ledger.py` 那条「ledger 永不作 cut 来源」同规格）；视图路径只许出现在「检索记录」栏。

---

**D-18｜MAJOR｜排期与止血优先级倒置**

推荐组合把两枪的实际止血（`reachability` / `premises` 必填）放在 S3，且建议与别批合批等窗口；先行的 S1 交付 V1 实体参数表，理由是「把六个量放在同一页」。但分类学 F-2 漏洞③已经实证：箱的入量参数与容量参数**当时就写在参数表同一行的相邻两栏**，六轮审查无人相乘。⇒ S1 对第一枪的边际增益接近零，而它占着首发位。

**修法**：把 D-02 修法①（`NOT_ASSESSED` / 界不可达条款不得作承重前提，落文书模板与 L2 schema）与 D-05 的 `allocation_choices` 提到 **S0**——两者都不动 canonical、不需要 freeze-ritual 窗口，是真正能当天上线的止血；V1 视图降为 S1 的附属产物。

---

### MINOR

**D-19｜MINOR｜§4.2「不履行的后果」那一列是空头支票**：「形态 checker 的 `direction` 对账发现无主的更严面 ⇒ 门红」——没有任何 checker 能从代码 diff 判定「模型变严了」，那正是本批要解决的问题本身。**修法**：换成可实现的替代闸：diff 触碰 routing/binding 守卫文件集时，批次记录必须勾选「本批新增过严面：有/无（有则列 face id）」，由 preflight 的 diff 范围检查强制（形态同既有 `code_assets.json` 分类机制）。

**D-20｜MINOR｜`parameters[].value_at_write` 是死重或漂移源**：checker 若断言它与 canonical 现值相等，字段冗余（直接解引用即可）；若不断言，它就是新一层过期标签——本批要治的正是过期标签。**修法**：删除 `value_at_write`，L1 只留 `ref`；快照值只在 L2 的 `value_at_derivation` 保留（那里有指纹语义支撑）。

**D-21｜MINOR｜`premise_fingerprint` 缺规范化规格**：键序、Decimal/分数表示（现场有 `11/2`、`10/17`、`21/22` 这类精确有理数）、以及 `kind: assumption` 前件「无值可取」的处理都没写。不写死 ⇒ 跨平台/跨会话指纹不稳 ⇒ currency 测试随机红 ⇒ 被静音。**修法**：明写序列化规格并复用 `src/io/strict_json.py` 的 exact-decimal 语义；assumption 类前件的指纹取其规范化 statement + 显式版本号。

**D-22｜MINOR｜`derived_rules.json` 单文件 + `saturation_runs[]` 运行日志混装**：规则与运行日志两种生命周期塞进同一 tracked JSON，多会话/多 worktree 并发写必然合并冲突（仓内已有 amend 撞车与 `.index` 缓存两次教训）。**修法**：一条目一文件（`cc_memory_vnext/cards/` 已有先例）+ 运行日志走 `.artifacts/` JSONL。

**D-23｜MINOR｜R-08 与 08-07 批的在案形状决策冲突，未登记也未走裁决位**：`RESEAL_MANIFEST.md` §6 明记「修正采 additive 形状……依据任务书『不删不改任何现有条款的语义本体，只加推导注记』」，并写明「owner 若偏好就地改写 statement，属简单再编辑 + 重走同一连锁」。设计直接写「废止打补丁形态」，没提这是在撤销昨天的任务书决策——按 R-24（档案检索前置）这是同型失误。**修法**：§9 增列第四项 owner 裁决「是否撤销 08-07 的 additive 形状决策」，附两条路径成本。

**D-24｜MINOR｜`capability_register` 三源之一的 `OWN-M*` 台账实为批次文书，且设计对它与 `#1–#21` 双标**：实测 OWN-M 编号只密集出现在 `docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md`（53 处），编号有缺口（M25/M26/M28 缺，附录 B-10），不是冻结件、不是台账。设计要求把推导编号表 `#1–#21` 内置进 canonical 消除悬空引用，却让承担能力枚举的 OWN-M 继续悬空。**修法**：同批把 OWN-M 结构化（与 `_derivation_matrix` 同规格），或明确降级为「索引，不作权威」并从三源里去掉。

**D-25｜MINOR｜`rules/derived/` 的外发风险无防线**：设计已把它列为 owner 裁决项 3，但只谈了「与 rules/ 全是冻结件的直觉冲突」。真风险是 C-50 同型——非冻结的 `rules/` 子目录被外发包夹带后，接收方无法从路径判断权威等级。**修法**：目录内每个文件必填头部 `_authority: NON_FROZEN_DERIVED`，且打包脚本的白/黑名单显式列出该目录。

---

## 3. 修法优先级（给下一轮设计席的最小集）

零 freeze-ritual、可当天上线：**D-02①（界不可达/NOT_ASSESSED 条款不得作承重前提）、D-05（`allocation_choices` 覆盖每个分母）、D-03/D-04（反向引用与 candidates 移出冻结件）、D-17（`docs/generated/` 引用即红）**。这四项把两枪止血与 exclusion 收件箱全部落在非冻结面上，且不占 freeze-ritual 窗口。

必须在 S3 之前定的：**D-01（失效戳改绑 canonical sha）、D-07（schema 钉法二选一）、D-13（条目形态分类 + 两个 schema 执行点）、D-15（补齐批再切两批）**。

必须在 S4/S5 之前补的：**D-06（界可达性台账 = 墙审计的第三类对象）、D-16（承重参数的 vendored provenance）、D-08/D-14（`implementation_anchors` + parity sentinel，复用 power_cover 先例）、D-10/D-11（分级失效 + 扫描产出 UNREVIEWED）**。

---

## 附录 A：本文没有攻击的面（避免被读成已审全）

- **推理流程轨**（`DESIGN_reasoning_process.md`）本文未审，两轨接口（R-15/R-16/R-20/R-29）的可行性归对方审查席。
- **箱案与均摊案的领域数学本身**（15 vs 300、42 维占空自由度）本文只作回测素材引用，未复算。
- **schema/pydantic 的具体 JSON 写法**未逐条起草，只给形态分类要求（D-13）。
- **字段填得对不对**这一格本文与设计同意：schema 与 checker 管在场与一致性，管不了正确性。

## 附录 B：本文依据的仓库事实（现场机器核实，2026-08-07）

| # | 事实 | 核实方式 |
|---|---|---|
| B-1 | `semantics` 共 14 键；`axiom_kernel` 与 `power_coverage_stencil` **无 `statement`**（前者 status/adopted/source_doc/role/scope_premises/axioms/ruling_level_inputs/model_stricter_faces；后者 applies_to/power_coverage_radius/anchor_footprint/coverage_shape/generator/axiom_derivation）；`facility_templates` 条目只有 dimensions/rotatable/needs_power/is_solid_z/port_rule | `python3 -c` 逐键 dump `rules/canonical_rules.json` |
| B-2 | canonical schema 有**两个**执行点：`src/interchange/preprocess_context.py:611-624`（`_validate_preprocess_source_schemas` → `jsonschema.validate`，由 `load_default_preprocess_context` 与 `load_preprocess_context_from_paths` 调用）与 `src/placement/placement_generator.py:470-476`（`load_templates` 内 `validate_json_schema`，冻结候选池生成路径） | 源码逐行 |
| B-3 | `src/tests/cuts/test_helpers_power_cover_stencil.py:100` 读 `rules["semantics"]["power_coverage_stencil"]`，把它与 `power_cover` helper / `placement_generator.gen_power_pole` / live master 覆盖判据钉成等值，并保留退役欧氏模型的 divergence band（docstring 自述「band cases are load-bearing」） | 文件 + `src/cuts/helpers/power_cover.py` docstring |
| B-4 | `protocol_storage_box_wireless.slot_count_clause.statement` 含 `blocks exactly when its 6 slots are all occupied`；`mixed_commodity_flow.statement` 明写 throughput/bandwidth OUT-OF-SCOPE、certified 谓词只管 connectivity 与 geometry | canonical dump |
| B-5 | `rate_lemma_scope.statement` 已含 `(ii) minimal-lane-allocation convention`，且 `usage_rule` 已要求引用者 discharge 两条前件 | canonical dump |
| B-6 | 箱口数另存于**冻结**的 `rules/preprocess_plan.json`：`utility_operations.box_sink = {facility_type: protocol_storage_box, generic_input_slots: 3, generic_output_slots: 0}`；vendored `src/adapters/industrial_planner/device_type_registry.json`（60,688 字节）**无 slot/capacity/flush 字段**，但含 `item_log_admission` / `item_pipe_admission` 等准入口器件 | `python3 -c` dump 两文件 |
| B-7 | `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` 的 `_PROTECTED_SURFACE_SHA256` 钉住 `scripts/preflight_gate.py` 的字节（并带「唯一授权后继」注释），另钉 `PROJECT_LOCK.md` sha 与 P1.2 sink 集 | 文件正则提取 |
| B-8 | 08-07 批已把 front-cell 约定写进 `axiom_kernel.axioms.A5_interfaces`：「the stored port coordinate in candidate placements IS the front/belt cell itself……converts only via the single `_port_front_cell` helper」 | canonical dump |
| B-9 | 08-07 canonical 批：17 处直接 pin + 连锁层 + 史料门；提交 pathspec 27 modified + 1 new dir；`RESEAL_MANIFEST.md` §6 记「修正采 additive 形状……依据任务书『不删不改任何现有条款的语义本体』」 | `RESEAL_MANIFEST.md` §1/§4/§6 |
| B-10 | `OWN-M` 编号实测 M01–M24 + M27 + M29（M25/M26/M28 缺），密集出处只有 `AXIOM_KERNEL_PROPOSAL_20260806.md`（53 处）与 `VERIFICATION_ANNEX_20260806.md`（27 处） | `rg -o "OWN-M[0-9]+" \| sort -u`、`rg -c` |
| B-11 | `src/tests/test_authoritative_numbers_currency.py` docstring 自述：刻意不扫散文过期整数（假阳到处是），健壮强制函数只有「核心节点值 == 现场重算」，且包 README 的投影未接线仍会漂 | 文件 docstring |
| B-12 | `docs/generated/` 目录当前不存在；`data/repository_governance/code_assets.json` 登记 `rules/canonical_rules.schema.json`（分类登记，非哈希 pin） | `ls` + JSON dump |

---

*本文件只写本路径下的对抗审查结论。未修改 `rules/canonical_rules.json`、`rules/canonical_rules.schema.json`、任何 `src/`、`scripts/` 或锁面文件，未跑 git 提交。*
