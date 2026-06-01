---
name: windows-ninth-review-pending
description: "单一 living 当前交接/现状源. 2026-05-31 交接 Windows. **2026-06-02 更新: GPT pro 正式九审 (v22 faithful+clean 双版) 双双回 B (非 clean GO), 复核全实, 4 soundness 修 + sizing gate 已落 (spike a29fb44 + master af9054a), v23 待重建; 下一关 = P1.3A 的 F1/F9 lowering 决策.** (slug 还叫 ninth-review-pending 但九审已完, 未改名因 inbound link 多). 环境见 windows-handoff-env, 设计见 p1-3a-design-phase."
metadata: 
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **这是项目单一 living「当前 phase/交接状态」权威源** (per [[memory-currency-protocol]])。环境落点细节见 [[windows-handoff-env]] (稳定 reference), P1.3A 设计/Step0 gate 细节见 [[p1-3a-design-phase]] (设计记录)。本条是这三者里唯一的「现状真相」入口, 另两条只补细节不重述现状。

## 最新状态 (2026-06-02) — 九审已回 B, 修复已落, v23 待重建

GPT pro 正式九审跑了 (用户把 v22 **faithful + clean 两版独立**送审, 两份报告都贴回主代理)。**双双判 B (未 clean close)**, 不是之前本地预审的 CLEAN GO —— 以正式九审为准 (per [[memory-currency-protocol]] §5: judgment 级结论由做判断的主体定, 正式九审 > 本地预审)。两份报告 finding 主代理**逐条对真代码+真数据复核, 全属实** (base64 不 validate / 36-unknown 静默 remap / salted hash / schema_err 不进门禁 / Finding 5 #2 sizing overclaim)。两份质量对比: 完整版那次更深 (36-unknown 那条), 干净版更广 (独占 3 条), 但**单跑各一次无法把"包差异"和"GPT run-to-run 噪声"分离** (只有 README 不同, 取并集才对, 见 [[external-review-reproducibility]])。

**已落修复 (2026-06-02):**
- spike `a29fb44` (`[SPIKE-V23-PATCH]`): toy_translator 4 修 (validate=True + blake2b stable hash + remap telemetry + schema_err 门禁), micro-probe 9→12 case 全 PASS; verdict.md Finding 5 #2 `YES→PARTIAL` + 第九审修正章 + Layer-2 risk #6。
- master `af9054a`: sizing cheap gate 归档 `docs/research/p1_2_spike_sizing_gate_20260601/` (RESULTS.md + sizing_gate.py)。
- **核心 sizing 结论**: cut body master 约束大小是 **~1000x lowering 设计变量**, 100K sizing 有界便宜 (~1–40 MB), **唯一** blow-up = F1 region_capacity / F9 density_envelope 的**大池子** (manufacturing ~17952 pose) 容量 cut 按展开式 lower (每条 ~2–3K term → ~1.9 GB)。其余 7 族任意 lower 都安全。

**v22 包已 stale** (verdict + spike code 已改); 下次送审或 P1.3A 前需 **v23 重建** (build 脚本复用 `cc_context/review/build_v22_*win.py`, 换 spike HEAD = a29fb44)。

---

2026-05-31 zhuran24 → 接手者 (Windows 11) 交接完成。

**环境** (摘要, 详 [[windows-handoff-env]]): 仓库现在仓库根 `D:\追光\zmd` (2026-05-31 从旧 `D:\追光\zmd\zmd` 上移一层)。venv = **Windows 布局** `.venv\Scripts\python.exe` (Python 3.13.13 + ortools 9.15.6755)。CC memory **canonical slug = `D-----zmd`** (旧 `D-----zmd-zmd` 副本因迁移前 slug 已 obsolete, 留作备份不再写)。多数 Linux 命令 (.venv/bin / cachyos_setup / pacman_freeze / systemd / temp_logger / LD_PRELOAD) 在本机**不适用**, 改 `.venv\Scripts\python.exe`。

**九审门禁** (接手第一件事): spike close gate (v22, GO_WITH_MINOR) 在等 GPT 正式九审。用户拍板「九审当硬门禁先闭环 + 再加一道 GPT pro 外审」。本 session 主代理做了**独立九审复审 = CLEAN GO** (本地复审, 非 GPT 输出):
- 真 soundness 守卫: F7/F8 `_validate_facility_cells_match_pose_registry` 回归 + `test_oracle_scope_digest` = 3/3 PASS (v12 那两个 BLOCKER 假 cert 攻击早在 master `68fa7f0`/`a3414ee` 修+带回归)
- 414 cuts test PASS (3.86s)
- v22 spike harness `toy_translator` F3 malformed fail-closed: 读逻辑核过 (`_decode_cert_b64` isinstance(dict) guard + F3 family 移出 payload-not-None 块) + 9-case 自测脚本实跑 9/9 PASS
- verdict.md 诚实 (Sizing-only, 5 项 Layer-2 风险明确 defer, 无 overclaim)

**已交付物** (在 `cc_context/review/`, 2026-06-01 结构整理移入已 tracked; faithful + clean 两版 per [[review-pkg-no-prompt-inside]]):
- `phase1_2_spike_review_v22.zip` (faithful, sha256 `a29f017a379d0774f9fc72d321f0d3cd95ee783ae3be1484b7fd2ceda8a4a29a`) + `phase1_2_spike_review_v22_clean.zip` (clean, 删 reviewer-priming) — v22 包 Windows 重建版, 单层 zip (原 7z-in-zip 双层换掉, 本机无 7z)。独立验过: build 脚本 0 泄漏 / 无 .git .venv / 无 prompt 混入 / code_context spike 11 文件 / candidate_placements 53.6MB 字节完整 / 无 priming。
- build 脚本 `build_v22_win.py` (faithful) + `build_v22_clean_win.py` (clean) 在 `cc_context/review/`, **可复用** portable builder: import 原 `scripts/build_phase1_2_spike_review_v22.py` 复用全部 README/文件清单/helper, 只换打包机制。修了 2 个 Windows 移植 bug: ① git show text-mode 强制 `encoding=utf-8` (GBK 呛中文 commit msg) ② `should_skip` 喂 `PurePosixPath` (Windows `\` 导致初版漏 21 个进包)。
- `GPT九审_prompt.md` — chat 单独给的审查 prompt (7-section + 不可达 armor, **不进 zip**)。

**打包/外审操作规范**: 整套走 [[index-packaging-cluster]] hub。

**依赖包** (GPT 在 linux cp313 装项目复现用): `cc_context/review/deps/` 含 34 个 wheel + `deps_linux_py313.zip` 均分 3 块 (`.001/.002/.003` 各 27.86MB, 因 GPT 单次上传体积限制) + `README_deps.txt`(cat 合并 + 离线 `pip install --no-index --find-links` 命令)。**闭包验证完整**: pip resolver 离线 resolve 整个 lock(34 全 pinned) 退出码 0、无缺 transitive; 3 块重组 sha256 = 原 zip byte-exact。regenerable, gitignored 不入库。**重建命令** (下次重送审): 从 Windows 拉 Linux cp313 wheel 用 `pip download --platform manylinux*... --python-version 313 --abi cp313 --only-binary=:all:`; 闭包验证用 `pip download --no-index --find-links <wheels>` 退出码 0 = 全 transitive 齐 (不需实际安装)。

**送审清单** (每个 GPT pro 窗口): ① review 包(`cc_context/review/` 的 faithful `phase1_2_spike_review_v22.zip` 或 clean `_clean.zip`) ② 3 个 deps 块 ③ 粘 `cc_context/review/GPT九审_prompt.md`(纯净, 直接全选粘)。两版**独立**送, 结论交叉比对。

**基础设施** (本 session 2026-06-01 落地): GitHub 实时备份已 live(私有库 zhuran24/endfield-exact-solver, post-commit 自动 push, pre-commit 自动同步 memory, SessionEnd 兜底 WIP) + 项目结构整理(CC/审查工件归 cc_context/{memory,tools,review}, root 清爽)。详 [[github-backup]]。

**下一步** (2026-06-02 修订, 九审已回 B 后): 正式九审已跑完 (B, 修复已落, 见顶部「最新状态」), 不再是「等送审」。真正的下一关 = **P1.3A 的 F1/F9 lowering 决策** —— sizing gate 把它量成带数字硬约束 (F1/F9 大池子展开 ~2–3K term/cut → ~1.9 GB@100K), P1.3A lowering 必须二选一: (a) witness 紧凑 no-good, 或 (b) 大池子展开容量 cut 设上界。这个决策走 **N=8 parallel design** (不 cherry-pick spike code), 由用户当 phase boundary auditor 拍板 (per [[main-merger-scope-creep-bias]])。production step_8 (F1-only) 落代码前先定这个 lowering。Step 0 cheap gate 已 8/8 PASS (详 [[p1-3a-design-phase]])。如还要再送一轮 GPT pro 外审, 先 **v23 重建** (v22 已 stale)。见 [[phase-1-2-progress]] + [[design-phase-n-parallel-agents]]。

**送审 (历史口径, 若再送)**: 见下方「送审清单」, 但包要先 v23 重建。

**(2026-06-01) 命名错位 (接手第一手陷阱, 易误判 phase)**: `docs/项目说明/06` 的 **doc-P1.3A = attach spike (已 done)**、**doc-P1.3B = 真 master 集成** (= 本 memory 口径里叫的「P1.3A 主体」); CLAUDE.md 旧 "Phase 3B" 已改正为 1.3A。`step_8_apply_to_master` 仍 `NotImplementedError`。
