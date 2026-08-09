# R3 批 A + 批 B 验收清单（机器收据制）

**批次**：规则系统重设计第三轮（R3）批 A（形式基座）+ 批 B（撤销过强声明）
**日期**：2026-08-07　**席位**：R3 批 A/B 施工席
**上游**：`.artifacts/gpt_pro_review_batch_20260807/verdict/fen5/ADJUDICATION_fen5.md`（核签书，§10 的 R3-批A / R3-批B 两张表是施工清单）+ 同目录 `files/PROPOSED_PATCHES_RULE_SYSTEM.md`（P-01…P-22）
**改动面**：`FIRST_PRINCIPLES_DESIGN.md` / `FINAL_DESIGN.md` / `DIFF_VERDICT.md` 三份，**仅此三份**。
**未动**：`failure_taxonomy_and_requirements.md`、`scout_*.md`、`canonical_anatomy.md`、`OWNER_DECISION_SUMMARY.md`、`rules/`、`src/`、`scripts/`、任何锁面文件。未 commit。未派子代理。批 C（机制加固，含代码）**一行未做**。

---

## 0. 怎么读这张表

每项给两类收据：

- **旧误文收据** = 该项要撤销的措辞在**正文里零裸命中**（命中只允许出现在 `> **superseded（R3 …）**` 留痕块内——留痕是 A3 四类表示里 `QUOTATION_FOR_EVIDENCE` 的用法，不是残留）。
- **新文在场收据** = 新措辞的 `rg` 命中与行号。

所有 `rg` 一律带 `--no-ignore`（仓库 `.rgignore` 会把整类文件投影出默认结果）。文件名缩写：`F` = `FIRST_PRINCIPLES_DESIGN.md`（946 行）、`N` = `FINAL_DESIGN.md`（774 行）、`D` = `DIFF_VERDICT.md`（282 行）。

**无收据不得标完成**——下表 13 项全部有收据。

---

## 1. 批 A（形式基座）

### A1　π 投影：两个包含式 → 健全/完整两条量化义务　〔P-04 直接收 / BLOCK-03〕

**做了什么**：`F` §1.3 引入投影 `π: M → G`（`M` = 完整模型赋值空间含辅助变量，`G` = 权威游戏状态空间），把原来的两个集合包含式改写成两条量化义务（健全性附 `Obj_M(m) = Obj_G(π(m))`；完整性带存在量词）；三种失败模式各一行（无辅助见证 / 投影非法 / 目标不保真）并各配在案实例；§1.7 同步（标题、两条方向的形式、新增「表是义务索引，不是证明」段）；WLOG 缩约的正规化义务 `N: G → G` 在此处点名、细则落 §1.4。

| 收据 | 命令 | 结果 |
|---|---|---|
| 旧误文零裸命中 | `rg -c --no-ignore '^需要两个包含方向' F` | **0** |
| 旧误文仅存于留痕块 | `rg -n --no-ignore '包含方向' F` | 2 命中，**均在 `> **superseded`** 行内（`F:142`、`F:271`） |
| π 定义在场 | `rg -n --no-ignore 'π: M → G' F` | `F:121`（§1.3 定义块）、另 1 处 §1.7 |
| 三种失败模式在场 | `rg -n --no-ignore '无辅助见证\|投影非法\|目标不保真' F` | 表在 §1.3，三行齐 |
| 「表是义务索引」在场 | `rg -n --no-ignore '表是义务索引，不是证明' F` | §1.7（`F` 内 1 处）+ §1.3 收尾一句 |
| 「表行全绿 ⇒ 包含已证」类措辞已改 | `rg -n --no-ignore '表行全绿' F` | 全部出现在 R3 新增的**禁止**语境（"凡是'表行全绿 ⇒ 保真已证'的读法，都是把索引当成了被索引物"） |

### A2　WLOG bundle：逐行 WLOG 不能自动合成为全局　〔P-05 直接收 / BLOCK-04〕

**做了什么**：`F` §1.4 新增 (R3-A2) 小节——反例（`M1` 只允许 `a`、`M2` 只允许 `b`，各自 WLOG 合取为空）、三个新字段（`wlog_bundle_id` / `normalizer` / `preservation_set`）、全局清账三选一（联合正规化 / 有序正规化逐步保持 / 直接给不劣见证）、单行只能标 `LOCALLY_WLOG`；`F` §1.7 与 §2.3 同步（判读值拆两级 `LOCALLY_WLOG` / `BUNDLE_CLEARED`，正当表字段表增三行 + 束级状态行）。

