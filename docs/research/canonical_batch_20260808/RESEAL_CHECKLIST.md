# freeze-ritual 落地连锁清单（canonical 08-08 批）

> 起草席出品，**本清单未执行任何一步**。落地由主线程在 main 上走。
> 行号是 2026-08-07 在 `3234c30` 上的实测值，**落地当天必须现场重测**（别死认行号）。

| | 旧 | 新（**DRAFT v3**） |
|---|---|---|
| `rules/canonical_rules.json` size | `40,371` | **`59,989`** |
| sha256（小写） | `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca` | **`c3fc3a34e67b2321048a8861a9b178c744361698a838039b0361287c9fb542c0`** |
| sha256（大写，两处用） | `B675FB6A1CDAE7920F90ABF63E59AA76EA8DF37AE8A8C5D5D15B10B94218C4CA` | **`C3FC3A34E67B2321048A8861A9B178C744361698A838039B0361287C9FB542C0`** |

> ⚠ **v1 的 `3cb6bea9…`/55,729 与 v2 的 `fedc9537…`/58,938 均已作废**（v2 = 五条裁决，v3 = 对抗复核 F1-F4 修复）。别拿旧代的值去填 pin。

**LF 铁律**：新 sha 必须按 LF 字节算。落地后重算一次并与上表核对：
```
git show HEAD:rules/canonical_rules.json | sha256sum
git show HEAD:rules/canonical_rules.json | wc -c
```
草案是在 Linux 侧以 `newline="\n"` 写出的，实测 CR 字节数 = 0。**绝不用 Python `write_text` / `json.dump` 直接写 tracked 文件**。

---

## 0. 开工前置（三件，缺一不可）

| # | 前置 | 为什么是前置 |
|---|---|---|
| P1 | **C26 回填**：`docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md` 的 `:115` 与 `:136` 落后于发包副本 | C14/C15 的依据就压在这两行的 fill-first 补翻上。不回填 = 改稿引用一份仓内查不到的表述。文本见 §3 C26 |
| P2 | ~~份6 provenance 入 tracked 档~~ **已办**（裁决 #6 建档） | `docs/research/canonical_batch_20260808/BOX_CACHE_PARAMETER_PROVENANCE.md` 已在本 worktree 立好（同样未提交），`cache_parameters.provenance` 的指针现在指得到实体。落地时**随批一起提交**，别漏进 pathspec |
| P3 | **树冻结**：认证链测试/preflight 跑起来之前，把所有 src/scripts 改动改完提交完 | 记忆卡 `sealed-file-edit-poisons-live-test-runs`：运行期改树内任何文件（含 docstring）都毒化成假红 |

---

## 1. sha / size pin 站点全集（**18 处**，全部必改）

> ⚠ **fen1 §3 的前置只列了 14 处，实测漏 5 处**：`test_w0_g1_generator_smoke.py:187`、`CLAUDE.md:106`、`PROJECT_LOCK.md:268`、`README.md:176`、`27_status_dashboard.md:87`。
> ⚠ `docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md` 的 17 处清单也**已过期一处**（dashboard 那行由 `4d0c7ef` 加入，晚于 canonical 批 `fab718a`）。**照抄任何一份旧清单都会漏。**
> ⚠ **两处是大写 sha**，只 grep 小写必漏 → 扫描一律 `rg -i`。
> ⚠ `strict_contract.py` 被 `.rgignore` 投影出 rg 默认结果 → 扫描一律带 `--no-ignore --hidden`；并**排除 `.claude/worktrees/`**（别的会话副本）与 `.git/`。

### A. 活代码 / 测试 pin（fail-closed，4 处）

| # | 路径 | 行 | 形态 |
|---|---|---|---|
| 1 | `scripts/preflight_gate.py` | 63 | **大写** sha；该表**无 size 常量**（`LOCKED_EXACT_ARTIFACT_SIZE_BYTES` 只钉 candidate_placements） |
| 2 | `src/search/certified_artifact_contract.py` | 100 | 小写 sha |
| 3 | `docs/research/witness_constructor_20260717/07_routing_aware/strict_contract.py` | 38 | 小写 sha。**这是活代码不是史料**——被 `src/tests/test_witness_campaign.py`、`test_witness_shelf_constructor.py` 真导入执行。另：`:33-37` 的注释块叙述的是 08-07 批，需同批改叙述 |
| 4 | `src/tests/test_w0_g1_generator_smoke.py` | 187 | 小写 sha |

