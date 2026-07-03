---
id: pr2-7-supervisor-seal-entrypoint-design
kind: decision
title: PR2 #7 生产 supervisor certify 入口的设计与安全边界 — scripts/run_supervisor_seal.py 薄接线,通电≠发布≠P1.2 closed,入口无 proof authority
summary: 2026-07-04 owner 拍板通电 PR2 #7,补 PROJECT_LOCK §1C(C5) 记的"生产 supervisor 入口不存在"操作链缺口(main.py 完成止于 CANDIDATE_PROPOSED,唯一 durable CERTIFIED mint 是 ExactCampaign.supervisor_seal(),此前只有测试调用)。**入口形态**:scripts/run_supervisor_seal.py 薄独立命令——resume 现有 CANDIDATE_PROPOSED proposal → 校验 marker 前置 → 调 campaign.supervisor_seal()(无 caller authority 参数,proof 复验全在隔离 L0 child)→ 按成功/异常退出码(0 sealed / 1 rejected / 2 precondition missing)。**四条安全边界(硬守,别放松)**:①只 mint campaign 级 CERTIFIED,不 publish、不碰 owner 门、不推导 P1.2 closed(公开发布仍 fail-closed 在 resolve_p1_2_publish_open_gate,gate=blocked_manual_review_count);②失败保持 CANDIDATE_PROPOSED + 非零退出,绝不 fallback 到 mark_campaign_stopped(CERTIFIED) 或伪造 terminal state;③参数最小(仅 --project-root),不给 marker/instance-id/proposal override,marker/instance_id 由 supervisor_seal/L0 从 disk 派生+复验;④走真实 supervisor_seal(),不手拼 L0SupervisorSealRequest、不复用 test 的 install_accepting_l0_supervisor_seal shim。**入口无 proof authority**:真正的验证权在 supervisor_seal→run_l0_supervisor_seal(隔离子进程 child 重放 sink/fixed-witness + parent 二次独立复核 domain + 写锁内 TOCTOU 重检 + 反绕过守卫),篡改入口脚本无法伪造 CERTIFIED,所以 close-kernel checker 不要求它登记为 sink(preflight --full 实证:新脚本不触发任何 obligation)。**测试坑(host floor)**:真实 seal 会撞 L0 dependency floor digest mismatch(如 attr/__init__.pyi)——repo 钉的 data/proof_obligations/pr2_dependency_floor_manifest.json 是 deploy-pending dev/CI placeholder,当前 Windows/机器的依赖版本不匹配;测试要 monkeypatch l0_module 的 DEPENDENCY_FLOOR_MANIFEST_REL/SIZE/SHA256 为 build_manifest() 生成的 host floor(见 test_p1_2_supervisor_pr1 的 autouse `_patch_l0_dependency_floor_for_host_tests`)。**完整度**:独立命令已满足 PROJECT_LOCK:154 的"生产命令从 marker 驱动独立 supervisor";把它接进生产 launcher(run_prod_*.ps1 / run_campaign_linux.sh 作 main.py 后自动第二阶段)是可选运维完整度,owner 2026-07-04 未拍(接的话别把 launcher 完成=seal 混淆 producer/seal 边界)。
scope:
  domains:
    - release-engineering
    - certified-exact
    - pr2
  paths:
    - scripts/run_supervisor_seal.py
    - src/tests/test_run_supervisor_seal.py
    - src/search/exact_campaign.py
    - src/search/pr2_l0_micro_verifier_core.py
  symbols:
    - supervisor_seal
    - run_l0_supervisor_seal
    - resolve_p1_2_publish_open_gate
status: active
priority: P1
triggers:
  intents:
    - wire-production-certify-entry
    - modify-supervisor-seal-entrypoint
    - run-production-seal
  keywords:
    - supervisor_seal
    - run_supervisor_seal
    - PR2 #7
    - 通电
    - certify 入口
    - production supervisor
    - proposal-ready marker
    - publish gate
    - P1.2
    - CANDIDATE_PROPOSED
    - dependency floor
    - CERTIFIED mint
  negative_keywords: []
  paths:
    - scripts/run_supervisor_seal.py
    - src/tests/test_run_supervisor_seal.py
  symbols:
    - supervisor_seal
    - run_l0_supervisor_seal
  error_regex:
    - "dependency floor digest mismatch"
    - "supervisor_seal_rejected"
    - "CERTIFIED campaign stop must be minted by supervisor_seal"
  examples:
    - 怎么让 main 跑到 CERTIFIED / 生产 seal 入口怎么调
    - 给 supervisor 入口加 publish 行不行
    - 真实 supervisor_seal 测试报 dependency floor digest mismatch
activation:
  layer_hint: L1
  must_know: false
  reason: 碰生产 certify/seal 入口、想让 main 产出 CERTIFIED、或改 supervisor_seal 调用面时该想起——通电的安全边界(≠发布≠closed、入口无 authority、失败 fail-closed)不显然,放松任一条都是 release soundness 违规。