| 收据 | 命令 | 结果 |
|---|---|---|
| 三个新字段在场 | `rg -c --no-ignore 'wlog_bundle_id' F` | **4** |
| 单行限制在场 | `rg -c --no-ignore 'LOCALLY_WLOG' F` | **4** |
| 束级清账在场 | `rg -n --no-ignore 'BUNDLE_CLEARED' F` | §1.4 / §1.7 / §2.3 三处 |
| 三选一义务在场 | `rg -n --no-ignore '联合正规化' F` | §1.4 (R3-A2) |
| `model_stricter_faces` 欠账已点名 | `rg -n --no-ignore 'model_stricter_faces' F` | §1.3（实测订正块）+ §1.4 (R3-A2) 末段（欠账登记）+ §2.5 归位表 |

**在案欠账登记（文书只登记，不改 canonical，挂 freeze-ritual 批）**：本席逐字读 `rules/canonical_rules.json` 的 `semantics.axiom_kernel.model_stricter_faces`（类型 `str`），实测登记**四处**面——① sink-front 单商品排他、② source-front 同款排他、③ routing 复验的额外 no-orphan / selected-source-reaches-sink、④ binding slot-single-commodity。**④ 已由 `port_commodity_scope` 走缩范围处理，未清的是 ①②③ 三处**，三处各自的"已证 WLOG"路径上都缺组合腿，且该字段是一句散文、装不下 `wlog_bundle_id`。

> **与核签书的一处数字差异（本席实测，已在 `F` §1.3 登记）**：核签书 §3.2 与 `F` 原文都写"**三处**面"。实际登记是四处；"三处"应读作"**未清三处**"，不是"登记三处"。**这不影响核签书的结论**（组合腿缺失的判定对三处成立），只影响计数措辞。

### A3　四类表示替换补-13　〔P-14 直接收 / BLOCK-11〕（含 C11：`semantics.entities` 改 `GENERATED_PROJECTION`）

**做了什么**：`F` §1.12 补-13 全面改写为 `AUTHORITATIVE_CURRENT` / `GENERATED_PROJECTION` / `IMMUTABLE_HISTORICAL_SNAPSHOT` / `QUOTATION_FOR_EVIDENCE` 四类（每类带必带字段 + 能否被当前语义消费）；推论 a 从"档案不得陈述命题"改为**档案层 = 保存 owner 裁决 exact decision payload 的不可变事件记录**（问题原文 / 裁决原文 / 证据 / 签名 / `supersedes`）；推论 b 的机检判据从"正文只在一个文件出现"改为"同一 id 的 `AUTHORITATIVE_CURRENT` 只许一份"；`F` §2.2 档案条目字段集同步；`F` §2.9 增量条同步。**C11**（纯文书措辞项，随 A3 顺手落，核签书 §10 标注）：`N` §3.5 规则 2 从"镜像 + 双向等值"改为 `GENERATED_PROJECTION`，`N` §6 批 3 验收②随之从"双向等值 checker"改为"重生成后 byte-identical"。

| 收据 | 命令 | 结果 |
|---|---|---|
| 四类表示在场 | `rg -c --no-ignore 'AUTHORITATIVE_CURRENT' F` | **6** |
| 旧结论已留痕 | `rg -n --no-ignore '只许有一个陈述位置' F` | 命中**均在 `superseded` 块内** |
| 档案层改事件记录 | `rg -n --no-ignore 'exact decision payload' F` | §1.12 推论 a + §2.2 档案条目 |
| 「档案条目不携带命题」已撤 | `rg -c --no-ignore '^\*\*档案条目\*\*：编号 / 日期 / 谁 / 依据形态.*原文指针。档案条目\*\*不携带命题\*\*' F` | **0**；该句仅以引文形式存活于 `superseded` 块（`F:555`） |
| C11 落地 | `rg -c --no-ignore 'GENERATED_PROJECTION' N` | **4**（§3.1 层表、§3.5 规则 2、批 3 验收） |
| C11 旧条款零裸命中 | `rg -c --no-ignore '^2\. \*\*与 L0 重叠的字段是镜像' N` | **0** |
| 跨稿一致 | `rg -c --no-ignore 'GENERATED_PROJECTION' F` | ≥1（§1.12 推论 e 点名 `N` §3.5 已同步改） |

### A4　废裸层号，改稳定类型名　〔P-21 直接收 / CONCERN-07〕

