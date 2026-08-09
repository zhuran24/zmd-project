# 侦察报告：canonical 冻结/pin 链全谱（2026-08-07）

> 只读侦察转述，**非权威**——承重引用前回源核对 file:line。fp-derivation 席派出、主线程存档。
> 原始任务输出已随会话临时区回收，本文件为唯一存续副本。
> **本文快照于 `b675fb6a` 代**（2026-08-07）。全篇的字节值与 sha 是那一代的实测值、刻意保持不动；
> 2026-08-08 批已把 canonical 推进到 `c3fc3a34` / 59,989 B，现行 pin 面读 `PROJECT_LOCK.md` 与
> `scripts/preflight_gate.py`。另：本文列的 pin 站点数在 08-08 批实测为 **18 处**（本文按 08-07 代计数）。

## 1. `rules/canonical_rules.json` 直接 pin 面（现值 40,371 B / `b675fb6a…`）

注意：contract 文件在 `src/search/certified_artifact_contract.py`（不在 `src/interchange/`）。

**代码/测试 pin（4 处，fail-closed）**：
- `scripts/preflight_gate.py:63` — `FROZEN_ARTIFACTS`，**大写** sha（小写 grep 会漏）。校验点 `:264`。
- `src/search/certified_artifact_contract.py:100` — `LOCKED_EXACT_ARTIFACT_SHA256`，小写；路径 `:92`。canonical **无 size pin**（`LOCKED_EXACT_ARTIFACT_SIZE_BYTES` `:107-109` 只钉 candidate_placements）。
- `docs/research/witness_constructor_20260717/07_routing_aware/strict_contract.py:38` — `EXPECTED_SHA256`；消费点 `:213`。该文件被 `.rgignore` 藏，审计需 `--no-ignore`。
- `src/tests/test_w0_g1_generator_smoke.py:187` — 运行期断言 `manifest.frozen_inputs.rules.sha256`。

**文档 pin（13 处，sha+size）**：`CLAUDE.md:105` · `FILE_STATUS.md:51` · `PROJECT_LOCK.md:268` · `README.md:176`（大写表） · `docs/README.md:48` · `docs/exact_campaign_operations.md:85-86` · `docs/parallel_configuration.md:42-43` · `docs/subjects/authoritative_numbers.md:13` · `docs/subjects/certified_exact_contract.md:13` · `docs/项目说明/01_overview.md:112-113` · `docs/项目说明/06_current_status.md:259-260` · `scripts/README.md:47-48` · `specs/11_pipeline_orchestration.md:30-31`。

**刻意保留的陈旧 pin（勿更新）**：`docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md:66`、roadmap 台账行、D6 README 生成链。

## 2. freeze-ritual 全链（一次 canonical 修改）

流程文书三层：`CLAUDE.md:103-107`（§5 铁律 `:107`：pin sha 按 LF 字节算 `git show HEAD:<file> | sha256`，绝不 `write_text`/`json.dump` 写 tracked 文件；提交 pathspec 覆盖 reseal 全集）；`PROJECT_LOCK.md:268-279, :302`（政策+pin 表）；`docs/research/canonical_batch_20260807/RESEAL_MANIFEST.md`（**唯一完整实操样本**，117 行）；`cc_memory_vnext/cards/close-kernel-reseal-execution-sop.md`（close-kernel 子链 SOP；开工前先 ruff-clean 源码否则 sha 反复漂）。

**无自动化脚本**——ritual 是手动迭代，靠 pin_audit_true_values.txt 式 Python import 断言审计（不用 grep）。

