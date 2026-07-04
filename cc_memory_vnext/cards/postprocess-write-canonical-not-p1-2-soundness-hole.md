---
id: postprocess-write-canonical-not-p1-2-soundness-hole
kind: decision
title: 非权威 postprocess/viewer 能物理写 canonical 交付路径 ≠ P1.2 soundness 洞 — authority 来自 sealed campaign 非"文件存在";判定逻辑 + 收口本地多镜头审方法(2026-07-04)
summary: 2026-07-04 P1.2 收口本地对抗审(12 镜头 codex + 对抗复验)剥出的唯一 finding 及两次独立复验判定,固化一条未来会反复用到的原则:**非权威 postprocess 层(viewer/serializer/adapter/report)即使能物理写 canonical 交付文件路径(data/solutions/final_solution.json / optimal_blueprint.json / certified_delivery_manifest.json),也不是 P1.2 above-TCB soundness 洞**——因为 P1.2 的 authority 来自 sealed campaign checkpoint + central publisher 事务派生 + 独立 verifier(SHA/等价重校验),不来自"canonical 路径文件存在/内容";PROJECT_LOCK:277 明确"文件存在或内部 CERTIFIED 文字不构成 publishability proof"。具体案例:src/render/industrial_planner_single_base_delivery_viewer.py 的 _copy_release_payload_artifacts() 有 path traversal(恶意 release manifest 的 relative_path='../../../../data/solutions/final_solution.json' 经裸 shutil.copy2 覆写 canonical,codex 隔离复现 canonical_was_overwritten=True),但判 refuted/TCB 线下。**收口本地审方法**:12 镜头 codex 多镜头 → 每 finding 对抗复验(默认 refuted、只留 above-TCB)→ 守 TCB 线不追线下;不起 GPT Pro 外审 round(2026-07-03 画线拍板还站着)。
scope:
  domains:
    - release-engineering
    - certified-exact
    - external-review
  paths:
    - src/render/industrial_planner_single_base_delivery_viewer.py
    - src/search/certified_surface.py
    - PROJECT_LOCK.md
  symbols:
    - publish_verified_certified_delivery_surface
    - resolve_p1_2_publish_open_gate
status: active
priority: P1
triggers:
  intents:
    - judge-if-a-finding-is-p1-2-soundness-hole
    - review-certified-delivery-surface
    - assess-postprocess-write-path
  keywords:
    - postprocess 写 canonical
    - viewer path traversal
    - filesystem hardening
    - soundness 洞判定
    - authority 来自 sealed
    - 文件存在不是证据
    - P1.2 收口
    - 本地多镜头审
    - containment
    - 绕过 central publisher
    - TCB 线下
  negative_keywords: []
  paths:
    - src/render/industrial_planner_single_base_delivery_viewer.py
    - src/search/certified_surface.py
  symbols:
    - publish_verified_certified_delivery_surface
  error_regex: []
  examples:
    - 某个 postprocess/exporter 能写 data/solutions/final_solution.json 算不算绕过发布闸
    - viewer 有 path traversal 是不是 P1.2 soundness 洞
    - 判定一个 finding 在不在 TCB 线上
activation:
  layer_hint: L1
  must_know: false
  reason: 审 P1.2 发布链或判定"某个能写 canonical 路径的 finding 是不是 soundness 洞"时该想起——直觉容易把"绕过 central publisher 写 canonical 文件"当成盖假章,但 P1.2 的 authority 不在文件、在 sealed campaign + 独立 verifier;这条判定省下一轮误报追查。
provenance:
  op: record
  reason: 2026-07-04 P1.2 收口本地对抗审(owner 离线期自驱,12 镜头 0 confirmed)剥出的唯一 finding 判定,固化判定原则与收口审方法。
  evidence:
    - "2026-07-04:12 镜头(首轮6+二轮6)codex 多镜头对抗审 P1.2 发布链,soundness 面 0 confirmed above-TCB 真洞。唯一 finding=viewer path traversal,两次独立对抗复验均判 refuted/线下;journal 核实各 finder 返回。全程未改源码,认证核心冻结完整。报告 scratchpad/p1-2-closeout-local-review-report.md。"
  updated_at: "2026-07-04"
---
非权威 postprocess/viewer 能物理写 canonical 交付路径 ≠ P1.2 soundness 洞(2026-07-04 收口本地审剥出并判定)。

