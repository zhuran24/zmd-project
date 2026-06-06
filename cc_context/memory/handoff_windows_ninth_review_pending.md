---
name: windows-ninth-review-pending
description: "单一 living 当前交接/现状源。2026-06-06 当前: 文档树 subject/projection + completeness gate 已收口到 004/005 clean 观察点; 本轮补强 memory publish-safety/currentness gate, 移除当前树 Gemini key, repo-native INSTANCE check, secret scan + memory health 接入 preflight。算法主线仍停在 Phase 1.2 spike close → v29 外审/之后 P1.3A 决策。"
metadata: 
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **这是项目单一 living「当前 phase/交接状态」权威源** (per [[memory-currency-protocol]])。环境落点细节见 [[windows-handoff-env]] (稳定 reference), P1.3A 设计/Step0 gate 细节见 [[p1-3a-design-phase]] (设计记录)。本条是这三者里唯一的「现状真相」入口, 另两条只补细节不重述现状。

<!-- AUTO-STATUS:BEGIN — 下面 `INSTANCE:` 槽**内**由 pre-commit stamp_living_status.py 自动 transclude (实例/分身模型, 见 [[github-backup]] / [[memory-currency-protocol]] rule#7); 别手改槽内值 -->
**自动现状标记** (可推导现状每 commit 自动刷, 结构上不可能 stale; 人写的判断散文见下方各 `##` 块):
- 最新 review 包: <!-- INSTANCE:latest_review_package -->v28 (sha `c00a957c73f1…`)<!-- /INSTANCE:latest_review_package -->
- spike 分支 HEAD: `<!-- INSTANCE:spike_head -->1850bb6<!-- /INSTANCE:spike_head -->`
- CLAUDE.md Current Phase: <!-- INSTANCE:current_phase -->1.2 spike close (subject projection)<!-- /INSTANCE:current_phase -->
- GitHub repo: <!-- INSTANCE:repo_url -->zhuran24/zmd<!-- /INSTANCE:repo_url -->
<!-- AUTO-STATUS:END -->

## 最新状态 (2026-06-06) — GPT 接手后文档树/记忆树 closeout + GitHub 上传准备

> **当前真相 (接手观察点)**: 当前干净项目观察点 HEAD = `89b5a641aee1b52b922a1c7da1db098b7fffe440` (`docs: close doc tree completeness gate`), branch `doc_tree_closeout_v20260606_004`; 观察点包解压后 `git status --short` 为空, memory repo mirror 与外层 `_cc_live_memory/` 字节一致。
>
> **文档树**: 已从“文件清单”升级成 subject/projection + completeness gate。`docs/subjects/*` 是抽象主体, concrete docs 内 `DOC-SUBJECT` blocks 是投影; `sync_doc_subjects.py --check` 与 `check_doc_tree_completeness.py` 已进 preflight。
>
> **记忆树**: 这轮补强见 [[memory-tree-publish-safety]]。重点是把 CC-era 半外部机制改成 repo-native：Gemini 明文 key 从当前树删除, Gemini scripts 改读 `GEMINI_API_KEY`; `stamp_living_status.py` 默认检查 `cc_context/memory`; 新增 secret scan + memory tree health gate 并接入 preflight。旧 key 已在历史/review 包里暴露, 最终止血需要 owner 在 Google 侧轮换/吊销。
>
> **GitHub**: GPT 连接器目标仓库曾显示不确定, 沙盒不能直接 `git push`。后续上传必须走 `zmd-gh-upload-bundle/v1` 给本地 Codex: 校验 SHA → apply patch → 跑 required checks → commit → 用户确认后 push/PR。
>
> **算法主线未改变**: certified exact / cut-family soundness 语义没动。Phase 1.2 spike close 之后仍应重建 v29 外审包、连续 clean 轮后再推进 P1.3A/step_8 master integration。下面 2026-06-04 v28 外审历史仍是算法主线最新 soundness 背景。

## 最新状态 (2026-06-04 晚) — v28 GPT 外审 = 4 个真 soundness 洞 (全修, F9 quarantine); 然后 Design A/B 工装 + 三轮对抗审查 (零 soundness); 后补验记忆覆盖

> **当前真相 (主线 + 工装两条线)**:
> **① 主线 (Phase 1.2 spike-close)**: v28 包 (sha `c00a957c`, 从 39c80c6 确定性重建) 送 GPT pro 外审 → **两 bundle 交叉, 4 个 confirmed_real soundness 洞** (内部严格审 7 轮 + 6 轮 GPT 全漏, 这次外审 + 我派对抗 verifier 对**真 master** 逐条构造伪 cert 才坐实):
>   - **A1/F5 pattern_nogood slot-collision (CRITICAL)**: evaluator 丢 slot 身份按 (group,pose) multiset 算, 伪核 `[(g,0,pA),(g,0,pB)]` 被 oracle 正确判 INFEASIBLE, 但 lift 成 multiset cut 比 oracle 证明的更强 → 误剪合法布局 slot0→pA/slot1→pB。
>   - **A2/F9 density_envelope max_allowed_area 量词倒置 (CRITICAL)**: validator 只验 K≤safe_ub + ∃witness area>K, 而 cut 需 ∀legal area≤K (`∃A area>K` ⊅ `∀L area≤K`); 伪 K=0 cert 过 validator → 误剪合法 9 格放置 = FP。
>   - **A3/F6 shape_packing_hall region_demand (HIGH)**: 没对 source-of-truth 下界 `max(0, D−对侧容量)` 校验, 伪 region_demand 误剪合法 split。
>   - **A4/F7F8 footprint (MED 加固)**: pole 2×2 / core 9×9 硬编码没钉 canonical (当前数据无 live FP, 防 drift)。+ D1 doc-currency。
>   修 (commit `e8c4643`, **red→green 实证**: 7 个对抗测试在未打补丁 master 全 FAIL): F5 slot-completeness guard / F6 `region_demand ≤ max(0,D−C_other)` + 限 left_or_bottom_boundary (用更准的 B2 版非过严 B1 版) / F7F8 footprint SoT。**F9 = quarantine** (validator fail-closed 拒 K<safe_ub, NP-hard tight-K 无便宜中间地带 → F9 整族实质停用; **反转 Gemini round-4 刻意 oracle-trust deferral**; replay 实证 validator 是信任边界且不重跑 oracle → 信任无法重算的 K 是真 replay-FP 暴露; 动了 PROJECT_LOCK + 5 cut-family spec; 解封须 P1.5+ 给 cert 加 area-capacity proof-carrying 字段)。**cuts 418→425**。
>   **可复用判定线**: validator 该不该独立重算某 cert 标量 = **能否便宜重算** —— canonical 常量 (radius/footprint / F6 的 max(0,D−C_other) 算术) O(1) 可查 = 不查纯属疏忽 must-fix; oracle 解的 NP-hard 子问题 (F9 tight-K / F5 INFEASIBLE) = 信任是刻意 P1.5+ deferral。**A2/F9 是 GPT 不知情重提了 Gemini r3 提出、r4 主动撤销的刻意 deferral** (新窗口零历史→撞已裁决决定, [[gpt-error-types-taxonomy]] 的"前提错估"; 盲打会反转刻意设计 + 删记录理由的测试 → verify-before-apply 实例)。
>   **主线现状**: 外审找到真洞已全修在 master; consecutive-clean 计数器**重置**; v28 包 (c00a957c) 被修复后的 master supersede; **下一关 = 重建 v29 + 续外审连续清零轮 (未做 —— 用户转去做 Design A/B 工装 + 本次补验)**。
>
> **② 工装 (用户指定 doc-currency + SoT 治本, 非主线)**: 把"核心节点(主体)+投影+强制函数"架构套到项目数字 + cut-family SoT, 见 [[authoritative-numbers-single-source]]:
>   - **Design A 数字单一来源**: `docs/research/p1_2_spike_sizing_gate_20260601/authoritative_numbers.json` 核心节点 + `gen_authoritative_numbers.py` + drift-test 强制函数 (master 只焊 cuts_tests_total)。
>   - **Design B 共享 SoT**: `src/cuts/helpers/canonical_sot.py` (F7/F8 委托消私有副本) + meta-test。
>   - **三轮对抗审查** (architecture-review→fix / fix-reverify / **fresh full re-review**): **全是 doc-currency/工装健壮/诚实度/完整性, 零 soundness**。Review #3 fresh-pass 在 **certified attach-scope 路径** `assumptions/verifiers.py:104` 逮到 canonical pole-radius lookup 的**第 4 个逐字副本** (verify_power_pole_jump_radius 用; 前 3 轮内审 + 6 轮外审全漏, meta-test 只扫 families/ 结构看不到), 已委托 canonical_sot (commit `d4ae058`)。诚实评估: **多轮对抗审下 soundness 一直稳, 真正递减回报的是完整性长尾** (架构 branding 比实现 scope 宽); 建议 100% consolidation 当一次性有界聚焦任务做 (**待办**: `verify_protocol_core_position` 近似副本 + 2 个 master-recomputable sizing 数 (type_pool/concrete) 真 master-recompute), 别靠反复 full 多代理审挤。
>   cuts 计数链: **418 (v28 four-hole fix e8c4643) → 425 → 437 (Design B meta-test) → 441 → 442 (R3 加固)**。
>
> 下面 v28-内部7轮 / v27 / v26 块是中间历史。

## (中间历史) 最新状态 (2026-06-04) — v28 (sha 6c90a199) + 内部严格审 7 轮: R3 逮 HIGH F7 soundness 洞, R4-R7 doc-currency; 实质 clean 但未达 3 连续 clean

> **当前真相 (摘要, v28 + 内部严格审)**: v27 (第六轮外审 B-minor 纯文档) 全修后, 用户把 close 标准提高为「**大节点 ≥3 次连续独立审查零问题**」。跑内部多镜头对抗审查 workflow (6 镜头 soundness/sizing-math/scoping/reproducibility/cross-doc/packaging-hygiene + 对抗 refute + completeness critic; 脚本 `cc_context/...省略.../workflows/scripts/v28-strict-internal-review-wf_84b207cd-4a8.js`, 每轮重建 v28 后跑) 共 7 轮:
> - **R3 = 最大收获: HIGH F7 soundness 洞 (已修)**。`src/cuts/families/power_hitting_set.py` validate 不校验 `cert.pole_radius` 对不对得上 `canonical_rules.facility_templates.power_pole.power_coverage_radius` (phase 6/7 的 CoverSet recompute 直接信 cert radius)。伪造 tiny-but-positive radius (0.0001, 过 schema `>0`) → CoverSet 空 → 验 'sound' → false-positive cut → 误剪可行布局 → certified_exact **丢精确性**。`replay.py` FAMILY_VALIDATORS 可达 (非死代码)。F8 (`power_grid_reach`) 早有 `_validate_pole_radius_sot` 防同样攻击 (R4 Finding#2), **F7 是唯一漏的 power 兄弟** (F1/F6/F8/F9 都 recompute 各自 cert 数值字段); 且 spec `07_power_hitting_set.md` 本就把 canonical pole_radius 列为 SoT 输入 → spec↔src 背离。**6 轮外部 GPT (v22-v27) + 我早先独立 backstop 全没抓到** —— 严格内审的价值实证。修: 加 `_lookup_canonical_pole_radius` + `_validate_pole_radius_sot` (镜像 F8, fail-closed) 插在 CoverSet recompute 前 + test `_make_state` 注入 canonical_rules + 2 回归测试 (forged 0.0001→unsound, canonical 缺→unsound)。**cuts 416→418**; full pytest 63 fail 全 pre-existing (rtree 未装 + .artifacts bundle 缺, 与本改无关; cuts subset 418 全过)。提交 master `39c80c6`。
> - **R4-R7 全 doc-currency / packaging (无 soundness)**: README_V22 (1000 行 v22-era 模板) 旧数字随包演进漂, 每轮逮 ~1-2 个镜像实例漏改。已修: cuts 计数现值→418 (+ 顶部「数字时效性」disclaimer 标历史段为快照) / F3 micro-probe 9→12 (简化掉易漂的 matrix) / remap `36/50`→`36/150 pair ≈24%` (verdict 3 处 + README) / verdict banner `两轮`→多轮 / runner B1 docstring / round-2 加的 smoke-cap 命令补「重生成 verdict 显示 NOT_GO 是 cap artifact」警告 / **build 阶段 identity scrub** (`_scrub_local_identity` in build_v28: `zhuran24`→devuser + 任意盘符反斜杠绝对路径→`<local-path>` + .ps1/.svg/.html 等扩展 + 空格路径字面替换; **不碰 code_context 保 SHA manifest**) / phase3b 残留 forward-slash 路径 (`E:/phase3b_workspaces`, 非身份) 用户选**接受 + README「隐私/scrub」段披露** (含一处 test 断言故意不 scrub 以保测试逻辑)。**身份 zhuran24/Lenovo/追光 全清 = 0**。spike 7 commit: `ae83f45`(F1 repo-root)→`a18c375`(utf-8)→`a45b8b2`(writer#1)→`143537c`(verdict risk#6)→`18acd90`/`a0b333a`(R2)→`830c5fd`(verdict L38 remap)。
> - **判定口径**: 按 workflow verdict (confirmed_count + critic 独立 overall_clean), 不强求 6 镜头都 emit —— **clean 包上 5/6 镜头常空返回 StructuredOutput** (查不到东西就散文收尾不调工具, 是工具 artifact 非包问题), 靠可靠的 critic (它独立重跑 sizing_gate 复现全数字 + 读 density_envelope source 确认 single-group 守卫 + 核 SHA256SUMS 11/11 + cross-doc)。R5/R7 degraded 但 critic 均 overall_clean。
> **v28 终包 sha `6c90a1998ce8b9705d880f480f3da59f508c986d46a3be7bb889007cbebe54ff`, 14.40MB/2191 files; 未交付用户/未送外部 (是内部-clean 候选)**。**下一关 = 继续内部连续清零 (R8+: 重建 v28 → 跑该 workflow → 目标连续 3 轮 0 confirmed + critic 0 substantive gap) 或 转外部 GPT pro 连续轮 (策略待用户定)**; 内部 doc-currency 是长尾, **实质已 clean 自 R3**。包/prompt 规范见 [[index-packaging-cluster]]。下面 v27/v26 块是中间历史。

## (历史) 最新状态 (2026-06-03) — v27 已建+独立 backstop 验+交付 (sha d2550e39); 第五轮外审 3 finding 全修; 等送 GPT 第六轮确认 或 进 P1.3A

> **当前真相 (摘要, v27)**: v26 送 GPT pro **第五轮外审**, 判 **B/PATCH (无新 soundness 洞, 无 concrete-literal cap 方向错, 核心 sizing 结论成立; GPT 预承诺应用补丁后 GO_WITH_MINOR for sizing-only close → 可进 P1.3A)**。3 finding 主代理逐条 reproduce (含读真源码核 reviewer 论断) 后全修:
> - **F1 (MED, reproducibility)**: review-mirror runner 跑 Phase B 时 `REPO_ROOT` 多走一层到 `project/code_context` → FileNotFound (v25 的 import shim 只解决 import 不解决数据路径)。spike runner + 6 lib 加 `_resolve_repo_root()` (探测含 `data/preprocessed/candidate_placements.json` + `src/` 的真根, production/mirror 两布局都对)。验: 两布局单测 PASS + 重建包上 mirror runner 越过 v26 精确失败点 (load_pose_registry 成功 load)。
> - **F2 (MED/LOW, scoping)**: sizing_gate 把 F9 **11,644** 误标当前 per-cut concrete vector; 真相 = `density_envelope` cert **single-group** (validator 拒 witness group ≠ cert group, 源码 `src/cuts/families/density_envelope.py:201-210` 实证), **当前 per-cut cert-group max 仍 784**, 4,608 是 same-template proxy, 11,644 只是 all-manufacturing cross-group **stress proxy** (F9 被保守夸大, 非隐藏 blow-up)。sizing_gate v5→v6 拆 `cert-grp/type-all/same-tpl/all-mfg/group-all` 列 + RESULTS/verdict 同步。
> - **F3 (LOW/MED, scoping)**: Finding 5 #1 "81,795 BoolVar | YES" 与 A-F1 冲突 → 降 **PARTIAL/proxy** (81,795 是 type-pool toy build, concrete 325,747 cheap-counted 非 B2 实测); 连 spike `write_verdict_md` 模板 #1 也改 PARTIAL (源头一致, 防 writer 重跑覆盖回 YES)。
> - **(re-audit 顺带, 非 v26 finding)**: ① **UTF-8** — `MANDATORY/HINT/jsonl` 读漏 `encoding`, 非-utf-8 locale (Windows GBK / Linux C-locale Docker) 读含 0x80 的 JSON 崩 (V21-8F2 当时只修了 PLACEMENTS), 补全 8 处 `encoding="utf-8"` (utf-8 locale 行为不变)。② writer #1 源头一致 (见 F3)。**注: 我在 Windows 验证时还撞到 `/tmp` 硬编码 (`measure_proto_bytesize`) —— 纯 Windows-incompat, 未修 (mirror runner 目标平台 Linux, 越界 scope)**。
> 落: master sizing_gate v6 + RESULTS v6 + `cc_context/review/build_v27_win.py`; spike `a45b8b2` (3 commit: `ae83f45` F1 + `a18c375` UTF-8 + `a45b8b2` writer)。**v27 终包 sha `d2550e3965911ab4d5f204e12128b7520379dee593996c525014fad5f2a02c5a`, 14.40MB/2190 files**。验: 独立 opus backstop 在**重建包**上确认 F1/F2/F3 全 CLOSED + density_envelope single-group 前提源码成立 + 跨文档一致 (逮到 1 LOW writer 残留, 已修+定向重验); pytest cuts **416**; F3 micro-probe **12/12**; 包内 sizing_gate v6 实跑 784/4608/11644/325747。**第六轮 (v27) 回执 (2026-06-03)**: 用户选"做干净再继续"→ 送 GPT pro (prompt `GPT_v27复审_prompt.md`, 不附 deps)。判 **B-minor**: **无 soundness 洞 / 无 sizing 数学反转 / 无 C 级 framing 错**; F1/F2/F3 全 closed (F2 single-group 前提 reviewer 独立核 density_envelope.py 实证); sizing 6 点结论 sound; bitset LSB / concrete-vs-type-pool / F7F8 守卫 / F3 fail-closed 全独立复现过 (它自己也跑出 416 / 12-12 / 784·4608·11644·325747); **无 NOT_GO 形式化主张**。剩 3 条全 LOW 文档: R1 RESULTS.md 历史 v3 表排在 v6 纠正段前 (gate 排序应 fail-closed) → patch 0001 v6 summary 提顶+旧块标历史; R2 verdict writer risk#6 仍 type-pool 措辞 → patch 0002 改 concrete 口径; R3 sizing_gate `cert-grp` 列名易误读 → patch 0003 改 `single-grp`。**3 patches verify-before-apply 后全应用到源** (0001/0003 git apply master; 0002 等价 Edit spike `a0b333a`)。reviewer 预承诺应用后可进 P1.3A。**真正下一关 = 进 P1.3A F1/F9 lowering** 决策 (带 concrete-literal cap = `len(final_concrete_literals)` + F9 single-group 现状, 见 [[p1-3a-design-phase]] + [[cp-sat-no-add-lazy-constraint]]); 走 N=8 parallel design, phase-boundary 待用户拍 (per [[main-merger-scope-creep-bias]])。第七轮终审 (v28 重建+送审) 仅用户要正式 A/GO 上记录才需 —— 我倾向跳过 (纯 doc-only + reviewer 已 pre-bless)。下面 v26/v25/v23 块是中间历史。

## (历史 v26, 已被上方 v27 supersede) — v26 已建+验+交付 (sha fb694152), 第四轮外审两份 B 并集 6 finding 全修

> **当前真相 (摘要, v26)**: spike close gate 走完 v22 九审(双 B)→v23 二次 B→v24→v25→**第四轮外审 (v25 送审, 两份独立都 substantive、都 B/PATCH, 无 soundness 洞)**。并集 **6 finding 全修 (v26)**: **A-F1 (最重) — sizing gate 数的是 facility type-pool overlap (总 81795), 但真 pose-bool master 按 `(facility_type, operation_type)` group×pose 建 var, concrete ≈4× (325747); group 展开后 F9 784→11644, F4 5429→20157。所以 type-pool UB (F9 3341/F4 5429/16-18K) 是 cheap proxy 不是真-master literal 上界; P1.3A expanded cap 输入 = 真 translator group/template/optional 展开后的 concrete literal vector 长度**; A-F2 F9 window `[x,y,h,w]` 读序; A-F3 runner mirror import shim; B-F1 sizing_gate family summary density 行不再 fallback 4.0; B-F2 OR-Tools 实测改 `ExportToFile` (B 的补丁用了 9.15 不存在的 `.ByteSize()` 会崩, 我实跑 catch 换掉 —— verify-before-apply 实例); B-F3 F7/F8 `_validate_facility_cells_match_pose_registry` 加 duplicate pose_id 唯一性守卫 (fail-closed, cuts 414→416)。落: master `0a7f37f` (sizing_gate v5 + F7/F8 守卫 + RESULTS v5 + p1_3a concrete-literal cap); spike `dc3516a` (verdict v25 段 + runner shim); build `build_v26_win.py` + prompt `GPT_v26复审_prompt.md`。**v26 终包 sha `fb69415272d8a7759c76d8283b0fab6da8dc4fce1f63a956ea81c7d0a296e00f`, 14.39MB/2190 files**。验: w0f48suxi (5 镜头+critic) overall_ship=True; whtrpfv0j (全覆盖+引擎对抗) 3 critical 全过 (包 clean 无 .pytest_cache/secret, 包内 sizing_gate 实跑 325747)。**SendUserFile 交付手机 4 件 (v26 zip + deps_part1/2/3), prompt 贴正文**。真正下一关 = 送 GPT 第五轮 **或** 直接进 P1.3A F1/F9 lowering 决策 (带 concrete-literal cap 硬数字进, 见 [[p1-3a-design-phase]] + [[cp-sat-no-add-lazy-constraint]])。下面 v25/v23 块是中间历史。

> **(历史, v25)** **当前真相 (摘要)**: spike close gate 走完 v22 九审(双 B)→v23 二次 B(7 finding)→v24(修 7)→v25(再修 7, 全证据精度/工件/锁门, 非 soundness)。**v25 终包 sha `f245bc9`, 验证 workflow critic overall_ship=True, 独立 re-audit 确认 clean**, 已 SendUserFile 交付手机端 4 件。(v25 的 sizing 数 784/3341/5429 是 **type-pool**, 已被 v26 A-F1 的 concrete-literal 口径 supersede —— 见上方 v26 块。) 下面 v23 块是中间历史。

> **当前真相 (最新)**: v23 送外审 (GPT pro 双份), 深的那份判 **B** 并 catch 一条**我自己犯的真错**: `sizing_gate.py` bitset 用 MSB-first 解码, 真源 `region_capacity_oracle._encode_region_bitset` 是 **LSB-first** (`arr[idx//8] |= 1<<(idx%8)`)。我对真源码核 + LSB 重算确认 reviewer 一字不差对: region_capacity 大池子 manufacturing 是 **264** term 不是我写的 2026; F9 10×10 window ~360–524。**"F1/F9 大池子 2000–3200 term → 1.9GB blow-up" 是 bug 假数字, 真实 fixture 尺度 ~264 term → ~100MB, 不爆。** 下面旧块 (line 19 "核心 sizing 结论" 等) 的数字/结论**已废, 待 v24 改**。新 sizing 结论见本块末。

**v23 外审 (2026-06-02, 第二次 B)**: 深份 7 finding, 浅份低信号 (没真跑/无 finding/"测过就 GO"——信息量基本在深份, 取并集深份主导)。7 finding 状态:
- **F2 (我的 bitset bug, 最重)**: 已确认属实, 见上。连带 RESULTS.md / verdict Layer-2 #6 / README v22→v23 / 本 memory 旧块的数字全错, 待 v24 全改。
- **F1 sizing_gate 不可复现**: 脚本硬编码读 `cc_context/review/phase1_2_spike_review_v22.zip` 取 fixture, 但 cc_context 不入包 → 包内审者跑不了。应改读包内 `data/cuts/spike/oracle_emit_fixture_45cert.jsonl` + `data/preprocessed/candidate_placements.json`。属实。
- **F3 scope 过窄**: "只 F1/F9 blow-up, 其余 7 族任意 lower 都安全" 不成立 —— expanded lowering 下 F4 separator ~5429 (loose)、cutset 173、port 500 也不小。应改成 "realistic compact lowering 全族安全; 任何 family 的 expanded/large-overlap lowering 都需 per-cut term cap + cumulative proto cap"。属实。
- **F4 F9 没真测**: sizing_gate 对 density_envelope 退回 compact witness(4), 没测 window→pose overlap。已补测: 10×10 window → manufacturing 360–524。属实。
- **F5 remap telemetry 没进 artifact**: TranslationReport 有字段, 但 `scale_ramp.py` RampTierReport 序列化 + `scale_ramp_results.jsonl`/`phase_b_results.json` 没写 → "100K applied=100%" 只对手调 translator 不静默, 对实际 artifact 仍静默。属实。
- **F6 verdict writer 没锁**: `spike_prod_scale_runner.py` 仍硬编码 `G10=True` + #2 模板仍写 YES (只手改的 verdict.md 是 PARTIAL) → 重跑 phase-B 会回归。属实。
- **F7 malformed scope**: 文案不能说 toy_translator 全局 fail-closed (只 F3; 非 F3 仍 fallback synthetic)。属实。

**纠正后 sizing 结论 (LSB, 2026-06-02)**: fixture 尺度下 (a) **所有 9 族 realistic compact (witness/no-good) lowering → 100K 都便宜 (~1MB)**; (b) **expanded (全 pose-overlap) lowering** 随 region×池密度变化, fixture 尺度 region/window 给 ~百级 term/cut (region 264 / cutset 173 / F9-window 360–524 / power 16 scoped / F4-separator 5429 是 all-types 宽松上界且 F4 本质 no-good 不会真这么 lower), 100K → ~0.1–0.3GB 量级, **不是 1.9GB**。blow-up 是 region-size×pool 的函数、跨所有族, 不是 F1/F9 专属。P1.3A lowering 硬约束 = 对**任何** geometric/expanded lowering 设 per-cut term cap + cumulative proto cap (不只 F1/F9)。方向 (cut-family LBBD → P1.3A) 两 reviewer 都认 sound (B not C)。

**v23 状态**: gate 仍 B, 不是 clean-A。是否走 v24 全补丁轮 (修 7 finding + 重建 + 再外审) **还是** 拿纠正后 (更温和) 的理解直接进 P1.3A —— phase-boundary 决策待用户拍 (per [[main-merger-scope-creep-bias]])。

**v24 已建+验+交付 (2026-06-02, 用户选了路线 1 全补丁轮)**: 7 finding 全修 (master `a7eff5d` sizing_gate LSB; spike `12f64dc` runner F6/ramp F5/remap_audit/verdict 纠正/F7; build `6e88c4c`+prompt `cf41637`)。v24 对抗验证 workflow (4 镜头+critic) 逮到**第 8 个** = G10 表 staleness (verdict/README G 表缺 schema_err, 与 F6 runner emit 不一致, 复发 v23 同 pattern) → spike `0ebfaff` + build transform 修 + 内联验 (两表含 schema_err, secret=0, 包内实跑 sizing_gate 产 264 不产 2026)。v24 终包 sha `991c5b79431578797ffd81848a79489cf636d52af467ad6c9d705e3eb17bf3bf`, master HEAD `0cbc355`。prompt = `cc_context/review/GPT_v24复审_prompt.md` (诚实披露 bitset bug)。**已 SendUserFile 交付手机**: 103MB 一体 bundle **无下载按钮** (真因未验证 —— 非确证"超上限"), 改拆 4 件单发 (v24 zip 14MB + deps_part1/2/3.zip 各 29MB, 这俩 size N=1 能下; 干净短名避 .002 掉号), prompt 贴正文。**送审踩坑见 [[windows-powershell-harness-pitfalls]]** (SendUserFile 手机端有时无下载按钮; 真因+真阈值都未验证, 别把 29MB 当安全线; workaround=拆小+干净短名+逐件核能不能下、不能再拆)。

**v25 已建+验+交付 (2026-06-02, 第三轮外审后)**: v24 送 GPT 第三轮 (两份独立都 substantive 判 B), 7 finding 全是证据精度/工件/锁门 (非 soundness): proto bytes/term 按约束类型分 (实测 BoolOr no-good ~10-11 B/term 非 4-6, linear ~3-4)、F9 补测跑全 6 条 (scoped max **784** 非 524, all-type UB 3341)、scale_ramp remap 字段精确化 (代码 emit+remap_audit 承载, 历史 jsonl 没重跑不带)、G10 _read_a3_fixture_stats 硬化 (坏 JSON/缺字段计 schema_err)、A3 emitter run_emit 加 family>=9、verdict writer 加 Layer-2 risk#6+writer 边界 banner、cap 按 max/p99。落: master `cce55a3`(sizing v3)+`1aa63b2`(build)+`e50eea7`/`13c19fc`(prompt)+`dd960c9`(polish); spike `2cf96d6`(runner/emitter/verdict)。v25 验证 workflow critic **overall_ship=True 0 blocker**, 另 3 非阻塞瑕疵 (junk 文件/manifest CRLF/F9 avg 590→628) 也修+重建。**v25 终包 sha `f245bc9cf1b05e2ee4a1f27288ddc986c58ca416e974f089cc6d4810200750b0`**。prompt = `cc_context/review/GPT_v25复审_prompt.md`。SendUserFile 交付 4 件 (v25 zip + deps_part1/2/3, deps 同 v24 未变)。**新增送审规范**: prompt 让 reviewer **给补丁 + 打包** (非 1:1), 已记 [[external-review-prompt-template]] (§6 之外第二个输出例外, reviewer 补丁仍 verify-before-apply 不盲打)。等用户送 GPT 第四轮结果。

---

## (历史快照, 已被上方纠正) v23 已建+多镜头验证 PASS

GPT pro 正式九审跑了 (用户把 v22 **faithful + clean 两版独立**送审, 两份报告都贴回主代理)。**双双判 B (未 clean close)**, 不是之前本地预审的 CLEAN GO —— 以正式九审为准 (per [[memory-currency-protocol]] §5: judgment 级结论由做判断的主体定, 正式九审 > 本地预审)。两份报告 finding 主代理**逐条对真代码+真数据复核, 全属实** (base64 不 validate / 36-unknown 静默 remap / salted hash / schema_err 不进门禁 / Finding 5 #2 sizing overclaim)。两份质量对比: 完整版那次更深 (36-unknown 那条), 干净版更广 (独占 3 条), 但**单跑各一次无法把"包差异"和"GPT run-to-run 噪声"分离** (只有 README 不同, 取并集才对, 见 [[external-review-reproducibility]])。

**已落修复 (2026-06-02):**
- spike `a29fb44` (`[SPIKE-V23-PATCH]`): toy_translator 4 修 (validate=True + blake2b stable hash + remap telemetry + schema_err 门禁), micro-probe 9→12 case 全 PASS; verdict.md Finding 5 #2 `YES→PARTIAL` + 第九审修正章 + Layer-2 risk #6。
- master `af9054a`: sizing cheap gate 归档 `docs/research/p1_2_spike_sizing_gate_20260601/` (RESULTS.md + sizing_gate.py)。
- **核心 sizing 结论 (LSB-corrected, 见顶部块)**: cut body master 约束大小取决于 lowering。fixture 尺度全 9 族 compact lowering → 100K 便宜 (~1–3 MB); expanded lowering 随 region×pool 变, fixture 尺度 ~百级 term/cut (region 大池子 **~264 不是 2026**) → 100K ~0.1–0.3 GB 不爆; 只有大 region/window 趋近全 pool 才数 GB。blow-up 跨**所有**族 (不止 F1/F9), compact 全族安全、任何族 expanded 需 term cap。(早先此行写的 ~2–3K term / 1.9GB / "只 F1/F9" 是 bitset MSB bug 假数字。)

**v23 包已建 + 验 (2026-06-02)**: `cc_context/review/phase1_2_spike_review_v23.zip` (faithful, **只打完整包**, sha256 `131609a399f6afa00b2b58eb94afb1503efa3d500372cb930a84ca702d782b73`, 14.37 MB, 2189 files)。build 脚本 `cc_context/review/build_v23_win.py` (基于 build_v22_win, 修了 REPO 旧 dual-slug 路径 `zmd\zmd`→`zmd` + OUT_DIR 放 REPO 外防自包含 + README v22→v23 节)。spike overlay 用 `git show {分支}:` 自动取 a29fb44 修复版。多镜头对抗验证 (5 镜头 + critic, workflow): verdict/spike-code 与分支字节一致、secret=0、cc_context/gemini-key/.git/.venv/nested-zip/prompt/build-脚本 全 0 泄漏、candidate_placements 字节完整、4 source-of-truth 在 (3 个 CRLF vs LF 宇宙噪声, JSON parse 一致)。**逮到并修了 1 个 blocker**: README 自己那张 Finding 5 cover 表 #2 行漏改 YES→PARTIAL (verdict.md 改了 README 镜像表没改), 已在 build 脚本加 transform 修 + 重验 PASS。下次送审直接送这个 + deps 3 块 + prompt。

**⚠️ 安全: v22 包 (已发 GPT) 泄漏 live Gemini key** — `scripts/gemini_cross_check_*.py` (10 文件) 内嵌真 key `<redacted-gemini-key>`, v22 build 没排除 → 已随 v22 review 包发给 GPT pro (OpenAI 现持有)。这跟 [[gemini-math-consultant]] 记的"key 留私库历史靠仓库私有保安全"不是一回事 (那防 GitHub 公开; 外发 LLM 厂商是另一暴露轴, 用户没拍过板)。v23 已排除 (secret=0)。**key 轮换 = 待用户决策** (倾向轮换: 成本低 + 外厂留存不可控; 用户之前接受私库留存风险但非外发语境)。轮换则改 Gemini key + 更新本地 10 个 gemini_cross_check 脚本即可。

---

2026-05-31 zhuran24 → 接手者 (Windows 11) 交接完成。

**环境** (摘要, 详 [[windows-handoff-env]]): 仓库现在仓库根 `D:\追光\zmd` (2026-05-31 从旧 `D:\追光\zmd\zmd` 上移一层)。venv = **Windows 布局** `.venv\Scripts\python.exe` (Python 3.13.13 + ortools 9.15.6755)。CC memory **canonical slug = `D-----zmd`** (旧 `D-----zmd-zmd` 副本因迁移前 slug 已 obsolete, 留作备份不再写)。多数 Linux 命令 (.venv/bin / cachyos_setup / pacman_freeze / systemd / temp_logger / LD_PRELOAD) 在本机**不适用**, 改 `.venv\Scripts\python.exe`。

**九审门禁** (接手第一件事): spike close gate (v22, GO_WITH_MINOR) 在等 GPT 正式九审。用户拍板「九审当硬门禁先闭环 + 再加一道 GPT pro 外审」。本 session 主代理做了**独立九审复审 = CLEAN GO** (本地复审, 非 GPT 输出):
- 真 soundness 守卫: F7/F8 `_validate_facility_cells_match_pose_registry` 回归 + `test_oracle_scope_digest` = 3/3 PASS (v12 那两个 BLOCKER 假 cert 攻击早在 master `68fa7f0`/`a3414ee` 修+带回归)
- 414 cuts test PASS (3.86s)
- v22 spike harness `toy_translator` F3 malformed fail-closed: 读逻辑核过 (`_decode_cert_b64` isinstance(dict) guard + F3 family 移出 payload-not-None 块) + 9-case 自测脚本实跑 9/9 PASS
- verdict.md 诚实 (Sizing-only, 5 项 Layer-2 风险明确 defer, 无 overclaim)

**已交付物** (在 `cc_context/review/`; ⚠️ `*.zip` 被 `.gitignore:49` 全局忽略 → review 包**不入库 / 不上 GitHub**, regenerable: build 脚本 + spike 分支 a29fb44 可重建; build 脚本本身 tracked; faithful + clean 两版 per [[review-pkg-no-prompt-inside]]):
- `phase1_2_spike_review_v22.zip` (faithful, sha256 `a29f017a379d0774f9fc72d321f0d3cd95ee783ae3be1484b7fd2ceda8a4a29a`) + `phase1_2_spike_review_v22_clean.zip` (clean, 删 reviewer-priming) — v22 包 Windows 重建版, 单层 zip (原 7z-in-zip 双层换掉, 本机无 7z)。独立验过: build 脚本 0 泄漏 / 无 .git .venv / 无 prompt 混入 / code_context spike 11 文件 / candidate_placements 53.6MB 字节完整 / 无 priming。
- build 脚本 `build_v22_win.py` (faithful) + `build_v22_clean_win.py` (clean) 在 `cc_context/review/`, **可复用** portable builder: import 原 `scripts/build_phase1_2_spike_review_v22.py` 复用全部 README/文件清单/helper, 只换打包机制。修了 2 个 Windows 移植 bug: ① git show text-mode 强制 `encoding=utf-8` (GBK 呛中文 commit msg) ② `should_skip` 喂 `PurePosixPath` (Windows `\` 导致初版漏 21 个进包)。
- `GPT九审_prompt.md` — chat 单独给的审查 prompt (7-section + 不可达 armor, **不进 zip**)。

**打包/外审操作规范**: 整套走 [[index-packaging-cluster]] hub。

**依赖包** ⚠️ **(2026-06-02 起: 以后送审不再附 deps, 用户定 —— reviewer 自己装/不需跑全环境; 见 [[index-packaging-cluster]] 交付段。deps 制品仍留 regenerable 不删, 只是不随交付发; 未来 prompt 删 deps 合并/复现段。下面是历史制品说明)**: (GPT 在 linux cp313 装项目复现用): `cc_context/review/deps/` 含 34 个 wheel + `deps_linux_py313.zip` 均分 3 块 (`.001/.002/.003` 各 27.86MB, 因 GPT 单次上传体积限制) + `README_deps.txt`(cat 合并 + 离线 `pip install --no-index --find-links` 命令)。**闭包验证完整**: pip resolver 离线 resolve 整个 lock(34 全 pinned) 退出码 0、无缺 transitive; 3 块重组 sha256 = 原 zip byte-exact。regenerable, gitignored 不入库。**重建命令** (下次重送审): 从 Windows 拉 Linux cp313 wheel 用 `pip download --platform manylinux*... --python-version 313 --abi cp313 --only-binary=:all:`; 闭包验证用 `pip download --no-index --find-links <wheels>` 退出码 0 = 全 transitive 齐 (不需实际安装)。

**送审清单 (v23 现行, 2026-06-02)**: ① `cc_context/review/phase1_2_spike_review_v23.zip` (faithful, 只打完整包; sha 131609a3) ② 3 个 deps 块 (`.001/.002/.003`) ③ 粘 `cc_context/review/GPT_v23复审_prompt.md` (v23 版, 直接全选粘; **不是** v22 的 `GPT九审_prompt.md` —— 那个 v22 口径已废)。2026-06-02 这 5 件已 SendUserFile 推给手机端待用户上传。(v22 的"两版独立送"对 v23 不适用, 只有 faithful。)

**基础设施** (本 session 2026-06-01 落地): GitHub 实时备份已 live(私有库 zhuran24/endfield-exact-solver, post-commit 自动 push, pre-commit 自动同步 memory, SessionEnd 兜底 WIP) + 项目结构整理(CC/审查工件归 cc_context/{memory,tools,review}, root 清爽)。详 [[github-backup]]。

**下一步** (2026-06-02 修订, 九审已回 B 后): 正式九审已跑完 (B, 修复已落, 见顶部「最新状态」), 不再是「等送审」。真正的下一关 = **P1.3A 的 lowering 决策** —— sizing gate (LSB-corrected) 把它量成带数字硬约束: **任何**族走 expanded lowering 都要设 per-cut term cap + cumulative proto budget (不止 F1/F9; fixture 尺度 ~百级 term/cut ~0.1–0.3GB 不爆, 大 region 才数 GB), 或维持 compact (witness/no-good) lowering 则全 9 族安全。**(注: 早先此处写的 ~2–3K term/1.9GB/"只 F1/F9" 是 MSB bug 假数字, 已废, 见顶部块。)** 这个决策走 **N=8 parallel design** (不 cherry-pick spike code), 由用户当 phase boundary auditor 拍板 (per [[main-merger-scope-creep-bias]])。production step_8 (F1-only) 落代码前先定这个 lowering。Step 0 cheap gate 当时 8/8 PASS 但**产物已随 untracked 文件丢失** (详 [[p1-3a-design-phase]] 顶部丢失警告)。如还要再送一轮 GPT pro 外审, 现已有 **v24 终包** (sha 991c5b79, 见上)。见 [[phase-1-2-progress]] + [[design-phase-n-parallel-agents]]。

**送审 (历史口径, 若再送)**: 见下方「送审清单」, 但包要先 v23 重建。

**(2026-06-01) 命名错位 (接手第一手陷阱, 易误判 phase)**: `docs/项目说明/06` 的 **doc-P1.3A = attach spike (已 done)**、**doc-P1.3B = 真 master 集成** (= 本 memory 口径里叫的「P1.3A 主体」); CLAUDE.md 旧 "Phase 3B" 已改正为 1.3A。`step_8_apply_to_master` 仍 `NotImplementedError`。
