# 规则系统重设计线批 1 自量凭据

> 凭据版本：v1，2026-08-15
>
> 模板：`docs/research/rule_system_redesign_20260807/batch0_20260815/EIGHT_STEP_TEMPLATE_V1.md`
>
> 当前结论：`FINAL_PASS_WITH_OPEN_DEBTS`。四件工具交付、五条定向验收与批尾共享文档三检均已完成；owner 已放行，三检全绿。开放欠账与其余七件待裁事项继续保留，不因本批通过而关闭。
>
> 权威边界：owner 已在 `OWNER_DECISION_SUMMARY.md` 头部 2026-08-15 裁定追记（提交 `3d34687cd244e82fda41ff18b88171e7b45298b1`）接受八件之第 4 件，故本批获准建立 `rules/derived/` 非冻结派生层。该裁定只批准目录形态；第 1 件③、第 2、3、5、6、7、8 件仍逐项待裁。本凭据不把 L2 条目、生成视图或工具输出升级为 canonical、owner authority 或 certified 结论。

## A. 批头

| 字段 | 本批填写 |
|---|---|
| 批 id / 标题 | `RULE-SYSTEM-REDESIGN-BATCH1-20260815` / 非冻结派生层与六视图工具批 |
| 日期 / 分支 / 起始基线 | 2026-08-15 / `main` / `3d34687cd244e82fda41ff18b88171e7b45298b1` |
| 当前主工具提交 | `368c3602b09b445de5a9bc2d241a68c40d6c9dff` |
| 当前凭据提交 | `9b5128d39880969128b56b3216353ad7d2518b2c` |
| 批尾共享基线 | `fd86ef8`；包含 owner 授权后的 `rules/derived/` 治理 carve-out、code-assets census 与硬编码根计数归一 |
| 一句话目标 | 把编号索引、上游差集、L2 派生条目与 L3 检索视图变成 tracked、可冷启动重算、可故意打红的开发侧工具链 |
| Plan / 立论 | 本对话执行席；按 `FINAL_DESIGN.md` §6 批 1 行逐项施工 |
| refute | 同一执行席的第二遍反向审查 + 21 个专门测试；不冒充人员独立核签 |
| 拒真 | 重点查四类误伤：`UNREVIEWED` 漂移是否被过度阻断、差集是否被误读成不可表达、视图是否被当权威、schema 是否偷钉 canonical SHA |
| 收批 | 本对话执行席完成批 1 自量；owner 已放行，批尾三检全绿，最终 verdict 见本文件末尾 |
| owner 已裁事项 | 第 4 件 `rules/derived/` 非冻结子目录＝接受 |
| owner 仍待裁事项 | 第 1 件③、2、3、5、6、7、8；本批不得顺手扩权 |
| 本批明确不做 | 不改 `rules/` 既有文件；不改 `src/`、`scripts/`、`data/`；不碰 freeze-ritual；不钉 canonical schema SHA；不接 CI 硬门；不实施运行时埋点；不修改 §0b 正文 |
| 工具身份 | `devtools/` 仓库治理面、非 certified TCB；只读 import `src.io.strict_json` exact-decimal 语义 |
| 本批证据上限 | 工具与投影的确定性、现有 tracked 文书/registry 的纯抽取事实；不产生新的游戏事实、模型完备性或数学 closure 结论 |

### 待裁总声明

1. **第 1 件③**：墙审计若发现不可表达能力后的放开优先级，仍等首轮清单，不在本批裁。
2. **第 2 件**：是否撤销三处“只加不改”形状决策，仍待裁。
3. **第 3 件**：canonical schema SHA 的钉法，仍待裁且属于批 2；本批 manifest 写死 `OUT_OF_SCOPE_BATCH_2_OWNER_DECISION_PENDING`，测试反向断言当前 SHA 未被写入。
4. **第 4 件**：已接受；仅授权 `rules/derived/` 非冻结目录及本批立架。
5. **第 5 件**：形态／凭据 checker 是否进 CI、何时转硬门，仍待裁。本批命令是人工运行的开发门。
6. **第 6 件**：§0b 三处正文改动仍待 owner 认可；本批只沿用批 0 模板，不改正文。
7. **第 7 件**：第五卡点和代码埋点仍待裁；`OD-B0-INST-01` 不因本批工具上线而关闭。
8. **第 8 件**：拒真席默认排法仍待 owner 裁；本批自量的反向 pass 不替代独立席制度。

