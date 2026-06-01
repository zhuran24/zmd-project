---
name: windows-ninth-review-pending
description: "单一 living 当前交接/现状源. 2026-05-31 项目交接到 Windows. 独立九审复审 CLEAN GO, v22 spike 包已 Windows 重建两版, 等用户送 GPT pro 正式九审 → P1.3A 主体 N=8 design. 环境细节见 windows-handoff-env, 设计细节见 p1-3a-design-phase."
metadata: 
  node_type: memory
  type: project
  originSessionId: ca5783d1-e3be-4591-8cfd-4ede5ed83635
---

> **这是项目单一 living「当前 phase/交接状态」权威源** (per [[memory-currency-protocol]])。环境落点细节见 [[windows-handoff-env]] (稳定 reference), P1.3A 设计/Step0 gate 细节见 [[p1-3a-design-phase]] (设计记录)。本条是这三者里唯一的「现状真相」入口, 另两条只补细节不重述现状。

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

**下一步**: 用户送两版 zip + prompt 给 GPT pro → 若正式九审 CLEAN GO → P1.3A 主体 (真 `PoseBoolExactMaster` 接入 LBBD + 多轮收敛, verdict 里 5 项 Layer-2 risk register) 走 **N=8 parallel design** (不 cherry-pick spike code)。Step 0 cheap gate 已 8/8 PASS (详 [[p1-3a-design-phase]]), production step_8 (F1-only) 仍等正式九审 CLEAN GO 才落代码。见 [[phase-1-2-progress]] + [[design-phase-n-parallel-agents]] + [[main-merger-scope-creep-bias]] (P1.3A phase boundary 用户是唯一可信 auditor)。

**(2026-06-01) 命名错位 (接手第一手陷阱, 易误判 phase)**: `docs/项目说明/06` 的 **doc-P1.3A = attach spike (已 done)**、**doc-P1.3B = 真 master 集成** (= 本 memory 口径里叫的「P1.3A 主体」); CLAUDE.md 旧 "Phase 3B" 已改正为 1.3A。`step_8_apply_to_master` 仍 `NotImplementedError`。
