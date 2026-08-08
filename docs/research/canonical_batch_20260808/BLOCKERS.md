# BLOCKERS / 待定点（canonical 08-08 改稿草案 · **v3**）

> v1 登记 7 条，主线程 2026-08-07 一次裁完（§1）。
> 其后对抗复核席出总判【修 4 处后可落地】，四条发现 F1-F4 已在 **v3** 全部修完（§1 末表）。
> **当前状态：零待决拍板项、零未修复核发现。** 草案 v3 完整、可解析、过全部结构门与内容门。
> 无 owner-only 闸新增；B1「先放着」未被重开。

---

## 1. 已裁（六条，判语一句 + 落点）

| # | 原议题 | 裁决 | 判语 | 落点 |
|---|---|---|---|---|
| **#1** | C6 完整性规则与 C21 同批互撞：新规则当场有一个未登记实例 | **走甲** | 加第六项**不算发明条款**——内容就是 C21 降格自身的台账化；权威 = fen2 核签 B1 ＋ owner「先放着＝甲案方向（scope restriction＋欠账登记）」 | `model_stricter_faces` 新增 `(6) ITEM-ADMISSION-PORT OMISSION`，四要素逐条落字、注明 owner 已决与重开条件。见 `DRAFT_DIFF.md` §5.1 |
| **#1 附** | 派生闭包公理要求的饱和扫描 | **照做** | C6 规则对全 semantics 扫至饱和 | 19 行扫描表进 `DRAFT_DIFF.md` §6：**新发现 1 条**（即 #13 准入口，已入表）、覆盖 5、不是限制 9、合规不入表 3（U-02 PLAUSIBLE 未 CONFIRMED / X1 本批已关案 / X3 方向相反） |
| **#2** | `terminal_clause` class (2) 的 occupied ≠ full 精度（落点外） | **采纳最小改法原文** | 本批已动 `terminal_clause`，同段精度病不分两批踩两次 freeze-ritual；方向虽保守，但按双向保真公理**过严措辞也是账** | owner 08-06 半句逐字不动 ＋ 前加到货限定 ＋ 后加指针句。机器核对：owner 原串在 v2 中原样存在。见 §5.2 |
| **#3** | `cache_parameters` 对 owner 定谳做了机制级细化（两处） | **两处都维持，不升级** | (a) fen6 深挖 1 ① 的结论就是「owner 两半都成立，精确机制是细化不是矛盾」，没越过佐证边界；**不拿去问 owner**——安全算术对两种机制读法都成立，问了是噪音。(b) 依赖已在 note 里显式点名即满足 `usage_rule` 的 must name that dependency，不再重复登记 | (a) 原样。(b) 按要求补定性句：leg (a) 明标 **CURRENT-MODEL theorem, not an assertion about adjudicated game semantics**；另补一条 owner 08-07 的**模型无关腿**（仅 2 终品可达仓储线 ⇒ 10 s 内 7+ 种凑不出），使格数账不再唯一依赖过严面 (1)。见 §5.4 |
| **#4** | C8+C11 合成时丢了 `:115` 首句 | **维持合成** | 丢得对——保留会重开 ② 刚补上的缺环（A5a ＋ 单槽参数） | 合成文本未动。见 §5.5 |
| **#5** | handbook §11 第 2 条（箱提升 drain 终点）不在 26 段清单里 | **并入本批** | 与 C12/C14 同区域，分两批改同一段文本不可接受 | 落成**实例级 discharge 注**而非无条件类变更：C12 一般形式一个字不动，其后追加 owner 2026-08-07 裁决的两本账（≤15 件/周期、15 ≪ 300 且 < 单槽 50、纯流种类 ≤3 < 6 组、每周期清零、≤10 s 永不中毒），数字**逐个对 roadmap 08-07 箱裁决行**、零新造。见 §5.3 |
| **#6** | `cache_parameters.provenance` 指向尚不存在的归档目录 | **建档** | 现有 canonical 条款一律有 `docs/research/canonical_batch_*/` 归档指针，删指针会成为唯一无归档的 provenance | `docs/research/canonical_batch_20260808/BOX_CACHE_PARAMETER_PROVENANCE.md` 已立（worktree 内、未提交），provenance 指针保留。见 §5.6 |

### 1b. 对抗复核四条发现（v3 全部修完）

| F | 定性 | 修法 | 落点 |
|---|---|---|---|
| **F1** | **承重** —— X1 格数腿在冻结件里写成无条件，前提集丢失，且半个模拟器外推被标成 owner 游戏定谳 | 补四条前提集 ＋ 重推触发器（与仓库桥同触发器）；归属改为「owner 令下的推理关案，非游戏定谳」；②的存货口半边明标模拟器外推 | `terminal_clause.adjudicated`；复述同步三处（`DRAFT_DIFF` §2 C9 / §6 第 18 行 / 本页 §3 X1 条）。见 `DRAFT_DIFF.md` §7.1 |
| **F2** | 轻微 —— 「10/17（旧 9/17 系笔误）」与「反例=0」的机器验证记录被段内删除且未声明 | **保留记录**：移进 `recompute_scope`；并在 `DRAFT_DIFF` C16 声明被删原句与处置理由 | `rate_lemma_scope.recompute_scope`。见 §7.2 |
| **F3** | 轻微 —— 一处 tracked 的 size-only pin 提及既不在必改也不在史料名单 | 写进 `RESEAL_CHECKLIST` §1C 点名为史料，免掉落地当天现判 | `GAME_RULE_IMPACT_AUDIT.md:17`。canonical 零字节改动。见 §7.3 |
| **F4** | 轻微 —— 同一个「≤3」在两处证据等级标注不一致 | 实例 discharge 的该句后加模型依赖指针 | `terminal_clause.statement`。见 §7.4 |