> `src/tests/test_v102_locked_exact_artifact_contract.py` **不用手改**：它全部从常量现算，且 `:184` 交叉核对 preflight 表与 contract 表必须逐字相等 → **1 与 2 必须同批改，改一个就红**。

### B. 文档 pin（sha ＋ size，14 处）

| # | 路径 | 行 | 备注 |
|---|---|---|---|
| 5 | `CLAUDE.md` | 106 | 同行还含 5 个 superseded candidate_placements sha，**只改 canonical 那一组** |
| 6 | `FILE_STATUS.md` | 51 | sha+size 同行 |
| 7 | `PROJECT_LOCK.md` | 268 | **改这行会触发 Chain D（§2.3）** |
| 8 | `README.md` | 176 | **大写 sha**（表格行） |
| 9 | `docs/README.md` | 48 | |
| 10 | `docs/exact_campaign_operations.md` | 85（size）+ 86（sha） | 跨两行 |
| 11 | `docs/parallel_configuration.md` | 42 + 43 | 跨两行 |
| 12 | `docs/subjects/authoritative_numbers.md` | 13 | |
| 13 | `docs/subjects/certified_exact_contract.md` | 13 | |
| 14 | `docs/项目说明/01_overview.md` | 112 + 113 | 跨两行 |
| 15 | `docs/项目说明/06_current_status.md` | 259 + 260 | 跨两行 |
| 16 | `scripts/README.md` | 47 + 48 | 跨两行 |
| 17 | `specs/11_pipeline_orchestration.md` | 30 + 31 | 跨两行 |
| 18 | `docs/项目说明/27_status_dashboard.md` | 87 | **旧清单漏项**；无时态页，按权威顺序第 5 条本来就必须同批更新 |

### C. 明确**不改**的（史料 / 别的链）

- `docs/项目说明/00_master_roadmap.md:532,578,599,610` —— dated 台账叙事行
- `docs/research/canonical_batch_20260807/{RESEAL_MANIFEST.md:12, pin_audit_true_values.txt:3-7, README.md:18}` —— 08-07 批的历史 before/after 证据
- `docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md:66`
- `docs/research/cleanroom_rederivation_20260718/25_rstar_pricetag_delivery_20260804/*` —— 钉更早代，replay 门故意 fail-closed
- `docs/research/w0_power_cycle_domino_d6_20260728/README.md:118` 及继承段历代值 —— 记代设计本意
- `docs/research/b1_sidewise_marked_membrane_20260724/authority_bootstrap_v1.py:24` —— 停在旧代，不在断言路径
- `docs/research/p2_0_specialized_20260807/refute_round1/GAME_RULE_IMPACT_AUDIT.md:17` —— **tracked，且只提 size 不提 sha**（原文 `rules/canonical_rules.json 全文（v1.2.0，40,371 字节，9 个顶层区块逐条过）`）。因为不含 sha，§1 的 sha 扫描照不到它，但 §7 验收步的 `rg -i '40,371|40371'` **一定会把它扫出来**。**它是史料**（记的是某轮审查当时覆盖了哪一版规则文件，不是现行状态断言）⇒ **不改**。此条由对抗复核 F3 点名补入，就是为了免掉落地当天的临时判断
- `a914ba63` / `adcc2a6e` / `d5e3911f` / `78e2bcf0` —— superseded **candidate_placements** 链，与 canonical 无关，**别顺手改**
- `.artifacts/**` —— untracked 本地证据
- **假阳性**：`data/proof_obligations/pr2_dependency_floor_manifest.json:6278` 命中 `40371` 是另一个 sha 内的巧合子串；`docs/research/batch_ce_attach_host_20260712/**/mem.csv` 同理

### D. 边界情况（主线程拍板）

`docs/research/rule_system_redesign_20260807/{scout_pin_chain.md:6,48, canonical_anatomy.md:3, failure_taxonomy_and_requirements.md:473}` —— 08-07 侦察报告，自称只读转述，但用**现在时**描述 pin 面。建议：不改字节值（保持批次快照忠实），在 `scout_pin_chain.md` 顶部加一行「本文快照于 `b675fb6a` 代」。

---

## 2. 连锁（不含 canonical sha 字面，但一动必红）