**做了什么**：两稿各加一节映射表（`F` §0.1 (R3-b) 在 `F:27` 起；`N`【R3 修订说明】(R3-b) 在 `N:8` 起），逐条对齐九个稳定类型名与**两版各自**的原层号；`F` §1.6 分层表、§1.8 冻结判据逐层、§2.1 目录树、§2.9 全部改类型名；`N` §0 第 1 句、§3.1 四层表、§3.1 层间接口、§3.7 层级计算全部改类型名；`D` 加【R3-A4】节并把 §5 合并建议第 1 条从裸层号改类型名。**层号此后只作本稿显示序号**，跨文书引用必须用类型名 + `schema_version`（P-21 原文即此口径）。

| 收据 | 命令 | 结果 |
|---|---|---|
| 冲突已显式登记 | `rg -n --no-ignore '同名反义' F N D` | 三份各 ≥1（`F` §0.1、`N`【R3 修订说明】、`D`【R3-A4】） |
| 类型名在场 | `rg -c --no-ignore 'PROBLEM_CLAIM' F` / `rg -c --no-ignore 'SOLVER_INPUT' N` | **7** / **6** |
| `D` 合并建议已改 | `rg -c --no-ignore '^1\. \*\*骨架取推导版\*\*：L0 问题 / L1 参数 / L2 公理 / L3 定理' D` | **0**（原句进 `superseded`） |
| `D` 新合并建议在场 | `rg -n --no-ignore '骨架取推导版的形态' D` | §5 第 1 条 |

### A5　`TARGET_CLAIM` / `PROVED_CLAIM` 双对象 + `ClaimDelta`　〔P-08 直接收 / BLOCK-07〕

**做了什么**：`F` §1.4 新增 (R3-A5)——双对象表（谁能改）、`ClaimDelta = TARGET_CLAIM − PROVED_CLAIM`、**缩范围只许改 `PROVED_CLAIM`**、墙在 `TARGET_CLAIM` 台账保持 `OPEN`、证书状态 `PARTIAL`/`CONDITIONAL` 且首页显示 `ClaimDelta`；处置 2 正文加指向；§1.6 分层表 `PROBLEM_CLAIM` 行注明拆双对象；§1.7 判读值同步。

| 收据 | 命令 | 结果 |
|---|---|---|
| 双对象在场 | `rg -c --no-ignore 'PROVED_CLAIM' F` | ≥4（§1.4 表 + §1.6 + §1.7 + §2.1） |
| `ClaimDelta` 在场 | `rg -c --no-ignore 'ClaimDelta' F` | **5** |
| 与 owner 口径对齐已写明 | `rg -n --no-ignore '目标不设降级退路' F` | §1.4 (R3-A5) `superseded` 块 |

### A6　三类产物（OBLIGATION / MECHANISM / HEURISTIC）全稿回标　〔P-01 改造后收 / BLOCK-01〕

**做了什么**：`F` §0.1 (R3-a) 立三类定义与标注要求（含"必须保留来源类别与首次引入版本"）；**逐处回标**——§2.1 目录树标 `MECHANISM`（并写明推得出的 OBLIGATION 只有两条）、§2.3 约束稳定编号的**落地形态**标 `MECHANISM`（义务是 OBLIGATION，形态不是；并记明更强的替代方案 = 统一登记接口自动发号，且**生成期剪枝那一级不可自动**，属批 C）、§1.10 工作队列标 `MECHANISM`（优先序是 OBLIGATION）；**§1.9 准入判据补标来源**（= C-15 + 病例驱动版 K-4 的对勘回流，回流路径记在 `D` 分歧 3；按三类判 = HEURISTIC + MECHANISM，**不是 OBLIGATION**）；核签书驳回的一处（"三张表推不出"是误伤）在 §0.1 留档。

**P-01 的改造**（按核签书 §10 A6，砍"版本化操作语义"全套）：`F` §1.1 只收两条——**实体参数表是权威游戏语义的一种投影**（不预设它足以表达全部经验事实）+ **引用参数/公理必须带 game build 版本**；外审要求的"签名/状态空间/初始条件/转移观察关系/随机性调度语义"整套**明文不收**，理由写在同处（违反补-12：无法被执行的义务不产生依据）。

