# 开放欠账台账 v1

> 建册日期：2026-08-15
>
> 权威边界：本台账把“知道有问题”升级为“谁负责、何时到期、逾期挡什么”。owner 已在 2026-08-15 裁定追记（`3d34687`）接受第 4 件，另行授权 `rules/derived/` 非冻结立架；本台账本身仍不授权修改 `src/`、`scripts/`、`data/` 或 `rules/` 既有冻结件，不启动 freeze-ritual，也不把其余七件待裁事项写成已批准。
>
> 负责人说明：下列负责人均是角色级临时责任席，用于确保欠账有人追；不是 owner 对优先级、人选或实现方案的逐项批准。涉及新增埋点的实现仍待 owner 第 7 件裁定。

## 1. 记账规则

1. 每条欠账有稳定 id、状态、负责人、到期日、阻断范围和关闭证据。
2. 状态受控词：`OPEN`、`OPEN_AUTHORIZATION_PENDING`、`OPEN_REVALIDATION`、`CLOSED_AT_BOOTSTRAP`、`SUPERSEDED`。
3. 关闭不能删除原行；必须补关闭日期、证据与“不再阻断什么”。
4. 到期日当天结束仍未关闭即为逾期。逾期不自动把结论判假，但阻断范围立即生效并上报收批席。
5. “列出 call site”不等于完成。每个 call site 单列状态，允许同一历史欠账在当前树分化为已修、作用域例外或仍开放。
6. 证明类结论依赖开放欠账时，必须写 `conditional` 并在方向暴露栏标欠账号；不得用“已登记”抵消阻断。

## 2. 首批索引

| id | 类别 | 对象 | 状态 | 临时负责人 | 到期日 | 阻断摘要 |
|---|---|---|---|---|---|---|
| OD-B0-C08-01 | C-08 call site | `benders_loop._extract_occupied_cells` | CLOSED_AT_BOOTSTRAP | strict-emptiness 复核席 | 2026-08-15 | 无，当前主 LBBD 路径已有代码与哨兵 |
| OD-B0-C08-02 | C-08 call site | fixed-witness occupancy | CLOSED_AT_BOOTSTRAP | terminal witness 复核席 | 2026-08-15 | 无，当前 fixed-witness 路径已有代码与哨兵 |
| OD-B0-C08-03 | C-08 call site | `build_routing_binding_context` | OPEN_REVALIDATION | binding/routing 语义复核席 | 2026-08-22 | 不得把该 context 单独当 strict-emptiness 证据 |
| OD-B0-C08-04 | C-08 call site | heuristic finder routing occupancy | OPEN | heuristic 认证语义复核席 | 2026-08-22 | `ghost_rect != None` 时不得无条件消费其 `CERTIFIED` |
| OD-B0-INST-01 | 埋点 | fail-closed、拒绝率与反向哨兵观察面 | OPEN_AUTHORIZATION_PENDING | 批 5 观察性设计席 | 2026-08-29 | 无埋点处不得写“真零”、拒绝率或已覆盖 |
| OD-B0-CANON-15 | canonical 措辞 | C-15 `rate_lemma_scope` 占空前件与 usage | CLOSED_AT_BOOTSTRAP | canonical 20260808 执行席 | 2026-08-08 | 无，旧欠账保留为历史行 |
| OD-B0-CANON-17 | canonical 措辞 | C-17 箱槽位/接收不变量措辞 | CLOSED_AT_BOOTSTRAP | canonical 20260808 执行席 | 2026-08-08 | 措辞本体不阻断；下游理由重核见 CHAIN-769 |
| OD-B0-CHAIN-769 | 连锁重写 | 定理 #21 与 U-01 箱口限制的理由重核 | OPEN_REVALIDATION | 批 0 连锁重写总责席 | 2026-08-22 | 两个下游结论不得沿用旧理由；删除动作被挡 |
| OD-B1-PACKAGE-01 | 打包接线 | `rules/derived/` 白／黑名单接入 `scripts/package_review_snapshot.py` | OPEN | 外审快照接线席 | 2026-08-29 | 不得声称标准外审包已自动纳入非冻结派生层 |
| OD-B1-THEOREM-REG-01 | 登记面耦合 | 未来 theorem registry 与 `rules/derived/` 状态机的形态对齐 | CONDITIONAL | 重设计线登记面对齐席（届时指派） | 无（触发器键控） | 触发前无阻断；触发后未对齐前不得声称两面登记机制同形态 |

台账当前数据非空：`10` 条，其中开放/待复核 `5` 条，条件项 `1` 条，启动时已关闭 `4` 条。前 8 条是批 0 首批；`OD-B1-PACKAGE-01` 是 owner 2026-08-15 第 4 件裁定后的批 1 追加事件；`OD-B1-THEOREM-REG-01` 是 2026-08-16 两线联合结论的追加事件。

