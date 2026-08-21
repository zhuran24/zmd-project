# ACLOSE_PROGRESS — I1_ACLOSE 批断点自续台账

- 批名:I1_ACLOSE(I1 异源化线 · owner 范围 A 收口批)
- 对象 worktree:`/home/zhuran24/.devspace/worktrees/zmd-pj-4dfe6504`
- 起始基线:e73add1(全部改动未 commit)
- 目标基底:main = `aa517cd`(指挥线 08-21 修订:改为「最新 main」,原写 3b02787)

中断重入先读本文件,不重做已标 DONE 的项。

## 段划分与状态

| 段 | 覆盖任务书项 | 状态 | 备注 |
|---|---|---|---|
| S1 基底更新与合流 | 任务 1 | **DONE** | HEAD=3b02787,12 冲突全解,投影重建,回归绿 |
| S1c 基底再合流 | 任务 1(指挥线 08-21 修订) | **DONE** | HEAD=aa517cd,13 文件合流,29 条 issue 逐字节同形 |
| S2a 五条守卫 mutation 测试 | 任务 2 + 任务 3 的补写面 | **DONE** | 60/60 通过;删守卫反证逐条命中 |
| S2b anchor 进强制层 + 语义投影 floor 同步 | 任务 3 的登记面 | **DONE** | 并入 S3 执行(required_tests 48→56) |
| S3 真 reseal | 任务 4 后半 | **DONE** | proof gate 29→1,幂等,红测仍 2 failed |
| S3b reopen 显式登记 | 任务 4 前半 + 任务 7 | **DONE** | 三处登记 + 投影重建,四门 rc=0 |
| S4 全套自验收据 | 任务 5 | TODO | 字节冻结后才可跑 |
| S5 HANDOFF/知识面/CLOSEOUT | 任务 6、7 + 产物封装 | TODO | |

## 已确立的执行事实(勘察产物,供重入直接复用)

### 三组新守卫坐标(`scripts/check_p1_2_proof_obligations.py`,函数 `_check_independent_infeasibility_reverifier_contract`,def 于 :14083)

- 守卫组 A —— PortBindingModel 构造点枚举:LBBDController `_binding_snapshot_kwargs` unpack(:14745 一带)
  + 三路径 `exactly one enumerated PortBindingModel constructor` 与三条 plan-derived keyword(:14800 一带)。
- 守卫组 B —— evaluator 豁免:`PORT_BINDING_CONSTRUCTOR_NON_AUTHORITY_EXEMPTIONS` 中
  `scripts/p2_14_evaluator/run_eval_v1_baseline.py` 必须保留 `exploratory_evaluation_non_authority`
  及其理由串,且该脚本不得进入 proof-bearing 漏斗(:14762–14798)。
- 守卫组 C —— runtime-relaxation 双校验:`certificate.py` 必须校验 theorem 的 `runtime_relaxations`,
  且必须含 "runtime_relaxations do not match reconstructed production relaxation state"(:14840–14854)。

checker 入口:`scripts/check_p1_2_proof_obligations.py:15088`。mutation 测试范式见
`src/tests/test_p1_2_independent_infeasibility_reverifier.py:1137` 起数例:写篡改副本到 tmp_path,
以关键字参数注入 `_check_independent_infeasibility_reverifier_contract(...)`,断言诊断串出现。

### 7 条 anchor 现状(manifest `obligations[13]` = `PO-INDEPENDENT-INFEASIBILITY-REVERIFY`)

`test_anchors`(门不消费)7 条 / `required_tests`(强制层)48 条。7 条 anchor:

实存 3 条(只需迁入 `required_tests`):
- `test_round3_certificate_checker_rejects_runtime_relaxation_tamper` — `src/tests/test_p1_2_independent_infeasibility_reverifier.py`
- `test_round3_exact_session_carries_plan_utility_operation_map` — `src/tests/test_exact_contract.py`
- `test_round3_pose_optional_synthesis_loads_plan_utility_map` — `src/tests/test_binding.py`

不存在 4 条(优先补写):
- `test_round3_checker_enumerates_non_controller_binding_constructors` → 覆盖守卫组 A
- `test_round3_checker_requires_runtime_relaxation_validation` → 覆盖守卫组 C
- `test_round3_checker_rejects_constant_runtime_observation` → 部分等价既有 `test_package_checker_rejects_constant_runtime_contract_fields`
- `test_round3_checker_rejects_generic_input_plan_bypass` → 部分等价既有 `test_package_checker_requires_plan_derived_generic_input_admission`

守卫组 B(evaluator 豁免)无对应 anchor 名,需另起测试名并一并纳入强制层。

### reseal 面

`close_kernel_contract.sink_files` 73 项,每项 `source_sha256` + `mutation_policy:
source_sha256_drift_reopens_p1_2_close_claim`。真 reseal = 全部更新到本批终字节。

### 硬边界(逐项复述,防重入漂移)

- 不 commit;不动主仓 tracked 文件;不写 re-close 记录。
- 不动 authority floor 与 review gate close 记录;两条 sealed-authority 红测保持红,不 skip/xfail/改绿。
- certificate/theorem/semantics 语义逻辑不动。
- 真实工件(54MB candidate_placements.json)只读临时接入必 finally 删。
- Python 一律 `/home/zhuran24/zmd-pj/.venv/bin/python`。

## S1 终态要点(供后续段直接引用)

- 基底:`HEAD=3b02787`,index 空,未 commit;12 个合流冲突全部按「由真源/实测重建」处置,
  只有 `MAINTAINING.md` 一段散文按合并后测试实现手写为终态(精确相等 + 同事务滚动)。
- 知识层并集成立:main 侧 43 份 research dossier 与 I1 侧两条全部在册,`dossiers_total=271`。
- **超出任务书预期的收敛**:桶③早批文档系统 7 行红**全部消失**——`docctl doctor` rc=0、
  `docctl gate --profile changed` rc=0 全 lane PASS(本会话已独立复跑确认)。根因是基底更新把
  main 侧刷新过的文档系统投影带入,叠加本段的全量投影重建,早批 stale 条件不再成立;
  没有修改门、测试、authority floor 或 sealed 记录。后续段的 KNOWN_RED 预期应据此收窄。
- proof gate 仍 rc=1、**恰好 29 条 issue**,与合流前同数同形,未新增。逐条分解(本会话实跑):

  | 组 | 条数 | 去向 |
  |---|---:|---|
  | strong-status composite(heuristic_feasible_finder allowlist) | 1 | authority 面,保持红 |
  | required-test anchor | 7 | S2 补完后应消失 |
  | close-kernel sink hash drift(checker / master_model / theorem / pr2_l0) | 4 | S3 reseal 后应消失 |
  | v99 floor(8 个文件,`changed without checker-floor reseal` + `drifted from the v99 sealed floor`) | 15 | S3 现场辨明归属 |
  | certified artifact runtime anchor semantic projection sha | 1 | S3 现场辨明归属 |
  | PortBindingModel 双 operation map | 1 | 桶②第 9 行,范围 A 未点名,保持红 |