## 第 0 步：批型判定与档案检索

### 0.1 七条件逐条判定

| 条件 | 触发 | 理由 | 本批动作 |
|---|---|---|---|
| ¹ 引用分类标签或定量参数 | 是 | 索引计数、registry 数量、canonical 参数和前提指纹均为本批输入 | 跑完整参数账与出处形态分级 |
| ² 新增或保留限制 | 是，治理限制 | `UNREVIEWED` 不得消费、`STALE + consumers` 才阻断、视图非权威 | 步骤 2 与双向保真必跑 |
| ³ 影响模型可行集 | 否 | 工具不进入 solver、candidate pool、certificate 或生产谓词 | 不跑模型 freeze／全树门禁 |
| ⁴ 修改冻结参数、配方、目标量或实例集 | 否 | canonical 与 schema 只读；SHA 仅记账，不写回 pin | 保留 byte identity 记录 |
| ⁵ 出现只有 owner 能定的残余 | 是 | 其余七件仍待裁；第 3、5、6、7、8 与本批邻接 | 显式拒绝顺手裁定 |
| ⁶ 触及承重代码语义面或工件字节 | 否于生产面 | 只新增 `devtools/` 与非权威投影；`src/io/strict_json.py` 只读 import | 工具测试而非 certified 回归 |
| ⁷ 触及 fail-closed、过滤、剥落或降级路径 | 是于 currency | 陈旧条目须显示；ACTIVE 有消费者时阻断，UNREVIEWED 不阻断 | 变异自证与正例反向哨兵必跑 |

### 0.2 批型结论

本批为“纯工具、tracked、非 certified TCB”的复合治理批：

- 交付 ①②是纯抽取／差分工具，结论上限是“在声明输入域内找到了什么”。
- 交付 ③是 L2 形态与 currency guard，改变消费门而不改变模型可行集。
- 交付 ④是 L3 非权威视图，必须同时验证可重生性与“不被当权威”的反向边界。
- 因批表要求五项实测且用户要求完整八步凭据，本凭据执行步骤 0 至 7；无科学结论处明确写“不适用”，不以空白冒充完成。

### 0.3 权威与仓内检索

| 路 | 输入 | 结论 | 本批消费方式 |
|---|---|---|---|
| 批次权威 | `FINAL_DESIGN.md` §6 批 1 行 | 四件交付、五条验收 | 范围权威 |
| owner 门牌 | `OWNER_DECISION_SUMMARY.md` 2026-08-15 追记，`3d34687` | 第 4 件接受；其余七件未扩权 | `rules/derived/` 唯一授权根 |
| 编号语料 | `AXIOM_KERNEL_PROPOSAL_20260806.md` + `VERIFICATION_ANNEX_20260806.md` | tracked 面可纯抽取 89 个 distinct id | `git grep` 为计数权威；`rg` 只作旁证 |
| vendored registry | `third_party_snapshots/industrial_planner/entity-definition.master.ts`，上游 commit `dd334ed5...` | 61 个顶层实体 id | 只读差集输入 |
| canonical | `rules/canonical_rules.json#/facility_templates` | 7 个 template id | 冻结机器真源，只读 |
| adapter 映射 | `src/adapters/industrial_planner/mapping_registry.py::_FACILITY_MAPPINGS` | 9 个显式 target id | 只读，用于避免把已显式映射者误列直接缺口 |
| 批 0 开放账 | `OPEN_DEBT_LEDGER.md` | 追加 `OD-B1-PACKAGE-01` | 打包接线后移，不改 `scripts/` |

### 0.4 docctl 与 owner 授权冲突处置