| 收据 | 命令 | 结果 |
|---|---|---|
| 三类定义在场 | `rg -n --no-ignore '^### \(R3-a\) 三类产物必须自报类别' F` | §0.1 |
| 全稿回标数 | `rg -c --no-ignore 'MECHANISM' F` | **13** |
| 目录树已标 | `rg -n --no-ignore '### 2.1 文书层次与文件组织　\*\*〔R3 分类：MECHANISM〕\*\*' F` | §2.1 标题行 |
| 两问三格补标来源 | `rg -n --no-ignore 'A6 来源标注' F` | §1.9 准入判据后（**全稿最严重的一处走私品**，逐字点名 C-15 + K-4） |
| P-01 改造已落 | `rg -n --no-ignore '本席对 P-01 的改造' F` | §1.1（明写"这一整套不收"及理由） |
| 未收"版本化操作语义" | `rg -c --no-ignore '状态空间、初始条件、转移' F` | 仅 1 处，在**拒收说明**里 |

### A7　`FIRST:19` 的 69 → 53

| 收据 | 命令 | 结果 |
|---|---|---|
| 旧数字零裸命中 | `rg -c --no-ignore '§3 是用 69' F` | **0** |
| 仅存留痕 | `rg -n --no-ignore '69' F` | 1 命中，在 `superseded` 块（`F:23`） |
| 新数字在场 | `rg -n --no-ignore '§3 是用 \*\*53\*\* 个历史病例' F` | §0 推导原则段 |

---

## 2. 批 B（撤销过强声明）

### B1　pairwise「= 饱和」→ `PAIRWISE_FIXED_POINT_INCOMPLETE`　〔P-17 直接收 / BLOCK-13〕

**做了什么**：`N` §4.8 停机判据全面改写——三个状态（`PAIRWISE_FIXED_POINT_INCOMPLETE` / `NOT_EXHAUSTIVE` / `UNKNOWN`），三前提反例 `x≥0, y≥0, x+y≤−1` 逐步写出（含"漏掉的恰恰是最强的负结晶，而本节自己明写负结晶都要报"），回灌为什么救不了（回灌池为空），**核签加重例**：owner 的 5 满 1 半是五前提塌点，**旗舰样板自身超出 pairwise 可达域**；pairwise 定位改 HEURISTIC；承重闭包结论交理论完备求解器取 UNSAT core / proof object，**点名在案载体** `certside/sidecar/runner.py` 的 OPB → RoundingSat(proof) → veripb 链（fail-closed 按 anchored 结论行判定、**刻意不用退出码**，见该文件 `:3-4`；已产出 PB-03 `(1326,34)` residual-band UNSAT 机器可验证书）。连带改：`N` §1.3 义务 2（"跑组合扫描至饱和"）、§4.8 三层圈定（"到顶未饱和"→ `NOT_EXHAUSTIVE`）、§3.7 层级计算（"给饱和扫描一个终止判据"→ 深度判据）。

| 收据 | 命令 | 结果 |
|---|---|---|
| 旧措辞零裸命中 | `rg -c --no-ignore '^\*\*停机判据\*\*：一轮 pairwise 零新结晶 = 饱和' N` | **0** |
| 同上（§1.3） | `rg -c --no-ignore '跑组合扫描至饱和' N` | **0** |
| 仅存留痕 | `rg -n --no-ignore '= 饱和' N` | 2 命中，1 在 `superseded` 块（`N:594`）、1 在解释该措辞为何撤的 R3 注（`N:584`） |
| 新状态名在场 | `rg -c --no-ignore 'PAIRWISE_FIXED_POINT_INCOMPLETE' N` | **2**（§1.3 + §4.8） |
| 三前提反例在场 | `rg -n --no-ignore 'x \+ y ≤ −1' N` | §4.8 |
| 核签加重例在场 | `rg -n --no-ignore '旗舰样板本身就在 pairwise 的可达范围之外' N` | §4.8 |
| veripb 链在场（两稿） | `rg -c --no-ignore 'veripb' N F` | `N` ≥1、`F` **2**（§1.9 第 3 类 + §4.8 交叉引用） |

### B2　53 行病例校验按六级强度重判并重算统计　〔P-10 改造后收 / BLOCK-09〕

**做了什么**：`F` §3 拆两个维度——**维度一（补推导依赖）= 原四值，原样保留**（"做过的分类工作不删"，核签书 §4.5 明确否掉了外审"撤销 23/22/4/4"的处方），表头改名并加**读法警告**；**维度二（保证强度）= 新增 §3.1b**，七个档（P-10 六级 + 核签书 §4.2 追加的 `DETECTS_IF_INSTRUMENTED`），**53 行逐行重判并给"效力挂在哪个前件上"的理由**；§3.2 统计改用维度二为主表，维度一原统计降为副表并加"两张表不可互换读"警告；§0 一句话的"覆盖 45 条"撤下改双维度报数。