- 两条 sealed-authority 红测保持红:2 tests / 2 failures,唯一差异仍是旧 floor `34e198fc…`
  对当前 `benders_loop.py` `461fc687…`。
- 承重集(自验收据口径)从 ROUND4C 的 62 个文件收为 **61**:
  `devtools/tests/test_document_maintenance_audit.py` 合流后与 main 一致(两边都把回归时钟滚到
  2026-08-20),不再是改动。S1 后基线 bearing digest `7b28ba8c615dcf179a57454029ad60f30d9709a97878a7761e831ad2dd314e01`。
- 独立备份(stash 已在 S1 验收后删除,这是当前唯一回滚点):
  `/tmp/claude-1000/-home-zhuran24-zmd-pj/f6f386e3-1fb1-441b-ae38-2c85b2baf49e/scratchpad/aclose_after_s1/`
  (`tracked.patch` + `untracked.tar.gz` + `META.txt`)。

## 封印面异源核验结论(2026-08-21,sol 查 + opus 复核)

### 三层互相独立的字节封印权威(实证)

同一个文件在三层里可以是三个不同的值。以 `src/search/benders_loop.py` 为例:

| 层 | 载体 | 当前值 |
|---|---|---|
| ① manifest sink hash | `p1_2_proof_obligations.json::close_kernel_contract.sink_files` (73 项) | `461fc6…`(＝当前字节) |
| ② checker v99 floor | `check_p1_2_proof_obligations.py` 内硬编码(133 路径,与①重叠 72) | `ad833b…` |
| ③ parity test floor | `test_rule_cut_evolution_authority_parity.py` 内硬编码(3 sink + 6 protected surface) | `34e198…` |

`scripts/check_p1_2_proof_obligations.py` 自己是①的 sink,但**不在**②的 v99 hash floor 里。

### 自指固定点已破除(实证,判词 HOLDS_WITH_CAVEAT)

`_proof_obligation_manifest_semantic_projection()` 构造投影时对每个 sink 执行
`if key != "source_sha256"`,因此改①**不改变**语义投影 —— 不存在
「改 checker → 改 checker 的 sink hash → 投影又变」的自指边。纯内存实验:改 1 项 / 3 项 / 全部 73 项
source_sha256,投影 SHA 恒为 `066b828a…`;对照实验改 `summary`、`source_digest_contract`、
`certified_cut_replay_contract.policy`、`close_kernel_contract.policy` 均使 SHA 变化,排除了
「投影函数整体失灵」的反例。manifest 全树扫描确认 73 个 sink hash 值只出现在那 73 个被剔除的位置,
没有第二份冗余清单把它们带回投影。

**caveat(重要)**:只改①**不足以**让 proof gate 转绿——把 73 项全部更新到当前字节后,
close-kernel 门仍报 **15 条 v99 floor 错误**,因为②是独立的一层。真 reseal 必须同时触及②。

### 两条 sealed-authority 红测的机制(判词 HOLDS,sol/opus 双席一致)

- `test_p1_2_manifest_and_registered_sink_bytes_remain_at_sealed_hashes`:名字有误导性。它**不是**
  73 项 manifest→当前字节的一般自洽检查。它先用测试内硬编码的 `_P1_2_SINK_SHA256`(**只有 3 项**)
  把 manifest 过滤到 3 条,再要求 manifest 值(:389)**和当前文件字节**(:391)都等于那个硬编码旧值。
  一般自洽层在 checker 的另一处(`if source_sha256 != current_sha256`)。
- `test_protected_surfaces_match_398f872_except_authorized_preflight_successor`:只对 6 个当前文件
  算 SHA 与测试内硬编码字典比较,**不读 manifest、不读 git**。
- 因此:**任何只改 manifest 的编辑都不可能让它们变绿**。opus 复核席用 shadow 树实跑闭合了整个编辑空间——
  即使把 manifest 的 benders 值恶意强制改成 `34e198fc…`(唯一能让 :389 过的编辑),测试改在 :391 失败
  (活字节 `461fc687…`)。红绿只由 `benders_loop.py` 的活字节决定。
- 复核席还堵了一条「假红」路径:该仓 conftest 有三套会静默改变结果的机制(`_FIXTURE_GUARDS` 子串匹配、
  `_TRACK_B_NODEID_GUARDS` nodeid 匹配、`_SLOW_TEST_NODEIDS` 标记);逐一核对,这两条 nodeid
  **零命中**,是真正执行后 FAILED,不是 skip。
- 作用域事实:主仓 `/home/zhuran24/zmd-pj` 里 `benders_loop.py` 恰为 `34e198fc…`(＝③的 floor),
  manifest 只有 67 个 sink,同样两个 nodeid 在主仓是**绿的**。红只属于本 worktree 的改动面。

### reseal 授权依据(明文)

`docs/AGENT_OPERATIONS.md` §7「Frozen artifacts 与 freeze ritual」给出规程:看到 hash mismatch 时
不要「顺手更新 expected」,先判断四件事——文件是否意外变化、**变更是否得到 owner/规范授权**、
哪些依赖该字节、是否需要完整 reseal;然后按六步执行(查 tracked 依赖 → 区分活 pin/机器义务/文档展示/
历史证据 → 只更新当前真源及其明确派生物 → 跑目标契约测试与完整 preflight → 长测试期间保持
认证链 tracked bytes 不变 → 提交后重算 hash)。

`PROJECT_LOCK.md` 的 close-kernel 威胁模型把 reseal 明确当作**被承认的仪式**:字节 sha floor
「常开拦死」的是手滑与外部篡改,而一批延期硬化项「只对**忠实 reseal 后**的蓄意内鬼有意义」。
即 reseal 本身不是禁区,判据是授权。

本批的授权链:I1 重写经五轮外部异源审计,第五轮终判 `CLEAN_FOR_REOPEN`;owner 于 2026-08-20
裁定范围 A 并要求「draft reseal 转真 reseal」。故①②及语义投影 floor 属授权内;③(parity test 的
硬编码 floor)与 review gate close 记录(manifest `review_anchor` / `status`)归 owner re-close 批,
保持红即是给 owner 看「本批确实改了受保护面」的证据。

## S2a 终态(五条守卫 mutation 测试)

写入位置 `src/tests/test_p1_2_independent_infeasibility_reverifier.py:1436-1669`,整文件 60 passed。
测试文件 SHA `d428ad7b…` → `d245892f…`;checker 字节**未变**(`e38beffa…` 前后一致)。