对 `rules/derived/*` 跑 `docctl context --intent edit` 时，通用 `rules/` policy 仍报告 owner-only、默认 `ALLOWED: no`。本批没有绕过该门，而是使用更具体、更新的 owner 显式裁定 `3d34687`：只准新建 `rules/derived/` 非冻结子目录，不准修改相邻既有文件。处置如下：

- 所有新文件根头均带 `NON_FROZEN_DERIVED` 与中文“非冻结派生件”声明。
- `git diff -- rules ':!rules/derived/**' src scripts data` 实测为空。
- 没有修改根 `DOC_POLICY.json` 或扩大整棵 `rules/` 的默认权限。

### 0.5 canonical 新鲜度

| 对象 | SHA-256 | 本批动作 |
|---|---|---|
| `rules/canonical_rules.json` | `c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0` | 只读；没有修改 |
| `rules/canonical_rules.schema.json` | `db8e1d6b63f1e31474257604b013068ec0435902a12aeb738a9cfa3c8396ed61` | 只读；当前 SHA 被测试确认未写入 schema/manifest pin |

## 第 1 步：参数账

### 1.1 编号索引账

`git grep` 输入域固定为两份权威语料。实测：

| 项 | 值 | 出处形态 |
|---|---:|---|
| distinct id | 89 | `git grep` 全 tracked 指定语料 |
| `OWN-M*` | 26 | M01–M24、M27、M29 |
| `SIM-M*` | 26 | 纯抽取 |
| `SIM-P*` | 10 | 纯抽取 |
| `SIM-R*` | 5 | 纯抽取 |
| `SIM-U*` | 5 | 纯抽取 |
| `W-*` | 17 | 纯抽取 |
| 明确缺号 | 3 | `OWN-M25`、`OWN-M26`、`OWN-M28` |

`rg` 在本次显式文件输入上旁证同为 89；但 `.rgignore` 可把路径投影掉，因此 manifest、JSONL HEADER、测试和凭据均把 `git grep` 写成计数权威。

### 1.2 registry 差集账

| 量 | 值 | 真源 |
|---|---:|---|
| vendored 顶层实体 id | 61 | `entity-definition.master.ts` 顶层 `id:` 纯抽取 |
| canonical `facility_templates` | 7 | frozen canonical |
| 显式 adapter target id | 9 | `_FACILITY_MAPPINGS` 纯抽取 |
| 当前直接登记的 vendored id | 9 | vendored ∩（template id ∪ adapter target） |
| `NOT_DIRECTLY_REGISTERED` | 52 | 差集脚本 |
| 必须命中 | 2/2 | `item_log_admission`、`item_pipe_admission` |

边界：`NOT_DIRECTLY_REGISTERED` 不是“模型不可表达”。generic template、routing state 或后续映射都可能承载同一能力；真正的表达力四态留给墙审计。

### 1.3 L2 指纹与形态账

| 项 | 当前值 | 说明 |
|---|---|---|
| schema | `rules/derived/derived_rule.schema.json` | Draft 2020-12；只约束形态 |
| 一条目一文件 | `entries/D-B1-SCAFFOLD-001.json` | 文件名与 id 相等 |
| 初始状态 | `UNREVIEWED` | 不得承重消费 |
| premise fingerprint | `4dcf493d32fab29d37f79996e5637bcd08aa51504b863c337d2eac32f679da13` | D-21 规范 |
| source premise | `rules/canonical_rules.json#/globals/logistics/belt_capacity_per_tick = 1/1` | exact-decimal 现场值 |
| assumption premise | statement + `assumption_version=1` | 不编造数值 |
| consumers | `[]` | 样例无承重消费者 |
| sentinel | 指向变异测试 nodeid | 可执行反向哨兵 |

### 1.4 D-21 指纹规范