### 2.1 Chain B —— contract 字节变 ⇒ close-kernel reseal（**严格有序，checker 自钉最后**）

| 序 | 路径 | 行 | 当前值 |
|---|---|---|---|
| B1 | `scripts/check_p1_2_proof_obligations.py` | 13023 | `'src/search/certified_artifact_contract.py': '0fb1a6507e4b3b8f21a186189b0e129b5537b386278bf0b19a4ac8178da9119b'` |
| B2 | `data/proof_obligations/p1_2_proof_obligations.json` | 1033 | contract obligation 的 `source_sha256` = 同上 |
| B3 | `data/proof_obligations/p1_2_proof_obligations.json` | 1016 | **checker 自钉** `ebb72f66824772c4b8adde3eca6c6360bf64d658f6d00183a1d5189c6a9f23ea` —— **必须最后算** |

跑通判据：`python scripts/check_p1_2_proof_obligations.py` → `15 obligations anchored; 67 proof-bearing sink files sealed`。

### 2.2 Chain C —— preflight 字节变 ⇒ parity 保护面

| 路径 | 行 | 当前值 |
|---|---|---|
| `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` | 75 | `"scripts/preflight_gate.py": "468eb896857ff2546b97c0238d213d92d182a53c44cb19041ece3f5e2dda7846"` |
| 同上（注释） | 56-65 | 「authorized preflight successor」叙事段 —— 改写为新 successor，旧代记在此 |

### 2.3 Chain D —— `PROJECT_LOCK.md` 字节变 ⇒ **6+1 继承链**（因 §1 的 pin #7 而触发）

当前 lock sha 实测 `e12b41d672aada38911d3f485fc866f14157959c166d1882dbbf62181568a343`。**常量名不统一，按名字 grep 会漏**：

| 路径 | 行 | 常量名 |
|---|---|---|
| `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` | 43 | `_PROJECT_LOCK_SHA256` |
| `src/tests/test_w0_d6_gate.py` | 47 | `PROJECT_LOCK_SHA256` |
| `src/tests/test_w0_d6_replay.py` | 60-61 | `EXPECTED_PROJECT_LOCK_SHA256` |
| `docs/research/w0_power_cycle_domino_d6_20260728/d6_joint_completion_gate.py` | 34 | `PROJECT_LOCK_SHA256`（**无 `EXPECTED_` 前缀**） |
| `docs/research/w0_power_cycle_domino_d6_20260728/replay_d6_certificate.py` | 48-50 | `EXPECTED_PROJECT_LOCK_SHA256` |
| `docs/research/w0_power_cycle_domino_d6_20260728/run_d6_research.py` | 53-54 | `EXPECTED_PROJECT_LOCK_SHA256` |
| **+1 派生重算** | `src/tests/test_w0_d6_gate.py:48` | D6 antecedent canonical-JSON 哈希，当前 `1ade6fc7…`，**内嵌 lock sha 故必须重算**，不是照抄 |
| 记代 | `docs/research/w0_power_cycle_domino_d6_20260728/README.md:129` | 继承段追加新代 |

> 记忆卡 `project-lock-sha-succession-chain` 实锤：`d5578f8` 漏过一次，潜伏到当晚全量门才炸。

### 2.4 strong-status allowlist

本批**不改任何写 strong status 的 AST 节点**（改动全在 JSON 数据与文档），预期 `check_strong_status_write_allowlist.py` 无需改。仍需跑通确认：`65 AST nodes, 83 allowlist entries`。

---

## 3. 承重档同批订正（F 组，非 canonical 字节但必须同批）