| 测试(:行) | 注入入口 | mutation | 断言诊断 |
|---|---|---|---|
| `test_round3_checker_enumerates_non_controller_binding_constructors` (:1436) | `heuristic_finder_path` | 副本末尾追加顶层 `PortBindingModel()`,全文件枚举变 2 而 `_verify_binding` 内仍 1 | `heuristic feasible finder must contain exactly one enumerated PortBindingModel constructor; found 2` |
| `test_round3_checker_requires_runtime_relaxation_validation` (:1468) 段一 | `package_path` | certificate 里 `"runtime_relaxations"` 错拼 | `... must validate theorem runtime_relaxations` |
| 同上 段二 | `package_path` | 删掉 `tuple(normalized_runtime_relaxations) != tuple(model.runtime_relaxations)` 比较块 | `... must compare runtime_relaxations to the reconstructed semantic model` |
| `test_round3_checker_rejects_constant_runtime_observation` (:1547) | `benders_loop_path` | 四个 contract 字段各自错接到**另一个**非恒定运行时变量 | `binding capability contract field is not wired to its runtime observation: <field>-><name>` |
| `test_round3_checker_rejects_generic_input_plan_bypass` (:1578) | `binding_subproblem_path` | `_generic_input_slot_capacity_map()` → `_generic_output_slot_capacity_map()` | `production generic-input provider admission must be plan-derived`,断言计数**恰为 2** |
| `test_round3_checker_requires_evaluator_non_authority_exemption` (:1608) 段一 | 真源 + monkeypatch exemption 表 | 篡改豁免分类元组/理由 | `P2 #14 evaluator PortBindingModel constructor must retain its explicit exploratory/evaluation non-authority exemption and reason` |
| 同上 段二 | `p2_14_evaluator_path` | 副本追加 `reverify_whole_layout_infeasibility()` / `_add_exact_persisted_nogood()` | `P2 #14 evaluator exemption is invalid if the script enters a proof-bearing cut or independent reverify funnel` |

**非恒真对照**:每条都先用未 mutation 的真源调用同一 checker 并断言诊断不存在
(:1443-1448 / :1478-1482 / :1558-1561 / :1582-1587 / :1620-1624)。

**删守卫反证**(离线,不改 worktree 字节):把 checker 复制到临时目录、逐个删掉守卫代码
(:14823-14827 / :14848-14851 / :14852-14856 / :14267-14274 / :14499-14500 与 :14680-14681 /
:14771-14775 / :14782-14798),再直接调用新增测试函数——**每一条删除都精确打红对应的新断言**
(:1460 / :1496 / :1515 / :1575×4 / :1605 / :1645 / :1669),无一例外。这直接闭合了
HANDOFF 桶②第 8 行「守卫本身没有守卫」的缺口。

**一处取证修正(如实记录)**:原判据设想 `generic-input provider admission must be plan-derived`
在 checker 的两处(:14500 与 :14681)中「有一处零覆盖」。实查不成立——两处条件完全相同、
在同一次调用中无条件执行,现有两个测试(:1176、:1399)都注入 `binding_subproblem_path`,
因此**同时命中两处**,不存在可分离的零覆盖处。按 fallback 改为覆盖此前未触及的 mutation 面
(input/output capacity map 交叉错接),并以「诊断计数严格等于 2」直接证明两处重复守卫均被命中。
未放宽断言,未改 checker。

**S2b 待办**:第五个测试名 `test_round3_checker_requires_evaluator_non_authority_exemption`
不在 checker 硬编码要求集里,但应一并写入 manifest 的 `required_tests`,使这条守卫也进强制层。

## S2a 异源核验(opus 推翻,判词 HOLDS_WITH_CAVEAT)

核验席自建 symlink 镜像独立复算,未复用执行席任何证据。落地在
`<scratchpad>/s2a_crosscheck_notes.md`(351 行 R1–R14)与 `<scratchpad>/s2a_coverage_table.txt`。

**推翻失败**:5 个测试无一假绿、无一恒真。9 次删守卫实验,每次删除**恰好**打红对应测试且**只**打红它;
两个对照组(删无关的 `shell=True` 守卫、删「must not be a constant」守卫)保持全绿。
输入侧 7 种无害 mutation 目标诊断 0 命中。

### 核验带回的四点(逐条处置)

**Q1 — 第五个测试没进强制层。** `test_round3_checker_requires_evaluator_non_authority_exemption`
既不在 manifest 也不在 checker 要求集,删掉它不会让任何门变红,「守卫的守卫」在它身上复发一层。
→ **S2b 处置**:写进 manifest `required_tests`(checker 会校验列出的符号必须存在)。

**Q2 — 非恒真对照建立在已红基线上。** `_check_independent_infeasibility_reverifier_contract`
对真仓返回 1 条错误(PortBindingModel 双 operation map,源于未提交的 `binding_subproblem.py`)。
断言只查特定串,仍然有效,但不能读成「基线干净」。→ 如实记录,不影响结论。

**Q3 — 另有两组重复守卫可单删而静默**:generic-output(:14507/:14688)与
must-not-be-constant(:14263/:14666)。全套 60 个测试里**只有** T4 用了严格计数断言,
这两组单删任一份都是静默回归。→ **范围 A 未点名,本批不修**,登记进 HANDOFF 桶②交后批与 owner。

**Q4 — 这批守卫是可达性感知、数据流盲的 token 锁(最重要)。** 核验席构造 5 个绕过,
**全部既击穿被守性质、又让守卫沉默、又让 5 个新测试保持全绿**:死分支常量化、
保留直接调用但丢弃返回值、用别名 `_M = PortBindingModel` 二次构造、`import as` + `getattr`
进 proof funnel、把比对改成 `if False and ...`。
→ 判定:**不触发汇报白名单**。理由:这不是新的 soundness 破口,而是 close kernel 的**设计边界**——
`PROJECT_LOCK.md` 明写它「is a small structural close kernel, not a theorem prover」,
其威胁模型也早已区分「手滑/无心之失与外部篡改由字节 sha floor 常开拦死」与
「只对忠实 reseal 后的蓄意内鬼有意义」的延期硬化项。这 5 个绕过全属后者。
但**必须写进 HANDOFF**:把「这 5 条绿了」读成「这些性质被守住了」是过度解读,
owner 与第六轮外审须知情。

### 覆盖 census(串行,独立 basetemp,控制组 60 passed)

`_check_independent_infeasibility_reverifier_contract` 共 **69 处 `errors.append`**:

| 判定 | 数量 |
|---:|---|
| 本轮 5 个新测试**独家**守住 | 8 |
| 既有测试守住 | 9 |
| 只有两份一起删才红(单删静默) | 4 |
| **完全零覆盖** | **48** |

48 处零覆盖是范围 A 之外的既有面,登记进 HANDOFF 供后批取用。

### 一个附带的运维发现(对本批收据有直接影响)

此前并行 census 归属错乱,根因**不是**新测试:`pytest.ini:2` 把全仓所有 pytest 进程钉在
`<repo>/.pytest_tmp` 一个固定目录,并发进程互删(`FileExistsError` 加下游 artifact_hashes 不符);
`docs/AGENT_OPERATIONS.md:83` 早已记载这条坑。加独立 `--basetemp` 后 5 路并发全部 60 passed。
在案 flaky 的 7 个测试全是**既有的** capsule 类测试,5 个新测试一次都没因并发假红过
(它们是纯 AST/文本层调用,不 spawn 子进程)。
→ S4 收据生成器已为每个 pytest 门指定独立 `--basetemp`,已规避。