## 3. C-08 四个 call site

历史权威坐标：`failure_taxonomy_and_requirements.md` C-08 与 `REFUTE_reasoning_process.md` M-07，旧树列出四个位置。批 0 按当前符号重新定位，不沿用漂移行号。

### OD-B0-C08-01：主 LBBD occupancy

| 字段 | 值 |
|---|---|
| 历史位置 | `src/search/benders_loop.py::_extract_occupied_cells`，旧记录约 `:8081` |
| 当前位置 | `src/search/benders_loop.py:8287`；函数把 `ghost_cells` 加入 routing obstacle set |
| 当前哨兵 | `src/tests/test_ghost_strict_emptiness.py:139` `test_extract_occupied_cells_includes_ghost_cells`；同文件还覆盖 owner map、digest 与 fail-closed ghost 解析 |
| 状态 | `CLOSED_AT_BOOTSTRAP` |
| 关闭日期 | 2026-08-15，批 0 只读核验当前树 |
| 关闭证据 | 源码显式 `occupied_cells.update(...)`，且专门测试钉住 ghost-inclusive 语义 |
| 不再阻断 | 主 LBBD 当前 occupancy extractor 的 strict-emptiness 消费 |
| 仍不证明 | 其他复制实现自动等值；它们各自看本表其他行 |

### OD-B0-C08-02：terminal fixed-witness occupancy

| 字段 | 值 |
|---|---|
| 历史位置 | `src/search/pr2_l0_fixed_witness_core.py`，旧记录约 `:875` |
| 当前位置 | `src/search/pr2_l0_fixed_witness_core.py:1758` `_extract_pose_resolved_occupancy` |
| 当前哨兵 | `src/tests/test_ghost_strict_emptiness.py:666` `test_witness_pose_resolved_occupancy_includes_ghost`，并覆盖 body-overlap fail-closed |
| 状态 | `CLOSED_AT_BOOTSTRAP` |
| 关闭日期 | 2026-08-15 |
| 关闭证据 | ghost cells 同时进入 occupied set 与 reserved owner map；body 落入 hole 直接拒绝 |
| 不再阻断 | 当前 terminal fixed-witness 路径的 strict-emptiness occupancy |
| 仍不证明 | 任何绕过 `_extract_pose_resolved_occupancy` 的新 witness path |

### OD-B0-C08-03：routing binding context 的作用域例外

| 字段 | 值 |
|---|---|
| 历史位置 | 旧记录为 `routing_binding_context.py:97`；当前文件为 `src/models/routing_binding_context.py` |
| 当前位置 | `src/models/routing_binding_context.py:65` `build_routing_binding_context` |
| 当前行为 | 显式排除 `ghost_pick` 等非设施 marker；注释给出的理由是该 context 可发出跨 anchor 的 unconditioned placement nogood，混入 ghost 会让 ghost-dependent 判定被全局应用 |
| 当前哨兵 | `src/tests/test_rab_sep_soundness_sentinels.py:225` 钉住 `ghost_pick` 即使有 pool 也必须排除 |
| 状态 | `OPEN_REVALIDATION`，不是简单“把 ghost 加进去” |
| 临时负责人 | binding/routing 语义复核席 |
| 到期日 | 2026-08-22 |
| 关闭动作 | 画清所有消费者：证明该 context 只承担 ghost-agnostic binding/nogood 角色，且任何可能产出 strict-empty witness 的路径随后必经 ghost-inclusive routing core；增加或指定一个跨层 parity sentinel。若证明不了，改作用域或降级消费者，不得直接照抄主 extractor |
| 阻断范围 | 不得把 `build_routing_binding_context` 本身引用为“空矩形什么都不能有”的实现证据；任何只凭该 context 出厂的 strict-emptiness 结论保持 conditional |
| 关闭所需证据 | 消费者穷尽清单 + 可执行跨层哨兵 + refute 对 unconditioned cut 语义的复核 |

### OD-B0-C08-04：heuristic finder 的 ghost 空洞

| 字段 | 值 |
|---|---|
| 历史位置 | `src/search/heuristic_feasible_finder.py`，旧记录约 `:169` |
| 当前位置 | `src/search/heuristic_feasible_finder.py:92` `_extract_occupied`；routing core 构造约 `:169` |
| 当前行为 | `_extract_occupied` 只读 facility pose 的 `occupied_cells`；`ghost_rect` 只传入 greedy proposal，没有进入 routing/flow obstacle set；函数末端仍可返回 `HeuristicFinderResult(status="CERTIFIED")` |
| 状态 | `OPEN` |
| 临时负责人 | heuristic 认证语义复核席 |
| 到期日 | 2026-08-22 |
| 关闭动作 | 二选一：A. 把所选 ghost anchor 解析成 ghost-inclusive occupancy，并钉住 routing/flow/owner map 等值；B. 对 `ghost_rect != None` 禁止返回强 `CERTIFIED`，改成不被认证消费者接受的候选状态。需新增针对 hole 穿路的红测与闭合后的绿测 |
| 阻断范围 | 在关闭前，任何 `ghost_rect != None` 的 heuristic `CERTIFIED`、由它导出的严格空地见证或 release/certification 强声明均不得无条件消费；最高为带本欠账号的 conditional/候选 |
| 关闭所需证据 | 源码修复或强状态降级 + 定向测试 + strong-status 写入面复核；本批不改代码 |