核签书点名的四行逐条落：**C-15**（见下）、**C-24 → `DETECTS_IF_INSTRUMENTED`**、**C-31 → `DETECTS_IF_REGISTERED`**（双射跑在两侧声明之间，共同遗漏则照过）、**C-52 → `DETECTS_IF_REGISTERED`**（表查询依赖登记完备）。另 **C-49 由"部分"改判 `OUT_OF_SCOPE`（发布面）**，本席在重判中发现并在 §3.2 显式登记。

**C-15 按核签书 §4.3 改**：`F` §3.1 的 C-15 行 + 补-4 推论 + §3.3 缺陷 3 三处同改——**"输入差集"表述作废**（`runs` 与 `machines` 都是已声明输入，均摊藏在**除法这个运算**里，差集恒为空），`FINAL` §4.4 聚合问**抬为补-4 的正式机械形态**（信息压缩操作清单，逐条带 `source_span` / 输入输出类型 / 所需语义前件 / 谁能违反它 / 替代分配下的结论范围）。

**`PREVENTS` 回测义务有界化**：按补-12 改为"**仅被下游承重结论引用的 `PREVENTS` 要求回测**"，其余标 `CLAIMED_PREVENTS_NOT_BACKTESTED`。**本轮实测：7 条 `PREVENTS` 全部标 `CLAIMED_PREVENTS_NOT_BACKTESTED`，强制回测条数 = 0**（包内零回测收据，且本设计尚无下游承重结论引用它——`N` §8 自己写明它在独立 refute 回来前不得被引用为已审定方法论）。这是义务有界化的结果，不是豁免。

| 收据 | 命令 | 结果 |
|---|---|---|
| 旧"覆盖 45 条"零裸命中 | `rg -c --no-ignore '一句话.*覆盖 45' F` | **0**（原句进 `superseded`，`F:7`） |
| 六级 + 一档在场 | `rg -c --no-ignore 'PREVENTS' F` / `'DETECTS_IF_INSTRUMENTED' F` | **14** / **8** |
| **53 行全判、无重复、无缺号** | `python3 -c` 抓 `^\| (C-\d\d) \| \`([A-Z_]+)\` \|` 计数 | `rows=53`、`dup=[]`、`missing=[]` |
| **统计与逐行判读逐格相符** | 同上脚本 `Counter` | `DETECTS_IF_REGISTERED 26` / `MAKES_VISIBLE_FOR_REVIEW 11` / `PREVENTS 7` / `OUT_OF_SCOPE 5` / `DETECTS_IF_INSTRUMENTED 3` / `DETECTS_UNCONDITIONALLY 1`，**合计 53**——与 §3.2 表逐格一致 |
| 维度一原统计保留 | `rg -n --no-ignore '拦住（原推导 §1.1–§1.10 即有对症装置） \| 23' F` | §3.2 副表在场（23/22/4/4 未删） |
| 两维不可互换读 | `rg -n --no-ignore '两张表不可互换读' F` | §3.2 |
| C-15 机械形态订正 | `rg -n --no-ignore '输入差集' F` | 3 命中，**均在 `superseded` / 订正语境**（补-4、§3.1b C-15 专栏、§3.3） |
| 回测义务有界化 | `rg -n --no-ignore 'CLAIMED_PREVENTS_NOT_BACKTESTED' F` | §3.2（含本轮实测 = 0 条强制回测） |

### B3　准入判据三格 → 四态，C/D 并进既有开放态词表　〔P-02 改造后收 / BLOCK-02〕

**做了什么**：`F` §1.9 准入判据改四态（A 删 / B 硬检查 / C 半判定→`PASS`/`FAIL`/`UNKNOWN`，`UNKNOWN` 阻断无条件 certified / D 无可执行判据→登记为开放证明义务），**C/D 明文并进既有词表**（`未清欠账` / `待复验` / `未测` / `未核`）与既有台账（覆盖账"未核"格、正当表脏行 + `ClaimDelta`），并写明"新造第二套开放态会当场违反补-13"；`N` §4.9 四条反退化条款第 4 条（"加不出停机判据的检查不许进"）同步改四态，并列出本方案已有的四个开放态承载位。核签书把本项从"结构重写门槛"降为编辑项，该定性也写进 `N` 的 `superseded` 块。