核验期间 checker 与测试文件 SHA 全程未变(`e38beffa…` / `d245892f…`),mutation 只落在镜像里。

## 任务书修订(指挥线,2026-08-21)

第 1 项「基底更新到 main=3b02787」改为「更新到最新 main」。现最新为 **`aa517cd`**
(「docs(故事书): 续写第十至十三章并定名,单列治理契约;登记 errata dossier」),
要求一次并到位,不做两遍。

`3b02787..aa517cd` 实测改动 13 个文件,与 reseal 的四个位点
(`check_p1_2_proof_obligations.py`、`p1_2_proof_obligations.json`、
`certified_artifact_contract.py`、`test_p1_2_independent_infeasibility_reverifier.py`)
**完全不相交**,故基底再合流与 reseal 面分析可并行。13 个中:

- 11 个是 S1 已处理过的同类合流点(`dossiers.json`、`knowledge_census.json`、
  八张知识投影、`MAINTENANCE_QUEUE.md`)——worktree 也动过,会冲突,解法同 S1;
- 2 个是新增且 worktree 未动过:`docs/项目说明/22_project_journey_plain_language.md`(+202)、
  `docs/项目说明/DOC_POLICY.json`(+32)——直接取 upstream 版本。

## WF resume 缓存语义(指挥线定谳,影响本批的补发策略)

缓存是**滚动哈希链 + 单向 miss latch**:任一席位死亡后,该 runId 从死点起**永久**失去续跑缓存。
推论:`resumeFromRunId` 在有席位死过的 run 上基本无用;**链内当场补发的缓存代价为零**,
所以补发环应做在 workflow 脚本层(`agent()` 落 null 即在同一 run 内补发),而不是事后 resume。
CC 自带的 resume 提示文案(「unchanged 即命中」)与真实语义不符,勿信。
全文见 `~/.claude/ops/zmd-pj/WF_RESUME_CACHE_SEMANTICS.md`。

本批已按此执行:reseal 审查 workflow 的脚本层带 `agentRetry` 包装(落 null 即补发,
补发席先读约定的残稿文件再续做);直派 Agent 的断点用 SendMessage 续命。

## reseal 面终态(异源审查 + shadow 实测,2026-08-21)

产物:`<scratchpad>/reseal_final.py`(646 行,守卫密集)。shadow 实测 rc=0,
**proof gate 29 → 1**,两条 parity 测试仍 **2 failed**,第二次运行**完全幂等**(files changed 0)。

### 封印共五层,原残稿只覆盖三层

| 层 | 载体 | 本批处置 |
|---|---|---|
| ① manifest sink hash(73) | `p1_2_proof_obligations.json::close_kernel_contract.sink_files` | reseal(步骤 E) |
| ② checker v99 floor(133 路径) | `check_p1_2_proof_obligations.py::CLOSE_KERNEL_V99_REQUIRED_SOURCE_SHA256_BY_PATH` | reseal(步骤 D,实测 9 项漂移) |
| ③ parity test floor | `test_rule_cut_evolution_authority_parity.py` 内硬编码 | **不动**,归 owner re-close |
| ④ strong-status 写点清单 | `data/proof_obligations/strong_status_write_allowlist.json` + checker `:63-66` 的双 pin(SHA + size) | reseal(步骤 F) |
| ⑤ Stage-B 语义封印 | `test_stage_b_contracts.py::_COORDINATE_DELEGATE_ALIAS_USE_DIGEST` | **不做**,只报告(见下) |

### 步骤序 A → B → C → D → F → E → V(顺序是承重的)

- A:manifest `obligations[13].required_tests` 并入 7 条 anchor(48→55)→ 重算语义投影 P
- B:`certified_artifact_contract.py::LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256` ← P
- C:checker `P1_2_PROOF_OBLIGATION_SEMANTIC_PROJECTION_SHA256` ← P
- D:checker v99 floor 133 路径 ← 当前字节
- **F:strong-status allowlist 最小重建 + checker 双 pin** ← 它改 checker 字节,故必须早于 E
- E:manifest 73 sink ← 最终字节(必须最后,才能封住 B/C/D/F 的终态)
- V:终态全量复验

`certified_artifact_contract.py` **同属①与②**,所以 B 必须早于 D 与 E。

### strong-status 属本批范围的明文依据(Simulate 席独立复核)

`PROJECT_LOCK.md:237-239` 把「强状态 allowlist」列进 close-kernel 必过面,并明写
「修改受保护文本/docstring 导致 hash 漂移时必须**按同一工作树重新封存**」。故④覆盖,
proof gate 收到 1 条而非 2 条。

### 脚本相对残稿补的五条守卫(都是残稿真正缺的)

1. **不许铸造新授权**(最重要):重建 allowlist 时,每个 AST finding 的语义元组
   `(pattern, module, qualname, keys, callee)` **必须已在该模块 allowlist 中存在**,否则硬失败。
   否则「按 AST 重建」等于把新出现的强状态写点自动登记成已授权。注入实测已触发拒绝。
2. **JSON 序列化保真守卫**:写任何 JSON 授权文件前,先证明 canonical dump 能**逐字节还原原文件**,
   否则拒绝——一次整文件重排会让覆盖它的所有 hash 漂移,原因与 reseal 无关且污染 diff 可审性。
3. **全树写集守卫**:前后各拍全树 sha,要求「新增 0 / 删除 0 / 变更 ⊆ {manifest, checker,
   certified_artifact_contract, allowlist}」。rc=0 因此携带一个「没碰别的东西」的正面陈述。
4. **终态全量复验**:133 floor + 73 sink + strong-status 三类检查 + checker 双 pin 对磁盘
   + 三处 P 一致,全部硬断言;不止验固定点。
5. **allowlist 最小重建而非整体再生**:只重建被判失败的模块(本树只有 `heuristic_feasible_finder.py`),
   其余条目逐字节不动,原 id 与 justification 原样存活;83→79 条,diff 只有 +13/-53 一块。

### 三条执行警告(S3 必须遵守)

- **不许搬运任何中间 hash**。残稿 `fourth_layer.md` 报的 allowlist 是 `b764cca8…`(整体再生),
  最小重建是 `0ca803f1…`(大小同为 49756)——大小相同、字节不同。checker 的 pin 必须按**最终字节**重算。
  同理 shadow 打印的 9 个 v99 值、5 个 sink 值、checker SHA 都只是中间值。
- **必须与并发写入对齐窗口**。Simulate 席在实测窗口内检测到并发会话改了 worktree 14 个文档/知识层文件
  (即 S1c,与封印面零交集)。真 worktree 上跑 reseal 时若 sink/floor 在 D 与 E 之间被第三方改动,
  会造成错封;脚本的全树写集守卫会把这种情况变成**硬失败**而非静默错封。故 **S3 必须在 S1c 完成后、
  且确认无并发写入时执行**。