| # | 落点 | 动作 | 文本要点 |
|---|---|---|---|
| **C26** | `docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md:115` | **回填**（发包副本已有、仓内档没有） | 把「同种物品可占多组（P2 待判）」改为「（**P2 已判**：owner 08-06 晚定谳「当然是会的」，且**满格后开新格**=fill-first；本格 08-07 补翻——原「待判」系裁决后漏更新，canonical slot_count_clause 已带 adjudicated 2026-08-06 字段）」。逐字源：`.artifacts/gpt_pro_review_batch_20260807/1_canonical_text/AXIOM_KERNEL_PROPOSAL_20260806.md:115` |
| **C26** | 同文件 `:136` | **回填** | 把「「6」须另证同型不占多槽（P2 判别实验）」改为带「**08-07 补翻：P2 已判**——owner 08-06 晚定谳同型可占多槽且满格后开新格，故该「另证」反向落空、类型数安全上界不存在，slot 口径为准，与 canonical slot_count_clause 一致」。逐字源同上 `:136` |
| **C24** | 同文件 `:155`（#21）与 `:229-234`（P3） | **必改** | 删「边界口」作为非拒收终端的例子；**两层理由都写**：口朝向 0 进 1 出（`preprocess_plan.json:41-45`）＋ X1 格数账（139 格条带 / 46 台取货口占 138 格 / 141 > 139）。canonical 的 `axiom_derivation` 引用 #21，不改这里等于留着回流入口 |
| **C25** | `docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md:114-121` | **加注不改文** | 「有线连接仓库的存货口（边界仓储口、核心）」是重分类前的残留表述。档案件按史料门纪律不改原文，**加一条指向 canonical 现行读法的注** |
| **P2** | `docs/research/canonical_batch_20260808/`（新建） | **建档** | 份6 深挖 1 ② 的可入档 provenance 条目 ＋ 本批改稿归档。见 §0 P2 与 `BLOCKERS.md` #6 |

---

## 4. 无时态速查层同批更新（权威顺序第 5 条：凡改动其所记状态的批必须同批更新）

| 页 | 行 | 要改什么 |
|---|---|---|
| `docs/项目说明/27_status_dashboard.md` | 87 | canonical sha 短标签（同时也是 §1 的 pin #18） |
| `docs/项目说明/26_rules_handbook.md` | §4.1（约 96-99） | 格数账/件数账的「两条前提**尚未入册**」措辞作废——两条已入册（`slot_count_clause.cache_parameters`）。改为指向 canonical 新键；同步两处新内容：①(a) 账的「模型 front 排他面」显式条件与它的 current-model theorem 定性；②owner 08-07 那条**不依赖该面**的腿（本实例仓储系候选仅 2 终品，凑不出 10 s 内 7+ 种） |
| `docs/项目说明/26_rules_handbook.md` | §11 欠账（约 247-252） | **两条一起销账**（裁决 #5）：①「缓存槽 fill-first 前提 ＋ 单槽容量参数未入 canonical」→ 本批 C15 结清；②「协议箱由 `terminal_clause` class (2) 提升为 drain 终点的措辞改判（裁决已在手）」→ 本批以**实例级 discharge 注**落地（类级规则不动），标结清并写明落法 |
| `docs/项目说明/26_rules_handbook.md` | §7 准入口行（`:168`）＋ 误读对照表行（`:234-235`） | 「条款 authority 前提『无候选池或谓词消费它』**当前满足**」改为指向 canonical 新的**条件式** authority（C23）；补一句「本批已把该省略面登记进 `model_stricter_faces` 第 (6) 项」（裁决 #1）。「处置 owner 已定＝先放着、随墙审计首轮回桌、准入口为种子案例」维持不变 |
| `docs/项目说明/26_rules_handbook.md` | 混流/终端段 | class (2) 从「6 槽静态界」改为「逐次到货接收不变量」＋本实例已 discharge；`model_stricter_faces` 从四项变**六项**（新增 `warehouse_bridge_exclusion` 与准入口省略面）＋两条使用规则 |
| `docs/项目说明/28_pitfalls_and_sop.md` | pin 面 SOP | 补记「canonical pin 面实测 18 处、两处大写、`strict_contract.py` 被 `.rgignore` 藏」这三条 |
| `docs/项目说明/00_master_roadmap.md` | 台账 | 记本批（不是状态权威，是排期/拍板台账） |

---

## 5. 必跑的门（顺序）

```
# 0) 先确认树是干净的、认证链测试没在跑
git status --short

# 1) 两个结构 checker（Chain B 之后）
./.venv/bin/python scripts/check_p1_2_proof_obligations.py
      期望: 15 obligations anchored; 67 proof-bearing sink files sealed
./.venv/bin/python scripts/check_strong_status_write_allowlist.py
      期望: 65 AST nodes, 83 allowlist entries

# 2) 全量 preflight（退出码只有 0/1，别等 2）
./.venv/bin/python scripts/preflight_gate.py --full

# 3) 慢 soundness lane —— 本批改了 certified_artifact_contract.py 的常量，属认证核心，不可跳
./.venv/bin/python scripts/preflight_gate.py --slow-tests        # 串行、~13min

# 4) 定点复跑（本批直接命中的）
./.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/reseal -q \
  src/tests/test_rules.py \
  src/tests/test_preprocess_context.py \
  src/tests/test_v102_locked_exact_artifact_contract.py \
  src/tests/test_w0_g1_generator_smoke.py \
  src/tests/test_w0_d6_gate.py src/tests/test_w0_d6_replay.py \
  src/tests/cuts/test_rule_cut_evolution_authority_parity.py \
  src/tests/test_witness_campaign.py src/tests/test_witness_shelf_constructor.py
```