## 4. 埋点欠账

### OD-B0-INST-01：fail-closed 与拒绝面观察性

| 字段 | 值 |
|---|---|
| 来源 | `FINAL_DESIGN.md` §4.7、§4.9 第五卡点及批 0“埋点欠账”要求 |
| 状态 | `OPEN_AUTHORIZATION_PENDING` |
| 临时负责人 | 批 5 观察性设计席 |
| 到期日 | 2026-08-29，先交有限存量清单与提案；代码实施等待 owner 第 7 件裁定 |
| 最小范围 | 本批新增 fail-closed 分支；存量清单中会影响 certified/UNKNOWN/过滤/剥落/降级的分支；触发器激活计数；理由码；剥落与降级计入拒绝率；限制删除后的反向哨兵；canonical ↔ implementation parity sentinel 指针 |
| 关闭动作 | 先提交“有限存量清单 + 每项现有观测点 + 缺口 + 预计成本”；owner 裁定后再实施。实施后凭据只能二选一：`真零（有埋点，计数=0）` 或 `无埋点（欠账号）` |
| 阻断范围 | 没有观测点时不得写“分支从未触发”“拒绝率为 0”“剥落没有发生”或“删除后无回归”；证明类结论必须填“无埋点 + OD-B0-INST-01”并按影响方向降级 |
| owner 待裁标记 | 新增第五卡点与代码埋点属于第 7 件，仍待 owner 逐项拍板；本行只建立欠账和设计交付期限 |

## 5. canonical 措辞两笔

### OD-B0-CANON-15：C-15 rate lemma 措辞

| 字段 | 值 |
|---|---|
| 原欠账 | `rate_lemma_scope` 的结论依赖台间占空分配，但旧前件只写满产与最少车道；REJUDGE 要求重写而非补一句 |
| 状态 | `CLOSED_AT_BOOTSTRAP` |
| 历史负责人 / 到期日 | canonical 20260808 执行席 / 2026-08-08 |
| 关闭证据 | `docs/research/canonical_batch_20260808/DRAFT_DIFF.md:198` C16 把等占空拆成事实半与假设半，并保留逐机器局部最少车道前件；`:220` C17 改写 usage rule；当前 `rules/canonical_rules.json` 已含新字段与限制语境 |
| 关闭日期 | 2026-08-08，批 0 于 2026-08-15 回读确认 |
| 不再阻断 | 旧的“canonical 还欠占空前件”表述 |
| 保留边界 | ordinary certified result 仍不自动清偿这些前件；这不是把 rate lemma 升成无条件证书事实 |

### OD-B0-CANON-17：C-17 箱条款措辞

| 字段 | 值 |
|---|---|
| 原欠账 | 协议箱槽位纪律、单槽容量、class (2) 接收不变量与冻结实例 discharge 的措辞需入 canonical |
| 状态 | `CLOSED_AT_BOOTSTRAP` |
| 历史负责人 / 到期日 | canonical 20260808 执行席 / 2026-08-08 |
| 关闭证据 | `docs/research/canonical_batch_20260808/DRAFT_DIFF.md:158` C14 改写 slot_count clause，`:174` C15 新增 cache parameters 与 blocking reachability note；current canonical 对 class-level bounded absorber 与 instance-level discharge 分层表述 |
| 关闭日期 | 2026-08-08，批 0 于 2026-08-15 回读确认 |
| 不再阻断 | canonical 措辞本体 |
| 保留边界 | 下游若仍沿用“C-17 待判”或“箱只是有界吸收所以限制多余”的旧理由，必须走 OD-B0-CHAIN-769；措辞关闭不自动修复消费者 |

## 6. FINAL_DESIGN :769 连锁重写触发

### OD-B0-CHAIN-769：箱案下游理由重核

