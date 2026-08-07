# RESEAL_MANIFEST — canonical 公理 kernel + 四件套修正批（2026-08-07）

施工席：canonical 修正批 worktree（agent-a1e5174b682fe3427）。owner 2026-08-07 晨拍板：
kernel 提案与四件套合并、一次 freeze-ritual 走完。本清单是 reseal 连锁的完整 pin 面
台账与提交 pathspec；真值审计输出（python import 断言，非 grep）见同目录
`pin_audit_true_values.txt`。

## 0. 核心字节变化

| 文件 | 旧 | 新 |
|---|---|---|
| `rules/canonical_rules.json` | 18,137 B / `c3666d78d5dd1329514c7813be9f91f09cb3ce7b94907ef5b6ce746c9bcbbbd5` | 40,371 B / `b675fb6a1cdae7920f90abf63e59aa76ea8df37ae8a8c5d5d15b10b94218c4ca` |
| `PROJECT_LOCK.md` | `10c3f7b9174974e84271bb1dc44df35e84fb73c5d65af0df68545c4b2c3fd82a` | `e12b41d672aada38911d3f485fc866f14157959c166d1882dbbf62181568a343` |
| `src/search/certified_artifact_contract.py` | `2fee2970de469ef89b0f2048489eec7a369c931d968be11c35073c9a16772075` | `0fb1a6507e4b3b8f21a186189b0e129b5537b386278bf0b19a4ac8178da9119b` |
| `scripts/check_p1_2_proof_obligations.py` | `fe93045b63ff0710423e78592e8f36ae6f2faecf4fcd9460e1f4200945a58e7e` | `ebb72f66824772c4b8adde3eca6c6360bf64d658f6d00183a1d5189c6a9f23ea` |
| `scripts/preflight_gate.py` | `c92139da391c750b8a12a74d8d8f34a6fd686e575e8d714e1f76a133301c10ec` | `468eb896857ff2546b97c0238d213d92d182a53c44cb19041ece3f5e2dda7846` |
| D6 antecedent fixture（派生哈希，非文件） | `eafeb6b2d75e06558b870f97b3b9690720cf6f51d3760ddbc4be09fbf9f2685f` | `1ade6fc7f783e033e272b07a4270522db1739b50af3c5efee58d84fedc830d26` |

canonical 内容变化 = 纯 additive（机器验证：8 个 solver 消费顶层段与 HEAD byte-identical，
现有 semantics 条款每个字段逐一 identical；新增 = `semantics.axiom_kernel` /
`rate_lemma_scope` / `port_commodity_scope` 三个新条目 + 现有 10 条款的注记子键）。
`metadata.version` 保持 1.2.0（version 流入派生工件 `current_preprocess_context.json`
`source_rules_version` 字段与 `test_preprocess_context.py:61` pin；本批不动 solver 消费面，
循 5f1b974 emptiness 批先例，派生 preprocess 工件字节不变）。

## 1. 第一层：canonical sha/size 直接 pin 面（17 处）

代码/测试（4）：
| 文件:位置 | 内容 |
|---|---|
| `scripts/preflight_gate.py:63` | FROZEN_ARTIFACTS，**大写** sha（grep 小写会漏，audit 必须大小写不敏感或 python 真值） |
| `src/search/certified_artifact_contract.py:100` | LOCKED_EXACT_ARTIFACT_SHA256，小写（canonical 无 size 常量——SIZE_BYTES 只钉 candidate_placements） |
| `docs/research/witness_constructor_20260717/07_routing_aware/strict_contract.py:35` | EXPECTED_SHA256 + 注释更新（该文件被 .rgignore 从默认 rg 投影排除，审计必须 `--no-ignore`） |
| `src/tests/test_w0_g1_generator_smoke.py:187` | frozen_inputs.rules.sha256 运行时断言 |

文档（13，sha+size 同步）：`CLAUDE.md` / `FILE_STATUS.md` / `PROJECT_LOCK.md` /
`README.md`（大写表格）/ `docs/README.md` / `docs/exact_campaign_operations.md` /
`docs/parallel_configuration.md` / `docs/subjects/authoritative_numbers.md` /
`docs/subjects/certified_exact_contract.md` / `docs/项目说明/01_overview.md` /
`docs/项目说明/06_current_status.md` / `scripts/README.md` /
`specs/11_pipeline_orchestration.md`。

## 2. 连锁层

**Chain B（contract 字节变 → close-kernel）**，按序：
1. `scripts/check_p1_2_proof_obligations.py:13023` CLOSE_KERNEL_V99 map 的 contract 条目 → `0fb1a650…`；
2. `data/proof_obligations/p1_2_proof_obligations.json:1033`（path=certified_artifact_contract.py 的 obligation）→ `0fb1a650…`；
3. checker 自身字节因步 1 变化 → 重算 checker sha → `p1_2_proof_obligations.json:1016`（checker 自钉条目）→ `ebb72f66…`。**checker 自钉最后**；语义投影不含 source_sha256，链一步收敛。

**Chain C（preflight 字节变 → parity 受保护面）**：
`src/tests/cuts/test_rule_cut_evolution_authority_parity.py` — `_PROTECTED_SURFACE_SHA256["scripts/preflight_gate.py"]` → `468eb896…` + authorized successor 注释改写（本批 successor 取代 08-05 emptiness successor，记代保留）。