- **⑤只报告不修改,但必须让 owner 看见**,否则「proof gate 绿」会被误读成「全树已封」。

### S2b 的一个遗留(reseal_final.py 不会自动覆盖)

步骤 A 只并入 `test_anchors` 的 7 条。第五个新测试
`test_round3_checker_requires_evaluator_non_authority_exemption` **不在** `test_anchors` 里,
需在 S3 单独写入 `required_tests`(见异源核验 Q1)。写入后语义投影 P 会与 shadow 实测值不同,
必须重算——这也是「不许搬运中间值」的一个实例。

### 关于第五层归属的订正

HANDOFF 桶②第 21 行把 Stage-B alias digest 记为「后批判断…不属于 I1 G3」。
实查:该常量相对 HEAD **已被本批更新过一次**(`74297d2e…` → `ba1baf51…`),说明本批本就打算 reseal,
只是最终字节集合继续变化后没有再次收口,现值应为 `c0e07e47…`。故它是**本批自己的遗留**,
不是外来项。S5 更新 HANDOFF 时须订正这一行的归属与事实。

## S3 真 reseal 终态验收(协调线独立复跑,2026-08-21)

`reseal_final.py` 在真 worktree 上执行完成。**协调线自行复跑验收,不采信执行席自述**:

| 验收项 | 结果 |
|---|---|
| P1.2 proof gate | rc=1,**恰 1 条**:`PortBindingModel must expose exactly one consumed utility operation map`。**无任何 semantic projection 残留诊断** |
| 两条 sealed-authority parity | **2 failed / 4 passed**,硬边界守住 |
| strong-status allowlist checker | rc=0:65 个已登记 AST 节点 / 79 条 allowlist(与预测的最小重建 83→79 一致) |
| `test_anchors` / `required_tests` | 8 / **56**(48+8),第五个测试已进强制层 |
| 幂等性 | 二次运行 `files changed: 0`,rc=0 |
| index / commit | index 空,未 commit,HEAD 仍 `aa517cd` |

脚本 V 阶段的硬断言(二次运行原样输出):

```text
V  projection fixpoint holds: cc5ed8abbef16c95e4c7e4b758e9478ba7b414bc8cad30a327dde72283f02e94
V  manifest field, checker floor and runtime anchor all equal P
V  all 133 v99 floor entries match current bytes
V  all 73 manifest sinks match current bytes
V  strong-status allowlist check passes and its checker pins match
V  manifest status / review_anchor / gate_id / sink inventory / obligation ids unchanged
V  files changed: 0
V  forbidden surfaces byte-identical: data/review_gates/phase_1_2_spike_close.json,
   src/tests/cuts/test_rule_cut_evolution_authority_parity.py
V  OUT-OF-SCOPE DRIFT: _COORDINATE_DELEGATE_ALIAS_USE_DIGEST
   pinned=ba1baf51… actual=c0e07e47… (test-side semantic seal; not a proof-gate issue, not resealed here)
```

### 终态 SHA(reseal 后)

| 文件 | SHA256(前 16) |
|---|---|
| `scripts/check_p1_2_proof_obligations.py` | `d1f05c70fc90b78f` |
| `data/proof_obligations/p1_2_proof_obligations.json` | `0b828c5bf1e2cee2` |
| `src/search/certified_artifact_contract.py` | `3bc22369557d2547` |
| `data/proof_obligations/strong_status_write_allowlist.json` | `0ca803f1b2a512eb` |
| 语义投影 P | `cc5ed8abbef16c95e4c7e4b758e9478ba7b414bc8cad30a327dde72283f02e94` |

未被改动(经确认):`src/tests/test_p1_2_independent_infeasibility_reverifier.py`(`d245892f…`,S2a 交付值)、
`src/tests/cuts/test_rule_cut_evolution_authority_parity.py`(git clean)、`data/review_gates/`(git clean)、
`src/tests/cuts/test_stage_b_contracts.py::_COORDINATE_DELEGATE_ALIAS_USE_DIGEST`(仍 `ba1baf51…`)。

工作区规模:42 tracked modified + 7 untracked 顶层路径(较 S1c 的 41 增一,即 allowlist 首次进入改动集)。

### 「不许搬中间值」的实证

shadow 阶段在旧基底 `3b02787` 上算得投影 `fdc6a39a…`;真树终值是 `cc5ed8ab…`——
因为多了第五个测试且基底已推到 `aa517cd`。而 allowlist 终值 `0ca803f1…` 与 shadow 一致
(aa517cd 只动文档/知识层,不影响 `heuristic_feasible_finder.py`)。**两者对照恰好说明:
哪些中间值会变、哪些不会变,事前无法可靠预判,所以只能按最终字节现算。**

### 执行席的一次正确停机

追加第五个 `test_anchor` 后 proof gate 由 29 升至 30,新增
`proof-obligation manifest semantic projection drifted from the reviewed P1.2 floor`。
执行席按硬边界停机待裁,未自行绕过。协调线裁定为**预期中间态**并授权继续,判据:
语义投影字段清单含 `obligations`,而 `test_anchors` 是其子字段,故追加必然使实算投影漂移;
交叉验证是同函数另一条诊断(比对 manifest `semantic_projection_sha256` **字段**与 checker floor)
**未**报出——即「实算值漂了、声明值没漂」,正是「改了内容但尚未重签」的精确特征。
步骤 A/C 重签后两条断言同时满足,终态已验证该诊断消失。

## S3b reopen 显式登记终态(协调线复验)

照 2026-08-05 先例的**职责分离**执行:

```text
mutation_policy / hash 漂移  →  证明重开已机械发生
知识台账 / dossier review     →  显式登记「发生了什么、因何发生、外审到哪、还缺什么」
owner decision record         →  唯一能执行 re-close
```

先例考据的关键结构事实:08-05 那次重开**没有** `DECISION-P1-2-REOPEN` 记录——
reopen 是 mutation policy 的机械后果,不是 owner 决定。本批照搬。

三处登记(协调线独立复验):

| 载体 | 终态 |
|---|---|
| `docs/项目说明/HISTORY.md:57` | 新节「2026-08-20:I1 异源化触发 P1.2 close claim 机械重开」,照 08-05 八槽结构 |
| `data/knowledge/dossiers.json` | `DOSSIER-COMMON-MODE-BINDING-REVERIFY-…` summary 更新到终态;`lifecycle=active`、`relevance=current_evidence`、`workflow.closure=null` 全部保持 |
| `data/knowledge/backfill_reviews.jsonl` | 新增 `REVIEW-…-ROUND5-REOPEN`(`status=current`、`outcome=deferred`、`supersedes` 指向旧条);旧条转 `superseded`,语义未被改写 |

四门验收(复跑):`check_knowledge_docs` rc=0 / `check_repository_code_assets check-current` rc=0 /
`docctl doctor` rc=0 / `docctl gate --profile changed` rc=0 全 PASS。

