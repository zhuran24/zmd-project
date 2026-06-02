---
name: review-pkg-7z-strategy
description: 大 review pkg (全项目 scope, 100+ MB unzipped) 用 7z 高压 + zip 壳 + ship 7za binary 解压工具. 实测压 5%. GPT 上传只接受 zip 壳但 7z 壳内.
metadata:
  node_type: memory
  type: reference
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-23 v8 review pkg 落地. cut-only scope (v1-v7, 87 file / 0.34 MB) 不够
reviewer 看 framework 跟主流程 (main.py / benders_loop / outer_search) 关系.
用户要全项目 scope.

## Strategy

```
project root (排除 大文件 / 历史 archive)
   ↓ shutil.copy 到 /tmp/_pkg_v8/project/
project.7z  (7z -mx=9 ultra 压缩)
   ↓
zip 壳 (.zip): project.7z + tools/7za + README + COMMIT_LOG
```

实测 v8 (commit 744305d):
- 项目 unzipped 102.8 MB, 2728 file
- 7z 压缩 → 5.34 MB (5%, 比 zip default 高 ~3-5x)
- 加 7za binary 1.59 MB (Linux x64 ELF, /usr/lib/7zip/7za)
- 最终 zip 壳 6.11 MB

## 排除清单 (顶层 dir / pattern)

EXCLUDE_TOPLEVEL:
- .venv (deps 单独 ship)
- .git (太大 + reviewer 不需)
- .pytest_cache / .mypy_cache / .ruff_cache
- .artifacts (campaign 产物)
- .codex_test_logs (69 MB 历史 telemetry)
- .upstream_clones (277 MB 上游 reference)
- .claude (250 MB Claude Code session)
- _codex_archive (7 MB 历史 codex 工作区)
- node_modules

EXCLUDE_NAMES (嵌套):
- __pycache__ / .pytest_cache / .mypy_cache / .ruff_cache

EXCLUDE_PATTERNS:
- **/telemetry_samples.jsonl (各 MB)
- **/exact_campaign_state.json.*
- **/exact_campaign_telemetry.json.*
- **/cache.*.db (mypy cache binary)
- **/tree.txt (1.4 MB)
- **/*.tar.xz

EXCLUDE_FILES (per [[review-pkg-no-prompt-inside]]):
- **⚠️ 纠正 (2026-06-02 审计)**: 早先这里写"v8 排除 docs/项目说明/*.md"是**记错了**。实核 v8 (commit 744305d) `EXCLUDE_FILES` **只含一个 plan doc**: `docs/research/p3_b_design_v2_20260521/PHASE_POST_1_1_REFACTOR_PLAN.md`。**`docs/项目说明/` 从未被排除** —— 它 commit b72bc22 才建 (比 v8 晚 ~3h), v13-v22 一直入包。所以 v8 排的是那一个 plan doc, 不是项目说明。
  - **⚠️ 翻转 (2026-06-01, v22 起)**: 连那个 plan-doc 排除也**撤销**了, plan docs 改为**保留入包**当 reviewer 背景 context (讲 spike 之后的工作 = 非被审对象, priming 风险低)。v22 build 脚本 `EXCLUDE_FILES=set()`。判别仍按 factual-vs-priming (见 [[review-pkg-data-completeness]])。别再照早先那条错记录排除项目说明。

EXCLUDE prefixes:
- scripts/build_phase1_1_gpt_pro_review_v (递归打包 build script 自己)

## 解包 workflow (README 给 reviewer)

```bash
unzip -q phase1_1_gpt_pro_review_v8.zip
cd _phase1_1_pkg_v8

# 用 ship 的 7za 解 project.7z
chmod +x tools/7za
./tools/7za x project.7z
cd project

# 跑 pytest / 静态工具
.venv/bin/python -m pytest src/tests/cuts/ -q
```

跨 platform: tools/7za 是 Linux x64 ELF (dynamically linked glibc). GPT pro
Linux sandbox 直接跑. Windows reviewer 用 7-Zip official / WinRAR.

## 何时用此 strategy

- review pkg 全项目 scope (vs cut/lib-only scope, 用 v1-v7 file list 即可)
- unzipped 项目 > 50 MB
- 同时需 ship 工具 (解 7z 不是 reviewer 系统默认)

何时不需要:
- review pkg 只 单 component (cut framework / 单 lib), 文件 < 100 个, zip 够
- reviewer 系统已有 7z (但安全起见仍 ship 解压工具防 reviewer 没装)

## Refs

- `scripts/build_phase1_1_gpt_pro_review_v8.py` 实施
- `~/linwin_share/phase1_1_gpt_pro_review_v8.zip` 实际包
- [[review-pkg-no-prompt-inside]] — 包内不放 prompt + 不放主动性内容
- [[big-milestone-gpt-pro-review]] — 大节点打包 trigger