- loader：直接 import `src.io.strict_json.load_strict_json_exact_decimal`。
- 对象键排序，数组顺序保留，字符串 NFC，CRLF/CR → LF。
- 所有整数／十进制与 `{exact_rational: p/q}` 化为约分有理数；拒绝 binary float。
- `source_value` 同时记录当前 source path + JSON Pointer + 现场值，并把 `value_at_derivation` 单独比对，防止重算指纹洗掉历史取值。
- `assumption` 取规范化 statement + 显式版本号。
- `derived` 取被引 id、level 与其 premise fingerprint。
- `_epoch`、schema SHA、mtime、绝对路径、locale、Python hash seed 均排除。

### 1.5 L3 视图账

| 视图 | tracked 字节 | 当前可见内容 | 权威上限 |
|---|---:|---|---|
| V1 实体参数 | 10,645 | 7 个 template；MISSING 共 53 | 检索视图 |
| V2 参数反向索引 | 10,247 | 13 个参数族；canonical/L2/冻结工件/代码列 | 代码列非完备 |
| V3 条目－谓词矩阵 | 6,688 | 13 个 semantics + `axis_without_axiom` | 六谓词全部 `NOT_ASSESSED` |
| V4 三审计台账投影 | 2,739 | 墙 bootstrap 141 行输入；界开放账 9 行；孔未建立 | 不产 verdict |
| V5 能力覆盖率 | 6,050 | 61 个 vendored id；9 显式映射，52 直接缺口 | 表达力统一 `NOT_ASSESSED` |
| V6 派生闭包图 | 1,572 | 1 节点、2 前提边 | level 不等于饱和 |

### 1.6 MISSING 与替代口径

| MISSING / 不可得 | 替代 | 状态与边界 |
|---|---|---|
| 两台物理机器 | 两个独立 Python 冷进程；不同 cwd、`PYTHONHASHSEED` 与空环境 | 仅证明当前实现跨独立进程稳定，不证明不同 OS/CPU/文件系统实现 |
| 代码 call site 穷尽性 | `git grep` 字面叶键，最多列 3 个定位点 | V2 表头强制“非完备”；不得当全仓消费者全集 |
| canonical schema pin 决策 | 明写 `OUT_OF_SCOPE_BATCH_2_OWNER_DECISION_PENDING` | 第 3 件仍待裁，本批不补 |
| 标准外审包自动接线 | manifest 声明 + `OD-B1-PACKAGE-01` | `scripts/package_review_snapshot.py` 未改，不得声称已自动携带 L2 |
| 六谓词逐项映射 | 全部 `NOT_ASSESSED` | 批 1 不替批 3/6 作审计 verdict |

## 第 2 步：可达性尺子

### 2.1 四个工具 guard

| guard | 危险条件 | 六选一判定 | 保守代价 | 摘除／关闭条件 |
|---|---|---|---|---|
| 编号索引 currency | tracked 语料新增/删去编号但索引仍旧 | 限制成立；保证方＝当前 git grep + append-only event 模型 | 语料变化需追加事件 | 当前 active id 与 git grep 集合一致 |
| L2 currency | 前提现场值与派生时值漂移 | 限制成立；保证方＝本 guard 自己 + source 真源 | ACTIVE 有消费者时阻断；UNREVIEWED 只显示 | 重推并过审，或退休/换代 |
| 差集解释闸 | “未直接登记”被读成“不可表达” | 限制成立；保证方＝显式边界与全量 `NOT_ASSESSED` | 不能直接拿差集下模型死刑 | 墙审计给出具实例 verdict |
| L3 消费闸 | 生成视图被当 canonical | 限制成立；保证方＝每个根 `_authority` + 批 0 G2 | 消费者必须回读 source_refs | 不允许摘除；视图本质恒非权威 |

### 2.2 反向哨兵

- `UNREVIEWED` 条目即使历史取值漂移，也必须 `stale=True` 但 `blocking=False`。
- 同一条目转 `ACTIVE` 且拥有 consumer 后，前提漂移必须 `blocking=True`。
- 差集中的 admissions 可以进入墙审计候选，但不能直接写“模型表达不了”。
- V3/V5 的未判格必须保持 `NOT_ASSESSED`，不能用空字符串或“无”假装已核。
- schema/manifest 不得出现当前 canonical schema SHA。