| 字段 | 值 |
|---|---|
| 触发源 | `FINAL_DESIGN.md` 文末“未清的欠账”中 superseded R3/BLOCK-10 段，当前约 `:769` |
| 变化 | C-17 最终判为“件数维度无条件、槽数维度 conditional on 单槽容量 provenance”；旧的“两个箱待判项未决，所以全部下游待核”已收窄。但两个消费者仍需重核，理由从 C-17 待判改为分类标签的界物理不可达与删除三签 |
| 状态 | `OPEN_REVALIDATION` |
| 总责席 | 批 0 连锁重写总责席 |
| 总到期日 | 2026-08-22 |
| 总阻断 | 两个消费者不得沿用旧理由；U-01 不得据旧判执行删除；定理 #21 不得把分类标签本身当完整前提 |

子动作：

| 子项 | 负责人 | 到期日 | 必做 | 阻断范围 |
|---|---|---|---|---|
| CHAIN-769-A：定理 #21“箱只是有界吸收”引用 | 定理 #21 复核席 | 2026-08-22 | 回读定理精确结论，把理由改成可核参数账：3 个输入口、10 s 冲刷、6 组/单槽容量、到货上界与当前路由语义；区分 class-level bounded 与 frozen-instance unreachable；跑消费三闸 | 在关闭前，凡以该标签单独支撑箱堵塞不可达、准入口不必要或证明类排除的结论均为 conditional |
| CHAIN-769-B：U-01“箱口限制多余、二期删” | U-01 限制复核席 | 2026-08-22 | 按八步模板第 2 步重跑可达性签；补具体游戏合法拒真实例搜索；删除必须有可达性签、拒真签、owner 签并走 freeze-ritual | 在关闭前，禁止删除/放宽该限制，禁止把“多余”作为无条件现态；最多登记为删除候选 |

关闭条件：两份独立复核凭据均存在，引用者落四态，开放项有新阻断范围；只改一句摘要或把负责人写进表不算关闭。

## 7. 批 1 打包接线欠账

### OD-B1-PACKAGE-01：非冻结派生层进入外审快照的显式名单

| 字段 | 值 |
|---|---|
| 触发源 | `OWNER_DECISION_SUMMARY.md` 头部 2026-08-15 裁定追记（`3d34687`）：第 4 件＝接受；批 1 立架建真目录，打包脚本接线挂后批 |
| 当前声明 | `rules/derived/manifest.json.package_declaration` 已列 include/exclude、目标脚本与本欠账号 |
| 状态 | `OPEN` |
| 临时负责人 | 外审快照接线席 |
| 到期日 | 2026-08-29；角色级临时期限，不冒充 owner 对后续批优先级的逐项批准 |
| 关闭动作 | 在独立后批修改 `scripts/package_review_snapshot.py`：显式读取或等价实现 manifest 的白／黑名单；增加 `unzip -l`／包清单回归，证明 `rules/derived/` 需要的文件在包内、canonical 既有冻结件未被误装成派生件；按当批边界重跑相应门禁 |
| 阻断范围 | 本欠账关闭前，不得写“标准 GPT Pro／外审快照会自动携带 L2 派生层”；若需外发，必须人工逐项对账并在外发台账注明临时组包路径 |
| 本批边界 | 批 1 不修改 `scripts/`；只把名单声明落在 `rules/derived/manifest.json` 并建账 |

## 8. 联合结论条件项

### OD-B1-THEOREM-REG-01：未来 theorem registry 与非冻结派生层的形态对齐

| 字段 | 值 |
|---|---|
| 触发源 | 2026-08-16 两线联合结论：推理外环架构草案已引用 `rules/derived/` 的 UNREVIEWED 状态机／前提指纹／currency 测试为「未来定理登记面」的形态先例 |
| 状态 | `CONDITIONAL`（触发器未到，无到期日） |
| 触发器 | 编译器官（金丝雀 5 号/6 号）获 owner 批准转入常态消费，或任何「theorem registry 实例化」提案出现 |
| 关闭动作 | 触发后两面对齐：research 侧 theorem registry 采用与 `rules/derived/` 同形态的状态机／指纹／currency／`_authority` 头，或显式登记分叉理由；结论回写本行 |
| 阻断范围 | 触发前无阻断；触发后未对齐前，不得声称「两面登记机制同形态」 |

## 9. 逾期与消费视图

| 视图 | 当前值 |
|---|---|
| 开放或待复核 | `OD-B0-C08-03`、`OD-B0-C08-04`、`OD-B0-INST-01`、`OD-B0-CHAIN-769`、`OD-B1-PACKAGE-01` |
| 条件项（触发器未到） | `OD-B1-THEOREM-REG-01` |
| 已关闭但保留历史 | `OD-B0-C08-01`、`OD-B0-C08-02`、`OD-B0-CANON-15`、`OD-B0-CANON-17` |
| 逾期 | 建册时 `0` |
| 证明类结论默认动作 | 依赖开放行则标 `conditional`，方向暴露栏写欠账号 |
| 删除限制默认动作 | 三签未齐则禁止删除 |
| 无埋点默认动作 | 写“无埋点 + OD-B0-INST-01”，不得写真零 |