链序：
1. **第一层**：17 处直接 pin（上述 4 代码 + 13 文档）。
2. **Chain B（contract 字节变 → close-kernel reseal）**，严格有序：a. `scripts/check_p1_2_proof_obligations.py:13023`（`CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH`，声明 `:12926`）；b. `data/proof_obligations/p1_2_proof_obligations.json:1033`（contract obligation `source_sha256`）；c. checker 自钉 `p1_2_proof_obligations.json:1016`（**永远最后**；在 JSON 不在源码，无鸡生蛋）。
3. **Chain C（preflight 字节变 → parity 保护面）**：`src/tests/cuts/test_rule_cut_evolution_authority_parity.py:75`（`_PROTECTED_SURFACE_SHA256["scripts/preflight_gate.py"]`）+授权后继注释（`:58`）；断言 `:314-316`。
4. **Chain D（PROJECT_LOCK.md 字节变 → 6+1 继承）**：`test_rule_cut_evolution_authority_parity.py:43` · `src/tests/test_w0_d6_gate.py:47` · `src/tests/test_w0_d6_replay.py:61` · `docs/research/w0_power_cycle_domino_d6_20260728/d6_joint_completion_gate.py:34` · `replay_d6_certificate.py:49` · `run_d6_research.py:54`；**+1 派生重算**：D6 antecedent canonical-JSON hash 内嵌 lock sha → 重算 → `test_w0_d6_gate.py:48` + D6 README 生成注。
5. **派生工件核查**：mandatory_exact_instances / generic_io_requirements / candidate_placements / current_preprocess_context 是否变——近两批均未变（只有 recipes/production_targets/facility_templates/globals 进 preprocess；`metadata.version` 刻意保持 1.2.0，其 pin 在 `test_preprocess_context.py:61`）。
6. **门禁**：双结构 checker → `preflight_gate.py --full` 与 `--slow-tests`；CI 在 `.github/workflows/project_foundation.yml:67`（--ci）与 `:102`（--slow-tests）。

## 3. `canonical_rules.schema.json` — 硬执行非装饰

根 `additionalProperties:false`（`:437`），新顶层键 fail-closed。三个运行期文件入口+测试强制：`src/interchange/preprocess_context.py:611-621`（`_validate_preprocess_source_schemas`，构造前跑，F-PRE-R10-01/`PROJECT_LOCK.md:371`）；`src/placement/placement_generator.py:476`（第三独立入口，F-PRE-R11-01/`PROJECT_LOCK.md:373`）；`src/tests/test_rules.py:45/:52/:61` + pydantic 二道门（`CanonicalRulesDocument.model_validate` + `src/rules/semantic_validator.py`）。**刻意逃生舱**：`semantics` 块 `additionalProperties:true`（schema `:431-434`）、非 required——08-07 公理批零 schema 改动全靠它。preflight 本身不跑 schema 校验（只钉字节，schema 经 pytest lane 到达）。

## 4. `rules/preprocess_plan.json`（1,383 B / `5c669c4f…`）additive-only 判定

pin 面：`preflight_gate.py:66`（大写）· `certified_artifact_contract.py:102`（路径 `:95`）· 13 处文档 pin（同 §1 清单各文件相邻行）。另绑进 campaign hash 闭包：`src/search/exact_campaign.py:287-291`（`OPTIONAL_EXACT_HASH_FILES`，消费 `:460`）。

新顶层键 fail-closed 双机制：任意新键 → schema 拒（`preprocess_plan.schema.json:105` 根 closed，required `:6-9`），在 `_validate_preprocess_source_schemas` 构造前触发；三个危险键（`recipes`/`production_targets`/`commodity_roles`，`preprocess_context.py:25` `PLAN_CANONICAL_OVERRIDE_KEYS`）→ 构造器显式 `ValueError`（`:177-185`，理由 R6-F-01）。**已知缝**：`build_preprocess_context_from_rules_and_plan` 是纯构造器，直接喂 dict（如测试）绕过 schema，只有 3 危险键兜底、其它未知顶层键静默忽略——`specs/18_preprocess_context_contract.md:32` 记明是刻意的。另有 `_validate_utility_operation_namespace_is_additive`（`:461-467`，调用 `:249`）。

## 5. canonical 近三次提交史

| commit | 日期 | 内容 |
|---|---|---|
| `2ea99eb` | 2026-08-07 | 公理 kernel+四件套合批：18,137B/`c3666d78…` → 40,371B/`b675fb6a…`，纯 additive 入 semantics；26 文件+1 新目录，schema **零改动**（semantics 开放块设计的实证） |
| `5f1b974` | 2026-08-05 | emptiness 定义补写：17,510B/`50128453…` → 18,137B/`c3666d78…`；**动了** schema（+38 行，双侧 required） |
| `9c0f724` | 2026-07-18 | 终品路由到物理 provider 大批，canonical 是众多文件之一 |

`2ea99eb` 经 `27969ca`（门收据）合入 main 为 `fab718a`；台账 `00ee932`。盘面字节与 pin 逐字相符（sha256sum 实测）。