## 第 3 步：前件卫生

### 3.1 七问

| 问 | 本批答案 |
|---|---|
| 自由度问 | 指纹只冻结声明的 premise material；不把文件时间、路径根、hash seed 等环境自由度混入 |
| 约定问 | 数字统一 exact rational；数组顺序保留而不擅自当集合；编号语料域显式限定两份文书 |
| 量词问 | “索引一致”只对声明 source_paths 成立；“差集”只对顶层实体 id 与直接登记集合成立 |
| 语境问 | L2/L3 为研究治理层，不能自动进入 certified；`ACTIVE` 也不等于 canonical |
| 权威问 | owner 裁定只授权目录；canonical、vendored registry、adapter 与批次推导各自保持原权威等级 |
| 使能问 | `_authority` 不是免责声明装饰，消费闸 G2 仍在下游强制回读 source_refs |
| 聚合问 | 计数以 distinct id/set 差集为准；每个数字在视图内带 source；`rg` 不参与权威计数 |

### 3.2 聚合与闭合层扫描

| 操作 | 隐含前件 | 处置 |
|---|---|---|
| `git grep` distinct count | 正则、source_paths、tracked 面固定 | HEADER 记录；测试逐项列 OWN ids 和缺号 |
| vendored 差集 | 顶层 id regex 与显式 adapter targets 是“直接登记”口径 | interpretation boundary 明写不等于表达力 |
| premise fingerprint | exact decimal、指针可解析、assumption 版本存在 | fail closed；binary float 禁止 |
| V2 code refs | 字面叶键可能高度非唯一 | 最多 3 个定位点；表头“非完备” |
| V4 三账 | 孔账未建立、墙/界只有 bootstrap 输入 | `NOT_ESTABLISHED` / `INPUTS_ONLY_NO_VERDICT` |
| V6 level | 深度不等于已审与已穷尽 | `UNREVIEWED` 和饱和禁语保留 |

### 3.3 六层覆盖

| 层 | 状态 | 说明 |
|---|---|---|
| 几何层 | 未审 | 仅投影 template 参数，不判几何正确性 |
| 速率/算术层 | 仅 exact-decimal 载入与指纹 | 不重证速率引理 |
| 参数来源层 | 已审 | source path、pointer、vendored commit、adapter target 明列 |
| 语义锚点层 | 已审形态，未审内容 | 语义 entry 可见，谓词映射 `NOT_ASSESSED` |
| 实现一致层 | 已审工具自身 | 21 测试、currency、冷进程一致；不覆盖 solver 实现 |
| 方向暴露层 | 已审 | 非完备、未判、非权威、开放欠账均显式 |

## 第 4 步：owner 裁决包

本批不新建 owner 裁决包：第 4 件已由 owner 直接裁定，仓内可计算的 schema、差集、指纹与视图均已自行完成。其余七件继续留在原决策表，不把工具实现偏好包装成新的 owner 事实题。

固定问题“这包里有没有本可以自己算的？”答案：没有包；所有可仓内计算项均已实测。需要 owner 的仍是既有七项产品/权威选择。

## 第 5 步：连锁重写

### 5.1 第 4 件裁定后的现行文书同步

| 文件 | 旧表述 | 新表述 | 历史保留 |
|---|---|---|---|
| `CONSUMPTION_GATES.md` | “不建立 `rules/derived/`” | 指向 `3d34687`：目录已获准，但候选/UNREVIEWED 仍不得承重 | `BATCH0_SELF_RECEIPT.md` 不改 |
| `EIGHT_STEP_TEMPLATE_V1.md` §7.4 | “尚未批准、不得创建” | 产出落 `rules/derived/entries/<id>.json`；目录身份非冻结 | 历史批 0 自量不改 |
| `OPEN_DEBT_LEDGER.md` | 无打包接线行，且总括句仍是八件全待裁 | 新增 `OD-B1-PACKAGE-01`；总括句改为第 4 件已批、其余七件待裁 | 原 8 条批 0 首批仍保留 |
| `OUTBOUND_REVIEW_LEDGER.md` | fen5 当前作用域仍写八件全部待裁 | 记录第 4 件已接受，但不把 fen5 或单项批准外推成整套方法获批 | 历史外发包记录不改 |