> v2→v3 的**全部字节差异**见同目录 `V2_TO_V3.diff`：JSON 侧恰 3 行（F1/F2/F4 各一），其余为三份配套文档的同步与 sha 登记行。F3 不动 canonical 字节。

---

## 2. 真正的残留项（四条，都不挡落地，落地席知情即可）

### R1 · 冻结件首次出现 CJK 字符

为满足 #5「裁决出处必须写」，实例级 discharge 注里出现路径 `docs/项目说明/00_master_roadmap.md`。
这是 `canonical_rules.json` **第一次**含中日韩字符——此前非 ASCII 只有 `—`×3 与 `§`×4。

- **技术面已实测无影响**：strict_json / jsonschema / pydantic / `load_templates()` 全 PASS，sha 按 UTF-8 字节算不受影响，85 个内容门测试全绿。
- **没有 ASCII 替代**：该 roadmap 路径本身含中文，要写出处就得带它。
- 落地席若坚持冻结件保持 ASCII-only，唯一的替代是只写文件名 `00_master_roadmap.md`（全仓唯一同名文件）而不写目录——**起草席不建议**，出处指针少一半路径就少一半可核性。

### R2 · 单槽容量 50 仍待 owner 游戏侧定级

份6 对勘书原话：该 provenance 条目「仍待 owner 游戏瞥一眼定级」。
本批按**模拟器规则层**等级入册，`evidence_grade` 已如实写明它不是 owner 游戏定谳级，并声明「模拟器行只是佐证、永不能顶替 owner 游戏定谳」。
将来 owner 在游戏里瞥一眼确认，**只需升级 `evidence_grade` 一个字段，结论与数字预期不变**（模拟器规则层 ＋ owner 2026-07-18 五答 ＋ owner 2026-08-06 定谳三方已一致）。**不是本批前置。**

### R4 · X1 关案的前提②有一半是模拟器外推（v3 已如实入册，但欠账仍在）

F1 修完后，冻结件已明写：存货口与取货口共用 `left_or_bottom_boundary` 这条前提，**取货口半边是 owner 2026-07-18 实测、存货口半边是模拟器同标志外推**。这一半是**承重的**——若存货口其实不受贴边约束，139 格条带的账整个不成立，X1 就从「已关案」退回「拒真候选墙」。

- **不挡本批**：措辞已如实标级，没有冒充 owner 定谳；且 `terminal_clause` 排除边界口还有**独立的 (a) 腿**（口朝向 0 进 1 出，来自冻结的 `preprocess_plan`），(b) 腿倒了 (a) 腿仍在。
- **销账路径**：owner 在游戏里瞥一眼「存货口是不是也只能贴左/下边界」即可定级；或产量目标一变就按写进条款的触发器重推。
- 与 R2 同型（都是「模拟器规则层结论等 owner 游戏侧定级」），可一并递。

### R3 · 落地时才能做完的三件（已在清单，不是待决）

- C24 / C25 / C26 三条承重档订正（`RESEAL_CHECKLIST.md` §3）——C26 是**开工前置**，不回填则改稿引用一份仓内查不到的表述。
- 18 处 pin 站点：fen1 §3 前置只列 14 处、`RESEAL_MANIFEST.md` 的 17 处清单也漏 1 处，**两份现成清单照抄都会漏**；且 `PROJECT_LOCK.md:268` 本身是 pin 站点，一改牵出 6+1 继承链（Chain D）。全表见 §1/§2.3。
- 26 手册三处同批更新（§4.1 两本账、§11 欠账**两条**一起销账、§7 准入口行改指条件式 authority ＋ 补第 (6) 项登记）。

---

## 3. 明确**不是** blocker 的

- **schema**：`semantics` 是 `additionalProperties: true` 且无 `properties` 子节点（`canonical_rules.schema.json:431-435`），整棵子树零约束；root 的 `additionalProperties: false` 只管顶层，本草案零顶层新增。`jsonschema.validate` PASS。
- **测试文本断言**：全仓唯一读 `semantics` 的内容断言只碰 `power_coverage_stencil`，与改动面不相交。v2 实测 85 passed。
- **③ de-mix 禁令的前提**：C23 写「现役 main 下暂仍成立」是**实测**——`rg -i 'demix|de_mix|de-mix|split_free|mixflow' src/ scripts/` 零命中；`git merge-base --is-ancestor fb76e15 main` 退出 1；`git branch --contains fb76e15` 只有 `mixflow-surgery`。
- **B1**：owner 已决「先放着」，本批按甲案方向落地 scope restriction ＋ 台账登记，**不重开、不建模过滤槽、不制造新 owner-only 闸**。
- **C7 拒绝改期**：U-02 是 PLAUSIBLE 未 CONFIRMED，按 C6 字面判据不入表合规；撞 mixflow 线 scope，是 scope 判断不是待决项。
- **X1**：本批 C9 的格数账已把它关案（141 > 139，任何容纳 266 mandatory 的布局都放不下），不再是拒真候选墙。**v3 按对抗复核 F1 订正**：该关案是**条件式**的——带四条前提（①产量目标冻结⇒46 ②存货口贴总线规则=取货口同款 ③口体 3×1 ④70×70），产量目标一变就要重推（与仓库桥同触发器）；且前提②的**存货口半边是模拟器同标志外推、不是 owner 游戏定谳**（取货口半边才是 owner 07-18 实测）。冻结件里的措辞已相应改为「owner 令下的推理关案，非游戏定谳」并写全前提集。