边界(复验):`data/knowledge/decisions.jsonl` **0 处改动**、`data/review_gates/` **0 处改动**、
manifest `0b828c5b…` 与 checker `d1f05c70…` 与 reseal 终态逐字节一致、index 空、HEAD `aa517cd`。

### 一处**未做**并交 owner 的缺口(不静默丢弃)

owner 的「范围 A」决定虽已发生(2026-08-20),但仓内**没有合格的 tracked authority source**:
`docs/research/common_mode_binding_reverify_20260820/OWNER_INSTRUCTION_20260820.md:9`
自称「不是 owner authority source」,而 `data/knowledge/schemas/decision.schema.json` 要求
`authority_source` 指向 tracked 文件。先例考据席建议先形成一份 tracked、窄范围、逐字的
owner ruling companion 再登记 decision——**但由执行侧去造这份 companion 等于替 owner 铸权**,
故本批不做,登记进 HANDOFF 交 owner 裁断:是否补一份 companion、或授权逐字抄录仓外会话原话
(owner 原始回答位于 `~/.claude/projects/-home-zhuran24-zmd-pj/3aff26c7-….jsonl:10590`,
内容为「A:守卫+锚点全补」)。

### 另一条交后批的发现(S1c 实测)

`devtools/build_knowledge_docs.py --refresh-dossiers` 会把 `dossiers.json::ledger_reviewed_at`
从三方一致的 `2026-08-20` **回退**到 `data/knowledge/current_state.json` 的旧值 `2026-08-18`,
并改写两个与本任务无关的 band22 dossier 的入口/标题/摘要,稳定造成文档回归 1 failed 与
changed gate rc=1。本批与 S1c 均改用不带 refresh 的八条生成命令规避。
待裁断:`current_state.json::ledger_reviewed_at` 与当前维护时钟的权威关系;
`refresh_dossiers()` 是否可以覆盖三侧已一致的新 review clock;
historical dossier 自动入口选择是否允许因目录扫描顺序漂移。

## 执行流水

- 2026-08-20:勘察完成,建立本台账。

- 2026-08-21:S1 基底更新与合流完成。
  - 路线:`HEAD=3b02787` 保持不动；从已执行 `stash pop` 留下的 12 个 `UU` 中续跑。11 个生成/实测产物先用 stage-2 (`Updated upstream`) 内容恢复可解析状态，随后全部由机器真源或真实测量覆盖；唯一手写冲突 `docs/governance/document-system/MAINTAINING.md` 按合并后测试实现改写。解冲突后用不改工作区的 `git reset` 清空 index；未使用 `git checkout` / `git restore`，未 commit。
  - 12 个冲突逐项处置:

    | 路径 | 终态处置 |
    |---|---|
    | `.docsystem/manifest.json` | stage-2 仅作 JSON 引导；随后按 manifest 自身的串行 pytest 命令重新实测 `test_timing_receipt`:2026-08-21、89 tests、最大 call `3.29s`、无 `>=8s` 节点、`raw_output_sha256=851ba3ad2dd5a3c8e2febd7c644acc3ba24f3583991fdb570ccaf0070c670462`，并重算三个 measured-input SHA-256。 |
    | `data/knowledge/knowledge_census.json` | 使用 `devtools/build_knowledge_docs.py::_computed_knowledge_census` 从合并真源重算唯一数字 fixture；终态 `dossiers_total=271`、`semantic_review_dossiers=42`，其余计数一并由同一函数给出。 |
    | `docs/BACKFILL_LEDGER.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/CATALOG.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/CURRENT.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/MAINTENANCE_QUEUE.md` | `devtools/docctl.py render-maintenance --write` 重建。 |
    | `docs/OPEN_QUESTIONS.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/REASONING_LEDGER.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/TERMINOLOGY.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/TOPIC_INDEX.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/VALIDITY_LEDGER.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/governance/document-system/MAINTAINING.md` | 手写为精确等式:`回归时钟 = dossiers.json::ledger_reviewed_at = 全部 active dossier 最新 opened_at/date`；新增 active dossier 时同事务滚动前两者，保留测试视界不授予 authority、不得改 `snapshot_as_of`、不得倒签等边界。 |

  - `MAINTAINING.md` 判断依据:合并后的 `src/tests/test_document_system.py:415-439` 先断言回归时钟精确等于 `ledger_reviewed_at`，再断言精确等于 active dossier 最新日期，失败信息具名显示两日期；`devtools/tests/test_document_maintenance_audit.py:20-21` 固定唯一默认回归日期，`:89-107` 以具名 active dossier 验证较早快照必须报陈旧，`:77-86` 验证维护队列只能是确定性、非授权投影。`devtools/tests/test_repository_code_assets.py:387-405` 另证明 artifact workspace roots 从 dossier registry 精确导出，`:779-788` 的自动合并变化只把当前源码发现数更新为 813，不对审计时钟建立更弱的下界；三处实现之间无矛盾。
  - 合并完整性:以 `3b02787^..3b02787` 的 `dossiers.json` ID 差集核得 upstream 集中登记恰为 43 条，43 条全部仍在当前 ledger；`DOSSIER-I1-ROUND4-SELF-CHECK-20260820-0CFC3F056C` 与 `DOSSIER-COMMON-MODE-BINDING-REVERIFY-20260820-0268E9394D` 也均存在。合并后 ledger 总数 271，`ledger_reviewed_at=2026-08-20`。
  - 实际重建与实测命令:

    ```bash
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/build_knowledge_docs.py --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-legacy --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-guidance --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-entrypoints --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-sections --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-convergence --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-maintenance --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/artifact_evidence.py render --write
    /home/zhuran24/zmd-pj/.venv/bin/python -m pytest -p no:randomly -p no:cacheprovider -q --basetemp=/tmp/claude-1000/-home-zhuran24-zmd-pj/f6f386e3-1fb1-441b-ae38-2c85b2baf49e/scratchpad/timing_receipt_20260821/pytest src/tests/test_document_system.py src/tests/test_knowledge_docs.py --durations=0 --durations-min=0
    ```

  - 回归结果:

    | 命令 | rc | 关键结果 |
    |---|---:|---|
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/check_knowledge_docs.py` | 0 | knowledge spine 与全部知识投影 fresh。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/check_repository_code_assets.py check-current` | 0 | `status=PASS`, current code-assets 2091。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python -m pytest -p no:randomly --basetemp=.../pytest_docs -q devtools/tests/test_document_maintenance_audit.py devtools/tests/test_repository_code_assets.py src/tests/test_document_system.py` | 0 | 114 passed,2 skipped。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py doctor` | 0 | document system self-consistent，投影 fresh。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py gate --profile changed` | 0 | 全 lane PASS。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python scripts/check_p1_2_proof_obligations.py` | 1 | 预期 29 issues，形状与合流前一致。 |
    | 两个 sealed-authority nodeid 的定点 pytest | 1 | 预期 2 failed；唯一 authority-floor 差异仍为 `34e198fc...` 对当前 `benders_loop.py` `461fc687...`。 |

  - 红点前后对照:sealed-authority `2 failed -> 2 failed`，P1.2 draft proof gate `29 issues -> 29 issues`，没有新增 soundness 红。早批记录中的 doctor maintenance-stale 与 changed gate 四个衍生 BLOCK，在本任务要求的真源重建后分别变为 rc=0 与全 lane PASS；清除原因仅是重新生成 stale 投影及其级联回归，未修改门、测试、authority floor、proof gate 或 sealed 记录。