### 5.2 打包接线后移

`rules/derived/manifest.json.package_declaration` 已声明 include/exclude、目标脚本和欠账号，但本批不改 `scripts/package_review_snapshot.py`。关闭前：

- 不得声称标准外审包自动包含 `rules/derived/`。
- 临时外发须人工 `unzip -l` 对账并在外发台账注明。
- 后批接线需同时证明派生层进包、canonical 既有冻结件没有被误归类成派生件。

### 5.3 六类消费者

| 类别 | 本批结果 |
|---|---|
| canonical 条目 | 零修改；schema SHA 不钉 |
| 仓内承重文书 | 只同步批 0 两份现行工作文书与开放账 |
| 兄弟线净输入 | vendored registry 与 adapter 只读 |
| 代码 call site | V2 只给非完备定位，不宣称名单闭合 |
| 记忆/知识层 | 六视图不进入记忆 authority；批尾 doc intake 尚待放行 |
| 在飞外部输入 | 标准 package 接线开放，见 `OD-B1-PACKAGE-01` |

## 第 6 步：双向保真验收

### 6.1 正向：工具必须抓到的坏形态

- 编号索引漏 id 或保留已消失 id → `check-ruling-index` 红。
- 手改 ACTIVE 条目的 `value_at_derivation` → `stale=True` 且 `blocking=True`。
- generated view 任一字节不等于冷重算 → `check-views` 红。
- admissions 没进入直接缺口 → `check-facility-gap` 红。
- `rules/derived/` 任一文件缺 `_authority` → `check-derived` 红。
- manifest 偷写 canonical schema SHA 或把 package 标已接线 → 测试红。

### 6.2 反向：合法形态不得被误伤

- `UNREVIEWED` 漂移可见但不阻断；测试 `test_unreviewed_stale_entry_is_visible_but_nonblocking` 通过。
- assumption 通过 statement + version 进入指纹，不要求伪造数值。
- `NOT_DIRECTLY_REGISTERED` 只进入候选清单，模型表达力保持 `NOT_ASSESSED`。
- V1 的 MISSING 是“没有字段”，不是“参数为零”。
- V4 孔审计零行写 `NOT_ESTABLISHED`，不是“无孔”。
- V2 `code_call_sites_non_exhaustive` 明写非完备，不把前三个定位点当全集。

### 6.3 工具测试

命令：

```text
.venv/bin/python -m ruff check \
  devtools/rule_system_tooling.py \
  devtools/tests/test_rule_system_tooling.py
.venv/bin/python -B devtools/rule_system_tooling.py check
.venv/bin/python -B -m pytest -q devtools/tests/test_rule_system_tooling.py
```

结果：ruff 全绿；完整 check `ok=true`；`21 passed in 0.65s`。

## 第 7 步：饱和扫描

### 7.1 本批圈层

| 层 | 扫描对象 | 结果 |
|---|---|---|
| 层 0 | 批 1 四件、五验收、第 4 件裁定边界 | 全覆盖 |
| 层 1 | 指纹×状态机、差集×能力含义、视图×消费闸、manifest×打包脚本 | 发现 1 笔新开放欠账：`OD-B1-PACKAGE-01` |
| 层 2 | schema pin、CI 硬门、运行时埋点、§0b、拒真排法 | 全部回到既有待裁表，没有擅自继续扩张 |

### 7.2 终止状态

本批只做有限工具面扫描。V5 明确把 61 个能力的表达力统一记为 `NOT_ASSESSED`；V6 只有一条 scaffold 节点。不存在“规则闭包已饱和”“全仓消费者已穷尽”或“能力全集已审完”的合法结论。

