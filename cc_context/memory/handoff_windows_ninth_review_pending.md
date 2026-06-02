---
name: windows-ninth-review-pending
description: "单一 living 当前交接/现状源. 2026-05-31 交接 Windows. **2026-06-02 最新: 九审 (v22) 双回 B → v23 二次 B → v24/v25 全补丁轮; v25 已建+验+交付 (sha f245bc9, critic overall_ship=True), 等用户送 GPT 第四轮; 下一关 = P1.3A 的 F1/F9 lowering 决策 (sizing bitset bug 已确认+修, 纠正后 fixture 尺度不爆).** (slug 还叫 ninth-review-pending 但九审早完, 未改名因 inbound link 多). 环境见 windows-handoff-env, 设计见 p1-3a-design-phase."
metadata: 
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **这是项目单一 living「当前 phase/交接状态」权威源** (per [[memory-currency-protocol]])。环境落点细节见 [[windows-handoff-env]] (稳定 reference), P1.3A 设计/Step0 gate 细节见 [[p1-3a-design-phase]] (设计记录)。本条是这三者里唯一的「现状真相」入口, 另两条只补细节不重述现状。

<!-- AUTO-STATUS:BEGIN — 下面 `INSTANCE:` 槽**内**由 pre-commit stamp_living_status.py 自动 transclude (实例/分身模型, 见 [[github-backup]] / [[memory-currency-protocol]] rule#7); 别手改槽内值 -->
**自动现状标记** (可推导现状每 commit 自动刷, 结构上不可能 stale; 人写的判断散文见下方各 `##` 块):
- 最新 review 包: <!-- INSTANCE:latest_review_package -->v26 (sha `fb69415272d8…`)<!-- /INSTANCE:latest_review_package -->
- spike 分支 HEAD: `<!-- INSTANCE:spike_head -->dc3516a<!-- /INSTANCE:spike_head -->`
- CLAUDE.md Current Phase: <!-- INSTANCE:current_phase -->1.3A (cut-family LBBD master 集成)<!-- /INSTANCE:current_phase -->
- GitHub repo: <!-- INSTANCE:repo_url -->zhuran24/endfield-exact-solver<!-- /INSTANCE:repo_url -->
<!-- AUTO-STATUS:END -->

## 最新状态 (2026-06-02) — v25 已建+验+交付 (sha f245bc9), 等 GPT 第四轮; 经 v23 二次 B→v24→v25 三轮修; sizing_gate bitset bug 已确认+修

> **当前真相 (摘要)**: spike close gate 走完 v22 九审(双 B)→v23 二次 B(7 finding)→v24(修 7)→v25(再修 7, 全证据精度/工件/锁门, 非 soundness)。**v25 终包 sha `f245bc9`, 验证 workflow critic overall_ship=True, 独立 re-audit 确认 clean**, 已 SendUserFile 交付手机端 4 件 (v25 zip + deps×3), 等用户送 GPT 第四轮。真正下一关 = P1.3A 的 F1/F9 lowering 决策 (sizing 纠正后 fixture 尺度不爆, 见下方 v25 块 + [[cp-sat-no-add-lazy-constraint]] proto 预算)。下面 v23 块是中间历史。

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

**⚠️ 安全: v22 包 (已发 GPT) 泄漏 live Gemini key** — `scripts/gemini_cross_check_*.py` (10 文件) 内嵌真 key `AIzaSyC8D0a_...`, v22 build 没排除 → 已随 v22 review 包发给 GPT pro (OpenAI 现持有)。这跟 [[gemini-math-consultant]] 记的"key 留私库历史靠仓库私有保安全"不是一回事 (那防 GitHub 公开; 外发 LLM 厂商是另一暴露轴, 用户没拍过板)。v23 已排除 (secret=0)。**key 轮换 = 待用户决策** (倾向轮换: 成本低 + 外厂留存不可控; 用户之前接受私库留存风险但非外发语境)。轮换则改 Gemini key + 更新本地 10 个 gemini_cross_check 脚本即可。

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

**依赖包** (GPT 在 linux cp313 装项目复现用): `cc_context/review/deps/` 含 34 个 wheel + `deps_linux_py313.zip` 均分 3 块 (`.001/.002/.003` 各 27.86MB, 因 GPT 单次上传体积限制) + `README_deps.txt`(cat 合并 + 离线 `pip install --no-index --find-links` 命令)。**闭包验证完整**: pip resolver 离线 resolve 整个 lock(34 全 pinned) 退出码 0、无缺 transitive; 3 块重组 sha256 = 原 zip byte-exact。regenerable, gitignored 不入库。**重建命令** (下次重送审): 从 Windows 拉 Linux cp313 wheel 用 `pip download --platform manylinux*... --python-version 313 --abi cp313 --only-binary=:all:`; 闭包验证用 `pip download --no-index --find-links <wheels>` 退出码 0 = 全 transitive 齐 (不需实际安装)。

**送审清单 (v23 现行, 2026-06-02)**: ① `cc_context/review/phase1_2_spike_review_v23.zip` (faithful, 只打完整包; sha 131609a3) ② 3 个 deps 块 (`.001/.002/.003`) ③ 粘 `cc_context/review/GPT_v23复审_prompt.md` (v23 版, 直接全选粘; **不是** v22 的 `GPT九审_prompt.md` —— 那个 v22 口径已废)。2026-06-02 这 5 件已 SendUserFile 推给手机端待用户上传。(v22 的"两版独立送"对 v23 不适用, 只有 faithful。)

**基础设施** (本 session 2026-06-01 落地): GitHub 实时备份已 live(私有库 zhuran24/endfield-exact-solver, post-commit 自动 push, pre-commit 自动同步 memory, SessionEnd 兜底 WIP) + 项目结构整理(CC/审查工件归 cc_context/{memory,tools,review}, root 清爽)。详 [[github-backup]]。

**下一步** (2026-06-02 修订, 九审已回 B 后): 正式九审已跑完 (B, 修复已落, 见顶部「最新状态」), 不再是「等送审」。真正的下一关 = **P1.3A 的 lowering 决策** —— sizing gate (LSB-corrected) 把它量成带数字硬约束: **任何**族走 expanded lowering 都要设 per-cut term cap + cumulative proto budget (不止 F1/F9; fixture 尺度 ~百级 term/cut ~0.1–0.3GB 不爆, 大 region 才数 GB), 或维持 compact (witness/no-good) lowering 则全 9 族安全。**(注: 早先此处写的 ~2–3K term/1.9GB/"只 F1/F9" 是 MSB bug 假数字, 已废, 见顶部块。)** 这个决策走 **N=8 parallel design** (不 cherry-pick spike code), 由用户当 phase boundary auditor 拍板 (per [[main-merger-scope-creep-bias]])。production step_8 (F1-only) 落代码前先定这个 lowering。Step 0 cheap gate 当时 8/8 PASS 但**产物已随 untracked 文件丢失** (详 [[p1-3a-design-phase]] 顶部丢失警告)。如还要再送一轮 GPT pro 外审, 现已有 **v24 终包** (sha 991c5b79, 见上)。见 [[phase-1-2-progress]] + [[design-phase-n-parallel-agents]]。

**送审 (历史口径, 若再送)**: 见下方「送审清单」, 但包要先 v23 重建。

**(2026-06-01) 命名错位 (接手第一手陷阱, 易误判 phase)**: `docs/项目说明/06` 的 **doc-P1.3A = attach spike (已 done)**、**doc-P1.3B = 真 master 集成** (= 本 memory 口径里叫的「P1.3A 主体」); CLAUDE.md 旧 "Phase 3B" 已改正为 1.3A。`step_8_apply_to_master` 仍 `NotImplementedError`。