- 2026-08-21:S1c 第二次基底更新与合流完成。
  - 路线:从 detached `HEAD=3b02787`、index 空、41 项 tracked 改动与 7 项 untracked 顶层路径开始；先在 worktree 外建立完整回滚包，再执行 `git stash push -u`、`git checkout aa517cd`、`git stash pop`。pop 后 `dossiers.json` 自动无冲突并集合并，另有 10 个生成文件进入 `UU`；这些文件以 stage-2 内容作为可解析占位，随后用不改工作区的 plain `git reset` 清空 unmerged/index 状态，再由合并真源重建。未 commit，未修改门、测试或 sealed authority floor。
  - 13 个上游变更逐项处置:

    | 路径 | 终态处置 |
    |---|---|
    | `data/knowledge/dossiers.json` | Git 自动无冲突合并后，按 ID 集合核验当前 272 条恰等于 upstream∪stash：保留 worktree 的 `DOSSIER-I1-ROUND4-SELF-CHECK-20260820-0CFC3F056C`、`DOSSIER-COMMON-MODE-BINDING-REVERIFY-20260820-0268E9394D`，并纳入 upstream 新增 `DOSSIER-P-MUS-LANDSCAPE-ERRATA-20260820-4FB752F398`；无缺失、无额外条目。 |
    | `data/knowledge/knowledge_census.json` | stage-2 仅作可解析占位；调用合并后 `devtools/build_knowledge_docs.py::_computed_knowledge_census` 从真源重算唯一数字 fixture。终态关键计数:`dossiers_total=272`、`semantic_review_dossiers=42`、`current_evidence_dossiers=17`、`backfill_reviews_total=55`、`current_reviews=45`。 |
    | `docs/BACKFILL_LEDGER.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/CATALOG.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/CURRENT.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/MAINTENANCE_QUEUE.md` | `devtools/docctl.py render-maintenance --write` 重建。 |
    | `docs/OPEN_QUESTIONS.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/REASONING_LEDGER.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/TERMINOLOGY.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/TOPIC_INDEX.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/VALIDITY_LEDGER.md` | `devtools/build_knowledge_docs.py --write` 重建。 |
    | `docs/项目说明/22_project_journey_plain_language.md` | worktree 未改过；当前字节与 `aa517cd` blob 的 SHA-256 一致，直接采用 upstream 版本。 |
    | `docs/项目说明/DOC_POLICY.json` | worktree 未改过；当前字节与 `aa517cd` blob 的 SHA-256 一致，直接采用 upstream 版本。 |

  - 实际重建命令:

    ```bash
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/build_knowledge_docs.py --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-legacy --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-guidance --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-entrypoints --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-sections --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-convergence --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py render-maintenance --write
    /home/zhuran24/zmd-pj/.venv/bin/python devtools/artifact_evidence.py render --write
    ```

    第一条生成命令先按维护 fixture 契约以 rc=1 报出五项 census drift；从真源重算 fixture 后，完整八条命令按上述顺序重跑并全部 rc=0。
  - 写入本条执行记录前的合流预验收:

    | 命令 | rc | 关键结果 |
    |---|---:|---|
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/check_knowledge_docs.py` | 0 | knowledge spine 与生成投影 fresh。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/check_repository_code_assets.py check-current` | 0 | `status=PASS`，current code-assets 2091。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python -m pytest -p no:randomly -p no:cacheprovider -q --basetemp=... devtools/tests/test_document_maintenance_audit.py devtools/tests/test_repository_code_assets.py src/tests/test_document_system.py` | 0 | 114 passed，2 skipped。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py doctor` | 0 | document system self-consistent，投影 fresh。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py gate --profile changed` | 0 | 全 lane PASS。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python scripts/check_p1_2_proof_obligations.py` | 1 | 恰 29 issues；整份输出及 issue 列表均与合流前 baseline 逐字节一致。 |
    | authority-parity 测试文件 | 1 | 2 failed，4 passed；失败 nodeid 与合流前一致，唯一差异仍为旧 floor `34e198fc...` 对当前 `benders_loop.py` `461fc687...`。 |

  - 红点前后对照:P1.2 draft proof gate `29 issues -> 29 issues`，sealed-authority `2 failed / 4 passed -> 2 failed / 4 passed`；doctor `0 -> 0`，changed gate `0 -> 0`。本次基底更新未新增红，也未意外消除既有红。