**Chain D（LOCK 字节变 → 6+1 继承链）**：
- 3 测试 pin：parity `_PROJECT_LOCK_SHA256:43`、`src/tests/test_w0_d6_gate.py:47`、`src/tests/test_w0_d6_replay.py:60-62` → `e12b41d6…`；
- 3 D6 脚本常量：`docs/research/w0_power_cycle_domino_d6_20260728/{d6_joint_completion_gate.py:34, replay_d6_certificate.py:48-50, run_d6_research.py:53-55}` → `e12b41d6…`；
- +1 antecedent 重算重钉：PROTOCOL 内嵌 lock sha → `build_d6_antecedent` canonical-json 哈希重算 = `1ade6fc7…` → `test_w0_d6_gate.py:48` + D6 `README.md` 继承段记代（新代=08-07 本批；上一代 10c3f7b9/eafeb6b2；再上 aeadef3a/6efaff3e；再早 64a68024/7de91e64）。

**不需要动的面（已核实为何不动）**：
- `rules/canonical_rules.schema.json` 与 `src/rules/models.py`：新增全部落在 `semantics` 段内，schema 该段 `additionalProperties: true`（schema:431-434）、pydantic 为 `Optional[Dict[str, Any]]`（models.py:185）；jsonschema/pydantic/strict_json 三解析实测通过；
- `scripts/check_strong_status_write_allowlist.py`：无 strong-status 写点变化，checker 实跑绿（65 nodes / 83 entries）；
- `data/solutions/current_preprocess_context.json`：不内嵌 canonical sha（实测 grep 零命中），version 未 bump 故字节不变；
- 派生 preprocess 工件（mandatory_exact_instances / generic_io_requirements / preprocess_plan）：只由 recipes/targets/templates/globals 派生，八段 byte-identical（见 DEPENDENCY_VERIFICATION.md）；
- `candidate_placements.json`：不需重生成（见 DEPENDENCY_VERIFICATION.md）。

## 3. 史料门（故意保留旧 pin，不改）

- `docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md:66`：08-05 emptiness 批的过渡记录（"pin 由 17,510B/5012… 改为 18,137B/c3666d78…"），历史叙事非现值声明；
- `docs/研项目说明/00_master_roadmap.md` 台账各行内的 c3666d78 与 `:422-425/:454-458` 行号引用：dated ledger 行 = 史料；台账新行（本批落地记录）与 §4 #12 / 缺口表 :555 行的销账由主线程在合入时写；
- `docs/research/w0_power_cycle_domino_d6_20260728/README.md` 继承段中的历代 lock/antecedent sha：记代设计本意；
- `.artifacts/**`：机器本地证据目录，untracked，不在本批 pathspec 内。

## 4. 提交 pathspec 全集（27 modified + 1 new dir）

```
rules/canonical_rules.json
scripts/preflight_gate.py
scripts/check_p1_2_proof_obligations.py
scripts/README.md
src/search/certified_artifact_contract.py
src/tests/cuts/test_rule_cut_evolution_authority_parity.py
src/tests/test_w0_d6_gate.py
src/tests/test_w0_d6_replay.py
src/tests/test_w0_g1_generator_smoke.py
data/proof_obligations/p1_2_proof_obligations.json
docs/research/w0_power_cycle_domino_d6_20260728/README.md
docs/research/w0_power_cycle_domino_d6_20260728/d6_joint_completion_gate.py
docs/research/w0_power_cycle_domino_d6_20260728/replay_d6_certificate.py
docs/research/w0_power_cycle_domino_d6_20260728/run_d6_research.py
docs/research/witness_constructor_20260717/07_routing_aware/strict_contract.py
docs/research/canonical_batch_20260807/          # 新目录：定谳存档 + 本清单 + 验证记录
CLAUDE.md
FILE_STATUS.md
PROJECT_LOCK.md
README.md
docs/README.md
docs/exact_campaign_operations.md
docs/parallel_configuration.md
docs/subjects/authoritative_numbers.md
docs/subjects/certified_exact_contract.md
docs/项目说明/01_overview.md
docs/项目说明/06_current_status.md
specs/11_pipeline_orchestration.md
```

## 5. 验证记录

- 双结构 checker 绿：`15 obligations anchored; 67 proof-bearing sink files sealed`；`65 registered AST node(s), 83 allowlist entry(ies)`；
- pin 链目标测试：parity + w0_d6 gate/replay + w0_g1 + preprocess_context = **119 passed**（`-p no:randomly --basetemp=.pytest_tmp/canonical_batch_pins`）；
- 真值审计（python import + assert，全部 MATCH）：`pin_audit_true_values.txt`；
- 残留审计：`rg -i --no-ignore --hidden` 六个旧 sha 在 live 面零残留，剩余命中全部在 §3 史料名单内；
- gate：`--full` 与 `--slow-tests` 完整输出见同目录 `gate_full_20260807.log` / `gate_slow_20260807.log`（提交后跑，树冻结纪律）。

## 6. 形状决策留痕（非开放问题）

1. **修正采 additive 形状**：现有条款 statement 字节保留，定谳修正以带 `adjudicated` 日期的子键落地（`terminal_clause` / `rationale_restated` / `slot_count_clause`）——依据任务书「不删不改任何现有条款的语义本体，只加推导注记与新增章节」。owner 若偏好就地改写 statement，属简单再编辑 + 重走本清单同一连锁。
2. **U-02（模型侧两商品合流后再分流结构性 INFEASIBLE，比在案终裁更强）**：属模型比 canonical 更严的保守面（方向安全），已在 `axiom_kernel.model_stricter_faces` 登记路由复验类；mixflow 手术线（b9207e7 起）正在动该表达面，不属本批 scope。
3. **source front 模型解锁**：canonical 只作 descriptive 登记（confirmed over-strict face），模型/sealed 面解锁明确排除在本批外（`axiom_kernel.model_stricter_faces` 内注明），与台账 08-06 行一致。