| scope | rounds | new_entries | terminated_by | 状态 |
|---|---:|---:|---|---|
| 批 1 工具与边界 pairwise | 2 | 1 个开放欠账 | 第二轮无新的本批内可执行项 | `PAIRWISE_FIXED_POINT_INCOMPLETE` |

## B. 四件交付物

### 交付 ①：裁决编号纯抽取 append-only 索引

- `rules/derived/ruling_index.jsonl`
- generator/checker：`devtools/rule_system_tooling.py`
- 形态：HEADER + `IDENTIFIER_EVENT` + `GAP_EVENT`；刷新只追加，不原地删改历史事件。
- 输入域、计数方法和 rg 旁证边界写在 HEADER。

### 交付 ②：vendored registry × facility templates 差集

- generator/checker：`devtools/rule_system_tooling.py`
- 首份 tracked 输出：`rules/derived/facility_template_gap.json`
- vendored 61、直接登记 9、差集 52；admission 两项均命中。

### 交付 ③：L2 `rules/derived/` 立架

- `rules/derived/README.md`
- `rules/derived/derived_rule.schema.json`
- `rules/derived/manifest.json`
- `rules/derived/entries/D-B1-SCAFFOLD-001.json`
- `rules/derived/ruling_index.jsonl`
- `rules/derived/facility_template_gap.json`
- currency、state machine、D-21 指纹、one-entry-per-file、`_authority`、package declaration 均已落真址。

### 交付 ④：L3 V1–V6 视图生成器与 currency 测试

- generator/checker：`devtools/rule_system_tooling.py`
- tests：`devtools/tests/test_rule_system_tooling.py`
- tracked views：`docs/generated/rule_system/V1_*.json` 至 `V6_*.json`
- 每张根均带 `GENERATED_VIEW_NON_AUTHORITY`，每个统计数带 source，tracked 字节必须等于冷重算。

## C. 五条验收实测

### 验收 ①：编号索引条数与 tracked 语料一致

**PASS。**

- `git grep` distinct：89。
- index active：89。
- OWN：M01–M24 + M27 + M29，共 26。
- 缺口：M25/M26/M28，三条 `EXPECTED_GAP_CONFIRMED` 已在 JSONL。
- plain `rg` 本次旁证也是 89，但不作为权威计数。

### 验收 ②：差集首份清单命中两个 admission

**PASS。**

```text
required_hits = [item_log_admission, item_pipe_admission]
missing_required_hits = []
gap_count = 52
byte_current = true
```

### 验收 ③：currency 变异自证

**PASS。** 对样例条目的第一条 premise 手工把 `value_at_derivation` 从 `1/1` 改为 `2/1`，并把条目置为 `ACTIVE`、挂一名 consumer；不改现场 canonical。

```text
stale = true
blocking = true
issue = value_at_derivation 2/1 does not match current source 1/1
```

原条目则 `stale=false/blocking=false`。另外，保持 `UNREVIEWED` 时同样漂移只显示、不阻断，反向哨兵通过。

### 验收 ④：V2 代码列头部有“非完备”

**PASS。**逐字：

```text
代码 call site（非完备；仅 git grep 字面叶键扫描；拼接、别名、动态访问和 .rgignore 投影都可能漏）
```

### 验收 ⑤：指纹独立冷启动一致

**PASS，采用已批准的替代口径。**两台物理机器不可得，改为两个独立进程：

| 进程 | cwd | `PYTHONHASHSEED` | 结果 |
|---|---|---|---|
| A | 仓库根 | `random` | `4dcf493d...9da13` |
| B | `/tmp` | `123456789` | `4dcf493d...9da13` |
| tracked 条目 | 不适用 | 不适用 | `4dcf493d...9da13` |

三者完整 SHA-256 均为：

`4dcf493d32fab29d37f79996e5637bcd08aa51504b863c337d2eac32f679da13`

诚实边界：该替代证明独立 Python 冷进程、cwd、环境与 hash seed 不影响当前算法；没有证明跨两台物理主机或不同 Python 实现的兼容性。

## D. 提交与批尾三检