| 收据 | 命令 | 结果 |
|---|---|---|
| `F` 旧三格零裸命中 | `rg -c --no-ignore '^\| 是 \| 否 \| \*\*删\*\*。它只是把上面那条公理换个说法' F` | **0** |
| `F` 四态在场 | `rg -n --no-ignore 'OPEN_PROOF\|开放证明义务' F` | §1.9 四态表 D 档 |
| `F` 并进既有词表已写明 | `rg -n --no-ignore '不新造开放态词表\|不许新造第二套开放态' F` | §1.9 两处 |
| `N` 旧条款零裸命中 | `rg -c --no-ignore '\*\*加不出停机判据的检查不许进\*\*。$' N` | **0** |
| `N` 新条款在场 | `rg -n --no-ignore '加不出完备停机判据的检查不许当硬门进' N` | `N:652` |
| `N` 四态表在场 | `rg -n --no-ignore '停机判据决定的是检查器能否给出' N` | §4.9 |

### B4　`DIFF` 头部改 `PROVISIONAL SELF-COMPARISON`，撤 15/8/2　〔P-18 改造后收 / BLOCK-14〕

**做了什么**：`D` 头部状态改 `PROVISIONAL SELF-COMPARISON——非独立裁决`；**15 / 8 / 2 三个数字全部撤下**（"2"在 §3 末、"15"在 §1 标题与正文、"8"在头部）；三条理由逐条给（**git 实测：`F` 与 `D` 同提交 `cc12e9a` 首次入库、`N` 在更早的 `8ad9c80`；对勘前快照仓内从不存在，不是"包里没带"**；`D` 自己写着两句不能同时成立的话；裁判自产）；P-18 五条逐条给处置（**第 1 条改为记明不可复验**，第 4 条记明**份 5 外审 + 核签书是第一份非自产判读**）；§0 总判读、§1 标题与第 14 条、§3 末的"只有两项"、§5 合并建议逐处撤销胜负与自评措辞；**八个分歧按核签书 §7.2 逐条重判**（§2 头部重判总表 + 分歧 1/4/5/6/7/8 各加节末 R3 块，分歧 2/3 在标题与总表）；`D:183` 的"唯一决策点"读法删除，改指向 `OWNER_DECISION_SUMMARY.md` 全清单。

| 收据 | 命令 | 结果 |
|---|---|---|
| 三个数零裸命中 | `rg -c --no-ignore '^\*\*三个数\*\*：收敛' D` | **0** |
| 仅存留痕 | `rg -n --no-ignore '\*\*三个数\*\*：收敛' D` | 1 命中，在 `superseded` 块（`D:9`） |
| "两法的独立性成立"零裸命中 | `rg -c --no-ignore '两法的独立性成立$' D` | **0** |
| §1 旧标题零裸命中 | `rg -c --no-ignore '^## 1\. 收敛点（两法独立到达，高置信）' D` | **0**（仅留痕 `D:57`） |
| §3 "只有两项"零裸命中 | `rg -c --no-ignore '^\*\*判为赘物或错位的只有第 14、15 两项' D` | **0** |
| 新状态在场 | `rg -n --no-ignore 'PROVISIONAL SELF-COMPARISON' D` | `D:3` |
| git 实测在场 | `rg -n --no-ignore 'cc12e9a' D` | 【R3 状态改判】理由 1（**实测复核**：`git log --diff-filter=A` 两条 hash 与核签书一致） |
| 八分歧重判表在场 | `rg -n --no-ignore 'R3 重判总表' D` | `D:85`（8 行齐 + 净结果行） |
| 八分歧逐条加注 | `rg -n --no-ignore -o '〔R3 块，B4[^〕]*〕' D` | **6** 处独立块（`D:110/151/163/173/186/194` = 分歧 1/4/5/6/7/8）；分歧 2/3 判读在标题 + §2 头部总表 |
| "唯一决策点"读法已删 | `rg -c --no-ignore '^\*\*留给 owner 的决策点\*\*（本文不代拍）：`semantics`' D` | **0** |
| 指向全清单 | `rg -n --no-ignore 'OWNER_DECISION_SUMMARY' D` | `D:276` 起（八件 + 三道事实题 + 默认动作） |

### B5　机器检查能力四分类，撤销「唯一可机检残渣」　〔P-03 直接收 / CONCERN-01〕

**做了什么**：`F` §1.9 改四分类（结构可判定 / 理论可判定 / 证明对象可核验 / 仅人审），每类给本仓在案载体；**第 3 类以 veripb 链为在案反证**（PB-03 `(1326,34)` residual-band UNSAT 机器可验证书，fail-closed 按 anchored 结论行判定、不用退出码）；节标题从"唯一的可机检残渣"改为"机器检查能力的四分类"；原对机器面的禁令（记账完整 ≠ 模型忠实）**保留**，但加一句限定：它约束的是**第 1 类**检查器的文案，不得被引用来否认第 2、3 类的存在。