- 2026-08-21:S3 封印重签(reseal)完成。
  - 回滚基线:执行前在 worktree 外建立完整备份 `/tmp/claude-1000/-home-zhuran24-zmd-pj/f6f386e3-1fb1-441b-ae38-2c85b2baf49e/scratchpad/s3_backup_20260821T090936Z/`，包含 tracked binary patch、141 个 untracked 文件归档、7434 个普通文件 SHA-256 清单、32 个符号链接记录及 `SHA256SUMS`；校验逐项通过。
  - 登记与重签:先证明 manifest 可由 `json.dumps(obj, ensure_ascii=False, indent=2) + "\n"` 逐字节还原，再把 `test_round3_checker_requires_evaluator_non_authority_exemption` 追加到 `PO-INDEPENDENT-INFEASIBILITY-REVERIFY.test_anchors`。追加后 `test_anchors=8`；未重签时 proof gate 从 29 条增至 30 条，唯一新增项为实算 semantic projection 漂移，且 manifest 声明值仍等于 checker floor，符合“封印内容已变、声明值尚未重签”的中间态。随后按 `A→B→C→D→F→E→V` 运行 `reseal_final.py`，`required_tests=48→56`，未搬运 shadow 中间 hash。
  - 终态语义投影:`P=cc5ed8abbef16c95e4c7e4b758e9478ba7b414bc8cad30a327dde72283f02e94`；manifest 字段、checker floor 与 `certified_artifact_contract.py` runtime anchor 三处一致。133 个 v99 floor、73 个 manifest sink 及 strong-status allowlist SHA/size pin 均与终态字节一致。
  - 封印面 SHA-256:

    | 文件 | S3 前 | S3 后 |
    |---|---|---|
    | `scripts/check_p1_2_proof_obligations.py` | `e38beffa53172dd7b577f863bd545e003852f559f72ef5eb918a888f872129d3` | `d1f05c70fc90b78f0e4662fb7a0757b320bad63feda9a5924eb8e6de17910c80` |
    | `data/proof_obligations/p1_2_proof_obligations.json` | `a64b856489c7397afbfa220b59ad053ccb9ff036376b0d9b36200533063f5647` | `0b828c5bf1e2cee2aa084977d113f82fd9a2cc561124bc86ffffc7e7e52a4b10` |
    | `src/search/certified_artifact_contract.py` | `0d8c33834d4b3659dcf82dd2c719a46ec8a35f84ca7f59b893028252cff651ce` | `3bc22369557d2547a40f098e1094da8121ba0ec2ee9c531079c250598bb5e591` |
    | `src/tests/test_p1_2_independent_infeasibility_reverifier.py` | `d245892ff52a6b932ff2aab2500d0a4bbfb4bc4516dd43942ec003cc01aba914` | `d245892ff52a6b932ff2aab2500d0a4bbfb4bc4516dd43942ec003cc01aba914` |
    | `data/proof_obligations/strong_status_write_allowlist.json` | `7472bba0be7f4de3dc4881ffe5c300ea81b163d9865c0d296b238f91169947c8` | `0ca803f1b2a512eb8967ac5eed2b9ffbcf0b3435e8102a4a17f0c7fd5f0799b7` |

  - 验收结果:

    | 检查 | rc | 终态结果 |
    |---|---:|---|
    | `scripts/check_p1_2_proof_obligations.py` | 1 | 恰 1 条:`PortBindingModel must expose exactly one consumed utility operation map; found ['_pose_optional_operation_by_template', '_utility_operation_by_template']`；无 semantic projection 诊断。 |
    | `src/tests/cuts/test_rule_cut_evolution_authority_parity.py` | 1 | `2 failed, 4 passed`；失败项仍为两条 sealed-authority parity，均未变绿、skip 或 error。 |
    | `scripts/check_strong_status_write_allowlist.py` | 0 | 65 个 registered AST node、79 条 allowlist entry，检查通过。 |
    | reseal 第二次运行 | 0 | 脚本报告 `files changed: 0`、`RESEAL OK`；普通解释器运行只刷新两个 ignored timestamp-based `.pyc`，源/JSON 字节不变。禁写 bytecode 的隔离复验同为 `files changed: 0`，未过滤全树 SHA 清单逐行一致。 |

  - 写集与边界:S3 内容写集恰为 manifest、checker、runtime contract、strong-status allowlist 四文件，独立增量 diff 为 43 insertions、74 deletions且 `git diff --check` 通过；manifest 的 `status`、`review_anchor`、`gate_id`、`close_kernel_contract.review_anchor`、sink 路径清单及 obligation ID 清单未变。parity floor、`data/review_gates/` close 记录、certificate/theorem/semantics 逻辑及 `test_stage_b_contracts.py` 均保持 S3 前字节；index 为空，未 `git add`、未 commit。
  - 已知越界红点继续保留:`_COORDINATE_DELEGATE_ALIAS_USE_DIGEST` pinned `ba1baf510ac63a0a6fc269d521ca19c7b3c18c64f27237b2cd100cc68068d0a8`，actual `c0e07e47a43311c4facc7e967ea39b86e66851cc2fec5ab157ba6b7fa31498a4`；本段未作语义裁定或重签。

- 2026-08-21:S3b P1.2 close claim 机械重开知识登记完成。
  - 完整备份:动手前已在 `/tmp/claude-1000/-home-zhuran24-zmd-pj/f6f386e3-1fb1-441b-ae38-2c85b2baf49e/scratchpad/s3b_backup/` 保存全 worktree 归档、tracked binary diff、untracked 归档、基线 status 与 7434 个普通文件 SHA-256 清单；整树归档和四个主目标均已校验可恢复。首次 untracked-only 补充归档因 `tar -C` 参数顺序返回 rc=2，随即重建并校验 rc=0；该失败未影响完整整树归档。
  - 显式重开登记:`docs/项目说明/HISTORY.md` 追加 2026-08-20 I1 异源化事件，按日期、批次、触发背景、承重面、验证状态、显式状态转移、owner 待办与证据坐标八槽记录。条目明确 73 个 close-kernel sink 的 sealed source SHA-256 漂移按 `source_sha256_drift_reopens_p1_2_close_claim` 机械重开 P1.2，并明确本事件不等于 re-close。
  - dossier 终态:`DOSSIER-COMMON-MODE-BINDING-REVERIFY-20260820-0268E9394D` 的 summary 已更新为 I1 纯标准库、闭式算术、artifact-bound 独立 binding 复验包、五轮异源审计 `CLEAN_FOR_REOPEN`、owner 范围 A 已执行并完成 reseal、owner re-close 尚未发生；`lifecycle=active`、`relevance=current_evidence`、`workflow.opened_at=2026-08-20`、`workflow.closure=null` 保持不变。
  - successor review:旧 `REVIEW-20260820-COMMON-MODE-BINDING-REVERIFY` 只把状态从 `current` 改为 `superseded`，其余字段与 S3b 备份逐字段一致；新增 current successor `REVIEW-20260820-COMMON-MODE-BINDING-REVERIFY-ROUND5-REOPEN`，`outcome=deferred`、`supersedes` 指向旧 review。新 review 保留 `ACLOSE_SELF_CHECK` 尚未落盘、owner re-close 尚未发生、绿灯/receipt/`CLEAN_FOR_REOPEN` 不替代 owner re-close 三项 unresolved，且不引用需要未落盘收据背书的精确数字。
  - census 伴随更新:新增一条 review 后，`data/knowledge/knowledge_census.json::counts.backfill_reviews_total` 按 `_computed_knowledge_census` 从 55 对账到 56；全量 fixture 与机器实算逐字段一致，其余 census 字段未变。
  - 投影重建:严格未使用 `--refresh-dossiers`。`build_knowledge_docs.py --write`、`docctl.py render-legacy --write`、`render-guidance --write`、`render-entrypoints --write`、`render-sections --write`、`render-convergence --write`、`render-maintenance --write`、`artifact_evidence.py render --write` 八条命令均 rc=0。生成写集为八份知识投影与 `docs/MAINTENANCE_QUEUE.md`；其余渲染目标字节未变。
  - 四门验收:

    | 命令 | rc | 结果 |
    |---|---:|---|
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/check_knowledge_docs.py` | 0 | knowledge spine 与投影 fresh。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/check_repository_code_assets.py check-current` | 0 | current code-assets 检查通过。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py doctor` | 0 | document system self-consistent。 |
    | `/home/zhuran24/zmd-pj/.venv/bin/python devtools/docctl.py gate --profile changed` | 0 | changed profile 全 lane PASS。 |

  - 边界:未建立或修改任何 decision；`data/knowledge/decisions.jsonl`、`data/review_gates/**`、`data/proof_obligations/**`、`scripts/check_p1_2_proof_obligations.py`、`src/**` 均未由 S3b 改动。未执行 owner re-close、未更新 review gate 或 re-close authority floor，未 commit、未 `git add`。