已完成精确 pathspec 提交：

1. `368c3602b09b445de5a9bc2d241a68c40d6c9dff`：工具、测试、`rules/derived/` 立架、V1–V6、批 0 现行门牌同步和 `OD-B1-PACKAGE-01`。
2. `9b5128d39880969128b56b3216353ad7d2518b2c`：本凭据、批 0 现行总括句同步和 V2 自指 currency 修正；历史 `BATCH0_SELF_RECEIPT.md` 未修改。

待命期间共享 HEAD 推进到 `fd86ef8`。该提交在 owner 显式授权下完成 `rules/derived/` 治理 carve-out，并把 code-assets census 与一处硬编码根计数对账归一；其中两个本批 `devtools` 新文件已由共享治理提交登记，本批没有重复修改 census。

三检开跑前实测：tracked diff、staged diff与共享生成页 diff 均为空。另有一份属于并行实验线的 untracked 文书：

`docs/research/solver_reasoning_outer_loop_reviews_20260815/REASONING_OUTER_LOOP_ARCHITECTURE_SKETCH.md`

本批未读取、修改、暂存或提交它。

批尾三检命令与结果：

| 命令 | 结果 |
|---|---|
| `.venv/bin/python devtools/docctl.py intake --changed` | 两次均 exit 0；首次 `changed paths: 11`，写入本收口补记后最终复跑为 `changed paths: 12`；均识别到上述并行线文书的 `DOC-EVENT-DOCUMENT-CREATED`，给出其所需 render/doctor 操作卡，但没有 BLOCK |
| `.venv/bin/python devtools/docctl.py doctor` | `PASS: document system is self-consistent and compatibility projections are fresh` |
| `.venv/bin/python devtools/check_knowledge_docs.py` | `PASS: knowledge spine is internally consistent and generated projections are fresh` |

三检未产生共享生成页差异。本次收口只修改本凭据，并将用该单一路径作精确 pathspec 提交；不夹带并行线的 untracked 文书或其他工作区内容。

## E. 收批表

| 步 | 触发 | 完成 | 结论 |
|---|---|---|---|
| 0 批型与档案 | 是 | 是 | PASS |
| 1 参数账 | 是 | 是 | PASS WITH EXPLICIT MISSING |
| 2 可达性尺子 | 是 | 是 | PASS；坏形态能红，合法未审形态不过度阻断 |
| 3 前件卫生 | 是 | 是 | PASS；exact-decimal、量词域、非完备边界明列 |
| 4 裁决包 | 条件触发 | 是 | 无新 owner 包；其余七件保持待裁 |
| 5 连锁重写 | 是 | 是 | 批 0 现行文书同步；package 接线建账 |
| 6 双向保真 | 是 | 是 | 21 测试 + 变异自证 + 冷进程一致 |
| 7 饱和扫描 | 完整凭据要求 | 是 | `PAIRWISE_FIXED_POINT_INCOMPLETE`，不宣称闭包饱和 |

方向暴露：

- 过严风险：把所有未直接登记实体判成不可表达；已用 `NOT_ASSESSED` 与解释边界阻断。
- 过松风险：V2 代码列只列字面前三个定位点；明确非完备，不能当消费者全集。
- `NOT_ESTABLISHED`：跨物理机器确定性、六谓词映射、孔审计机器台账、标准 package 自动接线、全仓能力表达力。
- conditional：任何引用 `OD-B1-PACKAGE-01` 关闭前的“标准外审包自动含派生层”声明。

本批可合法发布的最高结论：批 1 的四件开发工具已落 tracked 真址，五条验收与批尾三检全部通过；开放欠账和其余七件待裁事项仍按原状态保留。

不得发布的更强表述：其余七件已批准、canonical schema 已钉、L2 条目已获 owner/canonical 权威、六视图可作承重前提、全部能力已审、代码消费者已穷尽、规则闭包已饱和、标准外审包已自动接线。

收批席最终 verdict：`FINAL_PASS_WITH_OPEN_DEBTS`。