| 收据 | 命令 | 结果 |
|---|---|---|
| 旧标题零裸命中 | `rg -c --no-ignore '^### 1\.9 .*唯一的可机检残渣' F` | **0** |
| 全文旧措辞仅存留痕 | `rg -n --no-ignore '可机检残渣' F N D` | 1 命中，在 `superseded` 块（`F:386`） |
| 四分类在场 | `rg -n --no-ignore '结构可判定\|理论可判定\|证明对象可核验\|仅人审' F` | §1.9 四行表齐 |
| 在案反证在场 | `rg -n --no-ignore 'PB-03' F` | §1.9 第 3 类行 |
| 载体路径已核 | `ls certside/sidecar/runner.py` + `rg -n 'veripb\|anchored' certside/sidecar/runner.py` | 文件存在；`:3-4` 头注逐字确认 fail-closed 判据 = anchored 结论行、**禁退出码**（veripb 失败 exit 0、RoundingSat UNSAT exit 1） |
| 引用的下游已接通 | `rg -n --no-ignore '机器检查能力第 3 类' N` | `N` §4.8（B1 的承重闭包义务指回此处） |

### B6　C-17 统一判读（**P-11 拒收**）　〔BLOCK-10〕

**做了什么**：按核签书 §4.4 落**统一判读**——`C-17 = 不可达；件数维度无条件成立（15 件/冲刷周期 vs 6×50 = 300 件）；槽数维度 conditional on「单槽容量 50 落入冻结件」`；**两条待判项：①填槽纪律已作废**（owner 2026-08-06 定谳 fill-first，机器复核当时读的是 `AXIOM_KERNEL_PROPOSAL.md` 漏翻的陈旧副本 = 病例 C-53 本身）、**②单槽容量 50 的仓内 provenance 仍成立**。**P-11 拒收**并写明理由（仓内三条独立证据可解析：git 时序 / `00_master_roadmap.md` 08-07 台账行 `c7f7e70` / canonical `slot_count_clause.adjudicated` 字节；按 P-11 做等于让陈旧副本拉平正确副本 = C-53 的失效形态）；**ACCEPT 它的过程指控**（包内零原件 = CONCERN-05，处方 `EVIDENCE_MANIFEST` 挂批 C）。

**落地六处**：`F` §3.1 C-17 行 + 新增 §3.1a 统一判读块；`N` §2.2 F-02 落点、§2.5-② 现场复核（加订正块，把它记为 C-53 的第一手证据）、§3.4 变更 3、§4.2 样板（结论栏 待核 → 不可达 + 完整 R3 块 + 量子行补 fill-first 出处）、§6 批 6 验收⑥（一行 → 两行，两维分列）、§8 欠账；`D` §4-①（精确化为两维分列 + P-11 拒收）。

| 收据 | 命令 | 结果 |
|---|---|---|
| 统一判读在场（三份） | `rg -c --no-ignore '件数维度无条件成立' F N D` | `F` 1 / `N` 2 / `D` 1 |
| P-11 拒收已写明 | `rg -n --no-ignore 'P-11 拒收\|拒收该处方\|外审 P-11.*拒' F N D` | 三份各 ≥1 |
| ①作废、②保留 | `rg -n --no-ignore '已作废' F N` | `F` §3.1a 表、`N` §4.2 表 + §8 欠账 |
| `N` 旧"待核"结论仅存留痕 | `rg -n --no-ignore '\*\*这张表的正确结论是待核' N` | 1 命中，**在 `superseded` 块内**（`N:462`，含负面教材的**第二重**说明）；正文零裸命中 |
| `N` 旧 `open_premise_refs` 例零裸命中 | `rg -c --no-ignore 'open_premise_refs: \["同种物品填槽纪律（P2 待判）"\]，不是 `unreachable`' N` | **0** |
| 批 6 验收已改两行 | `rg -n --no-ignore '箱案在界台账里有两行' N` | `N:699` |
| canonical 字节已实测 | `python -c` 读 `semantics.protocol_storage_box_wireless.slot_count_clause.adjudicated` | 逐字含 `"the earlier 'six different commodities' phrasing was an example, not a bound"`（与核签书 §4.4 证据 3 一致） |

---

## 3. 结论