**解释器身份也是 pin**：一律 `./.venv/bin/python` 发射（正牌 `.venv`，`aa2f05b` 已回正）。用 backup 解释器会得到一批假红。
**gate 输出永远全量落文件**，别 `| tail`（BLOCKED 取证被毁过）。
**pytest 并发互踩**：`pytest.ini` 全局 `--basetemp=.pytest_tmp`，多窗口时各自覆盖为独立子目录。

---

## 6. 提交 pathspec 全集（一次提齐，漏一个就是半个 reseal）

```
rules/canonical_rules.json
scripts/preflight_gate.py
src/search/certified_artifact_contract.py
docs/research/witness_constructor_20260717/07_routing_aware/strict_contract.py
src/tests/test_w0_g1_generator_smoke.py
CLAUDE.md FILE_STATUS.md PROJECT_LOCK.md README.md
docs/README.md docs/exact_campaign_operations.md docs/parallel_configuration.md
docs/subjects/authoritative_numbers.md docs/subjects/certified_exact_contract.md
docs/项目说明/01_overview.md docs/项目说明/06_current_status.md
docs/项目说明/27_status_dashboard.md docs/项目说明/26_rules_handbook.md
docs/项目说明/28_pitfalls_and_sop.md docs/项目说明/00_master_roadmap.md
scripts/README.md specs/11_pipeline_orchestration.md
scripts/check_p1_2_proof_obligations.py data/proof_obligations/p1_2_proof_obligations.json
src/tests/cuts/test_rule_cut_evolution_authority_parity.py
src/tests/test_w0_d6_gate.py src/tests/test_w0_d6_replay.py
docs/research/w0_power_cycle_domino_d6_20260728/d6_joint_completion_gate.py
docs/research/w0_power_cycle_domino_d6_20260728/replay_d6_certificate.py
docs/research/w0_power_cycle_domino_d6_20260728/run_d6_research.py
docs/research/w0_power_cycle_domino_d6_20260728/README.md
docs/research/canonical_batch_20260807/AXIOM_KERNEL_PROPOSAL_20260806.md
docs/research/canonical_batch_20260807/PORT_SEMANTICS_REVERDICT_A_20260806.md
docs/research/canonical_batch_20260808/BOX_CACHE_PARAMETER_PROVENANCE.md   # 新建（裁决 #6），canonical 的 provenance 指针指着它
docs/research/rule_system_redesign_20260807/scout_pin_chain.md   # 若采纳 §1D 建议
```

> **`--amend` 前先验 HEAD 归属**（记忆卡 `amend-can-hit-another-sessions-commit`）：共享 index 仓库里 `--amend` 改的是 HEAD，中途被并发会话推进就折进对方提交。凡以 HEAD 为隐式参数的操作（amend/reset/rebase/cherry-pick）先验 HEAD 是不是自己的。

---

## 7. 落地后回执（建议逐条记进台账）

- [ ] `git show HEAD:rules/canonical_rules.json | sha256sum` = `c3fc3a34…` 且 `wc -c` = `59989`
- [ ] `docs/research/canonical_batch_20260808/BOX_CACHE_PARAMETER_PROVENANCE.md` 已随批提交（canonical 里有指针指着它，漏提 = 悬空引用）
- [ ] `rg -i --no-ignore --hidden 'b675fb6a'` 只剩 §1C 的史料站点（逐个点名核对，不是数字对上就算）
- [ ] `rg -i --no-ignore --hidden '40,371|40371'` 同上
- [ ] 两个 checker PASS（数字与期望逐字相同）
- [ ] `--full` 与 `--slow-tests` 全绿，输出全量落文件
- [ ] 26/27/28 三页已同批改
- [ ] **绿灯 ≠ owner 关门动作**：本批不产生任何 release closure、不推导 clean-review 计数