== 判定原则(未来审查会反复用到)==
遇到"某个非权威 postprocess 层(viewer / serializer / delivery_manifest / adapter / report / exporter)能物理写 canonical 交付文件路径(`data/solutions/final_solution.json`、`data/blueprints/optimal_blueprint.json`、`data/solutions/certified_delivery_manifest.json`),绕过 central publisher / open-gate"这类 finding:
- **默认它不是 P1.2 above-TCB soundness 洞。** P1.2 的 authority 来自 **sealed campaign checkpoint + central publisher 事务派生 + 独立 verifier(SHA256 + 内容等价重校验)**,**不来自"canonical 路径上有个文件 / 文件里写了 CERTIFIED 字样"**。PROJECT_LOCK:277 原文:"their mere presence or internal CERTIFIED text is not proof of publishability"——这是项目声明的受信假设,采信必须走独立 verifier。
- 要把它升成 soundness 洞,得证明"喂入 payload → 系统真的把伪造结果当 CERTIFIED **铸造/发布/采信**"的完整链条。写坏一个文件 ≠ 完成这条链。

== 案例:viewer release path traversal(2026-07-04,task #8)==
- `src/render/industrial_planner_single_base_delivery_viewer.py` 约 :419-438,`_copy_release_payload_artifacts()` 把 release manifest 的 `artifact.relative_path` 直接拼 `output_dir` 后裸 `shutil.copy2`,无 resolve 后 containment 校验、不拒 `..`。恶意 manifest `relative_path='../../../../data/solutions/final_solution.json'` 能覆写 canonical(codex 隔离复现 `canonical_was_overwritten=True`)。
- **判 refuted / 线下**,三层理由:
  1. **输入不可控 / 自伤**:正常路径 `relative_path` 来自 `scripts/build_*_release.py` 的 hardcoded `_RELEASE_SOURCE_FILE_SPECS`,checked-in manifest 无 `..`;唯一喂任意 manifest 的入口是 standalone `--pointer-json <任意路径>`,需攻击者已有本地任意文件写入能力。
  2. **认证判定链全不读这三文件裸内容当信任输入**:`certified_surface.publish_*` 从 sealed checkpoint `final_result` 派生并原子写出,旧文件只在 verifier 环节被读且要过 SHA256(`certified_surface.py:1136-1142`)+ 与 campaign result 的 `_json_equivalent` 校验(`delivery_manifest.py:576-580/635-682`);两个结构 checker 只做 AST/字节扫描不读内容;`ExactCampaign.save()/mark_campaign_stopped()` 的 unsupervised CERTIFIED 拦截 + `supervisor_seal()` 隔离 L0 校验都基于 campaign 内部状态;`package_review_snapshot.py` 只从 committed git tree materialize 而这三文件 gitignore。
  3. **viewer 架构上禁声称 CERTIFIED**:`src/render/industrial_planner_exact_status.py` `normalize_non_authoritative_exact_status()` 对 `CERTIFIED` token 直接 raise。
- **仍是真实 filesystem hardening 缺口**(缺 containment):修 = reject 绝对路径 + `..`,`resolve()` 后强制 containment 在 `output_dir/downloads/release` 内。**更广观察**:非权威 postprocess 能物理写 canonical 路径这个面,`serializer`/`delivery_manifest`/`adapters` 是否同类,值得**系统审**而非单点补(→ owner 排期,task #8)。修前先确认该文件在不在 close-kernel sink 名单(render/* 应 POSTPROCESS_ONLY、大概率非 sealed → 改它不触发 reseal)。

== 收口本地审方法(2026-07-04 亲历,可复用)==
- **12 镜头 codex 多镜头对抗审**认证发布链:反绕过守卫 / TOCTOU-pin到runtime / publisher-open-gate 旁路 / L0 child 隔离完整性 / producer-mint 分权 / strict-json+frozen-hash / resume·checkpoint 篡改 / 算法↔认证边界接缝 / 并行 scheduler 竞态 / frontier·fixed-witness identity / declare_mode canonical / artifact-contract 身份认定。
- 每 finding → **对抗复验**(默认 refuted,除非能给"输入 → 假 CERTIFIED 被铸/发布"的具体链条),只留 `is_real && above_tcb && !refuted`。
- **守 TCB 线**:线上=能伪造认证的 soundness 洞(必审);线下=对更强内部对手能否更严的强度选择(不追,见 [[review-convergence-tcb-line-not-zero-findings]])。
- **不起 GPT Pro 外审 round**(2026-07-03 画线拍板还站着);GPT Pro relay / clean 计数 / 手动门是 owner 三步。
- 坑:codex finder 可能 API 中断(单镜头挂)→ workflow resume 补跑;结论要读 journal 核实 finder 实际返回,别假设 cache 非空(见 [[codex-structured-output-placeholder-pitfall]])。

关联:主线计划见 [[p1-2-closeout-then-tcb-backlog-order]];TCB 线判据见 [[review-convergence-tcb-line-not-zero-findings]];relay staging 见 [[relay-review-clipboard-staging]]。