provenance:
  op: record
  reason: 2026-07-04 PR2 #7 通电落地(6 面深研 → 薄接线实现 → 测试 → --full 19 / --slow 46 绿)的设计与边界固化。
  evidence:
    - "2026-07-04 通电: scripts/run_supervisor_seal.py(commit 349c56c);6 codex 面深研(supervisor_seal 用法/marker/L0链/launcher/发布闸/CLI)全指向薄独立命令;实现只 resume+校验+supervisor_seal()+退出码;测试 3 个(真实 proposal→seal→CERTIFIED + spy 证入口不 publish + already-sealed/missing 前置 fail-closed,2 个真实 seal 登记 @slow);preflight --full 19(双 checker 60/65·83、pytest 3781)、--slow 46;checker 不要求入口登记 close-kernel(印证入口无 proof authority);P1.2 手动门状态不变。"
  updated_at: "2026-07-04"
---
PR2 #7 生产 supervisor certify 入口的设计与安全边界(2026-07-04 owner 拍板通电、亲历落地)。

== 缺口与入口 ==
PROJECT_LOCK §1C(C5) 把"生产 supervisor 可执行入口"列为 P1.2 done-condition 的机器条件,并记它当前不存在:normal `main.py` 完成只落 `CANDIDATE_PROPOSED`(producer 只产提案 + 写 `*.proposal_ready.json` marker),唯一 durable `CERTIFIED` mint 是 `ExactCampaign.supervisor_seal()`,此前 23 处调用全在 tests。通电 = 补这个入口。

**入口 = `scripts/run_supervisor_seal.py`,薄独立命令**:
```
ExactCampaign.load_or_create(project_root, resume=True)
  → 校验 final_status==CANDIDATE_PROPOSED 且 supervisor_proposal 存在(marker 前置先查)
  → campaign.supervisor_seal()   # 无参数;真实隔离 L0 复验
  → 成功=0 / rejected=1 / precondition_missing=2
```

== 四条安全边界(硬守)==
1. **只 mint campaign 级 CERTIFIED**,不 publish、不碰 owner 门、不推导 P1.2 closed。公开交付面(final_solution/blueprint/manifest)仍 fail-closed 在 `resolve_p1_2_publish_open_gate()`(gate=`blocked_manual_review_count`)。通电只补"入口存在"这个机器条件。**别给入口加 publish 调用**(测试用 spy 钉死:seal 期间 `publish_verified_certified_delivery_surface` 零调用)。
2. **失败保持 CANDIDATE_PROPOSED + 非零退出**,绝不 fallback 到 `mark_campaign_stopped(..., "CERTIFIED")` 或写 forged terminal state(这俩本就被反绕过守卫 raise)。
3. **参数最小**(仅 `--project-root`)。不给 `--marker-path`/`--campaign-instance-id`/`--proposal-bytes` override:marker 由 `proposal_ready_marker_path_for_campaign(campaign_path)` 派生,instance_id 由 supervisor_seal/L0 从 disk checkpoint 复验。
4. **走真实 `supervisor_seal()`**,不手拼 `L0SupervisorSealRequest`(它没有 caller-selected dependency floor)、不复用 test 的 `install_accepting_l0_supervisor_seal` shim(那是 write-shape 替身、不测 true child)。

== 入口无 proof authority(为什么它不必是 close-kernel sink)==
验证权全在 `supervisor_seal → run_l0_supervisor_seal`:隔离子进程(`-I -S -B -X pycache_prefix`)里 `pr2_l0_true_verifier_child.verify` 重放 candidate sink proof + fixed-witness + terminal frontier evidence,parent 再二次独立复核 domain response(nonce/strong_keys/publishable/violations/digest),写锁内 TOCTOU 重检 marker/checkpoint sha 后才 atomic 写 CERTIFIED。篡改入口脚本只能"调 supervisor_seal()（合法）"或"不调（无事发生）",无法伪造 CERTIFIED。故 `check_p1_2_proof_obligations.py` 不要求入口登记为 sink——preflight --full 实证:加了新脚本,60 sinks / 14 obligations 不变。

== 测试坑:host dependency floor ==
真实 seal 会撞 `ValueError: dependency floor digest mismatch:attr/__init__.pyi` —— repo 钉的 `data/proof_obligations/pr2_dependency_floor_manifest.json` 是 **deploy-pending dev/CI placeholder**（PR2 #9a,生产前需目标环境重生成 re-pin），当前机器的依赖版本对不上。测试要 monkeypatch `l0_module` 的 `DEPENDENCY_FLOOR_MANIFEST_REL/SIZE/SHA256` 为 `build_manifest()` 生成的 host floor（照抄 test_p1_2_supervisor_pr1 的 autouse `_patch_l0_dependency_floor_for_host_tests`）。负例（missing checkpoint/marker）在 main 的前置检查就 return 2、不进 seal,不需要 floor patch。真实 seal 测试 ~16–42s,登记 @slow。

== 完整度(可选,owner 未拍）==
独立命令已满足 PROJECT_LOCK:154 的"生产命令从 proposal-ready marker 驱动独立 supervisor"。把它接进生产 launcher（`run_prod_*.ps1` / `run_campaign_linux.sh` 作 `main.py` 完成后的自动第二阶段）是"受支持 launcher"的更完整形态,但接的话别把 launcher 完成=seal 混淆 producer/seal 边界（现有测试硬性维持 producer 只产 CANDIDATE_PROPOSED）。

发布/门/发布器边界见 [[review-convergence-tcb-line-not-zero-findings]] 与 PROJECT_LOCK §1C;reseal 实操见 [[close-kernel-reseal-execution-sop]];分工(发布面=leader 直做)见 [[agent-role-division-and-codex-collaboration]]。