**A1–A7、B1–B6 共 13 项全部完成，每项有收据。**旧误文关键短语在三份文书正文里**零裸命中**，全部命中都落在 `superseded` 留痕块内。新增/改写的措辞逐项可 `rg` 命中并给了行号。B2 的 53 行重判统计经独立脚本复算，**与 §3.2 表逐格相符**（53 行、无重复、无缺号）。

**改动条数**（按被替换或新增的正文块计）：`FIRST_PRINCIPLES_DESIGN.md` **21 处**（615 → 946 行）、`FINAL_DESIGN.md` **15 处**（683 → 774 行）、`DIFF_VERDICT.md` **14 处**（183 → 282 行）。

**批 C 一行未做**，正文里凡属批 C 的项已标"挂批 C"并登记欠账：传递依赖根 / `artifact_root`（BLOCK-12，`F` §1.8）、统一登记接口自动发号且分两级（BLOCK-06，`F` §2.3）、聚合问的 `source_span` 扩展与收据两类比对（BLOCK-08，`F` §3.1b）、`provenance` `oneOf` 四型（CONCERN-02，`F` §3.1a、`N` §4.2）、删 guard 的全称式义务（BLOCK-05，`D` 分歧 5）、`EVIDENCE_MANIFEST`（CONCERN-05，`F` §3.1a、`N` §4.2、`D` §4-①）。

---

## 4. 施工中发现的新问题（三条，需下一批处置）

### 问题 1（**最要紧**）：`OWNER_DECISION_SUMMARY.md` 仍带 C-17 的陈旧读法，而 B4 刚让 `DIFF` 指向它

`D:276` 按 B4 已改为指向 `OWNER_DECISION_SUMMARY.md` 作为 owner 决策的全清单。但该文件**"先说三件"第 1 条**逐字写着「所以槽数这一维当前的正确状态是**待核**，不是「不可达」」，**决策点第 1 件①**仍把填槽纪律列为待答的游戏事实题——**两处都是 B6 判为已作废的读法**。

**这构成一次新的 C-53 风险**：一个刚建立的指针指向一份陈旧的当前权威。该文件不在本轮改动面内（任务书列的被改对象只有三份），**已在 `D:276` 的 R3 块里显式登记为欠账**，但**必须在下一批同步**，否则 B6 的统一判读在传播层上没有闭合。

### 问题 2：`model_stricter_faces` 是四处面不是三处

核签书 §3.2 与 `F` 原文都写"三处面"。本席逐字读 canonical 该字段（类型 `str`），实测登记四处，其中 binding slot-single-commodity 已由 `port_commodity_scope` 走缩范围处理。**"三处"应读作"未清三处"**。已在 `F` §1.3 加实测订正块并在 §1.4 (R3-A2) 的欠账登记里按四处逐条列出。**不影响核签书的结论**（组合腿缺失对未清三处成立），但下一批把欠账写进 canonical 台账时要按四处的实际结构写。

### 问题 3：件数维度的"无条件"比核签书写的更稳，本席未擅改判读

核签书判"件数维度无条件成立"，算式是 `15 件/周期 vs 6×50 = 300 件`。但 300 这个数依赖②项欠账（单槽容量 50 无冻结件 provenance），字面上"无条件"与"依赖一个未清欠账的数字"看起来矛盾。本席的算术观察：15 件占满 6 槽需要单槽容量 ≤ 2（`ceil(15/6) = 3`），所以**任何"单槽容量 ≥ 3"都足以支撑件数维度不可达**，②项欠账咬的是"300 件"这个具体数字与槽数维度的陈述，**不咬件数维度的结论**。

**本席没有据此改判读**——已按纪律标为 `〔R3 施工席附注·【推导】，不替代上面的判读〕` 写在 `F` §3.1a 末。若要把它抬为正式论证（从而让件数维度真正独立于②项欠账），须按 A1/A2 的义务重写并配收据，属下一批。

### 另记：核签书内部无指令冲突

任务书要求"若核签书两处指令冲突，按 `ADJUDICATION` 优先并报告"。**本轮施工未遇到核签书自相冲突的指令**。唯一需要判断的是核签书 §10 的表（施工清单）与 §2–§9 展开节的**详略差异**——两者方向一致，展开节给的是语义依据，本席一律按展开节的细节施工、按 §10 的表定范围。

---

*本清单是验收凭据。未改 `rules/`、`src/`、`scripts/`、锁面文件与 `failure_taxonomy_and_requirements.md`；未跑 git 提交。*
